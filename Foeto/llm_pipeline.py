#!/usr/bin/env python3
"""
FoetoPath — Pipeline LLM.

Foetus :
  Passe 1 : orientation syndromique (brief seul)
  Passe 2 : generation du compte-rendu (output passe1 + dossier complet)

Placenta :
  CR : reformulation du CR template en prose médicale structurée

Backend : Magos (queue-based LLM broker, port 8200).
"""

import json
import logging
import re
import time
from typing import Optional

from services.magos import run_generation

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "passe1": {
        "model": "Qwen3.6-35B",
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
        },
        "timeout": 180,
        "retry_temperature": 0.1,
    },
    "passe2": {
        "model": "Qwen3.6-35B",
        "options": {
            "temperature": 0.2,
            "top_p": 0.85,
        },
        "timeout": 300,
        "min_words": 500,
    },
}


# ══════════════════════════════════════════════════════════════════════════
# Construction des prompts
# ══════════════════════════════════════════════════════════════════════════

def build_prompt_passe1(brief: dict) -> str:
    """Prompt pour la Passe 1 : orientation syndromique."""
    brief_json = json.dumps(brief, ensure_ascii=False, indent=2)

    return f"""Tu es un fœtopathologiste expert. Voici le brief d'un cas.

{brief_json}

CONSIGNES :
- Analyse les HPO codés **ET** les `constatations_non_codees` (anomalies renseignées en texte libre non mappées à un code HPO) : ces deux sources doivent être traitées au même niveau d'importance. Une constatation non codée n'est PAS une note secondaire — c'est une anomalie clinique réelle qui doit peser autant qu'un HPO dans le raisonnement.
- `antecedents_maternels` contient les FDR maternels structurés (positifs et négatifs) ainsi que gestité, parité, groupe sanguin, ATCD médicaux et traitements. Les FDR positifs orientent le raisonnement (consanguinité → récessif, diabète → macrosomie/cardiopathie, etc.).
- `examens_prenataux` distingue examens normaux et anormaux. Les anomalies échographiques et génétiques prénatales sont des arguments forts pour le raisonnement syndromique.
- `radio_anomalies` liste les anomalies radiologiques (os longs avec z-scores Chitty, discordances staturales, asymétries costales, anomalies vertébrales). Ces données sont complémentaires des HPO et doivent peser dans le diagnostic.
- Analyse aussi les z-scores anormaux, ratios anormaux, sémiologie littéraire et contradictions.
- Propose 3 à 5 hypothèses syndromiques classées par vraisemblance.
- Pour chaque hypothèse :
  - Nom du syndrome (+ OMIM si connu)
  - HPO du cas qui concordent (et cite également les constatations non codées concordantes dans `arguments_pour`)
  - HPO du cas qui ne concordent PAS (et cite les constatations non codées incompatibles dans `arguments_contre`)
  - HPO attendus du syndrome qui MANQUENT dans le cas
  - Niveau de confiance : fort / modéré / faible
- AUCUNE entrée de `constatations_non_codees` ne doit être silencieusement écartée. Si une hypothèse ne peut pas expliquer une constatation non codée, cela doit apparaître explicitement dans `arguments_contre` ou dans `anomalies_orphelines`, et faire baisser la confiance proportionnellement.
- Signale les anomalies isolées (codées ou non) qui ne rentrent dans aucun syndrome.
- Si tu identifies une séquence (ex: CHAOS), distingue-la du syndrome sous-jacent qui l'a causée.
- Pour chaque hypothèse, propose ensuite une **liste concrète d'éléments à rechercher activement** pour confirmer ou infirmer le diagnostic. Ces éléments doivent être ventilés par modalité dans le champ `examens_a_rechercher` :
  - `histologie` : lésions microscopiques spécifiques (ex : « hétérotopies neuronales corticales », « dysplasie tubulaire rénale », « hypoplasie pulmonaire sur coupes de poumon »).
  - `radiologie` : anomalies à chercher sur le babygramme ou l'imagerie (ex : « côtes courtes, métaphyses évasées », « anomalie vertébrale segmentaire »).
  - `examen_complementaire` : examens ciblés à demander (ex : « CGH-array », « séquençage panel ciliopathies », « étude placentaire histologique », « caryotype sur liquide amniotique »).
  - `macroscopie_a_revoir` : points à re-documenter à la macro ou sur photos (ex : « mesurer l'angle interorbitaire », « revoir le palais », « photographier les plis palmaires »).
  Chaque sous-liste doit contenir des items courts, actionnables, pertinents pour DISCRIMINER cette hypothèse des autres — pas une liste générique.

FORMAT DE SORTIE : JSON structuré uniquement.
```json
{{
  "hypotheses": [
    {{
      "rang": 1,
      "syndrome": "...",
      "omim": "...",
      "confiance": "fort | modéré | faible",
      "hpo_concordants": ["HP:...", ...],
      "hpo_discordants": ["HP:...", ...],
      "hpo_manquants": ["HP:...", ...],
      "arguments_pour": "...",
      "arguments_contre": "...",
      "examens_a_rechercher": {{
        "histologie": ["..."],
        "radiologie": ["..."],
        "examen_complementaire": ["..."],
        "macroscopie_a_revoir": ["..."]
      }},
      "commentaire": "..."
    }}
  ],
  "sequences_identifiees": [
    {{
      "sequence": "CHAOS",
      "mecanisme": "...",
      "signes_expliques": ["HP:...", ...]
    }}
  ],
  "anomalies_orphelines": [
    {{
      "signe": "...",
      "commentaire": "..."
    }}
  ]
}}
```
"""


def build_prompt_passe2(output_syndromique: dict, dossier_complet: dict,
                        identite: dict, template_cr: str = None) -> str:
    """Prompt pour la Passe 2 : génération du compte-rendu.

    Si template_cr est fourni, le LLM suit la structure du template rendu.
    Sinon, utilise la structure par défaut.
    """
    synd_json = json.dumps(output_syndromique, ensure_ascii=False, indent=2)
    dossier_json = json.dumps(dossier_complet, ensure_ascii=False, indent=2)
    id_json = json.dumps(identite, ensure_ascii=False, indent=2)

    if template_cr:
        structure_block = f"""- Suis EXACTEMENT la structure du modèle de CR ci-dessous.
- Chaque section du modèle doit être présente dans ton CR, dans le même ordre.
- Enrichis chaque section avec les données du dossier complet et l'orientation syndromique.
- Si le modèle contient des placeholders vides ou "#", remplace-les par les données réelles du dossier.
- Ajoute une conclusion syndromique finale (reprendre l'orientation du confrère, formulée comme « L'ensemble du tableau est évocateur de... »).

MODÈLE DE CR À SUIVRE :
{template_cr}"""
    else:
        structure_block = """- Structure :
  1. En-tête (identité, terme, indication, service demandeur)
  2. Examen externe
  3. Biométries (tableau avec z-scores)
  4. Radiologie
  5. Ouverture des cavités
  6. Examen in situ
  7. Masses d'organes (tableau avec z-scores et ratios)
  8. Neuropathologie
  9. Histologie (si données disponibles : organes examinés, lésions)
  10. Conclusion syndromique (reprendre l'orientation du confrère, formulée comme « L'ensemble du tableau est évocateur de... »)
  11. Examens complémentaires à proposer"""

    return f"""Tu es un fœtopathologiste rédigeant un compte-rendu d'autopsie.

ORIENTATION SYNDROMIQUE (établie par un confrère senior) :
{synd_json}

DOSSIER COMPLET :
{dossier_json}

IDENTITÉ :
{id_json}

CONSIGNES :
- Rédige un compte-rendu d'examen fœtopathologique complet en français.
{structure_block}

- Utilise un ton médical professionnel.
- Les valeurs normales vérifiées doivent apparaître (ex: "Situs solitus. Diaphragme intègre. Pas d'épanchement.").
- Les z-scores significatifs (|z| > 2) sont en gras.
- Les contradictions identifiées doivent être commentées dans le corps du texte, pas ignorées.
- Si des données d'histologie sont présentes dans le dossier, intègre-les dans la section appropriée.
- Ne fabrique AUCUNE donnée absente du JSON.

FORMAT : Texte structuré en markdown, prêt pour conversion en .docx.
"""


# ══════════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════════

def parse_json_response(content: str) -> Optional[dict]:
    """
    Extrait un objet JSON d'une réponse LLM qui peut contenir du markdown
    ou du texte autour du JSON.
    """
    m = re.search(r'```json\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    depth = 0
    start = None
    for i, ch in enumerate(content):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    start = None

    return None


def _call_magos(model: str, prompt: str, options: dict,
                timeout: int = 300) -> dict:
    """
    Appel au broker Magos via services.magos.run_generation.
    Retourne {response, thinking, tokens_in, tokens_out, duration_s}.
    """
    return run_generation(
        prompt=prompt,
        model=model,
        options=options,
        timeout=timeout,
    )


def _strip_think_tags(text: str) -> tuple[str, str]:
    """Extract inline <think> tags if present (fallback for some models)."""
    thinking = ""
    if "<think>" in text:
        m = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
        if m:
            thinking = m.group(1).strip()
            text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
    return text, thinking


# ══════════════════════════════════════════════════════════════════════════
# Pipeline principal
# ══════════════════════════════════════════════════════════════════════════

def _merge_config(user_config: dict = None) -> dict:
    """Fusionne une config partielle avec les valeurs par défaut."""
    if not user_config:
        return DEFAULT_CONFIG
    merged = {}
    for passe in ("passe1", "passe2"):
        base = dict(DEFAULT_CONFIG[passe])
        override = user_config.get(passe, {})
        if isinstance(override, dict):
            # Merge options séparément (dict imbriqué)
            if "options" in override:
                base["options"] = {**base.get("options", {}), **override["options"]}
                override = {k: v for k, v in override.items() if k != "options"}
            base.update(override)
        merged[passe] = base
    return merged


def pipeline_passe1(case_json: dict, config: dict = None) -> dict:
    """
    Passe 1 seule : orientation syndromique.
    Retourne le JSON structuré.
    """
    config = _merge_config(config)
    cfg1 = config["passe1"]

    brief = case_json.get("brief", {})
    prompt = build_prompt_passe1(brief)

    logger.info("Passe 1 — %s — lancement...", cfg1["model"])
    t0 = time.time()

    result = _call_magos(
        model=cfg1["model"],
        prompt=prompt,
        options=cfg1["options"],
        timeout=cfg1["timeout"],
    )

    content = result["response"]
    thinking = result["thinking"]
    content, extra_think = _strip_think_tags(content)
    thinking = thinking or extra_think

    elapsed = time.time() - t0
    logger.info("Passe 1 terminée en %.1fs (%d tok_out)%s",
                elapsed, result.get("tokens_out", 0),
                f" — thinking {len(thinking)} chars" if thinking else "")

    output = parse_json_response(content)

    if output is None:
        logger.warning("Passe 1 : JSON invalide, retry avec temperature %.1f",
                       cfg1["retry_temperature"])
        retry_opts = dict(cfg1["options"])
        retry_opts["temperature"] = cfg1["retry_temperature"]

        result = _call_magos(
            model=cfg1["model"],
            prompt=prompt,
            options=retry_opts,
            timeout=cfg1["timeout"],
        )
        content = result["response"]
        thinking_retry = result["thinking"]
        content, extra = _strip_think_tags(content)
        thinking = thinking or thinking_retry or extra
        output = parse_json_response(content)

    if output is None:
        raise ValueError(
            "Passe 1 : impossible d'extraire un JSON valide de la réponse. "
            f"Réponse brute : {content[:500]}"
        )

    if "hypotheses" not in output:
        logger.warning("Passe 1 : clé 'hypotheses' absente, wrapping")
        output = {"hypotheses": [], "raw_response": content}

    ret = {
        "output_syndromique": output,
        "meta": {
            "model": cfg1["model"],
            "elapsed_s": round(elapsed, 1),
            "eval_count": result.get("tokens_out", 0),
            "prompt_tokens": result.get("tokens_in", 0),
        },
    }
    if thinking:
        ret["thinking"] = thinking
    return ret


def pipeline_passe2(case_json: dict, output_syndromique: dict,
                    config: dict = None, template_cr: str = None) -> dict:
    """
    Passe 2 seule : génération du compte-rendu.
    Si template_cr est fourni, le CR suit la structure du template.
    """
    config = _merge_config(config)
    cfg2 = config["passe2"]

    dossier = case_json.get("dossier_complet", {})
    identite = case_json.get("brief", {}).get("identite", {})

    prompt = build_prompt_passe2(output_syndromique, dossier, identite,
                                 template_cr=template_cr)

    logger.info("Passe 2 — %s — lancement...", cfg2["model"])
    t0 = time.time()

    result = _call_magos(
        model=cfg2["model"],
        prompt=prompt,
        options=cfg2["options"],
        timeout=cfg2["timeout"],
    )

    cr_markdown = result["response"]
    thinking = result["thinking"]
    cr_markdown, extra = _strip_think_tags(cr_markdown)
    thinking = thinking or extra

    elapsed = time.time() - t0
    logger.info("Passe 2 terminée en %.1fs (%d tok_out)%s",
                elapsed, result.get("tokens_out", 0),
                f" — thinking {len(thinking)} chars" if thinking else "")

    word_count = len(cr_markdown.split())
    if word_count < cfg2["min_words"]:
        logger.warning("Passe 2 : CR trop court (%d mots < %d minimum)",
                       word_count, cfg2["min_words"])

    ret = {
        "compte_rendu_markdown": cr_markdown,
        "meta": {
            "model": cfg2["model"],
            "elapsed_s": round(elapsed, 1),
            "eval_count": result.get("tokens_out", 0),
            "word_count": word_count,
            "alerte_court": word_count < cfg2["min_words"],
        },
    }
    if thinking:
        ret["thinking"] = thinking
    return ret


def pipeline_llm(case_json: dict, config: dict = None,
                 template_cr: str = None) -> dict:
    """Pipeline complet deux passes (foetus)."""
    config = _merge_config(config)
    t_total = time.time()

    result_1 = pipeline_passe1(case_json, config)
    output_syndromique = result_1["output_syndromique"]

    result_2 = pipeline_passe2(case_json, output_syndromique, config,
                                template_cr=template_cr)

    total_elapsed = time.time() - t_total

    return {
        "orientation_syndromique": output_syndromique,
        "compte_rendu_markdown": result_2["compte_rendu_markdown"],
        "meta": {
            "passe1_model": result_1["meta"]["model"],
            "passe2_model": result_2["meta"]["model"],
            "passe1_tokens": result_1["meta"]["eval_count"],
            "passe2_tokens": result_2["meta"]["eval_count"],
            "passe1_elapsed_s": result_1["meta"]["elapsed_s"],
            "passe2_elapsed_s": result_2["meta"]["elapsed_s"],
            "total_elapsed_s": round(total_elapsed, 1),
            "cr_word_count": result_2["meta"]["word_count"],
            "cr_alerte_court": result_2["meta"]["alerte_court"],
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# Pipeline placenta — CR
# ══════════════════════════════════════════════════════════════════════════

PROMPT_PLACENTA_SYSTEM = (
    "Tu es un médecin anatomopathologiste spécialisé en pathologie pré- et "
    "périnatale. Tu rédiges depuis 20 ans des comptes rendus de placenta "
    "conformes au consensus d'Amsterdam."
)


def build_prompt_placenta_cr(cr_text: str) -> str:
    """Prompt pour la reformulation du CR placenta template en prose médicale."""
    return f"""Voici un compte-rendu structuré de placenta généré à partir de données brutes.

═══ COMPTE-RENDU SOURCE ═══

{cr_text}

═══ CONSIGNES ═══

Rédige en français un compte-rendu de placenta. Sépare chaque section par une ligne vide.

RENSEIGNEMENTS CLINIQUES

2-3 lignes maximum :
- Terme (SA + jours), indication de l'examen si précisée, sexe et masse du nouveau-né.
- Ne rien inventer si l'indication n'est pas dans le texte source.

DESCRIPTION MACROSCOPIQUE

Une phrase ou un court paragraphe par compartiment anatomique, chacun séparé par un saut de ligne :
- Galette : forme, complétude, dimensions (grand axe × petit axe × épaisseur), masse parée, z-score et trophicité.
- Ratio fœto-placentaire (F/P) avec DS.
- Plaque choriale.
- Cordon ombilical (insertion, longueur, spiralisation, anomalies).
- Membranes (insertion, aspect, anomalies).
- Plaque basale (complétude, aspect).
- Tranches de section : nombre de groupes, lésions focales.
- Photographies.
- Nombre de cassettes si renseigné, 5 par défaut.

DESCRIPTION MICROSCOPIQUE

Un paragraphe par compartiment, chacun séparé par un saut de ligne.
Grille de lecture systématique : cordon → membranes → parenchyme.
Parenchyme divisé en : plaque choriale, villosités, espace intervilleux, plaque basale.
Les phrases descriptives de la section microscopique du texte source proviennent de la base de référence FOETO : REPRENDS-LES telles quelles, sans les reformuler ni changer la terminologie. Tu peux les relier en prose fluide mais sans altérer le fond ni le vocabulaire.
La description microscopique reste PUREMENT MORPHOLOGIQUE : décris les lésions observées (infiltrats, dépôts, remaniements…) sans NOMMER le diagnostic. Ne nomme pas l'entité diagnostique (ex. ne pas écrire « chorioamniotite » ou « déciduite chronique » dans la description) — ces libellés sont réservés à la conclusion.
Pour chaque compartiment examiné normal : conserve la phrase de normalité du texte source.
N'ajoute AUCUNE anomalie qui n'est pas dans le texte source.

CONCLUSION

Format synthétique, un élément diagnostique par ligne, sans mise en gras ni astérisques :
- Ligne 1 : trophicité de la galette (« Galette entière eutrophe/hypotrophe (-X,XX DS) »).
- Lignes suivantes : chaque diagnostic retenu, un par ligne. C'est ICI qu'on NOMME le diagnostic (ce que la description ne fait pas). Les libellés de la conclusion source viennent de la base FOETO ; explicite les abréviations et stades en toutes lettres avec la terminologie Amsterdam (ex. « MIR stade 2 » → « chorioamniotite aiguë maternelle stade 2 » ; « MIR stade 1 » → « chorionite subchoriale aiguë stade 1 »). Un diagnostic par ligne, sans explication physiopathologique.
- Puis deux lignes vides.
- Dernière ligne : « Absence de : » suivie de la liste des pathologies récidivantes traitables non retrouvées (villite, intervillite, déciduite chronique, vasculopathie thrombotique fœtale, artériopathie déciduale…), séparées par des virgules.

═══ RÈGLES ABSOLUES ═══

- NE PAS inventer de chiffres ni de données absentes du texte source.
- Retranscrire EXACTEMENT les valeurs numériques (masses, DS, ratios, dimensions).
- Les descriptions microscopiques du texte source sont la référence FOETO : les reprendre fidèlement, ne pas les reformuler avec d'autres termes ni introduire de terminologie non présente dans la source.
- Prose médicale professionnelle, phrases complètes au présent pour les descriptions macro et micro.
- PAS de listes à puces dans les descriptions — uniquement de la prose en paragraphes.
- La conclusion est la SEULE section en format liste (une ligne par élément).
- PAS d'interprétation étiologique ni de recommandation clinique.

═══ COMPTE-RENDU RÉDIGÉ ═══
"""


def pipeline_placenta_cr(cr_text: str, model: str = None,
                         config: dict = None) -> dict:
    """
    Reformule un CR placenta template en prose médicale via Magos.

    Args:
        cr_text: texte du CR généré par le template Jinja2
        model: modèle LLM (défaut: setting llm_model)
        config: override options (temperature, top_p, ...)

    Returns:
        {generated_text, thinking, model, tokens, elapsed_s}
    """
    import db as _db
    if model is None:
        model = _db.get_setting("llm_model", "Qwen3.6-35B")

    options = {"temperature": 0.2, "top_p": 0.85}
    if config and isinstance(config, dict):
        options.update(config)

    prompt = build_prompt_placenta_cr(cr_text)

    logger.info("Placenta CR — %s — lancement...", model)
    t0 = time.time()

    result = _call_magos(
        model=model,
        prompt=prompt,
        options=options,
        timeout=300,
    )

    generated = result["response"]
    thinking = result["thinking"]
    generated, extra = _strip_think_tags(generated)
    thinking = thinking or extra

    elapsed = time.time() - t0
    logger.info("Placenta CR terminé en %.1fs (%d tok_out)", elapsed, result.get("tokens_out", 0))

    return {
        "generated_text": generated,
        "thinking": thinking,
        "model": model,
        "tokens": result.get("tokens_out", 0),
        "elapsed_s": round(elapsed, 1),
    }


# ══════════════════════════════════════════════════════════════════════════
# Reformulation CR foetus (prose médicale)
# ══════════════════════════════════════════════════════════════════════════

PROMPT_CR_FOETUS_SYSTEM = (
    "Tu es un médecin anatomopathologiste spécialisé en fœtopathologie. "
    "Tu rédiges des comptes-rendus d'examen fœtopathologique depuis 20 ans."
)


def build_prompt_foetus_cr(cr_text: str) -> str:
    """Prompt pour la reformulation du CR foetus template en prose médicale."""
    return f"""Tu dois transformer le compte-rendu structuré ci-dessous en un texte médical professionnel, tel qu'il serait envoyé à l'obstétricien prescripteur.

═══ RÈGLES ABSOLUES ═══

1. VALEURS NUMÉRIQUES : tu RETRANSCRIS EXACTEMENT chaque valeur (masses en grammes, mesures en mm, DS, ratios, LBWR, scores). Aucun arrondi, aucune omission.

2. STYLE DE RÉDACTION :
   - Prose médicale professionnelle, phrases complètes au présent
   - Tournures : « on observe », « l'examen met en évidence », « on note », « il est retrouvé », « il n'est pas mis en évidence »
   - PAS de listes à puces, PAS de tirets — uniquement de la prose en paragraphes
   - Employer le « nous » de modestie quand nécessaire (« nous avons examiné »)

3. STRUCTURE — conserver ces sections dans cet ordre :
   • RÉSUMÉ CLINIQUE : contexte obstétrical, indication, terme
   • ASPECT EXTERNE : REGROUPER tout ce qui est normal en une phrase. Chaque anomalie fait l'objet d'une phrase dédiée.
   • BIOMÉTRIES : les mesures normales sont groupées. Les mesures hors normes sont détaillées individuellement.
   • EXAMEN INTERNE : organe par organe. Organes normaux groupés. Anomalies détaillées avec masse et DS. Mentionner le LBWR.
   • PRÉLÈVEMENTS : liste concise
   • CONCLUSION : synthèse en un paragraphe

4. INTERDICTIONS STRICTES :
   - NE PAS inventer de données absentes du texte source
   - NE PAS ajouter d'interprétation diagnostique ou étiologique
   - NE PAS suggérer d'examens complémentaires
   - NE PAS modifier la conclusion si elle est déjà présente

═══ COMPTE-RENDU SOURCE ═══

{cr_text}

═══ COMPTE-RENDU RÉDIGÉ ═══
"""


def pipeline_foetus_cr(cr_text: str, model: str = None,
                       config: dict = None) -> dict:
    """
    Reformule un CR foetus template en prose médicale via Magos.

    Returns:
        {generated_text, thinking, model, tokens, elapsed_s}
    """
    import db as _db
    if model is None:
        model = _db.get_setting("llm_model", "Qwen3.6-35B")

    options = {"temperature": 0.2, "top_p": 0.85}
    if config and isinstance(config, dict):
        options.update(config)

    prompt = build_prompt_foetus_cr(cr_text)

    logger.info("Foetus CR — %s — lancement...", model)
    t0 = time.time()

    result = _call_magos(
        model=model,
        prompt=prompt,
        options=options,
        timeout=300,
    )

    generated = result["response"]
    thinking = result["thinking"]
    generated, extra = _strip_think_tags(generated)
    thinking = thinking or extra

    elapsed = time.time() - t0
    logger.info("Foetus CR terminé en %.1fs (%d tok_out)", elapsed, result.get("tokens_out", 0))

    return {
        "generated_text": generated,
        "thinking": thinking,
        "model": model,
        "tokens": result.get("tokens_out", 0),
        "elapsed_s": round(elapsed, 1),
    }


# ══════════════════════════════════════════════════════════════════════════
# Reformulation biométries (foetus)
# ══════════════════════════════════════════════════════════════════════════

def pipeline_biometrics(report_text: str, model: str = None) -> dict:
    """
    Reformule un rapport biométrique brut en prose médicale via Magos.

    Returns:
        {generated_text, model, tokens}
    """
    import db as _db
    if model is None:
        model = _db.get_setting("llm_model", "Qwen3.6-35B")

    prompt = f"""Tu es un médecin anatomopathologiste spécialisé en fœtopathologie. Tu dois rédiger un texte médical professionnel à partir des données biométriques brutes ci-dessous.

═══ RÈGLES ═══

1. VALEURS NUMÉRIQUES : retranscrire EXACTEMENT chaque valeur.

2. STYLE : prose médicale, phrases complètes au présent. Pas de listes à puces.

3. REGROUPEMENT : les mesures normales (-2 < DS < +2) sont regroupées en une phrase synthétique. Chaque anomalie (|DS| > 2) fait l'objet d'une phrase dédiée.

4. INTERDICTIONS : ne PAS inventer de données, ne PAS ajouter d'interprétation diagnostique.

═══ DONNÉES ═══

{report_text}

═══ TEXTE RÉDIGÉ ═══
"""

    result = _call_magos(
        model=model,
        prompt=prompt,
        options={"temperature": 0.2},
        timeout=180,
    )

    generated = result["response"]
    generated, _ = _strip_think_tags(generated)

    return {
        "generated_text": generated,
        "model": model,
        "tokens": result.get("tokens_out", 0),
    }
