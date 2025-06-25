"""Tests for the upload endpoint."""

import tempfile
import os
from pathlib import Path
from io import BytesIO
from unittest.mock import patch

import pytest
from flask import Flask

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
    assert "files" in data
    assert len(data["files"]) == 1
    assert data["files"][0] == "12345678/12345678_1750890839000.png"


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
    assert len(data["files"]) == 2
    assert all(f.startswith("12345678/") for f in data["files"])


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
    assert len(data["files"]) == 2
    assert "12345678/12345678_1750890839000.png" in data["files"]
    assert "87654321/87654321_1750890853000.jpg" in data["files"]


def test_upload_method_not_allowed(client):
    """Test upload endpoint with wrong HTTP method."""
    response = client.get("/api/v1/upload")
    assert response.status_code == 405 