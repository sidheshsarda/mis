# RequiredIssue.py — Detailed Analysis

**Source file:** `pages/RequiredIssue.py`
**Streamlit page title:** _Jute Issue Planner — Point-in-Time Snapshot (06:00)_
**Layout:** `wide`
**Mode:** Read-only (no DB write-backs)

This page is a Streamlit-based planner that builds a point-in-time (06:00) snapshot of:
1. Yarn-type production on a chosen date,
2. The active 5-day batch plan (selected_date+1 → selected_date+5),
3. Jute roll-stock as of next-day 06:00, and
4. The resulting **Required Issue** of jute (in MT and Bales) needed to keep maturity-adjusted target stocks on track.

---

## 1. Page-level constants

| Constant | Value | Meaning |
|---|---|---|
| `COMPANY_ID` | `2` | All SQL filters bind this `:co_id`. Hardcoded — the page is single-tenant. |
| `SNAPSHOT_HOUR` | `6` | Fixed daily cut-off used for stock/maturity (06:00 local). |
| `MATURITY_TOLERANCE_HRS` | `2` | Declared as `±2 hours`, displayed in the header. Not currently used by any computation — informational only. |

---

## 2. Inputs

### 2.1 User input (UI widget)
| Widget | Variable | Default | Notes |
|---|---|---|---|
| `st.date_input("Select date …")` | `selected_date` | `date.today() - 1 day` | The single primary input. Drives every downstream timestamp, query, and computation. |

### 2.2 Editable data input
| Widget | Variable | Purpose |
|---|---|---|
| `st.data_editor` (key `batch_plan_targets_editor`) | `edited_df` → `percent_df` | Lets the user override the **percentage of reference production** for each (yarn × plan_date) cell. Persisted in `st.session_state["batch_plan_targets_percent_v2"]`. Schema is keyed by `("_batch_plan_schema": (columns, plan_dates, plan_yarns))` so changes in the underlying plan reset the editor. |

The editor table has columns:
- `Yarn Type` (disabled text)
- `Reference Production (kg)` (disabled number; defaults to that yarn's prior-day production, or `1000.0` kg when missing)
- One `{YYYY-MM-DD} %` column per plan date, default `100.0`, `min_value=0.0`, `step=0.1`.

### 2.3 Derived timestamps / windows
| Variable | Formula | Used by |
|---|---|---|
| `snapshot_dt` | `datetime.combine(selected_date, time(06:00))` | header display, basis for the next two. |
| `opening_dt_str` / `closing_dt_str` | `snapshot_dt.strftime("%Y-%m-%d %H")` (equal) | Reserved point-in-time pair (kept identical so windowed contributions cancel). Not directly bound to any SQL on the page today. |
| `roll_snapshot_dt` | `snapshot_dt + 1 day` | Stock snapshot caption; the next-day 06:00 is treated as "current" inventory. |
| `roll_opening_dt_str` / `roll_closing_dt_str` | `roll_snapshot_dt.strftime("%Y-%m-%d %H")` (equal) | Bound to `:opening_dt` / `:closing_dt` in `q4_roll_stock_snapshot`. |
| `range_start` | `selected_date + 1 day` | Lower bound of the batch-plan window. |
| `range_end` | `range_start + 4 days` | Upper bound (so the window is 5 calendar days inclusive). |

### 2.4 External / module imports
- `db.engine` (SQLAlchemy engine from `db.py`) — passed into every query function as `_engine`.
- `streamlit`, `pandas`, `sqlalchemy.text`, plus `datetime` primitives.

---

## 3. Cached query functions

All six query functions use `@st.cache_data(ttl=60)`. The leading underscore on `_engine` excludes the engine from the cache key (Streamlit convention for unhashable args).

### `q1_production_by_yarn(_engine, dte: date) -> DataFrame`
- **Inputs bound:** `:co_id` = `COMPANY_ID`, `:doff_date` = `selected_date`.
- **Tables:** `vowsls.dofftable d` LEFT JOIN `vowsls.weaving_quality_master wqm` LEFT JOIN `vowsls.yarn_type_master ytm`.
- **Filter:** `company_id` and `doffdate = :doff_date`.
- **Group by:** `yarn_type, yarn_type_id`.
- **Returned columns:** `yarn_type` (`COALESCE … 'Unmapped'`), `yarn_type_id`, `total_netwt` (rounded), and on the Python side `total_netwt_MT = total_netwt / 1000`.

### `q2_batch_plan_window(_engine, start_d, end_d) -> DataFrame`
- **Inputs bound:** `:co_id`, `:start_d`, `:end_d`.
- **Tables:** `vowsls.batch_plan_daily_implement bpdi` LEFT JOIN `vowsls.yarn_type_master ytm`.
- **Filter:** `bpdi.company_id`, `plan_date BETWEEN :start_d AND :end_d`, `bpdi.is_active = 1`.
- **Returned columns:** `hdr_id, plan_date, batch_plan_code, yarn_type_id, yarn_type`.

### `q3_batch_composition(_engine) -> DataFrame`
- **Inputs bound:** `:co_id`.
- **Tables:** `vowsls.batch_plan_hdr bph` LEFT JOIN `vowsls.batch_plan_dtl bpd` LEFT JOIN `vowsls.jute_quality_price_master jqpm`.
- **Filter:** `bph.company_id`, `bph.is_active = 1`, plus `bpd.is_active = 1` and matching `company_id` in the join.
- **Returned columns:** `plan_hdr_id, plan_code, plan_name, percentage, jute_quality_id, jute_quality`.

### `q4_roll_stock_snapshot(_engine, opening_dt, closing_dt) -> DataFrame`
- **Inputs bound:** `:opening_dt`, `:closing_dt` (both `roll_opening_dt_str`).
- **Tables:** `EMPMILL12.spreader_prod_entry`, `EMPMILL12.spreader_roll_issue`.
- **Logic:** Four `UNION ALL` legs computing per `(bin_no, entry_id_grp, wt_per_roll, jute_quality_id)`:
  1. Opening production rolls **before** `:opening_dt`.
  2. Negative opening adjustment from issues **before** `:opening_dt`.
  3. Production **within** `[:opening_dt, :closing_dt)` (always zero because opening == closing).
  4. Issues **within** the same window (always zero).
- **HAVING** filters out rows where every value is zero.
- **Returned columns:** `bin_no, entry_id_grp, wt_per_roll, jute_quality_id, openstock, prodroll, issueroll, closstock`. The page additionally derives `closstock_rolls = closstock` and `closstock_MT = closstock * wt_per_roll / 1000`.

### `q5_maturity_map(_engine) -> DataFrame`
- No bound params.
- **Table:** `EMPMILL12.maturity_time_master mtm`.
- **Returned columns:** `jute_quality_id, maturity_hours`.

### `q6_jute_quality_lookup(_engine) -> DataFrame`
- **Inputs bound:** `:co_id`.
- **Table:** `vowsls.jute_quality_price_master jqpm`.
- **Returned columns:** `jute_quality_id, jute_quality`.

### DataFrame summary
| Variable | Source | Key columns |
|---|---|---|
| `prod_df` | `q1` | `yarn_type, yarn_type_id, total_netwt, total_netwt_MT` |
| `plan_df` | `q2` | `hdr_id, plan_date, batch_plan_code, yarn_type_id, yarn_type` |
| `composition_df` | `q3` | `plan_hdr_id, plan_code, plan_name, percentage, jute_quality_id, jute_quality` |
| `maturity_df` | `q5` | `jute_quality_id, maturity_hours` |
| `roll_stock_df` | `q4` | `…, closstock, closstock_MT` |
| `quality_lookup_df` | `q6` (or fallback from `composition_df`) | `jute_quality_id, jute_quality` |

`quality_lookup_df` has a fallback: when `q6` returns empty but `composition_df` is non-empty, it is rebuilt from the unique `(jute_quality_id, jute_quality)` pairs in the composition.

---

## 4. Display sections & their outputs

### Section A — Production by Yarn Type (selected date)
- Subheader: **"A. Production by Yarn Type (selected date)"**.
- If `prod_df` is empty → `st.info("No production rows for the selected date.")`.
- Else, inside an expander:
  - Left column: `st.dataframe` of `[yarn_type, yarn_type_id, total_netwt, total_netwt_MT]` with a caption noting the production date.
  - Right column: two `st.metric` cards:
    - `"Total production (kg)"` = `prod_df.total_netwt.sum()`.
    - `"Total production (MT)"` = `total_kg / 1000`.

### Section B — Batch Plan (selected_date+1 → +5 days)
- If `plan_df` is empty → `st.info("No active batch plan entries in this 5-day window.")`.
- Else the page builds:
  - `plan_dates` = sorted unique non-null `plan_date` values.
  - `plan_df['yarn_label']` = `yarn_type` or fallback `f"Yarn {yarn_type_id}"` or `"Unmapped"`.
  - `prod_base_map` = `{yarn_type → total_netwt}` from `prod_df`.
  - `table_df` = one row per yarn label with a `Reference Production (kg)` column (falling back to `1000.0` when missing/zero) and a `{date} %` column per plan date (default `100.0`).

#### B.1 — Editable Batch Plan Targets
- Markdown header **"Batch Plan Targets (per date)"**.
- `st.data_editor` renders the percentage editor described in §2.2.
- After edit, `targets_df` is derived: for each date column, `{date} Target (kg) = Reference Production (kg) × {date} % / 100` (rounded to 2 dp).

#### B.2 — Batch ↔ Yarn Pivot (Targets in kg)
- `target_long` = melt of the `Target (kg)` columns to long form with `plan_date`.
- Merged with `plan_df[['plan_date', 'yarn_label', 'batch_plan_code']]` on `(plan_date, Yarn Type)`. Missing `batch_plan_code` is filled `"Unassigned"`.
- Pivoted to a `(Batch Plan Code × Yarn Type)` × `plan_date` table with:
  - Date columns sorted chronologically.
  - `Row Total (kg)` per row.
  - A `Grand Total` row appended with `date_totals` and overall total.
- Output: `st.dataframe` titled **"Batch ↔ Yarn Pivot (Targets in kg)"** with a window caption.

#### B.3 — Batch Plan Totals by Date (expander)
- `batch_totals` = `summary.groupby(['batch_plan_code', 'plan_date']).Target (kg).sum()`.
- Pivoted to `Batch Plan Code × plan_date`, reindexed to ensure all date columns, with `Row Total (kg)` and a `Grand Total` row.
- Output: collapsed expander **"Batch Plan Totals by Date"**.

#### B.4 — Batch Plan with Jute (composition expander)
- Subset of `composition_df` whose `plan_code` is in the active batch plan codes.
- Renamed columns: `Batch Plan Code, Plan Name, Jute Quality, Percentage (%)` (rounded to 2 dp).
- Output: collapsed expander **"Batch Plan with Jute"**.

#### B.5 — Batch Plan with Jute — Contributions (MT)
- `contributions` = composition rows merged with `batch_totals_pivot` (excluding the Grand Total) so each row has its plan's daily totals.
- For each date column: `contribution = daily_total × percentage / 100`.
- `Row Total (kg)` summed across dates.
- The final display divides date columns and the row total by `1000` to express in MT, renaming `Row Total (kg)` → `Row Total (MT)`.
- Output: collapsed expander **"Batch Plan with Jute — Contributions (MT)"**.

#### B.6 — Jute Quality Totals (MT)
- `jute_totals` = `contributions_display.groupby('Jute Quality')[date_columns + ['Row Total (MT)']].sum()` (3 dp).
- Output: collapsed expander **"Jute Quality Totals (MT)"**.

##### Side-effect maps used downstream
- `plan_issue_date = selected_date + 1 day`; `plan_issue_label` = its `YYYY-MM-DD` string.
- `jute_day_totals_map`: `{Jute Quality → MT planned to be issued on plan_issue_date}`. If that date is absent from `jute_totals`, all values default to `0.0`.

#### B.7 — Target Roll Stock (MT) (expander)
Only computed when `maturity_df` is non-empty.
- `maturity_named` = `maturity_df` joined to `quality_lookup_df` on `jute_quality_id`. Rows with no quality match are dropped (when the lookup exists); otherwise `jute_quality` is coerced from the id.
- `maturity_by_quality` = `maturity_named.groupby('jute_quality').maturity_hours.mean()`.
- `target_stock = jute_totals.merge(maturity_by_quality, on='Jute Quality')` (missing maturity → `0.0`).
- Each date column is transformed to `target_value × maturity_hours / 24` (i.e. converted from "daily target MT" into "stock cover in MT for `maturity_hours/24` days").
- Output: expander **"Target Roll Stock (MT)"** with columns `[Jute Quality, *date_columns]`.

#### B.8 — Current roll stock map
- From `roll_stock_df`: `current_stock = roll_stock_df.groupby('jute_quality_id').closstock_MT.sum()`.
- Joined to `quality_lookup_df` to attach a human-readable `label` (falls back to the id when missing).
- `current_stock_map`: `{label → closstock_MT}` rounded to 3 dp.

#### B.9 — Target Roll Stock Snapshot (MT)
For each row of `target_stock` (i.e. each planned jute quality):
- `maturity_hours` from the row (defaulted to 0).
- `days_offset = round(maturity_hours / 24) + 1`.
- `closing_dt = selected_date + days_offset` (formatted `YYYY-MM-DD`).
- `target_value = target_stock[closing_dt_str]` if present else `0.0`.
- `current_value = current_stock_map[Jute Quality]` else `0.0`.
- `plan_issue = jute_day_totals_map[Jute Quality]` else `0.0`.
- **`required_issue = target_value - (current_value - plan_issue)`**.
- `planned_qualities` records the quality so it is not double-counted below.

Additionally, for every quality present in `current_stock_df` but **not** in `planned_qualities`:
- `maturity_hours` from `maturity_lookup`.
- `days_offset = round(maturity_hours / 24)` (no `+1` here).
- `closing_dt = selected_date + days_offset` if maturity > 0 else `selected_date`.
- `target_value = 0.0`, and `required_issue = 0 - (current_value - plan_issue)`.

All rows go into `snapshot_df` with columns:
`Jute Quality, Closing Target Stock Date, Target Stock (MT), Current Roll Stock (MT), Plan Issue (MT), Required Issue`.
Sorted by `Current Roll Stock (MT)` descending.

- Output: expander **"Target Roll Stock Snapshot (MT)"** with a caption referencing `roll_snapshot_dt`.

#### B.10 — Required Issue Snapshot (main output)
Built from `snapshot_df`:
- `summary_df = snapshot_df[['Jute Quality', 'Required Issue']]`.
- `Required Issue (Bales) = Required Issue / 0.148` (3 dp) — a hard-coded 0.148 MT/bale conversion.
- Output: `st.markdown("##### Required Issue Snapshot")` followed by `st.dataframe(summary_df)`.

Final fallback message: if `plan_dates` ends up empty after Section B prep, the page renders `st.info("Batch plan has no dates available for the selected window.")`.

---

## 5. Output catalogue (what a user actually sees)

In on-screen order:

1. **Header banner**: snapshot date/time, company id, maturity tolerance, mode.
2. **Section A header** + expander with the production dataframe and two metric cards (kg, MT).
3. **Section B header** + (when data exists):
   1. **Batch Plan Targets** editor (`st.data_editor`).
   2. **Batch ↔ Yarn Pivot (Targets in kg)** dataframe.
   3. **Batch Plan Totals by Date** (expander).
   4. **Batch Plan with Jute** (expander).
   5. **Batch Plan with Jute — Contributions (MT)** (expander).
   6. **Jute Quality Totals (MT)** (expander).
   7. **Target Roll Stock (MT)** (expander).
   8. **Target Roll Stock Snapshot (MT)** (expander).
   9. **Required Issue Snapshot** — the headline output (`Jute Quality`, `Required Issue` MT, `Required Issue (Bales)`).

**Primary deliverable:** the `Required Issue Snapshot` table — for each jute quality, how many MT (and bales) need to be issued today to land the maturity-adjusted target closing stock on the right date.

---

## 6. Validations and guard rails

The page does no formal schema validation; instead it relies on light empty-check guards and pandas safe-ops. The validations actually present:

| Guard | Where | Effect |
|---|---|---|
| `if prod_df.empty` | Section A | Renders `st.info("No production rows for the selected date.")` and skips A. |
| `if plan_df.empty` | Section B | Renders `st.info("No active batch plan entries …")` and skips B entirely. |
| `if plan_dates:` else `st.info("Batch plan has no dates available for the selected window.")` | Section B | Final fallback when `plan_df` exists but every `plan_date` is null. |
| `quality_lookup_df` fallback | After data load | If `q6` is empty but `composition_df` has quality info, rebuild lookup from composition. |
| `prod_base_map.get(yarn, None)` with `1000.0` default when missing/zero | Building target-table | Prevents division by / multiplication of a zero reference (also avoids `None`). |
| `st.session_state` schema check (`_batch_plan_schema`) | Editor | If `(columns, plan_dates, plan_yarns)` tuple changes, reset the editor to the freshly-built `table_df` so stale user edits don't bleed across plan changes. |
| `min_value=0.0` on each `% NumberColumn` | `column_config` | Prevents negative percentages in the editor. |
| `Yarn Type` and `Reference Production (kg)` columns `disabled=True` | Editor | User cannot edit identifiers / reference base. |
| `target_long = target_long[target_long["Target (kg)"].notna()]` | Pivot prep | Drops NaN targets before merging. |
| `summary["batch_plan_code"].fillna("Unassigned")` | Pivot | Surfaces yarns without a batch plan as a clearly-labelled bucket. |
| `maturity_named.dropna(subset=["jute_quality"])` | Target stock | Drops maturity rows whose quality can't be resolved (when a lookup exists). |
| `if maturity_df is not None and not maturity_df.empty` | Target Roll Stock branch | Whole Target/Required Issue pipeline is skipped if there's no maturity data. |
| `if not current_stock_df.empty` | Snapshot loop | Skips the "unplanned-quality" pass when there is no roll stock at all. |
| `planned_qualities` set | Snapshot loop | Prevents a quality from being added twice (once from the plan side, once from the stock side). |
| `float(... or 0.0)` coercions throughout the snapshot loop | Numeric ops | Defensive against `None` / NaN in maturity, target, current, and plan-issue values. |
| `HAVING closstock <> 0 OR openstock <> 0 OR prodroll <> 0 OR issueroll <> 0` | `q4` SQL | Drops zero-stock rows at the DB level. |
| `STR_TO_DATE(...)` boundary checks with `< :opening_dt` / `>= :opening_dt AND < :closing_dt` | `q4` SQL | Half-open interval prevents double-counting at the boundary; with `opening==closing`, the in-window legs are guaranteed zero. |
| `bpdi.is_active = 1`, `bph.is_active = 1`, `bpd.is_active = 1` | `q2`, `q3` SQL | Restrict to active plans only. |

### Implicit assumptions (NOT validated)
- `selected_date` is freely chosen; there is no bounds check on past/future dates.
- `COMPANY_ID = 2` is hardcoded — no UI to switch tenants.
- `MATURITY_TOLERANCE_HRS = 2` is displayed but never consumed.
- `0.148` MT/bale conversion is a magic constant.
- `wt_per_roll` is assumed to be in kg (the comment in `q1` explicitly notes the kg→MT conversion).
- Cache TTL is uniformly 60 s; concurrent edits within that window will see stale numbers.
- `roll_snapshot_dt = snapshot_dt + 1 day`: "current stock" is the next-day 06:00, not the selected date's 06:00.

---

## 7. Data-flow diagram (textual)

```
selected_date (UI)
   │
   ├── snapshot_dt ─── roll_snapshot_dt ──► q4_roll_stock_snapshot ──► roll_stock_df
   │
   ├── range_start, range_end ──────────► q2_batch_plan_window ─────► plan_df
   │
   └── selected_date ──────────────────► q1_production_by_yarn ────► prod_df

(no date deps) ─────────────────────────► q3_batch_composition ────► composition_df
(no date deps) ─────────────────────────► q5_maturity_map ─────────► maturity_df
(no date deps) ─────────────────────────► q6_jute_quality_lookup ──► quality_lookup_df
                                              │ fallback if empty
                                              └── composition_df[['jute_quality_id','jute_quality']]

prod_df ─► Section A (table + metrics)

plan_df ┐
prod_df ┼─► table_df ──► st.data_editor ──► percent_df ──► targets_df ──► target_long
       │                                                                     │
       └─────────────► plan_lookup ─────────────────────────────────────────┘
                                            │
                                            ▼
                                   summary, pivot_df, batch_totals_pivot
                                            │
composition_df ─────────────────────────────┤
                                            ▼
                              contributions ─► contributions_display (MT)
                                            │
                                            ▼
                                       jute_totals
                                            │
maturity_df ─► maturity_by_quality ────────┤
                                            ▼
                                      target_stock
                                            │
roll_stock_df ─► current_stock_map ────────┤
jute_day_totals_map ───────────────────────┤
                                            ▼
                                      snapshot_df
                                            │
                                            ▼
                                Required Issue Snapshot (MT + Bales)
```

---

## 8. Quick reference — formulas

- `total_netwt_MT = total_netwt / 1000`
- `closstock_MT = closstock × wt_per_roll / 1000`
- `Target (kg) = Reference Production (kg) × percentage / 100`
- `Contribution (kg) = Daily plan total (kg) × composition percentage / 100`
- `Target Roll Stock (MT) = Daily Jute Total (MT) × maturity_hours / 24`
- `Required Issue (MT) = Target Stock − (Current Roll Stock − Plan Issue)`
- `Required Issue (Bales) = Required Issue (MT) / 0.148`

---

## 9. Known limitations / things to watch

1. `MATURITY_TOLERANCE_HRS` is advertised but not wired into any logic.
2. `opening_dt_str` / `closing_dt_str` (the in-day pair) are computed but never bound to a SQL — only the next-day pair is used.
3. `COMPANY_ID` is hardcoded; multi-company support would require a selector.
4. `0.148` MT/bale and `1000.0` kg fallback are magic numbers.
5. The 0-default percentages can produce 0 targets, which in turn make `Required Issue ≈ Plan Issue − Current Stock` — easy to misread as "we have excess stock" when really nothing was planned.
6. `round(maturity_hours / 24)` truncates sub-day differences in maturity, then adds `+1` for the planned-quality branch and `+0` for the unplanned branch, which is asymmetric and is the most likely source of off-by-one date confusion in the snapshot.
7. Cache TTL is 60 s for every query; users editing percentages will still hit the same cached query results, but a stale row in `roll_stock_df` is invisible until 60 s elapse.
