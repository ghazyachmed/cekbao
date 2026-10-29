"""Worker process: relays the outbox and processes leased jobs. Run: python -m policyguard.worker

Stops cleanly on SIGINT/SIGTERM after the current job. Several workers can run at once; leases use
FOR UPDATE SKIP LOCKED, so each job is processed by one worker at a time.
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import time

from .runtime import build_runtime

log = logging.getLogger("policyguard.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    rt = build_runtime()
    owner = f"{socket.gethostname()}:{os.getpid()}"
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    mode = "live" if rt.settings.paid_inference_enabled else "rules (paid inference disabled)"
    log.info("worker %s started; extraction mode: %s", owner, mode)
    idle = 0.2
    while not stopping:
        relayed = rt.container.worker.relay()
        worked = rt.container.worker.run_once(owner)
        if worked or relayed:
            idle = 0.2
            continue
        time.sleep(idle)
        idle = min(idle * 2, 2.0)
    log.info("worker %s stopped", owner)


if __name__ == "__main__":
    main()
