FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN groupadd --gid 10001 factorygraph \
    && useradd --uid 10001 --gid factorygraph --create-home factorygraph

COPY --chown=factorygraph:factorygraph backend /app/backend
COPY --chown=factorygraph:factorygraph frontend /app/frontend
COPY --chown=factorygraph:factorygraph evaluation /app/evaluation
COPY --chown=factorygraph:factorygraph data /app/data
COPY --chown=factorygraph:factorygraph infra/schema.cypher /app/infra/schema.cypher

USER factorygraph

EXPOSE 8000 8501

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)"

CMD ["uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

