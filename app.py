import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib
from datetime import date
import os

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
DB_FILE = 'keiba_data.db'

def get_real_columns():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT * FROM race_results LIMIT 1")
    cols = [description[0] for description in cursor.description]
    conn.close()
    d_col = next((c for c in cols if "日" in c or "date" in c.lower()), "日付")
    m_col = next((c for c in cols if "月" in c or "month" in c.lower()), "月")
    t_col = next((c for c in cols if "時" in c or "time" in c.lower()), "時間")
    c_col = next((c for c in cols if "条件" in c or "クラス" in c or "class" in c.lower()), "条件")
    return d_col, m_col, t_col, c_col

d_col, m_col, t_col, c_col = get_real_columns()

# --- 👈 左側：サイドバー ---
st.sidebar.title("🎮 操作パネル")

# 1. 過去データの参照範囲
st.sidebar.header("1. 過去データの参照範囲")
range_type = st.sidebar.radio("指定方法", ["日付範囲で指定", "季節で指定"])

filter_query = ""
if range_type == "日付範囲で指定":
    start_date = st.sidebar.date_input("開始日", date(2020, 1, 1))
    end_date = st.sidebar.date_input("終了日", date(2025, 12, 31))
    filter_query = f"AND {d_col} >= '{start_date}' AND {d_col} <= '{end_date}'"
else:
    season = st.sidebar.selectbox("対象シーズン", ["春 (4-6月)", "秋 (10-11月)", "冬 (1-2月)"])
    years_back = st.sidebar.slider("過去何年分を対象にするか", 1, 6, 3)
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    current_year = 2026 
    start_year = current_year - years_back
    filter_query = f"AND {d_col} >= '{start_year}-01-01' AND {m_col} IN ({m_dict[season]})"

# 2. レース条件 (クラス指定を追加！)
st.sidebar.header("2. レース条件")
baba = st.sidebar.selectbox("馬場種別", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離(m)", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)

# クラス（条件）の絞り込み
race_class = st.sidebar.selectbox("レースクラス", ["全クラス", "新馬・未勝利", "1勝クラス", "2勝・3勝クラス", "オープン・重賞"])
class_sql = ""
if race_class == "新馬・未勝利":
    class_sql = f"AND ({c_col} LIKE '%新馬%' OR {c_col} LIKE '%未勝利%')"
elif race_class == "1勝クラス":
    class_sql = f"AND {c_col} LIKE '%1勝%'"
elif race_class == "2勝・3勝クラス":
    class_sql = f"AND ({c_col} LIKE '%2勝%' OR {c_col} LIKE '%3勝%')"
elif race_class == "オープン・重賞":
    class_sql = f"AND ({c_col} LIKE '%オープン%' OR {c_col} LIKE '%G1%' OR {c_col} LIKE '%G2%' OR {c_col} LIKE '%G3%' OR {c_col} LIKE '%L%')"

# 時間帯
time_zone = st.sidebar.selectbox("時間帯", ["全時間帯", "午前 (1R-6R付近)", "午後 (7R-12R付近)"])
time_sql = ""
if time_zone == "午前 (1R-6R付近)":
    time_sql = f"AND (CAST(SUBSTR({t_col}, 1, 2) AS INTEGER) < 13)"
elif time_zone == "午後 (7R-12R付近)":
    time_sql = f"AND (CAST(SUBSTR({t_col}, 1, 2) AS INTEGER) >= 13)"

if st.sidebar.button("【4大指標 統計を確認する】"):
    st.session_state.mode = "stats"

st.sidebar.markdown("---")
st.sidebar.header("3. 気になる馬情報")
st.sidebar.header("4. 期待値シミュレーター")

# --- データ読み込み ---
def load_filtered_data(baba_val, dist_val, extra_sql, t_sql, c_sql):
    conn = sqlite3.connect(DB_FILE)
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba_val}%' AND 距離={dist_val} {extra_sql} {t_sql} {c_sql}"
    try:
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"SQLエラーが発生しました。")
        st.code(query)
        return pd.DataFrame()
    finally:
        conn.close()

# --- 👉 右側：メインエリア ---
if "mode" not in st.session_state:
    st.info("👈 左側のボタンを押すと、分析結果が表示されます。")
    st.stop()

df = load_filtered_data(baba, dist, filter_query, time_sql, class_sql)

if not df.empty:
    st.success(f"✅ {len(df)}件のデータを抽出しました")
    st.dataframe(df.head(50))
else:
    st.warning("⚠️ 条件に合うデータが見つかりません。")
