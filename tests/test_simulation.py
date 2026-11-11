"""模拟补充必须可复现、可追溯，并保留原始账单。"""

from io import BytesIO
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from config import ROOT
from course_data import reconcile_sources
from pipeline import load_pipeline
from simulate_missing import augment_for_demo
from visualizations import hourly_telemetry


class SimulationTests(unittest.TestCase):
    def test_original_columns_preserved_and_reproducible(self):
        source, _, _, _ = reconcile_sources()
        result = augment_for_demo(source)
        pd.testing.assert_frame_equal(result[source.columns], source)
        pd.testing.assert_frame_equal(result, augment_for_demo(source))
        shuffled = augment_for_demo(source.sample(frac=1, random_state=1))
        pd.testing.assert_frame_equal(result.sort_index(), shuffled.sort_index())
        self.assertTrue(result.session_start.dt.hour.eq(source.start_hour).all())
        night = (result.start_hour <= 6) | (result.start_hour >= 18)
        self.assertTrue(result.loc[night, "solar_generation_kw"].eq(0).all())
        with self.assertRaises(ValueError):
            augment_for_demo(result)

    def test_csv_roundtrip_and_no_double_counting(self):
        source, _, _, _ = reconcile_sources()
        result = augment_for_demo(source)
        loaded, _, _ = load_pipeline(BytesIO(result.to_csv(index=False).encode()))
        self.assertEqual(
            loaded.net_billable_amount.tolist(), source.net_billable_amount.tolist()
        )
        self.assertTrue(
            loaded.supplement_origin.eq("SIMULATED_FOR_DEMONSTRATION").all()
        )
        snapshot = result.iloc[[0]]
        hourly = hourly_telemetry(pd.concat([snapshot, snapshot]))
        self.assertEqual(hourly.iloc[0].grid_load_kw, snapshot.iloc[0].grid_load_kw)

    def test_default_dashboard_discloses_simulation(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNotNone(app.session_state["context"]["simulation"])
        self.assertTrue(any("DEMONSTRATION MODE" in x.value for x in app.info))
        self.assertFalse(any("unavailable" in x.value for x in app.warning))
        self.assertEqual(len(app.date_input), 1)
        self.assertEqual(len(app.metric), 4)
        app.date_input(key="dates").set_value(
            (pd.Timestamp("2026-09-05").date(), pd.Timestamp("2026-09-06").date())
        ).run()
        selected = app.session_state["context"]["data"]
        self.assertTrue(selected.session_start.dt.day.between(5, 6).all())
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
