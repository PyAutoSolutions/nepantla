"""Regenera la lista de archivos que el service worker guarda para el modo avión.

    python scripts/update_shell.py

Úsalo cada vez que agregues, quites o renombres un archivo dentro de
`frontend/`. Si se te olvida, la prueba
`test_el_service_worker_guarda_todo_el_cascaron` falla y te lo recuerda.

No entran en la lista: el propio `sw.js`, la carpeta `audio/` (audios
opcionales que solo se usan con internet) ni los archivos .md y .txt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SW = FRONTEND / "sw.js"


def shell_files() -> list[str]:
    files = []
    for path in sorted(FRONTEND.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(FRONTEND).as_posix()
        if relative == "sw.js" or relative.startswith("audio/") or relative.endswith((".md", ".txt")):
            continue
        files.append(relative)
    # Primero lo indispensable para pintar la primera pantalla.
    first = ["index.html", "app.js", "css/app.css", "manifest.webmanifest"]
    return [f for f in first if f in files] + [f for f in files if f not in first]


def main() -> int:
    source = SW.read_text(encoding="utf-8")
    lines = ['  "./",'] + [f'  "./{name}",' for name in shell_files()]
    block = "const SHELL = [\n" + "\n".join(lines) + "\n];"
    updated, count = re.subn(r"const SHELL = \[.*?\n\];", lambda _: block, source, count=1, flags=re.S)
    if count != 1:
        print("No encontré la lista SHELL dentro de frontend/sw.js")
        return 1
    if updated != source:
        SW.write_text(updated, encoding="utf-8")
    print(f"sw.js: {len(lines)} entradas en el cascarón")
    return 0


if __name__ == "__main__":
    sys.exit(main())
