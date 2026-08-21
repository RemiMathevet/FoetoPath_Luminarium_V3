-- ============================================================================
-- bamara_schema.sql — Schéma BaMaRa-natif pour le Hub FoetoPath
-- Compatible SQLite, basé sur SDM-MR v2.17
-- Étendu avec les champs locaux du hub (workflow, chemins, actes)
-- ============================================================================

-- ── bam_identity : Identité patient/fœtus ──────────────────────────────────

CREATE TABLE IF NOT EXISTS bam_identity (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    case_uuid               TEXT UNIQUE,
    bamara_id               INTEGER,
    bamara_idmr             TEXT,
    medical_file_id         INTEGER,

    -- SDM item 1 : Consentement
    opposition              BOOLEAN DEFAULT FALSE,
    authorization_ern       TEXT,

    -- SDM item 2 : Identification
    ins                     TEXT,
    ipp                     TEXT,
    ipp_fetus               TEXT,

    -- SDM item 3 : Informations personnelles (patient né)
    family_name_birth       TEXT,
    family_name_used        TEXT,
    given_name_birth        TEXT,
    given_names             TEXT,
    given_name_used         TEXT,
    birth_date_year         INTEGER,
    birth_date_month        INTEGER,
    birth_date_day          INTEGER,
    birth_date_mask         INTEGER DEFAULT 0,
    gender                  TEXT NOT NULL,
    birth_country           TEXT,
    birth_commune_code      TEXT,

    -- SDM item 3.15 : Adresse de résidence
    residence_house_number  TEXT,
    residence_street_name   TEXT,
    residence_city          TEXT,
    residence_commune_code  TEXT,
    residence_country_name  TEXT,
    residence_country_code  TEXT NOT NULL DEFAULT 'FR',
    residence_address_id    INTEGER,
    residence_address_label TEXT,
    residence_postal_id     INTEGER,

    -- SDM item 5 : Statut vital
    deceased                BOOLEAN,
    death_date_year         INTEGER,
    death_date_month        INTEGER,
    death_date_day          INTEGER,
    death_date_mask         INTEGER DEFAULT 0,
    due_to_rd               TEXT,
    orpha_code_cause        TEXT,

    -- SDM item 17 : Informations complémentaires
    inbreeding              TEXT,
    out_of_sight            BOOLEAN,

    -- Données fœtus (foetusAdmData)
    is_fetus                BOOLEAN DEFAULT FALSE,
    mother_name             TEXT,
    mother_used_name        TEXT,
    mother_given_name       TEXT,
    mother_family_name_birth TEXT,
    pregnancy_date_year     INTEGER,
    pregnancy_date_month    INTEGER,
    pregnancy_date_day      INTEGER,
    pregnancy_date_mask     INTEGER DEFAULT 0,
    is_multiple_pregnancy   BOOLEAN DEFAULT FALSE,
    has_given_consent       BOOLEAN DEFAULT TRUE,

    -- SDM item 16 : Mère de l'enfant
    mother_given_name_birth  TEXT,

    -- SDM item 15 : Médecin traitant
    medecin_traitant_rpps       TEXT,
    medecin_traitant_name       TEXT,
    medecin_traitant_given_name TEXT,

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (gender IN ('M', 'F', 'UNK')),
    CHECK (inbreeding IN ('true', 'false', 'UNK') OR inbreeding IS NULL),
    CHECK (length(ins) = 13 OR ins IS NULL),
    CHECK (length(medecin_traitant_rpps) = 11 OR medecin_traitant_rpps IS NULL)
);

-- ── bam_medicare : Prise en charge MR ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS bam_medicare (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    bamara_id               INTEGER,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,

    pec_uuid                TEXT,
    fetus_id                TEXT,
    sent_by                 TEXT,

    inclusion_date_year     INTEGER NOT NULL,
    inclusion_date_month    INTEGER,
    inclusion_date_day      INTEGER,
    inclusion_date_mask     INTEGER DEFAULT 0,

    care_provider_rpps      TEXT,
    care_provider_name      TEXT,
    care_provider_given_name TEXT,

    site_code               TEXT NOT NULL,
    site_label              TEXT,
    site_id                 INTEGER,

    is_label                BOOLEAN DEFAULT TRUE,
    source_id               TEXT DEFAULT 'AUTONOMOUS',

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_encounter : Activité MR ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bam_encounter (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    bamara_id               INTEGER,
    medicare_id             INTEGER NOT NULL REFERENCES bam_medicare(id) ON DELETE CASCADE,

    encounter_uuid          TEXT,
    fetus_id                TEXT,

    encounter_date_year     INTEGER,
    encounter_date_month    INTEGER,
    encounter_date_day      INTEGER,
    encounter_date_mask     INTEGER DEFAULT 0,

    context                 TEXT NOT NULL,
    context_precision       TEXT,
    objectives              TEXT NOT NULL,

    participant_name        TEXT,
    participant_given_name  TEXT,
    participant_rpps        TEXT,
    participant_profession  TEXT,

    location_at_hospital    BOOLEAN DEFAULT TRUE,
    location_finess         TEXT,
    location_city_code      TEXT,
    location_country_code   TEXT,

    source_id               TEXT DEFAULT 'AUTONOMOUS',

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_condition : Diagnostic ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bam_condition (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    bamara_id               INTEGER,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,

    condition_uuid          TEXT,
    fetus_id                TEXT,
    comment                 TEXT,
    site_diag_code          TEXT,
    site_diag_label         TEXT,
    site_diag_id            INTEGER,

    -- SDM item 8 : Histoire de la maladie
    onset_first_signs       TEXT,
    onset_first_signs_age   INTEGER,
    early_diagnosis_status  TEXT,
    onset_diagnosis         TEXT,
    onset_diagnosis_age     INTEGER,
    onset_genetic           TEXT,
    onset_genetic_age       INTEGER,

    -- SDM item 9 : Diagnostic
    diagnostic_status       TEXT NOT NULL,
    genetic_characterization TEXT,
    description_code        TEXT,
    description_label       TEXT,
    is_complex_non_rare     BOOLEAN DEFAULT FALSE,
    complex_code            TEXT,
    complex_label           TEXT,
    heredity                TEXT,
    newborn_screening       TEXT,

    -- SDM item 10 : Confirmation
    mutation                TEXT,

    source_id               TEXT DEFAULT 'AUTONOMOUS',

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (diagnostic_status IN ('ONG', 'CON', 'INF', 'REF', 'ANP')),
    CHECK (heredity IN ('SPO', 'AD', 'AR', 'XLR', 'XLD', 'MI', 'INC') OR heredity IS NULL)
);

-- ── bam_clinical_description : HPO / CIM-10 / Orpha (N:1 → condition) ─────

CREATE TABLE IF NOT EXISTS bam_clinical_description (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id            INTEGER NOT NULL REFERENCES bam_condition(id) ON DELETE CASCADE,
    code                    TEXT NOT NULL,
    label                   TEXT NOT NULL,
    ref                     TEXT NOT NULL,
    CHECK (ref IN ('HPO', 'CIM10', 'ORPHA'))
);

-- ── bam_gene : Gènes HGNC (N:1 → condition) ──────────────────────────────

CREATE TABLE IF NOT EXISTS bam_gene (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id            INTEGER NOT NULL REFERENCES bam_condition(id) ON DELETE CASCADE,
    code                    TEXT NOT NULL,
    label                   TEXT NOT NULL
);

-- ── bam_biologic_method : Techniques diagnostiques (N:1 → condition) ──────

CREATE TABLE IF NOT EXISTS bam_biologic_method (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id            INTEGER NOT NULL REFERENCES bam_condition(id) ON DELETE CASCADE,
    code                    TEXT NOT NULL,
    label                   TEXT NOT NULL
);

-- ── bam_pregnancy_end : Fin de grossesse (1:1 → identity fœtus) ──────────

CREATE TABLE IF NOT EXISTS bam_pregnancy_end (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,

    birth                   BOOLEAN NOT NULL,
    termination_type        TEXT,
    stp_type                TEXT,
    death_date_year         INTEGER,
    death_date_month        INTEGER,
    death_date_day          INTEGER,
    death_date_mask         INTEGER DEFAULT 0,
    term_week               INTEGER,
    is_foetopathology_done  BOOLEAN,

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (termination_type IN ('IMG', 'ISG') OR termination_type IS NULL),
    CHECK (stp_type IN ('INUTERO', 'PERPARTUM') OR stp_type IS NULL),
    CHECK (term_week BETWEEN 4 AND 45 OR term_week IS NULL)
);

-- ── bam_antenatal : Données anté/néonatales (1:1 → identity) ─────────────

CREATE TABLE IF NOT EXISTS bam_antenatal (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,

    amp                     BOOLEAN,
    term                    INTEGER,
    height                  REAL,
    weight                  INTEGER,
    head_circumference      REAL,

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (term BETWEEN 4 AND 45 OR term IS NULL),
    CHECK (height BETWEEN 2.0 AND 60.0 OR height IS NULL),
    CHECK (weight BETWEEN 0 AND 8000 OR weight IS NULL),
    CHECK (head_circumference BETWEEN 5.0 AND 50.0 OR head_circumference IS NULL)
);

-- ── bam_research : Recherche (N:1 → identity) ────────────────────────────

CREATE TABLE IF NOT EXISTS bam_research (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    fetus_id                TEXT,
    contact_allowed         BOOLEAN,
    sample_research         BOOLEAN,
    sample_diagnostic       BOOLEAN,
    biobank                 TEXT,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_propositus : Premier cas diagnostiqué famille (1:1 → identity) ───

CREATE TABLE IF NOT EXISTS bam_propositus (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,
    propositus_ipp          TEXT,
    propositus_ins          TEXT,
    relation                TEXT NOT NULL,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_icf : Scores CIF (N:1 → identity) ────────────────────────────────

CREATE TABLE IF NOT EXISTS bam_icf (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    icf_uuid                TEXT,
    value                   TEXT NOT NULL,
    label                   TEXT,
    score_date_year         INTEGER,
    score_date_month        INTEGER,
    score_date_day          INTEGER,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_pregnancy_history : Historique grossesses (N:1 → identity mère) ──

CREATE TABLE IF NOT EXISTS bam_pregnancy_history (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    start_date_year         INTEGER NOT NULL,
    start_date_month        INTEGER,
    start_date_day          INTEGER,
    start_date_mask         INTEGER DEFAULT 0,
    end_date_year           INTEGER,
    end_date_month          INTEGER,
    end_date_day            INTEGER,
    end_date_mask           INTEGER DEFAULT 0,
    nb_fetus                INTEGER NOT NULL DEFAULT 1,
    amp                     BOOLEAN,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── bam_fetus : Fœtus dans une grossesse (N:1 → pregnancy_history) ──────

CREATE TABLE IF NOT EXISTS bam_fetus (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    pregnancy_history_id    INTEGER NOT NULL REFERENCES bam_pregnancy_history(id) ON DELETE CASCADE,
    multiple_preg_order     INTEGER NOT NULL DEFAULT 1,
    fetus_local_id          TEXT NOT NULL,
    given_name              TEXT,
    gender                  TEXT NOT NULL,
    is_multiple_pregnancy   BOOLEAN DEFAULT FALSE,
    pregnancy_outcome       TEXT,
    gestational_age         INTEGER,
    foetopathology          BOOLEAN,
    death_date_year         INTEGER,
    death_date_month        INTEGER,
    death_date_day          INTEGER,
    death_date_mask         INTEGER DEFAULT 0,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (gender IN ('M', 'F', 'UNK')),
    CHECK (gestational_age BETWEEN 4 AND 45 OR gestational_age IS NULL)
);

-- ══════════════════════════════════════════════════════════════════════════
-- Tables Hub locales — workflow, paths, actes, export
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS hub_case (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,

    hub_case_number         TEXT,
    case_id_externe         TEXT,
    case_type               TEXT,
    created_by              TEXT,
    assigned_to             TEXT,
    modified_by             TEXT,
    status                  TEXT DEFAULT 'DRAFT',
    notes                   TEXT,

    -- Champs locaux foetopathologie (pas dans BaMaRa)
    type_prelevement        TEXT,
    indication_examen       TEXT,
    contexte_clinique       TEXT,
    service_demandeur       TEXT,
    ddn_mere                TEXT,
    terme_jours             INTEGER,
    ville_maternite         TEXT,

    -- Workflow / actes
    acte_clinique           INTEGER DEFAULT 0,
    acte_imagerie           INTEGER DEFAULT 0,
    acte_anapath            INTEGER DEFAULT 0,
    acte_interne            INTEGER DEFAULT 0,
    acte_virtopsie          INTEGER DEFAULT 0,
    numero_placenta         TEXT,
    examen_placenta         INTEGER DEFAULT 0,

    -- Chemins fichiers
    dossier_macro_path      TEXT,
    dossier_lames_path      TEXT,

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (case_type IN ('MFIU', 'IMG', 'DECES_NEONATAL', 'DECES_PEDIATRIQUE',
                         'FCS', 'NAISSANCE', 'MPN', 'AUTRE') OR case_type IS NULL),
    CHECK (status IN ('DRAFT', 'READY', 'VALIDATED', 'SENT', 'ERROR', 'CONFIRMED'))
);

CREATE TABLE IF NOT EXISTS hub_bamara_export (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    export_status           TEXT NOT NULL DEFAULT 'PENDING',
    last_attempt_at         DATETIME,
    last_success_at         DATETIME,
    attempt_count           INTEGER DEFAULT 0,
    last_step_completed     INTEGER DEFAULT 0,
    bamara_identity_id      INTEGER,
    bamara_idmr             TEXT,
    bamara_medical_file_id  INTEGER,
    last_error_step         INTEGER,
    last_error_message      TEXT,
    last_error_code         TEXT,
    error_details           TEXT,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (export_status IN ('PENDING', 'IN_PROGRESS', 'SUCCESS', 'PARTIAL', 'ERROR', 'RETRY'))
);

CREATE TABLE IF NOT EXISTS hub_site_config (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    site_code               TEXT NOT NULL UNIQUE,
    hospital_code           TEXT NOT NULL,
    site_label              TEXT NOT NULL,
    site_bamara_id          INTEGER,
    is_default              BOOLEAN DEFAULT FALSE,
    bamara_email            TEXT,
    bamara_password_hash    TEXT,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hub_foeto_details (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id                 INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,

    modalite                    TEXT,

    -- MFIU
    terme_decouverte_sa         INTEGER,
    terme_decouverte_jours      INTEGER,
    date_decouverte             TEXT,
    terme_expulsion_sa          INTEGER,
    terme_expulsion_jours       INTEGER,
    date_expulsion              TEXT,
    derniere_preuve_vie_date    TEXT,
    derniere_preuve_vie_terme_sa INTEGER,
    derniere_preuve_vie_terme_jours INTEGER,
    grade_maceration            INTEGER,
    mode_expulsion              TEXT,

    -- IMG
    date_decision_cpdpn         TEXT,
    indication_img              TEXT,
    methode_feticide            TEXT,
    date_feticide               TEXT,

    -- Deces neonatal
    date_naissance              TEXT,
    heure_naissance             TEXT,
    apgar_1                     INTEGER,
    apgar_5                     INTEGER,
    apgar_10                    INTEGER,
    age_deces_heures            REAL,
    cause_deces_principale      TEXT,
    reanimation                 BOOLEAN,

    -- Deces pediatrique
    date_deces                  TEXT,
    age_deces_jours             INTEGER,
    lieu_deces                  TEXT,
    contexte_deces              TEXT,

    -- Commun
    mode_accouchement           TEXT,
    autopsie_consentement       BOOLEAN,
    autopsie_type               TEXT,
    placenta_examen             BOOLEAN,
    caryotype_demande           BOOLEAN,

    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (modalite IN ('IMG', 'MFIU', 'DECES_NEONATAL', 'DECES_PEDIATRIQUE') OR modalite IS NULL),
    CHECK (grade_maceration BETWEEN 0 AND 3 OR grade_maceration IS NULL),
    CHECK (autopsie_type IN ('complete', 'limitee', 'refusee') OR autopsie_type IS NULL)
);

CREATE TABLE IF NOT EXISTS hub_pediatric_details (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id             INTEGER NOT NULL UNIQUE REFERENCES bam_identity(id) ON DELETE CASCADE,

    date_naissance          TEXT,
    heure_naissance         TEXT,
    terme_naissance_sa      INTEGER,
    terme_naissance_jours   INTEGER,
    mode_accouchement       TEXT,
    poids_naissance_g       REAL,
    taille_naissance_cm     REAL,
    pc_naissance_mm         REAL,
    apgar_1                 INTEGER,
    apgar_5                 INTEGER,
    apgar_10                INTEGER,

    date_deces              TEXT,
    age_deces_jours         INTEGER,
    lieu_deces              TEXT,
    cause_deces_principale  TEXT,
    contexte_deces          TEXT,
    reanimation             BOOLEAN,

    poids_deces_g           REAL,
    taille_deces_cm         REAL,
    pc_deces_mm             REAL,

    autopsie_consentement   BOOLEAN,
    autopsie_type           TEXT,

    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CHECK (autopsie_type IN ('complete', 'limitee', 'refusee') OR autopsie_type IS NULL)
);

-- ── Tables workflow local ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS module_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    data_json   TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL,
    UNIQUE(case_id, module_name)
);

CREATE TABLE IF NOT EXISTS macro_folders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    folder_type     TEXT NOT NULL,
    folder_path     TEXT,
    photo_count     INTEGER DEFAULT 0,
    verified        INTEGER DEFAULT 0,
    last_scan       TEXT,
    UNIQUE(case_id, folder_type)
);

CREATE TABLE IF NOT EXISTS biometries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id   INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    type          TEXT NOT NULL,
    data_json     TEXT DEFAULT '{}',
    computed_json TEXT DEFAULT '{}',
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(identity_id, type)
);

CREATE TABLE IF NOT EXISTS descriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    systeme    TEXT NOT NULL,
    data_json  TEXT DEFAULT '{}',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(identity_id, systeme)
);

CREATE TABLE IF NOT EXISTS templates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT UNIQUE NOT NULL,
    type           TEXT NOT NULL,
    content_jinja2 TEXT NOT NULL,
    is_default     INTEGER DEFAULT 0,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_docs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id  INTEGER NOT NULL REFERENCES bam_identity(id) ON DELETE CASCADE,
    template_id  TEXT,
    content_html TEXT,
    content_text TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ══════════════════════════════════════════════════════════════════════════
-- Index
-- ══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_identity_ipp ON bam_identity(ipp);
CREATE INDEX IF NOT EXISTS idx_identity_ins ON bam_identity(ins);
CREATE INDEX IF NOT EXISTS idx_identity_mother ON bam_identity(mother_name, mother_given_name);
CREATE INDEX IF NOT EXISTS idx_identity_bamara ON bam_identity(bamara_id);
CREATE INDEX IF NOT EXISTS idx_medicare_identity ON bam_medicare(identity_id);
CREATE INDEX IF NOT EXISTS idx_encounter_medicare ON bam_encounter(medicare_id);
CREATE INDEX IF NOT EXISTS idx_condition_identity ON bam_condition(identity_id);
CREATE INDEX IF NOT EXISTS idx_clinical_desc_condition ON bam_clinical_description(condition_id);
CREATE INDEX IF NOT EXISTS idx_gene_condition ON bam_gene(condition_id);
CREATE INDEX IF NOT EXISTS idx_pregnancy_end_identity ON bam_pregnancy_end(identity_id);
CREATE INDEX IF NOT EXISTS idx_antenatal_identity ON bam_antenatal(identity_id);
CREATE INDEX IF NOT EXISTS idx_export_status ON hub_bamara_export(export_status);
CREATE INDEX IF NOT EXISTS idx_export_identity ON hub_bamara_export(identity_id);
CREATE INDEX IF NOT EXISTS idx_case_status ON hub_case(status);
CREATE INDEX IF NOT EXISTS idx_case_type ON hub_case(case_type);
CREATE INDEX IF NOT EXISTS idx_case_number ON hub_case(hub_case_number);
CREATE INDEX IF NOT EXISTS idx_module_case ON module_data(case_id, module_name);
CREATE INDEX IF NOT EXISTS idx_macro_case ON macro_folders(case_id);
CREATE INDEX IF NOT EXISTS idx_biometries_identity ON biometries(identity_id);
CREATE INDEX IF NOT EXISTS idx_descriptions_identity ON descriptions(identity_id);
CREATE INDEX IF NOT EXISTS idx_ped_details_identity ON hub_pediatric_details(identity_id);

-- ══════════════════════════════════════════════════════════════════════════
-- Seed : site Besançon par défaut
-- ══════════════════════════════════════════════════════════════════════════

INSERT OR IGNORE INTO hub_site_config (site_code, hospital_code, site_label, site_bamara_id, is_default)
VALUES ('S0034', 'H059', 'ADEST [CST] PIARD', 33, TRUE);
