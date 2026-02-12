"""
Curator Agent - AI Stock Universe Manager

Discovers, scores, and categorizes AI stocks from Russell 3000 index.
Promotes high-quality AI stocks to watchlist for Wilson to trade.
"""

import os
from google.adk.agents import Agent
from google.adk.models import LiteLlm

# Import Curator's tools
from app.agents.curator.tools import scan_stock_for_ai, update_trading_universe, get_trading_universe

# Import shared tools (reused from Wilson)
from app.agents.tools import log_journal, add_to_watchlist, fetch_market_data

# Import system prompt
from app.agents.curator.prompt import CURATOR_SYSTEM_PROMPT


# Configure LiteLlm for OpenRouter (same as Wilson)
openrouter_key = os.environ.get("OPENROUTER_API_KEY")

model = LiteLlm(
    model="openrouter/minimax/minimax-m2.5",
    api_key=openrouter_key,
    api_base="https://openrouter.ai/api/v1",
)

# Define Curator Agent
root_agent = curator = Agent(
    name="Curator",
    model=model,
    description="AI Stock Universe Manager for DeepDiver trading system",
    instruction=CURATOR_SYSTEM_PROMPT,
    tools=[
        # Curator-specific tools (3 new)
        scan_stock_for_ai,
        update_trading_universe,
        get_trading_universe,
        # Shared tools (3 reused from Wilson)
        log_journal,
        add_to_watchlist,
        fetch_market_data,
    ],
)
