#!/usr/bin/env python3
"""
FoetoPath — Module base de données (schéma BaMaRa-natif).

Architecture multi-tables :
  - bam_identity, bam_medicare, bam_encounter, bam_condition, ... → SDM-MR v2.17
  - hub_case, hub_foeto_details, hub_pediatric_details            → champs locaux
  - module_data, macro_folders, settings                          → workflow

Le CRUD case expose une interface plate (mêmes noms de champs qu'avant)
qui dispatch vers les bonnes tables BaMaRa en écriture et reconstruit
un dict unifié en lecture via JOIN.
"""

import json
import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from config import (KNOWN_MODULES_FOETUS, MACRO_FOLDER_TYPES, DEFAULT_SETTINGS,
                     BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID)
from db_core import DatabaseManager, _now, _row_to_dict

log = logging.getLogger(__name__)

# ── Instance partagée ────────────────────────────────────────────────────

_mgr = DatabaseManager(
    db_name="foetopath.db",
    cases_table="bam_identity",
    modules_table="module_data",
)

KNOWN_MODULES = KNOWN_MODULES_FOETUS

SCHEMA_FILE = Path(__file__).parent / "bamara_schema.sql"


# ── Init & Connexion ────────────────────────────────────────────────────

def _generate_uuid(conn) -> str:
    """Génère un UUID4 garanti unique dans bam_identity."""
    for _ in range(10):
        candidate = str(uuid.uuid4())
        if not conn.execute("SELECT 1 FROM bam_identity WHERE case_uuid=?", (candidate,)).fetchone():
            return candidate
    raise RuntimeError("UUID collision 10x — vérifier le PRNG")


def _ensure_case_uuids(conn):
    """Attribue un UUID aux cas existants qui n'en ont pas."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(bam_identity)").fetchall()}
    if "case_uuid" not in cols:
        conn.execute("ALTER TABLE bam_identity ADD COLUMN case_uuid TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_case_uuid ON bam_identity(case_uuid)")
    rows = conn.execute("SELECT id FROM bam_identity WHERE case_uuid IS NULL").fetchall()
    for r in rows:
        conn.execute("UPDATE bam_identity SET case_uuid=? WHERE id=?",
                     (_generate_uuid(conn), r[0]))
    if rows:
        log.info("Assigned UUIDs to %d existing cases", len(rows))


def init_db(base_dir: str | Path) -> Path:
    db_path = _mgr.set_path(base_dir)
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with _mgr.connect() as conn:
        conn.executescript(schema_sql)
        _ensure_default_settings(conn)
        _ensure_case_uuids(conn)
    _migrate_legacy_safe(db_path)
    return db_path


def get_db_path() -> Path:
    return _mgr.get_db_path()


_connect = _mgr.connect


def _ensure_default_settings(conn):
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v)
        )


def _migrate_legacy_safe(db_path):
    """Lance la migration legacy avec FK désactivées (connexion dédiée)."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.row_factory = sqlite3.Row
    try:
        _migrate_legacy(conn)
        conn.commit()
    except Exception:
        log.error("Legacy migration failed, rolling back", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


def _rebuild_table_fk(conn, table_name):
    """Reconstruit une table pour changer la FK cases(id) → bam_identity(id)."""
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not schema_row:
        return
    old_sql = schema_row[0]
    new_sql = old_sql.replace("REFERENCES cases(id)", "REFERENCES bam_identity(id)")
    if new_sql == old_sql:
        return
    idx_rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table_name,),
    ).fetchall()
    temp = f"_{table_name}_mig"
    conn.execute(f"ALTER TABLE [{table_name}] RENAME TO [{temp}]")
    conn.execute(new_sql)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info([{temp}])").fetchall()]
    cols_str = ", ".join(f"[{c}]" for c in cols)
    conn.execute(f"INSERT INTO [{table_name}] ({cols_str}) SELECT {cols_str} FROM [{temp}]")
    conn.execute(f"DROP TABLE [{temp}]")
    for idx_row in idx_rows:
        try:
            conn.execute(idx_row[0])
        except sqlite3.OperationalError:
            pass


def _migrate_legacy(conn):
    """Migre les données de l'ancienne table 'cases' si elle existe."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "cases" not in tables:
        return
    count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    already = conn.execute("SELECT COUNT(*) FROM bam_identity").fetchone()[0]
    if count == 0 or already > 0:
        return
    log.info("Migration legacy: %d cas à transférer depuis 'cases'", count)
    rows = conn.execute("SELECT * FROM cases").fetchall()
    id_map = {}
    for row in rows:
        r = dict(row)
        old_id = r.get("id")
        identity_id = _migrate_one_case(conn, r)
        if old_id and identity_id:
            id_map[old_id] = identity_id

    for old_id, new_id in id_map.items():
        if old_id != new_id:
            conn.execute("UPDATE module_data SET case_id = ? WHERE case_id = ?",
                         (new_id, old_id))
            conn.execute("UPDATE macro_folders SET case_id = ? WHERE case_id = ?",
                         (new_id, old_id))

    _rebuild_table_fk(conn, "module_data")
    _rebuild_table_fk(conn, "macro_folders")
    log.info("Migration legacy terminée: %d cas transférés", count)


def _migrate_one_case(conn, r):
    """Migre un seul cas de l'ancienne table 'cases' vers BaMaRa.
    Retourne le nouvel identity_id."""
    now = _now()
    gender = _map_sexe_to_gender(r.get("sexe"))
    mother_name = (r.get("nom_mere") or "").strip().upper() or None
    mother_given_name = (r.get("prenom_mere") or "").strip() or None
    mother_family_name_birth = (r.get("nom_naissance_mere") or "").strip().upper() or None
    nom_foetus = (r.get("nom_foetus") or "").strip().upper() or None
    prenom_foetus = (r.get("prenom_foetus") or "").strip() or None

    ddn_foetus_y, ddn_foetus_m, ddn_foetus_d = _parse_date(r.get("ddn_foetus"))
    death_y, death_m, death_d = _parse_date(r.get("date_deces"))
    residence_city = (r.get("lieu_residence") or "").strip() or None

    cursor = conn.execute(
        """INSERT INTO bam_identity (gender, is_fetus,
           mother_name, mother_given_name, mother_family_name_birth,
           family_name_used, given_name_used,
           birth_date_year, birth_date_month, birth_date_day,
           deceased, death_date_year, death_date_month, death_date_day,
           residence_city, residence_country_code,
           has_given_consent, created_at, updated_at)
        VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FR', 1, ?, ?)""",
        (gender, mother_name, mother_given_name, mother_family_name_birth,
         nom_foetus, prenom_foetus,
         ddn_foetus_y, ddn_foetus_m, ddn_foetus_d,
         1 if death_y else None, death_y, death_m, death_d,
         residence_city,
         r.get("created_at") or now, r.get("updated_at") or now),
    )
    identity_id = cursor.lastrowid

    type_issue = r.get("type_issue")
    case_type = _infer_case_type(type_issue, r.get("indication_examen"))
    terme_sa, terme_jours = _parse_terme(r.get("terme_issue"))

    conn.execute(
        """INSERT INTO hub_case (identity_id, hub_case_number, case_id_externe,
           case_type, type_prelevement, indication_examen, service_demandeur,
           ddn_mere, terme_jours, ville_maternite,
           acte_clinique, acte_imagerie, acte_anapath, acte_interne, acte_virtopsie,
           numero_placenta, examen_placenta,
           dossier_macro_path, dossier_lames_path,
           assigned_to, created_by, modified_by, status, notes,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (identity_id, r.get("numero_dossier"), r.get("case_id_externe"),
         case_type, type_issue, r.get("indication_examen"), r.get("service_demandeur"),
         r.get("ddn_mere"), terme_jours, r.get("ville_maternite"),
         r.get("acte_clinique") or 0, r.get("acte_imagerie") or 0,
         r.get("acte_anapath") or 0, r.get("acte_interne") or 0,
         r.get("acte_virtopsie") or 0,
         r.get("numero_placenta"), r.get("examen_placenta") or 0,
         r.get("dossier_macro_path"), r.get("dossier_lames_path"),
         r.get("assigned_to"), r.get("created_by"), r.get("modified_by"),
         _map_status_to_hub(r.get("statut")), r.get("notes"),
         r.get("created_at") or now, r.get("updated_at") or now),
    )

    conn.execute(
        """INSERT INTO bam_condition (identity_id, diagnostic_status,
           early_diagnosis_status, site_diag_code, site_diag_label,
           site_diag_id, source_id)
        VALUES (?, 'ONG', 'PRN', ?, ?, ?, 'AUTONOMOUS')""",
        (identity_id, BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID),
    )

    if terme_sa is not None:
        is_birth = type_issue == "MNN"
        termination_type = _infer_termination_type(type_issue, r.get("indication_examen"))
        conn.execute(
            """INSERT INTO bam_pregnancy_end (identity_id, birth, termination_type,
               term_week, is_foetopathology_done)
            VALUES (?, ?, ?, ?, 1)""",
            (identity_id, 1 if is_birth else 0,
             None if is_birth else termination_type, terme_sa),
        )

    date_examen = r.get("date_examen")
    if date_examen:
        ey, em, ed = _parse_date(date_examen)
        if ey:
            medecin = (r.get("medecin_referent") or "").strip() or None
            cursor2 = conn.execute(
                """INSERT INTO bam_medicare (identity_id, inclusion_date_year,
                   inclusion_date_month, inclusion_date_day, care_provider_name,
                   site_code, site_label, site_id, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'AUTONOMOUS')""",
                (identity_id, ey, em, ed, medecin,
                 BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID),
            )
            medicare_id = cursor2.lastrowid
            conn.execute(
                """INSERT INTO bam_encounter (medicare_id, encounter_date_year,
                   encounter_date_month, encounter_date_day, context,
                   context_precision, objectives, source_id)
                VALUES (?, ?, ?, ?, 'A', 'Examen foeto-placentaire', 'DIA', 'AUTONOMOUS')""",
                (medicare_id, ey, em, ed),
            )

    return identity_id


# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_date(iso_str):
    if not iso_str or str(iso_str).strip() == "":
        return None, None, None
    try:
        from datetime import datetime
        d = datetime.strptime(str(iso_str).strip()[:10], "%Y-%m-%d")
        return d.year, d.month, d.day
    except ValueError:
        return None, None, None


def _reconstruct_date(year, month, day):
    if year is None:
        return None
    try:
        return f"{int(year):04d}-{int(month or 1):02d}-{int(day or 1):02d}"
    except (ValueError, TypeError):
        return None


def _int_or_none(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float_or_none(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_terme(terme_str):
    """Parse '24+3', '24 SA + 3j', '24' en (sa, jours)."""
    if not terme_str:
        return None, None
    s = str(terme_str).replace("SA", "").replace("sa", "").replace("j", "").strip()
    m = re.match(r"(\d+)\s*[+]\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(\d+)", s)
    if m:
        return int(m.group(1)), 0
    return None, None


def _format_terme(sa, jours):
    if sa is None:
        return None
    if jours:
        return f"{sa} SA + {jours}j"
    return f"{sa} SA"


def _map_sexe_to_gender(sexe: str | None) -> str:
    if not sexe:
        return "UNK"
    s = sexe.strip().upper()
    if s in ("M", "MASCULIN", "GARCON", "GARÇON", "MALE"):
        return "M"
    if s in ("F", "FEMININ", "FÉMININ", "FILLE", "FEMALE"):
        return "F"
    return "UNK"


def _map_gender_to_sexe(gender: str | None) -> str:
    return gender if gender in ("M", "F") else "I"


def _map_status_to_hub(statut: str | None) -> str:
    mapping = {"en_cours": "DRAFT", "complet": "READY", "termine": "READY", "archive": "CONFIRMED"}
    return mapping.get(statut, "DRAFT")


def _map_status_from_hub(status: str | None) -> str:
    mapping = {"DRAFT": "en_cours", "READY": "complet", "VALIDATED": "complet",
               "SENT": "complet", "ERROR": "en_cours", "CONFIRMED": "archive"}
    return mapping.get(status, "en_cours")


def _infer_case_type(type_issue: str | None, indication: str | None = None) -> str:
    _MAP = {"IMG": "IMG", "MFIU": "MFIU", "MNN": "DECES_NEONATAL",
            "MPN": "MPN", "FCS": "FCS", "NAISSANCE": "NAISSANCE", "ISG": "FCS",
            "DECES_PEDIATRIQUE": "DECES_PEDIATRIQUE"}
    if type_issue and type_issue in _MAP:
        return _MAP[type_issue]
    if not indication:
        return "AUTRE"
    i = indication.upper()
    if "IMG" in i:
        return "IMG"
    if "MFIU" in i or "MORT" in i:
        return "MFIU"
    return "AUTRE"


def _infer_termination_type(type_issue: str | None, indication: str | None = None) -> str | None:
    _MAP = {"IMG": "IMG", "MFIU": "ISG", "FCS": "ISG", "ISG": "ISG", "MPN": "ISG"}
    if type_issue and type_issue in _MAP:
        return _MAP[type_issue]
    if not indication:
        return None
    i = indication.upper()
    if "IMG" in i:
        return "IMG"
    return "ISG" if ("MFIU" in i or "MORT" in i) else None


# ── Lecture : SELECT multi-tables ────────────────────────────────────────

_CASE_SELECT = """
SELECT
    i.id,
    i.case_uuid,
    hc.hub_case_number AS numero_dossier,
    hc.case_id_externe,
    i.mother_name AS nom_mere,
    i.mother_given_name AS prenom_mere,
    i.mother_family_name_birth AS nom_naissance_mere,
    hc.ddn_mere,
    i.residence_city AS lieu_residence,
    i.family_name_used AS nom_foetus,
    i.given_name_used AS prenom_foetus,
    i.gender,
    i.birth_date_year, i.birth_date_month, i.birth_date_day,
    i.death_date_year, i.death_date_month, i.death_date_day,
    pe.term_week AS terme_sa,
    hc.terme_jours,
    hc.type_prelevement,
    hc.indication_examen,
    hc.contexte_clinique,
    hc.service_demandeur,
    hc.ville_maternite,
    m.care_provider_name AS medecin_referent,
    m.care_provider_rpps AS medecin_rpps,
    m.inclusion_date_year, m.inclusion_date_month, m.inclusion_date_day,
    e.encounter_date_year, e.encounter_date_month, e.encounter_date_day,
    hc.acte_clinique, hc.acte_imagerie, hc.acte_anapath,
    hc.acte_interne, hc.acte_virtopsie,
    hc.numero_placenta, hc.examen_placenta,
    hc.dossier_macro_path, hc.dossier_lames_path,
    hc.status AS hub_status,
    hc.assigned_to, hc.created_by, hc.modified_by,
    hc.notes,
    i.ins, i.ipp, i.ipp_fetus,
    i.opposition,
    i.inbreeding AS consanguinite,
    i.is_multiple_pregnancy AS grossesse_multiple,
    i.medecin_traitant_rpps,
    ant.amp AS antenatal_amp,
    ant.term AS antenatal_term,
    ant.height AS antenatal_height,
    ant.weight AS antenatal_weight,
    ant.head_circumference AS antenatal_hc,
    prop.propositus_ipp,
    prop.propositus_ins,
    prop.relation AS propositus_relation,
    res.contact_allowed AS research_contact,
    res.sample_research,
    res.sample_diagnostic,
    res.biobank AS research_biobank,
    i.created_at,
    i.updated_at
FROM bam_identity i
LEFT JOIN hub_case hc ON hc.identity_id = i.id
LEFT JOIN bam_pregnancy_end pe ON pe.identity_id = i.id
LEFT JOIN bam_medicare m ON m.identity_id = i.id
LEFT JOIN bam_encounter e ON e.medicare_id = m.id
LEFT JOIN bam_antenatal ant ON ant.identity_id = i.id
LEFT JOIN bam_propositus prop ON prop.identity_id = i.id
LEFT JOIN bam_research res ON res.identity_id = i.id
"""


def _get_data_root() -> str:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'data_root'"
        ).fetchone()
        return row["value"] if row and row["value"] else ""


def _resolve_path(rel_path: str | None) -> str | None:
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        return rel_path
    root = _get_data_root()
    if root:
        return str(Path(root) / rel_path)
    return rel_path


def _to_relative_path(abs_path: str | None) -> str | None:
    if not abs_path:
        return abs_path
    root = _get_data_root()
    if root and abs_path.startswith(root):
        rel = abs_path[len(root):].lstrip("/")
        return rel if rel else abs_path
    return abs_path


def _row_to_case(row) -> dict:
    d = dict(row)
    d["sexe"] = _map_gender_to_sexe(d.pop("gender", None))
    d["ddn_foetus"] = _reconstruct_date(
        d.pop("birth_date_year", None),
        d.pop("birth_date_month", None),
        d.pop("birth_date_day", None),
    )
    d["date_deces"] = _reconstruct_date(
        d.pop("death_date_year", None),
        d.pop("death_date_month", None),
        d.pop("death_date_day", None),
    )
    d["date_reception"] = _reconstruct_date(
        d.pop("inclusion_date_year", None),
        d.pop("inclusion_date_month", None),
        d.pop("inclusion_date_day", None),
    )
    d["date_examen"] = _reconstruct_date(
        d.pop("encounter_date_year", None),
        d.pop("encounter_date_month", None),
        d.pop("encounter_date_day", None),
    )
    d["statut"] = _map_status_from_hub(d.pop("hub_status", None))
    d["type_issue"] = d.pop("type_prelevement", None)
    d["terme_issue"] = _format_terme(d.pop("terme_sa", None), d.get("terme_jours"))
    d["dossier_macro_path"] = _resolve_path(d.get("dossier_macro_path"))
    d["dossier_lames_path"] = _resolve_path(d.get("dossier_lames_path"))
    return d


# ── CRUD Cases ───────────────────────────────────────────────────────────

def create_case(data: dict) -> int:
    numero = data.get("numero_dossier")
    if numero:
        existing = get_case_by_numero(numero)
        if existing:
            raise ValueError(f"Le dossier {numero} existe déjà (id={existing['id']})")
    now = _now()
    gender = _map_sexe_to_gender(data.get("sexe"))
    mother_name = (data.get("nom_mere") or "").strip().upper() or None
    mother_given_name = (data.get("prenom_mere") or "").strip() or None
    mother_family_name_birth = (data.get("nom_naissance_mere") or "").strip().upper() or None
    nom_foetus = (data.get("nom_foetus") or "").strip().upper() or None
    prenom_foetus = (data.get("prenom_foetus") or "").strip() or None
    residence_city = (data.get("lieu_residence") or "").strip() or None

    ddn_foetus_y, ddn_foetus_m, ddn_foetus_d = _parse_date(data.get("ddn_foetus"))
    death_y, death_m, death_d = _parse_date(data.get("date_deces"))

    with _mgr.connect() as conn:
        case_uuid = _generate_uuid(conn)
        cursor = conn.execute(
            """INSERT INTO bam_identity (case_uuid, gender, is_fetus,
               mother_name, mother_given_name, mother_family_name_birth,
               family_name_used, given_name_used,
               birth_date_year, birth_date_month, birth_date_day,
               deceased, death_date_year, death_date_month, death_date_day,
               residence_city, residence_country_code,
               ins, ipp, ipp_fetus, opposition,
               inbreeding, is_multiple_pregnancy,
               medecin_traitant_rpps,
               has_given_consent, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FR',
                    ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (case_uuid, gender, mother_name, mother_given_name, mother_family_name_birth,
             nom_foetus, prenom_foetus,
             ddn_foetus_y, ddn_foetus_m, ddn_foetus_d,
             1 if death_y else None, death_y, death_m, death_d,
             residence_city,
             data.get("ins"), data.get("ipp"), data.get("ipp_fetus"),
             data.get("opposition"),
             data.get("consanguinite"), data.get("grossesse_multiple"),
             data.get("medecin_traitant_rpps"),
             now, now),
        )
        identity_id = cursor.lastrowid

        type_issue = data.get("type_issue")
        case_type = _infer_case_type(type_issue, data.get("indication_examen"))
        terme_sa, terme_jours_parsed = _parse_terme(data.get("terme_issue"))
        terme_jours = _int_or_none(data.get("terme_jours")) or terme_jours_parsed

        conn.execute(
            """INSERT INTO hub_case (identity_id, hub_case_number, case_id_externe,
               case_type, type_prelevement, indication_examen, contexte_clinique,
               service_demandeur, ddn_mere, terme_jours, ville_maternite,
               acte_clinique, acte_imagerie, acte_anapath, acte_interne, acte_virtopsie,
               numero_placenta, examen_placenta,
               dossier_macro_path, dossier_lames_path,
               assigned_to, created_by, status, notes,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)""",
            (identity_id, data.get("numero_dossier"), data.get("case_id_externe"),
             case_type, type_issue, data.get("indication_examen"),
             data.get("contexte_clinique"),
             data.get("service_demandeur"), data.get("ddn_mere"),
             terme_jours, data.get("ville_maternite"),
             1 if data.get("acte_clinique") else 0,
             1 if data.get("acte_imagerie") else 0,
             1 if data.get("acte_anapath") else 0,
             1 if data.get("acte_interne") else 0,
             1 if data.get("acte_virtopsie") else 0,
             data.get("numero_placenta"),
             1 if data.get("examen_placenta") else 0,
             _to_relative_path(data.get("dossier_macro_path")),
             _to_relative_path(data.get("dossier_lames_path")),
             data.get("assigned_to"), data.get("created_by"),
             data.get("notes"), now, now),
        )

        conn.execute(
            """INSERT INTO bam_condition (identity_id, diagnostic_status,
               early_diagnosis_status, site_diag_code, site_diag_label,
               site_diag_id, source_id)
            VALUES (?, 'ONG', 'PRN', ?, ?, ?, 'AUTONOMOUS')""",
            (identity_id, BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID),
        )

        if terme_sa is not None:
            is_birth = type_issue == "MNN"
            termination_type = _infer_termination_type(type_issue, data.get("indication_examen"))
            conn.execute(
                """INSERT INTO bam_pregnancy_end (identity_id, birth,
                   termination_type, term_week, is_foetopathology_done)
                VALUES (?, ?, ?, ?, 1)""",
                (identity_id, 1 if is_birth else 0,
                 None if is_birth else termination_type, terme_sa),
            )
            if is_birth:
                conn.execute(
                    "UPDATE bam_identity SET deceased = 1 WHERE id = ?",
                    (identity_id,),
                )

        date_reception = data.get("date_reception") or data.get("date_examen")
        if date_reception:
            ry, rm, rd = _parse_date(date_reception)
            if ry:
                medecin = (data.get("medecin_referent") or "").strip() or None
                cur2 = conn.execute(
                    """INSERT INTO bam_medicare (identity_id, inclusion_date_year,
                       inclusion_date_month, inclusion_date_day,
                       care_provider_name, care_provider_rpps,
                       site_code, site_label, site_id, source_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AUTONOMOUS')""",
                    (identity_id, ry, rm, rd, medecin,
                     data.get("medecin_rpps"),
                     BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID),
                )
                medicare_id = cur2.lastrowid

                date_examen = data.get("date_examen")
                if date_examen:
                    ey, em, ed = _parse_date(date_examen)
                    if ey:
                        conn.execute(
                            """INSERT INTO bam_encounter (medicare_id,
                               encounter_date_year, encounter_date_month,
                               encounter_date_day, context, context_precision,
                               objectives, source_id)
                            VALUES (?, ?, ?, ?, 'A', 'Examen foeto-placentaire',
                                    'DIA', 'AUTONOMOUS')""",
                            (medicare_id, ey, em, ed),
                        )

        return identity_id


def update_case(case_id: int, data: dict) -> bool:
    now = _now()

    with _mgr.connect() as conn:
        # ── bam_identity fields ──
        id_updates, id_params = [], []
        _identity_map = {
            "nom_mere": ("mother_name", lambda v: (v or "").strip().upper() or None),
            "prenom_mere": ("mother_given_name", lambda v: (v or "").strip() or None),
            "nom_naissance_mere": ("mother_family_name_birth", lambda v: (v or "").strip().upper() or None),
            "nom_foetus": ("family_name_used", lambda v: (v or "").strip().upper() or None),
            "prenom_foetus": ("given_name_used", lambda v: (v or "").strip() or None),
            "lieu_residence": ("residence_city", lambda v: (v or "").strip() or None),
            "ins": ("ins", lambda v: v or None),
            "ipp": ("ipp", lambda v: v or None),
            "ipp_fetus": ("ipp_fetus", lambda v: v or None),
            "opposition": ("opposition", lambda v: v),
            "consanguinite": ("inbreeding", lambda v: v),
            "grossesse_multiple": ("is_multiple_pregnancy", lambda v: v),
            "medecin_traitant_rpps": ("medecin_traitant_rpps", lambda v: (v or "").strip() or None),
        }
        for field, (col, transform) in _identity_map.items():
            if field in data:
                id_updates.append(f"{col} = ?")
                id_params.append(transform(data[field]))
        if "sexe" in data:
            id_updates.append("gender = ?")
            id_params.append(_map_sexe_to_gender(data["sexe"]))
        if "ddn_foetus" in data:
            y, m, d = _parse_date(data["ddn_foetus"])
            id_updates.extend(["birth_date_year = ?", "birth_date_month = ?", "birth_date_day = ?"])
            id_params.extend([y, m, d])
        if "date_deces" in data:
            y, m, d = _parse_date(data["date_deces"])
            id_updates.extend(["deceased = ?", "death_date_year = ?",
                               "death_date_month = ?", "death_date_day = ?"])
            id_params.extend([1 if y else None, y, m, d])
        if id_updates:
            id_updates.append("updated_at = ?")
            id_params.append(now)
            id_params.append(case_id)
            conn.execute(
                f"UPDATE bam_identity SET {', '.join(id_updates)} WHERE id = ?",
                id_params,
            )

        # ── hub_case fields ──
        hub_fields = {}
        _hub_direct = {
            "case_id_externe", "indication_examen", "contexte_clinique",
            "service_demandeur", "ddn_mere", "ville_maternite",
            "numero_placenta", "dossier_macro_path", "dossier_lames_path",
            "assigned_to", "modified_by", "notes",
        }
        for f in _hub_direct:
            if f in data:
                hub_fields[f] = data[f]
        if "dossier_macro_path" in hub_fields:
            hub_fields["dossier_macro_path"] = _to_relative_path(hub_fields["dossier_macro_path"])
        if "dossier_lames_path" in hub_fields:
            hub_fields["dossier_lames_path"] = _to_relative_path(hub_fields["dossier_lames_path"])
        if "numero_dossier" in data:
            hub_fields["hub_case_number"] = data["numero_dossier"]
        if "type_issue" in data:
            hub_fields["type_prelevement"] = data["type_issue"]
            hub_fields["case_type"] = _infer_case_type(
                data["type_issue"], data.get("indication_examen"))
        if "statut" in data:
            hub_fields["status"] = _map_status_to_hub(data["statut"])
        for flag in ("acte_clinique", "acte_imagerie", "acte_anapath",
                     "acte_interne", "acte_virtopsie", "examen_placenta"):
            if flag in data:
                hub_fields[flag] = 1 if data[flag] else 0
        if "terme_issue" in data:
            sa, jours = _parse_terme(data["terme_issue"])
            hub_fields["terme_jours"] = jours
        if "terme_jours" in data:
            hub_fields["terme_jours"] = _int_or_none(data["terme_jours"])
        if hub_fields:
            hub_fields["updated_at"] = now
            sets = ", ".join(f"{k} = ?" for k in hub_fields)
            conn.execute(
                f"UPDATE hub_case SET {sets} WHERE identity_id = ?",
                list(hub_fields.values()) + [case_id],
            )

        # ── bam_pregnancy_end ──
        terme_sa = None
        if "terme_issue" in data:
            terme_sa, _ = _parse_terme(data["terme_issue"])
        if terme_sa is not None:
            existing = conn.execute(
                "SELECT id FROM bam_pregnancy_end WHERE identity_id = ?", (case_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE bam_pregnancy_end SET term_week = ? WHERE identity_id = ?",
                    (terme_sa, case_id),
                )
            else:
                type_issue = data.get("type_issue")
                is_birth = type_issue == "MNN"
                termination_type = _infer_termination_type(
                    type_issue, data.get("indication_examen"))
                conn.execute(
                    """INSERT INTO bam_pregnancy_end (identity_id, birth,
                       termination_type, term_week, is_foetopathology_done)
                    VALUES (?, ?, ?, ?, 1)""",
                    (case_id, 1 if is_birth else 0,
                     None if is_birth else termination_type, terme_sa),
                )

        # ── bam_medicare / bam_encounter ──
        if "date_reception" in data or "medecin_referent" in data or "medecin_rpps" in data:
            medicare = conn.execute(
                "SELECT id FROM bam_medicare WHERE identity_id = ?", (case_id,)
            ).fetchone()
            date_reception = data.get("date_reception")
            ry, rm, rd = _parse_date(date_reception) if date_reception else (None, None, None)

            if medicare:
                med_updates, med_params = [], []
                if ry:
                    med_updates.extend(["inclusion_date_year = ?",
                                        "inclusion_date_month = ?",
                                        "inclusion_date_day = ?"])
                    med_params.extend([ry, rm, rd])
                if "medecin_referent" in data:
                    med_updates.append("care_provider_name = ?")
                    med_params.append((data["medecin_referent"] or "").strip() or None)
                if "medecin_rpps" in data:
                    med_updates.append("care_provider_rpps = ?")
                    med_params.append((data["medecin_rpps"] or "").strip() or None)
                if med_updates:
                    med_updates.append("updated_at = ?")
                    med_params.append(now)
                    med_params.append(medicare["id"])
                    conn.execute(
                        f"UPDATE bam_medicare SET {', '.join(med_updates)} WHERE id = ?",
                        med_params,
                    )
            elif ry:
                medecin = (data.get("medecin_referent") or "").strip() or None
                conn.execute(
                    """INSERT INTO bam_medicare (identity_id, inclusion_date_year,
                       inclusion_date_month, inclusion_date_day,
                       care_provider_name, care_provider_rpps,
                       site_code, site_label, site_id, source_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AUTONOMOUS')""",
                    (case_id, ry, rm, rd, medecin,
                     (data.get("medecin_rpps") or "").strip() or None,
                     BAMARA_SITE_CODE, BAMARA_SITE_LABEL, BAMARA_SITE_ID),
                )

        if "date_examen" in data:
            ey, em, ed = _parse_date(data["date_examen"])
            medicare = conn.execute(
                "SELECT id FROM bam_medicare WHERE identity_id = ?", (case_id,)
            ).fetchone()
            if medicare and ey:
                encounter = conn.execute(
                    "SELECT id FROM bam_encounter WHERE medicare_id = ?",
                    (medicare["id"],),
                ).fetchone()
                if encounter:
                    conn.execute(
                        """UPDATE bam_encounter SET encounter_date_year = ?,
                           encounter_date_month = ?, encounter_date_day = ?,
                           updated_at = ? WHERE id = ?""",
                        (ey, em, ed, now, encounter["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO bam_encounter (medicare_id,
                           encounter_date_year, encounter_date_month,
                           encounter_date_day, context, context_precision,
                           objectives, source_id)
                        VALUES (?, ?, ?, ?, 'A', 'Examen foeto-placentaire',
                                'DIA', 'AUTONOMOUS')""",
                        (medicare["id"], ey, em, ed),
                    )

        # ── bam_antenatal (upsert 1:1) ──
        _ant_fields = {
            "antenatal_amp": "amp",
            "antenatal_term": "term",
            "antenatal_height": "height",
            "antenatal_weight": "weight",
            "antenatal_hc": "head_circumference",
        }
        ant_vals = {}
        for src, col in _ant_fields.items():
            if src in data:
                v = data[src]
                if col == "amp":
                    ant_vals[col] = 1 if v else 0
                else:
                    ant_vals[col] = _int_or_none(v) if col in ("term", "weight") else _float_or_none(v)
        if ant_vals:
            existing = conn.execute(
                "SELECT id FROM bam_antenatal WHERE identity_id = ?", (case_id,)
            ).fetchone()
            if existing:
                sets = ", ".join(f"{k} = ?" for k in ant_vals)
                conn.execute(
                    f"UPDATE bam_antenatal SET {sets} WHERE identity_id = ?",
                    list(ant_vals.values()) + [case_id],
                )
            else:
                ant_vals["identity_id"] = case_id
                cols = ", ".join(ant_vals.keys())
                phs = ", ".join("?" * len(ant_vals))
                conn.execute(
                    f"INSERT INTO bam_antenatal ({cols}) VALUES ({phs})",
                    list(ant_vals.values()),
                )

        # ── bam_propositus (upsert 1:1) ──
        _prop_fields = {
            "propositus_ipp": "propositus_ipp",
            "propositus_ins": "propositus_ins",
            "propositus_relation": "relation",
        }
        prop_vals = {}
        for src, col in _prop_fields.items():
            if src in data:
                prop_vals[col] = (data[src] or "").strip() or None
        if prop_vals:
            if "relation" in prop_vals and not prop_vals["relation"]:
                prop_vals["relation"] = "INCONNU"
            existing = conn.execute(
                "SELECT id FROM bam_propositus WHERE identity_id = ?", (case_id,)
            ).fetchone()
            if existing:
                sets = ", ".join(f"{k} = ?" for k in prop_vals)
                conn.execute(
                    f"UPDATE bam_propositus SET {sets} WHERE identity_id = ?",
                    list(prop_vals.values()) + [case_id],
                )
            else:
                if not prop_vals.get("relation"):
                    prop_vals["relation"] = "INCONNU"
                prop_vals["identity_id"] = case_id
                cols = ", ".join(prop_vals.keys())
                phs = ", ".join("?" * len(prop_vals))
                conn.execute(
                    f"INSERT INTO bam_propositus ({cols}) VALUES ({phs})",
                    list(prop_vals.values()),
                )

        # ── bam_research (upsert) ──
        _res_fields = {
            "research_contact": "contact_allowed",
            "sample_research": "sample_research",
            "sample_diagnostic": "sample_diagnostic",
            "research_biobank": "biobank",
        }
        res_vals = {}
        for src, col in _res_fields.items():
            if src in data:
                v = data[src]
                if col == "biobank":
                    res_vals[col] = (v or "").strip() or None
                else:
                    res_vals[col] = 1 if v else 0
        if res_vals:
            existing = conn.execute(
                "SELECT id FROM bam_research WHERE identity_id = ?", (case_id,)
            ).fetchone()
            if existing:
                sets = ", ".join(f"{k} = ?" for k in res_vals)
                conn.execute(
                    f"UPDATE bam_research SET {sets} WHERE identity_id = ?",
                    list(res_vals.values()) + [case_id],
                )
            else:
                res_vals["identity_id"] = case_id
                cols = ", ".join(res_vals.keys())
                phs = ", ".join("?" * len(res_vals))
                conn.execute(
                    f"INSERT INTO bam_research ({cols}) VALUES ({phs})",
                    list(res_vals.values()),
                )

        return True


def get_case(case_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            _CASE_SELECT + " WHERE i.id = ?", (case_id,)
        ).fetchone()
        return _row_to_case(row) if row else None


def get_case_by_numero(numero: str) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            _CASE_SELECT + " WHERE hc.hub_case_number = ?", (numero,)
        ).fetchone()
        return _row_to_case(row) if row else None


def list_cases(statut: str = None, search: str = None) -> list[dict]:
    with _mgr.connect() as conn:
        query = _CASE_SELECT
        params = []
        clauses = ["(hc.case_type != 'DECES_PEDIATRIQUE' OR hc.case_type IS NULL)"]

        if statut:
            hub_status = _map_status_to_hub(statut)
            clauses.append("hc.status = ?")
            params.append(hub_status)
        if search:
            clauses.append(
                "(hc.hub_case_number LIKE ? OR i.mother_name LIKE ? "
                "OR hc.case_id_externe LIKE ? OR hc.indication_examen LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])

        query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY i.updated_at DESC"

        return [_row_to_case(r) for r in conn.execute(query, params).fetchall()]


def delete_case(case_id: int) -> bool:
    with _mgr.connect() as conn:
        cur = conn.execute("DELETE FROM bam_identity WHERE id = ?", (case_id,))
        return cur.rowcount > 0


# ── Module Data ──────────────────────────────────────────────────────────

def save_module_data(case_id: int, module_name: str, data: dict) -> bool:
    now = _now()
    with _mgr.connect() as conn:
        # Inject case_uuid in module header
        row = conn.execute("SELECT case_uuid FROM bam_identity WHERE id=?", (case_id,)).fetchone()
        if row and row[0] and isinstance(data, dict):
            data.setdefault("_case_uuid", row[0])
        json_str = json.dumps(data, ensure_ascii=False)
        conn.execute(
            """INSERT INTO module_data (case_id, module_name, data_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(case_id, module_name)
            DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at""",
            (case_id, module_name, json_str, now),
        )
        conn.execute(
            "UPDATE bam_identity SET updated_at = ? WHERE id = ?", (now, case_id)
        )
        return True


def get_module_data(case_id: int, module_name: str) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT data_json FROM module_data WHERE case_id = ? AND module_name = ?",
            (case_id, module_name),
        ).fetchone()
        if row:
            return json.loads(row["data_json"])
        return None


def get_all_modules(case_id: int) -> dict[str, dict]:
    with _mgr.connect() as conn:
        rows = conn.execute(
            "SELECT module_name, data_json, updated_at FROM module_data WHERE case_id = ?",
            (case_id,),
        ).fetchall()
        return {
            r["module_name"]: {
                "data": json.loads(r["data_json"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        }


# ── Macro Folders ────────────────────────────────────────────────────────

def scan_macro_folders(case_id: int, base_path: str) -> list[dict]:
    base = Path(base_path)
    results = []
    now = _now()
    photo_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

    with _mgr.connect() as conn:
        for ftype in MACRO_FOLDER_TYPES:
            folder = base / ftype
            exists = folder.is_dir()
            photo_count = 0
            if exists:
                for f in folder.iterdir():
                    if f.is_file() and f.suffix.lower() in photo_exts:
                        try:
                            if f.stat().st_size >= 1024:
                                photo_count += 1
                        except OSError:
                            pass

            conn.execute(
                """INSERT INTO macro_folders (case_id, folder_type, folder_path,
                   photo_count, last_scan)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(case_id, folder_type)
                DO UPDATE SET folder_path = excluded.folder_path,
                              photo_count = excluded.photo_count,
                              last_scan = excluded.last_scan""",
                (case_id, ftype, _to_relative_path(str(folder)) if exists else None, photo_count, now),
            )
            results.append({
                "type": ftype,
                "exists": exists,
                "path": str(folder) if exists else None,
                "photo_count": photo_count,
            })
    return results


def get_macro_folders(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM macro_folders WHERE case_id = ? ORDER BY folder_type",
            (case_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = _row_to_dict(r)
            d["folder_path"] = _resolve_path(d.get("folder_path"))
            result.append(d)
        return result


# ── Settings ─────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with _mgr.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with _mgr.connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Foeto Details ────────────────────────────────────────────────────────

FOETO_FIELDS = [
    "modalite",
    "terme_decouverte_sa", "terme_decouverte_jours", "date_decouverte",
    "terme_expulsion_sa", "terme_expulsion_jours", "date_expulsion",
    "derniere_preuve_vie_date", "derniere_preuve_vie_terme_sa",
    "derniere_preuve_vie_terme_jours", "grade_maceration", "mode_expulsion",
    "date_decision_cpdpn", "indication_img", "methode_feticide", "date_feticide",
    "date_naissance", "heure_naissance", "apgar_1", "apgar_5", "apgar_10",
    "age_deces_heures", "cause_deces_principale", "reanimation",
    "date_deces", "age_deces_jours", "lieu_deces", "contexte_deces",
    "mode_accouchement", "autopsie_consentement", "autopsie_type",
    "placenta_examen", "caryotype_demande",
]

_FOETO_INT_FIELDS = {
    "terme_decouverte_sa", "terme_decouverte_jours",
    "terme_expulsion_sa", "terme_expulsion_jours",
    "derniere_preuve_vie_terme_sa", "derniere_preuve_vie_terme_jours",
    "grade_maceration", "apgar_1", "apgar_5", "apgar_10", "age_deces_jours",
}
_FOETO_FLOAT_FIELDS = {"age_deces_heures"}
_FOETO_BOOL_FIELDS = {
    "reanimation", "autopsie_consentement", "placenta_examen", "caryotype_demande",
}


def get_foeto_details(case_id: int) -> dict | None:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM hub_foeto_details WHERE identity_id = ?", (case_id,)
        ).fetchone()
        return dict(row) if row else None


def save_foeto_details(case_id: int, data: dict):
    now = _now()
    values = {}
    for f in FOETO_FIELDS:
        v = data.get(f)
        if v is None or v == "":
            values[f] = None
        elif f in _FOETO_INT_FIELDS:
            values[f] = _int_or_none(v)
        elif f in _FOETO_FLOAT_FIELDS:
            try:
                values[f] = float(v)
            except (TypeError, ValueError):
                values[f] = None
        elif f in _FOETO_BOOL_FIELDS:
            values[f] = 1 if v and v not in ("0", "false", "off") else 0
        else:
            values[f] = str(v).strip() if v else None

    with _mgr.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM hub_foeto_details WHERE identity_id = ?", (case_id,)
        ).fetchone()
        if existing:
            values["updated_at"] = now
            sets = ", ".join(f"{k} = ?" for k in values)
            conn.execute(
                f"UPDATE hub_foeto_details SET {sets} WHERE identity_id = ?",
                list(values.values()) + [case_id],
            )
        else:
            values["identity_id"] = case_id
            values["created_at"] = now
            values["updated_at"] = now
            cols = ", ".join(values.keys())
            placeholders = ", ".join(["?"] * len(values))
            conn.execute(
                f"INSERT INTO hub_foeto_details ({cols}) VALUES ({placeholders})",
                list(values.values()),
            )

        _sync_foeto_to_bamara(case_id, values, conn)


def _sync_foeto_to_bamara(case_id: int, foeto: dict, conn):
    modalite = foeto.get("modalite")
    if not modalite:
        return

    if modalite in ("IMG", "MFIU"):
        termination_type = "IMG" if modalite == "IMG" else "ISG"
        date_exp = foeto.get("date_expulsion")
        y, m, d = _parse_date(date_exp) if date_exp else (None, None, None)
        terme = foeto.get("terme_expulsion_sa")

        existing = conn.execute(
            "SELECT id FROM bam_pregnancy_end WHERE identity_id = ?", (case_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE bam_pregnancy_end SET birth = 0, termination_type = ?,
                   stp_type = 'INUTERO', term_week = ?,
                   death_date_year = ?, death_date_month = ?, death_date_day = ?
                WHERE identity_id = ?""",
                (termination_type, terme, y, m, d, case_id),
            )
        else:
            conn.execute(
                """INSERT INTO bam_pregnancy_end (identity_id, birth, termination_type,
                   stp_type, term_week, death_date_year, death_date_month,
                   death_date_day, is_foetopathology_done)
                VALUES (?, 0, ?, 'INUTERO', ?, ?, ?, ?, 1)""",
                (case_id, termination_type, terme, y, m, d),
            )

    elif modalite in ("DECES_NEONATAL", "DECES_PEDIATRIQUE"):
        existing = conn.execute(
            "SELECT id FROM bam_pregnancy_end WHERE identity_id = ?", (case_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE bam_pregnancy_end SET birth = 1, termination_type = NULL,
                   stp_type = NULL WHERE identity_id = ?""",
                (case_id,),
            )
        else:
            conn.execute(
                """INSERT INTO bam_pregnancy_end (identity_id, birth,
                   is_foetopathology_done) VALUES (?, 1, 1)""",
                (case_id,),
            )
        conn.execute(
            "UPDATE bam_identity SET deceased = 1 WHERE id = ?", (case_id,)
        )


# ── Pediatric Details ──────────────────────────────────────────────────────

PEDIATRIC_FIELDS = [
    "date_naissance", "heure_naissance",
    "terme_naissance_sa", "terme_naissance_jours",
    "mode_accouchement",
    "poids_naissance_g", "taille_naissance_cm", "pc_naissance_mm",
    "apgar_1", "apgar_5", "apgar_10",
    "date_deces", "heure_deces", "age_deces_jours",
    "lieu_deces", "cause_deces_principale", "contexte_deces",
    "reanimation",
    "poids_deces_g", "taille_deces_cm", "pc_deces_mm",
    "autopsie_consentement", "autopsie_type",
]
_PED_INT_FIELDS = {"terme_naissance_sa", "terme_naissance_jours", "apgar_1", "apgar_5", "apgar_10", "age_deces_jours"}
_PED_FLOAT_FIELDS = {"poids_naissance_g", "taille_naissance_cm", "pc_naissance_mm", "poids_deces_g", "taille_deces_cm", "pc_deces_mm"}
_PED_BOOL_FIELDS = {"reanimation", "autopsie_consentement"}


def get_pediatric_details(case_id: int) -> dict | None:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM hub_pediatric_details WHERE identity_id = ?", (case_id,)
        ).fetchone()
        return dict(row) if row else None


def save_pediatric_details(case_id: int, data: dict):
    now = _now()
    values = {}
    for f in PEDIATRIC_FIELDS:
        v = data.get(f)
        if v is None or v == "":
            values[f] = None
        elif f in _PED_INT_FIELDS:
            values[f] = _int_or_none(v)
        elif f in _PED_FLOAT_FIELDS:
            values[f] = _float_or_none(v)
        elif f in _PED_BOOL_FIELDS:
            values[f] = 1 if v and v not in ("0", "false", "off") else 0
        else:
            values[f] = str(v).strip() if v else None

    with _mgr.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM hub_pediatric_details WHERE identity_id = ?", (case_id,)
        ).fetchone()
        if existing:
            values["updated_at"] = now
            sets = ", ".join(f"{k} = ?" for k in values)
            conn.execute(
                f"UPDATE hub_pediatric_details SET {sets} WHERE identity_id = ?",
                list(values.values()) + [case_id],
            )
        else:
            values["identity_id"] = case_id
            values["created_at"] = now
            values["updated_at"] = now
            cols = ", ".join(values.keys())
            placeholders = ", ".join(["?"] * len(values))
            conn.execute(
                f"INSERT INTO hub_pediatric_details ({cols}) VALUES ({placeholders})",
                list(values.values()),
            )

        _sync_foeto_to_bamara(case_id, {"modalite": "DECES_PEDIATRIQUE"}, conn)


def list_pediatric_cases(statut: str = None, search: str = None) -> list[dict]:
    with _mgr.connect() as conn:
        query = _CASE_SELECT
        params = []
        clauses = ["hc.case_type = 'DECES_PEDIATRIQUE'"]

        if statut:
            hub_status = _map_status_to_hub(statut)
            clauses.append("hc.status = ?")
            params.append(hub_status)
        if search:
            clauses.append(
                "(hc.hub_case_number LIKE ? OR i.mother_name LIKE ? "
                "OR hc.case_id_externe LIKE ? OR hc.indication_examen LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])

        query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY i.updated_at DESC"

        return [_row_to_case(r) for r in conn.execute(query, params).fetchall()]


# ── HPO (via bam_clinical_description) ───────────────────────────────────

def _get_condition_id(case_id: int, conn=None) -> int | None:
    def _query(c):
        row = c.execute(
            "SELECT id FROM bam_condition WHERE identity_id = ? ORDER BY id LIMIT 1",
            (case_id,),
        ).fetchone()
        return row["id"] if row else None
    if conn:
        return _query(conn)
    with _mgr.connect() as conn:
        return _query(conn)


def get_hpo_terms(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return []
        rows = conn.execute(
            """SELECT id, code AS hpo_code, label AS hpo_label, ref AS source
            FROM bam_clinical_description
            WHERE condition_id = ? ORDER BY code""",
            (condition_id,),
        ).fetchall()
        return [dict(r) | {"validated": 1, "case_id": case_id} for r in rows]


def add_hpo_term(case_id: int, hpo_code: str, hpo_label: str, source: str = "rule"):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        existing = conn.execute(
            "SELECT id FROM bam_clinical_description WHERE condition_id = ? AND code = ?",
            (condition_id, hpo_code),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE bam_clinical_description SET label = ? WHERE id = ?",
                (hpo_label, existing["id"]),
            )
        else:
            ref = "HPO"
            if hpo_code.startswith("ORPHA:"):
                ref = "ORPHA"
            elif hpo_code.startswith("ICD") or "." in hpo_code:
                ref = "CIM10"
            conn.execute(
                """INSERT INTO bam_clinical_description (condition_id, code, label, ref)
                VALUES (?, ?, ?, ?)""",
                (condition_id, hpo_code, hpo_label, ref),
            )


def remove_hpo_term(case_id: int, hpo_code: str):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        conn.execute(
            "DELETE FROM bam_clinical_description WHERE condition_id = ? AND code = ?",
            (condition_id, hpo_code),
        )


# ── Genes (bam_gene, N:1 → condition) ─────────────────────────────────

def get_genes(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return []
        rows = conn.execute(
            "SELECT id, code, label FROM bam_gene WHERE condition_id = ? ORDER BY code",
            (condition_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_gene(case_id: int, code: str, label: str):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        existing = conn.execute(
            "SELECT id FROM bam_gene WHERE condition_id = ? AND code = ?",
            (condition_id, code),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE bam_gene SET label = ? WHERE id = ?",
                (label, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO bam_gene (condition_id, code, label) VALUES (?, ?, ?)",
                (condition_id, code, label),
            )


def remove_gene(case_id: int, code: str):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        conn.execute(
            "DELETE FROM bam_gene WHERE condition_id = ? AND code = ?",
            (condition_id, code),
        )


# ── Biologic Methods (bam_biologic_method, N:1 → condition) ───────────

def get_biologic_methods(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return []
        rows = conn.execute(
            "SELECT id, code, label FROM bam_biologic_method WHERE condition_id = ? ORDER BY code",
            (condition_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_biologic_method(case_id: int, code: str, label: str):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        existing = conn.execute(
            "SELECT id FROM bam_biologic_method WHERE condition_id = ? AND code = ?",
            (condition_id, code),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE bam_biologic_method SET label = ? WHERE id = ?",
                (label, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO bam_biologic_method (condition_id, code, label) VALUES (?, ?, ?)",
                (condition_id, code, label),
            )


def remove_biologic_method(case_id: int, code: str):
    with _mgr.connect() as conn:
        condition_id = _get_condition_id(case_id, conn)
        if not condition_id:
            return
        conn.execute(
            "DELETE FROM bam_biologic_method WHERE condition_id = ? AND code = ?",
            (condition_id, code),
        )


# ── BaMaRa Export Data ───────────────────────────────────────────────────

def get_bamara_export_data(case_id: int) -> dict | None:
    with _mgr.connect() as conn:
        identity = conn.execute(
            "SELECT * FROM bam_identity WHERE id = ?", (case_id,)
        ).fetchone()
        if not identity:
            return None

        hub = conn.execute(
            "SELECT * FROM hub_case WHERE identity_id = ?", (case_id,)
        ).fetchone()
        medicare = conn.execute(
            "SELECT * FROM bam_medicare WHERE identity_id = ?", (case_id,)
        ).fetchone()
        encounter = None
        if medicare:
            encounter = conn.execute(
                "SELECT * FROM bam_encounter WHERE medicare_id = ?",
                (medicare["id"],),
            ).fetchone()
        condition = conn.execute(
            "SELECT * FROM bam_condition WHERE identity_id = ? ORDER BY id LIMIT 1",
            (case_id,),
        ).fetchone()
        hpo_terms = []
        genes = []
        biologic_methods = []
        if condition:
            hpo_terms = conn.execute(
                "SELECT code, label, ref FROM bam_clinical_description WHERE condition_id = ?",
                (condition["id"],),
            ).fetchall()
            genes = conn.execute(
                "SELECT code, label FROM bam_gene WHERE condition_id = ?",
                (condition["id"],),
            ).fetchall()
            biologic_methods = conn.execute(
                "SELECT code, label FROM bam_biologic_method WHERE condition_id = ?",
                (condition["id"],),
            ).fetchall()
        pregnancy_end = conn.execute(
            "SELECT * FROM bam_pregnancy_end WHERE identity_id = ?", (case_id,)
        ).fetchone()
        antenatal = conn.execute(
            "SELECT * FROM bam_antenatal WHERE identity_id = ?", (case_id,)
        ).fetchone()
        propositus = conn.execute(
            "SELECT * FROM bam_propositus WHERE identity_id = ?", (case_id,)
        ).fetchone()
        research = conn.execute(
            "SELECT * FROM bam_research WHERE identity_id = ?", (case_id,)
        ).fetchone()
        foeto = conn.execute(
            "SELECT * FROM hub_foeto_details WHERE identity_id = ?", (case_id,)
        ).fetchone()

        def _d(row):
            return dict(row) if row else {}

        return {
            "identity": _d(identity),
            "hub_case": _d(hub),
            "medicare": _d(medicare),
            "encounter": _d(encounter),
            "condition": _d(condition),
            "hpo_terms": [dict(r) for r in hpo_terms],
            "genes": [dict(r) for r in genes],
            "biologic_methods": [dict(r) for r in biologic_methods],
            "pregnancy_end": _d(pregnancy_end),
            "antenatal": _d(antenatal),
            "propositus": _d(propositus),
            "research": _d(research),
            "foeto_details": _d(foeto),
        }


# ── Import JSON ──────────────────────────────────────────────────────────

def import_case_from_json(json_path: str | Path) -> Optional[int]:
    path = Path(json_path)
    if not path.is_file():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    admin = data.get("case_admin", data)
    numero = admin.get("numero_dossier")
    if not numero:
        return None

    existing = get_case_by_numero(numero)
    if existing:
        case_id = existing["id"]
        update_case(case_id, admin)
    else:
        case_id = create_case(admin)

    for key in ["atcd_maternels", "grossesse_en_cours", "examens_prenataux", "atcd_obstetricaux"]:
        if key in data:
            save_module_data(case_id, key, data[key])

    return case_id


# ── CR Templates CRUD ──────────────────────────────────────────────────

def list_cr_templates() -> list[dict]:
    """Liste tous les templates CR utilisateur (DB)."""
    with _mgr.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM templates ORDER BY is_default DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_cr_template(template_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None


def create_cr_template(name: str, ttype: str, content: str,
                       is_default: int = 0) -> int:
    with _mgr.connect() as conn:
        cur = conn.execute(
            "INSERT INTO templates (name, type, content_jinja2, is_default) "
            "VALUES (?, ?, ?, ?)",
            (name, ttype, content, is_default),
        )
        return cur.lastrowid


def update_cr_template(template_id: int, name: str, ttype: str,
                       content: str):
    with _mgr.connect() as conn:
        conn.execute(
            "UPDATE templates SET name=?, type=?, content_jinja2=?, "
            "updated_at=? WHERE id=?",
            (name, ttype, content, _now(), template_id),
        )


def delete_cr_template(template_id: int):
    with _mgr.connect() as conn:
        conn.execute(
            "DELETE FROM generated_docs WHERE template_id = ?",
            (template_id,),
        )
        conn.execute(
            "DELETE FROM templates WHERE id = ? AND is_default = 0",
            (template_id,),
        )


def duplicate_cr_template(template_id: int) -> int | None:
    tpl = get_cr_template(template_id)
    if not tpl:
        return None
    return create_cr_template(
        tpl["name"] + " (copie)", tpl["type"], tpl["content_jinja2"]
    )


# ── Generated Docs CRUD ───────────────────────────────────────────────

def save_generated_doc(case_id: int, template_id,
                       html: str, text: str) -> int:
    with _mgr.connect() as conn:
        identity_row = conn.execute(
            "SELECT identity_id FROM hub_case WHERE id = ?", (case_id,)
        ).fetchone()
        if not identity_row:
            # Fallback : case_id est directement identity_id
            identity_id = case_id
        else:
            identity_id = identity_row["identity_id"]
        cur = conn.execute(
            "INSERT INTO generated_docs "
            "(identity_id, template_id, content_html, content_text) "
            "VALUES (?, ?, ?, ?)",
            (identity_id, template_id, html, text),
        )
        return cur.lastrowid


def list_generated_docs(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        rows = conn.execute("""
            SELECT id, template_id, content_html, content_text, generated_at
            FROM generated_docs
            WHERE identity_id = ?
            ORDER BY generated_at DESC
        """, (case_id,)).fetchall()
        return [dict(r) for r in rows]


def get_generated_doc(doc_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM generated_docs WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_generated_doc(doc_id: int):
    with _mgr.connect() as conn:
        conn.execute(
            "DELETE FROM generated_docs WHERE id = ?", (doc_id,)
        )
