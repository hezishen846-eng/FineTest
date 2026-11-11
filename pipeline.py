"""Section B1：CSV 校验、中位数插补、派生指标及可追踪的清洗审计。"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd

from config import POLICY

NUMERIC = [
    "duration_minutes",
    "energy_kwh",
    "overstay_minutes",
    "battery_temperature_c",
    "ambient_temperature_c",
    "grid_load_kw",
    "solar_generation_kw",
    "base_energy_fee",
]
REQUIRED = [
    "session_id",
    "hub_id",
    "session_start",
    "charger_type",
    "user_type",
] + NUMERIC
ALIASES = {
    "duration_mins": "duration_minutes",
    "overstay_mins": "overstay_minutes",
    "battery_temp_c": "battery_temperature_c",
    "ambient_temp_c": "ambient_temperature_c",
    "timestamp": "session_start",
    "start_time": "session_start",
}


class DataValidationError(ValueError):
    """可向用户展示的数据错误，不将无效数据静默替换成演示数据。"""


@dataclass
class Audit:
    input_rows: int
    exact_duplicates: int = 0
    rejected_rows: int = 0
    output_rows: int = 0
    imputed: dict = field(default_factory=dict)
    medians: dict = field(default_factory=dict)


def money(value):
    """金额按每条会话四舍五入至分；Decimal 避免二进制浮点舍入歧义。"""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def surcharge(base, rate):
    """先做十进制乘法，再统一舍入。"""
    return float(
        (Decimal(str(base)) * Decimal(str(rate))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def read_csv(source):
    """读取路径或上传的文件；身份字段先按文本保留，避免丢失前导零。"""
    try:
        frame = pd.read_csv(source, dtype=str, encoding="utf-8-sig")
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise DataValidationError(f"无法读取 CSV：{exc}") from exc
    return frame


def clean_data(raw):
    """返回清洗数据、审计和拒收记录。类别/日期不能可靠推断，因此拒收而非猜测。"""
    df = raw.copy()
    df.columns = [
        ALIASES.get(
            re.sub(r"\s+", "_", str(c).strip().lower()),
            re.sub(r"\s+", "_", str(c).strip().lower()),
        )
        for c in df.columns
    ]
    if df.columns.duplicated().any():
        raise DataValidationError("列名规范化后重复，请移除重复列。")
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise DataValidationError("缺少必要字段：" + ", ".join(missing))
    if df.empty:
        raise DataValidationError("CSV 没有数据行。")
    audit = Audit(input_rows=len(df))
    audit.exact_duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()
    reasons = pd.Series("", index=df.index, dtype="string")

    def reject(mask, reason):
        reasons.loc[mask] += reason + "; "

    for col in ("session_id", "hub_id"):
        df[col] = df[col].astype("string").str.strip()
        reject(df[col].isna() | df[col].eq(""), f"Missing {col}")
    # 相同 ID 但不同内容不能武断保留第一条，全部进入隔离记录。
    reject(df["session_id"].duplicated(keep=False), "Conflicting session ID")
    for col, allowed in [
        ("charger_type", {"AC", "DC"}),
        ("user_type", {"Student", "Staff", "Visitor"}),
    ]:
        text = df[col].astype("string").str.strip()
        df[col] = text.str.upper() if col == "charger_type" else text.str.title()
        reject(~df[col].isin(allowed), f"Invalid {col}")
    # 数据约定：本地马来西亚时间、无时区后缀；拒绝混合时区以免日期筛选错位。
    try:
        times = pd.to_datetime(df["session_start"], errors="coerce", format="mixed")
        if not pd.api.types.is_datetime64_dtype(times.dtype):
            raise DataValidationError(
                "时间列应为不带时区的校园本地时间，例如 2026-11-01 12:00。"
            )
    except (ValueError, TypeError) as exc:
        raise DataValidationError(f"时间格式不一致：{exc}") from exc
    df["session_start"] = times
    reject(times.isna(), "Invalid session_start")
    rejected = df.loc[reasons.ne("")].copy()
    rejected["rejection_reason"] = reasons[reasons.ne("")]
    df = df.loc[reasons.eq("")].copy()
    audit.rejected_rows = len(rejected)
    if df.empty:
        raise DataValidationError("所有记录均因 ID、时间或类别问题被拒收。")
    for col in NUMERIC:
        values = pd.to_numeric(df[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        if col == "duration_minutes":
            values = values.mask(values <= 0)  # 防止 Energy / 0 产生无穷大。
        elif "temperature" in col:
            values = values.mask(values < -273.15)
        else:
            values = values.mask(values < 0)
        median = values.median()
        if pd.isna(median):
            raise DataValidationError(f"{col} 全列没有有效数值，无法计算中位数。")
        audit.imputed[col] = int(values.isna().sum())
        audit.medians[col] = float(median)
        df[col] = values.fillna(median).astype(float)
    # 可选 SoC：如果提供就校验；不从能量推测缺失的电池荷电状态。
    for col in ("soc_start_pct", "soc_end_pct"):
        if col in df:
            values = pd.to_numeric(df[col], errors="coerce")
            df[col] = values.where(values.between(0, 100))
    audit.output_rows = len(df)
    return df.sort_values("session_start").reset_index(drop=True), audit, rejected


def engineer_features(clean, policy=POLICY):
    """向量化计算功率/碳减排；两项附加费分别以基础费为基数，不复利叠加。"""
    df = clean.copy()
    df["duration_hours"] = df["duration_minutes"] / 60
    df["power_rate_kw"] = df["energy_kwh"] / df["duration_hours"]
    df["carbon_savings_kg"] = df["energy_kwh"] * policy.carbon_factor
    df["start_hour"] = df["session_start"].dt.hour
    df["is_peak"] = df["start_hour"].between(
        policy.peak_start_hour, policy.peak_end_hour, inclusive="left"
    )
    df["billing_risk"] = (df["overstay_minutes"] > policy.overstay_minutes) & (
        df["battery_temperature_c"] > policy.risk_temperature_c
    )
    df["base_energy_fee"] = df["base_energy_fee"].map(money)
    df["peak_surcharge"] = [
        surcharge(base, policy.peak_rate) if peak else 0.0
        for base, peak in zip(df["base_energy_fee"], df["is_peak"])
    ]
    df["risk_surcharge"] = [
        surcharge(base, policy.risk_rate) if risk else 0.0
        for base, risk in zip(df["base_energy_fee"], df["billing_risk"])
    ]
    df["net_billable_amount"] = (
        df["base_energy_fee"] + df["peak_surcharge"] + df["risk_surcharge"]
    ).map(money)
    return df


def load_pipeline(source, policy=POLICY):
    """读取与清洗组合入口，CLI、网页和测试复用同一套规则。"""
    raw = read_csv(source)
    columns = {str(c).strip().lower() for c in raw.columns}
    if "grid_status_label" in columns and "start_hour" in columns:
        from course_data import load_course

        return load_course(raw)
    clean, audit, rejected = clean_data(raw)
    return engineer_features(clean, policy), audit, rejected


def export_results(data, audit, rejected, folder, policy=POLICY):
    """先写临时文件再替换，降低程序中断时产生半个 CSV 的风险。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, frame in [
        ("cleaned_energy_sales_data.csv", data),
        ("rejected_records.csv", rejected),
    ]:
        target = folder / name
        temporary = target.with_suffix(".tmp")
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        temporary.replace(target)
    rules = asdict(policy)
    if "billing_source" in data:
        from course_data import COURSE_RULES

        rules = COURSE_RULES
    payload = {"audit": asdict(audit), "pricing_assumptions": rules}
    (folder / "quality_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
