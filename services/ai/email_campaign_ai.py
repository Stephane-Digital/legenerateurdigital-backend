from __future__ import annotations

import random
import re
import uuid
from typing import Any, Dict, List

from services.content_engine_service import generate_ai_text

EMAIL_TYPE_PATTERNS = {
    7: ["nurture", "nurture", "objection", "vente", "nurture", "relance", "vente"],
    14: [
        "nurture",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "vente",
    ],
    30: [
        "nurture",
        "nurture",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "nurture",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "nurture",
        "objection",
        "vente",
        "nurture",
        "relance",
        "vente",
        "vente",
        "vente",
        "vente",
    ],
}

ANGLE_BANK = {
    "nurture": [
        "micro-histoire personnelle",
        "erreur fréquente de l'audience",
        "déclic pédagogique simple",
        "croyance à remplacer",
        "petit exercice concret à faire aujourd'hui",
        "question qui ouvre une prise de conscience",
        "mythe à déconstruire",
    ],
    "objection": [
        "manque de temps",
        "peur de ne pas réussir",
        "impression que c'est trop tard",
        "doute sur la valeur réelle de l'offre",
        "peur de se disperser",
        "peur de perdre de l'argent",
    ],
    "relance": [
        "rappel calme mais ferme",
        "urgence douce",
        "opportunité manquée si on attend",
        "décision simple aujourd'hui",
        "relance avec bénéfice concret",
        "mini checklist avant passage à l'action",
    ],
    "vente": [
        "bénéfice principal",
        "projection avant/après",
        "preuve sociale crédible",
        "offre + valeur perçue",
        "prise de décision immédiate",
        "comparaison avec le statu quo",
    ],
}

CTA_VARIANTS_V3 = [
    "Découvrir maintenant",
    "Voir comment ça fonctionne",
    "Accéder à la méthode",
    "Passer à l’action aujourd’hui",
    "Commencer simplement",
]

VIRAL_ANGLE_MODES_V3 = [
    "mythe à casser",
    "erreur fréquente",
    "avant/après",
    "objection retournée",
    "micro-story",
    "déclic pédagogique",
    "urgence douce",
    "comparaison avec le statu quo",
]

SECTION_RE = {
    "subject": re.compile(r"^\s*SUJET\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
    "preheader": re.compile(r"^\s*(?:PREHEADER|PRÉHEADER)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
    "body": re.compile(
        r"(?:^|\n)\s*(?:CORPS|BODY)\s*:\s*(.+?)(?=\n\s*CTA\s*:|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    "cta": re.compile(r"(?:^|\n)\s*CTA\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
}

BAD_TEMPLATE_MARKERS = [
    "🎁 ce que je te propose",
    "💡 ce qui change vraiment",
    "alex ia",
    "ton coach lgd",
    "aider prospects concernés",
    "prospects concernés par l’objectif",
    "laisser l’ia faire le plus gros du travail",
    "clarifier ton message",
    "structurer ton marketing digital",
]

DAY_ARCHETYPES = {
    1: {
        "role": "prise de conscience",
        "subject": "Tu n’as pas un problème d’information",
        "preheader": "Le vrai blocage est ailleurs.",
    },
    2: {
        "role": "erreur invisible",
        "subject": "L’erreur qui te garde bloqué",
        "preheader": "Apprendre encore ne suffit plus.",
    },
    3: {
        "role": "objection / peur",
        "subject": "Et si ce n’était pas trop tard ?",
        "preheader": "Le bon moment n’arrive pas tout seul.",
    },
    4: {
        "role": "solution claire",
        "subject": "Le plus simple pour avancer",
        "preheader": "Une offre simple vaut mieux qu’un plan parfait.",
    },
    5: {
        "role": "projection concrète",
        "subject": "Imagine dans 7 jours",
        "preheader": "Pas un rêve. Une prochaine étape claire.",
    },
    6: {
        "role": "relance / décision",
        "subject": "La checklist avant de te lancer",
        "preheader": "Quatre points pour sortir du flou.",
    },
    7: {
        "role": "CTA final",
        "subject": "Tu peux continuer à apprendre… ou commencer",
        "preheader": "La décision la plus rentable est souvent la plus simple.",
    },
}


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return text or fallback


def _normalize_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\r", "")
    text = text.replace("**", "")
    text = text.replace("CTA :", "")
    text = text.replace("CTA:", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _keep_only_first_email(raw: str) -> str:
    src = _normalize_text(raw)
    matches = list(re.finditer(r"(?im)^\s*SUJET\s*:", src))
    if len(matches) > 1:
        src = src[matches[0].start() : matches[1].start()]
    return src.strip()


def _remove_duplicate_halves(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""

    lines = [line.rstrip() for line in cleaned.split("\n")]
    if len(lines) >= 8 and len(lines) % 2 == 0:
        mid = len(lines) // 2
        first = "\n".join(lines[:mid]).strip()
        second = "\n".join(lines[mid:]).strip()
        if first and first == second:
            return first

    parts = [part.strip() for part in re.split(r"\n{2,}", cleaned) if part.strip()]
    if len(parts) >= 4 and len(parts) % 2 == 0:
        mid = len(parts) // 2
        first = "\n\n".join(parts[:mid]).strip()
        second = "\n\n".join(parts[mid:]).strip()
        if first and first == second:
            return first

    return cleaned


def _sanitize_body(body: str) -> str:
    cleaned = _remove_duplicate_halves(body)

    cleaned = re.split(r"(?im)^\s*SUJET\s*:", cleaned)[0].strip()
    cleaned = re.split(r"(?im)^\s*(?:PREHEADER|PRÉHEADER)\s*:", cleaned)[0].strip()

    # Supprime les signatures faibles ou automatiques qui cassent la tension de vente.
    cleaned = re.sub(r"(?is)\n*à\s+bientôt(?:\s+peut-être)?[\s\S]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?is)\n*à\s+très\s+vite[\s\S]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?is)\n*Alex IA\s*🤖[\s\S]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?is)\n*Ton Coach LGD[\s\S]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?is)\n*Le Générateur Digital\s*$", "", cleaned).strip()
    cleaned = re.sub(r"(?is)\n*LGD\s*$", "", cleaned).strip()

    cleaned = re.sub(r"(?im)^\s*👉.*$", "", cleaned).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_cta_from_body(body: str, cta: str) -> str:
    cleaned = _sanitize_body(body)
    clean_cta = _normalize_text(cta).strip()

    if clean_cta:
        escaped = re.escape(clean_cta)
        cleaned = re.sub(rf"(?im)^\s*👉?\s*{escaped}\s*[.!?]?\s*$", "", cleaned).strip()
        cleaned = re.sub(rf"(?is)\n+\s*👉?\s*{escaped}\s*[.!?]?\s*$", "", cleaned).strip()

    # Retire les CTA génériques fréquents si le modèle les ajoute dans le corps.
    generic_cta_patterns = [
        r"(?im)^\s*👉?\s*téléchargez votre guide gratuit maintenant\s*!?\s*$",
        r"(?im)^\s*👉?\s*découvrez comment commencer dès aujourd'hui\s*!?\s*$",
        r"(?im)^\s*👉?\s*inscrivez-vous dès maintenant pour découvrir notre méthode\s*!?\s*$",
        r"(?im)^\s*👉?\s*passez à l’action maintenant\s*!?\s*$",
        r"(?im)^\s*👉?\s*commencez maintenant\s*!?\s*$",
    ]
    for pattern in generic_cta_patterns:
        cleaned = re.sub(pattern, "", cleaned).strip()

    cleaned = re.sub(r"(?im)^\s*👉.*$", "", cleaned).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _is_bad_template(text: str) -> bool:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return True

    score = sum(1 for marker in BAD_TEMPLATE_MARKERS if marker in normalized)

    # Tolérance volontaire : un seul marqueur isolé ne doit plus bloquer une bonne sortie IA.
    return score >= 2


def _pattern_for_days(days: int) -> List[str]:
    if days in EMAIL_TYPE_PATTERNS:
        return EMAIL_TYPE_PATTERNS[days]
    if days <= 7:
        base = EMAIL_TYPE_PATTERNS[7]
    elif days <= 14:
        base = EMAIL_TYPE_PATTERNS[14]
    else:
        base = EMAIL_TYPE_PATTERNS[30]
    return [base[i % len(base)] for i in range(days)]


def _extract_sections(text: str) -> Dict[str, str]:
    src = _keep_only_first_email(text or "")
    out: Dict[str, str] = {}
    for key, pattern in SECTION_RE.items():
        match = pattern.search(src)
        if match:
            out[key] = match.group(1).strip()
    if "body" in out:
        out["body"] = _sanitize_body(out["body"])
    if "cta" in out:
        out["cta"] = out["cta"].split("\n")[0].strip()
    return out


def _v3_context_block(payload: Any) -> str:
    niche = _clean_text(_get(payload, "niche"), "")
    audience = _clean_text(_get(payload, "target_audience"), "")
    offer = _clean_text(_get(payload, "offer_name"), "")
    tone = _clean_text(_get(payload, "tone"), "premium")
    level = _clean_text(_get(payload, "level"), "")
    if not level:
        raw = f"{niche} {audience} {offer}".lower()
        if any(w in raw for w in ["débutant", "débutants", "simple", "lancer"]):
            level = "beginner"
        elif any(w in raw for w in ["expert", "avancé", "scaling", "b2b", "premium"]):
            level = "advanced"
        else:
            level = "intermediate"

    return f"""
CONTEXTE PERSONNALISATION V3
- Niche: {niche or "à inférer"}
- Audience: {audience or "à inférer"}
- Offre: {offer or "à inférer"}
- Ton préféré: {tone}
- Niveau détecté: {level}
- Règle: adapte la pédagogie, la densité et le vocabulaire à ce niveau.
""".strip()


def _cta_variant(base_cta: Any, day: int) -> str:
    """
    Ne modifie PAS le CTA généré par l’IA.
    On fait confiance au prompt LGD.
    """
    return _clean_text(base_cta, "")

def _fallback_email(
    *,
    day: int,
    email_type: str,
    offer_name: str,
    target_audience: str,
    main_promise: str,
    main_objective: str,
    primary_cta: str,
    sender_name: str,
    tone: str,
) -> Dict[str, Any]:
    archetype = DAY_ARCHETYPES.get(day, DAY_ARCHETYPES[((day - 1) % 7) + 1])

    clean_offer = _clean_text(offer_name, "votre offre")
    clean_audience = _clean_text(target_audience, "les personnes qui veulent avancer")
    clean_promise = _clean_text(main_promise, "obtenir un résultat concret")
    clean_objective = _clean_text(main_objective, "passer à l’action")
    clean_cta = _clean_text(primary_cta, "")

    if day == 1:
        body = f"""Bonjour {{{prenom}}},

Tu as peut-être déjà vécu ce moment étrange : tu sais que tu veux avancer, tu as lu des conseils, regardé des vidéos, noté des idées… mais rien ne sort vraiment.

Ce n’est pas parce que tu manques d’envie.

Souvent, le vrai problème, c’est que l’apprentissage donne une impression de progression alors qu’il ne crée pas encore de résultat.

Pour {clean_audience}, le premier déclic est simple : arrêter de chercher l’idée parfaite et choisir une action assez claire pour être faite aujourd’hui.

Avec {clean_offer}, l’objectif est de transformer ce flou en prochaine étape concrète : une offre plus claire, un message plus simple, et un chemin qui pousse enfin vers {clean_objective.lower()}.

Tu n’as pas besoin de tout maîtriser pour commencer. Tu as besoin d’un premier pas visible."""
    elif day == 2:
        body = f"""Bonjour {{{prenom}}},

L’erreur la plus fréquente, ce n’est pas de ne rien faire.

C’est de confondre préparation et progression.

Tu peux passer des semaines à améliorer ton idée, comparer les stratégies, demander des avis, revoir ton positionnement… et pourtant rester exactement au même point.

Le vrai signal que tu avances, ce n’est pas le nombre de choses que tu comprends. C’est ce que tu mets devant quelqu’un de réel : une offre, un message, une page, un email, une proposition.

Si ton objectif est {clean_objective.lower()}, il faut réduire le bruit et créer une première version vendable.

Pas parfaite.

Vendable.

C’est là que {clean_offer} devient utile : t’aider à sortir de la théorie et à construire quelque chose que ton audience peut comprendre, désirer et choisir."""
    elif day == 3:
        body = f"""Bonjour {{{prenom}}},

Tu peux avoir l’impression qu’il est trop tard.

Trop de monde parle déjà de business en ligne. Trop d’outils existent. Trop de personnes semblent plus avancées.

Mais ce raisonnement oublie une chose : les gens n’achètent pas parce qu’une offre est arrivée en premier. Ils achètent parce qu’elle arrive au bon moment, avec le bon message, et qu’elle répond clairement à leur problème.

Ton retard apparent peut même devenir un avantage si tu construis quelque chose de plus simple, plus humain et plus direct.

Pour {clean_audience}, la question n’est pas : “est-ce que tout existe déjà ?”

La vraie question est : “est-ce que quelqu’un peut m’aider à passer de la confusion à une action claire ?”

C’est précisément le rôle de {clean_offer} : raccourcir le chemin entre l’idée et l’exécution."""
    elif day == 4:
        body = f"""Bonjour {{{prenom}}},

La solution n’est pas de créer plus.

Ce n’est pas non plus d’ajouter encore un outil, une formation ou une stratégie à ton bureau mental déjà saturé.

La solution, c’est de simplifier le système.

Une offre claire.

Un message compréhensible.

Un angle qui parle à une vraie douleur.

Une action qui rapproche de {clean_promise.lower()}.

C’est ce que {clean_offer} doit permettre : prendre ce que tu as déjà en tête et le transformer en quelque chose d’utilisable pour vendre, communiquer et avancer.

Le but n’est pas de devenir parfait.

Le but est de créer une version assez claire pour être testée, améliorée, puis vendue."""
    elif day == 5:
        body = f"""Bonjour {{{prenom}}},

Imagine dans 7 jours.

Pas dans six mois. Pas quand tout sera parfait. Juste dans 7 jours.

Tu pourrais avoir une première offre clarifiée, un message plus net, une séquence email prête à être testée, ou une page simple qui explique enfin ce que tu proposes.

Ce changement ne vient pas d’un énorme plan.

Il vient d’une décision : arrêter de tout garder dans ta tête.

Quand ton idée devient visible, tu peux l’améliorer. Quand elle reste floue, tu ne peux que douter.

Pour {clean_audience}, {clean_offer} sert justement à ça : transformer l’intention en matière concrète.

Et une fois que c’est concret, tu n’es plus dans “un jour peut-être”.

Tu es déjà en train d’avancer."""
    elif day == 6:
        body = f"""Bonjour {{{prenom}}},

Avant de repousser encore, vérifie simplement ces quatre points.

1. Est-ce que ton offre peut être expliquée en une phrase claire ?

2. Est-ce que ton audience comprend immédiatement ce qu’elle gagne ?

3. Est-ce que ton message parle d’un problème réel, pas d’une idée vague ?

4. Est-ce que tu as une prochaine action concrète à faire aujourd’hui ?

Si une seule réponse est floue, ce n’est pas grave.

C’est même exactement le signe qu’il faut structurer plutôt que continuer à réfléchir seul.

{clean_offer} est conçu pour t’aider à remettre de l’ordre : clarifier, formuler, créer, puis passer à l’action.

Pas pour faire joli.

Pour avancer."""
    else:
        body = f"""Bonjour {{{prenom}}},

Tu peux continuer à apprendre.

Tu peux aussi continuer à comparer les outils, chercher la meilleure méthode, attendre le bon moment, ou te dire que tu commenceras quand ce sera plus clair.

Mais soyons honnêtes : si cette logique avait suffi, tu aurais déjà lancé quelque chose.

La clarté ne tombe pas du ciel. Elle se construit en mettant ton idée en mouvement.

Si ton objectif est vraiment {clean_objective.lower()}, alors la prochaine étape n’est pas de consommer plus de contenu.

C’est de créer une première version claire de ton offre et de la confronter au réel.

{clean_offer} est là pour ça : t’aider à passer du flou à une action structurée, sans perdre ton côté humain.

La décision est simple.

Rester dans la préparation.

Ou commencer maintenant."""

    return {
        "day": day,
        "email_type": email_type,
        "subject": archetype["subject"],
        "preheader": archetype["preheader"],
        "body": _sanitize_body(body),
        "cta": clean_cta,
    }


def _looks_too_similar(emails: List[Dict[str, Any]]) -> bool:
    if len(emails) < 2:
        return False
    subjects = [(_clean_text(e.get("subject"), "")).lower() for e in emails]
    prefixes = [(_clean_text(e.get("body"), "")[:260]).lower() for e in emails]
    repeated_subjects = len(set(subjects)) <= max(1, len(subjects) // 3)
    repeated_prefixes = len(set(prefixes)) <= max(1, len(prefixes) // 3)
    bad_template = any(_is_bad_template(str(e.get("body") or "")) for e in emails)
    return repeated_subjects or repeated_prefixes or bad_template


def _build_prompt(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> str:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    target_audience = _clean_text(_get(payload, "target_audience"), "votre audience")
    main_promise = _clean_text(_get(payload, "main_promise"), "atteindre un meilleur résultat")
    main_objective = _clean_text(_get(payload, "main_objective"), "passer à l'action")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "")
    tone = _clean_text(_get(payload, "tone"), "premium")
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    campaign_type = _clean_text(_get(payload, "campaign_type"), "vente")
    campaign_name = _clean_text(_get(payload, "name"), "Campagne E-mailing IA")
    product_context = _clean_text(_get(payload, "product_context"), "")
    objection = _clean_text(_get(payload, "main_objection"), "")
    proof = _clean_text(_get(payload, "proof"), "")
    niche = _clean_text(_get(payload, "niche"), "")
    archetype = DAY_ARCHETYPES.get(day, DAY_ARCHETYPES[((day - 1) % 7) + 1])

    return f"""
Tu es Emailing IA LGD.

Tu écris des emails de vente humains, directs et alignés avec une stratégie CMO.
Tu n’écris pas des emails génériques.
Tu n’écris pas du développement personnel vague.
Tu écris pour vendre une offre précise à une cible précise.
Tu écris comme si tu envoyais ces emails depuis un iPhone.

MISSION
Écris EXACTEMENT UN SEUL email pour le jour {day} de la séquence.
Cet appel correspond uniquement à CE jour.
Ne fais jamais référence aux autres emails.
Ne génère jamais plusieurs versions.

CONTEXTE STRATÉGIQUE CMO — PRIORITÉ ABSOLUE

* Campagne : {campaign_name}
* Type de campagne : {campaign_type}
* Jour : {day}
* Rôle du jour : {archetype["role"]}
* Type d’email : {email_type}
* Angle obligatoire : {angle}
* Offre à vendre : {offer_name}
* Audience cible : {target_audience}
* Niche : {niche or "non précisée"}
* Promesse principale : {main_promise}
* Objectif business : {main_objective}
* Objection / blocage principal : {objection or "à inférer depuis l’objectif"}
* Preuve / crédibilité : {proof or "non précisée, rester crédible"}
* Contexte produit : {product_context or "non précisé"}
* CTA principal fourni : {primary_cta or "à reformuler naturellement"}
* Ton souhaité : {tone}
* Expéditeur : {sender_name}
* Variation anti-répétition : {nonce}

RÈGLE CMO NON NÉGOCIABLE
Chaque email doit utiliser clairement :

1. l’offre : {offer_name}
2. la cible : {target_audience}
3. la promesse : {main_promise}
4. l’objection : {objection or "à inférer"}
5. l’angle du jour : {angle}

Si l’email peut fonctionner pour n’importe quelle offre, il est mauvais.
Si l’email parle surtout de motivation, procrastination ou peur sans lien direct avec l’offre, il est mauvais.
Si l’offre n’est pas identifiable dans le corps, il est mauvais.

BLOC CRITIQUE — DIFFÉRENCIATION LGD (OBLIGATOIRE)

Tu dois rendre Le Générateur Digital CONCRET.

Interdit de dire :

* “outil puissant”
* “accompagnement structuré”
* “solution complète”

Obligation d’expliquer concrètement ce que fait LGD dans la vraie vie :

Exemples attendus :

* t’aider à savoir quoi faire chaque jour
* transformer une idée en contenu prêt à publier
* t’éviter de réfléchir pendant des heures
* te guider étape par étape
* t’empêcher de te disperser
* te faire passer à l’action même quand tu bloques

Si LGD reste flou → l’email est mauvais.

BLOC PSYCHOLOGIQUE (OBLIGATOIRE)

Tu dois attaquer directement la vraie cause du blocage :

Ce n’est PAS :

* un manque de motivation

C’est :

* un manque de structure
* une surcharge d’informations
* une incapacité à passer à l’action

Tu dois le dire clairement.

BLOC RUPTURE (OBLIGATOIRE)

Chaque email doit contenir une phrase qui casse une croyance.

Exemples d’esprit :

* “le problème, ce n’est pas…”
* “tu crois que… mais en réalité…”
* “ce n’est pas ça qui te bloque”

Sans rupture → email trop faible.

BLOC VARIATION FORCÉE (OBLIGATOIRE)

Chaque email doit être différent.

Interdit de répéter :

* le même problème
* la même explication
* la même mécanique

Variation attendue :

Jour 1 : choc / prise de conscience brutale
Jour 2 : erreur précise que la cible fait
Jour 3 : peur réelle / objection forte
Jour 4 : démonstration concrète de LGD
Jour 5 : projection détaillée (scène réelle)
Jour 6 : simplification extrême (décision facile)
Jour 7 : tension + urgence douce

Si 2 emails se ressemblent → la séquence est mauvaise.

BLOC RÉALITÉ (OBLIGATOIRE)

Tu dois montrer des situations réelles :

* ouvrir une formation et ne rien appliquer
* prendre des notes sans jamais agir
* changer de stratégie toutes les semaines
* passer des heures à réfléchir sans publier
* commencer sans finir

Sans ça → email trop générique.

BLOC IMPACT (OBLIGATOIRE)

Chaque email doit contenir au moins une phrase forte.

Exemples d’esprit :

* “tu ne manques pas d’envie, tu manques de direction”
* “tu apprends plus que tu n’agis”
* “tu sais déjà trop de choses… mais tu ne fais rien”

Sans phrase forte → email oubliable.

STYLE LGD

* Phrases courtes.
* Ton humain.
* Écriture directe.
* Pas de blabla marketing.
* Pas de promesse irréaliste.
* Pas de fausse preuve.
* Pas de ton corporate.
* Pas de formule IA reconnaissable.
* Respiration visuelle obligatoire.
* Maximum 3 lignes par bloc.
* Tu peux confronter, mais toujours en lien avec l’offre.

PRONOM OBLIGATOIRE

Tu dois choisir un seul pronom pour tout l’email :

* soit TU
* soit VOUS

Par défaut : TU

Interdit de mélanger les deux.

Si un mélange est détecté → l’email est mauvais → recommence.

Tu parles comme à une seule personne.
Jamais comme à un groupe.

Ton email doit donner l’impression d’un message personnel écrit depuis un iPhone.

Chaque email doit être écrit différemment dans son rythme et sa structure.
Interdit de reproduire la même mécanique d’un email à l’autre.

STRUCTURE INVISIBLE (RENFORCÉE)

1. Hook direct lié au blocage ou à l’offre.
2. Identification très précise (la personne se reconnaît immédiatement)
3. Problème réel (ce qui la bloque VRAIMENT)
4. Rupture mentale (changement de perception)
5. Solution concrète avec LGD
6. Projection réaliste (résultat atteignable)
7. CTA naturel

Ne nomme jamais cette structure.

INTERDIT

* “Imagine”
* “Imagine un instant”
* “Chaque jour”
* “Tu sais quoi”
* “À bientôt”
* “À très vite”
* signature dans le corps
* ligne commençant par 👉 dans le corps
* CTA commercial agressif
* “réserve”
* “planifie”
* “inscris-toi”
* “clique”
* “découvre”
* “passe à l’action”
* “commence maintenant”

CTA
Le CTA doit être une pensée courte, pas un bouton de vente.
Il doit être différent selon le jour.
Il doit rester cohérent avec l’email.
Il doit donner une sensation de décision personnelle.

FORMAT STRICT
SUJET: ...
PREHEADER: ...
CORPS:
Bonjour {{{{prenom}}}},

...
CTA: ...

RAPPEL FINAL
Après la ligne CTA, tu t’arrêtes.
Tu n’ajoutes rien.
""".strip()



def _generate_one_email(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> Dict[str, Any]:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "Passez à l'action maintenant")
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    tone = _clean_text(_get(payload, "tone"), "premium")

    raw = generate_ai_text(
    prompt=_build_prompt(
        payload=payload,
        day=day,
        email_type=email_type,
        angle=angle,
        nonce=nonce
    ),
    tone=tone,
    language="fr",

    # 🔥 COPYWRITER ELITE SETTINGS
    temperature=0.82,
    top_p=0.9,
    frequency_penalty=0.4,
    presence_penalty=0.3
)
    parts = _extract_sections(str(raw))
    cta = _clean_text(parts.get("cta"), "")
    body = _strip_cta_from_body(_clean_text(parts.get("body"), ""), cta)

    if _is_bad_template(body):
        # Filtre soft : on nettoie sans bloquer une génération IA exploitable.
        body = _sanitize_body(body)

    return {
        "day": day,
        "email_type": email_type,
        "subject": _clean_text(parts.get("subject"), f"Jour {day} — {offer_name}"),
        "preheader": _clean_text(parts.get("preheader"), offer_name),
        "body": _clean_text(body, ""),
        "cta": cta,
    }


def _dedupe_final_emails(emails: List[Dict[str, Any]], payload: Any, email_types: List[str]) -> List[Dict[str, Any]]:
    clean_emails: List[Dict[str, Any]] = []
    seen_subjects: set[str] = set()
    seen_bodies: set[str] = set()

    for index, email in enumerate(emails):
        day = int(email.get("day") or index + 1)
        subject_key = re.sub(r"\s+", " ", _clean_text(email.get("subject"), "").lower()).strip()
        body_key = re.sub(r"\s+", " ", _clean_text(email.get("body"), "").lower()).strip()[:360]

        if not body_key:
            raise ValueError(f"Email IA jour {day} vide : génération live annulée.")

        if subject_key in seen_subjects:
            raise ValueError(f"Email IA jour {day} rejeté : sujet trop similaire.")

        if body_key in seen_bodies:
            raise ValueError(f"Email IA jour {day} rejeté : corps trop similaire.")

        if _is_bad_template(str(email.get("body") or "")):
            raise ValueError(f"Email IA jour {day} rejeté : ancien template détecté.")

        fallback_cta_pool = [
            "personne ne va le faire à ta place",
            "tu peux continuer… ou changer",
            "rien ne changera si tu ne changes rien",
            "tu sais déjà ce que tu dois faire",
            "ne laisse pas ça redevenir une idée",
            "maintenant tu sais",
        ]

        email["cta"] = _clean_text(email.get("cta"), "") or fallback_cta_pool[(day - 1) % len(fallback_cta_pool)]

        seen_subjects.add(subject_key)
        seen_bodies.add(body_key)
        clean_emails.append(email)

    return clean_emails


def generate_email_campaign_sequence(payload: Any) -> Dict[str, Any]:
    campaign_name = _clean_text(_get(payload, "name"), "Campagne E-mailing IA")
    campaign_type = _clean_text(_get(payload, "campaign_type"), "vente")
    duration_days = int(_get(payload, "duration_days", 7) or 7)
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    email_types = _pattern_for_days(duration_days)

    base_nonce = f"{uuid.uuid4().hex[:8]}-{random.randint(1000, 9999)}"

    def generate_live_pass(pass_name: str, angle_offset: int) -> List[Dict[str, Any]]:
        generated: List[Dict[str, Any]] = []

        for index in range(duration_days):
            day = index + 1
            email_type = email_types[index]
            angle_options = ANGLE_BANK.get(email_type, ["angle simple"])
            angle = angle_options[(index + angle_offset) % len(angle_options)]

            generated.append(
                _generate_one_email(
                    payload=payload,
                    day=day,
                    email_type=email_type,
                    angle=angle,
                    nonce=f"{base_nonce}-{pass_name}-{day}",
                )
            )

        return _dedupe_final_emails(generated, payload, email_types)

    try:
        emails = generate_live_pass("live", random.randint(0, 999))
    except Exception as first_error:
        try:
            emails = generate_live_pass("retry", 3)
        except Exception as retry_error:
            raise RuntimeError(
                "Génération IA live impossible. Aucun fallback local n’a été utilisé. "
                f"Erreur initiale: {first_error}. Erreur retry: {retry_error}"
            ) from retry_error

    if _looks_too_similar(emails):
        try:
            emails = generate_live_pass("similarity-retry", 5)
        except Exception as similarity_error:
            raise RuntimeError(
                "La génération IA live a produit une séquence trop similaire. "
                "Aucun fallback local n’a été utilisé."
            ) from similarity_error

    return {
        "campaign_name": campaign_name,
        "campaign_type": campaign_type,
        "duration_days": duration_days,
        "sender_name": sender_name,
        "emails": emails,
    }
