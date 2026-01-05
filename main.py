import os
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

# -----------------------------------------------------------------------------
# Safe Celery import (NÃO quebra API se Redis não existir)
# -----------------------------------------------------------------------------
celery_app = None
try:
    from celery_app import app as celery_app
except Exception as e:
    logger.warning(f"⚠️ Celery not available at startup: {e}")

# -----------------------------------------------------------------------------
# Crawlers
# -----------------------------------------------------------------------------
from google_patents_crawler import google_crawler
from inpi_crawler import inpi_crawler

# -----------------------------------------------------------------------------
# FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Pharmyrus Patent Intelligence API",
    version="31.0.3"
)

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PatentSearchRequest(BaseModel):
    molecule: str
    brand: Optional[str] = None
    dev_codes: List[str] = []
    cas: Optional[str] = None
    async_mode: bool = True


# -----------------------------------------------------------------------------
# Healthcheck (Railway)
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "running", "service": "pharmyrus"}


# -----------------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------------
@app.post("/search")
async def search(payload: PatentSearchRequest):

    if not payload.molecule:
        raise HTTPException(status_code=400, detail="molecule is required")

    # -----------------------------
    # ASYNC (Celery)
    # -----------------------------
    if payload.async_mode:
        if not celery_app:
            raise HTTPException(
                status_code=503,
                detail="Celery not available (Redis not configured)"
            )

        task = celery_app.send_task(
            "pharmyrus.search",
            kwargs={
                "molecule": payload.molecule,
                "brand": payload.brand,
                "dev_codes": payload.dev_codes,
                "cas": payload.cas,
            }
        )

        return {
            "status": "submitted",
            "task_id": task.id
        }

    # -----------------------------
    # SYNC (debug)
    # -----------------------------
    results = await inpi_crawler.search_inpi(
        molecule=payload.molecule,
        brand=payload.brand or "",
        dev_codes=payload.dev_codes,
        groq_api_key=GROQ_API_KEY
    )

    return {
        "status": "completed",
        "count": len(results),
        "results": results
    }
