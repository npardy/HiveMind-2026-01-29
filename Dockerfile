FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/flagged

# Run the orchestrator (config.yaml is mounted via docker-compose)
CMD ["python", "orchestrator.py"]
