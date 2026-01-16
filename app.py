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

# --- 🐎 アプリ設定 ---
st.set_page_config(page_title="東京競馬分析WS", layout="wide")
st.title("🏇 東京競馬分析ワークステーション")

@st.cache_data
def load_data(baba, dist, season):
    conn = sqlite3.connect('keiba_data.db')
    m_dict = {"冬 (1-2月)": "1,2", "春 (4-6月)": "4,5,6", "秋 (10-11月)": "10,11"}
    query = f"SELECT * FROM race_results WHERE 場所='東京' AND 馬場 LIKE '{baba}%' AND 距離={dist} AND 月 IN ({m_dict[season]})"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- 👈 左側：メニュー ---
st.sidebar.header("📊 分析条件設定")
baba = st.sidebar.selectbox("馬場", ["芝", "ダート"])
dist = st.sidebar.selectbox("距離", [1300, 1400, 1600, 1800, 2000, 2100, 2400], index=2)
season = st.sidebar.selectbox("季節", ["冬 (1-2月)", "春 (4-6月)", "秋 (10-11月)"])

df = load_data(baba, dist, season)

if not df.empty:
    # --- 自動列名判定ロジック ---
    # 列名に特定の文字が含まれているものを探す
    def find_col(possible_names, default_idx):
        for name in df.columns:
            if any(p in str(name) for p in possible_names):
                return name
        return df.columns[default_idx]

    id_col = find_col(['ID', 'id', 'レース', 'Race'], 0)
    chakujun_col = find_col(['着順', '着', 'Result', 'rank'], 1)
    waku_col = find_col(['枠', 'Bracket'], 2)
    ninki_col = find_col(['人気', 'Pop'], 3)
    umaban_col = find_col(['馬番', 'Num'], 4)
    
    # データの数値化（エラー対策）
    df[chakujun_col] = pd.to_numeric(df[chakujun_col], errors='coerce')
    df[waku_col] = pd.to_numeric(df[waku_col], errors='coerce')
    df[ninki_col] = pd.to_numeric(df[ninki_col], errors='coerce')

    st.success(f"✅ 解析対象: {df[id_col].nunique()} レース / {len(df)} 頭")

    # --- Section 1: 枠順別分析 ---
    st.header("📍 Section 1: 枠順の有利不利")
    waku_stats = df.groupby(waku_col)[chakujun_col].apply(lambda x: (x <= 3).mean() * 100)
    fig1, ax1 = plt.subplots(figsize=(10, 4))
    sns.barplot(x=waku_stats.index, y=waku_stats.values, palette="tab10", ax=ax1)
    ax1.set_ylabel("複勝率 (%)")
    st.pyplot(fig1)

    # --- Section 2: 人気別信頼度 ---
    st.header("🎯 Section 2: 人気別信頼度")
    pop_stats = df.groupby(ninki_col)[chakujun_col].apply(lambda x: (x <= 3).mean() * 100).head(10)
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    sns.lineplot(x=pop_stats.index, y=pop_stats.values, marker='o', color='red', ax=ax2)
    ax2.set_xticks(range(1, min(11, len(pop_stats)+1)))
    ax2.set_ylabel("複勝率 (%)")
    st.pyplot(fig2)

    # --- Section 3: 馬番別傾向 ---
    st.header("🏃 Section 3: 馬番別・コース傾向")
    fig3, ax3 = plt.subplots(figsize=(12, 4))
    sns.countplot(x=umaban_col, data=df[df[chakujun_col] <= 3], palette="Blues_r", ax=ax3)
    st.pyplot(fig3)

    # --- Section 4: データ一覧 ---
    st.header("📑 Section 4: 生データ")
    st.dataframe(df.head(100), height=400)

else:
    st.warning("⚠️ 該当データがありません。条件を変えてみてください。")
