# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DeepDiver** is an autonomous AI trading system combining a CANSLIM Scanner Dashboard (Flask web UI) with the Wilson AI agent for 24/7 market analysis and trade execution. The system uses Alpaca and Finnhub for real-time market data and Supabase for cloud persistence.

**Key Components:**
- **Dashboard**: Flask web UI for human oversight and discretionary trading
- **Wilson Agent**: Autonomous AI trader using Google ADK + OpenRouter LLM
- **Market Data**: Alpaca and Finnhub API for real-time stock prices and technical data
- **Cloud Persistence**: Supabase for all data storage (scans, positions, alerts, journal)
- **Real-time Updates**: WebSocket subscriptions via Supabase Realtime
- **Scheduled Tasks**: APScheduler for automated market monitoring

## Development Commands

### Running the Application

```bash
# Quick start (recommended)
./run.sh

# Or manually
uv sync          # Install dependencies
uv run run.py    # Start Flask server

# Docker deployment
docker-compose up -d
```

The app runs on `http://localhost:8080` by default (configurable via `PORT` in `.env`).

### Package Management

This project uses **uv** for dependency management (not pip):

```bash
# Install/sync dependencies
uv sync

# Add a new dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Update all dependencies
uv lock --upgrade

# Update specific package
uv lock --upgrade-package package-name
```

Dependencies are defined in `pyproject.toml`, NOT `requirements.txt`.

### Verification

```bash
# Run health checks
./verify.sh
```

### Manual Testing

```bash
# Test Supabase connection
uv run python -c "from app.dashboard.utils import get_settings; print(get_settings())"

# Test Wilson agent
uv run python -c "from app.agents.wilson import wilson; print(wilson.run('test'))"

# Test market data fetch
uv run python -c "from app.agents.tools import fetch_market_data; print(fetch_market_data('AAPL,MSFT'))"

# Test scheduled tasks
uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"
```

## Configuration

Required environment variables in `.env`:

**Market Data APIs:**
- `ALPACA_API_KEY` - Alpaca API key for real-time market data and trading
- `ALPACA_SECRET_KEY` - Alpaca secret key for authentication
- `FINNHUB_API_KEY` - Finnhub API key for additional market data and fundamentals

**Supabase (Cloud Database):**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Service role key (backend operations)
- `SUPABASE_ANON_KEY` - Anonymous key (frontend WebSocket subscriptions)

**AI Agent (Wilson):**
- `OPENROUTER_API_KEY` - OpenRouter API key for LLM access
- `GEMINI_API_KEY` - (Optional) Direct Gemini API fallback

**App:**
- `PORT` - Server port (default: 8080)
- `FLASK_ENV` - Environment (development/production)

## Architecture

### Application Structure

**Flask Application Factory Pattern** (`app/__init__.py`):
- `create_app()` initializes Flask app with CORS
- Registers dashboard blueprint
- Initializes Supabase client
- Initializes and starts APScheduler
- Loads scheduled tasks from `app/tasks.py`

```
app/
├── __init__.py           # App factory (create_app)
├── extensions.py         # Shared resources (Supabase client, Scheduler)
├── tasks.py              # Scheduled jobs (morning briefing, market monitor)
├── agents/               # AI Agent Logic
│   ├── wilson.py         # Lead trader agent (Google ADK)
│   ├── tools.py          # Agent tools (9 tools)
│   └── prompts.py        # Wilson's system prompt
├── dashboard/            # Web UI Blueprint
│   ├── __init__.py       # Blueprint registration
│   ├── routes.py         # API endpoints and page routes
│   └── utils.py          # Data access layer (Supabase queries)
└── templates/            # Jinja2 HTML templates
    ├── index.html        # Main dashboard
    ├── calendar.html     # Trading calendar
    ├── calls.html        # Covered calls tracker
    ├── routine.html      # Daily routine viewer
    └── routine_form.html # Routine entry form
```

**Entry point**: `run.py` calls `create_app()` and runs the Flask development server.

**Legacy files**: `app/data/` directory is created for backwards compatibility but is no longer used for primary data storage.

### Data Flow

**Complete Data Pipeline:**

```
1. Alpaca/Finnhub APIs
   ↓ (fetch_market_data tool)
2. Wilson Agent analyzes data
   ↓ (write_scan_results tool)
3. Supabase tables (scans, scan_stocks)
   ↓ (WebSocket subscription)
4. Dashboard UI auto-updates
```

**Key Details:**
- Wilson fetches real-time data from Alpaca and Finnhub every morning at 8:30 AM ET
- Wilson analyzes stocks using CANSLIM criteria autonomously
- Results are written to Supabase `scans` and `scan_stocks` tables
- Dashboard subscribes to Supabase Realtime via WebSocket
- UI receives instant updates when new data is inserted
- No polling, no cache invalidation needed

**Position Sizing Logic** (in `dashboard/routes.py:api_data()`):
```python
risk_per_share = pivot - stop
shares = int(risk_per_trade / risk_per_share)
cost = shares * pivot
```

### AI Agent System

**Wilson Agent** (`app/agents/wilson.py`):
- Built with Google ADK (Agent Development Kit)
- Uses OpenRouter for LLM access (model: `openai/google/gemini-2.0-flash-001`)
- Autonomous decision-making (no user prompts required)
- Logs all actions to Supabase `journal` table

**Agent Tools** (9 tools in `app/agents/tools.py`):

1. **`log_journal(agent, category, content)`**
   - Logs events to Supabase `journal` table
   - Categories: Trade, Error, Summary, Signal, Thinking

2. **`check_market_status()`**
   - Returns OPEN/CLOSED based on US Eastern Time market hours
   - Uses pytz for timezone handling

3. **`fetch_market_data(tickers)`**
   - Fetches real-time price data from Alpaca and Finnhub
   - Returns JSON with price, volume, change %, high, low

4. **`write_scan_results(market_regime, stocks_json, metadata_json)`**
   - Writes CANSLIM scan results to Supabase
   - Inserts into `scans` table and `scan_stocks` table
   - Returns scan ID

5. **`get_current_positions()`**
   - Retrieves all open positions from Supabase
   - Returns JSON list of positions

6. **`get_watchlist()`**
   - Gets stocks currently being monitored
   - Returns JSON list from `watchlist` table

7. **`update_position(position_id, updates_json)`**
   - Updates a position (change stop, close, etc.)
   - Takes JSON string with fields to update

8. **`check_alerts()`**
   - Checks if any price alerts have triggered
   - Returns untriggered alerts from `alerts` table

9. **`add_to_watchlist(ticker, status, score)`**
   - Adds or updates a stock in the watchlist
   - Status: 'Watching', 'Long', or 'Short'
   - Score: Sentiment score 0-100

**OpenRouter Integration**:
```python
model = Model(
    model_name="openai/google/gemini-2.0-flash-001",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

wilson = Agent(
    name="Wilson",
    model=model,
    intro=WILSON_SYSTEM_PROMPT,
    tools=[...all 9 tools...]
)
```

**Invoking the Agent**:
```python
response = wilson.run("Your prompt here")
print(response.text)
```

**Scheduled Tasks** (`app/tasks.py`):

1. **`task_morning_briefing()`**
   - Runs: 8:30 AM ET (Mon-Fri)
   - Wilson performs CANSLIM scan
   - Fetches market data, analyzes stocks, writes results
   - Checks alerts and current positions

2. **`task_market_monitor()`**
   - Runs: Every 15 minutes during market hours (9 AM - 4 PM ET, Mon-Fri)
   - Wilson monitors open positions
   - Checks alerts, updates watchlist

### Data Persistence

**Supabase Tables** (10 tables):

1. **`scans`** - CANSLIM scan metadata
   - Fields: scan_time, market_regime, dist_days, buy_ok, account_balance, risk_per_trade, actionable_count, metadata

2. **`scan_stocks`** - Individual stock candidates from scans
   - Fields: scan_id (FK), ticker, pivot, stop, rs_rating, comp_rating, eps_rating, setup_type, notes, metadata

3. **`settings`** - App configuration (key-value store)
   - Keys: account_equity, risk_pct, max_positions

4. **`alerts`** - Price alerts
   - Fields: ticker, condition (above/below), price, triggered

5. **`earnings`** - Earnings calendar
   - Fields: ticker (PK), earnings_date

6. **`positions`** - Stock positions
   - Fields: ticker, account, trade_type, entry_date, entry_price, shares, cost_basis, stop_price, target_price, setup_type, status, close_date, close_price, pnl, notes

7. **`covered_calls`** - Covered call trades
   - Fields: ticker, sell_date, expiry, strike, contracts, premium_per_contract, premium_total, delta, stock_price_at_sell, status, close_date, close_price, pnl, notes

8. **`routines`** - Daily trading routines
   - Fields: date, routine_type (premarket/postclose), data (JSONB)

9. **`watchlist`** - Stocks being monitored
   - Fields: ticker (PK), status, sentiment_score, last_updated

10. **`journal`** - Agent activity logs
    - Fields: agent_name, category, content, created_at, meta

**Database Schema Setup**:
Run `docs/supabase-schema.sql` in Supabase SQL Editor to create all tables.

**Real-time Subscriptions**:
Enable Supabase Realtime for these tables in Supabase Dashboard → Database → Replication:
- `scans`
- `scan_stocks`
- `positions`
- `alerts`
- `journal`

Frontend subscribes via WebSocket using `SUPABASE_ANON_KEY`.

### Dashboard API Endpoints

**Scans:**
- `GET /api/data` - Latest scan with position sizing calculations
- `GET /api/refresh` - Force refresh (currently alias for /api/data)
- `GET /api/export?filter=` - Export CSV
- `GET /api/history` - List all historical scans
- `GET /api/history/<scan_id>` - Get specific scan

**Alerts:**
- `GET /api/alerts` - List all alerts
- `POST /api/alerts` - Add alert (ticker, condition, price)
- `DELETE /api/alerts/<id>` - Delete alert

**Earnings:**
- `GET /api/earnings` - Get earnings calendar
- `POST /api/earnings` - Set earnings date (ticker, date)

**Settings:**
- `GET /api/settings` - Get account settings
- `POST /api/settings` - Update settings (account_equity, risk_pct, max_positions)

**Covered Calls:**
- `GET /api/calls` - List trades + summary stats
- `POST /api/calls` - Add new trade
- `PATCH /api/calls/<id>` - Close trade (expired/called_away/bought_back)
- `DELETE /api/calls/<id>` - Delete trade

**Positions:**
- `GET /api/positions` - List positions + summary (open/closed count, total PnL)
- `POST /api/positions` - Add position
- `PATCH /api/positions/<id>` - Update/close position
- `DELETE /api/positions/<id>` - Delete position

**Routines:**
- `GET /routine` - Redirect to today's routine
- `GET /routine/<date>` - View routine for date
- `GET /api/routine/<date>` - Get routine JSON
- `POST /api/routine/<date>` - Save routine (premarket/postclose)

**Calendar:**
- `GET /calendar` - Current month calendar view
- `GET /calendar/<year>/<month>` - Specific month calendar

**System:**
- `GET /system/health` - Health check (200 OK)
- `GET /api/health` - API health check

## Key Implementation Details

### Input Validation

All POST/PATCH endpoints validate input:
- **Tickers**: max 10 chars, alphanumeric + `.` and `-`
- **Prices**: positive, reasonable maximums ($1M for alerts, $100k for positions)
- **Shares/contracts**: positive integers with limits (1M shares, 10k contracts)
- **Trade types**: must be 'long' or 'short'
- **Alert conditions**: must be 'above' or 'below'

Returns `400 Bad Request` for validation failures with descriptive error messages.

### Templates

All templates in `app/templates/`:
- **`index.html`** - Main dashboard with embedded CSS/JS
- **`calendar.html`** - Calendar view for routines
- **`calls.html`** - Covered calls tracker
- **`routine.html`** - Daily routine viewer
- **`routine_form.html`** - Routine entry form

**Frontend Stack**:
- Vanilla JavaScript (no frameworks)
- CSS Grid and Flexbox for layout
- Fetch API for HTTP requests
- Supabase JavaScript client for WebSocket subscriptions
- Dark theme UI (#1a1a2e background)

### Real-time Updates

Frontend connects to Supabase Realtime:
```javascript
const supabase = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase
  .channel('scans')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'scans' },
      payload => refreshData())
  .subscribe()
```

Green indicator in UI shows real-time connection status.

### Scheduled Task System

**APScheduler** configured in `app/extensions.py`:
- Initialized via `scheduler.init_app(app)`
- Started in `create_app()` after loading `app/tasks.py`
- Uses `@scheduler.task()` decorator with cron expressions

**Adding a New Task:**
1. Add function to `app/tasks.py`
2. Decorate with `@scheduler.task('cron', id='task_id', ...)`
3. Scheduler auto-loads on app startup
4. Check logs for "Scheduler started" message

**Cron syntax examples:**
```python
# Weekdays at 8:30 AM
@scheduler.task('cron', day_of_week='mon-fri', hour=8, minute=30)

# Every 15 minutes between 9 AM - 4 PM on weekdays
@scheduler.task('cron', day_of_week='mon-fri', hour='9-16', minute='*/15')
```

## Common Development Tasks

### Adding a New Dashboard Feature

1. Add route in `app/dashboard/routes.py`
2. Add data access function in `app/dashboard/utils.py` (Supabase query)
3. Create or modify template in `app/templates/`
4. Add API endpoint under `/api/*` if needed
5. Update frontend JavaScript for real-time subscriptions if needed

### Adding a New Agent Tool

1. Define function in `app/agents/tools.py`
2. Add `@tool` decorator from `google.adk.tools`
3. Add docstring describing parameters and return value
4. Register tool in `app/agents/wilson.py` tools list
5. Wilson will auto-discover and use the tool

Example:
```python
from google.adk.tools import tool

@tool
def my_new_tool(param: str) -> str:
    """Description of what this tool does.

    Args:
        param: Description of parameter

    Returns:
        Description of return value
    """
    # Implementation
    return "result"
```

### Adding a New Scheduled Task

1. Add function to `app/tasks.py`
2. Decorate with `@scheduler.task('cron', id='unique_id', ...)`
3. Import any tools/functions needed
4. Add error handling and logging
5. Scheduler starts automatically on app launch

### Modifying Position Sizing Logic

Edit `app/dashboard/routes.py`, `api_data()` function (lines 36-56):
```python
# Current formula
risk_per_share = pivot - stop
shares = int(risk_per_trade / risk_per_share)
cost = shares * pivot
```

### Adding a New Supabase Table

1. Add SQL in `docs/supabase-schema.sql`
2. Run SQL in Supabase SQL Editor
3. Add helper functions in `app/dashboard/utils.py`
4. Add API endpoints in `app/dashboard/routes.py`
5. Enable Realtime if needed (Supabase Dashboard → Database → Replication)

### Adding a New Dependency

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Or manually edit pyproject.toml, then:
uv sync
```

## External Dependencies

**Required System Tools:**
- **uv**: Package installer and resolver (replaces pip + venv)
  - Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Required APIs:**
- **Alpaca**: Real-time market data and trading API (free tier available with live data)
- **Finnhub**: Additional market data and fundamental analysis (free tier available)
- **Supabase**: Cloud database and real-time subscriptions (free tier available)
- **OpenRouter**: LLM access (supports multiple providers, pay-per-use)

**Python Packages** (see `pyproject.toml`):
- `flask>=3.1.2` - Web framework
- `flask-apscheduler>=1.13.1` - Task scheduling
- `flask-cors>=6.0.2` - CORS support
- `google-adk>=1.25.0` - Agent framework
- `supabase>=2.28.0` - Cloud database client
- `alpaca-py` - Alpaca trading and market data API
- `finnhub-python` - Finnhub market data API
- `openai>=2.20.0` - OpenRouter client compatibility
- `pandas-market-calendars>=5.3.0` - Market hours detection
- `python-dotenv>=1.2.1` - Environment variable loading
- `litellm>=1.81.10` - LLM proxy/router

## Docker Deployment

### Building and Running

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Configuration

**Dockerfile**:
- Base: `python:3.11-slim`
- Installs uv
- Runs `uv sync --frozen` for reproducible builds
- Exposes port 8080
- Runs `uv run run.py`

**docker-compose.yml**:
- Service name: `deepdiver`
- Mounts code for hot reload during development
- Loads `.env` file
- Health check via `/api/health` endpoint
- Restarts unless stopped

### Production Considerations

For production deployment:
1. Remove volume mounts from docker-compose.yml
2. Set `FLASK_ENV=production` in .env
3. Use a proper WSGI server (e.g., gunicorn):
   ```bash
   uv add gunicorn
   # Update CMD in Dockerfile:
   CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "run:app"]
   ```
4. Set up reverse proxy (nginx) with SSL
5. Use managed Supabase instance
6. Configure firewall rules

## Troubleshooting Development

**"Failed to fetch data" / "No scans found":**
- Check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Verify Supabase tables exist: run `docs/supabase-schema.sql`
- Test Supabase connection: `uv run python -c "from app.dashboard.utils import get_settings; print(get_settings())"`
- Wilson must generate first scan via `task_morning_briefing`
- Manual trigger: `uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"`
- Check Supabase dashboard → Tables → `scans` table for data

**Port already in use:**
- Change `PORT=8081` in `.env`
- Or kill process: `lsof -ti:8080 | xargs kill`

**Real-time not working:**
- Verify Realtime enabled in Supabase → Database → Replication
- Check browser console for WebSocket connection messages
- Verify `SUPABASE_ANON_KEY` is set correctly in `.env`
- Look for green dot indicator in top-right of dashboard
- Check Supabase logs for connection errors

**Scheduler not running:**
- Check console for "Scheduler started" message
- Verify tasks are defined in `app/tasks.py` with `@scheduler.task()` decorator
- Test manually: `uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"`
- Check APScheduler logs for errors

**Agent failing:**
- Verify `OPENROUTER_API_KEY` is set and valid
- Check Supabase connection: `SUPABASE_URL` and `SUPABASE_KEY`
- View logs in Supabase `journal` table
- Test agent manually: `uv run python -c "from app.agents.wilson import wilson; print(wilson.run('test'))"`
- Check OpenRouter dashboard for API quota/errors

**Alpaca/Finnhub errors:**
- Verify `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `FINNHUB_API_KEY` are set and valid
- Check API quota on Alpaca and Finnhub dashboards
- Alpaca free tier includes live market data (paper trading account)
- Finnhub free tier has rate limits (60 calls/minute)

**uv command not found:**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Or via pip: `pip install uv`
- Add to PATH: `export PATH="$HOME/.cargo/bin:$PATH"`

**Docker build fails:**
- Clear build cache: `docker-compose build --no-cache`
- Check disk space: `docker system df`
- Verify .env file exists and is valid

## Known Issues

**routes.py references non-existent function:**
- `api_export()` calls `get_cached_data()` which doesn't exist in utils.py
- Should be replaced with `get_latest_scan()`
- File: `app/dashboard/routes.py` line 70

**Legacy JSON files:**
- `app/data/` directory is created but not actively used
- Some utility functions reference it for backwards compatibility
- Can be safely removed in future cleanup
