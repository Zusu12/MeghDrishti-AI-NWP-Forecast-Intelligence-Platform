FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directory if not present
RUN mkdir -p static

# Railway injects $PORT; default to 8000 for local development
ENV PORT=8000

# Expose port (informational)
EXPOSE 8000

# Run with Railway-compatible port binding
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
