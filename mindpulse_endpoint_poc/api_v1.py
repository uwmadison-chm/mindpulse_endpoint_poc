"""API v1 routes for MindPulse Endpoint POC."""

import logging
from pathlib import Path
from typing import Dict, Tuple, Any
from flask import request

from .models import Batch

logger = logging.getLogger(__name__)


def _build_message(batch: Batch) -> str:
    """Generate appropriate message for batch upload results."""
    num_success = len(batch.success_files)
    num_errors = len(batch.error_messages)

    if num_success > 0 and num_errors == 0:
        return f"{num_success} file{'s' if num_success != 1 else ''} uploaded successfully"
    elif num_success == 0 and num_errors > 0:
        return f"0 files uploaded, {num_errors} error{'s' if num_errors != 1 else ''}"
    else:
        return f"{num_success} file{'s' if num_success != 1 else ''} uploaded successfully, {num_errors} error{'s' if num_errors != 1 else ''}"


def _get_status_code(batch: Batch) -> int:
    """Determine HTTP status code based on batch upload results."""
    num_success = len(batch.success_files)
    num_errors = len(batch.error_messages)

    if num_errors == 0:
        return 201
    elif num_success == 0:
        return 400
    else:
        return 207


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

        # Handle empty request
        if not request.files:
            return {
                "message": "No files provided",
                "successes": [],
                "errors": []
            }, 200

        # Create batch and process files
        batch = Batch.setup_for_transfer(
            app.config["INCOMING_BATCH_PATH"], app.config["COMPLETE_BATCH_PATH"]
        )
        batch.process_batch(request.files)

        # Build response
        successes = [mpfile.path.name for mpfile in batch.success_files]
        errors = batch.error_messages

        resp_data = {
            "message": _build_message(batch),
            "successes": successes,
            "errors": errors
        }

        status_code = _get_status_code(batch)

        if len(batch.success_files) > 0:
            logger.info(
                f"Successfully uploaded {len(batch.success_files)} files to {batch.batch_path}"
            )

        return resp_data, status_code

    @app.route("/api/v1/health", methods=["GET"])
    def health_check() -> Tuple[Dict[str, Any], int]:
        """
        Health check endpoint.

        Returns:
            JSON response indicating service health
        """
        status_dict = {
            "status": "healthy",
            "service": "mindpulse-endpoint-poc",
            "version": "v1",
        }
        if app.debug:
            config_dict = {k: str(v) for k, v in app.config.items()}
            status_dict["config_strings"] = config_dict
        return status_dict, 200
