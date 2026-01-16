import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date
import os

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

# --- 👈 左側：サイドバー（見た目固定） ---
st.sidebar.title("🎮 操作パネル")

# 1. 過去データの参照範囲
st.sidebar.header("1. 過去データの参照範囲")
range_type = st.sidebar.radio("指定方法", ["日付範囲で指定", "季節で指定"])

# DBの「年」が「20」等の2桁なので、それに合わせるための処理
filter_query = ""
if range_type == "日付範囲で指定":
    start_date = st.sidebar.date_input("開始日", date(2020, 1, 1))
    end_date = st.sidebar.date_input("終了日", date(2025, 12, 31))
    # 年を2桁に変換して検索
    s_yr, e_yr = str(start_date.year)[2:], str(end_date.year)[2:]
    filter_query = f"AND 年 BETWEEN {s_yr} AND {e_yr}"
else:
    season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
    years_back = st.sidebar.slider("過去何年分を対象にするか", 1, 6, 3)
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    # 26年(2026)から遡る
    start_year_2digit = 26 - years_back
    filter_query = f"AND 年 >= {start_year_2digit} AND 月 IN ({m_dict[season]})"

# 2. レース条件
st.sidebar.header("2. レース条件")
baba_input = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
# DB表記に変換 (ダート -> ダ)
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
st.sidebar.header("4. 期待値シミュレーター")

# --- 🔍 データ取得 ---
def load_filtered_data(b_val, d_val, extra_sql, t_sql, c_sql):
    conn = sqlite3.connect(DB_FILE)
    query = f"""
    SELECT * FROM race_results 
    WHERE 場所 LIKE '%東京%' 
    AND 馬場 = '{b_val}' 
    AND 距離 = {d_val} 
    {extra_sql} {t_sql} {c_sql}
    """
    try:
        df = pd.read_sql(query, conn)
        return df, query
    except Exception as e:
        return pd.DataFrame(), str(e)
    finally:
        conn.close()

if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

df, sql_debug = load_filtered_data(baba_val, dist, filter_query, time_sql, class_sql)

if not df.empty:
    st.success(f"✅ {len(df)}件のデータを抽出しました")
    st.dataframe(df)
else:
    st.warning("⚠️ 条件に合うデータが0件です。")
    # デバッグ用にSQLを表示（不要なら後で消せます）
    st.code(sql_debug)
