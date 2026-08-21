"""
Ollama service: LLM integration for text generation and reformulation.
Uses only Python standard library (urllib) — no 'requests' dependency.
"""

import json
import logging
import subprocess as sp
import shutil
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

import db

log = logging.getLogger(__name__)


def _ollama_url() -> str:
    """Get configured Ollama URL, normalized with http:// scheme."""
    url = db.get_setting("ollama_url", "http://localhost:11434").strip()
    if not url:
        return "http://localhost:11434"
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def _is_remote_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host not in ("localhost", "127.0.0.1", "::1", "")


def _http_get(url: str, timeout: int = 5) -> dict:
    """GET request returning parsed JSON."""
    req = Request(url)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, timeout: int = 180) -> dict:
    """POST JSON request returning parsed JSON."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_ollama_status() -> dict:
    """
    Verifie si Ollama tourne, le demarre si besoin, puis liste les modeles.
    Pour les URLs distantes, on ne tente PAS de demarrer Ollama localement.
    """
    url = _ollama_url()
    is_remote = _is_remote_url(url)

    # 1. Check si deja en ligne
    running = False
    try:
        _http_get(f"{url}/api/tags", timeout=5)
        running = True
    except (URLError, OSError):
        log.debug("Ollama non joignable sur %s", url, exc_info=True)

    # 2. Si pas en ligne et URL distante → erreur claire
    started = False
    if not running and is_remote:
        raise RuntimeError(
            f"Ollama non joignable sur {url}. "
            "Verifiez que le serveur distant est en marche et accessible "
            "(pare-feu, port, OLLAMA_HOST=0.0.0.0 sur le serveur)."
        )

    if not running:
        # URL locale : tenter un demarrage automatique
        if not shutil.which("ollama"):
            raise RuntimeError(
                "Ollama n'est pas installe localement. "
                "Installez-le depuis https://ollama.ai ou configurez "
                "une URL distante dans les Settings."
            )

        try:
            sp.Popen(
                ["ollama", "serve"],
                stdout=sp.DEVNULL, stderr=sp.DEVNULL,
                start_new_session=True,
            )
            started = True
        except OSError as e:
            raise RuntimeError(f"Impossible de demarrer Ollama: {e}")

        # Attendre qu'il soit pret (max 10s)
        for _ in range(20):
            time.sleep(0.5)
            try:
                _http_get(f"{url}/api/tags", timeout=2)
                running = True
                break
            except (URLError, OSError):
                continue

        if not running:
            raise RuntimeError(
                "Ollama demarre mais pas encore pret. "
                "Reessayez dans quelques secondes."
            )

    # 3. Lister les modeles
    try:
        data = _http_get(f"{url}/api/tags", timeout=5)
        models = []
        for m in data.get("models", []):
            name = m.get("name", "")
            size_gb = round(m.get("size", 0) / (1024**3), 1)
            family = m.get("details", {}).get("family", "")
            params = m.get("details", {}).get("parameter_size", "")
            models.append({
                "name": name,
                "size_gb": size_gb,
                "family": family,
                "params": params,
            })

        return {
            "running": True,
            "started": started,
            "url": url,
            "models": models,
        }

    except (URLError, OSError) as e:
        raise RuntimeError(f"Erreur listing modeles sur {url}: {e}")


def run_ollama_biometrics(case_id: int, report_text: str, model: str = None) -> dict:
    """
    Envoie le rapport biometrique a Ollama pour reformulation
    en texte medical redige.
    """
    if model is None:
        model = db.get_setting("ollama_model", "mistral")

    url = _ollama_url()

    prompt = f"""Tu es un médecin anatomopathologiste spécialisé en fœtopathologie, rédacteur expérimenté de comptes-rendus médicaux. Tu dois rédiger un texte médical professionnel à partir des données biométriques brutes ci-dessous.

═══ RÈGLES ABSOLUES ═══

1. VALEURS NUMÉRIQUES : tu ne MODIFIES, ARRONDIS ou OMETS aucune valeur numérique. Chaque masse, DS, ratio, mesure est retranscrite EXACTEMENT.

2. STYLE DE RÉDACTION :
   - Utiliser « on observe », « on note », « l'examen met en évidence », « il est retrouvé »
   - Phrases complètes, fluides, au présent de l'indicatif
   - Vocabulaire anatomopathologique standard français
   - Pas de tirets ni de listes à puces — que de la prose

3. REGROUPEMENT DES RÉSULTATS NORMAUX :
   - Les mesures et organes NORMAUX (entre -2 et +2 DS) sont regroupés en une ou deux phrases synthétiques
   - Exemple : « Les biométries corporelles (masse, VT, VC, PC, pied) sont dans les limites de la normale pour le terme de XX SA (réf. Guihard-Costa 2002). »
   - Exemple : « Les masses du thymus, du cœur, du foie, de la rate et des surrénales sont en accord avec le terme. »

4. MISE EN ÉVIDENCE DES ANOMALIES :
   - Chaque anomalie (|DS| > 2) fait l'objet d'une phrase dédiée avec la valeur, la DS, et le qualificatif
   - Exemple : « On note une diminution significative de la masse rénale combinée à 3,44 g (-3,14 DS), en dessous du 5ème percentile. »
   - Les anomalies modérées (1 < |DS| < 2) peuvent être signalées comme « à la limite inférieure/supérieure de la normale »

5. RATIOS :
   - Mentionner le LBWR (rapport poumon/poids corporel) avec sa valeur et son interprétation
   - Les ratios organe/masse ne sont mentionnés que s'ils sont anormaux

6. TU NE RAJOUTES AUCUNE :
   - Interprétation diagnostique ou étiologique
   - Hypothèse non contenue dans les données
   - Recommandation clinique
   - Référence bibliographique non citée dans les données

═══ DONNÉES À RÉDIGER ═══

{report_text}

═══ TEXTE RÉDIGÉ ═══
"""

    try:
        result = _http_post_json(
            f"{url}/api/generate",
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 3000},
            },
            timeout=180,
        )

        generated_text = result.get("response", "")

        # Save to database
        computed = db.get_module_data(case_id, "computed_biometrics") or {}
        computed["ollama_text"] = generated_text
        computed["ollama_model"] = model
        db.save_module_data(case_id, "computed_biometrics", computed)

        return {
            "generated_text": generated_text,
            "model": model,
            "prompt_tokens": result.get("prompt_eval_count", 0),
            "completion_tokens": result.get("eval_count", 0),
        }

    except URLError as e:
        raise RuntimeError(f"Ollama non accessible sur {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Erreur Ollama: {e}")


def run_ollama_cr(case_id: int, cr_text: str, model: str = None) -> dict:
    """
    Envoie un texte CR a Ollama pour redaction en langage naturel medical.
    """
    if model is None:
        model = db.get_setting("ollama_model", "mistral")

    url = _ollama_url()

    prompt = f"""Tu es un médecin anatomopathologiste spécialisé en fœtopathologie. Tu rédiges des comptes-rendus d'examen fœtopathologique depuis 20 ans. Tu dois transformer le compte-rendu structuré ci-dessous en un texte médical professionnel, tel qu'il serait envoyé à l'obstétricien prescripteur.

═══ RÈGLES ABSOLUES — VIOLATION INTERDITE ═══

1. VALEURS NUMÉRIQUES : tu RETRANSCRIS EXACTEMENT chaque valeur (masses en grammes, mesures en mm, DS, ratios, LBWR, scores). Aucun arrondi, aucune omission.

2. STYLE DE RÉDACTION :
   - Prose médicale professionnelle, phrases complètes au présent
   - Tournures : « on observe », « l'examen met en évidence », « on note », « il est retrouvé », « il n'est pas mis en évidence »
   - PAS de listes à puces, PAS de tirets — uniquement de la prose en paragraphes
   - Employer le « nous » de modestie quand nécessaire (« nous avons examiné »)

3. STRUCTURE À RESPECTER — tu conserves ces sections dans cet ordre :
   • RÉSUMÉ CLINIQUE : contexte obstétrical, indication, terme
   • ASPECT EXTERNE : état du fœtus, macération, puis morphologie. REGROUPER tout ce qui est normal en une phrase (« L'examen externe ne révèle pas de particularité morphologique significative au niveau du crâne, de la face, des oreilles, du nez, du cou, du thorax, de l'abdomen, du dos et des membres. »). Chaque anomalie fait l'objet d'une phrase dédiée.
   • BIOMÉTRIES : les mesures normales sont groupées (« Les biométries corporelles sont dans les limites de la normale pour XX SA »). Les mesures hors normes sont détaillées individuellement.
   • EXAMEN INTERNE : organe par organe. Les organes normaux peuvent être groupés. Les anomalies sont décrites en détail avec masse et DS. Mentionner le LBWR. Conclure sur la concordance des pesées avec le terme.
   • PRÉLÈVEMENTS : liste concise
   • CONCLUSION : synthèse en un paragraphe avec sexe, terme estimé, anomalies principales

4. REGROUPEMENT DES NORMAUX :
   - Morphologie externe : une phrase listant tous les items normaux
   - Biométries : une phrase regroupant les mesures concordantes
   - Organes : une phrase pour les organes dont la masse est en accord avec le terme
   - Puis chaque anomalie séparément

5. ANOMALIES :
   - Chaque anomalie morphologique est décrite en une phrase précise
   - Chaque anomalie biométrique mentionne la valeur exacte et la DS
   - Utiliser « significativement diminué » (|DS| > 2), « modérément diminué » (1-2 DS), « à la limite inférieure de la normale »

6. INTERDICTIONS STRICTES :
   - NE PAS inventer de données absentes du texte source
   - NE PAS ajouter d'interprétation diagnostique ou étiologique
   - NE PAS suggérer d'examens complémentaires
   - NE PAS ajouter de références bibliographiques
   - NE PAS modifier la conclusion si elle est déjà présente

═══ COMPTE-RENDU SOURCE ═══

{cr_text}

═══ COMPTE-RENDU RÉDIGÉ ═══
"""

    try:
        result = _http_post_json(
            f"{url}/api/generate",
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": True,
                "options": {"temperature": 0.2, "num_predict": 4000},
            },
            timeout=300,
        )

        generated = result.get("response", "")
        thinking = result.get("thinking", "")

        # Fallback : certaines versions renvoient le thinking inline
        if not thinking and "<think>" in generated:
            import re
            m = re.search(r"<think>(.*?)</think>", generated, re.DOTALL)
            if m:
                thinking = m.group(1).strip()
                generated = re.sub(
                    r"<think>.*?</think>\s*", "", generated, flags=re.DOTALL
                ).strip()

        # Save to database
        db.save_module_data(case_id, "last_cr_ollama", {
            "text": generated,
            "thinking": thinking,
            "model": model,
        })

        return {
            "generated_text": generated,
            "thinking": thinking,
            "model": model,
            "tokens": result.get("eval_count", 0),
        }

    except URLError as e:
        raise RuntimeError(f"Ollama non accessible sur {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Erreur Ollama: {e}")
