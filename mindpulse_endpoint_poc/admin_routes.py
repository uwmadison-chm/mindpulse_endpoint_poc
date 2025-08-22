"""
Admin routes for the app
"""

import logging
from flask import url_for, redirect, render_template

from .models import enrollment_key

def register(app):
    app.logger.debug("Registering admin routes...")
    
    @app.get("/enrollments")
    def enrollments_form():
        return render_template('enrollments.html')
        
    @app.post("/enrollments")
    def create_enrollment():
        k = enrollment_key.EnrollmentKey.generate_and_persist_random(app.config['KEYS_PATH'])
        app.logger.debug(f"Generated key {k.hexdata} with short_sha {k.short_sha}")
        return redirect(url_for('enrollments_form'))