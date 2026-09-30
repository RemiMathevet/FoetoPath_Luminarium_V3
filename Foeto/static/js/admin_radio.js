var RADIO_CHITTY = null;
var RADIO_MATURATION = null;

// ── HPO mapping for radio chips & textareas (sourced from Foekinator Bone Dysplasias + hpo_mapping.js) ──
var RADIO_HPO_MAP = {
    // Chips → HPO (field → { chipValue → {code, term, term_fr} })
    chips: {
        'rad_thorax': {
            'En tonneau':   {code:'HP:0000774', term:'Narrow chest', term_fr:'Thorax etroit'},
            'Etroit':       {code:'HP:0000774', term:'Narrow chest', term_fr:'Thorax etroit'},
            'Asymetrique':  {code:'HP:0001555', term:'Asymmetry of the thorax', term_fr:'Asymetrie thoracique'}
        },
        'rad_vertebres': {
            'Fentes':                       {code:'HP:0003422', term:'Abnormal vertebral morphology', term_fr:'Anomalie vertebrale'},
            'Hemivertebres':                {code:'HP:0002937', term:'Hemivertebrae', term_fr:'Hemivertebre'},
            'Anomalie de segmentation':     {code:'HP:0003468', term:'Abnormal vertebral segmentation and fusion', term_fr:'Anomalie segmentation vertebrale'}
        },
        'rad_aspect_os': {
            'Demineralises':                    {code:'HP:0004349', term:'Decreased bone mineral density', term_fr:'Demineralisation osseuse'},
            'Fractures':                        {code:'HP:0002757', term:'Recurrent fractures', term_fr:'Fractures'},
            'Bandes claires metaphysaires':     {code:'HP:0003416', term:'Widened metaphyses', term_fr:'Metaphyses evasees'},
            'Incurves':                         {code:'HP:0006487', term:'Bowed long bones', term_fr:'Incurvation os longs'}
        }
    },
    // Textareas → keyword-to-HPO mapping (from Foekinator Bone Dysplasias database)
    textareaKeywords: [
        {kw:['fracture','cassure'],                      code:'HP:0002757', term:'Recurrent fractures', term_fr:'Fractures'},
        {kw:['demineralise','demineralisation','osteopenie'], code:'HP:0004349', term:'Decreased bone mineral density', term_fr:'Demineralisation osseuse'},
        {kw:['incurve','bowing','arque','incurvation'],  code:'HP:0006487', term:'Bowed long bones', term_fr:'Incurvation os longs'},
        {kw:['micromelie','micromele'],                  code:'HP:0002983', term:'Micromelia', term_fr:'Micromelie'},
        {kw:['rhizomelie','rhizomele'],                  code:'HP:0003026', term:'Rhizomelia', term_fr:'Rhizomelie'},
        {kw:['polydactylie'],                            code:'HP:0001161', term:'Polydactyly', term_fr:'Polydactylie postaxiale'},
        {kw:['syndactylie'],                             code:'HP:0001159', term:'Syndactyly', term_fr:'Syndactylie'},
        {kw:['brachydactylie'],                          code:'HP:0001156', term:'Brachydactyly', term_fr:'Brachydactylie'},
        {kw:['craniosynostose','craniostenose'],         code:'HP:0002676', term:'Craniosynostosis', term_fr:'Craniostenose'},
        {kw:['platyspondylie'],                          code:'HP:0000926', term:'Platyspondyly', term_fr:'Platyspondylie'},
        {kw:['arthrogrypose'],                           code:'HP:0002804', term:'Arthrogryposis multiplex congenita', term_fr:'Arthrogrypose'},
        {kw:['pied bot','talipes','varus equin'],        code:'HP:0001762', term:'Talipes equinovarus', term_fr:'Pied bot varus equin'},
        {kw:['aplasie radiale','absence radius','anomalie radiale'], code:'HP:0002973', term:'Abnormal forearm morphology', term_fr:'Anomalie radiale'},
        {kw:['agenese sacree','agénésie sacrée'],        code:'HP:0002827', term:'Abnormality of sacrum morphology', term_fr:'Defaut ossification sacrum'},
        {kw:['scoliose'],                                code:'HP:0002650', term:'Scoliosis', term_fr:'Scoliose'},
        {kw:['osteosclerose','osteocondensation'],       code:'HP:0011001', term:'Osteosclerosis', term_fr:'Osteosclerose'},
        {kw:['calcification','punctata','ponctuee'],     code:'HP:0002645', term:'Chondrodysplasia punctata', term_fr:'Calcifications ponctuees'},
        {kw:['dysostose','dysostosis'],                  code:'HP:0002652', term:'Dysostosis multiplex', term_fr:'Dysostose multiplex'},
        {kw:['luxation','dislocation'],                  code:'HP:0002999', term:'Congenital joint dislocation', term_fr:'Luxations articulaires congenitales'},
        {kw:['contracture'],                             code:'HP:0001371', term:'Flexion contracture', term_fr:'Contractures articulaires'},
        {kw:['hyperlaxite','hypermobilite'],              code:'HP:0001382', term:'Joint hypermobility', term_fr:'Hyperlaxite articulaire'},
        {kw:['anomalie costale','cotes surnumeraires','cotes absentes'], code:'HP:0000772', term:'Abnormal rib morphology', term_fr:'Anomalie costale'},
        {kw:['pectus','carinatum'],                      code:'HP:0000767', term:'Pectus carinatum', term_fr:'Pectus carinatum'},
        {kw:['os wormien'],                              code:'HP:0000689', term:'Wormian bones', term_fr:'Os wormiens'},
        {kw:['hypoplasie clavicule','clavicule hypoplasique'], code:'HP:0000885', term:'Hypoplastic clavicle', term_fr:'Hypoplasie claviculaire'},
        {kw:['iliaques petits','os iliaques'],           code:'HP:0003312', term:'Abnormally shaped iliac bones', term_fr:'Os iliaques petits/anormaux'},
        {kw:['maturation avancee','avance osseuse'],     code:'HP:0005257', term:'Advanced skeletal maturation', term_fr:'Maturation squelettique avancee'}
    ],
    // Textarea field IDs for keyword scanning
    textareaFields: ['rad_aspect', 'rad_vert_rem', 'rad_os_rem', 'rad_remarques'],
    // Z-score anomalies → HPO (auto-derived from biometry data)
    zscoreThresholds: {
        short: {code:'HP:0002983', term:'Micromelia', term_fr:'Micromelie'}  // Z < -2 (from Foekinator)
    }
};
var RADIO_BONES = [
    {key:'Humerus',label:'Humerus'},{key:'Radius',label:'Radius'},{key:'Ulna',label:'Ulna'},
    {key:'Femur',label:'Femur'},{key:'Tibia',label:'Tibia'},{key:'Fibula',label:'Fibula'},
    {key:'Piedradio',label:'Pied'}
];

function loadRadioRefTables() {
    if (RADIO_CHITTY && RADIO_MATURATION) return Promise.resolve();
    return Promise.all([
        fetch('/pwa/foet/Biometry_tables/ref_chitty_os_longs.json').then(r => r.json()),
        fetch('/pwa/foet/Biometry_tables/ref_maturation_osseuse.json').then(r => r.json())
    ]).then(([c, m]) => { RADIO_CHITTY = c; RADIO_MATURATION = m; });
}

// Helper: build a radio chip group (inline styles, no dependency on PWA css)
function _rChips(field, values, selected, multi) {
    return `<div data-field="${field}" style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 12px">${values.map(v =>
        `<button type="button" class="rad-chip${selected.includes(v) ? ' rad-sel' : ''}" data-v="${escHtml(v)}"
            onclick="${multi ? 'radioToggleChip(this)' : 'radioSelectChip(this)'}"
            style="padding:6px 14px;border-radius:16px;border:1px solid var(--border);background:${selected.includes(v)?'var(--accent-bg)':'var(--bg3)'};color:${selected.includes(v)?'var(--accent)':'var(--text2)'};font-size:12px;font-weight:500;cursor:pointer;transition:all .15s;white-space:nowrap">${escHtml(v)}</button>`
    ).join('')}</div>`;
}

function _rSectionTitle(text) {
    return `<div style="font-size:13px;font-weight:600;color:var(--accent);margin:20px 0 8px;padding-bottom:6px;border-bottom:1px solid var(--border)">${text}</div>`;
}

function _rLabel(text) {
    return `<label style="display:block;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">${text}</label>`;
}

function renderRadioPanel(c) {
    const el = document.getElementById('panel-radio');
    const caseId = c.id;
    const termeIssue = c.terme_issue || '';

    const radioMod = (c.modules || {}).radio;
    const rd = radioMod ? radioMod.data : null;

    const mf = (c.modules || {}).macro_frais;
    let autoSA = null, saSource = '';
    if (mf && mf.data && mf.data.terme && mf.data.terme.sa) {
        autoSA = mf.data.terme.sa; saSource = 'macro frais';
    } else if (termeIssue) {
        const m = String(termeIssue).match(/(\d+)/);
        if (m) { autoSA = parseInt(m[1]); saSource = 'dossier (' + termeIssue + ')'; }
    }

    const savedSA = rd && rd.terme ? rd.terme.sa : null;
    const savedJours = rd && rd.terme ? rd.terme.jours : 0;
    const displaySA = savedSA || autoSA || '';
    const displayJours = savedJours || 0;

    const thoraxSel = rd && rd.thorax_forme ? [rd.thorax_forme] : [];
    const vertSel = rd && rd.vertebres && rd.vertebres.aspects ? rd.vertebres.aspects : [];
    const osSel = rd && rd.aspect_os && rd.aspect_os.aspects ? rd.aspect_os.aspects : [];

    el.innerHTML = `
    <div style="max-width:820px">

        <!-- ── HEADER ── -->
        <div class="card">
            <div class="card-title"><span class="icon">&#128225;</span> Imagerie — Radiographies</div>
            ${saSource && !savedSA ? `<div style="font-size:12px;color:var(--accent);padding:8px 12px;background:var(--accent-bg);border-radius:var(--radius);margin-bottom:12px">Terme recupere depuis ${escHtml(saSource)} (SA ${autoSA}). Modifiable si besoin (MFIU, etc.).</div>` : ''}

            <div class="form-grid" style="margin-bottom:0">
                <div>
                    ${_rLabel('Terme (SA)')}
                    <input class="form-input" type="number" id="rad_sa" min="8" max="42" step="1" value="${displaySA}" placeholder="SA" oninput="radioRecalc();radioBuildMaturation()">
                </div>
                <div>
                    ${_rLabel('Jours')}
                    <input class="form-input" type="number" id="rad_jours" min="0" max="6" step="1" value="${displayJours}" placeholder="+j">
                </div>
            </div>
        </div>

        <!-- ── SQUELETTE ── -->
        <div class="card">
            <div class="card-title">Squelette</div>

            ${_rLabel('Aspect general')}
            <textarea class="form-input" id="rad_aspect" rows="2" placeholder="Aspect general du squelette..." style="margin-bottom:12px">${rd && rd.aspect_general ? escHtml(rd.aspect_general) : ''}</textarea>

            <div class="form-grid">
                <div>${_rLabel('Cotes droite')}<input class="form-input" type="number" id="rad_cotes_d" min="0" max="15" value="${rd && rd.cotes && rd.cotes.droite ? rd.cotes.droite : ''}" placeholder="12"></div>
                <div>${_rLabel('Cotes gauche')}<input class="form-input" type="number" id="rad_cotes_g" min="0" max="15" value="${rd && rd.cotes && rd.cotes.gauche ? rd.cotes.gauche : ''}" placeholder="12"></div>
            </div>

            ${_rLabel('Forme du thorax')}
            ${_rChips('rad_thorax', ['Normal','En tonneau','Etroit','Asymetrique'], thoraxSel, false)}

            ${_rLabel('Vertebres')}
            ${_rChips('rad_vertebres', ['Normales','Fentes','Hemivertebres','Anomalie de segmentation'], vertSel, true)}
            <textarea class="form-input" id="rad_vert_rem" rows="1" placeholder="Localisation, details..." style="margin-bottom:14px">${rd && rd.vertebres && rd.vertebres.remarques ? escHtml(rd.vertebres.remarques) : ''}</textarea>

            ${_rLabel('Aspect des os')}
            ${_rChips('rad_aspect_os', ['Normal','Demineralises','Fractures','Bandes claires metaphysaires','Incurves'], osSel, true)}
            <textarea class="form-input" id="rad_os_rem" rows="1" placeholder="Localisation des fractures, details...">${rd && rd.aspect_os && rd.aspect_os.remarques ? escHtml(rd.aspect_os.remarques) : ''}</textarea>
        </div>

        <!-- ── BIOMETRIES OSSEUSES ── -->
        <div class="card">
            <div class="card-title">Biometries osseuses</div>
            <div class="form-grid" style="margin-bottom:12px">
                <div>${_rLabel('BIP osseux (mm)')}<input class="form-input" type="number" id="rad_bip" step="0.1" value="${rd && rd.biometries && rd.biometries.bip_osseux_mm ? rd.biometries.bip_osseux_mm : ''}" placeholder="mm" oninput="radioRecalc()"></div>
                <div>${_rLabel('PC radio (mm)')}<input class="form-input" type="number" id="rad_pc" step="0.1" value="${rd && rd.biometries && rd.biometries.pc_radio_mm ? rd.biometries.pc_radio_mm : ''}" placeholder="mm" oninput="radioRecalc()"></div>
            </div>
            <div style="font-size:11px;color:var(--text3);margin-bottom:10px;font-style:italic">Os longs en mm — D et G. Z-score Chitty sur la moyenne.</div>
            <div style="overflow-x:auto">
                <table style="width:100%;border-collapse:collapse" id="rad_bones_table">
                    <thead><tr style="border-bottom:2px solid var(--border)">
                        <th style="text-align:left;padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.04em">Os</th>
                        <th style="padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;text-align:center">Droite</th>
                        <th style="padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;text-align:center">Gauche</th>
                        <th style="padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;text-align:center">Moy.</th>
                        <th style="padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;text-align:center">P50</th>
                        <th style="padding:8px 6px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;text-align:center">Z-score</th>
                    </tr></thead>
                    <tbody id="rad_bones_tbody"></tbody>
                </table>
            </div>
        </div>

        <!-- ── SCORES STATURAUX ── -->
        <div class="card">
            <div class="card-title">Scores staturaux</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div style="text-align:center;padding:16px;background:var(--bg3);border-radius:var(--radius-lg);border:1px solid var(--border)">
                    <div style="font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Hadlock (1984)</div>
                    <div style="font-size:1.6rem;font-weight:700;color:var(--warning);font-variant-numeric:tabular-nums" id="rad_hadlock">—</div>
                    <div style="font-size:10px;color:var(--text3);margin-top:4px;font-style:italic">11.38 + 0.07*(PC/10)*(F/10) + 0.98*(BIP/10)</div>
                </div>
                <div style="text-align:center;padding:16px;background:var(--bg3);border-radius:var(--radius-lg);border:1px solid var(--border)">
                    <div style="font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Adalian (2002)</div>
                    <div style="font-size:1.6rem;font-weight:700;color:var(--warning);font-variant-numeric:tabular-nums" id="rad_adalian">—</div>
                    <div style="font-size:10px;color:var(--text3);margin-top:4px;font-style:italic">0.434 * Femur + 6.93</div>
                </div>
            </div>
        </div>

        <!-- ── MATURATION OSSEUSE ── -->
        <div class="card">
            <div class="card-title">Maturation osseuse</div>
            <div style="display:flex;gap:14px;margin-bottom:10px;font-size:11px;color:var(--text3);flex-wrap:wrap">
                <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:3px;background:var(--success-bg);border:1px solid var(--success)"></span> Attendu au terme</span>
                <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:3px;background:var(--bg3);border:1px solid var(--border);opacity:.5"></span> Non attendu</span>
                <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:3px;background:var(--success)"></span> Present</span>
                <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:3px;background:var(--danger)"></span> Absent</span>
            </div>
            <div id="rad_maturation_grid" style="display:flex;flex-direction:column;gap:3px;max-height:450px;overflow-y:auto;padding-right:4px"></div>
        </div>

        <!-- ── REMARQUES ── -->
        <div class="card">
            <div class="card-title">Remarques</div>
            <textarea class="form-input" id="rad_remarques" rows="3" placeholder="Remarques complementaires...">${rd && rd.remarques ? escHtml(rd.remarques) : ''}</textarea>
        </div>

        <!-- ── HPO PREVIEW ── -->
        <div class="card">
            <div class="card-title" style="display:flex;align-items:center;gap:8px">
                <span>Codes HPO</span>
                <button class="btn btn-sm" onclick="radioRefreshHPO()" style="font-size:10px;padding:2px 8px">Actualiser</button>
                <span id="rad_hpo_count" style="font-size:11px;color:var(--text3);margin-left:auto">0 codes</span>
            </div>
            <div id="rad_hpo_preview" style="max-height:200px;overflow-y:auto;font-size:11px;color:var(--text3)">Cliquer sur Actualiser pour voir les codes HPO</div>
        </div>

        <!-- ── ACTIONS ── -->
        <div style="display:flex;gap:10px;margin-bottom:24px">
            <button class="btn btn-primary" onclick="radioSave(${caseId})">Enregistrer</button>
            <button class="btn" onclick="radioReset(${caseId})">Reinitialiser</button>
        </div>

    </div>`;

    loadRadioRefTables().then(() => {
        radioBuildBones(rd);
        radioBuildMaturation();
        radioRecalc();
        // Attach HPO autocomplete to textareas (must be called after DOM is built)
        adminInitHPOAutocomplete();
        // Restore HPO textarea selections from saved data
        if (rd && rd.hpo_codes && rd.hpo_codes.length) {
            // Restore tracked textarea selections
            rd.hpo_codes.filter(h => h.type === 'textarea_autocomplete').forEach(h => {
                if (h.source_field && !_radHpoTASelections[h.source_field]) _radHpoTASelections[h.source_field] = [];
                if (h.source_field) _radHpoTASelections[h.source_field].push({ code: h.code, term: h.term || '', item: h.source_value || '' });
            });
            radioShowHPO(rd.hpo_codes);
        }
    });
}

function radioBuildBones(rd) {
    const tbody = document.getElementById('rad_bones_tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const savedBones = rd && rd.biometries ? rd.biometries.os_longs || {} : {};
    RADIO_BONES.forEach(b => {
        const sv = savedBones[b.key] || {};
        const tr = document.createElement('tr');
        tr.style.cssText = 'border-bottom:1px solid var(--border)';
        tr.innerHTML = `
            <td style="padding:8px 6px;font-size:13px;font-weight:500;color:var(--text)">${b.label}</td>
            <td style="padding:6px 4px;text-align:center"><input class="form-input" style="width:68px;text-align:center;padding:6px 4px;font-family:var(--mono);font-size:13px" type="number" id="rad_${b.key}_d" step="0.1" value="${sv.droite != null ? sv.droite : ''}" oninput="radioRecalc()"></td>
            <td style="padding:6px 4px;text-align:center"><input class="form-input" style="width:68px;text-align:center;padding:6px 4px;font-family:var(--mono);font-size:13px" type="number" id="rad_${b.key}_g" step="0.1" value="${sv.gauche != null ? sv.gauche : ''}" oninput="radioRecalc()"></td>
            <td style="padding:8px 6px;text-align:center;font-family:var(--mono);font-size:13px;color:var(--text2)" id="rad_${b.key}_moy">—</td>
            <td style="padding:8px 6px;text-align:center;font-family:var(--mono);font-size:13px;color:var(--text3)" id="rad_${b.key}_p50">—</td>
            <td style="padding:8px 6px;text-align:center;font-family:var(--mono);font-size:13px;font-weight:700" id="rad_${b.key}_z">—</td>`;
        tbody.appendChild(tr);
    });
}

function radioBuildMaturation() {
    const grid = document.getElementById('rad_maturation_grid');
    if (!grid || !RADIO_MATURATION) return;
    // Preserve states if rebuilding
    const prevStates = {};
    grid.querySelectorAll('[data-idx]').forEach(el => { if (el.dataset.state !== 'null') prevStates[el.dataset.idx] = el.dataset.state; });

    grid.innerHTML = '';
    const sa = parseInt((document.getElementById('rad_sa') || {}).value) || null;

    // Also check saved data
    const radioMod = state.currentCase && state.currentCase.modules ? (state.currentCase.modules.radio || {}) : {};
    const rd = radioMod.data || null;
    const savedMat = rd && rd.maturation_osseuse ? rd.maturation_osseuse : [];
    const savedMap = {};
    savedMat.forEach(m => { savedMap[m.sa + '_' + m.label] = m.status; });

    RADIO_MATURATION.forEach((item, idx) => {
        const key = item.sa + '_' + item.label;
        const savedState = prevStates[String(idx)] || savedMap[key] || 'null';
        const isExpected = sa && item.sa <= sa;
        const isFuture = sa && item.sa > sa;

        const div = document.createElement('div');
        div.dataset.idx = idx;
        div.dataset.state = savedState;
        div.style.cssText = `display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:var(--radius);cursor:pointer;user-select:none;transition:all .15s;border:1px solid ${isExpected ? 'var(--success)' : 'transparent'};background:${isExpected ? 'var(--success-bg)' : 'var(--bg3)'};${isFuture ? 'opacity:.4;' : ''}`;

        const ck = document.createElement('div');
        ck.className = 'rad-mat-check';
        _rUpdateCheck(ck, savedState);
        div.appendChild(ck);

        const saSpan = document.createElement('span');
        saSpan.style.cssText = 'font-size:12px;font-weight:700;color:var(--accent);min-width:48px;font-variant-numeric:tabular-nums';
        saSpan.textContent = item.sa + ' SA';
        div.appendChild(saSpan);

        const labelSpan = document.createElement('span');
        labelSpan.style.cssText = 'font-size:12px;color:var(--text);flex:1';
        labelSpan.textContent = item.label;
        div.appendChild(labelSpan);

        div.onclick = function() {
            const s = this.dataset.state;
            const nk = this.querySelector('.rad-mat-check');
            if (s === 'null') { this.dataset.state = 'present'; _rUpdateCheck(nk, 'present'); }
            else if (s === 'present') { this.dataset.state = 'absent'; _rUpdateCheck(nk, 'absent'); }
            else { this.dataset.state = 'null'; _rUpdateCheck(nk, 'null'); }
        };
        grid.appendChild(div);
    });
}

function _rUpdateCheck(ck, state) {
    ck.style.cssText = 'width:20px;height:20px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;transition:all .15s;';
    if (state === 'present') { ck.style.cssText += 'background:var(--success);border:2px solid var(--success);color:#fff;'; ck.textContent = '\u2713'; }
    else if (state === 'absent') { ck.style.cssText += 'background:var(--danger);border:2px solid var(--danger);color:#fff;'; ck.textContent = '\u2717'; }
    else { ck.style.cssText += 'background:transparent;border:2px solid var(--border);color:transparent;'; ck.textContent = '\u2713'; }
}

function radioSelectChip(el) {
    el.parentElement.querySelectorAll('.rad-chip').forEach(c => {
        c.classList.remove('rad-sel');
        c.style.background = 'var(--bg3)'; c.style.color = 'var(--text2)'; c.style.borderColor = 'var(--border)';
    });
    el.classList.add('rad-sel');
    el.style.background = 'var(--accent-bg)'; el.style.color = 'var(--accent)'; el.style.borderColor = 'var(--accent)';
}

function radioToggleChip(el) {
    const wasSel = el.classList.contains('rad-sel');
    if (wasSel) {
        el.classList.remove('rad-sel');
        el.style.background = 'var(--bg3)'; el.style.color = 'var(--text2)'; el.style.borderColor = 'var(--border)';
    } else {
        el.classList.add('rad-sel');
        el.style.background = 'var(--accent-bg)'; el.style.color = 'var(--accent)'; el.style.borderColor = 'var(--accent)';
    }
    // Normal/Normales logic
    const group = el.parentElement;
    const txt = (el.getAttribute('data-v') || '').trim();
    const isNorm = txt === 'Normal' || txt === 'Normales';
    if (!wasSel) {
        if (isNorm) {
            group.querySelectorAll('.rad-chip').forEach(c => {
                if (c !== el) { c.classList.remove('rad-sel'); c.style.background='var(--bg3)'; c.style.color='var(--text2)'; c.style.borderColor='var(--border)'; }
            });
        } else {
            group.querySelectorAll('.rad-chip').forEach(c => {
                const cv = (c.getAttribute('data-v') || '').trim();
                if ((cv==='Normal'||cv==='Normales') && c!==el) { c.classList.remove('rad-sel'); c.style.background='var(--bg3)'; c.style.color='var(--text2)'; c.style.borderColor='var(--border)'; }
            });
        }
    }
}

function radioGetChips(field) {
    return Array.from(document.querySelectorAll(`[data-field="${field}"] .rad-chip.rad-sel`)).map(c => (c.getAttribute('data-v') || c.textContent).trim());
}

function radioRecalc() {
    if (!RADIO_CHITTY) return;
    const sa = parseInt(document.getElementById('rad_sa').value) || null;
    const ref = sa ? RADIO_CHITTY[String(sa)] : null;
    let femurMoy = null;

    RADIO_BONES.forEach(b => {
        const dv = parseFloat((document.getElementById('rad_'+b.key+'_d') || {}).value);
        const gv = parseFloat((document.getElementById('rad_'+b.key+'_g') || {}).value);
        let moy = null;
        if (!isNaN(dv) && !isNaN(gv)) moy = (dv + gv) / 2;
        else if (!isNaN(dv)) moy = dv;
        else if (!isNaN(gv)) moy = gv;

        const moyEl = document.getElementById('rad_'+b.key+'_moy');
        const p50El = document.getElementById('rad_'+b.key+'_p50');
        const zEl = document.getElementById('rad_'+b.key+'_z');
        if (!moyEl) return;

        moyEl.textContent = moy !== null ? moy.toFixed(1) : '—';
        if (ref && ref[b.key]) {
            p50El.textContent = ref[b.key].P50;
            if (moy !== null) {
                const z = (moy - ref[b.key].P50) / ref[b.key].SD;
                zEl.textContent = z.toFixed(2);
                zEl.style.color = Math.abs(z) <= 2 ? 'var(--success)' : Math.abs(z) <= 3 ? 'var(--warning)' : 'var(--danger)';
            } else { zEl.textContent = '—'; zEl.style.color = ''; }
        } else { p50El.textContent = '—'; zEl.textContent = '—'; zEl.style.color = ''; }
        if (b.key === 'Femur') femurMoy = moy;
    });

    // Scores
    const bip = parseFloat(document.getElementById('rad_bip').value);
    const pc = parseFloat(document.getElementById('rad_pc').value);
    const hEl = document.getElementById('rad_hadlock');
    const aEl = document.getElementById('rad_adalian');
    if (!isNaN(bip) && !isNaN(pc) && femurMoy !== null) {
        hEl.textContent = (11.38 + 0.07 * (pc/10) * (femurMoy/10) + 0.98 * (bip/10)).toFixed(1) + ' SA';
    } else { hEl.textContent = '—'; }
    if (femurMoy !== null) { aEl.textContent = (0.434 * femurMoy + 6.93).toFixed(1) + ' SA'; }
    else { aEl.textContent = '—'; }
}

// ── HPO collector for radio module ──
function radioCollectHPO(bones) {
    const findings = [];
    const seen = {};

    // 1. Collect from chip selections
    const chipMap = RADIO_HPO_MAP.chips;
    Object.keys(chipMap).forEach(field => {
        const selected = radioGetChips(field);
        selected.forEach(val => {
            const mapping = chipMap[field][val];
            if (mapping && !seen[mapping.code + '_' + field]) {
                findings.push({ code: mapping.code, term: mapping.term, term_fr: mapping.term_fr || '', source_field: field, source_value: val, type: 'chip', auto: true });
                seen[mapping.code + '_' + field] = true;
            }
        });
    });

    // 2. Collect from textarea content (keyword-based matching from Foekinator Bone Dysplasias)
    const kwList = RADIO_HPO_MAP.textareaKeywords;
    RADIO_HPO_MAP.textareaFields.forEach(taId => {
        const el = document.getElementById(taId);
        if (!el) return;
        const text = el.value.trim().toLowerCase();
        if (!text) return;
        kwList.forEach(({kw, code, term, term_fr}) => {
            if (kw.some(k => text.includes(k)) && !seen[code + '_' + taId]) {
                findings.push({ code, term, term_fr: term_fr || '', source_field: taId, source_value: text.substring(0, 80), type: 'textarea_keyword', auto: true });
                seen[code + '_' + taId] = true;
            }
        });
    });

    // 3. Collect from textarea HPO autocomplete selections
    Object.keys(_radHpoTASelections).forEach(taId => {
        const items = _radHpoTASelections[taId] || [];
        items.forEach(({code, term, item}) => {
            if (code && !seen[code + '_' + taId]) {
                findings.push({ code, term, term_fr: '', source_field: taId, source_value: item, type: 'textarea_autocomplete', auto: false });
                seen[code + '_' + taId] = true;
            }
        });
    });

    // 4. Collect from Z-score anomalies (bones with Z < -2 → micromelia)
    if (bones) {
        const thr = RADIO_HPO_MAP.zscoreThresholds;
        let hasShort = false;
        Object.keys(bones).forEach(bk => {
            const z = bones[bk].zscore_chitty;
            if (z !== null && z < -2) hasShort = true;
        });
        if (hasShort && !seen[thr.short.code + '_zscore']) {
            // Count affected bones for source detail
            const affected = Object.keys(bones).filter(bk => bones[bk].zscore_chitty !== null && bones[bk].zscore_chitty < -2);
            findings.push({ code: thr.short.code, term: thr.short.term, term_fr: thr.short.term_fr, source_field: 'biometries_zscore', source_value: affected.join(', ') + ' (Z < -2)', type: 'zscore', auto: true });
            seen[thr.short.code + '_zscore'] = true;
        }
    }

    return { findings: findings, source: 'admin_radio', timestamp: new Date().toISOString() };
}

function radioCollectData() {
    const sa = parseInt(document.getElementById('rad_sa').value) || null;
    const ref = sa && RADIO_CHITTY ? RADIO_CHITTY[String(sa)] : null;
    const bones = {};
    let femurMoy = null;

    RADIO_BONES.forEach(b => {
        const dv = parseFloat((document.getElementById('rad_'+b.key+'_d') || {}).value);
        const gv = parseFloat((document.getElementById('rad_'+b.key+'_g') || {}).value);
        let moy = null;
        if (!isNaN(dv) && !isNaN(gv)) moy = (dv+gv)/2;
        else if (!isNaN(dv)) moy = dv;
        else if (!isNaN(gv)) moy = gv;
        let zs = null;
        if (moy !== null && ref && ref[b.key]) zs = parseFloat(((moy - ref[b.key].P50) / ref[b.key].SD).toFixed(2));
        bones[b.key] = { droite: isNaN(dv)?null:dv, gauche: isNaN(gv)?null:gv, moyenne: moy !== null ? parseFloat(moy.toFixed(1)) : null, zscore_chitty: zs };
        if (b.key === 'Femur') femurMoy = moy;
    });

    const bip = parseFloat(document.getElementById('rad_bip').value);
    const pc = parseFloat(document.getElementById('rad_pc').value);
    let hadlock = null, adalian = null;
    if (!isNaN(bip) && !isNaN(pc) && femurMoy !== null) hadlock = parseFloat((11.38 + 0.07*(pc/10)*(femurMoy/10) + 0.98*(bip/10)).toFixed(1));
    if (femurMoy !== null) adalian = parseFloat((0.434*femurMoy+6.93).toFixed(1));

    const mat = [];
    document.querySelectorAll('#rad_maturation_grid > div').forEach(el => {
        if (el.dataset.state !== 'null' && RADIO_MATURATION) {
            const idx = parseInt(el.dataset.idx);
            mat.push({ sa: RADIO_MATURATION[idx].sa, label: RADIO_MATURATION[idx].label, status: el.dataset.state });
        }
    });

    // Collect HPO codes from chips, textareas and Z-score anomalies
    const hpo = radioCollectHPO(bones);

    return {
        type: 'imagerie_radio',
        terme: { sa: sa, jours: parseInt(document.getElementById('rad_jours').value) || 0 },
        aspect_general: document.getElementById('rad_aspect').value.trim() || null,
        cotes: { droite: parseInt(document.getElementById('rad_cotes_d').value) || null, gauche: parseInt(document.getElementById('rad_cotes_g').value) || null },
        thorax_forme: radioGetChips('rad_thorax')[0] || null,
        vertebres: { aspects: radioGetChips('rad_vertebres'), remarques: document.getElementById('rad_vert_rem').value.trim() || null },
        aspect_os: { aspects: radioGetChips('rad_aspect_os'), remarques: document.getElementById('rad_os_rem').value.trim() || null },
        biometries: { bip_osseux_mm: isNaN(bip)?null:bip, pc_radio_mm: isNaN(pc)?null:pc, os_longs: bones },
        scores_staturaux: { hadlock_sa: hadlock, adalian_sa: adalian },
        maturation_osseuse: mat,
        remarques: document.getElementById('rad_remarques').value.trim() || null,
        hpo_codes: hpo.findings.length ? hpo.findings : [],
        hpo_meta: { source: hpo.source, timestamp: hpo.timestamp }
    };
}

function radioSave(caseId) {
    const data = radioCollectData();
    fetch('/admin/api/cases/' + caseId + '/modules/radio', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => {
        if (r.ok) { toast('Radio enregistre', 'success'); if (state.currentCase) { if (!state.currentCase.modules) state.currentCase.modules = {}; state.currentCase.modules.radio = { data: data, updated_at: new Date().toISOString() }; } }
        else toast('Erreur sauvegarde radio', 'error');
    }).catch(() => toast('Erreur reseau', 'error'));
}

function radioReset(caseId) {
    if (!confirm('Reinitialiser le formulaire radio ?')) return;
    renderRadioPanel(state.currentCase);
}

// Live HPO preview in radio panel
function radioRefreshHPO() {
    const data = radioCollectData();
    radioShowHPO(data.hpo_codes || []);
}
function radioShowHPO(codes) {
    const container = document.getElementById('rad_hpo_preview');
    const counter = document.getElementById('rad_hpo_count');
    if (!container) return;
    counter.textContent = codes.length + ' code' + (codes.length !== 1 ? 's' : '');
    if (!codes.length) { container.innerHTML = '<span style="color:var(--text3);font-style:italic">Aucun code HPO detecte</span>'; return; }
    container.innerHTML = codes.map(h => {
        const typeColor = h.type === 'chip' ? 'var(--accent)' : h.type === 'zscore' ? 'var(--warning)' : 'var(--purple,#7c3aed)';
        const typeLabel = h.type === 'chip' ? 'chip' : h.type === 'zscore' ? 'Z-score' : 'texte';
        return `<div style="display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid var(--border)">
            <span style="font-family:var(--mono);color:var(--purple,#7c3aed);font-weight:600;font-size:11px;white-space:nowrap">${escHtml(h.code)}</span>
            <span style="font-size:11px;color:var(--text)">${escHtml(h.term_fr || h.term || '')}</span>
            <span style="font-size:9px;padding:1px 5px;border-radius:8px;background:${typeColor};color:#fff;white-space:nowrap;margin-left:auto">${typeLabel}</span>
        </div>`;
    }).join('');
}

// ══════════════════════════════════════════════════════════════
// GLOBAL HPO AUTOCOMPLETE ENGINE (all textareas — uses HPO_AUTOCOMPLETE from hpo_mapping.js)
// ══════════════════════════════════════════════════════════════

var _radHpoDropdown = null;
var _radHpoActiveTA = null;
var _radHpoTASelections = {};  // { textareaId: [{code, term, item}] }

// Known textarea → HPO section mappings (null = search all)
var ADMIN_HPO_TA_SECTIONS = {
    // Radio module
    'rad_aspect':   ['Os'],
    'rad_vert_rem': ['Os'],
    'rad_os_rem':   ['Os'],
    'rad_remarques': null,
    // Case form textareas
    'anomalies_suspectees': null,
    'anomalies_confirmees': null,
    'histoire_clinique': null,
    'atcd_medicaux': null,
    'ngs': null,
    'recherche_aneuploidie': null
};

function adminInitHPOAutocomplete() {
    if (typeof HPO_AUTOCOMPLETE === 'undefined') return;

    // Create dropdown once
    if (!_radHpoDropdown) {
        _radHpoDropdown = document.createElement('div');
        _radHpoDropdown.id = 'rad-hpo-dropdown';
        Object.assign(_radHpoDropdown.style, {
            display:'none', position:'fixed', zIndex:'9999',
            background:'var(--bg2,#fff)', border:'1px solid var(--border,#ddd)',
            borderRadius:'8px', overflowY:'auto', maxHeight:'220px',
            boxShadow:'0 8px 24px rgba(0,0,0,0.15)', fontSize:'12px'
        });
        document.body.appendChild(_radHpoDropdown);
        document.addEventListener('click', e => {
            if (_radHpoDropdown && !_radHpoDropdown.contains(e.target)) _radHpoDropdown.style.display = 'none';
        });
    }

    // Attach to ALL textareas on the page (by known ID or generic)
    document.querySelectorAll('textarea').forEach(el => {
        if (!el.id || el.dataset.hpoAttached) return;
        el.dataset.hpoAttached = '1';
        // Use known section mapping or default to null (search all)
        const sections = ADMIN_HPO_TA_SECTIONS.hasOwnProperty(el.id) ? ADMIN_HPO_TA_SECTIONS[el.id] : null;
        el.dataset.hpoSections = JSON.stringify(sections);
        if (!_radHpoTASelections[el.id]) _radHpoTASelections[el.id] = [];

        el.addEventListener('input', () => _radHpoHandleInput(el));
        el.addEventListener('focus', () => { _radHpoActiveTA = el; });
        el.addEventListener('keydown', e => {
            if (_radHpoDropdown.style.display === 'none') return;
            if (e.key === 'ArrowDown') { e.preventDefault(); _radHpoNav(1); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); _radHpoNav(-1); }
            else if (e.key === 'Enter') {
                const act = _radHpoDropdown.querySelector('.rad-hpo-item.active');
                if (act) { e.preventDefault(); act.click(); }
            } else if (e.key === 'Escape') { _radHpoDropdown.style.display = 'none'; }
        });
    });
}

function _radHpoHandleInput(el) {
    const val = el.value || '';
    const parts = val.split(/[,;]/);
    const lastPart = parts[parts.length - 1].trim().toLowerCase();
    if (lastPart.length < 2) { _radHpoDropdown.style.display = 'none'; return; }

    let sections = null;
    try { sections = JSON.parse(el.dataset.hpoSections); } catch(e) {}

    const matches = _radHpoSearch(lastPart, sections, 8);
    if (!matches.length) { _radHpoDropdown.style.display = 'none'; return; }

    _radHpoShowDropdown(el, matches, lastPart);
}

function _radHpoSearch(query, sections, max) {
    if (typeof HPO_AUTOCOMPLETE === 'undefined') return [];
    const results = [];
    for (let i = 0; i < HPO_AUTOCOMPLETE.length; i++) {
        const item = HPO_AUTOCOMPLETE[i];
        if (sections && sections.length) {
            if (!sections.includes(item.section)) continue;
        }
        let found = false;
        for (let j = 0; j < item.search.length; j++) {
            if (item.search[j].indexOf(query) >= 0) { found = true; break; }
        }
        // Also search in item name and alias
        if (!found && item.item && item.item.toLowerCase().indexOf(query) >= 0) found = true;
        if (!found && item.alias && item.alias.toLowerCase().indexOf(query) >= 0) found = true;
        if (found) {
            results.push(item);
            if (results.length >= max) break;
        }
    }
    return results;
}

function _radHpoShowDropdown(el, matches, query) {
    const rect = el.getBoundingClientRect();
    _radHpoDropdown.innerHTML = '';
    Object.assign(_radHpoDropdown.style, {
        display:'block', left: rect.left+'px', width: rect.width+'px'
    });
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow > 180) {
        _radHpoDropdown.style.top = (rect.bottom + 2) + 'px';
        _radHpoDropdown.style.bottom = 'auto';
        _radHpoDropdown.style.maxHeight = Math.min(spaceBelow - 10, 250) + 'px';
    } else {
        _radHpoDropdown.style.bottom = (window.innerHeight - rect.top + 2) + 'px';
        _radHpoDropdown.style.top = 'auto';
        _radHpoDropdown.style.maxHeight = Math.min(rect.top - 10, 250) + 'px';
    }

    matches.forEach((m, i) => {
        const div = document.createElement('div');
        div.className = 'rad-hpo-item' + (i === 0 ? ' active' : '');
        Object.assign(div.style, {
            padding:'8px 12px', cursor:'pointer', borderBottom:'1px solid var(--border,#eee)', transition:'background .1s'
        });
        div.addEventListener('mouseenter', () => {
            _radHpoDropdown.querySelectorAll('.rad-hpo-item').forEach(d => { d.classList.remove('active'); d.style.background=''; });
            div.classList.add('active'); div.style.background = 'var(--accent-bg,#f0f0ff)';
        });

        // Highlight match in item name
        let itemHtml = escHtml(m.item);
        const qi = m.item.toLowerCase().indexOf(query);
        if (qi >= 0) itemHtml = escHtml(m.item.substring(0, qi)) + '<strong style="color:var(--accent,#5b4fd6)">' + escHtml(m.item.substring(qi, qi + query.length)) + '</strong>' + escHtml(m.item.substring(qi + query.length));

        div.innerHTML = `<div style="font-size:12px;color:var(--text,#333);margin-bottom:1px">${itemHtml}</div>
            <div style="display:flex;gap:6px;align-items:center">
                <span style="font-family:var(--mono,monospace);font-size:10px;color:var(--purple,#7c3aed);font-weight:600">${m.hpo_code || ''}</span>
                <span style="font-size:10px;color:var(--text3,#999);font-style:italic">${escHtml(m.section || '')}</span>
                ${m.hpo_term ? '<span style="font-size:10px;color:var(--text3,#aaa)">' + escHtml(m.hpo_term) + '</span>' : ''}
            </div>`;

        div.addEventListener('click', () => _radHpoSelect(m));
        _radHpoDropdown.appendChild(div);
    });
}

function _radHpoSelect(match) {
    const el = _radHpoActiveTA;
    if (!el) return;

    // Replace the last segment (after comma/semicolon) with the selected item
    const val = el.value || '';
    const parts = val.split(/[,;]/);
    parts[parts.length - 1] = ' ' + match.item;
    el.value = parts.join(',').replace(/^[\s,]+/, '');

    // Track selection
    if (!_radHpoTASelections[el.id]) _radHpoTASelections[el.id] = [];
    const already = _radHpoTASelections[el.id].some(s => s.code === match.hpo_code);
    if (!already && match.hpo_code) {
        _radHpoTASelections[el.id].push({
            code: match.hpo_code,
            term: match.hpo_term || '',
            item: match.item
        });
    }

    _radHpoDropdown.style.display = 'none';

    // Show confirmation tag
    _radHpoShowTag(el, match);

    // Trigger input event
    el.dispatchEvent(new Event('input', { bubbles: true }));
}

function _radHpoShowTag(el, match) {
    if (!match.hpo_code) return;
    const tag = document.createElement('div');
    tag.textContent = match.hpo_code + ' \u2713';
    Object.assign(tag.style, {
        position:'fixed', background:'var(--success,#22c55e)', color:'#fff',
        padding:'3px 8px', borderRadius:'6px', fontSize:'11px', fontWeight:'600',
        pointerEvents:'none', zIndex:'10000', transition:'opacity 1.5s, transform 1.5s'
    });
    const rect = el.getBoundingClientRect();
    tag.style.left = (rect.right - 110) + 'px';
    tag.style.top = (rect.top - 22) + 'px';
    document.body.appendChild(tag);
    requestAnimationFrame(() => { tag.style.opacity = '0'; tag.style.transform = 'translateY(-12px)'; });
    setTimeout(() => { if (tag.parentNode) tag.parentNode.removeChild(tag); }, 1600);
}

function _radHpoNav(dir) {
    const items = _radHpoDropdown.querySelectorAll('.rad-hpo-item');
    if (!items.length) return;
    let idx = -1;
    items.forEach((it, i) => { if (it.classList.contains('active')) idx = i; });
    if (idx >= 0) { items[idx].classList.remove('active'); items[idx].style.background = ''; }
    let ni = idx + dir;
    if (ni < 0) ni = items.length - 1;
    if (ni >= items.length) ni = 0;
    items[ni].classList.add('active');
    items[ni].style.background = 'var(--accent-bg,#f0f0ff)';
    items[ni].scrollIntoView({ block: 'nearest' });
}

