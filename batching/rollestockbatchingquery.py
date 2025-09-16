import pandas as pd
from db import engine

def get_batch_data():
    query = """
    SELECT * FROM rollestock
    WHERE status = 'active'
    """
    df = pd.read_sql(query, engine)
    return df

def get_bin_no():
    query = """
    SELECT bn.bin_id, bn.bin_no FROM EMPMILL12.spreader_roll_bin_master bn;
    """
    df = pd.read_sql(query, engine)
    return df['bin_no'].tolist()

def get_jute_quality():
    query = """
    SELECT jq.id, jq.jute_quality
    FROM vowsls.jute_quality_price_master jq
    WHERE jq.company_id = 2 ;
    """
    df = pd.read_sql(query, engine)
    return df

def get_maturity_hours():
    query = """
    select mtm.jute_quality_id , mtm.maturity_hours  from EMPMILL12.maturity_time_master mtm ;
    """
    df = pd.read_sql(query, engine)
    if not df.empty:
        return df
    else:
        return pd.DataFrame({'jute_quality_id': [], 'maturity_hours': []})

