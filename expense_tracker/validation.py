"""命令行输入校验与金额转换。"""

import re
from datetime import date


class InputError(ValueError):
    """用户输入不符合要求。"""


_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_AMOUNT_PATTERN = re.compile(r"([0-9]+)(?:\.([0-9]{1,2}))?\Z")


def validate_date(value):
    if not _DATE_PATTERN.fullmatch(value):
        raise InputError("日期格式无效，请使用 YYYY-MM-DD。")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise InputError("日期不是有效的日历日期。")
    return value


def validate_category(value):
    category = value.strip()
    if not category:
        raise InputError("分类不能为空。")
    return category


def validate_date_range(start_date=None, end_date=None):
    if start_date is not None:
        start_date = validate_date(start_date)
    if end_date is not None:
        end_date = validate_date(end_date)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InputError("起始日期不能晚于结束日期。")
    return start_date, end_date


def validate_expense_id(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise InputError("ID 必须是正整数。")
    try:
        expense_id = int(value)
    except ValueError:
        raise InputError("ID 必须是正整数。")
    if expense_id <= 0:
        raise InputError("ID 必须是正整数。")
    return expense_id


def amount_to_cents(value):
    match = _AMOUNT_PATTERN.fullmatch(value)
    if match is None:
        raise InputError("金额格式无效，请输入正数，最多两位小数（例如 12 或 12.30）。")

    whole, fraction = match.groups()
    cents = int(whole) * 100 + int((fraction or "").ljust(2, "0") or "0")
    if cents <= 0:
        raise InputError("金额必须大于 0。")
    return cents


def format_amount(cents):
    return "{0}.{1:02d}".format(cents // 100, cents % 100)
