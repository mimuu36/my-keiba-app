import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date
import os
import matplotlib.colors as mcolors
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MaxNLocator

# --- 🔒 認証機能 ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["MY_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("パスワード入力", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("パスワード入力", type="password", on_change=password_entered, key="password")
        st.error("認証失敗")
        return False
    return True

if not check_password():
    st.stop()

st.set_page_config(page_title="東京競馬分析WS", layout="wide")
DB_FILE = 'keiba_data.db'

# --- 👈 左側：操作パネル (維持) ---
st.sidebar.title("🎮 操作パネル")
st.sidebar.header("1. 過去データの参照範囲")
range_type = st.sidebar.radio("指定方法", ["日付範囲で指定", "季節で指定"])

filter_query = ""
if range_type == "日付範囲で指定":
    start_date = st.sidebar.date_input("開始日", date(2020, 1, 1))
    end_date = st.sidebar.date_input("終了日", date(2025, 12, 31))
    s_yr, e_yr = str(start_date.year)[2:], str(end_date.year)[2:]
    filter_query = f"AND 年 BETWEEN {s_yr} AND {e_yr}"
else:
    season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
    years_back = st.sidebar.slider("過去何年分を対象にするか", 1, 6, 3)
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    start_year_2digit = 26 - years_back
    filter_query = f"AND 年 >= {start_year_2digit} AND 月 IN ({m_dict[season]})"

st.sidebar.header("2. レース条件")
baba_input = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
baba_val = "ダ" if baba_input == "ダート" else "芝"
baba_condition = st.sidebar.multiselect("馬場状態", ["良", "稍重", "重", "不良"], default=["良", "稍重", "重", "不良"])
cond_sql = ""
if baba_condition:
    cond_str = "','".join(baba_condition)
    cond_sql = f"AND 馬場状態 IN ('{cond_str}')"
dist = st.sidebar.selectbox("距離(m)", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)
race_class = st.sidebar.selectbox("レースクラス", ["全クラス", "新馬・未勝利", "1勝クラス", "2勝・3勝クラス", "オープン・重賞"])

time_mode = st.sidebar.radio("時間の指定方法", ["時間帯で選ぶ", "レース番号で選ぶ"])
time_sql = ""
if time_mode == "時間帯で選ぶ":
    tz = st.sidebar.selectbox("時間帯区分", ["全レース", "午前 (1R～4R)", "午後 (5R～12R)"])
    if tz == "午前 (1R～4R)":
        time_sql = "AND CAST(レース番号 AS INTEGER) <= 4"
    elif tz == "午後 (5R～12R)":
        time_sql = "AND CAST(レース番号 AS INTEGER) >= 5"
else:
    target_r = st.sidebar.number_input("レース番号(R)", 1, 12, 11)
    time_sql = f"AND CAST(レース番号 AS INTEGER) = {target_r}"

class_sql = ""
if race_class == "新馬・未勝利":
    class_sql = "AND (略レース名 LIKE '%新馬%' OR 略レース名 LIKE '%未勝利%')"
elif race_class == "1勝クラス":
    class_sql = "AND (略レース名 LIKE '%1勝%' OR 略レース名 LIKE '%500万%')"
elif race_class == "2勝・3勝クラス":
    class_sql = "AND (略レース名 LIKE '%2勝%' OR 略レース名 LIKE '%3勝%' OR 略レース名 LIKE '%1000万%' OR 略レース名 LIKE '%1600万%')"
elif race_class == "オープン・重賞":
    class_sql = "AND (略レース名 LIKE '%オープン%' OR 略レース名 LIKE '%OP%' OR 略レース名 LIKE '%重賞%' OR 略レース名 LIKE '%G%')"

if st.sidebar.button("【4大指標 統計を確認する】"):
    st.session_state.mode = "stats"

st.sidebar.markdown("---")
st.sidebar.header("3. 気になる馬情報")
target_horse_num = st.sidebar.number_input("気になる馬の馬番", 1, 18, 1)
highlight_on = st.sidebar.toggle("強調表示をONにする", value=False)
st.sidebar.header("4. 期待値シミュレーター")

# --- 🔍 統計計算関数 ---
def calc_stats(df, group_col):
    res = df.groupby(group_col).agg(
        出走回数=(group_col, 'count'),
        勝数=('確定着順', lambda x: (x == 1).sum()),
        複勝数=('確定着順', lambda x: (x <= 3).sum()),
        単勝回収計=('単勝オッズ', lambda x: df.loc[x.index[df.loc[x.index, '確定着順'] == 1], '単勝オッズ'].sum() * 100)
    ).reset_index()
    res['勝率'] = (res['勝数'] / res['出走回数'] * 100).round(1)
    res['複勝率'] = (res['複勝数'] / res['出走回数'] * 100).round(1)
    res['単勝回収率'] = (res['単勝回収計'] / (res['出走回数'] * 100)).round(1)
    return res

def add_smart_labels(ax, df_stats, col_name, val_name, suffix="%"):
    for i, p in enumerate(ax.patches):
        height = p.get_height()
        if height >= 0 and not pd.isna(height):
            count = df_stats.iloc[i]['出走回数']
            va = 'bottom' if height < 5 else 'top'
            y_pos = height + 0.3 if height < 5 else height - 0.3
            label_text = f'{height:.1f}{suffix}\n({int(count)})'
            txt = ax.annotate(label_text, (p.get_x() + p.get_width() / 2., y_pos), ha='center', va=va, color='black', fontweight='bold', fontsize=8)
            txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground='white')])

# --- 👉 右側：メイン表示エリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

conn = sqlite3.connect(DB_FILE)
query = f"SELECT * FROM race_results WHERE 場所 LIKE '%東京%' AND 馬場 = '{baba_val}' {cond_sql} AND 距離 = {dist} {filter_query} {time_sql} {class_sql}"
df = pd.read_sql(query, conn)
conn.close()

if df.empty:
    st.warning("⚠️ 条件に合うデータが0件です。")
    st.stop()

st.title(f"🚀 期待値分析（{len(df)}件）")
tab1, tab2, tab3, tab4 = st.tabs(["🔢 馬番別", "🏇 騎手別", "🎯 人気信頼度", "🧬 父馬別"])

# tab1, tab2 描画（内容は維持）
with tab1:
    st.subheader("馬番期待値")
    s1 = calc_stats(df, '馬番')
    if not s1.empty:
        avg_f = (df['確定着順'] <= 3).mean() * 100
        v_max = s1['複勝率'].max()
        s1_sorted = s1.sort_values('複勝率', ascending=False)
        top_5_gate = s1_sorted.head(5)['馬番'].tolist()
        colors = ['#E74C3C' if g == target_horse_num and highlight_on else ("#E74C3C" if g == top_5_gate[0] else "#E67E22" if g in top_5_gate[1:3] else "#F1C40F" if g in top_5_gate[3:5] else "#87CEEB") for g in s1['馬番']]
        if highlight_on: colors = ['#E74C3C' if x == target_horse_num else '#E5E7E9' for x in s1['馬番']]
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.barplot(x='馬番', y='複勝率', data=s1, ax=ax, palette=colors, edgecolor='white', linewidth=0.5)
        ax.axhline(avg_f, color='blue', linestyle='--', alpha=0.6, linewidth=1.5)
        ax.set_ylabel("複勝率 (%)")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        if v_max > 0: ax.set_ylim(0, v_max * 1.35)
        add_smart_labels(ax, s1, '馬番', '複勝率')
        st.pyplot(fig)
    else: st.write("データなし")

with tab2:
    st.subheader("騎手別：勝率（上位10名）")
    s2_all = calc_stats(df, '騎手')
    s2 = s2_all[s2_all['出走回数'] >= 5].sort_values('勝率', ascending=False).head(10)
    if not s2.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.barplot(x='騎手', y='勝率', data=s2, ax=ax, palette="Blues_r", order=s2['騎手'], edgecolor='white')
        ax.set_ylabel("勝率 (%)")
        v_max_s2 = s2['勝率'].max()
        if v_max_s2 > 0: ax.set_ylim(0, v_max_s2 * 1.35)
        add_smart_labels(ax, s2, '騎手', '勝率')
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else: st.info("出走回数5回以上の騎手データなし")

# --- tab3: 人気 & 波乱度 (定義テーブル追加) ---
with tab3:
    st.subheader("人気別：複勝率（信頼度）")
    s3 = calc_stats(df, '人気')
    s3 = s3[s3['人気'] <= 10].sort_values('人気')
    if not s3.empty:
        fig1, ax1 = plt.subplots(figsize=(10, 4))
        sns.barplot(x='人気', y='複勝率', data=s3, ax=ax1, palette="Greens_r", edgecolor='white')
        ax1.set_ylabel("複勝率 (%)")
        ax1.set_xlabel("人気順位")
        ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
        v_max_s3 = s3['複勝率'].max()
        if v_max_s3 > 0: ax1.set_ylim(0, v_max_s3 * 1.35)
        add_smart_labels(ax1, s3, '人気', '複勝率')
        st.pyplot(fig1)

    st.markdown("---")
    st.subheader("📉 レース波乱度分布（決着パターン）")
    
    # 波乱度計算
    race_results = df[df['確定着順'] <= 3].copy()
    r_groups = race_results.groupby(['年','月','日','レース番号'])['人気'].apply(list)
    dist_counts = {"人気決着": 0, "上位決着": 0, "穴注意": 0, "大波乱!!": 0}
    for ranks in r_groups:
        if len(ranks) < 3: continue
        ranks.sort()
        r1, r2, r3 = ranks[0], ranks[1], ranks[2]
        if r3 <= 3: dist_counts["人気決着"] += 1
        elif r3 <= 6: dist_counts["上位決着"] += 1
        elif r2 <= 5 and r3 >= 6: dist_counts["穴注意"] += 1
        else: dist_counts["大波乱!!"] += 1
    
    if sum(dist_counts.values()) > 0:
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        colors_pie = ["#2ECC71", "#3498DB", "#F1C40F", "#E74C3C"]
        ax2.pie(list(dist_counts.values()), labels=list(dist_counts.keys()), autopct='%1.1f%%', startangle=90, colors=colors_pie, wedgeprops={'edgecolor': 'white', 'linewidth': 2}, textprops={'fontweight': 'bold'})
        ax2.axis('equal') 
        st.pyplot(fig2)

        # 🛠️ 区分定義の補足テーブル
        st.markdown("#### 📝 区分定義（1着〜3着の顔ぶれ）")
        st.table(pd.DataFrame({
            "区分": ["人気決着", "上位決着", "穴注意", "大波乱!!"],
            "内容": [
                "3頭とも1〜3番人気以内",
                "3頭とも1〜6番人気以内（人気決着は除く）",
                "1〜5番人気が2頭 ＋ 6番人気以下が1頭",
                "6番人気以下が2頭以上、または1〜5番人気が1頭以下"
            ]
        }))
    else:
        st.write("波乱度を計算するための十分なレースデータがありません。")

with tab4:
    st.subheader("父馬別：単勝回収率上位10名")
    s4_all = calc_stats(df, '父馬名')
    s4 = s4_all[s4_all['出走回数'] >= 3].sort_values('単勝回収率', ascending=False).head(10)
    if not s4.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.barplot(x='父馬名', y='単勝回収率', data=s4, ax=ax, palette="YlOrBr_r", order=s4['父馬名'], edgecolor='white')
        ax.axhline(100, color='red', linestyle='--', alpha=0.5)
        ax.set_ylabel("単勝回収率 (%)")
        v_max_s4 = s4['単勝回収率'].max()
        if v_max_s4 > 0: ax.set_ylim(0, v_max_s4 * 1.35)
        add_smart_labels(ax, s4, '父馬名', '単勝回収率')
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else: st.info("出走回数3回以上の父馬データなし")
