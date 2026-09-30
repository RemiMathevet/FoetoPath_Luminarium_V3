const foekState = { phase: 'input', signs: [], present: [], absent: [], additional: [], ranking: [], suggestions: [], dbLoaded: false, activeSearch: -1 };

async function renderFoekinatorPanel(c) {
    const el = document.getElementById('panel-foekinator');

    // Load database list
    let dbs = [];
    try {
        const res = await api('/api/foekinator/databases');
        dbs = res.databases || [];
    } catch(e) {}

    // Reset state
    foekState.phase = 'input';
    foekState.signs = [{ hpo: null, polarity: 'present', query: '' }, { hpo: null, polarity: 'present', query: '' }, { hpo: null, polarity: 'present', query: '' }];
    foekState.additional = [];
    foekState.ranking = [];
    foekState.suggestions = [];
    foekState.dbLoaded = false;
    foekState.activeSearch = -1;

    let html = `
    <div class="foek-card" style="border-color:var(--accent)">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <span style="font-size:22px">&#129504;</span>
            <div>
                <div style="font-size:15px;font-weight:600">Foekinator</div>
                <div style="font-size:11px;color:var(--text3)">Diagnostic phénotypique bayésien</div>
            </div>
            <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
                <select class="fselect" id="foekDbSelect" style="font-size:12px;min-width:200px" onchange="foekLoadDb(this.value)">
                    <option value="">Choisir une base...</option>
                    ${dbs.map(d => '<option value="' + d.id + '">' + escHtml(d.name) + ' (' + d.diseases_count + ' syndromes)</option>').join('')}
                </select>
                <span id="foekDbStatus" style="font-size:11px;color:var(--text3)"></span>
            </div>
        </div>
    </div>
    <div id="foekMain" style="display:none">
        <div class="foek-wrap">
            <div class="foek-left">
                <div class="foek-card" id="foekSignsCard"></div>
                <div class="foek-card" id="foekSuggestionsCard" style="display:none"></div>
                <div class="foek-card" id="foekObsCard" style="display:none"></div>
                <button class="btn" id="foekResetBtn" onclick="foekReset()" style="width:100%;display:none">Réinitialiser</button>
            </div>
            <div class="foek-right">
                <div class="foek-card" id="foekRankingCard">
                    <div class="foek-section-title">Hypothèses diagnostiques</div>
                    <div style="text-align:center;padding:40px 20px;color:var(--text3);font-size:13px">
                        <div style="font-size:32px;margin-bottom:10px;opacity:0.3">&#129516;</div>
                        Entrez au moins 2 signes cardinaux pour démarrer l'analyse
                    </div>
                </div>
            </div>
        </div>
    </div>`;

    el.innerHTML = html;

    // Auto-load first db if only one
    if (dbs.length === 1) {
        document.getElementById('foekDbSelect').value = dbs[0].id;
        foekLoadDb(dbs[0].id);
    }
}

async function foekLoadDb(dbId) {
    if (!dbId) return;
    const status = document.getElementById('foekDbStatus');
    status.textContent = 'Chargement...'; status.style.color = 'var(--warning)';
    try {
        const info = await Foekinator.loadDatabase(dbId);
        status.textContent = info.diseasesCount + ' syndromes · ' + info.hpoCount + ' termes HPO';
        status.style.color = 'var(--success)';
        foekState.dbLoaded = true;
        document.getElementById('foekMain').style.display = '';
        foekRenderSigns();
    } catch(e) {
        status.textContent = 'Erreur: ' + e.message; status.style.color = 'var(--danger)';
    }
}

function foekRenderSigns() {
    const card = document.getElementById('foekSignsCard');
    const isInput = foekState.phase === 'input';
    let html = '<div class="foek-section-title">' + (isInput ? 'Signes cardinaux (min. 2)' : foekState.signs.filter(s => s.hpo).length + ' signes initiaux') + '</div>';

    foekState.signs.forEach((sign, idx) => {
        const polCls = sign.polarity === 'present' ? 'present' : 'absent';
        const polChar = sign.polarity === 'present' ? '+' : '−';
        html += '<div class="foek-sign-row" id="foekSignRow' + idx + '">';
        html += '<div class="foek-pol-btn ' + polCls + '" onclick="foekTogglePol(' + idx + ')" ' + (!isInput ? 'style="pointer-events:none;opacity:0.6"' : '') + '>' + polChar + '</div>';
        html += '<input class="foek-search-input" value="' + escHtml(sign.query) + '" placeholder="Signe ' + (idx + 1) + '..." ' + (!isInput ? 'disabled' : '') + ' onfocus="foekState.activeSearch=' + idx + '" oninput="foekSearch(' + idx + ',this.value)" id="foekInput' + idx + '">';
        if (isInput && foekState.signs.length > 2) html += '<button class="btn btn-sm" onclick="foekRemoveSign(' + idx + ')" style="padding:4px 8px">×</button>';
        html += '</div>';
    });

    if (isInput) {
        html += '<div style="display:flex;gap:8px;margin-top:10px">';
        if (foekState.signs.length < 6) html += '<button class="btn btn-sm" onclick="foekAddSign()" style="border-style:dashed">+ Ajouter un signe</button>';
        const filled = foekState.signs.filter(s => s.hpo).length;
        html += '<button class="btn btn-primary btn-sm" style="flex:1" onclick="foekStartRefine()" ' + (filled < 2 ? 'disabled' : '') + '>Lancer l\'analyse (' + filled + ' signes)</button>';
        html += '</div>';
    }

    card.innerHTML = html;
}

function foekSearch(idx, query) {
    foekState.signs[idx].query = query;
    // Remove existing dropdown
    const old = document.getElementById('foekDrop' + idx);
    if (old) old.remove();

    if (query.length < 2) return;

    const exclude = new Set(foekState.signs.filter(s => s.hpo).map(s => s.hpo).concat(foekState.additional.map(o => o.hpo)));
    const results = Foekinator.searchHPO(query, exclude);
    if (!results.length) return;

    const row = document.getElementById('foekSignRow' + idx);
    let dd = '<div class="foek-dropdown" id="foekDrop' + idx + '">';
    results.forEach(r => {
        dd += '<div class="foek-dropdown-item" onclick="foekSelectHPO(' + idx + ',\'' + r.id + '\',\'' + escHtml(r.name).replace(/'/g, "\\'") + '\')">';
        dd += '<div>' + escHtml(r.name) + '</div><div class="foek-hpo-id">' + r.id + '</div></div>';
    });
    dd += '</div>';
    row.insertAdjacentHTML('beforeend', dd);

    // Close on click outside
    setTimeout(() => {
        document.addEventListener('click', function _cl(e) {
            const d = document.getElementById('foekDrop' + idx);
            if (d && !d.contains(e.target)) { d.remove(); document.removeEventListener('click', _cl); }
        });
    }, 50);
}

function foekSelectHPO(idx, hpoId, name) {
    foekState.signs[idx].hpo = hpoId;
    foekState.signs[idx].query = name;
    const d = document.getElementById('foekDrop' + idx);
    if (d) d.remove();
    foekRenderSigns();
    foekUpdateRanking();
}

function foekTogglePol(idx) {
    if (foekState.phase !== 'input') return;
    foekState.signs[idx].polarity = foekState.signs[idx].polarity === 'present' ? 'absent' : 'present';
    foekRenderSigns();
    foekUpdateRanking();
}

function foekAddSign() {
    if (foekState.signs.length < 6) {
        foekState.signs.push({ hpo: null, polarity: 'present', query: '' });
        foekRenderSigns();
    }
}

function foekRemoveSign(idx) {
    if (foekState.signs.length > 2) {
        foekState.signs.splice(idx, 1);
        foekRenderSigns();
        foekUpdateRanking();
    }
}

function foekStartRefine() {
    const filled = foekState.signs.filter(s => s.hpo).length;
    if (filled < 2) return;
    foekState.phase = 'refine';
    foekRenderSigns();
    foekUpdateRanking();
    document.getElementById('foekResetBtn').style.display = '';
}

function foekUpdateRanking() {
    const present = foekState.signs.filter(s => s.hpo && s.polarity === 'present').map(s => s.hpo)
        .concat(foekState.additional.filter(o => o.polarity === 'present').map(o => o.hpo));
    const absent = foekState.signs.filter(s => s.hpo && s.polarity === 'absent').map(s => s.hpo)
        .concat(foekState.additional.filter(o => o.polarity === 'absent').map(o => o.hpo));

    if (present.length + absent.length === 0) return;

    const ranking = Foekinator.computePosteriors(present, absent);
    foekState.ranking = ranking;

    // Render ranking
    const card = document.getElementById('foekRankingCard');
    const totalQ = present.length + absent.length;
    let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">';
    html += '<div class="foek-section-title" style="margin:0">Hypothèses diagnostiques</div>';
    html += '<span style="font-size:10px;font-family:var(--mono);color:var(--accent);padding:2px 8px;border-radius:10px;background:var(--accent-bg)">' + totalQ + ' obs.</span>';
    html += '</div>';

    if (ranking.length && ranking[0].probability > 0.01) {
        // Top candidate
        const top = ranking[0];
        html += '<div class="foek-rank-top">';
        html += '<div style="display:flex;justify-content:space-between;align-items:baseline">';
        html += '<div style="font-size:15px;font-weight:600;color:var(--warning)">' + escHtml(top.name) + '</div>';
        html += '<div style="font-size:18px;font-weight:700;font-family:var(--mono);color:var(--warning)">' + (top.probability * 100).toFixed(1) + '%</div>';
        html += '</div>';
        html += '<div style="font-size:10px;font-family:var(--mono);color:var(--text3);margin-top:4px">' + top.id + '</div>';
        // Matching phenotypes
        html += '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:3px">';
        present.filter(h => top.phenotypes[h]).forEach(h => {
            html += '<span class="foek-obs-tag pos">' + Foekinator.getHPOName(h) + ' (' + (top.phenotypes[h] * 100).toFixed(0) + '%)</span>';
        });
        absent.filter(h => top.phenotypes[h] && top.phenotypes[h] > 0.3).forEach(h => {
            html += '<span class="foek-obs-tag neg">¬' + Foekinator.getHPOName(h) + ' (pén ' + (top.phenotypes[h] * 100).toFixed(0) + '%)</span>';
        });
        html += '</div></div>';
    }

    // Rest of ranking
    ranking.slice(1, 12).forEach((d, i) => {
        const pct = d.probability * 100;
        if (pct < 0.1) return;
        const barW = ranking[0].probability > 0 ? Math.min(pct / ranking[0].probability * 100, 100) : 0;
        html += '<div class="foek-rank-item">';
        html += '<div class="foek-rank-num">' + (i + 2) + '</div>';
        html += '<div style="flex:1;min-width:0"><div style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escHtml(d.name) + '</div>';
        html += '<div class="foek-rank-bar"><div class="foek-rank-fill" style="width:' + barW + '%;background:' + (pct > 10 ? 'var(--accent)' : 'var(--text3)') + '"></div></div></div>';
        html += '<div style="font-size:12px;font-family:var(--mono);color:' + (pct > 10 ? 'var(--accent)' : 'var(--text3)') + ';font-weight:' + (pct > 10 ? '600' : '400') + ';min-width:46px;text-align:right">' + (pct >= 1 ? pct.toFixed(1) : pct.toFixed(2)) + '%</div>';
        html += '</div>';
    });

    // Entropy
    const h = Foekinator.entropy(ranking.map(r => r.probability));
    html += '<div style="margin-top:14px;padding:8px 10px;border-radius:6px;background:var(--bg);border:1px solid var(--border);font-size:10px;font-family:var(--mono);color:var(--text3);display:flex;justify-content:space-between">';
    html += '<span>Entropie résiduelle</span><span style="color:var(--accent)">' + h.toFixed(2) + ' bits</span></div>';

    card.innerHTML = html;

    // Suggestions (in refine phase)
    if (foekState.phase === 'refine') {
        const suggestions = Foekinator.suggestNextQuestions(present, absent, 6);
        foekState.suggestions = suggestions;
        foekRenderSuggestions(suggestions);
        foekRenderObsHistory();
    }
}

function foekRenderSuggestions(suggestions) {
    const card = document.getElementById('foekSuggestionsCard');
    if (!suggestions.length) { card.style.display = 'none'; return; }
    card.style.display = '';

    let html = '<div class="foek-section-title" style="color:var(--warning)">Questions discriminantes</div>';
    html += '<div style="font-size:10px;color:var(--text3);margin-bottom:8px">Classées par gain d\'information (Shannon)</div>';

    suggestions.forEach((s, i) => {
        const already = foekState.additional.some(o => o.hpo === s.hpo);
        if (already) return;
        const name = Foekinator.getHPOName(s.hpo);
        html += '<div class="foek-suggest' + (i === 0 ? ' top' : '') + '">';
        html += '<div style="flex:1"><div class="foek-suggest-name">' + escHtml(name) + '</div>';
        html += '<div class="foek-suggest-meta">IG=' + s.infoGain.toFixed(3) + ' bit · P(oui)=' + (s.pYes * 100).toFixed(0) + '%</div></div>';
        html += '<button class="foek-suggest-btn yes" onclick="foekAnswer(\'' + s.hpo + '\',\'present\')">Oui</button>';
        html += '<button class="foek-suggest-btn no" onclick="foekAnswer(\'' + s.hpo + '\',\'absent\')">Non</button>';
        html += '</div>';
    });

    card.innerHTML = html;
}

function foekAnswer(hpo, polarity) {
    foekState.additional.push({ hpo, polarity });
    foekUpdateRanking();
}

function foekRenderObsHistory() {
    const card = document.getElementById('foekObsCard');
    if (!foekState.additional.length) { card.style.display = 'none'; return; }
    card.style.display = '';

    let html = '<div class="foek-section-title">Observations ajoutées (' + foekState.additional.length + ')</div>';
    foekState.additional.forEach(obs => {
        const polChar = obs.polarity === 'present' ? '+' : '−';
        const polCol = obs.polarity === 'present' ? 'var(--success)' : 'var(--danger)';
        html += '<div style="display:flex;gap:6px;align-items:center;padding:3px 0;font-size:12px">';
        html += '<span style="color:' + polCol + ';font-weight:700;width:14px">' + polChar + '</span>';
        html += '<span>' + escHtml(Foekinator.getHPOName(obs.hpo)) + '</span></div>';
    });
    card.innerHTML = html;
}

function foekReset() {
    foekState.phase = 'input';
    foekState.signs = [{ hpo: null, polarity: 'present', query: '' }, { hpo: null, polarity: 'present', query: '' }, { hpo: null, polarity: 'present', query: '' }];
    foekState.additional = [];
    foekState.ranking = [];
    foekState.suggestions = [];
    document.getElementById('foekResetBtn').style.display = 'none';
    document.getElementById('foekSuggestionsCard').style.display = 'none';
    document.getElementById('foekObsCard').style.display = 'none';
    document.getElementById('foekRankingCard').innerHTML = '<div class="foek-section-title">Hypothèses diagnostiques</div><div style="text-align:center;padding:40px 20px;color:var(--text3);font-size:13px"><div style="font-size:32px;margin-bottom:10px;opacity:0.3">&#129516;</div>Entrez au moins 2 signes cardinaux pour démarrer l\'analyse</div>';
    foekRenderSigns();
}

// ── CR Panel ─────────────────────────────────
