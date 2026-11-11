"""验证实际附件对齐、缺项不伪造及销售探索的边界。"""

import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from config import ROOT
from course_data import load_course, reconcile_sources, load_sales
from pipeline import DataValidationError


class CourseDataTests(unittest.TestCase):
    def test_all_supplied_rows_reconcile(self):
        data, audit, rejected, comparison = reconcile_sources()
        self.assertEqual(len(data), 1200)
        self.assertEqual(comparison.mismatched_rows.sum(), 0)
        self.assertEqual(audit.imputed["duration_minutes"], 25)
        self.assertEqual(audit.imputed["energy_kwh"], 35)
        self.assertTrue(rejected.empty)
        self.assertNotIn("session_start", data)
        self.assertNotIn("grid_load_kw", data)
        supplied = pd.read_csv(ROOT / "data/cleaned_energy_sales_data.csv")
        self.assertAlmostEqual(
            data.net_billable_amount.sum(), supplied.Net_Billable_MYR.sum()
        )

    def test_course_billing_boundaries(self):
        raw = pd.read_csv(ROOT / "ev_campus_dataset.csv").head(2).copy()
        raw["Duration_Mins"] = 60
        raw["Charger_Type"] = "AC"
        raw["Start_Hour"] = [17, 18]
        raw["Overstay_Mins"] = [15, 16]
        data, _, _ = load_course(raw)
        self.assertEqual(data.net_billable_amount.tolist(), [7.5, 6.5])

    def test_tampered_supplied_bill_rejected(self):
        raw = pd.read_csv(ROOT / "data/cleaned_energy_sales_data.csv")
        raw.loc[0, "Net_Billable_MYR"] += 1
        with self.assertRaises(DataValidationError):
            load_course(raw)

    def test_sales_preserves_original_unknown_values(self):
        sales = load_sales()
        self.assertEqual(len(sales), 500)
        self.assertEqual(sales.Units_Sold.isna().sum(), 15)
        self.assertEqual(sales.Total_Revenue_MYR.isna().sum(), 20)
        mask = sales.Revenue_Reconstructed
        pd.testing.assert_series_equal(
            sales.loc[mask, "Analysis_Revenue_MYR"],
            sales.loc[mask, "Units_Sold"] * sales.loc[mask, "Unit_Price_MYR"],
            check_names=False,
        )

    def test_hour_filter_and_sales_page(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.checkbox(key="demo_mode").set_value(False).run()
        app.slider(key="hours").set_value((12, 17)).run()
        self.assertTrue(
            app.session_state["context"]["data"].start_hour.between(12, 17).all()
        )
        app.switch_page("views/sales.py").run()
        self.assertEqual(len(app.exception), 0)
        app.multiselect(key="sales_hubs").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe[0].value), 0)


if __name__ == "__main__":
    unittest.main()
