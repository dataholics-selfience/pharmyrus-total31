import logging
import time
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

# ===== Existing Layers (NÃO MEXER) =====
from google_patents_crawler import search_google_patents
from inpi_crawler import (
    search_inpi_by_number,
    search_inpi_by_text
)
from merge_logic import merge_br_patents
from patent_cliff import calculate_patent_cliff

# ===== WIPO (NOVO – JÁ FUNCIONA) =====
from wipo_crawler import search_wipo_patents

# ===== Celery =====
try:
    from tasks import search_task
except ImportError:
    search_task = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

app = FastAPI(title="Pharmyrus Patent Intelligence API")

# ======================================================
# MODELS
# ======================================================

class SearchRequest(BaseModel):
    nome_molecula: str
    target_countries: List[str] = ["BR"]
    incluir_wo: bool = True
    async_mode: bool = False


# ======================================================
# CORE PIPELINE (SINCRONO)
# ======================================================

def run_patent_pipeline(req: SearchRequest) -> Dict[str, Any]:
    start_time = time.time()

    query = req.nome_molecula
    target_countries = req.target_countries

    result: Dict[str, Any] = {
        "metadata": {
            "query": query,
            "target_countries": target_countries,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "v33.0-PIPELINE"
        }
    }

    # ==================================================
    # FASE 1 — WIPO (DESCOBERTA RAIZ)
    # ==================================================
    wipo_wos = []
    if req.incluir_wo:
        try:
            logger.info("🌐 FASE 1: WIPO Discovery")
            wipo_wos = search_wipo_patents(query)
        except Exception as e:
            logger.error(f"WIPO failed (non-blocking): {e}")

    result["wipo_wos"] = wipo_wos

    # ==================================================
    # FASE 2 — GOOGLE PATENTS (EXPANSÃO)
    # ==================================================
    logger.info("🌐 FASE 2: Google Patents Expansion")
    google_wos, google_family = search_google_patents(query)

    # ==================================================
    # FASE 3 — CONSOLIDAÇÃO DE FAMÍLIAS
    # ==================================================
    all_wos = {wo["wo_number"] for wo in wipo_wos}
    all_wos.update(google_wos)

    family_map: Dict[str, Dict[str, List[str]]] = {}

    for wo, fam in google_family.items():
        family_map.setdefault(wo, {}).update(fam)

    result["all_wos"] = sorted(list(all_wos))
    result["family_map"] = family_map

    # ==================================================
    # FASE 4 — FILTRO POR PAÍS (SEM QUERY)
    # ==================================================
    candidates_by_country: Dict[str, List[str]] = {}

    for wo, fam in family_map.items():
        for country in target_countries:
            if country in fam:
                candidates_by_country.setdefault(country, []).extend(fam[country])

    result["candidates_by_country"] = candidates_by_country

    # ==================================================
    # FASE 5 — INPI (APENAS SE BR)
    # ==================================================
    br_patents = []
    br_orphans = []

    if "BR" in target_countries:
        logger.info("🇧🇷 FASE 5: INPI Materialization")

        br_numbers = list(set(candidates_by_country.get("BR", [])))

        # A) Busca direta por número
        direct_results = search_inpi_by_number(br_numbers)

        # B) Busca textual (PT-BR via Groq)
        text_results = search_inpi_by_text(query)

        # C) Merge final
        br_patents, br_orphans = merge_br_patents(
            direct_results,
            text_results
        )

    result["br_patents"] = br_patents
    result["br_orphans"] = br_orphans

    # ==================================================
    # FASE 6 — PATENT CLIFF
    # ==================================================
    result["patent_cliff"] = calculate_patent_cliff(br_patents)

    result["metadata"]["elapsed_seconds"] = round(time.time() - start_time, 2)

    return result


# ======================================================
# API ENDPOINTS
# ======================================================

@app.post("/search")
def search(req: SearchRequest, background: BackgroundTasks):
    if req.async_mode and search_task:
        task = search_task.delay(req.dict())
        return {"task_id": task.id, "status": "queued"}

    return run_patent_pipeline(req)


@app.post("/search/wipo")
def search_wipo_only(req: SearchRequest):
    return {
        "wipo_wos": search_wipo_patents(req.nome_molecula)
    }


@app.get("/health")
def health():
    return {"status": "ok"}
