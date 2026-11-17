# Atribuciones y licencias

Nepantla no carga nada de otros servidores. Todo lo que usa viaja dentro del
repositorio y está en esta lista.

## Resumen

| Qué | Autoría | Licencia |
|-----|---------|----------|
| Código (backend, frontend, scripts, pruebas) | Autores de Nepantla | MIT (archivo `LICENSE`) |
| Pictogramas (`frontend/icons/pictos.svg`) y logo | Originales de Nepantla | CC BY 4.0 |
| Frases en español (`frontend/data/phrases.es.json`) | Originales de Nepantla | CC BY 4.0 |
| Letra Atkinson Hyperlegible | Braille Institute of America, Inc. (2020) | SIL Open Font License 1.1 (`frontend/fonts/OFL.txt`) |
| Generador de códigos QR (`frontend/vendor/qrcode.js`) | Kazuhiko Arase (2009) | MIT |
| Audios de prueba (`packs/`) | Generados por `scripts/make_test_packs.py` | CC0 1.0 |
| **Voces de cada lengua** | **Quien las grabó y su comunidad** | **La que elija cada comunidad** (ver la ficha y el `LICENSE.txt` de cada paquete) |

La licencia del código **no cubre las voces**. Ver `docs/GOVERNANCE.md`.

## Pictogramas

Los 124 pictogramas del archivo `frontend/icons/pictos.svg` fueron
dibujados para este proyecto. No se copió ningún juego de iconos ajeno.

- Licencia de todos ellos: **Creative Commons Atribución 4.0 Internacional
  (CC BY 4.0)**. Cómo atribuir: «Pictogramas de Nepantla, CC BY 4.0».
- Están hechos en una cuadrícula de 48 x 48 con trazo de color `currentColor`,
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

Lista completa de identificadores (todos con la misma licencia, CC BY 4.0):

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
