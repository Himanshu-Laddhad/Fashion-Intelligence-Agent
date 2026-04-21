# Fashion Intelligence — Cursor Implementation Task Breakdown
> Each task is atomic and self-contained. Give Cursor **one task at a time**.  
> Never skip a task. Each one is a prerequisite for the next.  
> After each task, run the **Verification** command before proceeding.

---

## HOW TO USE THIS FILE
1. Copy the **"Cursor Prompt"** block verbatim into Cursor chat
2. Let Cursor implement it
3. Run the **Verify** command in your terminal
4. If green, move to next task. If red, paste the error back to Cursor.

---

## PHASE 0 — FOUNDATION
> Goal: Persistent storage + new data sources. Nothing analytical yet.

---

### TASK 0.1 — Add New Dependencies to requirements.txt

**Prerequisites:** None  
**Touches:** `requirements.txt` only  

**Cursor Prompt:**
```
Add the following packages to requirements.txt. Do NOT remove or change any existing entries.
Append these at the end under a comment "# Phase 1+ Dependencies":

duckdb>=0.10.0
pytrends>=4.9.0
praw>=7.7.0
prophet>=1.1.5
lifetimes>=0.11.3
implicit>=0.7.2
sentence-transformers>=2.7.0
scikit-survival>=0.22.0
lifelines>=0.27.0
mlflow>=2.13.0
pandera>=0.18.0
umap-learn>=0.5.6
hdbscan>=0.8.33
statsmodels>=0.14.0
scipy>=1.11.0
plotly>=5.20.0
pymannkendall>=1.4.3
```

**Verify:**
```bash
cd /path/to/FashionGpt_Studio
pip install -r requirements.txt --break-system-packages 2>&1 | tail -5
```
✅ Pass = no ERROR lines (warnings OK)

---

### TASK 0.2 — Create Database Schema File

**Prerequisites:** Task 0.1  
**Creates:** `database/schema.sql`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create a new file at database/schema.sql. 
This file contains DuckDB DDL statements to create all tables needed for the Fashion Intelligence system.
Create exactly these tables — no more, no less:

1. trend_snapshots — stores one row per (query, source, timestamp) with columns:
   id INTEGER PRIMARY KEY, query VARCHAR, source VARCHAR, 
   timestamp TIMESTAMP, item_count INTEGER, raw_json JSON

2. trend_scores — stores computed TVI scores per (query, date):
   id INTEGER PRIMARY KEY, query VARCHAR, scored_at TIMESTAMP,
   tvi_score FLOAT, google_trend_score FLOAT, social_score FLOAT,
   retail_score FLOAT, confidence VARCHAR, forecast_json JSON

3. google_trends_raw — stores pytrends time series data:
   id INTEGER PRIMARY KEY, query VARCHAR, fetched_at TIMESTAMP,
   interest_over_time JSON, related_queries JSON

4. fashion_items — stores scraped product items:
   id INTEGER PRIMARY KEY, source VARCHAR, query VARCHAR, 
   scraped_at TIMESTAMP, name VARCHAR, color VARCHAR, 
   material VARCHAR, price FLOAT, image_url VARCHAR, 
   description VARCHAR, embedding FLOAT[]

5. customer_segments — stores RFM + cluster assignment per customer:
   customer_id VARCHAR PRIMARY KEY, recency_days INTEGER,
   frequency INTEGER, monetary FLOAT, rfm_score VARCHAR,
   cluster_id INTEGER, cluster_label VARCHAR, 
   churn_probability FLOAT, clv_12m FLOAT, 
   segmented_at TIMESTAMP

6. model_registry — stores metadata for all trained models:
   id INTEGER PRIMARY KEY, model_name VARCHAR, version VARCHAR,
   trained_at TIMESTAMP, metrics JSON, params JSON, 
   artifact_path VARCHAR

Use SEQUENCE for auto-increment IDs where needed.
Include a comment at the top: "-- Fashion Intelligence DuckDB Schema"
```

**Verify:**
```bash
python -c "import duckdb; con = duckdb.connect(':memory:'); con.execute(open('database/schema.sql').read()); print('Schema OK:', len(con.execute(\"SHOW TABLES\").fetchall()), 'tables')"
```
✅ Pass = prints "Schema OK: 6 tables"

---

### TASK 0.3 — Create Database Manager Module

**Prerequisites:** Task 0.2  
**Creates:** `database/db_manager.py`, `database/__init__.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create database/__init__.py as an empty file.

Create database/db_manager.py with a class DatabaseManager that:

1. __init__(self, db_path: str = "outputs/fashion_intelligence.duckdb"):
   - Creates the outputs/ directory if it does not exist
   - Connects to DuckDB at db_path (creates file if not exists)
   - Runs database/schema.sql to initialize tables if they don't already exist
   - Stores self.conn = the duckdb connection

2. save_trend_snapshot(self, query: str, source: str, df: pd.DataFrame) -> int:
   - Converts df to JSON string
   - Inserts into trend_snapshots table
   - Returns the inserted row id

3. save_trend_score(self, query: str, tvi_score: float, component_scores: dict, confidence: str) -> int:
   - Inserts into trend_scores table
   - component_scores has keys: google, social, retail
   - Returns the inserted row id

4. save_google_trends(self, query: str, interest_df: pd.DataFrame, related: dict) -> int:
   - Inserts into google_trends_raw table
   - Returns the inserted row id

5. save_fashion_items(self, query: str, source: str, df: pd.DataFrame) -> int:
   - Inserts items from df into fashion_items table
   - Maps df columns to table columns — if a column doesn't exist in df, insert NULL
   - Returns count of rows inserted

6. get_trend_history(self, query: str, days: int = 90) -> pd.DataFrame:
   - Returns all trend_scores rows for query within last N days
   - Returns empty DataFrame if none found

7. get_fashion_items(self, query: str, source: str = None) -> pd.DataFrame:
   - Returns all fashion_items for query, optionally filtered by source

8. close(self):
   - Closes self.conn

Use a context manager (__enter__ / __exit__) so it can be used with `with DatabaseManager() as db:`.

Import: duckdb, pandas, json, pathlib.Path, datetime. 
No other imports.
Add a __main__ block that instantiates DatabaseManager, prints "DB initialized OK", and closes.
```

**Verify:**
```bash
python database/db_manager.py
```
✅ Pass = prints "DB initialized OK" and creates `outputs/fashion_intelligence.duckdb`

---

### TASK 0.4 — Integrate DatabaseManager into Orchestrator

**Prerequisites:** Task 0.3  
**Touches:** `backend/orchestrator.py` — add DB writes after each scrape step  

**Cursor Prompt:**
```
Modify backend/orchestrator.py. Do NOT change any existing function signatures or logic.
Make only these additions:

1. At the top, add this import (after existing imports):
   from database.db_manager import DatabaseManager

2. Inside run_fashion_query(), after the asyncio.gather() call and after 
   the exception handling block (around line 90, after all 4 DataFrames are ready),
   add this block:
   
   # --- Persist raw scrape data ---
   with DatabaseManager() as db:
       if not pinterest_df.empty:
           db.save_trend_snapshot(query, "pinterest", pinterest_df)
       if not zara_df.empty:
           db.save_fashion_items(query, "zara", zara_df)
           db.save_trend_snapshot(query, "zara", zara_df)
       if not uniqlo_df.empty:
           db.save_fashion_items(query, "uniqlo", uniqlo_df)
           db.save_trend_snapshot(query, "uniqlo", uniqlo_df)
       if not vogue_df.empty:
           db.save_trend_snapshot(query, "vogue", vogue_df)

3. After step 3 (brand customizations complete), add:
   # --- Persist trend scores ---
   with DatabaseManager() as db:
       db.save_trend_score(
           query=query,
           tvi_score=0.0,  # placeholder until TVI module is built
           component_scores={"google": 0.0, "social": 0.0, "retail": len(zara_df) + len(uniqlo_df)},
           confidence="pending"
       )

Do not change anything else. The app must still run exactly as before.
```

**Verify:**
```bash
python -c "
from database.db_manager import DatabaseManager
import pandas as pd
with DatabaseManager() as db:
    db.save_trend_snapshot('test', 'test', pd.DataFrame({'a':[1,2]}))
    print('Write OK')
    df = db.get_trend_history('test')
    print('Read OK, rows:', len(df))
"
```
✅ Pass = prints "Write OK" and "Read OK, rows: 1"

---

### TASK 0.5 — Create Google Trends Module

**Prerequisites:** Task 0.3  
**Creates:** `data_sources/google_trends.py`, `data_sources/__init__.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create data_sources/__init__.py as an empty file.

Create data_sources/google_trends.py with these functions:

1. fetch_trend_timeseries(query: str, timeframe: str = "today 5-y") -> pd.DataFrame:
   - Uses pytrends TrendReq with hl='en-US', tz=360
   - Calls build_payload([query], cat=0, timeframe=timeframe, geo='', gprop='')
   - Returns interest_over_time() as a DataFrame
   - If pytrends raises any exception, print a warning and return empty DataFrame
   - Add a 2-second sleep after the API call to avoid rate limiting

2. fetch_related_queries(query: str) -> dict:
   - Uses pytrends to fetch related_queries() for the given query
   - Returns the dict result, or empty dict on any exception

3. compute_trend_momentum(timeseries_df: pd.DataFrame) -> dict:
   - Takes the DataFrame from fetch_trend_timeseries
   - If DataFrame is empty, return {"momentum": 0.0, "direction": "unknown", "recent_avg": 0.0, "historical_avg": 0.0}
   - Computes recent_avg = mean of last 8 weeks
   - Computes historical_avg = mean of weeks 52-9 from end (i.e. older data)
   - Computes momentum = (recent_avg - historical_avg) / (historical_avg + 1e-9)  -- clip to [-1, 1]
   - direction = "rising" if momentum > 0.1, "falling" if momentum < -0.1, else "stable"
   - Returns dict with keys: momentum (float), direction (str), recent_avg (float), historical_avg (float)

4. get_trend_signal(query: str) -> dict:
   - Calls fetch_trend_timeseries(query)
   - Calls compute_trend_momentum on the result
   - Calls fetch_related_queries(query)
   - Returns merged dict: momentum result + {"related_queries": related_queries result, "query": query}

Add a __main__ block:
   result = get_trend_signal("denim jacket")
   print(result)

Imports needed: pytrends.request.TrendReq, pandas, time, typing
```

**Verify:**
```bash
python data_sources/google_trends.py
```
✅ Pass = prints a dict with keys: momentum, direction, recent_avg, historical_avg, related_queries, query  
(Values may be 0 if rate-limited — that's OK as long as no crash)

---

### TASK 0.6 — Create H&M Dataset Loader

**Prerequisites:** Task 0.3  
**Creates:** `data_sources/hm_loader.py`  
**Touches:** Nothing existing  

**Context for Cursor:** The H&M dataset CSVs will be placed by the user at `data/hm/articles.csv`, `data/hm/customers.csv`, `data/hm/transactions_train.csv`. These are from the Kaggle H&M Personalization Fashion Recommendations competition.

**Cursor Prompt:**
```
Create data_sources/hm_loader.py with these functions:

1. check_hm_data_available() -> bool:
   - Checks if all three files exist: data/hm/articles.csv, data/hm/customers.csv, data/hm/transactions_train.csv
   - Returns True if all exist, False otherwise

2. load_articles(nrows: int = None) -> pd.DataFrame:
   - Reads data/hm/articles.csv
   - Keeps only columns: article_id, product_type_name, product_group_name, 
     colour_group_name, perceived_colour_value_name, perceived_colour_master_name,
     section_name, garment_group_name, detail_desc
   - Renames them to: article_id, product_type, product_group, colour_group,
     colour_value, colour_master, section, garment_group, description
   - Returns DataFrame, or empty DataFrame if file not found

3. load_customers(nrows: int = None) -> pd.DataFrame:
   - Reads data/hm/customers.csv
   - Keeps only: customer_id, age, club_member_status, fashion_news_frequency
   - Returns DataFrame, or empty DataFrame if file not found

4. load_transactions(nrows: int = None) -> pd.DataFrame:
   - Reads data/hm/transactions_train.csv with parse_dates=['t_dat']
   - Keeps: t_dat, customer_id, article_id, price, sales_channel_id
   - Renames t_dat to transaction_date
   - Returns DataFrame, or empty DataFrame if file not found

5. load_sample(n_customers: int = 50000) -> dict:
   - Loads transactions (all rows), takes a random sample of n_customers unique customer_ids
   - Filters transactions to those customer_ids only
   - Loads articles and customers filtered to those same IDs
   - Returns {"transactions": df, "articles": df, "customers": df, "n_customers": n_customers}

6. get_data_summary() -> dict:
   - If data not available, return {"available": False}
   - Returns {"available": True, "n_customers": int, "n_articles": int, 
     "n_transactions": int, "date_range": [str, str]}

Add a __main__ block that prints get_data_summary().
```

**Verify:**
```bash
python data_sources/hm_loader.py
```
✅ Pass = prints `{'available': False}` if data not downloaded yet — this is correct and expected.

> **User action required after this task:** Download H&M dataset from https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data and place CSVs in `data/hm/` folder.

---

## PHASE 1 — TREND INTELLIGENCE ENGINE

---

### TASK 1.1 — Create Trend Velocity Index (TVI) Scorer

**Prerequisites:** Tasks 0.3, 0.5  
**Creates:** `analytics/trend_scorer.py`, `analytics/__init__.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/__init__.py as an empty file.

Create analytics/trend_scorer.py with these components:

CONSTANTS at top:
   WEIGHT_GOOGLE = 0.45
   WEIGHT_SOCIAL = 0.25
   WEIGHT_RETAIL = 0.30

CLASS TrendVelocityScorer:

   __init__(self):
       No arguments. No external state needed.

   score_retail_presence(self, zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame) -> float:
       - Counts total non-empty rows across both DataFrames
       - Normalises to 0-100 using: min(total_items / 20.0 * 100, 100)
       - Returns the float score

   score_from_google(self, momentum_dict: dict) -> float:
       - Takes the dict returned by data_sources.google_trends.compute_trend_momentum
       - momentum is in [-1, 1] range
       - Maps to 0-100: score = (momentum + 1) / 2 * 100
       - Returns the float score

   score_social(self, reddit_post_count: int, avg_upvotes: float = 0.0) -> float:
       - Maps post_count to 0-100 using log scale: min(log1p(reddit_post_count) / log1p(100) * 100, 100)
       - If avg_upvotes > 0, boost score by up to 10 points: boost = min(log1p(avg_upvotes)/log1p(1000)*10, 10)
       - Returns score + boost, clipped to 100
       - Import math for log1p

   compute_tvi(self, google_score: float, social_score: float, retail_score: float) -> dict:
       - Computes weighted TVI: tvi = WEIGHT_GOOGLE*google + WEIGHT_SOCIAL*social + WEIGHT_RETAIL*retail
       - Rounds tvi to 2 decimal places
       - confidence = "high" if all three scores > 20, "medium" if tvi > 30, else "low"
       - Returns {"tvi": tvi, "google_score": google_score, "social_score": social_score, 
                  "retail_score": retail_score, "confidence": confidence}

   score_query(self, query: str, zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame,
               google_momentum: dict = None, reddit_count: int = 0) -> dict:
       - Computes all three component scores
       - If google_momentum is None, uses {"momentum": 0.0} (no Google data case)
       - Calls compute_tvi
       - Adds key "query": query to result dict
       - Returns the full result dict

FUNCTION (module-level, not in class):
   def score_trend(query: str, zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame,
                   google_momentum: dict = None) -> dict:
       scorer = TrendVelocityScorer()
       return scorer.score_query(query, zara_df, uniqlo_df, google_momentum)

Add __main__ block:
   import pandas as pd
   fake_zara = pd.DataFrame({'name': ['item']*8})
   fake_uniqlo = pd.DataFrame({'name': ['item']*6})
   result = score_trend("denim jacket", fake_zara, fake_uniqlo, {"momentum": 0.3})
   print(result)
   assert "tvi" in result
   assert 0 <= result["tvi"] <= 100
   print("TVI scorer OK")
```

**Verify:**
```bash
python analytics/trend_scorer.py
```
✅ Pass = prints a dict with "tvi" key and "TVI scorer OK"

---

### TASK 1.2 — Integrate TVI into Orchestrator

**Prerequisites:** Task 1.1, Task 0.5  
**Touches:** `backend/orchestrator.py` — add TVI computation after scraping  

**Cursor Prompt:**
```
Modify backend/orchestrator.py. Add TVI scoring as a new step between step 3 (brand customization) and step 4 (image organization).

1. Add these imports at the top (after existing imports):
   from analytics.trend_scorer import score_trend
   from data_sources.google_trends import get_trend_signal

2. After the brand customizations complete print statement, add this new block labeled "Step 3.5":
   
   # Step 3.5: Compute Trend Velocity Index
   print("📈 Step 3.5: Computing Trend Velocity Index...")
   print("-" * 60)
   
   try:
       google_signal = get_trend_signal(query)
       tvi_result = score_trend(
           query=query,
           zara_df=zara_df,
           uniqlo_df=uniqlo_df,
           google_momentum=google_signal
       )
       print(f"   TVI Score: {tvi_result['tvi']:.1f}/100 (confidence: {tvi_result['confidence']})")
       print(f"   Google: {tvi_result['google_score']:.1f} | Social: {tvi_result['social_score']:.1f} | Retail: {tvi_result['retail_score']:.1f}")
   except Exception as e:
       print(f"   ⚠️ TVI computation failed: {e}")
       tvi_result = {"tvi": 0.0, "confidence": "error", "google_score": 0.0, "social_score": 0.0, "retail_score": 0.0}
   
   print("-" * 60 + "\n")

3. In the result dict (around line 160), add these two new keys:
   "tvi": tvi_result,
   "google_signal": google_signal if 'google_signal' in dir() else {},

4. In the existing "Persist trend scores" DB block (from Task 0.4), replace the placeholder values:
   tvi_score=tvi_result.get("tvi", 0.0),
   component_scores={
       "google": tvi_result.get("google_score", 0.0),
       "social": tvi_result.get("social_score", 0.0),
       "retail": tvi_result.get("retail_score", 0.0)
   },
   confidence=tvi_result.get("confidence", "unknown")

Do not change anything else.
```

**Verify:**
```bash
python -c "
from backend.orchestrator import run_fashion_query
import asyncio
from pathlib import Path
# Test that imports work and function signature is intact
print('Orchestrator imports OK')
print('tvi integration ready')
"
```
✅ Pass = no ImportError

---

### TASK 1.3 — Create Trend Forecasting Module

**Prerequisites:** Task 0.5, Task 0.3  
**Creates:** `analytics/trend_forecaster.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/trend_forecaster.py.

This module uses Facebook Prophet to forecast fashion trend trajectory.

IMPORTS: prophet (Prophet), pandas, numpy, json, warnings
Suppress prophet/cmdstanpy warnings with: warnings.filterwarnings('ignore')

FUNCTION: prepare_prophet_df(timeseries_df: pd.DataFrame, query: str) -> pd.DataFrame:
   - timeseries_df has a DatetimeIndex and a column named after the query (or the first column)
   - Prophet requires columns named "ds" (datetime) and "y" (value)
   - Reset index to get the date column, rename appropriately
   - Drop NaN rows
   - Return the prophet-ready DataFrame
   - Return empty DataFrame if input is empty

FUNCTION: fit_and_forecast(prophet_df: pd.DataFrame, periods: int = 90) -> dict:
   - If prophet_df is empty or has fewer than 10 rows, return {"available": False, "reason": "insufficient data"}
   - Initialize Prophet with:
       yearly_seasonality=True, weekly_seasonality=False, 
       daily_seasonality=False, seasonality_mode='multiplicative',
       changepoint_prior_scale=0.05
   - Fit the model (suppress output with redirect or try/except)
   - Create future DataFrame for `periods` days ahead
   - Call predict(future)
   - Extract from forecast: ds, yhat, yhat_lower, yhat_upper for future dates only
   - Compute trend_direction: compare mean of last 30 days of yhat vs first 30 days of yhat
     direction = "rising" if delta > 5, "falling" if delta < -5, else "stable"
   - Return dict:
     {"available": True, "forecast_periods": periods,
      "trend_direction": direction, 
      "forecast": forecast[["ds","yhat","yhat_lower","yhat_upper"]].tail(30).to_dict("records"),
      "changepoints": len(model.changepoints)}

FUNCTION: forecast_trend(query: str, timeseries_df: pd.DataFrame) -> dict:
   - Entry point: calls prepare_prophet_df then fit_and_forecast
   - Wraps in try/except — on any error return {"available": False, "reason": str(e)}

Add __main__ block:
   import pandas as pd, numpy as np
   dates = pd.date_range("2020-01-01", "2024-12-31", freq="W")
   vals = np.random.randint(20, 80, len(dates)).astype(float)
   df = pd.DataFrame({"ds": dates, "y": vals})
   result = fit_and_forecast(df, periods=90)
   print("Forecast available:", result.get("available"))
   print("Direction:", result.get("trend_direction"))
   print("Forecaster OK")
```

**Verify:**
```bash
python analytics/trend_forecaster.py
```
✅ Pass = prints "Forecast available: True", "Direction: ...", "Forecaster OK"

---

### TASK 1.4 — Create Mann-Kendall Trend Significance Test Module

**Prerequisites:** Task 0.5  
**Creates:** `analytics/statistical_tests.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/statistical_tests.py.

This module provides statistical testing on trend time series.

IMPORTS: pymannkendall as mk, pandas, numpy, scipy.stats

FUNCTION: run_mann_kendall(timeseries_df: pd.DataFrame, alpha: float = 0.05) -> dict:
   - Takes a DataFrame with a numeric column (first numeric column is used)
   - Extracts the series values as a list
   - If series has fewer than 10 values, return {"significant": False, "reason": "insufficient data", "p_value": None}
   - Runs mk.original_test(series)
   - Returns dict:
     {"significant": bool (p <= alpha),
      "p_value": float,
      "trend": str (result.trend — "increasing", "decreasing", or "no trend"),
      "slope": float (result.slope),
      "tau": float (result.Tau),
      "alpha_used": alpha}

FUNCTION: run_t_test_vs_baseline(recent_series: pd.Series, baseline_series: pd.Series) -> dict:
   - Runs scipy.stats.ttest_ind(recent_series.dropna(), baseline_series.dropna())
   - Returns dict:
     {"statistic": float, "p_value": float, 
      "significant": bool (p < 0.05),
      "direction": "recent_higher" if t > 0 else "baseline_higher"}

FUNCTION: compute_descriptive_stats(series: pd.Series) -> dict:
   - Returns: {"mean": float, "median": float, "std": float, 
               "q25": float, "q75": float, "min": float, "max": float,
               "cv": float}  -- cv is coefficient of variation (std/mean)

FUNCTION: test_trend_significance(timeseries_df: pd.DataFrame) -> dict:
   - Runs run_mann_kendall on the full series
   - Splits series at midpoint, runs run_t_test_vs_baseline (first half vs second half)
   - Runs compute_descriptive_stats on the full series
   - Returns merged dict of all three results under keys: "mann_kendall", "t_test", "descriptive"

Add __main__ block:
   import numpy as np
   dates = pd.date_range("2022-01-01", periods=52, freq="W")
   vals = np.linspace(30, 70, 52) + np.random.normal(0, 3, 52)
   df = pd.DataFrame({"value": vals}, index=dates)
   result = test_trend_significance(df)
   print("MK significant:", result["mann_kendall"]["significant"])
   print("Trend:", result["mann_kendall"]["trend"])
   print("Statistical tests OK")
```

**Verify:**
```bash
python analytics/statistical_tests.py
```
✅ Pass = prints "MK significant: True", "Trend: increasing", "Statistical tests OK"

---

## PHASE 2 — CUSTOMER INTELLIGENCE (H&M Dataset)

> **Important:** Tasks 2.1+ require H&M data in `data/hm/`. If not available, the modules still load — they return empty results gracefully.

---

### TASK 2.1 — Create RFM Feature Engineering Module

**Prerequisites:** Task 0.6  
**Creates:** `analytics/rfm.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/rfm.py.

This module computes RFM (Recency, Frequency, Monetary) features from transaction data.

IMPORTS: pandas, numpy, datetime

FUNCTION: compute_rfm(transactions_df: pd.DataFrame, 
                       snapshot_date: pd.Timestamp = None) -> pd.DataFrame:
   - transactions_df has columns: customer_id, transaction_date (datetime), price
   - snapshot_date defaults to max(transaction_date) + timedelta(days=1)
   - Computes per customer:
       R = (snapshot_date - max(transaction_date)).days   -- recency in days
       F = count of transactions
       M = sum of price
   - Returns DataFrame with columns: customer_id, recency, frequency, monetary

FUNCTION: score_rfm(rfm_df: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
   - Takes output of compute_rfm
   - Scores each dimension into quantiles 1-5 (5=best)
   - Recency: LOWER days = HIGHER score (reverse rank)
   - Frequency: HIGHER = better score
   - Monetary: HIGHER = better score
   - Handle ties with method='first' in rank
   - Adds columns: r_score, f_score, m_score (each 1-5)
   - Adds rfm_string: concatenation e.g. "555", "311"
   - Adds rfm_score: average of r, f, m scores
   - Returns augmented DataFrame

FUNCTION: label_segments(scored_rfm_df: pd.DataFrame) -> pd.DataFrame:
   - Adds a segment column based on rfm_string patterns:
       r_score=5 and f_score>=4: "Champions"
       r_score>=4 and f_score>=3: "Loyal Customers"
       r_score>=3 and f_score<=2 and m_score>=4: "Big Spenders"  
       r_score>=3 and f_score>=2: "Potential Loyalists"
       r_score=5 and f_score=1: "New Customers"
       r_score<=2 and f_score>=4: "At Risk"
       r_score<=2 and f_score<=2: "Churned"
       all others: "Needs Attention"
   - Returns DataFrame with segment column added

FUNCTION: build_rfm_pipeline(transactions_df: pd.DataFrame) -> pd.DataFrame:
   - Calls compute_rfm -> score_rfm -> label_segments in sequence
   - Returns fully labelled RFM DataFrame
   - Returns empty DataFrame with correct column names if input is empty

Add __main__ block:
   import pandas as pd, numpy as np
   np.random.seed(42)
   n = 1000
   customers = [f"C{i}" for i in range(200)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, n),
       "transaction_date": pd.date_range("2022-01-01", periods=n, freq="6H"),
       "price": np.random.uniform(10, 200, n)
   })
   result = build_rfm_pipeline(df)
   print("RFM shape:", result.shape)
   print("Segments:", result["segment"].value_counts().to_dict())
   print("RFM pipeline OK")
```

**Verify:**
```bash
python analytics/rfm.py
```
✅ Pass = prints RFM shape with 200 rows, segment distribution, "RFM pipeline OK"

---

### TASK 2.2 — Create Customer Segmentation Module (K-Means)

**Prerequisites:** Task 2.1  
**Creates:** `analytics/segmentation.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/segmentation.py.

This module performs K-Means clustering on RFM data and selects optimal K.

IMPORTS: pandas, numpy, sklearn.preprocessing.StandardScaler,
         sklearn.cluster.KMeans, sklearn.metrics.silhouette_score,
         sklearn.pipeline.Pipeline, warnings, json

FUNCTION: find_optimal_k(rfm_df: pd.DataFrame, k_range: range = range(2, 9)) -> dict:
   - Uses columns: recency, frequency, monetary from rfm_df
   - Scales with StandardScaler
   - For each k in k_range, fits KMeans(n_clusters=k, random_state=42, n_init=10)
   - Computes inertia and silhouette score for each k
   - Selects optimal_k as the k with the highest silhouette score
   - Returns {"optimal_k": int, "inertias": list, "silhouette_scores": list, "k_range": list(k_range)}

FUNCTION: fit_kmeans_pipeline(rfm_df: pd.DataFrame, n_clusters: int = None) -> tuple:
   - If n_clusters is None, calls find_optimal_k to determine it
   - Builds sklearn Pipeline: [("scaler", StandardScaler()), ("kmeans", KMeans(n_clusters=k, random_state=42, n_init=10))]
   - Fits pipeline on [recency, frequency, monetary] columns
   - Returns (fitted_pipeline, cluster_labels_array, optimal_k_info_dict)

FUNCTION: profile_clusters(rfm_df: pd.DataFrame, cluster_labels: np.ndarray) -> pd.DataFrame:
   - Adds cluster_id column to rfm_df copy
   - Groups by cluster_id and computes mean of: recency, frequency, monetary, rfm_score
   - Adds cluster_size column (count per cluster)
   - Returns cluster profile DataFrame

FUNCTION: assign_cluster_names(profile_df: pd.DataFrame) -> dict:
   - Takes the output of profile_clusters
   - For each cluster, assigns a business label based on relative position:
       Lowest recency + highest frequency + highest monetary = "VIP / Champions"
       Highest recency only = "Recently Lost"
       Lowest frequency + lowest monetary = "Dormant"
       Median values = "Core Customers"
       Other patterns = "Segment {id}"
   - Returns dict mapping cluster_id -> cluster_name

FUNCTION: run_segmentation(rfm_df: pd.DataFrame) -> dict:
   - Runs full pipeline: find_optimal_k -> fit_kmeans -> profile_clusters -> assign_cluster_names
   - Returns {"rfm_with_clusters": DataFrame, "cluster_profiles": DataFrame, 
              "cluster_names": dict, "k_info": dict, "n_clusters": int}
   - Returns safe empty result dict if rfm_df is empty

Add __main__ block:
   from rfm import build_rfm_pipeline
   import pandas as pd, numpy as np
   np.random.seed(42)
   customers = [f"C{i}" for i in range(500)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, 2000),
       "transaction_date": pd.date_range("2021-01-01", periods=2000, freq="4H"),
       "price": np.random.uniform(5, 300, 2000)
   })
   rfm = build_rfm_pipeline(df)
   result = run_segmentation(rfm)
   print("Optimal K:", result["n_clusters"])
   print("Cluster profiles:\n", result["cluster_profiles"])
   print("Segmentation OK")
```

**Verify:**
```bash
cd analytics && python segmentation.py && cd ..
```
✅ Pass = prints optimal K (should be 2-7), cluster profile table, "Segmentation OK"

---

### TASK 2.3 — Create Churn Labelling Module

**Prerequisites:** Task 2.1  
**Creates:** `analytics/churn_labeller.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/churn_labeller.py.

This module defines and applies implicit churn labels to transaction data.
(Fashion retail has no explicit cancellation — churn is inferred from purchase gaps.)

IMPORTS: pandas, numpy, scipy.stats

FUNCTION: compute_purchase_gaps(transactions_df: pd.DataFrame) -> pd.Series:
   - Groups by customer_id, sorts by transaction_date
   - Computes days between consecutive purchases per customer
   - Returns all gap values as a single flat Series (for distribution analysis)

FUNCTION: determine_churn_threshold(transactions_df: pd.DataFrame, 
                                     percentile: float = 90.0) -> dict:
   - Calls compute_purchase_gaps
   - Computes the Nth percentile of gap distribution as the churn threshold
   - Also computes: mean, median, std of gaps
   - Returns {"threshold_days": float, "percentile_used": float,
              "mean_gap": float, "median_gap": float, "std_gap": float,
              "n_gaps_analyzed": int}

FUNCTION: label_churn(transactions_df: pd.DataFrame, 
                       snapshot_date: pd.Timestamp = None,
                       threshold_days: float = None) -> pd.DataFrame:
   - snapshot_date defaults to max(transaction_date) + 1 day
   - If threshold_days is None, calls determine_churn_threshold to compute it
   - For each customer, computes days_since_last_purchase relative to snapshot_date
   - Labels churned = True if days_since_last_purchase > threshold_days
   - Returns DataFrame: customer_id, last_purchase_date, days_since_last,
                         threshold_days, churned (bool), churn_label ("Churned" / "Active")

FUNCTION: compute_churn_stats(churn_df: pd.DataFrame) -> dict:
   - Takes output of label_churn
   - Returns {"total_customers": int, "churned": int, "active": int, 
              "churn_rate": float, "threshold_days_used": float}

Add __main__ block:
   import pandas as pd, numpy as np
   np.random.seed(42)
   customers = [f"C{i}" for i in range(300)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, 1500),
       "transaction_date": pd.date_range("2021-01-01", periods=1500, freq="8H"),
       "price": np.random.uniform(10, 150, 1500)
   })
   threshold = determine_churn_threshold(df)
   print("Churn threshold:", threshold["threshold_days"], "days")
   churn_df = label_churn(df)
   stats = compute_churn_stats(churn_df)
   print("Churn rate:", f"{stats['churn_rate']:.1%}")
   print("Churn labeller OK")
```

**Verify:**
```bash
python analytics/churn_labeller.py
```
✅ Pass = prints churn threshold in days, churn rate percentage, "Churn labeller OK"

---

### TASK 2.4 — Create Survival Analysis Module

**Prerequisites:** Task 2.3  
**Creates:** `analytics/survival_analysis.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/survival_analysis.py.

This module runs Kaplan-Meier survival analysis and Cox Proportional Hazards model
on customer cohort data from the H&M dataset.

IMPORTS: lifelines (KaplanMeierFitter, CoxPHFitter), pandas, numpy, warnings
Suppress lifelines convergence warnings: warnings.filterwarnings('ignore')

FUNCTION: prepare_survival_df(transactions_df: pd.DataFrame, 
                               customers_df: pd.DataFrame = None,
                               churn_threshold_days: float = 120.0) -> pd.DataFrame:
   - Computes per customer: 
       first_purchase = min(transaction_date)
       last_purchase = max(transaction_date)
       observation_end = max(last_purchase) + timedelta(days=1) across all customers
       duration = (last_purchase - first_purchase).days + 1
       event_observed = True if (observation_end - last_purchase).days > churn_threshold_days
   - If customers_df provided, left-merges on customer_id to add: age, club_member_status
   - Fills missing age with median age
   - Returns DataFrame: customer_id, duration, event_observed, plus any joined columns

FUNCTION: fit_kaplan_meier(survival_df: pd.DataFrame, 
                            group_col: str = None) -> dict:
   - Fits KaplanMeierFitter on the full dataset
   - If group_col provided, fits separately for each unique group value
   - Returns dict: 
       {"overall": {"timeline": list, "survival_prob": list, "median_survival": float},
        "by_group": {group_val: {"timeline": list, "survival_prob": list} for each group},
        "log_rank_p_value": float or None (None if no group_col)}
   - For log-rank test between groups use lifelines.statistics.logrank_test

FUNCTION: fit_cox_ph(survival_df: pd.DataFrame, 
                     covariate_cols: list) -> dict:
   - Filters survival_df to only rows with no NaN in covariate_cols
   - Fits CoxPHFitter(penalizer=0.1) on [duration, event_observed] + covariate_cols
   - Returns dict:
       {"hazard_ratios": dict of covariate -> HR, 
        "p_values": dict of covariate -> p,
        "concordance": float,
        "significant_covariates": [cols where p < 0.05],
        "summary_html": str}  -- model.summary.to_html()

FUNCTION: run_survival_analysis(transactions_df: pd.DataFrame,
                                 customers_df: pd.DataFrame = None,
                                 churn_threshold_days: float = 120.0) -> dict:
   - Calls prepare_survival_df
   - Calls fit_kaplan_meier with group_col=None (overall curve)
   - If age column present: also calls fit_kaplan_meier with group_col="age_band"
     where age_band = pd.cut(age, bins=[0,25,35,45,100], labels=["<25","25-35","35-45","45+"])
   - Calls fit_cox_ph with available covariate columns (age if present, others as available)
   - Returns {"survival_data": survival_df, "km_overall": dict, 
              "km_by_age": dict or None, "cox": dict,
              "n_customers": int, "churn_rate": float}
   - Returns {"available": False} if transactions_df is empty

Add __main__ block with synthetic data:
   import pandas as pd, numpy as np
   np.random.seed(42)
   customers = [f"C{i}" for i in range(200)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, 800),
       "transaction_date": pd.date_range("2020-01-01", periods=800, freq="12H"),
       "price": np.random.uniform(10,200,800)
   })
   result = run_survival_analysis(df, churn_threshold_days=90.0)
   print("Survival analysis available:", result.get("available", True))
   print("Median survival:", result["km_overall"]["median_survival"])
   print("Cox concordance:", result["cox"]["concordance"])
   print("Survival analysis OK")
```

**Verify:**
```bash
python analytics/survival_analysis.py
```
✅ Pass = prints median survival days, Cox concordance index (~0.5-0.7), "Survival analysis OK"

---

### TASK 2.5 — Create CLV Prediction Module (BG/NBD + Gamma-Gamma)

**Prerequisites:** Task 2.1  
**Creates:** `analytics/clv.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/clv.py.

This module uses the BG/NBD model for purchase frequency prediction
and the Gamma-Gamma model for monetary value, producing 12-month CLV estimates.

IMPORTS: lifetimes (BetaGeoFitter, GammaGammaFitter, 
         summary_data_from_transaction_data), pandas, numpy, warnings
Suppress warnings: warnings.filterwarnings('ignore')

FUNCTION: prepare_lifetimes_df(transactions_df: pd.DataFrame) -> pd.DataFrame:
   - Uses lifetimes.utils.summary_data_from_transaction_data
   - Parameters: transactions_df, customer_id_col='customer_id', 
     datetime_col='transaction_date', monetary_value_col='price',
     observation_period_end=max(transaction_date)
   - Returns the summary DataFrame
   - Return empty DataFrame if input empty or has fewer than 50 unique customers

FUNCTION: fit_bgnbd(summary_df: pd.DataFrame) -> BetaGeoFitter:
   - Fits BetaGeoFitter(penalizer_coef=0.01) on summary_df
   - Returns fitted model

FUNCTION: fit_gamma_gamma(summary_df: pd.DataFrame) -> GammaGammaFitter:
   - Filters to customers with frequency > 0
   - Fits GammaGammaFitter(penalizer_coef=0.01)
   - Returns fitted model

FUNCTION: compute_clv(summary_df: pd.DataFrame, 
                       bgnbd_model: BetaGeoFitter,
                       gg_model: GammaGammaFitter,
                       months: int = 12,
                       discount_rate: float = 0.01) -> pd.DataFrame:
   - Uses gg_model.customer_lifetime_value(bgnbd_model, summary_df, ...)
   - Parameters: time=months, discount_rate=discount_rate, freq='M'
   - Adds clv column to summary_df copy
   - Returns DataFrame with: customer_id (index), frequency, recency, T, 
     monetary_value, predicted_purchases, clv

FUNCTION: run_clv_analysis(transactions_df: pd.DataFrame) -> dict:
   - Calls full pipeline: prepare_lifetimes_df -> fit_bgnbd -> fit_gamma_gamma -> compute_clv
   - Computes CLV percentiles: p25, p50, p75, p90
   - Returns {"available": True, "clv_df": DataFrame, "total_predicted_clv": float,
              "clv_percentiles": dict, "n_customers": int}
   - Returns {"available": False, "reason": str} on any exception or empty data

Add __main__ block:
   import pandas as pd, numpy as np
   np.random.seed(42)
   customers = [f"C{i}" for i in range(300)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, 1500),
       "transaction_date": pd.date_range("2021-01-01", periods=1500, freq="6H"),
       "price": np.abs(np.random.normal(50, 20, 1500))
   })
   result = run_clv_analysis(df)
   print("CLV available:", result["available"])
   if result["available"]:
       print("Median 12m CLV:", result["clv_percentiles"]["p50"])
       print("Total predicted CLV:", f"${result['total_predicted_clv']:,.0f}")
   print("CLV module OK")
```

**Verify:**
```bash
python analytics/clv.py
```
✅ Pass = prints CLV percentile values, total CLV, "CLV module OK"

---

## PHASE 3 — PREDICTIVE / RECOMMENDATION INTELLIGENCE

---

### TASK 3.1 — Create Style DNA Embeddings Module

**Prerequisites:** Tasks 0.3, 0.6  
**Creates:** `analytics/embeddings.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/embeddings.py.

This module creates semantic vector embeddings for fashion items using sentence-transformers.

IMPORTS: sentence_transformers (SentenceTransformer), pandas, numpy, 
         sklearn.metrics.pairwise (cosine_similarity), json

GLOBAL (lazy-loaded):
   _model = None
   MODEL_NAME = "all-MiniLM-L6-v2"

FUNCTION: get_model() -> SentenceTransformer:
   - Uses global _model
   - If _model is None, loads SentenceTransformer(MODEL_NAME)
   - Returns _model
   - This lazy loads the model only when first needed

FUNCTION: embed_text(texts: list) -> np.ndarray:
   - Calls get_model().encode(texts, show_progress_bar=False)
   - Returns numpy array of shape (len(texts), 384)
   - Returns np.zeros((len(texts), 384)) if texts is empty

FUNCTION: embed_fashion_items(df: pd.DataFrame, 
                               text_col: str = "description") -> pd.DataFrame:
   - Takes a DataFrame with a text column
   - Creates a combined_text column: fills NaN with "" then combines with name if available
   - Calls embed_text on combined_text list
   - Stores embedding as JSON string in new column "embedding_json"
   - Returns df with embedding_json added
   - Returns df unchanged if text_col not in df.columns

FUNCTION: find_similar_items(query_text: str, 
                              items_df: pd.DataFrame,
                              top_k: int = 5) -> pd.DataFrame:
   - Embeds query_text
   - Extracts embeddings from items_df.embedding_json (parses JSON strings)
   - Computes cosine similarity between query embedding and all item embeddings
   - Returns top_k rows from items_df with highest similarity, adds "similarity" column
   - Returns empty DataFrame if items_df has no embedding_json column

FUNCTION: build_item_similarity_matrix(items_df: pd.DataFrame) -> np.ndarray:
   - Extracts all embeddings from items_df.embedding_json
   - Computes cosine_similarity matrix
   - Returns numpy array of shape (n_items, n_items)

Add __main__ block:
   df = pd.DataFrame({
       "name": ["denim jacket", "blue jeans", "cotton t-shirt", "silk blouse", "wool coat"],
       "description": [
           "classic blue denim jacket with button closure",
           "slim fit blue denim jeans",
           "soft white cotton t-shirt basic",
           "elegant ivory silk blouse with collar",
           "warm charcoal grey wool winter coat"
       ]
   })
   embedded = embed_fashion_items(df)
   print("Embeddings shape: (5, has embedding_json)")
   similar = find_similar_items("denim casual blue", embedded, top_k=3)
   print("Similar to 'denim casual blue':", similar["name"].tolist())
   print("Embeddings OK")
```

**Verify:**
```bash
python analytics/embeddings.py
```
✅ Pass = prints similar items (should include denim/jeans items), "Embeddings OK"

---

### TASK 3.2 — Create ALS Recommendation Module

**Prerequisites:** Task 2.3  
**Creates:** `analytics/recommender.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/recommender.py.

This module builds an implicit ALS collaborative filtering recommender
trained on H&M purchase interaction data.

IMPORTS: implicit, scipy.sparse (csr_matrix), pandas, numpy, pickle, pathlib

FUNCTION: build_interaction_matrix(transactions_df: pd.DataFrame,
                                    articles_df: pd.DataFrame = None) -> tuple:
   - Builds a customer × article sparse matrix
   - Value = purchase frequency (count of times customer bought article)
   - Creates customer_id -> int index mapping and article_id -> int mapping
   - Returns (sparse_matrix, customer_to_idx dict, article_to_idx dict, idx_to_article dict)

FUNCTION: train_als_model(interaction_matrix: csr_matrix,
                           factors: int = 50,
                           iterations: int = 20) -> implicit.als.AlternatingLeastSquares:
   - Instantiates ALS: factors=factors, iterations=iterations, 
     regularization=0.01, use_gpu=False
   - Fits on interaction_matrix.T (items × users format required by implicit)
   - Returns fitted model

FUNCTION: recommend_for_customer(model, 
                                   customer_id: str,
                                   customer_to_idx: dict,
                                   idx_to_article: dict,
                                   interaction_matrix: csr_matrix,
                                   n: int = 10) -> list:
   - Looks up customer index; returns [] if not found
   - Calls model.recommend(user_idx, interaction_matrix[user_idx], N=n, filter_already_liked_items=True)
   - Returns list of article_id strings for top-N recommendations

FUNCTION: recommend_for_segment(model,
                                  segment_customer_ids: list,
                                  customer_to_idx: dict,
                                  idx_to_article: dict,
                                  interaction_matrix: csr_matrix,
                                  n: int = 10) -> list:
   - For each customer in segment (up to 100 sampled), gets top recommendations
   - Aggregates: counts how often each article appears across recommendations
   - Returns top-n most frequently recommended article_ids for the segment

FUNCTION: run_recommender_pipeline(transactions_df: pd.DataFrame,
                                    articles_df: pd.DataFrame = None) -> dict:
   - Returns {"available": False} if transactions_df empty or < 500 rows
   - Calls build_interaction_matrix -> train_als_model
   - Returns {"available": True, "model": model, "customer_to_idx": dict,
              "idx_to_article": dict, "interaction_matrix": sparse_matrix,
              "n_customers": int, "n_articles": int}

Add __main__ block:
   import pandas as pd, numpy as np
   np.random.seed(42)
   customers = [f"C{i}" for i in range(100)]
   articles = [f"A{i}" for i in range(50)]
   df = pd.DataFrame({
       "customer_id": np.random.choice(customers, 600),
       "article_id": np.random.choice(articles, 600),
       "transaction_date": pd.date_range("2021-01-01", periods=600, freq="12H"),
       "price": np.random.uniform(10,100,600)
   })
   result = run_recommender_pipeline(df)
   print("Recommender available:", result["available"])
   if result["available"]:
       recs = recommend_for_customer(result["model"], "C0", 
              result["customer_to_idx"], result["idx_to_article"],
              result["interaction_matrix"], n=5)
       print("Recs for C0:", recs)
   print("Recommender OK")
```

**Verify:**
```bash
python analytics/recommender.py
```
✅ Pass = prints article recommendations for C0, "Recommender OK"

---

### TASK 3.3 — Create Propensity Score Matching Module

**Prerequisites:** Tasks 2.1, 2.3  
**Creates:** `analytics/causal_analysis.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create analytics/causal_analysis.py.

This module uses propensity score matching (PSM) to test causal claims:
"Do customers who purchase trending items retain better?"

IMPORTS: pandas, numpy, sklearn.linear_model (LogisticRegression),
         sklearn.preprocessing (StandardScaler), scipy.stats (ttest_ind)

FUNCTION: create_treatment_flag(transactions_df: pd.DataFrame,
                                  high_tvi_article_ids: list) -> pd.DataFrame:
   - For each customer, flags treated=1 if they purchased at least one item in high_tvi_article_ids
   - Returns DataFrame: customer_id, treated (0/1), n_trending_purchases

FUNCTION: compute_propensity_scores(treatment_df: pd.DataFrame,
                                     covariate_cols: list) -> pd.DataFrame:
   - Fits LogisticRegression on covariate_cols to predict treated
   - Adds propensity_score column to treatment_df copy
   - Returns augmented DataFrame

FUNCTION: match_samples(scored_df: pd.DataFrame, 
                          caliper: float = 0.05) -> pd.DataFrame:
   - Greedy 1:1 nearest-neighbour matching on propensity_score
   - For each treated unit, find the closest untreated unit within caliper distance
   - Returns matched DataFrame with balanced treated/control groups
   - Adds match_id column

FUNCTION: compute_ate(matched_df: pd.DataFrame, 
                       outcome_col: str) -> dict:
   - Computes Average Treatment Effect on matched data
   - Runs t-test between treated and control on outcome_col
   - Returns {"ate": float, "t_stat": float, "p_value": float,
              "significant": bool, "n_treated": int, "n_control": int,
              "treated_mean": float, "control_mean": float}

FUNCTION: run_causal_analysis(transactions_df: pd.DataFrame,
                               churn_df: pd.DataFrame,
                               high_tvi_article_ids: list,
                               covariate_cols: list = None) -> dict:
   - Returns {"available": False} if either df is empty or article_ids is empty
   - Creates treatment flag, merges with churn_df on customer_id
   - Uses "churned" (from churn_df, as int 1/0) as outcome
   - Covariates default to ["frequency", "monetary"] from transaction aggregates
   - Runs full PSM pipeline
   - Returns {"available": True, "ate_result": dict, "matched_df": DataFrame,
              "n_treated": int, "n_control": int,
              "interpretation": str}
   - interpretation string: e.g. "Trending-item buyers have X% lower churn rate (p=Y)"

Add __main__ block:
   print("Causal analysis module loaded OK")
   print("Run with H&M data for full PSM analysis")
```

**Verify:**
```bash
python analytics/causal_analysis.py
```
✅ Pass = prints two "OK" lines with no errors

---

## PHASE 4 — OBSERVABILITY & DASHBOARD

---

### TASK 4.1 — Add MLflow Experiment Tracking

**Prerequisites:** Task 2.2, Task 2.4, Task 2.5  
**Creates:** `observability/mlflow_tracker.py`, `observability/__init__.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create observability/__init__.py as empty file.

Create observability/mlflow_tracker.py.

This module provides a thin wrapper around MLflow for logging analytics runs.
MLflow will store runs locally in mlruns/ directory.

IMPORTS: mlflow, mlflow.sklearn, pandas, json, pathlib, datetime

FUNCTION: setup_mlflow(experiment_name: str = "fashion_intelligence") -> str:
   - Sets tracking URI to local: mlflow.set_tracking_uri("mlruns")
   - Creates or gets experiment by name
   - Returns experiment_id string

FUNCTION: log_segmentation_run(k_info: dict, cluster_profiles: pd.DataFrame,
                                n_customers: int) -> str:
   - Starts an MLflow run with run_name="kmeans_segmentation"
   - Logs params: {"n_clusters": k_info.get("optimal_k"), "n_customers": n_customers}
   - Logs metrics: {"silhouette_score": max(k_info.get("silhouette_scores", [0])),
                    "optimal_k": k_info.get("optimal_k", 0)}
   - Logs cluster_profiles as artifact (save as CSV to temp file first)
   - Ends run and returns run_id

FUNCTION: log_survival_run(cox_result: dict, km_result: dict, 
                            n_customers: int) -> str:
   - Starts MLflow run with run_name="survival_analysis"
   - Logs params: {"n_customers": n_customers}
   - Logs metrics: {"concordance_index": cox_result.get("concordance", 0),
                    "median_survival_days": km_result.get("median_survival", 0)}
   - Ends run and returns run_id

FUNCTION: log_clv_run(clv_result: dict) -> str:
   - Starts MLflow run with run_name="clv_bgnbd"
   - Logs params: {"n_customers": clv_result.get("n_customers", 0)}
   - Logs metrics: {"median_clv": clv_result.get("clv_percentiles", {}).get("p50", 0),
                    "total_predicted_clv": clv_result.get("total_predicted_clv", 0)}
   - Ends run and returns run_id

FUNCTION: log_tvi_run(query: str, tvi_result: dict) -> str:
   - Starts MLflow run with run_name=f"tvi_{query}"
   - Logs params: {"query": query, "confidence": tvi_result.get("confidence")}
   - Logs metrics: {"tvi_score": tvi_result.get("tvi", 0),
                    "google_score": tvi_result.get("google_score", 0),
                    "retail_score": tvi_result.get("retail_score", 0)}
   - Ends run and returns run_id

Add __main__ block:
   setup_mlflow()
   run_id = log_tvi_run("test_query", {"tvi": 62.5, "confidence": "high", "google_score": 70.0, "retail_score": 55.0})
   print("MLflow run logged:", run_id)
   print("MLflow tracker OK")
```

**Verify:**
```bash
python observability/mlflow_tracker.py && ls mlruns/
```
✅ Pass = prints run_id, "MLflow tracker OK", and mlruns/ directory is created

---

### TASK 4.2 — Add Pandera Data Validation

**Prerequisites:** Task 0.3  
**Creates:** `observability/data_validators.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create observability/data_validators.py.

This module defines Pandera schemas to validate DataFrames at key pipeline boundaries.

IMPORTS: pandera as pa, pandas, typing

DEFINE these schemas as module-level constants:

SCRAPE_SCHEMA = pa.DataFrameSchema({
   "name": pa.Column(str, nullable=True),
}, name="ScrapedProductSchema")
# Note: use coerce=True on all schemas so type mismatches are cast not rejected

RFM_INPUT_SCHEMA = pa.DataFrameSchema({
   "customer_id": pa.Column(str, nullable=False),
   "transaction_date": pa.Column(pa.DateTime, nullable=False),
   "price": pa.Column(float, pa.Check.greater_than(0), nullable=False, coerce=True),
}, name="RFMInputSchema")

RFM_OUTPUT_SCHEMA = pa.DataFrameSchema({
   "customer_id": pa.Column(str, nullable=False),
   "recency": pa.Column(int, pa.Check.greater_than_or_equal_to(0), nullable=False),
   "frequency": pa.Column(int, pa.Check.greater_than(0), nullable=False),
   "monetary": pa.Column(float, pa.Check.greater_than(0), nullable=False),
}, name="RFMOutputSchema")

SURVIVAL_INPUT_SCHEMA = pa.DataFrameSchema({
   "customer_id": pa.Column(str, nullable=False),
   "duration": pa.Column(int, pa.Check.greater_than(0), nullable=False),
   "event_observed": pa.Column(bool, nullable=False),
}, name="SurvivalInputSchema")

FUNCTION: validate_df(df: pd.DataFrame, schema: pa.DataFrameSchema, 
                       label: str = "") -> tuple:
   - Tries schema.validate(df, lazy=True)
   - On SchemaErrors: prints warnings (not raises) with label
   - Returns (is_valid: bool, error_count: int)

FUNCTION: validate_rfm_input(df: pd.DataFrame) -> tuple:
   - Calls validate_df with RFM_INPUT_SCHEMA
   - Returns (bool, int)

FUNCTION: validate_rfm_output(df: pd.DataFrame) -> tuple:
   - Calls validate_df with RFM_OUTPUT_SCHEMA

FUNCTION: get_validation_report(df: pd.DataFrame, schema_name: str) -> dict:
   - Returns {"schema": schema_name, "rows": len(df), "columns": list(df.columns),
              "null_counts": df.isnull().sum().to_dict(),
              "dtypes": df.dtypes.astype(str).to_dict()}

Add __main__ block:
   import pandas as pd
   df = pd.DataFrame({
       "customer_id": ["C1","C2","C3"],
       "transaction_date": pd.to_datetime(["2022-01-01","2022-02-01","2022-03-01"]),
       "price": [10.5, 20.0, 5.0]
   })
   valid, errors = validate_rfm_input(df)
   print("RFM input valid:", valid, "| Errors:", errors)
   print("Validators OK")
```

**Verify:**
```bash
python observability/data_validators.py
```
✅ Pass = prints "RFM input valid: True | Errors: 0", "Validators OK"

---

### TASK 4.3 — Build Analytics Dashboard Page in Streamlit

**Prerequisites:** All Phase 1 and Phase 2 modules  
**Creates:** `pages/analytics_dashboard.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create pages/analytics_dashboard.py.

This is a new Streamlit page (Streamlit multi-page app format) that renders
the analytics dashboard. It does NOT call the Flask API — it reads directly from DuckDB.

IMPORTS: streamlit, plotly.express, plotly.graph_objects, pandas, numpy, 
         sys, pathlib
         sys.path.append(str(pathlib.Path(__file__).parent.parent))
         from database.db_manager import DatabaseManager

PAGE CONFIG: st.set_page_config(page_title="Analytics Dashboard", page_icon="📊", layout="wide")

SECTIONS (render in this order):

1. HEADER:
   st.title("📊 Fashion Intelligence Analytics Dashboard")
   st.caption("Live metrics from DuckDB — updates on each query run")

2. TREND VELOCITY INDEX HISTORY:
   - Loads trend_scores from DB using DatabaseManager().conn.execute("SELECT * FROM trend_scores ORDER BY scored_at DESC LIMIT 100").df()
   - If empty, shows st.info("No TVI data yet. Run a query in the main app.")
   - If data exists, shows:
     a) st.metric cards for: latest TVI, latest confidence, total queries tracked
     b) Plotly line chart of tvi_score over time, coloured by query

3. QUERY FREQUENCY TABLE:
   - Loads from trend_scores, groups by query, counts runs, shows avg TVI
   - Renders as st.dataframe

4. DATA SOURCES HEALTH:
   - Loads from trend_snapshots, groups by source, shows counts and last updated
   - Shows as a table

5. CUSTOMER INTELLIGENCE SECTION:
   - Shows header "👥 Customer Segments (H&M Dataset)"
   - Loads from customer_segments table
   - If empty: st.warning("Run customer analysis first. H&M data required in data/hm/")
   - If data exists:
     a) Pie chart of segment distribution using plotly.express.pie
     b) Scatter plot: monetary vs recency, coloured by cluster_label

6. MODEL REGISTRY:
   - Loads from model_registry table
   - Shows as st.dataframe if not empty

At the bottom add a "🔄 Refresh Data" button that calls st.rerun().

Use try/except around every DB read — show st.warning if DB file doesn't exist yet.
```

**Verify:**
```bash
streamlit run pages/analytics_dashboard.py --server.headless true &
sleep 3 && curl -s http://localhost:8502 | grep -c "Analytics" && kill %1
```
✅ Pass = curl returns 1 (page title found in HTML) — or just open in browser and confirm no crash

---

### TASK 4.4 — Create Master Analysis Runner Script

**Prerequisites:** All previous tasks  
**Creates:** `run_customer_analysis.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create run_customer_analysis.py at the project root.

This is a standalone script the user runs ONCE (or periodically) to:
1. Load H&M data
2. Run the full customer intelligence pipeline
3. Save results to DuckDB
4. Log experiments to MLflow

The script should be runnable with: python run_customer_analysis.py

IMPORTS: sys, pathlib, pandas, datetime, json
from data_sources.hm_loader import check_hm_data_available, load_sample, get_data_summary
from analytics.rfm import build_rfm_pipeline
from analytics.segmentation import run_segmentation
from analytics.churn_labeller import label_churn, determine_churn_threshold, compute_churn_stats
from analytics.survival_analysis import run_survival_analysis
from analytics.clv import run_clv_analysis
from analytics.recommender import run_recommender_pipeline
from database.db_manager import DatabaseManager
from observability.mlflow_tracker import setup_mlflow, log_segmentation_run, log_survival_run, log_clv_run
from observability.data_validators import validate_rfm_input

MAIN FUNCTION run_analysis(sample_customers: int = 50000):

   print("=" * 60)
   print("🧠 Fashion Intelligence — Customer Analysis Pipeline")
   print("=" * 60)
   
   # Step 1: Check data
   if not check_hm_data_available():
       print("❌ H&M data not found in data/hm/")
       print("   Download from: https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data")
       print("   Place files: articles.csv, customers.csv, transactions_train.csv in data/hm/")
       return
   
   print(f"✅ H&M data found: {get_data_summary()}")
   
   # Step 2: Load sample
   print(f"\n📥 Loading {sample_customers:,} customer sample...")
   data = load_sample(n_customers=sample_customers)
   transactions = data["transactions"]
   articles = data["articles"]
   customers = data["customers"]
   print(f"   Transactions: {len(transactions):,} | Customers: {len(customers):,} | Articles: {len(articles):,}")
   
   # Step 3: Validate
   is_valid, n_errors = validate_rfm_input(transactions)
   print(f"   Data validation: {'✅ OK' if is_valid else f'⚠️ {n_errors} issues (continuing anyway)'}")
   
   # Step 4: RFM
   print("\n🧮 Computing RFM features...")
   rfm_df = build_rfm_pipeline(transactions)
   print(f"   RFM complete: {len(rfm_df)} customers | Segments: {rfm_df['segment'].value_counts().to_dict()}")
   
   # Step 5: Segmentation
   print("\n🎯 Running K-Means segmentation...")
   seg_result = run_segmentation(rfm_df)
   print(f"   Optimal K: {seg_result['n_clusters']} | Cluster names: {seg_result['cluster_names']}")
   
   # Step 6: Churn
   print("\n📉 Labelling churn...")
   threshold = determine_churn_threshold(transactions)
   print(f"   Churn threshold: {threshold['threshold_days']:.0f} days (p{threshold['percentile_used']:.0f})")
   churn_df = label_churn(transactions)
   churn_stats = compute_churn_stats(churn_df)
   print(f"   Churn rate: {churn_stats['churn_rate']:.1%} | Active: {churn_stats['active']:,} | Churned: {churn_stats['churned']:,}")
   
   # Step 7: Survival
   print("\n📊 Running survival analysis...")
   survival_result = run_survival_analysis(transactions, customers)
   if survival_result.get("available", True):
       print(f"   Median survival: {survival_result['km_overall']['median_survival']:.0f} days")
       print(f"   Cox concordance: {survival_result['cox']['concordance']:.3f}")
   
   # Step 8: CLV
   print("\n💰 Computing Customer Lifetime Value...")
   clv_result = run_clv_analysis(transactions)
   if clv_result["available"]:
       print(f"   Median 12m CLV: ${clv_result['clv_percentiles']['p50']:.2f}")
       print(f"   Total projected: ${clv_result['total_predicted_clv']:,.0f}")
   
   # Step 9: Recommender
   print("\n🎲 Training recommendation model...")
   rec_result = run_recommender_pipeline(transactions, articles)
   print(f"   Recommender: {'✅ trained' if rec_result['available'] else '⚠️ insufficient data'}")
   
   # Step 10: Save to DuckDB
   print("\n💾 Saving to DuckDB...")
   with DatabaseManager() as db:
       # Save customer segment data
       segments_df = seg_result["rfm_with_clusters"].copy()
       churn_merged = churn_df.set_index("customer_id")["churned"]
       if "clv_df" in clv_result and clv_result["available"]:
           clv_merged = clv_result["clv_df"]["clv"]
       else:
           clv_merged = None
       
       # Build customer_segments table data
       save_df = segments_df[["customer_id","recency","frequency","monetary","segment","cluster_id"]].copy()
       save_df.columns = ["customer_id","recency_days","frequency","monetary","cluster_label","cluster_id"]
       save_df["churn_probability"] = save_df["customer_id"].map(churn_merged.astype(float)).fillna(0)
       save_df["clv_12m"] = save_df["customer_id"].map(clv_merged) if clv_merged is not None else 0.0
       save_df["rfm_score"] = segments_df.get("rfm_string", "000")
       save_df["segmented_at"] = datetime.datetime.now()
       
       db.conn.execute("DELETE FROM customer_segments")
       db.conn.execute("INSERT INTO customer_segments SELECT * FROM save_df")
       print(f"   ✅ Saved {len(save_df):,} customer segments to DuckDB")
   
   # Step 11: Log to MLflow
   setup_mlflow()
   log_segmentation_run(seg_result["k_info"], seg_result["cluster_profiles"], len(rfm_df))
   if survival_result.get("available", True):
       log_survival_run(survival_result["cox"], survival_result["km_overall"], survival_result["n_customers"])
   if clv_result["available"]:
       log_clv_run(clv_result)
   print("   ✅ Experiments logged to MLflow (run: mlflow ui)")
   
   print("\n" + "=" * 60)
   print("✅ Customer Intelligence Pipeline Complete!")
   print("   View results: streamlit run pages/analytics_dashboard.py")
   print("   View MLflow:  mlflow ui")
   print("=" * 60)

if __name__ == "__main__":
   import argparse
   parser = argparse.ArgumentParser()
   parser.add_argument("--sample", type=int, default=50000, help="Number of customers to sample")
   args = parser.parse_args()
   run_analysis(sample_customers=args.sample)
```

**Verify:**
```bash
python -c "import run_customer_analysis; print('Master runner imports OK')"
```
✅ Pass = prints "Master runner imports OK" with no ImportError

---

## FINAL VERIFICATION — Full Stack Smoke Test

Run after ALL tasks are complete:

```bash
# 1. Check all modules import cleanly
python -c "
from database.db_manager import DatabaseManager
from data_sources.google_trends import get_trend_signal
from data_sources.hm_loader import check_hm_data_available
from analytics.trend_scorer import score_trend
from analytics.trend_forecaster import forecast_trend
from analytics.statistical_tests import test_trend_significance
from analytics.rfm import build_rfm_pipeline
from analytics.segmentation import run_segmentation
from analytics.churn_labeller import label_churn
from analytics.survival_analysis import run_survival_analysis
from analytics.clv import run_clv_analysis
from analytics.recommender import run_recommender_pipeline
from analytics.embeddings import embed_fashion_items
from analytics.causal_analysis import run_causal_analysis
from observability.mlflow_tracker import setup_mlflow
from observability.data_validators import validate_rfm_input
print('ALL MODULES IMPORT OK ✅')
"

# 2. Check DB initializes
python -c "from database.db_manager import DatabaseManager; db = DatabaseManager(); db.close(); print('DB OK ✅')"

# 3. Check original app still works
python -c "from backend.orchestrator import run_fashion_query; print('Orchestrator OK ✅')"
```

✅ All three commands print OK = full system ready.

---

## PROJECT STRUCTURE AFTER ALL TASKS

```
FashionGpt_Studio/
├── app.py                          (unchanged)
├── server.py                       (unchanged)
├── run_customer_analysis.py        (NEW — one-shot analysis runner)
├── requirements.txt                (updated)
├── backend/
│   ├── orchestrator.py             (modified — DB + TVI added)
│   ├── ai_analyzer.py              (unchanged)
│   └── llm_config.py               (unchanged)
├── scrapers/                       (unchanged)
├── data_sources/
│   ├── google_trends.py            (NEW)
│   └── hm_loader.py                (NEW)
├── analytics/
│   ├── trend_scorer.py             (NEW — TVI)
│   ├── trend_forecaster.py         (NEW — Prophet)
│   ├── statistical_tests.py        (NEW — Mann-Kendall)
│   ├── rfm.py                      (NEW)
│   ├── segmentation.py             (NEW — K-Means)
│   ├── churn_labeller.py           (NEW)
│   ├── survival_analysis.py        (NEW — KM + Cox PH)
│   ├── clv.py                      (NEW — BG/NBD)
│   ├── embeddings.py               (NEW — sentence transformers)
│   ├── recommender.py              (NEW — ALS)
│   └── causal_analysis.py          (NEW — PSM)
├── database/
│   ├── db_manager.py               (NEW)
│   └── schema.sql                  (NEW)
├── observability/
│   ├── mlflow_tracker.py           (NEW)
│   └── data_validators.py          (NEW)
├── pages/
│   └── analytics_dashboard.py      (NEW — Streamlit page)
├── data/
│   └── hm/                         (user places Kaggle CSVs here)
└── outputs/
    └── fashion_intelligence.duckdb (auto-created)
```
