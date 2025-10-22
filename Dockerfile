# --------- Base image ----------
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for MySQL
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files first (needed for collectstatic)
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user and switch
RUN adduser --disabled-password djangouser
USER djangouser

# Expose port
EXPOSE 8000

# Run Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "AutomaticRAB.wsgi:application"]
