/**
 * FoetoPath — Idle Timeout (client-side)
 *
 * Détecte l'inactivité et déconnecte l'utilisateur.
 * Charge la durée depuis /admin/api/settings (clé idle_timeout_min, 1-30, défaut 8).
 * Affiche un warning 60s avant la déconnexion.
 * Reset à chaque interaction (clic, touche, scroll, souris).
 *
 * Usage: <script src="/static/idle-timeout.js"></script>
 */
(function () {
    'use strict';

    var DEFAULT_MINUTES = 8;
    var MIN_MINUTES = 1;
    var MAX_MINUTES = 30;
    var WARN_BEFORE = 60 * 1000;       // warning 60s avant
    var LOGOUT_URL = '/auth/logout';

    var IDLE_LIMIT = DEFAULT_MINUTES * 60 * 1000;
    var timer = null;
    var warnTimer = null;
    var banner = null;
    var countdown = null;
    var countdownInterval = null;
    var started = false;

    function createBanner() {
        if (banner) return;
        banner = document.createElement('div');
        banner.id = 'idleWarningBanner';
        banner.style.cssText = [
            'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:99999',
            'background:#e74c3c', 'color:#fff', 'padding:10px 20px',
            'font-family:sans-serif', 'font-size:14px', 'font-weight:600',
            'text-align:center', 'box-shadow:0 2px 12px rgba(0,0,0,0.3)',
            'display:none', 'transition:transform 0.3s',
            'transform:translateY(-100%)'
        ].join(';');
        banner.innerHTML =
            'Inactivité détectée — déconnexion dans <span id="idleCountdown">60</span>s ' +
            '<button onclick="window._idleReset()" style="' +
            'margin-left:16px;padding:4px 16px;border-radius:4px;border:1px solid #fff;' +
            'background:transparent;color:#fff;cursor:pointer;font-weight:600;font-size:13px' +
            '">Rester connecté</button>';
        document.body.appendChild(banner);
        countdown = document.getElementById('idleCountdown');
    }

    function showWarning() {
        createBanner();
        var warnSecs = Math.min(Math.round(WARN_BEFORE / 1000), Math.round(IDLE_LIMIT / 1000));
        countdown.textContent = warnSecs;
        banner.style.display = 'block';
        banner.offsetHeight; // force reflow
        banner.style.transform = 'translateY(0)';

        countdownInterval = setInterval(function () {
            warnSecs--;
            if (warnSecs <= 0) {
                clearInterval(countdownInterval);
                doLogout();
            } else {
                countdown.textContent = warnSecs;
            }
        }, 1000);
    }

    function hideWarning() {
        if (banner) {
            banner.style.transform = 'translateY(-100%)';
            setTimeout(function () { banner.style.display = 'none'; }, 300);
        }
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    }

    function doLogout() {
        window.location.href = LOGOUT_URL;
    }

    function resetTimers() {
        clearTimeout(warnTimer);
        clearTimeout(timer);
        hideWarning();

        var warnDelay = Math.max(IDLE_LIMIT - WARN_BEFORE, 0);
        warnTimer = setTimeout(showWarning, warnDelay);
        timer = setTimeout(doLogout, IDLE_LIMIT);
    }

    // Expose pour le bouton "Rester connecté"
    window._idleReset = function () {
        resetTimers();
        fetch('/auth/api/me', { method: 'GET', credentials: 'same-origin' }).catch(function () {});
    };

    // Événements d'activité (throttle 2s)
    var events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
    var throttled = false;
    function onActivity() {
        if (!started || throttled) return;
        throttled = true;
        setTimeout(function () { throttled = false; }, 2000);
        resetTimers();
    }
    events.forEach(function (evt) {
        document.addEventListener(evt, onActivity, { passive: true });
    });

    // Charger la config puis démarrer
    fetch('/admin/api/settings', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (s) {
            var mins = parseInt(s.idle_timeout_min, 10);
            if (isNaN(mins)) mins = DEFAULT_MINUTES;
            mins = Math.max(MIN_MINUTES, Math.min(MAX_MINUTES, mins));
            IDLE_LIMIT = mins * 60 * 1000;
        })
        .catch(function () {
            // Défaut 8 min si erreur réseau
        })
        .finally(function () {
            started = true;
            resetTimers();
        });
})();
