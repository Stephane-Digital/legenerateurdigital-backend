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
        f"Angle du jour : {angle}.\n\n"
        f"{closes[email_type]}\n\n"
        f"À très vite,\n{sender_name}\n\n"
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
    return f"""
Tu écris UN SEUL email marketing en français, premium, humain, concret, vraiment distinct des autres jours.
Jour: {day}
Type: {email_type}
Angle obligatoire: {angle}
Variation unique obligatoire: {nonce}

Contexte:
- Campagne: {campaign_name}
- Type campagne: {campaign_type}
- Offre: {offer_name}
- Audience: {target_audience}
- Promesse: {main_promise}
- Objectif: {main_objective}
- CTA principal: {primary_cta}
- Ton: {tone}
- Expéditeur: {sender_name}

Contraintes:
- Sujet court et fort.
- Préheader différent du sujet.
- Corps entre 180 et 320 mots.
- Utilise un angle spécifique à ce jour, sans répéter les formulations d'un autre jour.
- Ne dis jamais "angle du jour" ni "variation".
- Pas de JSON.
- Réponds STRICTEMENT avec ce format :

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
    if body and sender_name not in body:
        body = f"{body}\n\nÀ très vite,\n{sender_name}"

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
