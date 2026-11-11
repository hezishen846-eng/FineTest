"""有业务意义的边界测试：收费、缺失数据、隔离记录、筛选一致性与网页。"""

from decimal import Decimal
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from analytics import filter_sessions, kpis, previous_period, risk_mask
from pipeline import DataValidationError, clean_data, engineer_features, money
from section_a import total_surcharge
from visualizations import executive_panels, hourly_telemetry, operational_panels, plt

ROOT = Path(__file__).resolve().parents[1]


def records():
    """小型可手算样本，避免仅复述程序实现来验证程序本身。"""
    return pd.DataFrame(
        [
            {
                "session_id": f"S{i}",
                "hub_id": "H1",
                "session_start": time,
                "charger_type": "AC",
                "user_type": "Student",
                "duration_minutes": 60,
                "energy_kwh": energy,
                "overstay_minutes": overstay,
                "battery_temperature_c": temperature,
                "ambient_temperature_c": 30,
                "grid_load_kw": 50,
                "solar_generation_kw": 10,
                "base_energy_fee": 100,
            }
            for i, (time, energy, overstay, temperature) in enumerate(
                [
                    ("2026-11-01 12:00", 10, 21, 41),
                    ("2026-11-02 17:00", 20, 20, 50),
                    ("2026-11-03 23:59", 30, 30, 40),
                ]
            )
        ]
    )


def featured():
    return engineer_features(clean_data(records())[0])


class PipelineTests(unittest.TestCase):
    def test_formulas_and_additive_fees(self):
        row = featured().iloc[0]
        self.assertEqual(row["power_rate_kw"], 10)
        self.assertAlmostEqual(row["carbon_savings_kg"], 4.75)
        self.assertEqual(row["net_billable_amount"], 125)  # 100 + 10 + 15，非 126.5。

    def test_strict_boundaries(self):
        data = featured()
        self.assertEqual(data["billing_risk"].tolist(), [True, False, False])
        self.assertFalse(data.iloc[1]["is_peak"])  # 17:00 不属于 [12,17)。
        self.assertEqual(risk_mask(data, 41).tolist(), [False, False, False])

    def test_functional_surcharge(self):
        self.assertEqual(
            total_surcharge(records().to_dict("records")), Decimal("15.00")
        )
        self.assertEqual(total_surcharge([]), Decimal("0.00"))
        self.assertEqual(money(1.005), 1.01)

    def test_missing_and_invalid_numeric_imputed(self):
        raw = records()
        raw["energy_kwh"] = raw["energy_kwh"].astype(float)
        raw.loc[0, "energy_kwh"] = np.inf
        raw.loc[0, "duration_minutes"] = 0
        data, audit, _ = clean_data(raw)
        self.assertEqual(data.iloc[0]["energy_kwh"], 25)
        self.assertEqual(data.iloc[0]["duration_minutes"], 60)
        self.assertEqual(audit.imputed["energy_kwh"], 1)

    def test_all_missing_fails_explicitly(self):
        raw = records()
        raw["energy_kwh"] = np.nan
        with self.assertRaises(DataValidationError):
            clean_data(raw)

    def test_missing_schema(self):
        with self.assertRaises(DataValidationError):
            clean_data(records().drop(columns="session_start"))

    def test_categories_and_dates_quarantined(self):
        raw = records()
        raw.loc[0, "charger_type"] = "Wireless"
        raw.loc[1, "session_start"] = "not a date"
        data, audit, rejected = clean_data(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(audit.rejected_rows, 2)
        self.assertEqual(len(rejected), 2)

    def test_duplicate_conflict_not_silently_selected(self):
        raw = records()
        copy = raw.iloc[[0]].copy()
        copy["energy_kwh"] = 99
        data, audit, _ = clean_data(pd.concat([raw, copy], ignore_index=True))
        self.assertEqual(audit.rejected_rows, 2)
        self.assertNotIn("S0", set(data["session_id"]))

    def test_exact_duplicate_dropped(self):
        raw = records()
        data, audit, _ = clean_data(pd.concat([raw, raw.iloc[[0]]], ignore_index=True))
        self.assertEqual(len(data), 3)
        self.assertEqual(audit.exact_duplicates, 1)

    def test_inclusive_end_date_and_empty_chargers(self):
        data = featured()
        selected = filter_sessions(data, "2026-11-03", "2026-11-03", 0, ["AC"])
        self.assertEqual(selected["session_id"].tolist(), ["S2"])
        empty = filter_sessions(data, "2026-11-01", "2026-11-03", 0, [])
        self.assertTrue(empty.empty)
        self.assertEqual(kpis(empty)["alerts"], 0)

    def test_prior_period(self):
        previous = previous_period(featured(), "2026-11-03", "2026-11-03", 0, ["AC"])
        self.assertEqual(previous["session_id"].tolist(), ["S1"])

    def test_telemetry_not_double_counted(self):
        data = featured().iloc[[0]]
        duplicate = pd.concat([data, data], ignore_index=True)
        self.assertEqual(hourly_telemetry(duplicate).iloc[0]["grid_load_kw"], 50)

    def test_plots_empty_and_singleton(self):
        for frame in [featured().iloc[:0], featured().iloc[:1]]:
            for factory in [operational_panels, executive_panels]:
                figure = factory(frame)
                figure.canvas.draw()
                plt.close(figure)


class DashboardTests(unittest.TestCase):
    def test_overview_filters_and_empty_state(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)
        app.multiselect(key="chargers").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("0.00", app.metric[0].value)
        app.multiselect(key="chargers").set_value(["DC"]).run()
        context = app.session_state["context"]
        self.assertEqual(set(context["data"]["charger_type"]), {"DC"})
        app.slider(key="min_energy").set_value(30.0).run()
        self.assertTrue(
            (app.session_state["context"]["data"]["energy_kwh"] >= 30).all()
        )

    def test_alert_and_download_pages(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        app.switch_page("views/alerts.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("High-risk overstay", app.header[0].value)
        app.slider(key="temperature").set_value(80.0).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.success), 1)
        app.switch_page("views/data.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get("download_button")), 1)
        self.assertEqual(
            len(app.dataframe[0].value), len(app.session_state["context"]["data"])
        )


if __name__ == "__main__":
    unittest.main()
