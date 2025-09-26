from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
import secrets
import tempfile
from typing import List, Optional
import mmap

from werkzeug.utils import secure_filename
from werkzeug.security import safe_join
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

from .utils import ensure_directory_exists

import logging

logger = logging.getLogger(__name__)


SHORT_SHA_LEN = 8
KEY_LEN = 32

# When we're making a new key, this is the most times we'll try before giving
# up on filename collisions. This should never, ever, ever come up.
MAX_ITERS = 100


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
        search_filtered = re.sub(r"[^0-9a-f]+", "", search_norm_unsafe)
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
                raise ValueError(
                    f"Filename must have at least 4 parts separated by underscores: {filename}"
                )

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
                iv=iv,
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

    incoming_path: Path
    complete_path: Path
    batch_path: Path
    success_files: List[EncryptedMPFile]
    failure_files: List[Path]

    @classmethod
    def setup_for_transfer(kls, incoming_path, complete_path):
        batch_path = Path(tempfile.mkdtemp(dir=incoming_path))
        return kls(
            incoming_path=incoming_path,
            complete_path=complete_path,
            batch_path=batch_path,
            success_files=[],
            failure_files=[],
        )

    def process_batch(self, files):
        self._process_files(files)
        self._move_to_complete()

    def _process_files(self, files):
        """
        Process a batch of files, saving them to the batch directory

        Args:
            files: Dict of file objects from Flask request.files
        """

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
                logger.warning(
                    f"Error processing file {file_key}: {safe_filename} - {e}"
                )
                self.failure_files.append(file_obj.filename)

    def _move_to_complete(self):
        """
        Move the entire batch directory to the completed directory
        """
        dest_path = self.complete_path / self.batch_path.name
        result = self.batch_path.rename(dest_path)
        logger.debug(f"Moved batch to {result}")

        # Update batch_path to new location
        self.batch_path = result


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


@dataclass
class Encryptor:
    """
    AES-256-CBC encryptor for MindPulse files.

    Encrypts data using the enrollment key and generates a random IV for each file.
    The encrypted format is: IV (16 bytes) + encrypted_data
    """

    key: bytes

    @classmethod
    def from_enrollment_key(cls, enrollment_key: EnrollmentKey):
        """Create encryptor from an enrollment key."""
        key_bytes = bytes.fromhex(enrollment_key.hexdata)
        return cls(key=key_bytes)

    def encrypt(self, data: bytes) -> tuple[bytes, bytes]:
        """
        Encrypt data using AES-256-CBC.

        Args:
            data: Raw bytes to encrypt

        Returns:
            Tuple of (ciphertext, iv)
        """
        # Generate random IV
        iv = secrets.token_bytes(16)

        # Pad data using PKCS7
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()

        # Encrypt
        cipher = Cipher(
            algorithms.AES(self.key), modes.CBC(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Return ciphertext only and IV separately
        return ciphertext, iv

    def encrypt_file(self, source_path: Path, dest_path: Path) -> bytes:
        """
        Encrypt a file and save to destination.

        Args:
            source_path: Path to source file
            dest_path: Path to encrypted destination file

        Returns:
            The IV used for encryption
        """
        with open(source_path, "rb") as f:
            data = f.read()

        ciphertext, iv = self.encrypt(data)

        with open(dest_path, "wb") as f:
            f.write(ciphertext)

        return iv


@dataclass
class Decryptor:
    """
    AES-256-CBC decryptor for MindPulse files.

    Decrypts files using IV from the filename and encrypted content from the file.
    """

    key: bytes

    @classmethod
    def from_enrollment_key(cls, enrollment_key: EnrollmentKey):
        """Create decryptor from an enrollment key."""
        key_bytes = bytes.fromhex(enrollment_key.hexdata)
        return cls(key=key_bytes)

    def decrypt(self, mpfile: EncryptedMPFile, chunk_size: int = 64 * 1024) -> bytes:
        """
        Decrypt an EncryptedMPFile using memory mapping for efficient processing.

        Uses memory mapping to avoid loading the entire encrypted file into memory,
        making it efficient for files of any size.

        Args:
            mpfile: EncryptedMPFile object with path and IV
            chunk_size: Size of chunks to process at once (default: 64KB)

        Returns:
            Decrypted file data
        """
        with open(mpfile.path, "rb") as f:
            file_size = f.seek(0, 2)  # Get file size
            f.seek(0)  # Reset to beginning

            if file_size == 0:
                return b""

            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                # Create cipher
                cipher = Cipher(
                    algorithms.AES(self.key),
                    modes.CBC(mpfile.iv),
                    backend=default_backend(),
                )
                decryptor = cipher.decryptor()

                # Process the file in chunks - accumulate because we need
                # complete data to remove PKCS7 padding
                all_decrypted_data = b""

                for offset in range(0, file_size, chunk_size):
                    end_offset = min(offset + chunk_size, file_size)
                    chunk = mm[offset:end_offset]

                    if end_offset == file_size:
                        # Final chunk - call finalize
                        decrypted_chunk = decryptor.update(chunk) + decryptor.finalize()
                    else:
                        decrypted_chunk = decryptor.update(chunk)

                    all_decrypted_data += decrypted_chunk

                # Remove PKCS7 padding from complete data
                unpadder = padding.PKCS7(128).unpadder()
                data = unpadder.update(all_decrypted_data) + unpadder.finalize()

                return data

    def decrypt_to_path(
        self, mpfile: EncryptedMPFile, dest_path: Path, chunk_size: int = 64 * 1024
    ) -> None:
        """
        Decrypt an EncryptedMPFile and save directly to destination file.

        Args:
            mpfile: EncryptedMPFile object with path and IV
            dest_path: Path to save decrypted file
            chunk_size: Size of chunks to process at once (default: 64KB)
        """
        # Decrypt using the main decrypt method
        decrypted_data = self.decrypt(mpfile, chunk_size)

        # Write to destination file
        with open(dest_path, "wb") as output_file:
            output_file.write(decrypted_data)

    def get_file_info(self, mpfile: EncryptedMPFile) -> dict:
        """
        Get information about an encrypted file without fully decrypting it.

        Args:
            mpfile: EncryptedMPFile object

        Returns:
            Dictionary with file information
        """
        file_path = mpfile.path
        file_size = file_path.stat().st_size

        return {
            "path": str(file_path),
            "encrypted_size": file_size,
            "short_id": mpfile.short_id,
            "created_at": mpfile.created_at,
            "type": mpfile.type,
            "iv": mpfile.iv.hex(),
            "estimated_decrypted_size": file_size
            - 16,  # Rough estimate, actual will be smaller due to padding
        }
