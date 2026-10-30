from pathlib import Path
import sqlite3
import shutil
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "telarana.db"

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS recurring_income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            start_month TEXT NOT NULL,
            end_month TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS income_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recurring_id INTEGER NOT NULL REFERENCES recurring_income(id),
            amount REAL NOT NULL CHECK(amount >= 0),
            concept TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT
        );
        CREATE TABLE IF NOT EXISTS extra_income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            concept TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            entry_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recurring_obligation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            start_month TEXT NOT NULL,
            end_month TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS obligation_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recurring_id INTEGER NOT NULL REFERENCES recurring_obligation(id),
            amount REAL NOT NULL CHECK(amount >= 0),
            concept TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT
        );
        CREATE TABLE IF NOT EXISTS oneoff_obligation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            concept TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            entry_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target REAL NOT NULL CHECK(target > 0),
            saved REAL NOT NULL DEFAULT 0 CHECK(saved >= 0),
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS monthly_notes (
            month TEXT PRIMARY KEY,
            note TEXT DEFAULT ''
        );
        """)
        con.commit()

def month_now():
    return date.today().strftime("%Y-%m")

def add_recurring(kind, concept, amount, start_month, duration_months=None):
    table = "recurring_income" if kind == "income" else "recurring_obligation"
    versions = "income_versions" if kind == "income" else "obligation_versions"
    end = None
    if duration_months:
        y, m = map(int, start_month.split("-"))
        total = y * 12 + m - 1 + int(duration_months) - 1
        end = f"{total // 12:04d}-{total % 12 + 1:02d}"
    with connect() as con:
        cur = con.execute(f"INSERT INTO {table}(concept,amount,start_month,end_month) VALUES(?,?,?,?)",
                          (concept, amount, start_month, end))
        con.execute(f"INSERT INTO {versions}(recurring_id,amount,concept,valid_from,valid_to) VALUES(?,?,?,?,?)",
                    (cur.lastrowid, amount, concept, start_month, end))
        con.commit()

def add_monthly(kind, month, concept, amount, entry_date):
    table = "extra_income" if kind == "income" else "oneoff_obligation"
    with connect() as con:
        con.execute(f"INSERT INTO {table}(month,concept,amount,entry_date) VALUES(?,?,?,?)",
                    (month, concept, amount, entry_date))
        con.commit()

def get_month_data(month):
    with connect() as con:
        fixed = con.execute("""
            SELECT r.id, v.concept, v.amount FROM recurring_income r
            JOIN income_versions v ON v.recurring_id=r.id
            WHERE v.valid_from<=? AND (v.valid_to IS NULL OR v.valid_to>=?)
              AND r.start_month<=? AND (r.end_month IS NULL OR r.end_month>=?)
        """, (month, month, month, month)).fetchall()
        extras = con.execute("SELECT id,concept,amount,entry_date FROM extra_income WHERE month=? ORDER BY id DESC",(month,)).fetchall()
        recurring = con.execute("""
            SELECT r.id, v.concept, v.amount FROM recurring_obligation r
            JOIN obligation_versions v ON v.recurring_id=r.id
            WHERE v.valid_from<=? AND (v.valid_to IS NULL OR v.valid_to>=?)
              AND r.start_month<=? AND (r.end_month IS NULL OR r.end_month>=?)
        """, (month, month, month, month)).fetchall()
        oneoffs = con.execute("SELECT id,concept,amount,entry_date FROM oneoff_obligation WHERE month=? ORDER BY id DESC",(month,)).fetchall()
    fixed_total = sum(x["amount"] for x in fixed)
    extra_total = sum(x["amount"] for x in extras)
    rec_total = sum(x["amount"] for x in recurring)
    one_total = sum(x["amount"] for x in oneoffs)
    income = fixed_total + extra_total
    obligations = rec_total + one_total
    return {
        "fixed": fixed, "extras": extras, "recurring": recurring, "oneoffs": oneoffs,
        "fixed_total": fixed_total, "extra_total": extra_total,
        "rec_total": rec_total, "one_total": one_total,
        "income": income, "obligations": obligations, "result": income-obligations
    }

def _next_month(month):
    y,m = map(int, month.split("-"))
    return f"{y+1:04d}-01" if m == 12 else f"{y:04d}-{m+1:02d}"

def edit_recurring(kind, rid, concept, amount, effective_month):
    table = "recurring_income" if kind == "income" else "recurring_obligation"
    versions = "income_versions" if kind == "income" else "obligation_versions"
    with connect() as con:
        con.execute(f"UPDATE {versions} SET valid_to=? WHERE recurring_id=? AND valid_to IS NULL",
                    (_previous_month(effective_month), rid))
        con.execute(f"INSERT INTO {versions}(recurring_id,amount,concept,valid_from) VALUES(?,?,?,?)",
                    (rid, amount, concept, effective_month))
        con.execute(f"UPDATE {table} SET concept=?, amount=? WHERE id=?", (concept, amount, rid))
        con.commit()

def _previous_month(month):
    y,m = map(int, month.split("-"))
    return f"{y-1:04d}-12" if m == 1 else f"{y:04d}-{m-1:02d}"

def deactivate_recurring(kind, rid, effective_month):
    table = "recurring_income" if kind == "income" else "recurring_obligation"
    versions = "income_versions" if kind == "income" else "obligation_versions"
    with connect() as con:
        con.execute(f"UPDATE {versions} SET valid_to=? WHERE recurring_id=? AND valid_to IS NULL",
                    (_previous_month(effective_month), rid))
        con.execute(f"UPDATE {table} SET active=0 WHERE id=?", (rid,))
        con.commit()

def delete_monthly(kind, record_id):
    table = "extra_income" if kind == "income" else "oneoff_obligation"
    with connect() as con:
        con.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
        con.commit()

def list_recurring(kind):
    table = "recurring_income" if kind == "income" else "recurring_obligation"
    with connect() as con:
        return con.execute(f"SELECT * FROM {table} WHERE active=1 ORDER BY id DESC").fetchall()

def list_goals():
    with connect() as con:
        return con.execute("SELECT * FROM savings_goals WHERE active=1 ORDER BY id DESC").fetchall()

def add_goal(name, target):
    with connect() as con:
        con.execute("INSERT INTO savings_goals(name,target) VALUES(?,?)",(name,target))
        con.commit()

def add_goal_contribution(goal_id, amount):
    with connect() as con:
        con.execute("UPDATE savings_goals SET saved=saved+? WHERE id=?",(amount,goal_id))
        con.commit()

def delete_goal(goal_id):
    with connect() as con:
        con.execute("UPDATE savings_goals SET active=0 WHERE id=?",(goal_id,))
        con.commit()

def history(month_count=18):
    from datetime import datetime
    today = date.today()
    y,m = today.year,today.month
    months=[]
    for _ in range(month_count):
        key=f"{y:04d}-{m:02d}"
        d=get_month_data(key)
        months.append((key,d["income"],d["obligations"],d["result"]))
        m-=1
        if m==0: m=12; y-=1
    return list(reversed(months))

def backup_database(destination):
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, destination)
