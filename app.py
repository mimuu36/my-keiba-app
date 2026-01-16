import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib

# --- 🔒 簡易パスワード認証機能 ---
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
    else:
        return True

if not check_password():
    st.stop() # 認証が通るまでこれ以降のコードを実行しない

# --- 🐎 ここからメインの分析アプリ ---
st.title("🏇 東京競馬分析 (本番環境)")

@st.cache_data
def get_data(baba, dist, season):
    conn = sqlite3.connect('keiba_data.db')
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba}%' AND 距離={dist} AND 月 IN ({m_dict[season]})"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

baba = st.sidebar.selectbox("馬場", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)
season = st.sidebar.selectbox("季節", ["冬 (1-2月)", "春 (4-6月)", "秋 (10-11月)"])

if st.button("📊 分析実行"):
    df = get_data(baba, dist, season)
    if not df.empty:
        st.success(f"{len(df)} 件のデータを解析")
        fig, ax = plt.subplots()
        sns.countplot(x='馬番', data=df[df['確定着順']<=3], palette='Blues_r', ax=ax)
        st.pyplot(fig)
    else:
        st.warning("データがありません")
