"""CSV 导出功能。"""

import csv
from pathlib import Path

from .database import list_expenses
from .validation import format_amount


class ExportError(Exception):
    """CSV 目标路径或写入操作失败。"""


def export_expenses(database_path, output_path):
    output = Path(output_path).expanduser()
    if not output.parent.exists() or not output.parent.is_dir():
        raise ExportError("输出目录不存在：{0}".format(output.parent))

    expenses = list_expenses(database_path)
    created = False
    try:
        with output.open("x", encoding="utf-8-sig", newline="") as stream:
            created = True
            writer = csv.writer(stream)
            writer.writerow(("id", "date", "category", "amount", "note"))
            for expense in expenses:
                writer.writerow(
                    (
                        expense.id,
                        expense.expense_date,
                        expense.category,
                        format_amount(expense.amount_cents),
                        expense.note,
                    )
                )
    except FileExistsError:
        raise ExportError("输出文件已存在，拒绝覆盖：{0}".format(output))
    except (OSError, UnicodeError, csv.Error) as exc:
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise ExportError("无法写入 CSV 文件：{0}".format(exc))
    return len(expenses)
