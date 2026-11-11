"""统一保存项目路径和可解释的收费规则；没有学校实际电价时不冒充正式账单。"""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "ev_campus_dataset.csv"
OUTPUT_DIR = ROOT / "results"


@dataclass(frozen=True)
class PricingPolicy:
    """高峰规则是示例假设；15% 风险附加费来自 Section A 第二题。"""

    peak_start_hour: int = 12
    peak_end_hour: int = 17
    peak_rate: float = 0.10
    risk_rate: float = 0.15
    risk_temperature_c: float = 40.0
    overstay_minutes: float = 20.0
    carbon_factor: float = 0.475

    def __post_init__(self):
        if not 0 <= self.peak_start_hour < self.peak_end_hour <= 24:
            raise ValueError("高峰时间必须满足 0 <= 开始 < 结束 <= 24。")
        if not (0 <= self.peak_rate <= 1 and 0 <= self.risk_rate <= 1):
            raise ValueError("附加费比例必须在 0 到 1 之间。")


POLICY = PricingPolicy()
