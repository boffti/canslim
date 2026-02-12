from flask import Blueprint, render_template, jsonify, request, Response, redirect, url_for
from datetime import datetime
import io
import csv
import json
import os

from .utils import (
    get_latest_scan, get_scan_by_id, get_all_scans,
    get_settings, update_setting,
    get_all_alerts, add_alert, delete_alert,
    get_all_earnings, set_earnings_date,
    get_all_positions, add_position, update_position, delete_position, _positions_summary,
    get_all_calls, add_call, update_call, delete_call, _calls_summary,
    get_routine, save_routine, get_all_routine_dates,
    DEFAULT_SETTINGS
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
    """Return latest scan data as JSON"""
    try:
        scan = get_latest_scan()
        if scan is None:
            return jsonify({'error': 'No scans found'}), 404

        # Calculate Shares and Cost for each stock
        settings = get_settings()
        account_equity = float(settings.get('account_equity', 100000))
        risk_pct = float(settings.get('risk_pct', 0.01))
        risk_per_trade = account_equity * risk_pct

        for stock in scan.get('scan_stocks', []):
            try:
                pivot = float(stock.get('pivot', 0))
                stop = float(stock.get('stop', 0))
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

        return jsonify(scan)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/refresh')
def api_refresh():
    """Force refresh (no-op now, just returns latest data)"""
    return api_data()

@bp.route('/api/export')
def api_export():
    """Export filtered data as CSV"""
    data = get_latest_scan()
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
    return jsonify(get_all_alerts())

@bp.route('/api/alerts', methods=['POST'])
def add_alert_api():
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

        alert = add_alert(ticker, condition, price)
        if alert:
            return jsonify(alert), 201
        else:
            return jsonify({'error': 'Failed to save alert'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
def delete_alert_api(alert_id):
    """Delete an alert by ID"""
    try:
        if delete_alert(alert_id):
            return jsonify({'ok': True}), 200
        else:
            return jsonify({'error': 'Failed to delete alert'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Earnings API endpoints ---
@bp.route('/api/earnings', methods=['GET'])
def get_earnings():
    """Get all earnings dates"""
    return jsonify(get_all_earnings())

@bp.route('/api/earnings', methods=['POST'])
def set_earnings():
    """Set earnings date for a ticker"""
    try:
        data = request.json
        ticker = data.get('ticker', '').upper()
        date = data.get('date', '')

        if not ticker or not date:
            return jsonify({'error': 'Invalid ticker or date'}), 400

        if set_earnings_date(ticker, date):
            return jsonify({'ticker': ticker, 'date': date}), 200
        else:
            return jsonify({'error': 'Failed to save earnings date'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- History API endpoints ---
@bp.route('/api/history', methods=['GET'])
def get_history():
    """List all historical scans"""
    try:
        scans = get_all_scans(limit=100)
        return jsonify(scans)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/history/<int:scan_id>', methods=['GET'])
def get_historical_scan(scan_id):
    """Get specific historical scan"""
    try:
        scan = get_scan_by_id(scan_id)
        if not scan:
            return jsonify({'error': 'Scan not found'}), 404
        return jsonify(scan)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Settings API endpoints ---
@bp.route('/api/settings', methods=['GET'])
def get_settings_api():
    """Get scanner settings"""
    return jsonify(get_settings())

@bp.route('/api/settings', methods=['POST'])
def update_settings_api():
    """Update scanner settings"""
    try:
        data = request.json
        if 'account_equity' in data:
            update_setting('account_equity', float(data['account_equity']))
        if 'risk_pct' in data:
            update_setting('risk_pct', float(data['risk_pct']))
        if 'max_positions' in data:
            update_setting('max_positions', int(data['max_positions']))

        return jsonify(get_settings()), 200
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
    trades = get_all_calls()
    return jsonify({'trades': trades, 'summary': _calls_summary(trades)})

@bp.route('/api/calls', methods=['POST'])
def api_calls_add():
    try:
        data = request.json or {}

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
        }

        result = add_call(trade)
        if result:
            return jsonify({'ok': True, 'trade': result}), 201
        else:
            return jsonify({'error': 'Failed to add call'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@bp.route('/api/calls/<int:call_id>', methods=['PATCH'])
def api_calls_close(call_id):
    try:
        data = request.json
        calls = get_all_calls()

        # Find the call to update
        trade = None
        for t in calls:
            if t.get('id') == call_id:
                trade = t
                break

        if not trade:
            return jsonify({'error': 'Call not found'}), 404

        status = data.get('status', 'expired')
        updates = {
            'status': status,
            'close_date': data.get('close_date', datetime.now().strftime('%Y-%m-%d'))
        }

        if status == 'expired':
            updates['pnl'] = trade['premium_total']
        elif status == 'called_away':
            price_at_sell = trade.get('stock_price_at_sell', 0)
            appreciation = (trade['strike'] - price_at_sell) * trade['contracts'] * 100
            updates['pnl'] = round(trade['premium_total'] + appreciation, 2)
        else:
            buyback = data.get('buyback_price', 0) * trade['contracts'] * 100
            updates['pnl'] = round(trade['premium_total'] - buyback, 2)
            updates['close_price'] = data.get('buyback_price', 0)

        updates['notes'] = data.get('notes', trade.get('notes', ''))

        result = update_call(call_id, updates)
        if result:
            return jsonify({'ok': True})
        else:
            return jsonify({'error': 'Failed to update call'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/calls/<int:call_id>', methods=['DELETE'])
def api_calls_delete(call_id):
    try:
        if delete_call(call_id):
            return jsonify({'ok': True})
        else:
            return jsonify({'error': 'Failed to delete call'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Health Check ---
@bp.route('/api/health')
def health():
    return jsonify({"status": "ok", "app": "canslim-dashboard"})

# --- Trade Tracker: Stock Positions ---
@bp.route('/api/positions', methods=['GET'])
def api_positions_get():
    positions = get_all_positions()
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
        }

        result = add_position(position)
        if result:
            return jsonify({'ok': True, 'position': result}), 201
        else:
            return jsonify({'error': 'Failed to add position'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
