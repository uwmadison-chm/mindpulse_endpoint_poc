"""
A very simple model for enrollment keys.

These are AES256 keys, which are generally persisted to the filesystem.
"""


from dataclasses import dataclass
import hashlib
import secrets

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
        return kls(hexdata=infile.read_text().strip().lower())
    
    @classmethod
    def generate_random(kls):
        return kls(hexdata=secrets.token_hex(KEY_LEN))

    @property
    def short_sha(self):
        m = hashlib.sha256()
        key_bytes = bytes.fromhex(self.hexdata)
        m.update(key_bytes)
        digest = m.hexdigest()
        return digest[0:SHORT_SHA_LEN]


class UniqueGenerationError(RuntimeError):
    pass