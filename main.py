import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus-api")

app = FastAPI(title="Pharmyrus API", version="1.0.0")


# =========================
# Healthcheck
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# Request model
# =========================
class SearchRequest(BaseModel):
    molecule: str
    countries: Optional[List[str]] = ["BR"]
    include_wipo: bool = False


# =========================
# Search endpoint
# =========================
@app.post("/search")
def search(req: SearchRequest):
    try:
        from celery_app import app as celery_app  # IMPORT LAZY

        task = celery_app.send_task(
            "pharmyrus.search",
            args=[req.molecule, req.countries, req.include_wipo]
        )

        return {
            "task_id": task.id,
            "status": "queued"
        }

    except Exception as e:
        logger.exception("Failed to enqueue task")
        raise HTTPException(status_code=500, detail=str(e))
