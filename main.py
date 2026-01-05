import asyncio
import logging
from typing import List, Dict, Any, Set

from fastapi import FastAPI
from pydantic import BaseModel

# ===== Imports REAIS dos módulos existentes =====
from wipo_crawler import search_wipo_patents
from google_patents_crawler import google_crawler
from inpi_crawler import (
    search_inpi_by_number,
    search_inpi_by_text
)

# =================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

app = FastAPI(title="Pharmyrus API", version="v32.1")


# =========================
# Models
# =========================

class WipoRequest(BaseModel):
    nome_molecula: str
    brand_name: str | None = None
    dev_codes: List[str] | None = []
    cas: str | None = None
    target_countries: List[str] | None = ["BR"]


# =========================
# Healthcheck
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# MAIN SEARCH ENDPOINT
# =========================

@app.post("/search/wipo")
async def search_wipo_pipeline(req: WipoRequest):
    """
    Pipeline:
    1. WIPO (raiz PCT)
    2. Google Patents (complemento agressivo)
    3. INPI (materialização BR, lógica preservada)
    """

    molecule = req.nome_molecula
    brand = req.brand_name
    dev_codes = req.dev_codes or []
    cas = req.cas
    target_countries = req.target_countries or ["BR"]

    logger.info(f"🌐 Pipeline start | molecule={molecule}")

    # =====================================================
    # FASE 1 — WIPO (ROOT)
    # =====================================================
    wipo_results = await search_wipo_patents(
        molecule=molecule,
        dev_codes=dev_codes,
        cas=cas,
        max_results=200,
        headless=True
    )

    wipo_wos: Set[str] = {
        item["wo_number"]
        for item in wipo_results
        if item.get("wo_number")
    }

    logger.info(f"✅ WIPO: {len(wipo_wos)} WOs encontrados")

    # =====================================================
    # FASE 2 — GOOGLE PATENTS (COMPLEMENTO)
    # =====================================================
    google_new_wos = await google_crawler.search_google_patents(
        molecule=molecule,
        brand=brand,
        dev_codes=dev_codes,
        cas=cas,
        existing_wos=wipo_wos
    )

    all_wos = wipo_wos.union(google_new_wos)

    logger.info(
        f"🔎 Google Patents: +{len(google_new_wos)} WOs | Total={len(all_wos)}"
    )

    # =====================================================
    # FASE 3 — INPI (BR ONLY, LÓGICA PRESERVADA)
    # =====================================================
    br_patents = []
    br_orphans = []

    if "BR" in target_countries:
        logger.info("🇧🇷 INPI materialization started")

        # A) Busca direta por números BR (se existirem)
        for wo in all_wos:
            try:
                result = await search_inpi_by_number(wo)
                if result:
                    br_patents.append(result)
            except Exception as e:
                logger.warning(f"INPI number error {wo}: {e}")

        # B) Busca textual PT-BR (Groq)
        try:
            text_results = await search_inpi_by_text(
                molecule=molecule,
                dev_codes=dev_codes
            )
            br_orphans.extend(text_results)
        except Exception as e:
            logger.warning(f"INPI text search error: {e}")

    # =====================================================
    # RESPONSE
    # =====================================================
    return {
        "metadata": {
            "molecule": molecule,
            "total_wos": len(all_wos),
            "wipo_wos": len(wipo_wos),
            "google_new_wos": len(google_new_wos),
            "target_countries": target_countries
        },
        "wipo_patents": wipo_results,
        "google_new_wos": sorted(list(google_new_wos)),
        "br_patents": br_patents,
        "br_orphans": br_orphans
    }
