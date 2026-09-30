# FoetoPath Luminarium V2

> Application de foetopathologie numerique : gestion de cas, biometrie,
> comptes rendus, viewer WSI et labellisation microscopique.

## Structure

| Repertoire | Role | Port | Stack |
|---|---|---|---|
| `Foeto/` | Hub admin (cas, CR, biometrie, PWA, auth) | 5004 | Flask, SQLite, Jinja2 |
| `Lumi/` | Viewer WSI + labellisation FOETO | 5080 | Flask, OpenSlide, OpenSeadragon |

## Lancement

```bash
cd Foeto && python app.py --port 5004
cd Lumi && python app.py --port 5080 --root /media/SSDsamsung/slides
```

## Conventions

- Commit messages en francais
- Execution locale uniquement (P620)
- Venv partage : `~/Bureau/venv/`
