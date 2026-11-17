# Privacidad en Nepantla

## En una frase

**Nepantla no guarda datos de pacientes.** No pide nombre, edad ni expediente,
y lo que la persona responde no sale de la pantalla donde lo respondió.

## Para quien usa la app (español sencillo)

- La app no pregunta quién es usted.
- Lo que usted responde se queda en ese teléfono, solo mientras dura la
  consulta. Al terminar se borra.
- El resumen y la tarjeta de salida se muestran o se imprimen ahí mismo.
  Nadie más los recibe.
- No hay cuentas, ni cookies para seguirle, ni anuncios.
- Si usted grabó su voz para un paquete, puede retirarla cuando quiera.

## Qué se guarda y dónde

### En el teléfono de la clínica

| Qué | Dónde | Para qué | Cómo se borra |
|-----|-------|----------|---------------|
| Paquetes de lengua (lista de frases y audios) | IndexedDB | Trabajar sin internet | «Borrar del teléfono» o Ajustes → «Borrar todo» |
| Contadores pendientes: paquete + evento + cuántas veces | IndexedDB | Enviarlos en lote cuando haya red | Se borran al enviarse |
| Reportes de audio pendientes: paquete + frase + motivo | IndexedDB | Enviarlos cuando haya red | Se borran al enviarse |
| Contacto del intérprete que escribe la clínica | localStorage | Pantalla «Pedir intérprete» | Ajustes |
| Si el servidor está en modo demostración | localStorage | Mostrar u ocultar paquetes de prueba | Ajustes |
| El «cascarón» de la app (HTML, JS, CSS, pictogramas) | Cache Storage | Abrir sin internet | Borrar datos del sitio |

**Lo que no se guarda nunca:** respuestas, zonas del cuerpo tocadas, nivel de
dolor, el resumen, la tarjeta de salida ni la lengua elegida para un
paciente. Todo eso vive en una variable en memoria (`app.session` en
`frontend/app.js`) y desaparece al tocar «Terminar consulta», al cerrar la
app o después de 30 minutos sin tocar la pantalla.

### En el servidor

| Tabla | Contenido | Datos personales |
|-------|-----------|------------------|
| `usage_counts` | día, paquete, evento, cuántas veces | Ninguno |
| `reports` | grabación reportada, motivo de lista cerrada, día | Ninguno |
| `packs`, `phrases` | Paquetes y frases en español | Ninguno |
| `recordings`, `reviews` | Grabaciones, quién grabó y quién revisó (el nombre o seudónimo que cada quien eligió) | Voz y nombre elegido de hablantes y revisores |
| `consents` | Nombre para créditos, licencia, fecha y el **hash** del código de retiro | Nombre elegido |
| `studio_sessions` | Enlaces personales del estudio (solo su hash) | Nombre elegido |

El servidor no tiene tabla de pacientes, de consultas ni de respuestas. No
existe ningún endpoint que las reciba.

## Decisiones de privacidad y por qué se tomaron

1. **Respuestas solo en memoria.** Un teléfono de clínica pasa por muchas
   manos. Si no se escribe en disco, no hay nada que alguien pueda encontrar
   después.
2. **Contadores, no eventos.** `POST /api/usage` acepta únicamente
   `{pack_id, event, n}`. Rechaza cualquier campo extra y cualquier paquete
   que no exista, para que nadie pueda usar ese campo como escondite de un
   dato. El servidor apunta el **día**, nunca la hora.
3. **Envío en lote.** Los contadores salen al abrir la app, no cuando ocurre
   el evento. Así ni la hora del envío delata cuándo fue una consulta.
4. **Sin IP.** El código no lee ni guarda la dirección IP ni el navegador
   (`User-Agent`). Los límites de frecuencia se llevan por sesión del estudio
   o de forma global, nunca por IP. El servidor arranca con
   `--no-access-log`.
5. **Reportes sin texto libre.** Un cuadro de texto abierto es donde terminan
   escribiéndose nombres y diagnósticos por error. El reporte lleva paquete,
   frase y un motivo de cinco posibles.
6. **Cero terceros.** La app no carga nada de otros servidores: ni letras, ni
   scripts, ni analítica. La política CSP (`default-src 'self'`) lo impide y
   una prueba automática lo revisa.
7. **Sin cookies.** Ninguna respuesta del servidor pone cookies; hay una
   prueba que lo comprueba en todas las rutas.
8. **Enlaces del estudio.** El permiso va después del `#` de la dirección,
   que el navegador no envía al servidor. La app lo lee, lo quita de la barra
   y lo manda en una cabecera. En la base solo queda su hash SHA-256.
9. **Código de retiro.** Se muestra una sola vez y se guarda solo su hash.
   Ni quien administra el servidor puede leerlo.
10. **Metadatos de audio.** Al convertir cada grabación, ffmpeg elimina los
    metadatos del archivo (modelo del teléfono, fecha, ubicación si la hubiera).
11. **QR de la tarjeta.** Lleva solo la lista de indicaciones elegidas por el
    personal (identificadores de frases), después del `#`. No lleva nombre y
    no viaja al servidor.
12. **Micrófono.** Solo se enciende en el estudio, cuando la persona hablante
    toca «grabar» después de aceptar el consentimiento, y se apaga al terminar
    cada frase. La app de consulta no usa el micrófono.

## Lo que el código no controla

- **Registros del proveedor de hospedaje.** Railway (o cualquier proxy
  delante de la app) puede anotar IP y hora de cada petición en sus propios
  registros. Eso está fuera del código. Antes de usar la app con pacientes:
  revisar qué guarda el proveedor, por cuánto tiempo, y desactivarlo o
  acortarlo si se puede. Está en la lista de `docs/PENDIENTES.md`.
- **El teléfono mismo.** Capturas de pantalla, copias de seguridad del
  sistema o una persona mirando por encima del hombro quedan fuera del
  alcance de la app.
- **El portapapeles.** Si el personal copia el resumen, ese texto queda en el
  portapapeles del teléfono hasta que se copie otra cosa.

## Cómo comprobarlo usted mismo

```bash
python -m pytest backend/tests/test_usage.py backend/tests/test_security.py -q
python -m pytest e2e/test_app.py -k "no_se_guarda" -q
```

La primera revisa que el servidor no guarde nada identificable y que no haya
cookies ni recursos externos. La segunda abre un navegador, hace una
consulta y examina todo lo que quedó guardado en el teléfono.

## Revisión legal

Este documento describe lo que hace el software. **No es un aviso de
privacidad con validez legal.** Antes de un uso real hace falta que una
persona abogada lo revise frente a la legislación mexicana de protección de
datos personales y de datos de salud.
