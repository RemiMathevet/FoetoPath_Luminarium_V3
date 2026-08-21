const lbState = { photos: [], idx: 0, zoom: 1, rotation: 0, fit: true, panX: 0, panY: 0, dragging: false, startX: 0, startY: 0 };

function openLightbox(photos, startIdx) {
    lbState.photos = photos;
    lbState.idx = startIdx || 0;
    lbState.zoom = 1; lbState.rotation = 0; lbState.fit = true; lbState.panX = 0; lbState.panY = 0;
    document.getElementById('photoLightbox').classList.add('visible');
    lbUpdate();
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    document.getElementById('photoLightbox').classList.remove('visible');
    document.body.style.overflow = '';
}

function lbNav(dir) {
    lbState.idx = (lbState.idx + dir + lbState.photos.length) % lbState.photos.length;
    lbState.zoom = 1; lbState.rotation = 0; lbState.fit = true; lbState.panX = 0; lbState.panY = 0;
    lbUpdate();
}

function lbUpdate() {
    const p = lbState.photos[lbState.idx];
    if (!p) return;
    const img = document.getElementById('lbImg');
    img.src = p.full;
    document.getElementById('lbTitle').textContent = p.label || '';
    document.getElementById('lbCounter').textContent = (lbState.idx + 1) + ' / ' + lbState.photos.length;
    lbApplyTransform();
}

function lbApplyTransform() {
    const img = document.getElementById('lbImg');
    const s = lbState;
    if (s.fit) {
        img.style.maxWidth = '90vw'; img.style.maxHeight = '80vh';
    } else {
        img.style.maxWidth = 'none'; img.style.maxHeight = 'none';
    }
    img.style.transform = `translate(${s.panX}px, ${s.panY}px) scale(${s.zoom}) rotate(${s.rotation}deg)`;
}

function lbZoom(dir) {
    const steps = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8];
    const cur = lbState.zoom;
    let nextIdx;
    if (dir > 0) {
        nextIdx = steps.findIndex(s => s > cur + 0.01);
        if (nextIdx < 0) nextIdx = steps.length - 1;
    } else {
        nextIdx = steps.length - 1;
        for (let i = steps.length - 1; i >= 0; i--) { if (steps[i] < cur - 0.01) { nextIdx = i; break; } }
    }
    lbState.zoom = steps[nextIdx];
    lbState.fit = false;
    lbApplyTransform();
}

function lbZoomReset() {
    lbState.zoom = 1; lbState.panX = 0; lbState.panY = 0; lbState.fit = false;
    lbApplyTransform();
}

function lbFitToggle() {
    lbState.fit = !lbState.fit;
    if (lbState.fit) { lbState.zoom = 1; lbState.panX = 0; lbState.panY = 0; }
    lbApplyTransform();
}

function lbRotate(deg) {
    lbState.rotation = (lbState.rotation + deg) % 360;
    lbApplyTransform();
}

// Pan support (drag)
(function initLbPan() {
    const wrap = document.getElementById('lbImgWrap');
    if (!wrap) return;
    wrap.addEventListener('mousedown', e => {
        if (e.target.closest('.lightbox-nav')) return;
        lbState.dragging = true; lbState.startX = e.clientX - lbState.panX; lbState.startY = e.clientY - lbState.panY;
        wrap.classList.add('grabbing');
    });
    document.addEventListener('mousemove', e => {
        if (!lbState.dragging) return;
        lbState.panX = e.clientX - lbState.startX; lbState.panY = e.clientY - lbState.startY;
        lbApplyTransform();
    });
    document.addEventListener('mouseup', () => {
        lbState.dragging = false;
        document.getElementById('lbImgWrap')?.classList.remove('grabbing');
    });
    // Mouse wheel zoom
    wrap.addEventListener('wheel', e => {
        e.preventDefault();
        lbZoom(e.deltaY < 0 ? 1 : -1);
    }, { passive: false });
})();

// Keyboard navigation
document.addEventListener('keydown', e => {
    if (!document.getElementById('photoLightbox').classList.contains('visible')) return;
    if (e.key === 'Escape') closeLightbox();
    else if (e.key === 'ArrowLeft') lbNav(-1);
    else if (e.key === 'ArrowRight') lbNav(1);
    else if (e.key === '+' || e.key === '=') lbZoom(1);
    else if (e.key === '-') lbZoom(-1);
    else if (e.key === '0') lbZoomReset();
    else if (e.key === 'r' || e.key === 'R') lbRotate(e.shiftKey ? -90 : 90);
    else if (e.key === 'f' || e.key === 'F') lbFitToggle();
});

// ── Init ─────────────────────────────────────
loadViewerUrl();
loadCases();

