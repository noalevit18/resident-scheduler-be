#!/bin/sh
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting FastAPI application..."
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
