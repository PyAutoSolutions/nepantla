"""Genera el logo y los iconos de la app instalada.

    python scripts/make_icons.py

Necesita `rsvg-convert` (paquete librsvg2-bin). Los archivos ya vienen en el
repositorio: solo hace falta correr esto si cambia el logo o los colores.

El logo son dos globos de diálogo que se cruzan: dos lenguas que se encuentran
en la consulta. El de la izquierda toma el color del texto (blanco sobre añil,
tinta sobre papel) y el de la derecha es color jade. La parte de en medio, en
color maíz, es el "nepantla": el lugar entre dos orillas. Adentro van tres
rayitas de voz, porque la app solo usa voces humanas.

Escribe:
- el símbolo `logo` de `frontend/icons/pictos.svg` (rejilla de 48 x 48),
- `frontend/icons/favicon.svg` y los PNG de la app instalada.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "frontend" / "icons"

ANIL = "#1f2a6b"
TINTA = "#141b45"
MAIZ = "#ffc93c"
JADE = "#16a589"

# Dos círculos de radio 13 separados 12 unidades; centro vertical en 22.
R, CY, D = 13.0, 22.0, 12.0
CX1, CX2 = 24 - D / 2, 24 + D / 2


def _n(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _point(cx: float, degrees: float) -> tuple[float, float]:
    a = math.radians(degrees)
    return cx + R * math.cos(a), CY + R * math.sin(a)


def _tail(cx: float, side: int) -> str:
    """Colita del globo: side=-1 abajo a la izquierda, side=1 abajo a la derecha."""
    a1, a2 = (112, 146) if side < 0 else (68, 34)
    (x1, y1), (x2, y2) = _point(cx, a1), _point(cx, a2)
    tip = (cx + side * R * 0.95, CY + R * 1.30)
    c1 = (cx + side * R * 0.50, CY + R * 1.12)
    c2 = (cx + side * R * 0.98, CY + R * 0.95)
    return (
        f"M{_n(x1)} {_n(y1)}Q{_n(c1[0])} {_n(c1[1])} {_n(tip[0])} {_n(tip[1])}"
        f"Q{_n(c2[0])} {_n(c2[1])} {_n(x2)} {_n(y2)}Z"
    )


def _lens() -> str:
    h = math.sqrt(R * R - (D / 2) ** 2)
    return f"M24 {_n(CY - h)}A{_n(R)} {_n(R)} 0 0 1 24 {_n(CY + h)}A{_n(R)} {_n(R)} 0 0 1 24 {_n(CY - h)}Z"


def mark(left: str = "currentColor") -> str:
    """El logo en la rejilla de 48 x 48 (centrado en 24, 24.5)."""
    parts = []
    for cx, side, fill in ((CX1, -1, left), (CX2, 1, JADE)):
        parts.append(f'<circle cx="{_n(cx)}" cy="{_n(CY)}" r="{_n(R)}" fill="{fill}"/>')
        parts.append(f'<path d="{_tail(cx, side)}" fill="{fill}"/>')
    parts.append(f'<path d="{_lens()}" fill="{MAIZ}"/>')
    for x, height in ((20.9, 6.5), (24.0, 11.5), (27.1, 6.5)):
        parts.append(
            f'<rect x="{_n(x - 1.15)}" y="{_n(CY - height / 2)}" width="2.3" height="{_n(height)}" rx="1.15" fill="{TINTA}"/>'
        )
    return "".join(parts)


def symbol() -> str:
    return f'<symbol id="logo" viewBox="0 0 48 48"><g transform="translate(0 -0.5)">{mark()}</g></symbol>'


def logo_svg(size: int, corner: int, scale: float) -> str:
    s = 512 / 48 * scale
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 512 512">'
        f'<rect width="512" height="512" rx="{corner}" fill="{ANIL}"/>'
        f'<g transform="translate(256 256) scale({_n(s)}) translate(-24 -24.5)">{mark("#ffffff")}</g>'
        "</svg>\n"
    )


def render(svg: str, target: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as tmp:
        tmp.write(svg)
    subprocess.run(["rsvg-convert", tmp.name, "-o", str(target)], check=True)
    Path(tmp.name).unlink(missing_ok=True)


def update_sprite() -> None:
    sprite = ICONS / "pictos.svg"
    text = sprite.read_text(encoding="utf-8")
    new, count = re.subn(r'<symbol id="logo" [^\n]*</symbol>', symbol(), text)
    if count != 1:
        raise SystemExit("No encontré el símbolo «logo» en pictos.svg")
    sprite.write_text(new, encoding="utf-8")


def main() -> int:
    ICONS.mkdir(parents=True, exist_ok=True)
    update_sprite()
    (ICONS / "favicon.svg").write_text(logo_svg(512, 112, 0.92), encoding="utf-8")
    render(logo_svg(192, 112, 0.92), ICONS / "icon-192.png")
    render(logo_svg(512, 112, 0.92), ICONS / "icon-512.png")
    # "Maskable": Android recorta el icono en círculo; el logo va más chico.
    render(logo_svg(512, 0, 0.72), ICONS / "icon-maskable-512.png")
    render(logo_svg(180, 0, 0.84), ICONS / "apple-touch-icon.png")
    print("Logo e iconos listos en", ICONS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
