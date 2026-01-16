import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date

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
        st.error("😕 認証失敗")
        return False
    return True

if not check_password():
    st.stop()

# --- 🐎 アプリ設定 ---
st.set_page_config(page_title="東京競馬分析WS", layout="wide")

# --- 👈 左側：サイドバー（操作パネル） ---
st.sidebar.title("🎮 操作パネル")

# 1. 過去データの参照範囲 (ここを修正)
st.sidebar.header("1. 過去データの参照範囲")
range_type = st.sidebar.radio("指定方法", ["季節で指定", "日付範囲で指定"])

months_query = ""
if range_type == "季節で指定":
    season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    months_query = f"AND 月 IN ({m_dict[season]})"
else:
    start_date = st.sidebar.date_input("開始日", date(2020, 1, 1))
    end_date = st.sidebar.date_input("終了日", date(2025, 12, 31))
    # 日付指定の場合はSQLのWHERE句を日付用に作る
    months_query = f"AND 日付 BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"

# 2. レース条件 (見出しのみ維持)
st.sidebar.header("2. レース条件")
baba = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離(m)", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)

if st.sidebar.button("【4大指標 統計を確認する】"):
    st.session_state.mode = "stats"

# --- データ読み込み関数 ---
def load_filtered_data(baba, dist, extra_query):
    conn = sqlite3.connect('keiba_data.db')
    # extra_queryに日付または季節の条件が入る
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba}%' AND 距離={dist} {extra_query}"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- 👉 右側：メイン表示エリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

df = load_filtered_data(baba, dist, months_query)

if not df.empty:
    st.write(f"### 📊 分析結果 ({len(df)}件のデータ)")
    st.dataframe(df.head(10))
else:
    st.warning("⚠️ 該当データがありません。範囲を変えてみてください。")
