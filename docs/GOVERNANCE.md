# Gobernanza comunitaria de las voces

## Principio

**Las voces pertenecen a quien las grabó y a su comunidad.** Nepantla solo
las cuida mientras la comunidad quiera. El software está hecho para que esa
frase se cumpla sola, sin depender de la buena voluntad de quien administra
el servidor.

## Quién es quién

No hay cuentas de usuario. Cada persona recibe un **enlace personal** para un
paquete y un papel concretos.

| Papel | Qué puede hacer | Qué no puede hacer |
|-------|-----------------|--------------------|
| **Hablante** | Aceptar el consentimiento, grabar, regrabar y retirar su voz o una frase | Aprobar grabaciones (ni las suyas ni las de otros) |
| **Revisor** (intérprete o personal de salud) | Escuchar grabaciones pendientes y aprobarlas o rechazarlas con una nota | Revisar dos veces la misma grabación; revisar lo que él mismo grabó |
| **Guardián** (al menos dos por variante: una persona intérprete de esa variante y una persona de salud, nombradas o aprobadas por la comunidad) | Publicar el paquete, retirar frases, retirar el paquete completo, atender reportes | Grabar o revisar con ese mismo enlace |
| **Coordinación** (quien tiene `NEPANTLA_ADMIN_TOKEN`) | Crear paquetes en borrador, crear y revocar enlaces, ver conteos | **Publicar** un paquete, aprobar grabaciones, leer códigos de retiro |

La última fila es deliberada: quien administra el servidor no puede publicar
una lengua por su cuenta. Solo un guardián de esa variante puede.

## El camino de una grabación

1. **Consentimiento.** La persona hablante lee (y, cuando exista el audio,
   escucha) quién va a usar su voz, para qué, con qué licencia, con qué
   nombre aparece y cómo retirarla. Marca cuatro casillas por separado. Sin
   eso el servidor rechaza cualquier grabación.
2. **Código de retiro.** Al aceptar recibe un código que se muestra una sola
   vez. El servidor guarda únicamente su hash.
3. **Grabación.** Una frase a la vez. El servidor la convierte a Opus mono de
   16 kHz y le quita los metadatos.
4. **Doble revisión.** Una frase entra al paquete solo cuando tiene **dos
   aprobaciones de dos personas distintas** y **al menos una es intérprete de
   esa lengua**. Un solo rechazo la devuelve a la persona hablante con una
   nota. Quien grabó no puede revisar su propia voz.
5. **Publicación.** Aunque todas las frases estén revisadas, el paquete sigue
   en borrador hasta que un guardián lo aprueba.
6. **Versión.** Cada cambio (frase aprobada, frase retirada, publicación)
   sube la versión. Los teléfonos comparan versiones al conectarse.

## Retiro

Retirar es un derecho, no un favor. No se piden motivos.

| Quién | Qué retira | Cómo | Qué pasa |
|-------|------------|------|----------|
| Hablante | Una frase suya | `#/retirar` con su código | Se borra el archivo; el paquete sube de versión |
| Hablante | Toda su voz | `#/retirar` con su código | Se borran todos sus archivos (aprobados, pendientes y antiguos) y su nombre de créditos |
| Guardián | Una frase del paquete | Su enlace del estudio | Igual que arriba |
| Guardián | El paquete completo | Su enlace del estudio | Se borran todos los audios; el paquete deja de listarse |

En los teléfonos: en la **siguiente conexión**, la app borra los audios
retirados sin preguntar. Un paquete retirado desaparece completo y la app
avisa al personal de salud.

Límite honesto: un teléfono que nunca vuelve a conectarse conserva lo que
tenía. Por eso conviene pedir a las clínicas que abran la app con internet
de vez en cuando.

Si alguien pierde su código de retiro, puede pedir a los guardianes de su
paquete que retiren sus frases.

## Licencia y etiqueta comunitaria

- La licencia de cada paquete **la elige la comunidad**, no el proyecto. Se
  escribe tal cual en el paquete y se muestra en su ficha y en el
  consentimiento. Puede ser una licencia abierta, una restringida a uso en
  salud o un texto propio.
- La licencia del código (MIT) **no cubre las voces**. Cada paquete lleva su
  propio `LICENSE.txt`.
- El campo «etiqueta comunitaria» queda libre para que la comunidad indique
  condiciones propias de uso, si las tiene.
- La ficha pública de cada paquete muestra variante, comunidad, quién grabó,
  quién revisó, fecha, versión, licencia y guardianes.

## Reportes de audio incorrecto

Cualquier persona que use la app puede reportar una frase. El reporte lleva
el paquete, la frase y un motivo de lista cerrada; no lleva texto libre. Los
guardianes del paquete ven los reportes en su enlace y deciden: retirar la
frase, pedir que se grabe otra vez o descartar el reporte.

**Plazo: menos de 24 horas.** Los guardianes atienden cada reporte en menos
de un día. Si no pueden escucharlo a tiempo, retiran la frase mientras tanto:
es mejor que falte una frase a que suene una equivocada. Al retirarla, los
teléfonos la borran en su siguiente conexión.

## Paquetes de prueba

Los paquetes de `packs/` son **tonos generados por computadora**, sin voz.
Llevan `is_test: true`, solo se ven en modo demostración y el servidor se
niega a publicarlos. Existen para probar y mostrar la app sin usar la voz de
nadie ni hacer pasar un relleno por una lengua real.

## Lo que el software no resuelve

Estas decisiones son de personas y comunidades, no de código:

- Quién representa a una comunidad y cómo se nombra a sus guardianes.
- El acuerdo por escrito con cada comunidad antes de grabar.
- Si se paga a hablantes e intérpretes y cómo.
- Qué hacer cuando dos variantes vecinas no están de acuerdo sobre una frase.
- La revisión legal frente a la Ley Federal de Protección del Patrimonio
  Cultural de los Pueblos y Comunidades Indígenas y Afromexicanas.

Nada de eso está resuelto todavía. Ver `docs/PENDIENTES.md`.
