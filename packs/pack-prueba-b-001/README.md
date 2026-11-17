# Paquete `prueba-b-001`: AUDIO DE PRUEBA

**Esto no es una lengua real.** Cada "frase" es una melodía corta de tonos
generados por computadora. Existe para poder probar y mostrar Nepantla
sin usar la voz de nadie.

- Variante de prueba: Tonos graves (prueba B)
- Frases con audio: 19 (2 con un solo revisor, que la app no muestra)
- Estado: `draft` y `is_test: true`. El servidor solo lo enseña en modo
  demostración (`NEPANTLA_DEV_MODE=1`) y se niega a publicarlo.
- Revisores y "hablante": nombres de relleno.

Para regenerarlo: `python scripts/make_test_packs.py`.

Formato abierto de Nepantla, versión 1. Ver `docs/PACK_FORMAT.md`.
