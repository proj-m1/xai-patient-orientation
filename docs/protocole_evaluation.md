# Protocole d'évaluation

## 1. Jeux de données

- `data/cas_test.json` : 11 cas externes au code, utilisés pour la démonstration et la comparaison A/B.
- `data/cas_entrainement.json` : 22 cas synthétiques utilisés pour apprendre le modèle softmax.

Les cas d'entraînement et de test sont séparés. Les données sont pédagogiques : elles ne sont ni des dossiers médicaux ni une validation clinique.

## 2. Configurations comparées

- **A — règles seules** : moteur symbolique avec priorité et abstention sur information critique manquante.
- **B — hybride** : règles, modèle probabiliste et fusion orientée sécurité.

La fusion ne permet jamais au modèle de déclasser une règle critique. Elle expose la distribution des quatre orientations, les contributions apprises et les contradictions. Gemini est évalué séparément comme extracteur de faits ; il ne participe pas directement à la décision.

## 3. Métriques

Le endpoint `/api/benchmark` et `src/evaluation.py` produisent :

- exactitude globale et par configuration ;
- sensibilité aux urgences ;
- nombre de faux négatifs urgents ;
- matrice de confusion ;
- temps moyen d'inférence.

Pour une évaluation plus sérieuse, il faudra aussi ajouter Brier score, calibration des probabilités, taux d'abstention, couverture des règles et temps p50/p95.

## 4. Résultat du jeu actuel

Sur les 11 scénarios actuels, l'exécution observée donne :

| Métrique | A : règles | B : hybride |
|---|---:|---:|
| Exactitude | 90,9 % (10/11) | 100,0 % (11/11) |
| Sensibilité urgente | 100,0 % | 100,0 % |
| Faux négatifs urgents | 0 | 0 |

C10 illustre un cas où le moteur de règles ne couvre pas le profil, alors que le modèle apporte une orientation prioritaire. C11 vérifie qu'une règle critique reste prioritaire même si la distribution probabiliste est défavorable. C9 vérifie l'arbitrage contradiction + urgence.

## 5. Limites et recommandations

Les 11 scénarios ne permettent pas d'estimer une performance clinique. Il faut augmenter la diversité des profils, documenter la provenance des annotations, utiliser plusieurs annotateurs et conserver un jeu de test caché. Toute utilisation réelle nécessiterait une validation médicale, une gouvernance des données et un dispositif de supervision humaine.

## 6. Commandes

```bash
uv run pytest -q
uv run python src/hybride/integration_hybride.py
uv run python -c "from src.app import app; print(app.test_client().get('/api/benchmark').get_json()['synthese'])"
```
