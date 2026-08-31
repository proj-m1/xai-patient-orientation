"""Module symbolique (Rôles 1 & 2).

Contient l'ontologie des variables et le moteur d'inférence à base de règles.
"""

from src.symbolique.connaissances import (
    CHAMPS_ATTENDUS,
    CHAMPS_CRITIQUES,
    DOMAINES,
    ONTOLOGIE,
    REGLES,
    Regle,
)
from src.symbolique.moteur_regles import (
    Explication,
    TraceRegle,
    champs_manquants,
    charger_cas_test,
    detecter_contradictions,
    evaluer_cas,
    nouveau_cas,
    valider_faits,
)

__all__ = [
    "CHAMPS_ATTENDUS",
    "CHAMPS_CRITIQUES",
    "DOMAINES",
    "ONTOLOGIE",
    "REGLES",
    "Regle",
    "Explication",
    "TraceRegle",
    "champs_manquants",
    "charger_cas_test",
    "detecter_contradictions",
    "evaluer_cas",
    "nouveau_cas",
    "valider_faits",
]
