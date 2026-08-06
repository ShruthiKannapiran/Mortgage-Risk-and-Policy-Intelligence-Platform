import logging
import os
import sys

_CONFIGURED = False


def get_logger(name):
    global _CONFIGURED
    if not _CONFIGURED:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )
        _CONFIGURED = True
    return logging.getLogger(name)
