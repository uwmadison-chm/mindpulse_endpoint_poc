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


def parse_filename(filename: str) -> Tuple[str, str, str, str, str]:
    """
    Parse filename to extract components.

    Supports two formats:
    1. New format: {short_hash}_{timestamp}_{type}_{iv}.{ext}
    2. Legacy format: {subject_hash}_{timestamp}_{type}.{ext}

    short_hash: 8 hex digits identifying the enrollment key
    timestamp: ISO 8601 format with timezone or epoch time
    type: data type (e.g., screenshot, gps)
    iv: 24 hex digits (12 bytes) for encryption IV (new format only)

    Returns:
        Tuple of (subject_hash, timestamp, type, iv, extension)
        For legacy format, iv will be empty string
    """
    name_without_ext, ext = filename.rsplit(".", 1)
    parts = name_without_ext.split("_")

    if len(parts) == 4:
        # New format: short_hash_timestamp_type_iv.ext
        short_hash, timestamp, type_str, iv = parts

        # Validate short_hash (8 hex chars)
        if len(short_hash) != 8 or not re.match(r'^[0-9a-f]{8}$', short_hash.lower()):
            raise ValueError(f"Invalid short_hash: expected 8 hex chars, got '{short_hash}'")

        # Validate IV (24 hex chars = 12 bytes)
        if len(iv) != 24 or not re.match(r'^[0-9a-f]{24}$', iv.lower()):
            raise ValueError(f"Invalid IV: expected 24 hex chars, got '{iv}'")

        return short_hash, timestamp, type_str, iv, ext
    elif len(parts) == 3:
        # Legacy format: subject_hash_timestamp_type.ext
        subject_hash, timestamp, type_str = parts
        return subject_hash, timestamp, type_str, "", ext
    else:
        raise ValueError(f"Invalid filename format: {filename}")


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
    ready_dir = upload_path / "ready"
    
    ensure_directory_exists(incoming_dir)
    ensure_directory_exists(ready_dir)
    
    # Group files by subject_hash
    batch_dirs = []
    
    for filenum, file in files.items():
        safe_filename = secure_filename(file.filename)
        logger.debug(f"Processing {filenum}: {safe_filename}")
        try:
            subject_hash, timestamp, type_str, iv, extension = parse_filename(safe_filename)
        except Exception as e:
            logger.warning(f"Error parsing file {filenum}: {safe_filename}: {e}")
            invalid_files.append(f"{filenum}: {safe_filename}")
            continue
        
        # Create batch directory if it doesn't exist
        batch_dir = incoming_dir / subject_hash / timestamp
        batch_dirs.append(batch_dir)
        ensure_directory_exists(batch_dir)
        target = batch_dir / safe_filename
        file.save(target)
        logger.info(f"Saved {target}")
        saved_files.append(target)
    
    for bdir in batch_dirs:
        bname = bdir.name
        dest = ready_dir / bname
        
        result = bdir.rename(dest)
        logger.debug(f"{bname} -> {result}")
        
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

