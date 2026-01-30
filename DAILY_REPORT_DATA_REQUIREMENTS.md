# Daily Production Report - Data Requirements & Schema Specifications

This document outlines the additional data sources and database schema structures needed to complete the Daily Production Report as shown in the reference image.

## Overview
The Daily Production Report has been updated to include multiple new sections. Each section currently displays placeholder data and includes inline documentation about what database tables and data sources are required.

## Current Status
✅ **Implemented with Real Data:**
- Spinning Production Shift Wise (DOFF-10)
- Spinning Production Summary (Fine/Coarse)
- Winder Average Production Quality Wise
- Weaving Production /Day
- Weaving Production Shift Wise
- Workers Hands Details (basic calculation)
- Yarn Heavy Light Report (from Google Sheets)

📋 **Added with Placeholder Data & Requirements:**
- Twisting Production (KG)
- Finishing Section
- Heavy Light- SQC
- Jute Stock and Arrivals
- P W Production
- Extra Machine Run Basis & STD Production
- Enhanced Workers Hands Details (department breakdown)

---

## 1. TWISTING PRODUCTION (KG)

### Purpose
Track twisting production by quality type and shift, showing daily production and month-to-date totals.

### Required Database Table
**Table Name:** `twisting_daily_transaction` (or similar)

**Schema:**
```sql
CREATE TABLE twisting_daily_transaction (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    quality VARCHAR(50) NOT NULL,  -- e.g., "10 LBS 3PLY(LOCAL)", "10 LBS 3PLY", "28 LBS 3PLY"
    prod_a DECIMAL(10,2),  -- Production in shift A (kg)
    prod_b DECIMAL(10,2),  -- Production in shift B (kg)
    prod_c DECIMAL(10,2),  -- Production in shift C (kg)
    remarks VARCHAR(50),   -- e.g., "MILL", "SALE", "S"
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Sample Query:**
```sql
SELECT 
    quality,
    SUM(prod_a) as A,
    SUM(prod_b) as B,
    SUM(prod_c) as C,
    SUM(prod_a + prod_b + prod_c) as TOTAL,
    remarks
FROM twisting_daily_transaction
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality, remarks;
```

**MTD Query:**
```sql
SELECT 
    quality,
    SUM(prod_a + prod_b + prod_c) as MTD_Total
FROM twisting_daily_transaction
WHERE tran_date BETWEEN '{start_date}' AND '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality;
```

---

## 2. FINISHING SECTION

### Purpose
Track finishing operations including press production, stock levels, and loose stock by quality type.

### Required Database Table
**Table Name:** `finishing_production` (or similar)

**Schema:**
```sql
CREATE TABLE finishing_production (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    quality_type VARCHAR(20) NOT NULL,  -- "HESSIAN" or "SACKING"
    press_production_bale DECIMAL(10,2),
    stock_bale DECIMAL(10,2),
    loose_stock_mt DECIMAL(10,3),
    loose_stock_type VARCHAR(20),  -- e.g., "HPS", "SACKING", "OTHERS"
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Sample Query:**
```sql
-- Daily Production
SELECT 
    quality_type,
    SUM(press_production_bale) as press_production,
    SUM(stock_bale) as stock,
    GROUP_CONCAT(CONCAT(loose_stock_type, ' ', loose_stock_mt) SEPARATOR ', ') as loose_stock
FROM finishing_production
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality_type;

-- MTD Stock
SELECT SUM(stock_bale) as mtd_stock
FROM finishing_production
WHERE tran_date BETWEEN '{start_date}' AND '{selected_date}'
    AND company_id = 2
    AND is_active = 1;
```

---

## 3. HEAVY LIGHT- SQC

### Purpose
Track Statistical Quality Control (SQC) metrics for heavy/light analysis by quality type.

### Option 1: New Table
**Table Name:** `sqc_quality_daily`

**Schema:**
```sql
CREATE TABLE sqc_quality_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    quality VARCHAR(20) NOT NULL,  -- "HESSIAN", "SACKING", "OVERALL"
    overseed DECIMAL(10,2),
    corrected DECIMAL(10,2),
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Option 2: Integrate with Existing Yarn Heavy Light Report
This data could potentially be derived from the existing Google Sheets "YARN" data by aggregating at quality type level instead of individual quality codes.

**Sample Query (if using new table):**
```sql
-- Daily
SELECT 
    quality,
    overseed,
    corrected
FROM sqc_quality_daily
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1;

-- MTD
SELECT 
    quality,
    AVG(overseed) as mtd_overseed,
    AVG(corrected) as mtd_corrected
FROM sqc_quality_daily
WHERE tran_date BETWEEN '{start_date}' AND '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality;
```

---

## 4. JUTE STOCK AND ARRIVALS

### Purpose
Track jute raw material stock levels, issues, and daily arrivals by bale type.

### Required Database Tables

**Table 1:** `jute_stock_daily`
```sql
CREATE TABLE jute_stock_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    stock_mt DECIMAL(10,3),
    today_issued_mt DECIMAL(10,3),
    issue_5pg_mt DECIMAL(10,3),  -- Issue to 5PG
    bale_uncut_re_selection INT,
    total_re_selection INT,
    o_days_stock INT,  -- Outstanding days of stock
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table 2:** `jute_arrival_daily`
```sql
CREATE TABLE jute_arrival_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    bale_cut INT,
    bale_cut_re_selection INT,
    bale_uncut INT,
    bale_uncut_re_selection INT,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Alternative: Use Existing Batching Module
The codebase already has a batching module (see `batching/rollestockbatchingquery.py` with `get_jute_quality()` function). Consider extending this module to include stock tracking.

**Sample Queries:**
```sql
-- Stock
SELECT *
FROM jute_stock_daily
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1;

-- Arrivals
SELECT 
    bale_cut,
    bale_cut_re_selection,
    bale_uncut,
    bale_uncut_re_selection,
    (bale_cut + bale_cut_re_selection + bale_uncut + bale_uncut_re_selection) as total
FROM jute_arrival_daily
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1;
```

---

## 5. P W PRODUCTION

### Purpose
Track P W (Processed Winding?) production by quality and shift with remarks.

### Required Database Table
**Table Name:** `pw_production_daily`

**Schema:**
```sql
CREATE TABLE pw_production_daily (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tran_date DATE NOT NULL,
    company_id INT NOT NULL,
    quality VARCHAR(50) NOT NULL,  -- e.g., "9 LBS 1 PLY SLY", "13 LB 1 PLY(LOCAL)"
    prod_a DECIMAL(10,2),
    prod_b DECIMAL(10,2),
    prod_c DECIMAL(10,2),
    remarks VARCHAR(50),  -- e.g., "SALE", "S4"
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Sample Query:**
```sql
-- Daily
SELECT 
    quality,
    SUM(prod_a) as A,
    SUM(prod_b) as B,
    SUM(prod_c) as C,
    SUM(prod_a + prod_b + prod_c) as total,
    remarks
FROM pw_production_daily
WHERE tran_date = '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality, remarks;

-- MTD
SELECT 
    quality,
    SUM(prod_a + prod_b + prod_c) as mtd_total
FROM pw_production_daily
WHERE tran_date BETWEEN '{start_date}' AND '{selected_date}'
    AND company_id = 2
    AND is_active = 1
GROUP BY quality;
```

---

## 6. EXTRA MACHINE RUN BASIS & STD PRODUCTION

### Purpose
Calculate machine utilization efficiency by comparing actual vs target production across different machine types.

### Data Sources
This section can be **derived from existing tables** with additional calculations:

**Spinning:** From `spining_daily_transaction`
```sql
SELECT 
    'SPINNING' as type_of_machine,
    ROUND(SUM(hunprod)/SUM(mc_a + mc_b + mc_c), 0) as avg_target_machine,
    ROUND(SUM(prd_a + prd_b + prd_c)/SUM(mc_a + mc_b + mc_c), 0) as avg_act_machine,
    ROUND(SUM(prd_a + prd_b + prd_c)/1000, 3) as total_production,
    ROUND(SUM(prd_a + prd_b + prd_c)/
          (SUM(prd_a + prd_b + prd_c)/SUM(mc_a + mc_b + mc_c)), 2) as should_be_run_machine,
    SUM(mc_a + mc_b + mc_c) as act_run_no_machine
FROM spining_daily_transaction
WHERE tran_date = '{selected_date}'
    AND company_id = 2;
```

**Weaving:** From `weaving_daily_transaction`
```sql
-- HESSIAN (QualityType = 1)
SELECT 
    'WEAVING-HESSIAN' as type_of_machine,
    -- Calculate avg_target_machine based on standard efficiency
    ROUND(SUM(actkgs)/SUM(mc_a + mc_b + mc_c), 2) as avg_act_machine,
    ROUND(SUM(actkgs)/1000, 3) as total_production,
    SUM(mc_a + mc_b + mc_c) as act_run_no_machine
FROM weaving_daily_transaction wdt
LEFT JOIN weaving_master wm ON wm.q_code = wdt.q_code
WHERE wdt.tran_date = '{selected_date}'
    AND wdt.company_id = 2
    AND SUBSTR(wm.q_code, 1, 1) = '1';

-- SACKING (QualityType = 2)
-- Similar query with SUBSTR(wm.q_code, 1, 1) = '2'
```

**Required Master Data Table (if not exists):**
```sql
CREATE TABLE machine_targets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    machine_type VARCHAR(50),
    quality_type VARCHAR(50),
    target_production_per_machine DECIMAL(10,2),
    effective_from DATE,
    effective_to DATE,
    is_active TINYINT DEFAULT 1
);
```

---

## 7. ENHANCED WORKERS HANDS DETAILS

### Purpose
Provide detailed breakdown of worker hours and efficiency by department (SPINNING, WEAVING).

### Current Implementation
Uses `daily_attendance` table with basic calculation:
```sql
SELECT 
    SUBSTR(spell, 1, 1) AS shift,
    SUM(working_hours - idle_hours) AS whrs
FROM daily_attendance da
LEFT JOIN tbl_hrms_ed_official_details theod ON da.eb_id = theod.eb_id
WHERE da.company_id = 2 
    AND da.is_active = 1 
    AND da.attendance_date = '{selected_date}'
    AND theod.catagory_id NOT IN (30)
GROUP BY SUBSTR(spell, 1, 1);
```

### Enhancement Needed
**Add department/section filtering:**

**Option 1:** Add department column to existing query
```sql
SELECT 
    SUBSTR(spell, 1, 1) AS shift,
    theod.department,  -- or section_id
    SUM(working_hours - idle_hours) AS whrs,
    CASE 
        WHEN SUBSTR(spell, 1, 1) = 'A' THEN ROUND(SUM(working_hours - idle_hours) / 8, 2)
        WHEN SUBSTR(spell, 1, 1) = 'B' THEN ROUND(SUM(working_hours - idle_hours) / 8, 2)
        ELSE ROUND(SUM(working_hours - idle_hours) / 7.5, 2)
    END AS no_of_hands
FROM daily_attendance da
LEFT JOIN tbl_hrms_ed_official_details theod ON da.eb_id = theod.eb_id
WHERE da.company_id = 2 
    AND da.is_active = 1 
    AND da.attendance_date = '{selected_date}'
    AND theod.catagory_id NOT IN (30)
    AND theod.department IN ('SPINNING', 'WEAVING')
GROUP BY SUBSTR(spell, 1, 1), theod.department;
```

**Option 2:** Use category_id mapping
Create a mapping table if department info not directly available:
```sql
CREATE TABLE department_category_mapping (
    category_id INT,
    department_name VARCHAR(50),
    PRIMARY KEY (category_id)
);
```

---

## Implementation Priority

### High Priority (Essential for Report Completeness)
1. **Twisting Production** - Key production metric
2. **Finishing Section** - Critical for production flow tracking
3. **Enhanced Workers Hands Details** - Important for efficiency analysis

### Medium Priority (Important but can use alternatives)
4. **Extra Machine Run Basis** - Can be calculated from existing data
5. **P W Production** - Depends on business process importance
6. **Heavy Light- SQC** - Could initially use data from Google Sheets aggregation

### Lower Priority (Nice to Have)
7. **Jute Stock and Arrivals** - May already have partial data in batching module

---

## Integration Steps

### Step 1: Database Setup
1. Create new tables as specified above
2. Set up foreign key relationships where applicable
3. Add indexes on `tran_date` and `company_id` columns for performance

### Step 2: Data Entry Points
1. Create data entry forms in the application for new sections
2. Or set up ETL processes if data comes from external systems
3. Implement validation rules for data quality

### Step 3: Query Implementation
1. Create query functions in `/home/runner/work/mis/mis/overall/query.py`
2. Follow the pattern of existing functions (e.g., `get_dofftable_data()`)
3. Implement both daily and MTD (month-to-date) queries

### Step 4: UI Integration
1. Replace placeholder dataframes in `dailySummary.py` with actual query calls
2. Remove or update info boxes about data requirements
3. Add error handling for missing data

### Step 5: Testing
1. Test with sample data
2. Verify calculations match expected results
3. Test date range handling (daily, MTD)
4. Test performance with production data volumes

---

## Example Implementation Pattern

Here's how to add a new section (using Twisting Production as example):

**1. Add query function in `overall/query.py`:**
```python
def get_twisting_production(selected_date):
    query = f"""
    SELECT 
        quality,
        SUM(prod_a) as A,
        SUM(prod_b) as B,
        SUM(prod_c) as C,
        SUM(prod_a + prod_b + prod_c) as TOTAL,
        remarks
    FROM twisting_daily_transaction
    WHERE tran_date = '{selected_date}'
        AND company_id = 2
        AND is_active = 1
    GROUP BY quality, remarks
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_twisting_production_mtd(start_date, selected_date):
    query = f"""
    SELECT 
        quality,
        SUM(prod_a + prod_b + prod_c) as MTD_Total
    FROM twisting_daily_transaction
    WHERE tran_date BETWEEN '{start_date}' AND '{selected_date}'
        AND company_id = 2
        AND is_active = 1
    GROUP BY quality
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")
```

**2. Update imports in `dailySummary.py`:**
```python
from overall.query import (
    get_dofftable_data, get_dofftable_sum_by_date, 
    get_spg_fine_coarse, get_spg_sid_mtd, 
    get_quality_winding_details, weaving_details, 
    get_weaving_shiftwise, get_weaving_total_mtd, 
    get_hands_details, get_hands_mtd_details,
    get_twisting_production, get_twisting_production_mtd  # NEW
)
```

**3. Replace placeholder code:**
```python
# TWISTING PRODUCTION (KG)
st.markdown("### TWISTING PRODUCTION (KG)")
try:
    twisting_df, twisting_json = get_twisting_production(selected_date)
    if start_date:
        twisting_mtd_df, _ = get_twisting_production_mtd(start_date, selected_date)
        twisting_df = twisting_df.merge(twisting_mtd_df, on='quality', how='left')
    
    if not twisting_df.empty:
        st.dataframe(twisting_df, hide_index=True, use_container_width=True)
    else:
        st.info("No twisting production data available for the selected date.")
except Exception as e:
    st.error(f"Error fetching twisting production: {str(e)}")
```

---

## Contact & Support

For questions about data requirements or implementation, refer to:
- Database schema: Contact database administrator
- Business logic: Contact production managers for clarification on calculations
- Technical implementation: Refer to existing patterns in `overall/query.py` and `overall/dailySummary.py`

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-30 | Initial document created | Copilot Agent |
| 2026-01-30 | Added all section specifications | Copilot Agent |
