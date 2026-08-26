# Système Explicable d'Orientation des Patients

Mini-projet M1 SDIA — Raisonnement en Intelligence Artificielle (2026).

Système d'aide à la décision pour le premier accueil médical (régulation / urgences). Le système ne pose aucun diagnostic : il classe une situation clinique observée dans une catégorie d'orientation formalisée avec traçabilité complète du raisonnement.

---

## 1. Exigences

- **Cadrage formel :** 10 variables cliniques, logique ternaire (`"oui"`, `"non"`, `"inconnu"`), asymétrie des coûts d'erreur (0 faux négatif urgent toléré) et critères d'acceptation stricts.
- **Deux approches complémentaires & Hybridation :**
  - *Méthode 1 (Symbolique) :* Moteur déterministe à base de règles ordonnées par priorités (`data/regles.json`).
  - *Méthode 2 (Probabiliste) :* Régression Softmax multiclasses apprise par descente de gradient sur 22 cas structurés (`data/cas_entrainement.json`).
  - *Fusion de sécurité :* Une règle d'alerte vitale est prioritaire sur toute estimation probabiliste.
  - *Approche 3 (LLM optionnel) :* Extraction de faits depuis du texte libre vers un schéma JSON validé, sans délégation de décision.
- **Traitement des imperfections :**
  - *Incomplétude :* Refus de statuer (`DEMANDER_PRECISIONS`) si une variable critique est inconnue sans règle urgente.
  - *Contradictions :* Détection et arbitrage de sécurité (`SURVEILLANCE_MANUELLE_REQUISE` ou maintien de l'urgence si signe vital).
  - *Incertitude :* Distribution des probabilités et justification causale pas à pas.
- **Comparaison & Évaluation :** Comparaison de la Configuration A (Règles seules) et de la Configuration B (Hybridation) sur 11 cas de test dont 3 cas limites (C9, C10, C11).

---

## 2. Organisation en 5 Rôles

| Rôle                      | Périmètre                                                              | Modules du projet                                                       |
| -------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| **1. Formalisation** | Cadrage, ontologie des 10 variables, asymétrie des coûts               | `data/ontologie.json`, `docs/formalisation_connaissances.md`        |
| **2. Symbolique**    | Moteur déterministe à chaînage avant, priorités, contradictions      | `src/symbolique/`, `data/regles.json`                               |
| **3. Incertitude**   | Régression Softmax multiclasses, descente de gradient, contributions    | `src/probabiliste/`, `data/cas_entrainement.json`                   |
| **4. Intégration**  | Table de fusion de sécurité, API REST Flask, interface 2 colonnes, LLM | `src/hybride/`, `src/llm/`, `src/app.py`, `static/`             |
| **5. Évaluation**   | Jeux de test (dont C9-C11), métriques, benchmark et suite de tests      | `data/cas_test.json`, `src/evaluation.py`, `tests/test_triage.py` |

---

## 3. Installation

Le projet utilise **`uv`** pour la gestion déterministe des dépendances et de l'environnement virtuel.

```bash
# 1. Synchroniser l'environnement virtuel
uv sync

# 2. Lancer la suite de 21 tests automatisés
uv run pytest -q

# 3. Exécuter le moteur symbolique seul (Méthode 1)
uv run python src/symbolique/moteur_regles.py

# 4. Exécuter le modèle probabiliste seul (Méthode 2)
uv run python src/probabiliste/moteur_probabiliste.py

# 5. Lancer la comparaison hybride (Config A vs Config B)
uv run python src/hybride/integration_hybride.py

# 6. Lancer l'interface web locale
uv run python src/app.py
```

L'interface web est alors accessible sur `http://127.0.0.1:5000`.

---

## 4. Synthèse des Résultats (Benchmark 11 Cas)

| Métrique d'évaluation                 | Configuration A (Règles seules) | Configuration B (Hybride A+B) |      Objectif      |
| :-------------------------------------- | :------------------------------: | :---------------------------: | :-----------------: |
| **Exactitude globale**            |    **90,9 %** (10 / 11)    |  **100,0 %** (11 / 11)  |  $\ge 90,0\ \%$  |
| **Sensibilité urgences vitales** |    **100,0 %** (5 / 5)    |   **100,0 %** (5 / 5)   |  **100,0 %**  |
| **Faux négatifs urgents**        |           **0**           |          **0**          | **0 strict** |
| **Faux positifs urgents**         |                0                |               0               |       Minimum       |
| **Temps moyen par cas**           |        **0,011 ms**        |      **0,032 ms**      | $< 1,0\text{ ms}$ |

- **Cas limite C9 (Contradiction) :** Préservation de l'urgence vitale malgré la déclaration contradictoire de symptômes bénins.
- **Cas limite C10 (Gain de l'hybridation) :** Patient âgé et fatigué non couvert par les règles, correctement orienté en prioritaire par le modèle Softmax ($P = 64,2\ \%$).
- **Cas limite C11 (Conflit de modèles) :** Maintien absolu de l'urgence par la règle critique face à un score probabiliste modéré.
