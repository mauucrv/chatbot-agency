# AgencyBot WhatsApp Chatbot
# Multi-stage build: Node.js for admin frontend + Python for backend

# ── Stage 1: Build admin frontend ──────────────────────────
FROM node:20-alpine AS admin-builder

WORKDIR /admin
COPY admin/package.json admin/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY admin/ .
RUN npm run build

# ── Stage 2: Python application ────────────────────────────
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies and remove build tools
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy application code (specific directories to avoid leaking secrets)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy built admin frontend from stage 1
COPY --from=admin-builder /admin/dist /app/admin/dist

# Create directories for credentials and backups
RUN mkdir -p /app/credentials /app/backups && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with graceful shutdown timeout
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
