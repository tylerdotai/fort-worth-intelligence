FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install fastapi, uvicorn, pydantic, shapely, pyproj
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] pydantic \
    shapely pyproj requests

# Copy app
COPY api_server.py .
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY viewer/ ./viewer/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
