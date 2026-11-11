"""可调告警阈值只用于运营监测；不能反向改变原始费用。"""

import streamlit as st
from analytics import risk_mask

context = st.session_state["context"]
data, threshold = context["data"], context["threshold"]
st.header("High-risk overstay & alert center")
st.write(
    f"Current rule: overstay >20 minutes AND battery temperature >{threshold:.0f}°C."
)
alerts = data.loc[risk_mask(data, threshold)].sort_values(
    "battery_temperature_c", ascending=False
)
critical = alerts.loc[alerts["battery_temperature_c"] >= max(50, threshold + 5)]
if data.empty:
    st.info("No sessions are available in this selection.")
elif not critical.empty:
    st.error(
        f"{len(critical)} critical sessions need review; {len(alerts)} high-risk sessions in total."
    )
elif not alerts.empty:
    st.warning(f"{len(alerts)} high-risk sessions exceed both selected limits.")
else:
    st.success("No high-risk overstay sessions match the selected rules.")
st.caption(
    "Critical severity (illustrative): temperature ≥max(50°C, selected threshold +5°C), "
    "plus the overstay condition. This is an analysis alert, not a physical safety controller."
)
st.dataframe(
    alerts[
        [
            col
            for col in [
                "session_id",
                "session_start",
                "hub_id",
                "charger_type",
                "overstay_minutes",
                "battery_temperature_c",
                "scenario_risk_surcharge",
                "risk_surcharge",
                "start_hour",
            ]
            if col in alerts
        ]
    ],
    hide_index=True,
    width="stretch",
)
