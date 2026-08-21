/* ═══ FoetoPath — Shared Helpers ═══ */

// ── Safe DOM access ──
function gid(id) { return document.getElementById(id); }
function gval(id) { var el = gid(id); return el ? el.value : ''; }
function qsa(sel) { try { return document.querySelectorAll(sel); } catch(e) { return []; } }
function qs(sel) { try { return document.querySelector(sel); } catch(e) { return null; } }
function findParent(el, cls) {
  var node = el ? el.parentNode : null;
  while (node && node !== document) {
    if (node.classList && node.classList.contains(cls)) return node;
    node = node.parentNode;
  }
  return null;
}

// ── Accordion ──
function toggleAcc(id) {
  var el = gid(id); if (!el) return;
  el.classList.toggle('open');
}
function scrollToSection(id) {
  var el = gid(id); if (!el) return;
  if (!el.classList.contains('open')) el.classList.add('open');
  var hdr = qs('.header');
  var headerH = hdr ? hdr.offsetHeight : 80;
  var y = el.getBoundingClientRect().top + window.pageYOffset - headerH - 8;
  window.scrollTo({ top: y, behavior: 'smooth' });
  setActivePill(id);
}
// Alias for pages that use scrollTo('id')
function scrollTo(id) { scrollToSection(id); }
function setActivePill(id) {
  var pills = qsa('.nav-pill');
  for (var i = 0; i < pills.length; i++) pills[i].classList.remove('active');
  var pill = qs('[data-nav="' + id + '"]');
  if (pill) pill.classList.add('active');
}

// ── Navigation ──
var HUB = window.location.origin;

function goBack() {
  window.location.href = 'index.html';
}

// ── Chips ──
function selectChip(chip) {
  var group = findParent(chip, 'chip-group');
  if (!group) return;
  var chips = group.querySelectorAll('.chip');
  for (var i = 0; i < chips.length; i++) chips[i].classList.remove('selected');
  chip.classList.add('selected');
  if (typeof safeUpdateStatuses === 'function') safeUpdateStatuses();
}
function toggleChip(chip) { chip.classList.toggle('selected'); }
function toggleChipMulti(chip) {
  var g = findParent(chip, 'chip-group');
  if (!g) return;
  var t = chip.textContent.trim();
  var isN = (t === 'Normal' || t === 'Normaux' || t === 'Normales' || t === 'Normale');
  if (isN) {
    var c = g.querySelectorAll('.chip');
    for (var i = 0; i < c.length; i++) c[i].classList.remove('selected');
    chip.classList.add('selected');
  } else {
    var c = g.querySelectorAll('.chip');
    for (var i = 0; i < c.length; i++) {
      var ct = c[i].textContent.trim();
      if (ct === 'Normal' || ct === 'Normaux' || ct === 'Normales' || ct === 'Normale') c[i].classList.remove('selected');
    }
    chip.classList.toggle('selected');
  }
}
function getChips(field) {
  var els = qsa('[data-field="' + field + '"] .chip.selected');
  var arr = [];
  for (var i = 0; i < els.length; i++) arr.push(els[i].textContent.trim());
  return arr;
}
function selectChipByValue(field, value) {
  var chips = qsa('[data-field="' + field + '"] .chip');
  for (var i = 0; i < chips.length; i++) {
    chips[i].classList.remove('selected');
    if (chips[i].textContent.trim() === value) chips[i].classList.add('selected');
  }
}

// ── Yes/No toggles ──
function setYN(btn, val) {
  var row = findParent(btn, 'yn-toggle');
  if (!row) return;
  var btns = row.querySelectorAll('button');
  for (var i = 0; i < btns.length; i++) btns[i].className = '';
  btn.className = val === 'y' ? 'sel-y' : 'sel-n';
}
function collectYNs() {
  var result = {};
  var rows = qsa('.yn-row');
  for (var i = 0; i < rows.length; i++) {
    var toggle = rows[i].querySelector('.yn-toggle');
    if (!toggle) continue;
    var dataId = toggle.getAttribute('data-id');
    if (!dataId) continue;
    var sel = toggle.querySelector('.sel-y,.sel-n');
    if (sel) result[dataId] = sel.classList.contains('sel-y');
    else result[dataId] = null;
  }
  return result;
}

// ── Morpho toggles ──
function setMorpho(id, val, btn) {
  var row = findParent(btn, 'morpho-toggle');
  if (!row) return;
  var btns = row.querySelectorAll('button');
  for (var i = 0; i < btns.length; i++) btns[i].className = '';
  btn.className = val === 'n' ? 'sel-n' : 'sel-a';
  var detail = gid('md_' + id);
  if (detail) detail.classList.toggle('visible', val === 'a');
  if (typeof safeUpdateStatuses === 'function') safeUpdateStatuses();
}

// ── Photos ──
var photos = {};
var currentPhotoSlot = null;

function initPhotoInput() {
  var fileInput = gid('photo-file-input');
  if (!fileInput) return;
  fileInput.addEventListener('change', function(e) {
    var file = e.target.files[0];
    if (!file || !currentPhotoSlot) return;
    var reader = new FileReader();
    reader.onload = function(ev) {
      var slot = currentPhotoSlot;
      var key = slot.getAttribute('data-key');
      var dataUrl = ev.target.result;
      var labelEl = slot.querySelector('.label');
      var label = labelEl ? labelEl.textContent : key;
      photos[key] = { dataUrl: dataUrl, label: label };
      slot.classList.add('has-photo');
      slot.innerHTML = '<img src="' + dataUrl + '"><button class="remove-btn" onclick="event.stopPropagation();removePhoto(\'' + key + '\')">✕</button><div class="overlay-label">' + label + '</div>';
      if (typeof safeUpdateStatuses === 'function') safeUpdateStatuses();
    };
    reader.readAsDataURL(file);
    fileInput.value = '';
  });
}
function capturePhoto(slot) {
  currentPhotoSlot = slot;
  var fileInput = gid('photo-file-input');
  if (fileInput) fileInput.click();
}
function removePhoto(key) {
  delete photos[key];
  var slot = qs('[data-key="' + key + '"]');
  if (!slot) return;
  var label = slot.getAttribute('data-original-label') || key;
  slot.classList.remove('has-photo');
  slot.innerHTML = '<div class="icon">📷</div><div class="label">' + label + '</div>';
  if (typeof safeUpdateStatuses === 'function') safeUpdateStatuses();
}

// ── DS calculation helpers ──
function zs(v, m, sd) {
  if (!isFinite(v) || m == null || sd == null || sd === 0) return null;
  return (v - m) / sd;
}
function dsTag(val, cls) {
  if (val === null) return '';
  var r = Math.round(val * 100) / 100;
  var extra = Math.abs(r) > 2 ? ' alert' : '';
  return '<span class="ds-tag ' + cls + extra + '">' + cls.toUpperCase() + ' ' + r.toFixed(2) + '</span>';
}

// ── Status helpers ──
function setStatus(section, state, text) {
  var badge = gid('ast-' + section);
  if (badge) { badge.className = 'acc-status ' + state; badge.textContent = text; }
  var dot = gid('pdot-' + section);
  if (dot) { dot.className = 'pill-dot' + (state === 'done' ? ' done' : state === 'partial' ? ' partial' : ''); }
}

// ── Settings / Handedness / Theme ──
function loadSettings() {
  try {
    var raw = localStorage.getItem('foetopath_settings');
    if (raw) return JSON.parse(raw);
  } catch(e) {}
  return { gaucher: false, theme: 'sombre' };
}
function saveSettings(s) {
  try { localStorage.setItem('foetopath_settings', JSON.stringify(s)); } catch(e) {}
}
function applySettings() {
  var s = loadSettings();
  // Gaucher
  if (s.gaucher) document.body.classList.add('gaucher');
  else document.body.classList.remove('gaucher');
  // Theme
  document.body.classList.remove('theme-clair', 'theme-malvoyant');
  if (s.theme === 'clair') document.body.classList.add('theme-clair');
  else if (s.theme === 'malvoyant') document.body.classList.add('theme-malvoyant');
}

// ── Collapse buttons + optional extra photos — injected at bottom of each accordion ──
var extraPhotoCounters = {};
function injectCollapseButtons(withExtraPhotos) {
  var sections = qsa('.acc-section');
  for (var i = 0; i < sections.length; i++) {
    var sec = sections[i];
    var inner = sec.querySelector('.acc-body-inner');
    if (!inner) continue;
    if (inner.querySelector('.btn-collapse')) continue;
    var secId = sec.id;

    if (withExtraPhotos) {
      extraPhotoCounters[secId] = 0;

      // Extra photos grid (2 columns like macro_frais)
      var grid = document.createElement('div');
      grid.id = 'extra-photos-' + secId;
      grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px';
      inner.appendChild(grid);

      // Add photo button (same style as macro_frais)
      var addBtn = document.createElement('button');
      addBtn.className = 'btn-add-photo';
      addBtn.textContent = '＋ Photo supplémentaire';
      addBtn.setAttribute('onclick', 'addSectionExtraPhoto("' + secId + '")');
      inner.appendChild(addBtn);
    }

    // Collapse button
    var btn = document.createElement('button');
    btn.className = 'btn-collapse';
    btn.textContent = '▲ Replier';
    btn.setAttribute('onclick', 'collapseSection("' + secId + '")');
    inner.appendChild(btn);
  }
}
function addSectionExtraPhoto(secId) {
  if (!extraPhotoCounters[secId]) extraPhotoCounters[secId] = 0;
  extraPhotoCounters[secId]++;
  var n = extraPhotoCounters[secId];
  var grid = gid('extra-photos-' + secId);
  if (!grid) return;
  var key = 'xp_' + secId + '_' + n;
  var label = 'Suppl. ' + n;
  var slot = document.createElement('div');
  slot.className = 'photo-slot grid-slot';
  slot.setAttribute('data-key', key);
  slot.setAttribute('data-original-label', label);
  slot.setAttribute('onclick', 'capturePhoto(this)');
  slot.innerHTML = '<div class="icon big">📷</div><div class="label big">' + label + '</div>';
  grid.appendChild(slot);
}
function collapseSection(id) {
  var el = gid(id);
  if (el) {
    el.classList.remove('open');
    var hdr = qs('.header');
    var headerH = hdr ? hdr.offsetHeight : 80;
    var y = el.getBoundingClientRect().top + window.pageYOffset - headerH - 8;
    window.scrollTo({ top: y, behavior: 'smooth' });
  }
}
