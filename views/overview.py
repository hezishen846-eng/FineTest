"""全部图表只使用入口中已筛选的数据，避免不同面板统计口径不一致。"""

import streamlit as st
from visualizations import executive_panels, operational_panels, plt

data = st.session_state["context"]["data"]
st.header("Executive overview")
st.caption(
    "Default revenue preserves the supplied cleaned CSV bills. "
    "Carbon offset uses the assignment factor of 0.475 kg CO₂/kWh."
)
if st.session_state["context"].get("simulation"):
    st.caption(
        "Simulated telemetry illustrates software behavior. The correlations below are scenario results, not research findings."
    )
if "session_start" not in data:
    st.warning(
        "Charging data has no date, ambient temperature, grid load or solar generation. "
        "The requested grid/solar and ambient/grid correlation panels are unavailable."
    )
if not data.empty:
    for factory in (operational_panels, executive_panels):
        figure = factory(data)
        st.pyplot(figure, width="stretch")
        plt.close(figure)  # 每次页面重跑都释放图形，避免服务器累积内存。
    st.caption(
        "Where telemetry is supplied, grid/solar curves use session-linked hub snapshots; repeated snapshots "
        "are deduplicated. Missing hours are gaps, not zero. Correlation and trendlines "
        "do not establish causation."
    )
    if {"soc_start_pct", "soc_end_pct"}.issubset(data.columns):
        with st.expander("Battery state of charge"):
            st.dataframe(
                data[["session_id", "soc_start_pct", "soc_end_pct"]], hide_index=True
            )
