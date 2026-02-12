from flask import Blueprint, render_template, jsonify, request, Response, redirect, url_for
from datetime import datetime
import io
import csv
import json
import os

from .utils import (
    get_cached_data, load_json_file, save_json_file, 
    load_routine, save_routine, get_all_routine_dates,
    load_calls, save_calls, _calls_summary,
    load_positions, save_positions, _positions_summary,
    SETTINGS_FILE, ALERTS_FILE, EARNINGS_FILE, HISTORY_DIR, 
    DEFAULT_SETTINGS, SECTION_DIVIDERS
)

# Define Blueprint
bp = Blueprint('dashboard', __name__)

# --- Main Routes ---
@bp.route('/')
def index():
    """Render the dashboard"""
    return render_template('index.html')

@bp.route('/api/data')
def api_data():
    """Return cached sheet data as JSON"""
    data = get_cached_data()
    if data is None:
        return jsonify({'error': 'Failed to fetch data'}), 500
    
    # Calculate Shares and Cost for each stock
    settings = load_json_file(SETTINGS_FILE, {})
    account_equity = settings.get('account_equity', 100000)
    risk_pct = settings.get('risk_pct', 0.01)
    risk_per_trade = account_equity * risk_pct
    
    for stock in data['stocks']:
        try:
            pivot = float(stock.get('Pivot', 0))
            stop = float(stock.get('Stop', 0))
            if pivot > 0 and stop > 0 and pivot > stop:
                risk_per_share = pivot - stop
                shares = int(risk_per_trade / risk_per_share)
                stock['Shares'] = str(shares)
                stock['Cost'] = f"${shares * pivot:,.0f}"
            else:
                stock['Shares'] = ''
                stock['Cost'] = ''
        except (ValueError, ZeroDivisionError):
            stock['Shares'] = ''
            stock['Cost'] = ''
    
    # Add 'Cost' to headers if not already present
    headers = data.get('headers', [])
    if 'Cost' not in headers:
        # Add after 'Shares' if it exists, otherwise at the end
        if 'Shares' in headers:
            shares_idx = headers.index('Shares')
            headers.insert(shares_idx + 1, 'Cost')
        else:
            headers.append('Cost')
    
    return jsonify(data)

@bp.route('/api/refresh')
def api_refresh():
    """Force refresh the data"""
    data = get_cached_data(force_refresh=True)
    if data is None:
        return jsonify({'error': 'Failed to refresh data'}), 500
    return jsonify(data)

@bp.route('/api/export')
def api_export():
    """Export filtered data as CSV"""
    data = get_cached_data()
    if data is None:
        return jsonify({'error': 'Failed to fetch data'}), 500
    
    # Get filter parameter if provided
    filter_text = request.args.get('filter', '').lower()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    headers = data.get('headers', [])
    writer.writerow(headers)
    
    # Write stock data
    stocks = data.get('stocks', [])
    for stock in stocks:
        # Apply filter if provided
        if filter_text:
            ticker = stock.get('Ticker', '').lower()
            if filter_text not in ticker:
                continue
        
        row = [stock.get(header, '') for header in headers]
        writer.writerow(row)
    
    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=canslim_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )

# --- Alert API endpoints ---
@bp.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get all alerts"""
    alerts = load_json_file(ALERTS_FILE, [])
    return jsonify(alerts)

@bp.route('/api/alerts', methods=['POST'])
def add_alert():
    """Add a new alert"""
    try:
        data = request.json or {}
        
        # Validate ticker
        ticker = data.get('ticker', '').strip().upper()
        if not ticker or len(ticker) > 10 or not ticker.replace('.', '').replace('-', '').isalnum():
            return jsonify({'error': 'Invalid ticker (max 10 alphanumeric chars)'}), 400
        
        # Validate condition
        condition = data.get('condition', 'above')
        if condition not in ['above', 'below']:
            return jsonify({'error': 'Invalid condition (must be above or below)'}), 400
        
        # Validate price
        try:
            price = float(data.get('price', 0))
            if price <= 0 or price > 1000000:
                return jsonify({'error': 'Invalid price (must be positive, max $1M)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid price (must be a number)'}), 400
        
        alerts = load_json_file(ALERTS_FILE, [])
        
        new_alert = {
            'ticker': ticker,
            'condition': condition,
            'price': price,
            'created': datetime.utcnow().isoformat(),
            'triggered': False
        }
        
        alerts.append(new_alert)
        
        if save_json_file(ALERTS_FILE, alerts):
            return jsonify(new_alert), 201
        else:
            return jsonify({'error': 'Failed to save alert'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/alerts/<int:index>', methods=['DELETE'])
def delete_alert(index):
    """Delete an alert by index"""
    try:
        alerts = load_json_file(ALERTS_FILE, [])
        
        if index < 0 or index >= len(alerts):
            return jsonify({'error': 'Invalid index'}), 404
        
        deleted = alerts.pop(index)
        
        if save_json_file(ALERTS_FILE, alerts):
            return jsonify({'deleted': deleted}), 200
        else:
            return jsonify({'error': 'Failed to delete alert'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Earnings API endpoints ---
@bp.route('/api/earnings', methods=['GET'])
def get_earnings():
    """Get all earnings dates"""
    earnings = load_json_file(EARNINGS_FILE, {})
    return jsonify(earnings)

@bp.route('/api/earnings', methods=['POST'])
def set_earnings():
    """Set earnings date for a ticker"""
    try:
        data = request.json
        ticker = data.get('ticker', '').upper()
        date = data.get('date', '')
        
        if not ticker or not date:
            return jsonify({'error': 'Invalid ticker or date'}), 400
        
        earnings = load_json_file(EARNINGS_FILE, {})
        earnings[ticker] = date
        
        if save_json_file(EARNINGS_FILE, earnings):
            return jsonify({'ticker': ticker, 'date': date}), 200
        else:
            return jsonify({'error': 'Failed to save earnings date'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- History API endpoints ---
@bp.route('/api/history', methods=['GET'])
def get_history():
    """List all historical snapshots"""
    try:
        if not os.path.exists(HISTORY_DIR):
            return jsonify([])
        
        files = []
        for filename in sorted(os.listdir(HISTORY_DIR), reverse=True):
            if filename.endswith('.json'):
                filepath = os.path.join(HISTORY_DIR, filename)
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    files.append({
                        'filename': filename,
                        'scan_time': data.get('scan_time', 'Unknown'),
                        'stock_count': len(data.get('stocks', []))
                    })
        
        return jsonify(files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/history/<filename>', methods=['GET'])
def get_historical_snapshot(filename):
    """Get a specific historical snapshot"""
    try:
        filepath = os.path.join(HISTORY_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Snapshot not found'}), 404
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Settings API endpoints ---
@bp.route('/api/settings', methods=['GET'])
def get_settings():
    """Get scanner settings"""
    settings = load_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
    # Merge with defaults for any missing keys
    for k, v in DEFAULT_SETTINGS.items():
        if k not in settings:
            settings[k] = v
    return jsonify(settings)

@bp.route('/api/settings', methods=['POST'])
def update_settings():
    """Update scanner settings"""
    try:
        data = request.json
        settings = load_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
        
        if 'account_equity' in data:
            settings['account_equity'] = float(data['account_equity'])
        if 'risk_pct' in data:
            settings['risk_pct'] = float(data['risk_pct'])
        if 'max_positions' in data:
            settings['max_positions'] = int(data['max_positions'])
        
        if save_json_file(SETTINGS_FILE, settings):
            return jsonify(settings), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Daily Trading Routine ---
@bp.route('/routine')
def routine_today():
    today = datetime.now().strftime('%Y-%m-%d')
    return redirect(url_for('dashboard.routine_view', date_str=today))

@bp.route('/routine/<date_str>')
def routine_view(date_str):
    data = load_routine(date_str)
    return render_template('routine.html', date_str=date_str, data=data)

@bp.route('/routine/<date_str>/<routine_type>', methods=['GET', 'POST'])
def routine_form(date_str, routine_type):
    if routine_type not in ('premarket', 'postclose'):
        return 'Invalid type', 404
    data = load_routine(date_str)
    if request.method == 'POST':
        fields = {}
        for key in request.form:
            if key.startswith('routine_'):
                fields[key[8:]] = request.form[key]
        data[routine_type] = fields
        save_routine(date_str, data)
        return redirect(url_for('dashboard.routine_view', date_str=date_str))
    existing = data.get(routine_type, {})
    return render_template('routine_form.html', date_str=date_str,
                         routine_type=routine_type, data=existing)

import calendar as cal

@bp.route('/calendar')
@bp.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    today = datetime.now()
    if year is None: year = today.year
    if month is None: month = today.month
    weeks = cal.monthcalendar(year, month)
    num_days = cal.monthrange(year, month)[1]
    all_dates = get_all_routine_dates()
    days_data = {}
    for day in range(1, num_days + 1):
        ds = f'{year}-{month:02d}-{day:02d}'
        if ds in all_dates:
            days_data[day] = all_dates[ds]
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return render_template('calendar.html', year=year, month=month,
                         month_name=cal.month_name[month], weeks=weeks,
                         days_data=days_data, prev_year=prev_year,
                         prev_month=prev_month, next_year=next_year,
                         next_month=next_month,
                         today_str=today.strftime('%Y-%m-%d'))

@bp.route('/api/routine/<date_str>', methods=['GET'])
def api_routine_get(date_str):
    return jsonify(load_routine(date_str))

@bp.route('/api/routine/<date_str>', methods=['POST'])
def api_routine_save(date_str):
    req = request.json
    data = load_routine(date_str)
    rtype = req.get('type', 'premarket')
    if rtype in ('premarket', 'postclose'):
        data[rtype] = req.get('data', {})
    save_routine(date_str, data)
    return jsonify({'ok': True})


# --- Trade Tracker: Covered Calls ---
@bp.route('/calls')
def calls_page():
    return render_template('calls.html')

@bp.route('/api/calls', methods=['GET'])
def api_calls_get():
    trades = load_calls()
    return jsonify({'trades': trades, 'summary': _calls_summary(trades)})

@bp.route('/api/calls', methods=['POST'])
def api_calls_add():
    try:
        data = request.json or {}
        trades = load_calls()
        
        # Validate ticker
        ticker = data.get('ticker', 'SPY').strip().upper()
        if not ticker or len(ticker) > 10 or not ticker.replace('.', '').replace('-', '').isalnum():
            return jsonify({'error': 'Invalid ticker (max 10 alphanumeric chars)'}), 400
        
        # Validate contracts
        try:
            contracts = int(data.get('contracts', 1))
            if contracts <= 0 or contracts > 10000:
                return jsonify({'error': 'Invalid contracts (must be 1-10,000)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid contracts (must be an integer)'}), 400
        
        # Validate premium_per_contract
        try:
            premium_per = float(data.get('premium_per_contract', 0))
            if premium_per < 0 or premium_per > 10000:
                return jsonify({'error': 'Invalid premium (must be 0-$10,000)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid premium (must be a number)'}), 400
        
        # Validate strike
        try:
            strike = float(data.get('strike', 0))
            if strike <= 0 or strike > 100000:
                return jsonify({'error': 'Invalid strike (must be positive, max $100k)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid strike (must be a number)'}), 400
        
        trade = {
            'id': (max((t.get('id', 0) for t in trades), default=0) + 1),
            'ticker': ticker,
            'sell_date': data.get('sell_date', datetime.now().strftime('%Y-%m-%d')),
            'expiry': data.get('expiry', ''),
            'strike': strike,
            'contracts': contracts,
            'premium_per_contract': premium_per,
            'premium_total': round(premium_per * contracts * 100, 2),
            'delta': data.get('delta', 0.10),
            'stock_price_at_sell': data.get('stock_price', 0),
            'status': 'open',
            'close_date': None,
            'close_price': None,
            'pnl': None,
            'notes': data.get('notes', ''),
            'created_at': datetime.now().isoformat(),
        }
        trades.append(trade)
        save_calls(trades)
        return jsonify({'ok': True, 'trade': trade}), 201
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@bp.route('/api/calls/<int:trade_id>', methods=['PATCH'])
def api_calls_close(trade_id):
    data = request.json
    trades = load_calls()
    for t in trades:
        if t.get('id') == trade_id:
            status = data.get('status', 'expired')
            t['status'] = status
            t['close_date'] = data.get('close_date', datetime.now().strftime('%Y-%m-%d'))
            if status == 'expired':
                t['pnl'] = t['premium_total']
            elif status == 'called_away':
                price_at_sell = t.get('stock_price_at_sell', 0)
                appreciation = (t['strike'] - price_at_sell) * t['contracts'] * 100
                t['pnl'] = round(t['premium_total'] + appreciation, 2)
            else:
                buyback = data.get('buyback_price', 0) * t['contracts'] * 100
                t['pnl'] = round(t['premium_total'] - buyback, 2)
                t['close_price'] = data.get('buyback_price', 0)
            t['notes'] = data.get('notes', t.get('notes', ''))
            break
    save_calls(trades)
    return jsonify({'ok': True})

@bp.route('/api/calls/<int:trade_id>', methods=['DELETE'])
def api_calls_delete(trade_id):
    trades = load_calls()
    trades = [t for t in trades if t.get('id') != trade_id]
    save_calls(trades)
    return jsonify({'ok': True})

# --- Health Check ---
@bp.route('/api/health')
def health():
    return jsonify({"status": "ok", "app": "canslim-dashboard"})

# --- Trade Tracker: Stock Positions ---
@bp.route('/api/positions', methods=['GET'])
def api_positions_get():
    positions = load_positions()
    return jsonify({'positions': positions, 'summary': _positions_summary(positions)})

@bp.route('/api/quotes', methods=['GET'])
def api_quotes():
    """Get current prices for a list of tickers (requires external API setup)"""
    tickers = request.args.get('tickers', '')
    if not tickers:
        return jsonify({})
    return jsonify({'error': 'Market data API not configured'}), 501

@bp.route('/api/positions', methods=['POST'])
def api_positions_add():
    try:
        data = request.json or {}
        positions = load_positions()
        
        # Validate ticker
        ticker = data.get('ticker', '').strip().upper()
        if not ticker or len(ticker) > 10 or not ticker.replace('.', '').replace('-', '').isalnum():
            return jsonify({'error': 'Invalid ticker (max 10 alphanumeric chars)'}), 400
        
        # Validate shares
        try:
            shares = int(data.get('shares', 0))
            if shares <= 0 or shares > 1000000:
                return jsonify({'error': 'Invalid shares (must be 1-1,000,000)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid shares (must be an integer)'}), 400
        
        # Validate entry_price
        try:
            entry_price = float(data.get('entry_price', 0))
            if entry_price <= 0 or entry_price > 100000:
                return jsonify({'error': 'Invalid entry price (must be positive, max $100k)'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid entry price (must be a number)'}), 400
        
        # Validate optional prices
        stop_price = float(data.get('stop_price', 0)) if data.get('stop_price') else 0
        target_price = float(data.get('target_price', 0)) if data.get('target_price') else 0
        
        # Validate trade_type
        trade_type = data.get('trade_type', 'long')
        if trade_type not in ['long', 'short']:
            return jsonify({'error': 'Invalid trade_type (must be long or short)'}), 400
        
        position = {
            'id': (max((p.get('id', 0) for p in positions), default=0) + 1),
            'ticker': ticker,
            'account': data.get('account', 'default'),
            'trade_type': trade_type,
            'entry_date': data.get('entry_date', datetime.now().strftime('%Y-%m-%d')),
            'entry_price': entry_price,
            'shares': shares,
            'cost_basis': round(shares * entry_price, 2),
            'stop_price': stop_price,
            'target_price': target_price,
            'setup_type': data.get('setup_type', ''),
            'status': 'open',
            'close_date': None,
            'close_price': None,
            'pnl': None,
            'notes': data.get('notes', ''),
            'created_at': datetime.now().isoformat(),
        }
        positions.append(position)
        save_positions(positions)
        return jsonify({'ok': True, 'position': position}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
