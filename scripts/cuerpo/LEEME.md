# Cómo se hace el mapa del cuerpo

Las imágenes de `frontend/img/cuerpo/` y las zonas de
`frontend/js/cuerpo-datos.js` salen de un modelo humano 3D. No son fotos de
personas ni imágenes hechas con IA generativa.

## De dónde sale el cuerpo

- **MakeHuman** (https://github.com/makehumancommunity/makehuman): malla base
  `base.obj`, las formas de mujer y de hombre (`targets/macrodetails`) y el
  esqueleto con sus pesos (`rigs/default_weights.mhw`). El proyecto MakeHuman
  publicó todo eso con licencia **CC0 1.0** (ver su `LICENSE.md` y
  `LICENSE.ASSETS.md`), y dice expresamente que los renders son de quien los
  hace.
- Se usa una mezcla pareja de las tres formas étnicas de MakeHuman, piel
  morena media, cabello corto y ropa interior lisa.
- Mujer: 1.59 m. Hombre: 1.73 m. Postura en A, con los brazos separados para
  que se vean todas las partes.

## Cómo se calculan las zonas

`zones.py` clasifica cada cara de la malla 3D con dos cosas:

1. El hueso que más la mueve (pesos del esqueleto de MakeHuman): así se sabe
   si es brazo, antebrazo, mano, muslo, pierna, pie, cabeza o cuello. Codos y
   rodillas son lo que queda cerca de la articulación.
2. Medidas del propio modelo para el tronco: ombligo, pubis, pecho y la línea
   media. El abdomen usa las nueve regiones de la exploración clínica, con
   nombres sencillos («Boca del estómago», «Bajo vientre»…).

Como cada cara del modelo recibe una zona, **no queda ninguna parte del
cuerpo sin zona**. Derecha e izquierda son siempre las del paciente.

## Pasos

```bash
# 1. Bajar solo lo necesario de MakeHuman
mkdir -p scripts/cuerpo/trabajo && cd scripts/cuerpo/trabajo
git clone --depth 1 --filter=blob:none --sparse https://github.com/makehumancommunity/makehuman.git mh
cd mh && git sparse-checkout set --no-cone '/LICENSE*' '/makehuman/data/3dobjs' \
  '/makehuman/data/targets/macrodetails' '/makehuman/data/rigs' && cd ../..

# 2. Blender como módulo de Python (necesita Python 3.11)
python3.11 -m venv trabajo/bpy && trabajo/bpy/bin/pip install bpy numpy

# 3. (Opcional) Vista rápida de las zonas, sin Blender
python3 preview.py            # deja prev-*.png en trabajo/

# 4. Render realista e imagen de zonas de cada vista
for s in female male; do
  for v in front back; do trabajo/bpy/bin/python render.py $s $v 1200 64 trabajo/$s-$v both; done
  trabajo/bpy/bin/python render.py $s face 900 64 trabajo/$s-face both
done

# 5. WebP + trazos de cada zona, y el archivo de datos de la app
python3 zonemap.py trabajo/female-front ../../frontend/img/cuerpo/mujer-frente.webp 80
#   (igual para female-back → mujer-espalda, female-face → mujer-cara,
#    male-front → hombre-frente, male-back → hombre-espalda, male-face → hombre-cara)
python3 make_datos.py trabajo
```

`overlay.py` dibuja las orillas de las zonas sobre un render, para revisarlas a
ojo. Después de regenerar, corre `node --test tests_js/core.test.mjs`: la prueba
revisa que cada zona tenga nombre y que la derecha del paciente quede del lado
correcto en cada vista.

## Lo que falta

Que personal de salud y hablantes revisen si las zonas y sus nombres se
entienden en consulta (ver `docs/PENDIENTES.md`).
