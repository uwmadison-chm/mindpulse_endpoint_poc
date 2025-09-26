#!/usr/bin/env python3
"""
Usage: process_batches.py [options]

This script watches for directories to come into the COMPLETE_BATCH_PATH path
and when it does:

set <batch_name> to the basename of the directory

* Moves the directory to PROCESSING_PATH/in/<batch_name>
* Creates PROCESSING_PATH/out/<batch_name>
* For each file in the in path:
  * Find the enrollment key for it
  * Set the target path to be {short_hash}/{date_part_of_timestamp}/{type}/{filename_without_iv}.ext
  * Decrypt the file to the target path

So, if our batch is in tmp1234 and contains:
8ce4d5e6_2025-09-20T092542-0500_image_5ea30e9f40ce2e43d0b66c11c8324b05.png
8ce4d5e6_2025-09-21T172517-0500_metadata_101351bfd5e3812e8c14e5a7a46dd63b.json

we will get, in out/tmp1234:
8ce4d5e6/2025-09-20/image/8ce4d5e6_2025-09-20T092542-0500_image.png
8ce4d5e6/2025-09-20/metadata/8ce4d5e6_2025-09-21T172517-0500_metadata.json


After that is complete, we'll move out/tmp1234 to READY_FOR_UPLOAD_PATH/


Options:
  --debug       Print debugging information
"""

import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Any

from docopt import docopt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# Add the parent directory to sys.path to import the models and app
sys.path.insert(0, str(Path(__file__).parent.parent))

from mindpulse_endpoint_poc.models import EncryptedMPFile, EnrollmentKey, Decryptor
from app import create_app

logger = logging.getLogger(__name__)


class BatchEventHandler(FileSystemEventHandler):
    """Event handler for batch directory changes."""

    def __init__(self, processor: "BatchProcessor"):
        self.processor = processor

    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event in the complete batches directory."""
        logger.info(
            f"File system event detected: {event.event_type} - {event.src_path}"
        )
        # Just process everything in the complete batches directory
        self.processor.process_all_complete_batches()


class BatchProcessor:
    """Process batches of encrypted files using the new models architecture."""

    def __init__(self, app_config: Dict[str, Any]):
        """
        Initialize processor with Flask app configuration.

        Args:
            app_config: Flask app configuration dictionary
        """
        self.config = app_config
        self.complete_batch_path = app_config["COMPLETE_BATCH_PATH"]
        self.processing_path = app_config["PROCESSING_PATH"]
        self.processed_path = app_config[
            "PROCESSED_PATH"
        ]  # This is "READY_FOR_UPLOAD_PATH"
        self.failed_path = app_config["FAILED_PATH"]
        self.keys_path = app_config["KEYS_PATH"]

        # Ensure all directories exist (they should already from app initialization)
        for dir_path in [self.processing_path, self.processed_path, self.failed_path]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Create processing subdirectories
        (self.processing_path / "in").mkdir(parents=True, exist_ok=True)
        (self.processing_path / "out").mkdir(parents=True, exist_ok=True)

    def process_batch(self, batch_dir: Path) -> Dict[str, Any]:
        """
        Process a batch directory according to the new architecture.

        Args:
            batch_dir: Path to the batch directory to process

        Returns:
            Dictionary with processing results
        """
        results = {
            "batch_id": batch_dir.name,
            "files_processed": 0,
            "files_failed": 0,
            "errors": [],
        }

        batch_name = batch_dir.name

        try:
            # Move to processing/in/
            processing_in_path = self.processing_path / "in" / batch_name
            shutil.move(batch_dir, processing_in_path)
            logger.info(f"Moved {batch_name} to processing/in/")

            # Create processing/out/ directory
            processing_out_path = self.processing_path / "out" / batch_name
            processing_out_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created output directory: {processing_out_path}")

            # Process each file in the input directory
            for file_path in processing_in_path.iterdir():
                if file_path.is_file():
                    try:
                        logger.info(f"Processing file: {file_path.name}")

                        # Parse the encrypted file
                        mpfile = EncryptedMPFile.from_filename(file_path)

                        # Load the enrollment key
                        key = EnrollmentKey.load_for_short_sha(
                            self.keys_path, mpfile.short_id
                        )

                        # Create decryptor
                        decryptor = Decryptor.from_enrollment_key(key)

                        # Get date part directly from datetime object
                        date_part = mpfile.created_at.date().isoformat()

                        # Create target directory structure: {short_hash}/{date_part}/{type}/
                        target_dir = (
                            processing_out_path
                            / mpfile.short_id
                            / date_part
                            / mpfile.type
                        )
                        target_dir.mkdir(parents=True, exist_ok=True)

                        # Create target filename without IV using parsed components
                        # Original: 8ce4d5e6_2025-09-20T092542-0500_image_5ea30e9f40ce2e43d0b66c11c8324b05.png
                        # Target: 8ce4d5e6_2025-09-20T092542-0500_image.png
                        timestamp_str = mpfile.created_at.isoformat().replace(":", "")
                        filename_without_iv = f"{mpfile.short_id}_{timestamp_str}_{mpfile.type}{file_path.suffix}"

                        target_path = target_dir / filename_without_iv

                        # Decrypt file to target location
                        decryptor.decrypt_to_path(mpfile, target_path)

                        logger.info(
                            f"Successfully processed {file_path.name} -> {target_path}"
                        )
                        results["files_processed"] += 1

                    except Exception as e:
                        logger.error(f"Failed to process {file_path.name}: {e}")
                        results["files_failed"] += 1
                        results["errors"].append(
                            f"Failed to process {file_path.name}: {e}"
                        )

            # Move output directory to processed (ready for upload)
            final_dest = self.processed_path / batch_name
            if processing_out_path.exists():
                shutil.move(processing_out_path, final_dest)
                logger.info(f"Moved processed batch to: {final_dest}")

            # Clean up input directory
            if processing_in_path.exists():
                shutil.rmtree(processing_in_path)
                logger.info(f"Cleaned up input directory: {processing_in_path}")

        except Exception as e:
            logger.error(f"Error processing batch {batch_name}: {e}")
            results["errors"].append(f"Batch processing error: {e}")
            results["files_failed"] += 1
            # Don't handle failed batch movement here - let process_batch_safe handle it
            raise  # Re-raise so process_batch_safe can handle the failure

        return results

    def process_batch_safe(self, batch_dir: Path):
        """Safely process a batch with error handling."""
        batch_name = batch_dir.name
        failed_dest = self.failed_path / batch_name

        try:
            results = self.process_batch(batch_dir)

            success = results["files_failed"] == 0

            if not success:
                # If processing failed, move whatever remains to failed directory
                self._move_batch_to_failed(batch_name, "Some files failed to process")

            logger.info(f"Completed processing batch {batch_name}: {results}")

        except Exception as e:
            logger.error(f"Error processing batch {batch_name}: {e}")
            # Move batch to failed directory regardless of where it currently is
            self._move_batch_to_failed(batch_name, f"Processing error: {e}")

    def _move_batch_to_failed(self, batch_name: str, reason: str):
        """Move a batch to the failed directory, finding it wherever it currently is."""
        failed_dest = self.failed_path / batch_name

        # Check possible locations for the batch
        possible_locations = [
            self.complete_batch_path / batch_name,
            self.processing_path / "in" / batch_name,
            self.processing_path / "out" / batch_name,
        ]

        moved = False
        for location in possible_locations:
            if location.exists():
                try:
                    shutil.move(location, failed_dest)
                    logger.warning(
                        f"Moved failed batch to: {failed_dest} (reason: {reason})"
                    )
                    moved = True
                    break
                except Exception as move_error:
                    logger.error(
                        f"Failed to move batch from {location} to failed directory: {move_error}"
                    )

        if not moved:
            logger.error(
                f"Could not find batch {batch_name} to move to failed directory"
            )

    def process_all_complete_batches(self):
        """Process all directories in the complete batch path."""
        logger.info("Processing all batches in complete directory...")

        if not self.complete_batch_path.exists():
            logger.warning(
                f"Complete batch path does not exist: {self.complete_batch_path}"
            )
            return

        # Process each directory in complete batches
        for item in self.complete_batch_path.iterdir():
            if item.is_dir():
                logger.info(f"Found batch to process: {item.name}")
                self.process_batch_safe(item)

        logger.info("Finished processing all complete batches")

    def start_processing(self):
        """Start the batch processing system."""
        logger.info("Starting batch processing system")

        # Process any existing batches first
        self.process_all_complete_batches()

        # Start file watcher
        observer = self.start_watching()

        logger.info("Batch processing system started")
        return observer

    def start_watching(self):
        """Start watching the complete batch directory for new batches."""
        event_handler = BatchEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.complete_batch_path), recursive=False)
        observer.start()

        logger.info(
            f"Started watching {self.complete_batch_path} for new batch directories"
        )
        logger.info(f"Complete batch path: {self.complete_batch_path}")
        logger.info(f"Processing path: {self.processing_path}")
        logger.info(f"Processed path: {self.processed_path}")
        logger.info(f"Failed path: {self.failed_path}")
        logger.info(f"Keys path: {self.keys_path}")

        return observer


def main():
    """Main function to run the batch processor."""
    args = docopt(str(__doc__))

    # Configure logging
    log_level = logging.DEBUG if args["--debug"] else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]",
    )

    logger.info("Starting batch processor")

    # Create Flask app to get configuration
    app = create_app()

    # Create processor
    processor = BatchProcessor(app.config)

    # Start the complete processing system (worker thread + file watcher + queue existing)
    observer = processor.start_processing()

    try:
        # Keep the main thread alive - observer runs in background
        logger.info("Batch processor running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down batch processor...")

        # Stop the file observer
        observer.stop()
        observer.join()

        logger.info("Batch processor stopped")


if __name__ == "__main__":
    main()
