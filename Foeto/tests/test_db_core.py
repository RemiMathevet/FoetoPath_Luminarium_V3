"""Porte unique des connexions (db_core.open_db) — cf. chantier SQLCipher."""

import sqlite3

from db_core import open_db


def test_open_db_applique_wal_et_fk(tmp_path):
    conn = open_db(tmp_path / "t.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_open_db_fk_off_pour_les_migrations(tmp_path):
    conn = open_db(tmp_path / "t.db", foreign_keys=False, row_factory=False)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    assert conn.row_factory is None
    conn.close()


def test_fk_reellement_appliquees(tmp_path):
    """FK=ON doit refuser une reference orpheline, FK=OFF l'accepter."""
    db = tmp_path / "t.db"
    conn = open_db(db)
    conn.executescript(
        "CREATE TABLE parent(id INTEGER PRIMARY KEY);"
        "CREATE TABLE child(id INTEGER PRIMARY KEY,"
        " parent_id INTEGER NOT NULL REFERENCES parent(id) ON DELETE CASCADE);"
    )
    try:
        conn.execute("INSERT INTO child(parent_id) VALUES (999)")
        raise AssertionError("FK=ON aurait du rejeter l'orphelin")
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

    conn = open_db(db, foreign_keys=False)
    conn.execute("INSERT INTO child(parent_id) VALUES (999)")
    conn.commit()
    conn.close()
