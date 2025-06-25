"""API v1 routes for MindPulse Endpoint POC."""

import logging
from typing import Dict, Tuple, Any
from flask import request, current_app

from .services import handle_upload

# Set up logging
logger = logging.getLogger(__name__)


def register_api_v1_routes(app):
    """Register v1 API routes with the Flask app."""
    
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