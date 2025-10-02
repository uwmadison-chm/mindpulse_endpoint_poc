#!/usr/bin/env python3
"""Generate and submit encrypted test files to MindPulse API endpoint.

Usage:
    submit_test_files.py [options] <short_key> <api_endpoint> <source_files>...

Arguments:
    <short_key>         8-character hex short key (e.g., 'b27954ea')
    <api_endpoint>      API endpoint base URL (e.g., 'http://localhost:5001')
    <source_files>      Source files to encrypt and submit

Options:
    --days-back=N       Days back to spread timestamps [default: 1]
    -v, --verbose       Enable verbose logging
    -h, --help          Show this help message

Examples:
    submit_test_files.py b27954ea http://localhost:5001 test_data/sample1.png test_data/data.json
    submit_test_files.py b27954ea http://localhost:5001 test_data/* --verbose
"""

import logging
import random
import requests
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

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
        return "screenshot"
    elif ext in [".json", ".xml", ".csv"]:
        return "metadata"
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
    # Format timestamp without microseconds but with timezone offset, remove colons for filename compatibility
    timestamp_str = timestamp.replace(microsecond=0).isoformat().replace(":", "")
    iv_hex = iv.hex()
    return f"{short_key}_{timestamp_str}_{file_type}_{iv_hex}{original_ext}"


def create_encrypted_files(
    short_key: str, source_files: List[str], days_back: int = 7
) -> List[Path]:
    """
    Create encrypted files in a temporary directory.

    Args:
        short_key: 8-character hex short key
        source_files: List of source file paths
        days_back: Days back to spread timestamps

    Returns:
        List of paths to encrypted files
    """
    # Create Flask app to get configuration
    app = create_app()

    with app.app_context():
        keys_path = app.config["KEYS_PATH"]
        logger.debug(f"Using keys path: {keys_path}")

        # Load enrollment key
        try:
            enrollment_key = models.EnrollmentKey.load_for_short_sha(
                keys_path, short_key
            )
            logger.info(f"Loaded enrollment key: {enrollment_key.short_sha}")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Enrollment key file not found for short key: {short_key}"
            )

        # Create encryptor
        encryptor = models.Encryptor.from_enrollment_key(enrollment_key)

        # Generate timestamps for each source file
        count = len(source_files)
        timestamps = generate_plausible_timestamps(count, days_back)

        # Create temporary directory for encrypted files
        temp_dir = Path(tempfile.mkdtemp())
        logger.debug(f"Created temporary directory: {temp_dir}")

        encrypted_files = []

        for i, source_file_path in enumerate(source_files):
            # Use the specific source file
            source_file = Path(source_file_path)
            timestamp = timestamps[i]

            # Determine file type
            file_type = get_file_type_from_extension(source_file)

            # Encrypt the file
            logger.debug(f"Encrypting {source_file}")
            temp_encrypted = temp_dir / f"temp_{i}"
            iv = encryptor.encrypt_file(source_file, temp_encrypted)

            # Generate proper filename
            encrypted_filename = generate_encrypted_filename(
                short_key, timestamp, file_type, iv, source_file.suffix
            )

            # Move to final location
            final_path = temp_dir / encrypted_filename
            temp_encrypted.rename(final_path)

            encrypted_files.append(final_path)
            logger.info(f"Created encrypted file: {encrypted_filename}")

        return encrypted_files


def submit_files_to_api(
    api_endpoint: str, encrypted_files: List[Path]
) -> Dict[str, Any]:
    """
    Submit encrypted files to the API endpoint.

    Args:
        api_endpoint: Base URL of the API (e.g., http://localhost:5000)
        encrypted_files: List of encrypted file paths

    Returns:
        API response as dictionary
    """
    upload_url = f"{api_endpoint}/api/v1/upload"

    # Prepare files for upload
    files_dict = {}
    for i, file_path in enumerate(encrypted_files):
        file_key = f"file{i+1}"
        files_dict[file_key] = (
            file_path.name,
            open(file_path, "rb"),
            "application/octet-stream",
        )

    try:
        logger.info(f"Submitting {len(encrypted_files)} files to {upload_url}")

        # Log what we're sending
        print("\n=== Files Being Sent to Server ===")
        for file_key, (filename, file_handle, content_type) in files_dict.items():
            file_size = file_handle.seek(0, 2)  # Get file size
            file_handle.seek(0)  # Reset file pointer
            logger.info(f"{file_key}: {filename} ({file_size} bytes)")
        print()

        response = requests.post(upload_url, files=files_dict)

        # Close all file handles
        for file_tuple in files_dict.values():
            file_tuple[1].close()

        logger.info(f"API response: {response.status_code}")

        if response.status_code in [200, 201]:
            response_data = response.json()
            logger.info(
                f"Upload successful: {response_data.get('message', 'No message')}"
            )
            return response_data
        else:
            logger.error(f"Upload failed with status {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return {"error": f"HTTP {response.status_code}", "details": response.text}

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"error": "Request failed", "details": str(e)}

    except Exception as e:
        # Make sure we close file handles even if something goes wrong
        for file_tuple in files_dict.values():
            try:
                file_tuple[1].close()
            except:
                pass
        raise


def cleanup_temp_files(encrypted_files: List[Path]):
    """Clean up temporary encrypted files."""
    if encrypted_files:
        temp_dir = encrypted_files[0].parent
        try:
            for file_path in encrypted_files:
                file_path.unlink(missing_ok=True)
            temp_dir.rmdir()
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")


def main():
    args = docopt(__doc__)

    # Configure logging
    log_level = logging.DEBUG if args["--verbose"] else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Extract arguments
    short_key = args["<short_key>"]
    api_endpoint = args["<api_endpoint>"]
    source_file_paths = args["<source_files>"]
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

    # Validate source files exist
    source_files = []
    for file_path in source_file_paths:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Source file does not exist: {file_path}")
            sys.exit(1)
        source_files.append(str(path))

    if not source_files:
        logger.error("No valid source files provided")
        sys.exit(1)

    logger.info(f"Found {len(source_files)} source files")
    logger.info(f"Will encrypt {len(source_files)} files and submit to {api_endpoint}")

    encrypted_files = []

    try:
        # Create encrypted files
        encrypted_files = create_encrypted_files(short_key, source_files, days_back)

        # Submit to API
        response = submit_files_to_api(api_endpoint, encrypted_files)

        # Display results
        if "error" in response:
            logger.error(f"Submission failed: {response['error']}")
            if "details" in response:
                logger.error(f"Details: {response['details']}")
            sys.exit(1)
        else:
            logger.info("✅ Submission successful!")
            logger.info(f"Message: {response.get('message', 'No message')}")

            if "invalid_files" in response:
                logger.warning(f"Invalid files: {response['invalid_files']}")

        # Print complete server response
        print("\n=== Complete Server Response ===")
        import json
        print(json.dumps(response, indent=2, default=str))

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    finally:
        # Clean up temporary files
        if encrypted_files:
            cleanup_temp_files(encrypted_files)


if __name__ == "__main__":
    main()
