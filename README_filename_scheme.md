# New Filename Scheme Implementation

## Overview

This document describes the implementation of the new filename scheme that includes the encryption IV (Initialization Vector) directly in the filename, addressing security concerns with the previous timestamp-based IV approach.

## Filename Format

### New Format (Recommended)
```
<short_hash>_<timestamp>_<type>_<iv>.<ext>
```

**Example:**
```
b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png
```

**Components:**
- `short_hash`: 8 hex characters identifying the enrollment key (e.g., `b27954ea`)
- `timestamp`: ISO 8601 format with timezone (e.g., `2025-09-19T20:32:23-06:00`)
- `type`: Data type identifier (e.g., `screenshot`, `gps`, `audio`)
- `iv`: 24 hex characters representing 12 random bytes for encryption IV
- `ext`: File extension (e.g., `png`, `json`, `mp3`)

### Legacy Format (Still Supported)
```
<subject_hash>_<timestamp>_<type>.<ext>
```

**Example:**
```
12345678_1750890839000_screenshot.png
```

## Security Improvements

### Previous Approach Issues
- IVs were derived from timestamps, which are predictable
- Reduced cryptographic security due to IV predictability
- Potential for IV reuse in high-frequency scenarios

### New Approach Benefits
- **Truly Random IVs**: Each file gets a cryptographically secure random 12-byte IV
- **IV Uniqueness**: Statistically guaranteed unique IVs for each encryption operation
- **Transparent Storage**: IV is stored in filename, eliminating need to extract from file content
- **Backward Compatibility**: Legacy format still supported for existing files

## Implementation Details

### Core Changes

#### 1. Filename Parsing (`services.py`)
```python
def parse_filename(filename: str) -> Tuple[str, str, str, str, str]:
    """
    Parse filename to extract components.

    Returns: (subject_hash, timestamp, type, iv, extension)
    """
```

- Supports both new (4 parts) and legacy (3 parts) formats
- Validates short_hash (8 hex chars) and IV (24 hex chars)
- Returns empty string for IV in legacy format

#### 2. Decryption Updates (`processor_example.py`)
```python
def decrypt_file(self, encrypted_file: Path, key: bytes, iv: Optional[bytes] = None) -> Optional[bytes]:
```

- New optional `iv` parameter
- If IV provided (new format): uses IV from filename, file contains only ciphertext
- If IV not provided (legacy): extracts IV from first 16 bytes of file

#### 3. Utility Functions (`utils.py`)
```python
def generate_iv() -> bytes:
    """Generate a random 12-byte IV for AES encryption."""

def generate_filename(short_hash: str, data_type: str, extension: str,
                     timestamp: Optional[str] = None, iv: Optional[bytes] = None) -> str:
    """Generate a filename using the new format with IV."""

def validate_filename_format(filename: str) -> bool:
    """Validate if filename matches expected format."""
```

### File Processing Flow

#### New Format Processing
1. Parse filename to extract IV
2. Convert IV hex string to bytes
3. Read entire file as ciphertext (no IV prepended)
4. Decrypt using provided IV

#### Legacy Format Processing
1. Filename parsing returns empty IV
2. Read first 16 bytes of file as IV
3. Read remaining bytes as ciphertext
4. Decrypt using extracted IV

## Usage Examples

### Generating New Format Filenames
```python
from mindpulse_endpoint_poc.utils import generate_filename, generate_iv

# Auto-generate IV and timestamp
filename = generate_filename("b27954ea", "screenshot", "png")
# Result: b27954ea_2025-09-19T20:32:23.123456_screenshot_a1b2c3d4e5f6789012345678.png

# Specify IV and timestamp
iv = generate_iv()
timestamp = "2025-09-19T20:32:23-06:00"
filename = generate_filename("b27954ea", "screenshot", "png", timestamp, iv)
```

### Parsing Filenames
```python
from mindpulse_endpoint_poc.services import parse_filename

# New format
subject_hash, timestamp, type_str, iv, ext = parse_filename(
    "b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png"
)
# iv = "200ca379e712327de55f92e0"

# Legacy format
subject_hash, timestamp, type_str, iv, ext = parse_filename(
    "12345678_1750890839000_screenshot.png"
)
# iv = ""  (empty for legacy)
```

### Validation
```python
from mindpulse_endpoint_poc.utils import validate_filename_format

# Valid formats
assert validate_filename_format("b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png")
assert validate_filename_format("12345678_1750890839000_screenshot.png")

# Invalid format
assert not validate_filename_format("invalid_filename.png")
```

## Migration Strategy

### For Existing Systems
1. **No immediate changes required**: Legacy format continues to work
2. **Gradual migration**: New uploads can use new format while old files remain accessible
3. **Mixed processing**: System handles both formats transparently

### For New Implementations
1. Use `generate_filename()` utility for creating new files
2. Always include IV in filename for maximum security
3. Use proper timestamp format with timezone information

## Testing

The implementation includes comprehensive tests for:
- Filename parsing (both formats)
- IV generation and validation
- Filename generation utilities
- Upload endpoint compatibility
- Error handling for invalid formats

## Backward Compatibility

- **File Processing**: Existing encrypted files continue to work without modification
- **API Endpoints**: Upload endpoints accept both filename formats
- **Decryption**: Automatic detection and handling of both IV storage methods
- **Validation**: Both formats pass validation checks

## Security Considerations

### IV Requirements
- **Length**: Exactly 12 bytes (24 hex characters)
- **Randomness**: Cryptographically secure random generation
- **Uniqueness**: Each encryption operation uses a unique IV
- **Storage**: IV stored in filename, not prepended to ciphertext (new format)

### Cryptographic Properties
- **AES-256-CBC**: Encryption algorithm remains unchanged
- **Key Management**: Enrollment keys continue to use existing system
- **PKCS7 Padding**: Padding scheme remains unchanged

## Implementation Files Modified

1. **`mindpulse_endpoint_poc/services.py`**: Filename parsing logic
2. **`processor_example.py`**: Decryption with IV from filename
3. **`mindpulse_endpoint_poc/utils.py`**: Utility functions for IV and filename generation
4. **`tests/test_upload.py`**: Comprehensive test coverage

This implementation provides a robust, secure, and backward-compatible solution for including encryption IVs in filenames while maintaining the existing system's functionality.