import streamlit as st
import pandas as pd
import io
from datetime import datetime

# 店舗番号と店舗名のマッピング
store_map = {
    "2": "隼人", "3": "鷹尾", "4": "中町", "5": "三股", "7": "宮崎", "8": "熊本",
    "14": "鹿屋", "15": "吉野", "16": "花山手東", "17": "大根田", "18": "中山",
    "21": "土井", "22": "空港東", "23": "有田", "24": "春日", "25": "長嶺"
}

# 商品ごとの個数マスタ
product_unit_map = {
    "ぎょうざ２０個": 20, "ぎょうざ３０個": 30, "ぎょうざ４０個": 40, "ぎょうざ５０個": 50,
    "生姜入ぎょうざ３０個": 30,
    "宅配ぎょうざ40個": 40, "宅配ぎょうざ50個": 50,
    "宅配生姜40個餃子": 40, "宅配生姜50個餃子": 50
}

st.title("🥟 店舗別売上・来客・販売個数 分析")
st.caption("販売CSVまたはExcelファイルをアップロードしてください")

uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])

if uploaded_file:
    # データ読み込み
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, encoding="cp932", skiprows=2)
    else:
        df = pd.read_excel(uploaded_file, header=3)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["レシート番号", "商品名"], how="all")

    # 店舗番号抽出とマッピング
    df["店舗番号"] = df["レシート番号"].astype(str).str.extract(r"No\.(\d+)-")
    df["店舗名"] = df["店舗番号"].map(store_map)

    # 金額数値化
    df["合計"] = pd.to_numeric(df["合計"].astype(str).str.replace(",", ""), errors="coerce")
    df["数量"] = pd.to_numeric(df["数量"], errors="coerce")

    # 店舗別 売上・来客数・客単価
    receipt_summary = df.drop_duplicates(subset=["レシート番号"])[["レシート番号", "合計", "店舗名"]]
    store_sales = receipt_summary.groupby("店舗名").agg(
        売上金額=("合計", "sum"),
        来客数=("レシート番号", "count")
    )
    store_sales["客単価"] = (store_sales["売上金額"] / store_sales["来客数"]).round()

    st.subheader("📊 店舗別売上・来客数・客単価")
    st.dataframe(store_sales.reset_index())

    # 商品別販売数・総販売個数
    df["個数換算"] = df.apply(lambda row: row["数量"] * product_unit_map.get(row["商品名"], 0), axis=1)
    item_summary = df[df["商品名"].isin(product_unit_map.keys())]
    item_summary = item_summary.groupby(["店舗名", "商品名"]).agg(
        販売数=("数量", "sum"),
        総販売個数=("個数換算", "sum")
    ).reset_index()

    item_pivot = item_summary.pivot(index="店舗名", columns="商品名", values="販売数").fillna(0).astype(int)
    item_total = item_summary.groupby("店舗名")["総販売個数"].sum()
    item_pivot["総販売個数"] = item_total

    st.subheader("📦 店舗別・商品別の販売数／総販売個数")
    st.dataframe(item_pivot)

    # 時間帯別集計（9:00〜の形式）
    if "販売日時" in df.columns:
        df["販売日時"] = df["販売日時"].astype(str).str.replace(r"\(.+?\)", "", regex=True)
        df["販売日時"] = pd.to_datetime(df["販売日時"], format="%Y年%m月%d日 %H:%M", errors="coerce")
        df = df.dropna(subset=["販売日時"])
        df["時間帯"] = df["販売日時"].dt.floor("30min").dt.strftime("%H:%M〜")

        df_time = df.groupby(["店舗名", "時間帯"]).agg(
            来客数=("レシート番号", lambda x: x.nunique()),
            総販売個数=("個数換算", "sum")
        ).reset_index()

        visitors_pivot = df_time.pivot(index="店舗名", columns="時間帯", values="来客数").fillna(0).astype(int)
        units_pivot = df_time.pivot(index="店舗名", columns="時間帯", values="総販売個数").fillna(0).astype(int)

        visitors_pivot = visitors_pivot.sort_index(axis=1)
        units_pivot = units_pivot.sort_index(axis=1)

        st.subheader("📍 店舗別・時間帯別 来客数（30分刻み）")
        st.dataframe(visitors_pivot)

        st.subheader("📍 店舗別・時間帯別 総販売個数（30分刻み）")
        st.dataframe(units_pivot)

    else:
        st.warning("⚠️ 『販売日時』列が見つかりませんでした。時間帯集計はスキップされました。")

        # Excel出力（全データシートごとに書き出し）
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        store_sales.reset_index().to_excel(writer, sheet_name="店舗別_売上来客客単価", index=False)
        item_pivot.reset_index().to_excel(writer, sheet_name="店舗別_商品別販売", index=False)
        visitors_pivot.reset_index().to_excel(writer, sheet_name="店舗別_来客数_時間帯別", index=False)
        units_pivot.reset_index().to_excel(writer, sheet_name="店舗別_販売個数_時間帯別", index=False)

    st.download_button(
        label="📥 結果をExcelでダウンロード",
        data=output.getvalue(),
        file_name="販売分析結果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )