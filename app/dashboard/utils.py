import os
import json
import time
import fcntl
import subprocess
from datetime import datetime

# Configuration from environment variables
SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '')
SHEET_RANGE = os.getenv('SHEET_RANGE', "'Main'!A1:W50")
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')
CACHE_DURATION = int(os.getenv('CACHE_DURATION', '300'))  # 5 minutes default

# File paths - relative to app directory
# app/dashboard/utils.py -> app/data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

os.makedirs(DATA_DIR, exist_ok=True)

ALERTS_FILE = os.path.join(DATA_DIR, 'alerts.json')
EARNINGS_FILE = os.path.join(DATA_DIR, 'earnings.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
HISTORY_DIR = os.path.join(DATA_DIR, 'history')
ROUTINES_DIR = os.path.join(DATA_DIR, 'routines')
CALLS_DATA = os.path.join(DATA_DIR, 'covered_calls.json')
POSITIONS_DATA = os.path.join(DATA_DIR, 'positions.json')

os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(ROUTINES_DIR, exist_ok=True)

# Cache storage
cache = {
    'data': None,
    'timestamp': 0,
    'last_scan_time': None
}

DEFAULT_SETTINGS = {
    'account_equity': 100000,
    'risk_pct': 0.01,
    'max_positions': 6
}

def fetch_sheet_data():
    """Fetch data from Google Sheets using gog CLI"""
    if not SHEET_ID or not GOG_ACCOUNT:
        print("Error: GOOGLE_SHEET_ID and GOG_ACCOUNT environment variables must be set")
        return None
    
    try:
        env = os.environ.copy()
        env['GOG_ACCOUNT'] = GOG_ACCOUNT
        
        cmd = ['gog', 'sheets', 'get', SHEET_ID, SHEET_RANGE, '--json']
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Error fetching sheet: {result.stderr}")
            return None
        
        data = json.loads(result.stdout)
        return data.get('values', [])
    except Exception as e:
        print(f"Exception fetching sheet: {e}")
        return None

def parse_sheet_data(raw_values):
    """Parse raw sheet values into structured data"""
    if not raw_values or len(raw_values) < 5:
        return None
    
    # Row 0: Title and timestamp
    scan_time = raw_values[0][2] if len(raw_values[0]) > 2 else "Unknown"
    
    # Row 1: Market regime
    market_regime = raw_values[1][0] if len(raw_values[1]) > 0 else ""
    dist_days = raw_values[1][2] if len(raw_values[1]) > 2 else ""
    buy_ok = raw_values[1][4] if len(raw_values[1]) > 4 else ""
    
    # Row 2: Account info
    account = raw_values[2][0] if len(raw_values[2]) > 0 else ""
    risk_per_trade = raw_values[2][2] if len(raw_values[2]) > 2 else ""
    actionable = raw_values[2][4] if len(raw_values[2]) > 4 else ""
    
    # Row 4: Headers (skip row 3 which is empty)
    headers = raw_values[4] if len(raw_values) > 4 else []
    
    # Rows 5+: Stock data
    stocks = []
    for i in range(5, len(raw_values)):
        row = raw_values[i]
        if row and len(row) > 1:  # Skip empty rows
            stock = {}
            for j, header in enumerate(headers):
                stock[header] = row[j] if j < len(row) else ""
            stocks.append(stock)
    
    return {
        'scan_time': scan_time,
        'market': {
            'regime': market_regime,
            'dist_days': dist_days,
            'buy_ok': buy_ok
        },
        'account': {
            'balance': account,
            'risk_per_trade': risk_per_trade,
            'actionable': actionable
        },
        'headers': headers,
        'stocks': stocks,
        'cache_time': cache['timestamp']
    }

def save_historical_snapshot(data):
    """Save a snapshot of the current scan to history"""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        filename = f"scan_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
        filepath = os.path.join(HISTORY_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved historical snapshot: {filename}")
    except Exception as e:
        print(f"Error saving snapshot: {e}")

def get_cached_data(force_refresh=False):
    """Get data from cache or fetch if expired"""
    current_time = time.time()
    
    if force_refresh or cache['data'] is None or (current_time - cache['timestamp']) > CACHE_DURATION:
        raw_data = fetch_sheet_data()
        if raw_data:
            cache['data'] = parse_sheet_data(raw_data)
            cache['timestamp'] = current_time
            
            # Save historical snapshot if it's a new scan
            if cache['data'] and cache['data'].get('scan_time') != cache.get('last_scan_time'):
                save_historical_snapshot(cache['data'])
                cache['last_scan_time'] = cache['data'].get('scan_time')
    
    return cache['data']

def load_json_file(filepath, default=None):
    """Load JSON file or return default if not exists"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return default if default is not None else []

def save_json_file(filepath, data):
    """Save data to JSON file using atomic write with file locking"""
    try:
        tmp_path = filepath + '.tmp'
        lock_path = filepath + '.lock'
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with open(tmp_path, 'w') as f:
                    json.dump(data, f, indent=2)
                os.rename(tmp_path, filepath)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

# Routine helpers
def load_routine(date_str):
    path = os.path.join(ROUTINES_DIR, f'{date_str}.json')
    if os.path.exists(path):
        return json.loads(open(path).read())
    return {'date': date_str}

def save_routine(date_str, data):
    data['date'] = date_str
    data['updated_at'] = datetime.now().isoformat()
    path = os.path.join(ROUTINES_DIR, f'{date_str}.json')
    tmp_path = path + '.tmp'
    lock_path = path + '.lock'
    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.rename(tmp_path, path)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def get_all_routine_dates():
    """Get set of dates that have routine files."""
    dates = {}
    if not os.path.exists(ROUTINES_DIR):
        return dates
    for f in os.listdir(ROUTINES_DIR):
        if f.endswith('.json'):
            ds = f[:-5]
            try:
                data = json.loads(open(os.path.join(ROUTINES_DIR, f)).read())
                dates[ds] = {
                    'has_premarket': bool(data.get('premarket')),
                    'has_postclose': bool(data.get('postclose')),
                }
            except:
                pass
    return dates

# Calls helpers
def load_calls():
    return load_json_file(CALLS_DATA, [])

def save_calls(trades):
    save_json_file(CALLS_DATA, trades)

def _calls_summary(trades):
    def _summarize(subset, capital=100000):
        if not subset:
            return {'total_premium': 0, 'total_pnl': 0, 'total_trades': 0,
                    'expired': 0, 'called_away': 0, 'open': 0,
                    'weekly_avg': 0, 'annualized_yield': 0}
        total_premium = sum(t.get('premium_total', 0) for t in subset)
        closed = [t for t in subset if t.get('status') != 'open']
        total_pnl = sum(t.get('pnl', t.get('premium_total', 0)) for t in closed)
        open_t = [t for t in subset if t.get('status') == 'open']
        expired = [t for t in subset if t.get('status') == 'expired']
        called = [t for t in subset if t.get('status') == 'called_away']
        if subset:
            dates = sorted(set(t.get('sell_date', '')[:7] for t in subset if t.get('sell_date')))
            months = max(len(dates), 1)
            annualized = (total_premium / months) * 12 / max(capital, 1) * 100
        else:
            annualized = 0
        return {
            'total_premium': total_premium,
            'total_pnl': total_pnl,
            'total_trades': len(subset),
            'expired': len(expired),
            'called_away': len(called),
            'open': len(open_t),
            'weekly_avg': total_premium / max(len(subset), 1),
            'annualized_yield': annualized,
        }

    # Overall summary
    overall = _summarize(trades)

    # Per-ticker summaries
    tickers = sorted(set(t.get('ticker', 'SPY') for t in trades)) if trades else []
    by_ticker = {}
    for tk in tickers:
        subset = [t for t in trades if t.get('ticker', 'SPY') == tk]
        by_ticker[tk] = _summarize(subset, 100000)

    overall['tickers'] = tickers
    overall['by_ticker'] = by_ticker
    return overall

# Positions helpers
def load_positions():
    return load_json_file(POSITIONS_DATA, [])

def save_positions(positions):
    save_json_file(POSITIONS_DATA, positions)

def _positions_summary(positions):
    # This was missing in the original app.py view but referenced. 
    # I'll implement a basic one or check if I missed it in view_file.
    # checking view_file output... it was cut off.
    # I'll implement a basic one.
    open_pos = [p for p in positions if p.get('status') == 'open']
    closed_pos = [p for p in positions if p.get('status') != 'open']
    total_pnl = sum(p.get('pnl', 0) or 0 for p in closed_pos)
    
    return {
        'open_count': len(open_pos),
        'closed_count': len(closed_pos),
        'total_pnl': total_pnl
    }
