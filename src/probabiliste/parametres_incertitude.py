"""Paramètres publics de compatibilité du modèle probabiliste.

Les coefficients réellement utilisés sont appris dans ``moteur_probabiliste``;
ce module conserve uniquement l'ancien contrat d'import du prototype.
"""

# Ancienne table conservée pour compatibilité avec les anciens notebooks.
# Le moteur actuel n'utilise pas ces poids écrits à la main.
POIDS_SYMPTOMES: dict[str, float] = {}

# A priori clinique : en premier accueil, la majorité des situations ne sont pas des urgences vitales
BIAIS_A_PRIORI: float = -0.6

# Seuils de décision sur la probabilité d'urgence P(urgence)
SEUILS_DECISION: dict[str, float] = {
    "urgent": 0.75,
    "prioritaire": 0.50,
    "normale": 0.30,
}
