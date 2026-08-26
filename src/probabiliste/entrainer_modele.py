#!/usr/bin/env python3
"""Entraîne et inspecte le modèle probabiliste sur un fichier JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.probabiliste.moteur_probabiliste import ModeleSoftmax, ORIENTATIONS_MODELE


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraînement reproductible du modèle softmax")
    parser.add_argument("--data", type=Path, default=ROOT_DIR / "data" / "cas_entrainement.json")
    args = parser.parse_args()
    with open(args.data, encoding="utf-8") as fichier:
        observations = json.load(fichier)
    modele = ModeleSoftmax()
    modele.fit(observations)
    conformes = 0
    for observation in observations:
        orientation, _, _, _ = modele.predire(observation.get("faits", {}))
        conformes += int(orientation == observation.get("orientation"))
    print(f"Cas d'entraînement : {len(observations)}")
    print(f"Classes : {', '.join(ORIENTATIONS_MODELE)}")
    print(f"Itérations : {modele.epochs}")
    print(f"Exactitude sur l'entraînement : {100 * conformes / len(observations):.1f}%")
    print("Coefficients de la classe urgente :")
    for nom, poids in zip((
        "perte_conscience", "saignement_important", "douleur_thoracique",
        "difficulte_respiratoire", "temperature_elevee", "duree_longue",
        "fatigue_importante", "douleur_fort", "douleur_moyen", "douleur_faible",
        "age_fragile", "age_adulte",
    ), modele.poids[-1]):
        print(f"  {nom}: {poids:+.3f}")


if __name__ == "__main__":
    main()
