"""筛选后的数据展示和导出；全量审计单独标注，避免误认为筛选结果。"""

import streamlit as st

context = st.session_state["context"]
data = context["data"]
st.header("Filtered data & CSV export")
st.write(f"{len(data):,} sessions match the shared filters.")
st.dataframe(data, hide_index=True, width="stretch")
st.download_button(
    "Download filtered CSV",
    data.to_csv(index=False).encode("utf-8-sig"),
    file_name=(
        "filtered_simulation_augmented_data.csv"
        if context.get("simulation")
        else "filtered_energy_sales_data.csv"
    ),
    mime="text/csv",
)
with st.expander("Full-file cleaning audit"):
    st.json(context["audit"])
    st.dataframe(context["rejected"], hide_index=True)
    st.caption(
        "Audit totals cover the entire uploaded/source file before dashboard filtering."
    )
with st.expander("Pricing assumptions and units"):
    st.json(context["policy"])
    if "billing_source" in data:
        st.write(
            "Supplied bills: AC 6 MYR/hour; DC 15 MYR/hour; 25% peak surcharge "
            "for start hours 12–17 inclusive; overstay 0.50 MYR/min after 15 free minutes. "
            "These rules reproduce the supplied file and are not a verified campus tariff. "
            "The Section A 15% risk scenario is shown separately, not added to revenue."
        )
    else:
        st.write(
            "Extended demonstration schema uses the illustrative rules displayed above."
        )

if context.get("simulation"):
    with st.expander("Simulation assumptions and field provenance"):
        st.json(context["simulation"])
        st.write(
            "Disable Complete demonstration mode to return to the supplied charging data. "
            "Simulated dates and telemetry must not be described as campus measurements."
        )
