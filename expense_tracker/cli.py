"""支出记录命令行入口。"""

import argparse
import sqlite3
import sys

from .database import (
    add_expense,
    default_database_path,
    delete_expense,
    list_expenses,
    summarize_expenses,
)
from .exporter import ExportError, export_expenses
from .validation import (
    InputError,
    amount_to_cents,
    format_amount,
    validate_category,
    validate_date,
    validate_date_range,
    validate_expense_id,
)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m expense_tracker",
        description="记录个人日常支出，并查看记录和分类汇总。",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help="SQLite 数据库文件路径（默认：项目根目录下的 expenses.db）",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="新增一条支出")
    add_parser.add_argument("date", help="日期，格式 YYYY-MM-DD")
    add_parser.add_argument("category", help="支出分类")
    add_parser.add_argument("amount", help="金额（元），正数，最多两位小数")
    add_parser.add_argument("--note", default="", help="可选备注，支持中文")

    list_parser = commands.add_parser("list", help="查看支出记录，可按日期和分类筛选")
    _add_filter_arguments(list_parser)

    summary_parser = commands.add_parser("summary", help="查看分类合计和全部支出，可筛选")
    _add_filter_arguments(summary_parser)

    delete_parser = commands.add_parser("delete", help="按 ID 删除一条支出")
    delete_parser.add_argument("id", metavar="ID", help="要删除的正整数记录 ID")

    export_parser = commands.add_parser("export", help="将全部记录导出为 CSV")
    export_parser.add_argument("--output", required=True, metavar="PATH", help="CSV 输出文件路径")
    return parser


def _add_filter_arguments(parser):
    parser.add_argument("--start-date", metavar="YYYY-MM-DD", help="筛选起始日期（包含当天）")
    parser.add_argument("--end-date", metavar="YYYY-MM-DD", help="筛选结束日期（包含当天）")
    parser.add_argument("--category", help="按分类精确筛选")


def _print_expenses(expenses):
    if not expenses:
        print("暂无支出记录。")
        return

    for index, expense in enumerate(expenses):
        if index:
            print()
        print("ID：{0}".format(expense.id))
        print("日期：{0}".format(expense.expense_date))
        print("分类：{0}".format(expense.category))
        print("金额：{0}".format(format_amount(expense.amount_cents)))
        print("备注：{0}".format(expense.note))


def _print_summary(categories, total_cents):
    if categories:
        print("分类汇总：")
        for category, amount_cents in categories:
            print("{0}：{1}".format(category, format_amount(amount_cents)))
    else:
        print("暂无支出记录。")
    print("全部支出：{0}".format(format_amount(total_cents)))


def main(argv=None):
    args = _build_parser().parse_args(argv)
    database_path = args.db if args.db is not None else default_database_path()

    try:
        if args.command == "add":
            # 先完成所有输入校验，再连接数据库，避免无效输入写入记录。
            expense_date = validate_date(args.date)
            category = validate_category(args.category)
            amount_cents = amount_to_cents(args.amount)
            expense = add_expense(database_path, expense_date, category, amount_cents, args.note)
            print("新增成功，记录 ID：{0}".format(expense.id))
        elif args.command == "list":
            start_date, end_date = validate_date_range(args.start_date, args.end_date)
            category = validate_category(args.category) if args.category is not None else None
            _print_expenses(list_expenses(database_path, start_date, end_date, category))
        elif args.command == "summary":
            start_date, end_date = validate_date_range(args.start_date, args.end_date)
            category = validate_category(args.category) if args.category is not None else None
            categories, total_cents = summarize_expenses(
                database_path, start_date, end_date, category
            )
            _print_summary(categories, total_cents)
        elif args.command == "delete":
            expense_id = validate_expense_id(args.id)
            if delete_expense(database_path, expense_id):
                print("删除成功，记录 ID：{0}".format(expense_id))
            else:
                print("错误：未找到 ID 为 {0} 的支出记录。".format(expense_id), file=sys.stderr)
                return 1
        else:
            count = export_expenses(database_path, args.output)
            print("导出成功，共导出 {0} 条记录：{1}".format(count, args.output))
    except InputError as exc:
        print("错误：{0}".format(exc), file=sys.stderr)
        return 2
    except ExportError as exc:
        print("错误：{0}".format(exc), file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as exc:
        print("错误：无法访问数据库：{0}".format(exc), file=sys.stderr)
        return 1
    return 0
