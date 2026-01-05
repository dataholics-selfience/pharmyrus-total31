import time
import logging
import traceback
import asyncio
from celery_app import app

logger = logging.getLogger("pharmyrus-tasks")


@app.task(bind=True, name="pharmyrus.search")
def search_task(self, molecule: str, countries: list, include_wipo: bool):
    start = time.time()

    try:
        def progress(pct, step):
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": pct,
                    "step": step,
                    "elapsed": round(time.time() - start, 1),
                },
            )

        from main import search_patents  # IMPORT CONTROLADO

        progress(5, "Starting search")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            search_patents(
                molecule=molecule,
                countries=countries,
                include_wipo=include_wipo,
                progress_callback=progress,
            )
        )

        progress(100, "Completed")
        return result

    except Exception as e:
        logger.error(traceback.format_exc())
        raise e
