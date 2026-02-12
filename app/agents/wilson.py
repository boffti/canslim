import os
from google.adk.agents import Agent
from google.adk.models import LiteLlm
from app.agents.tools import (
    log_journal,
    check_market_status,
    fetch_market_data,
    write_scan_results,
    get_current_positions,
    get_watchlist,
    update_position,
    check_alerts,
    add_to_watchlist,
)
from app.agents.prompts import WILSON_SYSTEM_PROMPT

# Configure LiteLlm for OpenRouter
openrouter_key = os.environ.get("OPENROUTER_API_KEY")

# Create a LiteLlm instance configured for OpenRouter
# Use openrouter/ prefix with a valid free model
model = LiteLlm(
    model="openrouter/minimax/minimax-m2.5",
    api_key=openrouter_key,
    api_base="https://openrouter.ai/api/v1",
)

# Define the Orchestrator
wilson = Agent(
    name="Wilson",
    model=model,
    description="Lead trader agent for autonomous CANSLIM market analysis and trade execution",
    instruction=WILSON_SYSTEM_PROMPT,
    tools=[
        log_journal,
        check_market_status,
        fetch_market_data,
        write_scan_results,
        get_current_positions,
        get_watchlist,
        update_position,
        check_alerts,
        add_to_watchlist,
    ],
)
