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
    # Join production and issue tables, aggregate rolls and issued rolls by bin and entry_id_grp
    # Join on entry_id_grp only if both tables have it, otherwise join on spreader_prod_entry_id
    sql = text(
        """
        SELECT
            p.bin_no,
            p.entry_id_grp,
            p.jute_quality_id,
            p.no_of_rolls,
            p.produced_weight_kg,
            p.entry_date,
            p.entry_time,
            p.avg_entry_ts,
            COALESCE(i.issued_rolls, 0) AS issued_rolls,
            COALESCE(i.issued_weight_kg, 0) AS issued_weight_kg,
            (p.produced_weight_kg - COALESCE(i.issued_weight_kg, 0)) AS current_weight_kg,
            (p.produced_weight_kg - COALESCE(i.issued_weight_kg, 0)) / 1000.0 AS current_weight_mt
        FROM (
            SELECT
                bin_no,
                entry_id_grp,
                jute_quality_id,
                SUM(no_of_rolls) AS no_of_rolls,
                SUM(no_of_rolls * IFNULL(wt_per_roll, 0)) AS produced_weight_kg,
                MAX(entry_date) AS entry_date,
                MAX(entry_time) AS entry_time,
                AVG(UNIX_TIMESTAMP(CONCAT(entry_date, ' ', LPAD(entry_time, 2, '0'), ':00:00'))) AS avg_entry_ts
            FROM EMPMILL12.spreader_prod_entry
            GROUP BY bin_no, entry_id_grp, jute_quality_id
        ) p
        LEFT JOIN (
            SELECT 
                entry_id_grp, 
                SUM(no_of_rolls) AS issued_rolls,
                SUM(no_of_rolls * IFNULL(wt_per_roll, 0)) AS issued_weight_kg
            FROM EMPMILL12.spreader_roll_issue
            GROUP BY entry_id_grp
        ) i
        ON p.entry_id_grp = i.entry_id_grp
        WHERE (p.no_of_rolls - COALESCE(i.issued_rolls, 0)) > 0
        ORDER BY p.bin_no, p.entry_id_grp
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    return df

def fetch_available_weights_for_group(entry_id_grp: int) -> "pd.DataFrame":
    """
    For a given entry_id_grp, return per-weight available rolls after accounting for issues.
    Columns: wt_per_roll, produced_rolls, issued_rolls, available_rolls
    Only includes weights with available_rolls > 0.
    """
    sql = text(
        """
        SELECT 
            wt_per_roll,
            produced_rolls,
            issued_rolls,
            (produced_rolls - issued_rolls) AS available_rolls
        FROM (
            SELECT 
                p.wt_per_roll,
                SUM(p.no_of_rolls) AS produced_rolls,
                COALESCE(SUM(i.no_of_rolls), 0) AS issued_rolls
            FROM EMPMILL12.spreader_prod_entry p
            LEFT JOIN EMPMILL12.spreader_roll_issue i
                ON i.entry_id_grp = p.entry_id_grp AND i.wt_per_roll = p.wt_per_roll
            WHERE p.entry_id_grp = :entry_id_grp
            GROUP BY p.wt_per_roll
        ) t
        WHERE (produced_rolls - issued_rolls) > 0
        ORDER BY wt_per_roll
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"entry_id_grp": int(entry_id_grp)})
    return df
import datetime
from typing import Optional
import pandas as pd
from sqlalchemy import text
from db import engine
from .spreader_rules import evaluate_4hr_window


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
    trolley_no: int,
    wt_per_roll: float,
) -> Optional[int]:
    """
    Insert one row into EMPMILL12.spreader_prod_entry. Returns inserted id or None.
    """
    # Use the current stock query to determine entry_id_grp
    # Get max entry_id_grp across all bins
    max_grp_sql = text("SELECT COALESCE(MAX(entry_id_grp), 0) FROM EMPMILL12.spreader_prod_entry")
    stock_sql = text("""
        SELECT entry_id_grp, SUM(no_of_rolls) AS total_rolls, COALESCE(SUM(issued_rolls),0) AS total_issued
        FROM (
            SELECT p.entry_id_grp, p.no_of_rolls, COALESCE(SUM(i.no_of_rolls),0) AS issued_rolls
            FROM EMPMILL12.spreader_prod_entry p
            LEFT JOIN EMPMILL12.spreader_roll_issue i
                ON p.entry_id_grp = i.entry_id_grp
            WHERE p.bin_no = :bin_no
            GROUP BY p.entry_id_grp, p.no_of_rolls
        ) t
        GROUP BY entry_id_grp
        ORDER BY entry_id_grp DESC
    """)
    with engine.begin() as conn:
        # Get max entry_id_grp across all bins
        max_grp = conn.execute(max_grp_sql).scalar() or 0
        result = conn.execute(stock_sql, {"bin_no": bin_no})
        stock_rows = result.fetchall()
        # Find the latest group with stock > 0
        entry_id_grp = None
        reused_existing_group = False
        for row in stock_rows:
            grp, total_rolls, total_issued = row
            if (total_rolls - total_issued) > 0:
                entry_id_grp = grp
                reused_existing_group = True
                break
        if entry_id_grp is None:
            # No group with stock, assign max+1 (across all bins) or 1 if none
            entry_id_grp = max_grp + 1 if max_grp else 1
            reused_existing_group = False

        # If reusing an existing group for this bin, enforce quality freeze and 4-hour cutoff from first entry
        if reused_existing_group:
            # Quality freeze & window handled using shared utility
            first_row_sql = text(
                """
                SELECT jute_quality_id, entry_date, entry_time
                FROM EMPMILL12.spreader_prod_entry
                WHERE bin_no = :bin_no AND entry_id_grp = :entry_id_grp
                ORDER BY entry_date ASC, entry_time ASC
                LIMIT 1
                """
            )
            r = conn.execute(first_row_sql, {"bin_no": bin_no, "entry_id_grp": entry_id_grp}).fetchone()
            if r:
                grp_quality_id, earliest_date, earliest_time = int(r[0]), r[1], int(r[2])
                if int(jute_quality_id) != grp_quality_id:
                    raise ValueError("Jute quality is locked for this group and cannot be changed.")
                earliest_dt = datetime.datetime.combine(earliest_date, datetime.time(hour=earliest_time))
                candidate_dt = datetime.datetime.combine(entry_date, datetime.time(hour=int(entry_time)))
                if candidate_dt < earliest_dt:
                    raise ValueError(
                        f"Backdated not allowed. Earliest group entry {earliest_dt:%Y-%m-%d %H}:00; candidate {candidate_dt:%Y-%m-%d %H}:00."
                    )
            win = evaluate_4hr_window(entry_id_grp, entry_date, int(entry_time))
            if win is None:
                raise ValueError("Group not found for validation.")
            # Prevent back-dated earlier hour for same day relative to base when base is same day and candidate earlier.
            if win.base_dt.date() == entry_date and win.candidate_dt < win.base_dt:
                raise ValueError("Cannot insert earlier than the first entry hour for the day in this group.")
            if not win.allowed:
                raise ValueError(win.reason)
    sql = text(
        """
        INSERT INTO EMPMILL12.spreader_prod_entry
        (entry_date, spell, spreader_no, jute_quality_id, no_of_rolls, entry_time, bin_no, entry_id_grp, trolley_no, wt_per_roll)
        VALUES (:entry_date, :spell, :spreader_no, :jute_quality_id, :no_of_rolls, :entry_time, :bin_no, :entry_id_grp, :trolley_no, :wt_per_roll)
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
        "entry_id_grp": int(entry_id_grp),
        "trolley_no": int(trolley_no),
        "wt_per_roll": float(wt_per_roll),
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


