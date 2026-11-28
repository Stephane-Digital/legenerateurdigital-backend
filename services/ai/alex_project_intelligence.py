"""S3.C.3 — reconnaissance prudente du projet pour la conversation libre.

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
        r"je choisis|je change|je me lance|je vais|je decide|je compte|je souhaite devenir)\b", msg
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
    if previous and previous != kind and not (kind == "lgd_ambassador" and re.search(r"\b(je souhaite|je veux|je voudrais|j\'aimerais) devenir (?:un |une )?(?:ambassadeur|ambassadrice) lgd\b", msg)) and not re.search(r"\b(je change|je choisis plutot|nouveau projet|a la place|desormais)\b", msg):
        return {}

    return {
        "project_type": kind,
        "business_mode": "affiliate" if kind in ("affiliate", "lgd_ambassador") else "digital_product",
        "project_label": PROJECT_LABELS[kind],
        "project_status": "INTENT_DETECTED",
        "source": "alex_conversation_s3c3",
    }


def project_guidance(project: Dict[str, Any] | None) -> str:
    """Instructions ciblées, injectées seulement dans le mode conversation."""
    project = project if isinstance(project, dict) else {}
    kind = str(project.get("project_type") or "")
    if project.get("parcours") == "objectif_personnalise":
        return "\nOBJECTIF PERSONNALISÉ : respecte le projet libre."
    if not kind and project.get("parcours") == "affiliation":
        kind = "affiliate"
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
            "\nS3.C.3 — MENTOR AMBASSADEUR LGD : ces règles priment sur le plan marketing générique. "
            "Pour une demande de démarrage, explique brièvement : inscription Ambassadeur gratuite, "
            "aucun abonnement LGD obligatoire, 60 % de commission récurrente sur abonnements éligibles, "
            "validation après 30 jours actifs, aucun revenu garanti. Essai LGD 7 jours sans carte ni engagement. "
            "Utilise les réponses FormAction disponibles sans les redemander. "
            "Première mission si inscription ou lien non confirmé : vérifier l'inscription au programme "
            "et obtenir son lien personnel via le Centre de Croissance Ambassadeur, avec identifiant Systeme.io. "
            "Page programme : https://legenerateurdigital.systeme.io/affiliation-lgd ; "
            "lien essai : https://legenerateurdigital.systeme.io/trial?sa=ID (ID à remplacer, jamais inventer). "
            "Puis, seulement selon les acquis déclarés : identifier des prospects pertinents, préparer un message "
            "honnête, créer un contenu avec l'Éditeur Intelligent si utile, présenter l'essai, suivre les retours. "
            "Ne rends pas obligatoire une audience, une nouvelle niche, plusieurs réseaux ou une liste email. "
            "Pour le coaching progressif, donne UNE mission mesurable adaptée au temps disponible, "
            "avec résultat attendu et une question de validation. Ne suppose jamais une étape accomplie. "
            "Si un plan complet ou un livrable est demandé, fournis-le sans bloquer. "
            "Ne prétends jamais créer un compte, activer un lien ou consulter les ventes."
        )
    return ""


def explicit_project_switch(message: str, current: Dict[str, Any], patch: Dict[str, str]) -> bool:
    """Explicit switch only; a new title alone may be a revision."""
    msg = _normalized(message.strip())
    if not current:
        return False
    if patch.get("project_type") and patch["project_type"] != current.get("project_type"):
        return True
    return bool(re.search(
        r"\b(?:je change de projet|je passe a un autre projet|je commence un nouveau projet|"
        r"je veux (?:creer|ecrire|rediger) (?:un autre|un nouvel|un nouveau) (?:ebook|e-book|produit digital)|"
        r"je souhaite (?:creer|ecrire|rediger) (?:un autre|un nouvel|un nouveau) (?:ebook|e-book|produit digital))\b", msg
    ))
