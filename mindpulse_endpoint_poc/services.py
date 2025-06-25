"""Service layer for MindPulse Endpoint POC."""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from flask import Request
from werkzeug.exceptions import RequestEntityTooLarge

from .utils import allowed_file, get_secure_filename, ensure_directory_exists, get_unique_filename

logger = logging.getLogger(__name__)


def validate_and_collect_files(request: Request, config: dict) -> Tuple[List, List[str]]:
    """
    Validate and collect files from the request.
    
    Args:
        request: Flask request object
        config: Flask app config dictionary
        
    Returns:
        Tuple of (files, filenames) lists
    """
    max_files = config.get("MAX_FILES_PER_REQUEST", 1000)
    allowed_extensions = config.get("ALLOWED_EXTENSIONS", {".png", ".jpg", ".jpeg", ".gif", ".bmp"})
    
    files: List = []
    filenames: List[str] = []
    
    for i in range(1, max_files + 1):
        file_key = f"file{i}"
        file = request.files.get(file_key)
        
        if not file:
            break
            
        # Validate file extension
        if not allowed_file(file.filename, allowed_extensions):
            logger.warning(f"Rejected file with invalid extension: {file.filename}")
            continue
        
        # Get secure filename
        secure_name = get_secure_filename(file.filename)
        if not secure_name:
            logger.warning(f"Could not create secure filename for: {file.filename}")
            continue
        
        files.append(file)
        filenames.append(secure_name)
    
    return files, filenames


def save_files_to_disk(files: List, filenames: List[str], upload_folder: str) -> Tuple[List[str], Optional[str]]:
    """
    Save files to disk and return list of saved filenames.
    
    Args:
        files: List of file objects
        filenames: List of filenames
        upload_folder: Directory to save files to
        
    Returns:
        Tuple of (saved_filenames, error_message). error_message is None if successful.
    """
    saved_files: List[str] = []
    
    for file, filename in zip(files, filenames):
        try:
            # Ensure unique filename
            unique_filename = get_unique_filename(upload_folder, filename)
            file_path = Path(upload_folder) / unique_filename
            file.save(str(file_path))
            saved_files.append(unique_filename)
            logger.info(f"Successfully saved file: {unique_filename}")
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            return [], f"Failed to save file {filename}"
    
    return saved_files, None


def verify_files_exist(saved_files: List[str], upload_folder: str) -> Optional[str]:
    """
    Verify that all saved files actually exist on disk.
    
    Args:
        saved_files: List of filenames that should exist
        upload_folder: Directory where files should be
        
    Returns:
        Error message if any files are missing, None if all exist
    """
    missing_files = []
    for filename in saved_files:
        file_path = Path(upload_folder) / filename
        if not file_path.exists():
            missing_files.append(filename)
    
    if missing_files:
        logger.error(f"Files not found after save: {missing_files}")
        return f"Files not found after save: {missing_files}"
    
    return None


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
        upload_folder = config.get("UPLOAD_FOLDER", "/tmp/mindpulse_uploads")
        
        # Ensure upload directory exists
        ensure_directory_exists(upload_folder)
        
        # Validate and collect files
        files, filenames = validate_and_collect_files(request, config)
        
        if not files:
            return {"error": "No valid files found in request"}, 400
        
        # Save files to disk
        saved_files, save_error = save_files_to_disk(files, filenames, upload_folder)
        if save_error:
            return {"error": save_error}, 500
        
        # Verify files were saved
        verify_error = verify_files_exist(saved_files, upload_folder)
        if verify_error:
            return {"error": verify_error}, 500
        
        logger.info(f"Successfully uploaded {len(saved_files)} files")
        return {
            "message": f"{len(saved_files)} files uploaded successfully",
            "files": saved_files,
            "upload_folder": upload_folder
        }, 201

    except RequestEntityTooLarge:
        logger.error("Request entity too large")
        return {"error": "File size exceeds maximum allowed size"}, 413

    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        return {"error": "Internal server error"}, 500 