from google.adk.tools import tool
from app.extensions import supabase
import requests
import json
from datetime import datetime

@tool
def log_journal(agent: str, category: str, content: str) -> str:
    """Logs an event to the cloud database (Supabase).
    
    Args:
        agent: Name of the agent (e.g., 'Wilson', 'Scanner').
        category: Type of log (Trade, Error, Summary, Signal, Thinking).
        content: The message to log.
    """
    if not supabase:
        print(f"[Fallback Log] {agent} | {category}: {content}")
        return "Supabase not connected. Logged to stdout."
        
    try:
        data = {
            "agent_name": agent, 
            "category": category, 
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("journal").insert(data).execute()
        return "Logged successfully."
    except Exception as e:
        print(f"[Log Error] {e}")
        return f"Log failed: {e}"

@tool
def check_market_status() -> str:
    """Checks if the US stock market is currently open.
    
    Returns:
        A string indicating if the market is OPEN or CLOSED, and the time.
    """
    # Simple check based on time (9:30 AM - 4:00 PM ET)
    # For a real implementation, use pandas_market_calendars
    from datetime import datetime
    import pytz
    
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    
    is_weekday = now.weekday() < 5
    is_market_hours = (
        (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and
        (now.hour < 16)
    )
    
    status = "OPEN" if is_weekday and is_market_hours else "CLOSED"
    return f"Market is {status} (Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')})"
