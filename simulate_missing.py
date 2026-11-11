"""为功能演示补充缺失字段；模拟值不是实测数据，不用于实证结论。"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 72604
SIMULATED_FIELDS = [
    "session_start",
    "hub_id",
    "ambient_temperature_c",
    "grid_load_kw",
    "solar_generation_kw",
]
SIMULATION_RULES = {
    "purpose": "Software demonstration only; not measured campus telemetry",
    "seed": SEED,
    "date_range": "2026-09-01 to 2026-09-14 (arbitrary demonstration period)",
    "dates": "Stable hash of session ID selects day; original Start_Hour retained; minute=00",
    "hub": "One fictional site: DEMO_CAMPUS; not inferred from sales locations",
    "ambient_C": "29 + 4*sin(2*pi*(hour-8)/24) + Normal(0,0.7), clipped to [23,36]",
    "solar_kW": "120*max(0,sin(pi*(hour-6)/12))*daily_cloud_factor; factor Uniform(0.55,1); zero outside 06-18",
    "grid_kW": "220 + 90*weekday_business_hours + 35*evening_hours + 8*(ambient-26) - solar + Normal(0,12), clipped to >=50",
    "grid_definition": "Illustrative net grid import at the fictional site, not session charging power",
    "sampling": "One shared snapshot per site/hour; repeated session rows are deduplicated for plotting",
    "preserved": "All source columns, including duration, energy, battery temperature and supplied bills",
    "limitations": "Date-based revenue changes and correlations involving generated variables are scenario outputs, not empirical findings",
}


def augment_for_demo(data):
    """确定性生成：不覆盖已有字段；时间/天气/负荷的设定全部可追溯。"""
    collision = set(SIMULATED_FIELDS).intersection(data.columns)
    if collision:
        raise ValueError("模拟补充不能覆盖已有字段：" + ", ".join(sorted(collision)))
    result = data.copy()
    # 使用 ID 哈希分配日期，排序或筛选输入不会改变同一会话的模拟日期。
    day = result.session_id.map(
        lambda value: int(
            hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()[:8], 16
        )
        % 14
    )
    result["session_start"] = (
        pd.Timestamp("2026-09-01")
        + pd.to_timedelta(day, unit="D")
        + pd.to_timedelta(result.start_hour, unit="h")
    )
    result["hub_id"] = "DEMO_CAMPUS"
    rng = np.random.default_rng(SEED)
    times = pd.date_range("2026-09-01", periods=14 * 24, freq="h")
    h = times.hour.to_numpy()
    ambient = np.clip(
        29 + 4 * np.sin(2 * np.pi * (h - 8) / 24) + rng.normal(0, 0.7, len(times)),
        23,
        36,
    )
    clouds = np.repeat(rng.uniform(0.55, 1.0, 14), 24)
    solar = 120 * np.maximum(0, np.sin(np.pi * (h - 6) / 12)) * clouds
    solar[(h <= 6) | (h >= 18)] = 0
    business = (times.dayofweek.to_numpy() < 5) & (h >= 8) & (h < 18)
    evening = (h >= 18) & (h < 22)
    grid = np.maximum(
        50,
        220
        + 90 * business
        + 35 * evening
        + 8 * (ambient - 26)
        - solar
        + rng.normal(0, 12, len(times)),
    )
    for col, values in [
        ("ambient_temperature_c", ambient),
        ("grid_load_kw", grid),
        ("solar_generation_kw", solar),
    ]:
        lookup = pd.Series(np.round(values, 2), index=times)
        result[col] = result.session_start.map(lookup)
    # CSV 本身携带来源标记，离开网页之后仍可辨别模拟字段。
    result["supplement_origin"] = "SIMULATED_FOR_DEMONSTRATION"
    result["simulated_fields"] = ";".join(SIMULATED_FIELDS)
    return result


def export_demo(data, folder):
    """独立导出补充版及规则，不修改原始文件和已清理参考文件。"""
    from visualizations import save_charts

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    augmented = augment_for_demo(data)
    augmented.to_csv(
        folder / "simulation_augmented_energy_data.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (folder / "simulation_rules.json").write_text(
        json.dumps(SIMULATION_RULES, indent=2), encoding="utf-8"
    )
    save_charts(augmented, folder)
    return augmented


if __name__ == "__main__":
    from config import ROOT
    from course_data import reconcile_sources

    source, _, _, _ = reconcile_sources()
    export_demo(source, ROOT / "results/demonstration")
    print("Saved separate, clearly labelled demonstration dataset and charts.")
