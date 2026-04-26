# Fashion Intelligence Studio

> Real-time fashion trend analysis + customer intelligence — powered by Firecrawl, Groq LLM, DuckDB, and a full analytics pipeline.

---

## What it does

| Layer | What it does |
|---|---|
| **Trend Scraping** | Fetches live data from Pinterest, Zara, Uniqlo, and Vogue via Firecrawl |
| **AI Analysis** | Summarises trends and generates brand-specific insights using Groq LLM (text + vision) |
| **Image Intelligence** | Verifies and captions fashion images using Groq's Llama 4 Scout vision model |
| **Trend Velocity Index** | Scores each trend using Google Trends + social + retail presence |
| **Customer Intelligence** | RFM segmentation, churn labelling, CLV prediction, survival analysis, collaborative filtering |
| **Analytics Dashboard** | Live Streamlit page reading directly from DuckDB |
| **Experiment Tracking** | MLflow logs every analytics run with parameters and metrics |

---

## Architecture

```
app.py  ──────────────────►  server.py (Flask API)
(Streamlit UI)                    │
                                  ▼
                         backend/orchestrator.py
                         ├── scrapers/  (Pinterest, Zara, Uniqlo, Vogue)
                         ├── data_sources/google_trends.py
                         ├── analytics/trend_scorer.py  (TVI)
                         └── database/db_manager.py  (DuckDB)

run_customer_analysis.py  (standalone batch script)
├── data_sources/hm_loader.py
├── analytics/  (rfm → segmentation → churn → survival → clv → recommender)
├── database/db_manager.py
└── observability/  (mlflow_tracker, data_validators)

pages/analytics_dashboard.py  (Streamlit multi-page, reads DuckDB directly)
```

---

## Project structure

```
FashionGpt_Studio/
├── app.py                          # Streamlit frontend
├── server.py                       # Flask API backend
├── run_customer_analysis.py        # Batch customer intelligence pipeline
│
├── backend/
│   ├── orchestrator.py             # Scrape → analyse → score → persist
│   ├── ai_analyzer.py              # Groq LLM brand analysis
│   └── llm_config.py               # LLM model/prompt config
│
├── scrapers/
│   ├── pinterest_scraper.py
│   ├── zara_scraper.py
│   ├── uniqlo_scraper.py
│   ├── vogue_scraper.py
│   └── firecrawl_config.py         # Firecrawl API key + scrape options
│
├── data_sources/
│   ├── google_trends.py            # pytrends wrapper + momentum scorer
│   └── hm_loader.py                # H&M Kaggle dataset loader
│
├── analytics/
│   ├── trend_scorer.py             # Trend Velocity Index (TVI)
│   ├── trend_forecaster.py         # Prophet time-series forecasting
│   ├── statistical_tests.py        # Mann-Kendall + t-tests
│   ├── rfm.py                      # Recency / Frequency / Monetary
│   ├── segmentation.py             # K-Means clustering on RFM
│   ├── churn_labeller.py           # Implicit churn labelling
│   ├── survival_analysis.py        # Kaplan-Meier + Cox PH (lifelines)
│   ├── clv.py                      # BG/NBD + Gamma-Gamma CLV (lifetimes)
│   ├── embeddings.py               # Sentence-transformer item embeddings
│   ├── recommender.py              # Collaborative filtering (cornac MF)
│   └── causal_analysis.py          # Propensity score matching
│
├── database/
│   ├── schema.sql                  # DuckDB table definitions
│   └── db_manager.py               # DatabaseManager context-manager class
│
├── observability/
│   ├── mlflow_tracker.py           # MLflow experiment logging helpers
│   └── data_validators.py          # Pandera DataFrame schemas
│
├── pages/
│   └── analytics_dashboard.py      # Streamlit analytics page (reads DuckDB)
│
├── data/
│   └── hm/                         # H&M Kaggle CSVs (not committed)
│
├── outputs/                        # Generated reports (not committed)
├── requirements.txt
└── .env                            # API keys (not committed)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Windows / Python 3.13 note:** `implicit` and `scikit-survival` are replaced by `cornac` and `lifelines` respectively — both install without C++ build tools.

### 2. API keys

Create a `.env` file (or set environment variables):

```env
FIRECRAWL_API_KEY=fc-...
GROQ_API_KEY=gsk_...
```

`FIRECRAWL_API_KEY` can also be set directly in `scrapers/firecrawl_config.py`.

Groq is free — get a key at [console.groq.com](https://console.groq.com).  
Firecrawl — get a key at [firecrawl.dev](https://www.firecrawl.dev).

### 3. (Optional) H&M dataset

Required only for the customer intelligence pipeline. Download from Kaggle:

```
https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data
```

Place these three files in `data/hm/`:

```
data/hm/articles.csv
data/hm/customers.csv
data/hm/transactions_train.csv
```

---

## Running the app

### Live trend dashboard

```bash
# Terminal 1 — Flask API
python server.py

# Terminal 2 — Streamlit UI
python app.py
```

Open [http://localhost:8501](http://localhost:8501).

### Customer intelligence pipeline

Run once (or periodically) to process H&M data and populate DuckDB:

```bash
# Windows PowerShell
$env:PYTHONUTF8="1"; python -u run_customer_analysis.py

# Smaller sample for testing
$env:PYTHONUTF8="1"; python -u run_customer_analysis.py --sample 10000
```

Default sample: 50,000 customers (~5–6 min on a laptop).

### Analytics dashboard

```bash
streamlit run pages/analytics_dashboard.py
```

Or navigate to it from the Streamlit sidebar after launching `app.py` (multi-page app).

### MLflow experiment UI

```bash
mlflow ui
```

Open [http://localhost:5000](http://localhost:5000).

---

## Analytics modules

| Module | Algorithm | Output |
|---|---|---|
| `trend_scorer.py` | Weighted composite of Google / social / retail scores | Trend Velocity Index (0–100) + confidence label |
| `trend_forecaster.py` | Facebook Prophet | 30-day forecast + trend direction |
| `statistical_tests.py` | Mann-Kendall, Welch t-test | Trend significance p-values |
| `rfm.py` | Quantile scoring | Recency / Frequency / Monetary scores + 8 segment labels |
| `segmentation.py` | K-Means, silhouette optimisation | Optimal K, cluster profiles + names |
| `churn_labeller.py` | 90th-percentile gap threshold | Binary churn flag per customer |
| `survival_analysis.py` | Kaplan-Meier + Cox PH (`lifelines`) | Median survival, hazard ratios, concordance |
| `clv.py` | BG/NBD + Gamma-Gamma (`lifetimes`) | 12-month predicted CLV per customer |
| `embeddings.py` | `all-MiniLM-L6-v2` (sentence-transformers) | 384-dim item embeddings + cosine similarity |
| `recommender.py` | Matrix Factorisation (`cornac`) | Top-N item recommendations per user |
| `causal_analysis.py` | Propensity Score Matching (logistic regression) | Average Treatment Effect (ATE) |

---

## Database

DuckDB file: `outputs/fashion_intelligence.duckdb`

| Table | Contents |
|---|---|
| `trend_snapshots` | Raw scrape snapshots per query/source |
| `trend_scores` | Computed TVI scores per query |
| `fashion_items` | Individual scraped items |
| `google_trends_data` | pytrends time-series |
| `customer_segments` | RFM + cluster + churn + CLV per customer |
| `model_registry` | Logged model metadata |

---

## Environment notes

| Item | Value |
|---|---|
| Python | 3.13.5 |
| OS tested | Windows 10 (PowerShell) |
| `implicit` → | `cornac>=1.18.0` (no MSVC wheels for Python 3.13) |
| `scikit-survival` → | `lifelines` (ecos dependency requires MSVC) |
| MLflow backend | SQLite (`mlruns/mlflow.db`) |
