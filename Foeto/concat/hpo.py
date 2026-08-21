"""Extraction HPO et mapping pour le pipeline d'export LLM."""

from ._utils import _finding


def _collect_hpo_recursive(obj, source_path: str = "") -> list:
    """
    Parcours récursif R2 : collecte tous les objets ayant une clé "hpo"
    dans l'arbre JSON. Retourne une liste de {code, label, source}.
    """
    results = []
    if isinstance(obj, dict):
        if "hpo" in obj and isinstance(obj["hpo"], str) and obj["hpo"].startswith("HP:"):
            results.append({
                "code": obj["hpo"],
                "label": obj.get("hpo_label", ""),
                "source": source_path,
            })
        for k, v in obj.items():
            child_path = f"{source_path}.{k}" if source_path else k
            results.extend(_collect_hpo_recursive(v, child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_collect_hpo_recursive(item, source_path))
    return results


def _collect_constatations_libres_recursive(obj, source_path: str = "") -> list:
    """
    Parcours récursif : collecte toutes les `constatation` présentes sans code HPO
    associé (ni clé "hpo" HP:..., ni clé "hpo_label" non vide renvoyant à un code).
    Ces constatations viennent typiquement de champs texte libres (ogi_detail,
    commentaires macro, descriptions neuropath, etc.) non reconnus par le
    dictionnaire de fallback. Elles doivent rester visibles pour le LLM passe 1.
    Retourne une liste de {constatation, source}.
    """
    results = []
    if isinstance(obj, dict):
        const = obj.get("constatation")
        has_hpo = (
            isinstance(obj.get("hpo"), str)
            and obj["hpo"].startswith("HP:")
        )
        if isinstance(const, str) and const.strip() and not has_hpo:
            results.append({
                "constatation": const.strip(),
                "source": source_path,
            })
        for k, v in obj.items():
            if k == "constatation":
                continue
            child_path = f"{source_path}.{k}" if source_path else k
            results.extend(_collect_constatations_libres_recursive(v, child_path))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_constatations_libres_recursive(item, source_path))
    return results


def _extract_hpo_findings(module_data: dict) -> list:
    """
    Extrait les findings HPO d'un module PWA.
    Cherche dans : module.hpo.findings[] ET module.hpo_codes[]
    """
    findings = []

    hpo_obj = module_data.get("hpo", {})
    if isinstance(hpo_obj, dict):
        for f in hpo_obj.get("findings", []):
            if isinstance(f, dict) and f.get("code"):
                findings.append({
                    "code": f["code"],
                    "term": f.get("term", ""),
                    "source_field": f.get("source_field", ""),
                    "source_value": f.get("source_value", ""),
                })

    for c in module_data.get("hpo_codes", []):
        if isinstance(c, dict) and c.get("code"):
            findings.append({
                "code": c["code"],
                "term": c.get("term", c.get("term_fr", c.get("hpo_label", ""))),
                "source_field": c.get("source_field", ""),
                "source_value": c.get("source_value", c.get("constatation", "")),
                "source": c.get("source", ""),
            })

    return findings


_HPO_FALLBACK = {
    "ambiguïté génitale": ("HP:0000062", "Ambiguous genitalia"),
    "ambiguité génitale": ("HP:0000062", "Ambiguous genitalia"),
    "ambigus": ("HP:0000062", "Ambiguous genitalia"),
    "cryptorchidie": ("HP:0000028", "Cryptorchidism"),
    "cryptorchidie bilatérale": ("HP:0000028", "Cryptorchidism"),
    "cryptorchidie unilatérale": ("HP:0000028", "Cryptorchidism"),
    "hypospadias": ("HP:0000047", "Hypospadias"),
    "micropénis": ("HP:0000054", "Micropenis"),
    "atrésie laryngée": ("HP:0008668", "Laryngeal atresia"),
    "sténose laryngée": ("HP:0001601", "Laryngeal stenosis"),
    "atrésie trachéale": ("HP:0005607", "Tracheal atresia"),
    "coarctation de l'aorte": ("HP:0001680", "Coarctation of aorta"),
    "isthme aortique hypoplasique": ("HP:0004387", "Hypoplastic aortic arch"),
    "isthme hypoplasique": ("HP:0004387", "Hypoplastic aortic arch"),
    "dilatation ventriculaire": ("HP:0002119", "Ventriculomegaly"),
    "ventriculomégalie": ("HP:0002119", "Ventriculomegaly"),
    "hétérotopie nodulaire": ("HP:0007165", "Periventricular nodular heterotopia"),
    "heterotopie nodulaire": ("HP:0007165", "Periventricular nodular heterotopia"),
    "cardiomégalie": ("HP:0001640", "Cardiomegaly"),
    "dysplasie multikystique": ("HP:0000003", "Multicystic kidney dysplasia"),
    "gros reins bilatéraux": ("HP:0000105", "Enlarged kidney"),
    "gros reins": ("HP:0000105", "Enlarged kidney"),
    "omphalocèle": ("HP:0001539", "Omphalocele"),
    "laparoschisis": ("HP:0001543", "Gastroschisis"),
    "spina bifida": ("HP:0002414", "Spina bifida"),
    "fente labiale": ("HP:0000204", "Cleft upper lip"),
    "fente palatine": ("HP:0000175", "Cleft palate"),
    "micrognathie": ("HP:0000347", "Micrognathia"),
    "rétrognathie": ("HP:0000278", "Retrognathia"),
    "hypertélorisme": ("HP:0000316", "Hypertelorism"),
    "hypotélorisme": ("HP:0000601", "Hypotelorism"),
    "microphtalmie": ("HP:0000568", "Microphthalmia"),
    "anophtalmie": ("HP:0000528", "Anophthalmia"),
    "polydactylie": ("HP:0010442", "Polydactyly"),
    "syndactylie": ("HP:0001159", "Syndactyly"),
    "pied bot": ("HP:0001762", "Talipes equinovarus"),
    "hernie diaphragmatique": ("HP:0000776", "Congenital diaphragmatic hernia"),
    "hydrops": ("HP:0001789", "Hydrops fetalis"),
    "anasarque": ("HP:0001789", "Hydrops fetalis"),
    "situs inversus": ("HP:0001696", "Situs inversus totalis"),
    "dolichocéphalie": ("HP:0000268", "Dolichocephaly"),
    "brachycéphalie": ("HP:0000248", "Brachycephaly"),
    "pterygium colli": ("HP:0000465", "Webbed neck"),
    "anus imperforé": ("HP:0002023", "Anal atresia"),
    "imperforé": ("HP:0002023", "Anal atresia"),
    "artère ombilicale unique": ("HP:0001195", "Single umbilical artery"),
    "artère unique": ("HP:0001195", "Single umbilical artery"),
}


def _lookup_hpo(text: str) -> tuple:
    """Cherche un code HPO pour un texte libre. Retourne (code, label) ou (None, None)."""
    if not text:
        return (None, None)
    key = text.strip().lower()
    if key in _HPO_FALLBACK:
        return _HPO_FALLBACK[key]
    for pattern, (code, label) in _HPO_FALLBACK.items():
        if pattern in key or key in pattern:
            return (code, label)
    return (None, None)


def _parse_comma_list(text: str) -> list:
    """Sépare un texte par virgule en items individuels nettoyés."""
    if not text:
        return []
    items = [s.strip() for s in text.split(",")]
    return [s for s in items if s]


def _items_to_findings(items: list, hpo_findings: list = None) -> list:
    """
    Convertit une liste de textes en findings structurés.
    Cherche le HPO dans les findings PWA d'abord, puis dans le fallback.
    """
    pwa_index = {}
    if hpo_findings:
        for f in hpo_findings:
            sv = (f.get("source_value") or "").strip().lower()
            if sv and f.get("code"):
                pwa_index[sv] = (f["code"], f.get("term", ""))

    results = []
    for item in items:
        key = item.strip().lower()
        if key in pwa_index:
            code, term = pwa_index[key]
            results.append(_finding(item, code, term))
        else:
            code, label = _lookup_hpo(item)
            results.append(_finding(item, code, label))
    return results
