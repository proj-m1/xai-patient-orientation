#!/usr/bin/env python3
"""
Role 4 - Interface web (API Flask + frontend Vue.js via CDN)

Expose une API REST simple qui appelle le moteur hybride et renvoie la
decision finale + la justification + la trace des deux methodes.

Lance le serveur :
    python src/app.py
Puis ouvrir : http://127.0.0.1:5000
"""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moteur_regles import evaluer_cas, nouveau_cas  # noqa: E402
from moteur_probabiliste import evaluer_probabiliste  # noqa: E402
from integration_hybride import fusionner  # noqa: E402

app = Flask(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


@app.route("/")
def index():
    return send_from_directory(str(TEMPLATE_DIR), "index.html")


@app.route("/api/evaluer", methods=["POST"])
def api_evaluer():
    data = request.get_json(silent=True) or {}
    faits_bruts = data.get("faits", {})

    # Securite : on ne garde que les champs attendus, valeurs stringifiees.
    faits = {}
    for k, v in faits_bruts.items():
        if v in ("", None):
            continue
        faits[k] = str(v).lower()

    try:
        dec = fusionner(faits)
        exp_regles = evaluer_cas(faits)
        res_proba = evaluer_probabiliste(faits)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erreur": str(e)}), 400

    traces = [
        {"id": t.id, "description": t.description, "resultat": t.resultat}
        for t in exp_regles.regles_evaluees
    ]

    return jsonify({
        "orientation": dec.orientation,
        "confiance": dec.confiance,
        "source": dec.source,
        "probabilite_urgence": round(dec.probabilite_urgence, 4) if dec.probabilite_urgence is not None else None,
        "justification": dec.justification,
        "detail_regles": dec.detail_regles,
        "detail_probabiliste": dec.detail_probabiliste,
        "regles_evaluees": traces,
        "contradictions": dec.contradictions,
        "infos_manquantes": dec.infos_manquantes,
        "faits_recus": nouveau_cas(**faits),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
