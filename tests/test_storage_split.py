from __future__ import annotations

import os
import tempfile
import unittest

from futures_crawler.models import OutputConfig
from futures_crawler.storage import COMBINED_SHORT_START_LINE, TOTAL_LABEL, read_combined_report_sections, write_futures_split_rows


class StorageSplitTests(unittest.TestCase):
    def test_top_20_and_total_row(self) -> None:
        rows = []
        for i in range(25):
            rows.append(
                {
                    "会员简称": f"会员{i}",
                    "多单持仓": str(1000 - i),
                    "多单增减": str(i),
                    "多单持仓均价": "9000",
                    "空单持仓": str(2000 - i),
                    "空单增减": str(-i),
                    "空单持仓均价": "9100",
                    "收盘价": "9366",
                }
            )

        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "棕榈P2609_2026-06-27.csv")
            out_csv = write_futures_split_rows(
                output=OutputConfig(csv_path=out, encoding="utf-8", newline=""),
                rows=rows,
            )
            long_rows, embedded_short_rows, short_start_line = read_combined_report_sections(out_csv)

        self.assertEqual(out_csv, out)
        self.assertEqual(os.path.basename(out_csv), "棕榈P2609_2026-06-27.csv")
        self.assertEqual(short_start_line, COMBINED_SHORT_START_LINE)
        self.assertEqual(len(long_rows), 22)
        self.assertEqual(len(embedded_short_rows), 22)
        self.assertEqual(long_rows[-2]["名次"], TOTAL_LABEL)
        self.assertEqual(embedded_short_rows[-2]["名次"], TOTAL_LABEL)
        self.assertEqual(long_rows[0]["名次"], "1")
        self.assertEqual(long_rows[19]["名次"], "20")
        self.assertEqual(embedded_short_rows[0]["名次"], "1")
        self.assertEqual(embedded_short_rows[19]["名次"], "20")
        self.assertEqual(long_rows[-2]["多单持仓"], "19810")
        self.assertEqual(long_rows[-2]["多单增减"], "190")
        self.assertEqual(long_rows[0]["单量占比"], "5.05%")
        self.assertEqual(long_rows[0]["持仓金额"], "9000000.00")
        self.assertEqual(long_rows[0]["多单资金"], "5.05%")
        self.assertEqual(long_rows[-2]["单量占比"], "100.00%")
        self.assertEqual(long_rows[-2]["多单资金"], "100.00%")
        long_amount_total = sum(float(r["持仓金额"]) for r in long_rows[:-2])
        self.assertEqual(long_rows[-2]["持仓金额"], f"{long_amount_total:.2f}")
        self.assertEqual(embedded_short_rows[-2]["空单持仓"], "39810")
        self.assertEqual(embedded_short_rows[-2]["空单增减"], "-190")
        self.assertEqual(long_rows[-2]["多单持仓均价"], "看多均价")
        self.assertEqual(long_rows[-2]["收盘价"], "9000.00")
        self.assertEqual(long_rows[-1]["多单持仓均价"], "持多均价")
        self.assertEqual(long_rows[-1]["收盘价"], f"{long_amount_total / 19810:.2f}")
        self.assertEqual(embedded_short_rows[-2]["空单持仓均价"], "看空均价")
        self.assertEqual(embedded_short_rows[-2]["收盘价"], "9100.00")
        short_amount_total = sum(float(r["持仓金额"]) for r in embedded_short_rows[:-2])
        self.assertEqual(embedded_short_rows[-1]["空单持仓均价"], "持空均价")
        self.assertEqual(embedded_short_rows[-1]["收盘价"], f"{short_amount_total / 39810:.2f}")
        self.assertEqual(embedded_short_rows[0]["空单资金"], "5.02%")
        self.assertEqual(embedded_short_rows[-2]["空单资金"], "100.00%")


if __name__ == "__main__":
    unittest.main()
