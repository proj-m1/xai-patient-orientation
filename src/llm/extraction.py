"""Extraction facultative Gemini : texte libre vers faits, jamais texte vers orientation."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.symbolique import ONTOLOGIE
from src.symbolique.moteur_regles import valider_faits


class LLMIndisponible(RuntimeError):
    """Signale une absence de configuration ou un échec de l'API externe."""


def _schema_faits() -> dict[str, Any]:
    """Construit le schéma Gemini directement depuis l'ontologie centrale."""
    proprietes = {}
    for champ, definition in ONTOLOGIE.items():
        if definition["type"] == "entier":
            # Le schéma GenerateContent utilise les types OpenAPI en majuscules.
            proprietes[champ] = {"type": "STRING", "description": "entier entre 0 et 120, ou inconnu"}
        else:
            proprietes[champ] = {
                "type": "STRING",
                "enum": definition["valeurs"],
            }
    return {
        "type": "OBJECT",
        "properties": proprietes,
        "required": list(ONTOLOGIE),
        "propertyOrdering": list(ONTOLOGIE),
    }


def _texte_reponse(reponse: dict[str, Any]) -> str:
    """Récupère le texte JSON de la réponse GenerateContent."""
    candidates = reponse.get("candidates", [])
    if not candidates:
        raise LLMIndisponible("Gemini n'a retourné aucun candidat.")
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if isinstance(part.get("text"), str):
            return part["text"]
    raise LLMIndisponible("Réponse Gemini sans JSON exploitable.")


def extraire_faits(description: str, *, api_key: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Extrait des faits observables et transforme toute ambiguïté en inconnu."""
    if not isinstance(description, str) or not description.strip():
        raise ValueError("La description libre est obligatoire.")
    cle = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not cle:
        raise LLMIndisponible("GEMINI_API_KEY n'est pas configurée; le mode local reste disponible.")

    modele = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    instruction = (
        "Extrait uniquement les faits explicitement observables dans le texte. "
        "N'invente rien, ne pose aucun diagnostic et ne donne aucune orientation. "
        "Pour toute information absente ou ambiguë, utilise null. "
        "Les valeurs autorisées sont exactement celles du schéma.\n\nTexte : " + description
    )
    payload = {
        "contents": [{"parts": [{"text": instruction}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
                "responseSchema": _schema_faits(),
            },
        }
    modele = modele.removeprefix("models/")
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(modele, safe="") + ":generateContent"
    requete = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": cle, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(requete, timeout=20) as flux:
            reponse = json.load(flux)
    except HTTPError as erreur:
        detail = erreur.read().decode("utf-8", errors="replace")
        raise LLMIndisponible(f"Échec de l'appel Gemini ({erreur.code}) : {detail}") from erreur
    except (URLError, TimeoutError) as erreur:
        raise LLMIndisponible(f"Échec de l'appel Gemini : {erreur}") from erreur

    try:
        brut = json.loads(_texte_reponse(reponse))
    except (json.JSONDecodeError, TypeError) as erreur:
        raise LLMIndisponible("Gemini n'a pas retourné un JSON valide.") from erreur
    faits = {champ: ("inconnu" if valeur in (None, "") else valeur) for champ, valeur in brut.items()}
    if isinstance(faits.get("age"), str) and faits["age"] != "inconnu":
        try:
            faits["age"] = int(faits["age"])
        except ValueError as erreur:
            raise LLMIndisponible("Gemini a fourni un âge non numérique.") from erreur
    return valider_faits(faits)
