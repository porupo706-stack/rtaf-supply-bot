import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = "chat_logs.db"


def show_dashboard():

    st.header(
        "📊 Dashboard"
    )

    conn = sqlite3.connect(
        DB_NAME
    )

    df = pd.read_sql(
        """
        SELECT *
        FROM chat_logs
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()

    if df.empty:

        st.warning(
            "ยังไม่มีข้อมูล"
        )

        return

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "คำถามทั้งหมด",
        len(df)
    )

    col2.metric(
        "Cache Hit",
        int(df["cache_hit"].sum())
    )

    col3.metric(
        "Notebook",
        df["notebook_id"].nunique()
    )

    st.dataframe(
        df,
        use_container_width=True
    )