# tasks.py

import time
import asyncio
from celery_app import app
from core.search_engine import search_patents


@app.task(bind=True, name="pharmyrus.search")
def search_task(self, molecule, countries=None, include_wipo=False):
    start_time = time.time()

    class TaskRequest:
        def __init__(self):
            self.nome_molecula = molecule
            self.nome_comercial = None
            self.paises_alvo = countries or ["BR"]
            self.incluir_wo = include_wipo
            self.max_results = 100

    request = TaskRequest()

    def progress_callback(progress, step):
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": progress,
                "step": step,
                "elapsed": round(time.time() - start_time, 1)
            }
        )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        search_patents(request, progress_callback)
    )
