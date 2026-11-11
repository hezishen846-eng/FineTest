"""用户提供的三份课程数据：保留来源、复现清洗、单独开展销售探索。"""

import numpy as np
import pandas as pd

from config import ROOT
from pipeline import ALIASES, Audit, DataValidationError, read_csv

CLEANED_SOURCE = ROOT / "data/cleaned_energy_sales_data.csv"
SALES_SOURCE = ROOT / "data/sales_data.csv"
FIELD_MAP = {
    "carbon_savings_kgco2": "carbon_savings_kg",
    "base_fee_myr": "base_energy_fee",
    "peak_surge_myr": "peak_surcharge",
    "net_billable_myr": "net_billable_amount",
}
COURSE_RULES = {
    "source": "Rules inferred from supplied cleaned CSV; not a verified campus tariff",
    "AC_MYR_per_hour": 6,
    "DC_MYR_per_hour": 15,
    "peak_start_hour": 12,
    "peak_end_hour_inclusive": 17,
    "peak_rate": 0.25,
    "overstay_free_minutes": 15,
    "overstay_MYR_per_minute": 0.5,
    "carbon_factor": 0.475,
    "risk_15_percent": "Section A scenario only; excluded from supplied bills",
}


def load_course(raw):
    """兼容课程的 9 列原始数据或 17 列已清理数据，不生成虚构日期/遥测。"""
    df = raw.copy()
    df.columns = [
        FIELD_MAP.get(
            str(c).strip().lower(),
            ALIASES.get(str(c).strip().lower(), str(c).strip().lower()),
        )
        for c in df.columns
    ]
    required = [
        "session_id",
        "charger_type",
        "user_type",
        "start_hour",
        "duration_minutes",
        "energy_kwh",
        "overstay_minutes",
        "battery_temperature_c",
        "grid_status_label",
    ]
    if df.columns.duplicated().any() or not set(required).issubset(df):
        raise DataValidationError("课程数据列缺失或重复。")
    if df.empty:
        raise DataValidationError("课程文件没有数据行。")
    audit = Audit(input_rows=len(df))
    audit.exact_duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()
    df["charger_type"] = df.charger_type.astype("string").str.strip().str.upper()
    df["user_type"] = df.user_type.astype("string").str.strip().str.title()
    df["session_id"] = df.session_id.astype("string").str.strip()
    df["start_hour"] = pd.to_numeric(df.start_hour, errors="coerce")
    valid = (
        df.charger_type.isin(["AC", "DC"])
        & df.user_type.isin(["Student", "Staff", "Visitor"])
        & df.session_id.notna()
        & df.session_id.ne("")
        & ~df.session_id.duplicated(keep=False)
        & df.start_hour.between(0, 23)
        & df.start_hour.mod(1).eq(0)
    )
    rejected = df.loc[~valid].copy()
    rejected["rejection_reason"] = "Invalid ID, category or hour"
    df = df.loc[valid].copy()
    if df.empty:
        raise DataValidationError("没有有效的课程充电记录。")
    for col in [
        "duration_minutes",
        "energy_kwh",
        "overstay_minutes",
        "battery_temperature_c",
    ]:
        values = pd.to_numeric(df[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        lower = -273.15 if col == "battery_temperature_c" else 0
        values = values.mask(values < lower)
        if col == "duration_minutes":
            values = values.mask(values == 0)
        median = values.median()
        if pd.isna(median):
            raise DataValidationError(f"{col} 无有效数值，不能插补。")
        audit.imputed[col] = int(values.isna().sum())
        audit.medians[col] = float(median)
        df[col] = values.fillna(median)
    df["start_hour"] = df.start_hour.astype(int)
    # 收费规则由附件清理结果逐行核对得出；不沿用旧演示的 10% 高峰费。
    expected = {}
    expected["duration_hours"] = df.duration_minutes / 60
    expected["power_rate_kw"] = df.energy_kwh / expected["duration_hours"]
    expected["carbon_savings_kg"] = (df.energy_kwh * 0.475).round(2)
    expected["base_rate_myr"] = df.charger_type.map({"AC": 6.0, "DC": 15.0})
    expected["base_energy_fee"] = expected["duration_hours"] * expected["base_rate_myr"]
    expected["peak_surcharge"] = (
        expected["base_energy_fee"] * 0.25 * df.start_hour.between(12, 17)
    )
    expected["overstay_fee_myr"] = (df.overstay_minutes - 15).clip(lower=0) * 0.5
    expected["net_billable_amount"] = (
        expected["base_energy_fee"]
        + expected["peak_surcharge"]
        + expected["overstay_fee_myr"]
    ).round(2)
    supplied = "net_billable_amount" in df
    for col, calculated in expected.items():
        if col in df:
            # 已清理文件保留原值，只校验；防止把参考账单静默重写。
            values = pd.to_numeric(df[col], errors="coerce")
            if not np.isclose(values, calculated, rtol=1e-9, atol=1e-7).all():
                raise DataValidationError(
                    f"提供的 {col} 与已核对课程规则不一致，请检查。"
                )
            df[col] = values
        else:
            df[col] = calculated
    df["billing_risk"] = (df.overstay_minutes > 20) & (df.battery_temperature_c > 40)
    # 风险收费只作为 A2 的独立模拟，不加入已有账单。
    from pipeline import surcharge

    df["scenario_risk_surcharge"] = [
        surcharge(fee, 0.15) if risk else 0.0
        for fee, risk in zip(df.base_energy_fee, df.billing_risk)
    ]
    df["billing_source"] = (
        "Supplied cleaned CSV" if supplied else "Reproduced from raw course CSV"
    )
    # 补充版 CSV 可再次上传；按明确的类型读回日期及遥测，不重写账单。
    if "session_start" in df:
        df["session_start"] = pd.to_datetime(df.session_start, errors="coerce")
        if (
            df.session_start.isna().any()
            or not df.session_start.dt.hour.eq(df.start_hour).all()
        ):
            raise DataValidationError("补充日期无效或与原始开始小时不一致。")
    for col in ["ambient_temperature_c", "grid_load_kw", "solar_generation_kw"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if not np.isfinite(df[col]).all():
                raise DataValidationError(f"{col} 包含无效遥测。")
    audit.rejected_rows, audit.output_rows = len(rejected), len(df)
    return df.reset_index(drop=True), audit, rejected


def reconcile_sources():
    """逐 ID 对比原始数据的清洗结果与用户提供的清理文件，生成可审阅表。"""
    raw, audit, rejected = load_course(read_csv(ROOT / "ev_campus_dataset.csv"))
    supplied, _, _ = load_course(read_csv(CLEANED_SOURCE))
    left, right = raw.set_index("session_id"), supplied.set_index("session_id")
    if set(left.index) != set(right.index):
        raise DataValidationError("原始与已清理文件的会话 ID 不对应。")
    right = right.reindex(left.index)
    rows = []
    for col in left.columns.intersection(right.columns):
        if col == "billing_source":
            continue
        if pd.api.types.is_numeric_dtype(left[col]):
            matches = np.isclose(left[col], right[col], rtol=1e-9, atol=1e-7)
        else:
            matches = left[col].eq(right[col]).to_numpy()
        rows.append(
            {
                "field": col,
                "compared_rows": len(left),
                "mismatched_rows": int((~matches).sum()),
            }
        )
    return supplied, audit, rejected, pd.DataFrame(rows)


def load_sales():
    """独立销售表：不猜测销量、不与没有关联键的充电会话拼接。"""
    df = pd.read_csv(SALES_SOURCE)
    df["Transaction_Date"] = pd.to_datetime(df.Transaction_Date, errors="coerce")
    for col in ["Units_Sold", "Unit_Price_MYR", "Total_Revenue_MYR"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        df.loc[df[col] < 0, col] = np.nan
    df["Revenue_Reconstructed"] = (
        df.Total_Revenue_MYR.isna() & df.Units_Sold.notna() & df.Unit_Price_MYR.notna()
    )
    # 只在两个乘数均已知时恢复缺失收入，保留原始收入列和未知销量。
    df["Analysis_Revenue_MYR"] = df.Total_Revenue_MYR.fillna(
        df.Units_Sold * df.Unit_Price_MYR
    )
    df["Revenue_Mismatch"] = (
        df.Total_Revenue_MYR.notna()
        & df.Units_Sold.notna()
        & ~np.isclose(
            df.Total_Revenue_MYR, df.Units_Sold * df.Unit_Price_MYR, equal_nan=False
        )
    )
    return df
