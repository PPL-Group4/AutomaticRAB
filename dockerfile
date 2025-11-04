# Use the official Python image as the base image
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set the working directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt /app/

# Install system dependencies and Python packages
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

# Copy the entire project
COPY . /app/

# Create directories for uploads
RUN mkdir -p /app/media /app/tmp && chmod -R 777 /app/media /app/tmp

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port 8000 (default for Gunicorn)
EXPOSE 8000

# Start the application using Gunicorn
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --timeout 600 --workers 2 AutomaticRAB.wsgi:application"]
