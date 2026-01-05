import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Crawlers (já existentes)
from wipo_crawler import search_wipo_patents
from epo_crawler import search_epo_patents
from google_patents import search_google_patents
from inpi_crawler import search_inpi_patents
from pubchem import resolve_synonyms

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

app = FastAPI()


# ============================================================================
# MODELS
# ============================================================================

class SearchRequest(BaseModel):
    nome_molecula: str
    pais_alvo: str = "BR"


# ============================================================================
# SAFE EXECUTION HELPERS
# ============================================================================

async def safe_run(name: str, coro):
    """
    Executa qualquer crawler sem quebrar o fluxo.
    """
    try:
        logger.info(f"▶️ Starting {name}")
        result = await coro
        logger.info(f"✅ {name} finished")
        return result
    except Exception as e:
        logger.error(f"❌ {name} failed: {e}")
        return []


# ============================================================================
# MAIN ENDPOINT
# ============================================================================

@app.post("/search/wipo")
async def search_wipo_only(req: SearchRequest):
    """
    Endpoint isolado (mantido)
    """
    results = await safe_run(
        "WIPO",
        search_wipo_patents(
            molecule=req.nome_molecula,
            max_results=50,
            headless=True
        )
    )

    return {
        "metadata": {
            "molecule_name": req.nome_molecula,
            "search_date": datetime.utcnow().isoformat(),
            "source": "WIPO PatentScope only",
        },
        "wipo_patents": results,
    }


@app.post("/search/full")
async def search_full(req: SearchRequest):
    """
    PIPELINE COMPLETO – RESILIENTE
    """
    start = datetime.utcnow()

    # 1️⃣ Resolver sinônimos (uma vez só)
    synonyms = await safe_run(
        "PubChem Synonyms",
        resolve_synonyms(req.nome_molecula)
    )

    # 2️⃣ Fan-out de buscas (em paralelo)
    wipo_task = safe_run(
        "WIPO",
        search_wipo_patents(
            molecule=req.nome_molecula,
            dev_codes=synonyms.get("dev_codes"),
            cas=synonyms.get("cas"),
            max_results=200,
            headless=True
        )
    )

    epo_task = safe_run(
        "EPO",
        search_epo_patents(req.nome_molecula, synonyms)
    )

    google_task = safe_run(
        "Google Patents",
        search_google_patents(req.nome_molecula, synonyms)
    )

    wipo, epo, google = await asyncio.gather(
        wipo_task, epo_task, google_task
    )

    # 3️⃣ Consolidar WOs e BRs
    all_wos = {
        p["wo_number"]
        for src in (wipo, epo, google)
        for p in src
        if "wo_number" in p
    }

    br_patents = [
        p for p in google
        if p.get("country") == req.pais_alvo
    ]

    # 4️⃣ INPI somente se houver BR
    inpi = []
    if br_patents:
        inpi = await safe_run(
            "INPI",
            search_inpi_patents(br_patents, synonyms)
        )

    # 5️⃣ Resposta final
    return {
        "metadata": {
            "molecule_name": req.nome_molecula,
            "pais_alvo": req.pais_alvo,
            "elapsed_seconds": (datetime.utcnow() - start).total_seconds(),
            "version": "vFINAL-resilient",
        },
        "sources": {
            "wipo": len(wipo),
            "epo": len(epo),
            "google": len(google),
            "inpi": len(inpi),
        },
        "results": {
            "wipo": wipo,
            "epo": epo,
            "google": google,
            "inpi": inpi,
        },
    }
