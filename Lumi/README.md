# Lumi — Viewer WSI + Labellisation FOETO

Viewer de lames microscopiques MRXS avec systeme d'annotation et de labellisation par termes FOETO.

## Fonctionnalites

- **Viewer** : navigation deep-zoom OpenSlide + OpenSeadragon, cache tuiles en memoire, prefetch, thumbnails, labels et macro-images
- **Annotations** : regions geometriques (polygones, cercles, rectangles), mesures calibrees, annotations texte, sauvegarde JSON par lame
- **Labellisation FOETO** : selection organe + statut (normal/patho), diagnostic par termes FOETO (pathologie, retention, maturation), grades, recherche et quick-picks
- **Base de donnees** : lames.db (organ_status, diagnoses, slide_notes, foeto_terms) — termes charges depuis syndromes_foetaux.db
- **Cartographe** : exploration spatiale des lames
- **Rapport** : generation de bilans d'annotation par cas (concat_report)
- **Ingestion** : chaine jour ingest -> sort -> integrity -> blur -> mask (ingest/run_ingest.py)

## Structure

```
app.py                  Serveur Flask principal (viewer + API)
database.py             Gestion lames.db (organ_status, diagnoses, notes)
cartographer.py         Cartographe spatial
concat_report.py        Rapport d'annotations
ingest/                 Chaine jour d'ingestion MRXS (run_ingest.py)
static/viewer.js        Frontend OpenSeadragon + UI labellisation
templates/index.html    Page viewer
```

## Prerequis systeme

```bash
sudo apt install openslide-tools
```

## Lancement

```bash
pip install -r requirements.txt
python app.py --port 5080 --root /chemin/vers/lames
```

L'option `--root` definit le repertoire racine contenant les dossiers de lames MRXS. Sans cette option, le viewer propose un selecteur de dossier au demarrage.
