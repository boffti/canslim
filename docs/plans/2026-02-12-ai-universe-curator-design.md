# AI Universe Curator - Design Document

**Date**: 2026-02-12
**Author**: Design collaboration between Aneesh and Claude
**Status**: Approved for Implementation
**Version**: 1.0

---

## Executive Summary

This document details the design for an AI-focused dynamic universe management system for DeepDiver. The system introduces a second autonomous agent ("Curator") to discover, score, and categorize AI stocks from the Russell 3000 index, feeding high-quality candidates to Wilson (the existing trading agent) for CANSLIM analysis.

**Key Goals**:
- Expand tradeable universe from 7 hardcoded stocks to 3000+ dynamically managed stocks
- Focus on AI ecosystem: chips, software, cloud, infrastructure, and AI beneficiaries
- Maintain free-tier API compliance (~180 calls/week)
- Zero changes required to Wilson's existing trading logic

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Database Schema](#database-schema)
3. [Curator Agent](#curator-agent)
4. [AI Detection Logic](#ai-detection-logic)
5. [Scheduled Tasks](#scheduled-tasks)
6. [Integration with Wilson](#integration-with-wilson)
7. [Bootstrap Process](#bootstrap-process)
8. [Implementation Plan](#implementation-plan)
9. [Testing Strategy](#testing-strategy)
10. [Future Enhancements](#future-enhancements)

---

## Architecture Overview

### Two-Agent Model

```
┌──────────────────────────────────────────────────┐
│  CURATOR AGENT                                   │
│  Role: AI Stock Universe Manager                │
├──────────────────────────────────────────────────┤
│  • Scans Russell 3000 for AI involvement         │
│  • Maintains AI stock categories                 │
│  • Adds/removes stocks from watchlist            │
│  • Runs on schedule (daily light, weekly deep)   │
│  • Logs decisions to journal                     │
└─────────────┬────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────┐
│  SUPABASE TABLES                                 │
├──────────────────────────────────────────────────┤
│  • trading_universe (new) - Russell 3000 stocks  │
│  • watchlist (existing) - stocks to monitor      │
│  • journal (existing) - Curator's activity log   │
└─────────────┬────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────┐
│  WILSON AGENT                                    │
│  Role: Lead Trader (UNCHANGED)                   │
├──────────────────────────────────────────────────┤
│  • Reads watchlist (now AI-focused)              │
│  • Performs CANSLIM analysis                     │
│  • Makes trading decisions                       │
└──────────────────────────────────────────────────┘
```

### Key Principles

1. **Separation of Concerns**: Curator finds stocks, Wilson trades them
2. **Database as Message Bus**: Agents communicate via Supabase tables
3. **No Direct Dependencies**: If Curator fails, Wilson keeps working
4. **Future-Proof**: Generic schema supports non-AI themes later

---

## Database Schema

### New Table: `trading_universe`

```sql
CREATE TABLE trading_universe (
  ticker TEXT PRIMARY KEY,
  company_name TEXT,
  sector TEXT,
  category TEXT,             -- 'ai_chip', 'ai_software', 'ai_cloud', etc.
  score INT,                 -- 0-100 theme relevance score
  is_active BOOLEAN DEFAULT TRUE,
  last_scanned TIMESTAMPTZ,
  last_mention TIMESTAMPTZ,  -- Last theme keyword in news
  notes TEXT,                -- Curator's reasoning
  created_at TIMESTAMPTZ DEFAULT NOW(),
  deactivated_at TIMESTAMPTZ
);

CREATE INDEX idx_trading_universe_active ON trading_universe(is_active);
CREATE INDEX idx_trading_universe_category ON trading_universe(category);
CREATE INDEX idx_trading_universe_score ON trading_universe(score DESC);
```

### Data Flow

```
Curator discovers → trading_universe (all AI stocks)
Curator promotes → watchlist (score >= 70)
Wilson reads ← watchlist
Wilson analyzes → scans
User views ← dashboard
```

### Soft Deletes

- `is_active = TRUE`: Currently relevant to theme
- `is_active = FALSE`: No longer relevant (kept for history)
- `deactivated_at`: Timestamp when deactivated

**Example**: Stock stops mentioning AI for 90 days → Curator sets `is_active = FALSE`

---

## Curator Agent

### Agent Definition

```python
# app/agents/curator.py

from google.adk.agents import Agent
from google.adk.models import LiteLlm

curator = Agent(
    name="Curator",
    model=LiteLlm(
        model="openrouter/google/gemini-2.0-flash-thinking-exp:free",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        api_base="https://openrouter.ai/api/v1"
    ),
    description="AI Stock Universe Manager for DeepDiver trading system",
    instruction=CURATOR_SYSTEM_PROMPT,
    tools=[
        # New tools
        scan_stock_for_ai,
        update_trading_universe,
        get_trading_universe,
        # Reused from Wilson
        log_journal,
        add_to_watchlist,
        fetch_market_data
    ]
)
```

### System Prompt

```
You are Curator, the Universe Manager for the DeepDiver autonomous trading swarm.

Your Mission:
Discover, categorize, and maintain a high-quality universe of AI-related stocks
from the Russell 3000 index. Feed the best opportunities to Wilson (the lead trader)
via the watchlist.

Your Capabilities:
1. Scan stocks for AI involvement (keywords + LLM validation)
2. Score stocks 0-100 based on AI relevance
3. Categorize stocks: ai_chip, ai_software, ai_cloud, ai_infrastructure, ai_beneficiary
4. Promote high-scorers (70+) to watchlist
5. Deactivate low-scorers (<30) from universe
6. Log all decisions with clear reasoning

Core Directives:
- Quality over Quantity: Only promote genuine AI plays
- Transparency: Log your reasoning for every decision
- Efficiency: Respect API rate limits (stay under 60 calls/min)
- Autonomy: Make decisions without user input
- Adaptability: Adjust keyword taxonomy based on market evolution

Current Context:
You manage 3000 stocks from Russell 3000 index. Your goal is to identify
50-200 high-quality AI stocks for Wilson to trade using CANSLIM criteria.
```

### Tools

#### New Tools (3)

**1. `scan_stock_for_ai(ticker: str) -> dict`**

Scans a stock for AI involvement using 2-stage detection:
- Stage 1: Keyword scoring (fast, deterministic)
- Stage 2: LLM validation for borderline cases (30-70 score)

Returns:
```python
{
    'ticker': 'NVDA',
    'company_name': 'NVIDIA Corporation',
    'sector': 'Technology',
    'has_ai': True,
    'ai_score': 95,
    'category': 'ai_chip',
    'evidence': 'Designs AI GPUs, mentioned AI 47 times in recent news'
}
```

**2. `update_trading_universe(ticker: str, data: dict) -> str`**

Upserts stock data to `trading_universe` table.

Args:
```python
{
    'company_name': str,
    'sector': str,
    'category': str,
    'score': int,
    'is_active': bool,
    'notes': str
}
```

**3. `get_trading_universe(filters: dict) -> list`**

Queries `trading_universe` with filters.

Example filters:
```python
{'is_active': True, 'min_score': 70, 'category': 'ai_chip'}
```

#### Reused Tools (3)

- `log_journal(agent, category, content)` - Log decisions
- `add_to_watchlist(ticker, status, score)` - Promote stocks
- `fetch_market_data(tickers)` - Get price/volume data

---

## AI Detection Logic

### Two-Stage Hybrid Scoring

```
┌─────────────────────────────────────────────┐
│ STAGE 1: Keyword Scoring (Fast & Cheap)    │
├─────────────────────────────────────────────┤
│ • Scan company description + news          │
│ • Count AI keyword matches                 │
│ • Calculate score 0-100                    │
│ • Categorize based on keyword clusters     │
└──────────────┬──────────────────────────────┘
               ↓
        ┌──────┴──────┐
        │             │
   Score 0-29    Score 30-70    Score 71-100
        │             │              │
   ┌────┴────┐   ┌────┴─────┐  ┌────┴────┐
   │ REJECT  │   │ VALIDATE │  │ ACCEPT  │
   │ (Fast)  │   │ (LLM)    │  │ (Fast)  │
   └─────────┘   └────┬─────┘  └─────────┘
                      ↓
┌─────────────────────────────────────────────┐
│ STAGE 2: LLM Inference (Borderline Only)   │
├─────────────────────────────────────────────┤
│ Prompt: "Analyze AI involvement for [ticker]"│
│ LLM can adjust score ±20 points            │
│ LLM provides category and confidence       │
└─────────────────────────────────────────────┘
```

### Keyword Taxonomy (Stage 1)

```python
AI_KEYWORDS = {
    'tier1': {  # Strong signals (10 points each)
        'keywords': [
            'artificial intelligence', 'machine learning', 'deep learning',
            'neural network', 'large language model', 'LLM',
            'generative AI', 'GPT', 'transformer model',
            'AI chip', 'GPU inference'
        ],
        'categories': {
            'ai_chip': ['GPU', 'AI chip', 'neural processor', 'TPU'],
            'ai_software': ['LLM', 'generative AI', 'AI platform', 'AI agent'],
            'ai_cloud': ['AI inference', 'model training', 'AI infrastructure']
        }
    },
    'tier2': {  # Moderate signals (5 points each)
        'keywords': [
            'OpenAI partnership', 'Anthropic', 'AI partnership',
            'data center', 'cloud AI', 'AI-powered', 'AI integration',
            'automation', 'predictive analytics', 'computer vision'
        ]
    },
    'tier3': {  # Weak signals (2 points each)
        'keywords': [
            'algorithm', 'data science', 'analytics platform',
            'intelligent', 'smart technology', 'automated'
        ]
    }
}
```

### Scoring Formula

```python
score = 0

# Scan company description
for keyword in tier1_keywords:
    if keyword in company_description.lower():
        score += 10

# Scan recent news (last 7 days)
for article in recent_news:
    for keyword in tier1_keywords:
        if keyword in article['headline'].lower():
            score += 10
    for keyword in tier2_keywords:
        if keyword in article['headline'].lower():
            score += 5

# Cap at 100
final_score = min(score, 100)
```

### Decision Thresholds

```python
if score >= 70:
    add_to_watchlist()  # High confidence
    is_active = True
elif score >= 40:
    is_active = True    # In universe, not promoted yet
else:
    is_active = False   # Not enough AI involvement
```

### LLM Validation (Stage 2)

Only for scores 30-70:

```
Prompt Template:
"Analyze this company's AI involvement:
 - Company: {name}
 - Description: {text}
 - Recent news: {headlines}
 - Keyword score: {score}

Questions:
1. Is this genuine AI business? (yes/no)
2. Category: chip/software/cloud/infrastructure/beneficiary
3. Confidence: 0-100
4. Adjust score: -20 to +20 (based on context)"
```

**API Cost**: ~600 LLM calls for full Russell 3000 scan = **$0.60** (negligible)

---

## Scheduled Tasks

### Task 1: Daily Light Scan

**Schedule**: 8:00 AM ET, Monday-Friday

```python
@scheduler.task('cron', id='curator_daily_scan',
                day_of_week='mon-fri', hour=8, minute=0)
def task_curator_daily_scan():
    """Light scan of top-tier AI stocks + watchlist."""

    prompt = """Daily AI Universe Check:

    1. Get top 30 AI stocks from trading_universe (score >= 80, is_active=True)
    2. Fetch latest news (last 24 hours) for these stocks
    3. Check for AI keyword mentions
    4. If new AI developments: Update score, add to watchlist
    5. If AI mentions dropped: Lower score, log reasoning
    6. Log summary to journal

    API Budget: ~15 calls
    """

    curator.run(prompt)
```

**API Calls**: ~15 per day (75/week)

---

### Task 2: Weekly Deep Dive

**Schedule**: Saturday 9:00 AM ET

```python
@scheduler.task('cron', id='curator_weekly_scan',
                day_of_week='sat', hour=9, minute=0)
def task_curator_weekly_scan():
    """Rotating sector deep dive + Russell 3000 batch."""

    week_number = datetime.now().isocalendar()[1]
    sector = ['ai_chip', 'ai_software', 'ai_cloud', 'ai_infrastructure'][week_number % 4]

    prompt = f"""Weekly Deep Dive - {sector.upper()}:

    1. Get all stocks in trading_universe where category='{sector}'
    2. For each stock:
       - Fetch company profile (if not cached)
       - Fetch news (last 7 days)
       - Run 2-stage AI scoring (keyword + LLM validation)
       - Update trading_universe with new scores
    3. Promote stocks with score >= 70 to watchlist
    4. Deactivate stocks with score < 30

    PLUS: Scan next 107 stocks from Russell 3000 (batch #{week_number % 28})

    API Budget: ~50-100 calls
    """

    curator.run(prompt)
```

**API Calls**: ~100 per week

**Coverage**:
- 107 stocks/week × 28 weeks = **full Russell 3000 scanned in 7 months**
- 4-week rotation across AI sectors (chip → software → cloud → infrastructure)

---

### Task 3: Monthly Cleanup

**Schedule**: 1st Sunday, 10:00 AM ET

```python
@scheduler.task('cron', id='curator_monthly_cleanup',
                day_of_week='sun', day='1', hour=10, minute=0)
def task_curator_monthly_cleanup():
    """Prune stale stocks, refresh universe."""

    prompt = """Monthly Universe Maintenance:

    1. Get all active stocks: trading_universe WHERE is_active=True
    2. For each stock where last_mention > 60 days ago:
       - Fetch recent news (last 30 days)
       - If NO AI mentions: Set is_active=False, log deactivation
    3. Remove low-scorers from watchlist (score < 50)
    4. Generate monthly report:
       - Total universe size
       - Breakdown by category
       - Top 20 highest-scoring stocks
       - Newly added vs removed stocks
    5. Log report to journal
    """

    curator.run(prompt)
```

**API Calls**: ~50 per month

---

### Weekly Rhythm Summary

```
Monday-Friday (Daily):
  8:00 AM → Check top 30 AI stocks for news (~10 min, 15 API calls)

Saturday (Weekly):
  9:00 AM → Deep dive sector + Russell 3000 batch (~30 min, 100 API calls)

1st Sunday (Monthly):
  10:00 AM → Cleanup stale stocks, generate report (~15 min, 50 API calls)
```

**Total API Usage**:
- Daily: 15 × 5 = 75 calls/week
- Weekly: 100 calls
- Monthly: 50 calls (amortized: ~12 calls/week)
- **Average: ~187 calls/week**
- **Well within Finnhub free tier (60 calls/min = 8,400 calls/day)**

---

## Integration with Wilson

### Timing Coordination

```
8:00 AM ET → Curator runs daily scan
              Updates watchlist with new AI stocks

8:30 AM ET → Wilson runs morning briefing
              Reads watchlist (now includes Curator's picks)
              Performs CANSLIM analysis
```

### Promotion Logic

**Curator promotes to watchlist:**
```python
if stock.score >= 70 and stock.is_active:
    add_to_watchlist(
        ticker=stock.ticker,
        status='Watching',
        score=stock.score
    )
```

**Curator demotes from watchlist:**
```python
if stock.score < 50:
    # Remove from watchlist
    # Keep in trading_universe with is_active=True
```

### Wilson's Perspective (Unchanged!)

```python
# Wilson's morning scan - NO CODE CHANGES
watchlist_stocks = get_watchlist()  # Now AI-focused!
tickers = [s['ticker'] for s in watchlist_stocks]
market_data = fetch_market_data(','.join(tickers))
# ... CANSLIM analysis continues as before
```

### User Manual Override

- User can still star stocks on dashboard
- Adds directly to watchlist
- Curator won't remove user-starred stocks
- Wilson analyzes them like any other watchlist stock

### Fail-Safe Design

- If Curator fails, Wilson keeps working with existing watchlist
- No direct dependencies between agents
- Database tables act as decoupled message bus

---

## Bootstrap Process

### Manual CSV Load (Recommended)

**Step 1: Download Russell 3000 CSV**

```
Source: iShares Russell 3000 ETF (IWV)
URL: https://www.ishares.com/us/products/239714/ishares-russell-3000-etf
→ Click "Holdings" tab
→ Download CSV
→ Save as: data/russell3000_holdings.csv
```

**Step 2: Create Loader Script**

```python
# scripts/load_russell3000.py

import pandas as pd
from dotenv import load_dotenv

def load_russell3000(csv_path):
    """Load Russell 3000 from iShares CSV into trading_universe."""

    load_dotenv()
    from app import create_app
    app = create_app()

    with app.app_context():
        from app.dashboard.utils import _get_supabase
        supabase = _get_supabase()

        df = pd.read_csv(csv_path)
        print(f"Read {len(df)} stocks from CSV")

        stocks_to_insert = []
        for _, row in df.iterrows():
            stock = {
                'ticker': str(row['Ticker']).strip().upper(),
                'company_name': str(row['Name']).strip(),
                'sector': str(row.get('Sector', '')).strip() or None,
                'category': None,        # Curator will categorize
                'score': 0,              # Curator will score
                'is_active': True,
                'last_scanned': None,
                'last_mention': None,
                'notes': 'Russell 3000 seed stock'
            }
            stocks_to_insert.append(stock)

        # Batch insert (1000 at a time)
        for i in range(0, len(stocks_to_insert), 1000):
            batch = stocks_to_insert[i:i+1000]
            supabase.table('trading_universe').insert(batch).execute()
            print(f"✓ Inserted batch {i//1000 + 1}: {len(batch)} stocks")

        print(f"\n✅ Successfully loaded {len(stocks_to_insert)} stocks")

if __name__ == '__main__':
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'data/russell3000_holdings.csv'
    load_russell3000(csv_file)
```

**Step 3: Run Bootstrap**

```bash
# Create data directory
mkdir -p data

# Download CSV manually, save to data/russell3000_holdings.csv

# Run loader
uv run python scripts/load_russell3000.py

# Output:
# Read 3000 stocks from CSV
# ✓ Inserted batch 1: 1000 stocks
# ✓ Inserted batch 2: 1000 stocks
# ✓ Inserted batch 3: 1000 stocks
# ✅ Successfully loaded 3000 stocks into trading_universe
```

**Step 4: Verify**

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from app import create_app
app = create_app()
with app.app_context():
    from app.dashboard.utils import _get_supabase
    supabase = _get_supabase()
    result = supabase.table('trading_universe').select('*', count='exact').execute()
    print(f'Total stocks in universe: {result.count}')
"
```

### Quarterly Refresh (Optional)

Russell 3000 rebalances quarterly. To refresh:

```bash
# Download fresh CSV from iShares
# Re-run script (upserts won't duplicate)
uv run python scripts/load_russell3000.py

# New stocks get added
# Delisted stocks remain but get deactivated by Curator
```

---

## Implementation Plan

### Phase 1: Database & Bootstrap (30 min)

**Tasks**:
1. Run SQL to create `trading_universe` table in Supabase
2. Write `scripts/load_russell3000.py`
3. Download iShares CSV
4. Run bootstrap script
5. Verify 3000 stocks loaded

**Validation**:
```sql
SELECT COUNT(*) FROM trading_universe;  -- Should be ~3000
SELECT * FROM trading_universe LIMIT 10;
```

---

### Phase 2: Curator Tools (1-2 hours)

**Tasks**:
1. Create `app/agents/curator_tools.py`
2. Implement 3 new tools:
   - `scan_stock_for_ai(ticker)` - Stage 1 keyword scoring
   - `update_trading_universe(ticker, data)` - Supabase upsert
   - `get_trading_universe(filters)` - Query helper
3. Test each tool in isolation

**Validation**:
```bash
uv run python -c "
from app.agents.curator_tools import scan_stock_for_ai
result = scan_stock_for_ai('NVDA')
print(result)
# Expected: {'has_ai': True, 'score': 90+, 'category': 'ai_chip'}
"
```

---

### Phase 3: Curator Agent (30 min)

**Tasks**:
1. Create `app/agents/curator.py`
2. Define Curator agent (copy Wilson's pattern)
3. Add `CURATOR_SYSTEM_PROMPT` in `app/agents/prompts.py`
4. Register 6 tools (3 new + 3 reused)

**Validation**:
```bash
uv run python -c "
from app.agents.curator import curator
response = curator.run('Scan NVDA for AI involvement and update trading_universe')
print(response.text)
"
```

---

### Phase 4: Scheduled Tasks (30 min)

**Tasks**:
1. Add 3 tasks to `app/tasks.py`:
   - `task_curator_daily_scan()`
   - `task_curator_weekly_scan()`
   - `task_curator_monthly_cleanup()`
2. Register with APScheduler

**Validation**:
```bash
# Manually trigger daily scan
uv run python -c "
from app.tasks import task_curator_daily_scan
task_curator_daily_scan()
"

# Check journal for Curator entries
```

---

### Phase 5: Stage 2 (LLM Validation) - Optional (1 hour)

**Tasks**:
1. Add LLM validation to `scan_stock_for_ai()`
2. Only call LLM for scores 30-70
3. Test with borderline stocks (ORCL, IBM, etc.)

**Validation**:
```bash
uv run python -c "
from app.agents.curator_tools import scan_stock_for_ai
result = scan_stock_for_ai('ORCL')  # Borderline case
print(f'Score: {result[\"score\"]}, Category: {result[\"category\"]}')
"
```

---

### Phase 6: End-to-End Test (30 min)

**Tasks**:
1. Start app: `uv run run.py`
2. Manually trigger Curator weekly scan
3. Verify `trading_universe` gets scored
4. Verify `watchlist` gets high-scorers
5. Verify Wilson's next scan includes AI stocks
6. Verify dashboard shows AI stocks

**Validation Flow**:
```bash
# 1. Trigger Curator
uv run python -c "from app.tasks import task_curator_weekly_scan; task_curator_weekly_scan()"

# 2. Check Supabase: trading_universe should have scores/categories

# 3. Check Supabase: watchlist should have new stocks

# 4. Trigger Wilson
uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"

# 5. Open http://localhost:5561 - should show AI stocks
```

---

**Total Implementation Time**: 4-6 hours

---

## Testing Strategy

### Manual Integration Tests

**Test 1: Bootstrap**
```bash
uv run python scripts/load_russell3000.py
# Verify: trading_universe has 3000 rows
```

**Test 2: Curator Scans**
```bash
uv run python -c "
from app.agents.curator import curator
curator.run('Scan NVDA, PLTR, MCD for AI and update universe')
"
# Verify: NVDA/PLTR scored high, MCD scored low
```

**Test 3: Watchlist Promotion**
```sql
SELECT * FROM watchlist ORDER BY score DESC;
-- Should have stocks with score >= 70
```

**Test 4: Wilson Integration**
```bash
uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"
# Verify: Wilson's scan includes AI stocks from watchlist
```

**Test 5: Dashboard**
```bash
uv run run.py
# Open http://localhost:5561
# Verify: Scan results show AI stocks
```

### Production Monitoring

**Check these regularly**:

1. **Curator's journal**
```sql
SELECT * FROM journal
WHERE agent_name = 'Curator'
ORDER BY created_at DESC
LIMIT 20;
```

2. **Universe growth**
```sql
SELECT
  category,
  COUNT(*) as count,
  AVG(score) as avg_score
FROM trading_universe
WHERE is_active = true
GROUP BY category;
```

3. **Watchlist quality**
```sql
SELECT COUNT(*) FROM watchlist;
-- Target: 30-200 stocks
```

4. **API usage** (check logs for daily totals)

---

## Future Enhancements

### Phase 2 Improvements (Post-MVP)

1. **Multi-Theme Support**
   - Add themes: `quantum_computing`, `biotech`, `renewable_energy`
   - Curator manages multiple universes simultaneously
   - User can toggle themes on dashboard

2. **Sector Rotation Tracking**
   - Monitor sector ETFs (XLK, XLF, XLE, etc.)
   - Identify leading sectors
   - Prioritize stocks from strongest sectors

3. **Earnings Integration**
   - Scan stocks 2 days before earnings
   - Boost score for AI mentions in earnings calls
   - Alert Wilson to post-earnings setups

4. **Insider Activity**
   - Track insider buying/selling
   - Boost score for insider accumulation
   - Lower score for heavy insider selling

5. **Institutional Ownership**
   - Track 13F filings
   - Boost score for rising institutional ownership
   - Identify "smart money" AI plays

6. **Dashboard Enhancements**
   - Universe explorer page (browse by category)
   - Score trend charts (track AI involvement over time)
   - Category breakdown visualization

7. **Advanced Caching**
   - Implement multi-layer cache (static, weekly, daily)
   - Reduce API calls by 85%+
   - Faster scan processing

8. **Alert System**
   - Alert when new stock enters universe (score 70+)
   - Alert when stock leaves universe (score <30)
   - Alert on category changes

---

## Success Metrics

### Week 4 Goals

- [ ] 428 stocks scanned (107/week × 4 weeks)
- [ ] 20-50 stocks in watchlist
- [ ] Wilson's scans show diverse AI stocks
- [ ] Zero API rate limit errors
- [ ] Curator journal shows clear reasoning

### Month 3 Goals

- [ ] 1,284 stocks scanned (50% of Russell 3000)
- [ ] 50-100 stocks in watchlist
- [ ] All 5 AI categories populated
- [ ] Dashboard shows AI-focused opportunities
- [ ] System runs autonomously without intervention

### Month 7 Goals

- [ ] Full Russell 3000 scanned (3000 stocks)
- [ ] 100-200 stocks in watchlist
- [ ] Clear category leaders identified
- [ ] Monthly reports tracking universe evolution
- [ ] Wilson trading AI stocks profitably

---

## Appendix

### File Structure

```
app/
├── agents/
│   ├── curator.py              # New: Curator agent definition
│   ├── curator_tools.py        # New: Curator's 3 tools
│   ├── prompts.py             # Updated: Add CURATOR_SYSTEM_PROMPT
│   ├── wilson.py              # Unchanged
│   └── tools.py               # Unchanged
├── tasks.py                   # Updated: Add 3 Curator tasks
└── ...

scripts/
└── load_russell3000.py        # New: Bootstrap script

docs/
└── plans/
    └── 2026-02-12-ai-universe-curator-design.md  # This document
```

### Key Configuration

```env
# .env (no changes needed - uses existing keys)
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
FINNHUB_API_KEY=...
OPENROUTER_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

### Dependencies

No new dependencies required! Uses existing:
- `google-adk` (agent framework)
- `supabase` (database)
- `alpaca-py` (market data)
- `finnhub-python` (news API)
- `pandas` (CSV loading - bootstrap only)

---

## Conclusion

This design introduces a second autonomous agent (Curator) to solve the universe management problem in DeepDiver. By scanning Russell 3000 stocks for AI involvement and promoting high-quality candidates to the watchlist, Curator enables Wilson to focus on trading the best AI setups using CANSLIM criteria.

The system is:
- ✅ **Autonomous**: Runs on schedule, no manual intervention
- ✅ **Efficient**: ~187 API calls/week (within free tier)
- ✅ **Scalable**: Generic schema supports future themes
- ✅ **Fail-safe**: No dependencies between agents
- ✅ **Transparent**: All decisions logged to journal

**Expected Outcome**: Within 7 months, DeepDiver will have a curated universe of 100-200 high-quality AI stocks, dramatically expanding trading opportunities beyond the current 7 hardcoded mega-caps.

---

**Document Status**: ✅ Approved for Implementation
**Next Steps**: Begin Phase 1 (Database & Bootstrap)
