"""Entry point for the MindPulse Endpoint POC Flask application."""

import os
from mindpulse_endpoint_poc.app import create_app

app = create_app()


def main():
    """Run the Flask application."""
    # Get configuration from environment
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    print(f"Starting MindPulse Endpoint POC on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Upload folder: {app.config.get('UPLOAD_FOLDER', '/tmp/mindpulse_uploads')}")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
