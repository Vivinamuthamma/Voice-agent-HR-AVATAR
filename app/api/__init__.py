from flask import Flask

def register_routes(app: Flask):
    from .health import health_bp
    from .sessions import sessions_bp
    from .files import files_bp
    from .reports import reports_bp
    from .dashboard import dashboard_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(dashboard_bp)
