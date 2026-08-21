/* ═══════════════════════════════════════════════════════════════════
   FoetoPath — admin_cr.js
   Onglet CR : génération Jinja2, export JSON LLM, Magos
   ═══════════════════════════════════════════════════════════════════ */

// ── Safe API wrapper (gère les réponses non-JSON / erreurs HTTP) ──
// window._crApiBase set by the host page: '/admin' (foetus) or '/placenta'
async function crApi(url, opts = {}) {
    const base = window._crApiBase || '/admin';
    const res = await fetch(base + url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
        throw new Error(`Réponse non-JSON (HTTP ${res.status})`);
    }
    const data = await res.json();
    if (!res.ok && data.error) throw new Error(data.error);
    if (!res.ok) throw new Error(`Erreur HTTP ${res.status}`);
    return data;
}

// ══════════════════════════════════════════════════════════════════
// Panel principal
// ══════════════════════════════════════════════════════════════════

async function renderCRPanel(c) {
    const el = document.getElementById('panel-cr');
    const caseId = c.id;

    // Charger les templates disponibles (fichier + utilisateur)
    let templates = [];
    let userTemplates = [];
    try {
        const [resFile, resUser] = await Promise.all([
            crApi('/api/cr/templates'),
            crApi('/api/cr/user-templates'),
        ]);
        templates = resFile.templates || [];
        userTemplates = resUser.templates || [];
    } catch (e) {
        try { if (!templates.length) { templates = (await crApi('/api/cr/templates')).templates || []; } } catch (_) {}
    }

    const lastCr = c.modules?.last_cr?.data || {};
    const lastLlm = c.modules?.last_cr_llm?.data || {};
    const lastSynd = c.modules?.last_cr_syndromique?.data || {};

    window._crCache = {
        cr_redige: lastLlm,
        syndromique: lastSynd,
    };

    el.innerHTML = `
    <!-- ════ Modèles utilisateur ════ -->
    <div class="card" id="card-user-templates" style="border-color:var(--accent)">
        <div style="font-size:12px;color:var(--text3)">Chargement...</div>
    </div>

    <!-- ════ Génération CR Jinja2 ════ -->
    <div class="card" style="border-color:var(--accent);margin-top:16px">
        <div class="card-title"><span class="icon">&#128196;</span> Génération de compte-rendu</div>

        <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px">
            <div class="ff" style="min-width:200px">
                <label class="flabel">Template</label>
                <select class="fselect" id="crTemplateSelect" onchange="crShowVersion()">
                    ${templates.map(t => `<option value="${t.id}" data-version="${t.version || '1.0.0'}" ${lastCr.template_id === t.id ? 'selected' : ''}>${t.label} (v${t.version || '1.0.0'})</option>`).join('')}
                    ${userTemplates.length ? '<option disabled>── Modèles utilisateur ──</option>' : ''}
                    ${userTemplates.map(t => `<option value="user:${t.id}" data-user="true">${escHtml(t.name)}</option>`).join('')}
                </select>
            </div>
            <button class="btn btn-primary btn-sm" onclick="generateCR(${caseId})">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                Générer le CR
            </button>
            <button class="btn btn-sm" onclick="crShowChangelog()" title="Historique des versions" style="border-color:var(--text3);color:var(--text3)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>
                Changelog
            </button>
            <span id="crStatus" style="font-size:11px;color:var(--text3)"></span>
        </div>

        <div id="crOutput" style="${lastCr.text ? '' : 'display:none'}">
            <div style="font-size:12px;font-weight:600;color:var(--success);margin-bottom:6px">CR généré</div>
            <div id="crText" style="background:var(--bg);padding:14px;border-radius:var(--radius);font-size:12px;max-height:500px;overflow:auto;color:var(--text);border:1px solid var(--border);line-height:1.6">${lastCr.html || (lastCr.text ? escHtml(lastCr.text) : '')}</div>
            <div style="display:flex;gap:8px;margin-top:8px">
                <button class="btn btn-sm" onclick="copyCRText()">Copier</button>
            </div>
        </div>
    </div>

    ${(window._crApiBase || '/admin') === '/admin' ? `<!-- ════ CARD 2 : Export JSON pour LLM ════ -->
    <div class="card" style="border-color:var(--success);margin-top:16px">
        <div class="card-title"><span class="icon">&#128230;</span> Export JSON concaténé pour LLM</div>
        <p style="font-size:12px;color:var(--text3);margin-bottom:8px">Concatène tous les modules du cas en suivant l'ordre narratif d'une autopsie fœtale, calcule les z-scores, enrichit chaque anomalie avec son code HPO, et exporte un fichier <code>cas_concat_llm.json</code> prêt pour le LLM.</p>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <button class="btn btn-sm" id="crBtnConcatOllama" style="border-color:var(--success);color:var(--success)" onclick="crExportConcatOllama(${caseId})">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Préparer pour LLM (v3)
            </button>
            <button class="btn btn-sm" style="border-color:var(--text3);color:var(--text3);font-size:11px" onclick="crExportConcatOllama(${caseId},'v2')" title="Format v2.2 (rétrocompatibilité)">v2</button>
            <button class="btn btn-sm" style="border-color:var(--text3);color:var(--text3);font-size:11px" onclick="crExportConcatOllama(${caseId},'v1')" title="Ancien format (rétrocompatibilité)">v1</button>
            <span id="crConcatStatus" style="font-size:11px;color:var(--text3)"></span>
        </div>
        <div id="crConcatResult" style="display:none;margin-top:12px">
            <div style="background:var(--bg);padding:12px;border-radius:var(--radius);font-size:12px;border:1px solid var(--border)">
                <div id="crConcatInfo" style="color:var(--text);line-height:1.6"></div>
            </div>
        </div>
    </div>` : ''}

    <!-- ════ CARD 3 : LLM (Magos) ════ -->
    <div class="card" style="border-color:var(--info);margin-top:16px">
        <div class="card-title"><span class="icon">&#129302;</span> LLM local (Magos)</div>
        <div style="display:inline-flex;align-items:center;gap:6px;background:var(--warning-bg, rgba(255,193,7,0.12));border:1px solid var(--warning, #ffc107);border-radius:var(--radius);padding:4px 10px;margin-bottom:12px;font-size:11px;color:var(--warning, #e6a700)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span><b>Research use only</b> — Le texte généré doit être relu et validé par le médecin.</span>
        </div>

        <div style="margin-bottom:14px">
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <button class="btn btn-sm" id="crBtnLlmConnect" onclick="crConnectLlm()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    Connecter Magos
                </button>
                <span id="crLlmUrl" style="font-size:11px;color:var(--text3)"></span>
                <span id="crLlmStatus" style="font-size:11px"></span>
            </div>
            <span style="font-size:10px;color:var(--text3);margin-top:3px;display:block">L'URL se configure dans <a href="/admin/settings" style="color:var(--accent)">Paramètres</a>.</span>
        </div>

        <div id="crLlmControls" style="display:none">
            <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px">
                <div class="ff" style="min-width:220px">
                    <label class="flabel">Modèle</label>
                    <select class="fselect" id="crLlmModelSelect">
                        <option value="">Connectez d'abord Magos</option>
                    </select>
                </div>
                ${(window._crApiBase || '/admin') === '/admin' ? `<div class="ff" style="min-width:260px">
                    <label class="flabel">Type de prompt</label>
                    <select class="fselect" id="crLlmPromptSelect">
                        <option value="cr_redige" selected>CR rédigé (reformulation prose médicale)</option>
                        <option value="syndromique">Discussion syndromique (orientation diagnostique)</option>
                    </select>
                </div>` : ''}
            </div>

            <div id="crLlmPromptInfo" style="font-size:11px;color:var(--text3);margin-bottom:12px;line-height:1.5"></div>

            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
                <button class="btn btn-sm" id="crBtnLlmGenerate" style="border-color:var(--info);color:var(--info)" onclick="crRunLlm(${caseId})">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5,3 19,12 5,21"/></svg>
                    Lancer le LLM
                </button>
                <span id="crLlmGenerateStatus" style="font-size:11px;color:var(--text3)"></span>
            </div>
        </div>

        <div id="crLlmOutput" style="display:none">
            <div id="crLlmCachedBadge" style="display:none;font-size:11px;color:var(--text3);margin-bottom:6px;padding:4px 8px;background:var(--bg);border:1px dashed var(--border);border-radius:var(--radius)"></div>
            <div id="crLlmThinking"></div>
            <div id="crLlmTextLabel" style="font-size:12px;font-weight:600;color:var(--info);margin-bottom:6px">Texte généré</div>
            <div id="crLlmText" style="background:var(--bg);padding:14px;border-radius:var(--radius);font-size:13px;max-height:500px;overflow:auto;color:var(--text);border:1px solid var(--border);line-height:1.7;white-space:pre-wrap"></div>
            <div style="display:flex;gap:8px;margin-top:8px">
                <button class="btn btn-sm" onclick="navigator.clipboard.writeText(document.getElementById('crLlmText').innerText);toast('Copié','success')">Copier</button>
                <button class="btn btn-sm" onclick="_crClearCached()" style="border-color:var(--text3);color:var(--text3)">Effacer ce résultat</button>
            </div>
        </div>
    </div>

    <!-- ════ Historique CR générés ════ -->
    <div class="card" id="card-docs-history" style="border-color:var(--text3);margin-top:16px">
        <div style="font-size:12px;color:var(--text3)">Chargement...</div>
    </div>
    `;

    // Init prompt info text
    _crUpdatePromptInfo();

    // Init user templates and docs history
    renderUserTemplatesCard(caseId);
    renderDocsHistory(caseId);
    const promptSel = document.getElementById('crLlmPromptSelect');
    if (promptSel) {
        promptSel.addEventListener('change', _crUpdatePromptInfo);
        promptSel.addEventListener('change', () => _crShowCached(promptSel.value));
    }

    // Afficher le résultat caché correspondant au prompt par défaut
    _crShowCached(promptSel ? promptSel.value : 'cr_redige');
}

// ── Affiche dans l'UI le résultat sauvegardé pour un type de prompt ──
function _crShowCached(promptType) {
    const cache = (window._crCache || {})[promptType] || {};
    const outputDiv = document.getElementById('crLlmOutput');
    const badge = document.getElementById('crLlmCachedBadge');
    const textEl = document.getElementById('crLlmText');
    const labelEl = document.getElementById('crLlmTextLabel');

    let text = '';
    if (promptType === 'cr_redige') {
        text = cache.text || '';
    } else if (promptType === 'syndromique') {
        if (cache.output_syndromique) {
            text = _formatSyndromique(cache.output_syndromique);
        } else if (cache.text) {
            text = cache.text;
        }
    }

    if (!text) {
        if (outputDiv) outputDiv.style.display = 'none';
        if (badge) badge.style.display = 'none';
        _crRenderThinking('');
        return;
    }

    if (badge) {
        const parts = [];
        parts.push('Dernier résultat sauvegardé');
        if (cache.model) parts.push('modèle : ' + cache.model);
        if (cache.tokens) parts.push(cache.tokens + ' tokens');
        if (cache.elapsed_s) parts.push(cache.elapsed_s + ' s');
        if (cache.generated_at) {
            try {
                const d = new Date(cache.generated_at);
                parts.push('généré le ' + d.toLocaleString('fr-FR'));
            } catch (e) {}
        }
        badge.textContent = parts.join(' · ') + ' — cliquez sur « Lancer le LLM » pour régénérer.';
        badge.style.display = '';
    }

    if (labelEl) {
        labelEl.textContent = (promptType === 'syndromique')
            ? 'Orientation syndromique' + (cache.model ? ' (' + cache.model + ')' : '')
            : 'Texte généré' + (cache.model ? ' (' + cache.model + ')' : '');
    }
    if (textEl) textEl.innerText = text;
    if (outputDiv) outputDiv.style.display = '';

    _crRenderThinking(cache.thinking || '');
}

function _crClearCached() {
    const sel = document.getElementById('crLlmPromptSelect');
    const type = sel ? sel.value : 'cr_redige';
    if (window._crCache) window._crCache[type] = {};
    _crShowCached(type);
    toast('Résultat masqué (le LLM reste sauvegardé en base tant qu\'il n\'est pas ré-exécuté)', 'info');
}

function _crUpdatePromptInfo() {
    const sel = document.getElementById('crLlmPromptSelect');
    const info = document.getElementById('crLlmPromptInfo');
    if (!sel || !info) return;
    if (sel.value === 'cr_redige') {
        info.innerHTML = 'Prend le CR Jinja2 généré ci-dessus et le reformule en prose médicale rédigée (paragraphes, tournures professionnelles). <b>Prérequis :</b> CR généré.';
    } else {
        info.innerHTML = 'Analyse le JSON v3 (brief HPO + z-scores + ratios) pour proposer des hypothèses syndromiques classées par vraisemblance. <b>Prérequis :</b> JSON exporté.';
    }
}


// ══════════════════════════════════════════════════════════════════
// CR Generation
// ══════════════════════════════════════════════════════════════════

async function generateCR(caseId) {
    const sel = document.getElementById('crTemplateSelect');
    const opt = sel.options[sel.selectedIndex];
    const isUser = opt && opt.dataset.user === 'true';
    const tplVal = sel.value;
    const status = document.getElementById('crStatus');
    status.textContent = 'Génération...';
    status.style.color = 'var(--warning)';

    try {
        let res;
        if (isUser) {
            const templateId = parseInt(tplVal.replace('user:', ''));
            res = await crApi(`/api/cases/${caseId}/cr/generate-user`, {
                method: 'POST', body: JSON.stringify({ template_id: templateId }),
            });
        } else {
            res = await crApi('/api/cases/' + caseId + '/cr/generate', {
                method: 'POST', body: JSON.stringify({ template_id: tplVal }),
            });
        }
        document.getElementById('crText').innerHTML = res.html || escHtml(res.text);
        document.getElementById('crOutput').style.display = '';
        status.textContent = 'CR généré';
        status.style.color = 'var(--success)';
        toast('CR généré', 'success');
        renderDocsHistory(caseId);
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
        status.textContent = 'Erreur';
        status.style.color = 'var(--danger)';
    }
}

function copyCRText() {
    const text = document.getElementById('crText').innerText;
    navigator.clipboard.writeText(text).then(() => toast('CR copié', 'success'));
}

function crShowVersion() {
    const sel = document.getElementById('crTemplateSelect');
    const opt = sel.options[sel.selectedIndex];
    if (!opt) return;
    if (opt.dataset.user === 'true') {
        toast(`Modèle utilisateur: ${opt.textContent}`, 'info');
    } else {
        toast(`Template v${opt.dataset.version || '?'}`, 'info');
    }
}


// ══════════════════════════════════════════════════════════════════
// Changelog modal
// ══════════════════════════════════════════════════════════════════

async function crShowChangelog() {
    const sel = document.getElementById('crTemplateSelect');
    const opt = sel.options[sel.selectedIndex];
    if (opt && opt.dataset.user === 'true') { toast('Pas de changelog pour les modèles utilisateur', 'info'); return; }
    const tplId = sel.value;
    try {
        const res = await crApi(`/api/cr/templates/${tplId}/changelog`);
        const entries = res.changelog || [];
        if (!entries.length) { toast('Pas de changelog', 'info'); return; }

        let html = `<div style="max-height:400px;overflow:auto;font-size:12px;line-height:1.6">`;
        entries.forEach(e => {
            html += `<div style="margin-bottom:12px">`;
            html += `<div style="font-weight:700;color:var(--accent)">v${escHtml(e.version)} <span style="font-weight:400;color:var(--text3)">(${escHtml(e.date)})</span></div>`;
            html += `<ul style="margin:4px 0 0 16px;padding:0">`;
            (e.changes || []).forEach(c => { html += `<li style="margin-bottom:2px">${escHtml(c)}</li>`; });
            html += `</ul></div>`;
        });
        html += `</div>`;

        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center';
        overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `<div style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;max-width:500px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.3)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <span style="font-weight:700;font-size:14px">Changelog — ${escHtml(tplId)}</span>
                <button class="btn btn-sm" onclick="this.closest('[style*=fixed]').remove()">✕</button>
            </div>
            ${html}
        </div>`;
        document.body.appendChild(overlay);
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
    }
}


// ══════════════════════════════════════════════════════════════════
// Export JSON concaténé
// ══════════════════════════════════════════════════════════════════

async function crExportConcatOllama(caseId, version) {
    const btn = document.getElementById('crBtnConcatOllama');
    const status = document.getElementById('crConcatStatus');
    const resultDiv = document.getElementById('crConcatResult');
    const infoDiv = document.getElementById('crConcatInfo');
    const ver = version || 'v3';
    const btnIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';

    btn.disabled = true;
    btn.textContent = 'Export en cours...';
    status.textContent = `Construction JSON ${ver}…`;
    status.style.color = 'var(--warning)';

    try {
        const res = await crApi('/api/cases/' + caseId + '/concat-ollama', {
            method: 'POST', body: JSON.stringify({ version: ver }),
        });

        status.textContent = `Exporté (${res.version})`;
        status.style.color = 'var(--success)';
        toast(`JSON ${res.version} exporté`, 'success');

        const sections = (res.sections || []).join(', ');
        infoDiv.innerHTML = `
            <div style="margin-bottom:4px"><b>Fichier :</b> <code style="font-size:11px">${escHtml(res.path)}</code></div>
            <div style="margin-bottom:4px"><b>Schema :</b> ${escHtml(res.version)}</div>
            <div style="margin-bottom:4px"><b>Codes HPO :</b> ${res.hpo_count}</div>
            <div style="margin-bottom:4px"><b>Z-scores :</b> ${res.has_zscores ? '✓ calculés' + (res.terme_sa ? ' (' + res.terme_sa + ' SA)' : '') : '✗ pas de terme disponible'}</div>
            ${sections ? '<div style="margin-bottom:4px"><b>Sections :</b> <span style="font-size:11px;color:var(--text3)">' + escHtml(sections) + '</span></div>' : ''}
        `;
        resultDiv.style.display = '';
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
        status.textContent = 'Erreur';
        status.style.color = 'var(--danger)';
    } finally {
        btn.disabled = false;
        btn.innerHTML = btnIcon + ' Préparer pour LLM (v3)';
    }
}


// ══════════════════════════════════════════════════════════════════
// LLM (Magos) : connexion
// ══════════════════════════════════════════════════════════════════

async function crConnectLlm() {
    const btn = document.getElementById('crBtnLlmConnect');
    const urlSpan = document.getElementById('crLlmUrl');
    const status = document.getElementById('crLlmStatus');
    const controls = document.getElementById('crLlmControls');
    const select = document.getElementById('crLlmModelSelect');

    btn.disabled = true;
    btn.textContent = 'Connexion...';
    status.textContent = '';
    status.style.color = 'var(--warning)';

    try {
        // LLM status is always under /admin (entity-independent)
        const res = await fetch('/admin/api/llm/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        }).then(r => r.json());

        if (!res.running) {
            status.textContent = res.error || 'Magos non joignable';
            status.style.color = 'var(--danger)';
            btn.disabled = false;
            btn.textContent = 'Connecter Magos';
            return;
        }

        if (res.url) {
            urlSpan.textContent = res.url;
            urlSpan.style.color = 'var(--success)';
        }

        const models = res.models || [];
        status.textContent = `En ligne — ${models.length} modèle(s)`;
        status.style.color = 'var(--success)';
        btn.textContent = '✓ Connecté';
        btn.style.borderColor = 'var(--success)';
        btn.style.color = 'var(--success)';

        if (!models.length) {
            select.innerHTML = '<option value="">Aucun modèle disponible</option>';
            select.disabled = true;
            controls.style.display = '';
            return;
        }

        select.innerHTML = models.map(m =>
            `<option value="${m.name}">${m.name}${m.loaded ? ' (chargé)' : ''}</option>`
        ).join('');
        select.disabled = false;
        controls.style.display = '';
    } catch (e) {
        status.textContent = e.message;
        status.style.color = 'var(--danger)';
        urlSpan.style.color = 'var(--danger)';
        btn.disabled = false;
        btn.textContent = 'Connecter Magos';
    }
}


// ══════════════════════════════════════════════════════════════════
// LLM (Magos) : lancement (selon le type de prompt choisi)
// ══════════════════════════════════════════════════════════════════

async function crRunLlm(caseId) {
    const model = document.getElementById('crLlmModelSelect').value;
    const promptType = document.getElementById('crLlmPromptSelect')?.value || 'cr_redige';
    const genBtn = document.getElementById('crBtnLlmGenerate');
    const status = document.getElementById('crLlmGenerateStatus');

    if (!model) { toast('Sélectionnez un modèle', 'error'); return; }

    genBtn.disabled = true;
    genBtn.textContent = 'Génération...';

    try {
        let resultText = '';
        let resultModel = model;
        let resultTokens = 0;
        let resultThinking = '';
        let syndRaw = null;
        let elapsedS = 0;

        if (promptType === 'cr_redige') {
            // ── Prompt CR rédigé : reformulation du CR Jinja2 ──
            const crText = document.getElementById('crText')?.innerText || '';
            if (!crText) {
                toast('Générez d\'abord un CR (card 1)', 'error');
                genBtn.disabled = false;
                genBtn.textContent = 'Lancer le LLM';
                return;
            }

            status.textContent = `Envoi du CR à ${model}...`;
            status.style.color = 'var(--info)';

            const res = await crApi('/api/cases/' + caseId + '/cr/llm', {
                method: 'POST',
                body: JSON.stringify({ text: crText, model }),
            });

            resultText = res.generated_text;
            resultModel = res.model;
            resultTokens = res.tokens || 0;
            resultThinking = res.thinking || '';

        } else {
            // ── Prompt syndromique : orientation diagnostique via pipeline passe 1 ──
            status.textContent = `Export JSON v3 + envoi à ${model}...`;
            status.style.color = 'var(--info)';

            const res = await crApi('/api/cases/' + caseId + '/llm-pipeline?passe=1', {
                method: 'POST',
                body: JSON.stringify({ config: { passe1: { model } } }),
            });

            // Formater la réponse syndromique en texte lisible
            const synd = res.output_syndromique || {};
            syndRaw = synd;
            resultText = _formatSyndromique(synd);
            resultModel = res.meta?.model || model;
            resultTokens = res.meta?.eval_count || 0;
            resultThinking = res.thinking || '';
            elapsedS = res.meta?.elapsed_s || 0;
        }

        // Mettre à jour le cache local pour pouvoir basculer entre les deux
        // types de prompt sans avoir à relancer le LLM.
        if (!window._crCache) window._crCache = {};
        if (promptType === 'cr_redige') {
            window._crCache.cr_redige = {
                text: resultText,
                thinking: resultThinking,
                model: resultModel,
                tokens: resultTokens,
                generated_at: new Date().toISOString(),
            };
        } else {
            window._crCache.syndromique = {
                output_syndromique: syndRaw,
                text: resultText,
                thinking: resultThinking,
                model: resultModel,
                tokens: resultTokens,
                elapsed_s: elapsedS,
                generated_at: new Date().toISOString(),
            };
        }

        // Rendu unifié (affiche texte, thinking et badge de cache)
        _crShowCached(promptType);

        status.textContent = `Terminé (${resultModel}, ${resultTokens} tokens)`;
        status.style.color = 'var(--success)';
        toast('Texte généré', 'success');

    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
        status.textContent = e.message;
        status.style.color = 'var(--danger)';
    } finally {
        genBtn.disabled = false;
        genBtn.textContent = 'Lancer le LLM';
    }
}


// ── Afficher le raisonnement (thinking) du modèle ──
function _crRenderThinking(thinking) {
    const container = document.getElementById('crLlmThinking');
    if (!container) return;
    if (!thinking || !thinking.trim()) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = `
        <details style="margin-bottom:12px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg)">
            <summary style="cursor:pointer;padding:10px 14px;font-size:12px;font-weight:600;color:var(--text3);user-select:none">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="vertical-align:-2px;margin-right:4px"><path d="M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z"/><line x1="9" y1="21" x2="15" y2="21"/></svg>
                Raisonnement du modèle (${thinking.split(/\s+/).length} mots)
            </summary>
            <div style="padding:10px 14px;font-size:11px;line-height:1.6;color:var(--text3);white-space:pre-wrap;max-height:400px;overflow:auto;border-top:1px solid var(--border)">${escHtml(thinking)}</div>
        </details>
    `;
}

// ── Formater l'output syndromique en texte lisible ──
function _formatSyndromique(synd) {
    let lines = [];
    lines.push('ORIENTATION SYNDROMIQUE');
    lines.push('='.repeat(40));
    lines.push('');

    const hypos = synd.hypotheses || [];
    if (hypos.length) {
        hypos.forEach((h, i) => {
            lines.push(`${i + 1}. ${h.syndrome || '?'}${h.omim ? ' (OMIM ' + h.omim + ')' : ''}`);
            lines.push(`   Confiance : ${h.confiance || '?'}`);
            if (h.arguments_pour) lines.push(`   Arguments pour : ${h.arguments_pour}`);
            if (h.arguments_contre) lines.push(`   Arguments contre : ${h.arguments_contre}`);
            if (h.hpo_concordants?.length) lines.push(`   HPO concordants : ${h.hpo_concordants.join(', ')}`);
            if (h.hpo_discordants?.length) lines.push(`   HPO discordants : ${h.hpo_discordants.join(', ')}`);
            if (h.hpo_manquants?.length) lines.push(`   HPO manquants : ${h.hpo_manquants.join(', ')}`);
            const ex = h.examens_a_rechercher || {};
            const exSections = [
                ['Histologie', ex.histologie],
                ['Radiologie', ex.radiologie],
                ['Examens complémentaires', ex.examen_complementaire],
                ['Macroscopie à revoir', ex.macroscopie_a_revoir],
            ].filter(([, v]) => Array.isArray(v) && v.length);
            if (exSections.length) {
                lines.push('   À rechercher activement :');
                exSections.forEach(([label, items]) => {
                    lines.push(`     • ${label} :`);
                    items.forEach(it => lines.push(`         - ${it}`));
                });
            }
            if (h.commentaire) lines.push(`   Note : ${h.commentaire}`);
            lines.push('');
        });
    } else {
        lines.push('Pas d\'hypothèse syndromique identifiée.');
        lines.push('');
    }

    const seqs = synd.sequences_identifiees || [];
    if (seqs.length) {
        lines.push('SÉQUENCES IDENTIFIÉES');
        lines.push('-'.repeat(30));
        seqs.forEach(s => {
            lines.push(`• ${s.sequence} — ${s.mecanisme || ''}`);
            if (s.signes_expliques?.length) lines.push(`  Signes expliqués : ${s.signes_expliques.join(', ')}`);
        });
        lines.push('');
    }

    const orphs = synd.anomalies_orphelines || [];
    if (orphs.length) {
        lines.push('ANOMALIES ORPHELINES');
        lines.push('-'.repeat(30));
        orphs.forEach(a => {
            lines.push(`• ${a.signe}${a.commentaire ? ' — ' + a.commentaire : ''}`);
        });
        lines.push('');
    }

    // Fallback si la réponse brute est un texte
    if (!hypos.length && !seqs.length && !orphs.length) {
        const raw = synd.raw_response || JSON.stringify(synd, null, 2);
        return raw;
    }

    return lines.join('\n');
}


// ══════════════════════════════════════════════════════════════════
// CR Template Editor — Modèles utilisateur
// ══════════════════════════════════════════════════════════════════

let _tplVarPalette = null;
let _tplEditorCaseId = null;

async function _tplLoadVars() {
    if (_tplVarPalette) return _tplVarPalette;
    try {
        const res = await crApi('/api/cr/template-variables');
        _tplVarPalette = res.variables || {};
    } catch (e) { console.error('_tplLoadVars error:', e); _tplVarPalette = {}; }
    return _tplVarPalette;
}

// ── Render user templates card ──
async function renderUserTemplatesCard(caseId) {
    _tplEditorCaseId = caseId;
    const card = document.getElementById('card-user-templates');
    if (!card) return;

    let templates = [];
    try {
        const res = await crApi('/api/cr/user-templates');
        templates = res.templates || [];
    } catch (e) {}

    let listHtml = '';
    if (!templates.length) {
        listHtml = '<div style="font-size:12px;color:var(--text3);padding:8px">Aucun modèle utilisateur.</div>';
    } else {
        templates.forEach(t => {
            listHtml += `
            <div class="tpl-list-item" data-id="${t.id}">
                <span class="tpl-name">${escHtml(t.name)}</span>
                <span class="tpl-type">${escHtml(t.type)}</span>
                <button class="btn btn-sm" onclick="tplEdit(${t.id})" title="Modifier" style="padding:2px 6px">✏️</button>
                <button class="btn btn-sm" onclick="tplDuplicate(${t.id})" title="Dupliquer" style="padding:2px 6px">📋</button>
                <button class="btn btn-sm" onclick="tplGenerate(${_tplEditorCaseId}, ${t.id})" title="Générer CR" style="padding:2px 6px;border-color:var(--success);color:var(--success)">▶</button>
                ${!t.is_default ? `<button class="btn btn-sm" onclick="tplDelete(${t.id})" title="Supprimer" style="padding:2px 6px;border-color:var(--danger);color:var(--danger)">✕</button>` : ''}
            </div>`;
        });
    }

    card.innerHTML = `
        <div class="card-title"><span class="icon">📝</span> Modèles utilisateur (templates CR)</div>
        <div id="tplList">${listHtml}</div>
        <div style="margin-top:10px;display:flex;gap:8px">
            <button class="btn btn-sm" style="border-color:var(--accent);color:var(--accent)" onclick="tplNew()">+ Nouveau modèle</button>
        </div>
        <span id="tplStatus" style="font-size:11px;color:var(--text3);margin-top:6px;display:block"></span>
    `;
}

// ── CRUD actions ──
async function tplNew() {
    _tplOpenEditor(null);
}

async function tplEdit(id) {
    try {
        const tpls = await crApi('/api/cr/user-templates');
        const tpl = (tpls.templates || []).find(t => t.id === id);
        if (!tpl) { toast('Modèle introuvable', 'error'); return; }
        _tplOpenEditor(tpl);
    } catch (e) { toast('Erreur: ' + e.message, 'error'); }
}

async function tplDuplicate(id) {
    try {
        await crApi(`/api/cr/user-templates/${id}/duplicate`, { method: 'POST' });
        toast('Modèle dupliqué', 'success');
        renderUserTemplatesCard(_tplEditorCaseId);
    } catch (e) { toast('Erreur: ' + e.message, 'error'); }
}

async function tplDelete(id) {
    if (!confirm('Supprimer ce modèle ?')) return;
    try {
        await crApi(`/api/cr/user-templates/${id}`, { method: 'DELETE' });
        toast('Modèle supprimé', 'success');
        renderUserTemplatesCard(_tplEditorCaseId);
    } catch (e) { toast('Erreur: ' + e.message, 'error'); }
}

async function tplGenerate(caseId, templateId) {
    const status = document.getElementById('tplStatus');
    if (status) { status.textContent = 'Génération...'; status.style.color = 'var(--warning)'; }
    try {
        const res = await crApi(`/api/cases/${caseId}/cr/generate-user`, {
            method: 'POST',
            body: JSON.stringify({ template_id: templateId }),
        });
        if (status) { status.textContent = 'CR généré'; status.style.color = 'var(--success)'; }
        toast('CR généré depuis modèle utilisateur', 'success');
        _tplShowGeneratedPreview(res.html, res.text, res.doc_id);
        renderDocsHistory(caseId);
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
        if (status) { status.textContent = 'Erreur'; status.style.color = 'var(--danger)'; }
    }
}

function _tplShowGeneratedPreview(html, text, docId) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center';
    overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
    overlay.innerHTML = `<div style="background:var(--card, var(--bg2));border:1px solid var(--border);border-radius:var(--radius);padding:20px;max-width:700px;width:95%;max-height:80vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span style="font-weight:700;font-size:14px;color:var(--success)">CR généré (doc #${docId || '?'})</span>
            <button class="btn btn-sm" onclick="this.closest('[style*=fixed]').remove()">✕</button>
        </div>
        <div style="background:var(--bg);padding:14px;border-radius:var(--radius);font-size:12px;line-height:1.7;border:1px solid var(--border);max-height:60vh;overflow:auto;color:var(--text)">${html}</div>
        <div style="display:flex;gap:8px;margin-top:10px">
            <button class="btn btn-sm" onclick="navigator.clipboard.writeText(${JSON.stringify(text)});toast('Texte copié','success')">Copier le texte</button>
        </div>
    </div>`;
    document.body.appendChild(overlay);
}

// ── Editor modal ──
async function _tplOpenEditor(tpl) {
    const vars = await _tplLoadVars();
    const isEdit = !!tpl;

    let paletteHtml = '';
    for (const [groupName, groupVars] of Object.entries(vars)) {
        paletteHtml += `<div class="tpl-var-group" data-group="${escHtml(groupName)}">
            <h4>${escHtml(groupName)}</h4>`;
        for (const [varId, varLabel] of groupVars) {
            paletteHtml += `<span class="tpl-var-bubble" data-var="${escHtml(varId)}" title="${escHtml(varLabel)}">${escHtml(varLabel)}</span>`;
        }
        paletteHtml += '</div>';
    }

    const overlay = document.createElement('div');
    overlay.id = 'tplEditorOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9998;display:flex;align-items:center;justify-content:center';

    overlay.innerHTML = `<div style="background:var(--card, var(--bg2));border:1px solid var(--border);border-radius:var(--radius-lg, var(--radius));padding:20px;width:95%;max-width:1000px;height:90vh;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,0.4)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-shrink:0">
            <span style="font-weight:700;font-size:15px">${isEdit ? 'Modifier' : 'Nouveau'} modèle</span>
            <button class="btn btn-sm" onclick="document.getElementById('tplEditorOverlay').remove()">✕</button>
        </div>
        <div style="display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap;flex-shrink:0">
            <div class="ff" style="flex:1;min-width:180px">
                <label class="flabel">Nom</label>
                <input class="finput" id="tplEdName" value="${isEdit ? escHtml(tpl.name) : ''}" placeholder="Mon modèle CR">
            </div>
            <div class="ff" style="min-width:140px">
                <label class="flabel">Type</label>
                <select class="fselect" id="tplEdType">
                    ${['soffoet','court','prescription','courrier','custom'].map(v => `<option value="${v}" ${isEdit && tpl.type === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
            </div>
        </div>
        <div class="tpl-workspace">
            <div class="tpl-palette">
                <div style="font-size:12px;color:var(--text3);margin-bottom:6px">Cliquez pour insérer au curseur</div>
                <input type="text" class="tpl-palette-filter" id="tplVarFilter" placeholder="Filtrer...">
                ${paletteHtml}
            </div>
            <div class="tpl-editor-area">
                <div class="tpl-toolbar">
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('bold')"><b>G</b></button>
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('italic')"><i>I</i></button>
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('underline')"><u>S</u></button>
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('formatBlock','h3')">H3</button>
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('insertUnorderedList')">Liste</button>
                    <button type="button" class="btn btn-sm" onclick="_tplCmd('insertHorizontalRule')">---</button>
                </div>
                <div id="tplVisualEditor" contenteditable="true" class="tpl-visual-editor"></div>
                <textarea id="tplHiddenJinja" style="display:none"></textarea>
            </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end;flex-shrink:0">
            <button class="btn btn-sm" onclick="_tplPreview()">Aperçu</button>
            <button class="btn btn-sm btn-primary" onclick="_tplSave(${isEdit ? tpl.id : 'null'})">${isEdit ? 'Enregistrer' : 'Créer'}</button>
            <button class="btn btn-sm" onclick="document.getElementById('tplEditorOverlay').remove()">Annuler</button>
        </div>
    </div>`;

    document.body.appendChild(overlay);

    // Init editor content
    const editorEl = document.getElementById('tplVisualEditor');
    const hiddenEl = document.getElementById('tplHiddenJinja');
    if (isEdit && tpl.content_jinja2) {
        hiddenEl.value = tpl.content_jinja2;
        _tplLoadEditorContent(editorEl, hiddenEl, vars);
    }

    // Palette filter
    document.getElementById('tplVarFilter').addEventListener('input', function() {
        const q = this.value.toLowerCase();
        overlay.querySelectorAll('.tpl-var-bubble').forEach(b => {
            const match = b.title.toLowerCase().includes(q) || b.dataset.var.toLowerCase().includes(q);
            b.style.display = match ? '' : 'none';
        });
        overlay.querySelectorAll('.tpl-var-group').forEach(g => {
            const visible = g.querySelectorAll('.tpl-var-bubble:not([style*="display: none"])');
            g.style.display = visible.length ? '' : 'none';
        });
    });

    // Palette click-to-insert
    overlay.querySelectorAll('.tpl-var-bubble').forEach(btn => {
        btn.addEventListener('mousedown', e => e.preventDefault());
        btn.addEventListener('click', e => {
            e.preventDefault();
            const tag = _tplMakeVarTag(btn.dataset.var, btn.title);
            _tplInsertAtCursor(editorEl, tag);
        });
    });
}

const _TPL_ZWS = '​';

function _tplCmd(cmd, val) {
    const ed = document.getElementById('tplVisualEditor');
    if (ed) ed.focus();
    document.execCommand(cmd, false, val || null);
}

function _tplMakeVarTag(varName, label) {
    const tag = document.createElement('span');
    tag.className = 'tpl-var-tag';
    tag.contentEditable = 'false';
    tag.dataset.var = varName;
    const txt = document.createElement('span');
    txt.className = 'tpl-var-tag-label';
    txt.textContent = label || varName;
    const btn = document.createElement('span');
    btn.className = 'tpl-var-tag-close';
    btn.textContent = '×';
    btn.addEventListener('mousedown', e => { e.preventDefault(); e.stopPropagation(); tag.remove(); });
    tag.appendChild(txt);
    tag.appendChild(btn);
    return tag;
}

function _tplMakeJinjaTag(code) {
    const tag = document.createElement('span');
    tag.className = 'tpl-jinja-block';
    tag.contentEditable = 'false';
    tag.dataset.jinja = code;
    const txt = document.createElement('span');
    txt.className = 'tpl-jinja-block-label';
    txt.textContent = code;
    const btn = document.createElement('span');
    btn.className = 'tpl-var-tag-close';
    btn.textContent = '×';
    btn.addEventListener('mousedown', e => { e.preventDefault(); e.stopPropagation(); tag.remove(); });
    tag.appendChild(txt);
    tag.appendChild(btn);
    return tag;
}

function _tplInsertAtCursor(editorEl, node) {
    editorEl.focus();
    const spacer = document.createTextNode(_TPL_ZWS);
    const sel = window.getSelection();
    if (sel.rangeCount > 0) {
        const range = sel.getRangeAt(0);
        if (!editorEl.contains(range.commonAncestorContainer)) {
            editorEl.appendChild(node);
            editorEl.appendChild(spacer);
        } else {
            range.deleteContents();
            range.insertNode(spacer);
            range.insertNode(node);
            range.setStartAfter(spacer);
            range.collapse(true);
            sel.removeAllRanges();
            sel.addRange(range);
        }
    } else {
        editorEl.appendChild(node);
        editorEl.appendChild(spacer);
    }
}

function _tplVarLabelFor(varName) {
    if (!_tplVarPalette) return varName;
    for (const vars of Object.values(_tplVarPalette)) {
        for (const [vid, vlabel] of vars) {
            if (vid === varName) return vlabel;
        }
    }
    return varName;
}

function _tplSyncToHidden() {
    const editor = document.getElementById('tplVisualEditor');
    const hidden = document.getElementById('tplHiddenJinja');
    if (!editor || !hidden) return;
    const clone = editor.cloneNode(true);
    clone.querySelectorAll('.tpl-var-tag').forEach(t => {
        t.parentNode.replaceChild(document.createTextNode('{{ ' + t.dataset.var + ' }}'), t);
    });
    clone.querySelectorAll('.tpl-jinja-block').forEach(t => {
        t.parentNode.replaceChild(document.createTextNode(t.dataset.jinja), t);
    });
    hidden.value = clone.innerHTML.replace(/​/g, '');
}

function _tplLoadEditorContent(editorEl, hiddenEl, vars) {
    let content = hiddenEl.value;
    content = content.replace(/\{\{\s*([\w.]+(?:\(\))?)\s*\}\}/g, (m, varName) => {
        const id = 'vtag_' + Math.random().toString(36).substr(2, 6);
        return `<span class="tpl-vtag-ph" id="${id}" data-var="${varName}"></span>`;
    });
    content = content.replace(/(\{%.*?%\})/g, (m) => {
        const id = 'jtag_' + Math.random().toString(36).substr(2, 6);
        return `<span class="tpl-jtag-ph" id="${id}" data-jinja="${m.replace(/"/g, '&quot;')}"></span>`;
    });
    editorEl.innerHTML = content;

    editorEl.querySelectorAll('.tpl-vtag-ph').forEach(ph => {
        const tag = _tplMakeVarTag(ph.dataset.var, _tplVarLabelFor(ph.dataset.var));
        ph.parentNode.replaceChild(tag, ph);
        if (!tag.nextSibling || (tag.nextSibling.nodeType === 3 && !tag.nextSibling.textContent.length)) {
            tag.parentNode.insertBefore(document.createTextNode(_TPL_ZWS), tag.nextSibling);
        }
    });
    editorEl.querySelectorAll('.tpl-jtag-ph').forEach(ph => {
        const code = ph.dataset.jinja.replace(/&quot;/g, '"');
        const tag = _tplMakeJinjaTag(code);
        ph.parentNode.replaceChild(tag, ph);
        if (!tag.nextSibling || (tag.nextSibling.nodeType === 3 && !tag.nextSibling.textContent.length)) {
            tag.parentNode.insertBefore(document.createTextNode(_TPL_ZWS), tag.nextSibling);
        }
    });
}

async function _tplSave(id) {
    _tplSyncToHidden();
    const name = document.getElementById('tplEdName').value.trim();
    const type = document.getElementById('tplEdType').value;
    const content = document.getElementById('tplHiddenJinja').value;
    if (!name) { toast('Nom requis', 'error'); return; }

    try {
        if (id) {
            await crApi(`/api/cr/user-templates/${id}`, {
                method: 'PUT',
                body: JSON.stringify({ name, type, content_jinja2: content }),
            });
            toast('Modèle mis à jour', 'success');
        } else {
            await crApi('/api/cr/user-templates', {
                method: 'POST',
                body: JSON.stringify({ name, type, content_jinja2: content }),
            });
            toast('Modèle créé', 'success');
        }
        const overlay = document.getElementById('tplEditorOverlay');
        if (overlay) overlay.remove();
        renderUserTemplatesCard(_tplEditorCaseId);
    } catch (e) { toast('Erreur: ' + e.message, 'error'); }
}

function _tplPreview() {
    _tplSyncToHidden();
    const html = document.getElementById('tplHiddenJinja').value;
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center';
    overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
    overlay.innerHTML = `<div style="background:var(--card, var(--bg2));border:1px solid var(--border);border-radius:var(--radius);padding:20px;max-width:700px;width:90%;max-height:80vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span style="font-weight:700;font-size:14px">Aperçu du template</span>
            <button class="btn btn-sm" onclick="this.closest('[style*=fixed]').remove()">✕</button>
        </div>
        <div style="background:var(--bg);padding:14px;border-radius:var(--radius);font-size:12px;line-height:1.6;border:1px solid var(--border);color:var(--text)">${html}</div>
    </div>`;
    document.body.appendChild(overlay);
}


// ══════════════════════════════════════════════════════════════════
// Documents générés — Historique
// ══════════════════════════════════════════════════════════════════

async function renderDocsHistory(caseId) {
    const card = document.getElementById('card-docs-history');
    if (!card) return;

    let docs = [];
    try {
        const res = await crApi(`/api/cases/${caseId}/cr/docs`);
        docs = res.docs || [];
    } catch (e) {}

    if (!docs.length) {
        card.innerHTML = `
            <div class="card-title"><span class="icon">📄</span> Historique des CR générés</div>
            <div style="font-size:12px;color:var(--text3);padding:8px">Aucun document généré.</div>`;
        return;
    }

    let listHtml = '';
    docs.forEach(d => {
        const date = d.generated_at ? new Date(d.generated_at).toLocaleString('fr-FR') : '?';
        const tplLabel = d.template_name || d.template_id || '?';
        listHtml += `
        <div class="tpl-list-item" id="doc-item-${d.id}">
            <span class="tpl-name">${escHtml(String(tplLabel))}</span>
            <span style="font-size:11px;color:var(--text3)">${escHtml(date)}</span>
            <button class="btn btn-sm _dv" data-did="${d.id}" title="Voir" style="padding:2px 6px;cursor:pointer">&#128065;</button>
            <button class="btn btn-sm _dd" data-did="${d.id}" title="Supprimer" style="padding:2px 6px;border-color:var(--danger);color:var(--danger);cursor:pointer">&#10005;</button>
        </div>`;
    });

    card.innerHTML = `
        <div class="card-title"><span class="icon">📄</span> Historique des CR générés</div>
        ${listHtml}`;

    _bindDocButtons(caseId);
}

function _bindDocButtons(caseId) {
    const card = document.getElementById('card-docs-history');
    if (!card) return;
    card.querySelectorAll('._dv').forEach(btn => {
        btn.onclick = function() {
            const docId = Number(this.dataset.did);
            crApi(`/api/cr/docs/${docId}`).then(doc => {
                const overlay = document.getElementById('cr-doc-overlay');
                if (overlay) overlay.remove();
                const ov = document.createElement('div');
                ov.id = 'cr-doc-overlay';
                ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center';
                ov.innerHTML = `<div style="background:var(--card, var(--bg2));border:1px solid var(--border);border-radius:var(--radius);padding:20px;max-width:700px;width:95%;max-height:80vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3)">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                        <span style="font-weight:700;font-size:14px">Document #${doc.id}</span>
                        <button class="btn btn-sm" id="cr-ov-close" style="padding:2px 8px;cursor:pointer">&#10005;</button>
                    </div>
                    <div style="font-size:11px;color:var(--text3);margin-bottom:8px">Généré le ${doc.generated_at ? new Date(doc.generated_at).toLocaleString('fr-FR') : '?'}</div>
                    <div style="background:var(--bg);padding:14px;border-radius:var(--radius);font-size:12px;line-height:1.7;border:1px solid var(--border);max-height:60vh;overflow:auto;color:var(--text)">${doc.content_html || escHtml(doc.content_text || '')}</div>
                    <div style="display:flex;gap:8px;margin-top:10px">
                        <button class="btn btn-sm" id="cr-ov-copy" style="cursor:pointer">Copier le texte</button>
                    </div>
                </div>`;
                document.body.appendChild(ov);
                document.getElementById('cr-ov-close').onclick = function() { ov.remove(); };
                document.getElementById('cr-ov-copy').onclick = function() {
                    navigator.clipboard.writeText(doc.content_text || '');
                    toast('Texte copié', 'success');
                };
                ov.onclick = function(ev) { if (ev.target === ov) ov.remove(); };
            }).catch(err => toast('Erreur: ' + err.message, 'error'));
        };
    });
    card.querySelectorAll('._dd').forEach(btn => {
        btn.onclick = function() {
            if (!confirm('Supprimer ce document ?')) return;
            const docId = Number(this.dataset.did);
            const row = document.getElementById('doc-item-' + docId);
            crApi(`/api/cr/docs/${docId}`, { method: 'DELETE' }).then(() => {
                if (row) row.remove();
                toast('Document supprimé', 'success');
            }).catch(err => toast('Erreur: ' + err.message, 'error'));
        };
    });
}

// ── Pairing (legacy, now integrated in Macroscopie) ──
