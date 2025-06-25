"""Flask application factory for the MindPulse Endpoint POC."""

import logging
import os
from typing import Optional, Dict, Tuple, Any
from flask import Flask, request, current_app
from dotenv import load_dotenv

from .config import config
from .services import handle_upload
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
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Determine configuration
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Configure logging
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    else:
        logging.basicConfig(level=logging.DEBUG)
    
    # Register routes
    register_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


def register_routes(app: Flask) -> None:
    """Register all routes with the Flask app."""
    
    @app.route("/api/v1/upload", methods=["POST"])
    def upload() -> Tuple[Dict[str, Any], int]:
        """
        Handle file uploads from Android devices.
        
        Expects files to be sent as multipart/form-data with keys like "file1", "file2", etc.
        
        Returns:
            JSON response with upload status and HTTP status code
        """
        if request.method != "POST":
            return {"error": "Only POST method allowed"}, 405
        
        return handle_upload(request, current_app.config)

    @app.route("/api/v1/health", methods=["GET"])
    def health_check() -> Tuple[Dict[str, Any], int]:
        """
        Health check endpoint.
        
        Returns:
            JSON response indicating service health
        """
        return {"status": "healthy", "service": "mindpulse-endpoint-poc", "version": "v1"}, 200


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