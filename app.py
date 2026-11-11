"""Streamlit 总入口：共享数据、全局筛选、KPI 与多页面路由。

启动：python -m streamlit run app.py --server.address 127.0.0.1
请勿使用普通的 python app.py 代替 Streamlit 服务器。
"""

from dataclasses import asdict
from io import BytesIO
import math

import pandas as pd
import streamlit as st

from analytics import filter_sessions, kpis, previous_period
from config import DEFAULT_DATA, POLICY
from pipeline import DataValidationError, load_pipeline
from course_data import COURSE_RULES, reconcile_sources
from simulate_missing import augment_for_demo, SIMULATION_RULES

st.set_page_config(page_title="Campus Energy & EV", page_icon="⚡", layout="wide")


@st.cache_data(show_spinner="Validating sessions…")
def prepare(content):
    """以文件内容作为缓存键：CSV 更新后不会误用上一次清洗结果。"""
    return load_pipeline(BytesIO(content))


st.title("Campus Energy & EV Fleet")
st.caption("ShopEasy Logistics × Taylor's Smart Campus · Offline decision support")
uploaded = st.sidebar.file_uploader("Upload session CSV (optional)", type=["csv"])
try:
    content = uploaded.getvalue() if uploaded is not None else DEFAULT_DATA.read_bytes()
    if len(content) > 10 * 1024 * 1024:
        raise DataValidationError("CSV 超过 10 MB；请先分批处理。")
    if uploaded is None:
        data, audit, rejected, reconciliation = reconcile_sources()
        if reconciliation.mismatched_rows.sum():
            raise DataValidationError("原始与已清理文件不一致，请查看核对表。")
    else:
        data, audit, rejected = prepare(content)
except (OSError, DataValidationError) as exc:
    st.error(str(exc))
    st.info(
        "Use the documented schema in README.md. Missing required fields are not fabricated."
    )
    st.stop()

# 用户要求补充模拟字段：仅对缺少全部遥测字段的课程数据启用，原文件不改。
if "billing_source" in data and "session_start" not in data:
    demo_enabled = st.sidebar.checkbox(
        "Complete demonstration mode", value=True, key="demo_mode"
    )
    if demo_enabled:
        data = augment_for_demo(data)
is_augmented = (
    "supplement_origin" in data
    and data.supplement_origin.eq("SIMULATED_FOR_DEMONSTRATION").any()
)
if is_augmented:
    st.info(
        "DEMONSTRATION MODE · Dates, ambient temperature, grid load, solar output and site are simulated. "
        "Original charging values and bills are preserved."
    )

is_demo = "data_origin" in data and data["data_origin"].eq("SYNTHETIC_DEMO").any()
if is_demo:
    st.warning(
        "SYNTHETIC DEMO DATA — not campus measurements or actual financial results."
    )
elif not is_augmented:
    st.info(
        "User-supplied data. Provenance and measurement accuracy require independent verification."
    )

st.sidebar.header("Shared filters")
has_dates = "session_start" in data
if has_dates:
    first_date = data["session_start"].min().date()
    last_date = data["session_start"].max().date()
    default_start = max(first_date, last_date - pd.Timedelta(days=2))
    dates = st.sidebar.date_input(
        "Session date range",
        value=(default_start, last_date),
        min_value=first_date,
        max_value=last_date,
        key="dates",
    )
else:
    dates = None
    st.sidebar.info(
        "Charging dates unavailable. Date filtering and period deltas are unavailable."
    )
    hours = st.sidebar.slider("Session start hour", 0, 23, (0, 23), key="hours")
minimum = st.sidebar.slider(
    "Minimum energy (kWh)",
    0.0,
    float(max(1, math.ceil(data["energy_kwh"].max()))),
    0.0,
    step=1.0,
    key="min_energy",
)
chargers = st.sidebar.multiselect(
    "Charger type", ["AC", "DC"], default=["AC", "DC"], key="chargers"
)
threshold = st.sidebar.slider(
    "Alert temperature threshold (°C)", 20.0, 80.0, 40.0, step=1.0, key="temperature"
)
st.sidebar.caption("High risk: overstay >20 min AND temperature above this threshold.")
st.sidebar.caption("Monitoring thresholds do not change supplied bills.")
if has_dates:
    if len(dates) != 2:
        st.info("Select both a start and an end date.")
        st.stop()
    start, end = dates
    filtered = filter_sessions(data, start, end, minimum, chargers)
    prior = previous_period(data, start, end, minimum, chargers)
else:
    filtered = data.loc[
        data.start_hour.between(*hours)
        & (data.energy_kwh >= minimum)
        & data.charger_type.isin(chargers)
    ].copy()
    prior = data.iloc[:0]
current = kpis(filtered, threshold)
previous = kpis(prior, threshold) if not prior.empty else None
cards = [
    ("Total energy delivered", "energy", "kWh"),
    ("Carbon offset", "carbon", "kg CO₂"),
    ("Total revenue", "revenue", "MYR"),
    ("Active alert count", "alerts", "sessions"),
]
for column, (label, key, unit) in zip(st.columns(4), cards):
    value = f"{current[key]:,.0f}" if key == "alerts" else f"{current[key]:,.2f}"
    delta = None if previous is None else f"{current[key] - previous[key]:+,.2f} {unit}"
    column.metric(
        label,
        f"{value} {unit}",
        delta=delta,
        delta_color="inverse" if key == "alerts" else "normal",
    )
if is_augmented:
    st.caption(
        "Date-based KPI changes use simulated dates and do not represent observed historical changes."
    )
st.caption(
    "Deltas: previous equal-length date window, with identical charger/energy filters. "
    "No historical records = no delta. Alerts refer to selected sessions, not live telemetry."
)
if filtered.empty:
    st.info(
        "No sessions match the filters. Adjust the date, charger or energy selection."
    )
st.session_state["context"] = {
    "data": filtered,
    "audit": asdict(audit),
    "rejected": rejected,
    "simulation": SIMULATION_RULES if is_augmented else None,
    "threshold": threshold,
    "policy": COURSE_RULES if "billing_source" in data else asdict(POLICY),
}
navigation = st.navigation(
    [
        st.Page(
            "views/overview.py", title="Executive overview", icon="📊", default=True
        ),
        st.Page("views/alerts.py", title="High-risk alert center", icon="⚠️"),
        st.Page("views/data.py", title="Data and downloads", icon="📁"),
        st.Page("views/sales.py", title="Sales exploration", icon="🛒"),
    ]
)
navigation.run()
