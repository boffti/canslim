from app.extensions import scheduler
from app.agents.wilson import wilson
from app.agents.curator import curator
from datetime import datetime
import asyncio
from google.adk.runners import InMemoryRunner
from google.genai import types

@scheduler.task('cron', id='morning_briefing', day_of_week='mon-fri', hour=8, minute=30)
def task_morning_briefing():
    """Runs at 8:30 AM ET on Weekdays - Wilson performs CANSLIM scan."""
    print("⏰ Trigger: Morning Briefing / CANSLIM Scan")

    prompt = """It's 8:30 AM ET. Perform your morning CANSLIM scan:

    1. Check if market is open using check_market_status()
    2. Get watchlist stocks using get_watchlist() - these are AI stocks curated by Curator
    3. Fetch market data for watchlist stocks using fetch_market_data()
    4. Analyze each stock against CANSLIM criteria:
       - C: Current quarterly earnings (25%+ growth)
       - A: Annual earnings (25%+ growth over 3 years)
       - N: New highs, products, management
       - S: Supply & demand (volume, institutional buying)
       - L: Leader or laggard (RS rating > 80)
       - I: Institutional sponsorship
       - M: Market direction (confirm market regime)
    4. Determine market regime (Confirmed/Rally Attempt/Under Pressure/Correction)
    5. Write results using write_scan_results()
    6. Check alerts with check_alerts()
    7. Review current positions with get_current_positions()
    8. Log your analysis and recommendations to journal using log_journal()
    """

    async def run_wilson():
        # Create runner and session
        runner = InMemoryRunner(agent=wilson, app_name="deepdiver")
        session = await runner.session_service.create_session(
            app_name="deepdiver",
            user_id="system",
            session_id="morning_briefing"
        )

        # Run agent with prompt
        final_result = None
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_result = event.content.parts[0].text

        return final_result

    try:
        response = asyncio.run(run_wilson())
        print(f"✓ Morning scan completed")
        if response:
            print(f"Wilson's response: {response[:200]}...")
    except Exception as e:
        print(f"✗ Morning scan failed: {e}")
        # Log error to journal
        try:
            from app.agents.tools import log_journal
            log_journal("System", "Error", f"Morning scan failed: {e}")
        except:
            pass

@scheduler.task('cron', id='market_monitor', day_of_week='mon-fri', hour='9-16', minute='*/15')
def task_market_monitor():
    """Runs every 15 mins during market hours - Wilson monitors positions."""
    print("⏰ Trigger: Market Monitor")

    prompt = """Monitor the market and current positions:

    1. Check current positions using get_current_positions()
    2. Check if any alerts have triggered using check_alerts()
    3. Fetch latest prices for positions using fetch_market_data()
    4. If any positions need attention (hit stops, reached targets), log to journal
    5. Update watchlist if you see new opportunities
    """

    async def run_wilson():
        runner = InMemoryRunner(agent=wilson, app_name="deepdiver")
        session = await runner.session_service.create_session(
            app_name="deepdiver",
            user_id="system",
            session_id="market_monitor"
        )

        final_result = None
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_result = event.content.parts[0].text

        return final_result

    try:
        response = asyncio.run(run_wilson())
        print(f"✓ Market monitor completed: {response[:200] if response else 'No response'}...")
    except Exception as e:
        print(f"✗ Market monitor failed: {e}")


# ============================================================================
# CURATOR TASKS - AI Universe Management
# ============================================================================

@scheduler.task('cron', id='curator_daily_scan', day_of_week='mon-fri', hour=8, minute=0)
def task_curator_daily_scan():
    """Runs at 8:00 AM ET on Weekdays - Curator light scan of top AI stocks."""
    print("⏰ Trigger: Curator Daily Scan")

    prompt = """Daily AI Universe Check:

    1. Get top 30 AI stocks from trading_universe (score >= 80, is_active=True)
       Use: get_trading_universe('{"is_active": true, "min_score": 80, "limit": 30}')

    2. For each stock:
       - Fetch latest news (last 24 hours) via scan_stock_for_ai()
       - Check for AI keyword mentions

    3. Update scores:
       - If new AI developments mentioned: Increase score, update_trading_universe()
       - If AI mentions dropped or negative: Lower score

    4. Watchlist management:
       - If score >= 70 and not in watchlist: add_to_watchlist()
       - If score < 50 and in watchlist: log demotion (don't remove user-added)

    5. Log summary to journal:
       - How many stocks scanned
       - Any notable changes
       - Any promotions/demotions

    API Budget: ~15 calls - stay efficient!
    """

    async def run_curator():
        runner = InMemoryRunner(agent=curator, app_name="deepdiver")
        session = await runner.session_service.create_session(
            app_name="deepdiver",
            user_id="system",
            session_id="curator_daily"
        )

        final_result = None
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_result = event.content.parts[0].text

        return final_result

    try:
        response = asyncio.run(run_curator())
        print(f"✓ Daily scan completed")
        if response:
            print(f"Curator's response: {response[:200]}...")
    except Exception as e:
        print(f"✗ Daily scan failed: {e}")
        try:
            from app.agents.tools import log_journal
            log_journal("System", "Error", f"Curator daily scan failed: {e}")
        except:
            pass


@scheduler.task('cron', id='curator_weekly_scan', day_of_week='sat', hour=9, minute=0)
def task_curator_weekly_scan():
    """Runs Saturday 9:00 AM - Curator deep dive + Russell 3000 batch scan."""
    print("⏰ Trigger: Curator Weekly Deep Dive")

    # Determine which sector to focus on (4-week rotation)
    week_number = datetime.now().isocalendar()[1]
    sectors = ['ai_chip', 'ai_software', 'ai_cloud', 'ai_infrastructure']
    focus_sector = sectors[week_number % 4]
    batch_number = week_number % 28  # 28 weeks to scan all 3000 stocks

    prompt = f"""Weekly Deep Dive - {focus_sector.upper()} + Russell 3000 Batch {batch_number}:

PART 1: Sector Deep Dive
    1. Get all stocks in category '{focus_sector}':
       Use: get_trading_universe('{{"category": "{focus_sector}", "is_active": true}}')

    2. For each stock:
       - Fetch company profile and news (last 7 days) via scan_stock_for_ai()
       - Run 2-stage AI scoring (keyword + LLM validation if borderline)
       - Update trading_universe() with new scores/categories

    3. Watchlist management:
       - Promote stocks with score >= 70 to watchlist
       - Deactivate stocks with score < 30 (set is_active=False)

PART 2: Russell 3000 Progressive Scan
    1. Get batch #{batch_number} of unscanned/old stocks:
       - Get 107 stocks where last_scanned is NULL or > 7 days ago
       - Use: get_trading_universe('{{"limit": 107}}')

    2. For each stock:
       - Scan for AI involvement via scan_stock_for_ai()
       - If score > 0: Update trading_universe() with score and category
       - If score >= 70: add_to_watchlist()

    3. Log progress:
       - How many stocks scanned total
       - How many new AI stocks found
       - Current universe size by category

    API Budget: ~50-100 calls - this is the weekly deep work
    """

    async def run_curator():
        runner = InMemoryRunner(agent=curator, app_name="deepdiver")
        session = await runner.session_service.create_session(
            app_name="deepdiver",
            user_id="system",
            session_id=f"curator_weekly_{week_number}"
        )

        final_result = None
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_result = event.content.parts[0].text

        return final_result

    try:
        response = asyncio.run(run_curator())
        print(f"✓ Weekly scan completed - Sector: {focus_sector}, Batch: {batch_number}")
        if response:
            print(f"Curator's response: {response[:200]}...")
    except Exception as e:
        print(f"✗ Weekly scan failed: {e}")
        try:
            from app.agents.tools import log_journal
            log_journal("System", "Error", f"Curator weekly scan failed: {e}")
        except:
            pass


@scheduler.task('cron', id='curator_monthly_cleanup', day_of_week='sun', day='1', hour=10, minute=0)
def task_curator_monthly_cleanup():
    """Runs 1st Sunday 10:00 AM - Curator prunes stale stocks and generates report."""
    print("⏰ Trigger: Curator Monthly Cleanup")

    prompt = """Monthly Universe Maintenance:

    1. Find stale stocks (no recent AI mentions):
       - Get all active stocks: get_trading_universe('{"is_active": true}')
       - For each stock where last_mention > 60 days ago:
         * Fetch recent news (last 30 days) via scan_stock_for_ai()
         * If NO AI mentions: Set is_active=False, log deactivation reason
         * If still has AI mentions: Update last_mention timestamp

    2. Watchlist quality control:
       - Get current watchlist via tools
       - Remove stocks with score < 50 from watchlist
       - Keep user-added stocks (check notes field)

    3. Generate monthly report (log to journal):
       - Total universe size (active stocks)
       - Breakdown by category (ai_chip: X, ai_software: Y, etc.)
       - Top 20 highest-scoring stocks
       - Newly added vs removed stocks this month
       - Watchlist size and composition

    4. Identify trends:
       - Which AI sectors are growing/shrinking?
       - Any new AI themes emerging?
       - Recommendations for next month

    API Budget: ~50 calls - monthly maintenance work
    """

    async def run_curator():
        runner = InMemoryRunner(agent=curator, app_name="deepdiver")
        session = await runner.session_service.create_session(
            app_name="deepdiver",
            user_id="system",
            session_id="curator_monthly"
        )

        final_result = None
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_result = event.content.parts[0].text

        return final_result

    try:
        response = asyncio.run(run_curator())
        print(f"✓ Monthly cleanup completed")
        if response:
            print(f"Curator's response: {response[:200]}...")
    except Exception as e:
        print(f"✗ Monthly cleanup failed: {e}")
        try:
            from app.agents.tools import log_journal
            log_journal("System", "Error", f"Curator monthly cleanup failed: {e}")
        except:
            pass
