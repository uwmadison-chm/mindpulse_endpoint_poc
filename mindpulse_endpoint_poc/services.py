"""Service layer for MindPulse Endpoint POC."""

import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from flask import Request
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from .utils import ensure_directory_exists

logger = logging.getLogger(__name__)


def parse_filename(filename: str) -> Tuple[str, str, str, str]:
    """
    Parse filename to extract subject_hash, timestamp, and extension.
    
    Expected format: {subject_hash}_{timestamp}_{type}.{ext}
    subject_hash: 8 hex digits
    timestamp: epoch time with millisecond precision
    
    Returns:
        Tuple of (subject_hash, timestamp, type, extension)
    """
    ppt_hash, epochtime, typeext = filename.split("_")
    type, ext = typeext.split(".")
    return ppt_hash, epochtime, type, ext


def save_files_to_batch_directory(files: List, upload_path: Path) -> Tuple[List[str], List[str]]:
    """
    Save files to batch directories organized by subject_hash in the incoming directory.
    
    Args:
        files: List of file objects
        upload_path: Base directory to save files to (as Path)
        
    Returns:
        Tuple of (saved_filenames, invalid_filenames)
    """
    saved_files: List[str] = []
    invalid_files: List[str] = []
    
    # Create incoming directory
    incoming_dir = upload_path / "incoming"
    ensure_directory_exists(incoming_dir)
    
    # Group files by subject_hash
    batch_directories: Dict[str, List] = {}
    
    for filenum, file in files.items():
        safe_filename = secure_filename(file.filename)
        logger.debug(f"Processing {filenum}: {safe_filename}")
        try:
            subject_hash, timestamp, type, extension = parse_filename(safe_filename)
        except Exception as e:
            logger.warning(f"Error parsing file {filenum}: {safe_filename}")
            invalid_files.append(f"{filenum}: {safe_filename}")
            continue
        
        # Create batch directory if it doesn't exist
        batch_dir = incoming_dir / subject_hash / timestamp
        ensure_directory_exists(batch_dir)
        target = batch_dir / safe_filename
        file.save(target)
        logger.info(f"Saved {target}")
        saved_files.append(target)
                
    return saved_files, invalid_files


def handle_upload(request: Request, config: dict) -> Tuple[Dict[str, Any], int]:
    """
    Handle file uploads from Android devices.

    Args:
        request: Flask request object
        config: Flask app config dictionary

    Returns:
        JSON-serializable dict and HTTP status code
    """
    upload_path = config["UPLOAD_PATH"]
    
    if not request.files:
        return {"error": "No files found in request"}, 400
    
    # Save files to batch directories
    saved_files, invalid_files = save_files_to_batch_directory(request.files, upload_path)
    
    if not saved_files:
        return {"error": "No valid files found in request"}, 400
    
    logger.info(f"Successfully uploaded {len(saved_files)} files to {upload_path}")
    
    response_data = {
        "message": f"{len(saved_files)} files uploaded successfully"
    }
    
    if invalid_files:
        response_data["invalid_files"] = invalid_files
        response_data["message"] += f" ({len(invalid_files)} invalid files ignored)"
    
    return response_data, 201

