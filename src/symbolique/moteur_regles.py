#!/usr/bin/env python3
"""Méthode 1 : Moteur d'inférence symbolique à base de règles (Rôle 2)."""

import argparse
import json
import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.symbolique.connaissances import (
    CHAMPS_ATTENDUS,
    CHAMPS_CRITIQUES,
    REGLES,
    Regle,
    DOMAINES,
)


def nouveau_cas(**kwargs: Any) -> dict[str, Any]:
    """Crée un cas avec 'inconnu' par défaut pour chaque variable."""
    cas = {champ: "inconnu" for champ in CHAMPS_ATTENDUS}
    for champ, valeur in kwargs.items():
        if champ in CHAMPS_ATTENDUS:
            cas[champ] = valeur
    return cas


def valider_faits(faits_bruts: dict[str, Any]) -> dict[str, Any]:
    """Valide les domaines de l'ontologie et refuse les champs inconnus."""
    if not isinstance(faits_bruts, dict):
        raise ValueError("Le champ 'faits' doit être un objet JSON.")
    inconnus = sorted(set(faits_bruts) - set(CHAMPS_ATTENDUS))
    if inconnus:
        raise ValueError(f"Champs inconnus : {', '.join(inconnus)}.")

    faits = nouveau_cas(**faits_bruts)
    for champ, valeur in faits.items():
        if champ == "age" and valeur != "inconnu":
            if not isinstance(valeur, int) or isinstance(valeur, bool) or not 0 <= valeur <= 120:
                raise ValueError("Le champ 'age' doit être un entier entre 0 et 120 ou 'inconnu'.")
        elif champ != "age" and valeur not in DOMAINES[champ]:
            valeurs = ", ".join(sorted(str(v) for v in DOMAINES[champ]))
            raise ValueError(f"Valeur invalide pour '{champ}' : {valeur!r}. Valeurs : {valeurs}.")
    return faits


def detecter_contradictions(faits: dict) -> list[str]:
    """Détecte les incohérences évidentes dans les déclarations."""
    erreurs = []
    if faits.get("symptomes_legers") == "oui" and faits.get("perte_conscience") == "oui":
        erreurs.append("symptomes_legers = oui contredit perte_conscience = oui")
    if faits.get("symptomes_legers") == "oui" and faits.get("saignement_important") == "oui":
        erreurs.append("symptomes_legers = oui contredit saignement_important = oui")
    if faits.get("douleur") == "faible" and faits.get("douleur_thoracique") == "oui":
        erreurs.append("douleur = faible contredit douleur_thoracique = oui")
    return erreurs


def champs_manquants(faits: dict[str, Any]) -> list[str]:
    """Retourne les variables critiques non renseignées."""
    return [c for c in CHAMPS_CRITIQUES if faits.get(c) == "inconnu"]


@dataclass
class TraceRegle:
    id: str
    description: str
    resultat: bool


@dataclass
class Explication:
    faits_recus: dict
    regles_evaluees: list[TraceRegle]
    regle_activee: Optional[Regle]
    contradictions: list[str]
    infos_manquantes: list[str]
    orientation: str
    confiance: str
    justification: str


def evaluer_cas(faits_bruts: dict) -> Explication:
    """Évalue un cas patient et produit une orientation justifiée."""
    faits = valider_faits(faits_bruts)

    # 1. Évaluation des règles par ordre de priorité
    traces = []
    regle_activee = None
    for regle in REGLES:
        ok = bool(regle.condition(faits))
        traces.append(TraceRegle(regle.id, regle.description, ok))
        if ok and regle_activee is None:
            regle_activee = regle

    # 2. Analyse des imperfections
    contradictions = detecter_contradictions(faits)
    manquants = champs_manquants(faits)

    # 3. Décision selon la priorité clinique et la sécurité
    regle_critique = regle_activee is not None and regle_activee.critique
    if regle_critique:
        orientation = regle_activee.orientation
        confiance = "Moyenne (contradiction détectée, règle critique appliquée)" if contradictions else "Très élevée"
        justification = (
            (
                f"Contradiction ({'; '.join(contradictions)}). La règle "
                f"{regle_activee.id} ({regle_activee.description}) prime par sécurité."
            )
            if contradictions
            else f"Règle critique {regle_activee.id} déclenchée ({regle_activee.description})."
        )
    elif contradictions:
        orientation = "SURVEILLANCE_MANUELLE_REQUISE"
        confiance = "Faible (contradiction non tranchée)"
        justification = (
            f"Contradiction ({'; '.join(contradictions)}). "
            "Aucune règle critique applicable. Vérification humaine requise."
        )
    elif manquants:
        orientation = "DEMANDER_PRECISIONS"
        confiance = "Faible (informations critiques manquantes)"
        justification = f"Variables critiques manquantes : {', '.join(manquants)}."
    elif regle_activee is not None:
        orientation = regle_activee.orientation
        confiance = "Élevée" if regle_activee.critique else "Moyenne"
        justification = (
            f"Règle {regle_activee.id} déclenchée ({regle_activee.description}), "
            f"confiance {regle_activee.confiance}."
        )
    else:
        orientation = "CONSULTATION_NORMALE"
        confiance = "Faible (aucune règle décisive)"
        justification = (
            "Aucune règle applicable. Informations complètes mais profil non couvert par la base de règles."
        )

    return Explication(
        faits_recus=faits,
        regles_evaluees=traces,
        regle_activee=regle_activee,
        contradictions=contradictions,
        infos_manquantes=manquants,
        orientation=orientation,
        confiance=confiance,
        justification=justification,
    )


def charger_cas_test(chemin: Path) -> list[tuple[str, dict, Optional[str]]]:
    """Charge les cas de test depuis le fichier JSON."""
    with open(chemin, encoding="utf-8") as f:
        cas_liste = json.load(f)
    return [(c["nom"], c["faits"], c.get("decision_attendue")) for c in cas_liste]


def main():
    parser = argparse.ArgumentParser(description="Moteur à règles (Méthode 1)")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "cas_test.json",
    )
    parser.add_argument("--quiet", action="store_true", help="Bilan uniquement")
    args = parser.parse_args()

    cas = charger_cas_test(args.data)
    print("MOTEUR À RÈGLES — Configuration A (Méthode 1)")
    print(f"Fichier de données : {args.data}\n")

    reussites = 0
    t0 = time.perf_counter()

    for nom, faits, attendu in cas:
        exp = evaluer_cas(faits)
        ok = attendu is None or attendu.split(" ")[0] in exp.orientation
        if ok:
            reussites += 1

        if not args.quiet:
            print(f"=== {nom} ===")
            for t in exp.regles_evaluees:
                statut = "DÉCLENCHÉE" if t.resultat else "-"
                print(f"  {t.id} ({t.description}) -> {statut}")
            if exp.contradictions:
                print(f"  Contradictions : {'; '.join(exp.contradictions)}")
            if exp.infos_manquantes:
                print(f"  Manquants : {', '.join(exp.infos_manquantes)}")
            print(f"  Décision : {exp.orientation} [{exp.confiance}]")
            if attendu:
                print(f"  Attendu  : {attendu} -> {'OK' if ok else 'ÉCART'}")
            print()

    duree_ms = (time.perf_counter() - t0) * 1000
    print(f"Bilan : {reussites}/{len(cas)} cas conformes ({duree_ms:.2f} ms)")


if __name__ == "__main__":
    main()
