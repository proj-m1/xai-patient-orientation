#!/usr/bin/env python3
"""Rôle 4 : Intégration hybride et comparaison Config A vs Config B."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.probabiliste.moteur_probabiliste import evaluer_probabiliste
from src.symbolique.moteur_regles import (
    charger_cas_test,
    detecter_contradictions,
    evaluer_cas,
)


# --- 1. Structure de données de la décision hybride ---

@dataclass
class DecisionHybride:
    """Décision finale consolidée avec traçabilité complète des deux méthodes."""
    orientation: str
    confiance: str
    source: str
    justification: str
    probabilite_urgence: Optional[float] = None
    regle_id: Optional[str] = None
    detail_regles: str = ""
    detail_probabiliste: str = ""
    contradictions: list[str] = field(default_factory=list)
    infos_manquantes: list[str] = field(default_factory=list)


# --- 2. Table de fusion déterministe (Priorité à la Sécurité Clinique) ---

def fusionner(faits: dict[str, Any]) -> DecisionHybride:
    """Combine la méthode symbolique et la méthode probabiliste selon la table de fusion."""
    exp_regles = evaluer_cas(faits)
    res_proba = evaluer_probabiliste(faits)

    contradictions = detecter_contradictions(faits)
    manquants = exp_regles.infos_manquantes
    regle = exp_regles.regle_activee
    p_urg = res_proba.probabilite_urgence

    # Règle 1 : Contradiction sans règle critique -> Arbitrage manuel obligatoire
    if contradictions and (regle is None or not regle.critique):
        return DecisionHybride(
            orientation="SURVEILLANCE_MANUELLE_REQUISE",
            confiance="Faible (contradiction)",
            source="fusion",
            justification=f"Contradiction détectée ({'; '.join(contradictions)}). Vérification humaine requise.",
            probabilite_urgence=p_urg,
            contradictions=contradictions,
            detail_regles=exp_regles.justification,
            detail_probabiliste=res_proba.justification,
        )

    # Règle 2 : Règle critique déclenchée (R1, R2, R5) -> ORIENTATION_URGENTE absolue
    if regle is not None and regle.critique:
        return DecisionHybride(
            orientation=regle.orientation,
            confiance="Très élevée (règle critique)",
            source="regles",
            justification=f"Règle critique {regle.id} active ({regle.description}). Priorité absolue de sécurité.",
            probabilite_urgence=p_urg,
            regle_id=regle.id,
            contradictions=contradictions,
            detail_regles=exp_regles.justification,
            detail_probabiliste=res_proba.justification,
        )

    # Règle 3 : Données critiques manquantes sans règle -> Refus de deviner
    if manquants:
        return DecisionHybride(
            orientation="DEMANDER_PRECISIONS",
            confiance="Faible (données manquantes)",
            source="fusion",
            justification=f"Variables critiques manquantes : {', '.join(manquants)}. Complément d'information requis.",
            probabilite_urgence=p_urg,
            infos_manquantes=manquants,
            detail_regles=exp_regles.justification,
            detail_probabiliste=res_proba.justification,
        )

    # Règle 4 : Règle prioritaire (R3) -> Rehaussement en urgence si P(urgence) >= 0.90
    if regle is not None and regle.id == "R3":
        if p_urg >= 0.90:
            return DecisionHybride(
                orientation="ORIENTATION_URGENTE",
                confiance="Élevée (rehaussement)",
                source="fusion",
                justification=f"Règle {regle.id} déclenchée, rehaussée en ORIENTATION_URGENTE car P(urgence)={p_urg:.2f} >= 0.90.",
                probabilite_urgence=p_urg,
                regle_id=regle.id,
                detail_regles=exp_regles.justification,
                detail_probabiliste=res_proba.justification,
            )
        return DecisionHybride(
            orientation=regle.orientation,
            confiance=regle.confiance,
            source="regles",
            justification=f"Règle {regle.id} active ({regle.description}), P(urgence)={p_urg:.2f}.",
            probabilite_urgence=p_urg,
            regle_id=regle.id,
            detail_regles=exp_regles.justification,
            detail_probabiliste=res_proba.justification,
        )

    # Règle 5 : Règle de surveillance (R4) confirmée
    if regle is not None and regle.id == "R4":
        return DecisionHybride(
            orientation=regle.orientation,
            confiance="Moyenne",
            source="regles",
            justification=f"Règle de surveillance {regle.id} déclenchée (tableau bénin, P(urgence)={p_urg:.2f}).",
            probabilite_urgence=p_urg,
            regle_id=regle.id,
            detail_regles=exp_regles.justification,
            detail_probabiliste=res_proba.justification,
        )

    # Règle 6 : Aucune règle décisive -> Décision graduée par le modèle probabiliste
    return DecisionHybride(
        orientation=res_proba.orientation,
        confiance="Moyenne (probabiliste)",
        source="probabiliste",
        justification=f"Aucune règle symbolique applicable. Décision probabiliste : P(urgence)={p_urg:.2f} -> {res_proba.orientation}.",
        probabilite_urgence=p_urg,
        detail_regles=exp_regles.justification,
        detail_probabiliste=res_proba.justification,
    )


# --- 3. Comparaison Config A vs Config B (CLI) ---

def comparer(chemin_cas: Path) -> None:
    """Exécute et compare les deux configurations sur le jeu de test de référence."""
    cas_liste = charger_cas_test(chemin_cas)

    print("=" * 82)
    print("COMPARAISON DES DEUX CONFIGURATIONS D'ORIENTATION")
    print("Config A : Règles seules (Méthode 1)")
    print("Config B : Intégration hybride (Méthode 1 + Méthode 2)")
    print("=" * 82)
    print(f"{'Cas':<38} | {'Attendu':<22} | {'Config A':<16} | {'Config B'}")
    print("-" * 82)

    reussites_a = 0
    reussites_b = 0
    t_a_total = 0.0
    t_b_total = 0.0

    for nom, faits, attendu in cas_liste:
        t0 = time.perf_counter()
        exp_a = evaluer_cas(faits)
        t_a_total += time.perf_counter() - t0

        t0 = time.perf_counter()
        dec_b = fusionner(faits)
        t_b_total += time.perf_counter() - t0

        bon_a = bool(attendu and attendu == exp_a.orientation)
        bon_b = bool(attendu and attendu == dec_b.orientation)

        if bon_a:
            reussites_a += 1
        if bon_b:
            reussites_b += 1

        nom_court = nom[:36]
        att_court = (attendu or "N/A")[:20]
        res_a = f"{'OK' if bon_a else 'ÉCART':<5} ({exp_a.orientation[:8]})"
        res_b = f"{'OK' if bon_b else 'ÉCART':<5} ({dec_b.orientation[:8]})"
        print(f"{nom_court:<38} | {att_court:<22} | {res_a:<16} | {res_b}")

    n = len(cas_liste)
    print("=" * 82)
    print(f"Exactitude Config A (Règles seules) : {reussites_a}/{n} ({100*reussites_a/n:.1f}%) — {t_a_total*1000/n:.4f} ms/cas")
    print(f"Exactitude Config B (Hybridation)   : {reussites_b}/{n} ({100*reussites_b/n:.1f}%) — {t_b_total*1000/n:.4f} ms/cas")
    print("=" * 82)


def main() -> None:
    parser = argparse.ArgumentParser(description="Intégration hybride & Comparaison A vs B")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "cas_test.json",
        help="Chemin vers le fichier de cas de test JSON",
    )
    args = parser.parse_args()
    comparer(args.data)


if __name__ == "__main__":
    main()
