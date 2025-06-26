"""Service layer for MindPulse Endpoint POC."""

import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from flask import Request
from werkzeug.exceptions import RequestEntityTooLarge

from .utils import ensure_directory_exists

logger = logging.getLogger(__name__)


def parse_filename(filename: str) -> Tuple[str, str, str]:
    """
    Parse filename to extract subject_hash, timestamp, and extension.
    
    Expected format: {subject_hash}_{timestamp}.{ext}
    subject_hash: 8 hex digits
    timestamp: epoch time with millisecond precision
    
    Returns:
        Tuple of (subject_hash, timestamp, extension) or (None, None, None) if invalid
    """
    pattern = r'^([a-fA-F0-9]{8})_(\d+)\.(.+)$'
    match = re.match(pattern, filename)
    
    if match:
        subject_hash, timestamp, extension = match.groups()
        return subject_hash, timestamp, extension
    else:
        return None, None, None


def collect_files(request: Request) -> List:
    """
    Collect all files from the request, regardless of key.
    
    Args:
        request: Flask request object
        
    Returns:
        List of file objects
    """
    return list(request.files.values())


def save_files_to_batch_directory(files: List, upload_folder: Path) -> Tuple[List[str], List[str]]:
    """
    Save files to batch directories organized by subject_hash in the incoming directory.
    
    Args:
        files: List of file objects
        upload_folder: Base directory to save files to (as Path)
        
    Returns:
        Tuple of (saved_filenames, invalid_filenames)
    """
    saved_files: List[str] = []
    invalid_files: List[str] = []
    
    # Create incoming directory
    incoming_dir = upload_folder / "incoming"
    ensure_directory_exists(str(incoming_dir))
    
    # Group files by subject_hash
    batch_directories: Dict[str, List] = {}
    
    for file in files:
        original_filename = file.filename
        subject_hash, timestamp, extension = parse_filename(original_filename)
        
        if subject_hash is None:
            logger.warning(f"Invalid filename format: {original_filename}")
            invalid_files.append(original_filename)
            continue
        
        # Create batch directory if it doesn't exist
        batch_dir = incoming_dir / subject_hash
        if subject_hash not in batch_directories:
            batch_directories[subject_hash] = []
            ensure_directory_exists(str(batch_dir))
        
        batch_directories[subject_hash].append((file, original_filename))
    
    # Save files to their respective batch directories
    for subject_hash, file_list in batch_directories.items():
        batch_dir = incoming_dir / subject_hash
        
        for file, original_filename in file_list:
            # Use original filename as-is (it's already properly formatted)
            file_path = batch_dir / original_filename
            
            # Handle filename conflicts by adding timestamp if needed
            if file_path.exists():
                name, ext = original_filename.rsplit('.', 1)
                timestamp = str(int(time.time() * 1000))
                unique_filename = f"{name}_{timestamp}.{ext}"
                file_path = batch_dir / unique_filename
                logger.info(f"Filename conflict resolved: {original_filename} -> {unique_filename}")
            
            file.save(str(file_path))
            saved_files.append(f"incoming/{subject_hash}/{original_filename}")
            logger.info(f"Saved file: incoming/{subject_hash}/{original_filename}")
    
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
    try:
        upload_folder = config.get("UPLOAD_FOLDER", Path("/tmp/mindpulse_uploads"))
        
        # Ensure upload directory exists
        ensure_directory_exists(str(upload_folder))
        
        # Collect files
        files = collect_files(request)
        
        if not files:
            return {"error": "No files found in request"}, 400
        
        # Save files to batch directories
        saved_files, invalid_files = save_files_to_batch_directory(files, upload_folder)
        
        if not saved_files:
            return {"error": "No valid files found in request"}, 400
        
        logger.info(f"Successfully uploaded {len(saved_files)} files to {len(set(f.split('/')[0] for f in saved_files))} batch directories")
        
        response_data = {
            "message": f"{len(saved_files)} files uploaded successfully"
        }
        
        if invalid_files:
            response_data["invalid_files"] = invalid_files
            response_data["message"] += f" ({len(invalid_files)} invalid files ignored)"
        
        return response_data, 201

    except RequestEntityTooLarge:
        logger.error("Request entity too large")
        return {"error": "File size exceeds maximum allowed size"}, 413

    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        return {"error": "Internal server error"}, 500 