# Mini-projet — Raisonnement en IA : Système d'orientation des patients

Prototype de système d'aide à l'orientation de patients à raisonnement **explicite, vérifiable et évalué**. Le système ne pose pas de diagnostic médical : il classe une situation décrite par des faits dans une catégorie d'orientation, en justifiant chaque décision.

Deux approches complémentaires sont implémentées et combinées :

| Méthode | Approche | Fichier | Rôle |
|---|---|---|---|
| 1 | Moteur à règles (symbolique) | `src/moteur_regles.py` | 2 — moteur symbolique |
| 2 | Raisonnement probabiliste (score de risque sigmoïde) | `src/moteur_probabiliste.py` | 3 — incertitude/apprentissage |
| 1+2 | Intégration hybride + table de fusion | `src/integration_hybride.py` | 4 — intégration/interface |
| — | Formalisation & connaissances | `docs/formalisation_connaissances.md` | 1 — formalisation |

---

## Démarrage rapide

### 1. Dépendances

```bash
pip install -r requirements.txt
```

### 2. Lancer le moteur à règles seul (Configuration A)

```bash
python3 src/moteur_regles.py
```

### 3. Lancer la méthode probabiliste seule (méthode 2)

```bash
python3 src/moteur_probabiliste.py
```

### 4. Comparer les deux configurations (exigence du sujet)

```bash
python3 src/integration_hybride.py
```

Affiche le tableau de comparaison Config A (règles seules) vs Config B (hybride) sur les 11 cas de test, avec exactitude, temps et liste des échecs.

### 5. Interface web (démo)

```bash
python3 src/app.py
```

Puis ouvrir [http://127.0.0.1:5000](http://127.0.0.1:5000) dans un navigateur. L'interface (Vue.js via CDN) permet de saisir les observations d'un patient et d'afficher la décision finale, la confiance, la probabilité d'urgence, les règles évaluées, les contradictions et les informations manquantes.

---

## Structure du projet

```
projet_ia/
├── src/
│   ├── moteur_regles.py         # Méthode 1 : moteur à règles (rôle 2)
│   ├── moteur_probabiliste.py   # Méthode 2 : raisonnement probabiliste (rôle 3)
│   ├── integration_hybride.py   # Rôle 4 : table de fusion + comparaison
│   └── app.py                   # Rôle 4 : API Flask + interface web
├── templates/
│   └── index.html               # Interface Vue.js (CDN)
├── data/
│   └── cas_test.json            # 11 cas de test (reproductibilité)
├── docs/
│   └── formalisation_connaissances.md   # Rôle 1 : formalisation
├── requirements.txt
└── README.md
```

---

## Jeu de test

Le fichier `data/cas_test.json` contient 11 cas (dont 3 cas limites C9, C10, C11), externalisés du code pour la reproductibilité. Les cas couvrent :

- les situations simples (C1–C7) ;
- l'incomplétude (C8 : informations critiques manquantes) ;
- les contradictions (C9 : symptômes légers + perte de conscience) ;
- les cas ambigus que le moteur à règles seul ne tranche pas (C10) ;
- le cas d'une règle urgente activée malgré une douleur déclarée faible et une probabilité modérée (C11) : la règle critique prime par sécurité, jamais annulée par le modèle probabiliste.

---

## Table de fusion (orientée sécurité)

L'intégration (`integration_hybride.py`) applique une fusion déterministe dont le principe directeur est : *le coût d'un faux négatif urgent étant très élevé, la fusion privilégie toujours l'hypothèse la plus prudente*.

1. **Contradiction non tranchée** → `SURVEILLANCE_MANUELLE_REQUISE` (vérification humaine).
2. **Règle urgente déclenchée** → `ORIENTATION_URGENTE` conservée, même si la probabilité probabiliste est modérée (principe de sécurité : une règle critique n'est jamais annulée par le modèle). Cas C11.
3. **Informations critiques manquantes, aucune règle urgente** → `DEMANDER_PRECISIONS` (le système ne devine pas).
4. **Règle prioritaire (R3)** → conservée, sauf si P(urgence) ≥ 0.90 (probabilité très forte), auquel cas rehaussement en `ORIENTATION_URGENTE`.
5. **Aucune règle décisive** → décision par le modèle probabiliste.
6. Une **justification combinée** est toujours produite : « méthode 1 dit X parce que R… ; méthode 2 dit Y avec P=… ; fusion finale = … ».

---

## Résultats observés

Sur les 11 cas :

- **Config A (règles seules)** : 10/11 (90,9 %). Échec sur C10, cas ambigu que les règles ne couvrent pas et qui nécessite justement la méthode 2.
- **Config B (hybride)** : 10/11 (90,9 %). Résout C10. Le seul échec est C5.

### Limite connue : cas C5 / C10

Les cas C5 et C10 ont des **entrées identiques** (fatigue importante + douleur moyenne + température normale + durée courte, aucun signe critique) mais des décisions attendues **différentes** dans le jeu de test (`CONSULTATION_NORMALE` pour C5, `CONSULTATION_PRIORITAIRE` pour C10). Aucun système déterministe ne peut satisfaire les deux attendus simultanément. Le modèle probabiliste, calibré pour traiter C10 (le cas qui justifie l'existence de la méthode 2), produit `CONSULTATION_PRIORITAIRE` pour cette entrée : C10 est donc résolu, au prix de C5. Cette contradiction inhérente au jeu de test est documentée comme limite dans le rapport.

Temps de raisonnement : < 0,03 ms/cas pour la configuration hybride (compatible avec un usage interactif).

---

## Reproductibilité

- Code Python 3 standard, dépendances réduites au minimum (Flask uniquement pour l'interface).
- Cas de test externalisés dans `data/cas_test.json` (modifiables sans toucher au code).
- Chaque méthode est exécutable seule via la ligne de commande, avec l'option `--data` pour pointer vers un autre jeu de cas.
- Le script de comparaison produit un tableau reproductible des deux configurations.

## Notes par rôle

- **Rôle 1 (formalisation/connaissances)** : livré dans `docs/formalisation_connaissances.md` — problème, ontologie des variables, base de règles formalisée, coût des erreurs, critère d'acceptation, traçabilité formalisation↔code.
- **Rôle 4 (intégration/interface)** : livré dans `src/integration_hybride.py` (table de fusion + comparaison Config A/B) et `src/app.py` + `templates/index.html` (interface web).
- **Rôle 3 (probabiliste)** : `src/moteur_probabiliste.py` est une implémentation minimale fonctionnelle (scaffold), calibrée pour démontrer l'intégration ; le titulaire du rôle 3 peut remplacer les poids par des poids appris sans casser la fusion, tant que la fonction `evaluer_probabiliste(faits) -> ResultatProbabiliste` conserve sa signature.
