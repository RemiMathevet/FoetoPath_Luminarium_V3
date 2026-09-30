// ═══════════════════════════════════════════════════════════════════
// Foekinator — Bayesian Diagnostic Engine
// Loads JSON databases from /admin/api/foekinator/
// ═══════════════════════════════════════════════════════════════════

const Foekinator = (function() {

const DEFAULT_PENETRANCE = 0.01;

let _hpoTerms = {};
let _diseases = [];
let _diseasesMap = [];
let _dbMeta = {};

async function loadDatabase(dbId) {
    const res = await fetch('/admin/api/foekinator/load?id=' + encodeURIComponent(dbId));
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    _dbMeta = data._meta || {};
    _hpoTerms = data.hpo_terms || {};
    _diseases = data.diseases || [];

    _diseasesMap = _diseases.map(d => {
        const pheno = {};
        (d.phenotypes || []).forEach(p => { pheno[p.hpo_id] = p.penetrance; });
        return {
            id: d.disease_id,
            name: d.disease_name,
            prevalence: d.prevalence || 0.001,
            phenotypes: pheno,
        };
    });

    return { meta: _dbMeta, diseasesCount: _diseasesMap.length, hpoCount: Object.keys(_hpoTerms).length };
}

function _computePost(diseases, present, absent) {
    const totalPrev = diseases.reduce((s, d) => s + d.prevalence, 0);
    let post = diseases.map(d => ({ ...d, ll: Math.log(d.prevalence / totalPrev) }));
    for (const hpo of present) {
        for (let i = 0; i < post.length; i++) {
            post[i].ll += Math.log(post[i].phenotypes[hpo] || DEFAULT_PENETRANCE);
        }
    }
    for (const hpo of absent) {
        for (let i = 0; i < post.length; i++) {
            post[i].ll += Math.log(1 - (post[i].phenotypes[hpo] || DEFAULT_PENETRANCE));
        }
    }
    const maxLL = Math.max(...post.map(p => p.ll));
    const exp = post.map(p => Math.exp(p.ll - maxLL));
    const sum = exp.reduce((s, e) => s + e, 0);
    return post.map((p, i) => ({
        id: p.id, name: p.name, probability: exp[i] / sum, phenotypes: p.phenotypes,
    })).sort((a, b) => b.probability - a.probability);
}

function computePosteriors(present, absent) {
    return _computePost(_diseasesMap, present, absent);
}

function entropy(probs) {
    let h = 0;
    for (const p of probs) { if (p > 1e-15) h -= p * Math.log2(p); }
    return h;
}

function suggestNextQuestions(present, absent, topN) {
    topN = topN || 6;
    const posteriors = computePosteriors(present, absent);
    const currentH = entropy(posteriors.map(p => p.probability));
    const already = new Set([...present, ...absent]);

    const candidates = new Set();
    for (const d of _diseasesMap) {
        for (const hpo of Object.keys(d.phenotypes)) {
            if (!already.has(hpo)) candidates.add(hpo);
        }
    }

    const scored = [];
    for (const hpo of candidates) {
        let pYes = 0;
        for (const p of posteriors) { pYes += p.probability * (p.phenotypes[hpo] || DEFAULT_PENETRANCE); }
        const hYes = entropy(_computePost(_diseasesMap, [...present, hpo], absent).map(p => p.probability));
        const hNo = entropy(_computePost(_diseasesMap, present, [...absent, hpo]).map(p => p.probability));
        scored.push({ hpo, infoGain: currentH - (pYes * hYes + (1 - pYes) * hNo), pYes });
    }

    scored.sort((a, b) => b.infoGain - a.infoGain);
    return scored.slice(0, topN);
}

function searchHPO(query, excludeSet) {
    if (!query || query.length < 2) return [];
    const q = query.toLowerCase();
    return Object.entries(_hpoTerms)
        .filter(([id, t]) => {
            if (excludeSet && excludeSet.has(id)) return false;
            const name = (t.name_fr || t.name || '').toLowerCase();
            return name.includes(q) || id.toLowerCase().includes(q);
        })
        .slice(0, 10)
        .map(([id, t]) => ({ id, name: t.name_fr || t.name || id }));
}

function getHPOName(hpoId) {
    const t = _hpoTerms[hpoId];
    return t ? (t.name_fr || t.name || hpoId) : hpoId;
}

function getMeta() { return _dbMeta; }
function getDiseasesCount() { return _diseasesMap.length; }
function getHPOCount() { return Object.keys(_hpoTerms).length; }

return {
    loadDatabase, computePosteriors, entropy, suggestNextQuestions,
    searchHPO, getHPOName, getMeta, getDiseasesCount, getHPOCount,
};
})();
