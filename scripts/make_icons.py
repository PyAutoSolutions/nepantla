"""Genera los iconos de la app instalada a partir del logo.

    python scripts/make_icons.py

Necesita `rsvg-convert` (paquete librsvg2-bin). Los PNG ya vienen en el
repositorio: solo hace falta correr esto si cambia el logo o los colores.

El logo son dos círculos que se cruzan. La parte de en medio, en color maíz,
es el "nepantla": el lugar entre dos orillas.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "frontend" / "icons"

ANIL = "#1f2a6b"
MAIZ = "#ffc93c"


def logo_svg(size: int, corner: int, scale: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 512 512">'
        f'<rect width="512" height="512" rx="{corner}" fill="{ANIL}"/>'
        f'<g transform="translate(256 256) scale({scale}) translate(-24 -24)" fill="none" stroke="#ffffff" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M24 13.050a13 13 0 0 1 0 21.900 13 13 0 0 1 0-21.900z" fill="{MAIZ}" stroke="none"/>'
        '<circle cx="17" cy="24" r="13"/><circle cx="31" cy="24" r="13"/>'
        "</g></svg>\n"
    )


def render(svg: str, target: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as tmp:
        tmp.write(svg)
    subprocess.run(["rsvg-convert", tmp.name, "-o", str(target)], check=True)
    Path(tmp.name).unlink(missing_ok=True)


def main() -> int:
    ICONS.mkdir(parents=True, exist_ok=True)
    (ICONS / "favicon.svg").write_text(logo_svg(512, 112, 8.0), encoding="utf-8")
    render(logo_svg(192, 112, 8.0), ICONS / "icon-192.png")
    render(logo_svg(512, 112, 8.0), ICONS / "icon-512.png")
    # "Maskable": Android recorta el icono en círculo; el logo va más chico.
    render(logo_svg(512, 0, 6.0), ICONS / "icon-maskable-512.png")
    render(logo_svg(180, 0, 7.0), ICONS / "apple-touch-icon.png")
    print("Iconos listos en", ICONS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
