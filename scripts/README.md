# Scripts

Utility scripts for DeepDiver system maintenance.

## Bootstrap Scripts

### load_russell3000.py

Loads Russell 3000 stocks into the `trading_universe` table for Curator to scan.

**Prerequisites:**
1. Download Russell 3000 holdings CSV from iShares:
   - URL: https://www.ishares.com/us/products/239714/ishares-russell-3000-etf
   - Click "Holdings" tab
   - Download CSV
   - Save as: `data/russell3000_holdings.csv`

**Usage:**
```bash
uv run python scripts/load_russell3000.py
```

**Optional custom CSV path:**
```bash
uv run python scripts/load_russell3000.py /path/to/custom.csv
```

**Expected CSV columns:**
- `Ticker` (or `Symbol`): Stock ticker symbol
- `Name` (or `Company Name`): Company name
- `Sector` (or `GICS Sector`): Industry sector (optional)

**Output:**
- Inserts ~3000 stocks into `trading_universe` table
- All stocks start with `score=0`, `category=None`, `is_active=True`
- Curator will progressively scan and score them

**Verification:**
```sql
-- Run in Supabase SQL Editor
SELECT COUNT(*) FROM trading_universe;
SELECT * FROM trading_universe LIMIT 10;
```

**Quarterly Refresh:**

Russell 3000 rebalances quarterly. To refresh:
1. Download fresh CSV
2. Re-run script (upserts won't duplicate)
3. New stocks added, delisted stocks deactivated by Curator
