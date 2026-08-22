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

Les bases et les dossiers de cas partent chaque nuit vers trois cibles, en
snapshots datés : les photos sont dédupliquées par hardlink d'un snapshot à
l'autre, et les plus anciens sont purgés en FIFO au-delà d'un plafond de taille.
Rien n'est écrasé — une journée corrompue produit un snapshot de plus, elle ne
remplace pas les précédents.

La copie à chaud d'une base SQLite se fait par `VACUUM INTO` ou
`sqlite3 .backup`, jamais par `cp` sur une base en écriture.

Deux disques cibles vivent dans le même boîtier que la source : ils protègent
d'une panne disque, pas d'un sinistre du poste. Seule la cible hors-site compte
comme copie de secours.

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
dossiers placenta, templates de CR. Et les quatre coutures entre composants
(`Foeto/tests/test_integration.py`) : liaison dossier ↔ lame, génération du CR
microscopique, accès WSI par le proxy, soumission PWA.

Les numéros de dossier des fixtures sont inventés — ce répertoire part dans le
miroir public, où `publish_public.sh` refuse tout numéro réel.

## Chantiers en cours

- **SQLCipher** — regrouper les ouvertures de base derrière un point d'entrée
  unique, condition pour n'ajouter la clé qu'à un seul endroit le jour du
  chiffrement.
- **Canaris anti-rançongiciel** — répertoires-appâts dans l'arborescence des cas
  et des lames, surveillés en inotify : rien n'y est jamais créé ni modifié
  légitimement, donc le moindre événement est une alarme sans faux positif, et
  la réaction est immédiate plutôt que différée au prochain passage d'un cron.
  Surveiller le répertoire et pas seulement les fichiers-appâts : un
  rançongiciel qui écrit à côté puis supprime l'original ne déclenche aucun
  événement de modification.
  Les snapshots datés protègent déjà d'un écrasement ; ce que le canari couvre,
  c'est le délai de détection. Reste hors de sa portée le fait que le poste ait
  les droits d'écriture sur ses propres cibles de sauvegarde — un rançongiciel
  peut effacer les snapshots directement. Seule une sauvegarde en *pull*, ou une
  cible en append-only, ferme cette porte.

## Licence

Licence de recherche, usage non commercial, avec clause de non-dispositif
médical (règlement UE 2017/745). Voir [`LICENSE`](LICENSE).
