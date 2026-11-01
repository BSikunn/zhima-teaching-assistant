FROM node:22.14.0-alpine AS frontend
WORKDIR /build
ENV npm_config_cache=/build/.cache/npm
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11.13-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache TMPDIR=/app/.cache/tmp
WORKDIR /app
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY backend/app/ ./backend/app/
COPY resources/course-library/ ./resources/course-library/
COPY scripts/import-course-library.py ./scripts/import-course-library.py
RUN mkdir -p /app/data /app/logs /app/.cache/tmp /app/models
EXPOSE 8765 8767
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]

FROM nginx:1.28.0-alpine AS web
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /build/dist/ /usr/share/nginx/html/
EXPOSE 80
