"""统一筛选、风险规则与 KPI，保证所有页面使用相同的数据口径。"""

import pandas as pd


def filter_sessions(data, start, end, min_energy, charger_types):
    """结束日期采用次日零点之前，包含结束日的全部会话。"""
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("开始日期不能晚于结束日期。")
    mask = (
        (data["session_start"] >= pd.Timestamp(start))
        & (data["session_start"] < pd.Timestamp(end) + pd.Timedelta(days=1))
        & (data["energy_kwh"] >= min_energy)
        & data["charger_type"].isin(charger_types)
    )
    return data.loc[mask].copy()


def risk_mask(data, threshold=40.0):
    """边界严格使用 >：恰好 20 分钟或恰好阈值温度均不算高风险。"""
    return (data["overstay_minutes"] > 20) & (data["battery_temperature_c"] > threshold)


def kpis(data, threshold=40.0):
    """告警数是当前所选历史数据中的告警会话数，不表示实时设备状态。"""
    return {
        "energy": float(data["energy_kwh"].sum()),
        "carbon": float(data["carbon_savings_kg"].sum()),
        "revenue": round(float(data["net_billable_amount"].sum()), 2),
        "alerts": int(risk_mask(data, threshold).sum()),
    }


def previous_period(data, start, end, min_energy, charger_types):
    """比较相邻且等长的前一日期区间，不将缺少历史记录显示成 0% 增长。"""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    days = (end - start).days + 1
    return filter_sessions(
        data,
        start - pd.Timedelta(days=days),
        start - pd.Timedelta(days=1),
        min_energy,
        charger_types,
    )
