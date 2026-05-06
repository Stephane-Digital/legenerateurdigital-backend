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
        "subject": "Ce n’est pas le prix qui bloque",
        "preheader": "La vraie peur est plus discrète.",
    },
    4: {
        "role": "solution claire",
        "subject": "Le plus simple pour avancer",
        "preheader": "Une offre simple vaut mieux qu’un plan parfait.",
    },
    5: {
        "role": "projection concrète",
        "subject": "Dans 7 jours, tu peux avoir une preuve",
        "preheader": "Pas une idée de plus. Un signal réel.",
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


FORBIDDEN_CLICHE_PATTERNS = [
    "imagine",
    "imagine-toi",
    "imaginez",
    "imaginez-vous",
    "et si",
    "passe à l'action",
    "passez à l'action",
    "passer à l'action",
    "tu hésites",
    "vous hésitez",
    "crois en toi",
    "croyez en vous",
    "rien n'est impossible",
    "ne laisse pas passer cette opportunité",
    "c'est le moment",
    "prêt à",
    "prête à",
    "découvre comment",
    "transformer ton business",
    "transformer votre business",
]

GENERIC_CTA_PATTERNS = [
    "personne ne va le faire à ta place",
    "tu peux continuer… ou changer",
    "tu peux continuer... ou changer",
    "rien ne changera si tu ne changes rien",
    "tu sais déjà ce que tu dois faire",
    "ne laisse pas ça redevenir une idée",
    "maintenant tu sais",
    "passer à l’action aujourd’hui",
    "passer à l'action aujourd'hui",
    "découvrir maintenant",
    "voir comment ça fonctionne",
    "accéder à la méthode",
    "commencer simplement",
]

HUMAN_PAIN_BANK = {
    "business": [
        "ouvre Stripe plusieurs fois par jour sans notification",
        "rafraîchit ses analytics au lieu d’envoyer l’offre",
        "change encore le titre de sa page alors que personne ne l’a vue",
        "prépare un nouveau post alors qu’il n’a jamais relancé les prospects chauds",
        "garde son offre en brouillon parce qu’il a peur du silence après l’envoi",
        "achète un nouvel outil pour éviter le vrai geste : vendre",
        "dit que ça avance, mais aucun paiement n’est arrivé cette semaine",
        "voit des likes arriver, mais aucun message privé sérieux",
        "ouvre sa boîte mail en espérant une réponse qui n’arrive pas",
        "repousse l’envoi parce qu’il veut encore rendre le visuel plus propre",
    ],
    "fitness": [
        "promet de reprendre lundi puis craque le soir devant le frigo",
        "compte les calories deux jours puis abandonne au premier repas social",
        "évite le miroir après une journée trop longue",
        "cherche un nouveau programme au lieu de refaire la séance prévue",
        "se pèse le matin et laisse ce chiffre décider de toute sa journée",
        "sait quoi manger mais perd le contrôle quand la fatigue arrive",
    ],
    "crypto": [
        "ouvre son exchange à minuit après une bougie rouge",
        "vend trop tôt puis regarde le marché repartir sans lui",
        "achète parce qu’un groupe Telegram s’agite",
        "confond urgence et opportunité dès que le prix bouge",
        "cache ses pertes derrière l’idée qu’il va se refaire au prochain trade",
        "rafraîchit le graphique au lieu de respecter son plan",
    ],
    "productivity": [
        "déplace encore les mêmes tâches dans son agenda",
        "ouvre Notion pour réorganiser au lieu de terminer",
        "répond à trois notifications et perd le fil de sa vraie priorité",
        "finit la journée fatigué avec rien de vraiment livré",
        "commence par les petites tâches pour éviter celle qui compte",
        "se couche avec la sensation d’avoir été occupé, pas efficace",
    ],
    "confidence": [
        "réécrit son message dix fois puis ne l’envoie pas",
        "prépare sa prise de parole et coupe la caméra au dernier moment",
        "dit oui trop vite puis regrette dans la voiture",
        "évite de demander le prix juste pour ne pas déranger",
        "sourit en réunion alors qu’il voulait défendre son idée",
        "laisse quelqu’un d’autre décider parce que s’affirmer paraît trop risqué",
    ],
    "saas_tech": [
        "regarde sa courbe de churn grimper sans comprendre où ça fuit",
        "ajoute une énième feature alors que les utilisateurs bloquent encore dans l’onboarding",
        "voit des dizaines d’inscrits en essai mais presque personne ne sort sa carte bancaire",
        "passe la journée à corriger des bugs au lieu de parler aux utilisateurs qui abandonnent",
        "ouvre Hotjar et voit les visiteurs quitter la première étape de configuration",
        "repousse la sortie officielle parce que l’infrastructure pourrait encore être plus propre",
        "confond roadmap produit et vraie preuve de valeur payée",
        "corrige un détail d’interface au lieu d’appeler les trois comptes qui n’ont pas converti",
    ],
    "coaching_life": [
        "dit que tout va bien alors qu’il se sent s’éteindre dans son job actuel",
        "ouvre les offres d’emploi par habitude, soupire, puis referme l’onglet",
        "écoute un énième podcast de développement personnel sans changer son quotidien",
        "se lève à reculons en comptant les heures avant le week-end",
        "dit oui à des projets qui l’épuisent juste pour ne pas décevoir",
        "repousse son projet de reconversion en disant que ce n’est jamais le bon moment",
        "a déjà un carnet rempli d’idées mais aucune décision visible dans son agenda",
        "sourit en réunion alors qu’il sait qu’il n’a plus envie d’être là",
    ],
    "real_estate": [
        "scrolle sur SeLoger dès qu’une alerte mail tombe",
        "refait son plan de financement sur Excel en espérant que les chiffres changent",
        "rappelle un agent qui avait promis de revenir vers lui et ne répond plus",
        "visite un bien parfait sur les photos puis voit le défaut en cinq minutes",
        "hésite à faire une offre et regarde le bien partir en 48 heures",
        "laisse son dossier de prêt sur le bureau par peur du refus de la banque",
        "compare encore deux villes alors que son financement n’est pas verrouillé",
        "calcule la rentabilité nette mais évite d’appeler la banque",
    ],
}

NATURAL_CTA_BANK = {
    "business": [
        "Demain matin, tu peux avoir une offre envoyée au lieu d’une idée de plus.",
        "Le test à 1€ sert à ça : arrêter de deviner et regarder ce qui répond vraiment.",
        "Tu peux garder ton offre en brouillon, ou la mettre devant quelqu’un aujourd’hui.",
        "Le premier signal ne viendra pas d’un nouveau logo. Il viendra d’un envoi réel.",
        "Si tu veux une preuve, commence par créer quelque chose que quelqu’un peut acheter.",
    ],
    "fitness": [
        "Le prochain repas peut redevenir une décision, pas une compensation.",
        "Tu n’as pas besoin d’un lundi parfait. Tu as besoin d’un premier choix propre.",
        "Commence par la prochaine assiette. Le reste suivra.",
    ],
    "crypto": [
        "Le prochain trade doit suivre un plan, pas une panique.",
        "Avant d’acheter encore, reprends la règle que tu avais décidé d’ignorer.",
        "Tu peux chercher un signal de plus, ou reprendre le contrôle du risque.",
    ],
    "productivity": [
        "Ferme le tableau. Termine la tâche qui change vraiment ta journée.",
        "La prochaine heure peut produire un livrable, pas une nouvelle organisation.",
        "Choisis une tâche qui se voit quand elle est finie.",
    ],
    "confidence": [
        "Le prochain message peut rester en brouillon, ou devenir une vraie demande.",
        "Ta voix ne prendra pas plus de place tant que tu la gardes pour toi.",
        "Commence par dire clairement ce que tu voulais déjà dire.",
    ],
    "saas_tech": [
        "Tu peux coder une option de plus, ou rendre la valeur visible dès aujourd’hui.",
        "Le prochain utilisateur ne veut pas plus de boutons. Il veut comprendre quoi faire en premier.",
        "Ferme l’éditeur deux minutes. Regarde quelqu’un utiliser ton produit sans l’aider.",
        "La prochaine preuve ne viendra pas d’une feature. Elle viendra d’un utilisateur qui paie.",
    ],
    "coaching_life": [
        "La semaine prochaine ressemblera à celle-ci, sauf si tu changes le premier geste.",
        "Tu n’as pas besoin de tout quitter demain. Tu as besoin de poser une vraie limite aujourd’hui.",
        "Arrête d’attendre le déclic idéal. Choisis simplement par où tu commences.",
        "Le signal le plus clair, c’est ce que tu acceptes encore alors que tu sais déjà que ça t’éteint.",
    ],
    "real_estate": [
        "Le bon investissement ne vient pas de la chance. Il commence par un dossier qu’on peut défendre.",
        "Tu peux simuler encore trois scénarios, ou verrouiller la prochaine visite utile.",
        "Avant de chercher le bien parfait, assure-toi d’avoir une offre que le vendeur peut prendre au sérieux.",
        "Le bien parti en 48 heures n’attendait pas ton hésitation. Le prochain non plus.",
    ],
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


def _contains_any(text: str, patterns: List[str]) -> bool:
    normalized = _normalize_text(text).lower()
    return any(pattern in normalized for pattern in patterns)


def _infer_market_key(payload: Any) -> str:
    raw = " ".join(
        [
            _clean_text(_get(payload, "niche"), ""),
            _clean_text(_get(payload, "target_audience"), ""),
            _clean_text(_get(payload, "offer_name"), ""),
            _clean_text(_get(payload, "main_promise"), ""),
            _clean_text(_get(payload, "main_objective"), ""),
            _clean_text(_get(payload, "product_context"), ""),
        ]
    ).lower()

    if any(word in raw for word in ["sport", "fitness", "poids", "mincir", "muscle", "nutrition"]):
        return "fitness"
    if any(word in raw for word in ["crypto", "trading", "bitcoin", "btc", "exchange", "invest"]):
        return "crypto"
    if any(word in raw for word in ["productivité", "temps", "agenda", "organisation", "notion", "tâche"]):
        return "productivity"
    if any(word in raw for word in ["confiance", "timidité", "oser", "prise de parole", "affirmation"]):
        return "confidence"
    if any(word in raw for word in ["saas", "logiciel", "app", "tech", "churn", "code", "développeur", "mrr", "onboarding", "startup", "produit"]):
        return "saas_tech"
    if any(word in raw for word in ["coaching", "vie", "reconversion", "sens", "burnout", "épanouissement", "changer de vie", "job", "carrière"]):
        return "coaching_life"
    if any(word in raw for word in ["immo", "immobilier", "appartement", "achat", "locatif", "bien", "visite", "crédit", "prêt", "se loger", "seloger"]):
        return "real_estate"
    return "business"


def _select_human_pain_profile(payload: Any, *, day: int, angle: str, nonce: str) -> List[str]:
    market_key = _infer_market_key(payload)
    bank = HUMAN_PAIN_BANK.get(market_key, HUMAN_PAIN_BANK["business"])
    seed = f"{market_key}-{day}-{angle}-{nonce}"
    rng = random.Random(seed)
    count = min(4, len(bank))
    return rng.sample(bank, count)


def _format_bullets(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item.strip())


def _select_natural_cta(payload: Any, *, day: int, nonce: str) -> str:
    market_key = _infer_market_key(payload)
    bank = NATURAL_CTA_BANK.get(market_key, NATURAL_CTA_BANK["business"])
    seed = f"cta-{market_key}-{day}-{nonce}"
    rng = random.Random(seed)
    return bank[rng.randrange(len(bank))]


def _forbidden_cliche_score(text: str) -> int:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return 0

    weights = {
        "imagine": 1,
        "imagine-toi": 2,
        "imaginez": 2,
        "imaginez-vous": 2,
        "et si": 1,
        "passe à l'action": 3,
        "passez à l'action": 3,
        "passer à l'action": 3,
        "tu hésites": 2,
        "vous hésitez": 2,
        "crois en toi": 4,
        "croyez en vous": 4,
        "rien n'est impossible": 4,
        "ne laisse pas passer cette opportunité": 4,
        "c'est le moment": 2,
        "prêt à": 1,
        "prête à": 1,
        "découvre comment": 3,
        "transformer ton business": 4,
        "transformer votre business": 4,
    }

    score = 0
    for pattern, weight in weights.items():
        occurrences = normalized.count(pattern)
        if occurrences:
            score += occurrences * weight
    return score


def _is_forbidden_cliche(text: str) -> bool:
    # Score progressif : une micro-occurrence peut passer, un email entier cliché reste bloqué.
    return _forbidden_cliche_score(text) >= 5


def _is_generic_cta(text: str) -> bool:
    return _contains_any(text, GENERIC_CTA_PATTERNS)


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
        r"(?im)^\s*👉?\s*personne ne va le faire à ta place\s*[.!?]?\s*$",
        r"(?im)^\s*👉?\s*tu peux continuer… ou changer\s*[.!?]?\s*$",
        r"(?im)^\s*👉?\s*rien ne changera si tu ne changes rien\s*[.!?]?\s*$",
        r"(?im)^\s*👉?\s*tu sais déjà ce que tu dois faire\s*[.!?]?\s*$",
        r"(?im)^\s*👉?\s*ne laisse pas ça redevenir une idée\s*[.!?]?\s*$",
        r"(?im)^\s*👉?\s*maintenant tu sais\s*[.!?]?\s*$",
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
    main_objective = _clean_text(_get(payload, "main_objective"), "obtenir un résultat concret")
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
    human_pain_profile = _select_human_pain_profile(payload, day=day, angle=angle, nonce=nonce)
    natural_cta = _select_natural_cta(payload, day=day, nonce=nonce)

    prompt = f"""
Tu es Emailing IA LGD.

Tu n’écris pas comme un copywriter IA.
Tu n’écris pas une motivation LinkedIn.
Tu écris une scène réelle qui vend parce qu’elle sonne vraie.

MISSION
Écris EXACTEMENT UN SEUL email pour le jour {day}.
Ne fais jamais référence aux autres emails.
Ne génère jamais plusieurs versions.
Ne réutilise jamais exactement la même phrase d’un email à l’autre.

CONTEXTE STRATÉGIQUE CMO — PRIORITÉ ABSOLUE
Campagne : {campaign_name}
Type : {campaign_type}
Jour : {day}
Rôle : {archetype["role"]}
Type email : {email_type}
Angle : {angle}
Offre : {offer_name}
Cible : {target_audience}
Niche : {niche or "non précisée"}
Promesse : {main_promise}
Objectif : {main_objective}
Blocage réel : {objection or "à inférer depuis l’offre, la cible et le contexte"}
Preuve : {proof or "non précisée"}
Contexte : {product_context or "non précisé"}
CTA fourni : {primary_cta or "à reformuler naturellement"}
Ton : {tone}
Expéditeur : {sender_name}
Variation : {nonce}

MATIÈRE HUMAINE OBLIGATOIRE
Tu dois utiliser AU MOINS DEUX comportements réels ci-dessous.
Tu peux les reformuler, mais pas les rendre abstraits.
{_format_bullets(human_pain_profile)}

RÈGLE DE QUALITÉ LGD
L’email doit montrer une situation que la cible reconnaît immédiatement.
Si le texte peut fonctionner pour n’importe quelle offre, il est mauvais.
Si le texte peut être posté tel quel par un coach motivation, il est mauvais.
Si le texte explique le problème au lieu de le faire vivre, il est mauvais.

INTERDICTIONS ABSOLUES
N’utilise jamais ces formulations :
- imagine
- et si
- passe à l’action
- tu hésites
- crois en toi
- ne laisse pas passer cette opportunité
- c’est le moment
- prêt à / prête à
- découvre comment
- transformer ton business
- outil puissant
- solution complète
- le problème c’est
- avec LGD tu vas

SCÈNE OBLIGATOIRE
Le corps doit commencer par une scène observable en 2 à 5 lignes.
La scène doit contenir au moins UN détail concret : heure, écran, téléphone, paiement, silence, analytics, Stripe, WhatsApp, email, fatigue, brouillon, notification, page, prospect.

Exemples de niveau attendu, à ne pas recopier :
- Il est 22h48. Tu ouvres encore Stripe. Toujours zéro. Alors tu retournes modifier le bouton de ta page.
- Tu as trois brouillons prêts. Aucun envoyé. Pas parce qu’ils sont mauvais. Parce qu’après l’envoi, il faudra regarder le silence en face.

MÉCANISME DE VENTE
Tu dois relier la scène à l’offre {offer_name} sans dire “solution complète” ni “outil puissant”.
LGD doit apparaître comme un déclencheur : il aide à produire une action visible, testable, envoyable.

CONFRONTATION
Une phrase doit confronter honnêtement la cible.
Pas de morale.
Pas de motivation.
Une vérité sèche.

CTA NATUREL
Le CTA doit être une phrase de continuité, pas un bouton marketing.
Base possible : {natural_cta}
Interdit dans le CTA : clique, réserve, inscris-toi, télécharge, découvrir maintenant, personne ne va le faire à ta place, maintenant tu sais.

STYLE
- français naturel
- tutoiement uniquement
- phrases courtes
- lignes coupées
- rythme iPhone
- pas de markdown
- pas d’émoji sauf si le CTA final commence par 👉
- pas de signature

FORMAT STRICT
SUJET: ...
PREHEADER: ...
CORPS:
Bonjour {{{{prenom}}}},

...

CTA: ...

Tu t’arrêtes après le CTA.
""".strip()
    return prompt.strip()

def _generate_one_email(*, payload: Any, day: int, email_type: str, angle: str, nonce: str) -> Dict[str, Any]:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "")
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
    natural_cta = _select_natural_cta(payload, day=day, nonce=nonce)
    cta = _clean_text(parts.get("cta"), "")
    if not cta or _is_generic_cta(cta) or _is_forbidden_cliche(cta):
        cta = natural_cta

    body = _strip_cta_from_body(_clean_text(parts.get("body"), ""), cta)

    if _is_bad_template(body):
        # Filtre soft : on nettoie sans bloquer une génération IA exploitable.
        body = _sanitize_body(body)

    subject = _clean_text(parts.get("subject"), f"Jour {day} — {offer_name}")
    preheader = _clean_text(parts.get("preheader"), offer_name)

    generation_quality_scan = "\n".join([subject, preheader, body, cta])
    if _is_forbidden_cliche(generation_quality_scan):
        raise ValueError(
            f"Email IA jour {day} rejeté : cliché IA détecté "
            f"(score {_forbidden_cliche_score(generation_quality_scan)})."
        )

    return {
        "day": day,
        "email_type": email_type,
        "subject": subject,
        "preheader": preheader,
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

        fallback_cta_pool = NATURAL_CTA_BANK.get(_infer_market_key(payload), NATURAL_CTA_BANK["business"])
        cta = _clean_text(email.get("cta"), "")
        if not cta or _is_generic_cta(cta) or _is_forbidden_cliche(cta):
            cta = fallback_cta_pool[(day - 1) % len(fallback_cta_pool)]
        email["cta"] = cta

        full_quality_scan = "\n".join(
            [
                _clean_text(email.get("subject"), ""),
                _clean_text(email.get("preheader"), ""),
                _clean_text(email.get("body"), ""),
                _clean_text(email.get("cta"), ""),
            ]
        )
        if _is_forbidden_cliche(full_quality_scan):
            raise ValueError(
                f"Email IA jour {day} rejeté : cliché IA détecté "
                f"(score {_forbidden_cliche_score(full_quality_scan)})."
            )

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
