#!/usr/bin/env python3
"""Modèle probabiliste interprétable appris sur des cas structurés."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.symbolique.moteur_regles import charger_cas_test, nouveau_cas, valider_faits


ORIENTATIONS_MODELE = [
    "SURVEILLANCE",
    "CONSULTATION_NORMALE",
    "CONSULTATION_PRIORITAIRE",
    "ORIENTATION_URGENTE",
]

NOMS_FEATURES = [
    "perte_conscience",
    "saignement_important",
    "douleur_thoracique",
    "difficulte_respiratoire",
    "temperature_elevee",
    "duree_longue",
    "fatigue_importante",
    "douleur_fort",
    "douleur_moyen",
    "douleur_faible",
    "age_fragile",
    "age_adulte",
]


def sigmoide(x: float) -> float:
    """Conserve l'ancienne API pour les tests mathématiques du projet."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def vectoriser(faits_bruts: dict[str, Any]) -> list[float]:
    """Convertit les observations en variables explicables, sans imputer un oui."""
    faits = nouveau_cas(**faits_bruts)
    age = faits.get("age")
    return [
        float(faits.get("perte_conscience") == "oui"),
        float(faits.get("saignement_important") == "oui"),
        float(faits.get("douleur_thoracique") == "oui"),
        float(faits.get("difficulte_respiratoire") == "oui"),
        float(faits.get("temperature") == "elevee"),
        float(faits.get("duree_symptomes") == "longue"),
        float(faits.get("fatigue_importante") == "oui"),
        float(faits.get("douleur") == "fort"),
        float(faits.get("douleur") == "moyen"),
        float(faits.get("douleur") == "faible"),
        float(isinstance(age, int) and (age < 5 or age >= 75)),
        float(isinstance(age, int) and 5 <= age < 75),
    ]


class ModeleSoftmax:
    """Régression softmax multiclasses apprise par descente de gradient."""

    def __init__(self) -> None:
        self.poids = [[0.0] * len(NOMS_FEATURES) for _ in ORIENTATIONS_MODELE]
        self.biais = [0.0] * len(ORIENTATIONS_MODELE)
        self.epochs = 0

    def _probabilites(self, x: list[float]) -> list[float]:
        logits = [b + sum(w * v for w, v in zip(p, x)) for p, b in zip(self.poids, self.biais)]
        maximum = max(logits)
        exp = [math.exp(logit - maximum) for logit in logits]
        total = sum(exp)
        return [valeur / total for valeur in exp]

    def fit(self, observations: list[dict[str, Any]], epochs: int = 1800) -> None:
        """Apprend les coefficients sur le jeu JSON, sans dépendance externe."""
        donnees = []
        for observation in observations:
            cible = observation.get("orientation")
            if cible not in ORIENTATIONS_MODELE:
                continue
            donnees.append((vectoriser(observation.get("faits", {})), ORIENTATIONS_MODELE.index(cible)))
        if not donnees:
            raise ValueError("Jeu d'apprentissage vide ou sans orientations valides.")

        n = len(donnees)
        taux = 0.12
        regularisation = 0.006
        for _ in range(epochs):
            gradients_w = [[0.0] * len(NOMS_FEATURES) for _ in ORIENTATIONS_MODELE]
            gradients_b = [0.0] * len(ORIENTATIONS_MODELE)
            for x, cible in donnees:
                probabilites = self._probabilites(x)
                for classe in range(len(ORIENTATIONS_MODELE)):
                    erreur = probabilites[classe] - float(classe == cible)
                    gradients_b[classe] += erreur
                    for index, valeur in enumerate(x):
                        gradients_w[classe][index] += erreur * valeur
            for classe in range(len(ORIENTATIONS_MODELE)):
                self.biais[classe] -= taux * gradients_b[classe] / n
                for index in range(len(NOMS_FEATURES)):
                    gradient = gradients_w[classe][index] / n + regularisation * self.poids[classe][index]
                    self.poids[classe][index] -= taux * gradient
        self.epochs = epochs

    def predire(self, faits: dict[str, Any]) -> tuple[str, float, dict[str, float], float]:
        x = vectoriser(faits)
        probabilites = self._probabilites(x)
        index = max(range(len(probabilites)), key=probabilites.__getitem__)
        score_urgent = self.biais[-1] + sum(w * v for w, v in zip(self.poids[-1], x))
        return (
            ORIENTATIONS_MODELE[index],
            probabilites[-1],
            dict(zip(ORIENTATIONS_MODELE, probabilites)),
            score_urgent,
        )


def _charger_modele() -> ModeleSoftmax:
    chemin = ROOT_DIR / "data" / "cas_entrainement.json"
    with open(chemin, encoding="utf-8") as fichier:
        observations = json.load(fichier)
    modele = ModeleSoftmax()
    modele.fit(observations)
    return modele


MODELE = _charger_modele()


@dataclass
class Contribution:
    """Contribution d'une variable active au logit de la classe urgente."""
    symptome: str
    poids: float
    active: bool


@dataclass
class ResultatProbabiliste:
    """Résultat probabiliste avec distribution complète et explication locale."""
    score: float
    probabilite_urgence: float
    orientation: str
    contributions: list[Contribution] = field(default_factory=list)
    probabilites_par_orientation: dict[str, float] = field(default_factory=dict)
    justification: str = ""


def calculer_contributions(faits: dict[str, Any]) -> list[Contribution]:
    """Expose les coefficients appris qui sont activés pour le cas courant."""
    x = vectoriser(faits)
    return [
        Contribution(nom, MODELE.poids[-1][index], bool(valeur))
        for index, (nom, valeur) in enumerate(zip(NOMS_FEATURES, x))
    ]


def evaluer_probabiliste(faits_bruts: dict[str, Any]) -> ResultatProbabiliste:
    """Évalue une distribution de risque apprise; les règles de sécurité restent prioritaires."""
    faits = valider_faits(faits_bruts)
    orientation, probabilite, distribution, score = MODELE.predire(faits)
    contributions = calculer_contributions(faits)
    actives = [c for c in contributions if c.active]
    detail = ", ".join(f"{c.symptome} ({c.poids:+.2f})" for c in actives) or "aucun facteur observé"
    distribution_lisible = ", ".join(f"{nom}={valeur:.2f}" for nom, valeur in distribution.items())
    justification = (
        f"Modèle softmax appris ({MODELE.epochs} itérations), score urgent={score:+.2f}; "
        f"facteurs actifs : {detail}. Distribution : {distribution_lisible}."
    )
    return ResultatProbabiliste(
        score=score,
        probabilite_urgence=probabilite,
        orientation=orientation,
        contributions=contributions,
        probabilites_par_orientation=distribution,
        justification=justification,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Méthode 2 - Modèle probabiliste interprétable")
    parser.add_argument("--data", type=Path, default=ROOT_DIR / "data" / "cas_test.json")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    with open(args.data, encoding="utf-8") as fichier:
        cas_liste = json.load(fichier)
    conformes = 0
    for cas in cas_liste:
        resultat = evaluer_probabiliste(cas["faits"])
        attendu = cas.get("decision_attendue")
        ok = attendu == resultat.orientation
        conformes += int(ok)
        if not args.quiet:
            print(f"{cas['nom']} -> {resultat.orientation} ({resultat.probabilite_urgence:.2f}) {'OK' if ok else 'ÉCART'}")
    print(f"Bilan modèle probabiliste : {conformes}/{len(cas_liste)}")


if __name__ == "__main__":
    main()
