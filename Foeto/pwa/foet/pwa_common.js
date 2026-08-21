/* ═══════════════════════════════════════════════════════════════════════════
   FoetoPath PWA — Common Functions
   ═══════════════════════════════════════════════════════════════════════════ */

// ── FORMAT DOSSIER (aaPnnnn) ──
/** Normalise un numéro de dossier : force le P majuscule (ex: 25p1234 → 25P1234) */
function normalizeDossier(val) {
  return val.replace(/^(\d{2})p/i, '$1P');
}
/** Vérifie le format aaPnnnn (2 chiffres + P majuscule + chiffres) */
function isValidDossierFormat(val) {
  return /^\d{2}P\d+$/.test(val);
}

// ── DOSSIER INITIALIZATION ──
function initDossierField() {
  var params = new URLSearchParams(window.location.search);
  var dossier = normalizeDossier(params.get('dossier') || '—');
  var bEl = gid('badge-dossier');
  if (bEl) bEl.textContent = dossier;
  return dossier;
}

// ── LOCALSTORAGE HELPERS ──
function pwaSave(module, dossier, data) {
  try {
    localStorage.setItem('foet_' + module + '_' + dossier, JSON.stringify(data));
  } catch(e) {}
}

function pwaLoad(module, dossier) {
  try {
    var raw = localStorage.getItem('foet_' + module + '_' + dossier);
    if (raw) return JSON.parse(raw);
  } catch(e) {}
  return null;
}

function pwaLoadFromHub(dossier, module) {
  var url = HUB + '/admin/api/pwa/load?dossier=' + encodeURIComponent(dossier);
  if (module) url += '&module=' + encodeURIComponent(module);
  return fetch(url)
    .then(function(r) { return r.json(); })
    .catch(function() { return { found: false }; });
}

// ── PHOTO HANDLING ──
var photos = {};
var currentPhotoSlot = null;

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

function compressImage(dataUrl, maxWidth, quality) {
  return new Promise(function(resolve) {
    var img = new Image();
    img.onload = function() {
      var canvas = document.createElement('canvas');
      var ratio = maxWidth / img.width;
      canvas.width = maxWidth;
      canvas.height = Math.round(img.height * ratio);
      var ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      var compressed = canvas.toDataURL('image/jpeg', quality || 0.8);
      resolve(compressed);
    };
    img.src = dataUrl;
  });
}

// ── SERVER SUBMISSION ──
function _dataUrlToBlob(dataUrl) {
  var parts = dataUrl.split(',');
  var mime = parts[0].match(/:(.*?);/)[1];
  var b = atob(parts[1]);
  var arr = new Uint8Array(b.length);
  for (var j = 0; j < b.length; j++) arr[j] = b.charCodeAt(j);
  return new Blob([arr], {type: mime});
}

function _fetchAsBlob(url) {
  return fetch(url).then(function(r) {
    if (!r.ok) throw new Error('fetch failed');
    return r.blob();
  });
}

function _getCookie(name) {
  var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : '';
}

function _syncPwaUserFromCookie() {
  // Si le cookie pwa_username est posé par le serveur, le persister en localStorage
  var cookieUser = _getCookie('pwa_username');
  if (cookieUser) {
    try {
      var s = JSON.parse(localStorage.getItem('foetopath_settings') || '{}');
      if (s.pwa_user !== cookieUser) {
        s.pwa_user = cookieUser;
        localStorage.setItem('foetopath_settings', JSON.stringify(s));
      }
    } catch(e) {}
  }
}

function _getPwaUser() {
  _syncPwaUserFromCookie();
  try {
    var s = JSON.parse(localStorage.getItem('foetopath_settings') || '{}');
    return s.pwa_user || '';
  } catch(e) { return ''; }
}

// Sync au chargement de chaque page
_syncPwaUserFromCookie();

function pwaSubmit(dossier, module, data, photosObj) {
  photosObj = photosObj || photos;
  // ponytail: collectData() capture une var globale qui peut être stale → on force
  data.dossier = dossier;
  var fd = new FormData();
  fd.append('json_data', JSON.stringify(data));
  fd.append('dossier', dossier);
  fd.append('module', module);
  var pwaUser = _getPwaUser();
  if (pwaUser) fd.append('user', pwaUser);

  var btn = qs('.btn-primary');
  if (btn) { btn.textContent = 'Envoi…'; btn.disabled = true; }

  // N'envoyer que les NOUVELLES photos (locales). Les photos déjà sur le
  // serveur y restent — inutile de les re-télécharger et re-uploader.
  var pk = Object.keys(photosObj);
  for (var i = 0; i < pk.length; i++) {
    (function(key) {
      var photo = photosObj[key];
      if (photo.dataUrl) {
        try {
          var blob = _dataUrlToBlob(photo.dataUrl);
          var ext = blob.type.indexOf('png') >= 0 ? '.png' : '.jpg';
          fd.append('photo_' + key, blob, key + ext);
        } catch(e) {
          fd.append('b64_' + key, photo.dataUrl);
        }
      }
      // photo.serverUrl → déjà sur le serveur, on ne re-upload pas
    })(pk[i]);
  }

  return fetch(HUB + '/admin/api/pwa/submit', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(res) {
      if (btn) { btn.textContent = 'Enregistrer ✓'; btn.disabled = false; }
      if (res.status === 'ok') {
        showToast('✓ Données enregistrées\nDossier : ' + dossier + '\nPhotos : ' + (res.photos_saved || 0));
      } else {
        showToast('Erreur serveur : ' + (res.error || 'inconnue'), true);
      }
      return res;
    })
    .catch(function(err) {
      if (btn) { btn.textContent = 'Enregistrer ✓'; btn.disabled = false; }
      showToast('✓ Sauvegardées localement (hors-ligne)', true);
      return { status: 'offline' };
    });
}

// ── TOAST NOTIFICATIONS ──
function showToast(msg, isError) {
  var t = gid('toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  if (isError) t.classList.add('error');
  else t.classList.remove('error');
  t.classList.add('show');
  setTimeout(function() { t.classList.remove('show'); }, 2500);
}

// ── i18n: CHARGE LES TRADUCTIONS DEPUIS LE HUB ──
function pwaI18nInit() {
  if (typeof i18nInit === 'function') {
    return i18nInit(window.location.origin).then(function() {
      i18nApply();
    }).catch(function() {});
  }
  return Promise.resolve();
}
