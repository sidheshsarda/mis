from sqlalchemy import update

def update_issue_for_bin(bin_no: int, issue_date, issue_time, issue_spell, issue_rolls):
    """
    Update issue columns for the latest entry in a bin (no id column, so use entry_date, entry_time, bin_no, jute_quality_id).
    """
    # Find latest row for bin by max(entry_date, entry_time)
    find_sql = text("""
        SELECT entry_date, entry_time, bin_no, jute_quality_id
        FROM EMPMILL12.spreader_prod_entry
        WHERE bin_no = :bin_no
        ORDER BY entry_date DESC, entry_time DESC LIMIT 1
    """)
    update_sql = text("""
        UPDATE EMPMILL12.spreader_prod_entry
        SET issue_date = :issue_date,
            issue_time = :issue_time,
            issue_spell = :issue_spell,
            issue_rolls = :issue_rolls
        WHERE bin_no = :bin_no AND entry_date = :entry_date AND entry_time = :entry_time AND jute_quality_id = :jute_quality_id
    """)
    with engine.begin() as conn:
        result = conn.execute(find_sql, {"bin_no": bin_no})
        row = result.fetchone()
        if row:
            conn.execute(update_sql, {
                "issue_date": issue_date,
                "issue_time": issue_time,
                "issue_spell": issue_spell,
                "issue_rolls": issue_rolls,
                "bin_no": bin_no,
                "entry_date": row[0],
                "entry_time": row[1],
                "jute_quality_id": row[3],
            })

def fetch_bins_with_stock():
    """
    Fetch bins with current stock and maturity info.
    """
    sql = text(
        """
        SELECT
            bin_no,
            jute_quality_id,
            no_of_rolls,
            issue_rolls,
            entry_date,
            entry_time
        FROM EMPMILL12.spreader_prod_entry
        WHERE (no_of_rolls - IFNULL(issue_rolls, 0)) > 0
        ORDER BY bin_no
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    return df
import datetime
from typing import Optional
import pandas as pd
from sqlalchemy import text
from db import engine


def ensure_spreader_table() -> None:
    """Create the EMPMILL12.spreader_prod_entry table if it doesn't exist."""
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS EMPMILL12.spreader_prod_entry (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            entry_date DATE NOT NULL,
            spell CHAR(1) NOT NULL,
            spreader_no VARCHAR(64) NOT NULL,
            jute_quality_id INT NOT NULL,
            no_of_rolls INT NOT NULL,
            entry_time INT NOT NULL,
            bin_no INT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_entry_date (entry_date),
            KEY idx_spell (spell),
            KEY idx_spreader_no (spreader_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    try:
        with engine.begin() as conn:
            conn.execute(ddl)
    except Exception:
        # If we cannot create (permissions), ignore; page will still error with clear message.
        pass


def insert_spreader_prod_entry(
    entry_date: datetime.date,
    spell: str,
    spreader_no: str,
    jute_quality_id: int,
    no_of_rolls: int,
    entry_time: int,
    bin_no: int,
) -> Optional[int]:
    """
    Insert one row into EMPMILL12.spreader_prod_entry. Returns inserted id or None.
    """
    sql = text(
        """
        INSERT INTO EMPMILL12.spreader_prod_entry
        (entry_date, spell, spreader_no, jute_quality_id, no_of_rolls, entry_time, bin_no)
        VALUES (:entry_date, :spell, :spreader_no, :jute_quality_id, :no_of_rolls, :entry_time, :bin_no)
        """
    )
    params = {
        "entry_date": entry_date,
        "spell": spell,
        "spreader_no": spreader_no.strip(),
        "jute_quality_id": int(jute_quality_id),
        "no_of_rolls": int(no_of_rolls),
        "entry_time": int(entry_time),
        "bin_no": int(bin_no),
    }
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        try:
            return result.lastrowid  # MySQL should return lastrowid
        except Exception:
            rid = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            return int(rid) if rid is not None else None


def fetch_recent_spreader_entries(limit: int = 25) -> pd.DataFrame:
    """
    Fetch recent entries for display, only bins with stock, and show maturity.
    """
    sql = text(
        """
        SELECT
            entry_date,
            spell,
            spreader_no,
            jute_quality_id,
            no_of_rolls,
            entry_time,
            bin_no,
            issue_rolls
        FROM EMPMILL12.spreader_prod_entry
        WHERE (no_of_rolls - IFNULL(issue_rolls, 0)) > 0
        ORDER BY entry_date DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"limit": int(limit)})
    # Add maturity column
    if not df.empty:
        now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        def calc_maturity(row):
            entry_dt = datetime.datetime.combine(row['entry_date'], datetime.time(hour=row['entry_time']))
            delta = now - entry_dt
            return max(int(delta.total_seconds() // 3600), 0)
        df['Maturity (hrs)'] = df.apply(calc_maturity, axis=1)
    return df


# Ensure table exists on import so first page load works.
ensure_spreader_table()
