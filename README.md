# Système Explicable d'Orientation des Patients

Système d'aide à la décision pour le premier accueil médical (régulation et orientation de patients). Le système classe une situation clinique observée parmi un ensemble fini de catégories d'orientation sans poser de diagnostic médical, en fournissant une traçabilité et une justification formelle de chaque étape du raisonnement.

---

## 1. Description du système et Espace de décision

Le système prend en entrée 10 variables cliniques et retourne obligatoirement l'une des 6 décisions suivantes :

| Décision | Définition clinique |
| :--- | :--- |
| `ORIENTATION_URGENTE` | Prise en charge immédiate requise (urgence vitale ou détresse aiguë). |
| `CONSULTATION_PRIORITAIRE` | Consultation médicale requise dans la journée. |
| `CONSULTATION_NORMALE` | Consultation médicale standard non urgente. |
| `SURVEILLANCE` | Simple surveillance à domicile avec consignes d'alerte. |
| `DEMANDER_PRECISIONS` | Absence d'information critique empêchant une décision sécurisée. |
| `SURVEILLANCE_MANUELLE_REQUISE` | Contradiction clinique non arbitrable automatiquement, revue humaine exigée. |

---

## 2. Modélisation du Raisonnement et Hybridation

Le système combine deux approches complémentaires à travers une table de fusion déterministe orientée vers la sécurité :

```text
[Faits cliniques (10 variables)]
         │
         ├──► [Méthode 1 : Moteur Symbolique] ────► Détection contradictions + Règle prioritaire
         │                                                        │
         ├──► [Méthode 2 : Modèle Probabiliste] ──► Distribution Softmax + Contributions
         │                                                        │
         └──► [Table de Fusion Hybride Sécurisée] ────────────────┴──► Décision finale + Justification
```

### 2.1 Méthode 1 : Raisonnement symbolique déterministe
- **Chaînage avant ordonné :** Évaluation séquentielle d'une base de règles de production déclaratives (`data/regles.json`) par ordre décroissant de priorité (100 à 10).
- **Déclenchement strict :** Une règle n'est activée que si l'ensemble de ses prémisses est vérifié de manière non ambiguë.
- **Règles vitales :** Les règles d'urgence absolue (ex. perte de conscience, saignement abondant, association douleur thoracique et détresse respiratoire) disposent de la priorité maximale.

### 2.2 Méthode 2 : Raisonnement probabiliste explicable
- **Modèle :** Régression Softmax multiclasses entraînée par descente de gradient sur des profils cliniques formalisés (`data/cas_entrainement.json`).
- **Distribution de probabilités :** Calcul d'un vecteur de probabilités $P(Y = c \mid X)$ sur les orientations standard (`ORIENTATION_URGENTE`, `CONSULTATION_PRIORITAIRE`, `CONSULTATION_NORMALE`, `SURVEILLANCE`).
- **Explicabilité locale :** Décomposition du score linéaire par variable ($w_{c,i} \cdot x_i$) identifiant les facteurs aggravants ou rassurants pour chaque orientation.

### 2.3 Intégration hybride et Table de fusion
La décision finale est arbitrée selon un principe strict de préservation de la sécurité du patient :
1. **Contradiction clinique sans signe vital :** Orientation vers `SURVEILLANCE_MANUELLE_REQUISE`.
2. **Règle symbolique critique déclenchée (R1, R2, R5) :** Maintien immédiat de l'`ORIENTATION_URGENTE`, même si l'estimation probabiliste est inférieure au seuil nominal.
3. **Absence d'information critique sans règle urgente :** Refus de conclure et déclenchement de `DEMANDER_PRECISIONS`.
4. **Règle prioritaire (R3) :** Orientation `CONSULTATION_PRIORITAIRE`, rehaussée en `ORIENTATION_URGENTE` si $P(\text{urgence}) \ge 0,90$.
5. **Absence de règle symbolique applicable :** Décision déléguée au modèle probabiliste selon les seuils calibrés ($P \ge 0,75 \to \text{Urgent}$, $P \ge 0,50 \to \text{Prioritaire}$, $P \ge 0,30 \to \text{Normale}$, sinon $\text{Surveillance}$).

---

## 3. Traitement explicite des Imperfections

Le système intègre un traitement formel des trois formes d'imperfections de l'information :

### 3.1 Incomplétude (Logique ternaire et Refus de statuer)
- **Domaine ternaire :** Toute variable booléenne admet les valeurs `"oui"`, `"non"` ou `"inconnu"`.
- **Distinction sémantique :** L'état `"inconnu"` (absence d'information) est strictement dissocié de `"non"` (absence avérée du signe clinique).
- **Variables critiques :** Les variables `perte_conscience`, `difficulte_respiratoire`, `douleur_thoracique`, `saignement_important`, `temperature` et `duree_symptomes` sont désignées comme critiques. Si l'une d'elles est `"inconnu"` et qu'aucune règle d'urgence n'est satisfaite par ailleurs, le système refuse toute décision rassurante par défaut et émet `DEMANDER_PRECISIONS`.

### 3.2 Contradictions (Détection et Arbitrage)
Le système vérifie systématiquement la cohérence logique des observations :
1. Déclaration de symptômes bénins (`symptomes_legers = oui`) combinée à un signe de détresse vitale (`perte_conscience = oui` ou `saignement_important = oui`).
2. Déclaration d'une intensité douloureuse minime (`douleur = faible`) associée à une `douleur_thoracique = oui`.

*Arbitrage :* Si une règle d'alerte vitale est confirmée, l'urgence est maintenue pour protéger le patient tout en consignant la contradiction dans l'explication. En l'absence de règle critique, le système bloque l'inférence automatique et requiert une `SURVEILLANCE_MANUELLE_REQUISE`.

### 3.3 Incertitude (Quantification et Justification)
- **Quantification :** L'incertitude est représentée explicitement par la distribution multinomiale issue du modèle Softmax et l'entropie associée.
- **Transparence :** Chaque orientation produite s'accompagne d'un niveau de confiance qualifié (`Très élevée`, `Élevée`, `Moyenne`, `Faible / prudente`) et d'un rapport détaillé listant les règles validées, les faits manquants et les poids prépondérants.

---

## 4. Asymétrie des Coûts d'Erreur

La conception du système est régie par l'évaluation clinique des erreurs :

| Type d'erreur | Exemple clinique | Gravité | Politique de sécurité |
| :--- | :--- | :---: | :--- |
| **Faux négatif urgent** | Classer en `SURVEILLANCE` un patient en détresse vitale | **Critique** | **Tolérance 0 absolue** |
| **Fausse certitude** | Décider sur cas incomplet au lieu de `DEMANDER_PRECISIONS` | **Élevée** | Bloqué par l'ontologie critique |
| **Faux positif urgent** | Classer en `ORIENTATION_URGENTE` une situation bénigne | Modérée | Acceptable si doute clinique |
| **Erreur intermédiaire** | Confondre consultation normale et prioritaire | Faible | Arbitré par la distribution Softmax |

---

## 5. Structure du dépôt

```text
├── data/
│   ├── ontologie.json          # Définition formelle des 10 variables cliniques
│   ├── regles.json             # Base de règles symboliques ordonnées
│   ├── cas_entrainement.json   # Base d'apprentissage du modèle probabiliste
│   └── cas_test.json           # Jeu d'évaluation de référence (11 cas)
├── docs/
│   ├── formalisation_connaissances.md  # Cadrage formel, ontologie et logique
│   └── protocole_evaluation.md         # Méthodologie et métriques d'évaluation
├── src/
│   ├── symbolique/             # Méthode 1 : Moteur de règles déterministe
│   ├── probabiliste/           # Méthode 2 : Régression Softmax explicable
│   ├── hybride/                # Intégration hybride et table de décision
│   ├── llm/                    # Extraction structurée de texte (optionnel)
│   ├── evaluation.py           # Calcul des métriques d'exactitude et matrices
│   └── app.py                  # API REST Flask et interface utilisateur
├── static/                     # Interface web (HTML/CSS/JS)
└── tests/
    └── test_triage.py          # Suite de tests unitaires automatisés (21 tests)
```

---

## 6. Installation et Commandes d'exécution

Le projet est géré avec l'outil **`uv`**.

### Installation

```bash
uv sync
```

### Exécution des composants

```bash
# Exécution de la suite de tests automatisés (21 tests)
uv run pytest

# Exécution du moteur symbolique seul (Méthode 1 - Configuration A)
uv run python src/symbolique/moteur_regles.py

# Exécution du modèle probabiliste seul (Méthode 2)
uv run python src/probabiliste/moteur_probabiliste.py

# Comparaison des configurations (Configuration A vs Configuration B)
uv run python src/hybride/integration_hybride.py

# Lancement du serveur API et de l'interface web
uv run python src/app.py
```

L'interface web est disponible à l'adresse : `http://127.0.0.1:5000`.

---

## 7. Résultats Expérimentaux

Résultats obtenus sur le banc d'évaluation de référence (11 cas cliniques représentatifs) :

| Métrique d'évaluation | Configuration A (Règles seules) | Configuration B (Hybridation A+B) | Objectif cible |
| :--- | :---: | :---: | :---: |
| **Exactitude globale** | 90,9 % (10 / 11) | 100,0 % (11 / 11) | $\ge 90,0\ \%$ |
| **Sensibilité aux urgences vitales** | 100,0 % (5 / 5) | 100,0 % (5 / 5) | 100,0 % |
| **Faux négatifs urgents** | **0** | **0** | **0 strict** |
| **Faux positifs urgents** | 0 | 0 | Minimum |
| **Temps moyen d'inférence** | 0,017 ms / cas | 0,043 ms / cas | $< 1,0\text{ ms}$ |

### Analyse des cas limites

- **Cas C9 (Contradiction clinique) :** Maintien de l'`ORIENTATION_URGENTE` malgré la mention contradictoire de symptômes bénins.
- **Cas C10 (Apport de l'hybridation) :** Patient âgé et fatigué non couvert par les règles strictes, correctement reclassé en `CONSULTATION_PRIORITAIRE` par le modèle Softmax ($P = 64,2\ \%$).
- **Cas C11 (Conflit de modèles) :** Préservation absolue de la décision urgente de la règle critique face à un score probabiliste modéré.
