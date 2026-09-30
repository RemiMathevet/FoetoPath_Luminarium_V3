(function(){
var PAGE = location.pathname.replace(/\//g,'').replace('.html','') || 'index';
var css = document.createElement('style');
css.textContent = '\
.fb-btn{position:fixed;bottom:20px;right:20px;width:48px;height:48px;border-radius:50%;background:#185FA5;color:#fff;border:none;font-size:20px;cursor:pointer;box-shadow:0 3px 12px rgba(0,0,0,.2);z-index:99999;transition:all .2s;display:flex;align-items:center;justify-content:center;}\
.fb-btn:hover{background:#0f4a85;transform:scale(1.08);}\
.fb-bubbles{position:fixed;bottom:76px;right:20px;z-index:99999;display:none;flex-direction:column;align-items:flex-end;gap:8px;}\
.fb-bubble{display:flex;align-items:center;gap:10px;cursor:pointer;transition:all .15s;}\
.fb-bubble:hover .fb-bubble-label{background:#0f4a85;}\
.fb-bubble-icon{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 8px rgba(0,0,0,.15);}\
.fb-bubble-big .fb-bubble-icon{background:#185FA5;color:#fff;width:42px;height:42px;font-size:17px;}\
.fb-bubble-small .fb-bubble-icon{background:#fff;border:1.5px solid #185FA5;color:#185FA5;width:36px;height:36px;font-size:14px;}\
.fb-bubble-label{background:#185FA5;color:#fff;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:500;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.1);transition:background .15s;}\
.fb-bubble-small .fb-bubble-label{background:#555;font-size:11px;padding:5px 12px;}\
.fb-bubble-small:hover .fb-bubble-label{background:#333;}\
.fb-panel{position:fixed;width:340px;max-height:80vh;background:#fff;border:1px solid #e0e0e0;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.15);z-index:99999;display:none;overflow:hidden;}\
.fb-header{background:#185FA5;color:#fff;padding:10px 14px;font-size:13px;font-weight:500;cursor:move;display:flex;justify-content:space-between;align-items:center;user-select:none;}\
.fb-close{background:none;border:none;color:#fff;font-size:16px;cursor:pointer;opacity:.7;}\
.fb-close:hover{opacity:1;}\
.fb-body{padding:14px;}\
.fb-body label{font-size:11px;font-weight:500;color:#555;display:block;margin-bottom:4px;}\
.fb-body input,.fb-body select,.fb-body textarea{width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:6px;font-size:12px;margin-bottom:10px;font-family:inherit;box-sizing:border-box;}\
.fb-body input:focus,.fb-body select:focus,.fb-body textarea:focus{outline:none;border-color:#185FA5;}\
.fb-body textarea{height:100px;resize:vertical;}\
.fb-submit{width:100%;padding:9px;background:#185FA5;color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;}\
.fb-submit:hover{background:#0f4a85;}\
.fb-submit:disabled{background:#aaa;cursor:default;}\
.fb-ok{text-align:center;padding:20px;font-size:13px;color:#085041;}\
.fb-page{font-size:10px;color:#aaa;margin-bottom:10px;}\
.fb-list{max-height:55vh;overflow-y:auto;}\
.fb-item{border-bottom:1px solid #f0f0f0;padding:12px 0;}\
.fb-item:last-child{border-bottom:none;}\
.fb-item-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}\
.fb-item-author{font-size:12px;font-weight:500;color:#111;}\
.fb-item-meta{font-size:10px;color:#aaa;}\
.fb-item-page{font-size:10px;color:#185FA5;background:#E6F1FB;padding:2px 7px;border-radius:99px;display:inline-block;margin-bottom:4px;}\
.fb-item-text{font-size:12px;color:#333;line-height:1.5;}\
.fb-tag{font-size:9px;padding:2px 6px;border-radius:99px;font-weight:500;display:inline-block;}\
.fb-tag-idee{background:#E6F1FB;color:#185FA5;}\
.fb-tag-bug{background:#FCEBEB;color:#A32D2D;}\
.fb-tag-ux{background:#E3F8EE;color:#085041;}\
.fb-tag-autre{background:#f0f0f0;color:#666;}\
.fb-empty{text-align:center;padding:30px 14px;color:#aaa;font-size:12px;}\
';
document.head.appendChild(css);

var btn = document.createElement('button');
btn.className = 'fb-btn';
btn.innerHTML = '💡';
btn.title = 'Suggestions';
btn.style.position = 'fixed';
document.body.appendChild(btn);

var bubbles = document.createElement('div');
bubbles.className = 'fb-bubbles';
bubbles.innerHTML = '\
<div class="fb-bubble fb-bubble-big" data-action="add">\
<span class="fb-bubble-label">Proposer une amélioration</span>\
<span class="fb-bubble-icon">✏️</span>\
</div>\
<div class="fb-bubble fb-bubble-small" data-action="list">\
<span class="fb-bubble-label">Consulter les propositions</span>\
<span class="fb-bubble-icon">📋</span>\
</div>';
document.body.appendChild(bubbles);

var addPanel = document.createElement('div');
addPanel.className = 'fb-panel';
addPanel.style.bottom = '80px';
addPanel.style.right = '20px';
document.body.appendChild(addPanel);

var listPanel = document.createElement('div');
listPanel.className = 'fb-panel';
listPanel.style.bottom = '80px';
listPanel.style.right = '20px';
document.body.appendChild(listPanel);

var bubblesOpen = false;

function closeAll() {
  bubbles.style.display = 'none';
  addPanel.style.display = 'none';
  listPanel.style.display = 'none';
  bubblesOpen = false;
}

// Anchor the bubbles to the button's current position (button is draggable)
function positionBubbles() {
  var r = btn.getBoundingClientRect();
  bubbles.style.left = 'auto';
  bubbles.style.top = 'auto';
  bubbles.style.right = (window.innerWidth - r.right) + 'px';
  bubbles.style.bottom = (window.innerHeight - r.top + 8) + 'px';
}

// Draggable button, persisted across pages
(function(){
  try {
    var p = JSON.parse(localStorage.getItem('fbBtnPos') || 'null');
    if (p) {
      // clamp into viewport so a stale off-screen drag can't hide the button
      var L = Math.min(Math.max(parseInt(p.left, 10) || 0, 0), window.innerWidth - 48);
      var T = Math.min(Math.max(parseInt(p.top, 10) || 0, 0), window.innerHeight - 48);
      btn.style.left = L + 'px'; btn.style.top = T + 'px'; btn.style.right = 'auto'; btn.style.bottom = 'auto';
    }
  } catch(e){}
  var dragging = false, moved = false, sx, sy, ox, oy;
  btn.addEventListener('pointerdown', function(e){
    dragging = true; moved = false; sx = e.clientX; sy = e.clientY;
    var r = btn.getBoundingClientRect(); ox = r.left; oy = r.top;
    btn.setPointerCapture(e.pointerId);
  });
  btn.addEventListener('pointermove', function(e){
    if (!dragging) return;
    var dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) moved = true;
    if (moved) {
      btn.style.left = (ox + dx) + 'px'; btn.style.top = (oy + dy) + 'px';
      btn.style.right = 'auto'; btn.style.bottom = 'auto';
      if (bubblesOpen) positionBubbles();
    }
  });
  btn.addEventListener('pointerup', function(){
    dragging = false;
    if (moved) { btn._fbDragged = true; localStorage.setItem('fbBtnPos', JSON.stringify({ left: btn.style.left, top: btn.style.top })); }
  });
})();

btn.addEventListener('click', function(){
  if (btn._fbDragged) { btn._fbDragged = false; return; }  // ignore click that ended a drag
  if (addPanel.style.display === 'block' || listPanel.style.display === 'block') {
    closeAll();
    return;
  }
  bubblesOpen = !bubblesOpen;
  if (bubblesOpen) positionBubbles();
  bubbles.style.display = bubblesOpen ? 'flex' : 'none';
});

function formHTML() {
  return '<div class="fb-header"><span>Proposer une amélioration</span><button class="fb-close">&times;</button></div>\
<div class="fb-body">\
<div class="fb-page">Page : ' + PAGE + '</div>\
<label>Votre nom</label>\
<input id="fb-name" placeholder="Prénom ou initiales">\
<label>Type</label>\
<select id="fb-type"><option value="idee">Idée / fonctionnalité</option><option value="bug">Bug / problème</option><option value="ux">Ergonomie / UX</option><option value="autre">Autre</option></select>\
<label>Description</label>\
<textarea id="fb-text" placeholder="Décrivez votre suggestion..."></textarea>\
<button class="fb-submit" id="fb-send">Envoyer</button>\
</div>';
}

bubbles.querySelector('[data-action="add"]').addEventListener('click', function(){
  bubbles.style.display = 'none';
  bubblesOpen = false;
  listPanel.style.display = 'none';
  addPanel.innerHTML = formHTML();
  addPanel.style.display = 'block';
  resetDrag(addPanel);
  bindClose(addPanel);
  bindSubmit();
});

bubbles.querySelector('[data-action="list"]').addEventListener('click', function(){
  bubbles.style.display = 'none';
  bubblesOpen = false;
  addPanel.style.display = 'none';
  listPanel.innerHTML = '<div class="fb-header"><span>Propositions</span><button class="fb-close">&times;</button></div><div class="fb-body"><div style="text-align:center;color:#aaa;font-size:12px;">Chargement...</div></div>';
  listPanel.style.display = 'block';
  resetDrag(listPanel);
  bindClose(listPanel);
  loadFeedback();
});

function bindClose(panel) {
  panel.querySelector('.fb-close').addEventListener('click', function(){ panel.style.display = 'none'; });
}

function resetDrag(panel) {
  panel.style.bottom = '80px';
  panel.style.right = '20px';
  panel.style.left = '';
  panel.style.top = '';
  var header = panel.querySelector('.fb-header');
  var dragging = false, ddx = 0, ddy = 0;
  header.onmousedown = function(e){
    dragging = true;
    var r = panel.getBoundingClientRect();
    ddx = e.clientX - r.left;
    ddy = e.clientY - r.top;
    panel.style.bottom = 'auto';
    panel.style.right = 'auto';
    e.preventDefault();
  };
  document.addEventListener('mousemove', function(e){
    if (!dragging) return;
    panel.style.left = (e.clientX - ddx) + 'px';
    panel.style.top = (e.clientY - ddy) + 'px';
  });
  document.addEventListener('mouseup', function(){ dragging = false; });
}

var tagLabels = {idee:'Idée',bug:'Bug',ux:'UX',autre:'Autre'};

function loadFeedback() {
  fetch('/api/feedback').then(function(r){ return r.json(); }).then(function(data){
    var body = listPanel.querySelector('.fb-body');
    if (!data.items || data.items.length === 0) {
      body.innerHTML = '<div class="fb-empty">Aucune proposition pour le moment</div>';
      return;
    }
    var html = '<div class="fb-list">';
    data.items.forEach(function(item){
      var tagClass = 'fb-tag-' + (item.type || 'autre');
      html += '<div class="fb-item">\
<div class="fb-item-head"><span class="fb-item-author">' + esc(item.author) + '</span><span class="fb-item-meta">' + esc(item.date) + '</span></div>\
<span class="fb-item-page">' + esc(item.page) + '</span> <span class="fb-tag ' + tagClass + '">' + esc(tagLabels[item.type] || item.type) + '</span>\
<div class="fb-item-text">' + esc(item.text) + '</div>\
</div>';
    });
    html += '</div>';
    body.innerHTML = html;
  }).catch(function(){
    listPanel.querySelector('.fb-body').innerHTML = '<div class="fb-empty">Erreur de chargement</div>';
  });
}

function esc(s) {
  if (!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function bindSubmit() {
  document.getElementById('fb-send').addEventListener('click', function(){
    var name = document.getElementById('fb-name').value.trim();
    var type = document.getElementById('fb-type').value;
    var text = document.getElementById('fb-text').value.trim();
    if (!text) { document.getElementById('fb-text').style.borderColor = '#A32D2D'; return; }
    var sendBtn = this;
    sendBtn.disabled = true;
    sendBtn.textContent = 'Envoi...';
    fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name: name || 'Anonyme', type: type, text: text, page: location.pathname })
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.ok) {
        addPanel.querySelector('.fb-body').innerHTML = '<div class="fb-ok">Merci pour votre retour !</div>';
        setTimeout(function(){ addPanel.style.display = 'none'; }, 1500);
      }
    }).catch(function(){
      sendBtn.disabled = false;
      sendBtn.textContent = 'Erreur — Réessayer';
    });
  });
}
})();
