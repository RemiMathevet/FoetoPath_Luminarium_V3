/* ═══════════════════════════════════════════════════════════════════════════
   FoetoPath — Client-side i18n helper
   ═══════════════════════════════════════════════════════════════════════════
   Usage:
     await i18nInit();          // Charge les traductions (appeler une fois)
     t('nav.home')              // → "Hub" ou "Hub" selon la langue
     t('auth.rate_limited', {seconds: 30})  // → substitution de variables
   ═══════════════════════════════════════════════════════════════════════════ */

var _i18n = {};
var _i18nLang = 'fr';
var _i18nReady = false;

/**
 * Charge les traductions depuis le serveur.
 * Appeler une fois au chargement de la page.
 */
function i18nInit(hubUrl) {
  var base = hubUrl || window.location.origin;
  return fetch(base + '/api/i18n/current.json')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _i18n = data;
      _i18nLang = (data.meta && data.meta.code) || 'fr';
      _i18nReady = true;
      // Mettre à jour le <html lang="...">
      if (document.documentElement) {
        document.documentElement.lang = _i18nLang;
      }
      return data;
    })
    .catch(function(e) {
      console.warn('[i18n] Failed to load translations, using keys as fallback:', e);
      _i18nReady = false;
    });
}

/**
 * Traduit une clé pointée. Ex: t('nav.home') → "Hub"
 * @param {string} key - Clé pointée (ex: 'pwa.foet.macro_frais')
 * @param {Object} [vars] - Variables de substitution (ex: {seconds: 30})
 * @returns {string} Traduction ou clé elle-même si non trouvée
 */
function t(key, vars) {
  var parts = key.split('.');
  var current = _i18n;
  for (var i = 0; i < parts.length; i++) {
    if (current && typeof current === 'object') {
      current = current[parts[i]];
    } else {
      return key;
    }
  }
  if (typeof current !== 'string') return key;

  // Substitution de {var}
  if (vars) {
    Object.keys(vars).forEach(function(k) {
      current = current.replace(new RegExp('\\{' + k + '\\}', 'g'), vars[k]);
    });
  }
  return current;
}

/**
 * Applique les traductions à tous les éléments avec data-i18n.
 * Ex: <span data-i18n="nav.home">Hub</span>
 * Supporte aussi data-i18n-placeholder, data-i18n-title.
 */
function i18nApply() {
  if (!_i18nReady) return;

  // Texte contenu
  var els = document.querySelectorAll('[data-i18n]');
  for (var i = 0; i < els.length; i++) {
    var key = els[i].getAttribute('data-i18n');
    var val = t(key);
    if (val !== key) els[i].textContent = val;
  }

  // Placeholder
  els = document.querySelectorAll('[data-i18n-placeholder]');
  for (var i = 0; i < els.length; i++) {
    var key = els[i].getAttribute('data-i18n-placeholder');
    var val = t(key);
    if (val !== key) els[i].placeholder = val;
  }

  // Title/tooltip
  els = document.querySelectorAll('[data-i18n-title]');
  for (var i = 0; i < els.length; i++) {
    var key = els[i].getAttribute('data-i18n-title');
    var val = t(key);
    if (val !== key) els[i].title = val;
  }
}
