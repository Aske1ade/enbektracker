#! /usr/bin/env bash

# Let the DB start
python /app/app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Ensure storage bucket exists
python /app/app/init_storage.py

# Create initial data in DB
python /app/app/initial_data.py
