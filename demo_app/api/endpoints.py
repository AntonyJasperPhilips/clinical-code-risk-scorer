"""Thin in-memory API layer used by the demo UI."""

from typing import Dict, List


def paginate(items: List[dict], page: int, page_size: int = 20) -> Dict[str, object]:
    """Return a page slice plus pagination metadata.

    Pages are 1-indexed. Raises ValueError for non-positive page/page_size.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    start = (page - 1) * page_size
    end = start + page_size
    total = len(items)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "results": items[start:end],
    }


def search_patients(patients: List[dict], query: str) -> List[dict]:
    """Case-insensitive substring search over patient names."""
    q = query.strip().lower()
    if not q:
        return list(patients)
    return [p for p in patients if q in p.get("name", "").lower()]
