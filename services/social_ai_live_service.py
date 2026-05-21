from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class SocialAILiveError(RuntimeError):
    pass


ALLOWED_ROLES = {"hook", "body", "cta", "slide", "title"}

FORBIDDEN_WEAK_PHRASES = [
    "vous méritez",
    "croyez en vous",
    "crois en toi",
    "passez à l'action",
    "passe à l'action",
    "connectez-vous avec votre audience",
    "écoutez votre audience",
    "ecoutez votre audience",
    "contenu authentique",
    "authenticité",
    "apportez de la valeur",
    "apporter de la valeur",
    "il est essentiel",
    "dans le monde d'aujourd'hui",
    "découvrez comment",
    "decouvrez comment",
    "optimisez votre stratégie",
    "optimisez votre strategie",
    "comprenez ses besoins",
    "comprenez leurs besoins",
    "résultats concrets",
    "resultats concrets",
    "votre potentiel",
    "libérez votre potentiel",
    "transformez votre vie",
    "boostez votre présence",
    "stratégie gagnante",
    "communauté",
    "engagement authentique",
    "valeur réelle",
    "solutions miracles",
    "méthode parfaite",
]

MRR_TOKENS = [
    "mrr",
    "master resale",
    "produit digital",
    "produits digitaux",
    "formation",
    "formations",
    "affiliation",
    "revente",
]

STOP_TOKENS = [
    "arrête",
    "arrete",
    "stop",
    "doit arrêter",
    "doit arreter",
    "arrêter de faire",
    "arreter de faire",
    "stop doing",
]


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").replace("\r", "").strip()
    return text or fallback


def _clip(value: Any, limit: int = 2800) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise SocialAILiveError("Le package openai n'est pas installé sur le backend.")

    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or "").strip()
    if not api_key:
        raise SocialAILiveError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _model() -> str:
    return (
        os.getenv("OPENAI_MODEL_SOCIAL_AI", "").strip()
        or os.getenv("OPENAI_MODEL_SOCIAL", "").strip()
        or os.getenv("OPENAI_MODEL_TEXT", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _all_context(payload: Dict[str, Any]) -> str:
    return " ".join(
        _clean(payload.get(key))
        for key in [
            "format",
            "network",
            "goal",
            "objective",
            "category",
            "tone",
            "prompt",
            "brief",
            "context",
            "offer",
            "product",
            "subject",
            "audience",
            "target",
            "pain",
            "promise",
            "result",
            "objection",
            "cta",
        ]
    ).lower()


def _is_mrr(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in MRR_TOKENS)


def _wants_stop_doing(payload: Dict[str, Any]) -> bool:
    raw = _all_context(payload)
    return any(token in raw for token in STOP_TOKENS)


def _extract_json(raw: str) -> Dict[str, Any]:
    text = _clean(raw)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    raise SocialAILiveError("Réponse OpenAI non JSON pour Social AI LIVE.")


def _strip_labels(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(
        r"(?im)^\s*(HOOK|BODY|CTA|TITRE|LÉGENDE|LEGENDE|SLIDE\s*\d*|POST|CAPTION|CONSEIL|ASTUCE)\s*[:：-]\s*",
        "",
        cleaned,
    )
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"\n{4,}", "\n\n", cleaned)
    return cleaned.strip()


def _forbidden_brand_filter(text: str, allowed_offer: str = "") -> str:
    allowed = "lgd" in allowed_offer.lower() or "générateur digital" in allowed_offer.lower() or "generateur digital" in allowed_offer.lower()
    if allowed:
        return text
    cleaned = re.sub(r"\bLe\s+G[eé]n[eé]rateur\s+Digital\b", "ton offre", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bLGD\b", "ton offre", cleaned, flags=re.IGNORECASE)
    return cleaned


def _sanitize_payload_text(data: Dict[str, Any]) -> Dict[str, Any]:
    offer = _clean(data.get("offer") or data.get("product") or data.get("subject") or data.get("prompt"))

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return _forbidden_brand_filter(_strip_labels(value), offer)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    sanitized = walk(data)
    if isinstance(sanitized, dict):
        return sanitized
    return data


def _split_mobile_lines(text: str) -> str:
    """Force un rendu respirant sans transformer le sens."""
    raw = _strip_labels(text)
    if not raw:
        return raw

    # Préserve les lignes existantes quand elles sont déjà courtes.
    source_lines = [line.strip() for line in raw.split("\n")]
    out: List[str] = []

    for line in source_lines:
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue

        if len(line.split()) <= 11:
            out.append(line)
            continue

        # Coupe les phrases longues en fragments courts mobile-first.
        chunks = re.split(r"(?<=[.!?…])\s+", line)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            words = chunk.split()
            if len(words) <= 11:
                out.append(chunk)
                continue
            for i in range(0, len(words), 8):
                out.append(" ".join(words[i : i + 8]).strip())

    cleaned: List[str] = []
    previous_blank = False
    for line in out:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = blank

    return "\n\n".join(line for line in cleaned if line.strip())


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ'-]+\b", text or ""))


def _max_words_for(payload: Dict[str, Any]) -> int:
    fmt = _clean(payload.get("format"), "post").lower()
    network = _clean(payload.get("network"), "Instagram").lower()
    if "story" in fmt:
        return 65
    if "reel" in fmt or "tiktok" in network:
        return 120
    if "linkedin" in network or "linkedin" in fmt:
        return 160
    if "carrousel" in fmt:
        return 45
    return 135


def _trim_to_mobile(text: str, payload: Dict[str, Any]) -> str:
    max_words = _max_words_for(payload)
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).strip()
    clipped = re.sub(r"[,;:]?$", "", clipped).strip()
    return clipped + "."



def _flatten_text_to_blocks(text: str, payload: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    payload = payload or {}
    cleaned = _strip_labels(_clean(text))
    if not cleaned:
        return []

    # Convert common raw formats (HOOK:/BODY:/CTA:, A/B, caption) into safe blocks.
    hook = ""
    body = cleaned
    cta = ""

    hook_match = re.search(r"(?is)(?:^|\n)\s*HOOK\s*[:：-]\s*(.*?)(?=\n\s*(?:BODY|CTA)\s*[:：-]|$)", text or "")
    body_match = re.search(r"(?is)(?:^|\n)\s*BODY\s*[:：-]\s*(.*?)(?=\n\s*CTA\s*[:：-]|$)", text or "")
    cta_match = re.search(r"(?is)(?:^|\n)\s*CTA\s*[:：-]\s*(.*)$", text or "")

    if hook_match or body_match or cta_match:
        hook = _strip_labels(_clean(hook_match.group(1) if hook_match else ""))
        body = _strip_labels(_clean(body_match.group(1) if body_match else cleaned))
        cta = _strip_labels(_clean(cta_match.group(1) if cta_match else ""))
    else:
        parts = [line.strip() for line in cleaned.split("\n") if line.strip()]
        if len(parts) >= 2:
            hook = parts[0]
            tail = parts[1:]
            if tail and re.search(r"(?i)^(commente|partage|envoie|dis-moi|garde|sauvegarde|réponds|ecris|écris)", tail[-1]):
                cta = tail[-1]
                tail = tail[:-1]
            body = "\n\n".join(tail)
        else:
            hook = ""
            body = cleaned

    out: List[Dict[str, str]] = []
    if hook:
        out.append({"role": "hook", "text": _split_mobile_lines(_trim_to_mobile(hook, payload))})
    if body:
        out.append({"role": "body", "text": _split_mobile_lines(_trim_to_mobile(body, payload))})
    if cta:
        out.append({"role": "cta", "text": _split_mobile_lines(_trim_to_mobile(cta, payload))})

    return out


def _blocks_from_response(data: Dict[str, Any], payload: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    payload = payload or {}

    candidates = [
        data.get("blocks"),
        data.get("content_blocks"),
        data.get("items"),
        data.get("slides"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            blocks = []
            for item in candidate:
                if isinstance(item, dict):
                    role = _clean(item.get("role") or item.get("type") or item.get("kind"), "body").lower()
                    text = _clean(item.get("text") or item.get("content") or item.get("caption") or item.get("body"))
                    if role not in ALLOWED_ROLES:
                        role = "slide" if str(item.get("slide") or "").strip() else "body"
                    if text:
                        blocks.append({"role": role, "text": text})
                elif isinstance(item, str):
                    blocks.append({"role": "slide", "text": item})
            if blocks:
                return _normalize_blocks(blocks, payload)

    # Accept common non-block JSON shapes returned by the model.
    joined = ""
    for key in ["post", "caption", "content", "text", "body", "result", "output", "answer"]:
        if _clean(data.get(key)):
            joined = _clean(data.get(key))
            break

    if not joined:
        hook = _clean(data.get("hook") or data.get("title"))
        body = _clean(data.get("body") or data.get("caption") or data.get("content"))
        cta = _clean(data.get("cta"))
        if hook or body or cta:
            if hook:
                joined += f"HOOK: {hook}\n\n"
            if body:
                joined += f"BODY: {body}\n\n"
            if cta:
                joined += f"CTA: {cta}"

    blocks = _flatten_text_to_blocks(joined, payload)
    if blocks:
        return blocks

    raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

def _normalize_blocks(value: Any, payload: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise SocialAILiveError("Réponse Social AI LIVE invalide : blocks manquant.")

    blocks: List[Dict[str, str]] = []
    payload = payload or {}
    for item in value:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role"), "body").lower()
        text = _strip_labels(_clean(item.get("text")))
        if role not in ALLOWED_ROLES:
            role = "body"
        if text:
            if role in {"body", "hook", "cta"}:
                text = _trim_to_mobile(text, payload)
                text = _split_mobile_lines(text)
            blocks.append({"role": role, "text": text})

    if not blocks:
        raise SocialAILiveError("Réponse Social AI LIVE vide.")

    return blocks[:12]


def _normalize_string_list(value: Any, limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        text = _clean(item)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _flat_text_from_blocks(blocks: List[Dict[str, str]]) -> str:
    return "\n\n".join(_clean(block.get("text")) for block in blocks if _clean(block.get("text")))


def _has_long_paragraph(text: str) -> bool:
    for paragraph in re.split(r"\n\s*\n", text or ""):
        if _word_count(paragraph) > 34:
            return True
    return False


def _looks_weak(text: str, payload: Dict[str, Any] | None = None) -> bool:
    payload = payload or {}
    lower = text.lower()
    if any(phrase in lower for phrase in FORBIDDEN_WEAK_PHRASES):
        return True
    if _word_count(text) > _max_words_for(payload) + 25:
        return True
    if _has_long_paragraph(text):
        return True
    if "marketing digital" in lower and "mrr" not in lower and "formation" not in lower and "offre" not in lower:
        return True
    if _is_mrr(payload) and not any(token in lower for token in ["mrr", "formation", "formations", "publier", "contenu", "vente", "prospect", "vidéo", "video"]):
        return True
    if _wants_stop_doing(payload) and not any(token in lower for token in ["arrête", "arrete", "stop"]):
        return True
    if lower.count("si tu débutes dans le mrr") >= 2:
        return True
    if lower.startswith("si tu débutes dans le mrr") and not _wants_stop_doing(payload):
        return True
    return False


def _infer_market(payload: Dict[str, Any]) -> str:
    raw = _all_context(payload)
    if any(token in raw for token in MRR_TOKENS):
        return "MRR / produits digitaux"
    if any(token in raw for token in ["coach", "consultant", "accompagnement", "mentor"]):
        return "coaching / service"
    if any(token in raw for token in ["ecommerce", "e-commerce", "boutique", "shopify"]):
        return "e-commerce"
    if any(token in raw for token in ["saas", "logiciel", "application"]):
        return "SaaS"
    return "business digital"


def _context_prompt(payload: Dict[str, Any]) -> str:
    return f"""
CONTEXTE UTILISATEUR À RESPECTER À 100 %
- Format demandé : {_clean(payload.get('format'), 'post')}
- Réseau : {_clean(payload.get('network'), 'Instagram')}
- Objectif : {_clean(payload.get('goal') or payload.get('objective'), 'Autorité')}
- Catégorie / angle : {_clean(payload.get('category'), 'Conseils')}
- Ton demandé : {_clean(payload.get('tone'), 'direct, humain, premium')}
- Marché inféré : {_infer_market(payload)}
- Offre / produit / sujet : {_clip(payload.get('offer') or payload.get('product') or payload.get('subject') or payload.get('prompt'), 1100)}
- Audience : {_clip(payload.get('audience') or payload.get('target'), 1100)}
- Douleur : {_clip(payload.get('pain'), 900)}
- Promesse / résultat : {_clip(payload.get('promise') or payload.get('result'), 900)}
- Objection : {_clip(payload.get('objection'), 700)}
- CTA souhaité : {_clip(payload.get('cta'), 500)}
- Brief libre : {_clip(payload.get('prompt') or payload.get('brief') or payload.get('context'), 2200)}

OBÉISSANCE STRICTE AU BRIEF
- Si le brief dit "commence par", tu dois commencer exactement par cette intention.
- Si le brief dit "arrête de", la première idée doit être "arrête de ...".
- Si le brief contient MRR / formation / produit digital, tu dois parler de publication, exécution, contenu, prospects, ventes ou formations achetées.
- Tu n'as pas le droit de partir sur un autre angle plus général.
""".strip()


def _system_prompt() -> str:
    return """
Tu es SOCIAL AI HARDLOCK — cerveau LIVE premium pour posts sociaux courts, humains et publiables.

RÈGLE ABSOLUE : ZÉRO PAVÉ
Tu n'écris jamais d'article.
Tu n'écris jamais de paragraphe lourd.
Tu n'écris jamais de cours marketing.
Tu n'écris jamais de dissertation LinkedIn.

RÈGLE MARQUE
Tu ne mentionnes jamais LGD, Le Générateur Digital, une plateforme interne, un outil ou une marque non explicitement donnée par l'utilisateur.
L'utilisateur doit apparaître comme la personne intéressante à suivre dans SA niche.

MISSION
Créer un contenu mobile-first que l'utilisateur peut copier-coller immédiatement.
Le lecteur doit penser : "putain, c'est vrai".

STYLE OBLIGATOIRE
- phrases courtes ;
- respiration forte ;
- une seule idée par post ;
- tension concrète dès la première ligne ;
- douleur réelle ;
- conseil utile ;
- zéro blabla ;
- zéro phrase motivationnelle ;
- zéro corporate ;
- zéro vocabulaire de guru.

INTERDITS ABSOLUS
- "vous méritez" ;
- "croyez en vous" ;
- "passez à l'action" ;
- "écoutez votre audience" ;
- "contenu authentique" ;
- "apportez de la valeur" ;
- "optimisez votre stratégie" ;
- "dans le monde d'aujourd'hui" ;
- "il est essentiel" ;
- "découvrez comment" ;
- "boostez votre présence" ;
- "libérez votre potentiel".

FORMAT POST INSTAGRAM / FACEBOOK
80 à 135 mots maximum.
Lignes courtes.
Beaucoup de sauts de ligne.
Aucun bloc compact.

FORMAT REEL / TIKTOK
90 à 120 mots maximum.
Phrase écran par phrase écran.
Hook en 2 secondes.

FORMAT LINKEDIN
Plus mature, mais toujours respirant.
160 mots maximum.
Jamais pavé.

FORMAT CARROUSEL
Une idée par slide.
Très court.
Pas de paragraphes.

SI LE CONTEXTE EST MRR / PRODUITS DIGITAUX
Tu dois parler de choses terrain :
formations achetées, vidéos TikTok, stratégie, publication, page blanche, contenu publié, prospects, ventes, exécution.
Pas de motivation.
Pas de "gourous" sauf si l'utilisateur le demande.

SI LE BRIEF DEMANDE "ARRÊTE DE FAIRE ÇA"
Le post doit commencer par une idée de rupture claire en "arrête de...".
Tu peux utiliser "Si tu débutes dans le MRR :" quand c’est pertinent, mais tu ne dois PAS le répéter systématiquement.
Varie les hooks : vérité directe, scène du quotidien, contraste, question qui pique, phrase miroir.

RÉFÉRENCE DE STYLE À IMITER
Si tu débutes dans le MRR :

arrête de regarder des vidéos toute la journée.

Oui.

Vraiment.

Parce qu'à un moment :

tu n'as plus un problème d'information.

Tu as un problème d'exécution.

Tu regardes :

une vidéo TikTok
une autre stratégie
une autre méthode

Et le soir ?

Toujours zéro contenu publié.

Zéro prospect.

Zéro vente.

Le vrai déclic :

publier imparfaitement.

Parce qu'un contenu imparfait posté aujourd'hui…

bat toujours une stratégie “parfaite” restée dans ta tête.

SORTIE TECHNIQUE
Réponds uniquement en JSON valide.
Aucun markdown.
Aucun texte hors JSON.
""".strip()


def _quality_frame(payload: Dict[str, Any]) -> str:
    category = _clean(payload.get("category"), "Conseils").lower()
    network = _clean(payload.get("network"), "Instagram").lower()
    fmt = _clean(payload.get("format"), "post").lower()
    goal = _clean(payload.get("goal") or payload.get("objective"), "Autorité").lower()
    market = _infer_market(payload)

    category_line = "Donne un conseil utile, spécifique, sauvegardable. Une seule idée."
    if "algorith" in category:
        category_line = "Explique un principe algorithme terrain en une action simple : hook, rétention, sauvegarde, commentaire, timing ou recyclage. Aucun cours."
    elif "viral" in category:
        category_line = "Crée une vérité relatable, partageable, avec une phrase mémorable. Pas de buzz vide."
    elif "conversion" in category or "vente" in category or "convert" in goal:
        category_line = "Crée une prise de conscience qui rapproche le lecteur d'une décision, sans vendre lourdement."
    elif "mrr" in category or "MRR" in market:
        category_line = "Parle au débutant MRR / produits digitaux qui consomme, hésite, publie peu, veut vendre mais reste bloqué."

    if "tiktok" in network or "reel" in fmt:
        format_line = "Vidéo courte : 1 phrase par ligne, hook immédiat, aucun paragraphe."
        max_words = "90 à 120 mots maximum."
    elif "linkedin" in network:
        format_line = "LinkedIn : point de vue net, mais respirant. Aucun article."
        max_words = "140 à 160 mots maximum."
    elif "story" in fmt:
        format_line = "Story : ultra court, impact immédiat, très peu de texte."
        max_words = "35 à 65 mots maximum."
    else:
        format_line = "Instagram/Facebook : mobile-first, lignes courtes, respiration, punchline utile."
        max_words = "80 à 135 mots maximum."

    strict_start = ""
    if _wants_stop_doing(payload) and _is_mrr(payload):
        strict_start = """
DÉBUT CONTRÔLÉ POUR CE CAS
Tu dois ouvrir sur une rupture en "arrête de...", MAIS tu dois varier la forme.
Ne commence PAS toujours par "Si tu débutes dans le MRR :".
Choisis UNE des formes suivantes selon le seed créatif :
- "Si tu débutes dans le MRR :" puis "arrête de..."
- "Arrête de..." directement
- "Tu fais peut-être cette erreur :"
- "Le piège quand tu débutes dans le MRR :"
- "Tu crois manquer de stratégie. En vrai..."
- "Pendant que tu cherches la méthode parfaite..."
Ne pars pas sur les gourous, la motivation, l’authenticité vague ou un angle général.
""".strip()
    elif _wants_stop_doing(payload):
        strict_start = """
DÉBUT CONTRÔLÉ POUR CE CAS
La première idée doit contenir une rupture claire en "arrête de...", mais varie la formulation.
Ne transforme pas ça en conseil général.
""".strip()

    return f"""
CADRE QUALITÉ SPÉCIFIQUE
- Marché : {market}
- Angle prioritaire : {category_line}
- Adaptation format : {format_line}
- Longueur : {max_words}
{strict_start}

STRUCTURE OBLIGATOIRE POUR POST SIMPLE
1. Ligne 1 = situation spécifique.
2. Ligne 2 = "arrête de..." si demandé.
3. Mini tension concrète.
4. Exemple terrain.
5. Déclic.
6. Phrase mémorable.
7. CTA OBLIGATOIRE.

RÈGLE CTA HARD-LOCK
Le post doit TOUJOURS finir par une action claire adaptée à l'objectif :
- Éduquer → sauvegarde, commentaire, prise de conscience
- Convertir → commentaire, DM, lead, clic
- Attirer → réaction, opinion, partage
- Autorité → retour d'expérience, objection, avis
Jamais de fin sèche.
Jamais de post sans CTA.

EXEMPLES AUTORISÉS
- « Tu consommes plus de contenu que tu n'en publies. »
- « Tu n'as plus un problème d'information. Tu as un problème d'exécution. »
- « Un contenu imparfait publié bat une idée parfaite restée dans ta tête. »
- « Si ton audience ne comprend pas ton message en 3 secondes, elle ne va pas deviner la suite. »

EXEMPLES INTERDITS
- « Vous méritez de réussir. »
- « Connectez-vous à votre audience. »
- « Optimisez votre stratégie marketing. »
- « Créez du contenu authentique. »
""".strip()


def _single_generation_user_prompt(payload: Dict[str, Any]) -> str:
    fmt = _clean(payload.get("format"), "post").lower()
    seed = random.randint(10000, 999999)

    if fmt == "carrousel":
        blocks_rule = "Retourne 6 blocks role='slide' + 1 block role='cta'. Chaque slide = 18 mots max. Pas de paragraphe."
    elif fmt == "reel":
        blocks_rule = "Retourne 1 block role='hook', 1 block role='body' sous forme de script vidéo respirant, 1 block role='cta'."
    else:
        blocks_rule = "Retourne exactement 3 blocks obligatoires : role='hook', role='body', role='cta'. Le body doit être court, aéré, mobile-first. Le block role='cta' ne doit jamais être vide."

    return f"""
{_context_prompt(payload)}

{_quality_frame(payload)}

VARIATION LIVE
Seed créatif : {seed}
Tu dois produire un angle différent des générations précédentes.
Interdit de répéter systématiquement le même hook.
Interdit de commencer toutes les générations par "Si tu débutes dans le MRR".
Choisis un pattern selon le seed :
- seed finissant par 0/1 : scène concrète du quotidien ;
- seed finissant par 2/3 : vérité qui pique ;
- seed finissant par 4/5 : erreur fréquente ;
- seed finissant par 6/7 : contraste apprentissage/exécution ;
- seed finissant par 8/9 : question miroir.

CONTRAINTE PRINCIPALE
Écris comme si l'utilisateur allait copier-coller le contenu dans Instagram maintenant.
Pas de théorie.
Pas de phrase générique.
Pas de mini-article.
Pas de pavé.
Pas de motivation creuse.
Pas de guru talk.

{blocks_rule}

FORMAT JSON STRICT
{{
  "title": "titre interne court",
  "blocks": [
    {{"role": "hook", "text": "..."}},
    {{"role": "body", "text": "..."}},
    {{"role": "cta", "text": "CTA court, naturel et cohérent avec l'objectif"}}
  ],
  "performance": {{
    "recommended_format": "...",
    "publish_tip": "...",
    "algorithm_tip": "...",
    "visual_idea": "...",
    "variation_idea": "..."
  }},
  "angles": ["...", "...", "..."]
}}
""".strip()


def _repair_user_prompt(payload: Dict[str, Any], bad_text: str) -> str:
    return f"""
Le contenu suivant est REFUSÉ.
Il est trop générique, trop lourd, hors sujet ou pas assez mobile-first :

{_clip(bad_text, 1600)}

Réécris-le entièrement.

{_context_prompt(payload)}

{_quality_frame(payload)}

RÈGLES DE RÉÉCRITURE NON NÉGOCIABLES
- 80 à 135 mots maximum pour Instagram/Facebook.
- Aucune phrase de motivation.
- Aucune phrase corporate.
- Aucun paragraphe compact.
- Une seule idée forte.
- Si MRR : parle d'exécution, publication, contenu, prospects, ventes, formations achetées.
- Si le brief demande "arrête de", commence par "arrête de".
- Fais respirer chaque ligne.

JSON STRICT avec blocks hook/body/cta.
""".strip()


def _plan_90_user_prompt(payload: Dict[str, Any]) -> str:
    return f"""
{_context_prompt(payload)}

MISSION : PLAN 90 JOURS DE CONSEILS EXPERTS
Crée un calendrier de 90 jours pour que l'utilisateur puisse conseiller son audience et devenir une personne intéressante à suivre.
Ne génère PAS 90 posts complets.
Génère 90 angles forts, variés, actionnables, non répétitifs.

CHAQUE JOUR DOIT CONTENIR
- day
- theme
- angle
- objective
- recommended_format
- hook_seed
- audience_benefit
- algorithm_tip
- cta_type

RÈGLES
- 90 jours exactement.
- Aucun angle générique.
- Aucun doublon.
- Alterne : conseil d'autorité, erreur fréquente, algorithme, viralité douce, objection, conversion, storytelling, lead magnet, régularité, recyclage, CTA, preuve, confiance, anti-page blanche.
- Chaque hook_seed doit être court, spécifique et publiable.
- Jamais LGD, jamais marque interne.

JSON STRICT
{{
  "title": "Plan 90 jours - ...",
  "days": [
    {{
      "day": 1,
      "theme": "...",
      "angle": "...",
      "objective": "...",
      "recommended_format": "...",
      "hook_seed": "...",
      "audience_benefit": "...",
      "algorithm_tip": "...",
      "cta_type": "..."
    }}
  ]
}}
""".strip()


def _generate_json(prompt: str, *, max_tokens: int, temperature: float) -> Dict[str, Any]:
    client = _get_client()
    response = client.chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        top_p=0.88,
        frequency_penalty=0.95,
        presence_penalty=0.75,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    if not raw.strip():
        raise SocialAILiveError("Réponse OpenAI vide pour Social AI LIVE.")
    return _extract_json(raw)


def estimate_tokens(*parts: Any) -> int:
    text = " ".join(str(p or "") for p in parts)
    return max(1, int(len(text) / 4))


def _goal_label(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("goal") or payload.get("objective"), "").lower()


def _cta_seed(payload: Dict[str, Any], existing_text: str = "") -> str:
    goal = _goal_label(payload)
    network = _clean(payload.get("network"), "Instagram").lower()
    raw = _all_context(payload) + " " + str(existing_text or "").lower()

    if "convert" in goal or "vente" in goal or "dm" in goal or "lead" in goal:
        options = [
            "Commente “PLAN” si tu veux une version simple à appliquer.",
            "Écris-moi “PLAN” en DM si tu veux avancer sans repartir de zéro.",
            "Dis-moi où tu bloques aujourd'hui, je te réponds avec une piste simple.",
            "Garde ce post et passe à l'action aujourd'hui.",
        ]
    elif "attirer" in goal or "attention" in goal or "engagement" in goal or "comment" in goal:
        options = [
            "Tu te reconnais là-dedans ? Dis-le en commentaire.",
            "Partage ça à quelqu'un qui repousse encore sa première publication.",
            "Dis-moi en commentaire : tu bloques sur quoi en ce moment ?",
            "Sauvegarde ce post pour la prochaine fois où tu repousses encore.",
        ]
    elif "autor" in goal or "expert" in goal:
        options = [
            "Tu vois souvent cette erreur ? Dis-moi en commentaire.",
            "Garde cette règle pour ton prochain contenu.",
            "Quelle erreur tu vois le plus dans ta niche ?",
            "Sauvegarde ce rappel avant ta prochaine publication.",
        ]
    else:
        options = [
            "Sauvegarde ce post pour ta prochaine publication.",
            "Dis-moi en commentaire : qu'est-ce qui te bloque aujourd'hui ?",
            "Garde ça en tête avant de publier ton prochain contenu.",
            "Teste ça sur ton prochain post et observe la différence.",
        ]

    if _is_mrr(payload):
        options.extend([
            "Dis-moi en commentaire : qu'est-ce qui t'empêche de publier aujourd'hui ?",
            "Sauvegarde ce post avant de regarder une vidéo de plus.",
            "Publie une version imparfaite aujourd'hui, puis reviens me dire ce que ça a débloqué.",
        ])

    index = abs(hash((raw, network, random.randint(0, 9999)))) % len(options)
    return options[index]


def _has_cta_block(blocks: List[Dict[str, str]]) -> bool:
    for block in blocks:
        role = _clean(block.get("role"), "").lower()
        text = _clean(block.get("text"))
        if role == "cta" and text:
            return True
    return False


def _ensure_cta_block(blocks: List[Dict[str, str]], payload: Dict[str, Any]) -> List[Dict[str, str]]:
    if _has_cta_block(blocks):
        return blocks

    full_text = _flat_text_from_blocks(blocks)
    cta = _split_mobile_lines(_trim_to_mobile(_cta_seed(payload, full_text), payload))
    return [*blocks, {"role": "cta", "text": cta}]


def _postprocess_blocks(blocks: List[Dict[str, str]], payload: Dict[str, Any]) -> List[Dict[str, str]]:
    processed: List[Dict[str, str]] = []
    for block in blocks:
        role = _clean(block.get("role"), "body").lower()
        text = _clean(block.get("text"))
        if role in {"hook", "body", "cta"}:
            text = _trim_to_mobile(text, payload)
            text = _split_mobile_lines(text)
        processed.append({"role": role if role in ALLOWED_ROLES else "body", "text": text})
    return processed


def generate_social_ai_live(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _single_generation_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=1050, temperature=0.82 + random.random() * 0.08)
    data = _sanitize_payload_text(data)
    blocks = _blocks_from_response(data, safe_payload)
    blocks = _postprocess_blocks(blocks, safe_payload)
    blocks = _ensure_cta_block(blocks, safe_payload)

    full_text = _flat_text_from_blocks(blocks)
    repair_attempts = 0
    while _looks_weak(full_text, safe_payload) and repair_attempts < 2:
        repair_attempts += 1
        repair_prompt = _repair_user_prompt(safe_payload, full_text)
        data = _generate_json(repair_prompt, max_tokens=950, temperature=0.9 + random.random() * 0.06)
        data = _sanitize_payload_text(data)
        blocks = _blocks_from_response(data, safe_payload)
        blocks = _postprocess_blocks(blocks, safe_payload)
        blocks = _ensure_cta_block(blocks, safe_payload)
        full_text = _flat_text_from_blocks(blocks)

    performance = data.get("performance") if isinstance(data.get("performance"), dict) else {}

    return {
        "ok": True,
        "mode": "live_ai_hardlock_v5_zero_pave_mobile_first",
        "title": _clean(data.get("title"), "Social AI LIVE"),
        "blocks": blocks,
        "performance": {
            "recommended_format": _clean(performance.get("recommended_format"), "Post court mobile-first ou Reel selon le réseau."),
            "publish_tip": _clean(performance.get("publish_tip"), "Publie quand ton audience est disponible, puis compare les réponses qualifiées plutôt que les likes."),
            "algorithm_tip": _clean(performance.get("algorithm_tip"), "La première ligne doit faire comprendre en 3 secondes pourquoi le lecteur est concerné."),
            "visual_idea": _clean(performance.get("visual_idea"), "Une phrase forte en grand, peu de texte, contraste lisible."),
            "variation_idea": _clean(performance.get("variation_idea"), "Réécris le même angle avec une objection ou une situation concrète différente."),
        },
        "angles": _normalize_string_list(data.get("angles"), limit=8),
    }


def generate_social_ai_90_day_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_payload = _sanitize_payload_text(dict(payload or {}))
    prompt = _plan_90_user_prompt(safe_payload)
    data = _generate_json(prompt, max_tokens=6500, temperature=0.78)
    data = _sanitize_payload_text(data)

    raw_days = data.get("days")
    if not isinstance(raw_days, list):
        raise SocialAILiveError("Plan 90 jours invalide : days manquant.")

    days: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_days[:90], start=1):
        if not isinstance(item, dict):
            continue
        days.append(
            {
                "day": int(item.get("day") or index),
                "theme": _clean(item.get("theme"), f"Conseil jour {index}"),
                "angle": _clean(item.get("angle"), "Conseil utile"),
                "objective": _clean(item.get("objective"), "Créer de l'autorité"),
                "recommended_format": _clean(item.get("recommended_format"), "Post simple"),
                "hook_seed": _clean(item.get("hook_seed"), "Une vérité utile que ton audience doit entendre."),
                "audience_benefit": _clean(item.get("audience_benefit"), "Comprendre quoi faire ensuite."),
                "algorithm_tip": _clean(item.get("algorithm_tip"), "Commence par une tension claire."),
                "cta_type": _clean(item.get("cta_type"), "Question commentaire"),
            }
        )

    if len(days) < 90:
        raise SocialAILiveError("Le plan Social AI LIVE n'a pas généré 90 jours complets.")

    return {
        "ok": True,
        "mode": "live_ai_90_day_plan_v5_zero_pave",
        "title": _clean(data.get("title"), "Plan 90 jours de conseils"),
        "days": days,
    }


def generate_social_ai_day_from_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    day_data = payload.get("day_data") if isinstance(payload.get("day_data"), dict) else {}
    merged = dict(payload or {})
    merged["category"] = _clean(merged.get("category"), "Conseils")
    merged["prompt"] = "\n".join(
        [
            _clean(merged.get("prompt") or merged.get("brief")),
            f"Jour : {_clean(day_data.get('day'))}",
            f"Thème : {_clean(day_data.get('theme'))}",
            f"Angle : {_clean(day_data.get('angle'))}",
            f"Objectif : {_clean(day_data.get('objective'))}",
            f"Hook seed : {_clean(day_data.get('hook_seed'))}",
            f"Bénéfice audience : {_clean(day_data.get('audience_benefit'))}",
            f"Conseil algorithme : {_clean(day_data.get('algorithm_tip'))}",
            f"CTA : {_clean(day_data.get('cta_type'))}",
            "Génère maintenant le post complet de ce jour. Fais court, spécifique, mobile-first, non générique, zéro pavé.",
        ]
    ).strip()
    return generate_social_ai_live(merged)
