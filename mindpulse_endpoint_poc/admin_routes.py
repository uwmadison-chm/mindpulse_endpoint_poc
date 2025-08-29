"""
Admin routes for the app
"""

import logging
import re

from flask import url_for, redirect, render_template, request, flash

from .models import enrollment_key

def register(app):
    enrollment_key.logger = app.logger
    app.logger.debug("Registering admin routes...")
    
    @app.get("/enrollments")
    def enrollments_form():
        return render_template('enrollments.html')


    @app.get("/enrollments/<full_key>")
    def show_enrollment(full_key):
        keys_path = app.config['KEYS_PATH']
        key = enrollment_key.EnrollmentKey.load_for_search_str(keys_path, full_key)
        app.logger.info(f"show_enrollment loaded {key}")
        return render_template("show_enrollment.html", key=key)
    
    @app.get("/enrollments/search")
    def search_enrollments():
        keys_path = app.config['KEYS_PATH']
        key = None
        try:
            key = enrollment_key.EnrollmentKey.load_for_search_str(
                keys_path,
                request.args.get('q', '')
            )
            app.logger.info(key)
            return redirect(url_for('show_enrollment', full_key=key.hexdata))
        except Exception as e:
            flash('Enrollment not found')
            app.logger.error(e)
        return redirect(url_for('enrollments_form'))


    @app.post("/enrollments")
    def create_enrollment():
        k = enrollment_key.EnrollmentKey.generate_and_persist_random(app.config['KEYS_PATH'])
        app.logger.debug(f"Generated key {k.hexdata} with short_sha {k.short_sha}")
        return redirect(url_for('show_enrollment', full_key=k.hexdata))

