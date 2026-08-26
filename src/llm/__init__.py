"""Extraction facultative de faits depuis un texte libre par un modèle externe."""

from src.llm.extraction import LLMIndisponible, extraire_faits

__all__ = ["LLMIndisponible", "extraire_faits"]
