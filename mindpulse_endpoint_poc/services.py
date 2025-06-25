"""Service layer for MindPulse Endpoint POC."""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
from flask import Request
from werkzeug.exceptions import RequestEntityTooLarge

from .utils import get_secure_filename, ensure_directory_exists, get_unique_filename

logger = logging.getLogger(__name__)


def collect_files(request: Request) -> List:
    """
    Collect all files from the request, regardless of key.
    
    Args:
        request: Flask request object
    Returns:
        List of file objects
    """
    return list(request.files.values())


def save_files_to_disk(files: List, upload_folder: Path) -> List[str]:
    """
    Save files to disk and return list of saved filenames.
    
    Args:
        files: List of file objects
        upload_folder: Directory to save files to (as Path)
        
    Returns:
        List of saved filenames
    """
    saved_files: List[str] = []
    
    for file in files:
        # Get secure filename from the file object
        secure_name = get_secure_filename(file.filename)
        
        # Ensure unique filename
        unique_filename = get_unique_filename(str(upload_folder), secure_name)
        file_path = upload_folder / unique_filename
        file.save(str(file_path))
        saved_files.append(unique_filename)
        logger.info(f"Successfully saved file: {unique_filename}")
    
    return saved_files


def handle_upload(request: Request, config: dict) -> Tuple[Dict[str, Any], int]:
    """
    Handle file uploads from Android devices.

    Args:
        request: Flask request object
        config: Flask app config dictionary

    Returns:
        JSON-serializable dict and HTTP status code
    """
    try:
        upload_folder_str = config.get("UPLOAD_FOLDER", "/tmp/mindpulse_uploads")
        upload_folder = Path(upload_folder_str)
        
        # Ensure upload directory exists
        ensure_directory_exists(str(upload_folder))
        
        # Collect files
        files = collect_files(request)
        
        if not files:
            return {"error": "No files found in request"}, 400
        
        # Save files to disk
        saved_files = save_files_to_disk(files, upload_folder)
        
        logger.info(f"Successfully uploaded {len(saved_files)} files")
        return {
            "message": f"{len(saved_files)} files uploaded successfully",
            "files": saved_files,
            "upload_folder": str(upload_folder)
        }, 201

    except RequestEntityTooLarge:
        logger.error("Request entity too large")
        return {"error": "File size exceeds maximum allowed size"}, 413

    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        return {"error": "Internal server error"}, 500 