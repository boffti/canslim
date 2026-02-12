import os
from google.adk.agents import Agent
from google.adk.model import Model
from app.agents.tools import log_journal, check_market_status
from app.agents.prompts import WILSON_SYSTEM_PROMPT

import os
from google.adk.agents import Agent
from google.adk.model import Model
from app.agents.tools import log_journal, check_market_status
from app.agents.prompts import WILSON_SYSTEM_PROMPT

# Configure the Model for OpenRouter
# Using standard OpenAI compatibility mode for OpenRouter
openrouter_key = os.environ.get("OPENROUTER_API_KEY")

# Create a Model instance configured for OpenRouter
# Note: google-adk's Model class typically expects a specific client or model name.
# If ADK supports custom clients, we inject it here. 
# If ADK is strictly Gemini-only, we might need a workaround.
# Assuming ADK v2+ supports standard Model interface with custom base_url if using a compatible client.
# NOTE: The simplest way to make ADK work with OpenRouter is often to use the OpenAI client adapter 
# if ADK supports passing a client. If not, we use the `model_name` string format for LiteLLM if ADK uses LiteLLM under the hood.
# Based on common recent agent frameworks, we'll try configuring it as an OpenAI-compatible endpoint.

model = Model(
    model_name="openai/google/gemini-2.0-flash-001", # OpenRouter model ID
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1"
)

# Define the Orchestrator
wilson = Agent(
    name="Wilson",
    model=model,
    intro=WILSON_SYSTEM_PROMPT,
    tools=[log_journal, check_market_status]
)

