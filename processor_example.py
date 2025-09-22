#!/usr/bin/env python3
"""
Processor script for handling encrypted batch directories.

This script:
1. Watches for new batch directories in the 'incoming' directory using file system events
2. Moves them to 'ready' when they're stable
3. Moves them to 'processing' directory to prevent race conditions
4. Decrypts files using AES keys from KEYS_DIR
5. Determines correct MIME types using the `file` command
6. Corrects file extensions based on actual content
7. Rsyncs files to a remote destination
8. Moves to 'complete' or 'failed' directory based on results
"""

import os
import shutil
import time
import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Set
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# Import the same config system as the Flask app
from mindpulse_endpoint_poc.config import get_config
from mindpulse_endpoint_poc.services import parse_filename
from mindpulse_endpoint_poc.utils import build_organized_path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BatchEventHandler(FileSystemEventHandler):
    """Event handler for batch directory changes."""
    
    def __init__(self, processor: 'BatchProcessor'):
        self.processor = processor
        self.pending_batches: Set[str] = set()
    
    def on_created(self, event: FileSystemEvent):
        """Handle directory creation events."""
        if event.is_directory:
            batch_name = Path(event.src_path).name
            logger.info(f"New batch directory detected: {batch_name}")
            
            # Add to pending batches
            self.pending_batches.add(batch_name)
            
            # Schedule processing with a delay to allow for file completion
            threading.Timer(2.0, self._process_pending_batch, args=[batch_name]).start()
    
    def _process_pending_batch(self, batch_name: str):
        """Process a pending batch after a delay."""
        if batch_name in self.pending_batches:
            self.pending_batches.remove(batch_name)
        
        batch_path = self.processor.incoming_dir / batch_name
        if batch_path.exists() and batch_path.is_dir():
            logger.info(f"Processing batch: {batch_name}")
            self.processor.process_batch_safe(batch_path)


class BatchProcessor:
    def __init__(self, upload_base: Path, keys_dir: Path, rsync_dest_base: str):
        self.upload_base = upload_base
        self.incoming_dir = upload_base / "incoming"
        self.ready_dir = upload_base / "ready"
        self.processing_dir = upload_base / "processing"
        self.complete_dir = upload_base / "complete"
        self.failed_dir = upload_base / "failed"
        self.keys_dir = keys_dir
        self.rsync_dest_base = rsync_dest_base
        
        # Ensure all directories exist
        for dir_path in [self.incoming_dir, self.ready_dir, self.processing_dir, self.complete_dir, self.failed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure keys directory exists
        if not self.keys_dir.exists():
            raise ValueError(f"Keys directory does not exist: {self.keys_dir}")
    
    def get_aes_key(self, subject_hash: str) -> Optional[bytes]:
        """Get AES key for a subject from the keys directory."""
        key_file = self.keys_dir / f"{subject_hash}"
        if not key_file.exists():
            logger.error(f"Key file not found for subject {subject_hash}: {key_file}")
            return None
        
        try:
            with open(key_file, 'r') as f:
                key_hex = f.read().strip()
                return bytes.fromhex(key_hex)
        except Exception as e:
            logger.error(f"Failed to read key file {key_file}: {e}")
            return None
    
    def decrypt_file(self, encrypted_file: Path, key: bytes, iv: Optional[bytes] = None) -> Optional[bytes]:
        """
        Decrypt a file using AES-256-CBC.

        Args:
            encrypted_file: Path to encrypted file
            key: AES key bytes
            iv: Optional IV bytes. If None, extracts from first 16 bytes of file (legacy)
        """
        try:
            with open(encrypted_file, 'rb') as f:
                encrypted_data = f.read()

            if iv is not None:
                # New format: IV provided from filename, file contains only ciphertext
                ciphertext = encrypted_data
            else:
                # Legacy format: IV is first 16 bytes of file
                iv = encrypted_data[:16]
                ciphertext = encrypted_data[16:]

            # Create cipher
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            # Decrypt
            decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove PKCS7 padding
            padding_length = decrypted_data[-1]
            if padding_length < 16:
                decrypted_data = decrypted_data[:-padding_length]

            return decrypted_data

        except Exception as e:
            logger.error(f"Failed to decrypt {encrypted_file}: {e}")
            return None
    
    def get_mime_type(self, file_path: Path) -> Optional[str]:
        """Get MIME type using the `file` command."""
        try:
            result = subprocess.run(
                ['file', '--mime-type', str(file_path)],
                capture_output=True, text=True, check=True
            )
            mime_type = result.stdout.strip().split(': ')[1]
            return mime_type
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get MIME type for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting MIME type for {file_path}: {e}")
            return None
    
    def get_extension_from_mime_type(self, mime_type: str) -> str:
        """Get file extension from MIME type."""
        mime_to_ext = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/webp': '.webp',
            'image/tiff': '.tiff',
            'image/tif': '.tif',
        }
        return mime_to_ext.get(mime_type, '.bin')
    
    def rsync_file(self, local_file: Path, remote_dest: str) -> bool:
        """Rsync a file to the remote destination."""
        try:
            result = subprocess.run([
                'rsync', '-av', '--progress',
                str(local_file), remote_dest
            ], capture_output=True, text=True, check=True)
            
            logger.info(f"Successfully rsynced {local_file} to {remote_dest}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to rsync {local_file} to {remote_dest}: {e}")
            logger.error(f"rsync stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during rsync of {local_file}: {e}")
            return False
    
    def process_batch(self, batch_dir: Path) -> Dict[str, Any]:
        """
        Process a batch directory.
        
        This processes each file in the batch:
        1. Decrypt using AES key
        2. Determine correct MIME type
        3. Fix file extension
        4. Rsync to remote destination
        """
        results = {
            "batch_id": batch_dir.name,
            "files_processed": 0,
            "files_failed": 0,
            "errors": []
        }
        
        # Get AES key for this subject
        subject_hash = batch_dir.name
        key = self.get_aes_key(subject_hash)
        if key is None:
            results["errors"].append(f"No AES key found for subject {subject_hash}")
            return results
        
        # Create temporary directory for decrypted files
        temp_dir = batch_dir / "decrypted"
        temp_dir.mkdir(exist_ok=True)
        
        for file_path in batch_dir.iterdir():
            if file_path.is_file():
                try:
                    logger.info(f"Processing {file_path.name}")

                    # Parse filename to extract components
                    iv_bytes = None
                    subject_id = None
                    timestamp = None
                    file_type = None
                    original_ext = None

                    try:
                        subject_id, timestamp, file_type, iv_hex, original_ext = parse_filename(file_path.name)
                        if iv_hex:  # New format with IV in filename
                            iv_bytes = bytes.fromhex(iv_hex)
                            logger.debug(f"Extracted IV from filename: {iv_hex}")
                    except Exception as e:
                        logger.debug(f"Using legacy format for {file_path.name}: {e}")
                        # Fallback: use subject_hash as ID if parsing fails
                        subject_id = subject_hash
                        timestamp = "unknown"
                        file_type = "unknown"
                        original_ext = file_path.suffix.lstrip('.')

                    # 1. Decrypt the file
                    decrypted_data = self.decrypt_file(file_path, key, iv_bytes)
                    if decrypted_data is None:
                        results["files_failed"] += 1
                        results["errors"].append(f"Failed to decrypt {file_path.name}")
                        continue
                    
                    # 2. Save decrypted data to temp file
                    temp_file = temp_dir / f"decrypted_{file_path.name}"
                    with open(temp_file, 'wb') as f:
                        f.write(decrypted_data)
                    
                    # 3. Determine correct MIME type
                    mime_type = self.get_mime_type(temp_file)
                    if mime_type is None:
                        results["files_failed"] += 1
                        results["errors"].append(f"Failed to determine MIME type for {file_path.name}")
                        continue
                    
                    # 4. Get correct extension and rename
                    correct_ext = self.get_extension_from_mime_type(mime_type)
                    name_without_ext = file_path.stem
                    corrected_file = temp_dir / f"{name_without_ext}{correct_ext}"
                    
                    if temp_file != corrected_file:
                        temp_file.rename(corrected_file)
                        logger.info(f"Corrected extension for {file_path.name}: {corrected_file.name}")
                    
                    # 5. Build organized destination path
                    organized_path = build_organized_path(
                        subject_id, timestamp, file_type, mime_type, correct_ext
                    )
                    remote_dest = f"{self.rsync_dest_base}/{organized_path}"

                    logger.info(f"Organized destination: {remote_dest}")

                    # 6. Rsync to organized remote destination
                    if self.rsync_file(corrected_file, remote_dest):
                        results["files_processed"] += 1
                        logger.info(f"Successfully processed {file_path.name} -> {organized_path}{corrected_file.name}")
                    else:
                        results["files_failed"] += 1
                        results["errors"].append(f"Failed to rsync {file_path.name}")
                    
                except Exception as e:
                    results["files_failed"] += 1
                    results["errors"].append(f"Failed to process {file_path.name}: {e}")
                    logger.error(f"Failed to process {file_path.name}: {e}")
        
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
        
        return results
    
    def process_batch_safe(self, batch_dir: Path):
        """Safely process a batch by moving it through the directory states."""
        try:
            # Move from incoming to ready
            ready_path = self.move_to_ready(batch_dir)
            
            # Move from ready to processing
            processing_path = self.move_to_processing(ready_path)
            
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
                if 'processing_path' in locals() and processing_path.exists():
                    self.move_to_final_location(processing_path, False)
            except:
                pass
    
    def move_to_ready(self, batch_dir: Path) -> Path:
        """Move batch directory from incoming to ready."""
        ready_path = self.ready_dir / batch_dir.name
        shutil.move(str(batch_dir), str(ready_path))
        logger.info(f"Moved {batch_dir.name} to ready")
        return ready_path
    
    def move_to_processing(self, batch_dir: Path) -> Path:
        """Move batch directory from ready to processing."""
        processing_path = self.processing_dir / batch_dir.name
        shutil.move(str(batch_dir), str(processing_path))
        logger.info(f"Moved {batch_dir.name} to processing")
        return processing_path
    
    def move_to_final_location(self, batch_dir: Path, success: bool):
        """Move batch directory to complete or failed directory."""
        if success:
            final_path = self.complete_dir / batch_dir.name
            logger.info(f"Moving {batch_dir.name} to complete")
        else:
            final_path = self.failed_dir / batch_dir.name
            logger.warning(f"Moving {batch_dir.name} to failed")
        
        shutil.move(str(batch_dir), str(final_path))
    
    def start_watching(self):
        """Start watching the incoming directory for new batches."""
        event_handler = BatchEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.incoming_dir), recursive=False)
        observer.start()
        
        logger.info(f"Started watching {self.incoming_dir} for new batch directories")
        logger.info(f"Upload base: {self.upload_base}")
        logger.info(f"Ready dir: {self.ready_dir}")
        logger.info(f"Processing dir: {self.processing_dir}")
        logger.info(f"Complete dir: {self.complete_dir}")
        logger.info(f"Failed dir: {self.failed_dir}")
        logger.info(f"Keys dir: {self.keys_dir}")
        logger.info(f"Rsync dest: {self.rsync_dest_base}")
        
        return observer
    
    def process_existing_batches(self):
        """Process any existing batch directories that might have been missed."""
        logger.info("Checking for existing batch directories...")
        
        # Check incoming directory
        for item in self.incoming_dir.iterdir():
            if item.is_dir():
                logger.info(f"Found existing batch in incoming: {item.name}")
                self.process_batch_safe(item)
        
        # Check ready directory
        for item in self.ready_dir.iterdir():
            if item.is_dir():
                logger.info(f"Found existing batch in ready: {item.name}")
                self.process_batch_safe(item)


def get_processor_directories(config_name: str = None) -> tuple[Path, Path, str]:
    """
    Get processor directories and settings using the same config system as the Flask app.
    
    Args:
        config_name: Configuration name (development, production, etc.)
        
    Returns:
        Tuple of (upload_base, keys_dir, rsync_dest_base)
    """
    # Get config using shared function
    config_class = get_config(config_name)
    
    # Get upload directory from config (already a Path object)
    upload_base = config_class.UPLOAD_FOLDER
    
    # Get keys directory and rsync destination from environment
    keys_dir = Path(os.environ.get("KEYS_DIR", "/etc/mindpulse/keys"))
    rsync_dest_base = os.environ.get("RSYNC_DEST_BASE", "user@remote-server:/path/to/destination")
    
    return upload_base, keys_dir, rsync_dest_base


if __name__ == "__main__":
    import sys
    
    # Get config name from command line or use default
    config_name = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Get directories and settings using the same config system
    upload_base, keys_dir, rsync_dest_base = get_processor_directories(config_name)
    
    logger.info(f"Using config: {config_name or 'default'}")
    logger.info(f"Upload base: {upload_base}")
    logger.info(f"Keys directory: {keys_dir}")
    logger.info(f"Rsync destination: {rsync_dest_base}")
    
    # Create processor
    processor = BatchProcessor(upload_base, keys_dir, rsync_dest_base)
    
    # Process any existing batches first
    processor.process_existing_batches()
    
    # Start watching for new batches
    observer = processor.start_watching()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down batch processor...")
        observer.stop()
        observer.join()
        logger.info("Batch processor stopped") 