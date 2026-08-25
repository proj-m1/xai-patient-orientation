# Système explicable d'orientation des patients

Mini-projet — Raisonnement en Intelligence Artificielle (SDIA M1, 2026)

## 1. Objectif

À partir d'informations sur un patient (âge, température, durée des
symptômes, douleur, difficulté respiratoire, douleur thoracique, perte de
conscience, saignement important, fatigue importante), le système propose
une orientation parmi quatre catégories :

1. Orientation urgente
2. Consultation prioritaire
3. Consultation normale
4. Surveillance / demande d'informations supplémentaires

Chaque décision est accompagnée d'une explication : informations prises en
compte, règles appliquées, niveau d'incertitude, informations manquantes,
raison de la décision finale.

## 2. État d'avancement

| Approche | Statut |
|---|---|
| Méthode 1 — moteur à règles (symbolique) | ✅ Implémentée (`src/moteur_regles.py`) |
| Méthode 2 — raisonnement probabiliste (réseau bayésien simplifié) | ⏳ À venir |
| Fusion des deux méthodes (Configuration B) | ⏳ À venir |
| Comparaison chiffrée des configurations A / B | ⏳ À venir (le script actuel calcule déjà exactitude, temps et échecs pour la configuration A seule) |

## 3. Prérequis / dépendances

- Python **3.10+** (utilisation de `list[tuple[...]]`, aucune dépendance
  tierce nécessaire pour la méthode 1).
- Aucune bibliothèque externe requise à ce stade (bibliothèque standard
  uniquement : `json`, `argparse`, `time`, `dataclasses`, `pathlib`).

Quand la méthode 2 (probabiliste) sera ajoutée, ce fichier et
`requirements.txt` seront mis à jour si une dépendance externe devient
nécessaire (ex. `pgmpy` pour un vrai réseau bayésien, sinon implémentation
maison en Python pur).

## 4. Structure du projet

```
projet/
├── README.md
├── requirements.txt
├── data/
│   └── cas_test.json      # 11 cas de test (dont 3 cas limites), séparés du code
└── src/
    └── moteur_regles.py   # Méthode 1 : moteur à règles + trace explicative
```

## 5. Commande de lancement

Depuis la racine du projet :

```bash
python3 src/moteur_regles.py
```

Options disponibles :

```bash
# Utiliser un autre jeu de cas de test
python3 src/moteur_regles.py --data data/cas_test.json

# N'afficher que le bilan final (sans la trace détaillée de chaque cas)
python3 src/moteur_regles.py --quiet
```

## 6. Sortie produite

Pour chaque cas de test, le script affiche :

- les faits reçus (entrées du patient) ;
- chaque règle évaluée et son résultat (déclenchée / non déclenchée) ;
- les contradictions détectées entre les faits, s'il y en a ;
- les informations critiques manquantes, s'il y en a ;
- le niveau de confiance ;
- la décision finale ;
- la justification en langage naturel.

Puis un **bilan global** :

- exactitude par rapport aux décisions attendues du jeu de test ;
- temps de raisonnement total et moyen ;
- liste des échecs (décision attendue vs obtenue) ;
- liste des cas que le moteur à règles seul ne peut pas trancher finement
  (et qui nécessitent donc la méthode 2, à venir).

## 7. Jeu de données de test

`data/cas_test.json` contient 11 cas (C1 à C11), dont 3 cas limites (C9,
C10, C11), conformément à l'exigence du sujet (≥ 10 cas dont 3 limites).
Chaque cas comprend :

```json
{
  "nom": "C1 - Symptômes légers, durée courte, aucune alerte",
  "faits": { "temperature": "normale", "douleur": "faible", "...": "..." },
  "decision_attendue": "SURVEILLANCE"
}
```

Le champ `"inconnu"` signifie explicitement une information manquante
(distincte de `"non"`).

## 8. Limites connues (méthode 1 seule)

- Les cas C4, C5 et C10 ne peuvent pas être tranchés finement par les
  règles seules : elles retombent sur une orientation par défaut
  (`CONSULTATION_NORMALE`) avec un niveau de confiance faible. Le cas C10
  échoue explicitement au test (décision attendue :
  `CONSULTATION_PRIORITAIRE`), ce qui illustre concrètement pourquoi la
  méthode 2 (raisonnement probabiliste) est nécessaire en complément.
- La règle **R5** (saignement important → orientation urgente) a été
  ajoutée par l'équipe pour couvrir le cas C7 ; elle ne figure pas
  explicitement dans l'énoncé du sujet et doit être justifiée dans le
  rapport comme une connaissance choisie par le groupe.
- Le système fournit une orientation explicable ; il ne remplace pas une
  décision humaine (rappel de l'hypothèse du sujet).

## 9. Contribution

- **Rôle 2 (moteur symbolique)** : `src/moteur_regles.py` — base de règles,
  détection de contradictions/informations manquantes, trace explicative.

*(Section à compléter par les autres membres du groupe au fur et à mesure
de leur contribution : formalisation, méthode probabiliste, intégration,
tests.)*
