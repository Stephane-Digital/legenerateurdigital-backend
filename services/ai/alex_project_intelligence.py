"""S3.C.2 — reconnaissance prudente du projet pour la conversation libre.

Pas d'appel IA, pas de quota, pas de DB. Ne persiste que les intentions explicites.
"""
from __future__ import annotations

import re
from typing import Any, Dict

PROJECT_LABELS = {
    "ebook": "Création d'ebook",
    "digital_product": "Création de produit digital",
    "affiliate": "Affiliation",
    "lgd_ambassador": "Programme Ambassadeur LGD",
}


def _normalized(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def detect_explicit_project(message: str, current: Dict[str, Any] | None = None) -> Dict[str, str]:
    """Renvoie un patch minimal uniquement quand un projet est clairement choisi.

    Une simple question (« c'est quoi l'affiliation ? ») n'est PAS un choix de projet.
    Un projet existant n'est jamais écrasé par une simple mention d'un autre sujet.
    """
    msg = _normalized(message.strip())
    existing = current if isinstance(current, dict) else {}
    explicit = bool(re.search(
        r"\b(je veux|je souhaite|j'aimerais|je voudrais|mon projet est|mon objectif est|"
        r"je choisis|je me lance|je vais|je decide|je compte|je souhaite devenir)\b", msg
    ))
    if not explicit:
        return {}

    if "objectif_personnalise" in msg or existing.get("parcours") == "objectif_personnalise":
        return {}

    kind = ""
    if re.search(r"\b(ambassadeur|ambassadrice)\b", msg) and "lgd" in msg:
        kind = "lgd_ambassador"
    elif any(term in msg for term in ("ebook", "e-book", "livre numerique")):
        kind = "ebook"
    elif any(term in msg for term in ("produit digital", "produit numerique", "formation digitale")):
        kind = "digital_product"
    elif any(term in msg for term in ("affiliation", "affilie", "commission", "recommander une formation")):
        kind = "affiliate"
    if not kind:
        return {}

    previous = str(existing.get("project_type") or "")
    if previous and previous != kind and not re.search(r"\b(je change|je choisis plutot|nouveau projet|a la place|desormais)\b", msg):
        return {}

    return {
        "project_type": kind,
        "business_mode": "affiliate" if kind in ("affiliate", "lgd_ambassador") else "digital_product",
        "project_label": PROJECT_LABELS[kind],
        "project_status": "INTENT_DETECTED",
        "source": "alex_conversation_s3c2",
    }


def project_guidance(project: Dict[str, Any] | None) -> str:
    """Instructions ciblées, injectées seulement dans le mode conversation."""
    project = project if isinstance(project, dict) else {}
    kind = str(project.get("project_type") or "")
    if kind == "ebook":
        return (
            "\nPROJET CONFIRMÉ : EBOOK. Aide à définir lecteur, problème, promesse, "
            "sommaire, rédaction chapitre par chapitre, révision, mise en page et diffusion. "
            "Ne présume pas que l'ebook doit être vendu : demande seulement si cela devient utile. "
            "Quand l'utilisateur demande un chapitre, rédige-le concrètement."
        )
    if kind == "digital_product":
        return (
            "\nPROJET CONFIRMÉ : PRODUIT DIGITAL. Clarifie l'offre, l'audience, le problème, "
            "le format, le prototype, la validation de demande, la mise en vente et la communication. "
            "Ne force pas un tunnel MRR. Donne une seule action prioritaire."
        )
    if kind == "affiliate":
        return (
            "\nPROJET CONFIRMÉ : AFFILIATION. Vérifie l'offre choisie, l'audience, les règles "
            "de promotion, les contenus utiles, les conversations, le suivi et les conversions. "
            "Tu peux proposer le Programme Ambassadeur LGD comme alternative facultative."
        )
    if kind == "lgd_ambassador":
        return (
            "\nPROJET CONFIRMÉ : AMBASSADEUR LGD. Accompagne étape par étape : "
            "1) vérifier l'inscription gratuite Systeme.io et le lien ?sa=ID ; "
            "2) identifier l'audience et son problème ; 3) bâtir un message de recommandation honnête ; "
            "4) créer un premier contenu avec l'Éditeur Intelligent ; 5) orienter vers l'essai LGD "
            "de 7 jours sans carte bancaire ; 6) suivre les conversations et les résultats réels ; "
            "7) ajuster selon les retours. Ne prétends pas activer un compte ou mesurer les ventes. "
            "Commission : 60 % récurrente sur abonnements éligibles, validée après 30 jours "
            "d'abonnement actif, sans revenu garanti. Une mission mesurable à la fois."
        )
    return ""
