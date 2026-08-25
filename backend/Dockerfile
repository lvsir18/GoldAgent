FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NUMBA_CACHE_DIR=/app/.cache/numba
WORKDIR /app
RUN addgroup --system goldagent && adduser --system --ingroup goldagent goldagent

COPY pyproject.toml README.md ./
COPY src ./src
COPY backend ./backend
COPY main.py run_backend.py config.yaml alembic.ini ./
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data /app/logs /app/reports /app/.cache/numba && chown -R goldagent:goldagent /app
USER goldagent
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
