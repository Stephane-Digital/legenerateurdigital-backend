from __future__ import annotations

import random
import re
import uuid
from typing import Any, Dict, List

# On suppose que cette fonction accepte l'argument temperature. 
# Si votre service ne l'accepte pas, il faudra ajuster l'interface de generate_ai_text.
from services.content_engine_service import generate_ai_text

EMAIL_TYPE_PATTERNS = {
    7: ["nurture", "nurture", "objection", "vente", "nurture", "relance", "vente"],
    14: ["nurture", "nurture", "objection", "vente", "nurture", "relance", "vente"] * 2,
    30: ["nurture", "nurture", "nurture", "objection", "vente", "nurture", "relance", "vente"] * 4,
}

ANGLE_BANK = {
    "nurture": [
        "la vérité que personne n'ose dire dans ta niche",
        "pourquoi j'ai failli tout arrêter (vulnérabilité)",
        "le conseil que je donnerais à mon 'moi' d'il y a 2 ans",
        "une observation surprenante faite ce matin",
        "le mythe du 'moment idéal'",
        "ce que tes concurrents te cachent par peur",
    ],
    "objection": [
        "le coût réel de ne rien changer aujourd'hui",
        "pourquoi le manque de temps est une illusion",
        "l'arnaque de la perfection avant l'action",
        "peur de l'échec vs certitude du regret",
        "pourquoi ton cerveau te ment pour te protéger",
    ],
    "relance": [
        "une décision simple pour ton 'toi' du futur",
        "le risque de voir cette opportunité devenir un simple souvenir",
        "une mini checklist pour trancher maintenant",
        "dernière réflexion avant de fermer cette porte",
    ],
    "vente": [
        "le calcul mathématique de ton ROI potentiel",
        "pourquoi cette offre n'est PAS pour tout le monde",
        "projection : ton quotidien dans 6 mois avec vs sans",
        "réponse à : 'Est-ce que ça va vraiment marcher pour moi ?'",
    ],
}

DAY_ARCHETYPES = {
    1: {"role": "connexion / empathie", "subject": "C’est pas ta faute", "preheader": "On nous ment souvent sur la méthode."},
    2: {"role": "vérité brutale", "subject": "Le problème est ailleurs", "preheader": "Ce n’est pas un manque de travail."},
    3: {"role": "coût de l'inaction", "subject": "Le prix du statu quo", "preheader": "Attendre coûte plus cher qu'agir."},
    4: {"role": "solution logique", "subject": "La voie la plus directe", "preheader": "Comment simplifier radicalement."},
    5: {"role": "preuve de concept", "subject": "Ce qui se passe quand on ose", "preheader": "Des résultats, pas des théories."},
    6: {"role": "urgence douce", "subject": "Une décision à prendre", "preheader": "Demain est souvent un autre mot pour jamais."},
    7: {"role": "décision finale", "subject": "À toi de choisir", "preheader": "On s'arrête là ou on commence ?"},
}

SECTION_RE = {
    "subject": re.compile(r"^\s*SUJET\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
    "preheader": re.compile(r"^\s*(?:PREHEADER|PRÉHEADER)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
    "body": re.compile(r"(?:^|\n)\s*(?:CORPS|BODY)\s*:\s*(.+?)(?=\n\s*CTA\s*:|\Z)", re.IGNORECASE | re.DOTALL),
    "cta": re.compile(r"(?:^|\n)\s*CTA\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
}

def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None: return default
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return text or fallback

def _normalize_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\r", "").replace("**", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _sanitize_body(body: str) -> str:
    cleaned = _normalize_text(body)
    # Suppression des signatures et patterns automatiques IA
    patterns = [r"(?is)\n*à\s+bientôt.*$", r"(?is)\n*Cordialement.*$", r"(?is)\n*Alex IA.*$", r"(?is)\n*Ton Coach LGD.*$"]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned).strip()
    return cleaned

def _extract_sections(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, pattern in SECTION_RE.items():
        match = pattern.search(text)
        if match:
            out[key] = match.group(1).strip()
    if "body" in out:
        out["body"] = _sanitize_body(out["body"])
    return out

def _build_prompt(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> str:
    offer_name = _clean_text(_get(payload, "offer_name"), "votre offre")
    target_audience = _clean_text(_get(payload, "target_audience"), "votre audience")
    main_promise = _clean_text(_get(payload, "main_promise"), "obtenir un résultat")
    tone = _clean_text(_get(payload, "tone"), "premium")
    archetype = DAY_ARCHETYPES.get(day, DAY_ARCHETYPES[((day - 1) % 7) + 1])
    awareness = "Conscience du problème" if day < 3 else "Conscience de la solution"

    return f"""
PRIORITÉ : ÉCRITURE "SANS FILTRE" (STYLE IPHONE / NOTE PERSONNELLE)
Tu es un copywriter d'élite. Ton but est de créer un email qui ne ressemble PAS à du marketing.

MISSION : 
Écris UN SEUL email en français. Le lecteur doit avoir l'impression que tu viens de lui envoyer ça entre deux rendez-vous.

1. HUMANISATION RADICALE
- Oralité : Utilise "C'est pas", "On va dire que", "Le truc c'est...".
- Pas de pavés : Des phrases courtes. De l'air.
- Émotion : Parle de la frustration réelle, pas de concepts vagues.

2. CONVERSION (PSYCHOLOGIE)
- Niveau de conscience : {awareness}. 
- Coût de l'inaction : Montre ce qu'il perd (énergie, temps) s'il reste là où il est.
- Angle du jour : {angle}.

CONTEXTE :
- Offre : {offer_name}
- Audience : {target_audience}
- Promesse : {main_promise}
- Jour : {day} ({archetype["role"]})
- Nonce : {nonce}

RÈGLES STRICTES :
- INTERDIT : Commencer par "J'espère que tu vas bien" ou "Imagine".
- INTERDIT : Utiliser des emojis de vente (🚀, 🎁, 💰).
- INTERDIT : Signer l'email.
- COMMENCE DIRECTEMENT par une observation ou une vérité qui pique.

LA RÈGLE DU CTA :
- Si l'email est "vente" ou "relance" : Propose une suite logique et naturelle (ex: "Tu viens ?", "Regarde ici si tu es prêt").
- Si l'email est "nurture" ou "objection" : Termine par une question qui fait réfléchir.

FORMAT OBLIGATOIRE :
SUJET: ...
PREHEADER: ...
CORPS:
Bonjour {{prenom}},
(Ton texte)

CTA: (Ta phrase d'action ou de réflexion)
""".strip()

def _generate_one_email(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> Dict[str, Any]:
    # TEMPÉRATURE À 0.8 POUR L'HUMANISATION
    raw = generate_ai_text(
        prompt=_build_prompt(payload=payload, day=day, email_type=email_type, angle=angle, nonce=nonce),
        tone=_clean_text(_get(payload, "tone"), "premium"),
        language="fr",
        temperature=0.8 
    )
    parts = _extract_sections(str(raw))
    
    return {
        "day": day,
        "email_type": email_type,
        "subject": _clean_text(parts.get("subject"), f"Note pour {{{'prenom'}}}"),
        "preheader": _clean_text(parts.get("preheader"), ""),
        "body": _clean_text(parts.get("body"), ""),
        "cta": _clean_text(parts.get("cta"), "à toi de voir"),
    }

def generate_email_campaign_sequence(payload: Any) -> Dict[str, Any]:
    duration_days = int(_get(payload, "duration_days", 7) or 7)
    email_types = _pattern_for_days(duration_days)
    base_nonce = uuid.uuid4().hex[:8]
    
    emails = []
    for i in range(duration_days):
        day = i + 1
        e_type = email_types[i]
        angles = ANGLE_BANK.get(e_type, ["angle simple"])
        angle = random.choice(angles)
        
        emails.append(_generate_one_email(
            payload=payload, 
            day=day, 
            email_type=e_type, 
            angle=angle, 
            nonce=f"{base_nonce}-{day}"
        ))

    return {
        "campaign_name": _clean_text(_get(payload, "name")),
        "emails": emails,
    }

def _pattern_for_days(days: int) -> List[str]:
    if days in EMAIL_TYPE_PATTERNS: return EMAIL_TYPE_PATTERNS[days]
    return [EMAIL_TYPE_PATTERNS[7][i % 7] for i in range(days)]
