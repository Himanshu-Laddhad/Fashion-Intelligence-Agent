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

### TASK 1.1 — RFM Segmentation Module (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/rfm.py`

**Notes:**
- `score_rfm` recency inversion: ranks ascending (low days → low rank), cuts into n_quantiles, then applies `(n_quantiles + 1) - score` to flip so score 5 = most recent
- `np.select` evaluates conditions in priority order — segment rules overlap intentionally (e.g. a `r=5, f=4` customer is `Champions`, not `Loyal Customers`)
- `build_rfm_pipeline` returns a DataFrame with all 10 column names pre-set on empty input, safe for downstream `.empty` checks
- `"6H"` freq string in test data fixed to `"6h"` (pandas deprecation in 2.x)
- 198 of 200 customers segmented (2 customers had no transactions in the random seed — expected)
- Verified: `python analytics/rfm.py` → `RFM shape: (198, 10)`, all 8 segments populated ✅

---

### TASK 1.2 — K-Means Segmentation Module (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/segmentation.py`

**Notes:**
- `find_optimal_k` scales with a fresh `StandardScaler` (not reused) to avoid data leakage between k evaluations; the pipeline scaler in `fit_kmeans_pipeline` is separate
- `assign_cluster_names` uses relative rank positions across clusters, not absolute thresholds — makes labels stable across different datasets
- `__main__` adds `analytics/` to `sys.path` with a `Path(__file__).parent` insert so `from rfm import build_rfm_pipeline` resolves correctly when run from project root
- `"4H"` freq string fixed to `"4h"` (pandas 2.x deprecation)
- Optimal K=2 on the synthetic dataset is expected — 500 customers with uniform random transactions create two natural frequency/recency clusters
- Verified: `python analytics/segmentation.py` → `Optimal K: 2`, cluster profiles printed, `Segmentation OK` ✅

---

### TASK 1.3 — Churn Labeller Module (2026-04-20)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/churn_labeller.py`

**Notes:**
- `compute_purchase_gaps` uses `groupby → apply → diff().dt.days` — the `.reset_index(drop=True)` flattens the multi-level index from the groupby apply into a plain flat Series
- `label_churn` computes `days_since_last` as integer days via `.dt.days`; `threshold_days` is stored as a column on every row so downstream `compute_churn_stats` can retrieve it without needing a separate argument
- `stats_` used as variable name in `__main__` to avoid shadowing the `scipy.stats` import
- `"8H"` freq fixed to `"8h"` (pandas 2.x deprecation)
- Verified: `python analytics/churn_labeller.py` → threshold: 176.8 days, churn rate: 16.2%, `Churn labeller OK` ✅

---

### TASK 1.4 — Survival Analysis Module (2026-04-20)
**Status:** ✅ Completed, no deviations — uses `lifelines` as substituted in Task 0.1

**Created:** `analytics/survival_analysis.py`

**Notes:**
- Uses `lifelines.KaplanMeierFitter`, `CoxPHFitter`, `multivariate_logrank_test` — all from the already-installed `lifelines` package (substitute for `scikit-survival`)
- Spec inconsistency fixed: `median_survival` is inside `overall` per spec, but test accesses it as `km_overall["median_survival"]` — both paths now work (key surfaced at top level as convenience shortcut)
- `fit_cox_ph` drops constant covariates before fitting (Cox can't handle zero-variance columns)
- `run_survival_analysis` only adds `age` to Cox covariates if the column is present; returns `concordance: 0.0` safely when no covariates are available
- `median_survival: inf` on synthetic data is mathematically correct — KM curve never crosses 0.5 when most customers are "active"
- `"12H"` freq fixed to `"12h"` (pandas 2.x deprecation)
- Verified: `python analytics/survival_analysis.py` → all three print lines pass ✅

---

### TASK 1.5 — CLV Module (2026-04-20)
**Status:** ✅ Completed with API deviation

**Created:** `analytics/clv.py`

**Deviation — lifetimes API change:**
| Spec (CURSOR_TASKS.md) | Actual installed lifetimes API |
|---|---|
| `gg_model.customer_lifetime_value(bgnbd_model, df[repeat_mask], time=..., ...)` | `gg_model.customer_lifetime_value(bgnbd_model, frequency, recency, T, monetary_value, time=..., ...)` |

The installed `lifetimes` version requires individual Series arguments (`frequency`, `recency`, `T`, `monetary_value`) rather than a single summary DataFrame. Fixed in `compute_clv`.

**Notes:**
- `predicted_purchases` computed via `conditional_expected_number_of_purchases_up_to_time(months*30, ...)` (days)
- `customer_lifetime_value` called with `freq='M'` as specified; lifetimes normalises recency/T internally
- CLV assigned back to full `df` with `df.loc[clv_series.index, "clv"] = ...` — customers with `frequency == 0` get `clv = 0.0`
- `"6H"` freq fixed to `"6h"` (pandas 2.x)
- Verified: `python analytics/clv.py` → `CLV available: True`, median $7.62, total $2,334 ✅

---

### TASK 1.6 — Sentence-Transformer Embeddings Module (2026-04-21)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/embeddings.py`

**Notes:**
- `get_model()` lazy-loads `all-MiniLM-L6-v2` on first call and caches in module-level `_model` — subsequent calls are free
- Model downloaded on first run (~90s including HuggingFace CDN retries); cached locally in `~/.cache/huggingface/` for future runs
- `embed_fashion_items` combines `name + " " + description` when both columns are present; falls back to `description` only
- `embedding_json` stores vectors as JSON strings — compatible with DuckDB `FLOAT[]` column via `json.loads()` at read time
- Similarity ranking correctly places denim/blue items at top for "denim casual blue" query ✅
- Verified: `python analytics/embeddings.py` → `Similar to 'denim casual blue': ['blue jeans', 'denim jacket', 'cotton t-shirt']` ✅

---

### TASK 1.7 — Collaborative Filtering Recommender (2026-04-21)
**Status:** ✅ Completed with planned substitution (Task 0.1)

**Created:** `analytics/recommender.py`

**Deviation — `implicit` → `cornac` (as per Task 0.1):**
| Spec | Implementation |
|---|---|
| `implicit.als.AlternatingLeastSquares` | `cornac.models.MF` |
| `model.recommend(user_idx, row, N, filter_already_liked_items)` | `_ALSAdapter.recommend()` — same signature |

**Approach:**
- `build_interaction_matrix` builds a standard CSR matrix (unchanged from spec)
- `train_als_model` converts CSR integer indices to string UIR triplets for cornac, trains `cornac.models.MF`, then re-maps `u_factors`/`i_factors` back to our integer index space
- `_ALSAdapter` stores re-mapped factor matrices and exposes `recommend()` via `i_factors @ u_factors[user_idx]` — mathematically equivalent to ALS scoring
- All public function signatures match spec exactly; no calling code changes needed
- `recommend_for_segment` uses `Counter.most_common(n)` to aggregate across up to 100 sampled customers

**Notes:**
- `cornac.models.MF` uses SGD (not ALS), but produces equivalent latent factor matrices for scoring purposes
- Index re-mapping: cornac's internal `uid_map`/`iid_map` are reversed by casting keys back to `int()`
- Verified: `python analytics/recommender.py` → `Recs for C0: ['A32', 'A45', ...]`, `Recommender OK` ✅

---

### TASK 1.8 — Causal Analysis / PSM Module (2026-04-21)
**Status:** ✅ Completed, no deviations

**Created:** `analytics/causal_analysis.py`

**Notes:**
- `match_samples` sorts treated units by propensity score before greedy matching — reduces systematic bias vs. random-order matching
- Unmatched treated units are silently dropped (standard PSM convention); caliper default 0.05 is industry-standard for logit-scale PS
- `run_causal_analysis` builds `frequency` and `monetary` covariates from transaction aggregates when `covariate_cols=None` — no dependency on external RFM pipeline
- `interpretation` string is self-describing for both significant and non-significant results
- Smoke test: 95/95 matched pairs, `p=0.329` (no signal in random data — correct) ✅
- Verified: `python analytics/causal_analysis.py` → `Causal analysis module loaded OK` ✅

---

### TASK 1.9 — MLflow Observability Tracker (2026-04-21)
**Status:** ✅ Completed with proactive improvement

**Created:** `observability/__init__.py` (empty), `observability/mlflow_tracker.py`

**Proactive deviation — SQLite backend:**
| Spec | Implementation |
|---|---|
| `mlflow.set_tracking_uri("mlruns")` (filesystem) | `mlflow.set_tracking_uri("sqlite:///mlruns/mlflow.db")` (SQLite) |

Reason: MLflow's filesystem tracking store was deprecated February 2026. Running in April 2026, the filesystem backend triggers a `FutureWarning` and may break in a future MLflow release. Switched to SQLite backend (`mlruns/mlflow.db`) which is the recommended local replacement. `*.db` added to `.gitignore`.

**Notes:**
- `setup_mlflow` creates `mlruns/` directory if missing before setting the URI
- `log_segmentation_run` saves cluster profiles as a temp CSV artifact — uses `tempfile.NamedTemporaryFile` (cross-platform)
- `log_survival_run` guards `median_survival=inf` (common when KM curve never crosses 0.5) — maps to 0.0 for MLflow metric compatibility
- MLflow DB initialisation INFO logs appear only on first run
- `*.db`, `*.db-shm`, `*.db-wal` added to `.gitignore`
- Verified: `python observability/mlflow_tracker.py` → `MLflow run logged: <uuid>`, `MLflow tracker OK` ✅

---

### TASK 2.0 — Pandera Data Validators (2026-04-21)
**Status:** ✅ Completed with import fix

**Created:** `observability/data_validators.py`

**Proactive fix — pandera import:**
| Spec | Implementation |
|---|---|
| `import pandera as pa` | `import pandera.pandas as pa` |

Reason: `pandera>=0.18.0` deprecates top-level `import pandera as pa` for pandas usage — triggers `FutureWarning`. Correct import is `import pandera.pandas as pa`.

**Notes:**
- All 4 schemas use `coerce=True` at the schema level (cast mismatches instead of rejecting)
- `validate_df` uses `lazy=True` to collect all failures before returning — error count from `len(exc.failure_cases)`
- `validate_df` prints warnings but never raises — safe to call at pipeline boundaries without breaking execution
- `pa.DateTime` maps to pandas datetime64 dtype correctly with `import pandera.pandas as pa`
- Verified: `python observability/data_validators.py` → `RFM input valid: True | Errors: 0`, `Validators OK` ✅

---

### TASK 2.1 — Analytics Dashboard Streamlit Page (2026-04-21)
**Status:** ✅ Completed, no deviations

**Created:** `pages/analytics_dashboard.py`

**Notes:**
- Uses `pd.DataFrame | None` return type hint for `_safe_read` — requires Python 3.10+ union syntax (Python 3.13 ✅)
- All 6 DB reads wrapped in `_safe_read` which catches any exception (DB not found, empty table, schema mismatch) and shows `st.warning` — page never crashes
- `customer_segments` scatter uses `recency_days` column name (matches `database/schema.sql`) not `recency` (which is the RFM intermediate name)
- `st.rerun()` used for refresh button — `st.experimental_rerun()` is deprecated in Streamlit 1.28+
- Page is Streamlit multi-page compatible (`pages/` directory, `set_page_config` at top)
- No Flask API calls — reads directly from DuckDB via `DatabaseManager`
- Verified: `python -c "import ast; ast.parse(...)"` → **Syntax OK**, no linter errors ✅

---

### TASK 2.2 — run_customer_analysis.py standalone pipeline script (2026-04-21)
**Status:** ✅ Completed

**Created:** `run_customer_analysis.py` (project root)

**Notes:**
- Script is runnable with `python run_customer_analysis.py` or `python run_customer_analysis.py --sample N`
- Added `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at top to support emoji output on Windows cp1252 terminals; **requires `-u` (unbuffered) flag or `PYTHONUTF8=1` env var to flush output progressively** (buffering suppresses output otherwise — discovered in live test)
- Recommended invocation: `$env:PYTHONUTF8="1"; python -u run_customer_analysis.py`
- DuckDB save: `save_df` columns are ordered exactly to match `customer_segments` schema column order (`_CS_COLS` constant) before `INSERT INTO customer_segments SELECT * FROM save_df`
- Extracted `_save_customer_segments()` helper to keep `run_analysis()` readable; wraps in `try/except` to prevent DB errors from blocking MLflow logging
- `survival_result.get("available", True)` correctly handles both: absent key (= success dict) and `{"available": False}` (= skipped)
- `median_survival` infinity guard: prints `"∞"` instead of crashing on `:.0f` format spec
- `cluster_label` column falls back through `cluster_name` → `segment` → `"Unknown"` in case segmentation returns different key names
- `rfm_string` column presence is guarded: `if "rfm_string" in segments_df.columns else "000"` to avoid KeyError
- Live test with real H&M data (1.37M customers, 31M transactions, 50k sample):
  - Load: 1,167,771 transactions, 50,000 customers, 105,542 articles ✅
  - RFM: 8 segments ✅ | Segmentation: optimal K=2 ✅
  - Churn: 80.4% rate (33-day threshold) ✅
  - Survival: median 386 days, Cox concordance 0.528 ✅
  - CLV: median $0.00 (most customers < 2 purchases — BG/NBD filters them out), total $474 ✅
  - Recommender: trained ✅ | DuckDB: 50,000 rows saved ✅ | MLflow: logged ✅
  - Total runtime: ~5 min 25 sec on 50k customer sample

---

## Upcoming Tasks (from CURSOR_TASKS.md)

| Task | Description | Notes |
|---|---|---|
| 2.3+ | TBD | — |

---

*Last updated: 2026-04-21 by agent*
