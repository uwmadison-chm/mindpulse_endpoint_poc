# MindPulse Endpoint POC

A proof-of-concept Flask application for handling Android screenshot uploads. This application provides a simple HTTP endpoint that accepts file uploads and stores them locally for further processing.

## Features

- **File Upload Endpoint**: Accepts multiple files via POST requests
- **Local Storage**: Stores uploaded files in a configurable local directory
- **Batch Processor**: Processes encrypted files with AES decryption, MIME type detection, and rsync
- **Simple & Fast**: No file validation or verification - just saves files
- **Configuration Management**: Environment-based configuration with multiple profiles
- **Health Check**: Built-in health check endpoint
- **Modern Python**: Uses Python 3.13+ with type hints and modern practices
- **Production Ready**: Includes proper error handling, logging, and security measures

## Quick Start

### Prerequisites

- Python 3.13 or higher
- `uv` package manager (recommended) or `pip`

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd mindpulse_endpoint_poc
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Set up environment variables:
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. Run the application:
   ```bash
   python main.py
   ```

The application will start on `http://localhost:5000` by default.

## Configuration

The application uses environment variables for configuration. Copy `env.example` to `.env` and modify as needed:

### Environment Variables

- `FLASK_ENV`: Environment mode (`development`, `testing`, `production`)
- `FLASK_DEBUG`: Enable debug mode (`true`/`false`)
- `FLASK_HOST`: Host to bind to (default: `0.0.0.0`)
- `FLASK_PORT`: Port to bind to (default: `5000`)
- `SECRET_KEY`: Flask secret key (required in production)
- `UPLOAD_FOLDER`: Directory to store uploaded files (default: `/tmp/mindpulse_uploads`)
- `MAX_CONTENT_LENGTH`: Maximum file size in bytes (default: 16MB)
- `KEYS_DIR`: Directory containing AES key files in hex format (default: `/etc/mindpulse/keys`)
- `RSYNC_DEST_BASE`: Base rsync destination for processed files (default: `user@remote-server:/path/to/destination`)

## API Endpoints

### POST /api/v1/upload

Uploads multiple files from Android devices.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Files must be named according to the pattern "{subject_hash}_{timestamp}.{ext}" -- subject_hash is an 8-hex-digit hash identifying the subject, and {timestamp} is an epoch time with millisecond precision. {ext} will generally, but not necessarily, be an image extension
- Files not matching this pattern will be logged but not saved.
- Files in a batch should have the same subject_hash but it's not a problem if they don't

**Example using curl:**
```bash
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file1=@12345678_1750890839000.png" \
  -F "file2=@12345678_1750890853000.png"
```

**Response:**
```json
{
  "message": "2 files uploaded successfully"
}
```

**Note:** All file types are accepted. No validation is performed - files are simply saved to the upload directory.


### GET /api/v1/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "mindpulse-endpoint-poc",
  "version": "v1"
}
```

## Development

### Running in Development Mode

```bash
FLASK_ENV=development FLASK_DEBUG=true python main.py
```

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run black .
```

### Type Checking

```bash
uv run mypy .
```

## Project Structure

```
mindpulse_endpoint_poc/
├── mindpulse_endpoint_poc/
│   ├── __init__.py          # Package initialization
│   ├── app.py              # Flask application factory
│   ├── api_v1.py           # API v1 routes
│   ├── config.py           # Configuration management
│   ├── services.py         # Business logic
│   └── utils.py            # Utility functions
├── main.py                 # Application entry point
├── pyproject.toml          # Project configuration
├── env.example             # Environment variables example
└── README.md              # This file
```

## Security Considerations

- **Secure Filenames**: Uses Werkzeug's `secure_filename` to prevent path traversal
- **File Size Limits**: Configurable maximum file size
- **Unique Filenames**: Prevents filename conflicts
- **Environment Configuration**: Sensitive settings via environment variables

## Production Deployment

For production deployment:

1. Set `FLASK_ENV=production`
2. Set a strong `SECRET_KEY`
3. Configure `UPLOAD_FOLDER` to a persistent directory
4. Use a production WSGI server (e.g., Gunicorn, uWSGI)
5. Set up proper logging and monitoring

### Example with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "main:app"
```

## License

[Add your license information here]

## Batch Processor

The application includes a batch processor script (`processor_example.py`) that handles encrypted files:

### Features

- **AES Decryption**: Decrypts files using subject-specific AES keys
- **MIME Type Detection**: Uses the `file` command to determine correct file types
- **Extension Correction**: Fixes incorrect file extensions based on actual content
- **Rsync Integration**: Transfers processed files to remote destinations
- **Batch Processing**: Processes entire directories atomically
- **Error Handling**: Moves failed batches to a separate directory

### Running the Processor

```bash
# Run with default configuration
python processor_example.py

# Run with specific configuration
python processor_example.py production
```

### Processor Workflow

1. **Watch for Batches**: Monitors the upload directory for new batch directories
2. **Move to Processing**: Atomically moves batches to prevent race conditions
3. **Decrypt Files**: Uses AES-256-CBC to decrypt each file
4. **Detect MIME Type**: Uses the `file` command to determine actual file type
5. **Correct Extensions**: Renames files with correct extensions based on content
6. **Rsync to Remote**: Transfers files to the configured remote destination
7. **Cleanup**: Moves batch to "processed" or "failed" directory

### Key Requirements

- **AES Keys**: Keys must be stored as hex files in `KEYS_DIR` with filenames matching subject hashes
- **Linux Environment**: Requires the `file` command for MIME type detection
- **Rsync Access**: Must have SSH access to the remote destination
- **File Permissions**: Must have read/write access to all directories

### Example Key File Structure

```
/etc/mindpulse/keys/
├── 12345678.key  # Hex-encoded AES key for subject 12345678
├── abcdef12.key  # Hex-encoded AES key for subject abcdef12
└── ...
```
