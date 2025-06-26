"""Utility functions for the MindPulse Endpoint POC."""

import re
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


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    """
    Check if a filename has an allowed extension.
    
    Args:
        filename: The filename to check
        allowed_extensions: Set of allowed file extensions (including the dot)
        
    Returns:
        True if the file extension is allowed, False otherwise
    """
    return Path(filename).suffix.lower() in allowed_extensions


def get_secure_filename(filename: str) -> str:
    """
    Get a secure version of the filename.
    
    Args:
        filename: The original filename
        
    Returns:
        A secure version of the filename
    """
    return secure_filename(filename)


def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists
    """
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def get_unique_filename(base_path: str, filename: str) -> str:
    """
    Get a unique filename by appending a number if the file already exists.
    
    Args:
        base_path: The base directory path
        filename: The desired filename
        
    Returns:
        A unique filename that doesn't conflict with existing files
    """
    file_path = Path(base_path) / filename
    counter = 1
    
    while file_path.exists():
        name, ext = Path(filename).stem, Path(filename).suffix
        new_filename = f"{name}_{counter}{ext}"
        file_path = Path(base_path) / new_filename
        counter += 1
    
    return file_path.name 