"""Base de datos SQLite: un solo archivo, sin ORM.

Las tablas siguen el esquema de la especificación. Las columnas marcadas como
"extensión" son las mínimas que hicieron falta para cumplir las reglas
(guardianes, paquetes de prueba, rol del revisor, sesiones del estudio).

Decisión de privacidad: no existe ninguna tabla de pacientes, consultas ni
respuestas. `usage_counts` y `reports` guardan el día, nunca la hora.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS packs (
    id              TEXT PRIMARY KEY,
    variant         TEXT NOT NULL,
    language        TEXT NOT NULL,
    community       TEXT NOT NULL DEFAULT '',
    region          TEXT NOT NULL DEFAULT '',
    version         TEXT NOT NULL DEFAULT '0.1.0',
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'approved', 'withdrawn')),
    license         TEXT NOT NULL DEFAULT '',
    community_label TEXT,
    created_at      TEXT NOT NULL,
    -- extensiones
    guardians       TEXT NOT NULL DEFAULT '[]',
    is_test         INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phrases (
    id          TEXT PRIMARY KEY,
    scenario    TEXT NOT NULL,
    es_text     TEXT NOT NULL,
    answer_type TEXT NOT NULL
                CHECK (answer_type IN ('yes_no', 'pictogram', 'body_map',
                                       'pain_scale', 'duration', 'none')),
    pictogram   TEXT,
    priority    TEXT NOT NULL DEFAULT 'normal'
                CHECK (priority IN ('normal', 'critica')),
    -- extensiones
    position    INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS consents (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_name           TEXT NOT NULL,
    license               TEXT NOT NULL,
    withdrawal_token_hash TEXT NOT NULL UNIQUE,
    signed_at             TEXT NOT NULL,
    -- extensión
    withdrawn_at          TEXT
);

CREATE TABLE IF NOT EXISTS recordings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id       TEXT NOT NULL REFERENCES packs(id),
    phrase_id     TEXT NOT NULL REFERENCES phrases(id),
    audio_path    TEXT NOT NULL,
    speaker_alias TEXT NOT NULL,
    consent_id    INTEGER NOT NULL REFERENCES consents(id),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected',
                                    'superseded', 'withdrawn')),
    created_at    TEXT NOT NULL,
    -- extensiones
    approved_at   TEXT,
    bytes         INTEGER NOT NULL DEFAULT 0
);

-- Como mucho una grabación vigente por frase y paquete.
CREATE UNIQUE INDEX IF NOT EXISTS one_approved_per_phrase
    ON recordings (pack_id, phrase_id) WHERE status = 'approved';
CREATE INDEX IF NOT EXISTS recordings_by_pack ON recordings (pack_id, status);
CREATE INDEX IF NOT EXISTS recordings_by_consent ON recordings (consent_id);

CREATE TABLE IF NOT EXISTS reviews (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id   INTEGER NOT NULL REFERENCES recordings(id),
    reviewer_alias TEXT NOT NULL,
    verdict        TEXT NOT NULL CHECK (verdict IN ('approve', 'reject')),
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    -- extensión: 'interpreter', 'health' o 'imported'
    reviewer_role  TEXT NOT NULL DEFAULT 'health',
    UNIQUE (recording_id, reviewer_alias)
);

CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER NOT NULL REFERENCES recordings(id),
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'resolved', 'dismissed')),
    created_at   TEXT NOT NULL  -- solo el día (AAAA-MM-DD)
);

-- Solo conteos agregados por día. Sin IP, sin dispositivo, sin hora.
CREATE TABLE IF NOT EXISTS usage_counts (
    day     TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    event   TEXT NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, pack_id, event)
);

-- extensión: enlaces únicos del estudio (hablantes, revisores, guardianes)
CREATE TABLE IF NOT EXISTS studio_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash     TEXT NOT NULL UNIQUE,
    pack_id        TEXT NOT NULL REFERENCES packs(id),
    role           TEXT NOT NULL CHECK (role IN ('speaker', 'reviewer', 'guardian')),
    alias          TEXT NOT NULL,
    is_interpreter INTEGER NOT NULL DEFAULT 0,
    consent_id     INTEGER REFERENCES consents(id),
    created_at     TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    revoked        INTEGER NOT NULL DEFAULT 0
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    """Día en UTC. Es la única marca de tiempo que llevan conteos y reportes."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def days_from_now(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def open_db(settings) -> Iterator[sqlite3.Connection]:
    """Conexión con transacción: confirma al salir, deshace si hubo error."""
    conn = connect(settings.db_path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Pone al día una base creada con una versión anterior del esquema."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(packs)")}
    if "region" not in columns:
        conn.execute("ALTER TABLE packs ADD COLUMN region TEXT NOT NULL DEFAULT ''")


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def seed_phrases(conn: sqlite3.Connection, phrases_file: Path) -> int:
    """Copia las frases en español del frontend a la tabla `phrases`.

    `frontend/data/phrases.es.json` es la única fuente: así la app sin
    internet y el servidor nunca se desincronizan.
    """
    data = json.loads(phrases_file.read_text(encoding="utf-8"))
    items = list(data.get("system_phrases", [])) + list(data["phrases"])
    ids = []
    for position, phrase in enumerate(items):
        ids.append(phrase["id"])
        conn.execute(
            """
            INSERT INTO phrases (id, scenario, es_text, answer_type, pictogram,
                                 priority, position, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                scenario = excluded.scenario,
                es_text = excluded.es_text,
                answer_type = excluded.answer_type,
                pictogram = excluded.pictogram,
                priority = excluded.priority,
                position = excluded.position,
                active = 1
            """,
            (
                phrase["id"],
                phrase["scenario"],
                phrase["es_text"],
                phrase["answer_type"],
                phrase.get("pictogram"),
                phrase.get("priority", "normal"),
                position,
            ),
        )
    # Las frases que ya no están en el archivo se desactivan, no se borran:
    # puede haber grabaciones que las referencian.
    marks = ",".join("?" for _ in ids)
    conn.execute(f"UPDATE phrases SET active = 0 WHERE id NOT IN ({marks})", ids)
    return len(ids)
