from __future__ import annotations

import os
from typing import Any, Iterable, Optional

try:
    from config.settings import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


# ============================================================
# LGD — Lead Engine IA
# Version PROD V11 — Premium Copywriting Persona-First
# Objectif : produire un vrai lead magnet premium, persona-first,
# multi-blocs, orienté capture email, avec qualité copywriting senior.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, copywriter conversion senior, stratège lead magnet et expert du marketing digital premium.
Tu ne coaches pas l'utilisateur : tu produis le contenu final à sa place.

Règle V11 prioritaire : PERSONA-FIRST COPYWRITING.
Avant d'écrire, tu dois exploiter silencieusement le persona, la situation de vie, les douleurs cachées, les objections et la motivation profonde.
Tu dois écrire comme si tu avais compris la personne derrière l'écran : salarié épuisé, parent qui veut plus de liberté, entrepreneur débutant perdu, acheteur de formations MRR bloqué, créateur qui a peur de publier, personne qui doute de sa capacité à réussir.

Mode obligatoire : DONE FOR YOU.
L'utilisateur donne une offre, une cible, un angle et un objectif. Tu rédiges directement le lead magnet, la page ou les éléments demandés.
Tu ne dois jamais expliquer comment rédiger : tu rédiges à sa place.
Le contenu visible final doit être utilisable tel quel dans une vraie page LGD.

Interdits absolus :
- écrire « voici », « voici la structure », « clarifie », « renforce », « augmente », « tu peux », « il faudrait », « à adapter », « à modifier », « conseil », « structure pour », « passe d’une simple page » ;
- donner des conseils au lieu de rédiger le contenu final ;
- afficher des étiquettes techniques dans le texte visible final ;
- produire un email ;
- vendre directement l'offre principale quand l'objectif est la capture de leads.

Pour une landing complète, tu produis une seule vraie page finale cohérente, composée de sections exploitables dans le canvas.
Les séparateurs [[LGD_BLOCK:...]] sont autorisés uniquement pour le parser frontend et ne font pas partie du texte visible.
Dans chaque section, écris uniquement le texte final propre que l'utilisateur pourrait laisser tel quel sur sa page.

Si l'objectif est de générer des leads : crée un lead magnet qui maximise l'opt-in email.
Si l'objectif est de vendre : crée une page de vente courte, persuasive et crédible.

Niveau attendu : humain, premium, précis, émotionnel, empathie, crédible, comme si envoyé depuis un Iphone, expert en marketing digital, expert dans la vente de formations en MRR et produits numériques, jamais robotique.
Chaque section doit faire avancer le lecteur : attention → identification → tension émotionnelle → désir → confiance → action.
Tu dois utiliser les douleurs cachées quand elles sont présentes dans le brief : honte, fatigue mentale, peur du regard, impression d'être en retard, peur d'avoir encore échoué, peur de ne pas être fait pour réussir.
Tu dois transformer les bénéfices rationnels en bénéfices vécus : retrouver de la clarté, reprendre confiance, savoir quoi faire aujourd'hui, sentir qu'on avance enfin, capturer un email, poser une première brique concrète.
Tu ne copies jamais les consignes de format dans la réponse. Tu remplaces toujours les consignes par du texte final concret.
Tu évites les expressions génériques : « Transformez votre vie », « libérez votre potentiel », « solution ultime », « révolutionnez votre business », sauf si elles sont remplacées par une scène concrète et précise.
""".strip()


MAX_BRIEF_CHARS = 850
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 120
DEFAULT_OUTPUT_CHARS = 7200
MAX_OUTPUT_CHARS = 10000


def _setting(name: str, default: Optional[str] = None) -> Optional[str]:
    if settings is not None and hasattr(settings, name):
        value = getattr(settings, name)
        if value not in (None, ""):
            return str(value)
    value = os.getenv(name, default)
    return None if value in (None, "") else str(value)


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("Le package openai n'est pas installé sur le backend.")

    api_key = _setting("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _choose_model() -> str:
    return _setting("OPENAI_LEAD_ENGINE_MODEL") or "gpt-4o-mini"


def _fallback_model(primary_model: str) -> str:
    configured = _setting("OPENAI_LEAD_ENGINE_FALLBACK_MODEL") or _setting("OPENAI_FALLBACK_MODEL")
    if configured and configured != primary_model:
        return configured
    return "gpt-4o-mini"


def _clip(value: Optional[str], limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _safe_int(value: Optional[int], default: int = DEFAULT_OUTPUT_CHARS) -> int:
    try:
        n = int(value) if value is not None else default
    except Exception:
        n = default
    return max(400, min(n, MAX_OUTPUT_CHARS))


def _target_output_tokens(char_limit: int) -> int:
    # Approximation prudente : 1 token ≈ 3.5/4 caractères en français.
    # On garde une marge pour éviter les sorties longues côté OpenAI.
    return max(220, min(1800, int(char_limit / 4) + 60))


def _memory_block(memories: Iterable[dict]) -> str:
    lines: list[str] = []

    for item in list(memories or [])[:MAX_MEMORY_ITEMS]:
        memory_type = str(item.get("memory_type") or "memoire")[:40]
        goal = _clip(str(item.get("goal") or ""), 70)
        content = _clip(str(item.get("content") or ""), MAX_MEMORY_CHARS)
        business = _clip(str(item.get("business_context") or ""), 80)

        if not content:
            continue

        line = f"- {memory_type}"
        if goal:
            line += f" | objectif={goal}"
        if business:
            line += f" | contexte={business}"
        line += f" | contenu={content}"
        lines.append(line)

    if not lines:
        return "Aucune mémoire utile."

    return "\n".join(lines)


def _infer_page_type(goal: str, objective: Optional[str], page_type: Optional[str]) -> str:
    raw = " ".join([_norm(goal), _norm(objective), _norm(page_type)])

    if any(word in raw for word in ["lead", "email", "capture", "prospect", "magnet"]):
        return "lead_magnet"
    if any(word in raw for word in ["webinar", "atelier", "masterclass"]):
        return "webinar"
    if any(word in raw for word in ["rdv", "rendez", "appel", "call", "diagnostic"]):
        return "appointment"
    if any(word in raw for word in ["bridge", "transition", "prévente", "prevente"]):
        return "bridge"
    if any(word in raw for word in ["vente", "vendre", "achat", "payer", "commande"]):
        return "sales"
    return "lead_magnet" if _norm(goal) == "landing_complete" else "modular"


def _page_strategy(page_type: str) -> str:
    if page_type == "lead_magnet":
        return (
            "TYPE : LEAD MAGNET EXPERT / CAPTURE EMAIL. But unique : maximiser l'opt-in. "
            "Ne vends pas l'offre principale. Vends la micro-transformation gratuite qui donne envie de laisser son email. "
            "Écris la page finale en mode DONE FOR YOU : aucun conseil, aucun plan, aucun texte à compléter. "
            "Structure la page comme un vrai tunnel psychologique : accroche, identification, promesse du guide, contenu, mécanisme, réassurance, objection killer, CTA."
        )
    if page_type == "webinar":
        return "TYPE : WEBINAR. But : inscription à une session avec prise de conscience forte."
    if page_type == "appointment":
        return "TYPE : RDV. But : réserver un diagnostic simple et rassurant."
    if page_type == "bridge":
        return "TYPE : BRIDGE PAGE. But : créer confiance et transition vers l'étape suivante."
    if page_type == "sales":
        return "TYPE : LANDING VENTE. But : désir + confiance + passage à l'achat, sans surpromesse."
    return "TYPE : MODULE COURT. Répondre uniquement au bouton demandé."


def _copilot_options_block(
    *,
    objective: Optional[str],
    angle: Optional[str],
    audience: Optional[str],
    tone: Optional[str],
    max_length: int,
    cta_url: Optional[str],
    page_type: str,
) -> str:
    return f"""
OPTIONS COPILOTE À RESPECTER :
Objectif : {_clip(objective, 90) or "Générer des leads"}
Type de page : {page_type}
Angle : {_clip(angle, 90) or "conversion claire"}
Audience : {_clip(audience, 120) or "audience froide ou tiède"}
Ton : {_clip(tone, 90) or "humain premium"}
Longueur automatique recommandée : {max_length} caractères maximum de sécurité, tous blocs inclus
URL CTA : {_clip(cta_url, 220) or "à renseigner"}
""".strip()


def _goal_instruction(goal: str, page_type: str, max_length: int) -> str:
    value = str(goal or "landing_complete")

    if value == "hooks":
        return "Produit exactement 10 hooks premium, numérotés de 1 à 10. Chaque hook doit toucher une douleur, un désir ou une objection différente. Pas de conseil, pas de remplissage."
    if value == "cta":
        return "Produit exactement 10 CTA de lead magnet premium, orientés capture email. Mélange CTA doux, émotionnels et directs. Aucun CTA générique du type Transformez votre vie."
    if value == "benefits":
        return "Produit exactement 8 bénéfices premium : résultat concret + émotion débloquée + situation vécue. Pas de bénéfices génériques."
    if value == "variants":
        return "Produit 3 variantes A/B/C : hook, micro-promesse, CTA. Très court."
    if value == "rewrite_landing":
        return "Réécris le contenu fourni en blocs plus courts. Ne rajoute pas de longueur."

    if page_type == "lead_magnet":
        return (
            "Rédige un Lead Magnet Expert final, prêt à injecter, en sections séparées par les marqueurs [[LGD_BLOCK:...]]. "
            "Chaque section doit pouvoir devenir un calque texte distinct, mais le texte visible ne doit contenir aucun label technique. "
            "Objectif : capture email maximale, pas vente directe. "
            "Minimum 8 sections obligatoires pour landing_complete. "
            "Le rendu doit être plus fort qu'une réponse ChatGPT générique : persona précis, scène concrète, douleur cachée, désir, mécanisme, objection killer et CTA."
        )

    return f"Produit une structure {page_type} courte en blocs injectables. Aucun doublon."


def _format_rules(page_type: str, max_length: int, cta_url: Optional[str]) -> str:
    if page_type == "lead_magnet":
        return f"""
FORMAT TECHNIQUE OBLIGATOIRE POUR LE PARSER FRONTEND.
Les marqueurs [[LGD_BLOCK:...]] sont obligatoires, mais le texte après chaque marqueur doit être du contenu final visible, sans consigne.

[[LGD_BLOCK:HERO]]
Rédige directement le hero final visible : une accroche émotionnelle précise qui arrête le scroll, une micro-promesse gratuite et un CTA d'opt-in. Le hero doit nommer une situation vécue, pas une promesse vague. Intègre naturellement l'URL si elle est fournie : {_clip(cta_url, 220) or "à renseigner"}.

[[LGD_BLOCK:IDENTIFICATION]]
Rédige directement la scène d'identification finale avec détails psychologiques concrets : formations achetées, surcharge d'informations, peur de recommencer, honte silencieuse, fatigue mentale. Le prospect doit penser : « c'est exactement moi ».

[[LGD_BLOCK:AGITATION]]
Rédige directement l'agitation finale : le coût concret de rester bloqué, la frustration de voir les autres avancer, le doute intérieur, sans conseil ni analyse.

[[LGD_BLOCK:MICRO_TRANSFORMATION]]
Rédige directement la micro-transformation promise par le lead magnet : passer du chaos à une première action claire, visible et réalisable.

[[LGD_BLOCK:CE_QUE_TU_RECOIS]]
Rédige directement 5 lignes finales sur ce que le prospect reçoit dans le guide. Chaque ligne doit donner envie de laisser son email, avec un résultat concret.

[[LGD_BLOCK:MECANISME]]
Rédige directement le mécanisme final : pourquoi ce lead magnet aide vraiment là où les formations génériques échouent, sans promesse magique.

[[LGD_BLOCK:OBJECTION_KILLER]]
Rédige directement les réponses finales aux objections fortes : pas le temps, déjà essayé, pas d'audience, peur d'échouer encore.

[[LGD_BLOCK:REASSURANCE]]
Rédige directement la réassurance finale : débutant accepté, pas besoin d'être influenceur, progression réaliste.

[[LGD_BLOCK:CTA_FINAL]]
Rédige directement le CTA final : une phrase émotionnelle + un appel clair à laisser son email. Le CTA doit vendre le guide gratuit, pas la formation. Ajoute naturellement l'URL CTA si elle est fournie : {_clip(cta_url, 220) or "à renseigner"}.

RÈGLES NON NÉGOCIABLES :
- Minimum obligatoire : 8 marqueurs [[LGD_BLOCK:...]].
- N'écris jamais BLOC 1, TITRE:, SOUS-TITRE:, CTA:, DOULEUR:, BÉNÉFICES:, QUESTION:, RÉPONSE: dans le contenu visible.
- N'écris jamais des conseils ni une analyse. Écris uniquement la page finale.
- N'écris jamais « voici », « clarifie », « renforce », « augmente », « tu peux », « structure », « à modifier », « rédige », « directement », « final visible », « consigne ».
- Ne renvoie jamais une seule section pour Landing complète.
TOTAL MAXIMUM DE SÉCURITÉ : {max_length} caractères.
""".strip()

    return f"""
FORMAT TECHNIQUE OBLIGATOIRE POUR LE PARSER FRONTEND :
[[LGD_BLOCK:HERO]]
Texte final du hero, sans préfixe technique.

[[LGD_BLOCK:DOULEUR]]
Texte final de la douleur, sans préfixe technique.

[[LGD_BLOCK:PROMESSE]]
Texte final de la promesse, sans préfixe technique.

[[LGD_BLOCK:MECANISME]]
Texte final du mécanisme, sans préfixe technique.

[[LGD_BLOCK:CTA_FINAL]]
Texte final du CTA avec URL si fournie : {_clip(cta_url, 220) or "à renseigner"}

TOTAL MAXIMUM DE SÉCURITÉ : {max_length} caractères.
""".strip()


def _sanitize_done_for_you_output(text: str) -> str:
    forbidden_starts = (
        "voici ",
        "voici la structure",
        "structure ",
        "conseil",
        "clarifie",
        "renforce",
        "augmente",
        "tu peux",
        "vous pouvez",
        "à faire",
        "a faire",
        "passe d'une simple page",
        "passe d’une simple page",
    )
    cleaned_lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        low = line.strip().lower()
        if any(low.startswith(prefix) for prefix in forbidden_starts):
            continue
        # Retire les labels techniques en début de ligne s'ils apparaissent malgré l'instruction.
        for prefix in ("TITRE:", "SOUS-TITRE:", "SOUS TITRE:", "CTA:", "URL CTA:", "DOULEUR:", "BÉNÉFICES:", "BENEFICES:", "PROMESSE:", "QUESTION:", "RÉPONSE:", "REPONSE:"):
            if line.strip().upper().startswith(prefix):
                line = line.strip()[len(prefix):].strip()
                break
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _extract_offer_hint(brief: str) -> str:
    text = str(brief or "").strip()
    for marker in ("OFFRE :", "Offre / sujet :", "Offre:", "Sujet / offre"):
        if marker.lower() in text.lower():
            idx = text.lower().find(marker.lower())
            chunk = text[idx + len(marker):].strip().splitlines()[0].strip()
            if chunk:
                return _clip(chunk, 180)
    return _clip(text.splitlines()[0] if text else "ton offre", 180)


def _fallback_landing_blocks(*, brief: str, cta_url: Optional[str]) -> str:
    offer = _extract_offer_hint(brief)
    url = _clip(cta_url, 220) or ""
    url_line = f"\n{url}" if url else ""
    return f"""
[[LGD_BLOCK:HERO]]
Vous avez acheté des formations, testé des idées, regardé des vidéos… mais rien n’a vraiment bougé. Recevez le guide gratuit pour transformer {offer} en première action claire, simple et visible.{url_line}

[[LGD_BLOCK:IDENTIFICATION]]
Vous n’avez pas besoin d’une énième promesse magique. Vous avez besoin de savoir quoi faire maintenant, dans quel ordre, sans vous perdre dans les tunnels, les outils et les méthodes qui se contredisent.

[[LGD_BLOCK:AGITATION]]
Chaque semaine passée à hésiter renforce la même impression : les autres avancent, pendant que vous recommencez encore une nouvelle formation sans publier, sans vendre, sans vraie direction.

[[LGD_BLOCK:MICRO_TRANSFORMATION]]
Ce guide vous aide à identifier la première étape concrète pour sortir de la dispersion et construire une page simple qui capte des prospects au lieu de rester bloqué dans la préparation.

[[LGD_BLOCK:CE_QUE_TU_RECOIS]]
Un angle clair pour présenter votre offre sans paraître forcé.\nUne structure de page pensée pour récupérer des emails.\nLes erreurs qui bloquent les débutants avant leur première vente.\nUn chemin simple pour passer de l’idée à l’action.\nUn CTA prêt à utiliser pour inviter le prospect à laisser son email.

[[LGD_BLOCK:MECANISME]]
La méthode repose sur une idée simple : arrêter de vendre trop tôt, créer d’abord une micro-victoire, puis utiliser l’email pour construire la confiance avant la vente.

[[LGD_BLOCK:OBJECTION_KILLER]]
Pas d’audience ? Commencez avec une page claire.\nPas technique ? Le guide simplifie les étapes.\nDéjà essayé ? Cette fois, l’objectif n’est pas de tout faire, mais de lancer la première action qui attire un prospect.

[[LGD_BLOCK:REASSURANCE]]
C’est pensé pour les débutants, les personnes qui manquent de temps et celles qui veulent avancer sans devenir influenceur, sans jargon et sans promesse irréaliste.

[[LGD_BLOCK:CTA_FINAL]]
Laissez votre email et recevez le guide pour arrêter de tourner en rond et poser la première brique de votre système de prospects.{url_line}
""".strip()



def _is_strong_landing_output(text: str) -> bool:
    raw = str(text or "")
    marker_count = raw.count("[[LGD_BLOCK:")
    visible = _sanitize_done_for_you_output(raw).strip()
    forbidden = ("voici la structure", "clarifie", "renforce", "augmente", "tu peux", "vous pouvez", "conseil", "transformez votre vie", "libérez votre potentiel", "solution ultime", "révolutionnez")
    if any(word in visible.lower() for word in forbidden):
        return False
    return marker_count >= 6 and len(visible) >= 900


def _landing_needs_strict_retry(goal: str, page_type: str, content: str) -> bool:
    return _norm(goal) == "landing_complete" and page_type == "lead_magnet" and not _is_strong_landing_output(content)

def build_lead_prompt(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str],
    business_context: Optional[str],
    memories: Iterable[dict],
    objective: Optional[str] = None,
    angle: Optional[str] = None,
    audience: Optional[str] = None,
    tone: Optional[str] = None,
    max_length: Optional[int] = None,
    cta_url: Optional[str] = None,
    page_type: Optional[str] = None,
) -> tuple[str, int, str]:
    safe_goal = _clip(goal, 80)
    safe_brief = _clip(brief, MAX_BRIEF_CHARS)
    safe_style = _clip(emotional_style, 140) or "humain premium"
    safe_context = _clip(business_context, 200) or "lead generation premium"
    safe_max_length = _safe_int(max_length, DEFAULT_OUTPUT_CHARS)
    inferred_page_type = _infer_page_type(safe_goal, objective, page_type)

    prompt = f"""
{_page_strategy(inferred_page_type)}

{_copilot_options_block(
    objective=objective,
    angle=angle,
    audience=audience,
    tone=tone,
    max_length=safe_max_length,
    cta_url=cta_url,
    page_type=inferred_page_type,
)}

BRIEF UTILISATEUR :
{safe_brief}

STYLE COMPLÉMENTAIRE : {safe_style}
CONTEXTE MÉTIER : {safe_context}
MÉMOIRE UTILE :
{_memory_block(memories)}

MISSION :
{_goal_instruction(safe_goal, inferred_page_type, safe_max_length)}

CONTRAINTES STRICTES :
- Longueur automatique : utilise assez de texte pour produire une vraie page complète, sans dépasser {safe_max_length} caractères.
- Réponds uniquement avec le contenu final demandé, sans introduction, commentaire, conseil ni phrase méta.
- N'écris pas une page de vente si l'objectif est de générer des leads.
- Ne parle pas d'achat direct dans le HERO d'un lead magnet.
- Chaque bloc doit être propre, finalisé, positionnable séparément dans le canvas, et ne jamais être une consigne.
- Utilise l'angle, l'audience et le ton fournis.
- Si l'angle mentionne MRR : parle de formations achetées, dispersion, surcharge d'informations, inaction, première vente.
- Si l'objectif est génération de leads : vends l'envie de recevoir le lead magnet, pas l'achat de l'offre principale.
- Interdiction absolue de donner des conseils : le texte doit être final, prêt à utiliser. Ne jamais écrire « voici », « voici la structure », « clarifie », « renforce », « augmente », « structure », « à modifier », « tu peux ».
- Si le ton est storytelling : ajoute une micro-scène concrète, mais sans transformer la page en récit long.
- Chaque bloc doit apporter une nouvelle raison de laisser son email.
- Ne répète pas le même bloc sous deux formes.
- Pas de markdown décoratif, pas de tableau, pas de guillemets.

{_format_rules(inferred_page_type, safe_max_length, cta_url)}
""".strip()

    return prompt, safe_max_length, inferred_page_type


def _text_from_chat_response(response: Any) -> str:
    try:
        if not getattr(response, "choices", None):
            return ""
        message = response.choices[0].message
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    value = item.get("text") or item.get("content") or ""
                    if isinstance(value, dict):
                        value = value.get("value") or value.get("text") or ""
                    if value:
                        parts.append(str(value))
                else:
                    value = getattr(item, "text", None) or getattr(item, "content", None) or ""
                    if value:
                        parts.append(str(value))
            return "\n".join(parts).strip()
    except Exception:
        return ""
    return ""


def _text_from_responses_response(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    try:
        for output in getattr(response, "output", []) or []:
            for content in getattr(output, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(str(text))
    except Exception:
        pass

    return "\n".join(parts).strip()


def _chat_completion(client: Any, *, model: str, messages: list[dict[str, str]], char_limit: int) -> str:
    max_out = _target_output_tokens(char_limit)

    try:
        if model.lower().startswith("gpt-5"):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_out,
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.72,
                max_tokens=max_out,
            )
    except TypeError:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_out,
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "max_tokens" in error_text or "temperature" in error_text or "unsupported" in error_text:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_out,
            )
        else:
            raise

    return _text_from_chat_response(response)


def _responses_completion(client: Any, *, model: str, prompt: str, char_limit: int) -> str:
    if not hasattr(client, "responses"):
        return ""

    max_out = _target_output_tokens(char_limit)

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=max_out,
        )
    except TypeError:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=max_out,
        )
    except Exception:
        return ""

    return _text_from_responses_response(response)


def _dedupe_near_lines(text: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        key = line.lower().strip(" -•:;.!?")
        if key and len(key) > 24:
            if key in seen:
                continue
            seen.add(key)
        lines.append(line)
    return "\n".join(lines).strip()


def _trim_to_char_limit(text: str, char_limit: int) -> str:
    cleaned = _dedupe_near_lines(str(text or "").strip())
    if len(cleaned) <= char_limit:
        return cleaned

    cut = cleaned[:char_limit].rstrip()
    break_points = [cut.rfind("\n\nBLOC"), cut.rfind("\nBLOC"), cut.rfind("\n- "), cut.rfind("\n")]
    last_break = max(break_points)
    if last_break > int(char_limit * 0.65):
        cut = cut[:last_break].rstrip()
    return cut.rstrip()


def _compact_output(text: str, *, char_limit: int, page_type: str, brief: str = "", cta_url: Optional[str] = None) -> str:
    hard_limit = _safe_int(char_limit, DEFAULT_OUTPUT_CHARS)
    cleaned = _sanitize_done_for_you_output(_trim_to_char_limit(text, hard_limit))

    # Sécurité anti-page-de-vente trop longue : si un lead magnet dépasse encore,
    # on retire les blocs secondaires au lieu de renvoyer un pavé.
    if page_type == "lead_magnet" and len(cleaned) > hard_limit:
        parts = cleaned.split("\n\nBLOC")
        cleaned = parts[0]
        for part in parts[1:5]:
            candidate = cleaned + "\n\nBLOC" + part
            if len(candidate) > hard_limit:
                break
            cleaned = candidate

    return cleaned.strip()


def generate_lead_content(
    *,
    goal: str,
    brief: str,
    emotional_style: Optional[str] = None,
    business_context: Optional[str] = None,
    memories: Optional[Iterable[dict]] = None,
    objective: Optional[str] = None,
    angle: Optional[str] = None,
    audience: Optional[str] = None,
    tone: Optional[str] = None,
    max_length: Optional[int] = None,
    cta_url: Optional[str] = None,
    page_type: Optional[str] = None,
) -> str:
    client = _get_client()
    prompt, char_limit, inferred_page_type = build_lead_prompt(
        goal=goal,
        brief=brief,
        emotional_style=emotional_style,
        business_context=business_context,
        memories=list(memories or [])[:MAX_MEMORY_ITEMS],
        objective=objective,
        angle=angle,
        audience=audience,
        tone=tone,
        max_length=max_length,
        cta_url=cta_url,
        page_type=page_type,
    )

    model = _choose_model()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    errors: list[str] = []
    candidate_models = [model]
    fallback = _fallback_model(model)
    if fallback not in candidate_models:
        candidate_models.append(fallback)

    for candidate_model in candidate_models:
        try:
            content = _chat_completion(client, model=candidate_model, messages=messages, char_limit=char_limit)
            if content:
                compact = _compact_output(content, char_limit=char_limit, page_type=inferred_page_type, brief=brief, cta_url=cta_url)
                if _landing_needs_strict_retry(goal, inferred_page_type, compact):
                    strict_prompt = prompt + "\n\nCORRECTION OBLIGATOIRE : ta réponse précédente était trop courte ou pas assez structurée. Génère maintenant une vraie landing complète DONE FOR YOU avec au moins 8 marqueurs [[LGD_BLOCK:...]], du texte final visible, aucun conseil, aucun label technique visible, aucune phrase méta."
                    strict_messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": strict_prompt},
                    ]
                    retry = _chat_completion(client, model=candidate_model, messages=strict_messages, char_limit=max(char_limit, 7200))
                    retry_compact = _compact_output(retry, char_limit=max(char_limit, 7200), page_type=inferred_page_type, brief=brief, cta_url=cta_url) if retry else ""
                    if _is_strong_landing_output(retry_compact):
                        return retry_compact
                return compact
            content = _responses_completion(client, model=candidate_model, prompt=prompt, char_limit=char_limit)
            if content:
                compact = _compact_output(content, char_limit=char_limit, page_type=inferred_page_type, brief=brief, cta_url=cta_url)
                if _landing_needs_strict_retry(goal, inferred_page_type, compact):
                    strict_prompt = prompt + "\n\nCORRECTION OBLIGATOIRE : génère une vraie landing complète DONE FOR YOU avec au moins 8 marqueurs [[LGD_BLOCK:...]], du texte final visible, aucun conseil, aucun label technique visible, aucune phrase méta."
                    retry = _responses_completion(client, model=candidate_model, prompt=strict_prompt, char_limit=max(char_limit, 7200))
                    retry_compact = _compact_output(retry, char_limit=max(char_limit, 7200), page_type=inferred_page_type, brief=brief, cta_url=cta_url) if retry else ""
                    if _is_strong_landing_output(retry_compact):
                        return retry_compact
                return compact
            errors.append(f"{candidate_model}: réponse vide")
        except Exception as exc:
            errors.append(f"{candidate_model}: {exc}")

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
