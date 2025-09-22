from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
import secrets
import tempfile
from typing import List

from werkzeug.utils import secure_filename
from werkzeug.security import safe_join

from .utils import ensure_directory_exists

import logging
logger = logging.getLogger(__name__)


SHORT_SHA_LEN=8
KEY_LEN=32

# When we're making a new key, this is the most times we'll try before giving
# up on filename collisions. This should never, ever, ever come up.
MAX_ITERS=100

@dataclass
class EnrollmentKey:
    """
    A very simple model for enrollment keys.

    These are AES256 keys, which are generally persisted to the filesystem.
    """

    hexdata: str
    
    @classmethod
    def generate_and_persist_random(kls, keys_path):
        for i in range(MAX_ITERS):
            k = kls.generate_random()
            outfile = keys_path / f"{k.short_sha}.key"
            if outfile.exists():
                continue
            outfile.write_text(k.hexdata.lower())
            return k
        raise UniqueGenerationError.new(f"Could not generate unique key in {keys_path}")
            
    
    @classmethod
    def load_for_short_sha(kls, keys_path, short_sha):
        infile = keys_path / f"{short_sha}.key"
        logger.debug(f"Trying to read {infile}")
        return kls(hexdata=infile.read_text().strip().lower())
    
    @classmethod
    def load_for_search_str(kls, keys_path, search_str):
        # search_str should either be an 8-hexchar shortsha or a 64-hexchar key
        search_norm_unsafe = search_str.strip().lower()
        logger.debug(f"{search_norm_unsafe=}")
        search_filtered = re.sub(r'[^0-9a-f]+', '', search_norm_unsafe)
        logger.debug(f"{search_filtered=}")
        kb = keys_path.resolve()
        key_file = kb / f"{search_filtered}.key"
        logger.debug(f"Key file is: {key_file}")
        key_file.relative_to(kb)
        if key_file.exists():
            return kls.load_for_short_sha(keys_path, search_filtered)
        # okay maybe it's a key
        short_sha = short_sha_for_hex(search_filtered)
        # I _know_ this is a safe string because it's from a hash
        # If file doesn't exist we'll raise a FileNotFoundError, that's fine
        return kls.load_for_short_sha(keys_path, short_sha)
        
    @classmethod
    def generate_random(kls):
        return kls(hexdata=secrets.token_hex(KEY_LEN))
    
    
    @property
    def short_sha(self):
        return short_sha_for_hex(self.hexdata)


@dataclass
class EncryptedMPFile:
    path: Path
    short_id: str
    created_at: datetime
    type: str
    iv: bytes

    @classmethod
    def from_filename(kls, file_path):
        """
        Parses the parts out from the filename and returns an EncryptedMPFile
        If the parse fails, throws a ValueError

        Filenames are like:
        {short_id}_{created_at}_{type}_{iv}.ext

        created_at is in ISO8601 with timezone offset
        """
        file_path = Path(file_path)
        filename = file_path.name

        try:
            # Split filename into parts
            name_without_ext = file_path.stem
            parts = name_without_ext.split("_")

            if len(parts) < 4:
                raise ValueError(f"Filename must have at least 4 parts separated by underscores: {filename}")

            short_id = parts[0]
            created_at_str = parts[1]
            type_part = parts[2]
            iv_part = parts[3]

            # Parse created_at
            created_at = datetime.fromisoformat(created_at_str)

            # Parse IV (should be hex string)
            iv = bytes.fromhex(iv_part)

            return kls(
                path=file_path,
                short_id=short_id,
                created_at=created_at,
                type=type_part,
                iv=iv
            )

        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid filename format '{filename}': {e}")


@dataclass
class Batch:
    """
    A class for handling a batch of uploaded files and saving them to a directory
    for later processing.

    (This replaces the old services.py)

    The directory will include:

    * A set of files with normalized, safe names
    """

    batch_path: Path
    success_files: List[EncryptedMPFile]
    failure_files: List[Path]
    
    @classmethod
    def create_batch_dir(kls, base_dir):
        batch_path = Path(tempfile.mktemp(dir=base_dir))
        return kls(batch_path=batch_path)
    
    def process_files(self, files):
        """
        Process a batch of files, saving them to the batch directory

        Args:
            files: Dict of file objects from Flask request.files
        """
        self.batch_path.mkdir(parents=True, exist_ok=True)

        for file_key, file_obj in files.items():
            try:
                safe_filename = secure_filename(file_obj.filename)
                logger.debug(f"Processing {file_key}: {safe_filename}")

                # Validate filename format by attempting to parse it
                EncryptedMPFile.from_filename(safe_filename)

                # Save the file to batch directory
                target_path = self.batch_path / safe_filename
                file_obj.save(target_path)

                # Create EncryptedMPFile object with actual saved path
                mpfile = EncryptedMPFile.from_filename(target_path)
                self.success_files.append(mpfile)
                logger.info(f"Saved {target_path}")

            except (ValueError, Exception) as e:
                logger.warning(f"Error processing file {file_key}: {safe_filename} - {e}")
                self.failure_files.append(file_obj.filename)

    def move_to_ready(self, ready_dir):
        """
        Move the entire batch directory to the ready directory

        Args:
            ready_dir: Path to the ready directory
        """
        ready_dir = Path(ready_dir)
        ready_dir.mkdir(parents=True, exist_ok=True)

        batch_name = self.batch_path.name
        dest_path = ready_dir / batch_name

        result = self.batch_path.rename(dest_path)
        logger.debug(f"Moved batch {batch_name} -> {result}")

        # Update batch_path to new location
        self.batch_path = dest_path
        return result


def short_sha_for_hex(hex_str):
    """
    Just a little helper function; turns something like:
    71d38589d53b60c7f194f34a8b754e3004ead45248367f592e8e387258d3d0b4
    into something like:
    b27954ea
    """
    m = hashlib.sha256()
    key_bytes = bytes.fromhex(hex_str)
    m.update(key_bytes)
    digest = m.hexdigest()
    return digest[0:SHORT_SHA_LEN]



class UniqueGenerationError(RuntimeError):
    pass

class PathError(ValueError):
    pass