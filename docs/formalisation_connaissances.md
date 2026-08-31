# Rôle 1 — Formalisation et connaissances

---

## 1. Objectif du système

Le système a pour objectif d'aider à l'orientation de patients en premier accueil (accueil infirmier ou centre de régulation).

Il ne pose aucun diagnostic médical : il classe une situation décrite par des faits observés dans une catégorie d'orientation prédéfinie, en explicitant son raisonnement.

À partir d'une description partielle ou complète de l'état d'un patient, le système produit :

1. une orientation parmi un ensemble fini de décisions ;
2. un niveau de confiance associé ;
3. une justification du raisonnement ;
4. le signalement des informations manquantes et des contradictions éventuelles.

### Espace de décision

Le système retourne obligatoirement l'une des décisions suivantes :

| Orientation                       | Signification                                                   |
| :-------------------------------- | :-------------------------------------------------------------- |
| `ORIENTATION_URGENTE`           | Prise en charge immédiate requise                              |
| `CONSULTATION_PRIORITAIRE`      | Consultation médicale dans la journée                         |
| `CONSULTATION_NORMALE`          | Consultation standard non urgente                               |
| `SURVEILLANCE`                  | Surveillance simple à domicile                                 |
| `DEMANDER_PRECISIONS`           | Informations critiques manquantes, refus de conclure            |
| `SURVEILLANCE_MANUELLE_REQUISE` | Contradiction non arbitrable, vérification humaine nécessaire |

---

## 2. Entrées du système

### 2.1 Logique ternaire

Les variables cliniques booléennes admettent trois valeurs :

```text
"oui" | "non" | "inconnu"
```

L'état `"inconnu"` formalise l'absence d'information, distincte de l'absence de signe (`"non"`). Cette distinction permet de traiter explicitement l'incomplétude.

### 2.2 Ontologie des variables

| Variable                    | Domaine                                         | Catégorie  | Description                         |
| :-------------------------- | :---------------------------------------------- | :---------- | :---------------------------------- |
| `temperature`             | `normale` / `elevee` / `inconnu`          | critique    | Signe vital thermique               |
| `duree_symptomes`         | `courte` / `longue` / `inconnu`           | critique    | Évolution temporelle               |
| `difficulte_respiratoire` | `oui` / `non` / `inconnu`                 | critique    | Signe fonctionnel respiratoire      |
| `douleur_thoracique`      | `oui` / `non` / `inconnu`                 | critique    | Signe fonctionnel cardiothoracique  |
| `perte_conscience`        | `oui` / `non` / `inconnu`                 | critique    | Signe neurologique d'alerte         |
| `saignement_important`    | `oui` / `non` / `inconnu`                 | critique    | Signe hémodynamique d'alerte       |
| `douleur`                 | `faible` / `moyen` / `fort` / `inconnu` | secondaire  | Intensité subjective de la douleur |
| `fatigue_importante`      | `oui` / `non` / `inconnu`                 | secondaire  | Signe général d'asthénie         |
| `symptomes_legers`        | `oui` / `non` / `inconnu`                 | déclaratif | Déclaration globale du patient     |
| `age`                     | entier /`"inconnu"`                           | contextuel  | Caractéristique patient            |

Une variable est dite **critique** si son absence (`"inconnu"`) peut masquer une urgence vitale et doit empêcher une conclusion normale ou rassurante par défaut.

---

## 3. Connaissances du domaine

### 3.1 Base de règles logiques

Les connaissances sont modélisées sous forme de règles de production déclaratives dans `data/regles.json`, ordonnées par priorité décroissante. Une condition n'est satisfaite que si toutes ses prémisses sont connues et égales à la valeur attendue.

| Règle | Priorité | Condition (SI)                                                            | Conclusion (ALORS)           | Confiance         |
| :----- | :-------- | :------------------------------------------------------------------------ | :--------------------------- | :---------------- |
| R1     | 100       | `perte_conscience = oui`                                                | `ORIENTATION_URGENTE`      | Très élevée    |
| R5     | 95        | `saignement_important = oui`                                            | `ORIENTATION_URGENTE`      | Très élevée    |
| R2     | 90        | `douleur_thoracique = oui` ET `difficulte_respiratoire = oui`         | `ORIENTATION_URGENTE`      | Très élevée    |
| R3     | 50        | `temperature = elevee` ET `duree_symptomes = longue`                  | `CONSULTATION_PRIORITAIRE` | Moyenne           |
| R4     | 10        | `douleur = faible` ET `temperature = normale` ET `duree_symptomes = courte` ET tous les signes critiques sont explicitement `non` | `SURVEILLANCE` | Faible (prudente) |

### 3.2 Traitement de l'incomplétude

L'absence d'une variable critique n'empêche pas le déclenchement d'une règle urgente non concernée par cette variable.

En revanche, si aucune règle critique ne se déclenche et qu'au moins une variable critique vaut `"inconnu"`, le système conclut `DEMANDER_PRECISIONS`. Une règle rassurante ne peut donc jamais transformer un inconnu en absence de signe.

### 3.3 Traitement des contradictions

Trois situations contradictoires sont identifiées :

1. `symptomes_legers = oui` ET `perte_conscience = oui`
2. `symptomes_legers = oui` ET `saignement_important = oui`
3. `douleur = faible` ET `douleur_thoracique = oui`

Règle de résolution :

- Si une règle critique (R1, R5, R2) est satisfaite, la décision urgente est maintenue et la contradiction est signalée dans la justification.
- En l'absence de règle critique applicable, le système bloque la décision automatique et retourne `SURVEILLANCE_MANUELLE_REQUISE`.

### 3.4 Modèle probabiliste et extraction de texte

La méthode 2 est une régression softmax multiclasses apprise par descente de gradient sur `data/cas_entrainement.json`. Elle fournit une distribution sur les quatre orientations ordinaires et expose les coefficients actifs pour le cas courant. Les données sont synthétiques : la sortie est une estimation pédagogique, pas une probabilité clinique calibrée.

Une description libre peut être envoyée à `POST /api/extraire-faits`. L'approche 3 utilise Gemini comme extracteur : il ne produit aucune orientation, respecte un schéma JSON strict et transforme toute ambiguïté en `inconnu`. Le moteur local reste responsable de la décision et de sa justification.

---

## 4. Hypothèses de modélisation

- H1 — Les observations fournies sont traitées telles quelles (sincères mais potentiellement incomplètes ou contradictoires).
- H2 — Le système évalue une situation ponctuelle à un instant t (pas d'historique temporel multi-visites).
- H3 — Les règles sont des simplifications pédagogiques pour un prototype démonstrateur, non un référentiel médical certifié.
- H4 — Le jeu de test est constitué de cas représentatifs incluant des situations simples, incomplètes, contradictoires et limites.

---

## 5. Contraintes du système

- C1 — Espace fermé : la décision appartient strictement à l'ensemble défini au §1.
- C2 — Refus de faux réconfort : aucune décision de confiance élevée ne peut être prise en présence de variables critiques inconnues sans règle d'urgence déclenchée.
- C3 — Traçabilité : toute contradiction détectée doit figurer dans la justification finale.
- C4 — Performance : le temps de réponse doit être compatible avec une utilisation interactive en temps réel (< 1 ms par cas).

---

## 6. Coût des erreurs

Toutes les erreurs de classification n'ont pas la même gravité :

| Type d'erreur         | Exemple                                                                    | Gravité clinique                                   |
| :-------------------- | :------------------------------------------------------------------------- | :-------------------------------------------------- |
| Faux négatif urgent  | Classer en`SURVEILLANCE` un patient nécessitant `ORIENTATION_URGENTE` | **Critique** (perte de chance / danger vital) |
| Faux positif urgent   | Classer en`ORIENTATION_URGENTE` une situation bénigne                   | Modérée (surcharge logistique)                    |
| Erreur intermédiaire | Confondre`CONSULTATION_NORMALE` et `CONSULTATION_PRIORITAIRE`          | Faible à modérée                                 |
| Fausse certitude      | Conclure au lieu de`DEMANDER_PRECISIONS` sur cas incomplet               | Élevée (décision non étayée)                   |

**Principe de sécurité** : face à l'asymétrie des coûts, en cas de doute ou d'ambiguïté, le système privilégie systématiquement l'orientation la plus protectrice pour le patient.

---

## 7. Critère d'acceptation du prototype

Le prototype est validé si, sur le jeu de test de référence (au moins 10 cas, dont 3 cas limites) :

1. Zéro faux négatif urgent n'est produit.
2. L'exactitude globale est supérieure ou égale à 80 % sur les cas non ambigus.
3. 100 % des cas avec variables critiques manquantes sans règle urgente ni contradiction aboutissent à `DEMANDER_PRECISIONS`.
4. 100 % des contradictions présentes dans les cas de test sont détectées et documentées dans la justification.
