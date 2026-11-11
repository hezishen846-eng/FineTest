"""仅生成明确标注的模拟数据；不会声称这些记录来自学校或真实传感器。"""

import argparse

import numpy as np
import pandas as pd

from config import DEFAULT_DATA


def create_demo():
    """固定随机种子，以便复现实验和测试；每小时每站两个会话共享遥测。"""
    rng = np.random.default_rng(72604)
    rows = []
    times = pd.date_range("2026-11-01", periods=24 * 7, freq="h")
    for timestamp in times:
        for hub in ["Library", "Residence", "Sports"]:
            ambient = 28 + 4 * np.sin((timestamp.hour - 7) / 24 * 2 * np.pi)
            solar = max(0, 35 * np.sin((timestamp.hour - 6) / 12 * np.pi))
            grid = max(0, 55 + 20 * (12 <= timestamp.hour < 17) + rng.normal(0, 6))
            for _ in range(2):
                charger = rng.choice(["AC", "DC"])
                duration = int(rng.integers(20, 160))
                energy = round(
                    float(
                        rng.uniform(4, 20) if charger == "AC" else rng.uniform(15, 60)
                    ),
                    2,
                )
                temperature = round(
                    float(ambient + energy * 0.27 + rng.normal(0, 4)), 1
                )
                rows.append(
                    {
                        "session_id": f"DEMO-{len(rows) + 1:05}",
                        "hub_id": hub,
                        "session_start": timestamp,
                        "charger_type": charger,
                        "user_type": rng.choice(["Student", "Staff", "Visitor"]),
                        "duration_minutes": duration,
                        "energy_kwh": energy,
                        "overstay_minutes": int(rng.choice([0, 5, 20, 21, 35, 60])),
                        "battery_temperature_c": temperature,
                        "ambient_temperature_c": round(ambient, 1),
                        "grid_load_kw": round(grid, 2),
                        "solar_generation_kw": round(solar, 2),
                        "base_energy_fee": round(
                            energy * (0.5 if charger == "AC" else 0.8), 2
                        ),
                        "soc_start_pct": 20,
                        "soc_end_pct": int(rng.integers(40, 100)),
                        "data_origin": "SYNTHETIC_DEMO",
                    }
                )
    frame = pd.DataFrame(rows)
    # 有意加入少量缺失值、无效数值、无效类别及重复行，验证清洗路径。
    for col in ["energy_kwh", "duration_minutes", "battery_temperature_c"]:
        frame.loc[rng.choice(len(frame), 10, replace=False), col] = np.nan
    frame.loc[0, "duration_minutes"] = 0
    frame.loc[1, "charger_type"] = "INVALID"
    frame.loc[2, "session_start"] = pd.NaT
    return pd.concat([frame, frame.iloc[[10]]], ignore_index=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_DATA))
    args = parser.parse_args()
    from pathlib import Path

    destination = Path(args.output)
    if destination.exists():
        raise SystemExit("目标已存在，为防止覆盖真实数据，请指定其他 --output 路径。")
    create_demo().to_csv(destination, index=False)
    print(f"Synthetic demonstration data saved: {destination}")
