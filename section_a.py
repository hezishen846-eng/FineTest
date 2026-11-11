"""Section A 的可运行代码示例；解释和设计取舍见 README 的对应表。"""

from decimal import Decimal, ROUND_HALF_UP
from functools import reduce

import numpy as np
import pandas as pd


def numpy_examples():
    """NumPy：矩阵切片与布尔掩码，避免逐个元素的 Python 循环。"""
    loads = np.arange(72, dtype=float).reshape(3, 24)
    peak_hours = loads[:, 12:17]  # 三个充电站、第 12 至 16 小时；切片通常共享内存。
    temperatures = np.array([37.5, 45.0, 46.2, 51.0])
    overheated = temperatures[temperatures > 45]  # 严格大于 45°C；布尔索引产生新数组。
    return peak_hours, overheated


def pandas_examples():
    """Pandas：利用列名、缺失值规则和分组操作保留业务语义。"""
    frame = pd.DataFrame(
        {
            "charger_type": ["AC", "DC", "AC", "DC"],
            "power_kw": [7.0, np.nan, 11.0, 50.0],
            "revenue": [10.0, 20.0, 8.0, 15.0],
        }
    )
    frame["power_kw"] = frame["power_kw"].fillna(frame["power_kw"].median())
    revenue = frame.groupby("charger_type")["revenue"].sum()
    return frame, revenue


def price_alert(record):
    """对基础费加收 15%；附加费收入不是含本金的 115% 总额。"""
    base = Decimal(str(record["base_energy_fee"]))
    extra = (base * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {**record, "surcharge": extra, "fee_after_surcharge": base + extra}


def high_risk_records(records):
    """filter / map 均返回惰性迭代器，不额外复制整个输入列表。

    lambda 只表达无副作用的筛选谓词；复杂金额逻辑放到命名函数中，便于测试。
    传入的 records 应当是已经过字段校验的记录。
    """
    risky = filter(
        lambda row: row["overstay_minutes"] > 20 and row["battery_temperature_c"] > 40,
        records,
    )
    return map(price_alert, risky)


def total_surcharge(records):
    """reduce 只累计附加费；初始值保证没有告警时仍返回 Decimal('0.00')。"""
    return reduce(
        lambda total, row: total + row["surcharge"],
        high_risk_records(records),
        Decimal("0.00"),
    )


def main():
    """打印样例与可手算的验证：100 和 80 的 15% 附加费合计 27。"""
    peak, hot = numpy_examples()
    frame, revenue = pandas_examples()
    print("NumPy peak-hour slice:\n", peak)
    print("Temperatures >45°C:", hot)
    print("Pandas median imputation:\n", frame)
    print("Revenue by charger type:\n", revenue)
    records = [
        {"overstay_minutes": 21, "battery_temperature_c": 41, "base_energy_fee": 100},
        {"overstay_minutes": 30, "battery_temperature_c": 50, "base_energy_fee": 80},
        {"overstay_minutes": 20, "battery_temperature_c": 50, "base_energy_fee": 60},
    ]
    print("High-risk fee examples:", list(high_risk_records(records)))
    print("Total surcharge revenue:", total_surcharge(records))


if __name__ == "__main__":
    main()
