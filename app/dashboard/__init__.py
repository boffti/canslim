from .routes import bp as dashboard_bp

def init_app(app):
    app.register_blueprint(dashboard_bp)
