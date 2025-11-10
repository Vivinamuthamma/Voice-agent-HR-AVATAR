from flask import Flask, current_app, render_template, g
from flask_cors import CORS
import logging
from dotenv import load_dotenv
from pathlib import Path

from async_manager import AsyncLiveKitManager



# Load environment variables from keys.env
dotenv_path = Path(__file__).parent / 'keys.env'
load_dotenv(dotenv_path=dotenv_path)
import os
from app.core.config import Config
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

def create_app():
    """Application factory for Flask app."""
    setup_logging()

    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Initialize configuration
    config = Config()
    app.config.from_object(config)

    # Secure CORS configuration - allow only specific origins in production
    if os.getenv('FLASK_ENV') == 'production':
        CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS[0]}})
    else:

        CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})

    # Setup TLS
    config.setup_tls()

    # Import and register blueprints
    from app.api import register_routes
    register_routes(app)

    @app.route('/')
    def index():
        """Serve the main application"""
        return render_template('index.html')

    @app.before_request
    def before_request():
        if 'livekit_manager' not in g:
            try:
                # Check if LiveKit credentials are available
                if not all([current_app.config.get('LIVEKIT_API_KEY'), current_app.config.get('LIVEKIT_API_SECRET'), current_app.config.get('LIVEKIT_URL')]):
                    logger.error("Missing LiveKit configuration - check environment variables")
                    g.livekit_manager = None
                    return

                g.livekit_manager = AsyncLiveKitManager(
                    url=current_app.config['LIVEKIT_URL'],
                    api_key=current_app.config['LIVEKIT_API_KEY'],
                    api_secret=current_app.config['LIVEKIT_API_SECRET']
                )
                logger.debug("LiveKit manager created for request")
            except Exception as e:
                g.livekit_manager = None
                logger.error(f"LiveKit manager initialization failed for request: {e}", exc_info=True)

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Endpoint not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return {"error": "Internal server error"}, 500

    return app
