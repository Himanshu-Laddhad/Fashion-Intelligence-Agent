# Agent Context & Plan Deviations

> This file tracks decisions, deviations from `CURSOR_TASKS.md`, and environment-specific notes.  
> Updated by the agent as tasks are executed. Reference this before starting any new task.

---

## Environment

| Item | Value |
|---|---|
| OS | Windows 10 (win32 10.0.26200) |
| Python | 3.13.5 |
| Shell | PowerShell (use `;` not `&&` for chaining commands) |
| Conda | Not available |
| C++ Build Tools (MSVC) | **Not installed** — affects any package requiring native compilation |

---

## Task Log

### TASK 0.1 — Dependencies (2026-04-20)
**Status:** ✅ Completed with substitutions

**Original plan packages installed successfully:**
- `duckdb`, `pytrends`, `praw`, `prophet`, `lifetimes`, `sentence-transformers`
- `lifelines`, `mlflow`, `pandera`, `umap-learn`, `hdbscan`, `statsmodels`
- `scipy`, `plotly`, `pymannkendall`

**Substitutions made (MSVC build tools not available):**

| Original (CURSOR_TASKS.md) | Replacement | Reason |
|---|---|---|
| `implicit>=0.7.2` | `cornac>=1.18.0` | `implicit` has no pre-built wheel for Python 3.13 on Windows; requires CMake + Visual Studio. `cornac` covers ALS, BPR, and more, with pre-built wheels. ✅ Installed `cornac==2.3.5` |
| `scikit-survival>=0.22.0` | ~~`pysurvival`~~ → **`lifelines` (already installed)** | All `scikit-survival` versions depend on `ecos` (MSVC required). `pysurvival` also failed — source-only, no Python 3.13 wheels. `lifelines` (Cox PH, Kaplan-Meier, Weibull, etc.) already installed covers all planned survival analysis use cases. ✅ No new install needed |

**API mapping for future tasks:**

- `implicit.als.AlternatingLeastSquares` → `cornac.models.MF` or `cornac.models.BPR`
- `sksurv.ensemble.RandomSurvivalForest` → `lifelines` does not have RSF; defer or implement via `scikit-learn` ExtraTrees if needed
- `sksurv.linear_model.CoxPHSurvivalAnalysis` → `lifelines.CoxPHFitter`

---

## Known Constraints

- **PowerShell**: Use `;` to chain commands, not `&&`.
- **No MSVC**: Any future package requiring C compilation will fail unless build tools are installed. Packages to watch: `lightfm`, `implicit`, `ecos`, `osqp`, `cvxpy`.
- **Python 3.13.5**: Some older packages may not have 3.13 wheels yet. Prefer packages with `py3-none-any` wheels.

---

### TASK 0.2 — Database Schema (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `database/schema.sql`

**Notes:**
- Used `CREATE SEQUENCE IF NOT EXISTS` + `DEFAULT nextval(...)` for all integer PKs (DuckDB pattern)
- `customer_segments` uses `customer_id VARCHAR PRIMARY KEY` — no sequence needed (natural key)
- `fashion_items.embedding FLOAT[]` will store `sentence-transformers` vectors (384 or 768-dim)
- Verified: `python -c "import duckdb; ..."` → **Schema OK: 6 tables** ✅

---

### TASK 0.3 — Database Manager Module (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `database/__init__.py` (empty), `database/db_manager.py`

**Notes:**
- `DatabaseManager.__init__` resolves `schema.sql` relative to `__file__` so it works from any working directory
- `save_trend_snapshot` / `save_trend_score` / `save_google_trends` use `MAX(id)` to retrieve the inserted row id (DuckDB does not support `lastrowid` on the connection object)
- `save_fashion_items` uses `executemany`; missing df columns safely map to `None`
- `get_trend_history` uses DuckDB's `INTERVAL (?) DAY` parameterised syntax
- Context manager (`__enter__`/`__exit__`) calls `close()` on exit; returns `False` so exceptions propagate normally
- Verified: `python database/db_manager.py` → **"DB initialized OK"** + `outputs/fashion_intelligence.duckdb` created ✅

---

### TASK 0.4 — Integrate DatabaseManager into Orchestrator (2026-04-20)
**Status:** ✅ Completed, no deviations

**Touched:** `backend/orchestrator.py` (3 additions only, nothing removed or changed)

**Additions:**
1. Line 23: `from database.db_manager import DatabaseManager` (after existing imports)
2. Lines 92–103: persist raw scrape data block after exception handling, before data collection summary print
3. Lines 142–149: persist trend scores block after Step 3 brand customizations complete

**Notes:**
- `tvi_score=0.0` and `confidence="pending"` are intentional placeholders — TVI module not yet built
- `retail` component score = `len(zara_df) + len(uniqlo_df)` as specified
- Verified: `python -c "import ast; ast.parse(...)"` → **Syntax OK** ✅
- No existing function signatures, logic, or output changed

---

### TASK 0.5 — Google Trends Data Source (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `data_sources/__init__.py` (empty), `data_sources/google_trends.py`

**Notes:**
- `fetch_trend_timeseries` sleeps 2s after each API call per spec; exceptions return empty DataFrame
- `compute_trend_momentum` selects first non-`isPartial` numeric column — safe for both weekly and daily pytrends responses
- Historical slice uses `iloc[-(52):-8]` (weeks 52–9 from end); falls back gracefully if series is shorter than 52 rows
- `FutureWarning` from `pytrends` about `fillna` downcasting is a library-internal issue — no action needed
- Verified: `python data_sources/google_trends.py` → live result with all 6 keys ✅  
  `{'momentum': 0.92, 'direction': 'rising', 'recent_avg': 63.5, 'related_queries': {...}, 'query': 'denim jacket'}`

---

### TASK 0.6 — H&M Dataset Loader (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `data_sources/hm_loader.py`

**Notes:**
- All file paths are relative (`data/hm/...`) — must be run from project root
- Column selection uses `[c for c in cols if c in df.columns]` guards against schema drift in the Kaggle CSV
- `load_articles` reads `article_id` as `str` dtype to preserve leading zeros
- `load_sample` uses `random_state=42` for reproducibility; caps sample to `len(all_ids)` if dataset is smaller
- `get_data_summary` uses `nunique()` on `customer_id` (not `len`) to count distinct customers
- Verified: `python data_sources/hm_loader.py` → `{'available': False}` (correct — Kaggle CSVs not yet placed) ✅
- **Action required from user:** Place H&M Kaggle CSVs at `data/hm/articles.csv`, `data/hm/customers.csv`, `data/hm/transactions_train.csv`

---

### TASK 0.7 — Trend Velocity Scorer (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/__init__.py` (empty), `analytics/trend_scorer.py`

**Notes:**
- `score_retail_presence` uses `dropna(how="all")` to skip fully-empty rows before counting
- `score_social` upvote boost only applied when `avg_upvotes > 0` (guards log1p(0) = 0 edge case)
- `confidence` logic: `"high"` requires all three components > 20; `"medium"` requires tvi > 30; else `"low"`
- Module-level `score_trend()` is a convenience wrapper — instantiates a fresh `TrendVelocityScorer` each call
- Verified: `python analytics/trend_scorer.py` → `tvi: 50.25, confidence: medium` + assertions pass ✅

---

### TASK 0.8 — Wire TVI into Orchestrator (2026-04-20)
**Status:** ✅ Completed, no deviations

**Touched:** `backend/orchestrator.py` (4 additions, nothing removed or changed)

**Additions:**
1. Lines 24–25: `from analytics.trend_scorer import score_trend` + `from data_sources.google_trends import get_trend_signal`
2. Lines 144–165: Step 3.5 block — calls `get_trend_signal` then `score_trend`; full `except` block sets `google_signal = {}` so result dict guard `'google_signal' in dir()` always resolves cleanly
3. Lines 169–175: DB persist block updated from placeholder `0.0` values to live `tvi_result.get(...)` values
4. Lines 215–216: `"tvi"` and `"google_signal"` keys added to result dict

**Notes:**
- `google_signal = {}` is explicitly set in the `except` branch so `'google_signal' in dir()` always evaluates to `True` — the `dir()` guard is still kept for safety per spec
- `get_trend_signal` makes a live pytrends call; adds ~8s per query run (includes 2s sleep from Task 0.5)
- Verified: `python -c "import ast; ast.parse(...)"` → **Syntax OK** ✅

---

### TASK 0.9 — Prophet Trend Forecaster (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/trend_forecaster.py`

**Notes:**
- `prophet` installed cleanly (no MSVC needed) — no substitution required
- `warnings.filterwarnings("ignore")` suppresses Prophet's FutureWarnings
- cmdstanpy re-registers its `StreamHandler` on every `model.fit()` call, so `logging.getLogger` level-setting alone is insufficient. Fix: `logging.disable(logging.INFO)` bracketing the `fit()` call, restored to `logging.NOTSET` in `finally`
- stdout is also redirected during fit via `io.StringIO()` as belt-and-braces suppression
- `prepare_prophet_df` handles both DatetimeIndex (pytrends output) and plain `ds`/`date` column DataFrames
- `fit_and_forecast` uses future-only rows for direction calc; `ds` serialised to `"%Y-%m-%d"` strings in the returned forecast records (JSON-safe)
- Verified: `python analytics/trend_forecaster.py` → `Forecast available: True` + `Forecaster OK`, no log noise ✅

---

### TASK 1.0 — Statistical Trend Tests (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/statistical_tests.py`

**Notes:**
- `run_mann_kendall` guards for no-numeric-column case in addition to the spec's < 10 rows guard
- `compute_descriptive_stats` returns `float("nan")` for `cv` when `mean == 0` (avoids ZeroDivisionError)
- `test_trend_significance` resets the series index before midpoint split so `iloc` is positionally correct after `dropna()`
- Verified: `python analytics/statistical_tests.py` → `MK significant: True`, `Trend: increasing`, `Statistical tests OK` ✅

---

## Upcoming Tasks (from CURSOR_TASKS.md)

| Task | Description | Notes |
|---|---|---|
| 1.1+ | TBD | — |

---

*Last updated: 2026-04-20 by agent*
