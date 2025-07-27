#!/bin/bash

# Rich Message Automation System - Docker Entrypoint Script
set -e

echo "Starting Rich Message Automation System..."

# Set default environment variables
export FLASK_ENV=${FLASK_ENV:-production}
export DEBUG=${DEBUG:-false}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Wait for dependencies to be ready
echo "Waiting for dependencies..."

# Wait for PostgreSQL
if [ -n "$POSTGRES_HOST" ]; then
    echo "Waiting for PostgreSQL at $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
    while ! nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do
        sleep 1
    done
    echo "PostgreSQL is ready!"
fi

# Wait for Redis
if [ -n "$REDIS_HOST" ]; then
    echo "Waiting for Redis at $REDIS_HOST:${REDIS_PORT:-6379}..."
    while ! nc -z "$REDIS_HOST" "${REDIS_PORT:-6379}"; do
        sleep 1
    done
    echo "Redis is ready!"
fi

# Run database migrations if needed
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    python -c "
from src.utils.metrics_storage import get_metrics_storage
storage = get_metrics_storage()
storage.initialize_database()
print('Database initialized successfully')
"
fi

# Create necessary directories
mkdir -p /app/logs /app/data /app/tmp

# Set proper permissions
chown -R appuser:appuser /app/logs /app/data /app/tmp

# Validate configuration
echo "Validating configuration..."
python -c "
from src.config.settings import Settings
try:
    settings = Settings()
    print('Configuration validation successful')
    print(f'Environment: {settings.FLASK_ENV}')
    print(f'Debug mode: {settings.DEBUG}')
    print(f'Log level: {settings.LOG_LEVEL}')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    exit(1)
"

# Health check before starting
echo "Performing pre-start health check..."
python -c "
import sys
try:
    # Import core modules to check for import errors
    from src.services.rich_message_service import RichMessageService
    from src.services.line_service import LineService
    from src.utils.analytics_tracker import get_analytics_tracker
    print('Pre-start health check passed')
except Exception as e:
    print(f'Pre-start health check failed: {e}')
    sys.exit(1)
"

echo "All checks passed. Starting application..."

# Execute the main command
exec "$@"