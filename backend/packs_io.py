"""Importar y exportar paquetes en el formato abierto (ver docs/PACK_FORMAT.md).

Uso desde la terminal:

    python -m backend.packs_io import packs/pack-prueba-a-001
    python -m backend.packs_io export nah-central-001 salida/
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import sqlite3
import sys
from pathlib import Path

from .config import Settings
from .db import init_db, now_iso, open_db, seed_phrases
from .models import ID_PATTERN, PACK_STATUSES
from .security import hash_token, new_token
from .services import GREETING_ID, build_manifest, norm_alias

_ID = re.compile(ID_PATTERN)


class PackError(Exception):
    pass


def _distinct(names) -> list[str]:
    unique: dict[str, str] = {}
    for name in names or []:
        if isinstance(name, str) and name.strip():
            unique.setdefault(norm_alias(name), name.strip())
    return list(unique.values())


def _store_audio(settings: Settings, pack_id: str, source: Path) -> tuple[str, int]:
    target_dir = settings.audio_dir / pack_id
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(12)}.opus"
    shutil.copyfile(source, target_dir / name)
    return f"{pack_id}/{name}", (target_dir / name).stat().st_size


def import_pack_dir(
    conn: sqlite3.Connection, settings: Settings, pack_dir: Path, *, force: bool = False
) -> dict:
    """Carga una carpeta `pack-<codigo>/` a la base.

    Reglas que se respetan al importar:
    * Una frase con menos de dos revisores distintos entra como "pendiente"
      y la app no la muestra.
    * Si el paquete ya existe no se toca, salvo con `force=True`.
    * Devuelve los tokens de retiro (uno por voz). Solo existen en este
      momento: en la base queda únicamente su hash.
    """
    manifest_file = pack_dir / "manifest.json"
    if not manifest_file.is_file():
        raise PackError(f"No hay manifest.json en {pack_dir}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    if manifest.get("format_version") != 1:
        raise PackError("format_version desconocido (se esperaba 1).")
    pack_id = str(manifest.get("pack_id", ""))
    if not _ID.match(pack_id):
        raise PackError("pack_id no válido.")
    status = manifest.get("status", "draft")
    if status not in PACK_STATUSES:
        raise PackError("status no válido.")
    is_test = bool(manifest.get("is_test", False))
    if is_test and status != "draft":
        raise PackError("Un paquete de prueba solo puede estar en borrador.")

    exists = conn.execute("SELECT 1 FROM packs WHERE id = ?", (pack_id,)).fetchone()
    if exists and not force:
        return {"pack_id": pack_id, "imported": False, "tokens": {}}
    if exists:
        for rec in conn.execute("SELECT audio_path FROM recordings WHERE pack_id = ?", (pack_id,)):
            if rec["audio_path"]:
                (settings.audio_dir / rec["audio_path"]).unlink(missing_ok=True)
        conn.execute(
            "DELETE FROM reviews WHERE recording_id IN (SELECT id FROM recordings WHERE pack_id = ?)",
            (pack_id,),
        )
        conn.execute(
            "DELETE FROM reports WHERE recording_id IN (SELECT id FROM recordings WHERE pack_id = ?)",
            (pack_id,),
        )
        conn.execute("DELETE FROM recordings WHERE pack_id = ?", (pack_id,))
        conn.execute("DELETE FROM studio_sessions WHERE pack_id = ?", (pack_id,))
        conn.execute("DELETE FROM packs WHERE id = ?", (pack_id,))

    now = now_iso()
    conn.execute(
        """
        INSERT INTO packs (id, variant, language, community, version, status, license,
                           community_label, created_at, guardians, is_test, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pack_id,
            str(manifest.get("variant", "")),
            str(manifest.get("language", "")),
            str(manifest.get("community", "")),
            str(manifest.get("version", "0.1.0")),
            status,
            str(manifest.get("license", "")),
            manifest.get("community_label"),
            now,
            json.dumps(_distinct(manifest.get("guardians")), ensure_ascii=False),
            int(is_test),
            now,
        ),
    )

    known = {row["id"] for row in conn.execute("SELECT id FROM phrases")}
    consents: dict[str, int] = {}
    tokens: dict[str, str] = {}

    def consent_for(speaker: str) -> int:
        key = norm_alias(speaker)
        if key not in consents:
            token = new_token()
            cur = conn.execute(
                "INSERT INTO consents (credit_name, license, withdrawal_token_hash, signed_at)"
                " VALUES (?, ?, ?, ?)",
                (speaker, str(manifest.get("license", "")), hash_token(token), now),
            )
            consents[key] = cur.lastrowid
            tokens[speaker] = token
        return consents[key]

    entries = [dict(p) for p in manifest.get("phrases", [])]
    greeting = manifest.get("greeting")
    if isinstance(greeting, dict):
        entries.append({**greeting, "id": GREETING_ID, "audio": greeting.get("audio", "greeting.opus")})

    imported = pending = skipped = 0
    for entry in entries:
        phrase_id = str(entry.get("id", ""))
        audio_rel = str(entry.get("audio", ""))
        source = (pack_dir / audio_rel).resolve()
        if phrase_id not in known or pack_dir.resolve() not in source.parents or not source.is_file():
            skipped += 1
            continue
        reviewers = _distinct(entry.get("reviewed_by"))
        speaker = str(entry.get("recorded_by") or "sin-credito").strip()
        approved = len(reviewers) >= 2
        audio_path, size = _store_audio(settings, pack_id, source)
        cur = conn.execute(
            """
            INSERT INTO recordings (pack_id, phrase_id, audio_path, speaker_alias, consent_id,
                                    status, created_at, approved_at, bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pack_id, phrase_id, audio_path, speaker, consent_for(speaker),
                "approved" if approved else "pending", now,
                (str(entry.get("approved_at")) if approved and entry.get("approved_at") else (now if approved else None)),
                size,
            ),
        )
        for reviewer in reviewers:
            conn.execute(
                "INSERT INTO reviews (recording_id, reviewer_alias, verdict, note, created_at, reviewer_role)"
                " VALUES (?, ?, 'approve', '', ?, 'imported')",
                (cur.lastrowid, reviewer, now),
            )
        if approved:
            imported += 1
        else:
            pending += 1

    return {
        "pack_id": pack_id,
        "imported": True,
        "approved_phrases": imported,
        "pending_phrases": pending,
        "skipped": skipped,
        "tokens": tokens,
    }


def import_example_packs(conn: sqlite3.Connection, settings: Settings) -> list[dict]:
    results = []
    if not settings.packs_dir.is_dir():
        return results
    for pack_dir in sorted(settings.packs_dir.glob("pack-*")):
        if (pack_dir / "manifest.json").is_file():
            try:
                results.append(import_pack_dir(conn, settings, pack_dir))
            except (PackError, json.JSONDecodeError, OSError) as exc:
                results.append({"pack_id": pack_dir.name, "imported": False, "error": str(exc)})
    return results


def export_pack(conn: sqlite3.Connection, settings: Settings, pack_id: str, dest: Path) -> Path:
    """Escribe el paquete como carpeta `pack-<codigo>/` lista para compartir."""
    pack = conn.execute("SELECT * FROM packs WHERE id = ?", (pack_id,)).fetchone()
    if pack is None:
        raise PackError("Paquete no encontrado.")
    manifest = build_manifest(conn, pack)
    out = dest / f"pack-{pack_id}"
    (out / "audio").mkdir(parents=True, exist_ok=True)

    paths = {
        row["phrase_id"]: row["audio_path"]
        for row in conn.execute(
            "SELECT phrase_id, audio_path FROM recordings WHERE pack_id = ? AND status = 'approved'",
            (pack_id,),
        )
    }
    for phrase in manifest["phrases"]:
        shutil.copyfile(settings.audio_dir / paths[phrase["id"]], out / phrase["audio"])
    if manifest["greeting"]:
        shutil.copyfile(settings.audio_dir / paths[GREETING_ID], out / "greeting.opus")

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "LICENSE.txt").write_text(
        f"Licencia de este paquete, elegida por su comunidad:\n\n{pack['license'] or '(sin definir)'}\n",
        encoding="utf-8",
    )
    label = " (AUDIO DE PRUEBA, no es una lengua real)" if pack["is_test"] else ""
    (out / "README.md").write_text(
        f"# Paquete {pack_id}{label}\n\n"
        f"- Lengua: {pack['language']}\n- Variante: {pack['variant']}\n"
        f"- Comunidad: {pack['community']}\n- Versión: {pack['version']}\n"
        f"- Estado: {pack['status']}\n- Frases: {len(manifest['phrases'])}\n\n"
        "Formato abierto de Nepantla, versión 1. Ver docs/PACK_FORMAT.md.\n",
        encoding="utf-8",
    )
    return out


def _main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in {"import", "export"}:
        print(__doc__)
        return 2
    settings = Settings.from_env()
    init_db(settings.db_path)
    with open_db(settings) as conn:
        seed_phrases(conn, settings.phrases_file)
        if argv[1] == "import":
            result = import_pack_dir(conn, settings, Path(argv[2]), force="--force" in argv)
            tokens = result.pop("tokens")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if tokens:
                print("\nTokens de retiro (guárdalos y entrégalos a cada hablante; no se vuelven a mostrar):")
                for speaker, token in tokens.items():
                    print(f"  {speaker}: {token}")
        else:
            if len(argv) < 4:
                print("Falta la carpeta de destino.")
                return 2
            print(export_pack(conn, settings, argv[2], Path(argv[3])))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
