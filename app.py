import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date

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
st.set_page_config(page_title="東京競馬分析WS", layout="wide")

# --- 👈 左側：サイドバー ---
st.sidebar.title("🎮 操作パネル")

# 1. 過去データの参照範囲
st.sidebar.header("1. 過去データの参照範囲")
range_type = st.sidebar.radio("指定方法", ["日付範囲で指定", "季節で指定"])

# SQLのWHERE句を組み立てるための変数
filter_query = ""

if range_type == "日付範囲で指定":
    start_date = st.sidebar.date_input("開始日", date(2020, 1, 1))
    end_date = st.sidebar.date_input("終了日", date(2025, 12, 31))
    # 文字列として安全にSQLに組み込む
    filter_query = f"AND 日付 >= '{start_date}' AND 日付 <= '{end_date}'"
else:
    season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    filter_query = f"AND 月 IN ({m_dict[season]})"

# 2. レース条件
st.sidebar.header("2. レース条件")
baba = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離(m)", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)

if st.sidebar.button("【4大指標 統計を確認する】"):
    st.session_state.mode = "stats"

# 3, 4の枠組み
st.sidebar.markdown("---")
st.sidebar.header("3. 気になる馬情報")
st.sidebar.header("4. 期待値シミュレーター")

# --- データ読み込み関数 (エラー対策強化) ---
def load_filtered_data(baba_val, dist_val, extra_sql):
    conn = sqlite3.connect('keiba_data.db')
    # SQL文を一行で安全に組み立て
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba_val}%' AND 距離={dist_val} {extra_sql}"
    try:
        df = pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"SQLエラーが発生しました: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

# --- 👉 右側：メイン表示エリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

# フィルタリングしてデータ取得
df = load_filtered_data(baba, dist, filter_query)

if not df.empty:
    st.success(f"✅ {len(df)}件のデータを抽出しました")
    st.dataframe(df.head(50))
else:
    st.warning("⚠️ 条件に合うデータが0件です。範囲を広げてみてください。")
