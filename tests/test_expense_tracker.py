import contextlib
import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from expense_tracker.cli import main
from expense_tracker.database import list_expenses, summarize_expenses


class ExpenseTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "nested" / "test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(["--db", str(self.database_path)] + list(args))
        return status, stdout.getvalue(), stderr.getvalue()

    def add(self, expense_date, category, amount, note=None):
        args = ["add", expense_date, category, amount]
        if note is not None:
            args.extend(["--note", note])
        return self.run_cli(*args)

    def test_add_assigns_integer_id_and_persists_after_reopening(self):
        status, output, error = self.add("2026-10-09", "餐饮", "36.50", "午餐")
        self.assertEqual(status, 0, error)
        self.assertIn("记录 ID：1", output)

        records = list_expenses(self.database_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, 1)
        self.assertEqual(records[0].category, "餐饮")
        self.assertEqual(records[0].amount_cents, 3650)
        self.assertEqual(records[0].note, "午餐")

        status, output, error = self.run_cli("list")
        self.assertEqual(status, 0, error)
        self.assertIn("金额：36.50", output)
        self.assertIn("备注：午餐", output)

    def test_list_sorts_by_date_then_id(self):
        self.add("2026-10-10", "晚餐", "20")
        self.add("2026-10-09", "早餐", "8")
        self.add("2026-10-10", "交通", "5")

        status, output, error = self.run_cli("list")
        self.assertEqual(status, 0, error)
        self.assertLess(output.index("ID：2"), output.index("ID：1"))
        self.assertLess(output.index("ID：1"), output.index("ID：3"))

    def test_filtered_list_uses_inclusive_date_bounds_and_exact_category(self):
        self.add("2026-10-08", "餐饮", "1.00")
        self.add("2026-10-09", "餐饮", "2.00")
        self.add("2026-10-10", "餐饮", "3.00")
        self.add("2026-10-10", "交通", "4.00")
        self.add("2026-10-11", "餐饮", "5.00")

        status, output, error = self.run_cli(
            "list",
            "--start-date", "2026-10-09",
            "--end-date", "2026-10-10",
            "--category", " 餐饮 ",
        )
        self.assertEqual(status, 0, error)
        self.assertIn("ID：2", output)
        self.assertIn("ID：3", output)
        self.assertNotIn("ID：1", output)
        self.assertNotIn("ID：4", output)
        self.assertNotIn("ID：5", output)
        self.assertLess(output.index("ID：2"), output.index("ID：3"))

    def test_filtered_list_allows_one_sided_date_ranges(self):
        self.add("2026-10-08", "餐饮", "1.00")
        self.add("2026-10-09", "餐饮", "2.00")
        self.add("2026-10-10", "餐饮", "3.00")
        self.add("2026-10-11", "餐饮", "4.00")

        status, start_output, error = self.run_cli("list", "--start-date", "2026-10-10")
        self.assertEqual(status, 0, error)
        self.assertNotIn("ID：1", start_output)
        self.assertNotIn("ID：2", start_output)
        self.assertIn("ID：3", start_output)
        self.assertIn("ID：4", start_output)

        status, end_output, error = self.run_cli("list", "--end-date", "2026-10-09")
        self.assertEqual(status, 0, error)
        self.assertIn("ID：1", end_output)
        self.assertIn("ID：2", end_output)
        self.assertNotIn("ID：3", end_output)
        self.assertNotIn("ID：4", end_output)

    def test_filtered_summary_applies_date_and_category_together(self):
        self.add("2026-10-08", "餐饮", "1.00")
        self.add("2026-10-09", "餐饮", "2.10")
        self.add("2026-10-10", "餐饮", "3.20")
        self.add("2026-10-10", "交通", "40.00")
        self.add("2026-10-11", "餐饮", "50.00")

        status, output, error = self.run_cli(
            "summary",
            "--start-date", "2026-10-09",
            "--end-date", "2026-10-10",
            "--category", "餐饮",
        )
        self.assertEqual(status, 0, error)
        self.assertIn("餐饮：5.30", output)
        self.assertIn("全部支出：5.30", output)
        self.assertNotIn("交通", output)

    def test_no_filter_matches_show_empty_state_and_zero_total(self):
        self.add("2026-10-09", "餐饮", "1.00")

        status, list_output, error = self.run_cli("list", "--category", "不存在")
        self.assertEqual(status, 0, error)
        self.assertIn("暂无支出记录。", list_output)

        status, summary_output, error = self.run_cli("summary", "--category", "不存在")
        self.assertEqual(status, 0, error)
        self.assertIn("暂无支出记录。", summary_output)
        self.assertIn("全部支出：0.00", summary_output)

    def test_invalid_filter_dates_and_reversed_range_fail(self):
        self.add("2026-10-09", "餐饮", "1.00")
        for options, expected_error in (
            (("--start-date", "2025-02-29"), "日历日期"),
            (("--start-date", "2026-10-10", "--end-date", "2026-10-09"), "起始日期不能晚于结束日期"),
        ):
            with self.subTest(options=options):
                status, output, error = self.run_cli("list", *options)
                self.assertNotEqual(status, 0)
                self.assertIn(expected_error, error)
                self.assertEqual(len(list_expenses(self.database_path)), 1)

    def test_delete_removes_only_the_selected_record_and_persists(self):
        self.add("2026-10-09", "餐饮", "1.00")
        self.add("2026-10-10", "交通", "2.00")
        self.add("2026-10-11", "日用品", "3.00")

        status, output, error = self.run_cli("delete", "2")
        self.assertEqual(status, 0, error)
        self.assertIn("删除成功", output)
        self.assertIn("ID：2", output)

        status, output, error = self.run_cli("list")
        self.assertEqual(status, 0, error)
        self.assertIn("ID：1", output)
        self.assertNotIn("ID：2", output)
        self.assertIn("ID：3", output)
        status, output, error = self.run_cli("summary")
        self.assertEqual(status, 0, error)
        self.assertIn("全部支出：4.00", output)

    def test_delete_missing_or_invalid_id_fails_without_changing_records(self):
        self.add("2026-10-09", "餐饮", "1.00")
        original = list_expenses(self.database_path)

        status, output, error = self.run_cli("delete", "99")
        self.assertNotEqual(status, 0)
        self.assertIn("未找到", error)
        self.assertEqual(list_expenses(self.database_path), original)

        for invalid_id in ("0", "-1", "abc", "1.5"):
            with self.subTest(invalid_id=invalid_id):
                status, output, error = self.run_cli("delete", invalid_id)
                self.assertNotEqual(status, 0)
                self.assertIn("ID 必须是正整数", error)
                self.assertEqual(list_expenses(self.database_path), original)

    def test_export_writes_utf8_bom_csv_with_sorted_rows_and_special_characters(self):
        special_note = '午餐, 店员说"很好"\n第二行'
        self.add("2026-10-10", "餐饮", "12.30", special_note)
        self.add("2026-10-09", "交通,出行", "5", "公交")
        original = list_expenses(self.database_path)
        output_path = Path(self.temp_dir.name) / "expenses.csv"

        status, output, error = self.run_cli("export", "--output", str(output_path))
        self.assertEqual(status, 0, error)
        self.assertIn("导出成功，共导出 2 条记录", output)
        self.assertTrue(output_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        with output_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, ["id", "date", "category", "amount", "note"])
        self.assertEqual([row["date"] for row in rows], ["2026-10-09", "2026-10-10"])
        self.assertEqual(rows[0]["category"], "交通,出行")
        self.assertEqual(rows[0]["amount"], "5.00")
        self.assertEqual(rows[0]["note"], "公交")
        self.assertEqual(rows[1]["note"], special_note)
        self.assertEqual(list_expenses(self.database_path), original)

    def test_export_empty_database_writes_header_only(self):
        output_path = Path(self.temp_dir.name) / "empty.csv"
        status, output, error = self.run_cli("export", "--output", str(output_path))
        self.assertEqual(status, 0, error)
        with output_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ["id", "date", "category", "amount", "note"])
            self.assertEqual(list(reader), [])

    def test_export_refuses_to_overwrite_and_reports_missing_parent(self):
        output_path = Path(self.temp_dir.name) / "existing.csv"
        output_path.write_text("preserve this content", encoding="utf-8")

        status, output, error = self.run_cli("export", "--output", str(output_path))
        self.assertNotEqual(status, 0)
        self.assertIn("已存在", error)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "preserve this content")

        missing_path = Path(self.temp_dir.name) / "missing" / "expenses.csv"
        status, output, error = self.run_cli("export", "--output", str(missing_path))
        self.assertNotEqual(status, 0)
        self.assertIn("输出目录不存在", error)
        self.assertFalse(missing_path.exists())

    def test_first_phase_database_keeps_existing_records(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE expenses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        expense_date TEXT NOT NULL,
                        category TEXT NOT NULL COLLATE BINARY,
                        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                        note TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO expenses (id, expense_date, category, amount_cents, note) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (41, "2026-10-09", "餐饮", 1234, "旧数据"),
                )

        status, output, error = self.run_cli("list", "--category", "餐饮")
        self.assertEqual(status, 0, error)
        self.assertIn("ID：41", output)
        self.assertIn("备注：旧数据", output)

    def test_summary_uses_exact_integer_cents(self):
        self.add("2026-10-09", "餐饮", "1.10")
        self.add("2026-10-09", "餐饮", "2.20")
        self.add("2026-10-09", "交通", "3.05")

        categories, total_cents = summarize_expenses(self.database_path)
        self.assertEqual(categories, [("交通", 305), ("餐饮", 330)])
        self.assertEqual(total_cents, 635)

        status, output, error = self.run_cli("summary")
        self.assertEqual(status, 0, error)
        self.assertIn("交通：3.05", output)
        self.assertIn("餐饮：3.30", output)
        self.assertIn("全部支出：6.35", output)

    def test_categories_are_trimmed_then_grouped_exactly(self):
        self.add("2026-10-09", " Food ", "1.10")
        self.add("2026-10-09", "Food", "2.20")
        self.add("2026-10-09", "food", "3.05")

        categories, total_cents = summarize_expenses(self.database_path)
        self.assertEqual(categories, [("Food", 330), ("food", 305)])
        self.assertEqual(total_cents, 635)

    def test_blank_category_is_rejected_without_adding_record(self):
        status, output, error = self.add("2026-10-09", "   ", "10.00")
        self.assertNotEqual(status, 0)
        self.assertIn("不能为空", error)
        self.assertEqual(list_expenses(self.database_path), [])

    def test_empty_list_and_summary_are_explicit(self):
        status, output, error = self.run_cli("list")
        self.assertEqual(status, 0, error)
        self.assertIn("暂无支出记录。", output)

        status, output, error = self.run_cli("summary")
        self.assertEqual(status, 0, error)
        self.assertIn("全部支出：0.00", output)

    def test_invalid_calendar_date_does_not_add_record(self):
        status, output, error = self.add("2025-02-29", "餐饮", "10.00")
        self.assertNotEqual(status, 0)
        self.assertIn("日历日期", error)
        self.assertEqual(list_expenses(self.database_path), [])

    def test_invalid_amounts_do_not_add_records(self):
        for amount in ("0", "-1.00", "1e2", "1.001"):
            with self.subTest(amount=amount):
                status, output, error = self.add("2026-10-09", "餐饮", amount)
                self.assertNotEqual(status, 0)
                self.assertIn("金额", error)
                self.assertEqual(list_expenses(self.database_path), [])


if __name__ == "__main__":
    unittest.main()
