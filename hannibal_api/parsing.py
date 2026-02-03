from __future__ import annotations

import re
from typing import List


def parse_entity_ids(value: str) -> List[int]:
    """Parse entity ids from either "186" or "186,187"."""

    raw = [v.strip() for v in value.split(",") if v.strip()]
    if not raw:
        raise ValueError("entity id list is empty")

    out: List[int] = []
    for token in raw:
        if not re.fullmatch(r"\d+", token):
            raise ValueError(f"invalid entity id: {token!r}")
        eid = int(token)
        if eid < 1:
            raise ValueError(f"entity id must be >= 1, got: {eid}")
        out.append(eid)
    return out
