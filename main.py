import os
import logging
from typing import List, Dict, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from celery_app import celery_app
from tasks import run_full_patent_search

from google_patents_crawler import google_crawler
from inpi_crawler import inpi_crawler

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

# -----------------------------------------------------------------------------
# FastAPI App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Pharmyrus Patent Intelligence API",
    version="31.0.3",
    description="Freedom to Operate & Patent Discovery Engine"
)

# -----------------------------------------------------------------------------
# ENV VARS (Railway)
# -----------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.warning("⚠️ GROQ_API_KEY not set")

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PatentSearchRequest(BaseModel):
    molecule: str
    brand: Optional[str] = None
    dev_codes: List[str] = []
    cas: Optional[str] = None
    country_target: str = "BR"
    async_mode: bool = True


class PatentSearchResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    message: str


# -----------------------------------------------------------------------------
# Healthcheck (CRÍTICO para Railway)
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "Pharmyrus",
        "version": "31.0.3",
        "status": "running"
    }


# -----------------------------------------------------------------------------
# Main Search Endpoint
# -----------------------------------------------------------------------------
@app.post("/search", response_model=PatentSearchResponse)
async def search_patents(payload: PatentSearchRequest):
    """
    Main entry point for patent search
    Supports sync (debug) and async (Celery) execution
    """

    if not payload.molecule:
        raise HTTPException(status_code=400, detail="Molecule is required")

    logger.info("🔎 New patent search request")
    logger.info(f"   Molecule: {payload.molecule}")
    logger.info(f"   Brand: {payload.brand}")
    logger.info(f"   Country target: {payload.country_target}")
    logger.info(f"   Async: {payload.async_mode}")

    # -------------------------
    # ASYNC MODE (PRODUCTION)
    # -------------------------
    if payload.async_mode:
        task = celery_app.send_task(
            "pharmyrus.search",
            kwargs={
                "molecule": payload.molecule,
                "brand": payload.brand,
                "dev_codes": payload.dev_codes,
                "cas": payload.cas,
                "country_target": payload.country_target,
            }
        )

        return PatentSearchResponse(
            task_id=task.id,
            status="submitted",
            message="Patent search started asynchronously"
        )

    # -------------------------
    # SYNC MODE (DEBUG / DEV)
    # -------------------------
    try:
        results = await run_full_patent_search(
            molecule=payload.molecule,
            brand=payload.brand,
            dev_codes=payload.dev_codes,
            cas=payload.cas,
            country_target=payload.country_target,
            groq_api_key=GROQ_API_KEY
        )

        return PatentSearchResponse(
            status="completed",
            message=f"Search completed with {len(results)} results"
        )

    except Exception as e:
        logger.exception("❌ Search failed")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Direct INPI Endpoint (Opcional, mas útil)
# -----------------------------------------------------------------------------
@app.post("/search/inpi")
async def search_inpi_only(payload: PatentSearchRequest):
    """
    Direct INPI search (debug / diagnostics)
    """

    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    results = await inpi_crawler.search_inpi(
        molecule=payload.molecule,
        brand=payload.brand or "",
        dev_codes=payload.dev_codes,
        groq_api_key=GROQ_API_KEY
    )

    return {
        "source": "INPI",
        "count": len(results),
        "results": results
    }
