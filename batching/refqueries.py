# query 1 - production data
# SELECT 
#     ytm.yarn_type,
#     ytm.yarn_type_id,
#     ROUND(SUM(d.netwt), 0) AS total_netwt
# FROM vowsls.dofftable d
# LEFT JOIN vowsls.weaving_quality_master wqm 
#        ON wqm.quality_code = d.q_code 
#       AND wqm.company_id = d.company_id
# LEFT JOIN vowsls.yarn_type_master ytm 
#        ON ytm.company_id = 2 
#       AND ytm.yarn_type = wqm.yarn_type
# WHERE d.company_id = 2 
#   AND d.doffdate = '2025-09-24'
# GROUP BY ytm.yarn_type, ytm.yarn_type_id
# ORDER BY ytm.yarn_type;

# query 2 - batch plan date wise 
# SELECT 
#     bpdi.hdr_id, 
#     bpdi.plan_date, 
#     bpdi.batch_plan_code, 
#     bpdi.yarn_type_id, 
#     ytm.yarn_type
# FROM vowsls.batch_plan_daily_implement bpdi
# LEFT JOIN vowsls.yarn_type_master ytm 
#        ON ytm.yarn_type_id = bpdi.yarn_type_id
# WHERE bpdi.company_id = 2
#   AND bpdi.plan_date BETWEEN '2025-09-24' AND DATE_ADD('2025-09-24', INTERVAL 4 DAY)
#   AND bpdi.is_active = 1
# ORDER BY bpdi.hdr_id DESC;

# query 3 - batch plan details 

# select bph.plan_hdr_id , bph.plan_code , bph.plan_name , bph.percentage, bpd.jute_quality_id , jqpm.jute_quality   from vowsls.batch_plan_hdr bph 
# left join vowsls.batch_plan_dtl bpd on bpd.batch_plan_hdr_id = bph.plan_hdr_id and bpd.is_active =1 and bpd.company_id =2
# left join vowsls.jute_quality_price_master jqpm on jqpm.id = bpd.jute_quality_id 
# where bph.company_id =2 and bph.is_active =1 ;


# query 4 - roll stock for a date and time 

# SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
#                SUM(openstock) AS openstock,
#                SUM(prodroll)  AS prodroll,
#                SUM(issueroll) AS issueroll,
#                SUM(openstock) + SUM(prodroll) - SUM(issueroll) AS closstock
#         FROM (
#             -- Opening stock from production before snapshot
#         SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
#                    SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
#             FROM (
#                 SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
#                        spe.jute_quality_id, spe.no_of_rolls,
#                        CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
#                 FROM EMPMILL12.spreader_prod_entry spe
#             ) sprdprod
#             WHERE STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
#             GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
#             UNION ALL
#             -- Opening stock negative adjustment from issues before snapshot
#             SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
#                    -SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
#             FROM (
#                 SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,issue_date,
#                        CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
#                        sri.issue_time, sri.no_of_rolls
#                 FROM EMPMILL12.spreader_roll_issue sri
#                 LEFT JOIN (select entry_id_grp,bin_no,jute_quality_id,sum(no_of_rolls) pdrolls
#             from EMPMILL12.spreader_prod_entry
#                         group by entry_id_grp,bin_no,jute_quality_id) spe ON spe.entry_id_grp = sri.entry_id_grp
#             ) sprdissu
#             WHERE STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
#             GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
#             UNION ALL
#             -- Production within window
#             SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
#                    0 AS openstock, SUM(no_of_rolls) AS prodroll, 0 AS issueroll
#             FROM (
#                 SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
#                        spe.jute_quality_id, spe.no_of_rolls,
#                        CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
#                 FROM EMPMILL12.spreader_prod_entry spe
#             ) sprdprod2
#             WHERE STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H') >= STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
#             AND STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H')< STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
#             GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
#             UNION ALL
#             -- Issues within window
#             SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
#                    0 AS openstock, 0 AS prodroll, SUM(no_of_rolls) AS issueroll
#             FROM (
#                 SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,issue_date,
#                        CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
#                        sri.issue_time, sri.no_of_rolls
#                 FROM EMPMILL12.spreader_roll_issue sri
#                 LEFT JOIN (select entry_id_grp,bin_no,jute_quality_id,sum(no_of_rolls) pdrolls
#             from EMPMILL12.spreader_prod_entry
#                         group by entry_id_grp,bin_no,jute_quality_id) spe ON spe.entry_id_grp = sri.entry_id_grp
#             ) sprdissu2
#             WHERE STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H')>= STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
#             AND STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H')< STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
#             GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
#         ) g
#         GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
#         HAVING closstock <> 0 OR openstock <> 0 OR prodroll <> 0 OR issueroll <> 0
#         ORDER BY bin_no, entry_id_grp, wt_per_roll

# query 5 - maturity hours 

# def get_maturity_hours():
#     query = """
#     select mtm.jute_quality_id , mtm.maturity_hours  from EMPMILL12.maturity_time_master mtm ;
#     """
#     df = pd.read_sql(query, engine)
#     if not df.empty:
#         return df
#     else:
#         return pd.DataFrame({'jute_quality_id': [], 'maturity_hours': []}) 
