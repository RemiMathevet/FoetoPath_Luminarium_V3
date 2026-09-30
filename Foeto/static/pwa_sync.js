// Helpers PWA partagés : détection de session expirée + gestion des réponses
// de submit (401/403 → bandeau reconnexion, 409 → conflit anti-clobber).
// Inclus par toutes les PWA (placenta, foetus, divers) pour éviter la
// duplication du même code de gestion dans chaque fichier.

function pwaShowSessionBanner(msg) {
  let b = document.getElementById('pwaSessionBanner');
  if (!b) {
    b = document.createElement('div');
    b.id = 'pwaSessionBanner';
    b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;' +
      'background:#c0392b;color:#fff;padding:10px 14px;text-align:center;' +
      'font-weight:600;box-shadow:0 2px 6px rgba(0,0,0,.3)';
    document.body.appendChild(b);
  }
  b.innerHTML = msg + ' <a href="/auth/login" style="color:#fff;text-decoration:underline">Se reconnecter</a>';
  b.style.display = 'block';
}

function pwaHideSessionBanner() {
  const b = document.getElementById('pwaSessionBanner');
  if (b) b.style.display = 'none';
}

// Ping /auth/api/me : affiche le bandeau si la session hub est déjà morte,
// pour prévenir AVANT que le technicien remplisse tout le formulaire.
async function pwaCheckSession(hub) {
  try {
    const r = await fetch((hub || '') + '/auth/api/me');
    if (r.status === 401 || r.status === 403) {
      pwaShowSessionBanner('Session expirée — vos enregistrements ne seront pas synchronisés.');
      return false;
    }
    pwaHideSessionBanner();
    return true;
  } catch (e) { return true; }  // hors ligne : ne pas bloquer, sync plus tard
}

// Traite une réponse de submit NON-ok. Retourne true si géré (bandeau/toast posé).
async function pwaHandleSubmitError(resp, showToast) {
  if (resp.status === 401 || resp.status === 403) {
    pwaShowSessionBanner('Session expirée — reconnectez-vous. Rien n\'a été synchronisé (données gardées en local).');
    showToast('Session expirée : non synchronisé.', true);
    return true;
  }
  if (resp.status === 409) {
    const err = await resp.json().catch(() => ({}));
    showToast(err.message || 'Refusé : le dossier contient déjà des données plus complètes.', true);
    return true;
  }
  const err = await resp.json().catch(() => ({}));
  showToast('Sync échouée : ' + (err.error || resp.status), true);
  return true;
}
