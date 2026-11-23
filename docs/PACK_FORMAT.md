# Formato abierto del paquete de lengua (versión 1)

Un paquete es **una carpeta o un zip por variante**. El formato es abierto a
propósito: una comunidad debe poder llevarse sus voces a otro lado, y otros
proyectos deben poder leer o producir paquetes sin depender de Nepantla.

## Carpeta

```
pack-nah-central-001/
  manifest.json
  audio/
    urg-001.opus
    urg-002.opus
    ...
  greeting.opus     (saludo corto en esa variante, para elegir por audio)
  LICENSE.txt       (la licencia que eligió la comunidad)
  README.md         (ficha del paquete en español)
```

El nombre de la carpeta es `pack-` seguido del `pack_id`.

## `manifest.json`

```json
{
  "format_version": 1,
  "pack_id": "nah-central-001",
  "language": "Náhuatl",
  "variant": "Náhuatl del centro (ejemplo ficticio)",
  "community": "Nombre de la comunidad",
  "region": "Municipio y estado, o región",
  "version": "0.1.0",
  "status": "draft",
  "license": "La que eligió la comunidad",
  "community_label": null,
  "guardians": ["Guardiana Uno", "Guardián Dos"],
  "greeting": {
    "audio": "greeting.opus",
    "reviewed_by": ["Revisora A", "Revisor B"],
    "recorded_by": "Hablante Uno",
    "approved_at": "2026-12-01"
  },
  "phrases": [
    {
      "id": "urg-001",
      "audio": "audio/urg-001.opus",
      "reviewed_by": ["Revisora A", "Revisor B"],
      "recorded_by": "Hablante Uno",
      "approved_at": "2026-12-01"
    }
  ]
}
```

El ejemplo de arriba es ficticio. **No existe todavía ningún paquete de una
lengua real.**

### Campos del paquete

| Campo | Tipo | Notas |
|-------|------|-------|
| `format_version` | número | Siempre `1`. Otro valor se rechaza. |
| `pack_id` | texto | Minúsculas, números y guiones; de 3 a 64 caracteres. |
| `language`, `variant`, `community` | texto | Como los nombra la comunidad. |
| `region` | texto | Dónde se habla esa variante: municipio, estado o región. Opcional; si falta, la ficha dice «Sin registrar». |
| `version` | texto | Tres números (`0.1.0`). Sube con cada cambio. |
| `status` | texto | `draft`, `approved` o `withdrawn`. |
| `license` | texto | Libre: la define la comunidad. |
| `community_label` | texto o `null` | Etiqueta comunitaria, si la hay. |
| `guardians` | lista de texto | Nombres o seudónimos de las personas guardianas. |
| `greeting` | objeto o `null` | Igual que una frase, sin `id`. |
| `phrases` | lista | Ver abajo. |
| `is_test` | booleano (opcional) | `true` solo en paquetes de AUDIO DE PRUEBA. |

### Campos de cada frase

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | texto | Debe existir en `frontend/data/phrases.es.json` (`urg-001`). |
| `audio` | texto | Ruta dentro del paquete: `audio/<id>.opus`. |
| `reviewed_by` | lista de texto | Personas que la aprobaron. |
| `recorded_by` | texto | Nombre que la persona hablante eligió para créditos. |
| `approved_at` | texto | Día de la aprobación, `AAAA-MM-DD`. |
| `bytes` | número (opcional) | Tamaño del audio. Lo agrega el servidor al servir el manifest; la app lo usa para comprobar la descarga. |

## Reglas

1. **Doble revisión.** La app solo muestra frases con `reviewed_by` de **al
   menos dos personas distintas**. La misma persona escrita dos veces cuenta
   una. Esta regla se aplica dos veces: en el servidor, al armar el manifest,
   y en la app, al leerlo.
2. **Borradores.** Un paquete con `status: "draft"` solo se ve en modo
   demostración (`NEPANTLA_DEV_MODE=1`).
3. **Retirados.** Un paquete con `status: "withdrawn"` no se sirve (el
   servidor responde 410) y se borra de los teléfonos en su siguiente
   conexión.
4. **Paquetes de prueba.** `is_test: true` obliga a `status: "draft"`. El
   servidor se niega a publicarlos y nunca los lista fuera del modo
   demostración.
5. **Audio.** Opus dentro de Ogg, mono, 16 kHz, alrededor de 16 kbps, sin
   metadatos. Un paquete completo de unas 80 frases pesa menos de 1 MB.
6. **Rutas.** Los audios viven dentro de la carpeta del paquete. Una ruta
   que salga de ella se rechaza.

## Importar y exportar

```bash
# Carpeta -> base de datos del servidor
python -m backend.packs_io import packs/pack-prueba-a-001

# Base de datos -> carpeta en el formato abierto
python -m backend.packs_io export nah-central-001 salida/
```

Al arrancar, el servidor importa solo las carpetas de `packs/` (variable
`NEPANTLA_PACKS_DIR`). Para desactivarlo: `NEPANTLA_IMPORT_EXAMPLE_PACKS=0`.

Un paquete importado conserva sus revisores tal como vienen en el manifest.
Quien importa un paquete es responsable de que esas revisiones sean reales.

## Cómo sirve la app un paquete

| Dirección | Qué devuelve |
|-----------|--------------|
| `GET /api/packs` | Paquetes visibles y lista de retirados |
| `GET /api/packs/{id}/manifest.json` | El manifest, solo con frases de doble revisión |
| `GET /api/packs/{id}/audio/{frase}.opus` | El audio de una frase aprobada |
| `GET /api/packs/{id}/greeting.opus` | El saludo |

## Paquetes de ejemplo

`packs/pack-prueba-a-001` (todas las frases) y `packs/pack-prueba-b-001`
(incompleto a propósito, con dos frases de un solo revisor) son **tonos
generados por computadora**. Se regeneran con
`python scripts/make_test_packs.py`.
