# DeepDiver - Autonomous AI Trading System

An autonomous AI trading system combining a CANSLIM Scanner Dashboard (Flask web UI) with the **Wilson AI agent** for 24/7 market analysis and trade execution. The system uses real-time market data from Alpaca and Finnhub, cloud persistence via Supabase, and autonomous decision-making powered by Google ADK and OpenRouter LLM.

![DeepDiver Dashboard](docs/screenshot-placeholder.png)

## Overview

**DeepDiver** is not just a dashboard—it's an autonomous trading system where the Wilson AI agent performs market analysis, generates CANSLIM scans, monitors positions, and makes trading decisions independently. The dashboard provides human oversight and discretionary trading capabilities.

### Key Components

- 🤖 **Wilson AI Agent**: Autonomous trader using Google ADK + OpenRouter LLM
- 📊 **CANSLIM Scanner**: Real-time stock analysis based on CANSLIM methodology
- 📈 **Market Data**: Live data from Alpaca and Finnhub APIs
- ☁️ **Cloud Persistence**: Supabase for all data storage with real-time WebSocket updates
- ⏰ **Scheduled Tasks**: APScheduler for automated morning briefings and market monitoring
- 🎨 **Web Dashboard**: Flask-based UI for human oversight and manual trading

## Features

### 🤖 AI Agent Capabilities

- **Autonomous Market Analysis**: Wilson performs CANSLIM scans every morning at 8:30 AM ET
- **Position Monitoring**: Checks open positions every 15 minutes during market hours
- **Alert Management**: Monitors price alerts and triggers notifications
- **Trade Journaling**: Logs all decisions and actions to Supabase
- **9 Specialized Tools**: Market data fetching, position management, watchlist updates, and more

### 📊 Dashboard Features

- **Real-time Updates**: WebSocket subscriptions for instant data refresh
- **Position Sizing Calculator**: Automatic share calculation based on risk parameters
- **Historical Scans**: Browse past CANSLIM scan results
- **Trade Journal**: Track stock positions and covered calls with P&L
- **Price Alerts**: Set and monitor price alerts
- **Earnings Calendar**: Track upcoming earnings dates
- **Daily Routines**: Pre-market and post-close trading checklists
- **Dark Mode UI**: Professional interface optimized for extended use

### 📈 Trading Tools

- **Market Regime Tracking**: Confirmed, Rally Attempt, Under Pressure, Correction
- **Risk Management**: Configure account size, risk per trade, max positions
- **CSV Export**: Export scan results for further analysis
- **Live Filtering**: Search and filter stocks in real-time
- **Color-Coded Signals**: Visual indicators for buy/sell signals, RS ratings

## Tech Stack

- **Backend**: Python 3.12+ with Flask (application factory pattern)
- **Frontend**: Vanilla JavaScript with Supabase Realtime client
- **AI Agent**: Google ADK (Agent Development Kit) + OpenRouter LLM
- **Market Data**: Alpaca API (real-time quotes) + Finnhub API (fundamentals)
- **Database**: Supabase (PostgreSQL with real-time subscriptions)
- **Task Scheduler**: APScheduler for automated market monitoring
- **Package Manager**: uv (modern Python package installer)

## Prerequisites

1. **Python 3.12+**
2. **uv package manager** - [Install uv](https://github.com/astral-sh/uv)
3. **API Keys** (free tiers available):
   - Alpaca API (real-time market data)
   - Finnhub API (market fundamentals)
   - Supabase account (cloud database)
   - OpenRouter API (LLM access)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/deepdiver.git
cd deepdiver
```

### 2. Install uv Package Manager

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and set your API keys:

```env
# --- Market Data APIs ---
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here

# --- Supabase (Cloud Database) ---
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_service_role_key_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# --- AI Agent (Wilson) ---
OPENROUTER_API_KEY=your_openrouter_api_key_here
# GEMINI_API_KEY=your_gemini_api_key_here (Optional fallback)

# --- App Config ---
FLASK_ENV=development
PORT=8080
```

### 4. Set Up Supabase Database

1. Create a free Supabase account at [supabase.com](https://supabase.com)
2. Create a new project
3. Copy your project URL and keys to `.env`
4. Run the schema setup:
   - Open Supabase SQL Editor
   - Copy contents of `docs/supabase-schema.sql`
   - Execute the SQL to create all tables
5. Enable Realtime:
   - Go to Database → Replication
   - Enable replication for: `scans`, `scan_stocks`, `positions`, `alerts`, `journal`

### 5. Install Dependencies and Run

```bash
# Quick start (recommended)
chmod +x run.sh
./run.sh

# Or manually
uv sync          # Install dependencies
uv run run.py    # Start Flask server
```

### 6. Access the Dashboard

Open your browser to:
```
http://localhost:8080
```

## Usage

### First Run

On first launch, Wilson will:
1. Check market status
2. Wait for the morning briefing (8:30 AM ET on weekdays)
3. Perform CANSLIM scan and populate the dashboard
4. Monitor positions every 15 minutes during market hours

You can manually trigger a scan:
```bash
uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"
```

### Dashboard Navigation

- **Home**: Main CANSLIM scanner dashboard
- **Calendar**: View and log daily trading routines
- **Calls**: Track covered call positions
- **History**: Browse historical scan results
- **Settings**: Configure account equity, risk %, max positions

### Wilson AI Agent

Wilson operates autonomously with 9 specialized tools:

1. **log_journal**: Logs all decisions and actions
2. **check_market_status**: Determines if market is open/closed
3. **fetch_market_data**: Gets real-time price data from Alpaca/Finnhub
4. **write_scan_results**: Saves CANSLIM scan results to Supabase
5. **get_current_positions**: Retrieves open positions
6. **get_watchlist**: Gets monitored stocks
7. **update_position**: Updates position stops, targets, or closes trades
8. **check_alerts**: Monitors price alerts
9. **add_to_watchlist**: Adds stocks to monitoring list

View Wilson's activity in the Supabase `journal` table.

### Scheduled Tasks

- **Morning Briefing**: 8:30 AM ET (Mon-Fri) - CANSLIM scan
- **Market Monitor**: Every 15 min during market hours (9 AM - 4 PM ET, Mon-Fri)

## Project Structure

```
deepdiver/
├── app/
│   ├── __init__.py           # Flask application factory
│   ├── extensions.py         # Supabase client, APScheduler
│   ├── tasks.py              # Scheduled jobs (morning briefing, market monitor)
│   ├── agents/               # AI Agent Logic
│   │   ├── wilson.py         # Wilson AI agent (Google ADK)
│   │   ├── tools.py          # 9 agent tools
│   │   └── prompts.py        # Wilson's system prompt
│   ├── dashboard/            # Web UI Blueprint
│   │   ├── __init__.py       # Blueprint registration
│   │   ├── routes.py         # API endpoints and page routes
│   │   └── utils.py          # Data access layer (Supabase queries)
│   └── templates/            # Jinja2 HTML templates
│       ├── index.html        # Main dashboard
│       ├── calendar.html     # Trading calendar
│       ├── calls.html        # Covered calls tracker
│       ├── routine.html      # Daily routine viewer
│       └── routine_form.html # Routine entry form
├── docs/
│   ├── supabase-schema.sql   # Database schema
│   └── ...                   # Additional documentation
├── run.py                    # Application entry point
├── run.sh                    # Launch script with env validation
├── pyproject.toml            # Python dependencies (uv format)
├── .env.example              # Example environment variables
├── Dockerfile                # Docker container config
├── docker-compose.yml        # Docker Compose setup
└── README.md                 # This file
```

## Configuration

### Account Settings

Configure via the web UI or directly in Supabase `settings` table:

- **account_equity**: Total account value (default: $100,000)
- **risk_pct**: Risk per trade as decimal (default: 0.01 = 1%)
- **max_positions**: Maximum concurrent positions (default: 6)

### Position Sizing Formula

```python
risk_per_trade = account_equity * risk_pct
risk_per_share = pivot - stop
shares = int(risk_per_trade / risk_per_share)
cost = shares * pivot
```

## API Endpoints

### Scans
- `GET /api/data` - Latest scan with position sizing
- `GET /api/refresh` - Force refresh
- `GET /api/export?filter=` - Export CSV
- `GET /api/history` - List all scans
- `GET /api/history/<scan_id>` - Get specific scan

### Positions
- `GET /api/positions` - List positions + summary
- `POST /api/positions` - Add position
- `PATCH /api/positions/<id>` - Update/close position
- `DELETE /api/positions/<id>` - Delete position

### Alerts
- `GET /api/alerts` - List alerts
- `POST /api/alerts` - Add alert
- `DELETE /api/alerts/<id>` - Delete alert

### Settings
- `GET /api/settings` - Get account settings
- `POST /api/settings` - Update settings

See `app/dashboard/routes.py` for complete API documentation.

## Docker Deployment

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

For production deployment, see `CLAUDE.md` for detailed instructions.

## Development

### Adding a New Agent Tool

1. Define function in `app/agents/tools.py`
2. Add `@tool` decorator from `google.adk.tools`
3. Register in `app/agents/wilson.py` tools list

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
    return "result"
```

### Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --dev package-name
```

### Running Tests

```bash
uv run pytest
```

## Troubleshooting

### "Failed to fetch data" / "No scans found"

- Verify Supabase credentials in `.env`
- Run database schema: `docs/supabase-schema.sql`
- Manually trigger scan: `uv run python -c "from app.tasks import task_morning_briefing; task_morning_briefing()"`
- Check Supabase dashboard → Tables → `scans` for data

### Real-time Updates Not Working

- Enable Realtime in Supabase → Database → Replication
- Verify `SUPABASE_ANON_KEY` is set correctly
- Check browser console for WebSocket errors
- Look for green dot indicator in dashboard top-right

### Agent Not Running

- Verify `OPENROUTER_API_KEY` is valid
- Check Supabase `journal` table for Wilson's logs
- Test manually: `uv run python -c "from app.agents.wilson import wilson; print(wilson.run('test'))"`

### Port Already in Use

```bash
# Change port in .env
PORT=8081

# Or kill existing process
lsof -ti:8080 | xargs kill
```

For more troubleshooting, see `CLAUDE.md`.

## Documentation

- **CLAUDE.md**: Comprehensive developer guide for AI assistants
- **docs/supabase-schema.sql**: Database schema
- **docs/QUICKSTART.md**: Quick start guide
- **docs/TESTING.md**: Testing documentation

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Built with AI-powered development tools.

---

**Disclaimer**: This tool is for educational and research purposes. Always do your own due diligence before making investment decisions. Past performance does not guarantee future results. Autonomous trading carries significant risk.
