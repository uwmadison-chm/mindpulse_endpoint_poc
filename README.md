# MindPulse Endpoint POC

A proof-of-concept Flask application for handling Android screenshot uploads. This application provides a simple HTTP endpoint that accepts file uploads and stores them locally for further processing.

## Features

- **File Upload Endpoint**: Accepts multiple files via POST requests
- **Local Storage**: Stores uploaded files in a configurable local directory
- **File Validation**: Validates file extensions and ensures secure filenames
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
- `MAX_FILES_PER_REQUEST`: Maximum files per request (default: 1000)

## API Endpoints

### POST /api/v1/upload

Uploads multiple files from Android devices.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Files should be named `file1`, `file2`, `file3`, etc.

**Example using curl:**
```bash
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file1=@screenshot1.png" \
  -F "file2=@screenshot2.jpg"
```

**Response:**
```json
{
  "message": "2 files uploaded successfully",
  "files": ["screenshot1.png", "screenshot2.jpg"],
  "upload_folder": "/tmp/mindpulse_uploads"
}
```

**Supported file types:**
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- BMP (`.bmp`)

### GET /api/v1/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "mindpulse-endpoint-poc"
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
│   ├── config.py           # Configuration management
│   ├── utils.py            # Utility functions
│   └── views.py            # API endpoints
├── main.py                 # Application entry point
├── pyproject.toml          # Project configuration
├── env.example             # Environment variables example
└── README.md              # This file
```

## Security Considerations

- **File Validation**: Only allows specific image file extensions
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
