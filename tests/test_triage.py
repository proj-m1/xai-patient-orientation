"""Rôle 5 : Suite de tests automatisés et validation de qualité.

Vérifie l'exactitude, la robustesse aux imperfections, la performance
et la conformité des deux configurations (A et B) aux spécifications.
"""

import json
import time
from pathlib import Path

from src.app import app
from src.hybride import fusionner
from src.probabiliste import evaluer_probabiliste, sigmoide
from src.symbolique import (
    CHAMPS_ATTENDUS,
    CHAMPS_CRITIQUES,
    REGLES,
    champs_manquants,
    detecter_contradictions,
    evaluer_cas,
    nouveau_cas,
    valider_faits,
)


# ===========================================================================
# 1. TESTS DE L'ONTOLOGIE ET DES DONNÉES (RÔLE 1)
# ===========================================================================

def test_ontologie_structure():
    """Vérifie la présence et la complétude des variables formalisées."""
    assert len(CHAMPS_ATTENDUS) == 10
    assert "perte_conscience" in CHAMPS_CRITIQUES
    assert "saignement_important" in CHAMPS_CRITIQUES
    assert "difficulte_respiratoire" in CHAMPS_CRITIQUES


def test_nouveau_cas_defaut():
    """Vérifie que chaque variable non renseignée est initialisée à 'inconnu'."""
    cas = nouveau_cas(temperature="normale")
    assert cas["temperature"] == "normale"
    assert cas["perte_conscience"] == "inconnu"
    assert cas["douleur"] == "inconnu"


# ===========================================================================
# 2. TESTS DU MOTEUR SYMBOLIQUE (RÔLE 2 - MÉTHODE 1)
# ===========================================================================

def test_regle_r1_perte_conscience():
    """Règle R1 (Priorité 100) : Perte de conscience = ORIENTATION_URGENTE."""
    cas = {"perte_conscience": "oui", "temperature": "normale"}
    res = evaluer_cas(cas)
    assert res.orientation == "ORIENTATION_URGENTE"
    assert res.regle_activee is not None
    assert res.regle_activee.id == "R1"


def test_regle_r5_saignement_important():
    """Règle R5 (Priorité 95) : Saignement important = ORIENTATION_URGENTE."""
    cas = {"saignement_important": "oui"}
    res = evaluer_cas(cas)
    assert res.orientation == "ORIENTATION_URGENTE"
    assert res.regle_activee is not None
    assert res.regle_activee.id == "R5"


def test_regle_r2_detresse_cardiorespiratoire():
    """Règle R2 (Priorité 90) : Douleur thoracique + Détresse respiratoire = ORIENTATION_URGENTE."""
    cas = {"douleur_thoracique": "oui", "difficulte_respiratoire": "oui"}
    res = evaluer_cas(cas)
    assert res.orientation == "ORIENTATION_URGENTE"
    assert res.regle_activee is not None
    assert res.regle_activee.id == "R2"


def test_regle_r3_temperature_et_duree():
    """Règle R3 (Priorité 50) : Fièvre + Durée longue = CONSULTATION_PRIORITAIRE."""
    cas = {
        "temperature": "elevee",
        "duree_symptomes": "longue",
        "perte_conscience": "non",
        "difficulte_respiratoire": "non",
        "douleur_thoracique": "non",
        "saignement_important": "non",
    }
    res = evaluer_cas(cas)
    assert res.orientation == "CONSULTATION_PRIORITAIRE"
    assert res.regle_activee is not None
    assert res.regle_activee.id == "R3"


def test_regle_r4_surveillance_benigne():
    """Règle R4 (Priorité 10) : Douleur faible, T° normale et aucun signe critique = SURVEILLANCE."""
    cas = {
        "douleur": "faible",
        "temperature": "normale",
        "duree_symptomes": "courte",
        "difficulte_respiratoire": "non",
        "douleur_thoracique": "non",
        "perte_conscience": "non",
        "saignement_important": "non",
    }
    res = evaluer_cas(cas)
    assert res.orientation == "SURVEILLANCE"
    assert res.regle_activee is not None
    assert res.regle_activee.id == "R4"


# ===========================================================================
# 3. TESTS DES IMPERFECTIONS (INCOMPLÉTUDE & CONTRADICTIONS)
# ===========================================================================

def test_incompletude_critique_demander_precisions():
    """Si des variables critiques sont 'inconnu' sans règle active -> DEMANDER_PRECISIONS."""
    cas = {"perte_conscience": "inconnu", "temperature": "inconnu"}
    res = evaluer_cas(cas)
    assert res.orientation == "DEMANDER_PRECISIONS"
    assert len(res.infos_manquantes) > 0


def test_inconnu_ne_peut_pas_declencher_surveillance():
    """Une règle rassurante exige des valeurs négatives explicites pour les champs critiques."""
    cas = {
        "douleur": "faible",
        "temperature": "normale",
        "duree_symptomes": "inconnu",
        "perte_conscience": "non",
        "saignement_important": "non",
        "difficulte_respiratoire": "non",
        "douleur_thoracique": "non",
    }
    assert evaluer_cas(cas).orientation == "DEMANDER_PRECISIONS"
    assert fusionner(cas).orientation == "DEMANDER_PRECISIONS"


def test_validation_ontologie():
    """Les valeurs hors ontologie sont refusées avant tout raisonnement."""
    try:
        valider_faits({"temperature": "tres_chaude"})
    except ValueError as erreur:
        assert "temperature" in str(erreur)
    else:
        raise AssertionError("Une valeur invalide a été acceptée")


def test_regles_declarees():
    """Les règles viennent du fichier de connaissances externe."""
    assert {regle.id for regle in REGLES} == {"R1", "R2", "R3", "R4", "R5"}


def test_distribution_probabiliste_somme_a_un():
    """Le modèle expose une distribution multiclasses cohérente."""
    resultat = evaluer_probabiliste({"temperature": "normale", "duree_symptomes": "courte"})
    assert abs(sum(resultat.probabilites_par_orientation.values()) - 1.0) < 1e-9


def test_contradiction_sans_regle_critique():
    """Contradiction non arbitrable automatiquement -> SURVEILLANCE_MANUELLE_REQUISE."""
    cas = {
        "symptomes_legers": "oui",
        "douleur": "faible",
        "douleur_thoracique": "oui",
        "difficulte_respiratoire": "non",
        "perte_conscience": "non",
        "saignement_important": "non",
        "temperature": "normale",
        "duree_symptomes": "courte",
    }
    res = evaluer_cas(cas)
    assert res.orientation == "SURVEILLANCE_MANUELLE_REQUISE"
    assert len(res.contradictions) > 0


# ===========================================================================
# 4. TESTS DU MODÈLE PROBABILISTE (RÔLE 3 - MÉTHODE 2)
# ===========================================================================

def test_sigmoide_bornes_et_monotonie():
    """Vérifie les propriétés mathématiques de la fonction logistique sigmoïde."""
    assert sigmoide(0.0) == 0.5
    assert 0.0 < sigmoide(-5.0) < 0.01
    assert 0.99 < sigmoide(5.0) < 1.0
    assert sigmoide(-2.0) < sigmoide(2.0)


def test_probabiliste_calcul_urgence():
    """Signe d'urgence majeure -> Score élevé et probabilité > 0.75."""
    cas = {"perte_conscience": "oui"}
    res = evaluer_probabiliste(cas)
    assert res.score > 1.5
    assert res.probabilite_urgence >= 0.75
    assert res.orientation == "ORIENTATION_URGENTE"


# ===========================================================================
# 5. TESTS DE L'INTÉGRATION HYBRIDE & CAS LIMITES (RÔLE 4)
# ===========================================================================

def test_fusion_priorite_securite_absolue():
    """Une règle urgente déclenchée ne doit JAMAIS être déclassée par le modèle probabiliste."""
    cas = {"perte_conscience": "oui", "douleur": "faible", "temperature": "normale"}
    dec = fusionner(cas)
    assert dec.orientation == "ORIENTATION_URGENTE"
    assert dec.source == "regles"


def test_cas_limite_c9_contradiction_avec_regle_urgente():
    """Cas C9 : 'symptômes légers' contredit 'perte de conscience' -> R1 prime par sécurité."""
    cas = {"symptomes_legers": "oui", "perte_conscience": "oui"}
    dec = fusionner(cas)
    assert dec.orientation == "ORIENTATION_URGENTE"
    assert len(dec.contradictions) > 0


def test_cas_limite_c10_delegation_probabiliste():
    """Cas C10 : Aucune règle activée mais risque continu élevé -> rehaussé en PRIORITAIRE."""
    cas = {
        "temperature": "normale",
        "duree_symptomes": "courte",
        "douleur": "moyen",
        "difficulte_respiratoire": "non",
        "douleur_thoracique": "non",
        "perte_conscience": "non",
        "saignement_important": "non",
        "fatigue_importante": "oui",
    }
    dec = fusionner(cas)
    assert dec.orientation == "CONSULTATION_PRIORITAIRE"
    assert dec.source == "probabiliste"


def test_cas_limite_c11_regle_urgente_maintien():
    """Cas C11 : Règle urgente active mais probabilité basse -> Urgence maintenue par sécurité."""
    cas = {
        "temperature": "normale",
        "duree_symptomes": "courte",
        "douleur": "faible",
        "perte_conscience": "oui",
    }
    dec = fusionner(cas)
    assert dec.orientation == "ORIENTATION_URGENTE"


# ===========================================================================
# 6. TESTS D'EXACTITUDE GLOBALE ET DE PERFORMANCE (RÔLE 5)
# ===========================================================================

def test_jeu_de_donnees_11_cas_reproductibilite():
    """Vérifie la reproductibilité et l'exactitude >= 90% sur le benchmark officiel."""
    chemin = Path(__file__).resolve().parent.parent / "data" / "cas_test.json"
    assert chemin.exists()

    with open(chemin, encoding="utf-8") as f:
        cas_liste = json.load(f)

    assert len(cas_liste) == 11
    reussites = 0
    t0 = time.perf_counter()

    for cas in cas_liste:
        dec = fusionner(cas["faits"])
        attendu = cas.get("decision_attendue")
        if attendu and attendu.split(" ")[0] in dec.orientation:
            reussites += 1

    duree_totale_ms = (time.perf_counter() - t0) * 1000
    temps_moyen_ms = duree_totale_ms / len(cas_liste)

    # 1. Exactitude >= 90% (10/11 cas conformes)
    assert reussites >= 10

    # 2. Performance : temps moyen largement inférieur à la limite de 1 ms
    assert temps_moyen_ms < 0.1


# ===========================================================================
# 7. TESTS DE L'API WEB FLASK
# ===========================================================================

def test_api_flask_endpoints():
    """Vérifie la conformité des routes REST pour l'IHM et l'intégration."""
    client = app.test_client()

    # 1. Page d'accueil statique
    r_index = client.get("/")
    assert r_index.status_code == 200

    # 2. Liste des cas de test
    r_cas = client.get("/api/cas_test")
    assert r_cas.status_code == 200
    assert len(r_cas.get_json()) == 11

    # 3. Évaluation d'un cas clinique
    r_eval = client.post("/api/evaluer", json={"faits": {"perte_conscience": "oui"}})
    assert r_eval.status_code == 200
    data = r_eval.get_json()
    assert data["orientation"] == "ORIENTATION_URGENTE"
    assert "config_a" in data
    assert "config_b" in data
    assert "etat_incertitude" in data
    assert "temps_calcul_ms" in data

    # 4. Benchmark complet
    r_bench = client.get("/api/benchmark")
    assert r_bench.status_code == 200
    bench_data = r_bench.get_json()
    assert bench_data["total_cas"] == 11
    assert bench_data["synthese"]["exactitude_config_b"] >= 90.0

    r_invalid = client.post("/api/evaluer", json={"faits": {"temperature": "invalid"}})
    assert r_invalid.status_code == 422

    r_llm = client.post("/api/extraire-faits", json={"description": "test"})
    assert r_llm.status_code in (200, 503)
