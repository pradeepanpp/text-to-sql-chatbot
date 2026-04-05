# src/text_to_sql/utils/logger.py
"""Shared logger — same pattern as jailbreak project."""

import logging
import sys

def get_logger(name: str = "text_to_sql") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_logger()