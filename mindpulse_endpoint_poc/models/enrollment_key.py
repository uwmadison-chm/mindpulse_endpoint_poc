"""
A very simple model for enrollment keys.

These are AES256 keys, which are generally persisted to the filesystem.
"""


from dataclasses import dataclass
import hashlib
import re
import secrets

import logging
logger = logging.getLogger(__name__)


SHORT_SHA_LEN=8
KEY_LEN=32

# When we're making a new key, this is the most times we'll try before giving
# up on filename collisions. This should never, ever, ever come up.
MAX_ITERS=100

@dataclass
class EnrollmentKey:
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

def short_sha_for_hex(hex_str):
    m = hashlib.sha256()
    key_bytes = bytes.fromhex(hex_str)
    m.update(key_bytes)
    digest = m.hexdigest()
    return digest[0:SHORT_SHA_LEN]


class UniqueGenerationError(RuntimeError):
    pass

class PathError(ValueError):
    pass