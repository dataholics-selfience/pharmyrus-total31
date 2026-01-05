# main.py

import os
from fastapi import FastAPI
from celery.result import AsyncResult
from celery_app import app as celery_app
from pydantic import BaseModel


ROLE = os.getenv("ROLE", "api")

app = FastAPI(title="Pharmyrus API")


class SearchRequest(BaseModel):
    nome_molecula: str
    paises_alvo: list[str] = ["BR"]
    incluir_wo: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "role": ROLE}


@app.post("/search")
def start_search(req: SearchRequest):
    task = celery_app.send_task(
        "pharmyrus.search",
        args=[req.nome_molecula, req.paises_alvo, req.incluir_wo]
    )

    return {
        "task_id": task.id,
        "status": "started"
    }


@app.get("/status/{task_id}")
def task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    return {
        "state": task.state,
        "result": task.result if task.ready() else None
    }
