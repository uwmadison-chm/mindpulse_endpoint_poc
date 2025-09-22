"""API v1 routes for MindPulse Endpoint POC."""

import logging
from pathlib import Path
from typing import Dict, Tuple, Any
from flask import request, current_app

from .models import Batch

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

        if not request.files:
            return {"error": "No files found in request"}, 400

        upload_path = current_app.config["UPLOAD_PATH"]

        # Create batch and process files
        batch = Batch.create_batch_dir(upload_path)
        batch.process_files(request.files)

        if not batch.success_files:
            return {"error": "No valid files found in request"}, 400

        # Move to ready directory
        ready_dir = upload_path / "ready"
        batch.move_to_ready(ready_dir)

        logger.info(f"Successfully uploaded {len(batch.success_files)} files to {upload_path}")

        response_data = {
            "message": f"{len(batch.success_files)} files uploaded successfully"
        }

        if batch.failure_files:
            response_data["invalid_files"] = batch.failure_files
            response_data["message"] += f" ({len(batch.failure_files)} invalid files ignored)"

        return response_data, 201

    @app.route("/api/v1/health", methods=["GET"])
    def health_check() -> Tuple[Dict[str, Any], int]:
        """
        Health check endpoint.
        
        Returns:
            JSON response indicating service health
        """
        status_dict = {"status": "healthy", "service": "mindpulse-endpoint-poc", "version": "v1"}
        if app.debug:
            config_dict = {k: str(v) for k, v in app.config.items()}
            status_dict['config_strings'] = config_dict
        return status_dict, 200