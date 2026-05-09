from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT_DISPATCH = """
Tu es CMO IA Dispatch, le cerveau marketing stratégique de Le Générateur Digital.

Rôle strict :
- tu ne rédiges PAS le contenu final à la place des modules ;
- tu analyses le contexte utilisateur ;
- tu décides le levier prioritaire ;
- tu construis un contexte structuré exploitable par le bon module LGD.

Modules LGD :
- emailing : campagnes email orientées offre, séquence, objection, CTA ;
- lead_engine : lead magnet, landing page, promesse de capture, angle prospect ;
- editor : post/carrousel/visuel, hook, structure créative, caption directionnelle ;
- coach : plan d'action, clarification stratégique, exécution priorisée.

Règles absolues :
- français ;
- concret, précis, orienté business ;
- pas de contenu générique ;
- pas de contenu final long ;
- chaque champ doit aider le module cible à générer mieux que ChatGPT brut ;
- si une donnée manque, fais une hypothèse utile et explicite-la dans assumptions ;
- le CMO prépare le brief intelligent, le module produit ensuite.
""".strip()

SYSTEM_PROMPT_STRATEGY = """
Tu es CMO IA V5, le cerveau marketing autonome de Le Générateur Digital.
Tu prends une décision marketing claire et tu fournis une action prioritaire exploitable.
Réponse en français, concrète, directe, sans blabla.
""".strip()

_ALLOWED_MODULES = {"emailing", "lead_engine", "editor", "coach"}


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("Le package openai n'est pas installé sur le backend.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquante dans l'environnement backend.")

    return OpenAI(api_key=api_key)


def _choose_model() -> str:
    return (
        os.getenv("OPENAI_CMO_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {
        "diagnostic": raw.strip(),
        "decision": {
            "recommended_module": "coach",
            "priority_action": "Clarifier la stratégie avant de générer.",
            "reason": "La réponse IA n'a pas pu être structurée correctement.",
        },
        "context": {},
        "module_payloads": {},
        "assumptions": ["Réponse brute conservée dans diagnostic."],
        "warnings": ["JSON invalide retourné par le modèle."],
    }


def _normalize_module(value: str) -> str:
    module = _clean(value).lower()
    if module in {"email", "emailing", "email_campaigns", "campagne_email"}:
        return "emailing"
    if module in {"lead", "lead_engine", "lead-engine", "landing", "landing_page"}:
        return "lead_engine"
    if module in {"editor", "editeur", "éditeur", "post", "carrousel"}:
        return "editor"
    if module in {"coach", "coach_ia", "coach-ia"}:
        return "coach"
    return ""


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _fallback_dispatch(*, objective: str, blocker: str, target_module: str, audience: str, offer: str) -> Dict[str, Any]:
    module = _normalize_module(target_module) or "coach"
    clean_objective = _clean(objective, "Clarifier une action marketing rentable.")
    clean_blocker = _clean(blocker, "Le blocage principal n'est pas encore précisé.")
    clean_offer = _clean(offer, "offre à clarifier")
    clean_audience = _clean(audience, "audience à préciser")

    context = {
        "objective": clean_objective,
        "blocker": clean_blocker,
        "offer": clean_offer,
        "audience": clean_audience,
        "angle": f"Partir du blocage réel pour rendre {clean_offer} plus désirable.",
        "promise": f"Aider {clean_audience} à avancer malgré : {clean_blocker}.",
        "cta": "Passer à l'action maintenant",
        "tone": "premium, humain, direct",
    }

    return {
        "diagnostic": f"L'utilisateur veut : {clean_objective}. Le blocage identifié est : {clean_blocker}. Le CMO doit envoyer un brief structuré au module {module} au lieu de générer un contenu générique.",
        "decision": {
            "recommended_module": module,
            "priority_action": "Transmettre un contexte marketing cadré au module cible.",
            "reason": "Un brief structuré permet au module de produire un résultat aligné avec l'offre, la cible, la promesse et le CTA.",
        },
        "context": context,
        "module_payloads": _build_module_payloads(context),
        "assumptions": ["Fallback local utilisé uniquement si la sortie IA est incomplète."],
        "warnings": [],
    }


def _build_module_payloads(context: Dict[str, Any]) -> Dict[str, Any]:
    objective = _clean(context.get("objective"))
    blocker = _clean(context.get("blocker"))
    offer = _clean(context.get("offer"), "offre")
    audience = _clean(context.get("audience"), "audience")
    angle = _clean(context.get("angle"), f"Rendre {offer} évident pour {audience}")
    promise = _clean(context.get("promise"), f"Obtenir un résultat concret avec {offer}")
    cta = _clean(context.get("cta"), "Passer à l'action")
    tone = _clean(context.get("tone"), "premium, humain, direct")

    return {
        "emailing": {
            "module": "emailing",
            "campaign_goal": objective,
            "offer_name": offer,
            "target_audience": audience,
            "main_blocker": blocker,
            "conversion_angle": angle,
            "main_promise": promise,
            "primary_cta": cta,
            "tone": tone,
            "sequence_direction": [
                "Email 1 : faire résonner le problème et poser le coût de l'inaction.",
                "Email 2 : présenter le mécanisme de transformation derrière l'offre.",
                "Email 3 : lever l'objection principale et pousser vers le CTA.",
            ],
        },
        "lead_engine": {
            "module": "lead_engine",
            "lead_goal": f"Capturer des prospects intéressés par {offer}",
            "lead_magnet_angle": angle,
            "lead_magnet_promise": promise,
            "target_audience": audience,
            "problem_to_solve": blocker,
            "offer_bridge": offer,
            "cta_label": "Recevoir la ressource",
            "landing_direction": "Hero clair, bénéfice immédiat, 3 points de valeur, preuve simple, formulaire, CTA.",
        },
        "editor": {
            "module": "editor",
            "creative_goal": objective,
            "format_recommendation": "post",
            "hook_direction": angle,
            "body_direction": f"Montrer le blocage ({blocker}), révéler la promesse ({promise}), puis guider vers {cta}.",
            "visual_direction": "Visuel premium sombre/doré, message central court, contraste fort, CTA lisible.",
            "caption_direction": "Caption courte : problème, prise de conscience, promesse, CTA.",
        },
        "coach": {
            "module": "coach",
            "mission_title": f"Plan CMO — {offer}",
            "brief": f"Objectif : {objective}\nBlocage : {blocker}\nOffre : {offer}\nCible : {audience}\nAngle : {angle}\nPromesse : {promise}\nCTA : {cta}",
            "expected_output": "Plan d'action priorisé, prochaines étapes, risques à éviter, critères de validation.",
            "duration_minutes": 45,
        },
    }


def _build_dispatch_prompt(
    *,
    objective: str,
    blocker: str,
    target_module: str,
    niche: str,
    audience: str,
    offer: str,
    current_situation: str,
    constraints: str,
    preferred_channel: str,
    tone: str,
    user_level: str,
) -> str:
    normalized_module = _normalize_module(target_module) or "à décider"
    return f"""
OBJECTIF UTILISATEUR
{objective or "non précisé"}

BLOCAGE UTILISATEUR
{blocker or "non précisé"}

CONTEXTE BUSINESS
- Module demandé : {normalized_module}
- Niche : {niche or "non précisée"}
- Audience : {audience or "non précisée"}
- Offre : {offer or "non précisée"}
- Situation actuelle : {current_situation or "non précisée"}
- Contraintes : {constraints or "non précisées"}
- Canal préféré : {preferred_channel or "à recommander"}
- Ton : {tone or "premium, humain, direct"}
- Niveau utilisateur : {user_level or "intermediate"}

MISSION
Analyse le contexte, décide le meilleur module si nécessaire, puis prépare un payload structuré pour TOUS les modules.
Le payload du module demandé doit être le plus précis.
Ne rédige pas de contenu final long. Donne des directions stratégiques propres.

FORMAT STRICT — JSON VALIDE UNIQUEMENT
{{
  "diagnostic": "diagnostic marketing précis en 4 à 7 lignes",
  "decision": {{
    "recommended_module": "emailing | lead_engine | editor | coach",
    "priority_action": "action prioritaire claire",
    "reason": "pourquoi ce module ou cette action est prioritaire maintenant"
  }},
  "context": {{
    "objective": "objectif reformulé",
    "blocker": "blocage reformulé",
    "offer": "offre claire",
    "audience": "cible claire",
    "niche": "niche si utile",
    "pain": "douleur principale",
    "desire": "désir principal",
    "angle": "angle marketing précis",
    "promise": "promesse spécifique et crédible",
    "mechanism": "mécanisme ou logique de transformation",
    "objection": "objection dominante",
    "cta": "CTA recommandé",
    "tone": "ton recommandé"
  }},
  "module_payloads": {{
    "emailing": {{
      "module": "emailing",
      "campaign_goal": "...",
      "offer_name": "...",
      "target_audience": "...",
      "main_blocker": "...",
      "conversion_angle": "...",
      "main_promise": "...",
      "primary_cta": "...",
      "tone": "...",
      "sequence_direction": ["...", "...", "..."]
    }},
    "lead_engine": {{
      "module": "lead_engine",
      "lead_goal": "...",
      "lead_magnet_angle": "...",
      "lead_magnet_promise": "...",
      "target_audience": "...",
      "problem_to_solve": "...",
      "offer_bridge": "...",
      "cta_label": "...",
      "landing_direction": "..."
    }},
    "editor": {{
      "module": "editor",
      "creative_goal": "...",
      "format_recommendation": "post | carrousel",
      "hook_direction": "...",
      "body_direction": "...",
      "visual_direction": "...",
      "caption_direction": "..."
    }},
    "coach": {{
      "module": "coach",
      "mission_title": "...",
      "brief": "...",
      "expected_output": "...",
      "duration_minutes": 45
    }}
  }},
  "assumptions": ["hypothèse utile si une donnée manque"],
  "warnings": ["risque ou piège à éviter"]
}}
""".strip()


def _complete_dispatch(data: Dict[str, Any], *, objective: str, blocker: str, target_module: str, audience: str, offer: str) -> Dict[str, Any]:
    fallback = _fallback_dispatch(
        objective=objective,
        blocker=blocker,
        target_module=target_module,
        audience=audience,
        offer=offer,
    )

    decision = data.get("decision") if isinstance(data.get("decision"), dict) else {}
    recommended_module = _normalize_module(str(decision.get("recommended_module", "")))
    if recommended_module not in _ALLOWED_MODULES:
        recommended_module = _normalize_module(target_module) or fallback["decision"]["recommended_module"]

    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    merged_context = {**fallback["context"], **{k: v for k, v in context.items() if v not in (None, "")}}

    module_payloads = data.get("module_payloads") if isinstance(data.get("module_payloads"), dict) else {}
    completed_payloads = _build_module_payloads(merged_context)
    for key, value in module_payloads.items():
        normalized_key = _normalize_module(str(key))
        if normalized_key in completed_payloads and isinstance(value, dict):
            completed_payloads[normalized_key] = {**completed_payloads[normalized_key], **value}

    result = {
        "diagnostic": _clean(data.get("diagnostic"), fallback["diagnostic"]),
        "decision": {
            "recommended_module": recommended_module,
            "priority_action": _clean(decision.get("priority_action"), fallback["decision"]["priority_action"]),
            "reason": _clean(decision.get("reason"), fallback["decision"]["reason"]),
        },
        "context": merged_context,
        "module_payloads": completed_payloads,
        "assumptions": _ensure_list(data.get("assumptions")) or fallback["assumptions"],
        "warnings": _ensure_list(data.get("warnings")),
        "meta": {
            "module": "CMO IA Dispatch",
            "mode": "analyze_decide_dispatch",
            "model": _choose_model(),
            "content_generation": "disabled_at_cmo_level",
        },
    }
    return result


def generate_cmo_dispatch(
    *,
    objective: str,
    blocker: str = "",
    target_module: str = "",
    niche: str = "",
    audience: str = "",
    offer: str = "",
    current_situation: str = "",
    constraints: str = "",
    preferred_channel: str = "",
    tone: str = "premium, humain, direct",
    user_level: str = "intermediate",
) -> Dict[str, Any]:
    if not _clean(objective):
        raise ValueError("objective est requis.")

    prompt = _build_dispatch_prompt(
        objective=_clean(objective),
        blocker=_clean(blocker),
        target_module=_clean(target_module),
        niche=_clean(niche),
        audience=_clean(audience),
        offer=_clean(offer),
        current_situation=_clean(current_situation),
        constraints=_clean(constraints),
        preferred_channel=_clean(preferred_channel),
        tone=_clean(tone, "premium, humain, direct"),
        user_level=_clean(user_level, "intermediate"),
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=_choose_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_DISPATCH},
            {"role": "user", "content": prompt},
        ],
        temperature=0.32,
        max_tokens=1400,
        response_format={"type": "json_object"},
    )

    content = ""
    try:
        content = (response.choices[0].message.content or "").strip()
    except Exception:
        content = ""

    if not content:
        raise RuntimeError("Réponse OpenAI vide pour CMO IA Dispatch.")

    data = _safe_json_loads(content)
    return _complete_dispatch(data, objective=objective, blocker=blocker, target_module=target_module, audience=audience, offer=offer)


def _build_strategy_prompt(
    *,
    objective: str,
    niche: str,
    audience: str,
    offer: str,
    current_situation: str,
    constraints: str,
    preferred_channel: str,
    tone: str,
    user_level: str,
) -> str:
    return f"""
OBJECTIF UTILISATEUR
{objective or "non précisé"}

CONTEXTE BUSINESS
- Niche : {niche or "non précisée"}
- Audience : {audience or "non précisée"}
- Offre : {offer or "non précisée"}
- Situation actuelle : {current_situation or "non précisée"}
- Contraintes : {constraints or "non précisées"}
- Canal préféré : {preferred_channel or "à recommander"}
- Ton : {tone or "premium, humain, direct"}
- Niveau utilisateur : {user_level or "intermediate"}

FORMAT STRICT — JSON VALIDE UNIQUEMENT
{{
  "diagnostic": "diagnostic clair en 3 à 6 lignes",
  "priority_action": "une action prioritaire claire",
  "why_this_action": "pourquoi cette action est la plus rentable maintenant",
  "execution_plan": [
    {{"step": 1, "title": "...", "detail": "..."}},
    {{"step": 2, "title": "...", "detail": "..."}}
  ],
  "generated_content": {{
    "post": "",
    "email": "",
    "cta": "CTA clair",
    "lead_magnet_idea": "idée courte si pertinent"
  }},
  "next_best_action": "la prochaine action à faire juste après",
  "risk_to_avoid": "le piège principal à éviter"
}}
""".strip()


def generate_cmo_strategy(
    *,
    objective: str,
    niche: str = "",
    audience: str = "",
    offer: str = "",
    current_situation: str = "",
    constraints: str = "",
    preferred_channel: str = "",
    tone: str = "premium, humain, direct",
    user_level: str = "intermediate",
) -> Dict[str, Any]:
    """
    Ancienne fonction conservée pour compatibilité.
    Le nouveau système propre passe par generate_cmo_dispatch().
    """
    if not _clean(objective):
        raise ValueError("objective est requis.")

    prompt = _build_strategy_prompt(
        objective=_clean(objective),
        niche=_clean(niche),
        audience=_clean(audience),
        offer=_clean(offer),
        current_situation=_clean(current_situation),
        constraints=_clean(constraints),
        preferred_channel=_clean(preferred_channel),
        tone=_clean(tone, "premium, humain, direct"),
        user_level=_clean(user_level, "intermediate"),
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=_choose_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_STRATEGY},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
        max_tokens=1200,
        response_format={"type": "json_object"},
    )

    content = ""
    try:
        content = (response.choices[0].message.content or "").strip()
    except Exception:
        content = ""

    if not content:
        raise RuntimeError("Réponse OpenAI vide pour CMO IA V5.")

    data = _safe_json_loads(content)
    data["meta"] = {
        "module": "CMO IA V5",
        "mode": "legacy_strategy_compat",
        "model": _choose_model(),
    }
    return data
