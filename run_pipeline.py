"""命令行入口：清洗、导出、打印统计并生成五种题目要求的图表。"""

import argparse
import logging
from pathlib import Path
import json

from config import DEFAULT_DATA, OUTPUT_DIR
from pipeline import DataValidationError, export_results, load_pipeline
from visualizations import save_charts
from course_data import reconcile_sources, load_sales
from simulate_missing import export_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if Path(args.data).resolve() == DEFAULT_DATA.resolve():
            data, audit, rejected, comparison = reconcile_sources()
            if comparison.mismatched_rows.sum():
                raise DataValidationError("原始与已清理文件不一致。")
            Path(args.output).mkdir(parents=True, exist_ok=True)
            comparison.to_csv(
                Path(args.output) / "source_reconciliation.csv", index=False
            )
            sales = load_sales()
            sales.to_csv(Path(args.output) / "sales_exploration.csv", index=False)
            summary = {
                "rows": len(sales),
                "missing_units": int(sales.Units_Sold.isna().sum()),
                "original_missing_revenue": int(sales.Total_Revenue_MYR.isna().sum()),
                "reconstructed_revenue_rows": int(sales.Revenue_Reconstructed.sum()),
                "unresolved_revenue_rows": int(sales.Analysis_Revenue_MYR.isna().sum()),
                "revenue_mismatches": int(sales.Revenue_Mismatch.sum()),
                "known_analysis_revenue_MYR": float(sales.Analysis_Revenue_MYR.sum()),
            }
            (Path(args.output) / "sales_quality_report.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            sales.groupby("Category").Analysis_Revenue_MYR.agg(["count", "sum"]).to_csv(
                Path(args.output) / "sales_revenue_by_category.csv"
            )
        else:
            data, audit, rejected = load_pipeline(args.data)
        export_results(data, audit, rejected, args.output)
        save_charts(data, args.output)
        if "billing_source" in data and "session_start" not in data:
            export_demo(data, Path(args.output) / "demonstration")
    except (DataValidationError, OSError, ValueError) as exc:
        logging.error("Pipeline failed: %s", exc)
        return 1
    print("Cleaning audit:", audit)
    print(
        "\nSummary statistics:\n",
        data.select_dtypes("number").describe().round(2).to_string(),
    )
    print(
        "\nRevenue by charger type:\n",
        data.groupby("charger_type")["net_billable_amount"].sum().round(2).to_string(),
    )
    logging.info("Outputs saved to %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
