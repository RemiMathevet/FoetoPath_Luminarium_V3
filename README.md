# FoetoPath Luminarium V2

Application de fœtopathologie numérique pour l'examen post-mortem fœtal et
placentaire : gestion des dossiers, biométrie, comptes rendus, lecture de lames
virtuelles et labellisation microscopique.

**Ce logiciel n'est pas un dispositif médical.** Voir [`LICENSE`](LICENSE), § 7.

## Architecture

```
Foeto/   Hub d'administration          Flask   port 5004
Lumi/    Viewer WSI + labellisation    Flask   port 5080  (127.0.0.1)
```

**Foeto** gère les cas (fœtus, placenta, pédiatrique), les biométries
(Guihard-Costa, Maroun, Muller-Brochut), les comptes rendus (Jinja2 puis
reformulation LLM via Magos), l'authentification (Argon2id + TOTP), l'audit et
les PWA de saisie terrain.

**Lumi** sert les lames MRXS/NDPI via OpenSlide et OpenSeadragon, avec
labellisation par termes FOETO, annotations géométriques et cartographe spatial.

### Le viewer n'est pas exposé

Lumi écoute sur `127.0.0.1` et n'a pas d'authentification native. Tout accès
externe passe par le hub, qui le proxifie sous `/viewer/*`
(`Foeto/viewer_proxy_bp.py`) derrière `@login_required`. C'est un choix
délibéré : l'auth vit en un seul endroit. Exposer Lumi directement (tunnel
dédié, conteneur, bind `0.0.0.0`) casse ce modèle et impose d'ajouter une auth
au viewer d'abord.

Le hub consomme en retour les données du viewer (diagnostics, `organ_status`,
annotations) pour rédiger la microscopie des comptes rendus.

## Prérequis

- Python 3.11+
- OpenSlide : `sudo apt install openslide-tools`
- SQLite 3

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r Foeto/requirements.txt -r Lumi/requirements.txt
```

## Lancement

```bash
cd Foeto && python app.py --port 5004 --data-dir /chemin/vers/data
cd Lumi  && python app.py --port 5080 --root /chemin/vers/lames
```

Au premier lancement, le hub crée les bases et demande la configuration du
compte administrateur.

## Politique de données

### Rien de nominatif dans ce dépôt

Aucune donnée patient, aucun numéro d'examen réel, aucune photo ne sont versionnés.
Le code et les données vivent dans des arborescences séparées : les bases et les
dossiers de cas sont sous `--data-dir` (ou le paramètre `db_directory`, réglable
dans l'interface), jamais sous le dépôt.

### Bases par domaine

Chaque domaine a sa base SQLite, sans jointure inter-base ; les liens se font en
Python.

| Base | Contenu |
|---|---|
| `foetopath.db` | dossiers fœtus, biométrie, CR |
| `placenta.db` | dossiers placenta, modules, photos |
| `pediatrique.db` | dossiers pédiatriques |
| `lames.db` | lames, labellisation, annotations |
| `auth.db` | comptes, rôles, secrets TOTP |
| `audit.db` | journal d'accès et de modification |
| `syndromes_foetaux.db` | terminologie FOETO/HPO (référence, non nominative) |

Périmètre de chiffrement : les six premières, qui portent des identifiants
(`cases.numero_dossier`, `nom_mere`, `prenom_foetus`, `bam_identity.ipp`,
`lames.nom_lame`) ou des secrets d'authentification. `syndromes_foetaux.db` n'a
aucune colonne identifiante et reste **en clair** : c'est de la terminologie
publique, et c'est la seule base que le viewer ouvre.

Les connexions passent par un gestionnaire commun (`Foeto/db_core.py`,
`Lumi/database.py`) : WAL activé, `foreign_keys=ON`. Les contraintes
référentielles sont déclarées en forme colonne (`REFERENCES … ON DELETE
CASCADE`). Seule la migration legacy (`Foeto/db.py:_migrate_legacy_safe`) coupe
les FK, sur une connexion dédiée.

### Chiffrement au repos — pas encore en place

Les bases ne sont **pas chiffrées**. La confidentialité repose aujourd'hui sur
le chiffrement du disque et les droits du système de fichiers. Le passage à
SQLCipher est prévu avant toute diffusion hors du poste d'origine ; il est
préparé mais pas activé (voir « Chantiers » plus bas).

Le jour du chiffrement, les **copies de sauvegarde** du répertoire de données
(`*.backup_*.db`) devront être traitées avec les bases vives : elles contiennent
les mêmes identifiants, et chiffrer l'originale en laissant ses copies en clair
à côté n'apporte rien.

### Sauvegarde

Les bases et les dossiers de cas sont répliqués par copie de fichiers vers un
volume de sauvegarde. La copie à chaud d'une base SQLite doit se faire par
`VACUUM INTO` ou `sqlite3 .backup`, pas par `cp` sur une base en écriture.

### Miroir public

Ce dépôt est **privé** et fait référence. Le miroir public est produit par
`./publish_public.sh`, qui n'exporte que le hub et le viewer, exclut les scripts
de recherche et `Foeto/feedback`, et **refuse de publier** si un numéro d'examen
réel apparaît dans le périmètre. Ne jamais éditer le dépôt public à la main : il
est écrasé à chaque publication.

## Tests

```bash
python -m pytest Foeto/tests -q
```

Couverts : schéma et migrations, auth et TOTP, permissions, rate limiter, audit,
dossiers placenta, templates de CR.

## Chantiers en cours

- **SQLCipher** — regrouper les ouvertures de base derrière un point d'entrée
  unique, condition pour n'ajouter la clé qu'à un seul endroit le jour du
  chiffrement.
- **Tests d'intégration** — liaison dossier ↔ placenta ↔ lame, génération de CR,
  accès WSI, PWA.

## Licence

Licence de recherche, usage non commercial, avec clause de non-dispositif
médical (règlement UE 2017/745). Voir [`LICENSE`](LICENSE).
