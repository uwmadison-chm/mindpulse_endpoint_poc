#!/usr/bin/env python3
"""
Usage: decrypt_file.py <short_hash> <input_file> <output_file>

Simple script to decrypt a single file using an enrollment key.

Arguments:
    <short_hash>    8-character hex short hash identifying the enrollment key
    <input_file>    Path to encrypted file to decrypt
    <output_file>   Path where decrypted file should be saved

The script will:
1. Load the enrollment key for the given short hash
2. Parse the filename to extract the IV
3. Decrypt the file and save it to the output path

Example:
    decrypt_file.py 8ce4d5e6 encrypted_file.jpg decrypted_file.jpg
"""

import logging
import sys
from pathlib import Path

from docopt import docopt

# Add the parent directory to sys.path to import the models and app
sys.path.insert(0, str(Path(__file__).parent.parent))

from mindpulse_endpoint_poc.models import EncryptedMPFile, EnrollmentKey, Decryptor
from app import create_app

logger = logging.getLogger(__name__)


def main():
    """Main function to decrypt a single file."""
    args = docopt(str(__doc__))

    # Configure logging - always verbose
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    short_hash = args["<short_hash>"]
    input_file = Path(args["<input_file>"])
    output_file = Path(args["<output_file>"])

    logger.info(f"Starting file decryption")
    logger.info(f"Short hash: {short_hash}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output file: {output_file}")

    # Validate input file exists
    if not input_file.exists():
        logger.error(f"Input file does not exist: {input_file}")
        sys.exit(1)

    try:
        # Create Flask app to get configuration
        app = create_app()
        keys_path = app.config["KEYS_PATH"]
        logger.info(f"Using keys path: {keys_path}")

        # Parse the encrypted file to get IV and other info
        logger.info(f"Parsing encrypted file: {input_file.name}")
        mpfile = EncryptedMPFile.from_filename(input_file)
        logger.info(f"Parsed file info - Short ID: {mpfile.short_id}, Type: {mpfile.type}, Created: {mpfile.created_at}")
        logger.info(f"IV: {mpfile.iv.hex()}")

        # Verify the short hash matches
        if mpfile.short_id != short_hash:
            logger.warning(f"Short hash mismatch: filename has {mpfile.short_id}, you specified {short_hash}")
            logger.info(f"Using short hash from filename: {mpfile.short_id}")
            short_hash = mpfile.short_id

        # Load the enrollment key
        logger.info(f"Loading enrollment key for: {short_hash}")
        key = EnrollmentKey.load_for_short_sha(keys_path, short_hash)
        logger.info(f"Successfully loaded key")

        # Create decryptor
        logger.info(f"Creating decryptor")
        decryptor = Decryptor.from_enrollment_key(key)

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Decrypt file
        logger.info(f"Decrypting file...")
        decryptor.decrypt_to_path(mpfile, output_file)

        logger.info(f"Successfully decrypted file to: {output_file}")
        logger.info(f"Output file size: {output_file.stat().st_size} bytes")

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid filename format: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()