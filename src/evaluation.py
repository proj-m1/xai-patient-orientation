"""Métriques reproductibles pour comparer une configuration de triage."""

from __future__ import annotations

from typing import Any, Callable


def calculer_metriques(cas_liste: list[Any], evaluer: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    """Calcule exactitude, matrice de confusion et sensibilité urgente."""
    normalises = [
        (cas[1], cas[2]) if isinstance(cas, tuple) else (cas["faits"], cas.get("decision_attendue"))
        for cas in cas_liste
    ]
    attendus = [attendu for _, attendu in normalises]
    obtenus = [evaluer(faits) for faits, _ in normalises]
    orientations = sorted({v for v in attendus if v})
    confusion = {
        attendu: {obtenu: 0 for obtenu in orientations}
        for attendu in orientations
    }
    conformes = 0
    for attendu, obtenu in zip(attendus, obtenus):
        valeur = getattr(obtenu, "orientation", obtenu)
        conformes += int(attendu == valeur)
        if attendu in confusion and valeur in confusion[attendu]:
            confusion[attendu][valeur] += 1
    urgents = [index for index, attendu in enumerate(attendus) if attendu == "ORIENTATION_URGENTE"]
    urgents_corrects = sum(
        getattr(obtenus[index], "orientation", obtenus[index]) == "ORIENTATION_URGENTE"
        for index in urgents
    )
    return {
        "exactitude": round(100 * conformes / len(cas_liste), 1) if cas_liste else 0.0,
        "conformes": conformes,
        "sensibilite_urgente": round(100 * urgents_corrects / len(urgents), 1) if urgents else None,
        "faux_negatifs_urgents": len(urgents) - urgents_corrects,
        "matrice_confusion": confusion,
    }
