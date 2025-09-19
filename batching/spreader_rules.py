import datetime
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import text
from db import engine

@dataclass
class WindowResult:
    allowed: bool
    base_dt: datetime.datetime
    allowed_end_dt: datetime.datetime
    candidate_dt: datetime.datetime
    reason: str = ""


def evaluate_4hr_window(entry_id_grp: int, candidate_date, candidate_hour: int) -> Optional[WindowResult]:
    """
    Determine if a candidate entry (date + hour) is within the 4-hour allowable window
    for the given active group. Logic:
      1. If there is at least one entry on candidate_date: window = earliest(entry_time) .. +4h
      2. Else check previous day earliest entry; if its +4h crosses midnight into candidate_date, continue that window.
      3. Else candidate becomes first entry for a new daily window.
    Returns WindowResult or None if group not found.
    """
    candidate_dt = datetime.datetime.combine(candidate_date, datetime.time(hour=int(candidate_hour)))
    with engine.connect() as conn:
        # Ensure group exists
        grp_exists = conn.execute(text("SELECT 1 FROM EMPMILL12.spreader_prod_entry WHERE entry_id_grp = :g LIMIT 1"), {"g": entry_id_grp}).fetchone()
        if not grp_exists:
            return None
        # Earliest group entry overall (for anti-backdate safeguard)
        earliest_row = conn.execute(text("""
            SELECT entry_date, entry_time
            FROM EMPMILL12.spreader_prod_entry
            WHERE entry_id_grp = :g
            ORDER BY entry_date ASC, entry_time ASC
            LIMIT 1
        """), {"g": entry_id_grp}).fetchone()
        if earliest_row:
            earliest_dt = datetime.datetime.combine(earliest_row[0], datetime.time(hour=int(earliest_row[1])))
            if candidate_dt < earliest_dt:
                return WindowResult(
                    allowed=False,
                    base_dt=earliest_dt,
                    allowed_end_dt=earliest_dt + datetime.timedelta(hours=4),
                    candidate_dt=candidate_dt,
                    reason=(
                        f"Backdated not allowed. Earliest group entry {earliest_dt:%Y-%m-%d %H}:00; "
                        f"candidate {candidate_dt:%Y-%m-%d %H}:00 precedes it."
                    )
                )
        # Same-day earliest
        same_day = conn.execute(text("""
            SELECT MIN(entry_time) AS min_hour
            FROM EMPMILL12.spreader_prod_entry
            WHERE entry_id_grp = :g AND entry_date = :d
        """), {"g": entry_id_grp, "d": candidate_date}).fetchone()
        base_dt = None
        allowed_end_dt = None
        if same_day and same_day[0] is not None:
            base_hour = int(same_day[0])
            base_dt = datetime.datetime.combine(candidate_date, datetime.time(hour=base_hour))
            allowed_end_dt = base_dt + datetime.timedelta(hours=4)
        else:
            # Previous day cross-midnight check
            prev_date = candidate_date - datetime.timedelta(days=1)
            prev_row = conn.execute(text("""
                SELECT MIN(entry_time) AS min_hour
                FROM EMPMILL12.spreader_prod_entry
                WHERE entry_id_grp = :g AND entry_date = :pd
            """), {"g": entry_id_grp, "pd": prev_date}).fetchone()
            if prev_row and prev_row[0] is not None:
                prev_first_hour = int(prev_row[0])
                prev_first_dt = datetime.datetime.combine(prev_date, datetime.time(hour=prev_first_hour))
                prev_window_end = prev_first_dt + datetime.timedelta(hours=4)
                if prev_window_end.date() == candidate_date:  # crosses midnight
                    base_dt = prev_first_dt
                    allowed_end_dt = prev_window_end
            if base_dt is None:
                # Start new window at candidate
                base_dt = candidate_dt
                allowed_end_dt = candidate_dt + datetime.timedelta(hours=4)
        allowed = candidate_dt <= allowed_end_dt
        reason = ""
        if not allowed:
            reason = (f"Window closed. Base {base_dt:%Y-%m-%d %H}:00 → allowed until {allowed_end_dt:%Y-%m-%d %H}:00; "
                      f"candidate {candidate_dt:%Y-%m-%d %H}:00 outside 4-hour window.")
        return WindowResult(allowed=allowed, base_dt=base_dt, allowed_end_dt=allowed_end_dt, candidate_dt=candidate_dt, reason=reason)
