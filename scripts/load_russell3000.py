#!/usr/bin/env python3
"""
Bootstrap script to load Russell 3000 stocks into trading_universe table.

Usage:
    1. Download Russell 3000 holdings CSV from iShares IWV ETF:
       https://www.ishares.com/us/products/239714/ishares-russell-3000-etf
    2. Save as: data/russell3000_holdings.csv
    3. Run: uv run python scripts/load_russell3000.py

Expected CSV columns:
    - Ticker: Stock symbol
    - Name: Company name
    - Sector: Industry sector (optional)
"""

import pandas as pd
from dotenv import load_dotenv
import sys
import os

# Ensure project root is on sys.path so `app` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_russell3000(csv_path='data/russell3000_holdings.csv'):
    """Load Russell 3000 stocks from iShares CSV into trading_universe table."""

    # Load environment variables
    load_dotenv()

    # Initialize Flask app to get Supabase client
    from app import create_app
    app = create_app()

    with app.app_context():
        from app.dashboard.utils import _get_supabase
        supabase = _get_supabase()

        if not supabase:
            print("❌ Error: Supabase not connected. Check .env file.")
            return False

        # Check if file exists
        if not os.path.exists(csv_path):
            print(f"❌ Error: CSV file not found at {csv_path}")
            print("\nPlease download Russell 3000 holdings CSV from:")
            print("https://www.ishares.com/us/products/239714/ishares-russell-3000-etf")
            print(f"Save as: {csv_path}")
            return False

        # Read CSV
        try:
            df = pd.read_csv(csv_path)
            print(f"📊 Read {len(df)} stocks from CSV")
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            return False

        # Map CSV columns (adjust based on actual iShares format)
        # Common iShares CSV column names: 'Ticker', 'Name', 'Sector', 'Weight', 'Market Value'
        stocks_to_insert = []

        for idx, row in df.iterrows():
            try:
                ticker = str(row.get('Ticker', row.get('Symbol', ''))).strip().upper()

                if not ticker or ticker == '' or ticker == 'NAN':
                    continue

                stock = {
                    'ticker': ticker,
                    'company_name': str(row.get('Name', row.get('Company Name', ''))).strip(),
                    'sector': str(row.get('Sector', row.get('GICS Sector', ''))).strip() or None,
                    'category': None,        # Curator will categorize
                    'score': 0,              # Curator will score
                    'is_active': True,
                    'last_scanned': None,
                    'last_mention': None,
                    'notes': 'Russell 3000 seed stock'
                }
                stocks_to_insert.append(stock)
            except Exception as e:
                print(f"⚠️  Warning: Skipped row {idx}: {e}")
                continue

        if not stocks_to_insert:
            print("❌ Error: No valid stocks found in CSV")
            return False

        # Deduplicate by ticker (keep last occurrence)
        seen = {}
        for stock in stocks_to_insert:
            seen[stock['ticker']] = stock
        stocks_to_insert = list(seen.values())

        print(f"✓ Prepared {len(stocks_to_insert)} stocks for insertion (after dedup)")

        # Batch insert to Supabase (1000 rows at a time)
        total = len(stocks_to_insert)
        batch_size = 1000
        inserted = 0

        try:
            for i in range(0, total, batch_size):
                batch = stocks_to_insert[i:i+batch_size]
                supabase.table('trading_universe').upsert(batch, on_conflict='ticker').execute()
                inserted += len(batch)
                print(f"✓ Upserted batch {i//batch_size + 1}: {len(batch)} stocks ({inserted}/{total})")
        except Exception as e:
            print(f"❌ Error inserting data: {e}")
            print(f"Successfully inserted {inserted} stocks before error")
            return False

        print(f"\n✅ Successfully loaded {total} stocks into trading_universe table")
        print("\nNext steps:")
        print("1. Go to Supabase Dashboard → SQL Editor")
        print("2. Verify: SELECT COUNT(*) FROM trading_universe;")
        print("3. Start Curator: uv run python -c \"from app.tasks import task_curator_weekly_scan; task_curator_weekly_scan()\"")

        return True


if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'data/russell3000_holdings.csv'

    print("=" * 60)
    print("Russell 3000 Bootstrap Script")
    print("=" * 60)
    print(f"CSV file: {csv_file}\n")

    success = load_russell3000(csv_file)
    sys.exit(0 if success else 1)
