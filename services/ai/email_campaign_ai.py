from __future__ import annotations

import random
import re
import uuid
from typing import Any, Dict, List

from services.content_engine_service import generate_ai_text

EMAIL_TYPE_PATTERNS = {
    7: ["nurture", "nurture", "objection", "vente", "nurture", "relance", "vente"],
    14: [
        "nurture", "nurture", "objection", "vente", "nurture", "relance", "vente",
        "nurture", "objection", "vente", "nurture", "relance", "vente", "vente",
    ],
    30: [
        "nurture", "nurture", "nurture", "objection", "vente", "nurture", "relance", "vente", "nurture", "objection",
        "vente", "nurture", "relance", "vente", "nurture", "nurture", "objection", "vente", "nurture", "relance",
        "vente", "nurture", "objection", "vente", "nurture", "relance", "vente", "vente", "vente", "vente",
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


SECTION_RE = {
    "subject": re.compile(r"SUJET\s*:\s*(.+?)(?=\n(?:PREHEADER|PRÉHEADER)\s*:|\Z)", re.IGNORECASE | re.DOTALL),
    "preheader": re.compile(r"(?:PREHEADER|PRÉHEADER)\s*:\s*(.+?)(?=\nCORPS\s*:|\nBODY\s*:|\Z)", re.IGNORECASE | re.DOTALL),
    "body": re.compile(r"(?:CORPS|BODY)\s*:\s*(.+?)(?=\nCTA\s*:|\Z)", re.IGNORECASE | re.DOTALL),
    "cta": re.compile(r"CTA\s*:\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL),
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
    src = (text or "").strip()
    out: Dict[str, str] = {}
    for key, pattern in SECTION_RE.items():
        match = pattern.search(src)
        if match:
            out[key] = match.group(1).strip()
    return out


def _fallback_email(*, day: int, email_type: str, offer_name: str, target_audience: str, main_promise: str, main_objective: str, primary_cta: str, sender_name: str, tone: str) -> Dict[str, Any]:
    angles = ANGLE_BANK.get(email_type, ["angle simple"])
    angle = angles[(day - 1) % len(angles)]
    intros = {
        "nurture": f"Je repense à une situation très simple : beaucoup de personnes comme {target_audience} veulent progresser, mais restent bloquées parce qu'elles essaient d'aller trop vite ou dans le mauvais ordre.",
        "objection": f"Le blocage du moment est souvent le suivant : on se dit qu'on verra plus tard, qu'il manque encore quelque chose avant d'avancer, alors que ce qui manque surtout, c'est une méthode claire.",
        "relance": f"Petit rappel aujourd'hui : différer une décision n'enlève pas le problème, ça repousse seulement les résultats. Quand l'objectif est important, repousser coûte souvent plus cher que passer à l'action.",
        "vente": f"Parlons concret aujourd'hui : {offer_name} a été pensé pour transformer une intention floue en progression mesurable. Ce n'est pas juste de l'information de plus, c'est une trajectoire plus claire.",
    }
    middles = {
        "nurture": f"Si votre audience veut {main_promise.lower()}, elle a besoin d'une marche simple à gravir, pas d'une montagne. L'idée du jour, c'est de choisir un seul levier utile et de l'exécuter proprement.",
        "objection": f"Beaucoup pensent qu'il faut d'abord avoir plus de temps, plus de compétences ou plus de certitude. En réalité, le vrai déclic arrive souvent quand on entre dans un cadre qui réduit l'hésitation et donne une direction.",
        "relance": f"Revenez à la vraie question : est-ce que rester dans la situation actuelle vous rapproche vraiment de {main_objective.lower()} ? Si la réponse est non, il faut utiliser cet instant comme point de bascule.",
        "vente": f"Le bénéfice central de {offer_name} est simple : vous faire gagner en clarté, en vitesse d'exécution et en cohérence. C'est exactement ce qu'il faut quand on veut éviter la dispersion et avancer plus vite.",
    }
    closes = {
        "nurture": f"Ce n'est pas un email pour vendre à tout prix. C'est un email pour vous aider à voir qu'un changement concret devient possible dès qu'on adopte un meilleur système.",
        "objection": f"Le but n'est pas d'effacer toute peur. Le but est de ne plus laisser cette peur piloter vos décisions. Une bonne offre sert aussi à ça : réduire le brouillard.",
        "relance": f"Vous n'avez pas besoin d'attendre un meilleur moment. Vous avez surtout besoin d'un moment où vous décidez enfin d'avancer sérieusement.",
        "vente": f"Si vous voulez accélérer proprement, éviter les détours inutiles et passer à l'étape supérieure, c'est maintenant qu'il faut transformer l'intention en décision.",
    }
    body = (
        f"Bonjour,\n\n"
        f"{intros[email_type]}\n\n"
        f"{middles[email_type]}\n\n"
        f"{closes[email_type]}\n\n"
        f"CTA : {primary_cta}"
    )
    return {
        "day": day,
        "email_type": email_type,
        "subject": f"Jour {day} — {offer_name} | {angle}",
        "preheader": f"{email_type.capitalize()} — {angle}",
        "body": body,
        "cta": primary_cta,
    }


def _looks_too_similar(emails: List[Dict[str, Any]]) -> bool:
    if len(emails) < 2:
        return False
    subjects = [(_clean_text(e.get("subject"), "")).lower() for e in emails]
    prefixes = [(_clean_text(e.get("body"), "")[:180]).lower() for e in emails]
    repeated_subjects = len(set(subjects)) <= max(1, len(subjects) // 2)
    repeated_prefixes = len(set(prefixes)) <= max(1, len(prefixes) // 2)
    return repeated_subjects or repeated_prefixes


def _build_prompt(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> str:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    target_audience = _clean_text(_get(payload, "target_audience"), "votre audience")
    main_promise = _clean_text(_get(payload, "main_promise"), "atteindre un meilleur résultat")
    main_objective = _clean_text(_get(payload, "main_objective"), "passer à l'action")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "Passez à l'action maintenant")
    tone = _clean_text(_get(payload, "tone"), "premium")
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    campaign_type = _clean_text(_get(payload, "campaign_type"), "vente")
    campaign_name = _clean_text(_get(payload, "name"), "Campagne E-mailing IA")
    product_context = _clean_text(_get(payload, "product_context"), "")
    objection = _clean_text(_get(payload, "main_objection"), "")
    proof = _clean_text(_get(payload, "proof"), "")

    return f"""
Tu es Emailing IA LGD V2 : copywriter senior direct-response + stratège Systeme.io.

MISSION
Écris UN SEUL email marketing en français, prêt à être utilisé dans une séquence Systeme.io.
L'email doit être humain, naturel, crédible, orienté conversion, et distinct des autres jours.

CONTEXTE
- Campagne: {campaign_name}
- Type campagne: {campaign_type}
- Jour: {day}
- Type d'email: {email_type}
- Angle obligatoire: {angle}
- Mode viral V3 recommandé: {random.choice(VIRAL_ANGLE_MODES_V3)}
- Variation unique anti-répétition: {nonce}
- Offre: {offer_name}
- Audience: {target_audience}
- Promesse: {main_promise}
- Objectif utilisateur: {main_objective}
- Objection principale: {objection or "non précisée, à inférer"}
- Preuve / crédibilité: {proof or "non précisée, reste crédible et évite les fausses preuves"}
- Contexte produit: {product_context or "non précisé"}
- CTA principal: {primary_cta}
- Variantes CTA possibles: {", ".join(CTA_VARIANTS_V3)}
- Ton: {tone}
- Expéditeur: {sender_name}

{_v3_context_block(payload)}

RAISONNEMENT SILENCIEUX AVANT RÉDACTION
Analyse sans l'afficher :
1. douleur principale,
2. désir profond,
3. objection ou frein,
4. transformation promise,
5. mécanisme de persuasion le plus adapté,
6. CTA le plus fluide.

RÈGLES DE COPYWRITING
- Première phrase = hook clair, humain, concret.
- Phrases courtes. Respiration. Pas de pavé compact.
- Évite le ton corporate, scolaire, robotique ou trop vendeur.
- Ne copie jamais un contenu existant : transforme l'angle, la structure et les formulations.
- Pas de fausse preuve, pas de promesse irréaliste, pas de manipulation.
- Si l'email est "nurture" : valeur + prise de conscience.
- Si l'email est "objection" : rassurer + recadrer le blocage.
- Si l'email est "relance" : urgence douce + bénéfice + décision simple.
- Si l'email est "vente" : avant/après + valeur + CTA.
- Ne signe pas l'email dans le CORPS. Le frontend ajoute la signature.
- Si le CTA principal est faible ou trop vague, rends-le plus désirable sans changer l'intention.
- Crée une sensation d'élan : le lecteur doit savoir quoi faire ensuite.
- N'écris jamais "angle du jour", "variation", "A/B", "structure", "analyse".

FORMAT STRICT
SUJET: ...
PREHEADER: ...
CORPS:
...
CTA: {primary_cta}
""".strip()


def _generate_one_email(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> Dict[str, Any]:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "Passez à l'action maintenant")
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    tone = _clean_text(_get(payload, "tone"), "premium")

    raw = generate_ai_text(prompt=_build_prompt(payload=payload, day=day, email_type=email_type, angle=angle, nonce=nonce), tone=tone, language="fr")
    parts = _extract_sections(str(raw))

    body = _clean_text(parts.get("body"), "")
    # Signature volontairement gérée côté frontend pour éviter les doublons dans Systeme.io.
    body = re.sub(r"(?is)\n*à\s+(?:très\s+vite|bientôt)[, !]*\n?.*$", "", body).strip()

    return {
        "day": day,
        "email_type": email_type,
        "subject": _clean_text(parts.get("subject"), f"Jour {day} — {offer_name}"),
        "preheader": _clean_text(parts.get("preheader"), offer_name),
        "body": _clean_text(body, f"Bonjour,\n\n{offer_name}\n\nÀ très vite,\n{sender_name}"),
        "cta": _clean_text(parts.get("cta"), primary_cta),
    }


def generate_email_campaign_sequence(payload: Any) -> Dict[str, Any]:
    campaign_name = _clean_text(_get(payload, "name"), "Campagne E-mailing IA")
    campaign_type = _clean_text(_get(payload, "campaign_type"), "vente")
    duration_days = int(_get(payload, "duration_days", 7) or 7)
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    email_types = _pattern_for_days(duration_days)

    base_nonce = f"{uuid.uuid4().hex[:8]}-{random.randint(1000, 9999)}"
    emails: List[Dict[str, Any]] = []

    for index in range(duration_days):
        day = index + 1
        email_type = email_types[index]
        angle_options = ANGLE_BANK.get(email_type, ["angle simple"])
        angle = angle_options[(index + random.randint(0, len(angle_options)-1)) % len(angle_options)]
        try:
            email = _generate_one_email(
                payload=payload,
                day=day,
                email_type=email_type,
                angle=angle,
                nonce=f"{base_nonce}-{day}",
            )
        except Exception:
            email = _fallback_email(
                day=day,
                email_type=email_type,
                offer_name=_clean_text(_get(payload, "offer_name"), "Votre offre"),
                target_audience=_clean_text(_get(payload, "target_audience"), "votre audience"),
                main_promise=_clean_text(_get(payload, "main_promise"), "atteindre un meilleur résultat"),
                main_objective=_clean_text(_get(payload, "main_objective"), "passer à l'action"),
                primary_cta=_clean_text(_get(payload, "primary_cta"), "Passez à l'action maintenant"),
                sender_name=sender_name,
                tone=_clean_text(_get(payload, "tone"), "premium"),
            )
        emails.append(email)

    if _looks_too_similar(emails):
        second_pass: List[Dict[str, Any]] = []
        for index in range(duration_days):
            day = index + 1
            email_type = email_types[index]
            angle_options = ANGLE_BANK.get(email_type, ["angle simple"])
            angle = angle_options[(index + 2) % len(angle_options)]
            try:
                second_pass.append(
                    _generate_one_email(
                        payload=payload,
                        day=day,
                        email_type=email_type,
                        angle=angle,
                        nonce=f"{base_nonce}-retry-{day}",
                    )
                )
            except Exception:
                second_pass.append(_fallback_email(
                    day=day,
                    email_type=email_type,
                    offer_name=_clean_text(_get(payload, "offer_name"), "Votre offre"),
                    target_audience=_clean_text(_get(payload, "target_audience"), "votre audience"),
                    main_promise=_clean_text(_get(payload, "main_promise"), "atteindre un meilleur résultat"),
                    main_objective=_clean_text(_get(payload, "main_objective"), "passer à l'action"),
                    primary_cta=_clean_text(_get(payload, "primary_cta"), "Passez à l'action maintenant"),
                    sender_name=sender_name,
                    tone=_clean_text(_get(payload, "tone"), "premium"),
                ))
        emails = second_pass

    return {
        "campaign_name": campaign_name,
        "campaign_type": campaign_type,
        "duration_days": duration_days,
        "sender_name": sender_name,
        "emails": emails,
    }
