#!/usr/bin/env python3
"""
Example processor script for handling batch directories.

This script demonstrates the recommended approach for processing batch directories:
1. Watch for new batch directories
2. Move them to a "processing" directory to prevent race conditions
3. Process each file in the batch
4. Move to "processed" or "failed" directory based on results
"""

import os
import shutil
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

# Import the same config system as the Flask app
from mindpulse_endpoint_poc.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BatchProcessor:
    def __init__(self, upload_dir: Path, processing_dir: Path, processed_dir: Path, failed_dir: Path):
        self.upload_dir = upload_dir
        self.processing_dir = processing_dir
        self.processed_dir = processed_dir
        self.failed_dir = failed_dir
        
        # Ensure all directories exist
        for dir_path in [self.upload_dir, self.processing_dir, self.processed_dir, self.failed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_new_batches(self) -> List[Path]:
        """Get list of batch directories that are ready for processing."""
        batches = []
        for item in self.upload_dir.iterdir():
            if item.is_dir() and self._is_batch_ready(item):
                batches.append(item)
        return batches
    
    def _is_batch_ready(self, batch_dir: Path) -> bool:
        """
        Check if a batch directory is ready for processing.
        
        This is where you'd implement your logic to determine if a batch is complete.
        For example:
        - Check if all expected files are present
        - Check if a "complete" flag file exists
        - Check if no new files have been added in the last N seconds
        """
        # Simple example: consider ready if directory has been stable for 5 seconds
        # In practice, you might have more sophisticated logic
        return True
    
    def move_to_processing(self, batch_dir: Path) -> Path:
        """Move batch directory to processing directory to prevent race conditions."""
        processing_path = self.processing_dir / batch_dir.name
        shutil.move(str(batch_dir), str(processing_path))
        logger.info(f"Moved {batch_dir.name} to processing")
        return processing_path
    
    def process_batch(self, batch_dir: Path) -> Dict[str, Any]:
        """
        Process a batch directory.
        
        This is where you'd implement your actual processing logic:
        - Decrypt images
        - Determine true file types
        - Upload to servers
        - etc.
        """
        results = {
            "batch_id": batch_dir.name,
            "files_processed": 0,
            "files_failed": 0,
            "errors": []
        }
        
        for file_path in batch_dir.iterdir():
            if file_path.is_file():
                try:
                    # Example processing steps:
                    logger.info(f"Processing {file_path.name}")
                    
                    # 1. Decrypt the file (if needed)
                    # decrypted_data = decrypt_file(file_path)
                    
                    # 2. Determine true file type
                    # true_type = detect_file_type(decrypted_data)
                    
                    # 3. Upload to server
                    # upload_to_server(decrypted_data, true_type)
                    
                    # 4. Store metadata
                    # store_metadata(file_path, true_type)
                    
                    results["files_processed"] += 1
                    logger.info(f"Successfully processed {file_path.name}")
                    
                except Exception as e:
                    results["files_failed"] += 1
                    results["errors"].append(f"Failed to process {file_path.name}: {e}")
                    logger.error(f"Failed to process {file_path.name}: {e}")
        
        return results
    
    def move_to_final_location(self, batch_dir: Path, success: bool):
        """Move batch directory to processed or failed directory."""
        if success:
            final_path = self.processed_dir / batch_dir.name
            logger.info(f"Moving {batch_dir.name} to processed")
        else:
            final_path = self.failed_dir / batch_dir.name
            logger.warning(f"Moving {batch_dir.name} to failed")
        
        shutil.move(str(batch_dir), str(final_path))
    
    def run_once(self):
        """Process one batch of directories."""
        new_batches = self.get_new_batches()
        
        for batch_dir in new_batches:
            try:
                # Move to processing directory to prevent race conditions
                processing_path = self.move_to_processing(batch_dir)
                
                # Process the batch
                results = self.process_batch(processing_path)
                
                # Determine success (you might have more sophisticated logic)
                success = results["files_failed"] == 0
                
                # Move to final location
                self.move_to_final_location(processing_path, success)
                
                logger.info(f"Completed processing batch {batch_dir.name}: {results}")
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_dir.name}: {e}")
                # Move to failed directory if we can
                try:
                    if processing_path.exists():
                        self.move_to_final_location(processing_path, False)
                except:
                    pass
    
    def run_forever(self, sleep_seconds: int = 5):
        """Run the processor continuously."""
        logger.info(f"Starting batch processor. Watching {self.upload_dir}")
        logger.info(f"Processing dir: {self.processing_dir}")
        logger.info(f"Processed dir: {self.processed_dir}")
        logger.info(f"Failed dir: {self.failed_dir}")
        
        while True:
            try:
                self.run_once()
                time.sleep(sleep_seconds)
            except KeyboardInterrupt:
                logger.info("Shutting down batch processor")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(sleep_seconds)


def get_processor_directories(config_name: str = None) -> tuple[Path, Path, Path, Path]:
    """
    Get processor directories using the same config system as the Flask app.
    
    Args:
        config_name: Configuration name (development, production, etc.)
        
    Returns:
        Tuple of (upload_dir, processing_dir, processed_dir, failed_dir)
    """
    # Get config using shared function
    config_class = get_config(config_name)
    
    # Get upload directory from config (already a Path object)
    upload_dir = config_class.UPLOAD_FOLDER
    
    # Create processor directories relative to upload directory
    processing_dir = upload_dir.parent / "mindpulse_processing"
    processed_dir = upload_dir.parent / "mindpulse_processed"
    failed_dir = upload_dir.parent / "mindpulse_failed"
    
    return upload_dir, processing_dir, processed_dir, failed_dir


if __name__ == "__main__":
    import sys
    
    # Get config name from command line or use default
    config_name = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Get directories using the same config system
    upload_dir, processing_dir, processed_dir, failed_dir = get_processor_directories(config_name)
    
    logger.info(f"Using config: {config_name or 'default'}")
    logger.info(f"Upload directory: {upload_dir}")
    logger.info(f"Processing directory: {processing_dir}")
    logger.info(f"Processed directory: {processed_dir}")
    logger.info(f"Failed directory: {failed_dir}")
    
    # Create and run processor
    processor = BatchProcessor(upload_dir, processing_dir, processed_dir, failed_dir)
    processor.run_forever() 