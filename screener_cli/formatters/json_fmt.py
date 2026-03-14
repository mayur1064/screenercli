"""JSON formatter — serialises dataclasses to a JSON string."""

from __future__ import annotations

import dataclasses
import json
from typing import Any


def _default(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(data: Any, indent: int = 2) -> str:
    """
    Serialise *data* (dataclass, dict, or list) to a formatted JSON string.

    Dataclass instances are recursively converted via ``dataclasses.asdict``.
    """
    return json.dumps(data, default=_default, indent=indent, ensure_ascii=False)


def print_json(data: Any) -> None:
    """Print the JSON representation of *data* to stdout."""
    print(to_json(data))
