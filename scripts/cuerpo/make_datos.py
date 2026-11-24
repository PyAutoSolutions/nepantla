"""Junta las zonas de las seis vistas en frontend/js/cuerpo-datos.js.
Uso: python make_datos.py CARPETA_DE_RENDERS  (la que usó zonemap.py)."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = Path(sys.argv[1])
body = {"female": "mujer", "male": "hombre"}
views = {"front": "frente", "back": "espalda", "face": "cara"}
out = ['/* Mapa del cuerpo: imágenes y zonas. Archivo GENERADO por',
       '   scripts/cuerpo/zonemap.py a partir del modelo 3D (MakeHuman, CC0).',
       '   No se edita a mano: se vuelve a generar. Cada zona es',
       '   [id, trazo SVG, x e y donde va la palomita]. */', '', 'export const CUERPOS = {']
for s, es in body.items():
    out.append(f'  {es}: {{')
    for v, ev in views.items():
        d = json.loads((src / f"{s}-{v}-zonas.json").read_text())
        out.append(f'    {ev}: {{')
        out.append(f'      img: "./img/cuerpo/{es}-{ev}.webp", w: {d["w"]}, h: {d["h"]},')
        out.append('      zonas: [')
        for z in sorted(d["zonas"], key=lambda z: -z[4]):  # las chicas al final, encima
            out.append(f'        [{json.dumps(z[0])}, "{z[1]}", {z[2]}, {z[3]}],')
        out.append('      ],')
        out.append('    },')
    out.append('  },')
out.append('};')
(ROOT / "frontend" / "js" / "cuerpo-datos.js").write_text("\n".join(out) + "\n", encoding="utf-8")
print("listo")
