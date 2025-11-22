from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any

__all__ = ["render_pdf"]

def render_pdf(
    meta: Optional[Dict[str, Any]] = None,
    output_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Minimal PDF stub. Writes a tiny valid PDF if output_path is set; otherwise returns metadata."""
    meta = meta or {"title": "Demo"}
    if output_path is not None:
        p = Path(output_path)
        try:
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4\n% stub\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
        except Exception:
            p.write_text("stub artifact", encoding="utf-8")
        return {"output_path": str(p), "meta": meta}
    return {"output_path": None, "meta": meta}
