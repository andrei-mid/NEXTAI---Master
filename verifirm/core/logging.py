"""Structured logging. Every record carries run_id, cui and agent from context variables.

Usage:
    log = get_logger(__name__)
    with log_context(run_id=run.run_id, cui=run.cui):
        log.info("identity sheet built", extra={"n_sources": 3})
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_CONTEXT_FIELDS = ("run_id", "cui", "agent")
_context: dict[str, ContextVar[str | None]] = {
    name: ContextVar(f"verifirm_{name}", default=None) for name in _CONTEXT_FIELDS
}
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


@contextmanager
def log_context(**values: str | None) -> Iterator[None]:
    """Bind run_id / cui / agent for every log record emitted inside the block."""
    unknown = set(values) - set(_CONTEXT_FIELDS)
    if unknown:
        raise ValueError(f"unknown log context fields: {sorted(unknown)}")
    tokens = {name: _context[name].set(value) for name, value in values.items()}
    try:
        yield
    finally:
        for name, token in tokens.items():
            _context[name].reset(token)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for name, var in _context.items():
            if not hasattr(record, name):
                setattr(record, name, var.get())
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ContextFilter())
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [%(run_id)s %(cui)s %(agent)s] %(message)s"
            )
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
