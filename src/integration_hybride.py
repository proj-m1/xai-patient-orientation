#!/usr/bin/env python3
"""
Rôle 4 - Intégration hybride + table de fusion

Ce module intègre les deux méthodes complémentaires du projet :
  - Méthode 1 (moteur à règles, symbolique) -> src/moteur_regles.py
  - Méthode 2 (raisonnement probabiliste)  -> src/moteur_probabiliste.py

et applique une TABLE DE FUSION déterministe orientée sécurité pour produire
une décision finale unique, accompagnée d'une justification combinée.

Principe directeur (cf. docs/formalisation_connaissances.md §3.2) :
le coût d'un faux négatif urgent étant très élevé, la fusion privilégie
toujours l'hypothèse la plus prudente. Une règle critique déclenchée n'est
jamais annulée par le modèle probabiliste.

Le module fournit aussi la COMPARAISON DES DEUX CONFIGURATIONS exigée par le
sujet (Configuration A = règles seules, Configuration B = hybride) sur le jeu
de test, avec analyse d'exactitude, de cohérence, de temps et des échecs.

Usage :
    python src/integration_hybride.py --data data/cas_test.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from moteur_regles import evaluer_cas, nouveau_cas  # noqa: E402
from moteur_probabiliste import evaluer_probabiliste  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Table de fusion
# ---------------------------------------------------------------------------

@dataclass
class DecisionHybride:
    orientation: str
    confiance: str
    source: str                       # "regles" | "probabiliste" | "fusion"
    justification: str
    detail_regles: str = ""
    detail_probabiliste: str = ""
    probabilite_urgence: Optional[float] = None
    contradictions: list[str] = field(default_factory=list)
    infos_manquantes: list[str] = field(default_factory=list)


def fusionner(faits_bruts: dict) -> DecisionHybride:
    """Applique la table de fusion entre le moteur à règles et le probabiliste."""
    faits = nouveau_cas(**faits_bruts)

    exp_regles = evaluer_cas(faits)
    res_proba = evaluer_probabiliste(faits)

    orientation_regles = exp_regles.orientation
    p = res_proba.probabilite_urgence

    contradictions = exp_regles.contradictions
    manquants = exp_regles.infos_manquantes

    detail_regles = (
        f"Méthode 1 (règles) : {orientation_regles} "
        f"(confiance {exp_regles.confiance}). "
    )
    if exp_regles.regle_activee is not None:
        detail_regles += (
            f"Règle déclenchée : {exp_regles.regle_activee.id} - "
            f"{exp_regles.regle_activee.description}. "
        )
    detail_probabiliste = (
        f"Méthode 2 (probabiliste) : {res_proba.orientation} "
        f"(P(urgence)={p:.2f}, score={res_proba.score:+.2f}). "
    )

    # --- TABLE DE FUSION (orientée sécurité) ---
    #
    # Cas 1 : contradiction non tranchée par une règle critique.
    if orientation_regles == "SURVEILLANCE_MANUELLE_REQUISE":
        return DecisionHybride(
            orientation="SURVEILLANCE_MANUELLE_REQUISE",
            confiance="faible (contradiction non tranchée)",
            source="regles",
            justification=(
                "Fusion : contradiction détectée et aucune règle critique ne "
                "permet de trancher. Le système refuse de conclure seul et "
                "demande une vérification humaine. " + detail_regles
            ),
            detail_regles=detail_regles,
            detail_probabiliste=detail_probabiliste,
            probabilite_urgence=p,
            contradictions=contradictions,
            infos_manquantes=manquants,
        )

    # Cas 2 : règle urgente déclenchée -> on la garde même si la probabilité
    # est faible (principe de sécurité : on n'annule jamais un signe critique).
    if orientation_regles == "ORIENTATION_URGENTE":
        note = ""
        if p < 0.75:
            note = (
                " Le modèle probabiliste estime P(urgence)="
                f"{p:.2f} (sous le seuil urgent du probabiliste) mais "
                "la règle critique prime par sécurité : une règle urgente "
                "déclenchée n'est jamais annulée par le modèle probabiliste."
            )
        return DecisionHybride(
            orientation="ORIENTATION_URGENTE",
            confiance="très élevée (règle critique + sécurité)",
            source="regles",
            justification=(
                "Fusion : une règle critique (urgence) s'est déclenchée. "
                "Elle n'est pas annulée par le modèle probabiliste, "
                "conformément au principe de sécurité." + note + " "
                + detail_regles + detail_probabiliste
            ),
            detail_regles=detail_regles,
            detail_probabiliste=detail_probabiliste,
            probabilite_urgence=p,
            contradictions=contradictions,
            infos_manquantes=manquants,
        )

    # Cas 3 : informations critiques manquantes et aucune règle urgente ->
    # on ne devine pas, on demande des précisions.
    if orientation_regles == "DEMANDER_PRECISIONS":
        return DecisionHybride(
            orientation="DEMANDER_PRECISIONS",
            confiance="faible (informations critiques manquantes)",
            source="regles",
            justification=(
                "Fusion : des informations critiques manquent et aucune règle "
                "décisive ne s'est déclenchée. Le système ne conclut pas à "
                "haute confiance et demande des précisions plutôt que de "
                "deviner. " + detail_regles
            ),
            detail_regles=detail_regles,
            detail_probabiliste=detail_probabiliste,
            probabilite_urgence=p,
            contradictions=contradictions,
            infos_manquantes=manquants,
        )

    # Cas 4 : règle prioritaire (R3) -> on la conserve, sauf si le probabiliste
    # signale une urgence très forte (P>=0.90), auquel cas on passe en URGENT.
    if orientation_regles == "CONSULTATION_PRIORITAIRE":
        if p >= 0.90:
            return DecisionHybride(
                orientation="ORIENTATION_URGENTE",
                confiance="élevée (règle prioritaire + probabilité très forte)",
                source="fusion",
                justification=(
                    "Fusion : la règle R3 donnait CONSULTATION_PRIORITAIRE, "
                    f"mais le modèle probabiliste estime P(urgence)={p:.2f} "
                    "(>=0.90, probabilité très forte). Par sécurité, la décision "
                    "est rehaussée en ORIENTATION_URGENTE." + " " + detail_regles + detail_probabiliste
                ),
                detail_regles=detail_regles,
                detail_probabiliste=detail_probabiliste,
                probabilite_urgence=p,
                contradictions=contradictions,
                infos_manquantes=manquants,
            )
        return DecisionHybride(
            orientation="CONSULTATION_PRIORITAIRE",
            confiance="moyenne (règle prioritaire confirmée)",
            source="regles",
            justification=(
                "Fusion : la règle R3 (consultation prioritaire) est confirmée "
                f"par le modèle probabiliste (P={p:.2f}). " + detail_regles + detail_probabiliste
            ),
            detail_regles=detail_regles,
            detail_probabiliste=detail_probabiliste,
            probabilite_urgence=p,
            contradictions=contradictions,
            infos_manquantes=manquants,
        )

    # Cas 5 : aucune règle décisive (SURVEILLANCE ou défaut par règles) ->
    # on s'en remet au modèle probabiliste.
    decision_probabiliste = res_proba.orientation
    return DecisionHybride(
        orientation=decision_probabiliste,
        confiance="moyenne (décision par modèle probabiliste)",
        source="probabiliste",
        justification=(
            "Fusion : aucune règle décisive ne couvre ce cas. La décision "
            "finale provient du modèle probabiliste." + " "
            + detail_regles + detail_probabiliste
        ),
        detail_regles=detail_regles,
        detail_probabiliste=detail_probabiliste,
        probabilite_urgence=p,
        contradictions=contradictions,
        infos_manquantes=manquants,
    )


# ---------------------------------------------------------------------------
# 2. Comparaison des deux configurations (exigence du sujet)
# ---------------------------------------------------------------------------

def charger_cas_test(chemin: Path):
    if chemin.exists():
        with open(chemin, encoding="utf-8") as f:
            brut = json.load(f)
        return [(c["nom"], c["faits"], c.get("decision_attendue")) for c in brut]
    print(f"[avertissement] {chemin} introuvable.")
    return []


def _concordant(obtenu: str, attendu: Optional[str]) -> bool:
    if attendu is None:
        return True
    return attendu.split(" ")[0] in obtenu


def comparer_configurations(chemin: Path) -> None:
    cas = charger_cas_test(chemin)
    if not cas:
        return

    print("=" * 78)
    print("COMPARAISON DES DEUX CONFIGURATIONS")
    print("  Config A : moteur à règles seul (méthode 1)")
    print("  Config B : intégration hybride (méthode 1 + méthode 2 + fusion)")
    print("=" * 78)

    lignes = []
    ok_a = ok_b = 0
    ta = tb = 0.0
    echecs_a = []
    echecs_b = []

    for nom, faits, attendu in cas:
        t0 = time.perf_counter()
        exp_a = evaluer_cas(faits)
        ta += time.perf_counter() - t0
        res_a = exp_a.orientation
        bon_a = _concordant(res_a, attendu)
        ok_a += int(bon_a)
        if not bon_a:
            echecs_a.append((nom, attendu, res_a))

        t0 = time.perf_counter()
        dec_b = fusionner(faits)
        tb += time.perf_counter() - t0
        res_b = dec_b.orientation
        bon_b = _concordant(res_b, attendu)
        ok_b += int(bon_b)
        if not bon_b:
            echecs_b.append((nom, attendu, res_b))

        lignes.append((nom, res_a, res_b, dec_b.probabilite_urgence, attendu, bon_a, bon_b))

    n = len(cas)
    print(f"\n{'Cas':<46} {'Config A':<28} {'Config B':<28} {'Attendu'}")
    print("-" * 140)
    for nom, ra, rb, prob, attendu, ba, bb in lignes:
        nom_court = nom if len(nom) <= 45 else nom[:42] + "..."
        ra_court = (ra[:26] + "...") if len(ra) > 28 else ra
        rb_court = (rb[:26] + "...") if len(rb) > 28 else rb
        marque = "" if (ba and bb) else "  <-- ecart"
        print(f"{nom_court:<46} {ra_court:<28} {rb_court:<28} {attendu}{marque}")

    print("\n--- Synthese ---")
    print(f"Cas traites : {n}")
    print(f"Exactitude Config A (regles)   : {ok_a}/{n} = {100*ok_a/n:.1f}%")
    print(f"Exactitude Config B (hybride)  : {ok_b}/{n} = {100*ok_b/n:.1f}%")
    print(f"Temps total A : {ta*1000:.3f} ms ({1000*ta/n:.4f} ms/cas)")
    print(f"Temps total B : {tb*1000:.3f} ms ({1000*tb/n:.4f} ms/cas)")

    if echecs_a:
        print("\nEchecs Config A :")
        for nom, attendu, obtenu in echecs_a:
            print(f"  - {nom} : attendu={attendu} / obtenu={obtenu}")
    if echecs_b:
        print("\nEchecs Config B :")
        for nom, attendu, obtenu in echecs_b:
            print(f"  - {nom} : attendu={attendu} / obtenu={obtenu}")


def main():
    parser = argparse.ArgumentParser(
        description="Role 4 - integration hybride (moteur a regles + probabiliste)"
    )
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "cas_test.json")
    args = parser.parse_args()
    comparer_configurations(args.data)


if __name__ == "__main__":
    main()
