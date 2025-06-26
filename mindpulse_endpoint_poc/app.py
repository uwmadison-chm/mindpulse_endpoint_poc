"""Flask application factory for the MindPulse Endpoint POC."""

import logging
from typing import Optional
from flask import Flask

from .config import get_config
from .api_v1 import register_api_v1_routes
from . import services  # Import to ensure module is loaded


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory function.
    
    Args:
        config_name: Name of the configuration to use. If None, will use
                    FLASK_ENV environment variable or default to 'development'
    
    Returns:
        Configured Flask application instance
    """
    # Get configuration using shared function
    config_class = get_config(config_name)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    # Configure logging
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    else:
        logging.basicConfig(level=logging.DEBUG)
    
    # Register routes
    register_api_v1_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


def register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for the application.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return {"error": "Method not allowed"}, 405
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return {"error": "Request entity too large"}, 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return {"error": "Internal server error"}, 500 