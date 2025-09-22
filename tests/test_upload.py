"""Tests for the upload endpoint."""

from io import BytesIO

import pytest

from mindpulse_endpoint_poc.app import create_app
from mindpulse_endpoint_poc.utils import parse_size_string
from mindpulse_endpoint_poc.services import parse_filename


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app("testing")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


def test_parse_size_string():
    """Test the parse_size_string function with various formats."""
    # Test basic formats
    assert parse_size_string("16M") == 16 * 1024 * 1024
    assert parse_size_string("1GB") == 1024 * 1024 * 1024
    assert parse_size_string("512K") == 512 * 1024
    assert parse_size_string("2TB") == 2 * 1024 * 1024 * 1024 * 1024
    
    # Test with spaces and different cases
    assert parse_size_string(" 16M ") == 16 * 1024 * 1024
    assert parse_size_string("1gb") == 1024 * 1024 * 1024
    assert parse_size_string("1GB") == 1024 * 1024 * 1024
    
    # Test decimal values
    assert parse_size_string("1.5GB") == int(1.5 * 1024 * 1024 * 1024)
    
    # Test bytes (no unit)
    assert parse_size_string("1024") == 1024


def test_parse_size_string_invalid():
    """Test parse_size_string with invalid formats."""
    with pytest.raises(ValueError):
        parse_size_string("")
    
    with pytest.raises(ValueError):
        parse_size_string("invalid")
    
    with pytest.raises(ValueError):
        parse_size_string("16X")  # Invalid unit


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "mindpulse-endpoint-poc"


def test_upload_no_files(client):
    """Test upload endpoint with no files."""
    response = client.post("/api/v1/upload")
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_upload_single_file(client):
    """Test upload endpoint with a single file."""
    # Create a mock image file with proper naming format
    image_data = b"fake image data"

    response = client.post(
        "/api/v1/upload",
        data={"file1": (BytesIO(image_data), "12345678_1750890839000.png")},
        content_type="multipart/form-data"
    )

    assert response.status_code == 201
    data = response.get_json()
    assert "message" in data
    assert "1 files uploaded successfully" in data["message"]


def test_upload_invalid_filename_format(client):
    """Test upload endpoint with invalid filename format."""
    file_data = b"fake file data"
    
    response = client.post(
        "/api/v1/upload",
        data={"file1": (BytesIO(file_data), "invalid_filename.txt")},
        content_type="multipart/form-data"
    )
    
    # Should return 400 because no valid files were found
    assert response.status_code == 400


def test_upload_multiple_files_same_batch(client):
    """Test upload endpoint with multiple files in the same batch."""
    image_data = b"fake image data"

    response = client.post(
        "/api/v1/upload",
        data={
            "file1": (BytesIO(image_data), "12345678_1750890839000.png"),
            "file2": (BytesIO(image_data), "12345678_1750890853000.png"),
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 201
    data = response.get_json()
    assert "2 files uploaded successfully" in data["message"]


def test_upload_multiple_batches(client):
    """Test upload endpoint with files from different batches."""
    image_data = b"fake image data"

    response = client.post(
        "/api/v1/upload",
        data={
            "file1": (BytesIO(image_data), "12345678_1750890839000.png"),
            "file2": (BytesIO(image_data), "87654321_1750890853000.jpg"),
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 201
    data = response.get_json()
    assert "2 files uploaded successfully" in data["message"]


def test_upload_method_not_allowed(client):
    """Test upload endpoint with wrong HTTP method."""
    response = client.get("/api/v1/upload")
    assert response.status_code == 405


def test_parse_filename_new_format():
    """Test parse_filename with new IV-in-filename format."""
    filename = "b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png"
    short_hash, timestamp, type_str, iv, ext = parse_filename(filename)

    assert short_hash == "b27954ea"
    assert timestamp == "2025-09-19T20:32:23-06:00"
    assert type_str == "screenshot"
    assert iv == "200ca379e712327de55f92e0"
    assert ext == "png"


def test_parse_filename_legacy_format():
    """Test parse_filename with legacy format."""
    filename = "12345678_1750890839000_screenshot.png"
    subject_hash, timestamp, type_str, iv, ext = parse_filename(filename)

    assert subject_hash == "12345678"
    assert timestamp == "1750890839000"
    assert type_str == "screenshot"
    assert iv == ""  # Empty for legacy format
    assert ext == "png"


def test_parse_filename_invalid_formats():
    """Test parse_filename with invalid formats."""
    with pytest.raises(ValueError):
        parse_filename("invalid.png")

    with pytest.raises(ValueError):
        parse_filename("too_many_parts_here_and_here_and_here.png")

    # Invalid short_hash length
    with pytest.raises(ValueError):
        parse_filename("b2795_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png")

    # Invalid IV length
    with pytest.raises(ValueError):
        parse_filename("b27954ea_2025-09-19T20:32:23-06:00_screenshot_invalid.png")


def test_generate_iv():
    """Test IV generation."""
    iv1 = generate_iv()
    iv2 = generate_iv()

    # Should be 12 bytes
    assert len(iv1) == 12
    assert len(iv2) == 12

    # Should be different (statistically very unlikely to be same)
    assert iv1 != iv2


def test_generate_filename():
    """Test filename generation with new format."""
    # Test with provided IV and timestamp
    iv = bytes.fromhex("200ca379e712327de55f92e0")
    timestamp = "2025-09-19T20:32:23-06:00"

    filename = generate_filename("b27954ea", "screenshot", "png", timestamp, iv)
    expected = "b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png"
    assert filename == expected

    # Test with auto-generated IV and timestamp
    filename2 = generate_filename("b27954ea", "gps", "json")
    parts = filename2.split("_")
    assert len(parts) == 4
    assert parts[0] == "b27954ea"
    assert parts[2] == "gps"
    assert filename2.endswith(".json")


def test_validate_filename_format():
    """Test filename format validation."""
    # Valid new format
    assert validate_filename_format("b27954ea_2025-09-19T20:32:23-06:00_screenshot_200ca379e712327de55f92e0.png")

    # Valid legacy format
    assert validate_filename_format("12345678_1750890839000_screenshot.png")

    # Invalid formats
    assert not validate_filename_format("invalid.png")
    assert not validate_filename_format("too_many_parts_here_and_here.png") 