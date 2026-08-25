# Rôle 1 — Formalisation et connaissances

**Projet :** Système explicable d'orientation des patients
**Cours :** Raisonnement en Intelligence Artificielle — Mini-projet M1 SDIA 2026
**Rôle documenté ici :** 1. Formalisation / connaissances
**Auteur de cette contribution :** RAKOTONIRINA Tahinjanahary

---

## 1. Choix et cadrage du problème

### 1.1 Domaine choisi

Le groupe a choisi de concevoir un **système d'aide à l'orientation de patients** dans un contexte de premier accueil (type accueil infirmier ou centre d'appel de régulation). Le système ne pose pas de diagnostic médical : il classe une situation décrite par un ensemble de faits observés dans une **catégorie d'orientation**, avec une justification explicite du raisonnement suivi.

Ce choix respecte la contrainte du sujet : le système ne doit pas se limiter à « appeler un modèle et afficher une prédiction ». Chaque décision doit pouvoir être retracée jusqu'aux règles ou aux probabilités qui l'ont produite.

### 1.2 Objectif du système

Étant donné une description partielle ou complète de l'état d'un patient (symptômes, signes vitaux, durée d'évolution), le système doit :

1. produire une **orientation** parmi un ensemble fini de décisions possibles ;
2. produire un **niveau de confiance** associé à cette décision ;
3. produire une **justification lisible** (quelles règles ou quelles probabilités ont conduit à ce résultat) ;
4. signaler explicitement les **informations manquantes** et les **contradictions** entre faits, plutôt que de les ignorer.

### 1.3 Sorties possibles (espace de décision)

| Orientation | Signification |
|---|---|
| `ORIENTATION_URGENTE` | Prise en charge immédiate requise |
| `CONSULTATION_PRIORITAIRE` | Consultation à programmer rapidement (même jour) |
| `CONSULTATION_NORMALE` | Consultation standard, pas de caractère d'urgence identifié |
| `SURVEILLANCE` | Pas de consultation immédiate, simple surveillance à domicile |
| `DEMANDER_PRECISIONS` | Le système refuse de conclure : informations critiques manquantes |
| `SURVEILLANCE_MANUELLE_REQUISE` | Contradiction non tranchée automatiquement : vérification humaine nécessaire |

Cet ensemble fermé de sorties est un choix de formalisation volontaire : il permet une évaluation quantitative simple (comparaison décision obtenue / décision attendue) exigée par le protocole d'évaluation du sujet.

---

## 2. Entrées du système

### 2.1 Nature des entrées

Un **cas** est un ensemble de faits sur un patient, représenté comme un dictionnaire `champ → valeur`. Les valeurs cliniques booléennes utilisent volontairement trois états et non deux :

```
"oui" | "non" | "inconnu"
```

Le choix d'un troisième état `"inconnu"` (plutôt que de forcer `"non"` par défaut) est **la décision de formalisation centrale du rôle 1** : elle permet de distinguer *absence de signe confirmée* et *absence d'information*, ce qui est indispensable pour traiter l'incomplétude comme l'exige le sujet.

### 2.2 Table des variables (ontologie des faits)

| Variable | Domaine | Rôle |
|---|---|---|
| `age` | entier ou `"inconnu"` | contextuel (non exploité par les règles actuelles, réservé pour extension) |
| `temperature` | `normale` / `elevee` / `inconnu` | critique |
| `duree_symptomes` | `courte` / `longue` / `inconnu` | critique |
| `douleur` | `faible` / `moyen` / `fort` / `inconnu` | secondaire |
| `difficulte_respiratoire` | `oui` / `non` / `inconnu` | critique |
| `douleur_thoracique` | `oui` / `non` / `inconnu` | critique |
| `perte_conscience` | `oui` / `non` / `inconnu` | critique |
| `saignement_important` | `oui` / `non` / `inconnu` | critique |
| `fatigue_importante` | `oui` / `non` / `inconnu` | secondaire, utilisée par la méthode probabiliste |
| `symptomes_legers` | `oui` / `non` / `inconnu` | déclaratif, utilisé pour détecter les contradictions |

Les variables dites **critiques** sont celles dont l'absence de valeur (`inconnu`) doit empêcher une conclusion à haute confiance si aucune règle certaine ne s'est déclenchée (cf. §5).

### 2.3 Hypothèses de modélisation

- H1 — Les faits fournis sont supposés sincères mais potentiellement incomplets ou incohérents (erreur de saisie, patient peu coopératif) : le système doit rester robuste dans ces deux cas.
- H2 — Un seul cas est traité à la fois ; il n'y a pas de suivi temporel multi-visites dans cette version.
- H3 — Les règles cliniques codées (R1 à R5) sont des simplifications pédagogiques validées par le groupe, pas un protocole médical réel ; le système est un prototype démonstrateur, non un dispositif médical.
- H4 — La méthode probabiliste (méthode 2) est entraînée/calibrée sur un jeu de cas synthétiques cohérent avec la base de règles, dans le seul but de couvrir les cas que les règles ne tranchent pas.

### 2.4 Contraintes

- C1 — Le système doit toujours retourner une décision parmi l'ensemble fermé défini en §1.3, jamais une valeur libre.
- C2 — Le système ne doit jamais renvoyer une confiance « élevée » lorsque des informations critiques manquent et qu'aucune règle certaine ne s'est déclenchée.
- C3 — Une contradiction détectée doit toujours apparaître dans la justification, même si une règle prioritaire tranche malgré elle.
- C4 — Le temps de raisonnement doit rester compatible avec un usage interactif (mesuré en millisecondes, cf. rôle 5 / évaluation).

---

## 3. Coût des erreurs et critère d'acceptation

### 3.1 Analyse du coût des erreurs

Toutes les erreurs n'ont pas le même coût dans un système d'orientation médicale : c'est pourquoi le sujet impose de le traiter explicitement.

| Type d'erreur | Exemple | Coût |
|---|---|---|
| Faux négatif urgent | Décider `SURVEILLANCE` alors que la situation exigeait `ORIENTATION_URGENTE` | **Très élevé** — mise en danger du patient |
| Faux positif urgent | Décider `ORIENTATION_URGENTE` alors qu'une simple consultation aurait suffi | Modéré — coût organisationnel, pas de danger vital |
| Confusion entre niveaux intermédiaires | `CONSULTATION_NORMALE` au lieu de `CONSULTATION_PRIORITAIRE` | Faible à modéré |
| Conclusion à tort au lieu de `DEMANDER_PRECISIONS` | Le système tranche alors qu'il aurait dû avouer son incertitude | Élevé — fausse confiance dangereuse |

### 3.2 Principe de conception induit

Le coût très asymétrique du faux négatif urgent justifie le **principe de sécurité** appliqué dans tout le système (formalisé au rôle 4 dans la table de fusion) : *en cas de doute, le système privilégie toujours l'hypothèse la plus prudente* (ne jamais sous-estimer un signe critique, préférer avouer l'incertitude plutôt que deviner).

### 3.3 Critère d'acceptation du prototype

Le prototype est jugé acceptant si, sur le jeu de test (≥ 10 cas dont 3 cas limites, cf. `data/cas_test.json`) :

1. **Zéro** faux négatif urgent (aucun cas réellement urgent classé `SURVEILLANCE` ou `CONSULTATION_NORMALE`) ;
2. exactitude globale ≥ 80 % sur l'ensemble des cas non ambigus ;
3. 100 % des cas avec informations critiques manquantes ET aucune règle déclenchée produisent `DEMANDER_PRECISIONS` (jamais une conclusion silencieuse) ;
4. 100 % des contradictions injectées dans les cas de test sont détectées et mentionnées dans la justification.

---

## 4. Connaissances : base de règles formalisée

La base de connaissances symbolique (implémentée dans `src/moteur_regles.py`, rôle 2) est ici formalisée indépendamment du code, sous forme logique `SI ... ALORS ...`, pour documenter le raisonnement de manière lisible et vérifiable par un tiers.

| Règle | Priorité | Condition (SI) | Conclusion (ALORS) | Confiance clinique |
|---|---|---|---|---|
| R1 | 100 | `perte_conscience = oui` | `ORIENTATION_URGENTE` | très élevée |
| R5 | 95 | `saignement_important = oui` | `ORIENTATION_URGENTE` | très élevée |
| R2 | 90 | `douleur_thoracique = oui` ET `difficulte_respiratoire = oui` | `ORIENTATION_URGENTE` | très élevée |
| R3 | 50 | `temperature = elevee` ET `duree_symptomes = longue` | `CONSULTATION_PRIORITAIRE` | moyenne |
| R4 | 10 | `douleur = faible` ET `temperature = normale` ET aucun signe critique à `oui` | `SURVEILLANCE` | faible (prudente) |

Les règles sont évaluées dans l'ordre décroissant de priorité ; la première règle qui se déclenche est retenue (principe « la règle la plus critique gagne »). Ce choix formalise directement le principe de sécurité du §3.2 : les règles à très haute priorité (R1, R5, R2) correspondent toutes à des signes dont l'oubli aurait le coût d'erreur le plus élevé.

### 4.1 Gestion de l'incomplétude

Une variable dite critique (§2.2) laissée à `"inconnu"` **n'empêche pas** l'évaluation des règles (une règle non concernée par cette variable peut toujours se déclencher), mais elle empêche le système de conclure `CONSULTATION_NORMALE` par défaut : si aucune règle ne se déclenche et qu'au moins une variable critique est inconnue, la décision devient `DEMANDER_PRECISIONS` avec une confiance qualifiée de faible (cf. C2).

### 4.2 Gestion des contradictions

Trois contradictions sont formalisées explicitement (module `detecter_contradictions`) :

1. `symptomes_legers = oui` **et** `perte_conscience = oui` ;
2. `symptomes_legers = oui` **et** `saignement_important = oui` ;
3. `douleur = faible` **et** `douleur_thoracique = oui`.

Ces contradictions modélisent le cas réel d'un patient qui minimise ses symptômes alors qu'un signe objectif contredit cette minimisation. Le principe de résolution retenu (cf. C3, détaillé au rôle 4) est : une règle critique déclenchée reste appliquée malgré la contradiction, mais celle-ci est toujours signalée dans la justification ; en l'absence de règle critique, la contradiction bloque la conclusion automatique (`SURVEILLANCE_MANUELLE_REQUISE`).

---

## 5. Articulation avec la méthode 2 (probabiliste)

Le moteur à règles seul (méthode 1) est volontairement incomplet : certains cas ne déclenchent aucune règle tout en ayant des informations complètes (par exemple une fatigue importante isolée). Ces cas sont identifiés dans la justification par la mention *« nécessite le modèle probabiliste »* et transmis à la méthode 2 (réseau bayésien naïf / score de risque, rôle 3), dont la sortie est ensuite combinée à celle du moteur à règles par la table de fusion définie au rôle 4 (`src/integration_hybride.py`).

Cette articulation répond directement à l'exigence du sujet d'implémenter *« au moins deux approches complémentaires »* : le rôle 1 formalise ici *pourquoi* elles sont complémentaires (les règles couvrent les cas certains à fort enjeu, le probabiliste couvre les cas ambigus) plutôt que redondantes.

---

## 6. Traçabilité formalisation ↔ code

| Concept formalisé (rôle 1) | Implémentation (rôle 2 / rôle 3 / rôle 4) |
|---|---|
| Variables et domaines (§2.2) | `CHAMPS_ATTENDUS` dans `src/moteur_regles.py` |
| Variables critiques (§2.2) | `CHAMPS_CRITIQUES` dans `src/moteur_regles.py` |
| Règles R1–R5 (§4) | classe `Regle` et liste `REGLES` dans `src/moteur_regles.py` |
| Contradictions (§4.2) | `detecter_contradictions()` dans `src/moteur_regles.py` |
| Décision `DEMANDER_PRECISIONS` (§4.1) | branche `elif manquants` de `evaluer_cas()` |
| Méthode 2 (§5) | `src/moteur_probabiliste.py` |
| Fusion des deux méthodes (§5) | `src/integration_hybride.py` |
| Critère d'acceptation (§3.3) | jeu de cas `data/cas_test.json`, script d'évaluation |
