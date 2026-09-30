/* ═══ FoetoPath — HPO Engine ═══
 * Collecte silencieuse des codes HPO depuis les chips, toggles et textareas.
 * - Chips/toggles : mapping automatique vers HPO via HPO_FORM_MAP
 * - Textareas : autocomplétion dropdown avec termes HPO
 * - collectHPO() : renvoie le JSON des codes HPO par section
 * Requires: hpo_mapping.js (loaded before this file)
 */

// ═══════════════════════════════════════════════════
// 1. FORM → HPO MAPPING (chips & toggles)
// ═══════════════════════════════════════════════════

var HPO_FORM_MAP = {
  chips: {
    // ── Ouverture & Situs ──
    'situs': {
      'Inversus': {code:'HP:0001696', term:'Situs inversus totalis'},
      'Ambiguus': {code:'HP:0042109', term:'Situs ambiguus'}
    },
    'diaphragme': {
      'Hernie G': {code:'HP:0000776', term:'Congenital diaphragmatic hernia'},
      'Hernie D': {code:'HP:0000776', term:'Congenital diaphragmatic hernia'},
      'Hernie bilat.': {code:'HP:0000776', term:'Congenital diaphragmatic hernia'}
    },

    // ── Thymus ──
    'thymus_aspect': {
      'Absent': {code:'HP:0005359', term:'Aplasia of the thymus'},
      'Pétéchies': {code:'HP:0000967', term:'Petechiae'}
    },

    // ── Péricarde ──
    'pericarde': {
      'Épanchement': {code:'HP:0001698', term:'Pericardial effusion'},
      'Hémopéricarde': {code:'HP:0001698', term:'Pericardial effusion'},
      'Pétéchies': {code:'HP:0000967', term:'Petechiae'}
    },

    // ── Gros vaisseaux ──
    'gros_vx': {
      'Transposition': {code:'HP:0001669', term:'Transposition of the great arteries'},
      'Coarctation': {code:'HP:0001680', term:'Coarctation of aorta'}
    },
    'crosse': {
      'Droite': {code:'HP:0012020', term:'Right aortic arch'},
      'Double arc': {code:'HP:0012021', term:'Double aortic arch'}
    },
    'isthme': {
      'Hypoplasique': {code:'HP:0001680', term:'Coarctation of aorta'}
    },

    // ── 4 cavités ──
    'quatre_cav': {
      'Hypoplasie cœur D': {code:'HP:0010954', term:'Hypoplastic right ventricle'},
      'Hypoplasie cœur G': {code:'HP:0004383', term:'Hypoplastic left ventricle'}
    },

    // ── Foramen ovale ──
    'foramen_ovale': {
      'FO restrictif': {code:'HP:0001654', term:'Abnormal heart valve morphology'},
      'FO fermé': {code:'HP:0001631', term:'Atrial septal defect'}
    },

    // ── Sinus coronaire ──
    'sinus_cor': {
      'Dilaté': {code:'HP:0005148', term:'Dilated coronary sinus'}
    },

    // ── Valve pulmonaire ──
    'valve_pulm': {
      'Bicuspide': {code:'HP:0001641', term:'Abnormal pulmonary valve morphology'},
      'Sténosée': {code:'HP:0001642', term:'Pulmonic stenosis'},
      'Atrésie': {code:'HP:0001656', term:'Tricuspid atresia'}
    },

    // ── Septum IV ──
    'septum_iv': {
      'CIV périmemb.': {code:'HP:0011682', term:'Perimembranous ventricular septal defect'},
      'CIV membr.': {code:'HP:0011682', term:'Perimembranous ventricular septal defect'},
      'CIV muscul.': {code:'HP:0011623', term:'Muscular ventricular septal defect'}
    },

    // ── Valve aortique ──
    'valve_aort': {
      'Bicuspide': {code:'HP:0001647', term:'Bicuspid aortic valve'},
      'Sténosée': {code:'HP:0001650', term:'Aortic valve stenosis'}
    },

    // ── Valve tricuspide ──
    'valve_tric': {
      'Ebstein': {code:'HP:0010316', term:'Ebstein anomaly of the tricuspid valve'}
    },

    // ── Valve mitrale ──
    'valve_mitr': {
      'Anormale': {code:'HP:0001633', term:'Abnormal mitral valve morphology'}
    },

    // ── Poumons ──
    'poumons_morpho': {
      'Pétéchies': {code:'HP:0000967', term:'Petechiae'},
      'Anom. lobation': {code:'HP:0002101', term:'Abnormal lung lobation'},
      'Hypoplasie': {code:'HP:0002089', term:'Pulmonary hypoplasia'},
      'CPAM/MAKP': {code:'HP:0006525', term:'Congenital pulmonary airway malformation'},
      'Séquestration': {code:'HP:0004960', term:'Pulmonary sequestration'}
    },

    // ── Foie ──
    'foie_aspect': {
      'Pâle': {code:'HP:0001410', term:'Decreased liver function'},
      'Ictérique': {code:'HP:0000952', term:'Jaundice'},
      'Congestif': {code:'HP:0001399', term:'Hepatic failure'}
    },

    // ── Estomac ──
    'estomac_aspect': {
      'Petit': {code:'HP:0002579', term:'Gastrointestinal atresia'},
      'Distendu': {code:'HP:0100738', term:'Abnormal stomach morphology'},
      'Atrésie': {code:'HP:0002579', term:'Gastrointestinal atresia'}
    },

    // ── Tube digestif ──
    'tube_dig': {
      'Mésentère commun': {code:'HP:0002566', term:'Intestinal malrotation'},
      'Dolicho-côlon': {code:'HP:0100738', term:'Abnormal stomach morphology'},
      'Atrésie': {code:'HP:0001397', term:'Hepatic steatosis'},
      'Apple peel': {code:'HP:0011100', term:'Jejunal atresia'}
    },

    // ── Anus ──
    'anus_int': {
      'Imperforé': {code:'HP:0002023', term:'Anal atresia'}
    },

    // ── Pancréas ──
    'pancreas': {
      'Annulaire': {code:'HP:0001732', term:'Annular pancreas'}
    },

    // ── Rate ──
    'rate': {
      'Rates accessoires': {code:'HP:0001747', term:'Accessory spleen'}
    },

    // ── Surrénales ──
    'surrenales': {
      'En galette': {code:'HP:0000846', term:'Adrenal insufficiency'},
      'Jaunes': {code:'HP:0000846', term:'Adrenal insufficiency'}
    },

    // ── Reins ──
    'reins': {
      'Kystiques': {code:'HP:0000113', term:'Polycystic kidney dysplasia'},
      'Dysplasie multiK': {code:'HP:0000003', term:'Multicystic kidney dysplasia'},
      'Kystes non déf.': {code:'HP:0000107', term:'Renal cyst'},
      'Agénésie': {code:'HP:0000104', term:'Renal agenesis'}
    },

    // ── Voies urinaires ──
    'voies_urin': {
      'Uretères dilatés': {code:'HP:0000073', term:'Ureteral obstruction'},
      'Hydronéphrose': {code:'HP:0000126', term:'Hydronephrosis'},
      'Atrésie': {code:'HP:0000070', term:'Ureteropelvic junction obstruction'}
    },

    // ── Vessie ──
    'vessie_morph': {
      'Mégavessie': {code:'HP:0010475', term:'Megacystis'},
      'Valves urét. post.': {code:'HP:0010957', term:'Congenital posterior urethral valve'}
    },

    // ── Gonades ──
    'gonades_pos': {
      'Inguinales': {code:'HP:0000028', term:'Cryptorchidism'},
      'Abdominales': {code:'HP:0000028', term:'Cryptorchidism'}
    },

    // ── Cerveau ──
    'cerveau_ext': {
      'Hémorragies méningées': {code:'HP:0002138', term:'Subarachnoid hemorrhage'},
      'Lissencéphalie': {code:'HP:0001339', term:'Lissencephaly'},
      'Polymicrogyrie': {code:'HP:0002126', term:'Polymicrogyria'}
    },

    // ── Moelle ──
    'moelle': {
      'Anormale': {code:'HP:0002143', term:'Abnormality of the spinal cord'}
    }
  },

  // ── YN toggles → HPO (valeur y = finding positif) ──
  toggles: {
    'anasarque': {y: {code:'HP:0001789', term:'Hydrops fetalis'}},
    'fistule_abs': {n: {code:'HP:0002575', term:'Tracheoesophageal fistula'}},
    'vcsg': {y: {code:'HP:0005301', term:'Persistent left superior vena cava'}},
    'canal_art': {y: {code:'HP:0001643', term:'Patent ductus arteriosus'}},
    'vb_presente': {n: {code:'HP:0005245', term:'Absent gallbladder'}},
    'meckel': {y: {code:'HP:0002245', term:'Meckel diverticulum'}}
  },

  // ── Textareas : sections HPO à chercher pour l'autocomplete ──
  textareas: {
    'airway_detail': ['Poumons'],
    'ogi_detail': ['Gonades'],
    'tsa_detail': ['Cœur'],
    'og_retours': ['Cœur'],
    'civ_diam': [],
    'mitrale_det': ['Cœur'],
    'estomac_contenu': ['Tube digestif'],
    'tube_dig_detail': ['Tube digestif'],
    'neuro_detail': ['Encéphale', 'Moelle épinière'],
    'commentaire': null,
    'lesion_desc_*': null,
    // macro_frais morpho text inputs
    'mtxt_*': null
  }
};

// ═══════════════════════════════════════════════════
// 2. HPO CODE COLLECTOR (silent)
// ═══════════════════════════════════════════════════

function collectHPO() {
  var result = { findings: [], source: 'pwa_macro', timestamp: new Date().toISOString() };
  var seen = {};

  // 2a. Collect from chips
  var chipMap = HPO_FORM_MAP.chips;
  var fields = Object.keys(chipMap);
  for (var i = 0; i < fields.length; i++) {
    var field = fields[i];
    var selected = getChips(field);
    var fieldMap = chipMap[field];
    for (var j = 0; j < selected.length; j++) {
      var val = selected[j];
      if (fieldMap[val] && !seen[fieldMap[val].code + '_' + field]) {
        result.findings.push({
          code: fieldMap[val].code,
          term: fieldMap[val].term,
          source_field: field,
          source_value: val,
          type: 'chip'
        });
        seen[fieldMap[val].code + '_' + field] = true;
      }
    }
  }

  // 2b. Collect from YN toggles
  var yns = collectYNs();
  var toggleMap = HPO_FORM_MAP.toggles;
  var toggleIds = Object.keys(toggleMap);
  for (var i = 0; i < toggleIds.length; i++) {
    var tid = toggleIds[i];
    if (yns[tid] === undefined || yns[tid] === null) continue;
    var mapping = toggleMap[tid];
    var key = yns[tid] ? 'y' : 'n';
    if (mapping[key]) {
      result.findings.push({
        code: mapping[key].code,
        term: mapping[key].term,
        source_field: tid,
        source_value: key === 'y' ? 'Oui' : 'Non',
        type: 'toggle'
      });
    }
  }

  // 2c. Collect from textareas with HPO-tagged items
  if (typeof _hpoTextareaSelections !== 'undefined') {
    var taIds = Object.keys(_hpoTextareaSelections);
    for (var i = 0; i < taIds.length; i++) {
      var taId = taIds[i];
      var items = _hpoTextareaSelections[taId];
      for (var j = 0; j < items.length; j++) {
        if (!seen[items[j].code + '_' + taId]) {
          result.findings.push({
            code: items[j].code,
            term: items[j].term,
            source_field: taId,
            source_value: items[j].item,
            type: 'textarea_autocomplete'
          });
          seen[items[j].code + '_' + taId] = true;
        }
      }
    }
  }

  return result;
}

// ═══════════════════════════════════════════════════
// 3. TEXTAREA AUTOCOMPLETE ENGINE
// ═══════════════════════════════════════════════════

var _hpoTextareaSelections = {};
var _hpoDropdown = null;
var _hpoActiveTextarea = null;

function initHPOAutocomplete() {
  // Create dropdown element
  _hpoDropdown = document.createElement('div');
  _hpoDropdown.className = 'hpo-dropdown';
  _hpoDropdown.style.display = 'none';
  document.body.appendChild(_hpoDropdown);

  // Attach to all textareas and text inputs with HPO sections
  var taConfig = HPO_FORM_MAP.textareas;
  var ids = Object.keys(taConfig);
  for (var i = 0; i < ids.length; i++) {
    var id = ids[i];
    if (id.indexOf('*') >= 0) continue;
    var el = gid(id);
    if (el) attachHPOAutocomplete(el, taConfig[id]);
  }

  // For wildcard patterns (e.g., lesion_desc_*)
  for (var i = 0; i < ids.length; i++) {
    if (ids[i].indexOf('*') >= 0) {
      var prefix = ids[i].replace('*', '');
      var allInputs = qsa('input[id^="' + prefix + '"], textarea[id^="' + prefix + '"]');
      for (var j = 0; j < allInputs.length; j++) {
        attachHPOAutocomplete(allInputs[j], taConfig[ids[i]]);
      }
    }
  }

  // Close dropdown on click outside
  document.addEventListener('click', function(e) {
    if (_hpoDropdown && !_hpoDropdown.contains(e.target)) {
      _hpoDropdown.style.display = 'none';
    }
  });
}

function attachHPOAutocomplete(el, sections) {
  if (!el) return;
  el.setAttribute('data-hpo-sections', JSON.stringify(sections));
  if (!_hpoTextareaSelections[el.id]) _hpoTextareaSelections[el.id] = [];

  el.addEventListener('input', function(e) {
    handleHPOInput(e.target);
  });
  el.addEventListener('focus', function(e) {
    _hpoActiveTextarea = e.target;
  });
  el.addEventListener('keydown', function(e) {
    if (_hpoDropdown.style.display !== 'none') {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        navigateDropdown(1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        navigateDropdown(-1);
      } else if (e.key === 'Enter') {
        var active = _hpoDropdown.querySelector('.hpo-item.active');
        if (active) { e.preventDefault(); active.click(); }
      } else if (e.key === 'Escape') {
        _hpoDropdown.style.display = 'none';
      }
    }
  });
}

function handleHPOInput(el) {
  var val = el.value || '';
  // Get the last "segment" after comma or semicolon for multi-term input
  var parts = val.split(/[,;]/);
  var lastPart = parts[parts.length - 1].trim();

  if (lastPart.length < 2) {
    _hpoDropdown.style.display = 'none';
    return;
  }

  var sections = null;
  try { sections = JSON.parse(el.getAttribute('data-hpo-sections')); } catch(e) {}

  var matches = searchHPO(lastPart, sections, 8);
  if (matches.length === 0) {
    _hpoDropdown.style.display = 'none';
    return;
  }

  showDropdown(el, matches, lastPart);
}

function searchHPO(query, sections, maxResults) {
  if (typeof HPO_AUTOCOMPLETE === 'undefined') return [];
  var q = query.toLowerCase();
  var results = [];

  for (var i = 0; i < HPO_AUTOCOMPLETE.length; i++) {
    var item = HPO_AUTOCOMPLETE[i];
    // Filter by sections if specified
    if (sections && sections.length > 0) {
      var inSection = false;
      for (var s = 0; s < sections.length; s++) {
        if (item.section === sections[s]) { inSection = true; break; }
      }
      if (!inSection) continue;
    }

    // Search in all search terms
    var found = false;
    for (var j = 0; j < item.search.length; j++) {
      if (item.search[j].indexOf(q) >= 0) { found = true; break; }
    }
    if (found) {
      results.push(item);
      if (results.length >= maxResults) break;
    }
  }
  return results;
}

function showDropdown(el, matches, query) {
  var rect = el.getBoundingClientRect();
  _hpoDropdown.innerHTML = '';
  _hpoDropdown.style.display = 'block';
  _hpoDropdown.style.position = 'fixed';
  _hpoDropdown.style.left = rect.left + 'px';
  _hpoDropdown.style.width = rect.width + 'px';
  _hpoDropdown.style.zIndex = '9999';

  // Position below or above depending on space
  var spaceBelow = window.innerHeight - rect.bottom;
  if (spaceBelow > 200 || spaceBelow > rect.top) {
    _hpoDropdown.style.top = rect.bottom + 2 + 'px';
    _hpoDropdown.style.bottom = 'auto';
    _hpoDropdown.style.maxHeight = Math.min(spaceBelow - 10, 250) + 'px';
  } else {
    _hpoDropdown.style.bottom = (window.innerHeight - rect.top + 2) + 'px';
    _hpoDropdown.style.top = 'auto';
    _hpoDropdown.style.maxHeight = Math.min(rect.top - 10, 250) + 'px';
  }

  for (var i = 0; i < matches.length; i++) {
    var m = matches[i];
    var div = document.createElement('div');
    div.className = 'hpo-item' + (i === 0 ? ' active' : '');
    div.setAttribute('data-idx', i);
    div.setAttribute('data-code', m.hpo_code);
    div.setAttribute('data-term', m.hpo_term);
    div.setAttribute('data-item', m.item);

    var html = '<div class="hpo-item-main">' + highlightMatch(m.item, query) + '</div>';
    html += '<div class="hpo-item-meta">';
    html += '<span class="hpo-code">' + m.hpo_code + '</span>';
    html += '<span class="hpo-section">' + m.section + '</span>';
    html += '</div>';
    if (m.hpo_term) {
      html += '<div class="hpo-item-en">' + m.hpo_term + '</div>';
    }
    div.innerHTML = html;

    div.addEventListener('click', (function(match) {
      return function() { selectHPOItem(match); };
    })(m));

    _hpoDropdown.appendChild(div);
  }
}

function highlightMatch(text, query) {
  var idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return text;
  return text.substring(0, idx) + '<strong>' + text.substring(idx, idx + query.length) + '</strong>' + text.substring(idx + query.length);
}

function selectHPOItem(match) {
  var el = _hpoActiveTextarea;
  if (!el) return;

  var val = el.value || '';
  var parts = val.split(/[,;]/);
  parts[parts.length - 1] = ' ' + match.item;
  el.value = parts.join(',').replace(/^[\s,]+/, '');

  // Track selected HPO items for this textarea
  if (!_hpoTextareaSelections[el.id]) _hpoTextareaSelections[el.id] = [];
  var already = false;
  for (var i = 0; i < _hpoTextareaSelections[el.id].length; i++) {
    if (_hpoTextareaSelections[el.id][i].code === match.hpo_code) { already = true; break; }
  }
  if (!already) {
    _hpoTextareaSelections[el.id].push({
      code: match.hpo_code,
      term: match.hpo_term,
      item: match.item
    });
  }

  _hpoDropdown.style.display = 'none';

  // Show subtle confirmation
  showHPOTag(el, match);

  // Trigger any existing input handlers
  if (typeof el.oninput === 'function') el.oninput();
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

function showHPOTag(el, match) {
  // Show a small transient tag confirming the HPO code was captured
  var tag = document.createElement('div');
  tag.className = 'hpo-confirm-tag';
  tag.textContent = match.hpo_code + ' ✓';
  tag.style.position = 'absolute';
  var rect = el.getBoundingClientRect();
  tag.style.left = (rect.right - 100) + 'px';
  tag.style.top = (rect.top - 20 + window.pageYOffset) + 'px';
  document.body.appendChild(tag);
  setTimeout(function() { if (tag.parentNode) tag.parentNode.removeChild(tag); }, 1500);
}

function navigateDropdown(dir) {
  var items = _hpoDropdown.querySelectorAll('.hpo-item');
  if (items.length === 0) return;
  var activeIdx = -1;
  for (var i = 0; i < items.length; i++) {
    if (items[i].classList.contains('active')) { activeIdx = i; break; }
  }
  if (activeIdx >= 0) items[activeIdx].classList.remove('active');
  var newIdx = activeIdx + dir;
  if (newIdx < 0) newIdx = items.length - 1;
  if (newIdx >= items.length) newIdx = 0;
  items[newIdx].classList.add('active');
  items[newIdx].scrollIntoView({ block: 'nearest' });
}

// ═══════════════════════════════════════════════════
// 4. HPO PERSISTENCE (localStorage backup)
// ═══════════════════════════════════════════════════

function saveHPOToLocalStorage(dossier, module) {
  try {
    var hpo = collectHPO();
    hpo.dossier = dossier;
    hpo.module = module;
    localStorage.setItem('hpo_' + module + '_' + dossier, JSON.stringify(hpo));
  } catch(e) {}
}

function loadHPOFromLocalStorage(dossier, module) {
  try {
    var raw = localStorage.getItem('hpo_' + module + '_' + dossier);
    if (raw) return JSON.parse(raw);
  } catch(e) {}
  return null;
}

// ═══════════════════════════════════════════════════
// 5. CSS INJECTION (dropdown styles)
// ═══════════════════════════════════════════════════

(function injectHPOStyles() {
  var style = document.createElement('style');
  style.textContent = [
    '.hpo-dropdown {',
    '  background: var(--card-bg, #1e1e2e);',
    '  border: 1px solid var(--border, #333);',
    '  border-radius: 10px;',
    '  overflow-y: auto;',
    '  box-shadow: 0 8px 24px rgba(0,0,0,0.4);',
    '  -webkit-overflow-scrolling: touch;',
    '}',
    '.hpo-item {',
    '  padding: 10px 14px;',
    '  cursor: pointer;',
    '  border-bottom: 1px solid var(--border, #2a2a3a);',
    '  transition: background 0.15s;',
    '}',
    '.hpo-item:last-child { border-bottom: none; }',
    '.hpo-item.active, .hpo-item:hover {',
    '  background: var(--accent-bg, #2a2a4a);',
    '}',
    '.hpo-item-main {',
    '  font-size: 0.95rem;',
    '  color: var(--text, #e0e0e0);',
    '  margin-bottom: 2px;',
    '}',
    '.hpo-item-main strong { color: var(--accent, #7c6fff); }',
    '.hpo-item-meta {',
    '  display: flex;',
    '  gap: 8px;',
    '  font-size: 0.75rem;',
    '}',
    '.hpo-code {',
    '  color: var(--accent, #7c6fff);',
    '  font-family: monospace;',
    '  font-weight: 600;',
    '}',
    '.hpo-section {',
    '  color: var(--text-muted, #888);',
    '  font-style: italic;',
    '}',
    '.hpo-item-en {',
    '  font-size: 0.75rem;',
    '  color: var(--text-muted, #888);',
    '  margin-top: 1px;',
    '}',
    '.hpo-confirm-tag {',
    '  position: absolute;',
    '  background: var(--success, #22c55e);',
    '  color: #fff;',
    '  padding: 3px 8px;',
    '  border-radius: 6px;',
    '  font-size: 0.72rem;',
    '  font-weight: 600;',
    '  pointer-events: none;',
    '  animation: hpoTagFade 1.5s ease forwards;',
    '  z-index: 10000;',
    '}',
    '@keyframes hpoTagFade {',
    '  0% { opacity: 1; transform: translateY(0); }',
    '  70% { opacity: 1; transform: translateY(-5px); }',
    '  100% { opacity: 0; transform: translateY(-12px); }',
    '}',
    '',
    '/* Theme clair override */',
    '.theme-clair .hpo-dropdown { background: #fff; border-color: #ddd; box-shadow: 0 8px 24px rgba(0,0,0,0.12); }',
    '.theme-clair .hpo-item { border-bottom-color: #eee; }',
    '.theme-clair .hpo-item.active, .theme-clair .hpo-item:hover { background: #f0f0ff; }',
    '.theme-clair .hpo-item-main { color: #222; }',
    '.theme-clair .hpo-item-main strong { color: #5b4fd6; }',
    '.theme-clair .hpo-code { color: #5b4fd6; }',
    '.theme-clair .hpo-item-en, .theme-clair .hpo-section { color: #999; }'
  ].join('\n');
  document.head.appendChild(style);
})();

// ═══════════════════════════════════════════════════
// 6. INIT (call after DOM ready)
// ═══════════════════════════════════════════════════

function initHPOEngine() {
  if (typeof HPO_AUTOCOMPLETE !== 'undefined') {
    initHPOAutocomplete();
  }
}

// Auto-init when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    setTimeout(initHPOEngine, 100);
  });
} else {
  setTimeout(initHPOEngine, 100);
}
