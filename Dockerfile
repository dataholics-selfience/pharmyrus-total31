FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY google_patents_crawler.py .
COPY inpi_crawler.py .
COPY wipo_crawler.py .
COPY family_resolver.py .
COPY materialization.py .
COPY merge_logic.py .
COPY patent_cliff.py .
COPY celery_app.py .
COPY tasks.py .

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# ⬇️ AQUI ESTÁ A CHAVE
CMD ["bash", "-c", "\
  if [ \"$ROLE\" = \"worker\" ]; then \
    celery -A celery_app worker --loglevel=info --concurrency=1; \
  else \
    uvicorn main:app --host 0.0.0.0 --port ${PORT}; \
  fi"]
