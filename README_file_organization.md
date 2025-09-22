# Server-Side File Organization

## Overview

This document describes how the server organizes decrypted files using an intelligent hierarchical structure based on participant ID, date, and file type.

## File Organization Structure

### Decrypted File Hierarchy

After processing and decryption, files are organized on the server using a clean hierarchical structure:

```
{rsync_dest_base}/
├── {ID}/                          # Subject/participant ID (enrollment_hash)
│   ├── {date}/                    # Date in YYYY-MM-DD format
│   │   ├── screenshot/            # Screenshot files
│   │   │   └── filename.png
│   │   ├── gps/                   # GPS data files
│   │   │   └── filename.json
│   │   ├── metadata/              # Metadata files
│   │   │   └── filename.json
│   │   ├── video/                 # Video files
│   │   │   └── filename.mp4
│   │   ├── audio/                 # Audio files (if any)
│   │   │   └── filename.wav
│   │   ├── sensor_data/           # Sensor data files
│   │   │   └── filename.json
│   │   └── other/                 # Unknown/invalid file types
│   │       └── filename.bin
│   └── 2025-09-20/
│       ├── screenshot/
│       ├── gps/
│       └── metadata/
```

## Organization Logic

### Subject ID Extraction
- **New format**: Uses `short_hash` from filename (8 hex characters)
- **Legacy format**: Uses `subject_hash` from filename
- **Fallback**: Uses batch directory name if parsing fails

### Date Extraction
- **ISO 8601 timestamps**: Extracts date portion (YYYY-MM-DD)
  - Example: `2025-09-19T20:32:23-06:00` → `2025-09-19`
- **Epoch timestamps**: Converts to date format
  - Example: `1750890839000` → `2025-06-25`
- **Invalid timestamps**: Uses current date as fallback

### Type Categorization

Files are organized primarily by the `type` field from the filename, with fallbacks for edge cases:

#### 1. Filename Type (Primary Method)
The `type` component from the filename is used directly as the directory name:
- `screenshot` → `screenshot/`
- `gps` → `gps/`
- `metadata` → `metadata/`
- `video` → `video/`
- `audio` → `audio/`
- `sensor_data` → `sensor_data/`
- Any valid alphanumeric type → `{type}/`

#### 2. MIME Type (Fallback for Invalid Types)
Only used if filename type is missing or contains invalid characters:
- `image/*` → `images/`
- `audio/*` → `audio/`
- `video/*` → `video/`
- `application/json`, `text/json` → `data/`

#### 3. File Extension (Final Fallback)
Used only if both filename type and MIME type are unavailable:
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.tiff` → `images/`
- `.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a` → `audio/`
- `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm` → `video/`
- `.json`, `.csv`, `.txt` → `data/`
- All others → `other/`

## Example Organization

### Input Files (Current Format)
```
b27954ea_a7f3c8d9e2b1f056_screenshot.png
b27954ea_d4e8b2c1a9f7e3d2_metadata.json
b27954ea_f1a5c7e9b3d8a2f4_gps.json
b27954ea_c9a2f7d1e8b4c6a3_video.mp4
```

### Organized Output Structure
```
remote_server/
├── b27954ea/                      # Participant b27954ea
│   └── 2025-09-22/                # Date extracted from timestamp
│       ├── screenshot/            # Direct from filename type
│       │   └── b27954ea_a7f3c8d9e2b1f056_screenshot.png
│       ├── metadata/              # Direct from filename type
│       │   └── b27954ea_d4e8b2c1a9f7e3d2_metadata.json
│       ├── gps/                   # Direct from filename type
│       │   └── b27954ea_f1a5c7e9b3d8a2f4_gps.json
│       └── video/                 # Direct from filename type
│           └── b27954ea_c9a2f7d1e8b4c6a3_video.mp4
```

### Additional Examples
```
# Custom sensor types work automatically
b27954ea_xyz123_accelerometer.json    → b27954ea/2025-09-22/accelerometer/
b27954ea_abc456_heart_rate.json       → b27954ea/2025-09-22/heart_rate/
b27954ea_def789_location_history.json → b27954ea/2025-09-22/location_history/

# Invalid types fall back to MIME/extension detection
b27954ea_ghi012_invalid-type!.png     → b27954ea/2025-09-22/images/
```

## Implementation Details

### Utility Functions

#### `extract_date_from_timestamp(timestamp: str) -> str`
Converts various timestamp formats to YYYY-MM-DD:
```python
extract_date_from_timestamp("2025-09-19T20:32:23-06:00")  # → "2025-09-19"
extract_date_from_timestamp("1750890839000")              # → "2025-06-25"
```

#### `get_file_type_category(mime_type: str, extension: str, filename_type: str) -> str`
Categorizes files into directory types:
```python
get_file_type_category("image/png", "png", "screenshot")   # → "images"
get_file_type_category("application/json", "json", "gps")  # → "gps"
get_file_type_category("audio/wav", "wav", "audio")        # → "audio"
```

#### `build_organized_path(subject_id: str, timestamp: str, file_type: str, mime_type: str, extension: str) -> str`
Builds complete organized path:
```python
build_organized_path("b27954ea", "2025-09-19T20:32:23-06:00", "screenshot", "image/png", "png")
# → "b27954ea/2025-09-19/images/"
```

### Processing Flow

1. **Parse filename** to extract subject_id, timestamp, and file_type
2. **Decrypt file** using appropriate IV (from filename or file header)
3. **Detect MIME type** from decrypted content
4. **Correct file extension** based on actual content
5. **Build organized path** using utility functions
6. **Transfer file** to organized destination via rsync

## Benefits

### For Data Analysis
- **Time-series Analysis**: Easy to find all data for a date range
- **Cross-participant Comparison**: Compare same data types across participants
- **Type-specific Processing**: Process all images, audio, etc. separately

### For Data Management
- **Intuitive Browsing**: Navigate by participant → date → type
- **Scalable Structure**: Handles thousands of participants and files
- **Automatic Organization**: No manual sorting required
- **Type Segregation**: Files grouped by purpose

### For System Administration
- **Predictable Paths**: Know exactly where files will be stored
- **Easy Backup**: Backup specific data types or date ranges
- **Storage Optimization**: Different storage policies per file type
- **Access Control**: Fine-grained permissions by participant/type

## Configuration

The organization system uses these configurable components:

- **`rsync_dest_base`**: Base destination path for organized files
- **Date format**: Always YYYY-MM-DD for consistency
- **Type mappings**: Configurable in `get_file_type_category()` function
- **Fallback behavior**: Graceful handling of parsing failures

This intelligent organization system transforms the flat encrypted file structure into a meaningful, browsable hierarchy that supports various research and analysis workflows while maintaining data integrity and security.