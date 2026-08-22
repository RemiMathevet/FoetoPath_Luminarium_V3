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

### Canari anti-rançongiciel

`canary_sentinel.py` surveille en inotify des répertoires-appâts. Rien n'y est
jamais créé ni modifié légitimement, donc le moindre événement est une alarme sans
faux positif, et la réaction est immédiate plutôt que différée au prochain passage
d'un cron.

Les appâts se posent en trois couches, du plus tôt mordu au plus tard :

| Où | Pourquoi |
|---|---|
| `$HOME` | Un rançongiciel arrivé par le navigateur ou le mail commence là, pas sur les disques de données |
| Racine de chaque disque | Il est mordu avant que le parcours ne descende dans les gros arbres |
| Dans les arbres de cas et de lames | Dernier filet, si le parcours commence par le milieu |

Seuls les appâts posés dans les arbres de cas ont besoin d'un nom commençant par
un point : le scan placenta crée un dossier par sous-répertoire trouvé, et un appât
visible y fabriquerait un faux cas. Rien n'énumère les racines de disque ni `$HOME`,
les appâts y sont donc visibles — ce qui est préférable, un parcours qui saute les
noms cachés les voit quand même.

L'appât se met dans un répertoire à lui, jamais en fichier nu à la racine d'un
disque : la surveillance porte sur le répertoire contenant, et une racine de disque
sert de zone de dépôt. Le moindre `cp` y déclencherait une fausse alarme.

La surveillance porte sur le **répertoire**, pas seulement sur les fichiers-appâts :
un rançongiciel qui écrit à côté puis supprime l'original ne déclenche aucun
événement de modification, et la note de rançon déposée dans chaque répertoire
parcouru est une création. Les appâts portent un contenu plausible — un
répertoire vide peut être sauté.

Sur les arbres qu'aucune sauvegarde ne parcourt, `--watch-read` ajoute l'ouverture
et la lecture aux événements surveillés. Personne n'ouvre jamais un appât, donc
une lecture dénonce la reconnaissance **avant** le chiffrement. C'est le
déclenchement le plus précoce disponible, mais c'est le seul qui puisse avoir un
faux positif : la lecture, contrairement à l'écriture, a des auteurs légitimes.
D'où trois garde-fous, un par lecteur légitime identifié.

Le parcours d'un répertoire n'est pas un événement de lecture (`IN_ISDIR` est
ignoré), sans quoi le `du` de la purge nocturne déclencherait chaque nuit. Ce
filtre suffit à mettre `ls`, `tree`, `find` et `du` hors de cause : aucun n'ouvre
le contenu d'un fichier. Ensuite, `backup_snapshot.sh` exclut les appâts du rsync,
sans quoi la sauvegarde les lirait tous les soirs — ils n'ont rien à faire dans
un snapshot de toute façon, `--seed` les recrée.

Reste `grep -r`, la seule commande courante qui lise vraiment les fichiers, et qui
descend dans les répertoires cachés. Un `--exclude-dir` sur le nom d'appât, posé
en alias, ferme le cas — mais un alias ne vaut que pour les shells interactifs :
un script qui grep récursivement dans un arbre surveillé en lecture doit porter
l'exclusion lui-même.

Au déclenchement, dans l'ordre : pose du verrou, coupure de la sortie réseau,
arrêt des unités systemd, des tunnels, des serveurs, puis mail. Le verrou d'abord
parce qu'un redémarrage peut courir contre nous ; le réseau avant les serveurs
parce que c'est le chemin d'entrée.

**Couper la sortie, pas les processus.** Tuer les tunnels ne tient pas : ce sont
des unités `Restart=on-failure`, et pour systemd un `SIGKILL` est un échec — elles
reviennent en quelques secondes. La sentinelle pose donc une règle nftables dans
une table à elle, qui bloque le port de l'edge Cloudflare en TCP et en UDP. Elle
survit aux redémarrages d'unité et vaut pour tous les tunnels, y compris ceux
ajoutés après coup : aucun inventaire à tenir à jour. Les processus sont tués
ensuite, pour l'effet immédiat ; s'ils reviennent, ils ne joignent plus personne.

Ce n'est pas une précaution théorique : le hub n'est pas la seule porte. Une
douzaine de services distincts tournent sur le même compte et écrivent dans les
mêmes arborescences, et le hub — Argon2id + TOTP — est le mieux défendu du lot.
Le jour de l'incident on veut « plus rien ne sort », pas « ces deux-là s'arrêtent ».

**Le verrou est ce qui empêche la résurrection.** Tuer un processus ne suffit
pas : un `Restart=always` le ramène en cinq secondes. `Foeto/app.py` et
`Lumi/app.py` refusent donc de démarrer tant que le fichier verrou existe et
sortent en code 66, que le lancement vienne de systemd, de nohup, d'un cron ou
de la main. L'unité met ce code en `RestartPreventExitStatus` pour ne pas boucler.
Le verrou survit au redémarrage du poste et ne se lève qu'à la main.

```bash
./canary_sentinel.py --self-check                    # événement → verrou, de bout en bout
./canary_sentinel.py --seed --watch <dir_appat>      # poser les appâts
./canary_sentinel.py --systemd --watch <dir_appat> \
    --port 5004 --port 5080 --tunnels-all            # unité à installer
```

Ce que le canari ne couvre pas : le poste a les droits d'écriture sur ses propres
cibles de sauvegarde, donc un rançongiciel peut effacer les snapshots
directement. Seule une sauvegarde en *pull*, ou une cible en append-only, ferme
cette porte. Et la copie hors-site n'est pas surveillée : inotify est local, il
faudrait une sentinelle sur la machine distante.

#### Lever le verrou à la main

Rien ne se relance tout seul, et c'est voulu. La levée est une décision, pas une
manipulation — le verrou dit *quand* et *quoi*, à vous de dire *pourquoi*.

```bash
cat ~/.foetopath_canary_tripped        # horodatage et événement déclencheur
```

Avant de lever, établir ce qui a bougé depuis cet horodatage — la question n'est
pas « le canari a-t-il eu raison », c'est « qu'est-ce qui a touché ce
répertoire » :

```bash
find <arbre_surveillé> -newermt '2026-01-01 12:00' -type f | head -50
ls -l <répertoire_appât>/              # les appâts eux-mêmes ont-ils changé ?
```

Un déclenchement compris et bénin (une manipulation à soi, un outil d'indexation)
se lève ainsi :

```bash
sudo nft delete table inet canari                       # rouvrir la sortie réseau
rm ~/.foetopath_canary_tripped
./canary_sentinel.py --seed --watch <répertoire_appât>   # réarmer si les appâts ont bougé
```

Ne pas oublier la table `nft` : sans elle, les serveurs redémarrent et paraissent
sains, mais aucun tunnel ne monte. C'est l'état le plus pénible à diagnostiquer —
tout est vert en local, rien ne répond de l'extérieur.

Puis **relancer la sentinelle avant les serveurs** — sinon on rouvre l'accès sans
surveillance, et c'est précisément la fenêtre qu'on cherchait à fermer.

Si le déclenchement n'est pas expliqué, le verrou reste posé : débrancher le
réseau, monter la dernière sauvegarde saine en lecture seule, et comparer avant
de restaurer quoi que ce soit.

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
- **Canari anti-rançongiciel** — écrit et testé (voir plus haut), pas encore
  déployé : appâts à poser dans l'arborescence de production et unité systemd à
  installer.
- **Sauvegarde en pull ou cible append-only** — tant que le poste peut écrire sur
  ses propres cibles, les snapshots restent à portée d'un rançongiciel.

## Licence

Licence de recherche, usage non commercial, avec clause de non-dispositif
médical (règlement UE 2017/745). Voir [`LICENSE`](LICENSE).
