"""SQLite 持久化层。金额以整数分保存，保证计算精确。"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Expense:
    id: int
    expense_date: str
    category: str
    amount_cents: int
    note: str


def default_database_path():
    return Path(__file__).resolve().parent.parent / "expenses.db"


def _connect(database_path):
    path = Path(database_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _database(database_path):
    connection = _connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _initialize(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            category TEXT NOT NULL COLLATE BINARY,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            note TEXT NOT NULL DEFAULT ''
        )
        """
    )


def add_expense(database_path, expense_date, category, amount_cents, note=""):
    with _database(database_path) as connection:
        _initialize(connection)
        cursor = connection.execute(
            """
            INSERT INTO expenses (expense_date, category, amount_cents, note)
            VALUES (?, ?, ?, ?)
            """,
            (expense_date, category, amount_cents, note),
        )
        row = connection.execute(
            "SELECT id, expense_date, category, amount_cents, note FROM expenses WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return _row_to_expense(row)


def _filter_clause(start_date=None, end_date=None, category=None):
    conditions = []
    parameters = []
    if start_date is not None:
        conditions.append("expense_date >= ?")
        parameters.append(start_date)
    if end_date is not None:
        conditions.append("expense_date <= ?")
        parameters.append(end_date)
    if category is not None:
        conditions.append("category = ? COLLATE BINARY")
        parameters.append(category)
    if conditions:
        return " WHERE " + " AND ".join(conditions), parameters
    return "", parameters


def list_expenses(database_path, start_date=None, end_date=None, category=None):
    where_clause, parameters = _filter_clause(start_date, end_date, category)
    with _database(database_path) as connection:
        _initialize(connection)
        rows = connection.execute(
            """
            SELECT id, expense_date, category, amount_cents, note
            FROM expenses
            """ + where_clause + " ORDER BY expense_date ASC, id ASC",
            parameters,
        ).fetchall()
        return [_row_to_expense(row) for row in rows]


def summarize_expenses(database_path, start_date=None, end_date=None, category=None):
    where_clause, parameters = _filter_clause(start_date, end_date, category)
    with _database(database_path) as connection:
        _initialize(connection)
        rows = connection.execute(
            """
            SELECT category, SUM(amount_cents) AS total_cents
            FROM expenses
            """ + where_clause + """
            GROUP BY category COLLATE BINARY
            ORDER BY category COLLATE BINARY ASC
            """,
            parameters,
        ).fetchall()
        total_row = connection.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total_cents FROM expenses" + where_clause,
            parameters,
        ).fetchone()
        return [(row["category"], row["total_cents"]) for row in rows], total_row["total_cents"]


def delete_expense(database_path, expense_id):
    with _database(database_path) as connection:
        _initialize(connection)
        cursor = connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        return cursor.rowcount == 1


def _row_to_expense(row):
    return Expense(
        id=row["id"],
        expense_date=row["expense_date"],
        category=row["category"],
        amount_cents=row["amount_cents"],
        note=row["note"],
    )
