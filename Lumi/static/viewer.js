// ── State ────────────────────────────────────────────────
let state = {
    root: '',
    cases: [],
    currentCase: null,
    slides: [],
    photos: [],
    currentSlideIndex: -1,
    currentPhotoIndex: -1,
    osdViewer: null,
    rotation: 0,
    viewMode: 'slide', // 'slide' or 'photo'
    labelVisible: false,
    // Annotation state
    editMode: 'nav',     // 'nav' | 'draw' | 'paint' — un seul outil arme le clic à la fois
    annMode: false,      // dérivé : le tracé à la main est armé
    annColor: '#e74c3c',
    annLevel: 0,  // 0=label lame, 1=région faible G, 2=histo moyen G
    annLabel: '',
    tissueType: '',
    annotations: [],     // [{points_px, color, label, note, level, id, created, tissue_type}, ...]
    annDrawing: false,
    annCurrentPath: [],
    annHighlighted: null, // id of highlighted annotation
    // Calibration
    mppX: 0,
    mppY: 0,
    objectivePower: 0,
    // Measurement tool
    measureMode: false,
    measurements: [],       // [{id, start:[x,y], end:[x,y], distUm}]
    measurePending: null,   // [x,y] first click waiting for second
    measureCursor: null,    // [x,y] current mouse pos for preview
    // Labellisation state
    labelOrgans: {},        // {organ: 'normal'|'patho'}
    labelDiagnoses: [],     // selected diagnosis IDs
    labelNote: '',
    labelSummary: {},       // {slide_id: 'labeled'|'unlabeled'}
    // Heatmap overlay (V1 : score sonde par patch, coord viewer)
    heatmap: null,          // {patch_side_l0, patches:[[x,y,score],...]}
    // Peinture de superpixels : géométrie de la vue courante, recalculée à chaque déplacement
    spMode: false,
    spGrid: false,          // grille en simple affichage, sans outil armé ni limite de champ
    spTiles: {},            // cache client : clé de tuile -> [{id, poly}]
    spPolys: [],            // superpixels des tuiles en vue, aplatis
    spBusy: false,
    spPending: false,
    spMsg: '',
};

// ── Helpers ──────────────────────────────────────────────
function toast(msg, isError = false) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.toggle('error', isError);
    el.classList.add('visible');
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove('visible'), 3500);
}
function setLoading(on) {
    document.getElementById('loadingOverlay').classList.toggle('visible', on);
}
// Base path for API calls — detects reverse proxy (e.g. /viewer/)
const _BASE = window.location.pathname.replace(/\/+$/, '').replace(/\/?$/, '');
function _url(path) { return _BASE + path; }

async function api(url, body) {
    const res = await fetch(_url(url), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    // Le serveur peut répondre du HTML : page de login quand la session a expiré, erreur du
    // tunnel s'il redémarre. res.json() remontait alors un « Unexpected token '<' » illisible.
    const txt = await res.text();
    try {
        return JSON.parse(txt);
    } catch {
        if (/<form[^>]*login|mot de passe/i.test(txt)) {
            return { error: 'Session expirée — recharge la page pour te reconnecter' };
        }
        return { error: `Réponse inattendue du serveur (HTTP ${res.status})` };
    }
}

// Keep-alive : rafraîchit la session hub (idle 8 min) pendant la lecture d'une
// lame sans chargement de tuile. Gate sur une interaction réelle depuis le
// dernier tick — un onglet abandonné ne ping plus et idle-out normalement, ce
// qui préserve l'auto-logout. Ne touche ni le cookie 2FA (4h) ni la session
// absolue (12h), volontairement. ponytail: réutilise /api/foeto/organs, pas
// d'endpoint dédié ; si idle_timeout_min descend <4, augmenter la fréquence.
let _kaInteracted = false;
['pointerdown', 'wheel', 'keydown', 'mousemove'].forEach(ev =>
    window.addEventListener(ev, () => { _kaInteracted = true; }, { passive: true }));
setInterval(() => {
    if (!_kaInteracted) return;
    _kaInteracted = false;
    fetch(_url('/api/foeto/organs'), { cache: 'no-store' }).catch(() => {});
}, 4 * 60 * 1000);

// ── OSD Creation Helper ──────────────────────────────────
function createOSD(tileSources) {
    if (state.osdViewer) { state.osdViewer.destroy(); state.osdViewer = null; }
    state.rotation = 0;
    state.osdViewer = OpenSeadragon({
        id: 'viewer',
        prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.1/images/',
        tileSources: tileSources,
        animationTime: 0.3,
        blendTime: 0.1,
        constrainDuringPan: false,
        maxZoomPixelRatio: 4,
        minZoomImageRatio: 0.5,
        visibilityRatio: 0.3,
        zoomPerScroll: 1.3,
        zoomPerClick: 2.0,
        showNavigator: true,
        navigatorPosition: 'BOTTOM_RIGHT',
        navigatorSizeRatio: 0.15,
        navigatorAutoFade: true,
        showNavigationControl: true,
        navigationControlAnchor: OpenSeadragon.ControlAnchor.TOP_LEFT,
        gestureSettingsMouse: { clickToZoom: true, dblClickToZoom: true },
        gestureSettingsTouch: { pinchToZoom: true },
        crossOriginPolicy: false,
        imageLoaderLimit: 6,
        timeout: 60000,
        degrees: 0,
        tabIndex: -1,
    });
    state.osdViewer.innerTracker.keyHandler = null;
    state.osdViewer.innerTracker.keyDownHandler = null;
    state.osdViewer.addHandler('open', () => { setLoading(false); updateZoomIndicator(); });
    state.osdViewer.addHandler('open-failed', () => {
        setLoading(false);
        toast('Erreur ouverture', true);
    });
    // Attach annotation re-render on viewport change
    annAttachViewportHandler();
    // Re-apply display filters (persist across slide switches)
    updateDisplayFilters();
    _makeNavMovable();
}

function _makeNavMovable() {
    const nav = state.osdViewer && state.osdViewer.navigator && state.osdViewer.navigator.element;
    if (!nav) return;
    Object.assign(nav.style, { resize: 'both', overflow: 'hidden', zIndex: 30 });
    new ResizeObserver(() => state.osdViewer.navigator.updateSize && state.osdViewer.navigator.updateSize()).observe(nav);
    // ponytail: Shift+drag to move — plain drag is reserved by OSD to pan via the mini-map
    let drag = false, sx, sy, ox, oy;
    nav.addEventListener('pointerdown', e => {
        if (!e.shiftKey) return;
        drag = true; sx = e.clientX; sy = e.clientY;
        const r = nav.getBoundingClientRect(); ox = r.left; oy = r.top;
        nav.setPointerCapture(e.pointerId); e.stopPropagation(); e.preventDefault();
    });
    nav.addEventListener('pointermove', e => {
        if (!drag) return;
        Object.assign(nav.style, { right: 'auto', bottom: 'auto', left: (ox + e.clientX - sx) + 'px', top: (oy + e.clientY - sy) + 'px' });
    });
    nav.addEventListener('pointerup', () => { drag = false; });
}

function updateZoomIndicator() {
    const el = document.getElementById('zoomIndicator');
    if (!state.osdViewer || !state.osdViewer.viewport || !state.osdViewer.world.getItemCount()) { el.textContent = ''; return; }
    const vp = state.osdViewer.viewport;
    const containerW = state.osdViewer.container.clientWidth;
    const tiledImage = state.osdViewer.world.getItemAt(0);
    const imageW = tiledImage.getContentSize().x;
    // OSD zoom = viewport-widths per image-width; convert to pixels ratio
    const pxRatio = vp.getZoom(true) * containerW / imageW;
    if (state.objectivePower > 0) {
        const mag = state.objectivePower * pxRatio;
        el.textContent = mag >= 1 ? `×${mag.toFixed(1)}` : `×${mag.toFixed(2)}`;
    } else {
        el.textContent = `${(pxRatio * 100).toFixed(0)}%`;
    }
}

// ── Load Cases ───────────────────────────────────────────
async function loadCases() {
    const root = document.getElementById('rootInput').value.trim();
    if (!root) { toast('Entrez un chemin de dossier', true); return; }
    state.root = root;
    const btn = document.getElementById('btnLoad');
    btn.textContent = '...'; btn.disabled = true;
    try {
        const data = await api('/api/browse', { root });
        if (data.error) { toast(data.error, true); return; }
        state.cases = data.cases;
        renderCaseList();
        document.getElementById('caseCount').textContent = data.cases.length;
        toast(data.cases.length === 0 ? 'Aucun cas trouvé' : `${data.cases.length} cas trouvé(s)`, data.cases.length === 0);
    } catch (e) {
        toast('Erreur réseau: ' + e.message, true);
    } finally {
        btn.textContent = 'Charger'; btn.disabled = false;
    }
}

// ── Render Case List ─────────────────────────────────────
function renderCaseList() {
    const el = document.getElementById('caseList');
    if (state.cases.length === 0) {
        el.innerHTML = '<div class="sidebar-empty">Aucun cas trouvé</div>';
        return;
    }
    el.innerHTML = state.cases.map((c, i) => {
        const parts = [];
        if (c.slide_count > 0) parts.push(`${c.slide_count} lame${c.slide_count > 1 ? 's' : ''}`);
        if (c.photo_count > 0) parts.push(`<span class="photo-count">${c.photo_count} photo${c.photo_count > 1 ? 's' : ''}</span>`);
        if (c.annotated_count > 0) parts.push(`${c.annotated_count} annotée${c.annotated_count > 1 ? 's' : ''}`);
        const doneIcon = c.annotated_count > 0 ? '<span style="color:var(--success);margin-right:4px;">&#10003;</span>' : '';
        return `
            <div class="case-item ${state.currentCase === i ? 'active' : ''}"
                 onclick="selectCase(${i})" title="${c.path}">
                <div class="case-item-name">${doneIcon}${c.is_root ? '&#128194; ' : ''}${c.name}</div>
                <div class="case-item-counts">${parts.join(' &middot; ')}</div>
            </div>`;
    }).join('');
}

// ── Select Case ──────────────────────────────────────────
async function selectCase(index) {
    state.currentCase = index;
    state.currentSlideIndex = -1;
    state.currentPhotoIndex = -1;
    state.viewMode = 'slide';
    closeLabel();
    renderCaseList();
    document.getElementById('welcomeScreen').classList.add('hidden');
    const caseData = state.cases[index];
    setLoading(true);
    try {
        const data = await api('/api/slides', { folder: caseData.path, root: state.root });
        state.slides = data.slides || [];
        state.photos = data.photos || [];
        renderCarousel();
        loadCaseIndex();
        // Load label summary for carousel badges
        fetch(_url(`/api/slides/label-summary?folder=${encodeURIComponent(caseData.path)}`))
            .then(r => r.json())
            .then(data => {
                state.labelSummary = data.statuses || {};
                renderCarousel();
            })
            .catch(() => {});
        if (state._autoSlide && state.slides.length > 0) {
            const idx = state.slides.findIndex(s => s.path === state._autoSlide || s.path.endsWith(state._autoSlide.split('/').pop()));
            loadSlide(idx >= 0 ? idx : 0);
            delete state._autoSlide;
        } else if (state.slides.length > 0) {
            loadSlide(0);
        } else if (state.photos.length > 0) {
            loadPhoto(0);
        } else {
            if (state.osdViewer) { state.osdViewer.destroy(); state.osdViewer = null; }
            document.getElementById('slideMeta').textContent = '';
            setLoading(false);
        }
    } catch (e) {
        toast('Erreur chargement: ' + e.message, true);
        setLoading(false);
    }
}

// ── Case index (left column: slides → labels + annotations) ──
async function loadCaseIndex() {
    if (state.currentCase == null || !state.cases[state.currentCase]) return;
    const folder = state.cases[state.currentCase].path;
    try {
        const r = await fetch(_url('/api/case/index?folder=' + encodeURIComponent(folder)));
        state.caseIndexData = (await r.json()).slides || {};
    } catch (e) { state.caseIndexData = {}; }
    renderCaseIndex();
}

function renderCaseIndex() {
    const el = document.getElementById('caseIndex');
    if (!el) return;
    const data = state.caseIndexData || {};
    const orgLbl = o => _LABELS[o] || o;
    el.innerHTML = state.slides.map((s, i) => {
        const d = data[s.name] || {};
        const active = (state.viewMode === 'slide' && i === state.currentSlideIndex) ? 'active' : '';
        const normals = (d.organs || []).filter(o => o.status === 'normal');
        const labels = d.labels || [];
        const anns = (d.annotations || []).filter(a => !a.class_id || !a.class_id.startsWith('STRUCT:'));
        let lines = '';
        if (normals.length || labels.length) {
            lines += '<div class="ci-sub">Labels</div>';
            lines += normals.map(o => `<div class="ci-label normal">${orgLbl(o.organ)} — normal</div>`).join('');
            lines += labels.map(l => {
                const org = l.organ ? orgLbl(l.organ) + ' — ' : '';
                const g = l.grade ? ` (G${l.grade})` : '';
                return `<div class="ci-label patho" title="${org}${l.label}${g}">${org}${l.label}${g}</div>`;
            }).join('');
        }
        if (anns.length) {
            lines += '<div class="ci-sub ci-sub2">Annotations</div>';
            lines += anns.map(a => `<div class="ci-ann" title="${a.label}"><span class="ci-swatch" style="background:${a.color || '#888'}"></span>${a.label}</div>`).join('');
        }
        return `<div class="ci-slide ${active}">
            <div class="ci-name" onclick="loadSlide(${i})" title="${s.name}">${s.name}</div>${lines}
        </div>`;
    }).join('') || '<div class="sidebar-empty">Aucune lame</div>';
}

function toggleCaseIndex() {
    const sb = document.querySelector('.sidebar');
    const rh = document.querySelector('.resize-handle');
    const hide = sb.style.display !== 'none';
    sb.style.display = hide ? 'none' : '';
    if (rh) rh.style.display = hide ? 'none' : '';
    const btn = document.getElementById('btnIndex');
    if (btn) btn.classList.toggle('active', !hide);
    if (state.osdViewer) setTimeout(() => state.osdViewer.viewport.resize(), 60);
}

// ── Render Carousel ──────────────────────────────────────
function renderCarousel() {
    const el = document.getElementById('carousel');
    const hasSlides = state.slides.length > 0;
    const hasPhotos = state.photos.length > 0;
    const showSlideRow = hasSlides && (state.slides.length > 1 || hasPhotos);

    if (!showSlideRow && !hasPhotos) { el.classList.remove('visible'); return; }
    el.classList.add('visible');
    let html = '';

    if (showSlideRow) {
        html += '<div class="carousel-section-label slide-label">&#128300; Lames (' + state.slides.length + ')</div><div class="carousel-scroll">';
        html += state.slides.map((s, i) => {
            const labeledClass = state.labelSummary[s.name] === 'labeled' ? 'labeled' : '';
            return `
            <div class="carousel-item slide-item ${state.viewMode === 'slide' && i === state.currentSlideIndex ? 'active' : ''} ${labeledClass}"
                 onclick="loadSlide(${i})" title="${s.name}">
                <img src="${_BASE}/api/slide/thumbnail?path=${encodeURIComponent(s.path)}&w=160&h=160" alt="${s.name}" loading="lazy">
                <div class="carousel-item-label">${s.name}</div>
            </div>`;
        }).join('');
        html += '</div>';
    }
    if (hasPhotos) {
        html += '<div class="carousel-section-label photo-label">&#128247; Photos (' + state.photos.length + ')</div><div class="carousel-scroll">';
        html += state.photos.map((p, i) => `
            <div class="carousel-item photo-item ${state.viewMode === 'photo' && i === state.currentPhotoIndex ? 'active' : ''}"
                 onclick="loadPhoto(${i})" title="${p.filename} (${p.size_kb} KB)">
                <img src="${_BASE}/api/photo/thumbnail?path=${encodeURIComponent(p.path)}&w=160&h=160" alt="${p.name}" loading="lazy">
                <div class="carousel-item-label">${p.filename}</div>
            </div>`).join('');
        html += '</div>';
    }
    el.innerHTML = html;

    requestAnimationFrame(() => {
        const active = el.querySelector('.carousel-item.active');
        if (active) active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    });
}

// ── Load Slide (OpenSlide DZI) ───────────────────────────
async function loadSlide(index) {
    if (index < 0 || index >= state.slides.length) return;
    state.currentSlideIndex = index;
    state.viewMode = 'slide';
    state.currentPhotoIndex = -1;
    closeLabel();
    const slide = state.slides[index];

    setLoading(true);
    renderCarousel();
    document.getElementById('shortcutsHint').classList.add('visible');
    document.getElementById('viewBadge').classList.remove('visible');
    document.getElementById('btnLabel').classList.add('visible');
    renderCaseIndex();

    // Reset annotation and measure mode on slide switch
    if (document.getElementById('annPanel').classList.contains('visible')) closePanelRight();
    if (state.measureMode) toggleMeasureMode();
    state.measurements = [];
    state.mppX = 0;
    state.mppY = 0;
    state.heatmap = null;
    document.getElementById('btnHeatmap').classList.remove('active');
    document.getElementById('heatmapSelect').style.display = 'none';

    try {
        const info = await api('/api/slide/info', { path: slide.path });
        if (info.dimensions) {
            const [w, h] = info.dimensions;
            const mpx = ((w * h) / 1e6).toFixed(1);
            state.mppX = info.mpp_x || 0;
            state.mppY = info.mpp_y || 0;
            state.objectivePower = info.objective_power || 0;
            const mppStr = state.mppX > 0 ? `  \u00b7  ${state.mppX.toFixed(3)} \u00b5m/px` : '';
            document.getElementById('slideMeta').textContent =
                `${slide.name}  \u00b7  ${w.toLocaleString()} \u00d7 ${h.toLocaleString()} px  \u00b7  ${mpx} Mpx${mppStr}`;
            // Populate export level dropdown
            annPopulateLevels(info);
        }
    } catch (e) {}

    const tileSource = {
        getTileUrl: function(level, x, y) {
            // Tuiles natives : CHROMA est appliqué client-side (feColorMatrix), pas server-side.
            return `${_BASE}/api/slide/tile/${level}/${x}_${y}.jpeg?path=${encodeURIComponent(slide.path)}`;
        },
        height: null, width: null, tileSize: 254, tileOverlap: 1, minLevel: 0, maxLevel: null,
    };
    try {
        const dziRes = await fetch(_url('/api/slide/dzi'), {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: slide.path }),
        });
        const xml = new DOMParser().parseFromString(await dziRes.text(), 'application/xml');
        const image = xml.querySelector('Image'), size = xml.querySelector('Size');
        if (image && size) {
            tileSource.width = parseInt(size.getAttribute('Width'));
            tileSource.height = parseInt(size.getAttribute('Height'));
            tileSource.tileSize = parseInt(image.getAttribute('TileSize'));
            tileSource.tileOverlap = parseInt(image.getAttribute('Overlap'));
            tileSource.maxLevel = Math.ceil(Math.log2(Math.max(tileSource.width, tileSource.height)));
        }
    } catch (e) { toast('Erreur DZI: ' + e.message, true); setLoading(false); return; }

    createOSD(tileSource);

    // Load existing annotations for this slide
    annLoad(slide.path);

    // Load labellisation status for this slide
    labelLoad(slide.name);
}

// ── Load Photo (in OSD as simple image) ──────────────────
function loadPhoto(index) {
    if (index < 0 || index >= state.photos.length) return;
    state.currentPhotoIndex = index;
    state.viewMode = 'photo';
    state.currentSlideIndex = -1;
    closeLabel();
    const photo = state.photos[index];

    setLoading(true);
    renderCarousel();
    document.getElementById('shortcutsHint').classList.add('visible');
    document.getElementById('viewBadge').classList.add('visible');
    document.getElementById('btnLabel').classList.remove('visible');
    document.getElementById('slideMeta').textContent =
        `${photo.filename}  \u00b7  ${photo.size_kb} KB`;

    createOSD({
        type: 'image',
        url: `${_BASE}/api/photo/serve?path=${encodeURIComponent(photo.path)}`,
    });
}

// ── Navigate prev/next in current mode ───────────────────
function navPrev() {
    if (state.viewMode === 'slide') loadSlide(state.currentSlideIndex - 1);
    else loadPhoto(state.currentPhotoIndex - 1);
}
function navNext() {
    if (state.viewMode === 'slide') loadSlide(state.currentSlideIndex + 1);
    else loadPhoto(state.currentPhotoIndex + 1);
}

// ── Label ────────────────────────────────────────────────
function toggleLabel() {
    if (state.labelVisible) { closeLabel(); return; }
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const slide = state.slides[state.currentSlideIndex];
    const img = document.getElementById('labelPopupImg');
    const popup = document.getElementById('labelPopup');

    // Reset macro annotation state for new image
    macroAnnState.active = false;
    macroAnnState.drawing = false;
    macroAnnState.currentPath = [];
    macroAnnState.annotations = [];
    macroAnnState.imgNaturalW = 0;
    macroAnnState.imgNaturalH = 0;
    document.getElementById('btnMacroAnnotate').classList.remove('active');
    document.getElementById('macroAnnToolbar').classList.remove('visible');
    document.getElementById('macroAnnCanvas').classList.remove('drawing');
    macroAnnUpdateCount();

    // When image loads, capture natural dimensions, resize canvas, and load existing annotations
    img.onload = function() {
        macroAnnState.imgNaturalW = img.naturalWidth;
        macroAnnState.imgNaturalH = img.naturalHeight;
        macroAnnResizeCanvas();
        macroAnnRender();
        // Load existing macro annotations
        macroAnnLoad(slide.path);
        // Also fetch macro info from backend for accurate dimensions
        fetch(`${_BASE}/api/slide/macro/info?path=${encodeURIComponent(slide.path)}`)
            .then(r => r.json())
            .then(data => {
                if (data.width && data.height) {
                    macroAnnState.imgNaturalW = data.width;
                    macroAnnState.imgNaturalH = data.height;
                    macroAnnState.macroType = data.type || 'macro';
                }
            })
            .catch(() => {});
    };

    // Try label first, fallback to macro
    img.onerror = function() {
        img.onerror = function() {
            toast('Pas d\'étiquette disponible pour cette lame', true);
            popup.classList.remove('visible');
            state.labelVisible = false;
        };
        img.src = `${_BASE}/api/slide/label?path=${encodeURIComponent(slide.path)}&type=macro`;
        document.getElementById('labelPopupTitle').textContent = 'Macro — ' + slide.name;
    };
    img.src = `${_BASE}/api/slide/label?path=${encodeURIComponent(slide.path)}&type=label`;
    document.getElementById('labelPopupTitle').textContent = 'Étiquette — ' + slide.name;
    popup.classList.add('visible');
    state.labelVisible = true;
}
function closeLabel() {
    document.getElementById('labelPopup').classList.remove('visible');
    state.labelVisible = false;
    // Deactivate macro annotation mode
    if (macroAnnState.active) {
        macroAnnState.active = false;
        macroAnnState.drawing = false;
        macroAnnState.currentPath = [];
        document.getElementById('btnMacroAnnotate').classList.remove('active');
        document.getElementById('macroAnnToolbar').classList.remove('visible');
        document.getElementById('macroAnnCanvas').classList.remove('drawing');
    }
}

// ── Keyboard ─────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') { if (e.key === 'Enter' && e.target.id === 'rootInput') loadCases(); return; }

    // Close context menu on Escape
    if (e.key === 'Escape' && document.getElementById('ctxMenu').classList.contains('visible')) { hideContextMenu(); e.preventDefault(); return; }
    // Close label on Escape
    if (e.key === 'Escape' && state.labelVisible) { closeLabel(); e.preventDefault(); return; }
    // Cancel pending measurement or clear all on Escape
    if (e.key === 'Escape' && state.measureMode) {
        if (state.measurePending) { state.measurePending = null; state.measureCursor = null; annRender(); }
        else { measureClearAll(); }
        e.preventDefault(); return;
    }

    const vp = state.osdViewer ? state.osdViewer.viewport : null;

    // Helper: rotation-aware pan
    function rotatedPan(rawDx, rawDy) {
        if (!vp) return;
        const angle = -state.rotation * Math.PI / 180;
        const dx = Math.cos(angle) * rawDx - Math.sin(angle) * rawDy;
        const dy = Math.sin(angle) * rawDx + Math.cos(angle) * rawDy;
        vp.panBy(new OpenSeadragon.Point(dx, dy));
    }

    switch (e.key) {
        // Arrow keys: pan 90% respecting rotation
        case 'ArrowLeft':
            e.preventDefault();
            if (vp) { const b = vp.getBounds(); rotatedPan(-b.width * 0.9, 0); }
            break;
        case 'ArrowRight':
            e.preventDefault();
            if (vp) { const b = vp.getBounds(); rotatedPan(b.width * 0.9, 0); }
            break;
        case 'ArrowUp':
            e.preventDefault();
            if (vp) { const b = vp.getBounds(); rotatedPan(0, -b.height * 0.9); }
            break;
        case 'ArrowDown':
            e.preventDefault();
            if (vp) { const b = vp.getBounds(); rotatedPan(0, b.height * 0.9); }
            break;

        // Numpad 4/6 or Q/D: prev/next
        case '4':
            if (e.location === 3 || e.code === 'Numpad4') { e.preventDefault(); navPrev(); }
            break;
        case '6':
            if (e.location === 3 || e.code === 'Numpad6') { e.preventDefault(); navNext(); }
            break;
        case 'q': case 'Q': e.preventDefault(); navPrev(); break;
        case 'd': case 'D': e.preventDefault(); navNext(); break;

        // Numpad 7/9: rotate 90° | A/E: rotate 10°
        case '7':
            if (e.location === 3 || e.code === 'Numpad7') {
                e.preventDefault();
                if (vp) { state.rotation = (state.rotation - 90 + 360) % 360; vp.setRotation(state.rotation); }
            }
            break;
        case '9':
            if (e.location === 3 || e.code === 'Numpad9') {
                e.preventDefault();
                if (vp) { state.rotation = (state.rotation + 90) % 360; vp.setRotation(state.rotation); }
            }
            break;
        case 'a': case 'A':
            e.preventDefault();
            if (vp) { state.rotation = (state.rotation - 10 + 360) % 360; vp.setRotation(state.rotation); }
            break;
        case 'e': case 'E':
            e.preventDefault();
            if (vp) { state.rotation = (state.rotation + 10) % 360; vp.setRotation(state.rotation); }
            break;

        // R: reset
        case 'r': case 'R':
            if (vp) { state.rotation = 0; vp.setRotation(0); vp.goHome(); }
            break;
        // F: fullscreen
        case 'f': case 'F':
            if (state.osdViewer) state.osdViewer.setFullScreen(!state.osdViewer.isFullPage());
            break;
        // L: label toggle
        case 'l': case 'L':
            toggleLabel();
            break;
        // N: annotation mode toggle
        case 'n': case 'N':
            toggleAnnotationMode();
            break;
        // M: measure mode toggle
        case 'm': case 'M':
            toggleMeasureMode();
            break;
        // P: peinture de superpixels
        case 'p': case 'P':
            toggleSuperpixelMode();
            break;
        // W: Normal + Save + Next
        case 'w': case 'W':
            e.preventDefault();
            labelNormalAndNext();
            break;
        // I: display settings toggle
        case 'i': case 'I':
            toggleDisplaySettings();
            break;
        // H: heatmap overlay toggle
        case 'h': case 'H':
            heatmapToggle();
            break;
    }

    // Ctrl+S: save annotations
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (state.editMode !== 'nav' && state.annotations.length > 0) annSave();
    }
});

document.getElementById('rootInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadCases();
});

// ── Annotation System (LDA-ready) ─────────────────────────
const ANN_LEVELS = { 0: 'Label lame', 1: 'Région (faible G)', 2: 'Histo (moyen G)' };

// Source of truth: foeto_terms DB via /api/config/labels
let LDA_CLASSES = {};

// Fœtus organ state
let FOETO_ORGANS = [];         // all available organs
let FOETO_TERMS_CACHE = {};    // {organ: {axis: [{id,label}]}}
let FOETO_QUICK_CACHE = {};    // {organ: [{id,label}]}
let PLACENTA_TISSUS = [];      // [{name,label}] — tissus placenta, pour le menu clic-droit DB-driven
let FOETO_RETENTION_CACHE = {}; // {organ: [{id,label}]}
let FOETO_MATURATION_CACHE = {}; // {organ: [{id,label}]}
let FOETO_GRADES = {};         // {term_id: [{grade, desc}]}
let _allFoetusOptions = [];    // flat list for search filter
let FOETO_SEGMENTS = [];       // [{id, label}] from foeto_term_segments

state.domain = 'placenta';     // 'placenta' or 'foetus'
state.annTarget = 'sign';      // 'sign' or 'struct' — which selector was last used
state.selectedOrgans = [];     // checked fetal organs

fetch(_url('/api/config/labels')).then(r => r.json()).then(cfg => {
    if (cfg.lda_classes) {
        LDA_CLASSES = {};
        for (const [k, v] of Object.entries(cfg.lda_classes)) LDA_CLASSES[parseInt(k)] = v;
    }
    annPopulateClassDropdown();
}).catch(e => console.error('Labels fetch failed:', e));

// Load structures + grades once
const _LABELS = {};  // name → label_fr (all domains/types)

fetch(_url('/api/foeto/structures')).then(r => r.json()).then(data => {
    const all = data.structures || [];
    all.forEach(s => { _LABELS[s.name] = s.label; });

    FOETO_ORGANS = all.filter(s => s.domain === 'foetus' && s.type === 'organe').map(s => s.name);
    _renderOrganPills();

    const tissues = all.filter(s => s.domain === 'placenta' && s.type === 'tissu');
    PLACENTA_TISSUS = tissues.map(s => ({ name: s.name, label: s.label }));
    // Prefetch des quick picks (viewer_quick=1) par tissu → menu clic-droit DB-driven
    if (PLACENTA_TISSUS.length) {
        fetch(_url('/api/foeto/terms?organs=' + PLACENTA_TISSUS.map(t => t.name).join(',')))
            .then(r => r.json())
            .then(data => Object.assign(FOETO_QUICK_CACHE, data.quick || {}))
            .catch(() => {});
    }
    const mkBtn = (s, onclick) => `<button class="tissue-btn" data-tissue="${s.name}" onclick="${onclick}('${s.name}', this)">${s.label}</button>`;
    const annEl = document.getElementById('tissueSelector');
    if (annEl) annEl.innerHTML = tissues.map(s => mkBtn(s, 'setTissue')).join('');

    FOETO_SEGMENTS = all.filter(s => s.type === 'structure').map(s => ({ id: 'STRUCT:' + s.name, label: s.label }));
    _populateStructDropdown();
}).catch(() => {});

fetch(_url('/api/foeto/grades')).then(r => r.json()).then(data => {
    FOETO_GRADES = data.grades || {};
}).catch(() => {});

function _diagBaseId(diagStr) { return diagStr.replace(/\.G\d+$/, ''); }
function _diagGrade(diagStr) { const m = diagStr.match(/\.G(\d+)$/); return m ? parseInt(m[1]) : 0; }
function _findDiagEntry(list, termId) { return list.find(d => _diagBaseId(d) === termId); }
function _isGradable(termId) { return !!FOETO_GRADES[termId]; }

function setDomain(domain, el) {
    state.domain = domain;
    document.querySelectorAll('.ann-domain-btn').forEach(b => b.classList.remove('active'));
    if (el) el.classList.add('active');
    document.getElementById('placentaTools').style.display = domain === 'placenta' ? '' : 'none';
    document.getElementById('foetusTools').style.display = domain === 'foetus' ? '' : 'none';
    document.getElementById('annClassSearch').style.display = '';
    if (domain === 'placenta') {
        _loadTissueTerms();
    } else {
        _loadOrganTerms();
    }
    // Labellisation tab: show/hide organ sections
    document.getElementById('labelPlacentaSection').style.display = domain === 'placenta' ? '' : 'none';
    document.getElementById('labelOrganSection').style.display = domain === 'foetus' ? '' : 'none';
    // Reset label state on domain switch
    state.labelOrgans = {};
    state.labelDiagnoses = [];
    labelRefreshUI();
}

function _renderOrganPills() {
    const el = document.getElementById('organPills');
    if (!el) return;
    el.innerHTML = FOETO_ORGANS.map(o => {
        const sel = state.selectedOrgans.includes(o) ? 'selected' : '';
        const label = _LABELS[o] || o;
        return `<span class="ann-diag-tag organ-pill ${sel}" onclick="toggleOrgan('${o}')">${label}</span>`;
    }).join('');
}

function toggleOrgan(organ) {
    const idx = state.selectedOrgans.indexOf(organ);
    if (idx >= 0) state.selectedOrgans.splice(idx, 1);
    else state.selectedOrgans.push(organ);
    _renderOrganPills();
    _loadOrganTerms();
}

function _loadOrganTerms() {
    if (state.selectedOrgans.length === 0) {
        FOETO_TERMS_CACHE = {};
        _populateFoetusClassDropdown();
        return;
    }
    const needed = state.selectedOrgans.filter(o => !(o in FOETO_TERMS_CACHE));
    if (needed.length === 0) {
        _populateFoetusClassDropdown();
        return;
    }
    fetch(_url('/api/foeto/terms?organs=' + state.selectedOrgans.join(','))).then(r => r.json()).then(data => {
        Object.assign(FOETO_TERMS_CACHE, data.terms || {});
        _populateFoetusClassDropdown();
    }).catch(() => {});
}

// ponytail: free-text class routed to a manual label
const OTHER_OPT = '<option value="__other__">Autre (texte libre)…</option>';
const _byLabel = (a, b) => a.label.localeCompare(b.label, 'fr');

function _populateFoetusClassDropdown() {
    const sel = document.getElementById('annClassSelect');
    if (!sel) return;
    _allFoetusOptions = [];
    let html = '';
    for (const org of state.selectedOrgans) {
        const byAxis = FOETO_TERMS_CACHE[org] || {};
        const label = _LABELS[org] || org;
        for (const [axis, terms] of Object.entries(byAxis)) {
            html += `<optgroup label="${label} — ${axis}">`;
            for (const t of [...terms].sort(_byLabel)) {
                html += `<option value="${t.id}">${t.label}</option>`;
                _allFoetusOptions.push({ id: t.id, label: t.label, org, axis });
            }
            html += '</optgroup>';
        }
    }
    sel.innerHTML = (html || '<option value="">Sélectionnez des organes</option>') + OTHER_OPT;
    annOnClassChange();
}

function annFilterClasses() {
    const q = (document.getElementById('annClassSearch').value || '').toLowerCase().trim();
    const sel = document.getElementById('annClassSelect');
    if (!q) { annPopulateClassDropdown(); return; }
    const filtered = _allFoetusOptions.filter(t => t.label.toLowerCase().includes(q)).sort(_byLabel);
    sel.innerHTML = (filtered.length === 0
        ? '<option value="">Aucun résultat</option>'
        : filtered.map(t => `<option value="${t.id}">${t.label}</option>`).join('')) + OTHER_OPT;
    annOnClassChange();
}

// ── Structure segments (independent from signs) ──────────────────────

function _populateStructDropdown() {
    const sel = document.getElementById('annStructSelect');
    if (!sel) return;
    sel.innerHTML = '<option value="">— aucune —</option>' +
        FOETO_SEGMENTS.map(s => `<option value="${s.id}">${s.label}</option>`).join('');
}

// Signe et Structure s'excluent : on annote l'un OU l'autre. Choisir dans un menu vide donc
// l'autre, sinon les deux lignes restent remplies et rien ne dit laquelle part dans l'annotation.
function annSyncTarget() {
    const signOn = state.annTarget === 'sign';
    document.getElementById('annSignRow').classList.toggle('ann-row-off', !signOn);
    document.getElementById('annStructRow').classList.toggle('ann-row-off', signOn);
}

function annOnStructChange() {
    const sel = document.getElementById('annStructSelect');
    if (sel && sel.value) {
        state.annTarget = 'struct';
        document.getElementById('annStructSwatch').style.background = '#e67e22';
        const signSel = document.getElementById('annClassSelect');
        if (signSel) signSel.value = '';
        const other = document.getElementById('annOtherLabel');
        if (other) other.style.display = 'none';
    }
    annSyncTarget();
}

function annOnClassChange() {
    const swatch = document.getElementById('annClassSwatch');
    const sel = document.getElementById('annClassSelect');
    const isOther = sel && sel.value === '__other__';
    const otherInput = document.getElementById('annOtherLabel');
    if (otherInput) otherInput.style.display = isOther ? '' : 'none';
    state.annColor = isOther ? '#95a5a6' : '#3498db';
    swatch.style.background = state.annColor;
    if (sel && sel.value) {
        state.annTarget = 'sign';
        const structSel = document.getElementById('annStructSelect');
        if (structSel) structSel.value = '';
    }
    annSyncTarget();
}

function annFilterStructs() {
    const q = (document.getElementById('annStructSearch').value || '').toLowerCase().trim();
    const sel = document.getElementById('annStructSelect');
    const list = q ? FOETO_SEGMENTS.filter(s => s.label.toLowerCase().includes(q)) : FOETO_SEGMENTS;
    sel.innerHTML = '<option value="">— aucune —</option>' +
        list.map(s => `<option value="${s.id}">${s.label}</option>`).join('');
}

function setTissue(tissue, el) {
    state.tissueType = tissue;
    document.querySelectorAll('.tissue-btn').forEach(b => b.classList.remove('active'));
    if (el) el.classList.add('active');
    _loadTissueTerms();
}

function _loadTissueTerms() {
    const tissue = state.tissueType;
    if (!tissue) { _populatePlacentaClassDropdown(); return; }
    if (tissue in FOETO_TERMS_CACHE) { _populatePlacentaClassDropdown(); return; }
    fetch(_url('/api/foeto/terms?organs=' + tissue)).then(r => r.json()).then(data => {
        Object.assign(FOETO_TERMS_CACHE, data.terms || {});
        _populatePlacentaClassDropdown();
    }).catch(() => {});
}

function _populatePlacentaClassDropdown() {
    const sel = document.getElementById('annClassSelect');
    if (!sel) return;
    const tissue = state.tissueType;
    const byAxis = FOETO_TERMS_CACHE[tissue] || {};
    _allFoetusOptions = [];
    let html = '';
    for (const [axis, terms] of Object.entries(byAxis)) {
        html += `<optgroup label="${tissue} — ${axis}">`;
        for (const t of [...terms].sort(_byLabel)) {
            html += `<option value="${t.id}" data-level="${t.level ?? ''}">${t.label}</option>`;
            _allFoetusOptions.push({ id: t.id, label: t.label, org: tissue, axis });
        }
        html += '</optgroup>';
    }
    sel.innerHTML = (html || '<option value="">Sélectionnez un tissu</option>') + OTHER_OPT;
    annOnClassChange();
}

let annIdCounter = 0;

function ldaGetClass(level, classId) {
    const classes = LDA_CLASSES[level] || [];
    return classes.find(c => c.id === classId) || null;
}

function ldaGetSelectedClass() {
    const sel = document.getElementById('annClassSelect');
    const classId = sel ? sel.value : '';
    return ldaGetClass(state.annLevel, classId);
}

function annPopulateClassDropdown() {
    if (state.domain === 'foetus') { _populateFoetusClassDropdown(); return; }
    _populatePlacentaClassDropdown();
}

// ponytail: annSetLevel kept as no-op for any residual callers
function annSetLevel() {}

// populated by fetch callback above

function switchTab(tab) {
    document.querySelectorAll('.ann-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.getElementById('tabLabel').style.display = tab === 'label' ? '' : 'none';
    document.getElementById('tabAnnotate').style.display = tab === 'annotate' ? '' : 'none';
    // peindre par défaut : c'est le geste qui va dominer, détourer devient l'exception (P bascule)
    setEditMode(tab === 'annotate' ? 'paint' : 'nav');
}

// Un seul outil arme le clic à la fois. Détourer et peindre se le disputaient (mousedown de tracé
// contre canvas-click de peinture) et rien à l'écran ne disait lequel allait répondre.
function setEditMode(mode) {
    if (mode !== 'nav' && (state.viewMode !== 'slide' || state.currentSlideIndex < 0)) {
        toast('Annotation disponible uniquement sur les lames', true);
        mode = 'nav';
    }
    if (mode !== 'nav' && state.measureMode) toggleMeasureMode();

    state.editMode = mode;
    state.annMode = mode === 'draw';
    state.spMode = mode === 'paint';
    state.annDrawing = false;

    document.querySelectorAll('.ann-tool-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.tool === mode));
    document.getElementById('annotationCanvas').classList.toggle('drawing', mode === 'draw');
    document.getElementById('annDrawingBadge').classList.toggle('visible', mode === 'draw');
    document.getElementById('spBadge').classList.toggle('visible', mode === 'paint');
    document.getElementById('btnAnnotate').classList.toggle('active', mode !== 'nav');

    if (state.osdViewer) {
        // en peinture le clic peint, mais le pan reste libre : on se déplace sans changer d'outil
        state.osdViewer.gestureSettingsMouse.clickToZoom = mode === 'nav';
        state.osdViewer.gestureSettingsMouse.dblClickToZoom = mode === 'nav';
        state.osdViewer.panHorizontal = mode !== 'draw';
        state.osdViewer.panVertical = mode !== 'draw';
        state.osdViewer.removeHandler('canvas-click', spCanvasClick);
        state.osdViewer.removeHandler('animation-finish', spLoad);
        if (mode === 'paint') state.osdViewer.addHandler('canvas-click', spCanvasClick);
        if (mode === 'paint' || state.spGrid) {
            state.osdViewer.addHandler('animation-finish', spLoad);
            spLoad();
        }
    }
    if (mode !== 'paint' && !state.spGrid) { state.spTiles = {}; state.spPolys = []; state.spMsg = ''; }

    annResizeCanvas();
    annRender();
    if (mode !== 'nav') annRenderList();
}

function openPanelRight(tab) {
    const panel = document.getElementById('annPanel');
    const handle = document.getElementById('resizeHandleRight');

    panel.classList.add('visible');
    handle.classList.add('visible');

    switchTab(tab);
}

function closePanelRight() {
    document.getElementById('annPanel').classList.remove('visible');
    document.getElementById('resizeHandleRight').classList.remove('visible');
    state.annCurrentPath = [];
    state.annHighlighted = null;
    setEditMode('nav');
}

function toggleAnnotationMode() {
    if (state.viewMode !== 'slide') { toast('Annotations disponibles uniquement sur les lames', true); return; }
    const panel = document.getElementById('annPanel');
    if (panel.classList.contains('visible')) {
        closePanelRight();
    } else {
        openPanelRight('label');
    }
}

function annResizeCanvas() {
    const canvas = document.getElementById('annotationCanvas');
    const viewer = document.getElementById('viewer');
    canvas.width = viewer.clientWidth;
    canvas.height = viewer.clientHeight;
}

function annScreenToImage(screenX, screenY) {
    if (!state.osdViewer) return null;
    const rect = state.osdViewer.element.getBoundingClientRect();
    const vp = state.osdViewer.viewport;
    const pt = vp.viewportToImageCoordinates(vp.pointFromPixel(
        new OpenSeadragon.Point(screenX - rect.left, screenY - rect.top)));
    return [Math.round(pt.x), Math.round(pt.y)];
}

function annImageToCanvas(imgX, imgY) {
    if (!state.osdViewer) return null;
    const vp = state.osdViewer.viewport;
    const pt = vp.pixelFromPoint(vp.imageToViewportCoordinates(new OpenSeadragon.Point(imgX, imgY)));
    return [pt.x, pt.y];
}

// ── Annotation Rendering ─────────────────────────────────
function annRender() {
    const canvas = document.getElementById('annotationCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (state.heatmap) heatmapRender(ctx);
    if ((state.spMode || state.spGrid) && state.spPolys.length) spRender(ctx);
    for (const ann of state.annotations) {
        annDrawPath(ctx, ann.points_px, ann.color, true, ann.id === state.annHighlighted);
    }
    if (state.annCurrentPath.length > 1) {
        annDrawPath(ctx, state.annCurrentPath, state.annColor, false, false);
    }
    if (state.measurements.length > 0 || state.measurePending) {
        measureRenderAll(ctx);
    }
    measureUpdateDeleteBtns();
}

function annDrawPath(ctx, points, color, closed, highlighted) {
    if (points.length < 2) return;
    ctx.beginPath();
    const first = annImageToCanvas(points[0][0], points[0][1]);
    if (!first) return;
    ctx.moveTo(first[0], first[1]);
    for (let i = 1; i < points.length; i++) {
        const pt = annImageToCanvas(points[i][0], points[i][1]);
        if (pt) ctx.lineTo(pt[0], pt[1]);
    }
    if (closed) ctx.closePath();
    ctx.fillStyle = color + (highlighted ? '40' : '18');
    if (closed) ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = highlighted ? 3 : 2;
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    if (highlighted) ctx.setLineDash([6, 4]); else ctx.setLineDash([]);
    ctx.stroke();
    ctx.setLineDash([]);
}

// ── Heatmap overlay (V1) ─────────────────────────────────
function heatmapLabel(variant) {
    const m = variant.match(/^(.+)_x(\d+)$/);
    if (!m) return variant;
    const enc = { ctranspath: 'CTP', dinov2_vits: 'DINOv2' }[m[1]] || m[1];
    return `${enc} ×${m[2]}`;
}

async function heatmapToggle() {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const btn = document.getElementById('btnHeatmap');
    const sel = document.getElementById('heatmapSelect');
    if (state.heatmap) {   // OFF
        state.heatmap = null; btn.classList.remove('active');
        sel.style.display = 'none'; annRender(); return;
    }
    const slide = state.slides[state.currentSlideIndex];
    try {
        const res = await fetch(`${_BASE}/api/heatmap/list?slide_path=${encodeURIComponent(slide.path)}`);
        const { variants } = await res.json();
        if (!variants || !variants.length) { toast('Pas de heatmap pour cette lame', true); return; }
        sel.innerHTML = variants.map(v => `<option value="${v}">${heatmapLabel(v)}</option>`).join('');
        sel.style.display = '';
        btn.classList.add('active');
        heatmapLoadVariant(variants[0]);
    } catch (e) { toast('Erreur heatmap: ' + e.message, true); }
}

async function heatmapLoadVariant(variant) {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const slide = state.slides[state.currentSlideIndex];
    try {
        const res = await fetch(`${_BASE}/api/heatmap/load?slide_path=${encodeURIComponent(slide.path)}&variant=${encodeURIComponent(variant)}`);
        const data = await res.json();
        if (!data.exists || !data.patches.length) { toast('Variante introuvable', true); return; }
        state.heatmap = data;
        toast(`Heatmap ${heatmapLabel(variant)} : ${data.patches.length} vaisseaux`);
        annRender();
    } catch (e) { toast('Erreur heatmap: ' + e.message, true); }
}

function heatmapRender(ctx) {
    const s = state.heatmap.patch_side_l0;
    for (const [x, y, score] of state.heatmap.patches) {
        const a = annImageToCanvas(x, y);
        const b = annImageToCanvas(x + s, y + s);
        if (!a || !b) continue;
        const hue = (1 - score) * 240;   // score 0 → bleu, 1 → rouge
        ctx.fillStyle = `hsla(${hue}, 90%, 50%, 0.42)`;
        ctx.fillRect(a[0], a[1], b[0] - a[0], b[1] - a[1]);
    }
}

// ── Drawing Events ───────────────────────────────────────
(function() {
    const canvas = document.getElementById('annotationCanvas');

    canvas.addEventListener('mousedown', (e) => {
        if (!state.annMode || e.button !== 0) return;
        e.preventDefault();
        state.annDrawing = true;
        state.annCurrentPath = [];
        const pt = annScreenToImage(e.clientX, e.clientY);
        if (pt) state.annCurrentPath.push(pt);
    });
    canvas.addEventListener('mousemove', (e) => {
        if (!state.annDrawing) return;
        const pt = annScreenToImage(e.clientX, e.clientY);
        if (pt) { state.annCurrentPath.push(pt); annRender(); }
    });
    canvas.addEventListener('mouseup', () => {
        if (!state.annDrawing) return;
        state.annDrawing = false;
        annFinishStroke();
    });
    canvas.addEventListener('mouseleave', () => {
        if (state.annDrawing) { state.annDrawing = false; state.annCurrentPath = []; annRender(); }
    });

    // Touch
    canvas.addEventListener('touchstart', (e) => {
        if (!state.annMode || e.touches.length !== 1) return;
        e.preventDefault();
        state.annDrawing = true;
        state.annCurrentPath = [];
        const pt = annScreenToImage(e.touches[0].clientX, e.touches[0].clientY);
        if (pt) state.annCurrentPath.push(pt);
    }, { passive: false });
    canvas.addEventListener('touchmove', (e) => {
        if (!state.annDrawing || e.touches.length !== 1) return;
        e.preventDefault();
        const pt = annScreenToImage(e.touches[0].clientX, e.touches[0].clientY);
        if (pt) { state.annCurrentPath.push(pt); annRender(); }
    }, { passive: false });
    canvas.addEventListener('touchend', () => {
        if (!state.annDrawing) return;
        state.annDrawing = false;
        annFinishStroke();
    });
})();

function annCurrentClass() {
    const sel = document.getElementById('annClassSelect');
    const structSel = document.getElementById('annStructSelect');
    const tissueType = state.domain === 'foetus' ? state.selectedOrgans.join(',') : state.tissueType;
    let label, classId, color;

    let annLevel = 1;  // une annotation dessinée est au minimum une Région (faible G)
    if (sel && sel.value === '__other__') {
        classId = '';
        label = (document.getElementById('annOtherLabel').value || '').trim() || 'Autre';
        color = '#95a5a6';
    } else if (state.annTarget === 'struct' && structSel && structSel.value) {
        classId = structSel.value;
        label = structSel.options[structSel.selectedIndex].textContent;
        color = '#e67e22';
    } else {
        classId = sel ? sel.value : '';
        const opt = sel ? sel.options[sel.selectedIndex] : null;
        label = opt ? opt.textContent : '';
        color = '#3498db';
        if (opt && opt.dataset.level !== '') annLevel = parseInt(opt.dataset.level, 10);
    }
    return { label, classId, color, annLevel, tissueType };
}

function annFinishStroke() {
    if (state.annCurrentPath.length > 5) {
        const note = document.getElementById('annLabelInput').value.trim();
        const { label, classId, color, annLevel, tissueType } = annCurrentClass();
        state.annotations.push({
            id: 'ann_' + (++annIdCounter),
            points_px: [...state.annCurrentPath],
            color, label, note, class_id: classId,
            tissue_type: tissueType,
            level: annLevel, created: new Date().toISOString(),
        });
        annUpdateCount();
        annRenderList();
    }
    state.annCurrentPath = [];
    annRender();
}

// ── Measurement Tool ─────────────────────────────────────
let measureIdCounter = 0;

function formatDistance(um) {
    if (um > 500) return (um / 1000).toFixed(2) + ' mm';
    return um.toFixed(1) + ' µm';
}

function formatArea(um2) {
    if (um2 <= 0) return '';
    if (um2 >= 1e6) return (um2 / 1e6).toFixed(2) + ' mm²';
    return Math.round(um2).toLocaleString() + ' µm²';
}

function computePolygonArea(points) {
    if (points.length < 3) return 0;
    let area = 0;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        area += points[j][0] * points[i][1];
        area -= points[i][0] * points[j][1];
    }
    return Math.abs(area) / 2;
}

function computeDistance(p1, p2) {
    const dx = (p2[0] - p1[0]) * (state.mppX || 1);
    const dy = (p2[1] - p1[1]) * (state.mppY || 1);
    return Math.sqrt(dx * dx + dy * dy);
}

function toggleMeasureMode() {
    if (state.viewMode !== 'slide') { toast('Mesures disponibles uniquement sur les lames', true); return; }
    if (state.mppX <= 0 || state.mppY <= 0) {
        toast('Pas de calibration (MPP) disponible — distances en pixels', false);
    }
    state.measureMode = !state.measureMode;
    const btn = document.getElementById('btnMeasure');
    const canvas = document.getElementById('annotationCanvas');
    const badge = document.getElementById('measureBadge');

    btn.classList.toggle('active', state.measureMode);
    badge.classList.toggle('visible', state.measureMode);

    if (state.measureMode) {
        if (state.editMode !== 'nav') setEditMode('nav');   // mesurer désarme détourage/peinture
        canvas.classList.add('measuring');
        if (state.osdViewer) {
            state.osdViewer.gestureSettingsMouse.clickToZoom = false;
            state.osdViewer.gestureSettingsMouse.dblClickToZoom = false;
            state.osdViewer.panHorizontal = false;
            state.osdViewer.panVertical = false;
        }
    } else {
        canvas.classList.remove('measuring');
        state.measurePending = null;
        state.measureCursor = null;
        if (state.osdViewer && state.editMode === 'nav') {
            state.osdViewer.gestureSettingsMouse.clickToZoom = true;
            state.osdViewer.gestureSettingsMouse.dblClickToZoom = true;
            state.osdViewer.panHorizontal = true;
            state.osdViewer.panVertical = true;
        }
    }
    annRender();
}

function measureUpdateCount() {
    document.getElementById('measureCount').textContent = state.measurements.length;
}

function measureClearAll() {
    state.measurements = [];
    state.measurePending = null;
    state.measureCursor = null;
    measureUpdateCount();
    annRender();
}

// Measure mode canvas events
(function() {
    const canvas = document.getElementById('annotationCanvas');

    canvas.addEventListener('click', (e) => {
        if (!state.measureMode || e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        const pt = annScreenToImage(e.clientX, e.clientY);
        if (!pt) return;

        if (!state.measurePending) {
            state.measurePending = pt;
        } else {
            const dist = computeDistance(state.measurePending, pt);
            state.measurements.push({
                id: 'meas_' + (++measureIdCounter),
                start: state.measurePending,
                end: pt,
                distUm: dist,
            });
            state.measurePending = null;
            state.measureCursor = null;
            measureUpdateCount();
        }
        annRender();
    });

    canvas.addEventListener('mousemove', (e) => {
        if (!state.measureMode || !state.measurePending) return;
        const pt = annScreenToImage(e.clientX, e.clientY);
        if (pt) { state.measureCursor = pt; annRender(); }
    });

    canvas.addEventListener('contextmenu', (e) => {
        if (!state.measureMode) return;
        e.preventDefault();
        if (state.measurePending) {
            state.measurePending = null;
            state.measureCursor = null;
            annRender();
        } else if (state.measurements.length > 0) {
            state.measurements.pop();
            measureUpdateCount();
            annRender();
        }
    });
})();

function measureRenderAll(ctx) {
    const hasCalib = state.mppX > 0 && state.mppY > 0;
    for (const m of state.measurements) {
        measureDrawLine(ctx, m.start, m.end, m.distUm, hasCalib, false);
    }
    if (state.measurePending) {
        const start = annImageToCanvas(state.measurePending[0], state.measurePending[1]);
        if (start) {
            ctx.beginPath();
            ctx.arc(start[0], start[1], 5, 0, Math.PI * 2);
            ctx.fillStyle = '#2ecc71';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
        if (state.measureCursor) {
            const dist = computeDistance(state.measurePending, state.measureCursor);
            measureDrawLine(ctx, state.measurePending, state.measureCursor, dist, hasCalib, true);
        }
    }
}

function measureDrawLine(ctx, p1, p2, distUm, hasCalib, preview) {
    const a = annImageToCanvas(p1[0], p1[1]);
    const b = annImageToCanvas(p2[0], p2[1]);
    if (!a || !b) return;

    // Line
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.strokeStyle = preview ? '#2ecc7188' : '#2ecc71';
    ctx.lineWidth = preview ? 2 : 2.5;
    ctx.setLineDash(preview ? [6, 4] : []);
    ctx.stroke();
    ctx.setLineDash([]);

    // Endpoints
    for (const pt of [a, b]) {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 4, 0, Math.PI * 2);
        ctx.fillStyle = '#2ecc71';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }

    // Distance label at midpoint
    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    const label = hasCalib ? formatDistance(distUm) : Math.round(distUm) + ' px';
    ctx.font = 'bold 13px "DM Sans", sans-serif';
    const tw = ctx.measureText(label).width;
    const pad = 5;
    ctx.fillStyle = 'rgba(15, 17, 23, 0.85)';
    const rx = mx - tw / 2 - pad, ry = my - 10 - pad, rw = tw + pad * 2, rh = 20 + pad;
    ctx.beginPath();
    if (ctx.roundRect) { ctx.roundRect(rx, ry, rw, rh, 4); }
    else { ctx.rect(rx, ry, rw, rh); }
    ctx.fill();
    ctx.strokeStyle = '#2ecc71';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#2ecc71';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, mx, my);
}

function measureUpdateDeleteBtns() {
    const overlay = document.getElementById('measureDeleteOverlay');
    if (!overlay) return;
    if (state.measurements.length === 0) { overlay.innerHTML = ''; return; }
    const viewer = document.getElementById('viewer');
    const vRect = viewer.getBoundingClientRect();
    overlay.innerHTML = state.measurements.map(m => {
        const a = annImageToCanvas(m.end[0], m.end[1]);
        if (!a) return '';
        const x = a[0] + 12;
        const y = a[1] - 12;
        if (x < -20 || y < -20 || x > vRect.width + 20 || y > vRect.height + 20) return '';
        return `<button class="measure-delete-btn" style="left:${x}px;top:${y}px"
                    onclick="measureDeleteById('${m.id}')" title="Supprimer">&times;</button>`;
    }).join('');
}

function measureDeleteById(id) {
    state.measurements = state.measurements.filter(m => m.id !== id);
    measureUpdateCount();
    annRender();
}

// ── Peinture de superpixels ──────────────────────────────
// Un polygone tracé à la main est fidèle au DIAGNOSTIC, pas au contenu en pixels : il embarque
// fibrine et sang, qui diluent toute mesure de couleur faite ensuite. Peindre des superpixels
// rend l'annotation fidèle au pixel sans coûter plus de temps au lecteur.
// 90 µm = diamètre d'une villosité distale, le grain anatomique visé. Seule taille précalculée sur
// TOUTES les lames ; une autre valeur n'a de grille que là où le précalcul a été lancé, sinon SLIC
// tourne en direct (~12 s/tuile) et le mode Grille ne sert que ce qui est déjà en cache.
let SP_UM = 90;

// ponytail: le cache client est clé par sp_um (tile_key), donc rien à purger en changeant de taille
function setSpUm(um) {
    SP_UM = +um;
    if (state.spGrid || state.spMode) spLoad();
}

function spPointInPoly(x, y, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
        if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}

// Raccourci P : bascule peindre / détourer sans passer par la barre d'outils.
function toggleSuperpixelMode() {
    if (!document.getElementById('annPanel').classList.contains('visible')) openPanelRight('annotate');
    setEditMode(state.editMode === 'paint' ? 'draw' : 'paint');
}

// Le serveur découpe la lame en tuiles fixes et met chacune en cache : on ne redemande jamais
// une tuile déjà reçue, et le superpixel sous le curseur ne change pas quand on zoome.
// Grille en simple affichage : aucun outil armé, pas de limite de champ, et le serveur ne sert
// que les tuiles DÉJÀ en cache — c'est le calage de ce cache-là qu'on vient vérifier à l'œil.
function toggleSpGrid() {
    state.spGrid = !state.spGrid;
    document.getElementById('btnSpGrid').classList.toggle('active', state.spGrid);
    if (state.osdViewer) {
        state.osdViewer.removeHandler('animation-finish', spLoad);
        if (state.spGrid || state.spMode) state.osdViewer.addHandler('animation-finish', spLoad);
    }
    if (state.spGrid) spLoad();
    else if (!state.spMode) { state.spTiles = {}; state.spPolys = []; state.spMsg = ''; }
    annResizeCanvas();
    annRender();
}

async function spLoad() {
    if ((!state.spMode && !state.spGrid) || state.currentSlideIndex < 0) return;
    if (state.spBusy) { state.spPending = true; return; }
    state.spBusy = true;
    const countEl = document.getElementById('spCount');
    const slide = state.slides[state.currentSlideIndex];
    const vp = state.osdViewer.viewport;
    const r = vp.viewportToImageRectangle(vp.getBounds(true));
    try {
        countEl.textContent = '…';
        const res = await api('/api/superpixels', {
            slide_path: slide.path,
            bbox: [r.x, r.y, r.width, r.height],
            sp_um: SP_UM,
            have: Object.keys(state.spTiles),
            grid: !state.spMode,
        });
        if (res.error) { toast('Superpixels : ' + res.error, true); return; }
        for (const t of res.tiles || []) {
            state.spTiles[t.key] = (t.geojson.features || []).map(f => ({
                id: f.id, poly: f.geometry.coordinates[0], color: f.properties?.color,
            }));
        }
        state.spPolys = (res.keys || []).flatMap(k => state.spTiles[k] || []);
        if (res.message && res.message !== state.spMsg) toast(res.message, true);
        state.spMsg = res.message || '';
        countEl.textContent = res.pending ? `${state.spPolys.length} +${res.pending}…` : state.spPolys.length;
        annRender();
        if (res.pending) state.spPending = true;   // lame non précalculée : le serveur ne fait
                                                   // qu'une tuile par requête, on redemande
    } catch (e) {
        toast('Erreur superpixels: ' + e.message, true);
    } finally {
        state.spBusy = false;
        if (state.spPending) { state.spPending = false; spLoad(); }
    }
}

// Peint (ou dépeint si toggle) le superpixel sous le point image donné. Renvoie true si l'état
// des annotations a changé — l'appelant décide quand rafraîchir la liste (coûteux au pinceau).
function spPaintAt(x, y, toggle) {
    // Dépeindre se décide sur la GÉOMÉTRIE, pas sur sp_key : après un passage de 90 à 60 µm le
    // superpixel d'origine n'existe plus dans spPolys, son annotation deviendrait ineffaçable et
    // on repeindrait le même tissu par-dessus — deux annotations superposées comptent deux fois
    // les mêmes pixels, exactement ce que la peinture est censée éviter.
    for (let i = state.annotations.length - 1; i >= 0; i--) {
        const a = state.annotations[i];
        if (!a.sp_key || !spPointInPoly(x, y, a.points_px)) continue;
        if (!toggle) return false;              // au pinceau, repasser dessus ne l'efface pas
        state.annotations.splice(i, 1);
        return true;
    }

    for (let i = state.spPolys.length - 1; i >= 0; i--) {
        const { id: key, poly } = state.spPolys[i];
        if (!spPointInPoly(x, y, poly)) continue;
        const { label, classId, color, annLevel, tissueType } = annCurrentClass();
        if (!classId && !label) {
            toast('Choisir une classe dans le panneau Annoter avant de peindre', true); return false;
        }
        state.annotations.push({
            id: 'ann_' + (++annIdCounter),
            points_px: poly.map(q => [q[0], q[1]]),
            color, label, note: '', class_id: classId,
            tissue_type: tissueType, sp_key: key,
            level: annLevel, created: new Date().toISOString(),
        });
        spBrushPoly = poly;
        return true;
    }
    return false;
}

function spCanvasClick(e) {
    if (!state.spMode || !e.quick) return;      // e.quick : un vrai clic, pas la fin d'un pan
    e.preventDefaultAction = true;
    const vp = state.osdViewer.viewport;
    const p = vp.viewportToImageCoordinates(vp.pointFromPixel(e.position));
    if (spPaintAt(p.x, p.y, true)) { annUpdateCount(); annRenderList(); annRender(); }
}

// ── Pinceau : clic droit maintenu, tous les superpixels traversés passent dans la classe courante.
// Le clic gauche reste le toggle d'un superpixel unique.
let spBrushing = false;
let spBrushPrev = null;     // dernier point écran du trait
let spBrushPoly = null;     // dernier superpixel peint — évite de rebalayer spPolys à chaque sample
(function () {
    const viewer = document.getElementById('viewer');

    function brushSample(sx, sy) {
        const p = annScreenToImage(sx, sy);
        if (!p) return false;
        if (spBrushPoly && spPointInPoly(p[0], p[1], spBrushPoly)) return false;
        return spPaintAt(p[0], p[1], false);
    }

    function brushTo(sx, sy) {
        let changed = false;
        if (spBrushPrev) {
            // interpole : une souris rapide saute par-dessus des superpixels entiers
            const dx = sx - spBrushPrev[0], dy = sy - spBrushPrev[1];
            const n = Math.min(200, Math.max(1, Math.ceil(Math.hypot(dx, dy) / 5)));
            for (let i = 1; i <= n; i++) {
                if (brushSample(spBrushPrev[0] + dx * i / n, spBrushPrev[1] + dy * i / n)) changed = true;
            }
        } else if (brushSample(sx, sy)) changed = true;
        spBrushPrev = [sx, sy];
        if (changed) annRender();
    }

    function brushEnd() {
        if (!spBrushing) return;
        spBrushing = false;
        spBrushPrev = null;
        spBrushPoly = null;
        annUpdateCount();
        annRenderList();
        annRender();
    }

    // Pointer events, pas mouse events : OpenSeadragon annule le pointerdown de sa toile, ce qui
    // supprime les mousedown/mousemove de compatibilité — un handler souris n'est jamais appelé.
    // Capture sur window pour passer avant le MouseTracker d'OSD, qui est sur la toile en dessous.
    window.addEventListener('pointerdown', e => {
        if (e.button !== 2 || !state.spMode || state.measureMode) return;
        if (!viewer.contains(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
        spBrushing = true;
        spBrushPrev = null;
        spBrushPoly = null;
        brushTo(e.clientX, e.clientY);
    }, true);

    window.addEventListener('pointermove', e => {
        if (!spBrushing) return;
        if (!(e.buttons & 2)) { brushEnd(); return; }   // bouton relâché hors fenêtre
        e.stopPropagation();
        brushTo(e.clientX, e.clientY);
    }, true);

    window.addEventListener('pointerup', e => { if (e.button === 2) brushEnd(); }, true);
    window.addEventListener('pointercancel', brushEnd, true);
})();

function spRender(ctx) {
    ctx.save();
    // les superpixels SLIC n'ont pas de `color` : noir 1 px, lisible sur le rose pâle du HES.
    // Une couche d'objets classes (villo_unet) la pose par feature et sort en trait epais.
    for (const { poly, color } of state.spPolys) {
        ctx.strokeStyle = color || 'rgba(0,0,0,0.55)';
        ctx.lineWidth = color ? 2.5 : 1;
        const first = annImageToCanvas(poly[0][0], poly[0][1]);
        if (!first) continue;
        ctx.beginPath();
        ctx.moveTo(first[0], first[1]);
        for (let i = 1; i < poly.length; i++) {
            const pt = annImageToCanvas(poly[i][0], poly[i][1]);
            if (pt) ctx.lineTo(pt[0], pt[1]);
        }
        ctx.closePath();
        ctx.stroke();
    }
    ctx.restore();
}

// ── Annotation List ──────────────────────────────────────
function annUpdateCount() {
    document.getElementById('annCount').textContent = state.annotations.length;
    annUpdateExportBtn();
}

function annRenderList() {
    const container = document.getElementById('annListScroll');
    if (state.annotations.length === 0) {
        container.innerHTML = '<div class="ann-list-empty">Dessinez sur la lame pour annoter</div>';
        return;
    }
    container.innerHTML = state.annotations.map((ann, i) => {
        const levelTag = ANN_LEVELS[ann.level] || '?';
        const nPts = ann.points_px.length;
        const areaPx2 = computePolygonArea(ann.points_px);
        let areaStr = '';
        if (areaPx2 > 0 && state.mppX > 0 && state.mppY > 0) {
            const areaUm2 = areaPx2 * state.mppX * state.mppY;
            areaStr = ' · ' + formatArea(areaUm2);
        } else if (areaPx2 > 0) {
            areaStr = ' · ' + Math.round(areaPx2).toLocaleString() + ' px²';
        }
        const noteStr = ann.note ? ` — <span style="color:var(--text-muted);font-style:italic">${ann.note}</span>` : '';
        return `
        <div class="ann-list-item ${ann.id === state.annHighlighted ? 'highlighted' : ''}"
             onmouseenter="annHighlight('${ann.id}')" onmouseleave="annHighlight(null)">
            <div class="ann-list-swatch" style="background:${ann.color}"></div>
            <div class="ann-list-info">
                <div class="ann-list-info-label" id="annLabel_${ann.id}" ondblclick="annStartEdit('${ann.id}')"
                     title="Double-clic pour éditer la note">${ann.label}${noteStr}</div>
                <div class="ann-list-info-meta">${ann.tissue_type ? '<span class="tissue-badge ' + ann.tissue_type + '">' + ann.tissue_type + '</span> ' : ''}${levelTag} · ${nPts} pts${areaStr}${ann.class_id ? ' · <span style="color:var(--accent)">' + ann.class_id + '</span>' : ''}</div>
            </div>
            <div class="ann-list-actions">
                <button class="ann-list-action goto" onclick="annGoTo('${ann.id}')" title="Aller à">&#8982;</button>
                <button class="ann-list-action" onclick="annStartEdit('${ann.id}')" title="Éditer la note">&#9998;</button>
                <button class="ann-list-action delete" onclick="annDeleteOne('${ann.id}')" title="Supprimer">&#10005;</button>
            </div>
        </div>`;
    }).join('');
}

function annHighlight(id) {
    state.annHighlighted = id;
    annRender();
    // Update highlighted class in list
    document.querySelectorAll('.ann-list-item').forEach(el => el.classList.remove('highlighted'));
    if (id) {
        const items = document.querySelectorAll('.ann-list-item');
        const idx = state.annotations.findIndex(a => a.id === id);
        if (idx >= 0 && items[idx]) items[idx].classList.add('highlighted');
    }
}

function annGoTo(id) {
    const ann = state.annotations.find(a => a.id === id);
    if (!ann || !state.osdViewer) return;
    // Compute bounding box
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [x, y] of ann.points_px) {
        if (x < minX) minX = x; if (y < minY) minY = y;
        if (x > maxX) maxX = x; if (y > maxY) maxY = y;
    }
    // Add padding
    const padX = (maxX - minX) * 0.15;
    const padY = (maxY - minY) * 0.15;
    minX -= padX; minY -= padY; maxX += padX; maxY += padY;

    const vp = state.osdViewer.viewport;
    const topLeft = vp.imageToViewportCoordinates(new OpenSeadragon.Point(minX, minY));
    const bottomRight = vp.imageToViewportCoordinates(new OpenSeadragon.Point(maxX, maxY));
    const rect = new OpenSeadragon.Rect(topLeft.x, topLeft.y, bottomRight.x - topLeft.x, bottomRight.y - topLeft.y);
    vp.fitBounds(rect);

    state.annHighlighted = id;
    annRender();
    annRenderList();
}

function annStartEdit(id) {
    const ann = state.annotations.find(a => a.id === id);
    if (!ann) return;
    const labelEl = document.getElementById('annLabel_' + id);
    if (!labelEl) return;
    labelEl.innerHTML = `${ann.label} <input class="ann-edit-input" value="${ann.note || ''}" placeholder="note / grading…"
        onkeydown="if(event.key==='Enter')annFinishEdit('${id}',this.value);if(event.key==='Escape')annRenderList();"
        onblur="annFinishEdit('${id}',this.value)">`;
    labelEl.querySelector('input').focus();
    labelEl.querySelector('input').select();
}

function annFinishEdit(id, newNote) {
    const ann = state.annotations.find(a => a.id === id);
    if (ann) ann.note = newNote.trim();
    annRenderList();
    annRender();
}

function annDeleteOne(id) {
    state.annotations = state.annotations.filter(a => a.id !== id);
    annUpdateCount();
    annRenderList();
    annRender();
}

function annUndo() {
    if (state.annotations.length === 0) return;
    state.annotations.pop();
    annUpdateCount(); annRenderList(); annRender();
}

function annClearAll() {
    if (state.annotations.length === 0) return;
    if (!confirm(`Effacer ${state.annotations.length} annotation(s) ?`)) return;
    state.annotations = [];
    annUpdateCount(); annRenderList(); annRender();
}

async function annSave() {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    if (state.annotations.length === 0) {
        toast('Aucune annotation', true); return;
    }
    const slide = state.slides[state.currentSlideIndex];
    const features = state.annotations.map(ann => {
        const areaPx2 = computePolygonArea(ann.points_px);
        const areaUm2 = (state.mppX > 0 && state.mppY > 0) ? areaPx2 * state.mppX * state.mppY : null;
        return {
            coordinates: [ann.points_px],
            properties: {
                id: ann.id, label: ann.label, note: ann.note || '', color: ann.color,
                class_id: ann.class_id || '',
                tissue_type: ann.tissue_type || state.tissueType,
                ann_class: ann.class_id || '',
                sp_key: ann.sp_key || null,
                level: ann.level, level_name: ANN_LEVELS[ann.level],
                area_px2: Math.round(areaPx2),
                area_um2: areaUm2 ? Math.round(areaUm2) : null,
                created: ann.created,
            },
        };
    });
    try {
        const tissueType = state.domain === 'foetus' ? state.selectedOrgans.join(',') : state.tissueType;
        const res = await api('/api/annotations/save', {
            root: state.root, slide_path: slide.path, features: features,
            tissue_type: tissueType,
        });
        if (res.ok) {
            toast(`${res.feature_count} annotation(s) sauvegardée(s)`);
            loadCaseIndex();
        } else toast('Erreur: ' + (res.error || 'inconnue'), true);
    } catch (e) { toast('Erreur réseau: ' + e.message, true); }
}

async function annLoad(slidePath) {
    state.annotations = [];
    state.annHighlighted = null;
    annUpdateCount();
    try {
        const res = await fetch(`${_BASE}/api/annotations/load?root=${encodeURIComponent(state.root)}&slide_path=${encodeURIComponent(slidePath)}`);
        const data = await res.json();
        if (data.exists) {
            const meta = data.metadata || {};
            const tissue = meta.tissue_type || '';

            if (state.domain === 'foetus') {
                state.selectedOrgans = tissue.split(',').map(s => s.trim()).filter(Boolean);
                _renderOrganPills();
                FOETO_TERMS_CACHE = {};
                _loadOrganTerms();
            } else if (tissue) {
                setTissue(tissue, document.querySelector(`.tissue-btn[data-tissue="${tissue}"]`));
            }

            if (data.features && data.features.length > 0) {
                for (const feat of data.features) {
                    const coords = feat.geometry?.coordinates?.[0] || [];
                    const p = feat.properties || {};
                    const aid = p.id || 'ann_' + (++annIdCounter);
                    const m = /^ann_(\d+)$/.exec(aid);  // évite que la prochaine annotation réutilise un id chargé
                    if (m) annIdCounter = Math.max(annIdCounter, parseInt(m[1], 10));
                    state.annotations.push({
                        id: aid,
                        points_px: coords,
                        color: p.color || '#e74c3c',
                        label: p.label || '',
                        note: p.note || '',
                        class_id: p.class_id || '',
                        tissue_type: p.tissue_type || '',
                        sp_key: p.sp_key || null,   // sans lui, un superpixel rechargé ne se dépeint plus
                        level: p.level || 1,
                        created: p.created || '',
                    });
                }
                annUpdateCount();
            }
            toast(`${state.annotations.length} annotation(s) chargée(s)`);
        }
    } catch (e) {}
    if (state.editMode !== 'nav') annRenderList();
    annRender();
}

function annAttachViewportHandler() {
    if (!state.osdViewer) return;
    state.osdViewer.addHandler('update-viewport', () => {
        if (state.annotations.length > 0 || state.annCurrentPath.length > 0
            || state.measurements.length > 0 || state.measurePending || state.spPolys.length > 0) {
            annResizeCanvas(); annRender();
        }
        updateZoomIndicator();
    });
    state.osdViewer.addHandler('resize', () => { annResizeCanvas(); annRender(); });
}

// ── Macro Image Annotation System ─────────────────────────
let macroAnnState = {
    active: false,
    drawing: false,
    currentPath: [],       // [[x_px, y_px], ...] in macro image pixels
    annotations: [],       // [{id, points_px, color, label, created}, ...]
    color: '#e74c3c',
    imgNaturalW: 0,        // Actual macro image width in pixels
    imgNaturalH: 0,        // Actual macro image height in pixels
    macroType: 'macro',    // 'macro' or 'label'
};
let macroAnnIdCounter = 0;

const MACRO_ANN_COLORS = [
    { color: '#e74c3c', name: 'Rouge' }, { color: '#27ae60', name: 'Vert' },
    { color: '#2980b9', name: 'Bleu' }, { color: '#f39c12', name: 'Orange' },
    { color: '#8e44ad', name: 'Violet' }, { color: '#1abc9c', name: 'Turquoise' },
];

// Init macro annotation color buttons
(function() {
    const container = document.getElementById('macroAnnColors');
    container.innerHTML = MACRO_ANN_COLORS.map((c, i) => `
        <div class="macro-ann-color-btn ${i === 0 ? 'active' : ''}"
             style="background:${c.color}"
             onclick="macroAnnSetColor('${c.color}', this)"
             title="${c.name}"></div>
    `).join('');
})();

function macroAnnSetColor(color, el) {
    macroAnnState.color = color;
    document.querySelectorAll('.macro-ann-color-btn').forEach(b => b.classList.remove('active'));
    if (el) el.classList.add('active');
}

function macroAnnToggle() {
    macroAnnState.active = !macroAnnState.active;
    const btn = document.getElementById('btnMacroAnnotate');
    const toolbar = document.getElementById('macroAnnToolbar');
    const canvas = document.getElementById('macroAnnCanvas');

    btn.classList.toggle('active', macroAnnState.active);
    toolbar.classList.toggle('visible', macroAnnState.active);
    canvas.classList.toggle('drawing', macroAnnState.active);

    if (macroAnnState.active) {
        macroAnnResizeCanvas();
        macroAnnRender();
    } else {
        macroAnnState.drawing = false;
        macroAnnState.currentPath = [];
    }
}

function macroAnnResizeCanvas() {
    const img = document.getElementById('labelPopupImg');
    const canvas = document.getElementById('macroAnnCanvas');
    // Match canvas size to the displayed image size
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = img.clientWidth + 'px';
    canvas.style.height = img.clientHeight + 'px';
}

// Convert screen coordinates to macro image pixel coordinates
function macroAnnScreenToImage(screenX, screenY) {
    const img = document.getElementById('labelPopupImg');
    const rect = img.getBoundingClientRect();
    // Position relative to displayed image
    const relX = screenX - rect.left;
    const relY = screenY - rect.top;
    // Scale to natural image dimensions
    const scaleX = macroAnnState.imgNaturalW / img.clientWidth;
    const scaleY = macroAnnState.imgNaturalH / img.clientHeight;
    return [Math.round(relX * scaleX), Math.round(relY * scaleY)];
}

// Convert macro image pixel coordinates to canvas coordinates
function macroAnnImageToCanvas(imgX, imgY) {
    const img = document.getElementById('labelPopupImg');
    const scaleX = img.clientWidth / macroAnnState.imgNaturalW;
    const scaleY = img.clientHeight / macroAnnState.imgNaturalH;
    return [imgX * scaleX, imgY * scaleY];
}

function macroAnnRender() {
    const canvas = document.getElementById('macroAnnCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (const ann of macroAnnState.annotations) {
        macroAnnDrawPath(ctx, ann.points_px, ann.color, true);
    }
    if (macroAnnState.currentPath.length > 1) {
        macroAnnDrawPath(ctx, macroAnnState.currentPath, macroAnnState.color, false);
    }
}

function macroAnnDrawPath(ctx, points, color, closed) {
    if (points.length < 2) return;
    ctx.beginPath();
    const first = macroAnnImageToCanvas(points[0][0], points[0][1]);
    ctx.moveTo(first[0], first[1]);
    for (let i = 1; i < points.length; i++) {
        const pt = macroAnnImageToCanvas(points[i][0], points[i][1]);
        ctx.lineTo(pt[0], pt[1]);
    }
    if (closed) ctx.closePath();
    ctx.fillStyle = color + '25';
    if (closed) ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
}

// Drawing events on macro canvas
(function() {
    const canvas = document.getElementById('macroAnnCanvas');

    canvas.addEventListener('mousedown', (e) => {
        if (!macroAnnState.active || e.button !== 0) return;
        e.preventDefault();
        macroAnnState.drawing = true;
        macroAnnState.currentPath = [];
        const pt = macroAnnScreenToImage(e.clientX, e.clientY);
        macroAnnState.currentPath.push(pt);
    });
    canvas.addEventListener('mousemove', (e) => {
        if (!macroAnnState.drawing) return;
        const pt = macroAnnScreenToImage(e.clientX, e.clientY);
        macroAnnState.currentPath.push(pt);
        macroAnnRender();
    });
    canvas.addEventListener('mouseup', () => {
        if (!macroAnnState.drawing) return;
        macroAnnState.drawing = false;
        macroAnnFinishStroke();
    });
    canvas.addEventListener('mouseleave', () => {
        if (macroAnnState.drawing) {
            macroAnnState.drawing = false;
            macroAnnState.currentPath = [];
            macroAnnRender();
        }
    });

    // Touch support
    canvas.addEventListener('touchstart', (e) => {
        if (!macroAnnState.active || e.touches.length !== 1) return;
        e.preventDefault();
        macroAnnState.drawing = true;
        macroAnnState.currentPath = [];
        const pt = macroAnnScreenToImage(e.touches[0].clientX, e.touches[0].clientY);
        macroAnnState.currentPath.push(pt);
    }, { passive: false });
    canvas.addEventListener('touchmove', (e) => {
        if (!macroAnnState.drawing || e.touches.length !== 1) return;
        e.preventDefault();
        const pt = macroAnnScreenToImage(e.touches[0].clientX, e.touches[0].clientY);
        macroAnnState.currentPath.push(pt);
        macroAnnRender();
    }, { passive: false });
    canvas.addEventListener('touchend', () => {
        if (!macroAnnState.drawing) return;
        macroAnnState.drawing = false;
        macroAnnFinishStroke();
    });
})();

function macroAnnFinishStroke() {
    if (macroAnnState.currentPath.length > 5) {
        const label = document.getElementById('macroAnnLabelInput').value.trim() || 'Macro';
        macroAnnState.annotations.push({
            id: 'macro_ann_' + (++macroAnnIdCounter),
            points_px: [...macroAnnState.currentPath],
            color: macroAnnState.color,
            label: label,
            created: new Date().toISOString(),
        });
        macroAnnUpdateCount();
    }
    macroAnnState.currentPath = [];
    macroAnnRender();
}

function macroAnnUpdateCount() {
    document.getElementById('macroAnnCount').textContent =
        macroAnnState.annotations.length + ' annotation(s)';
}

function macroAnnUndo() {
    if (macroAnnState.annotations.length === 0) return;
    macroAnnState.annotations.pop();
    macroAnnUpdateCount();
    macroAnnRender();
}

function macroAnnClearAll() {
    if (macroAnnState.annotations.length === 0) return;
    if (!confirm(`Effacer ${macroAnnState.annotations.length} annotation(s) macro ?`)) return;
    macroAnnState.annotations = [];
    macroAnnUpdateCount();
    macroAnnRender();
}

async function macroAnnSave() {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    if (macroAnnState.annotations.length === 0) {
        toast('Aucune annotation macro à sauvegarder', true); return;
    }
    const slide = state.slides[state.currentSlideIndex];
    const features = macroAnnState.annotations.map(ann => ({
        coordinates: [ann.points_px],
        properties: {
            id: ann.id,
            label: ann.label,
            color: ann.color,
            created: ann.created,
        },
    }));
    try {
        const res = await api('/api/annotations/macro/save', {
            root: state.root,
            slide_path: slide.path,
            features: features,
            macro_dimensions: [macroAnnState.imgNaturalW, macroAnnState.imgNaturalH],
        });
        if (res.ok) toast(`${res.feature_count} annotation(s) macro sauvegardée(s)`);
        else toast('Erreur: ' + (res.error || 'inconnue'), true);
    } catch (e) { toast('Erreur réseau: ' + e.message, true); }
}

async function macroAnnLoad(slidePath) {
    macroAnnState.annotations = [];
    macroAnnUpdateCount();
    try {
        const res = await fetch(
            `${_BASE}/api/annotations/macro/load?root=${encodeURIComponent(state.root)}&slide_path=${encodeURIComponent(slidePath)}`
        );
        const data = await res.json();
        if (data.exists && data.features && data.features.length > 0) {
            for (const feat of data.features) {
                const coords = feat.geometry?.coordinates?.[0] || [];
                const p = feat.properties || {};
                macroAnnState.annotations.push({
                    id: p.id || 'macro_ann_' + (++macroAnnIdCounter),
                    points_px: coords,
                    color: p.color || '#e74c3c',
                    label: p.label || 'Macro',
                    created: p.created || '',
                });
            }
            macroAnnUpdateCount();
            toast(`${macroAnnState.annotations.length} annotation(s) macro chargée(s)`);
        }
    } catch (e) {}
    macroAnnRender();
}

// ponytail: tile export supprimé, stubs pour éviter les erreurs si appelé
function annPopulateLevels() {}
function annUpdateExportBtn() {}

// ── Display Settings (Brightness / Contrast / Gamma / Saturation / Presets) ──
const IHC_PRESETS = [
    {
        id: 'pnn', label: 'PNN / Noyaux',
        desc: 'Rehausse les noyaux polylobés (hématoxyline)',
        brightness: 1.05, contrast: 1.6, saturate: 1.3, hue: 0,
        gR: 1.8, gG: 1.2, gB: 0.6,
    },
    {
        id: 'fibrose', label: 'Fibrose',
        desc: 'Rehausse le collagène (éosine)',
        brightness: 1.05, contrast: 1.4, saturate: 1.5, hue: 0,
        gR: 0.6, gG: 1.3, gB: 1.8,
    },
    {
        id: 'trichrome', label: 'Trichrome',
        desc: 'Simule un Masson : collagène → bleu-vert',
        brightness: 1.0, contrast: 1.3, saturate: 2.0, hue: 180,
        gR: 0.8, gG: 0.7, gB: 0.9,
    },
    {
        id: 'fer', label: 'Fer / Sidéro.',
        desc: 'Rehausse l\'hémosidérine (pigment brun-doré)',
        brightness: 0.95, contrast: 1.5, saturate: 1.8, hue: 0,
        gR: 0.7, gG: 1.0, gB: 1.5,
    },
    {
        id: 'inflam', label: 'Inflammation',
        desc: 'Rehausse les cellules inflammatoires',
        brightness: 1.0, contrast: 1.8, saturate: 1.2, hue: 0,
        gR: 1.5, gG: 1.1, gB: 0.7,
    },
    {
        id: 'meconium', label: 'Méconium',
        desc: 'Rehausse le pigment méconial (vert-brun)',
        brightness: 1.0, contrast: 1.4, saturate: 2.2, hue: 0,
        gR: 1.3, gG: 0.6, gB: 1.1,
    },
    {
        id: 'erythro', label: 'Érythroblastes',
        desc: 'Rehausse les érythrocytes nucléés',
        brightness: 1.1, contrast: 1.5, saturate: 1.6, hue: 0,
        gR: 0.7, gG: 1.4, gB: 1.4,
    },
];

let activePresetId = null;

// Build preset buttons
(function() {
    const container = document.getElementById('displayPresets');
    container.innerHTML = IHC_PRESETS.map(p =>
        `<button class="display-preset-btn" data-preset="${p.id}" onclick="applyPreset('${p.id}')" title="${p.desc}">${p.label}</button>`
    ).join('');
})();

// Matrice de coloration HES (colonnes H/E/S en OD-RGB), calib_viewer.json id ab1d87f9.
// Colonnes H et S échangées vs le JSON : l'assignation dominante-canal de la NMF
// non ancrée avait interverti hématoxyline et safran (constaté à l'œil 2026-07-18).
const CHROMA_S = [[0.737, 0.000, 0.002],
                  [0.608, 0.918, 0.000],
                  [0.295, 0.396, 1.000]];
const CHROMA_SINV = inv3(CHROMA_S);

function inv3(m) {
    const a = m[0][0], b = m[0][1], c = m[0][2],
          d = m[1][0], e = m[1][1], f = m[1][2],
          g = m[2][0], h = m[2][1], i = m[2][2];
    const A = e * i - f * h, B = c * h - b * i, C = b * f - c * e;
    const det = a * A + d * B + g * C;
    return [[A / det, B / det, C / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]];
}

// Espace encre : encre ≈ 1 - I. On boost les concentrations par les gains, puis on
// recompose : I' = 1 - gK·(S·diag(gH,gE,gS)·Sinv)·(1 - I). Identité quand tous gains=1.
// V2 : luminosité (B) et saturation (V) pliées dans la même matrice (1 passe GPU).
// M = Sat(V)·B·A , T = Sat(V)·B·t. Poids luma feColorMatrix : 0.213/0.715/0.072.
function chromaMatrix() {
    const g = state.chromaGains || { H: 1, E: 1, S: 1, K: 1, B: 1, V: 1 };
    const B = g.B ?? 1, V = g.V ?? 1;
    const SG = CHROMA_S.map(row => [row[0] * g.H, row[1] * g.E, row[2] * g.S]);
    // A (3x3) + offset t : recomposition espace encre, avec luminosité B.
    const A = [], t = [];
    for (let r = 0; r < 3; r++) {
        let rowsum = 0;
        A.push([]);
        for (let cc = 0; cc < 3; cc++) {
            let a = 0;
            for (let k = 0; k < 3; k++) a += SG[r][k] * CHROMA_SINV[k][cc];
            a *= g.K * B;
            A[r].push(a);
            rowsum += a;
        }
        t.push((1 - rowsum / B) * B);   // t = B·(1 - sum(A/B)) = B - rowsum
    }
    // Saturation : Sat(V)[r][c] = luma[c]·(1-V) + (r==c ? V : 0).
    const luma = [0.213, 0.715, 0.072];
    const vals = [];
    for (let r = 0; r < 3; r++) {
        let tr = 0;
        for (let cc = 0; cc < 3; cc++) {
            let m = 0;
            for (let k = 0; k < 3; k++) {
                const sat = luma[k] * (1 - V) + (r === k ? V : 0);
                m += sat * A[k][cc];
                if (cc === 0) tr += sat * t[k];
            }
            vals.push(m);
        }
        vals.push(0);        // canal alpha
        vals.push(tr);       // offset saturé
    }
    vals.push(0, 0, 0, 1, 0);        // alpha inchangé
    return vals.map(v => v.toFixed(4)).join(' ');
}

function toggleChroma() {
    state.chromaOn = !state.chromaOn;
    if (!state.chromaGains) state.chromaGains = { H: 1, E: 1, S: 1, K: 1, B: 1, V: 1 };
    document.getElementById('btnChroma').classList.toggle('active', state.chromaOn);
    document.getElementById('chromaChannels').classList.toggle('visible', state.chromaOn);
    document.getElementById('chromaMat').setAttribute('values', chromaMatrix());
    updateDisplayFilters('chroma');
}

function chromaGainLabel(ch) {
    const v = parseFloat(document.getElementById('chroma' + ch).value);
    document.getElementById('chroma' + ch + 'Val').textContent = v.toFixed(2);
    (state.chromaGains || (state.chromaGains = { H: 1, E: 1, S: 1, K: 1, B: 1, V: 1 }))[ch] = v;
    document.getElementById('chromaMat').setAttribute('values', chromaMatrix());
    updateDisplayFilters('chroma');
}

function toggleDisplaySettings() {
    const panel = document.getElementById('displaySettings');
    const btn = document.getElementById('btnDisplay');
    const isVisible = panel.classList.contains('visible');
    panel.classList.toggle('visible', !isVisible);
    btn.classList.toggle('active', !isVisible);
}

function toggleChannelGamma() {
    const group = document.getElementById('channelGroup');
    const arrow = document.getElementById('channelArrow');
    const vis = group.classList.toggle('visible');
    arrow.classList.toggle('open', vis);
}

function updateDisplayFilters(fromChannel) {
    const brightness = parseFloat(document.getElementById('brightnessSlider').value);
    const contrast = parseFloat(document.getElementById('contrastSlider').value);
    const saturate = parseFloat(document.getElementById('saturateSlider').value);
    const hue = parseFloat(document.getElementById('hueSlider').value);
    let gR = parseFloat(document.getElementById('gammaRSlider').value);
    let gG = parseFloat(document.getElementById('gammaGSlider').value);
    let gB = parseFloat(document.getElementById('gammaBSlider').value);

    // Update value labels
    document.getElementById('brightnessVal').textContent = brightness.toFixed(2);
    document.getElementById('contrastVal').textContent = contrast.toFixed(2);
    document.getElementById('saturateVal').textContent = saturate.toFixed(2);
    document.getElementById('hueVal').textContent = Math.round(hue) + '°';
    document.getElementById('gammaRVal').textContent = gR.toFixed(2);
    document.getElementById('gammaGVal').textContent = gG.toFixed(2);
    document.getElementById('gammaBVal').textContent = gB.toFixed(2);

    // Update SVG gamma filter per channel
    document.getElementById('gammaR').setAttribute('exponent', gR);
    document.getElementById('gammaG').setAttribute('exponent', gG);
    document.getElementById('gammaB').setAttribute('exponent', gB);

    // Apply combined CSS filter (CHROMA d'abord pour démixer avant les réglages d'affichage)
    const viewer = document.getElementById('viewer');
    const gammaActive = gR !== 1 || gG !== 1 || gB !== 1;
    const parts = [];
    if (state.chromaOn) parts.push('url(#chromaFilter)');
    if (gammaActive) parts.push('url(#gammaFilter)');
    if (brightness !== 1) parts.push(`brightness(${brightness})`);
    if (contrast !== 1) parts.push(`contrast(${contrast})`);
    if (saturate !== 1) parts.push(`saturate(${saturate})`);
    if (hue !== 0) parts.push(`hue-rotate(${hue}deg)`);
    viewer.style.filter = parts.join(' ');

    // Clear active preset highlight if user manually changed a slider
    if (!fromChannel || fromChannel === true) {
        activePresetId = null;
        document.querySelectorAll('.display-preset-btn').forEach(b => b.classList.remove('active'));
    }
}

function applyPreset(presetId) {
    const p = IHC_PRESETS.find(x => x.id === presetId);
    if (!p) return;
    document.getElementById('brightnessSlider').value = p.brightness;
    document.getElementById('contrastSlider').value = p.contrast;
    document.getElementById('saturateSlider').value = p.saturate;
    document.getElementById('hueSlider').value = p.hue;
    document.getElementById('gammaRSlider').value = p.gR;
    document.getElementById('gammaGSlider').value = p.gG;
    document.getElementById('gammaBSlider').value = p.gB;

    // Show per-channel gamma if channels differ
    if (p.gR !== p.gG || p.gG !== p.gB) {
        document.getElementById('channelGroup').classList.add('visible');
        document.getElementById('channelArrow').classList.add('open');
    }

    activePresetId = presetId;
    document.querySelectorAll('.display-preset-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.preset === presetId);
    });

    updateDisplayFilters('preset');
}

function resetDisplaySettings() {
    document.getElementById('brightnessSlider').value = 1;
    document.getElementById('contrastSlider').value = 1;
    document.getElementById('saturateSlider').value = 1;
    document.getElementById('hueSlider').value = 0;
    document.getElementById('gammaRSlider').value = 1;
    document.getElementById('gammaGSlider').value = 1;
    document.getElementById('gammaBSlider').value = 1;
    activePresetId = null;
    document.querySelectorAll('.display-preset-btn').forEach(b => b.classList.remove('active'));
    updateDisplayFilters('preset');
}

// ── Sidebar Resize ───────────────────────────────────────
(function() {
    const handle = document.getElementById('resizeHandle');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('dragOverlay');
    const MIN_W = 140, MAX_W = 600;
    let dragging = false, startX, startW;
    function startDrag(x) {
        dragging = true; startX = x; startW = sidebar.offsetWidth;
        handle.classList.add('dragging'); overlay.classList.add('active');
    }
    function doDrag(x) {
        if (!dragging) return;
        const w = Math.min(MAX_W, Math.max(MIN_W, startW + (x - startX)));
        sidebar.style.width = w + 'px'; sidebar.style.minWidth = w + 'px';
    }
    function stopDrag() {
        if (!dragging) return;
        dragging = false; handle.classList.remove('dragging'); overlay.classList.remove('active');
        if (state.osdViewer) setTimeout(() => state.osdViewer.viewport.resize(), 50);
    }
    handle.addEventListener('mousedown', (e) => { e.preventDefault(); startDrag(e.clientX); });
    document.addEventListener('mousemove', (e) => doDrag(e.clientX));
    document.addEventListener('mouseup', stopDrag);
    overlay.addEventListener('mousemove', (e) => doDrag(e.clientX));
    overlay.addEventListener('mouseup', stopDrag);
    handle.addEventListener('touchstart', (e) => startDrag(e.touches[0].clientX), { passive: true });
    document.addEventListener('touchmove', (e) => { if (dragging) doDrag(e.touches[0].clientX); }, { passive: true });
    document.addEventListener('touchend', stopDrag);
})();

// ── Right Panel Resize ───────────────────────────────────
(function() {
    const handle = document.getElementById('resizeHandleRight');
    const annPanel = document.getElementById('annPanel');
    const overlay = document.getElementById('dragOverlay');
    const MIN_W = 280, MAX_W = 900;
    let dragging = false, startX, startW, activePanel;

    function getActivePanel() {
        return annPanel.classList.contains('visible') ? annPanel : null;
    }

    function startDrag(x) {
        activePanel = getActivePanel();
        if (!activePanel) return;
        dragging = true; startX = x; startW = activePanel.offsetWidth;
        handle.classList.add('dragging'); overlay.classList.add('active');
        activePanel.classList.add('no-transition');
    }
    function doDrag(x) {
        if (!dragging || !activePanel) return;
        const w = Math.min(MAX_W, Math.max(MIN_W, startW - (x - startX)));
        activePanel.style.width = w + 'px'; activePanel.style.minWidth = w + 'px';
    }
    function stopDrag() {
        if (!dragging) return;
        dragging = false; handle.classList.remove('dragging'); overlay.classList.remove('active');
        if (activePanel) activePanel.classList.remove('no-transition');
        if (state.osdViewer) setTimeout(() => state.osdViewer.viewport.resize(), 50);
    }
    handle.addEventListener('mousedown', (e) => { e.preventDefault(); startDrag(e.clientX); });
    document.addEventListener('mousemove', (e) => doDrag(e.clientX));
    document.addEventListener('mouseup', stopDrag);
    overlay.addEventListener('mousemove', (e) => doDrag(e.clientX));
    overlay.addEventListener('mouseup', stopDrag);
    handle.addEventListener('touchstart', (e) => startDrag(e.touches[0].clientX), { passive: true });
    document.addEventListener('touchmove', (e) => { if (dragging) doDrag(e.touches[0].clientX); }, { passive: true });
    document.addEventListener('touchend', stopDrag);
})();

// ── Labellisation System ────────────────────────────────

function labelToggleTissue(tissue, el) {
    if (tissue in state.labelOrgans) {
        delete state.labelOrgans[tissue];
        if (el) el.classList.remove('active');
    } else {
        state.labelOrgans[tissue] = 'normal';
        if (el) el.classList.add('active');
    }
    labelRefreshUI();
}

function labelRefreshUI() {
    const hasOrgan = Object.keys(state.labelOrgans).length > 0;
    document.getElementById('labelStatusSection').style.display = hasOrgan ? '' : 'none';

    const values = Object.values(state.labelOrgans);
    const allNormal = values.length > 0 && values.every(v => v === 'normal');
    const anyPatho = values.some(v => v === 'patho');
    document.getElementById('btnNormal').classList.toggle('active', allNormal);
    document.getElementById('btnPatho').classList.toggle('active', anyPatho);

    document.getElementById('labelSignsSection').style.display = anyPatho ? '' : 'none';
    document.getElementById('labelRetentionSection').style.display = anyPatho ? '' : 'none';
    document.getElementById('labelMaturationSection').style.display = hasOrgan ? '' : 'none';

    // Sync tissue buttons in placenta mode
    if (state.domain === 'placenta') {
        document.querySelectorAll('#labelPlacentaSection .tissue-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.tissue in state.labelOrgans);
        });
    }

    labelRenderQuickTags();
    _loadLabelTerms();
    if (state.domain === 'foetus') {
        labelRenderOrganPills();
    }
}

function labelRenderOrganPills() {
    const el = document.getElementById('labelOrganPills');
    if (!el) return;
    el.innerHTML = FOETO_ORGANS.map(o => {
        const status = state.labelOrgans[o];
        let cls = '';
        if (status === 'normal') cls = 'label-normal';
        else if (status === 'patho') cls = 'label-patho';
        const label = _LABELS[o] || o;
        return `<span class="ann-diag-tag organ-pill ${cls}" onclick="labelToggleOrgan('${o}')">${label}</span>`;
    }).join('');
}

function labelToggleOrgan(organ) {
    if (organ in state.labelOrgans) {
        delete state.labelOrgans[organ];
    } else {
        state.labelOrgans[organ] = 'normal';
    }
    labelRefreshUI();
}

function setOrganStatus(status) {
    const organs = Object.keys(state.labelOrgans);
    if (organs.length === 0) { toast('Sélectionnez au moins un organe', true); return; }

    if (status === 'normal') {
        // If switching from patho to normal, confirm if diagnoses exist
        const hadPatho = Object.values(state.labelOrgans).some(v => v === 'patho');
        if (hadPatho && state.labelDiagnoses.length > 0) {
            if (!confirm('Passer en Normal effacera les signes sélectionnés. Continuer ?')) return;
            state.labelDiagnoses = [];
        }
    }

    for (const org of organs) {
        state.labelOrgans[org] = status;
    }
    labelRefreshUI();
}

function _loadLabelTerms() {
    const organs = Object.keys(state.labelOrgans);
    if (organs.length === 0) return;
    const queryOrgans = state.domain === 'placenta' ? [...new Set([...organs, 'placenta'])] : organs;
    fetch(_url('/api/foeto/terms?organs=' + queryOrgans.join(','))).then(r => r.json()).then(data => {
        Object.assign(FOETO_TERMS_CACHE, data.terms || {});
        Object.assign(FOETO_QUICK_CACHE, data.quick || {});
        Object.assign(FOETO_RETENTION_CACHE, data.retention || {});
        Object.assign(FOETO_MATURATION_CACHE, data.maturation || {});
        labelRenderQuickTags();
        labelRenderRetentionTags();
        labelRenderMaturationTags();
        labelRenderSelectedSigns();
        _buildLabelSignOptions();
    }).catch(() => {});
}

function labelRenderQuickTags() {
    const el = document.getElementById('labelQuickTags');
    if (!el) return;
    const organs = Object.keys(state.labelOrgans);
    if (organs.length === 0) { el.innerHTML = ''; return; }
    let html = '';
    for (const org of organs) {
        const quick = FOETO_QUICK_CACHE[org] || [];
        if (quick.length === 0) continue;
        const label = _LABELS[org] || org.charAt(0).toUpperCase() + org.slice(1);
        html += `<span style="font-size:9px;color:var(--text-muted);width:100%;margin-top:2px;">${label}</span>`;
        const grouped = {};
        for (const t of quick) { (grouped[t.group || ''] ??= []).push(t); }
        for (const [grp, items] of Object.entries(grouped)) {
            if (grp) html += `<span class="tag-group-label">${grp}</span>`;
            html += items.map(t => {
                const entry = _findDiagEntry(state.labelDiagnoses, t.id);
                const sel = entry ? 'selected' : '';
                const short = t.label.length > 40 ? t.label.slice(0, 38) + '...' : t.label;
                const simBtn = sel ? ` <span class="sim-btn" onclick="event.stopPropagation();openSimilar('${t.id}')" title="Lames similaires">&#128269;</span>` : '';
                let gradeHtml = '';
                if (sel && _isGradable(t.id)) {
                    const g = _diagGrade(entry);
                    gradeHtml = `<span class="grade-btns">${FOETO_GRADES[t.id].map(gi =>
                        `<span class="grade-btn${g===gi.grade?' active':''}" title="${gi.desc}" onclick="event.stopPropagation();labelSetGrade('${t.id}',${gi.grade})">G${gi.grade}</span>`
                    ).join('')}</span>`;
                }
                return `<span class="ann-diag-tag ${sel}" title="${t.label}" onclick="labelToggleDiag('${t.id}')">${short}${simBtn}</span>${gradeHtml}`;
            }).join('');
        }
    }
    el.innerHTML = html || '<span style="font-size:10px;color:var(--text-muted);">Aucun signe rapide</span>';
}

function _labelTermLabel(id) {
    for (const org of Object.keys(state.labelOrgans)) {
        for (const terms of Object.values(FOETO_TERMS_CACHE[org] || {})) {
            const t = terms.find(x => x.id === id); if (t) return t.label;
        }
        for (const cache of [FOETO_RETENTION_CACHE, FOETO_MATURATION_CACHE, FOETO_QUICK_CACHE]) {
            const t = (cache[org] || []).find(x => x.id === id); if (t) return t.label;
        }
    }
    return id;
}

function labelRenderSelectedSigns() {
    const el = document.getElementById('labelSelectedSigns');
    if (!el) return;
    if (!state.labelDiagnoses.length) { el.innerHTML = ''; return; }
    el.innerHTML = '<span class="ann-tools-row-label" style="width:100%;margin-top:2px;">Sélectionnés</span>' +
        state.labelDiagnoses.map(d => {
            const base = _diagBaseId(d), g = _diagGrade(d);
            const lbl = _labelTermLabel(base) + (g ? ` (G${g})` : '');
            return `<span class="ann-diag-tag selected" title="Retirer" onclick="labelToggleDiag('${base}')">${lbl} &times;</span>`;
        }).join('');
}

function _labelRefreshDiags() {
    labelRenderQuickTags(); labelRenderRetentionTags(); labelRenderMaturationTags();
    labelRenderSelectedSigns(); labelSignSearchUpdate();
}

function labelToggleDiag(id) {
    const existing = _findDiagEntry(state.labelDiagnoses, id);
    if (existing) state.labelDiagnoses.splice(state.labelDiagnoses.indexOf(existing), 1);
    else state.labelDiagnoses.push(id);
    _labelRefreshDiags();
}

function labelSetGrade(termId, grade) {
    const existing = _findDiagEntry(state.labelDiagnoses, termId);
    if (existing) state.labelDiagnoses.splice(state.labelDiagnoses.indexOf(existing), 1);
    const cur = _diagGrade(existing || '');
    // ponytail: toggle off if same grade clicked again
    state.labelDiagnoses.push(cur === grade ? termId : `${termId}.G${grade}`);
    _labelRefreshDiags();
}

function labelRenderRetentionTags() {
    const el = document.getElementById('labelRetentionTags');
    if (!el) return;
    const organs = Object.keys(state.labelOrgans);
    let html = '';
    for (const org of organs) {
        const items = FOETO_RETENTION_CACHE[org] || [];
        if (items.length === 0) continue;
        const label = _LABELS[org] || org;
        html += `<span style="font-size:9px;color:var(--text-muted);width:100%;margin-top:2px;">${label}</span>`;
        html += items.map(t => {
            const entry = _findDiagEntry(state.labelDiagnoses, t.id);
            const sel = entry ? 'selected' : '';
            const short = t.label.length > 50 ? t.label.slice(0, 48) + '...' : t.label;
            const simBtn = sel ? ` <span class="sim-btn" onclick="event.stopPropagation();openSimilar('${t.id}')" title="Lames similaires">&#128269;</span>` : '';
            let gradeHtml = '';
            if (sel && _isGradable(t.id)) {
                const g = _diagGrade(entry);
                gradeHtml = `<span class="grade-btns">${FOETO_GRADES[t.id].map(gi =>
                    `<span class="grade-btn${g===gi.grade?' active':''}" title="${gi.desc}" onclick="event.stopPropagation();labelSetGrade('${t.id}',${gi.grade})">G${gi.grade}</span>`
                ).join('')}</span>`;
            }
            return `<span class="ann-diag-tag retention-tag ${sel}" title="${t.label}" onclick="labelToggleDiag('${t.id}')">${short}${simBtn}</span>${gradeHtml}`;
        }).join('');
    }
    el.innerHTML = html || '';
}

function labelRenderMaturationTags() {
    const el = document.getElementById('labelMaturationTags');
    if (!el) return;
    const organs = Object.keys(state.labelOrgans);
    let html = '';
    for (const org of organs) {
        const items = FOETO_MATURATION_CACHE[org] || [];
        if (items.length === 0) continue;
        const label = _LABELS[org] || org;
        html += `<span style="font-size:9px;color:var(--text-muted);width:100%;margin-top:2px;">${label}</span>`;
        const grouped = {};
        for (const t of items) { (grouped[t.group || ''] ??= []).push(t); }
        for (const [grp, gItems] of Object.entries(grouped)) {
            if (grp) html += `<span class="tag-group-label">${grp}</span>`;
            html += gItems.map(t => {
                const entry = _findDiagEntry(state.labelDiagnoses, t.id);
                const sel = entry ? 'selected' : '';
                const short = t.label.length > 50 ? t.label.slice(0, 48) + '...' : t.label;
                let gradeHtml = '';
                if (sel && _isGradable(t.id)) {
                    const g = _diagGrade(entry);
                    gradeHtml = `<span class="grade-btns">${FOETO_GRADES[t.id].map(gi =>
                        `<span class="grade-btn${g===gi.grade?' active':''}" title="${gi.desc}" onclick="event.stopPropagation();labelSetGrade('${t.id}',${gi.grade})">G${gi.grade}</span>`
                    ).join('')}</span>`;
                }
                return `<span class="ann-diag-tag maturation-tag ${sel}" title="${t.label}" onclick="labelToggleDiag('${t.id}')">${short}</span>${gradeHtml}`;
            }).join('');
        }
    }
    el.innerHTML = html || '';
}

let _labelSignOptions = [];
function _buildLabelSignOptions() {
    _labelSignOptions = [];
    for (const org of Object.keys(state.labelOrgans)) {
        const byAxis = FOETO_TERMS_CACHE[org] || {};
        const label = _LABELS[org] || org;
        for (const terms of Object.values(byAxis)) {
            for (const t of terms) _labelSignOptions.push({ ...t, org, orgLabel: label });
        }
    }
}

function labelSignSearchUpdate() {
    const q = (document.getElementById('labelSignSearch').value || '').toLowerCase().trim();
    const el = document.getElementById('labelSignResults');
    if (!q || q.length < 3) { el.innerHTML = ''; return; }
    const hits = _labelSignOptions.filter(t => t.label.toLowerCase().includes(q)).slice(0, 15);
    if (hits.length === 0) { el.innerHTML = '<span style="font-size:10px;color:var(--text-muted);padding:2px 4px;">Aucun résultat</span>'; return; }
    el.innerHTML = hits.map(t => {
        const entry = _findDiagEntry(state.labelDiagnoses, t.id);
        const sel = entry ? 'selected' : '';
        const short = t.label.length > 55 ? t.label.slice(0, 53) + '...' : t.label;
        const simBtn = sel ? ` <span class="sim-btn" onclick="event.stopPropagation();openSimilar('${t.id}')" title="Lames similaires">&#128269;</span>` : '';
        let gradeHtml = '';
        if (sel && _isGradable(t.id)) {
            const g = _diagGrade(entry);
            gradeHtml = `<span class="grade-btns">${FOETO_GRADES[t.id].map(gi =>
                `<span class="grade-btn${g===gi.grade?' active':''}" title="${gi.desc}" onclick="event.stopPropagation();labelSetGrade('${t.id}',${gi.grade})">G${gi.grade}</span>`
            ).join('')}</span>`;
        }
        return `<span class="ann-diag-tag ${sel}" title="${t.orgLabel}: ${t.label}" onclick="labelToggleDiag('${t.id}')">${short}${simBtn}</span>${gradeHtml}`;
    }).join('');
}

async function labelSave() {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const slide = state.slides[state.currentSlideIndex];
    const slideId = slide.name; // stem
    const organs = Object.entries(state.labelOrgans).map(([organ, status]) => ({ organ, status }));
    const note = document.getElementById('labelNote').value.trim();

    try {
        const res = await api('/api/slide/label-save', {
            slide_id: slideId,
            slide_path: slide.path,
            organs: organs,
            diagnoses: state.labelDiagnoses,
            note: note,
        });
        if (res.ok) {
            toast('Labellisation sauvegardée');
            loadCaseIndex();
            // Update local carousel badge
            state.labelSummary[slideId] = res.labeled ? 'labeled' : 'unlabeled';
            renderCarousel();
        } else {
            toast('Erreur: ' + (res.error || 'inconnue'), true);
        }
    } catch (e) { toast('Erreur réseau: ' + e.message, true); }
}

async function labelNormalAndNext() {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const organs = Object.keys(state.labelOrgans);
    if (organs.length === 0) { toast('Sélectionnez au moins un organe/tissu', true); return; }
    for (const org of organs) state.labelOrgans[org] = 'normal';
    state.labelDiagnoses = [];
    await labelSave();
    navNext();
}

async function labelLoad(slideId) {
    state.labelOrgans = {};
    state.labelDiagnoses = [];
    state.labelNote = '';
    const noteEl = document.getElementById('labelNote');
    if (noteEl) noteEl.value = '';

    try {
        const res = await fetch(_url(`/api/slide/label-status?slide_id=${encodeURIComponent(slideId)}`));
        const data = await res.json();
        if (data.organs && data.organs.length > 0) {
            for (const o of data.organs) {
                state.labelOrgans[o.organ] = o.status;
            }
        }
        if (data.diagnoses) state.labelDiagnoses = data.diagnoses;
        if (data.note) {
            state.labelNote = data.note;
            if (noteEl) noteEl.value = data.note;
        }
    } catch (e) {}

    labelRefreshUI();
}

// ── Context Menu (right-click on viewer) ─────────────────

// Sous-menu d'un tissu construit depuis les quick picks DB (viewer_quick=1), plus aucun signe hardcodé.
function _ctxOrganSubmenu(organ) {
    let html = `<div class="ctx-menu-item accent" onclick="ctxLabelQuick('${organ}','normal')"><span class="ctx-check">&#10003;</span> Normal</div>`;
    for (const t of (FOETO_QUICK_CACHE[organ] || [])) {
        const sel = state.labelDiagnoses.includes(t.id);
        html += `<div class="ctx-menu-item ${sel ? 'selected' : ''}" onclick="ctxLabelQuick('${organ}','patho','${t.id}')"><span class="ctx-check">${sel ? '&#10003;' : ''}</span>${t.label}</div>`;
    }
    return html;
}

function showContextMenu(x, y) {
    if (state.viewMode !== 'slide' || state.currentSlideIndex < 0) return;
    const menu = document.getElementById('ctxMenu');
    const organs = Object.keys(state.labelOrgans);
    const anyPatho = Object.values(state.labelOrgans).some(v => v === 'patho');

    let html = '';
    // Normal + Save + Next
    html += `<div class="ctx-menu-item accent" onclick="ctxNormal()"><span class="ctx-check">&#10003;</span> Normal &rarr; suivante</div>`;

    // Placenta labelling tree (DB-driven : un sous-menu par tissu, signes = quick picks)
    if (state.domain === 'placenta') {
        html += '<div class="ctx-menu-sep"></div>';
        for (const t of PLACENTA_TISSUS) {
            html += `<div class="ctx-menu-sub"><div class="ctx-menu-item">${t.label} &#9656;</div><div class="ctx-submenu">${_ctxOrganSubmenu(t.name)}</div></div>`;
        }
    }

    // Quick picks grouped by type_patho (only if organ selected + patho)
    if (organs.length > 0 && anyPatho) {
        const all = [];
        for (const org of organs) {
            for (const t of (FOETO_QUICK_CACHE[org] || [])) {
                if (!all.find(p => p.id === t.id)) all.push(t);
            }
        }
        if (all.length > 0) {
            const grouped = {};
            for (const t of all) { (grouped[t.group || ''] ??= []).push(t); }
            for (const [grp, items] of Object.entries(grouped)) {
                html += '<div class="ctx-menu-sep"></div>';
                if (grp) html += `<div class="ctx-menu-group">${grp}</div>`;
                for (const p of items) {
                    const sel = state.labelDiagnoses.includes(p.id);
                    const short = p.label.length > 35 ? p.label.slice(0, 33) + '...' : p.label;
                    html += `<div class="ctx-menu-item ${sel ? 'selected' : ''}" onclick="ctxToggleSign('${p.id}')"><span class="ctx-check">${sel ? '&#10003;' : ''}</span>${short}</div>`;
                }
            }
        }
    }

    html += '<div class="ctx-menu-sep"></div>';
    html += `<div class="ctx-menu-item" onclick="ctxAnnotate()"><span class="ctx-check">&#9998;</span> Annoter ici &rarr;</div>`;
    if (state.labelDiagnoses.length > 0) {
        html += `<div class="ctx-menu-item" onclick="ctxSimilar()"><span class="ctx-check">&#128269;</span> Lames similaires &rarr;</div>`;
    }
    html += `<div class="ctx-menu-item" onclick="ctxNote()"><span class="ctx-check">&#9998;</span> Note...</div>`;

    menu.innerHTML = html;

    // Position (keep within viewport)
    menu.style.left = Math.min(x, window.innerWidth - 220) + 'px';
    menu.style.top = Math.min(y, window.innerHeight - 200) + 'px';
    menu.classList.add('visible');
}

function hideContextMenu() {
    document.getElementById('ctxMenu').classList.remove('visible');
}

function ctxNormal() {
    hideContextMenu();
    labelNormalAndNext();
}

function ctxLabelQuick(organ, status, diagId) {
    hideContextMenu();
    state.labelOrgans[organ] = status;
    if (diagId && !state.labelDiagnoses.includes(diagId)) state.labelDiagnoses.push(diagId);
    labelRefreshUI();
    labelSave();
}

function ctxToggleSign(id) {
    labelToggleDiag(id);
    // Re-render menu in place to update checkmarks
    const menu = document.getElementById('ctxMenu');
    const rect = menu.getBoundingClientRect();
    showContextMenu(rect.left, rect.top);
}

function ctxAnnotate() {
    hideContextMenu();
    openPanelRight('annotate');
}

function ctxNote() {
    hideContextMenu();
    openPanelRight('label');
    setTimeout(() => document.getElementById('labelNote').focus(), 100);
}

// Capture right-click on viewer
document.getElementById('viewer').addEventListener('contextmenu', e => {
    e.preventDefault();          // en peinture le clic droit est le pinceau, pas un menu
    if (state.measureMode || state.editMode !== 'nav') return;
    e.stopPropagation();
    showContextMenu(e.clientX, e.clientY);
});

// Close on click outside or Escape
document.addEventListener('mousedown', e => {
    const menu = document.getElementById('ctxMenu');
    if (menu.classList.contains('visible') && !menu.contains(e.target)) hideContextMenu();
});
// ponytail: Escape handler already exists in keydown, add ctx close there

// ── Similar Slides Gallery ──────────────────────────────

function ctxSimilar() {
    hideContextMenu();
    if (state.labelDiagnoses.length > 0) openSimilar(state.labelDiagnoses[0]);
}

async function openSimilar(diagId) {
    const dialog = document.getElementById('similarDialog');
    const title = document.getElementById('similarTitle');
    const grid = document.getElementById('similarGrid');

    title.textContent = 'Chargement...';
    grid.innerHTML = '';
    dialog.showModal();

    try {
        const res = await fetch(_url(`/api/slides/similar?diagnosis=${encodeURIComponent(diagId)}`));
        const data = await res.json();
        title.textContent = `${data.label} (${data.diagnosis}) — ${data.slides.length} lame(s)`;
        if (data.slides.length === 0) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px;">Aucune lame avec ce signe</div>';
            return;
        }
        grid.innerHTML = data.slides.map(s => {
            const thumbUrl = s.filename && s.folder
                ? `${_BASE}/api/slide/thumbnail?path=${encodeURIComponent(s.folder + '/' + s.filename)}&w=240&h=240`
                : '';
            const caseName = s.folder ? s.folder.split('/').pop() : '';
            return `<div class="similar-card" onclick="navigateToSimilar('${encodeURIComponent(s.folder)}','${encodeURIComponent(s.folder + '/' + s.filename)}')" title="${s.slide_id}">
                ${thumbUrl ? `<img src="${thumbUrl}" alt="${s.slide_id}" loading="lazy">` : '<div style="width:100%;aspect-ratio:1;background:var(--bg-tertiary);border-radius:var(--radius-sm)"></div>'}
                <div class="similar-card-label">${caseName}</div>
                <div class="similar-card-sub">${s.slide_id}${s.organs.length ? ' · ' + s.organs.join(', ') : ''}</div>
            </div>`;
        }).join('');
    } catch (e) {
        title.textContent = 'Erreur';
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--danger);padding:24px;">${e.message}</div>`;
    }
}

function closeSimilar() {
    document.getElementById('similarDialog').close();
}

function navigateToSimilar(folderEnc, pathEnc) {
    closeSimilar();
    const folder = decodeURIComponent(folderEnc);
    const path = decodeURIComponent(pathEnc);
    // Same case? Just switch slide
    if (state.currentCase !== null && state.cases[state.currentCase] && state.cases[state.currentCase].path === folder) {
        const idx = state.slides.findIndex(s => s.path === path);
        if (idx >= 0) { loadSlide(idx); return; }
    }
    // Different case: find it, load it, then auto-navigate to the slide
    const caseIdx = state.cases.findIndex(c => c.path === folder);
    if (caseIdx >= 0) {
        state._autoSlide = path;
        selectCase(caseIdx);
    } else {
        toast('Cas non trouvé dans le dossier actuel', true);
    }
}

// Close dialog on backdrop click
document.getElementById('similarDialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeSimilar();
});

// ── URL params & focused mode ────────────────────────────
(function() {
    const params = new URLSearchParams(window.location.search);
    const root = params.get('root');
    const slidePath = params.get('slide');
    if (root) document.getElementById('rootInput').value = root;

    if (root && slidePath) {
        // Focused mode (opened from a case): left column becomes the case index
        document.querySelector('.folder-input-group').style.display = 'none';
        document.getElementById('caseList').style.display = 'none';
        const hdr = document.querySelector('.sidebar-header');
        if (hdr) hdr.style.display = 'none';
        document.getElementById('caseIndex').style.display = '';
        state._autoSlide = slidePath;
    }
})();

// ── Auto-load ────────────────────────────────────────────
if (document.getElementById('rootInput').value.trim()) {
    loadCases().then(() => {
        if (state._autoSlide && state.cases.length) selectCase(0);
    });
}
