"""Utility functions for the MindPulse Endpoint POC."""

import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional
from werkzeug.utils import secure_filename


def parse_size_string(size_str: str) -> int:
    """
    Parse a human-readable size string into bytes.
    
    Supports formats like: "16M", "1GB", "512K", "2TB", etc.
    
    Args:
        size_str: Human-readable size string (e.g., "16M", "1GB")
        
    Returns:
        Size in bytes
        
    Raises:
        ValueError: If the size string format is invalid
    """
    if not size_str:
        raise ValueError("Size string cannot be empty")
    
    # Remove any whitespace and convert to uppercase
    size_str = size_str.strip().upper()
    
    # Pattern to match: number + optional unit (K, M, G, T)
    pattern = r'^(\d+(?:\.\d+)?)\s*(K|M|G|T)?B?$'
    match = re.match(pattern, size_str)
    
    if not match:
        raise ValueError(f"Invalid size format: {size_str}. Use format like '16M', '1GB', etc.")
    
    number = float(match.group(1))
    unit = match.group(2) or ''  # Default to bytes if no unit
    
    # Convert to bytes
    multipliers = {
        '': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
    }
    
    return int(number * multipliers[unit])


def ensure_directory_exists(directory_path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory_path: Path to the directory to ensure exists
    """
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def generate_iv() -> bytes:
    """
    Generate a random 12-byte IV for AES encryption.

    Returns:
        12 random bytes suitable for use as AES IV
    """
    return secrets.token_bytes(12)


def generate_filename(short_hash: str, data_type: str, extension: str,
                     timestamp: Optional[str] = None, iv: Optional[bytes] = None) -> str:
    """
    Generate a filename using the new format with IV.

    Format: {short_hash}_{timestamp}_{type}_{iv}.{ext}

    Args:
        short_hash: 8 hex character enrollment key identifier
        data_type: Type of data (e.g., 'screenshot', 'gps')
        extension: File extension without dot (e.g., 'png', 'json')
        timestamp: Optional ISO 8601 timestamp. If None, uses current time
        iv: Optional IV bytes. If None, generates random IV

    Returns:
        Filename string in new format
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    if iv is None:
        iv = generate_iv()

    iv_hex = iv.hex()

    return f"{short_hash}_{timestamp}_{data_type}_{iv_hex}.{extension}"


def validate_filename_format(filename: str) -> bool:
    """
    Validate if filename matches expected format.

    Supports both new and legacy formats:
    - New: {short_hash}_{timestamp}_{type}_{iv}.{ext}
    - Legacy: {subject_hash}_{timestamp}_{type}.{ext}

    Args:
        filename: Filename to validate

    Returns:
        True if filename matches a valid format
    """
    try:
        from .services import parse_filename
        parse_filename(filename)
        return True
    except (ValueError, ImportError):
        return False


def extract_date_from_timestamp(timestamp: str) -> str:
    """
    Extract date in YYYY-MM-DD format from timestamp.

    Handles both ISO 8601 and epoch timestamp formats.

    Args:
        timestamp: Timestamp string (ISO 8601 or epoch)

    Returns:
        Date string in YYYY-MM-DD format
    """
    import re
    from datetime import datetime

    # Try ISO 8601 format first
    iso_match = re.match(r'^(\d{4}-\d{2}-\d{2})', timestamp)
    if iso_match:
        return iso_match.group(1)

    # Try epoch timestamp (milliseconds)
    try:
        # Handle both seconds and milliseconds
        if len(timestamp) > 10:  # Milliseconds
            epoch_time = int(timestamp) / 1000
        else:  # Seconds
            epoch_time = int(timestamp)

        dt = datetime.fromtimestamp(epoch_time)
        return dt.strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        # Fallback: use current date
        return datetime.now().strftime('%Y-%m-%d')


def get_file_type_category(mime_type: str, extension: str, filename_type: str = "") -> str:
    """
    Categorize file into type directory based primarily on filename type.

    Args:
        mime_type: MIME type of the file
        extension: File extension
        filename_type: Type from filename (e.g., 'screenshot', 'gps', 'metadata')

    Returns:
        Directory category name (uses filename type directly when possible)
    """
    # Use filename type directly as the primary organization method
    if filename_type and filename_type.strip():
        # Clean the type string and use it as directory name
        clean_type = filename_type.lower().strip()

        # Only use it if it's a reasonable directory name (alphanumeric + underscore)
        import re
        if re.match(r'^[a-z0-9_]+$', clean_type):
            return clean_type

    # Fallback to MIME type categorization only if filename type is missing/invalid
    if mime_type:
        main_type = mime_type.split('/')[0].lower()
        if main_type == 'image':
            return 'images'
        elif main_type == 'audio':
            return 'audio'
        elif main_type == 'video':
            return 'video'
        elif mime_type in ['application/json', 'text/json']:
            return 'data'

    # Final fallback to extension
    extension = extension.lower().lstrip('.')
    if extension in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff']:
        return 'images'
    elif extension in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
        return 'audio'
    elif extension in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
        return 'video'
    elif extension in ['json', 'csv', 'txt']:
        return 'data'

    # Default category
    return 'other'


def build_organized_path(subject_id: str, timestamp: str, file_type: str,
                        mime_type: str = "", extension: str = "") -> str:
    """
    Build organized file path: ID/date/type/

    Args:
        subject_id: Subject/participant ID
        timestamp: Timestamp from filename
        file_type: Type from filename
        mime_type: MIME type of file
        extension: File extension

    Returns:
        Relative path string (e.g., "b27954ea/2025-09-19/images/")
    """
    date = extract_date_from_timestamp(timestamp)
    category = get_file_type_category(mime_type, extension, file_type)

    return f"{subject_id}/{date}/{category}/"
