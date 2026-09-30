"""
FoetoPath — Palette de variables disponibles pour les templates CR.

Deux sources :
  1. TEMPLATE_VARIABLES  — variables « de haut niveau » du contexte CR
     (retournées par build_cr_context dans cr_templates.py)
  2. build_dynamic_palette(case_id) — scanne la DB (table cases + module_data)
     pour exposer TOUS les champs réellement saisis
"""

TEMPLATE_VARIABLES = {
    # ── Identité / Dossier (extraits par build_cr_context) ──
    "Identité / Dossier": [
        ("numero", "Numéro de dossier"),
        ("sexe", "Sexe (M/F/I)"),
        ("type_issue", "Type d'issue (IMG/MFIU/…)"),
        ("indication", "Indication d'examen"),
        ("medecin", "Médecin référent"),
        ("service", "Service demandeur"),
        ("date_examen", "Date d'examen"),
        ("date_deces", "Date de décès"),
        ("date_autopsie_exif", "Date/heure autopsie (EXIF)"),
        ("terme_sa", "Terme (SA)"),
        ("terme_j", "Terme (jours)"),
    ],
    "Identité maternelle": [
        ("nom_mere", "Nom de la mère"),
        ("prenom_mere", "Prénom de la mère"),
        ("ddn_mere", "Date de naissance mère"),
        ("age_mere", "Âge mère à l'accouchement"),
    ],
    # ── Champs case.* (accès direct au dict case) ──
    "Identité fœtus / Case": [
        ("case.nom_foetus", "Nom du fœtus"),
        ("case.prenom_foetus", "Prénom du fœtus"),
        ("case.ddn_foetus", "Date naissance/décès fœtus"),
        ("case.nom_naissance_mere", "Nom de naissance mère"),
        ("case.lieu_residence", "Lieu de résidence"),
        ("case.ville_maternite", "Ville maternité"),
        ("case.numero_placenta", "Numéro placenta"),
        ("case.case_id_externe", "ID externe"),
        ("case.terme_issue", "Terme à l'issue (texte)"),
        ("case.ipp", "IPP mère"),
        ("case.ipp_fetus", "IPP fœtus"),
        ("case.ins", "INS"),
        ("case.consanguinite", "Consanguinité (case)"),
        ("case.grossesse_multiple", "Grossesse multiple"),
        ("case.date_reception", "Date de réception"),
        ("case.contexte_clinique", "Contexte clinique"),
        ("case.notes", "Notes libres"),
    ],
    # ── Module atcd_maternels ──
    "ATCD maternels": [
        ("atcd_mat.profession_mere", "Profession"),
        ("atcd_mat.gestite", "Gestité"),
        ("atcd_mat.parite", "Parité"),
        ("atcd_mat.groupe_sanguin", "Groupe sanguin"),
        ("atcd_mat.rhesus", "Rhésus"),
        ("atcd_mat.fdr_hta", "FDR : HTA"),
        ("atcd_mat.fdr_diabete", "FDR : Diabète"),
        ("atcd_mat.fdr_tabac", "FDR : Tabac"),
        ("atcd_mat.fdr_alcool", "FDR : Alcool"),
        ("atcd_mat.fdr_consanguinite", "FDR : Consanguinité"),
        ("atcd_mat.atcd_medicaux", "Antécédents médicaux"),
        ("atcd_mat.traitements", "Traitements en cours"),
        ("split_fdr().positifs", "FDR positifs (liste)"),
        ("split_fdr().negatifs", "FDR négatifs (liste)"),
    ],
    # ── Module atcd_obstetricaux ──
    "ATCD obstétricaux": [
        ("_table_atcd_obs()", "Tableau ATCD obstétricaux (HTML)"),
    ],
    # ── Module grossesse_en_cours ──
    "Grossesse en cours": [
        ("grossesse.mode_conception", "Mode de conception"),
        ("grossesse.amp_type", "Type AMP"),
        ("grossesse.ddg", "DDG"),
        ("grossesse.risque_t21", "Risque T21"),
        ("grossesse.bhcg", "β-hCG (MoM)"),
        ("grossesse.pappa", "PAPP-A (MoM)"),
        ("grossesse.lcc", "LCC (mm)"),
        ("grossesse.cn", "CN (mm)"),
        ("grossesse.lieu_suivi", "Lieu de suivi"),
        ("grossesse.histoire_clinique", "Histoire clinique"),
    ],
    # ── Module examens_prenataux ──
    "Examens prénataux": [
        ("exam_prenataux.echo_t1_status", "Écho T1 — statut"),
        ("exam_prenataux.echo_t1_details", "Écho T1 — détails"),
        ("exam_prenataux.echo_t2_status", "Écho T2 — statut"),
        ("exam_prenataux.echo_t2_details", "Écho T2 — détails"),
        ("exam_prenataux.echo_t3_status", "Écho T3 — statut"),
        ("exam_prenataux.echo_t3_details", "Écho T3 — détails"),
        ("exam_prenataux.caryotype", "Caryotype"),
        ("exam_prenataux.acpa", "ACPA (CGH-Array)"),
        ("exam_prenataux.ngs", "NGS / Exome"),
        ("exam_prenataux.recherche_aneuploidie", "DPNI / Aneuploïdie"),
        ("exam_prenataux.anomalies_suspectees", "Anomalies suspectées"),
        ("exam_prenataux.anomalies_confirmees", "Anomalies confirmées"),
        ("split_prenatal().normaux", "Examens prénataux normaux (liste)"),
        ("split_prenatal().anormaux", "Examens prénataux anormaux (liste)"),
    ],
    # ── Macro frais ──
    "Macro frais — Aspect": [
        ("etat", "État général (frais/fixé)"),
        ("maceration.maroun_score", "Score macération Maroun"),
        ("table_genest()", "Tableau critères Genest (HTML)"),
        ("genest_retention()", "Estimation rétention (texte)"),
        ("commentaire_frais", "Commentaire examen frais"),
        ("anomalies_frais", "Anomalies frais (liste)"),
    ],
    "Macro frais — Biométries": [
        ("bio.masse", "Poids (g)"),
        ("bio.pied", "Longueur du pied (mm)"),
        ("bio.vt", "Taille vertex-talon (mm)"),
        ("bio.vc", "Taille vertex-coccyx (mm)"),
        ("bio.pc", "Périmètre crânien (mm)"),
        ("bio.bip", "Diamètre bi-pariétal (mm)"),
        ("bio.pt", "Périmètre thoracique (mm)"),
        ("bio.pa", "Périmètre abdominal (mm)"),
        ("bio.dici", "Distance inter-canthi int (mm)"),
        ("bio.dice", "Distance inter-canthi ext (mm)"),
        ("bio.dim", "Distance inter-mamelonnaire (mm)"),
        ("bio.sternum", "Sternum (mm)"),
        ("bio.fo", "Fontanelle occ (mm)"),
        ("bio.fpd", "Fente palpébrale D (mm)"),
        ("bio.fpg", "Fente palpébrale G (mm)"),
        ("bio.main", "Main (mm)"),
    ],
    "Macro frais — Morphologie": [
        ("split_morpho()", "Morpho → {normales, anomalies}"),
        ("split_morpho().normales", "Morpho — éléments normaux (liste)"),
        ("split_morpho().anomalies", "Morpho — anomalies (liste)"),
    ],
    # ── Biométries calculées ──
    "Biométries calculées": [
        ("table_biometries_externes()", "Tableau biométries examen externe (HTML)"),
        ("table_biometries_internes()", "Tableau masses organes examen interne (HTML)"),
        ("_table_biometries()", "Tableau combiné ext + int (HTML)"),
        ("lbwr.valeur", "LBWR — valeur"),
        ("lbwr.alerte", "LBWR — alerte"),
        ("alertes", "Alertes biométriques (liste)"),
        ("trophicite", "Trophicité"),
    ],
    # ── Autopsie — Ouverture ──
    "Autopsie — Ouverture": [
        ("ouverture.situs", "Situs viscéral"),
        ("ouverture.diaphragme", "Coupoles diaphragmatiques"),
        ("ouverture.ogi", "OGI"),
        ("ouverture.ogi_detail", "OGI détail"),
        ("ouverture.epanchements.pleural_d", "Épanchement pleural D (mL)"),
        ("ouverture.epanchements.pleural_g", "Épanchement pleural G (mL)"),
        ("ouverture.epanchements.pericarde", "Épanchement péricardique (mL)"),
        ("ouverture.epanchements.peritoine", "Épanchement péritonéal (mL)"),
    ],
    "Autopsie — Voies aériennes": [
        ("voies_aeriennes.detail", "Voies aériennes — détail"),
    ],
    "Autopsie — Thorax": [
        ("thorax.thymus.aspect", "Thymus — aspect"),
        ("thorax.thymus.masse", "Thymus — masse (g)"),
        ("thorax.tvi", "TVI"),
        ("thorax.pericarde", "Péricarde"),
        ("thorax.tsa.etat", "TSA — état"),
        ("thorax.tsa.detail", "TSA — détail"),
    ],
    "Autopsie — Cœur": [
        ("coeur.crosse", "Crosse aortique"),
        ("coeur.isthme", "Isthme"),
        ("coeur.quatre_cav", "Quatre cavités"),
        ("coeur.foramen_ovale", "Foramen ovale"),
        ("coeur.sinus_cor", "Sinus coronaire"),
        ("coeur.gros_vx", "Gros vaisseaux"),
        ("coeur.og_retours", "Retours veineux OG"),
        ("coeur.vd_ej.valve_pulm", "Valve pulmonaire"),
        ("coeur.vg_ej.septum_iv", "Septum IV"),
        ("coeur.vg_ej.civ_diam", "CIV diamètre (mm)"),
        ("coeur.vg_ej.valve_aort", "Valve aortique"),
        ("coeur.vd_av.valve_tric", "Valve tricuspide"),
        ("coeur.vg_av.valve_mitr", "Valve mitrale"),
        ("coeur.vg_av.detail", "VG AV — détail"),
        ("coeur.masse", "Cœur — masse (g)"),
    ],
    "Autopsie — Poumons": [
        ("poumons.morpho", "Poumons — morphologie"),
        ("poumons.docimasie", "Docimasie pulmonaire"),
        ("poumons.masse_d", "Poumon D — masse (g)"),
        ("poumons.masse_g", "Poumon G — masse (g)"),
    ],
    "Autopsie — Digestif": [
        ("digestif.foie.aspect", "Foie — aspect"),
        ("digestif.foie.masse", "Foie — masse (g)"),
        ("digestif.estomac.aspect", "Estomac — aspect"),
        ("digestif.estomac.contenu", "Estomac — contenu"),
        ("digestif.estomac.docimasie_gastrique", "Docimasie gastrique"),
        ("digestif.tube_dig.aspects", "Tube digestif — aspects"),
        ("digestif.tube_dig.detail", "Tube digestif — détail"),
        ("digestif.meconium", "Méconium"),
        ("digestif.anus", "Anus (interne)"),
        ("digestif.rate.aspects", "Rate — aspects"),
        ("digestif.rate.masse", "Rate — masse (g)"),
        ("digestif.pancreas.aspect", "Pancréas — aspect"),
        ("digestif.pancreas.masse", "Pancréas — masse (g)"),
    ],
    "Autopsie — Rétropéritoine": [
        ("retroperitoine.reins.aspects", "Reins — aspects"),
        ("retroperitoine.reins.masse_d", "Rein D — masse (g)"),
        ("retroperitoine.reins.masse_g", "Rein G — masse (g)"),
        ("retroperitoine.surrenales.aspects", "Surrénales — aspects"),
        ("retroperitoine.surrenales.masse_d", "Surrénale D — masse (g)"),
        ("retroperitoine.surrenales.masse_g", "Surrénale G — masse (g)"),
        ("retroperitoine.voies_urin", "Voies urinaires"),
        ("retroperitoine.vessie", "Vessie"),
        ("retroperitoine.gonades_pos", "Gonades"),
    ],
    "Autopsie — Neuro": [
        ("neuro.cerveau_ext", "Cerveau externe"),
        ("neuro.gyration", "Gyration"),
        ("neuro.moelle", "Moelle"),
        ("neuro.masse_cerveau", "Masse cerveau (g)"),
        ("neuro.detail", "Neuro — détail"),
    ],
    "Autopsie — Prélèvements": [
        ("prelevements.annexes", "Prélèvements standards (liste)"),
        ("prelevements.annexes_det", "Compléments standards"),
        ("prelevements.speciaux", "Prélèvements spéciaux (liste)"),
        ("prelevements.speciaux_det", "Détail spéciaux"),
        ("prelevements.congelation", "Congélation"),
        ("prelevements.dnatheque", "DNAthèque"),
    ],
    "Autopsie — Commentaire": [
        ("commentaire_autopsie", "Commentaire autopsie"),
    ],
    # ── Autopsie — Tri normal / anormal ──
    "Autopsie — Normal vs Anormal": [
        ("split_morpho().normales", "Morpho externe — normaux (liste)"),
        ("split_morpho().anomalies", "Morpho externe — anomalies (liste)"),
        ("split_autopsie().normales", "Autopsie — organes normaux (liste)"),
        ("split_autopsie().anomalies", "Autopsie — anomalies (liste)"),
    ],
    # ── Après fixation ──
    "Après fixation": [
        ("split_fixe().normales", "Organes fixés normaux (liste)"),
        ("split_fixe().anomalies", "Organes fixés — lésions (liste)"),
        ("macro_fixe.commentaire", "Commentaire macro fixé"),
    ],
    # ── Radiologie ──
    "Radiologie — Général": [
        ("rad_terme_sa", "Terme radio (SA)"),
        ("rad_aspect_general", "Aspect général radio"),
        ("rad_thorax_forme", "Forme du thorax"),
        ("rad_remarques", "Remarques radio"),
        ("rad_hpo_codes", "Codes HPO radio (liste)"),
    ],
    "Radiologie — Squelette axial": [
        ("rad_cotes.droite", "Côtes droite"),
        ("rad_cotes.gauche", "Côtes gauche"),
        ("rad_vertebres.aspects", "Vertèbres — aspects"),
        ("rad_vertebres.remarques", "Vertèbres — remarques"),
    ],
    "Radiologie — Os et biométries": [
        ("rad_aspect_os.aspects", "Aspect os — anomalies"),
        ("rad_biometries.bip_osseux_mm", "BIP osseux (mm)"),
        ("rad_biometries.pc_radio_mm", "PC radio (mm)"),
        ("table_os_longs()", "Tableau os longs Chitty (HTML)"),
    ],
    "Radiologie — Scores staturaux": [
        ("rad_scores.hadlock_sa", "Hadlock (SA)"),
        ("rad_scores.adalian_sa", "Adalian (SA)"),
    ],
    "Radiologie — Maturation": [
        ("table_maturation()", "Tableau maturation osseuse (HTML)"),
    ],
    "Radiologie — Normal vs Anormal": [
        ("split_radio().normales", "Radio — éléments normaux (liste)"),
        ("split_radio().anomalies", "Radio — anomalies (liste)"),
    ],
    # ── Histologie (stub) ──
    "Histologie": [
        ("histo_organes", "Organes examinés (liste)"),
        ("histo_lesions", "Lésions histologiques (liste)"),
    ],
    # ── Labellisation viewer ──
    "Labellisation FOETO": [
        ("labellisation_micro_text", "Texte microscopie labellisation (organe : description)"),
        ("labellisation_table", "Tableau [{organe, statut, findings: [{text, nb_lames}], notes}]"),
        ("composite_micro_text", "Texte composite : normal par défaut, pathologies remplacent"),
    ],
    # ── Conclusion ──
    "Conclusion": [
        ("all_anomalies", "Toutes anomalies agrégées (liste)"),
        ("trophicite", "Trophicité"),
    ],
    # ── Photos ──
    "Photos": [
        ("photos_frais", "Photos examen frais (liste)"),
        ("photos_autopsie", "Photos autopsie (liste)"),
    ],
}


# ══════════════════════════════════════════════════════════════════════════
# Palette placenta (variables de build_cr_context dans placenta_cr_templates.py)
# ══════════════════════════════════════════════════════════════════════════

TEMPLATE_VARIABLES_PLACENTA = {
    "Dossier": [
        ("numero", "Numéro de dossier"),
        ("statut", "Statut du cas"),
    ],
    "Contexte": [
        ("terme_sa", "Terme (SA)"),
        ("terme_j", "Terme (jours)"),
        ("terme_source", "Source du terme"),
        ("masse_foetale_g", "Masse fœtale (g)"),
        ("sexe", "Sexe (M/F)"),
        ("indication_terme", "Indication d'examen"),
    ],
    "Biométrie galette": [
        ("grand_axe_cm", "Grand axe (cm)"),
        ("petit_axe_cm", "Petit axe (cm)"),
        ("epaisseur_cm", "Épaisseur (cm)"),
        ("masse_paree_g", "Masse parée (g)"),
        ("forme", "Forme du disque"),
        ("completude", "Complétude (liste)"),
    ],
    "Z-score (Redline)": [
        ("zscore.masse_ds", "Z-score masse (DS)"),
        ("zscore.percentile", "Percentile"),
        ("zscore.trophicite", "Trophicité"),
        ("zscore.ref.moyenne", "Réf. moyenne (g)"),
        ("zscore.ref.sd", "Réf. SD"),
        ("zscore.extrapolated", "Extrapolé (bool)"),
        ("zscore.ratio_fp", "Ratio F/P"),
        ("zscore.ratio_ds", "Ratio DS"),
    ],
    "Plaques": [
        ("plaque_choriale", "Plaque choriale (dict)"),
        ("plaque_basale", "Plaque basale (dict)"),
    ],
    "Cordon": [
        ("cordon.insertion", "Insertion"),
        ("cordon.longueur_cm", "Longueur (cm)"),
        ("cordon.spiralisation", "Spiralisation"),
        ("cordon.vaisseaux", "Vaisseaux"),
        ("cordon.palmure_amniotique", "Palmure amniotique"),
        ("cordon.striction", "Striction"),
        ("cordon.remarques", "Remarques cordon"),
    ],
    "Membranes": [
        ("membranes.insertion", "Insertion"),
        ("membranes.aspect", "Aspect"),
        ("membranes.marginee_pct", "Marginée (%)"),
        ("membranes.remarques", "Remarques membranes"),
    ],
    "Tranches de section": [
        ("nb_tranches_groups", "Nombre de groupes de tranches"),
        ("lesions", "Lésions focales (liste de dict)"),
        ("tranches_commentaire", "Commentaire tranches de section"),
    ],
    "Microscopie": [
        ("micro_text", "Texte microscopie (grille)"),
        ("viewer_micro_text", "Texte annotations viewer"),
        ("viewer_conclusion_items", "Conclusion viewer"),
        ("labellisation_micro_text", "Labellisation FOETO (texte organe : description)"),
        ("labellisation_table", "Tableau [{organe, statut, findings: [{text, nb_lames}], notes}]"),
        ("composite_micro_text", "Texte composite : placenta normal par défaut, compartiments pathologiques remplacés"),
    ],
    "Helpers": [
        ("_completude(completude)", "Formate complétude en texte"),
        ("_plaque(plaque_choriale)", "Formate plaque complète (aspect + note)"),
        ("_plaque_short(plaque_basale)", "Formate plaque courte (aspect seul)"),
    ],
    "Photos": [
        ("photos_frais", "Photos examen frais (liste)"),
        ("photos_tranches", "Photos tranches (liste)"),
    ],
}
