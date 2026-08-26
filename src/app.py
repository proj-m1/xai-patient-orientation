#!/usr/bin/env python3
"""Rôle 4 : Serveur web Flask et API REST d'orientation des patients."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify, request, send_from_directory

from src.hybride import fusionner
from src.llm import LLMIndisponible, extraire_faits
from src.probabiliste import evaluer_probabiliste
from src.symbolique import ONTOLOGIE, charger_cas_test, evaluer_cas, nouveau_cas, valider_faits
from src.evaluation import calculer_metriques

BASE_DIR = ROOT_DIR
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="",
)


@app.route("/")
def index():
    """Page d'accueil de l'interface d'orientation."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/cas_test", methods=["GET"])
def api_cas_test():
    """Retourne la liste des cas de test prédéfinis pour démonstration."""
    chemin = DATA_DIR / "cas_test.json"
    if not chemin.exists():
        return jsonify([])
    with open(chemin, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/ontologie", methods=["GET"])
def api_ontologie():
    """Expose les champs et valeurs autorisés à l'interface."""
    return jsonify(ONTOLOGIE)


def determiner_etat_incertitude(exp_regles, res_proba, dec_hybride) -> dict[str, str]:
    """Détermine l'état épistémique global (Suggestion 4 : indicateur d'incertitude)."""
    if exp_regles.contradictions:
        return {
            "type": "contradiction",
            "label": "Contradiction Détectée",
            "description": "Incohérence entre déclarations et signes cliniques.",
        }
    if exp_regles.infos_manquantes:
        return {
            "type": "incomplet",
            "label": "Incomplet (Données Manquantes)",
            "description": "Variables critiques inconnues, refus de deviner.",
        }
    if exp_regles.regle_activee is not None and exp_regles.regle_activee.priorite >= 90:
        return {
            "type": "certain_urgent",
            "label": "Certain (Urgence Critique)",
            "description": f"Règle déterministe {exp_regles.regle_activee.id} déclenchée à priorité maximale.",
        }
    if exp_regles.regle_activee is not None:
        return {
            "type": "certain_regle",
            "label": "Certain (Règle Métier)",
            "description": f"Règle déterministe {exp_regles.regle_activee.id} appliquée.",
        }
    return {
        "type": "probabiliste",
        "label": "Incertain (Arbitrage Probabiliste)",
        "description": "Aucune règle déterministe applicable, décision graduée par score de risque.",
    }


def construire_etapes_justification(exp_regles, dec_hybride) -> list[str]:
    """Transforme la trace technique en quelques étapes lisibles pour l'interface."""
    etapes: list[str] = []

    if exp_regles.contradictions:
        etapes.append("Une contradiction a été détectée dans les informations fournies.")

    if exp_regles.infos_manquantes:
        noms = ", ".join(
            ONTOLOGIE[nom]["libelle"].lower()
            for nom in exp_regles.infos_manquantes
            if nom in ONTOLOGIE
        )
        if noms:
            etapes.append(f"Il manque des informations critiques : {noms}.")

    regle = exp_regles.regle_activee
    if regle is not None:
        if regle.critique:
            etapes.append(f"Le signe d'alerte détecté active la règle {regle.id} et impose une orientation urgente.")
        else:
            etapes.append(f"La règle {regle.id} s'applique au profil observé.")
    elif not exp_regles.contradictions:
        etapes.append("Aucune règle déterministe ne couvre exactement ce profil.")

    if dec_hybride.source == "probabiliste":
        etapes.append("Le modèle probabiliste complète l'analyse à partir des facteurs observés.")
    elif dec_hybride.source == "fusion" and not regle:
        etapes.append("La fusion demande une vérification ou des précisions avant de conclure.")

    return etapes


@app.route("/api/evaluer", methods=["POST"])
def api_evaluer():
    """Évalue un cas patient et retourne la décision hybride et la comparaison A vs B."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"erreur": "Le corps JSON doit être un objet."}), 422
    faits_bruts = data.get("faits", {})
    if not isinstance(faits_bruts, dict):
        return jsonify({"erreur": "Le champ 'faits' doit être un objet."}), 422

    faits = {
        k: (v.lower() if isinstance(v, str) else v)
        for k, v in faits_bruts.items()
        if v not in ("", None)
    }

    t0 = time.perf_counter()
    try:
        faits = valider_faits(faits)
        dec = fusionner(faits)
        exp_regles = evaluer_cas(faits)
        res_proba = evaluer_probabiliste(faits)
    except Exception as e:
        return jsonify({"erreur": str(e)}), 422

    duree_ms = round((time.perf_counter() - t0) * 1000, 3)

    traces = [
        {"id": t.id, "description": t.description, "resultat": t.resultat}
        for t in exp_regles.regles_evaluees
    ]

    contribs = [
        {"symptome": c.symptome, "poids": c.poids, "active": c.active}
        for c in res_proba.contributions
    ]

    etat_incertitude = determiner_etat_incertitude(exp_regles, res_proba, dec)
    justification_etapes = construire_etapes_justification(exp_regles, dec)

    return jsonify({
        # Décision hybride finale (Config B)
        "orientation": dec.orientation,
        "confiance": dec.confiance,
        "source": dec.source,
        "justification": dec.justification,
        "justification_etapes": justification_etapes,
        "regle_activee": exp_regles.regle_activee.id if exp_regles.regle_activee else None,
        "probabilite_urgence": round(dec.probabilite_urgence, 4) if dec.probabilite_urgence is not None else None,
        "score_risque": round(res_proba.score, 2),

        # Comparaison live Config A vs Config B (Suggestion 1)
        "config_a": {
            "orientation": exp_regles.orientation,
            "confiance": exp_regles.confiance,
            "justification": exp_regles.justification,
            "regle_activee": exp_regles.regle_activee.id if exp_regles.regle_activee else None,
        },
        "config_b": {
            "orientation": dec.orientation,
            "confiance": dec.confiance,
            "justification": dec.justification,
            "source": dec.source,
        },

        # Indicateur global d'incertitude (Suggestion 4)
        "etat_incertitude": etat_incertitude,

        # Traces explicatives
        "detail_regles": dec.detail_regles,
        "detail_probabiliste": dec.detail_probabiliste,
        "regles_evaluees": traces,
        "contributions_probabilistes": contribs,
        "probabilites_par_orientation": res_proba.probabilites_par_orientation,
        "contradictions": dec.contradictions,
        "infos_manquantes": dec.infos_manquantes,
        "faits_recus": nouveau_cas(**faits),
        "temps_calcul_ms": duree_ms,
    })


@app.route("/api/extraire-faits", methods=["POST"])
def api_extraire_faits():
    """Convertit explicitement un texte en faits; aucune orientation n'est déléguée au LLM."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"erreur": "Le corps JSON doit être un objet."}), 422
    try:
        faits = extraire_faits(data.get("description", ""))
    except LLMIndisponible as erreur:
        return jsonify({"erreur": str(erreur), "mode": "local_indisponible"}), 503
    except ValueError as erreur:
        return jsonify({"erreur": str(erreur)}), 422
    return jsonify({"faits": faits, "message": "Faits extraits; la décision doit encore être calculée par le moteur local."})


@app.route("/api/benchmark", methods=["GET"])
def api_benchmark():
    """Évalue et compare automatiquement l'ensemble des 11 cas de test (Suggestion 2)."""
    chemin = DATA_DIR / "cas_test.json"
    if not chemin.exists():
        return jsonify({"erreur": "Jeu de données introuvable"}), 404

    cas_liste = charger_cas_test(chemin)
    resultats = []
    reussites_a = 0
    reussites_b = 0
    t_a_total = 0.0
    t_b_total = 0.0

    for nom, faits, attendu in cas_liste:
        t0 = time.perf_counter()
        exp_a = evaluer_cas(faits)
        t_a = (time.perf_counter() - t0) * 1000
        t_a_total += t_a

        t0 = time.perf_counter()
        dec_b = fusionner(faits)
        t_b = (time.perf_counter() - t0) * 1000
        t_b_total += t_b

        bon_a = bool(attendu and attendu == exp_a.orientation)
        bon_b = bool(attendu and attendu == dec_b.orientation)

        if bon_a:
            reussites_a += 1
        if bon_b:
            reussites_b += 1

        resultats.append({
            "nom": nom,
            "faits": faits,
            "attendu": attendu,
            "config_a": {
                "orientation": exp_a.orientation,
                "concorde": bon_a,
                "temps_ms": round(t_a, 4),
            },
            "config_b": {
                "orientation": dec_b.orientation,
                "concorde": bon_b,
                "temps_ms": round(t_b, 4),
                "probabilite_urgence": round(dec_b.probabilite_urgence, 4) if dec_b.probabilite_urgence is not None else None,
            },
        })

    n = len(cas_liste)
    metriques_a = calculer_metriques(cas_liste, evaluer_cas)
    metriques_b = calculer_metriques(cas_liste, fusionner)
    return jsonify({
        "total_cas": n,
        "synthese": {
            "exactitude_config_a": round(100 * reussites_a / n, 1),
            "reussites_config_a": reussites_a,
            "sensibilite_urgente_a": metriques_a["sensibilite_urgente"],
            "faux_negatifs_urgents_a": metriques_a["faux_negatifs_urgents"],
            "temps_moyen_a_ms": round(t_a_total / n, 4),
            "exactitude_config_b": round(100 * reussites_b / n, 1),
            "reussites_config_b": reussites_b,
            "sensibilite_urgente_b": metriques_b["sensibilite_urgente"],
            "faux_negatifs_urgents_b": metriques_b["faux_negatifs_urgents"],
            "temps_moyen_b_ms": round(t_b_total / n, 4),
            "matrice_confusion_a": metriques_a["matrice_confusion"],
            "matrice_confusion_b": metriques_b["matrice_confusion"],
        },
        "details": resultats,
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
