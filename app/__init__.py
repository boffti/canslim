from flask import Flask
from app.extensions import scheduler, init_supabase
from app.dashboard import init_app as init_dashboard
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for development
    
    # Config
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SUPABASE_URL'] = os.environ.get("SUPABASE_URL")
    app.config['SUPABASE_KEY'] = os.environ.get("SUPABASE_KEY")
    
    # Initialize Extensions
    init_supabase(app)
    scheduler.init_app(app)
    
    # Register Blueprints
    init_dashboard(app)
    
    # Load Tasks (This registers the cron jobs)
    try:
        from app import tasks
        scheduler.start()
        print("Scheduler started")
    except Exception as e:
        print(f"Failed to start scheduler: {e}")
    
    # Root route to check if app is running (Dashboard is at / so this might be redundant or conflict if dashboard has /)
    # Since dashboard has @bp.route('/'), and is registered at root, we don't need a separate index here.
    # However, let's add a health check.
    @app.route("/system/health")
    def system_health():
        return "DeepDiver System Active", 200
        
    return app
