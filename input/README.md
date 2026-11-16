# input/

Fichiers à fournir soi-même (ils ne sont pas dans le dépôt, voir `.gitignore`) :

| Fichier | D'où il vient |
|---|---|
| `queens-domain-actors.json` | `node map/extract-map-data.js <dossier des niveaux exportés> input/queens-domain-actors.json` |
| `VideoConfigMap.json` | export FModel du niveau `VideoConfigMap` (sert à placer la boutique de l'Île du marchand) |

`enemy_names.json` (fourni) : liste des fiches du bestiaire, utilisée par `map/add_bestiary.py`.
