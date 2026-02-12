from app.extensions import scheduler
from app.agents.wilson import wilson

@scheduler.task('cron', id='morning_briefing', day_of_week='mon-fri', hour=8, minute=30)
def task_morning_briefing():
    """Runs at 8:30 AM ET on Weekdays."""
    print("⏰ Trigger: Morning Briefing")
    
    prompt = "It is 8:30 AM. Perform the pre-market scan and log your outlook."
    
    # Run the Agent
    try:
        response = wilson.run(prompt)
        print(f"Wilson Finished: {response.text}")
    except Exception as e:
        print(f"Wilson Crashed: {e}")

@scheduler.task('cron', id='market_monitor', day_of_week='mon-fri', hour='9-16', minute='*/15')
def task_market_monitor():
    """Runs every 15 mins during market hours."""
    print("⏰ Trigger: Market Monitor")
    wilson.run("Check the watchlist for breakout signals.")
