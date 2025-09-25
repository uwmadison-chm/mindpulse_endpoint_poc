#!/usr/bin/env python3
"""Generate encrypted test files for MindPulse endpoint POC.

Usage:
    generate_test_files.py [options] <short_key> <output_dir> <input>...

Arguments:
    <short_key>         8-character hex short key (e.g., 'b27954ea')
    <output_dir>        Output directory for encrypted files
    <input>             Input files to encrypt

Options:
    --days-back=N       Days back to spread timestamps [default: 1]
    -v, --verbose       Enable verbose logging
    -h, --help          Show this help message

Examples:
    generate_test_files.py b27954ea output/ test_data/sample1.png test_data/data.json
    generate_test_files.py --verbose b27954ea output/ test_data/*
"""

import glob
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from docopt import docopt

# Add the parent directory to sys.path to import the models
sys.path.insert(0, str(Path(__file__).parent.parent))

from mindpulse_endpoint_poc import models
from app import create_app

logger = logging.getLogger(__name__)


def generate_plausible_timestamps(count: int, days_back: int = 7) -> List[datetime]:
    """
    Generate plausible timestamps spread over recent days with timezone offset.

    Args:
        count: Number of timestamps to generate
        days_back: How many days back to spread timestamps over

    Returns:
        List of datetime objects with local timezone
    """
    # Use local timezone
    local_tz = datetime.now().astimezone().tzinfo
    now = datetime.now(local_tz)
    start_time = now - timedelta(days=days_back)

    timestamps = []
    for i in range(count):
        # Spread timestamps randomly over the time period
        random_seconds = random.randint(0, int((now - start_time).total_seconds()))
        timestamp = start_time + timedelta(seconds=random_seconds)
        timestamps.append(timestamp)

    # Sort timestamps chronologically
    timestamps.sort()
    return timestamps


def get_file_type_from_extension(file_path: Path) -> str:
    """
    Get file type identifier from file extension.

    Args:
        file_path: Path to the file

    Returns:
        File type string (e.g., 'image', 'data', 'text')
    """
    ext = file_path.suffix.lower()

    if ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"]:
        return "image"
    elif ext in [".json", ".xml", ".csv"]:
        return "data"
    elif ext in [".txt", ".log", ".md"]:
        return "text"
    else:
        return "file"


def generate_encrypted_filename(
    short_key: str, timestamp: datetime, file_type: str, iv: bytes, original_ext: str
) -> str:
    """
    Generate the properly formatted encrypted filename.

    Format: {short_id}_{created_at}_{type}_{iv}.ext

    Args:
        short_key: 8-character hex short key
        timestamp: File creation timestamp (with timezone)
        file_type: Type of file (image, data, etc.)
        iv: Initialization vector bytes
        original_ext: Original file extension

    Returns:
        Formatted filename
    """
    # Format timestamp without microseconds but with timezone offset
    timestamp_str = timestamp.replace(microsecond=0).isoformat()
    iv_hex = iv.hex()
    return f"{short_key}_{timestamp_str}_{file_type}_{iv_hex}{original_ext}"


def main():
    args = docopt(__doc__)

    # Configure logging
    log_level = logging.DEBUG if args["--verbose"] else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Extract arguments
    short_key = args["<short_key>"]
    output_dir = args["<output_dir>"]
    input_files = args["<input>"]
    days_back = int(args["--days-back"])

    # Validate short_key format
    if len(short_key) != 8:
        logger.error("Short key must be exactly 8 characters")
        sys.exit(1)

    try:
        int(short_key, 16)  # Validate hex format
    except ValueError:
        logger.error("Short key must be valid hexadecimal")
        sys.exit(1)

    # Create Flask app to get configuration
    app = create_app()

    with app.app_context():
        keys_path = app.config["KEYS_PATH"]
        logger.info(f"Using keys path: {keys_path}")

        # Load enrollment key
        try:
            enrollment_key = models.EnrollmentKey.load_for_short_sha(
                keys_path, short_key
            )
            logger.info(f"Loaded enrollment key: {enrollment_key.short_sha}")
        except FileNotFoundError:
            logger.error(f"Enrollment key file not found for short key: {short_key}")
            logger.error(f"Make sure {keys_path}/{short_key}.key exists")
            sys.exit(1)

        # Create encryptor
        encryptor = models.Encryptor.from_enrollment_key(enrollment_key)

        # Validate input files exist
        source_files = []
        for file_path in input_files:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"Input file does not exist: {file_path}")
                sys.exit(1)
            source_files.append(path)

        if not source_files:
            logger.error("No valid input files provided")
            sys.exit(1)

        logger.info(f"Found {len(source_files)} input files")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate timestamps for each input file
        count = len(source_files)
        timestamps = generate_plausible_timestamps(count, days_back)

        # Generate encrypted files
        generated_count = 0
        for i, source_file in enumerate(source_files):
            timestamp = timestamps[i]

            # Determine file type
            file_type = get_file_type_from_extension(source_file)

            # Encrypt the file
            logger.debug(f"Encrypting {source_file}")
            iv = encryptor.encrypt_file(source_file, Path("/tmp/temp_encrypted"))

            # Generate proper filename
            encrypted_filename = generate_encrypted_filename(
                short_key, timestamp, file_type, iv, source_file.suffix
            )

            # Move to final location
            final_path = output_path / encrypted_filename
            Path("/tmp/temp_encrypted").rename(final_path)

            logger.info(f"Generated: {encrypted_filename}")
            generated_count += 1

        logger.info(
            f"Successfully generated {generated_count} encrypted files in {output_path}"
        )


if __name__ == "__main__":
    main()
