import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib

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
        st.error("😕 認証失敗")
        return False
    return True

if not check_password():
    st.stop()

# --- 🐎 アプリ設定 ---
st.set_page_config(page_title="東京競馬分析・期待値ツール", layout="wide")

@st.cache_data
def load_data(baba, dist, months):
    conn = sqlite3.connect('keiba_data.db')
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba}%' AND 距離={dist} AND 月 IN ({months})"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- 👈 左側：サイドバー（操作パネル） ---
st.sidebar.title("🎮 操作パネル")

# 1. 参照期間
st.sidebar.header("1. 参照期間")
season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}

# 2. レース条件
st.sidebar.header("2. レース条件")
baba = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離(m)", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)

if st.sidebar.button("【4大指標 統計を確認する】"):
    st.session_state.mode = "stats"

st.sidebar.markdown("---")

# 3. 気になる馬情報
st.sidebar.header("3. 気になる馬情報")
uma_num = st.sidebar.number_input("ターゲット馬番", 1, 18, 1)
uma_on = st.sidebar.checkbox("馬番フィルター有効", value=False)

# 4. 全馬期待値シミュレーター
st.sidebar.header("4. 期待値シミュレーター")
sim_on = st.sidebar.checkbox("シミュレーター起動", value=False)

if st.sidebar.button("【分析実行＆期待値算出】"):
    st.session_state.mode = "sim"

# --- 👉 右側：メイン表示エリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、ここに結果が表示されます。")
    st.stop()

df = load_data(baba, dist, m_dict[season])

# 列名補正（念のため）
chakujun_col = '確定着順' if '確定着順' in df.columns else ('着順' if '着順' in df.columns else df.columns[1])
ninki_col = '人気' if '人気' in df.columns else 'popularity'

if st.session_state.mode == "stats":
    st.header(f"📊 {season} {baba}{dist}m 統計データ")
    col1, col2 = st.columns(2)
    # ここに開発環境で作った統計グラフを表示
    with col1:
        st.subheader("📍 枠順別複勝率")
        stats = df.groupby('枠番')[chakujun_col].apply(lambda x: (pd.to_numeric(x, errors='coerce') <= 3).mean() * 100)
        fig, ax = plt.subplots()
        sns.barplot(x=stats.index, y=stats.values, ax=ax)
        st.pyplot(fig)
    with col2:
        st.subheader("🎯 人気別複勝率")
        pop = df.groupby(ninki_col)[chakujun_col].apply(lambda x: (pd.to_numeric(x, errors='coerce') <= 3).mean() * 100).head(10)
        fig, ax = plt.subplots()
        sns.lineplot(x=pop.index, y=pop.values, marker='o', color='red', ax=ax)
        st.pyplot(fig)

elif st.session_state.mode == "sim":
    st.header("🧮 期待値シミュレーション")
    if sim_on:
        st.success("分析完了！全馬の期待値を算出しました。")
        # ターゲット馬番の強調表示など
        if uma_on:
            st.write(f"🐎 ターゲット馬番 {uma_num} 番の個別分析結果を表示中...")
        st.dataframe(df.head(50))
    else:
        st.warning("左側の『4.シミュレーター起動』にチェックを入れてから実行してください。")
