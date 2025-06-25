"""Configuration management for the MindPulse Endpoint POC."""

import os
from pathlib import Path
from typing import Optional

from .utils import parse_size_string


class Config:
    """Base configuration class."""
    
    # Flask configuration
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    
    # Upload configuration
    UPLOAD_FOLDER: str = os.environ.get("UPLOAD_FOLDER") or "/tmp/mindpulse_uploads"
    
    # Parse MAX_CONTENT_LENGTH from human-readable string
    _max_content_length_str = os.environ.get("MAX_CONTENT_LENGTH", "16M")
    try:
        MAX_CONTENT_LENGTH: int = parse_size_string(_max_content_length_str)
    except ValueError as e:
        print(f"Warning: Invalid MAX_CONTENT_LENGTH format '{_max_content_length_str}'. Using default 16M. Error: {e}")
        MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB default
        
    @classmethod
    def init_app(cls, app) -> None:
        """Initialize the application with this configuration."""
        # Ensure upload directory exists
        upload_path = Path(cls.UPLOAD_FOLDER)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Set Flask configuration
        app.config["SECRET_KEY"] = cls.SECRET_KEY
        app.config["MAX_CONTENT_LENGTH"] = cls.MAX_CONTENT_LENGTH


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    """Testing configuration."""
    
    DEBUG: bool = False
    TESTING: bool = True
    UPLOAD_FOLDER: str = "/tmp/mindpulse_test_uploads"
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(Config):
    """Production configuration."""
    
    DEBUG: bool = False
    TESTING: bool = False
    
    @classmethod
    def init_app(cls, app) -> None:
        """Initialize the application with production configuration."""
        super().init_app(app)
        
        # Production-specific configurations
        if not cls.SECRET_KEY or cls.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError("SECRET_KEY must be set in production")


# Configuration mapping
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
} 