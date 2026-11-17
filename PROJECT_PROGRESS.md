# Nepantla: bitácora de avance

Este archivo existe para poder retomar el trabajo sin repetir nada si una
sesión se corta. Se actualiza al cerrar cada bloque. **No sustituye a
revisar los archivos**: antes de continuar, corre las pruebas de la sección 5.

Última actualización: 16 de noviembre de 2026. **Software terminado y empaquetado
(versión 0.1.0). Falta publicarlo: lo detiene GitHub (sección 11).**

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
python -m pytest -q                      # backend: 138 pruebas
node --test tests_js/core.test.mjs       # lógica de la app: 10 pruebas
python -m pytest e2e -q                  # navegador: 14 pruebas (necesita Chrome/Chromium)
```

Resultados de la última corrida (15 nov 2026): 138 / 10 / 14, todas en verde
(162 en total). Se corrieron dos veces: en la carpeta de trabajo y desde una
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
- [ ] **Lighthouse no se corrió.** Se intentó dos veces (15 nov con `npx`,
      16 nov con `npm install`) y las dos veces el sistema de permisos del
      entorno de trabajo bloqueó instalar y ejecutar la herramienta. No hay
      resultados de Lighthouse; las mediciones de arriba son pruebas propias,
      no un informe de Lighthouse. Se corre en un minuto desde Chrome
      (F12 → pestaña Lighthouse) o con `npx lighthouse http://localhost:8000 --view`.

### Contra «Cuándo está terminado el MVP»

| Criterio de la especificación | Estado |
|-------------------------------|--------|
| Instalable y funcional en modo avión | Cumplido y probado |
| 6 escenarios con ~80 frases en español, con pictogramas | Cumplido (83 frases, 124 pictogramas) |
| Al menos un idioma con todas las frases grabadas y doblemente revisadas | **Pendiente: necesita personas reales** |
| Ficha pública, botón de reportar y retiro de voces | Cumplido y probado |
| Pruebas pasando y Lighthouse sin errores graves | Pruebas: 162 en verde. Lighthouse: sin correr |
| Prueba piloto con personal de salud y un hablante | **Pendiente: necesita personas reales** |

### Siguiente acción concreta

1. Subir el repositorio a GitHub.
2. Desplegar en Railway en modo demostración (pasos en `README.md`).
3. Correr Lighthouse y probar en dos teléfonos reales.
4. Empezar por `docs/PENDIENTES.md`: revisión clínica y primer acuerdo con una comunidad.

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

## 11. Publicación: estado real comprobado el 16 nov 2026

### GitHub: no se subió

- Cuenta: `PyAutoSolutions`, con dos repositorios públicos (`rainshield` y
  `BecaRadar_Mexico`). **No existe ningún repositorio `nepantla`.**
- Por qué: el conector de GitHub de la sesión rechaza crear repositorios
  (`403 Resource not accessible by integration`, comprobado el 15 y el 16 de
  noviembre), solo acepta archivos de texto (no fuentes, iconos ni audios) y
  la sesión no tiene la cuenta enlazada para hacer `git push`
  («no GitHub account linked»).
- Qué falta: crear el repositorio y subir el contenido del ZIP (comandos en
  `README.md`). Alternativa: enlazar GitHub en la configuración de Claude y
  crear el repositorio vacío, para que una sesión pueda hacer el `push`.

### Railway: preparado, sin despliegue

- Proyecto `nepantla` (`471f38a4-24e3-42e1-a6c9-daecd72a0987`), entorno
  `production` (`c5c37bba-d1ec-49a8-aa6a-f98d2b140d53`), servicio
  `nepantla-demo` (`e187d0d7-e353-4e11-992a-8b6a94df2cff`).
- Estado comprobado: servicio **apagado**, **0 despliegues**, **sin dominio**.
  Variables puestas: `NEPANTLA_DEV_MODE`, `NEPANTLA_FORCE_HTTPS`,
  `NEPANTLA_DATA_DIR`. Volumen `nepantla-datos` montado en `/data`.
- Sin token de administración a propósito: el estudio de grabación queda
  apagado en un demo público.
- No se contrató nada ni se cambió de plan.
- Qué falta: conectar el repositorio al servicio y generar el dominio. Solo
  se puede cuando el código esté en GitHub.
- Ensayo en local de lo que hará el contenedor (16 nov): instalación limpia
  solo con `requirements.txt`, arranque con el mismo comando y las mismas
  variables. Resultado: `/api/health` responde 200 sin encabezados de proxy
  (así lo revisa Railway), `http` redirige a `https` (308), llegan CSP y HSTS,
  no hay cookies, salen los 2 paquetes de prueba y sus audios, y los datos
  siguen ahí después de reiniciar. Esto no sustituye al despliegue real.

### Demostración sin servidor

- Página privada de Claude «Nepantla (demo con audio de prueba)», versión
  `1794806737-034d`. Sigue publicada; solo la ve el dueño de la cuenta.
- Una construcción nueva hecha desde el ZIP final sale idéntica, archivo por
  archivo, a lo publicado.
- Límites de ese visor: no deja instalar la app ni usarla sin conexión, y no
  imprime. Para eso hace falta Railway o GitHub Pages.
- El flujo `.github/workflows/demo.yml` (GitHub Pages) no se ha podido probar
  en GitHub.

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

### Lo que necesita a una persona

1. Subir el código a GitHub.
2. Conectar el repositorio en Railway y generar el dominio.
3. Correr Lighthouse y probar en dos teléfonos reales.
4. La validación humana de `docs/PENDIENTES.md`: revisión clínica de las 83
   frases, hablantes e intérpretes, acuerdo con una comunidad y sus
   guardianes, revisión legal, prueba piloto y el audio humano del
   consentimiento.

**Nepantla no está listo para usarse con pacientes** hasta completar el
punto 4. Los audios incluidos son tonos de prueba, no grabaciones en ninguna
lengua.
