# Lo que falta y solo pueden hacer personas

El software está completo y probado. **La herramienta todavía no puede
usarse con pacientes.** Lo que falta no se resuelve con código, y nada de
esto se puede inventar.

## Antes de grabar una sola frase

- [ ] **Revisión clínica firmada** de las 83 frases en español
      (`docs/FUENTES.md` explica qué revisar).
- [ ] **Acuerdo con la comunidad** de la primera variante: quiénes serán sus
      guardianes, qué licencia eligen y si quieren una etiqueta comunitaria.
- [ ] **Intérpretes certificados** de esa variante para la doble revisión.
      Una pista para buscarlos: el Padrón Nacional de Intérpretes y
      Traductores en Lenguas Indígenas (PANITLI) del INALI. Hay que confirmar
      con la institución que el padrón siga vigente.
- [ ] **Audio del consentimiento** grabado por una persona, guardado en
      `frontend/audio/consentimiento.es.opus`. Cuando el archivo existe, el
      botón «Escuchar esta explicación» aparece solo.

## Antes de usarla en una clínica

- [ ] **Revisión legal** por una persona abogada: normativa de la COFEPRIS
      sobre software como dispositivo médico, protección de datos personales
      y la Ley Federal de Protección del Patrimonio Cultural de los Pueblos
      y Comunidades Indígenas y Afromexicanas.
- [ ] **Registros del proveedor de hospedaje**: confirmar qué guarda Railway
      (IP, hora) y por cuánto tiempo; desactivarlo o acortarlo si se puede.
- [ ] **Al menos un idioma** con todas las frases grabadas y con doble
      revisión, publicado por sus guardianes.
- [ ] **Prueba piloto** con personal de salud y un hablante, con notas.
- [ ] **Probar en teléfonos reales**: ya funciona en un Android en modo avión
      (21 nov); faltan un Android de gama baja y un iPhone.
- [x] **Lighthouse** (16 nov 2026, PageSpeed Insights, móvil): rendimiento
      99, accesibilidad 96, buenas prácticas 100, SEO 60 (`noindex` a
      propósito). La barra fija que tapa los últimos enlaces del inicio se
      queda como está (decisión del 22 nov, `PROJECT_PROGRESS.md`, sección 11).
- [ ] **TalkBack**: recorrer la app con el lector de pantalla de Android.

## Para la prueba piloto (plantilla de notas)

Anotar sin nombres de pacientes:

1. ¿La persona reconoció su variante con el saludo? ¿Al primer intento?
2. ¿Qué frases marcó «No entendí»? ¿Cuáles tuvo que escuchar dos veces?
3. ¿Entendió los dibujos de sí y no? ¿El mapa del cuerpo? ¿Las caritas?
4. ¿Cuánto tardó la consulta comparada con una sin la app?
5. ¿El resumen le sirvió al médico? ¿Qué le faltó?
6. ¿En qué momento hizo falta llamar a un intérprete?
7. ¿Algo resultó incómodo, ofensivo o confuso?

Mientras esas notas no existan, no se debe afirmar que la herramienta
«funciona» ni dar cifras de impacto.

## Pasos de publicación

- [x] Código en GitHub: `PyAutoSolutions/nepantla`.
- [x] Demo en Railway: https://nepantla-demo-production.up.railway.app
- [x] Borrar la llave de despliegue temporal que se usó para subir el código.
- [ ] **Registros de Railway**: guardan IP y navegador de cada petición.
      Preguntar el plazo de conservación antes de usar la app con pacientes
      (ver `docs/PRIVACY.md`).
- [ ] **Copias fuera del volumen**: antes de grabar voces reales, activar
      *Backups* en Railway (cuesta por GB) y exportar cada paquete publicado
      a una computadora de la coordinación.
- [x] **GitHub Pages** activo desde el 23 nov 2026: sitio del proyecto en
      https://pyautosolutions.github.io/nepantla/ y demo sin servidor en
      https://pyautosolutions.github.io/nepantla/demo/, gratis y sin fecha de
      vencimiento.
- [x] Video demo de 78 s con subtítulos y la cinta de «AUDIO DE PRUEBA»
      siempre visible (está en el sitio del proyecto).
