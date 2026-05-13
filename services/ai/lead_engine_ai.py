from __future__ import annotations

import os
import re
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
# Version PROD V10.6 — Premium multi-blocs verrouillé
# Objectif : produire une vraie landing lead magnet structurée,
# sans faux fallback silencieux, sans sortie 1 bloc, sans réponse coupée.
# ============================================================

SYSTEM_PROMPT = """
Tu es LEAD ENGINE LGD, copywriter conversion senior, stratège lead magnet et expert du marketing digital premium.
Tu ne coaches pas l'utilisateur : tu produis le contenu final à sa place.

RÈGLE PRIORITAIRE : SORTIE MULTI-BLOCS STRICTE.
Pour une landing complète, tu dois produire une page finale exploitable en sections séparées par les marqueurs [[LGD_BLOCK:...]].
Ces marqueurs servent uniquement au parser frontend. Le texte visible qui suit chaque marqueur doit être propre, final et utilisable tel quel.

RÈGLE PERSONA-FIRST.
Avant d'écrire, tu lis le brief comme un stratège marketing humain. Tu extrais silencieusement :
- l'offre exacte ;
- le modèle économique ;
- la cible réelle ;
- les personas probables ;
- la situation de vie ;
- les douleurs visibles ;
- les douleurs cachées ;
- les objections ;
- la promesse crédible ;
- le niveau émotionnel demandé ;
- le type de conversion attendu.

Si le brief mentionne une affiliation, une commission, un programme partenaire ou une rémunération récurrente :
tu comprends que la page ne doit PAS vendre uniquement le produit final.
Tu dois créer un lead magnet qui capte l'email, prépare la confiance et rend l'opportunité crédible.
Tu dois faire sentir le bénéfice utilisateur : créer une source de revenu progressive, simple à comprendre, sans promesse magique.

Si le brief mentionne LGD, Le Générateur Digital, automatisation, IA, marketing digital, tunnels, emails, contenus ou business en ligne :
tu dois positionner LGD comme un outil d'action concret, pas comme une promesse vague.
LGD aide à passer de l'idée à l'exécution : contenu, lead magnet, emails, pages, stratégie, conversion.

Mode obligatoire : DONE FOR YOU.
L'utilisateur donne une offre, une cible, un angle et un objectif. Tu rédiges directement le lead magnet, la page ou les éléments demandés.
Tu ne dois jamais expliquer comment rédiger : tu rédiges à sa place.
Le contenu visible final doit être utilisable tel quel dans une vraie page LGD.

Interdits absolus :
- écrire « voici », « voici la structure », « clarifie », « renforce », « augmente », « tu peux », « il faudrait », « à adapter », « à modifier », « conseil », « structure pour », « passe d’une simple page » ;
- donner des conseils au lieu de rédiger le contenu final ;
- afficher des étiquettes techniques dans le texte visible final ;
- produire un email ;
- vendre directement l'offre principale quand l'objectif est la capture de leads ;
- écrire un texte IA générique du type « transformez votre vie », « libérez votre potentiel », « solution ultime », « révolutionnez votre business ».

Niveau attendu : humain, premium, précis, émotionnel, crédible, expert marketing digital, jamais robotique.
Chaque section doit faire avancer le lecteur : attention → identification → tension émotionnelle → désir → confiance → action.

Tu dois utiliser les douleurs cachées quand elles sont présentes ou déductibles :
honte de ne pas réussir, fatigue mentale, peur du regard des proches, impression d'être en retard,
peur d'avoir encore échoué, peur de ne pas être fait pour réussir, peur de reperdre de l'argent.

Tu dois transformer les bénéfices rationnels en bénéfices vécus :
retrouver de la clarté, reprendre confiance, savoir quoi faire aujourd'hui, sentir qu'on avance enfin,
capturer un email, poser une première brique concrète, créer une source de revenu progressive.

Tu ne copies jamais les consignes de format dans la réponse.
Tu remplaces toujours les consignes par du texte final concret.
""".strip()


MAX_BRIEF_CHARS = 5200
MAX_MEMORY_ITEMS = 1
MAX_MEMORY_CHARS = 180
DEFAULT_OUTPUT_CHARS = 8200
MAX_OUTPUT_CHARS = 12000
MIN_LANDING_CHARS = 2400
MIN_LANDING_BLOCKS = 8

REQUIRED_LANDING_BLOCKS = [
    "HERO",
    "IDENTIFICATION",
    "AGITATION",
    "MICRO_TRANSFORMATION",
    "CE_QUE_TU_RECOIS",
    "MECANISME",
    "OBJECTION_KILLER",
    "REASSURANCE",
    "CTA_FINAL",
]

FORBIDDEN_VISIBLE_FRAGMENTS = (
    "voici la structure",
    "voici une structure",
    "clarifie",
    "renforce",
    "augmente",
    "tu peux",
    "vous pouvez",
    "conseil",
    "à adapter",
    "a adapter",
    "à modifier",
    "a modifier",
    "transformez votre vie",
    "libérez votre potentiel",
    "solution ultime",
    "révolutionnez votre business",
)


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
    return max(1200, min(n, MAX_OUTPUT_CHARS))


def _target_output_tokens(char_limit: int) -> int:
    # Correctif V10.6 : l'ancien plafond était trop bas et provoquait des sorties tronquées.
    # Pour une vraie landing française, on autorise assez de sortie pour 8 à 9 blocs.
    estimated = int(max(char_limit, DEFAULT_OUTPUT_CHARS) / 2.45) + 700
    return max(2200, min(5200, estimated))


def _memory_block(memories: Iterable[dict]) -> str:
    lines: list[str] = []

    for item in list(memories or [])[:MAX_MEMORY_ITEMS]:
        memory_type = str(item.get("memory_type") or "memoire")[:40]
        goal = _clip(str(item.get("goal") or ""), 70)
        content = _clip(str(item.get("content") or ""), MAX_MEMORY_CHARS)
        business = _clip(str(item.get("business_context") or ""), 100)

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
            "Structure la page comme un vrai tunnel psychologique : accroche, identification, agitation, micro-transformation, "
            "contenu reçu, mécanisme, objections, réassurance et CTA. Si le brief parle d'affiliation, explique l'opportunité "
            "sans la rendre magique : capter l'email, éduquer, montrer le chemin et préparer la vente."
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
Objectif : {_clip(objective, 120) or "Générer des leads"}
Type de page : {page_type}
Angle : {_clip(angle, 140) or "conversion claire"}
Audience : {_clip(audience, 180) or "audience froide ou tiède"}
Ton : {_clip(tone, 120) or "humain premium"}
Longueur automatique recommandée : {max_length} caractères maximum de sécurité, tous blocs inclus
URL CTA : {_clip(cta_url, 240) or "à renseigner"}
""".strip()


def _goal_instruction(goal: str, page_type: str, max_length: int) -> str:
    value = str(goal or "landing_complete")

    if value == "hooks":
        return (
            "Produit exactement 10 hooks premium numérotés de 1 à 10. "
            "Chaque hook doit cibler une douleur ou un désir différent : argent, temps, famille, honte silencieuse, surcharge d'infos, peur d'échouer, envie de liberté, besoin de première action. "
            "Aucun conseil, aucun remplissage, aucun hook générique. Chaque hook doit pouvoir être utilisé tel quel sur une landing."
        )
    if value == "cta":
        return (
            "Produit exactement 10 CTA premium pour capture email, numérotés de 1 à 10. "
            "Ils doivent donner envie de recevoir le guide maintenant, sans vendre directement l'offre principale. "
            "Mélange : CTA doux, CTA émotionnels, CTA directs, CTA curiosité. Aucun CTA générique."
        )
    if value == "benefits":
        return (
            "Produit exactement 8 bénéfices premium numérotés de 1 à 8 : résultat concret + émotion débloquée + situation vécue. "
            "Chaque bénéfice doit être spécifique au brief, pas générique."
        )
    if value == "variants":
        return "Produit 3 variantes A/B/C : hook, micro-promesse, CTA. Très court."
    if value == "rewrite_landing":
        return "Réécris le contenu fourni en blocs plus courts. Ne rajoute pas de longueur."

    if page_type == "lead_magnet":
        return (
            "Rédige un Lead Magnet Expert final, prêt à injecter, en sections séparées par les marqueurs [[LGD_BLOCK:...]]. "
            "Chaque section doit pouvoir devenir un calque texte distinct, mais le texte visible ne doit contenir aucun label technique. "
            "Objectif : capture email maximale, pas vente directe. "
            "Minimum 9 sections obligatoires pour landing_complete. "
            "Chaque section doit contenir au moins 2 phrases concrètes, sauf CTA_FINAL qui peut être plus direct. "
            "Le rendu doit être plus fort qu'une réponse ChatGPT générique : angle précis, émotion, désir, mécanisme, objection killer et CTA."
        )

    return f"Produit une structure {page_type} courte en blocs injectables. Aucun doublon."


def _format_rules(page_type: str, max_length: int, cta_url: Optional[str]) -> str:
    if page_type == "lead_magnet":
        return f"""
FORMAT TECHNIQUE OBLIGATOIRE POUR LE PARSER FRONTEND.
Utilise exactement les 9 marqueurs ci-dessous, dans cet ordre, une seule fois chacun.
Les marqueurs [[LGD_BLOCK:...]] sont obligatoires, mais le texte après chaque marqueur doit être du contenu final visible, sans consigne.

[[LGD_BLOCK:HERO]]
Accroche émotionnelle + micro-promesse gratuite + appel à l'opt-in. Intègre naturellement l'URL si elle est fournie : {_clip(cta_url, 240) or "à renseigner"}.

[[LGD_BLOCK:IDENTIFICATION]]
Scène d'identification : le prospect doit se reconnaître dans sa situation réelle.

[[LGD_BLOCK:AGITATION]]
Coût concret de rester bloqué : temps perdu, fatigue mentale, honte silencieuse, peur d'échouer encore.

[[LGD_BLOCK:MICRO_TRANSFORMATION]]
Micro-transformation promise par le lead magnet : clarté, première action, chemin réaliste.

[[LGD_BLOCK:CE_QUE_TU_RECOIS]]
4 à 5 lignes finales sur ce que le prospect reçoit dans le guide. Pas de liste technique froide.

[[LGD_BLOCK:MECANISME]]
Pourquoi ce lead magnet aide vraiment : logique simple, action progressive, sans promesse magique.

[[LGD_BLOCK:OBJECTION_KILLER]]
Réponses finales aux objections fortes : pas le temps, déjà essayé, pas d'audience, peur d'échouer encore.

[[LGD_BLOCK:REASSURANCE]]
Réassurance finale : débutant accepté, pas besoin d'être influenceur, progression réaliste, pas de bullshit.

[[LGD_BLOCK:CTA_FINAL]]
CTA final : phrase émotionnelle + appel clair à laisser son email. Ajoute naturellement l'URL CTA si elle est fournie : {_clip(cta_url, 240) or "à renseigner"}.

RÈGLES NON NÉGOCIABLES :
- Minimum obligatoire : 9 marqueurs [[LGD_BLOCK:...]].
- Ne renvoie jamais une seule section pour Landing complète.
- Ne renvoie jamais seulement HERO ou HERO + IDENTIFICATION.
- Si tu manques de place, raccourcis chaque bloc, mais garde les 9 blocs.
- N'écris jamais BLOC 1, TITRE:, SOUS-TITRE:, CTA:, DOULEUR:, BÉNÉFICES:, QUESTION:, RÉPONSE: dans le contenu visible.
- N'écris jamais des conseils ni une analyse. Écris uniquement la page finale.
- N'écris jamais « voici », « clarifie », « renforce », « augmente », « tu peux », « structure », « à modifier », « rédige », « directement », « final visible », « consigne ».
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
Texte final du CTA avec URL si fournie : {_clip(cta_url, 240) or "à renseigner"}

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
    labels = (
        "TITRE:",
        "SOUS-TITRE:",
        "SOUS TITRE:",
        "CTA:",
        "URL CTA:",
        "DOULEUR:",
        "BÉNÉFICES:",
        "BENEFICES:",
        "PROMESSE:",
        "QUESTION:",
        "RÉPONSE:",
        "REPONSE:",
    )

    cleaned_lines: list[str] = []
    for raw in str(text or "").replace("```", "").splitlines():
        line = raw.rstrip()
        low = line.strip().lower()
        if any(low.startswith(prefix) for prefix in forbidden_starts):
            continue
        for prefix in labels:
            if line.strip().upper().startswith(prefix):
                line = line.strip()[len(prefix) :].strip()
                break
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned


def _prompt_brain_context(brief: str, objective: Optional[str], angle: Optional[str], audience: Optional[str], tone: Optional[str]) -> str:
    raw = " ".join([
        str(brief or ""),
        str(objective or ""),
        str(angle or ""),
        str(audience or ""),
        str(tone or ""),
    ]).lower()

    signals: list[str] = []

    if any(word in raw for word in ["affiliation", "commission", "partenaire", "récurrent", "recurrent", "60%"]):
        signals.append(
            "MODÈLE DÉTECTÉ : affiliation / commission récurrente. "
            "Ne vends pas brutalement le produit. Crée une page de capture qui vend l'envie de découvrir une opportunité simple, crédible et progressive. "
            "Insiste sur la confiance, la transparence, l'action concrète et la construction d'un revenu complémentaire, sans promesse magique."
        )

    if any(word in raw for word in ["lgd", "générateur digital", "generateur digital", "le générateur digital"]):
        signals.append(
            "OFFRE DÉTECTÉE : Le Générateur Digital. "
            "Présente LGD comme une plateforme d'action marketing : créer des contenus, pages, emails, lead magnets et tunnels avec l'IA. "
            "Évite le discours outil-technique ; montre le bénéfice concret pour une personne bloquée."
        )

    if any(word in raw for word in ["maman", "mère", "mere", "congé maternité", "foyer", "enfants", "parent"]):
        signals.append(
            "PERSONA POSSIBLE : parent / maman ou papa qui veut gagner en liberté sans sacrifier sa famille. "
            "Utilise la motivation temps-famille, revenu maison, fierté et reprise de contrôle."
        )

    if any(word in raw for word in ["salarié", "salarie", "job", "travail", "patron", "burnout", "routine"]):
        signals.append(
            "PERSONA POSSIBLE : salarié fatigué. "
            "Utilise la fatigue du quotidien, l'envie de ne plus subir, le besoin de complément de revenu et de plan clair."
        )

    if any(word in raw for word in ["formation", "mrr", "dropshipping", "crypto", "ia", "freelancing", "sans résultat", "sans resultats"]):
        signals.append(
            "PERSONA POSSIBLE : acheteur de formations bloqué. "
            "Utilise la surcharge d'informations, la honte silencieuse, la peur d'encore abandonner, la frustration de voir les autres réussir."
        )

    if not signals:
        signals.append(
            "Aucun persona explicite détecté. Infère un persona crédible à partir de l'offre, de l'objectif, de l'audience et de l'angle. "
            "Reste concret, humain et orienté conversion."
        )

    return "\n".join(f"- {item}" for item in signals)


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
    safe_style = _clip(emotional_style, 180) or "humain premium"
    safe_context = _clip(business_context, 260) or "lead generation premium"
    safe_max_length = _safe_int(max_length, DEFAULT_OUTPUT_CHARS)
    inferred_page_type = _infer_page_type(safe_goal, objective, page_type)

    if _norm(safe_goal) == "landing_complete" and inferred_page_type == "lead_magnet":
        safe_max_length = max(safe_max_length, DEFAULT_OUTPUT_CHARS)

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

PROMPT BRAIN LGD :
{_prompt_brain_context(safe_brief, objective, angle, audience, tone)}

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
- Si le brief parle d'affiliation ou de commission : vends la découverte d'une opportunité crédible et progressive, jamais une promesse de richesse rapide.
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
                temperature=0.74,
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
        if key and len(key) > 34 and not key.startswith("[[lgd_block:"):
            if key in seen:
                continue
            seen.add(key)
        lines.append(line)
    return "\n".join(lines).strip()


def _landing_block_count(text: str) -> int:
    return len(re.findall(r"\[\[LGD_BLOCK:[A-Z0-9_\-]+\]\]", str(text or "")))


def _missing_required_blocks(text: str) -> list[str]:
    raw = str(text or "")
    return [block for block in REQUIRED_LANDING_BLOCKS if f"[[LGD_BLOCK:{block}]]" not in raw]


def _visible_text(text: str) -> str:
    return re.sub(r"\[\[LGD_BLOCK:[A-Z0-9_\-]+\]\]", "", str(text or "")).strip()


def _trim_to_char_limit(text: str, char_limit: int, *, page_type: str = "modular") -> str:
    cleaned = _dedupe_near_lines(str(text or "").strip())
    if len(cleaned) <= char_limit:
        return cleaned

    if page_type == "lead_magnet":
        # Ne jamais couper une landing au milieu des blocs obligatoires.
        # On laisse une marge contrôlée plutôt que de renvoyer 1 ou 2 blocs.
        return cleaned[: min(len(cleaned), MAX_OUTPUT_CHARS)].rstrip()

    cut = cleaned[:char_limit].rstrip()
    break_points = [cut.rfind("\n\nBLOC"), cut.rfind("\nBLOC"), cut.rfind("\n- "), cut.rfind("\n")]
    last_break = max(break_points)
    if last_break > int(char_limit * 0.65):
        cut = cut[:last_break].rstrip()
    return cut.rstrip()


def _compact_output(text: str, *, char_limit: int, page_type: str) -> str:
    hard_limit = _safe_int(char_limit, DEFAULT_OUTPUT_CHARS)
    cleaned = _sanitize_done_for_you_output(_trim_to_char_limit(text, hard_limit, page_type=page_type))

    if not cleaned.strip():
        return ""

    return cleaned.strip()


def _is_landing_complete_goal(goal: str, page_type: str) -> bool:
    return _norm(goal) == "landing_complete" and page_type == "lead_magnet"


def _is_strong_landing_output(text: str) -> bool:
    raw = str(text or "")
    visible = _sanitize_done_for_you_output(_visible_text(raw)).strip()
    low = visible.lower()

    # Correctif PROD V10.7 : ne plus rejeter une vraie réponse OpenAI uniquement
    # parce qu'une expression naturelle comme « vous pouvez » apparaît dans un bloc.
    # On bloque seulement les sorties manifestement méta / consignes.
    hard_meta_fragments = (
        "voici la structure",
        "voici une structure",
        "structure de page",
        "à modifier",
        "a modifier",
        "à adapter",
        "a adapter",
        "rédige directement",
        "redige directement",
        "texte final visible",
        "consigne",
    )
    if any(fragment in low for fragment in hard_meta_fragments):
        return False
    if _landing_block_count(raw) < MIN_LANDING_BLOCKS:
        return False
    if _missing_required_blocks(raw):
        return False
    # Le frontend sait injecter 8/9 blocs même si la landing est concise.
    # On évite donc de transformer une vraie sortie structurée en erreur 502.
    if len(visible) < 1200:
        return False
    if raw.strip().endswith("[[LGD_BLOCK:IDENTIFICATION]]") or raw.strip().endswith("[[LGD_BLOCK:HERO]]"):
        return False
    return True


def _landing_quality_score(text: str) -> int:
    raw = str(text or "")
    visible = _visible_text(raw)
    score = 0
    score += _landing_block_count(raw) * 1000
    score -= len(_missing_required_blocks(raw)) * 700
    score += min(len(visible), 7000)
    if raw.strip().endswith("[[LGD_BLOCK:IDENTIFICATION]]") or raw.strip().endswith("[[LGD_BLOCK:HERO]]"):
        score -= 2000
    return score


def _strict_retry_prompt(prompt: str, attempt: int) -> str:
    return (
        prompt
        + f"\n\nRETRY LGD OBLIGATOIRE #{attempt} — LA RÉPONSE PRÉCÉDENTE ÉTAIT TROP FAIBLE OU INCOMPLÈTE. "
        + "Génère maintenant une vraie landing complète DONE FOR YOU avec exactement les 9 marqueurs obligatoires : "
        + ", ".join(f"[[LGD_BLOCK:{block}]]" for block in REQUIRED_LANDING_BLOCKS)
        + ". Chaque section doit contenir du texte final utilisable tel quel. "
        + "Interdiction absolue de fallback, de conseils, de plan, de phrase méta, de contenu générique. "
        + "Exploite l'offre, le persona, les douleurs cachées, l'affiliation/commission si présent, la capture email et le CTA. "
        + "Ne t'arrête pas après HERO. Continue jusqu'à CTA_FINAL."
    )


def _completion_attempt(client: Any, *, model: str, prompt: str, char_limit: int) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    content = _chat_completion(client, model=model, messages=messages, char_limit=char_limit)
    if content:
        return content

    return _responses_completion(client, model=model, prompt=prompt, char_limit=char_limit)


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

    is_landing = _is_landing_complete_goal(goal, inferred_page_type)
    if is_landing:
        char_limit = max(char_limit, DEFAULT_OUTPUT_CHARS)

    model = _choose_model()
    fallback = _fallback_model(model)
    candidate_models = [model]
    if fallback not in candidate_models:
        candidate_models.append(fallback)

    errors: list[str] = []
    weak_outputs: list[str] = []

    for candidate_model in candidate_models:
        attempts = [prompt]
        if is_landing:
            attempts.append(_strict_retry_prompt(prompt, 1))
            attempts.append(_strict_retry_prompt(prompt, 2))

        for index, attempt_prompt in enumerate(attempts, start=1):
            try:
                raw = _completion_attempt(
                    client,
                    model=candidate_model,
                    prompt=attempt_prompt,
                    char_limit=char_limit,
                )
                compact = _compact_output(raw, char_limit=char_limit, page_type=inferred_page_type) if raw else ""

                if not compact:
                    errors.append(f"{candidate_model} tentative {index}: réponse vide")
                    continue

                if is_landing:
                    if _is_strong_landing_output(compact):
                        return compact
                    weak_outputs.append(compact)
                    errors.append(
                        f"{candidate_model} tentative {index}: sortie faible "
                        f"({ _landing_block_count(compact) } blocs, manquants={','.join(_missing_required_blocks(compact)) or 'aucun'}, chars={len(_visible_text(compact))})"
                    )
                    continue

                return compact
            except Exception as exc:
                errors.append(f"{candidate_model} tentative {index}: {exc}")

    # Correctif PROD V10.7 : ne jamais transformer une vraie réponse OpenAI structurée
    # en erreur bloquante côté frontend. Si OpenAI fournit une sortie imparfaite mais
    # exploitable, on renvoie la meilleure version au lieu d'afficher
    # « Génération IA impossible ».
    if weak_outputs:
        best = sorted(weak_outputs, key=_landing_quality_score, reverse=True)[0]
        if is_landing and _landing_block_count(best) >= 2:
            return best
        return best

    if is_landing:
        diagnostic = " | ".join(errors[-6:]) or "sortie incomplète"
        raise RuntimeError(
            "Lead Engine IA n'a reçu aucune sortie exploitable depuis OpenAI. "
            f"Diagnostic: {diagnostic}"
        )

    raise RuntimeError("Réponse OpenAI vide pour Lead Engine. " + " | ".join(errors))
