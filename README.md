# FoetoPath Luminarium V2

Application de foetopathologie numerique pour l'examen post-mortem foetal et placentaire.

## Architecture

```
Foeto/   Hub d'administration        Flask   port 5004
Lumi/    Viewer WSI + labellisation   Flask   port 5080
```

**Foeto** gere les cas (foetus, placenta, pediatrique), les biometries (Guihard-Costa, Maroun, Muller-Brochut), les comptes rendus (Jinja2 + reformulation LLM via Magos), l'authentification (Argon2 + TOTP) et les PWA de saisie terrain.

**Lumi** sert les lames MRXS via OpenSlide + OpenSeadragon avec un systeme de labellisation par termes FOETO (organes, pathologies, retention, maturation), des annotations geometriques (regions, mesures) et un cartographe spatial.

Le hub proxy le viewer via `/viewer/*` et consomme ses donnees (diagnostics, organ_status, annotations) pour la microscopie des CR.

## Prerequis

- Python 3.11+
- OpenSlide (bibliotheque systeme) : `sudo apt install openslide-tools`
- SQLite 3

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r Foeto/requirements.txt -r Lumi/requirements.txt
```

## Lancement

```bash
# Hub
cd Foeto && python app.py --port 5004

# Viewer
cd Lumi && python app.py --port 5080 --root /chemin/vers/lames
```

Au premier lancement, le hub cree les bases SQLite et demande la configuration du compte administrateur.

## Donnees

Les bases SQLite (foetopath.db, placenta.db, lames.db, auth.db) et les dossiers photos/lames sont stockes dans un repertoire configurable (`--data-dir` ou via l'interface Parametres). Aucune donnee patient n'est incluse dans ce depot.

## Licence

Logiciel a usage hospitalier interne. Voir `Foeto/LICENSE.txt`.
