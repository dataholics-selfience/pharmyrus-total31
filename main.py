import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# =========================================
# CONFIG
# =========================================

ROLE = os.getenv("ROLE", "api").lower()
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

# =========================================
# FASTAPI APP (somente API)
# =========================================

app = FastAPI(title="Pharmyrus API", version="1.0.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "role": ROLE
    }


# =========================================
# API ENDPOINTS
# =========================================

if ROLE == "api":
    from tasks import run_search

    @app.post("/search")
    def search(payload: dict):
        task = run_search.delay(payload)
        return {
            "task_id": task.id,
            "status": "queued"
        }


# =========================================
# STARTUP LOG
# =========================================

logger.info(f"🚀 Starting Pharmyrus with ROLE={ROLE}")
