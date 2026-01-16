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
        st.text_input("パスワードを入力してください", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("パスワードを入力してください", type="password", on_change=password_entered, key="password")
        st.error("😕 パスワードが違います")
        return False
    return True

if not check_password():
    st.stop()

# --- 🐎 本格分析機能（エラー対策版） ---
st.set_page_config(page_title="東京競馬分析WS", layout="wide")
st.title("🏇 東京競馬分析ワークステーション")

@st.cache_data
def load_data(baba, dist, season):
    conn = sqlite3.connect('keiba_data.db')
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    # 列名を気にせず一旦全部読み込む
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba}%' AND 距離={dist} AND 月 IN ({m_dict[season]})"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# サイドバー設定
st.sidebar.header("分析条件")
baba = st.sidebar.selectbox("馬場", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)
season = st.sidebar.selectbox("季節", ["冬 (1-2月)", "春 (4-6月)", "秋 (10-11月)"])

df = load_data(baba, dist, season)

if not df.empty:
    # --- 列名のゆらぎを吸収する処理 ---
    # 'レースID' がなければ 'RaceID' を探す、といった処理
    id_col = 'レースID' if 'レースID' in df.columns else ('RaceID' if 'RaceID' in df.columns else df.columns[0])
    chakujun_col = '確定着順' if '確定着順' in df.columns else ('着順' if '着順' in df.columns else 'result')
    ninki_col = '人気' if '人気' in df.columns else 'popularity'
    waku_col = '枠番' if '枠番' in df.columns else 'bracket'

    total_races = df[id_col].nunique()
    st.info(f"対象データ: {total_races} レース / {len(df)} 件")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 枠順別・複勝率")
        if waku_col in df.columns:
            waku_stats = df.groupby(waku_col)[chakujun_col].apply(lambda x: (pd.to_numeric(x, errors='coerce') <= 3).mean() * 100)
            fig, ax = plt.subplots()
            sns.barplot(x=waku_stats.index, y=waku_stats.values, palette="viridis", ax=ax)
            ax.set_ylabel("複勝率 (%)")
            st.pyplot(fig)

    with col2:
        st.subheader("🎯 人気別・複勝率")
        if ninki_col in df.columns:
            pop_stats = df.groupby(ninki_col)[chakujun_col].apply(lambda x: (pd.to_numeric(x, errors='coerce') <= 3).mean() * 100).head(10)
            fig, ax = plt.subplots()
            sns.lineplot(x=pop_stats.index, y=pop_stats.values, marker='o', color='red', ax=ax)
            ax.set_xticks(range(1, min(11, len(pop_stats)+1)))
            st.pyplot(fig)

    st.subheader("📑 詳細データ（着順上位）")
    st.dataframe(df.head(50))
else:
    st.warning("条件に合うデータがありません。")
