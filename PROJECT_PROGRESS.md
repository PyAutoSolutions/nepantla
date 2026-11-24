# Nepantla: bitácora de avance

Este archivo existe para poder retomar el trabajo sin repetir nada si una
sesión se corta. Se actualiza al cerrar cada bloque. **No sustituye a
revisar los archivos**: antes de continuar, corre las pruebas de la sección 5.

Última actualización: 24 de noviembre de 2026. **Versión 0.1.0 terminada,
publicada en GitHub y en GitHub Pages, y desplegada en Railway en modo
demostración. Lo único que falta es trabajo de personas (sección 11).**

## 1. Objetivo

Construir completo el MVP descrito en «Nepantla: especificación de
construcción (MVP)»: una PWA que funciona sin internet para que personas que
hablan una lengua indígena de México y personal de salud se entiendan en una
consulta, usando **solo audios humanos revisados**, pictogramas, mapa
corporal y escala de dolor.

## 2. Reglas que no se pueden romper (de la especificación)

1. Solo audio humano con doble revisión (una de ellas, intérprete de la lengua).
2. Cero datos de pacientes fuera del teléfono.
3. Las voces pertenecen a su comunidad: licencia, guardianes y retiro.
4. Siempre hay un camino a un intérprete humano («Pedir intérprete» en todas las pantallas).
5. No dañar: nada de diagnósticos ni tratamientos.
6. Accesible primero: audio antes que texto, botones de 56 px o más.
7. Sin internet por defecto.

Tampoco: frameworks pesados, analítica de terceros, cookies de seguimiento,
scripts externos, IA generativa, reconocimiento de voz, cuentas de usuario.
No se inventan frases en lenguas indígenas, nombres de revisores reales,
cifras de impacto ni permisos de comunidades.

## 3. Estado por bloque

| # | Bloque | Estado | Evidencia |
|---|--------|--------|-----------|
| 1 | Backend FastAPI + SQLite (paquetes, uso, reportes, estudio, retiro, respaldos, cabeceras) | Terminado | `backend/`, 135 pruebas pytest en verde |
| 2 | Contenido: 83 frases en 6 escenarios, con fuentes oficiales | Terminado (falta revisión clínica humana) | `frontend/data/phrases.es.json` |
| 3 | 124 pictogramas SVG propios | Terminado | `frontend/icons/pictos.svg` |
| 4 | Paquetes de AUDIO DE PRUEBA (tonos, sin voz) | Terminado | `packs/pack-prueba-a-001`, `packs/pack-prueba-b-001`, `scripts/make_test_packs.py` |
| 5 | PWA: 12 pantallas de consulta, modo médico/paciente | Terminado | `frontend/app.js`, `frontend/js/views-consult.js`, `views-packs.js` |
| 6 | Modo sin internet (service worker + IndexedDB + versiones + borrado de retirados) | Terminado | `frontend/sw.js`, `frontend/js/store.js`, `net.js` |
| 7 | Estudio: consentimiento, grabación, doble revisión, guardián, retiro, coordinación | Terminado | `frontend/js/views-studio.js` |
| 8 | Pruebas en navegador (Playwright) y de lógica (node) | Terminado | `e2e/` 13 pruebas, `tests_js/` 10 pruebas |
| 9 | Documentación y despliegue | Terminado | `README.md`, `docs/` (6 documentos), `Dockerfile`, `railway.json`, `requirements*.txt`, `LICENSE` |
| 10 | Revisión final y empaquetado | Terminado (Lighthouse quedó sin correr, ver sección 7) | `nepantla.zip` |

## 4. Decisiones ya tomadas (no cambiarlas sin motivo)

- **Respuestas de la consulta solo en memoria** (`app.session`). Nunca en
  IndexedDB ni localStorage. Se borran al terminar, al cerrar o tras 30 min.
- **Contadores en lote**: se suman en el teléfono y salen al abrir la app, no
  en el momento del evento. El servidor guarda solo día + paquete + evento + n.
- **Sin IP en ningún lado**: los límites de frecuencia se llevan por sesión
  del estudio o globales, nunca por IP.
- **Reportes sin texto libre**: paquete, frase y motivo de lista cerrada.
- **Tokens del estudio después del `#`** y guardados solo como hash SHA-256.
- **Audios de prueba = tonos**, no voz sintética, con `is_test: true` y
  `status: draft`. El servidor se niega a publicarlos.
- **Cruces de los pictogramas en color tinta**, nunca rojas (emblema protegido).
- **QR de la tarjeta**: solo identificadores de frases, en el fragmento de la URL.
- Modo demostración: `NEPANTLA_DEV_MODE=1`. Sin esa variable no se ve ningún
  paquete en borrador ni de prueba.

## 5. Cómo comprobar el estado real

```bash
python -m pytest -q                      # backend: 140 pruebas
node --test tests_js/core.test.mjs       # lógica de la app: 10 pruebas
python -m pytest e2e -q                  # navegador: 14 pruebas (necesita Chrome/Chromium)
```

Resultados de la última corrida (23 nov 2026): 140 / 10 / 14, todas en verde
(164 en total). Antes (15 nov): 138 / 10 / 14. Se corrieron dos veces: en la carpeta de trabajo y desde una
copia extraída del ZIP de entrega.

## 6. Bloque 9: documentación y despliegue (terminado)

- [x] `docs/PRIVACY.md`
- [x] `docs/GOVERNANCE.md`
- [x] `docs/ATTRIBUTIONS.md`
- [x] `docs/PACK_FORMAT.md`
- [x] `docs/FUENTES.md`
- [x] `docs/PENDIENTES.md` (lo que requiere personas reales)
- [x] `README.md`
- [x] `requirements.txt`, `requirements-dev.txt`
- [x] `Dockerfile`, `railway.json`, `.dockerignore`, `.gitignore`
- [x] `LICENSE`

## 7. Bloque 10: cierre (terminado)

- [x] Revisión integral contra la sección «Cuándo está terminado el MVP».
- [x] Medición propia de lo que Lighthouse revisaría: primera pantalla en
      1.7 s con red 3G simulada, cascarón de menos de 120 KB comprimido,
      contraste AAA en el texto principal, nombres accesibles y un solo
      título por pantalla, botones de 56 px o más en modo paciente.
- [x] Empaquetado en `nepantla.zip`.
- [x] **Lighthouse 13.6.0** sobre el demo desplegado, vía PageSpeed Insights
      (móvil, Moto G Power emulado, 4G lenta, 16 nov 2026): rendimiento 99,
      accesibilidad 96, buenas prácticas 100, SEO 60. Instalarlo en el
      entorno de trabajo no se permitió (15 y 16 nov), por eso se corrió en
      el servicio de Google contra la liga pública. Detalle en la sección 11.

### Contra «Cuándo está terminado el MVP»

| Criterio de la especificación | Estado |
|-------------------------------|--------|
| Instalable y funcional en modo avión | Cumplido y probado |
| 6 escenarios con ~80 frases en español, con pictogramas | Cumplido (83 frases, 124 pictogramas) |
| Al menos un idioma con todas las frases grabadas y doblemente revisadas | **Pendiente: necesita personas reales** |
| Ficha pública, botón de reportar y retiro de voces | Cumplido y probado |
| Pruebas pasando y Lighthouse sin errores graves | Pruebas: 164 en verde. Lighthouse: 99 / 96 / 100 / 60, sin errores graves |
| Prueba piloto con personal de salud y un hablante | **Pendiente: necesita personas reales** |

### Siguiente acción concreta

1. Probar el demo en un Android de gama baja y en un iPhone, y recorrerlo
   con TalkBack.
2. Empezar por `docs/PENDIENTES.md`: revisión clínica y primer acuerdo con
   una comunidad.

## 8. Fuentes consultadas (ya están citadas en `phrases.es.json`)

- NOM-007-SSA2-2016, numeral 5.3.1.3 (urgencia obstétrica).
- IMSS, Maternidad: signos de alarma en el embarazo.
- Servicios de Salud de Veracruz, folleto de signos de alarma (2024).
- NOM-031-SSA2-1999, numerales 7.2.6.1.3 y 8.2.5.1.3.1 (niñez).
- OPS/OMS, AIEPI: signos generales de peligro.
- Servicios de Salud de Puebla, material del Día del Niño y la Niña.

## 9. Pendiente que NO se puede hacer con código

Reclutar hablantes e intérpretes certificados, acuerdo con guardianes de cada
variante, revisión clínica firmada de las frases, revisión legal (COFEPRIS y
Ley Federal de Protección del Patrimonio Cultural de los Pueblos y
Comunidades Indígenas y Afromexicanas), prueba piloto, audio humano del
consentimiento (`frontend/audio/consentimiento.es.opus`).

## 10. Problemas conocidos

- iPhone anteriores a iOS 18.4 no reproducen Opus dentro de Ogg. El público
  objetivo es Android de gama baja; queda documentado en el README.
- El registro de accesos de Railway (su proxy) queda fuera del código: hay
  que revisarlo al desplegar (ver `docs/PRIVACY.md`).

## 11. Publicación: estado real comprobado el 22 nov 2026

### GitHub: hecho

- Repositorio público `PyAutoSolutions/nepantla`, rama `main`. Lo subió
  Gabriel desde su teléfono con el ZIP de 194 archivos (el conector de
  GitHub de la sesión no podía crear repositorios: error 403). Último commit
  comprobado: `4965d97` («Actualizar README, progreso y pendientes»).
- Comparado el 22 nov archivo por archivo contra la versión de trabajo: el
  árbol de git es idéntico (`e508c258…`, 194 archivos).
- El flujo «Demo estático» corrió en GitHub con los dos `push` y terminó en
  verde: como Pages no está activado, revisa, no publica y no marca error.
- Gabriel ya borró la llave de despliegue temporal.

### Railway: desplegado en modo demostración

- Liga: https://nepantla-demo-production.up.railway.app
- Proyecto `nepantla`, servicio `nepantla-demo`, despliegue
  `a13781e9-13ed-4487-aaf1-e30416885c5e` (commit `4965d97`): SUCCESS, región
  `sfo`. Se vuelve a desplegar solo con cada `push` a `main`.
- Variables `NEPANTLA_DEV_MODE=1`, `NEPANTLA_FORCE_HTTPS=1` y
  `NEPANTLA_DATA_DIR=/data`; volumen `nepantla-datos` (500 MB) en `/data`.
  Sin token de administración: el estudio queda apagado.
- No se contrató nada ni se cambió de plan.

Comprobado en la liga pública:

- `/api/health` responde
  `{"ok":true,"dev_mode":true,"build":"35e69ec22a51","studio":false,"ffmpeg":true}`.
- El inicio carga con la cinta de modo demostración y salen los dos paquetes
  de prueba.
- Guardar el paquete de prueba A desde un navegador real terminó en
  «Guardado en este teléfono»: la app y el servidor se comunican (manifiesto
  y 84 audios).
- Registro HTTP de Railway: ninguna respuesta de error de la app. El único
  404 fue `/robots.txt`, que no existe.
- Registro de arranque: volumen montado y Uvicorn en marcha, sin errores.
- Modo sin conexión en la liga: Gabriel lo probó el 21 nov en su teléfono
  Android. Guardó el paquete de prueba A con internet, puso modo avión (sin
  Wi-Fi ni datos) y abrió la liga en una pestaña nueva: la app cargó desde
  el teléfono con el aviso «Sin internet. Todo sigue funcionando con lo
  guardado.», mostró la variante guardada y dejó elegir lengua.

### Lighthouse

Lighthouse 13.6.0 vía PageSpeed Insights (móvil, Moto G Power emulado, 4G
lenta), sobre la liga pública:

| Categoría | Puntos |
|---|---|
| Rendimiento | 99 (FCP 0.8 s, LCP 1.4 s, TBT 0 ms, CLS 0.062) |
| Accesibilidad | 96 |
| Buenas prácticas | 100 |
| SEO | 60 |

- SEO 60 es a propósito: `index.html` pide no aparecer en buscadores
  (`noindex`), porque es una demostración con audio de prueba.
- Accesibilidad 96: el único hallazgo es «Touch targets do not have
  sufficient size or spacing». Los botones miden 56 px o más; el problema es
  que la barra fija de «Emergencia» y «Pedir intérprete» queda encima de los
  últimos enlaces del inicio («Acerca de y créditos», «Ajustes de esta
  clínica») hasta que se desplaza la pantalla.
- Arreglo propuesto, sin aplicar: que solo se desplace el contenido y la
  barra quede fuera (`.app` con altura `100dvh` y `main` con su propio
  desplazamiento, solo donde el navegador entienda `dvh`), volver arriba al
  cambiar de pantalla y quitar esa altura al imprimir. No se aplicó porque
  cambia cómo se desplaza toda la app y debe probarse antes en teléfonos
  reales.
- Decisión (22 nov): la barra se queda como está. En las capturas del
  teléfono de Gabriel, al bajar la pantalla todo el contenido queda por
  encima de la barra. Cambiar cómo se desplaza toda la app por ese punto de
  Lighthouse no compensa el riesgo; el arreglo queda escrito por si la
  prueba piloto lo pide.

### Demostración sin servidor

- Página privada de Claude «Nepantla (demo con audio de prueba)», versión
  `1794806737-034d`. Sigue publicada; solo la ve el dueño de la cuenta.
- Una construcción nueva hecha desde el ZIP final sale idéntica, archivo por
  archivo, a lo publicado.
- Límites de ese visor: no deja instalar la app ni usarla sin conexión, y no
  imprime. Para eso hace falta Railway o GitHub Pages.
- El flujo `.github/workflows/demo.yml` ya corrió en GitHub, en verde y sin
  publicar, porque Pages no estaba activado. Desde el 23 nov Pages está
  activo y publica (ver «Publicación final»).

### Correcciones de esta etapa

- El visor de Claude rechaza archivos `.opus`: la demostración ahora lleva
  los audios de cada paquete juntos en `audio.json`.
- Dos avisos 404 vistos al probar la demostración dentro de un marco
  resultaron ser del icono de la página de prueba, no de la app (48
  peticiones de la app, todas con respuesta 200).
- El flujo de GitHub Pages ahora también se dispara en la rama `master`, y
  antes de publicar revisa si Pages está activado con la fuente «GitHub
  Actions». Si no lo está, no publica y termina sin error: antes, la primera
  subida a GitHub habría dejado una ejecución fallida.
- Nuevo `.gitattributes`: saltos de línea LF en todos los archivos de texto,
  también al subir el proyecto desde Windows.

### ZIP definitivo

`nepantla.zip`: 194 archivos, exactamente los que entrarían al repositorio
(respeta `.gitignore`). Sin `.env`, sin base de datos, sin credenciales ni
correos. Las 162 pruebas se corrieron desde una copia extraída del ZIP; tras
los últimos cambios (flujo de Pages, `.gitattributes` y documentación, sin
tocar código) se repitieron las 138 del servidor.
Desde el 16 nov, la copia de referencia es el repositorio de GitHub.

### Material para mostrarlo (22 nov)

- Sitio de una página: `docs/index.html` (problema, cifras con fuente,
  cómo funciona, principios, estado y cómo ayudar). Lleva dentro el video,
  las capturas y la letra, sin nada de otros servidores. El flujo de Pages
  lo publica en la raíz y la demo sin servidor en `/demo/`.
- Probado en local bajo `/nepantla/`, como en GitHub Pages: el sitio se ve
  bien a 1280 y 390 px de ancho, y la demo en `/demo/` guarda el paquete y
  vuelve a abrir sin internet.
- Video demo de 78 s, vertical, con subtítulos y los dos tonos de prueba.
- `docs/pantallas.jpg`: seis pantallas para el README.
- Fuera del repositorio: PDF de una hoja, póster, formato de revisión
  clínica y mensajes para pedir cartas y revisiones.
- Cifras: INEGI, Censo 2020 (7 364 645 hablantes de 3 años y más; 865 972
  no hablan español) e INALI, Catálogo de 2008 (68 agrupaciones, 364
  variantes, 11 familias).

### Cierre de la revisión contra la checklist (23 nov)

Revisión punto por punto contra «Nepantla: checklist de lanzamiento». Se
cerraron cuatro detalles de código y documentos:

- La ficha de cada paquete muestra la **revisión clínica** de las frases
  (pendiente, o nombre, papel y fecha de quien firmó). Datos en
  `frontend/data/phrases.es.json`: `clinical_review` y `clinical_reviewers`.
- **Región** de la variante en el formato de paquete, el estudio, el
  servidor y la ficha. Las bases anteriores ganan la columna solas.
- `GOVERNANCE.md`: reportes atendidos en **menos de 24 horas** (si no, la
  frase se retira mientras tanto) y **guardianes**: al menos una persona
  intérprete y una de salud por variante.
- `PRIVACY.md` y la pantalla de privacidad: Railway registra IP y navegador
  de cada petición; plan de copias de seguridad fuera del volumen.

Pruebas: 140 del servidor (2 nuevas: región en el manifiesto y migración de
una base anterior), 10 de lógica y 14 de navegador, todas en verde.

### Entrega del 23 nov

- Lista de convocatorias que se hacen desde casa, con fechas comprobadas en
  sus páginas oficiales: documento aparte «Convocatorias para Nepantla (desde
  casa)», fuera del repositorio.
- Los 19 archivos que cambiaron desde el commit `4965d97` de GitHub van en
  `nepantla-cambios-23nov.zip`, con sus carpetas. Gabriel los subió desde
  Termux el mismo día (commit `1d28049`).
- El sitio publicado como artifact ya dice «Más de 160 pruebas».
- Copias de seguridad: la base de Railway hoy solo guarda datos de prueba, y
  las copias de Railway no se pueden descargar. Cuando haya datos reales:
  exportar los paquetes desde el Estudio y decidir si se activan las copias
  de Railway, que tienen costo.

### Publicación final (comprobada el 24 nov)

- GitHub: commit `1d28049` en `main`. Su árbol de git es idéntico al de la
  versión de trabajo (`16efe303…`).
- GitHub Pages: activado el 23 nov con la fuente «GitHub Actions»; el flujo
  «Demo estático» publica en cada `push`.
  - Sitio: https://pyautosolutions.github.io/nepantla/ (ya dice «Más de 160
    pruebas»).
  - Demo sin servidor: https://pyautosolutions.github.io/nepantla/demo/.
    Probada en un navegador: carga con la cinta de modo demostración, guarda
    el paquete de prueba A («Ya funciona sin internet») y la ficha muestra
    «Revisión clínica de las frases: Pendiente».
- Railway: despliegue `d11e3b8d-bb64-46c6-9f25-0ddd92be8d06` (commit
  `1d28049`): SUCCESS. `/api/health` responde con `build` `de3a62c05445`, que
  es la huella del frontend de esta versión; el servidor arrancó sin errores
  con la base que ya existía.

### Lo que necesita a una persona

1. Probar el demo en un Android de gama baja y en un iPhone, y recorrerlo
   con TalkBack.
2. La validación humana de `docs/PENDIENTES.md`: revisión clínica de las 83
   frases, hablantes e intérpretes, acuerdo con una comunidad y sus
   guardianes, revisión legal, prueba piloto y el audio humano del
   consentimiento.

**Nepantla no está listo para usarse con pacientes** hasta completar el
punto 2. Los audios incluidos son tonos de prueba, no grabaciones en ninguna
lengua.
