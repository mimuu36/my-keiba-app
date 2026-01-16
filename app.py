import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date
import os
import matplotlib.colors as mcolors

# --- 🔒 認証機能 (維持) ---
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

# --- 👈 左側：操作パネル (完全固定) ---
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

def add_labels_inside(ax, suffix="%"):
    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(f'{height:.1f}{suffix}', 
                        (p.get_x() + p.get_width() / 2., height / 2), 
                        ha='center', va='center', 
                        color='white', fontweight='bold', fontsize=9)

# --- 👉 右側：メイン表示エリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

conn = sqlite3.connect(DB_FILE)
query = f"SELECT * FROM race_results WHERE 場所 LIKE '%東京%' AND 馬場 = '{baba_val}' AND 距離 = {dist} {filter_query} {time_sql} {class_sql}"
df = pd.read_sql(query, conn)
conn.close()

if df.empty:
    st.warning("⚠️ 条件に合うデータが0件です。")
    st.stop()

st.title(f"🚀 期待値分析（{len(df)}件）")

tab1, tab2, tab3, tab4 = st.tabs(["🔢 馬番別", "🏇 騎手別", "🎯 人気信頼度", "🧬 父馬別"])

with tab1:
    st.subheader("馬番期待値")
    s1 = calc_stats(df, '馬番')
    avg_fukusho = (df['確定着順'] <= 3).mean() * 100
    
    # --- 🎨 期待値条件による色分け ---
    high_cmap = mcolors.LinearSegmentedColormap.from_list("high", ["#F1C40F", "#E67E22", "#E74C3C"]) # 黄 -> 橙 -> 赤
    
    colors = []
    if highlight_on:
        colors = ['#E74C3C' if x == target_horse_num else '#DCDCDC' for x in s1['馬番']]
    else:
        # 平均以上のデータの中での正規化用
        high_vals = s1[s1['複勝率'] >= avg_fukusho]['複勝率']
        v_min = high_vals.min() if not high_vals.empty else avg_fukusho
        v_max = high_vals.max() if not high_vals.empty else avg_fukusho + 1

        for val in s1['複勝率']:
            if val >= avg_fukusho:
                # 平均以上のものはグラデーション
                ratio = (val - v_min) / (v_max - v_min) if v_max != v_min else 1.0
                colors.append(high_cmap(ratio))
            else:
                # 平均以下のものは一律で青
                colors.append("#3498DB")

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(x='馬番', y='複勝率', data=s1, ax=ax, palette=colors)
    ax.axhline(avg_fukusho, color='blue', linestyle='--', label='全体平均')
    ax.set_ylabel("複勝率 (%)")
    add_labels_inside(ax)
    st.pyplot(fig)
    
    target_row = s1.sort_values('複勝率', ascending=False).iloc[0]
    st.markdown(f"💡 **この条件だと {int(target_row['馬番'])}番（{target_row['複勝率']}%）が狙い！** (全体平均: {avg_fukusho:.1f}%)")

with tab2:
    st.subheader("騎手別：勝率（上位10名）")
    s2 = calc_stats(df, '騎手')
    s2 = s2[s2['出走回数'] >= 5].sort_values('勝率', ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(x='騎手', y='勝率', data=s2, ax=ax, palette="Blues_r", order=s2['騎手'])
    ax.set_ylabel("勝率 (%)")
    add_labels_inside(ax)
    plt.xticks(rotation=45)
    st.pyplot(fig)

with tab3:
    st.subheader("人気別：複勝率（信頼度）")
    s3 = calc_stats(df, '人気')
    s3 = s3[s3['人気'] <= 10].sort_values('人気')
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(x='人気', y='複勝率', data=s3, ax=ax, palette="Greens_r")
    ax.set_ylabel("複勝率 (%)")
    add_labels_inside(ax)
    st.pyplot(fig)

with tab4:
    st.subheader("父馬別：単勝回収率（上位10名）")
    s4 = calc_stats(df, '父馬名')
    s4 = s4[s4['出走回数'] >= 3].sort_values('単勝回収率', ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(x='父馬名', y='単勝回収率', data=s4, ax=ax, palette="YlOrBr_r", order=s4['父馬名'])
    ax.axhline(100, color='red', linestyle='--')
    ax.set_ylabel("単勝回収率 (%)")
    add_labels_inside(ax)
    plt.xticks(rotation=45)
    st.pyplot(fig)
    
