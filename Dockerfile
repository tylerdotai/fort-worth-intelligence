FROM python:3.12-slim

WORKDIR /app

# Install system deps for shapely, pyproj, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gdal-bin libproj-dev proj-bin \
    libgeos-dev libxml2 libxslt1-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

ENV PORT=8000
ENV FWI_LOG_LEVEL=INFO
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
