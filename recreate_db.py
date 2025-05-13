#!/usr/bin/env python3
from app import app, db
import os

# Delete the existing database file
db_file = 'dev_tools.db'
if os.path.exists(db_file):
    print(f"Removing existing database file: {db_file}")
    os.remove(db_file)
else:
    print(f"No existing database file found: {db_file}")

# Create all database tables
with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully.")
    
print("Database has been recreated with all necessary tables.")
