# Atribuciones y licencias

Nepantla no carga nada de otros servidores. Todo lo que usa viaja dentro del
repositorio y está en esta lista.

## Resumen

| Qué | Autoría | Licencia |
|-----|---------|----------|
| Código (backend, frontend, scripts, pruebas) | Autores de Nepantla | MIT (archivo `LICENSE`) |
| Pictogramas de interfaz y logo (`frontend/icons/pictos.svg`) | Originales de Nepantla | CC BY 4.0 |
| 56 pictogramas a color (mismo archivo, lista abajo) | Fluent Emoji Flat, Microsoft Corporation | MIT (`frontend/icons/LICENSE-fluent-emoji.txt`) |
| Imágenes del mapa del cuerpo (`frontend/img/cuerpo/`) | Render propio del modelo 3D de MakeHuman | Modelo: CC0 1.0. Imágenes: CC0 1.0 |
| Frases en español (`frontend/data/phrases.es.json`) | Originales de Nepantla | CC BY 4.0 |
| Letra Atkinson Hyperlegible | Braille Institute of America, Inc. (2020) | SIL Open Font License 1.1 (`frontend/fonts/OFL.txt`) |
| Generador de códigos QR (`frontend/vendor/qrcode.js`) | Kazuhiko Arase (2009) | MIT |
| Audios de prueba (`packs/`) | Generados por `scripts/make_test_packs.py` | CC0 1.0 |
| **Voces de cada lengua** | **Quien las grabó y su comunidad** | **La que elija cada comunidad** (ver la ficha y el `LICENSE.txt` de cada paquete) |

La licencia del código **no cubre las voces**. Ver `docs/GOVERNANCE.md`.

## Pictogramas

El archivo `frontend/icons/pictos.svg` tiene 124 pictogramas. Los de la
interfaz y 15 de contenido son dibujos originales de este proyecto. Desde el
24 de noviembre de 2026, 56 pictogramas de contenido usan dibujos a color de
**Fluent Emoji Flat** (ver «Pictogramas a color» más abajo), porque los de línea en
blanco y negro costaban más trabajo de reconocer.

- Licencia de los dibujos originales: **Creative Commons Atribución 4.0 Internacional
  (CC BY 4.0)**. Cómo atribuir: «Pictogramas de Nepantla, CC BY 4.0».
- Los originales están hechos en una cuadrícula de 48 x 48 con trazo de color `currentColor`,
  así heredan el color del texto y se ven bien en claro y en oscuro.
- El significado nunca depende solo del color: el rojo y el amarillo
  refuerzan una forma que ya se entiende sin ellos.

Dos decisiones que conviene conocer antes de modificarlos:

1. **Las cruces no son rojas.** La cruz roja sobre fondo blanco es un emblema
   protegido por los Convenios de Ginebra y por la legislación mexicana. En
   `urgencias`, `hospital` y `regresar` la cruz va en el color de la tinta.
2. **Las caritas de dolor (`cara-0` a `cara-5`) son propias.** No son la
   escala Wong-Baker FACES® ni la Faces Pain Scale Revised, que tienen sus
   propias condiciones de uso. Son seis dibujos originales que acompañan a
   los números del 0 al 10.

Lista completa de identificadores. Los que aparecen en la sección «Pictogramas a color» usan el dibujo de Fluent Emoji (MIT); los demás son originales (CC BY 4.0):

| | | | |
|---|---|---|---|
| `logo` | `altavoz` | `pausa` | `detener` |
| `grabar` | `microfono` | `si` | `no` |
| `entendi` | `no-entendi` | `emergencia` | `atras` |
| `adelante` | `inicio` | `descargar` | `borrar` |
| `info` | `imprimir` | `copiar` | `pantalla` |
| `repetir` | `bandera` | `ajustes` | `con-red` |
| `sin-red` | `paquete` | `escudo` | `hoy` |
| `dias` | `semanas` | `paciente` | `personal` |
| `qr` | `ok` | `mas` | `menos` |
| `compartir` | `saludo` | `lista` | `resumen` |
| `tarjeta` | `doble-revision` | `reloj` | `enlace` |
| `ojo` | `telefono` | `gente` | `documento` |
| `urgencias` | `alarma` | `respirar` | `pecho` |
| `sangre` | `pregunta` | `dolor` | `escala-dolor` |
| `calendario` | `desmayo` | `convulsion` | `golpe-cabeza` |
| `dolor-cabeza` | `debilidad` | `vomito` | `fiebre` |
| `caida` | `animal` | `diabetes` | `presion` |
| `embarazo` | `meses` | `bebe-movimiento` | `liquido` |
| `vision` | `oido` | `hinchazon` | `dolor-estomago` |
| `parto` | `orinar` | `diarrea` | `sangre-excremento` |
| `consulta` | `nino` | `beber` | `dormido` |
| `tos` | `cartilla` | `pastilla` | `frasco` |
| `medicina-hoy` | `planta` | `medicina-mal` | `alergia` |
| `una-vez` | `dos-veces` | `tres-veces` | `con-comida` |
| `todos-los-dias` | `no-alcohol` | `explicar` | `duda` |
| `revisar` | `muestra-sangre` | `inyeccion` | `suero` |
| `radiografia` | `acuerdo` | `familia` | `decir-no` |
| `interprete` | `hospital` | `regresar` | `cita` |
| `herida` | `mareo` | `edad-recien-nacido` | `edad-bebe` |
| `edad-nino-chico` | `edad-nino-grande` | `cara-0` | `cara-1` |
| `cara-2` | `cara-3` | `cara-4` | `cara-5` |

Para ver todos juntos: `python scripts/contact_sheet.py pictos.png`.

Si se agrega un icono de terceros, hay que anotarlo aquí con su autor, su
licencia y su origen **antes** de usarlo.

## Pictogramas a color (Fluent Emoji)

Origen: Fluent Emoji Flat de Microsoft Corporation
(https://github.com/microsoft/fluentui-emoji), tomados del paquete
`@iconify-json/fluent-emoji-flat` 1.2.6. Licencia MIT; el aviso completo está
en `frontend/icons/LICENSE-fluent-emoji.txt`. Se combinaron (un dibujo grande
y, a veces, uno chico en la esquina) con `scripts/pictos/build_pictos.py`. Las
personas usan el tono de piel medio.

No se usaron los emoji de hospital ni de ambulancia porque llevan una cruz
roja: `urgencias`, `hospital` y `regresar` siguen siendo los dibujos
originales con la cruz en color de tinta.

| | | | |
|---|---|---|---|
| `acuerdo` | `alarma` | `alergia` | `animal` |
| `bebe-movimiento` | `beber` | `calendario` | `cartilla` |
| `cita` | `con-comida` | `consulta` | `convulsion` |
| `decir-no` | `desmayo` | `diabetes` | `diarrea` |
| `dolor` | `dolor-cabeza` | `dormido` | `dos-veces` |
| `edad-bebe` | `edad-nino-chico` | `edad-nino-grande` | `edad-recien-nacido` |
| `embarazo` | `explicar` | `familia` | `fiebre` |
| `golpe-cabeza` | `herida` | `inyeccion` | `liquido` |
| `mareo` | `medicina-hoy` | `medicina-mal` | `meses` |
| `muestra-sangre` | `nino` | `no-alcohol` | `oido` |
| `orinar` | `parto` | `pastilla` | `planta` |
| `pregunta` | `respirar` | `revisar` | `saludo` |
| `sangre` | `sangre-excremento` | `todos-los-dias` | `tos` |
| `tres-veces` | `una-vez` | `vision` | `vomito` |

## Imágenes del mapa del cuerpo

`frontend/img/cuerpo/*.webp` son renders hechos para Nepantla con Blender a
partir del modelo humano de **MakeHuman** (malla base, targets de forma y
esqueleto), que el proyecto MakeHuman publicó con licencia **CC0 1.0**
(https://github.com/makehumancommunity/makehuman, archivos `LICENSE.md` y
`LICENSE.ASSETS.md`). No son fotos de personas reales ni imágenes hechas con
IA generativa. Las zonas que se pueden tocar (`frontend/js/cuerpo-datos.js`)
salen del mismo modelo 3D. Cómo se generan: `scripts/cuerpo/LEEME.md`.
Las imágenes también se entregan con licencia CC0 1.0.

## Letra

**Atkinson Hyperlegible**, diseñada por el Braille Institute para que las
letras parecidas (I, l, 1; O, 0) se distingan mejor con baja visión.
Copyright 2020 Braille Institute of America, Inc. Licencia SIL Open Font
License 1.1; el texto completo está en `frontend/fonts/OFL.txt`. Se sirven
dos pesos (400 y 700) desde el propio servidor.

## Código QR

`frontend/vendor/qrcode.js` es «QR Code Generator for JavaScript», Copyright
(c) 2009 Kazuhiko Arase, licencia MIT. El archivo conserva su aviso original.
«QR Code» es marca registrada de DENSO WAVE INCORPORATED.

## Audios de prueba

Los archivos de `packs/pack-prueba-*` son tonos generados por computadora.
No contienen voz humana ni representan a ninguna lengua, comunidad o
persona. Se entregan al dominio público (CC0 1.0).

## Fuentes de las frases

Las listas oficiales que se consultaron para redactar las frases de embarazo,
niñez y señales de alarma están en `docs/FUENTES.md`. Las frases son
redacción propia a partir de esas listas; no copian su texto.

## Dependencias de Python

FastAPI, Uvicorn, Pydantic y python-multipart (para correr el servidor), y
pytest, httpx, Playwright, Pillow y zxing-cpp (solo para las pruebas). Cada
una conserva su propia licencia; se instalan con `pip` y no se redistribuyen
dentro de este repositorio. La conversión de audio usa ffmpeg con libopus,
que se instala aparte.
