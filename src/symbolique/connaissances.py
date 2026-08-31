"""Ontologie et chargement déclaratif des règles symboliques."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# --- 1. Ontologie des variables (Rôle 1) ---

# Ensemble des variables attendues (logique ternaire : "oui" / "non" / "inconnu")
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _charger_json(nom: str) -> Any:
    with open(_DATA_DIR / nom, encoding="utf-8") as fichier:
        return json.load(fichier)


ONTOLOGIE: dict[str, dict[str, Any]] = _charger_json("ontologie.json")
CHAMPS_ATTENDUS: list[str] = list(ONTOLOGIE)

# Variables critiques dont l'absence bloque une conclusion normale
CHAMPS_CRITIQUES: list[str] = [
    champ for champ, definition in ONTOLOGIE.items() if definition.get("critique", False)
]

DOMAINES: dict[str, set[Any]] = {
    champ: set(definition["valeurs"])
    for champ, definition in ONTOLOGIE.items()
}


# --- 2. Base de règles symboliques (Rôle 2) ---

@dataclass
class Regle:
    id: str
    priorite: int
    conditions: list[dict[str, str]]
    orientation: str
    confiance: str
    description: str
    critique: bool = False

    def condition(self, faits: dict[str, Any]) -> bool:
        """Évalue une conjonction en logique prudente : inconnu n'est jamais vrai."""
        return all(
            faits.get(c["champ"], "inconnu") == c["valeur"]
            for c in self.conditions
        )


def _charger_definitions() -> list[dict[str, Any]]:
    chemin = Path(__file__).resolve().parents[2] / "data" / "regles.json"
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


REGLES: list[Regle] = sorted(
    [Regle(**definition) for definition in _charger_definitions()],
    key=lambda r: -r.priorite,
)
