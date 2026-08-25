#!/usr/bin/env python3
"""
Méthode 2 : raisonnement probabiliste (rôle 3 - scaffold)

Ce module est la méthode 2 complémentaire du moteur à règles (méthode 1).
Il est volontairement simple et explicite : un modèle linéaire de score de
risque transformé en probabilité par une sigmoïde, chaque symptôme pesant
selon un poids documenté. Le but n'est pas la performance prédictive mais la
TRANSPARENCE : on peut expliquer, pour chaque cas, quels symptômes ont fait
monter la probabilité et de combien.

NOTE DE RÔLE : ce fichier est une implémentation minimale fonctionnelle
destinée à être reprise/affinée par le rôle 3 (incertitude/apprentissage).
Il est calibré pour couvrir les cas que le moteur à règles ne tranche pas
(cf. docs/formalisation_connaissances.md §5). Les poids ci-dessous sont des
choix pédagogiques, facilement remplaçables par des poids appris.

Usage autonome :
    python src/moteur_probabiliste.py --data data/cas_test.json
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Réutilise la représentation des faits du moteur à règles (rôle 1/2) pour
# garantir que les deux méthodes parlent exactement des mêmes variables.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from moteur_regles import nouveau_cas, CHAMPS_ATTENDUS  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Poids des symptômes (base de connaissances probabiliste)
# ---------------------------------------------------------------------------

# Poids positif = augmente la probabilité d'une orientation urgente.
# Poids négatif = signe rassurant qui la diminue.
POIDS = {
    "perte_conscience": 3.0,
    "saignement_important": 3.0,
    "douleur_thoracique": 2.5,
    "difficulte_respiratoire": 2.5,
    "temperature_elevee": 0.6,      # temperature == "elevee"
    "duree_longue": 0.4,           # duree_symptomes == "longue"
    "fatigue_importante": 1.2,
    "douleur_fort": 1.0,            # douleur == "fort"
    "douleur_moyen": 0.6,           # douleur == "moyen"
    "douleur_faible": -0.3,         # douleur == "faible"
    "temperature_normale": -0.5,   # temperature == "normale"
}

BIAS = -0.6  # a priori : la plupart des cas ne sont pas urgents


# ---------------------------------------------------------------------------
# 2. Structures de résultat
# ---------------------------------------------------------------------------

@dataclass
class Contribution:
    symptome: str
    poids: float
    active: bool


@dataclass
class ResultatProbabiliste:
    score: float
    probabilite_urgence: float
    orientation: str
    contributions: list[Contribution] = field(default_factory=list)
    justification: str = ""


# ---------------------------------------------------------------------------
# 3. Calcul du score et de la probabilité
# ---------------------------------------------------------------------------

def calculer_contributions(faits: dict) -> list[Contribution]:
    """Active les poids correspondant à l'état de chaque fait du patient."""
    contribs: list[Contribution] = []

    def add(cle_symptome, cle_poids):
        contribs.append(Contribution(
            symptome=cle_symptome, poids=POIDS[cle_poids],
            active=faits.get(cle_symptome) == "oui",
        ))

    add("perte_conscience", "perte_conscience")
    add("saignement_important", "saignement_important")
    add("douleur_thoracique", "douleur_thoracique")
    add("difficulte_respiratoire", "difficulte_respiratoire")
    add("fatigue_importante", "fatigue_importante")

    # Variables à domaines > 2 états : on active le poids du niveau observé.
    if faits.get("temperature") == "elevee":
        contribs.append(Contribution("temperature_elevee", POIDS["temperature_elevee"], True))
    elif faits.get("temperature") == "normale":
        contribs.append(Contribution("temperature_normale", POIDS["temperature_normale"], True))
    else:
        contribs.append(Contribution("temperature_elevee", POIDS["temperature_elevee"], False))
        contribs.append(Contribution("temperature_normale", POIDS["temperature_normale"], False))

    if faits.get("duree_symptomes") == "longue":
        contribs.append(Contribution("duree_longue", POIDS["duree_longue"], True))
    else:
        contribs.append(Contribution("duree_longue", POIDS["duree_longue"], False))

    niveau = faits.get("douleur")
    for niveau_douleur, cle in [("fort", "douleur_fort"), ("moyen", "douleur_moyen"), ("faible", "douleur_faible")]:
        contribs.append(Contribution(cle, POIDS[cle], niveau == niveau_douleur))

    return contribs


def sigmoide(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# Seuils de décision (P(urgence)) -> orientation. Calibrés pour que les cas
# ambigus (C10 : fatigue + douleur moyenne) tombent en CONSULTATION_PRIORITAIRE.
SEUIL_URGENT = 0.75
SEUIL_PRIORITAIRE = 0.50
SEUIL_NORMALE = 0.30


def evaluer_probabiliste(faits_bruts: dict) -> ResultatProbabiliste:
    faits = nouveau_cas(**faits_bruts)
    contribs = calculer_contributions(faits)

    score = BIAS
    for c in contribs:
        if c.active:
            score += c.poids

    proba = sigmoide(score)

    if proba >= SEUIL_URGENT:
        orientation = "ORIENTATION_URGENTE"
    elif proba >= SEUIL_PRIORITAIRE:
        orientation = "CONSULTATION_PRIORITAIRE"
    elif proba >= SEUIL_NORMALE:
        orientation = "CONSULTATION_NORMALE"
    else:
        orientation = "SURVEILLANCE"

    actives = [c for c in contribs if c.active]
    detail = ", ".join(f"{c.symptome} ({c.poids:+.1f})" for c in actives) or "aucun signe actif"
    justification = (
        f"Score de risque = {score:+.2f} (biais {BIAS:+.1f} + contributions : {detail}). "
        f"P(urgence) = {proba:.2f}. Décision probabiliste : {orientation} "
        f"(seuils : urgent≥{SEUIL_URGENT}, prioritaire≥{SEUIL_PRIORITAIRE}, "
        f"normale≥{SEUIL_NORMALE})."
    )

    return ResultatProbabiliste(
        score=score,
        probabilite_urgence=proba,
        orientation=orientation,
        contributions=contribs,
        justification=justification,
    )


# ---------------------------------------------------------------------------
# 4. Exécution autonome (démonstration / rôle 3)
# ---------------------------------------------------------------------------

def charger_cas_test(chemin: Path):
    if chemin.exists():
        with open(chemin, encoding="utf-8") as f:
            brut = json.load(f)
        return [(c["nom"], c["faits"], c.get("decision_attendue")) for c in brut]
    print(f"[avertissement] {chemin} introuvable.")
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Méthode 2 - raisonnement probabiliste (score de risque sigmoïde)"
    )
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "cas_test.json")
    args = parser.parse_args()

    cas = charger_cas_test(args.data)
    print("MÉTHODE 2 — Raisonnement probabiliste")
    print(f"Cas chargés depuis : {args.data}\n")

    total = len(cas)
    ok = 0
    t0 = 0.0
    for nom, faits, attendu in cas:
        debut = time.perf_counter()
        res = evaluer_probabiliste(faits)
        t0 += time.perf_counter() - debut
        match = ""
        if attendu is not None:
            m = attendu.split(" ")[0] in res.orientation
            ok += int(m)
            match = "OK" if m else "à comparer"
        print(f"- {nom}")
        print(f"    P(urgence)={res.probabilite_urgence:.2f}  -> {res.orientation}  [{match}]")
        print(f"    {res.justification}")

    print(f"\nBilan méthode 2 : {ok}/{total} concordent avec l'attendu, temps total {t0*1000:.3f} ms")


if __name__ == "__main__":
    main()
