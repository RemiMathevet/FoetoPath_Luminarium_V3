# Foeto — Hub d'administration FoetoPath

Backend Flask + frontend PWA pour la gestion des cas de foetopathologie.

## Fonctionnalites

- **Cas foetus** : saisie (macro frais, autopsie, radio, neuropath, macro fixe), biometries automatiques (z-scores Guihard-Costa / Maroun / Muller-Brochut), codes HPO
- **Cas placenta** : galette (dimensions, completude, z-score masse), cordon, membranes, tranches, lesions focales
- **Cas pediatrique** : biometries Molina 2019
- **Comptes rendus** : templates Jinja2 (SOFFOET, court, neuropath, radio, placenta), templates utilisateur (editeur visuel), reformulation LLM via Magos, historique des documents generes
- **Microscopie** : proxy vers le viewer Lumi, injection des labellisations FOETO dans les CR
- **PWA** : formulaires de saisie terrain (macro frais foetus/placenta, radio, neuropath) synchronises avec le hub
- **Authentification** : Argon2 + TOTP, roles (admin/editor/spectator), audit trail
- **Akinator** : arbre decisionnel interactif pour l'orientation diagnostique (Foekinator)

## Structure

```
app.py                  Point d'entree Flask, blueprints
admin_bp.py             Blueprint admin foetus
placenta_bp.py          Blueprint placenta
cr_shared_bp.py         Blueprint CR partage (foetus + placenta)
biometrics.py           Moteur z-scores (OrganExtractor, DSCalculator)
reference_data.py       Tables de reference biometriques
services/lumi.py        Interface avec le viewer (slides, annotations, CR micro)
services/magos.py       Client LLM Magos
pwa/                    PWA terrain (foet/, placentas/, divers/, neonat/)
templates/cr/           Templates Jinja2 des comptes rendus
static/js/              JS admin (admin_cr.js, admin_render.js, ...)
```

## Lancement

```bash
pip install -r requirements.txt
python app.py --port 5004
```

## Tests

```bash
pytest
```
