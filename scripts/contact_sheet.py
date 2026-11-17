"""Hoja de contacto de los pictogramas, para revisarlos a ojo.

    python scripts/contact_sheet.py salida.png

Necesita `rsvg-convert` (paquete librsvg2-bin). No forma parte de la app.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPRITE = ROOT / "frontend" / "icons" / "pictos.svg"


def build(output: Path, columns: int = 10, cell: int = 96, only: list[str] | None = None) -> int:
    source = SPRITE.read_text(encoding="utf-8")
    ids = re.findall(r'<symbol[^>]*\bid="([^"]+)"', source)
    if only:
        ids = [i for i in ids if i in only]
    inner = source[source.index(">", source.index("<svg")) + 1 : source.rindex("</svg>")]
    rows = (len(ids) + columns - 1) // columns
    label = 16
    width, height = columns * cell, rows * (cell + label)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" color="#141B45">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        inner,
    ]
    for index, symbol in enumerate(ids):
        x = (index % columns) * cell
        y = (index // columns) * (cell + label)
        parts.append(f'<rect x="{x + 2}" y="{y + 2}" width="{cell - 4}" height="{cell - 4}" fill="none" stroke="#ccd" />')
        parts.append(f'<use href="#{symbol}" x="{x + 12}" y="{y + 12}" width="{cell - 24}" height="{cell - 24}"/>')
        parts.append(
            f'<text x="{x + cell / 2}" y="{y + cell + 10}" font-size="10" font-family="sans-serif" '
            f'text-anchor="middle" fill="#333">{symbol}</text>'
        )
    parts.append("</svg>")
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as tmp:
        tmp.write("\n".join(parts))
    subprocess.run(["rsvg-convert", tmp.name, "-o", str(output)], check=True)
    Path(tmp.name).unlink(missing_ok=True)
    return len(ids)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "pictos.png")
    print(build(target, only=sys.argv[2:] or None), "pictogramas ->", target)
