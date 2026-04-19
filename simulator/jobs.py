from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

import requests

from . import simulate
from .config import DELINEO

logger = logging.getLogger(__name__)


class ProgressEmitter:
    def __init__(self, msg_queue: queue.Queue) -> None:
        self.msg_queue = msg_queue
        self.last_progress = -1
        self.last_message = None

    def __call__(self, current_step, max_steps, message=None) -> None:
        progress = int((current_step / max_steps) * 100)
        msg_changed = message is not None and message != self.last_message
        progress_changed = progress != self.last_progress
        if not msg_changed and not progress_changed:
            return

        self.last_progress = progress
        if message is not None:
            self.last_message = message
        self.msg_queue.put(
            {
                "type": "progress",
                "value": progress,
                "message": self.last_message,
            }
        )

    def upload_started(self) -> None:
        self.msg_queue.put(
            {
                "type": "progress",
                "value": 100,
                "message": "Uploading results...",
            }
        )

    def emit_error(self, message: str) -> None:
        self.msg_queue.put({"type": "error", "message": message})

    def emit_result(self, simulation_id: int) -> None:
        self.msg_queue.put({"type": "result", "data": {"id": simulation_id}})


class SimulationResultUploader:
    def __init__(
        self,
        base_url: str = DELINEO["DB_URL"],
        session: Optional[requests.Session] = None,
        retries: int = 2,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url
        self.session = session or requests.Session()
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

    def upload(self, sim_data: dict, file_paths: dict) -> tuple[Optional[int], Optional[str]]:
        simulation_id = None
        last_error = None

        for attempt in range(self.retries):
            with open(file_paths["simdata"], "rb") as simdata_file, open(
                file_paths["patterns"], "rb"
            ) as patterns_file:
                try:
                    response = self.session.post(
                        f"{self.base_url}simdata",
                        data={
                            "czone_id": int(sim_data["czone_id"]),
                            "length": int(sim_data["length"]),
                        },
                        files={
                            "simdata": ("simdata.json.gz", simdata_file, "application/gzip"),
                            "patterns": ("patterns.json.gz", patterns_file, "application/gzip"),
                        },
                        timeout=600,
                    )
                except requests.RequestException as request_error:
                    last_error = f"Network error uploading results: {request_error}"
                    logger.warning("[attempt %d] %s", attempt + 1, last_error)
                    time.sleep(self.retry_delay_seconds)
                    continue

            if not response.ok:
                last_error = f"Storage returned {response.status_code}"
                logger.warning("[attempt %d] %s", attempt + 1, last_error)
                time.sleep(self.retry_delay_seconds)
                continue

            try:
                simulation_id = response.json()["data"]["id"]
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as parse_error:
                body_len = len(response.content or b"")
                last_error = (
                    f"Storage response was not valid JSON "
                    f"(status {response.status_code}, {body_len} bytes): {parse_error}"
                )
                logger.warning("[attempt %d] %s", attempt + 1, last_error)
                time.sleep(self.retry_delay_seconds)
                continue

            break

        return simulation_id, last_error


@contextmanager
def managed_simulation_tempdir(base_dir: str) -> Iterator[str]:
    local_temp = os.path.join(base_dir, "sim_temp")
    os.makedirs(local_temp, exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir=local_temp)
    logger.info("Created temp dir: %s", temp_dir)
    try:
        yield temp_dir
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def run_simulation_job(
    sim_data: dict,
    msg_queue: queue.Queue,
    base_dir: str,
    uploader: Optional[SimulationResultUploader] = None,
) -> None:
    progress = ProgressEmitter(msg_queue)
    uploader = uploader or SimulationResultUploader()

    try:
        with managed_simulation_tempdir(base_dir) as temp_dir:
            file_paths = simulate.run_simulator(
                sim_data,
                enable_logging=False,
                output_dir=temp_dir,
                progress_callback=progress,
            )

            progress.upload_started()
            if "error" in file_paths:
                progress.emit_error(file_paths["error"])
                return

            simulation_id, last_error = uploader.upload(sim_data, file_paths)
            if simulation_id is not None:
                logger.info("Sent successfully")
                progress.emit_result(simulation_id)
                return

            progress.emit_error(
                f"Failed to save simulation results. {last_error or 'unknown error'}"
            )
    except Exception as exc:
        logger.exception("Simulation error")
        progress.emit_error(str(exc))
    finally:
        msg_queue.put(None)


def start_simulation_job(sim_data: dict, msg_queue: queue.Queue, base_dir: str) -> threading.Thread:
    thread = threading.Thread(
        target=run_simulation_job,
        args=(sim_data, msg_queue, base_dir),
    )
    thread.start()
    return thread


def stream_sse_messages(msg_queue: queue.Queue):
    while True:
        message = msg_queue.get()
        if message is None:
            break
        yield f"data: {json.dumps(message)}\n\n"
