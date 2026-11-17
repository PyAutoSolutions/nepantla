"""Accesibilidad que se puede comprobar sin navegador: contraste de color.

La especificación pide contraste alto. Aquí se calcula, con la fórmula de
las WCAG 2.x, el contraste de las parejas de color que usa la hoja de estilos.
"""
from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "frontend" / "css" / "app.css"


def palette() -> dict[str, str]:
    root = re.search(r":root\s*\{(.*?)\n\}", CSS.read_text(encoding="utf-8"), re.S).group(1)
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", root))


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_el_texto_principal_tiene_contraste_alto():
    """Nivel AAA (7:1) en las parejas que llevan el texto que se lee."""
    c = palette()
    pairs = [
        ("tinta", "papel"),      # texto del personal sobre blanco
        ("papel", "anil"),       # zona del paciente
        ("tinta", "maiz"),       # botones amarillos y cintas de aviso
        ("tinta", "niebla"),     # tarjetas y campos
        ("maiz", "anil-hondo"),  # barra inferior y portada
        ("papel", "anil-hondo"),
    ]
    for front, back in pairs:
        ratio = contrast(c[front], c[back])
        assert ratio >= 7, f"{front} sobre {back}: {ratio:.1f}:1"


def test_el_texto_secundario_y_los_colores_de_estado_pasan_el_minimo():
    """Nivel AA (4.5:1) en texto menor y en los botones rojo y verde."""
    c = palette()
    pairs = [("gris", "papel"), ("gris", "niebla"), ("papel", "rojo"), ("papel", "verde"), ("rojo", "papel"), ("verde", "papel")]
    for front, back in pairs:
        ratio = contrast(c[front], c[back])
        assert ratio >= 4.5, f"{front} sobre {back}: {ratio:.1f}:1"
