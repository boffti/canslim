# 🚀 Curator Quick Start

**Status:** Code Complete - Need Model Config

---

## ⚡ 5-Minute Setup

### 1. Configure Model (REQUIRED)

**Choose ONE option:**

**Option A: Use Gemini API** (Recommended - Free Tier Available)
```bash
# Add to .env
GEMINI_API_KEY=your_gemini_key_here
```

Update `app/agents/curator.py` and `app/agents/wilson.py`:
```python
from google.adk.models import Model

model = Model(
    model_name="gemini-1.5-flash",
    api_key=os.environ.get("GEMINI_API_KEY")
)
```

**Option B: Use Valid OpenRouter Model**

Check https://openrouter.ai/models for models with "Function calling: Yes"

Example:
```python
model = LiteLlm(
    model="openrouter/anthropic/claude-3-5-sonnet",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1"
)
```

### 2. Test Curator

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from app.tasks import task_curator_daily_scan
task_curator_daily_scan()
"
```

### 3. Verify Results

Check Supabase tables:
- `trading_universe` - Stocks scanned
- `watchlist` - High-scorers (70+)
- `journal` - Curator logs

### 4. Launch System

```bash
uv run run.py
# Visit: http://localhost:5561
```

---

## 📋 What You Get

- ✅ **trading_universe** table ready (3000+ stocks)
- ✅ **3 new Curator tools** (scan, update, query)
- ✅ **3 scheduled tasks** (daily, weekly, monthly)
- ✅ **Wilson updated** to use AI watchlist
- ✅ **Full documentation** in `docs/`

---

## 🎯 Next Steps (Optional)

### Bootstrap Russell 3000
```bash
# 1. Download: https://www.ishares.com/us/products/239714/
# 2. Save as: data/russell3000_holdings.csv
# 3. Run: uv run python scripts/load_russell3000.py
```

### Monitor Activity
```sql
-- Supabase SQL Editor
SELECT * FROM journal WHERE agent_name = 'Curator' ORDER BY created_at DESC;
SELECT * FROM watchlist;
SELECT COUNT(*) FROM trading_universe WHERE is_active = true;
```

---

## 📖 Full Documentation

- **Complete Summary**: `docs/IMPLEMENTATION_COMPLETE_SUMMARY.md`
- **Design Doc**: `docs/plans/2026-02-12-ai-universe-curator-design.md`
- **Implementation Status**: `docs/CURATOR_IMPLEMENTATION_STATUS.md`

---

## ⏱️ Timeline

**5 min** - Configure model
**2 min** - Test Curator
**Done!** - System operational

**Optional:**
**10 min** - Bootstrap Russell 3000

---

## 🆘 Troubleshooting

**"Model not found"** → Check model ID at https://openrouter.ai/models
**"No tool support"** → Choose model with function calling
**"No results"** → Run `task_curator_daily_scan()` manually
**"Supabase error"** → Check `.env` has `SUPABASE_URL` and `SUPABASE_KEY`

---

**Ready? Configure your model and test!** 🎉
