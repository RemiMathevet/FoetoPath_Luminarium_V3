
// ── State ────────────────────────────────────
let state = {
    cases: [],
    currentCase: null,
    currentFilter: '',
    editingCaseId: null,
    viewerUrl: null,
};

// ── API helpers ──────────────────────────────
async function api(url, opts = {}) {
    const res = await fetch('/admin' + url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    return res.json();
}

async function loadViewerUrl() {
    try {
        const data = await api('/api/viewer-url');
        state.viewerUrl = data.url;
    } catch (_) {}
}

function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast visible' + (type ? ' ' + type : '');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('visible'), 4000);
}

// ── Cases ────────────────────────────────────
async function loadCases() {
    const q = document.getElementById('searchInput').value.trim();
    const params = new URLSearchParams();
    if (state.currentFilter) params.set('statut', state.currentFilter);
    if (q) params.set('q', q);
    try {
        const data = await api('/api/cases?' + params);
        state.cases = data.cases || [];
        renderCaseList();
        // Load lame counts in background
        const numeros = state.cases.map(c => c.numero_dossier).filter(Boolean);
        if (numeros.length) {
            try {
                const counts = await api('/api/lumi-counts?numeros=' + encodeURIComponent(numeros.join(',')));
                state.lameCounts = counts;
                renderCaseList();
            } catch(_) {}
        }
    } catch (e) {
        toast('Erreur chargement: ' + e.message, 'error');
    }
}

function renderCaseList() {
    const el = document.getElementById('caseList');
    if (!state.cases.length) {
        el.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg><h3>Aucun cas</h3></div>`;
        return;
    }
    el.innerHTML = state.cases.map(c => {
        const isActive = state.currentCase && state.currentCase.id === c.id;
        const nom = [c.nom_mere, c.prenom_mere].filter(Boolean).join(' ') || 'Sans nom';
        const macroOk = c.macro_folders && c.macro_folders.some(f => f.photo_count > 0);
        const lameCount = (state.lameCounts || {})[c.numero_dossier] || 0;
        return `
        <div class="case-item ${isActive ? 'active' : ''}" onclick="selectCase(${c.id})">
            <div class="case-item-top">
                <span class="case-item-num">${c.numero_dossier}</span>
                <span class="case-item-status ${c.statut}">${c.statut === 'en_cours' ? 'En cours' : c.statut === 'complet' ? 'Complet' : 'Archivé'}</span>
            </div>
            <div class="case-item-name">${nom}${c.case_id_externe ? ' · ' + c.case_id_externe : ''}</div>
            <div class="case-item-meta">
                ${c.terme_issue ? '<span>' + c.terme_issue + ' SA</span>' : ''}
                ${c.type_issue ? '<span>' + c.type_issue + '</span>' : ''}
                <span>${c.module_count || 0} module(s)</span>
                <span class="dot ${macroOk ? 'ok' : 'missing'}" title="${macroOk ? 'Photos macro' : 'Pas de photos'}"></span>
                ${lameCount ? '<span class="dot lames" title="' + lameCount + ' lame(s) dans Lumi"></span>' : ''}
                ${c.assigned_to ? '<span style="color:var(--info);font-size:10px" title="Attribué à ' + c.assigned_to + '">&#128100; ' + c.assigned_to + '</span>' : ''}
            </div>
        </div>`;
    }).join('');
}

async function selectCase(id) {
    try {
        const c = await api('/api/cases/' + id);
        state.currentCase = c;
        renderCaseList();
        renderCaseDetail(c);
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
    }
}

function renderCaseDetail(c) {
    const nom = [c.nom_mere, c.prenom_mere].filter(Boolean).join(' ') || 'Sans nom';
    document.getElementById('mainTitle').textContent = c.numero_dossier + ' — ' + nom;
    document.getElementById('mainActions').innerHTML = `
        <div style="display:flex;gap:8px">
            <button class="btn btn-sm" onclick="openViewerForCase(state.currentCase)" title="Ouvrir photos/lames dans le viewer">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                Viewer
            </button>
            <button class="btn btn-sm" onclick="editCase(${c.id})">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Modifier
            </button>
            <button class="btn btn-sm" onclick="scanMacro(${c.id})">Scan macro</button>
            <button class="btn btn-sm btn-danger" onclick="deleteCase(${c.id})">Supprimer</button>
        </div>`;

    // Tabs
    document.getElementById('mainBody').innerHTML = `
        <div class="tabs" style="margin-bottom:20px">
            <div class="tab active" onclick="switchTab(this,'info')">Informations</div>
            <div class="tab" onclick="switchTab(this,'macroscopie')">Macroscopie</div>
            <div class="tab" onclick="switchTab(this,'microscopie')">Microscopie <span id="micro-badge" style="display:none;background:var(--info,#3498db);color:#fff;font-size:9px;padding:1px 5px;border-radius:8px;margin-left:4px"></span></div>
            <div class="tab" onclick="switchTab(this,'radio')">Radio</div>
            <div class="tab" onclick="switchTab(this,'modules')">Données modules</div>
            <div class="tab" onclick="switchTab(this,'foekinator')">Foekinator</div>
            <div class="tab" onclick="switchTab(this,'aidediag')">Aide diag</div>
            <div class="tab" onclick="switchTab(this,'cr')">CR</div>
        </div>
        <div class="tab-panel active" id="panel-info"></div>
        <div class="tab-panel" id="panel-macroscopie"></div>
        <div class="tab-panel" id="panel-microscopie"></div>
        <div class="tab-panel" id="panel-radio"></div>
        <div class="tab-panel" id="panel-modules"></div>
        <div class="tab-panel" id="panel-foekinator"></div>
        <div class="tab-panel" id="panel-aidediag"></div>
        <div class="tab-panel" id="panel-cr"></div>
    `;

    renderInfoPanel(c);
    renderModulesPanel(c);

    // Update micro badge
    const lc = (state.lameCounts || {})[c.numero_dossier] || 0;
    const badge = document.getElementById('micro-badge');
    if (badge) {
        if (lc > 0) { badge.textContent = lc; badge.style.display = 'inline'; }
        else { badge.style.display = 'none'; }
    }
}

function switchTab(el, name) {
    el.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('panel-' + name).classList.add('active');

    if (name === 'macroscopie' && state.currentCase) {
        renderMacroscopiePanel(state.currentCase);
    }
    if (name === 'microscopie' && state.currentCase) {
        renderMicroscopiePanel(state.currentCase);
    }
    if (name === 'radio' && state.currentCase) {
        renderRadioPanel(state.currentCase);
    }
    if (name === 'foekinator' && state.currentCase) {
        renderFoekinatorPanel(state.currentCase);
    }
    if (name === 'aidediag' && state.currentCase) {
        renderAideDiagPanel(state.currentCase);
    }
    if (name === 'cr' && state.currentCase) {
        renderCRPanel(state.currentCase);
    }
}

function renderInfoPanel(c) {
    const el = document.getElementById('panel-info');
    // Module data from BDD
    const mod = c.modules || {};
    const atcdMat = mod.atcd_maternels?.data || {};
    const atcdObs = mod.atcd_obstetricaux?.data || {};
    const gross = mod.grossesse_en_cours?.data || {};
    const exPren = mod.examens_prenataux?.data || {};

    // Helper: value or empty
    const v = (val) => val || '';
    const chk = (val) => val ? 'checked' : '';
    const sel = (val, opt) => val === opt ? 'selected' : '';

    el.innerHTML = `
    <div class="save-indicator" id="saveIndicator">&#10003; Sauvegardé</div>
    <div class="form-nav" id="formNav">
        <button class="form-nav-btn active" onclick="showFormSec(1)"><span class="form-nav-num">1</span> Dossier Admin</button>
        <button class="form-nav-btn" onclick="showFormSec(2)"><span class="form-nav-num">2</span> ATCD Maternels</button>
        <button class="form-nav-btn" onclick="showFormSec(3)"><span class="form-nav-num">3</span> ATCD Obstétricaux</button>
        <button class="form-nav-btn" onclick="showFormSec(4)"><span class="form-nav-num">4</span> Grossesse en cours</button>
        <button class="form-nav-btn" onclick="showFormSec(5)"><span class="form-nav-num">5</span> Examens Prénataux</button>
        <button class="form-nav-btn" onclick="showFormSec(6)"><span class="form-nav-num">6</span> BaMaRa</button>
    </div>

    <!-- ═══ SECTION 1: Dossier Administratif ═══ -->
    <div class="fsec active" data-fsec="1">
        <div class="fsec-header"><div class="fsec-num">1</div><div><div class="fsec-title">Dossier Administratif</div><div class="fsec-desc">Informations générales du dossier et identités</div></div></div>

        <div class="fgroup"><div class="fgroup-title">Identification du Dossier</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Numéro de dossier *</label><input class="finput" data-field="numero_dossier" value="${v(c.numero_dossier)}" readonly style="opacity:0.6"></div>
                <div class="ff"><label class="flabel">ID Externe</label><input class="finput" data-field="case_id_externe" value="${v(c.case_id_externe)}"></div>
                <div class="ff"><label class="flabel">IPP mère</label><input class="finput" data-field="ipp" value="${v(c.ipp)}"></div>
                <div class="ff"><label class="flabel">IPP fœtus</label><input class="finput" data-field="ipp_fetus" value="${v(c.ipp_fetus)}"></div>
                <div class="ff"><label class="flabel">INS</label><input class="finput" data-field="ins" value="${v(c.ins)}" maxlength="13" placeholder="13 caractères"></div>
                <div class="ff"><label class="flabel">Opposition BaMaRa</label>
                    <select class="fselect" data-field="opposition">
                        <option value="0" ${c.opposition ? '' : 'selected'}>Non</option>
                        <option value="1" ${c.opposition ? 'selected' : ''}>Oui</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Identité de la Mère</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Nom</label><input class="finput" data-field="nom_mere" value="${v(c.nom_mere)}"></div>
                <div class="ff"><label class="flabel">Prénom</label><input class="finput" data-field="prenom_mere" value="${v(c.prenom_mere)}"></div>
                <div class="ff"><label class="flabel">Nom de naissance</label><input class="finput" data-field="nom_naissance_mere" value="${v(c.nom_naissance_mere)}"></div>
                <div class="ff"><label class="flabel">Date de naissance</label><input type="date" class="finput" data-field="ddn_mere" value="${v(c.ddn_mere)}"></div>
                <div class="ff"><label class="flabel">Lieu de résidence</label><input class="finput" data-field="lieu_residence" value="${v(c.lieu_residence)}"></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Identité du Fœtus</div>
            <div class="fgrid cols-3">
                <div class="ff"><label class="flabel">Nom</label><input class="finput" data-field="nom_foetus" value="${v(c.nom_foetus)}"></div>
                <div class="ff"><label class="flabel">Prénom</label><input class="finput" data-field="prenom_foetus" value="${v(c.prenom_foetus)}"></div>
                <div class="ff"><label class="flabel">Date naissance/décès</label><input type="date" class="finput" data-field="ddn_foetus" value="${v(c.ddn_foetus)}"></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Contexte du Dossier</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Ville maternité</label><input class="finput" data-field="ville_maternite" value="${v(c.ville_maternite)}"></div>
                <div class="ff"><label class="flabel">Date réception</label><input type="date" class="finput" data-field="date_reception" value="${v(c.date_reception)}"></div>
                <div class="ff"><label class="flabel">Consanguinité</label>
                    <select class="fselect" data-field="consanguinite">
                        <option value="">—</option>
                        <option value="true" ${sel(c.consanguinite,'true')}>Oui</option>
                        <option value="false" ${sel(c.consanguinite,'false')}>Non</option>
                        <option value="UNK" ${sel(c.consanguinite,'UNK')}>Inconnu</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Grossesse multiple</label>
                    <select class="fselect" data-field="grossesse_multiple">
                        <option value="0" ${c.grossesse_multiple ? '' : 'selected'}>Non</option>
                        <option value="1" ${c.grossesse_multiple ? 'selected' : ''}>Oui</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Service demandeur</label>
                    <select class="fselect" data-field="service_demandeur">
                        <option value="">—</option>
                        <option value="gynecologie" ${sel(c.service_demandeur,'gynecologie')}>Gynécologie</option>
                        <option value="obstetrique" ${sel(c.service_demandeur,'obstetrique')}>Obstétrique</option>
                        <option value="neonatologie" ${sel(c.service_demandeur,'neonatologie')}>Néonatologie</option>
                        <option value="genetique" ${sel(c.service_demandeur,'genetique')}>Génétique</option>
                        <option value="autre" ${sel(c.service_demandeur,'autre')}>Autre</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Médecin référent</label><input class="finput" data-field="medecin_referent" value="${v(c.medecin_referent)}"></div>
                <div class="ff"><label class="flabel">Type d'issue</label>
                    <select class="fselect" data-field="type_issue">
                        <option value="">—</option>
                        <option value="IMG" ${sel(c.type_issue,'IMG')}>IMG</option>
                        <option value="FCS" ${sel(c.type_issue,'FCS')}>FCS</option>
                        <option value="MFIU" ${sel(c.type_issue,'MFIU')}>MFIU</option>
                        <option value="MPN" ${sel(c.type_issue,'MPN')}>Mort per-natale</option>
                        <option value="MNN" ${sel(c.type_issue,'MNN')}>Mort néonatale</option>
                        <option value="NAISSANCE" ${sel(c.type_issue,'NAISSANCE')}>Naissance</option>
                        <option value="ISG" ${sel(c.type_issue,'ISG')}>ISG</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Terme à l'issue</label><input class="finput" data-field="terme_issue" value="${v(c.terme_issue)}" placeholder="Ex: 24 SA + 3j"></div>
                <div class="ff"><label class="flabel">Sexe</label>
                    <select class="fselect" data-field="sexe">
                        <option value="">—</option>
                        <option value="M" ${sel(c.sexe,'M')}>Masculin</option>
                        <option value="F" ${sel(c.sexe,'F')}>Féminin</option>
                        <option value="I" ${sel(c.sexe,'I')}>Indéterminé</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Date de décès</label><input type="date" class="finput" data-field="date_deces" value="${v(c.date_deces)}"></div>
                <div class="ff"><label class="flabel">Date d'examen fœtopath</label><input type="date" class="finput" data-field="date_examen" value="${v(c.date_examen)}"></div>
                <div class="ff"><label class="flabel">Date autopsie (EXIF)</label><input class="finput" value="${v(c.date_autopsie_exif)}" readonly style="opacity:0.7;cursor:default" title="Extraite de la photo avant ouverture"></div>
                <div class="ff"><label class="flabel">RPPS médecin traitant</label><input class="finput" data-field="medecin_traitant_rpps" value="${v(c.medecin_traitant_rpps)}" maxlength="11" placeholder="11 chiffres"></div>
            </div>
            <div class="fgrid" style="margin-top:8px">
                <div class="ff full"><label class="flabel">Indication de l'examen</label><textarea class="ftextarea" data-field="indication_examen" placeholder="Motif de la demande...">${v(c.indication_examen)}</textarea></div>
                <div class="ff full"><label class="flabel">Contexte clinique</label><textarea class="ftextarea" data-field="contexte_clinique" placeholder="Contexte clinique détaillé...">${v(c.contexte_clinique)}</textarea></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Type d'Acte et Workflow</div>
            <div class="fcheck-group" style="margin-bottom:10px">
                <label class="fcheck-item"><input type="checkbox" data-field="acte_clinique" ${chk(c.acte_clinique)}> Examen clinique</label>
                <label class="fcheck-item"><input type="checkbox" data-field="acte_imagerie" ${chk(c.acte_imagerie)}> Imagerie</label>
                <label class="fcheck-item"><input type="checkbox" data-field="acte_anapath" ${chk(c.acte_anapath)}> Anapath</label>
                <label class="fcheck-item"><input type="checkbox" data-field="acte_interne" ${chk(c.acte_interne)}> Examen interne</label>
                <label class="fcheck-item"><input type="checkbox" data-field="acte_virtopsie" ${chk(c.acte_virtopsie)}> Virtopsie</label>
            </div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Numéro placenta</label><input class="finput" data-field="numero_placenta" value="${v(c.numero_placenta)}"></div>
                <div class="ff"><label class="flabel">&nbsp;</label><label class="fcheck-item" style="margin-top:4px"><input type="checkbox" data-field="examen_placenta" ${chk(c.examen_placenta)}> Examen du placenta prévu</label></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Chemins fichiers</div>
            <div class="fgrid">
                <div class="ff full"><label class="flabel">Chemin dossier macro (photos)</label><input class="finput" data-field="dossier_macro_path" value="${v(c.dossier_macro_path)}"></div>
                <div class="ff full"><label class="flabel">Chemin dossier lames</label><input class="finput" data-field="dossier_lames_path" value="${v(c.dossier_lames_path)}"></div>
            </div>
        </div>

        <div class="fsec-actions"><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer</button><button class="btn btn-primary btn-sm" onclick="showFormSec(2)">ATCD Maternels &rarr;</button></div>
    </div>

    <!-- ═══ SECTION 2: ATCD Maternels ═══ -->
    <div class="fsec" data-fsec="2">
        <div class="fsec-header"><div class="fsec-num">2</div><div><div class="fsec-title">Antécédents Maternels</div><div class="fsec-desc">Contexte médical et facteurs de risque</div></div></div>

        <div class="fgroup"><div class="fgroup-title">Informations Générales</div>
            <div class="fgrid cols-3">
                <div class="ff"><label class="flabel">Profession</label><input class="finput" data-mod="atcd_maternels" data-key="profession_mere" value="${v(atcdMat.profession_mere)}"></div>
                <div class="ff"><label class="flabel">Gestité</label>
                    <select class="fselect" data-mod="atcd_maternels" data-key="gestite">
                        <option value="">—</option>
                        ${[1,2,3,4,5,'6+'].map(g => `<option value="${g}" ${atcdMat.gestite==g?'selected':''}>${g}${g==1?' (Primigeste)':''}</option>`).join('')}
                    </select>
                </div>
                <div class="ff"><label class="flabel">Parité</label>
                    <select class="fselect" data-mod="atcd_maternels" data-key="parite">
                        <option value="">—</option>
                        ${[0,1,2,3,4,'5+'].map(p => `<option value="${p}" ${atcdMat.parite==p?'selected':''}>${p}${p==0?' (Nullipare)':p==1?' (Primipare)':''}</option>`).join('')}
                    </select>
                </div>
                <div class="ff"><label class="flabel">Groupe sanguin</label>
                    <select class="fselect" data-mod="atcd_maternels" data-key="groupe_sanguin">
                        <option value="">—</option>
                        ${['A','B','AB','O'].map(g => `<option value="${g}" ${sel(atcdMat.groupe_sanguin,g)}>${g}</option>`).join('')}
                    </select>
                </div>
                <div class="ff"><label class="flabel">Rhésus</label>
                    <select class="fselect" data-mod="atcd_maternels" data-key="rhesus">
                        <option value="">—</option>
                        <option value="positif" ${sel(atcdMat.rhesus,'positif')}>Positif (+)</option>
                        <option value="negatif" ${sel(atcdMat.rhesus,'negatif')}>Négatif (−)</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Facteurs de Risque</div>
            <div class="fcheck-group">
                <label class="fcheck-item"><input type="checkbox" data-mod="atcd_maternels" data-key="fdr_hta" ${chk(atcdMat.fdr_hta)}> HTA</label>
                <label class="fcheck-item"><input type="checkbox" data-mod="atcd_maternels" data-key="fdr_diabete" ${chk(atcdMat.fdr_diabete)}> Diabète</label>
                <label class="fcheck-item"><input type="checkbox" data-mod="atcd_maternels" data-key="fdr_tabac" ${chk(atcdMat.fdr_tabac)}> Tabac</label>
                <label class="fcheck-item"><input type="checkbox" data-mod="atcd_maternels" data-key="fdr_alcool" ${chk(atcdMat.fdr_alcool)}> Alcool</label>
                <label class="fcheck-item"><input type="checkbox" data-mod="atcd_maternels" data-key="fdr_consanguinite" ${chk(atcdMat.fdr_consanguinite)}> Consanguinité</label>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Antécédents et Traitements</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Antécédents médicaux</label><textarea class="ftextarea" data-mod="atcd_maternels" data-key="atcd_medicaux" placeholder="Pathologies, interventions...">${v(atcdMat.atcd_medicaux)}</textarea></div>
                <div class="ff"><label class="flabel">Traitements en cours</label><textarea class="ftextarea" data-mod="atcd_maternels" data-key="traitements" placeholder="Médicaments, posologies...">${v(atcdMat.traitements)}</textarea></div>
            </div>
        </div>

        <div class="fsec-actions"><button class="btn btn-sm" onclick="showFormSec(1)">&larr; Dossier Admin</button><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer</button><button class="btn btn-primary btn-sm" onclick="showFormSec(3)">ATCD Obstétricaux &rarr;</button></div>
    </div>

    <!-- ═══ SECTION 3: ATCD Obstétricaux ═══ -->
    <div class="fsec" data-fsec="3">
        <div class="fsec-header"><div class="fsec-num">3</div><div><div class="fsec-title">Antécédents Obstétricaux</div><div class="fsec-desc">Historique des grossesses précédentes</div></div></div>

        <div id="grossessesContainer">${renderGrossesses(Array.isArray(atcdObs) ? atcdObs : atcdObs.grossesses || [])}</div>
        <button class="btn btn-sm" onclick="addGrossesse()" style="margin-top:8px">+ Ajouter une grossesse</button>

        <div class="fsec-actions"><button class="btn btn-sm" onclick="showFormSec(2)">&larr; ATCD Maternels</button><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer</button><button class="btn btn-primary btn-sm" onclick="showFormSec(4)">Grossesse en cours &rarr;</button></div>
    </div>

    <!-- ═══ SECTION 4: Grossesse en Cours ═══ -->
    <div class="fsec" data-fsec="4">
        <div class="fsec-header"><div class="fsec-num">4</div><div><div class="fsec-title">Grossesse en Cours</div><div class="fsec-desc">Données prénatales de la grossesse actuelle</div></div></div>

        <div class="fgroup"><div class="fgroup-title">Mode de Conception</div>
            <div class="fgrid cols-3">
                <div class="ff"><label class="flabel">Mode</label>
                    <select class="fselect" data-mod="grossesse_en_cours" data-key="mode_conception">
                        <option value="">—</option>
                        <option value="spontanee" ${sel(gross.mode_conception,'spontanee')}>Spontanée</option>
                        <option value="amp" ${sel(gross.mode_conception,'amp')}>AMP</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Type d'AMP</label>
                    <select class="fselect" data-mod="grossesse_en_cours" data-key="amp_type">
                        <option value="">—</option>
                        ${['FIV','ICSI','IAC','IAD','DON_OVOCYTES'].map(t => `<option value="${t}" ${sel(gross.amp_type,t)}>${t}</option>`).join('')}
                    </select>
                </div>
                <div class="ff"><label class="flabel">DDG</label><input type="date" class="finput" data-mod="grossesse_en_cours" data-key="ddg" value="${v(gross.ddg)}"></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Marqueurs Sériques (T1)</div>
            <div class="fgrid cols-5">
                <div class="ff"><label class="flabel">Risque T21</label><input class="finput" data-mod="grossesse_en_cours" data-key="risque_t21" value="${v(gross.risque_t21)}" placeholder="1/1500"></div>
                <div class="ff"><label class="flabel">β-hCG (MoM)</label><input type="number" step="0.01" class="finput" data-mod="grossesse_en_cours" data-key="bhcg" value="${v(gross.bhcg)}"></div>
                <div class="ff"><label class="flabel">PAPP-A (MoM)</label><input type="number" step="0.01" class="finput" data-mod="grossesse_en_cours" data-key="pappa" value="${v(gross.pappa)}"></div>
                <div class="ff"><label class="flabel">LCC (mm)</label><input type="number" step="0.1" class="finput" data-mod="grossesse_en_cours" data-key="lcc" value="${v(gross.lcc)}"></div>
                <div class="ff"><label class="flabel">CN (mm)</label><input type="number" step="0.1" class="finput" data-mod="grossesse_en_cours" data-key="cn" value="${v(gross.cn)}"></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Suivi de Grossesse</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Lieu de suivi</label><input class="finput" data-mod="grossesse_en_cours" data-key="lieu_suivi" value="${v(gross.lieu_suivi)}"></div>
            </div>
            <div class="ff full" style="margin-top:8px"><label class="flabel">Histoire clinique</label><textarea class="ftextarea" data-mod="grossesse_en_cours" data-key="histoire_clinique" placeholder="Déroulement, événements notables..." style="min-height:100px">${v(gross.histoire_clinique)}</textarea></div>
        </div>

        <div class="fsec-actions"><button class="btn btn-sm" onclick="showFormSec(3)">&larr; ATCD Obstétricaux</button><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer</button><button class="btn btn-primary btn-sm" onclick="showFormSec(5)">Examens Prénataux &rarr;</button></div>
    </div>

    <!-- ═══ SECTION 5: Examens Prénataux ═══ -->
    <div class="fsec" data-fsec="5">
        <div class="fsec-header"><div class="fsec-num">5</div><div><div class="fsec-title">Examens Prénataux</div><div class="fsec-desc">Échographies et résultats génétiques</div></div></div>

        <div class="fgroup"><div class="fgroup-title">Échographies</div>
            ${['t1','t2','t3'].map((t,i) => {
                const label = ['T1 (11-14 SA)','T2 (20-24 SA)','T3 (30-34 SA)'][i];
                const echoData = typeof exPren['echo_'+t] === 'string' ? JSON.parse(exPren['echo_'+t] || '{}') : (exPren['echo_'+t] || {});
                return `<div class="fgrid" style="margin-bottom:10px">
                    <div class="ff"><label class="flabel">Écho ${label}</label>
                        <select class="fselect" data-mod="examens_prenataux" data-key="echo_${t}_status">
                            <option value="">Non réalisée</option>
                            <option value="normal" ${sel(exPren['echo_'+t+'_status'] || echoData.status,'normal')}>Normal</option>
                            <option value="anormal" ${sel(exPren['echo_'+t+'_status'] || echoData.status,'anormal')}>Anormal</option>
                        </select>
                    </div>
                    <div class="ff"><label class="flabel">Détails ${label.split(' ')[0]}</label><input class="finput" data-mod="examens_prenataux" data-key="echo_${t}_details" value="${v(exPren['echo_'+t+'_details'] || echoData.details)}" placeholder="Commentaires..."></div>
                </div>`;
            }).join('')}
        </div>

        <div class="fgroup"><div class="fgroup-title">Examens Génétiques</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Caryotype</label><input class="finput" data-mod="examens_prenataux" data-key="caryotype" value="${v(exPren.caryotype)}" placeholder="46,XX ou 47,XY,+21"></div>
                <div class="ff"><label class="flabel">ACPA (CGH-Array)</label>
                    <select class="fselect" data-mod="examens_prenataux" data-key="acpa">
                        <option value="">Non réalisée</option>
                        <option value="normal" ${sel(exPren.acpa,'normal')}>Normal</option>
                        <option value="anormal" ${sel(exPren.acpa,'anormal')}>Anormal</option>
                        <option value="en_cours" ${sel(exPren.acpa,'en_cours')}>En cours</option>
                    </select>
                </div>
            </div>
            <div class="fgrid" style="margin-top:8px">
                <div class="ff"><label class="flabel">NGS / Exome</label><textarea class="ftextarea" data-mod="examens_prenataux" data-key="ngs" placeholder="Résultats séquençage...">${v(exPren.ngs)}</textarea></div>
                <div class="ff"><label class="flabel">DPNI / Aneuploïdie</label><textarea class="ftextarea" data-mod="examens_prenataux" data-key="recherche_aneuploidie" placeholder="Résultats DPNI...">${v(exPren.recherche_aneuploidie)}</textarea></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Bilan des Anomalies</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Anomalies suspectées</label><textarea class="ftextarea" data-mod="examens_prenataux" data-key="anomalies_suspectees" placeholder="Anomalies dépistées en prénatal...">${v(exPren.anomalies_suspectees)}</textarea></div>
                <div class="ff"><label class="flabel">Anomalies confirmées</label><textarea class="ftextarea" data-mod="examens_prenataux" data-key="anomalies_confirmees" placeholder="Anomalies confirmées...">${v(exPren.anomalies_confirmees)}</textarea></div>
            </div>
        </div>

        <div class="fsec-actions"><button class="btn btn-sm" onclick="showFormSec(4)">&larr; Grossesse en cours</button><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer</button><button class="btn btn-primary btn-sm" onclick="showFormSec(6)">BaMaRa &rarr;</button></div>
    </div>

    <!-- ── Section 6: BaMaRa Complémentaire ── -->
    <div class="fsec" data-fsec="6">
        <div class="fsec-header"><div class="fsec-num">6</div><div><div class="fsec-title">BaMaRa Complémentaire</div><div class="fsec-desc">Données SDM-MR : anténatal, propositus, recherche, gènes, techniques</div></div></div>

        <div class="fgroup"><div class="fgroup-title">Propositus</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">IPP propositus</label><input class="finput" data-field="propositus_ipp" value="${v(c.propositus_ipp)}"></div>
                <div class="ff"><label class="flabel">INS propositus</label><input class="finput" data-field="propositus_ins" value="${v(c.propositus_ins)}" maxlength="13"></div>
                <div class="ff"><label class="flabel">Relation</label>
                    <select class="fselect" data-field="propositus_relation">
                        <option value="">—</option>
                        <option value="MERE" ${sel(c.propositus_relation,'MERE')}>Mère</option>
                        <option value="PERE" ${sel(c.propositus_relation,'PERE')}>Père</option>
                        <option value="FOETUS" ${sel(c.propositus_relation,'FOETUS')}>Foetus</option>
                        <option value="INCONNU" ${sel(c.propositus_relation,'INCONNU')}>Inconnu</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Recherche</div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Contact autorisé</label><label class="fcheck-item"><input type="checkbox" data-field="research_contact" ${chk(c.research_contact)}> Autorisation de contact</label></div>
                <div class="ff"><label class="flabel">Échantillon recherche</label><label class="fcheck-item"><input type="checkbox" data-field="sample_research" ${chk(c.sample_research)}> Recherche</label></div>
                <div class="ff"><label class="flabel">Échantillon diagnostic</label><label class="fcheck-item"><input type="checkbox" data-field="sample_diagnostic" ${chk(c.sample_diagnostic)}> Diagnostic</label></div>
                <div class="ff"><label class="flabel">Biobanque</label><input class="finput" data-field="research_biobank" value="${v(c.research_biobank)}" placeholder="Identifiant biobanque"></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Gènes (HGNC)</div>
            <div id="bamara-genes-list" style="margin-bottom:8px"></div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Code</label><input class="finput" id="bamara-gene-code" placeholder="Ex: BRCA1"></div>
                <div class="ff"><label class="flabel">Libellé</label><input class="finput" id="bamara-gene-label" placeholder="Nom du gène"></div>
                <div class="ff"><label class="flabel">&nbsp;</label><button class="btn btn-primary btn-sm" onclick="addBamaraGene()">+ Ajouter</button></div>
            </div>
        </div>

        <div class="fgroup"><div class="fgroup-title">Techniques Biologiques</div>
            <div id="bamara-biomethods-list" style="margin-bottom:8px"></div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Code</label><input class="finput" id="bamara-biomethod-code" placeholder="Ex: FISH, CGH"></div>
                <div class="ff"><label class="flabel">Libellé</label><input class="finput" id="bamara-biomethod-label" placeholder="Description de la technique"></div>
                <div class="ff"><label class="flabel">&nbsp;</label><button class="btn btn-primary btn-sm" onclick="addBamaraBioMethod()">+ Ajouter</button></div>
            </div>
        </div>

        <div class="fsec-actions"><button class="btn btn-sm" onclick="showFormSec(5)">&larr; Examens Prénataux</button><button class="btn btn-success btn-sm" onclick="saveFullForm()">&#10003; Enregistrer tout</button></div>
    </div>

    <div style="display:flex;flex-wrap:wrap;gap:8px;font-size:11px;color:var(--text3);margin-top:16px;align-items:center">
        <span>Créé : ${c.created_at ? new Date(c.created_at).toLocaleString('fr-FR') : '—'}${c.created_by ? ' par <b style="color:var(--text2)">' + escHtml(c.created_by) + '</b>' : ''}</span>
        <span>·</span>
        <span>Mis à jour : ${c.updated_at ? new Date(c.updated_at).toLocaleString('fr-FR') : '—'}${c.modified_by ? ' par <b style="color:var(--text2)">' + escHtml(c.modified_by) + '</b>' : ''}</span>
        <span>·</span>
        <span>Statut : <select class="fselect" data-field="statut" style="display:inline;width:auto;padding:2px 6px;font-size:11px">
            <option value="en_cours" ${sel(c.statut,'en_cours')}>En cours</option>
            <option value="complet" ${sel(c.statut,'complet')}>Complet</option>
            <option value="archive" ${sel(c.statut,'archive')}>Archivé</option>
        </select></span>
        <span>·</span>
        <span>Attribué à : <select class="fselect" id="assignedToSelect" data-field="assigned_to" style="display:inline;width:auto;padding:2px 6px;font-size:11px"
            onchange="assignCase(this.value)">
            <option value="">— Non attribué —</option>
        </select></span>
    </div>
    `;

    // Attach autosave listeners
    attachFormListeners();

    // Attach HPO autocomplete to all textareas in the case form
    setTimeout(() => adminInitHPOAutocomplete(), 150);

    // Load BaMaRa N:1 lists (genes, biologic methods)
    loadBamaraGenes();
    loadBamaraBioMethods();

    // Charger la liste des utilisateurs dans le dropdown "Attribué à"
    loadAssignedToDropdown(c.assigned_to || '');
}

// Cache global des utilisateurs pour le dropdown
let _cachedUsers = null;

async function loadAssignedToDropdown(currentValue) {
    const sel = document.getElementById('assignedToSelect');
    if (!sel) return;

    // Charger les utilisateurs (cache)
    if (!_cachedUsers) {
        try {
            const res = await api('/api/users/list');
            _cachedUsers = res.users || [];
        } catch(e) {
            _cachedUsers = [];
        }
    }

    // Remplir le dropdown
    let html = '<option value="">— Non attribué —</option>';
    _cachedUsers.forEach(u => {
        const display = u.display_name || u.username;
        const roleTag = u.role === 'admin' ? ' (admin)' : u.role === 'admin_centre' ? ' (admin centre)' : '';
        const selected = (u.username === currentValue) ? 'selected' : '';
        html += `<option value="${escHtml(u.username)}" ${selected}>${escHtml(display)}${roleTag}</option>`;
    });
    sel.innerHTML = html;
}

async function assignCase(username) {
    if (!state.currentCase) return;
    try {
        await api('/api/cases/' + state.currentCase.id, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({assigned_to: username})
        });
        state.currentCase.assigned_to = username;
        toast(username ? 'Cas attribué à ' + username : 'Attribution retirée', 'success');
    } catch(e) {
        toast('Erreur attribution: ' + e.message, 'error');
    }
}

function renderGrossesses(list) {
    if (!list || !list.length) list = [{}];
    return list.map((g, i) => `
        <div class="fgroup" data-gross-idx="${i}">
            <div class="fgroup-title" style="display:flex;justify-content:space-between;align-items:center">
                Grossesse précédente #${i+1}
                ${i > 0 ? `<button class="btn btn-sm btn-danger" onclick="removeGrossesse(${i})" style="padding:2px 8px;font-size:10px">&times;</button>` : ''}
            </div>
            <div class="fgrid">
                <div class="ff"><label class="flabel">Date</label><input class="finput" data-gross="${i}" data-gkey="date" value="${g.date||''}" placeholder="2020 ou 06/2020"></div>
                <div class="ff"><label class="flabel">Issue</label>
                    <select class="fselect" data-gross="${i}" data-gkey="issue">
                        <option value="">—</option>
                        <option value="NAISSANCE_VIVANTE" ${g.issue==='NAISSANCE_VIVANTE'?'selected':''}>Naissance vivante</option>
                        <option value="MFIU" ${g.issue==='MFIU'?'selected':''}>MFIU</option>
                        <option value="IMG" ${g.issue==='IMG'?'selected':''}>IMG</option>
                        <option value="FCS" ${g.issue==='FCS'?'selected':''}>Fausse couche spontanée</option>
                        <option value="GEU" ${g.issue==='GEU'?'selected':''}>GEU</option>
                        <option value="AUTRE" ${g.issue==='AUTRE'?'selected':''}>Autre</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Terme d'accouchement</label><input class="finput" data-gross="${i}" data-gkey="terme_accouchement" value="${g.terme_accouchement||''}" placeholder="38 SA"></div>
                <div class="ff"><label class="flabel">Voie d'accouchement</label>
                    <select class="fselect" data-gross="${i}" data-gkey="voie_accouchement">
                        <option value="">—</option>
                        <option value="VBS" ${g.voie_accouchement==='VBS'?'selected':''}>Voie basse spontanée</option>
                        <option value="CESARIENNE" ${g.voie_accouchement==='CESARIENNE'?'selected':''}>Césarienne</option>
                        <option value="AUTRE" ${g.voie_accouchement==='AUTRE'?'selected':''}>Autre</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Sexe</label>
                    <select class="fselect" data-gross="${i}" data-gkey="sexe">
                        <option value="">—</option>
                        <option value="M" ${g.sexe==='M'?'selected':''}>M</option>
                        <option value="F" ${g.sexe==='F'?'selected':''}>F</option>
                    </select>
                </div>
                <div class="ff"><label class="flabel">Percentile AUDIPOG</label>
                    <select class="fselect" data-gross="${i}" data-gkey="percentile_audipog">
                        <option value="">—</option>
                        <option value="3" ${g.percentile_audipog==3?'selected':''}>&lt;3e (RCIU)</option>
                        <option value="10" ${g.percentile_audipog==10?'selected':''}>3-10e (PAG)</option>
                        <option value="50" ${g.percentile_audipog==50?'selected':''}>10-90e (Normal)</option>
                        <option value="90" ${g.percentile_audipog==90?'selected':''}>90-97e</option>
                        <option value="97" ${g.percentile_audipog==97?'selected':''}>&gt;97e (Macrosomie)</option>
                    </select>
                </div>
            </div>
        </div>
    `).join('');
}

function addGrossesse() {
    const container = document.getElementById('grossessesContainer');
    const count = container.querySelectorAll('[data-gross-idx]').length;
    container.insertAdjacentHTML('beforeend', renderGrossesses([{}]).replace(/data-gross-idx="0"/g, `data-gross-idx="${count}"`).replace(/data-gross="0"/g, `data-gross="${count}"`).replace(/#1/, `#${count+1}`));
}

function removeGrossesse(idx) {
    const el = document.querySelector(`[data-gross-idx="${idx}"]`);
    if (el) el.remove();
}

function showFormSec(n) {
    document.querySelectorAll('.fsec').forEach(s => s.classList.toggle('active', s.dataset.fsec == n));
    document.querySelectorAll('.form-nav-btn').forEach((b, i) => b.classList.toggle('active', i === n-1));
}

// ── BaMaRa N:1 lists (genes, biologic methods) ──────────

async function loadBamaraGenes() {
    if (!state.currentCase) return;
    const list = document.getElementById('bamara-genes-list');
    if (!list) return;
    try {
        const genes = await api('/api/cases/' + state.currentCase.id + '/genes');
        list.innerHTML = genes.length ? genes.map(g =>
            `<span class="tag-pill">${escHtml(g.code)} — ${escHtml(g.label)} <button class="tag-rm" onclick="removeBamaraGene('${escHtml(g.code)}')">&times;</button></span>`
        ).join(' ') : '<span style="color:var(--text3);font-size:12px">Aucun gène</span>';
    } catch(e) { list.innerHTML = ''; }
}

async function addBamaraGene() {
    if (!state.currentCase) return;
    const code = document.getElementById('bamara-gene-code').value.trim();
    const label = document.getElementById('bamara-gene-label').value.trim();
    if (!code) return;
    await api('/api/cases/' + state.currentCase.id + '/genes', { method: 'POST', body: JSON.stringify({code, label}) });
    document.getElementById('bamara-gene-code').value = '';
    document.getElementById('bamara-gene-label').value = '';
    loadBamaraGenes();
}

async function removeBamaraGene(code) {
    if (!state.currentCase) return;
    await api('/api/cases/' + state.currentCase.id + '/genes', { method: 'DELETE', body: JSON.stringify({code}) });
    loadBamaraGenes();
}

async function loadBamaraBioMethods() {
    if (!state.currentCase) return;
    const list = document.getElementById('bamara-biomethods-list');
    if (!list) return;
    try {
        const methods = await api('/api/cases/' + state.currentCase.id + '/biologic-methods');
        list.innerHTML = methods.length ? methods.map(m =>
            `<span class="tag-pill">${escHtml(m.code)} — ${escHtml(m.label)} <button class="tag-rm" onclick="removeBamaraBioMethod('${escHtml(m.code)}')">&times;</button></span>`
        ).join(' ') : '<span style="color:var(--text3);font-size:12px">Aucune technique</span>';
    } catch(e) { list.innerHTML = ''; }
}

async function addBamaraBioMethod() {
    if (!state.currentCase) return;
    const code = document.getElementById('bamara-biomethod-code').value.trim();
    const label = document.getElementById('bamara-biomethod-label').value.trim();
    if (!code) return;
    await api('/api/cases/' + state.currentCase.id + '/biologic-methods', { method: 'POST', body: JSON.stringify({code, label}) });
    document.getElementById('bamara-biomethod-code').value = '';
    document.getElementById('bamara-biomethod-label').value = '';
    loadBamaraBioMethods();
}

async function removeBamaraBioMethod(code) {
    if (!state.currentCase) return;
    await api('/api/cases/' + state.currentCase.id + '/biologic-methods', { method: 'DELETE', body: JSON.stringify({code}) });
    loadBamaraBioMethods();
}

// ── Auto-save logic ──────────────────────────
let _saveTimer;
function attachFormListeners() {
    document.querySelectorAll('#panel-info .finput, #panel-info .fselect, #panel-info .ftextarea, #panel-info input[type="checkbox"]').forEach(el => {
        // Select et checkbox : save immédiat au changement
        el.addEventListener('change', () => { clearTimeout(_saveTimer); _saveTimer = setTimeout(saveFullForm, 300); });
        // Frappe clavier : save après 1s d'inactivité
        if (el.tagName !== 'SELECT' && el.type !== 'checkbox') {
            el.addEventListener('input', () => { clearTimeout(_saveTimer); _saveTimer = setTimeout(saveFullForm, 1000); });
        }
    });
}

async function saveFullForm() {
    if (!state.currentCase) return;
    const caseId = state.currentCase.id;

    // 1. Collect case admin fields
    const caseData = {};
    document.querySelectorAll('#panel-info [data-field]').forEach(el => {
        const key = el.dataset.field;
        if (el.type === 'checkbox') caseData[key] = el.checked;
        else caseData[key] = el.value || null;
    });
    delete caseData.numero_dossier; // never overwrite

    // 2. Collect module data
    const modules = {};
    document.querySelectorAll('#panel-info [data-mod]').forEach(el => {
        const mod = el.dataset.mod;
        const key = el.dataset.key;
        if (!modules[mod]) modules[mod] = {};
        if (el.type === 'checkbox') modules[mod][key] = el.checked;
        else modules[mod][key] = el.value || null;
    });

    // 3. Collect grossesses
    const grossesses = [];
    document.querySelectorAll('#panel-info [data-gross]').forEach(el => {
        const idx = parseInt(el.dataset.gross);
        if (!grossesses[idx]) grossesses[idx] = {};
        grossesses[idx][el.dataset.gkey] = el.value || null;
    });
    const validGross = grossesses.filter(g => g && Object.values(g).some(v => v));

    try {
        // Save case admin
        await api('/api/cases/' + caseId, { method: 'PUT', body: JSON.stringify(caseData) });
        // Save each module
        for (const [mod, data] of Object.entries(modules)) {
            await api('/api/cases/' + caseId + '/modules/' + mod, { method: 'PUT', body: JSON.stringify(data) });
        }
        // Save grossesses
        if (validGross.length || modules.atcd_obstetricaux) {
            await api('/api/cases/' + caseId + '/modules/atcd_obstetricaux', { method: 'PUT', body: JSON.stringify(validGross) });
        }
        // Show saved indicator
        const ind = document.getElementById('saveIndicator');
        if (ind) { ind.classList.add('visible'); setTimeout(() => ind.classList.remove('visible'), 2000); }

        // Refresh sidebar
        loadCases();
    } catch (e) {
        toast('Erreur sauvegarde: ' + e.message, 'error');
    }
}

// ── Macroscopie Panel (unified) ───────────────

function openViewerLames(rootPath, slidePath) {
    if (!state.viewerUrl) { toast('URL viewer non configurée', 'error'); return; }
    let url = state.viewerUrl + '/?';
    if (rootPath) url += 'root=' + encodeURIComponent(rootPath);
    if (slidePath) url += '&slide=' + encodeURIComponent(slidePath);
    window.open(url, '_blank');
}

function openViewerPhotos(caseId, macroPath) {
    // Viewer photos dédié
    let url = '/admin/viewer-photos?';
    if (caseId) url += 'case_id=' + caseId;
    else if (macroPath) url += 'path=' + encodeURIComponent(macroPath);
    window.open(url, '_blank');
}

function openViewerForCase(caseData) {
    // Ouvre les deux viewers si les deux paths sont définis
    const macroPath = caseData?.dossier_macro_path;
    const lamesPath = caseData?.dossier_lames_path;
    let opened = false;
    if (macroPath) {
        openViewerPhotos(caseData.id);
        opened = true;
    }
    if (lamesPath) {
        openViewerLames(lamesPath);
        opened = true;
    }
    if (!opened) toast('Aucun chemin photos/lames défini pour ce cas', 'error');
}

// ── CRUD actions ─────────────────────────────
function openNewCaseModal() {
    state.editingCaseId = null;
    document.getElementById('modalTitle').textContent = 'Nouveau cas';
    document.getElementById('btnSaveCase').textContent = 'Créer le cas';
    // Reset form
    ['f_numero','f_id_ext','f_nom_mere','f_prenom_mere','f_nom_naiss','f_ddn_mere',
     'f_prenom_foetus','f_sexe','f_terme','f_type_issue','f_date_deces','f_date_examen',
     'f_medecin','f_service','f_indication','f_macro_path','f_lames_path',
     'f_ville_maternite','f_date_reception','f_contexte_clinique',
     'f_ipp','f_ipp_fetus','f_ins','f_consanguinite'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('newCaseModal').classList.add('visible');
}

function editCase(id) {
    const c = state.cases.find(x => x.id === id) || state.currentCase;
    if (!c) return;
    state.editingCaseId = id;
    document.getElementById('modalTitle').textContent = 'Modifier ' + c.numero_dossier;
    document.getElementById('btnSaveCase').textContent = 'Enregistrer';

    const map = {
        f_numero: 'numero_dossier', f_id_ext: 'case_id_externe',
        f_nom_mere: 'nom_mere', f_prenom_mere: 'prenom_mere',
        f_nom_naiss: 'nom_naissance_mere', f_ddn_mere: 'ddn_mere',
        f_prenom_foetus: 'prenom_foetus', f_sexe: 'sexe',
        f_terme: 'terme_issue', f_type_issue: 'type_issue',
        f_date_deces: 'date_deces', f_date_examen: 'date_examen',
        f_medecin: 'medecin_referent', f_service: 'service_demandeur',
        f_indication: 'indication_examen',
        f_macro_path: 'dossier_macro_path', f_lames_path: 'dossier_lames_path',
        f_ville_maternite: 'ville_maternite',
        f_date_reception: 'date_reception',
        f_contexte_clinique: 'contexte_clinique',
        f_ipp: 'ipp', f_ipp_fetus: 'ipp_fetus',
        f_ins: 'ins', f_consanguinite: 'consanguinite',
    };
    for (const [elId, field] of Object.entries(map)) {
        const el = document.getElementById(elId);
        if (el) el.value = c[field] || '';
    }

    document.getElementById('newCaseModal').classList.add('visible');
}

async function saveCase() {
    const data = {
        numero_dossier: document.getElementById('f_numero').value.trim(),
        case_id_externe: document.getElementById('f_id_ext').value.trim() || null,
        nom_mere: document.getElementById('f_nom_mere').value.trim() || null,
        prenom_mere: document.getElementById('f_prenom_mere').value.trim() || null,
        nom_naissance_mere: document.getElementById('f_nom_naiss').value.trim() || null,
        ddn_mere: document.getElementById('f_ddn_mere').value || null,
        prenom_foetus: document.getElementById('f_prenom_foetus').value.trim() || null,
        sexe: document.getElementById('f_sexe').value || null,
        terme_issue: document.getElementById('f_terme').value.trim() || null,
        type_issue: document.getElementById('f_type_issue').value || null,
        date_deces: document.getElementById('f_date_deces').value || null,
        date_examen: document.getElementById('f_date_examen').value || null,
        medecin_referent: document.getElementById('f_medecin').value.trim() || null,
        service_demandeur: document.getElementById('f_service').value.trim() || null,
        indication_examen: document.getElementById('f_indication').value.trim() || null,
        dossier_macro_path: document.getElementById('f_macro_path').value.trim() || null,
        dossier_lames_path: document.getElementById('f_lames_path').value.trim() || null,
        ville_maternite: document.getElementById('f_ville_maternite').value.trim() || null,
        date_reception: document.getElementById('f_date_reception').value || null,
        contexte_clinique: document.getElementById('f_contexte_clinique').value.trim() || null,
        ipp: document.getElementById('f_ipp').value.trim() || null,
        ipp_fetus: document.getElementById('f_ipp_fetus').value.trim() || null,
        ins: document.getElementById('f_ins').value.trim() || null,
        consanguinite: document.getElementById('f_consanguinite').value || null,
    };

    if (!data.numero_dossier) {
        toast('Numéro de dossier requis', 'error');
        return;
    }

    try {
        if (state.editingCaseId) {
            await api('/api/cases/' + state.editingCaseId, { method: 'PUT', body: JSON.stringify(data) });
            toast('Cas mis à jour', 'success');
        } else {
            const res = await api('/api/cases', { method: 'POST', body: JSON.stringify(data) });
            if (res.error) { toast(res.error, 'error'); return; }
            toast('Cas créé', 'success');
        }
        closeModal('newCaseModal');
        await loadCases();
        if (state.editingCaseId) selectCase(state.editingCaseId);
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
    }
}

async function deleteCase(id) {
    if (!confirm('Supprimer ce cas et toutes ses données ? Cette action est irréversible.')) return;
    try {
        await api('/api/cases/' + id, { method: 'DELETE' });
        toast('Cas supprimé', 'success');
        state.currentCase = null;
        document.getElementById('mainTitle').textContent = 'Sélectionnez un cas';
        document.getElementById('mainActions').innerHTML = '';
        document.getElementById('mainBody').innerHTML = '<div class="empty-state"><h3>Cas supprimé</h3></div>';
        await loadCases();
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
    }
}

async function scanMacro(caseId) {
    try {
        const res = await api('/api/cases/' + caseId + '/scan-macro', { method: 'POST' });
        if (res.error) { toast(res.error, 'error'); return; }
        toast('Scan terminé : ' + res.folders.filter(f => f.exists).length + ' dossier(s) trouvé(s)', 'success');
        await selectCase(caseId);
    } catch (e) {
        toast('Erreur scan: ' + e.message, 'error');
    }
}

// ── Sync local ───────────────────────────────
async function syncLocal() {
    const btn = document.getElementById('btnSync');
    btn.disabled = true;
    toast('Scan du dossier local en cours...');
    try {
        const launch = await api('/api/sync', { method: 'POST', body: JSON.stringify({}) });
        if (launch.error) { toast(launch.error, 'error'); return; }
        const jobId = launch.job_id;
        const poll = () => new Promise((resolve, reject) => {
            const iv = setInterval(async () => {
                try {
                    const s = await api(`/api/sync/${jobId}`);
                    if (s.status === 'done') { clearInterval(iv); resolve(s.result); }
                    else if (s.status === 'error') { clearInterval(iv); reject(new Error(s.error)); }
                } catch (e) { clearInterval(iv); reject(e); }
            }, 2000);
        });
        const result = await poll();
        toast(result.message, 'success');
        await loadCases();
    } catch (e) {
        toast('Erreur scan: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

// ── Settings → moved to /admin/settings page ──

// ── Utils ────────────────────────────────────
function closeModal(id) { document.getElementById(id).classList.remove('visible'); }
function setFilter(el, val) {
    state.currentFilter = val;
    el.parentElement.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    loadCases();
}
function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;'); }
// Escape a path for safe embedding inside onclick="fn('...')" attributes
// Doubles backslashes and escapes single quotes so the JS parser doesn't eat them
function escPath(s) { return (s || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'"); }
let _searchTimer;
function debouncedSearch() { clearTimeout(_searchTimer); _searchTimer = setTimeout(loadCases, 300); }

// ── Keyboard ─────────────────────────────────
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.visible').forEach(m => m.classList.remove('visible'));
    }
});

// ── Biometrics compute ───────────────────────
async function saveTermeDetermine(caseId, val) {
    const sa = parseInt(val);
    const data = sa && sa >= 10 ? { sa } : null;
    if (data) {
        await api('/api/cases/' + caseId + '/modules/terme_determine', { method: 'PUT', body: JSON.stringify(data) });
    }
}

async function computeBiometrics(caseId) {
    const status = document.getElementById('computeStatus');
    status.textContent = 'Calcul en cours...';
    status.style.color = 'var(--warning)';
    try {
        const tdInput = document.getElementById('terme_determine_input');
        const tdVal = tdInput ? parseInt(tdInput.value) : null;
        const body = tdVal && tdVal >= 10 ? { terme_sa: tdVal } : {};
        const res = await api('/api/cases/' + caseId + '/compute', { method: 'POST', body: JSON.stringify(body) });
        if (res.error) { toast(res.error, 'error'); status.textContent = 'Erreur'; status.style.color = 'var(--danger)'; return; }
        const nAlerts = (res.results.alertes || []).length;
        toast(`Calcul terminé — ${nAlerts} alerte(s)`, 'success');
        status.textContent = 'Terminé';
        status.style.color = 'var(--success)';
        // Refresh
        await selectCase(caseId);
        // Switch to modules tab
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(t => t.classList.remove('active'));
        tabs[3]?.classList.add('active');
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.getElementById('panel-modules')?.classList.add('active');
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
        status.textContent = 'Erreur réseau';
        status.style.color = 'var(--danger)';
    }
}

// ── Themes ────────────────────────────────────
function setTheme(name) {
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('foetopath-theme', name);
    // Update picker active state
    document.querySelectorAll('.theme-option').forEach(el => {
        el.classList.toggle('active', el.dataset.theme === name);
    });
}

// Init theme from localStorage on page load
(function initTheme() {
    const saved = localStorage.getItem('foetopath-theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
})();

// Theme picker now on /admin/settings page

// ── Photo Lightbox ────────────────────────────
