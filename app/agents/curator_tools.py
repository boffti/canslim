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
            llm_result = _llm_validation(ticker, result)
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


def _llm_validation(ticker: str, stage1_result: dict) -> dict:
    """Stage 2: LLM validation for borderline scores (30-70)."""

    # This would call the LLM to validate
    # For now, return stage1 result unchanged
    # TODO: Implement LLM validation call via OpenRouter

    prompt = f"""Analyze this company's AI involvement:

Company: {stage1_result['company_name']} ({ticker})
Sector: {stage1_result.get('sector', 'Unknown')}
Keyword Score: {stage1_result['score']}
Evidence: {stage1_result['evidence']}

Questions:
1. Is this a genuine AI company? (yes/no)
2. What's the primary AI category: ai_chip, ai_software, ai_cloud, ai_infrastructure, or ai_beneficiary?
3. Adjust score between {stage1_result['score']-20} and {stage1_result['score']+20} based on context.
4. Provide brief reasoning (1 sentence).

Return JSON:
{{
  "is_genuine_ai": bool,
  "category": str,
  "adjusted_score": int,
  "reasoning": str
}}
"""

    # For MVP, skip LLM validation and return stage1 result
    # TODO: Add actual LLM call here
    return {
        'adjusted_score': stage1_result['score'],
        'category': stage1_result['category'],
        'reasoning': 'LLM validation not implemented yet - using keyword scoring'
    }


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
