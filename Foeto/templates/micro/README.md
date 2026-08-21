# Grilles de lecture — Microscopie

Ce dossier contient les templates de grilles de lecture pour l'examen microscopique.

## Format

Chaque template est un fichier `.json` avec la structure suivante :

```json
{
  "name": "Nom de la grille",
  "description": "Description courte",
  "icon": "🔬",
  "organ_type": "poumon",
  "fields": [
    {
      "id": "architecture",
      "label": "Architecture générale",
      "type": "select",
      "options": ["Normal", "Remanié", "Immature"]
    },
    {
      "id": "inflammation",
      "label": "Inflammation",
      "type": "yn"
    },
    {
      "id": "commentaire",
      "label": "Commentaire",
      "type": "text"
    }
  ]
}
```

## Types de champs supportés

- `select` : choix unique parmi des options
- `multi` : choix multiples
- `yn` : oui/non
- `text` : texte libre
- `number` : valeur numérique
- `score` : score numérique avec échelle

## Ajout d'une grille

Créez un fichier `.json` dans ce dossier. Il apparaîtra automatiquement dans l'onglet Microscopie de l'admin.
