# Use the official Python image as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/

# System deps for mysqlclient/psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    pkg-config \
    libpq-dev \
    default-libmysqlclient-dev && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn && \
    apt-get remove -y gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Create temp directory for file uploads
RUN mkdir -p /tmp/media

# Expose the port the app runs on
EXPOSE 8000

# Run Gunicorn with increased timeout for file processing
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --timeout 600 --workers 2 AutomaticRAB.wsgi:application"]
