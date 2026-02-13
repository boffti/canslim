"""
Curator Agent Tools for AI Stock Universe Management

Provides tools for discovering, scoring, and categorizing AI stocks
from the Russell 3000 index.
"""

from google.adk.tools import FunctionTool
from app.extensions import supabase
import requests
import json
import os
from datetime import datetime, timedelta


# AI Keyword Taxonomy
AI_KEYWORDS = {
    'tier1': {  # Strong AI signals (10 points each)
        'keywords': [
            'artificial intelligence', 'machine learning', 'deep learning',
            'neural network', 'large language model', 'llm', 'generative ai',
            'gpt', 'transformer model', 'ai chip', 'gpu inference', 'nvidia gpu',
            'neural processor', 'tpu', 'ai accelerator'
        ],
        'categories': {
            'ai_chip': ['gpu', 'ai chip', 'neural processor', 'tpu', 'ai accelerator', 'nvidia', 'cuda'],
            'ai_software': ['llm', 'generative ai', 'ai platform', 'ai agent', 'chatgpt', 'gpt'],
            'ai_cloud': ['ai inference', 'model training', 'ai infrastructure', 'gpu cloud']
        }
    },
    'tier2': {  # Moderate signals (5 points each)
        'keywords': [
            'openai partnership', 'anthropic', 'ai partnership',
            'data center', 'cloud ai', 'ai-powered', 'ai integration',
            'automation', 'predictive analytics', 'computer vision',
            'natural language processing', 'nlp', 'ai model'
        ]
    },
    'tier3': {  # Weak signals (2 points each) - optional, often too noisy
        'keywords': [
            'algorithm', 'data science', 'analytics platform',
            'intelligent', 'smart technology', 'automated'
        ]
    }
}


def _fetch_edgar_ai_mentions(ticker: str, company_name: str) -> dict:
    """Fetch AI-related mentions from SEC EDGAR 10-K filings (free, no API key).

    Uses EDGAR full-text search to find 'artificial intelligence' in recent
    10-K filings. Snippets reveal whether AI is mentioned in R&D, product,
    or operations context.

    Args:
        ticker: Stock symbol (used as fallback label only)
        company_name: Company name for EDGAR entity search

    Returns:
        dict with:
            count (int): Number of filing hits
            snippets (list[str]): Up to 5 text snippets from filings
            error (str): Error message if request failed (optional)
    """
    import urllib.parse

    base_url = "https://efts.sec.gov/LATEST/search-index"
    params = {
        "q": '"artificial intelligence" OR "machine learning" OR "generative AI"',
        "forms": "10-K",
        "dateRange": "custom",
        "startdt": "2023-01-01",
        "enddt": datetime.now().strftime("%Y-%m-%d"),
        "entity": company_name,
    }

    try:
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "DeepDiver/1.0 research@example.com"}
        )
        response.raise_for_status()
        data = response.json()

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {}).get("value", 0)

        snippets = []
        for hit in hits[:5]:
            highlights = hit.get("highlight", {}).get("file_contents", [])
            if not isinstance(highlights, list) or not highlights:
                continue
            snippet = highlights[0].replace("<em>", "").replace("</em>", "")
            snippets.append(snippet[:300])

        return {
            "count": total,
            "snippets": snippets,
        }

    except requests.exceptions.HTTPError as e:
        return {
            "count": 0,
            "snippets": [],
            "error": f"HTTP {e.response.status_code if e.response else 'unknown'}: {str(e)}",
        }
    except Exception as e:
        return {
            "count": 0,
            "snippets": [],
            "error": str(e),
        }


def _scan_stock_for_ai(ticker: str) -> str:
    """Scans a stock for AI involvement using 2-stage detection.

    Stage 1: Keyword scoring (deterministic)
    Stage 2: LLM validation for borderline scores (30-70)

    Args:
        ticker: Stock symbol to scan

    Returns:
        JSON string with scan results:
        {
            'ticker': str,
            'company_name': str,
            'sector': str,
            'has_ai': bool,
            'score': int (0-100),
            'category': str,
            'evidence': str
        }
    """
    ticker = ticker.upper().strip()

    try:
        # Stage 1: Keyword Scoring
        result = _keyword_scoring(ticker)

        # Stage 2: LLM Validation (only for borderline scores)
        if 30 <= result['score'] <= 70:
            edgar_data = _fetch_edgar_ai_mentions(ticker, result.get('company_name', ticker))
            llm_result = _llm_validation(ticker, result, edgar_data)
            result['score'] = llm_result['adjusted_score']
            result['category'] = llm_result['category']
            result['evidence'] += f" | LLM: {llm_result['reasoning']}"

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            'ticker': ticker,
            'error': str(e),
            'has_ai': False,
            'score': 0
        })


def _keyword_scoring(ticker: str) -> dict:
    """Stage 1: Keyword-based scoring using Finnhub company profile + news."""

    finnhub_api_key = os.getenv('FINNHUB_API_KEY')
    if not finnhub_api_key:
        raise Exception("FINNHUB_API_KEY not set")

    score = 0
    evidence = []
    category = None
    company_name = ticker
    sector = None

    # Fetch company profile
    try:
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={finnhub_api_key}"
        profile_response = requests.get(profile_url, timeout=10)
        profile_data = profile_response.json()

        if profile_data:
            company_name = profile_data.get('name', ticker)
            sector = profile_data.get('finnhubIndustry', None)
            description = profile_data.get('description', '').lower()

            # Score company description
            for keyword in AI_KEYWORDS['tier1']['keywords']:
                if keyword in description:
                    score += 10
                    evidence.append(f"Description: '{keyword}'")

            for keyword in AI_KEYWORDS['tier2']['keywords']:
                if keyword in description:
                    score += 5
                    evidence.append(f"Description: '{keyword}'")

    except Exception as e:
        print(f"Warning: Could not fetch profile for {ticker}: {e}")

    # Fetch recent news (last 7 days)
    try:
        date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')
        news_url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={date_from}&to={date_to}&token={finnhub_api_key}"
        news_response = requests.get(news_url, timeout=10)
        news_data = news_response.json()

        # Limit to 10 most recent articles
        for article in news_data[:10]:
            headline = article.get('headline', '').lower()
            summary = article.get('summary', '').lower()
            text = f"{headline} {summary}"

            for keyword in AI_KEYWORDS['tier1']['keywords']:
                if keyword in text:
                    score += 10
                    evidence.append(f"News: '{keyword}' in headline")
                    break  # Count once per article

            for keyword in AI_KEYWORDS['tier2']['keywords']:
                if keyword in text:
                    score += 5
                    break

    except Exception as e:
        print(f"Warning: Could not fetch news for {ticker}: {e}")

    # Cap score at 100
    score = min(score, 100)

    # Categorize based on keywords found
    if score > 0:
        category = _categorize_stock(evidence)

    return {
        'ticker': ticker,
        'company_name': company_name,
        'sector': sector,
        'has_ai': score >= 40,
        'score': score,
        'category': category or 'ai_beneficiary',
        'evidence': ' | '.join(evidence[:5])  # Limit evidence length
    }


def _categorize_stock(evidence: list) -> str:
    """Determine AI category based on evidence."""

    evidence_text = ' '.join(evidence).lower()

    category_keywords = AI_KEYWORDS['tier1']['categories']

    # Check each category
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in evidence_text:
                return category

    # Default category
    return 'ai_beneficiary'


def _llm_validation(ticker: str, stage1_result: dict, edgar_data: dict) -> dict:
    """Stage 2: LLM classification for involvement_level + category refinement.

    Calls OpenRouter (via openai SDK) to classify:
    - involvement_level: research_ai | build_ai | leverage_ai | use_ai
    - category: ai_chip | ai_software | ai_cloud | ai_infrastructure | ai_beneficiary
    - adjusted_score: keyword score +/- adjustment based on context
    - reasoning: one-sentence explanation

    Only called for borderline keyword scores (30-70). Safe defaults returned
    on any error.

    Args:
        ticker: Stock symbol
        stage1_result: Output from _keyword_scoring
        edgar_data: Output from _fetch_edgar_ai_mentions

    Returns:
        dict with involvement_level, category, adjusted_score, reasoning
    """
    from openai import OpenAI

    safe_default = {
        "involvement_level": "use_ai",
        "category": stage1_result.get("category", "ai_beneficiary"),
        "adjusted_score": stage1_result["score"],
        "reasoning": "LLM validation unavailable — using keyword score.",
    }

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return safe_default

    edgar_snippets = "\n".join(edgar_data.get("snippets", [])[:3]) or "No SEC filings found."
    edgar_count = edgar_data.get("count", 0)

    prompt = f"""You are classifying a stock's relationship to AI for a trading system.

Company: {stage1_result['company_name']} ({ticker})
Sector: {stage1_result.get('sector', 'Unknown')}
Keyword Evidence: {stage1_result.get('evidence', 'None')}
Keyword Score: {stage1_result['score']} / 100
SEC 10-K AI Mentions: {edgar_count} filing(s) found
SEC Snippets:
{edgar_snippets}

Classify this company using BOTH fields:

involvement_level — choose one:
- "research_ai": Core business IS AI research (dedicated AI labs, publishes AI papers, AI patents are primary IP)
- "build_ai": Builds and SELLS AI products as primary business (AI chips, LLM platforms, AI SaaS)
- "leverage_ai": Uses AI to SIGNIFICANTLY enhance existing products or margins
- "use_ai": Uses off-the-shelf AI tools operationally

category — choose one:
- "ai_chip": Designs/manufactures AI processors (GPUs, TPUs, neural chips)
- "ai_software": Builds AI applications, LLMs, or AI-native platforms
- "ai_cloud": Provides AI infrastructure (training, inference, cloud AI services)
- "ai_infrastructure": Enables AI (data centers, networking, storage for AI workloads)
- "ai_beneficiary": Benefits from AI adoption but AI isn't core to product

adjusted_score: Start from {stage1_result['score']}, adjust by at most +/-20.

Return ONLY valid JSON, no markdown:
{{
  "involvement_level": "...",
  "category": "...",
  "adjusted_score": <integer 0-100>,
  "reasoning": "<one sentence>"
}}"""

    try:
        client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
        response = client.chat.completions.create(
            model="google/gemini-flash-1.5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:].lstrip()

        # Extract JSON object region robustly (handles leading/trailing text)
        start_idx = raw.find("{")
        end_idx = raw.rfind("}")
        if start_idx >= 0 and end_idx > start_idx:
            raw = raw[start_idx:end_idx + 1]

        result = json.loads(raw)

        valid_levels = {"research_ai", "build_ai", "leverage_ai", "use_ai"}
        valid_categories = {"ai_chip", "ai_software", "ai_cloud", "ai_infrastructure", "ai_beneficiary"}

        return {
            "involvement_level": result.get("involvement_level") if result.get("involvement_level") in valid_levels else "use_ai",
            "category": result.get("category") if result.get("category") in valid_categories else safe_default["category"],
            "adjusted_score": max(0, min(100, int(result.get("adjusted_score", stage1_result.get("score", 50))))),
            "reasoning": str(result.get("reasoning", ""))[:500],
        }

    except Exception as e:
        safe_default["reasoning"] = f"LLM error: {str(e)[:100]}"
        return safe_default


def _update_trading_universe(ticker: str, data_json: str) -> str:
    """Add or update a stock in the trading_universe table.

    Args:
        ticker: Stock symbol
        data_json: JSON string with fields to update:
            {
                'company_name': str,
                'sector': str,
                'category': str,
                'score': int,
                'is_active': bool,
                'notes': str
            }

    Returns:
        Confirmation message
    """
    if not supabase:
        return "Error: Supabase not connected"

    try:
        data = json.loads(data_json)
        ticker = ticker.upper().strip()

        # Prepare upsert data
        upsert_data = {
            'ticker': ticker,
            'last_scanned': datetime.utcnow().isoformat()
        }

        # Add optional fields
        if 'company_name' in data:
            upsert_data['company_name'] = data['company_name']
        if 'sector' in data:
            upsert_data['sector'] = data['sector']
        if 'category' in data:
            upsert_data['category'] = data['category']
        if 'score' in data:
            upsert_data['score'] = int(data['score'])
        if 'is_active' in data:
            upsert_data['is_active'] = bool(data['is_active'])
            if not data['is_active']:
                upsert_data['deactivated_at'] = datetime.utcnow().isoformat()
        if 'notes' in data:
            upsert_data['notes'] = data['notes']

        # Update last_mention if mentioned in recent scan
        if data.get('score', 0) > 0:
            upsert_data['last_mention'] = datetime.utcnow().isoformat()

        # Upsert to Supabase
        result = supabase.table('trading_universe').upsert(upsert_data).execute()

        return f"✓ Updated {ticker} in trading_universe (score: {data.get('score', 'N/A')}, category: {data.get('category', 'N/A')})"

    except Exception as e:
        return f"Error updating trading_universe for {ticker}: {str(e)}"


def _get_trading_universe(filters_json: str = "{}") -> str:
    """Query trading_universe table with filters.

    Args:
        filters_json: JSON string with filter criteria:
            {
                'is_active': bool,
                'min_score': int,
                'max_score': int,
                'category': str,
                'limit': int
            }

    Returns:
        JSON string with list of matching stocks
    """
    if not supabase:
        return json.dumps({'error': 'Supabase not connected'})

    try:
        filters = json.loads(filters_json)

        # Build query
        query = supabase.table('trading_universe').select('*')

        # Apply filters
        if 'is_active' in filters:
            query = query.eq('is_active', filters['is_active'])

        if 'min_score' in filters:
            query = query.gte('score', filters['min_score'])

        if 'max_score' in filters:
            query = query.lte('score', filters['max_score'])

        if 'category' in filters:
            query = query.eq('category', filters['category'])

        # Order by score descending
        query = query.order('score', desc=True)

        # Limit results
        limit = filters.get('limit', 100)
        query = query.limit(limit)

        # Execute query
        result = query.execute()

        return json.dumps({
            'count': len(result.data),
            'stocks': result.data
        }, indent=2)

    except Exception as e:
        return json.dumps({'error': str(e)})


# Wrap functions with FunctionTool for google-adk compatibility
scan_stock_for_ai = FunctionTool(_scan_stock_for_ai)
update_trading_universe = FunctionTool(_update_trading_universe)
get_trading_universe = FunctionTool(_get_trading_universe)
