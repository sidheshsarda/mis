import datetime
from typing import Optional
from sqlalchemy import text
from db import engine

def insert_spreader_roll_issue(
    breaker_inter_no: str,
    no_of_rolls: int,
    issue_time: int,
    issue_date: datetime.date,
    spell: str,
    spreader_prod_entry_id: int,
    wt_per_roll: float
) -> Optional[int]:
    """
    Insert a new issue entry into EMPMILL12.spreader_roll_issue.
    Returns inserted id or None.
    """
    # spreader_prod_entry_id is actually entry_id_grp now
    entry_id_grp = spreader_prod_entry_id
    # Find bin_no for the given entry_id_grp (latest for that group)
    find_sql = text("""
        SELECT bin_no FROM EMPMILL12.spreader_prod_entry WHERE entry_id_grp = :entry_id_grp ORDER BY entry_date DESC, entry_time DESC LIMIT 1
    """)
    with engine.begin() as conn:
        row = conn.execute(find_sql, {"entry_id_grp": entry_id_grp}).fetchone()
        if not row:
            return None
        bin_no = row[0]

        # Validation 1: Issue datetime must be >= group's first production datetime
        first_dt_sql = text(
            """
            SELECT 
                MIN(CONCAT(entry_date, ' ', LPAD(entry_time, 2, '0'), ':00:00')) AS first_dt
            FROM EMPMILL12.spreader_prod_entry
            WHERE entry_id_grp = :entry_id_grp
            """
        )
        first_dt_row = conn.execute(first_dt_sql, {"entry_id_grp": entry_id_grp}).fetchone()
        if first_dt_row and first_dt_row[0]:
            from datetime import datetime as _dt
            first_dt = _dt.strptime(str(first_dt_row[0]), "%Y-%m-%d %H:%M:%S")
            issue_dt = _dt.combine(issue_date, _dt.min.time()).replace(hour=int(issue_time))
            if issue_dt < first_dt:
                raise ValueError("Issue date/time must be after the production start of this group.")

        # Validation 2: Quantity must not exceed current stock for the selected weight
        stock_sql = text(
            """
            SELECT 
                (COALESCE((SELECT SUM(p.no_of_rolls) FROM EMPMILL12.spreader_prod_entry p WHERE p.entry_id_grp = :entry_id_grp AND p.wt_per_roll = :wt_per_roll), 0) -
                 COALESCE((SELECT SUM(i.no_of_rolls) FROM EMPMILL12.spreader_roll_issue i WHERE i.entry_id_grp = :entry_id_grp AND i.wt_per_roll = :wt_per_roll), 0)) AS current_stock
            """
        )
        current_stock = conn.execute(stock_sql, {"entry_id_grp": entry_id_grp, "wt_per_roll": float(wt_per_roll)}).scalar() or 0
        if int(no_of_rolls) > int(current_stock):
            raise ValueError(f"Cannot issue more than current stock for {wt_per_roll} kg rolls ({int(current_stock)} rolls available).")
        sql = text("""
            INSERT INTO EMPMILL12.spreader_roll_issue
            (breaker_inter_no, no_of_rolls, issue_time, issue_date, spell, entry_id_grp, wt_per_roll)
            VALUES (:breaker_inter_no, :no_of_rolls, :issue_time, :issue_date, :spell, :entry_id_grp, :wt_per_roll)
        """)
        params = {
            "breaker_inter_no": breaker_inter_no,
            "no_of_rolls": int(no_of_rolls),
            "issue_time": int(issue_time),
            "issue_date": issue_date,
            "spell": spell,
            "entry_id_grp": int(entry_id_grp),
            "wt_per_roll": float(wt_per_roll),
        }
        result = conn.execute(sql, params)
        try:
            return result.lastrowid
        except Exception:
            rid = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            return int(rid) if rid is not None else None
