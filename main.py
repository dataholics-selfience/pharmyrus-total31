"""
Pharmyrus Main API
FastAPI entrypoint + core search orchestration
SAFE for Railway + Celery
"""

import os
import time
import logging
from typing import List, Optional, Callable

from fastapi import FastAPI
from pydantic import BaseModel

# -------------------------------------------------
# Logging
# -------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------

app = FastAPI(
    title="Pharmyrus API",
    version="31.0.3",
)

# -------------------------------------------------
# Health Check (Railway-safe)
# -------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}

# -------------------------------------------------
# Request Model
# -------------------------------------------------

class PatentSearchRequest(BaseModel):
    nome_molecula: str
    nome_comercial: Optional[str] = None
    paises_alvo: List[str] = ["BR"]
    incluir_wo: bool = False
    max_results: int = 100

# -------------------------------------------------
# Core Search Function (USED BY API + CELERY)
# -------------------------------------------------

async def search_patents(
    request: PatentSearchRequest,
    progress_callback: Optional[Callable[[int, str], None]] = None
):
    """
    Core orchestration logic.
    Can be called by:
    - FastAPI endpoint
    - Celery background task
    """

    start = time.time()

    def progress(pct: int, step: str):
        if progress_callback:
            progress_callback(pct, step)
        logger.info(f"[{pct}%] {step}")

    progress(0, "Initializing search")

    results = {
        "molecule": request.nome_molecula,
        "countries": request.paises_alvo,
        "sources": {},
        "started_at": start,
    }

    # -------------------------------
    # Google Patents
    # -------------------------------
    try:
        progress(10, "Searching Google Patents")
        from google_patents_crawler import search_google_patents

        results["sources"]["google_patents"] = search_google_patents(
            molecule=request.nome_molecula,
            countries=request.paises_alvo,
            max_results=request.max_results,
        )
    except Exception as e:
        logger.exception("Google Patents failed")
        results["sources"]["google_patents_error"] = str(e)

    # -------------------------------
    # INPI
    # -------------------------------
    try:
        progress(40, "Searching INPI")
        from inpi_crawler import search_inpi

        results["sources"]["inpi"] = search_inpi(
            molecule=request.nome_molecula,
            countries=request.paises_alvo,
        )
    except Exception as e:
        logger.exception("INPI failed")
        results["sources"]["inpi_error"] = str(e)

    # -------------------------------
    # WIPO (optional)
    # -------------------------------
    if request.incluir_wo:
        try:
            progress(70, "Searching WIPO")
            from wipo_crawler import search_wipo

            results["sources"]["wipo"] = search_wipo(
                molecule=request.nome_molecula,
            )
        except Exception as e:
            logger.exception("WIPO failed")
            results["sources"]["wipo_error"] = str(e)

    progress(90, "Merging results")

    try:
        from merge_logic import merge_patents
        results["merged"] = merge_patents(results["sources"])
    except Exception as e:
        logger.exception("Merge failed")
        results["merge_error"] = str(e)

    elapsed = round(time.time() - start, 1)
    progress(100, f"Completed in {elapsed}s")

    results["elapsed_seconds"] = elapsed
    return results

# -------------------------------------------------
# API Endpoint (SYNC trigger)
# -------------------------------------------------

@app.post("/search")
async def search_endpoint(request: PatentSearchRequest):
    logger.info(f"🔍 API search request: {request.nome_molecula}")
    return await search_patents(request)
