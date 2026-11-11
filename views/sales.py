"""500 条销售交易的独立探索页面；销售日期不能冒充充电日期。"""

import streamlit as st
from course_data import load_sales

st.header("Sales exploration — separate transaction dataset")
st.caption(
    "Source: sales_data.csv. These transactions have no shared session key with the charging data. "
    "Charging filters and KPIs above apply to EV sessions; the controls below apply only to sales."
)
sales = load_sales()
dates = st.date_input(
    "Sales transaction dates",
    (sales.Transaction_Date.min().date(), sales.Transaction_Date.max().date()),
    key="sales_dates",
)
hubs = st.multiselect(
    "Sales hub",
    sorted(sales.Hub_Location.unique()),
    default=sorted(sales.Hub_Location.unique()),
    key="sales_hubs",
)
if len(dates) != 2:
    st.info("Select both transaction dates.")
    st.stop()
selected = sales.loc[
    sales.Transaction_Date.dt.date.between(*dates) & sales.Hub_Location.isin(hubs)
]
cols = st.columns(3)
cols[0].metric("Sales transactions", len(selected))
cols[1].metric(
    "Known / reconstructable sales revenue",
    f"MYR {selected.Analysis_Revenue_MYR.sum():,.2f}",
)
cols[2].metric(
    "Unresolved revenue records", int(selected.Analysis_Revenue_MYR.isna().sum())
)
st.info(
    f"Selection: {selected.Units_Sold.isna().sum()} missing unit counts; "
    f"{selected.Total_Revenue_MYR.isna().sum()} originally missing revenue values; "
    f"{selected.Revenue_Reconstructed.sum()} revenues reconstructed from known units × unit price; "
    f"{selected.Revenue_Mismatch.sum()} recorded revenues differ from units × price."
)
st.caption(
    "Original columns are preserved. Missing units remain unknown. Revenue totals exclude "
    "unresolved amounts; no revenue is inferred when either multiplier is missing."
)
if not selected.empty:
    st.subheader("Revenue by category")
    st.bar_chart(
        selected.groupby("Category").Analysis_Revenue_MYR.sum(min_count=1),
        y_label="MYR",
    )
    st.subheader("Daily transaction revenue")
    st.line_chart(
        selected.groupby("Transaction_Date").Analysis_Revenue_MYR.sum(min_count=1),
        y_label="MYR",
    )
    st.subheader("Revenue by hub")
    st.bar_chart(
        selected.groupby("Hub_Location").Analysis_Revenue_MYR.sum(min_count=1),
        y_label="MYR",
    )
else:
    st.info("No transactions match the sales filters.")
st.dataframe(selected, hide_index=True, width="stretch")
st.download_button(
    "Download sales exploration CSV",
    selected.to_csv(index=False).encode("utf-8-sig"),
    file_name="sales_exploration.csv",
    mime="text/csv",
)
