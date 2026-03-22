# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY backend/requirements.txt /app/backend/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the source code and data directories
COPY mine_scheduler /app/mine_scheduler
COPY backend /app/backend
COPY data /app/data
COPY external_data /app/external_data

# Set PYTHONPATH to include the root directory for local imports
ENV PYTHONPATH=/app

# Expose the API port
EXPOSE 8000

# Command to run the application
# We run uvicorn from the root so that 'mine_scheduler' is importable
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
