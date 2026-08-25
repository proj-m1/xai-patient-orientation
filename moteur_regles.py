#!/usr/bin/env python3
"""
Système explicable d'orientation des patients
Méthode 1 : moteur à règles (symbolique)

Ce module implémente UNIQUEMENT la première méthode demandée par le sujet
(système à règles). Il est conçu pour être branché plus tard sur la
deuxième méthode (raisonnement probabiliste) via la table de fusion du
sujet, mais fonctionne ici de façon autonome et complète.

Le moteur respecte les exigences du sujet :
  - explique les informations prises en compte
  - explique les règles appliquées (ou non)
  - signale les informations manquantes
  - détecte les contradictions entre faits
  - fournit un niveau de confiance et une justification lisible
"""

import argparse
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# 1. Représentation des cas (faits patient)
# ---------------------------------------------------------------------------

# Valeurs possibles : "oui", "non", "inconnu" pour les booléens cliniques.
# "inconnu" signifie explicitement une information manquante (et non "non").

CHAMPS_ATTENDUS = [
    "age",
    "temperature",          # "normale" | "elevee" | "inconnu"
    "duree_symptomes",      # "courte" | "longue" | "inconnu"
    "douleur",              # "faible" | "moyen" | "fort" | "inconnu"
    "difficulte_respiratoire",
    "douleur_thoracique",
    "perte_conscience",
    "saignement_important",
    "fatigue_importante",
    "symptomes_legers",     # utilisé pour illustrer les contradictions
]

# Champs jugés critiques : s'ils sont inconnus ET qu'aucune règle certaine
# ne s'est déclenchée, le système doit le signaler (exigence du sujet :
# "ne pas conclure avec une confiance élevée si informations manquantes").
CHAMPS_CRITIQUES = [
    "perte_conscience",
    "difficulte_respiratoire",
    "douleur_thoracique",
    "saignement_important",
    "temperature",
    "duree_symptomes",
]


def nouveau_cas(**kwargs) -> dict:
    """Construit un cas patient avec valeurs par défaut = 'inconnu'."""
    cas = {champ: "inconnu" for champ in CHAMPS_ATTENDUS}
    cas.update(kwargs)
    return cas


# ---------------------------------------------------------------------------
# 2. Base de règles explicites
# ---------------------------------------------------------------------------

@dataclass
class Regle:
    id: str
    priorite: int                       # plus grand = plus prioritaire/critique
    condition: Callable[[dict], bool]
    orientation: str
    niveau_priorite_clinique: str        # texte affiché ("très élevée", ...)
    description: str                     # texte humain de la condition


REGLES: list[Regle] = [
    Regle(
        id="R1",
        priorite=100,
        condition=lambda f: f["perte_conscience"] == "oui",
        orientation="ORIENTATION_URGENTE",
        niveau_priorite_clinique="très élevée",
        description="perte_conscience = oui",
    ),
    Regle(
        id="R2",
        priorite=90,
        condition=lambda f: f["douleur_thoracique"] == "oui"
        and f["difficulte_respiratoire"] == "oui",
        orientation="ORIENTATION_URGENTE",
        niveau_priorite_clinique="très élevée",
        description="douleur_thoracique = oui ET difficulte_respiratoire = oui",
    ),
    Regle(
        id="R5",
        priorite=95,
        condition=lambda f: f["saignement_important"] == "oui",
        orientation="ORIENTATION_URGENTE",
        niveau_priorite_clinique="très élevée",
        description="saignement_important = oui",
        # Règle ajoutée pour couvrir le cas de test C7 du sujet, dans le
        # même esprit que R1/R2 (signe critique isolé et décisif).
    ),
    Regle(
        id="R3",
        priorite=50,
        condition=lambda f: f["temperature"] == "elevee"
        and f["duree_symptomes"] == "longue",
        orientation="CONSULTATION_PRIORITAIRE",
        niveau_priorite_clinique="moyenne",
        description="temperature = élevée ET duree_symptomes = longue",
    ),
    Regle(
        id="R4",
        priorite=10,
        condition=lambda f: f["douleur"] == "faible"
        and f["temperature"] == "normale"
        and f["difficulte_respiratoire"] != "oui"
        and f["douleur_thoracique"] != "oui"
        and f["perte_conscience"] != "oui"
        and f["saignement_important"] != "oui",
        orientation="SURVEILLANCE",
        niveau_priorite_clinique="faible",
        description="douleur = faible ET temperature = normale ET aucun signe critique",
    ),
]

REGLES = sorted(REGLES, key=lambda r: -r.priorite)


# ---------------------------------------------------------------------------
# 3. Détection des contradictions
# ---------------------------------------------------------------------------

def detecter_contradictions(faits: dict) -> list[str]:
    """Renvoie une liste de messages décrivant les contradictions trouvées."""
    contradictions = []

    if faits.get("symptomes_legers") == "oui" and faits.get("perte_conscience") == "oui":
        contradictions.append(
            "symptomes_legers = oui contredit perte_conscience = oui "
            "(une perte de conscience n'est pas un symptôme léger)."
        )

    if faits.get("symptomes_legers") == "oui" and faits.get("saignement_important") == "oui":
        contradictions.append(
            "symptomes_legers = oui contredit saignement_important = oui."
        )

    if faits.get("douleur") == "faible" and faits.get("douleur_thoracique") == "oui":
        contradictions.append(
            "douleur = faible contredit douleur_thoracique = oui "
            "(douleur déclarée faible alors qu'une douleur thoracique est signalée)."
        )

    return contradictions


# ---------------------------------------------------------------------------
# 4. Détection des informations manquantes
# ---------------------------------------------------------------------------

def champs_manquants(faits: dict) -> list[str]:
    return [c for c in CHAMPS_CRITIQUES if faits.get(c) == "inconnu"]


# ---------------------------------------------------------------------------
# 5. Moteur d'inférence + trace explicative
# ---------------------------------------------------------------------------

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
    faits = nouveau_cas(**faits_bruts)

    # a) évaluer chaque règle, dans l'ordre de priorité
    traces = []
    regle_activee = None
    for regle in REGLES:
        resultat = bool(regle.condition(faits))
        traces.append(TraceRegle(regle.id, regle.description, resultat))
        if resultat and regle_activee is None:
            regle_activee = regle  # la première règle qui matche = la plus prioritaire

    # b) contradictions et infos manquantes, calculées indépendamment
    contradictions = detecter_contradictions(faits)
    manquants = champs_manquants(faits)

    # c) décision finale du moteur à règles seul
    if contradictions and regle_activee is not None:
        # Exigence du sujet : une règle critique reste prioritaire même en
        # cas de contradiction détectée ; on l'applique mais on signale le
        # conflit explicitement.
        orientation = regle_activee.orientation
        confiance = "moyenne (contradiction détectée, mais règle critique appliquée)"
        justification = (
            f"Contradiction détectée dans les faits ({'; '.join(contradictions)}). "
            f"La règle {regle_activee.id} ({regle_activee.description}) est "
            f"prioritaire ({regle_activee.niveau_priorite_clinique}) et détermine "
            f"la décision finale malgré la contradiction."
        )
    elif contradictions and regle_activee is None:
        orientation = "SURVEILLANCE_MANUELLE_REQUISE"
        confiance = "faible (contradiction non tranchée par une règle)"
        justification = (
            f"Contradiction détectée ({'; '.join(contradictions)}) et aucune "
            f"règle critique ne permet de trancher automatiquement. "
            f"Une vérification humaine est nécessaire."
        )
    elif regle_activee is not None:
        orientation = regle_activee.orientation
        confiance = "élevée" if regle_activee.priorite >= 90 else "moyenne"
        justification = (
            f"La règle {regle_activee.id} s'est déclenchée "
            f"({regle_activee.description}), priorité clinique "
            f"{regle_activee.niveau_priorite_clinique}."
        )
    elif manquants:
        orientation = "DEMANDER_PRECISIONS"
        confiance = "faible (informations critiques manquantes)"
        justification = (
            "Aucune règle ne s'est déclenchée et des informations critiques "
            f"manquent : {', '.join(manquants)}. Conformément à la contrainte "
            "du sujet, le système ne conclut pas avec une confiance élevée "
            "et demande des précisions plutôt que de deviner."
        )
    else:
        # Aucune règle ne matche, pas d'infos manquantes, pas de contradiction :
        # le moteur à règles seul ne peut pas trancher plus finement.
        # C'est précisément le rôle de la méthode 2 (probabiliste).
        orientation = "CONSULTATION_NORMALE (par défaut, à affiner par méthode 2)"
        confiance = "faible (aucune règle décisive, nécessite le modèle probabiliste)"
        justification = (
            "Aucune règle du moteur symbolique ne couvre ce cas et toutes les "
            "informations critiques sont renseignées. Le moteur à règles seul "
            "retombe sur une orientation par défaut ; le raisonnement "
            "probabiliste (méthode 2) est nécessaire pour affiner la décision."
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


# ---------------------------------------------------------------------------
# 6. Affichage de la trace de raisonnement (format demandé par le sujet)
# ---------------------------------------------------------------------------

def afficher_trace(nom_cas: str, faits_bruts: dict, attendu: Optional[str] = None) -> Explication:
    exp = evaluer_cas(faits_bruts)

    print(f"\n=== Cas : {nom_cas} ===")
    print("Faits reçus :")
    for k, v in faits_bruts.items():
        print(f"  - {k} : {v}")

    print("Règles évaluées :")
    for t in exp.regles_evaluees:
        statut = "DÉCLENCHÉE" if t.resultat else "non déclenchée"
        print(f"  - {t.id} ({t.description}) -> {statut}")

    if exp.contradictions:
        print("Contradictions détectées :")
        for c in exp.contradictions:
            print(f"  - {c}")
    else:
        print("Contradictions détectées : aucune")

    if exp.infos_manquantes:
        print(f"Informations manquantes : {', '.join(exp.infos_manquantes)}")
    else:
        print("Informations manquantes : aucune")

    print(f"Niveau de confiance : {exp.confiance}")
    print(f"Décision finale : {exp.orientation}")
    print(f"Justification : {exp.justification}")

    if attendu:
        ok = attendu.split(" ")[0] in exp.orientation  # comparaison simple
        print(f"Décision attendue (sujet) : {attendu}  ->  {'OK' if ok else 'À COMPARER'}")

    return exp


# ---------------------------------------------------------------------------
# 7. Cas de test du sujet (C1 à C11)
# ---------------------------------------------------------------------------

CAS_DE_TEST = [
    (
        "C1 - Symptômes légers, durée courte, aucune alerte",
        nouveau_cas(
            douleur="faible", temperature="normale", duree_symptomes="courte",
            difficulte_respiratoire="non", douleur_thoracique="non",
            perte_conscience="non", saignement_important="non",
            fatigue_importante="non",
        ),
        "SURVEILLANCE",
    ),
    (
        "C2 - Température élevée, durée longue",
        nouveau_cas(
            temperature="elevee", duree_symptomes="longue", douleur="moyen",
            difficulte_respiratoire="non", douleur_thoracique="non",
            perte_conscience="non", saignement_important="non",
        ),
        "CONSULTATION_PRIORITAIRE",
    ),
    (
        "C3 - Douleur thoracique et difficulté respiratoire",
        nouveau_cas(
            douleur_thoracique="oui", difficulte_respiratoire="oui",
            temperature="normale", duree_symptomes="courte",
            perte_conscience="non", saignement_important="non",
        ),
        "ORIENTATION_URGENTE",
    ),
    (
        "C4 - Douleur moyenne, température normale",
        nouveau_cas(
            douleur="moyen", temperature="normale", duree_symptomes="courte",
            difficulte_respiratoire="non", douleur_thoracique="non",
            perte_conscience="non", saignement_important="non",
        ),
        "CONSULTATION_NORMALE",
    ),
    (
        "C5 - Fatigue importante, informations complètes",
        nouveau_cas(
            fatigue_importante="oui", douleur="moyen", temperature="normale",
            duree_symptomes="courte", difficulte_respiratoire="non",
            douleur_thoracique="non", perte_conscience="non",
            saignement_important="non",
        ),
        "CONSULTATION_NORMALE",  # nuance fine laissée à la méthode 2
    ),
    (
        "C6 - Perte de conscience",
        nouveau_cas(
            perte_conscience="oui", temperature="normale", duree_symptomes="courte",
        ),
        "ORIENTATION_URGENTE",
    ),
    (
        "C7 - Saignement important",
        nouveau_cas(
            saignement_important="oui", temperature="normale", duree_symptomes="courte",
        ),
        "ORIENTATION_URGENTE",
    ),
    (
        "C8 - Température inconnue et durée inconnue",
        nouveau_cas(
            temperature="inconnu", duree_symptomes="inconnu",
            difficulte_respiratoire="inconnu", douleur_thoracique="inconnu",
            perte_conscience="non", saignement_important="inconnu",
        ),
        "DEMANDER_PRECISIONS",
    ),
    (
        "C9 (limite) - Symptômes légers et perte de conscience",
        nouveau_cas(
            symptomes_legers="oui", perte_conscience="oui",
            temperature="normale", duree_symptomes="courte",
        ),
        "ORIENTATION_URGENTE",
    ),
    (
        "C10 (limite) - Risque probabiliste élevé, aucune règle activée",
        nouveau_cas(
            douleur="moyen", temperature="normale", duree_symptomes="courte",
            difficulte_respiratoire="non", douleur_thoracique="non",
            perte_conscience="non", saignement_important="non",
            fatigue_importante="oui",
        ),
        "CONSULTATION_PRIORITAIRE",  # nécessite la méthode 2 (probabiliste)
    ),
    (
        "C11 (limite) - Règle urgente active mais probabilité faible",
        nouveau_cas(
            perte_conscience="oui", temperature="normale", duree_symptomes="courte",
            douleur="faible",
        ),
        "ORIENTATION_URGENTE",
    ),
]


def charger_cas_test(chemin: Path) -> list[tuple[str, dict, Optional[str]]]:
    """Charge les cas de test depuis un fichier JSON externe (reproductibilité).

    Si le fichier n'existe pas, retombe sur les cas codés en dur (CAS_DE_TEST)
    pour que le script reste exécutable même sans le dossier data/.
    """
    if chemin.exists():
        with open(chemin, encoding="utf-8") as f:
            brut = json.load(f)
        return [(c["nom"], c["faits"], c.get("decision_attendue")) for c in brut]
    print(f"[avertissement] {chemin} introuvable, utilisation des cas intégrés au code.")
    return CAS_DE_TEST


def main():
    parser = argparse.ArgumentParser(
        description="Moteur à règles - système d'orientation des patients (méthode 1)"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "cas_test.json",
        help="Chemin du fichier JSON contenant les cas de test "
        "(défaut : data/cas_test.json)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="N'affiche que le bilan final, pas la trace détaillée de chaque cas.",
    )
    args = parser.parse_args()

    cas_de_test = charger_cas_test(args.data)

    print("MOTEUR À RÈGLES — Système explicable d'orientation des patients")
    print("Configuration A : moteur à règles uniquement (méthode 1 du sujet)")
    print(f"Cas de test chargés depuis : {args.data}\n")

    total = len(cas_de_test)
    reussites = 0
    echecs = []
    besoin_methode2 = []
    temps_total = 0.0

    for nom, faits, attendu in cas_de_test:
        debut = time.perf_counter()
        exp = evaluer_cas(faits)
        temps_total += time.perf_counter() - debut

        if not args.quiet:
            afficher_trace(nom, faits, attendu)

        if "méthode 2" in exp.justification:
            besoin_methode2.append(nom)

        if attendu is not None:
            ok = attendu.split(" ")[0] in exp.orientation
            if ok:
                reussites += 1
            else:
                echecs.append((nom, attendu, exp.orientation))

    print("\n\n=== Bilan Configuration A (règles seules) ===")
    print(f"Cas traités : {total}")
    print(f"Exactitude (par rapport aux décisions attendues) : {reussites}/{total}")
    print(f"Temps de raisonnement total : {temps_total*1000:.3f} ms "
          f"({temps_total*1000/total:.4f} ms/cas en moyenne)")

    if echecs:
        print("Échecs (décision attendue vs obtenue) :")
        for nom, attendu, obtenu in echecs:
            print(f"  - {nom}\n      attendu : {attendu}\n      obtenu  : {obtenu}")
    else:
        print("Échecs : aucun")

    print("\nCas où le moteur à règles seul est insuffisant "
          "(nécessite la méthode 2 - probabiliste) :")
    for c in besoin_methode2:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
