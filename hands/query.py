import pandas as pd
from db import engine


def get_daily_hand_comparison(start_date, end_date):
    """
    Get daily hand comparison data joined with occupation master norms,
    designation and master department.
    Filters by company_id = 2 and is_active = 1.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
    
    Returns:
        DataFrame with hand comparison data
    """
    query = f"""
    SELECT 
        tdhd.tran_date,
        omn.OCCU_DESC AS occupation,
        omn.OCCU_SHR_NAME AS short_name,
        omn.DEPT_ID,
        omn.DIRECT_INDIRECT,
        omn.VARIABLE_FIXED,
        md.dept_desc AS department,
        tdhd.shift_a,
        tdhd.shift_b,
        tdhd.shift_c,
        tdhd.shift_g,
        tdhd.target_a,
        tdhd.target_b,
        tdhd.target_c,
        tdhd.excess_hands,
        tdhd.short_hands
    FROM EMPMILL12.tbl_daily_hand_comp_data tdhd
    INNER JOIN vowsls.designation d 
        ON tdhd.desig_id = d.id 
    INNER JOIN EMPMILL12.OCCUPATION_MASTER_NORMS omn 
        ON d.id = omn.desig_id
    LEFT JOIN vowsls.master_department md 
        ON d.department = md.mdept_id and md.company_id = d.company_id
    WHERE tdhd.company_id = 2 
        AND tdhd.is_active = 1
        AND tdhd.tran_date BETWEEN '{start_date}' AND '{end_date}'
    ORDER BY tdhd.tran_date, omn.OCCU_DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


def get_daily_hand_summary(start_date, end_date):
    """
    Get summarized daily hand data by date with direct/indirect info.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
    
    Returns:
        DataFrame with summarized hand data per day
    """
    query = f"""
    SELECT 
        tdhd.tran_date,
        omn.DIRECT_INDIRECT,
        SUM(tdhd.shift_a) AS total_shift_a,
        SUM(tdhd.shift_b) AS total_shift_b,
        SUM(tdhd.shift_c) AS total_shift_c,
        SUM(tdhd.shift_g) AS total_shift_g,
        SUM(tdhd.target_a) AS total_target_a,
        SUM(tdhd.target_b) AS total_target_b,
        SUM(tdhd.target_c) AS total_target_c,
        SUM(tdhd.excess_hands) AS total_excess_hands,
        SUM(tdhd.short_hands) AS total_short_hands
    FROM EMPMILL12.tbl_daily_hand_comp_data tdhd
    JOIN vowsls.designation d 
        ON tdhd.desig_id = d.id
    JOIN EMPMILL12.OCCUPATION_MASTER_NORMS omn 
        ON d.id = omn.desig_id
    WHERE tdhd.company_id = 2 
        AND tdhd.is_active = 1
        AND tdhd.tran_date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY tdhd.tran_date, omn.DIRECT_INDIRECT
    ORDER BY tdhd.tran_date
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


def get_hand_comparison_by_occupation(start_date, end_date):
    """
    Get hand comparison data summarized by occupation for date range,
    including department information.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
    
    Returns:
        DataFrame with hand data grouped by occupation
    """
    query = f"""
    SELECT 
        omn.OCCU_DESC AS occupation,
        omn.OCCU_SHR_NAME AS short_name,
        omn.DIRECT_INDIRECT,
        omn.VARIABLE_FIXED,
        md.dept_desc AS department,
        SUM(tdhd.shift_a) AS total_shift_a,
        SUM(tdhd.shift_b) AS total_shift_b,
        SUM(tdhd.shift_c) AS total_shift_c,
        SUM(tdhd.shift_g) AS total_shift_g,
        SUM(tdhd.target_a) AS total_target_a,
        SUM(tdhd.target_b) AS total_target_b,
        SUM(tdhd.target_c) AS total_target_c,
        SUM(tdhd.excess_hands) AS total_excess_hands,
        SUM(tdhd.short_hands) AS total_short_hands
    FROM EMPMILL12.tbl_daily_hand_comp_data tdhd
    JOIN vowsls.designation d 
        ON tdhd.desig_id = d.id
    JOIN EMPMILL12.OCCUPATION_MASTER_NORMS omn 
        ON d.id = omn.desig_id
    LEFT JOIN vowsls.master_department md 
        ON d.department = md.mdept_id and md.company_id = d.company_id
    WHERE tdhd.company_id = 2 
        AND tdhd.is_active = 1
        AND tdhd.tran_date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY omn.OCCU_DESC, omn.OCCU_SHR_NAME, omn.DIRECT_INDIRECT, omn.VARIABLE_FIXED,
             md.dept_desc
    ORDER BY md.dept_desc, omn.OCCU_DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


def get_hand_summary_by_department(start_date, end_date):
    """
    Get hand data summarized by department for date range.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
    
    Returns:
        DataFrame with hand data grouped by department
    """
    query = f"""
    SELECT 
        md.dept_code,
        md.dept_desc AS department,
        omn.DIRECT_INDIRECT,
        SUM(tdhd.shift_a) AS total_shift_a,
        SUM(tdhd.shift_b) AS total_shift_b,
        SUM(tdhd.shift_c) AS total_shift_c,
        SUM(tdhd.shift_g) AS total_shift_g,
        SUM(tdhd.target_a) AS total_target_a,
        SUM(tdhd.target_b) AS total_target_b,
        SUM(tdhd.target_c) AS total_target_c,
        SUM(tdhd.excess_hands) AS total_excess_hands,
        SUM(tdhd.short_hands) AS total_short_hands
    FROM EMPMILL12.tbl_daily_hand_comp_data tdhd
    JOIN vowsls.designation d 
        ON tdhd.desig_id = d.id
    JOIN EMPMILL12.OCCUPATION_MASTER_NORMS omn 
        ON d.id = omn.desig_id
    LEFT JOIN vowsls.master_department md 
        ON d.department = md.mdept_id and md.company_id = d.company_id
    WHERE tdhd.company_id = 2 
        AND tdhd.is_active = 1
        AND tdhd.tran_date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY md.dept_code, md.dept_desc, omn.DIRECT_INDIRECT
    ORDER BY md.dept_code
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df
