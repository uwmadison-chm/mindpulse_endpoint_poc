"""Flask application factory for the MindPulse Endpoint POC."""

import logging
from typing import Optional
from pathlib import Path

from flask import Flask

from mindpulse_endpoint_poc import initial_settings
from mindpulse_endpoint_poc.api_v1 import register_api_v1_routes
from mindpulse_endpoint_poc import admin_routes
from mindpulse_endpoint_poc import utils

def create_app() -> Flask:
    """
    Application factory function.
    Configuration is set using MINDPULSE environment variables:
    
    
    Returns:
        Configured Flask application instance
    """
    # Get configuration using shared function
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(initial_settings)
    app.config.from_prefixed_env(prefix='MINDPULSE')
    initialize_state(app.config)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )
    if app.debug or app.testing:
       app.logger.setLevel(logging.DEBUG)
    
    app.logger.debug(f"App config: {app.config}")
    
    # Register routes
    register_api_v1_routes(app)
    
    admin_routes.register(app)
    
    # Register error handlers
    register_error_handlers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for the application.
    
    Args:
        app: Flask application instance
    """
    import traceback
    
    def add_stacktrace_if_debug(dict_in):
        if app.debug:
            dict_in["traceback"] = traceback.format_stack()
        return dict_in
        
    @app.errorhandler(404)
    def not_found(error):
        app.logger.error("404", exc_info=(error))
        err_dict = add_stacktrace_if_debug({"error": "Not found"})
        return err_dict, 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        app.logger.error("405", exc_info=(error))
        err_dict = add_stacktrace_if_debug({"error": "Method not allowed"})
        return err_dict, 405
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.error("413", exc_info=(error))
        err_dict = add_stacktrace_if_debug({"error": "Request entity too large"})
        return err_dict, 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error("500", exc_info=(error))
        err_dict = add_stacktrace_if_debug({"error": "Other error"})
        return err_dict, 500 
        

def initialize_state(config: dict) -> None:
    max_content_length = utils.parse_size_string(config['MAX_CONTENT_LENGTH'])
    config['MAX_CONTENT_LENGTH_RAW'] = config['MAX_CONTENT_LENGTH']
    config['MAX_CONTENT_LENGTH'] = max_content_length
    
    config['UPLOAD_PATH_RAW'] = config['UPLOAD_PATH']
    upload_path = Path(config['UPLOAD_PATH'])
    upload_path.mkdir(exist_ok=True, parents=True)
    config['UPLOAD_PATH'] = upload_path
    config['INCOMING_PATH'] = upload_path / 'incoming'
    config['READY_PATH'] = upload_path / 'ready'
    
    config['KEYS_PATH_RAW'] = config['KEYS_PATH']
    keys_path = Path(config['KEYS_PATH'])
    keys_path.mkdir(exist_ok=True, parents=True)
    config['KEYS_PATH'] = keys_path


def pathify(config: dict, key: str) -> None:
    path_str = config[key]
    path_path = Path(path_str)
    path_path.mkdir(exist_ok=True, parents=True)
    raw_key = f"{key}_RAW"
    config[raw_key] = path_str
    config[key] = path_path


app = create_app()