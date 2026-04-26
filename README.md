# Retail Trend Intelligence Platform

Built a real-time trend momentum detection system for fashion retail, aggregating Google Trends signals and social media imagery to classify product categories as rising, stable, or falling — applicable to trend-driven inventory and assortment planning at retailers.

The system computes a directional momentum score for any fashion query, surfaces regionally segmented demand signals across 200+ countries, and ranks visual references by a composite Relevance Trend Score — giving buyers and planners a single interface to move from search to decision.

---

## Business applications

- **Trend desk (Nike, Adidas):** Monitor week-over-week momentum on silhouettes, colorways, and collaboration categories. Flag rising signals before they peak so product teams can accelerate sampling or marketing spend.
- **Assortment planning (Zara, H&M):** Use rising/stable/falling classification to adjust open-to-buy allocations per category each buying cycle — reduce exposure on falling trends, deepen buys on rising ones.
- **Seasonal buying (Nordstrom, Bloomingdale's):** Compare regional demand heatmaps to identify where a trend is gaining traction earliest, informing which markets get early-season depth versus a wait-and-see position.
- **Wholesale & brand sales (PVH, Tapestry):** Equip sales teams with objective trend velocity data to present to retail accounts, replacing anecdotal pitch decks with quantified demand signals.
- **E-commerce merchandising (ASOS, Revolve):** Feed momentum scores into on-site ranking logic to surface rising-trend products higher in search and category pages without waiting for sales data to accumulate.

---

## What this project currently includes

### Core capabilities

- Live Google Trends analysis for a user-generated fashion query
- Trend momentum scoring with directional classification (rising / stable / falling)
- Packed bubble chart for related trend terms (monochrome, size by score)
- Regional interest visualization (interactive globe + word cloud)
- Pinterest image scraping, deduplication, and relevance verification
- Groq LLM dashboard copy generation (cached per search phrase, refreshed on demand)
- Fashion Relevance Trend Score for ranking images before display
- Local SQLite caching for trend data and image metadata
- Signal validation backtest against Pinterest Predicts 2024–2026 labeled dataset

### Tech stack

- Frontend: Streamlit, Plotly, Matplotlib, WordCloud
- Data: pandas, pytrends, SQLite
- Scraping: Selenium (Pinterest)
- AI: Groq (text + vision)

---

## Why these design choices

- Streamlit for rapid iteration:
  The app is analytics-first and interactive. Streamlit keeps UI and data code in one place, reducing overhead.

- pytrends as primary signal source:
  Google Trends provides normalized public interest data that is easy to compare over time and across regions.

- SQLite cache (`outputs/trend_cache.db`):
  Avoids repeated pytrends/scraping calls for the same query and timeframe, improving responsiveness and reducing rate-limit pressure.

- Groq for both text and vision:
  Single provider simplifies configuration and avoids mixed-provider failure modes.

- Pinterest + LLM verification:
  Pinterest retrieval is high recall; vision verification improves precision for trend relevance. Images that fail download or are marked irrelevant by the vision model are excluded before display.

- Dashboard copy cached in session state:
  `generate_dashboard_copy` is called once per unique search phrase and refresh cycle. Subsequent filter changes that don't trigger a refresh reuse the cached copy, avoiding redundant LLM calls.

---

## Architecture and flow

1. User selects filters in Streamlit UI (`app.py`)
2. App builds a search phrase from filter values
3. App checks trend cache (`db.py`)
4. If cache miss:
   - Fetch Google Trends time series
   - Fetch Google Trends regional interest
   - Fetch related queries and build term list (case-insensitive deduplication)
   - Save all to SQLite
5. App computes momentum metrics
6. App generates editorial copy from Groq, cached in session state until next refresh
7. App loads or scrapes Pinterest images (`scrapers/pinterest_scraper.py`)
8. App verifies/captions images with Groq vision — failed or irrelevant images are dropped
9. App scores and ranks images by Fashion Relevance Trend Score
10. App renders charts, bubbles, map/word cloud, and image grid

---

## Metrics: exact calculation logic

### 1) Interest Over Time

Source: Google Trends `interest_over_time()`

- Scale is Google-normalized 0-100 for the selected timeframe
- The chart plots this series directly
- No additional scaling is applied in app logic

### 2) Trend Terms Bubble Score

Source: Google Trends `related_queries()` top + rising entries

- Terms are collected from the first available bucket for the query
- Duplicates removed case-insensitively (e.g. "Denim Jacket" and "denim jacket" deduplicate to one entry)
- Display limit is 10

Score handling:

- If values are numeric: use those numeric values
- If some are missing: fill missing with the median numeric value
- If all are non-numeric (for example breakout-style labels):
  fallback score by rank with
  `score_i = max(10, (N - i) * 10)` for sorted index `i`

Bubble sizing pipeline:

- Normalize score:
  `norm = (score - min_score) / max(max_score - min_score, 1.0)`
- Radius used for packing and rendering:
  `r = 0.26 + norm^0.65 * 0.34`
- Packed layout:
  iterative collision resolution + center gravity for compact clustering

Color encoding:

- Monochrome blue hue
- Higher score => lighter blue (higher lightness)

### 3) Momentum Score

Implemented in `data_sources/google_trends.py::compute_trend_momentum`.

Given a single trend series:

- `recent_avg`:
  mean of last 8 points (or full mean if fewer than 8 points)

- `historical_avg`:
  - if length >= 52: mean of points `[-52:-8]`
  - else if length > 8: mean of points `[:-8]`
  - else: mean of full series

- Raw momentum:
  `raw = (recent_avg - historical_avg) / (historical_avg + 1e-9)`

- Clipped momentum:
  `momentum = clip(raw, -1.0, 1.0)`

Direction thresholds:

- `rising` if momentum > 0.1
- `falling` if momentum < -0.1
- `stable` otherwise

Dashboard also shows:

- recent interest average (8-week)
- historical baseline
- delta = `recent_avg - historical_avg`

### 4) Geographic Interest

Source: Google Trends `interest_by_region(resolution="COUNTRY")`

- Uses country-level trend values (0-100)
- Globe map colors by interest value
- Word cloud uses the same values as frequencies
  (larger word = higher interest)

### 5) Image Verification

For displayed images:

- `verified_count = sum(image.verified == True)`
- Caption shown as:
  - `X images · Y verified by Groq Vision` if any verified
  - otherwise `X trend-aligned images from Pinterest`

Verification path:

- URL upgraded to higher Pinterest resolution where possible
- Image downloaded; any network/HTTP error drops the image entirely
- Groq vision returns strict JSON `{ "relevant": bool, "caption": str }`
- If `relevant: false` or any exception occurs, image is excluded from the grid

### 6) Fashion Relevance Trend Score (Image Ranking)

Implemented in `backend/fashion_scorer.py`. Each Pinterest image is scored 0–100 and ranked before display.

#### Sub-scores

| Sub-score | Source | Default (no LLM) |
|---|---|---|
| `trend_match` | Hybrid: LLM vision + rule-based term match | Rule-only |
| `style_match` | LLM aesthetic/style alignment | 60 |
| `freshness` | Rule: weighted avg of matched trend-term strengths | 45 |
| `quality` | LLM visual clarity and framing | 60 |

#### Trend-term normalization

Raw Google Trends term scores are normalized to 0–100 within the current result set before scoring:

```
norm_i = (raw_i - min) / max(max - min, 1.0) * 100
```

#### Rule-based trend match

Checks image caption/description for each trend term and averages normalized scores of matched terms. Returns 42 if no terms match, 45 if no text available.

#### LLM vision scoring (when Groq vision is configured)

The image is sent to the vision model with the search phrase, trend terms, and their strength values. The model returns:

```json
{
  "relevant": true,
  "trend_match": 0-100,
  "style_match": 0-100,
  "quality": 0-100,
  "matched_terms": ["term1", "term2"],
  "reason": "max 15 words"
}
```

- If `relevant: false`: `quality` and `style_match` are capped at 35 (image kept but penalized)
- `matched_terms` from the LLM feed the `freshness` calculation
- On any LLM failure, rule-based fallback values are used

#### Hybrid trend_match blend

```
combined_trend = 0.6 * llm_trend + 0.4 * rule_trend   (vision available)
combined_trend = rule_trend                             (vision unavailable)
```

#### Final fashion score formula

```
fashion_score = 0.45 * combined_trend
              + 0.25 * style_match
              + 0.20 * freshness
              + 0.10 * quality
```

Result is clamped to [0, 100] and rounded to one decimal place.

#### Ranking and display

- Images sorted descending by `fashion_score`; top 6 kept for display
- Each image shows its `fashion_score` and `score_reason` (LLM rationale or rule-based fallback)
- Scores cached in SQLite and reused on subsequent loads for the same query

### 7) AI-generated Editorial Fields

Generated by `generate_dashboard_copy()` in `backend/ai_analyzer.py`:

- `headline`
- `summary`
- `microcopy`
- `normalized_phrase`

Caching: the result is stored in `st.session_state` keyed by `search_phrase + refresh_nonce`. A new LLM call is only made when the search phrase changes or the user presses **Refresh Trends**.

If LLM fails/unavailable, deterministic fallback text is generated from filters + terms.

---

## Signal validation

The momentum scorer was backtested against Pinterest Predicts 2024–2026 — an independently labeled dataset of fashion trend predictions with confirmed/denied ground truth labels.

**Methodology:** For each query, the full Google Trends time series was pulled and `compute_trend_momentum` was evaluated at every week of the predicted year using only data available up to that point (no lookahead). The first week the scorer crossed the rising threshold (momentum > 0.1) was recorded. Lead time was measured from that date to the actual peak interest week in the raw series.

**Results (21 evaluable queries):**

| Metric | Value |
|---|---|
| Precision | 0.69 |
| Recall | 0.56 |
| F1 | 0.62 |
| Mean lead time | 19.4 weeks |
| Median lead time | 12.9 weeks |
| Flagged before peak | 13 / 13 rising queries |

The scorer correctly identified 9 of 16 confirmed rising trends and flagged none of them after their peak — all rising signals fired ahead of the actual interest peak. 11 of 32 queries returned no Google Trends data (rate-limiting or query too niche) and were excluded.

Results are surfaced in the app under the **📊 Signal Validation** tab.

To regenerate:

```bash
python -m backtest.run_backtest
```

---

## Current project structure

```text
FashionGpt_Studio/
├── app.py                          # Streamlit dashboard (Trend Explorer + Signal Validation tabs)
├── db.py                           # SQLite cache helpers
├── ui_components.py                # UI component library
├── requirements.txt
├── .env.example
├── pinterest_predicts_fashion_labeled.csv   # Ground truth labels for backtest
│
├── backend/
│   ├── ai_analyzer.py              # LLM copy generation + image verification
│   ├── fashion_scorer.py           # Fashion Relevance Trend Score
│   └── llm_config.py               # Groq configuration and call wrappers
│
├── data_sources/
│   └── google_trends.py            # pytrends fetchers + momentum computation
│
├── scrapers/
│   └── pinterest_scraper.py        # Selenium Pinterest scraper
│
├── backtest/
│   ├── fetch_trends.py             # Batch-fetch historical Trends series
│   ├── sliding_window_scorer.py    # Weekly rolling momentum evaluation
│   ├── compute_metrics.py          # Confusion matrix, precision/recall, lead times
│   ├── visualize.py                # Spaghetti chart + lead time bar chart
│   ├── run_backtest.py             # Orchestrator — runs all steps in order
│   └── data/                       # raw/ and scored/ CSVs per query
│
├── backtest/results/               # metrics.csv, summary.txt, PNG charts
│
└── outputs/                        # cache DB + temporary scrape outputs
```

---

## Setup

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment

Copy `.env.example` to `.env` and set:

```env
GROQ_API_KEY=your-groq-api-key-here
```

Optional overrides:

```env
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
```

### 3) Run app

```bash
streamlit run app.py
```

---

## Operational notes

- **Refresh Trends** button clears both trend and image cache tables and triggers a fresh LLM copy generation
- Dashboard copy is cached per search phrase — changing filters without refreshing reuses the existing copy
- pytrends can rate-limit or return sparse values for niche queries
- Selenium scraping quality depends on Pinterest DOM/network behavior
- If Groq is unavailable, trend analytics still run; AI copy/vision gracefully degrade to deterministic fallbacks

---

## Roadmap ideas

- Persist historical snapshots for query-level trend comparisons over sessions
- Add test coverage for momentum and bubble-score preprocessing
