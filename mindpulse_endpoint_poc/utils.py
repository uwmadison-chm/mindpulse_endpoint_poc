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


def ensure_directory_exists(directory_path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists
    """
    Path(directory_path).mkdir(parents=True, exist_ok=True)
