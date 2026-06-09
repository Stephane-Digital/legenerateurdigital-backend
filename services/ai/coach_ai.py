from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


FALLBACK_REPLY = (
    "Je suis Alex. Donne-moi :\n"
    "1) ton objectif concret\n"
    "2) ton temps disponible par jour\n"
    "3) si tu veux créer ton propre produit digital ou développer une activité d’affiliation\n"
    "4) ta niche, ton idée d’offre ou l’offre que tu veux promouvoir\n\n"
    "Et je te construis un parcours FormAction clair avec une prochaine action unique."
)


def _clean(s: Any) -> str:
    return str(s or "").strip()


def _compact_context(context: Dict[str, Any] | None) -> str:
    if not isinstance(context, dict) or not context:
        return "Aucun contexte profil fourni."

    keys = (
        "goal",
        "businessGoal",
        "revenueGoalMonthly",
        "deadlineDays",
        "niche",
        "offer",
        "audience",
        "audienceSize",
        "stage",
        "businessModel",
        "timePerDay",
        "mainBlocker",
        "level",
        "last_action",
        "business_mode",
        "project_type",
        "project_name",
        "project_status",
        "selected_niche",
        "selected_platform",
        "recommended_platform",
        "estimated_days_to_market",
        "roadmap_step",
    )
    out = []
    for key in keys:
        value = context.get(key)
        if value is None or value == "":
            continue
        out.append(f"{key}={_clean(value)[:160]}")

    trajectory = context.get("trajectory")
    if isinstance(trajectory, dict):
        target = trajectory.get("targetLabel") or trajectory.get("target")
        horizon = trajectory.get("horizonDays")
        step = trajectory.get("currentStep")
        forbidden = trajectory.get("forbiddenFocus")
        if target:
            out.append(f"trajectory_target={_clean(target)[:160]}")
        if horizon:
            out.append(f"trajectory_horizon_days={_clean(horizon)[:40]}")
        if step:
            out.append(f"trajectory_current_step={_clean(step)[:160]}")
        if forbidden:
            try:
                out.append(f"forbidden_focus={json.dumps(forbidden, ensure_ascii=False)[:220]}")
            except Exception:
                pass

    return " | ".join(out) if out else "Contexte profil présent mais non exploitable."



def _detect_project_intent(message: str) -> str:
    msg = _clean(message).lower()

    affiliate_words = (
        "affiliation",
        "affilié",
        "affilie",
        "commission",
        "promouvoir",
        "recommander",
        "code liberté",
        "code liberte",
        "formation en affiliation",
        "offre existante",
    )
    product_words = (
        "produit digital",
        "ebook",
        "e-book",
        "créer un produit",
        "creer un produit",
        "produit rentable",
        "niche rentable",
        "niches rentables",
        "quoi vendre",
        "mise en vente",
    )

    if any(word in msg for word in affiliate_words):
        return "AFFILIATE_MODE"
    if any(word in msg for word in product_words):
        return "PRODUCT_CREATOR_MODE"
    return ""


def _project_mode_prompt(message: str) -> str:
    intent = _detect_project_intent(message)
    if not intent:
        return ""

    common = (
        "\n\nMODE FORMACTION ACTIVÉ — RÈGLES PRIORITAIRES:\n"
        "- Coach Alex doit piloter LGD comme un architecte business, pas comme un chatbot.\n"
        "- L'utilisateur ne doit pas choisir les modules seul: Alex indique le bon module au bon moment.\n"
        "- Alex avance mission par mission. Une seule mission prioritaire à la fois.\n"
        "- Alex doit afficher un temps estimé réaliste jusqu'à la mise en vente quand le projet s'y prête.\n"
        "- Alex doit proposer une prochaine action courte, mesurable et réalisable aujourd'hui.\n"
        "- Ne jamais promettre un revenu garanti. Parler de trajectoire, probabilité, clarté et exécution.\n"
    )

    if intent == "AFFILIATE_MODE":
        return (
            common
            + "\nPARCOURS DÉTECTÉ: ACTIVITÉ D'AFFILIATION.\n"
            "Si l'utilisateur veut vendre Code Liberté ou une formation existante, ne jamais présenter l'offre comme du MRR sauf si l'utilisateur le précise explicitement.\n"
            "Alex doit traiter l'offre comme une activité d'affiliation: choisir l'audience, positionner l'offre, créer les contenus, capter des prospects, relancer, planifier.\n"
            "Structure attendue si c'est un nouveau projet d'affiliation:\n"
            "1) confirmer l'offre à promouvoir;\n"
            "2) proposer 3 à 5 audiences possibles;\n"
            "3) recommander l'audience la mieux positionnée;\n"
            "4) estimer le temps jusqu'à première mise en vente;\n"
            "5) donner la mission du jour.\n"
            "Modules LGD à orchestrer: Coach Alex, Lead Engine IA, Éditeur Intelligent, Emailing IA, Planner IA, Bibliothèque.\n"
        )

    return (
        common
        + "\nPARCOURS DÉTECTÉ: CRÉATION DE PRODUIT DIGITAL.\n"
        "Si l'utilisateur demande une niche rentable ou un produit digital rentable, Alex doit proposer 5 niches avec forte demande.\n"
        "Pour chaque niche: demande, douleur principale, audience cible, produit digital possible, prix conseillé, difficulté, rapidité de lancement, concurrence, potentiel, score de réussite LGD.\n"
        "Alex doit recommander UNE niche comme meilleure option et expliquer pourquoi.\n"
        "L'utilisateur doit pouvoir choisir, demander une variante ou régénérer.\n"
        "Une fois la niche validée, Alex construit le projet de A à Z: positionnement, avatar, promesse, offre, produit, bonus, prix, plateforme, lead magnet, page, emails, contenus, planner, mise en vente.\n"
        "Alex doit recommander la meilleure plateforme de vente selon le projet: Systeme.io, Gumroad, Payhip, KDP ou autre, avec un score et une raison claire.\n"
    )


def _system_prompt(mode: str, focus: str, plan: str, context: Dict[str, Any] | None = None, message: str = "") -> str:
    mode_n = _clean(mode).lower() or "premium"
    focus_n = _clean(focus).lower() or "jour"
    plan_n = _clean(plan).lower() or "essentiel"
    ctx = _compact_context(context)
    project_guidance = _project_mode_prompt(message)

    return (
        "Tu es Alex V3, Coach Business IA premium de Le Générateur Digital. "
        "Ta valeur ajoutée n’est pas de répondre comme ChatGPT. Ta valeur est de transformer une situation floue "
        "en objectif clair, trajectoire réaliste, priorité unique et action mesurable.\n\n"
        f"Contexte technique: mode={mode_n}, focus={focus_n}, plan={plan_n}.\n"
        f"Contexte utilisateur disponible: {ctx}\n\n"
        "Méthode invisible V3 à appliquer avant chaque réponse:\n"
        "1) identifier l’objectif business réel;\n"
        "2) identifier le blocage principal;\n"
        "3) couper la dispersion;\n"
        "4) choisir le levier le plus rentable selon temps/niveau/audience;\n"
        "5) donner un plan clair A → B;\n"
        "6) terminer par UNE prochaine action mesurable.\n\n"
        "Règles de réponse:\n"
        "- français naturel, direct, humain, rassurant;\n"
        "- pas de blabla, pas de théorie générale, pas de disclaimer inutile;\n"
        "- si l’utilisateur se disperse, dis clairement STOP puis recentre;\n"
        "- donne toujours une priorité unique;\n"
        "- quand c’est pertinent, structure en: Objectif / Diagnostic / Plan / Action du jour;\n"
        "- ne promets jamais de résultat garanti; parle de trajectoire réaliste;\n"
        "- si le contexte contient un objectif chiffré, adapte la réponse à cet objectif;\n"
        "- évite les réponses longues: utile, clair, exploitable."
        f"{project_guidance}"
    )


def _extract_usage(usage: Any) -> Optional[Dict[str, int]]:
    try:
        if not usage:
            return None
        pt = int(getattr(usage, "prompt_tokens", None) or usage.get("prompt_tokens") or 0)
        ct = int(getattr(usage, "completion_tokens", None) or usage.get("completion_tokens") or 0)
        tt = int(getattr(usage, "total_tokens", None) or usage.get("total_tokens") or (pt + ct))
        return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    except Exception:
        return None


def generate_coach_reply(
    *,
    message: str,
    mode: str = "action",
    focus: str = "jour",
    context: Dict[str, Any] | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
    plan: str = "essentiel",
    depth: int | None = None,
) -> Dict[str, Any] | str:
    msg = _clean(message)
    if not msg:
        return {"reply": FALLBACK_REPLY, "source": "fallback"}

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
    if not api_key:
        return {"reply": FALLBACK_REPLY, "source": "fallback_no_key"}

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        sys = _system_prompt(mode=mode, focus=focus, plan=plan, context=context, message=msg)

        meta_bits = []
        if user_name:
            meta_bits.append(f"user_name={_clean(user_name)[:80]}")
        if user_email:
            meta_bits.append(f"user_email={_clean(user_email)[:120]}")
        if user_id is not None:
            meta_bits.append(f"user_id={int(user_id)}")
        if meta_bits:
            sys += "\n\nMeta: " + ", ".join(meta_bits)

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_COACH", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": msg},
            ],
            temperature=0.42,
            max_tokens=900,
        )

        reply = ""
        try:
            reply = (resp.choices[0].message.content or "").strip()
        except Exception:
            reply = ""

        if not reply:
            return {"reply": FALLBACK_REPLY, "source": "fallback_empty"}

        usage = _extract_usage(getattr(resp, "usage", None))
        return {"reply": reply, "source": "openai", "usage": usage}

    except Exception:
        return {"reply": FALLBACK_REPLY, "source": "fallback_error"}

def _fallback_live_result(source: str = "fallback") -> Dict[str, Any]:
    return {
        "success": False,
        "source": source,
        "title": "Diagnostic stratégique Alex",
        "diagnostic": "Alex Live n’est pas disponible pour le moment.",
        "realBlocker": "Le moteur local doit prendre le relais.",
        "premiumMission": "Exécuter la mission du jour générée par le moteur Alex.",
        "mistakeToAvoid": "Ne pas se disperser.",
        "expectedResult": "Avoir réalisé une action mesurable aujourd’hui.",
        "actionSteps": [
            "Relire la mission du jour.",
            "Faire uniquement l’action demandée.",
            "Mesurer le KPI indiqué.",
        ],
        "kpiLabel": "Action réalisée",
        "durationMin": 45,
        "editorPrompt": "Créer un contenu simple à partir de la mission du jour.",
    }


def _live_strategist_system_prompt(plan: str) -> str:
    plan_n = _clean(plan).lower() or "essentiel"
    return (
        "Tu es Alex Stratège IA Live Premium, coach business de Le Générateur Digital. "
        "Tu ne dois pas produire une réponse générale. Tu dois transformer le contexte fourni "
        "en diagnostic stratégique ultra concret, humain et exploitable.\n\n"
        f"Plan utilisateur: {plan_n}.\n\n"
        "Tu dois répondre uniquement en JSON valide, sans markdown, sans texte autour.\n"
        "Structure JSON obligatoire:\n"
        "{\n"
        '  "title": "titre court",\n'
        '  "diagnostic": "diagnostic humain et stratégique",\n'
        '  "realBlocker": "blocage réel sous-jacent",\n'
        '  "premiumMission": "mission premium du jour",\n'
        '  "mistakeToAvoid": "erreur à éviter aujourd’hui",\n'
        '  "expectedResult": "résultat concret attendu ce soir",\n'
        '  "actionSteps": ["étape 1", "étape 2", "étape 3"],\n'
        '  "kpiLabel": "KPI mesurable",\n'
        '  "durationMin": 45,\n'
        '  "editorPrompt": "prompt prêt pour générer le contenu dans l’éditeur"\n'
        "}\n\n"
        "Règles:\n"
        "- français naturel, direct, humain, rassurant;\n"
        "- parle comme un coach business expérimenté, pas comme un générateur de templates;\n"
        "- priorité à la première vente, aux conversations qualifiées et à l’action du jour;\n"
        "- ne promets jamais de résultat garanti;\n"
        "- pas de blabla, pas de théorie, pas de longs paragraphes;\n"
        "- actionSteps: 3 à 5 étapes maximum;\n"
        "- durationMin doit être 25, 45 ou 60 selon le temps disponible et la mission;\n"
        "- editorPrompt doit aider à créer un post, carrousel, story ou script DM selon la mission."
    )


def _safe_json_loads(text: str) -> Dict[str, Any]:
    raw = _clean(text)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return {}
    return {}


def _normalize_live_result(data: Dict[str, Any], usage: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    fallback = _fallback_live_result("fallback_normalize")

    def text(key: str) -> str:
        value = _clean(data.get(key))
        return value or str(fallback.get(key) or "")

    steps_raw = data.get("actionSteps")
    steps: list[str] = []
    if isinstance(steps_raw, list):
        steps = [_clean(x) for x in steps_raw if _clean(x)]
    if not steps:
        steps = list(fallback["actionSteps"])
    steps = steps[:5]

    try:
        duration = int(data.get("durationMin") or fallback["durationMin"])
    except Exception:
        duration = int(fallback["durationMin"])
    if duration not in (25, 45, 60):
        duration = 45

    result = {
        "success": True,
        "source": "openai",
        "title": text("title"),
        "diagnostic": text("diagnostic"),
        "realBlocker": text("realBlocker"),
        "premiumMission": text("premiumMission"),
        "mistakeToAvoid": text("mistakeToAvoid"),
        "expectedResult": text("expectedResult"),
        "actionSteps": steps,
        "kpiLabel": text("kpiLabel"),
        "durationMin": duration,
        "editorPrompt": text("editorPrompt"),
    }
    if usage:
        result["usage"] = usage
    return result


def generate_live_strategist(
    *,
    payload: Dict[str, Any],
    user_id: int | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
    plan: str = "essentiel",
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
    if not api_key:
        return _fallback_live_result("fallback_no_key")

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        sys = _live_strategist_system_prompt(plan)

        meta: Dict[str, Any] = {}
        if user_id is not None:
            meta["user_id"] = int(user_id)
        if user_email:
            meta["user_email"] = _clean(user_email)[:120]
        if user_name:
            meta["user_name"] = _clean(user_name)[:80]

        regeneration_id = _clean(payload.get("regenerationId"))
        regeneration_instruction = _clean(payload.get("regenerationInstruction"))

        instruction = (
            "Analyse le questionnaire, la mission locale et le contexte. "
            "Produis une mission premium unique, plus humaine que le fallback local. "
            "Tu dois préserver le positionnement LGD: business digital, action concrète, vente douce, zéro promesse agressive."
        )

        if regeneration_id:
            instruction += (
                "\n\nRÉGÉNÉRATION MANUELLE: l'utilisateur a cliqué sur Régénérer l'analyse. "
                "Tu dois produire une variation réellement différente: nouvel angle stratégique, nouveaux mots, nouvelles actions, "
                "sans changer l'objectif business ni inventer de nouvelle offre. "
                f"Identifiant de variation: {regeneration_id}."
            )
            if regeneration_instruction:
                instruction += f"\nInstruction frontend: {regeneration_instruction}"

        user_payload = {
            "meta": meta,
            "payload": payload,
            "instruction": instruction,
        }

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_COACH_LIVE", os.getenv("OPENAI_MODEL_COACH", "gpt-4o-mini")),
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)[:14000]},
            ],
            temperature=0.72 if _clean(payload.get("regenerationId")) else 0.58,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )

        content = ""
        try:
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""

        data = _safe_json_loads(content)
        if not data:
            return _fallback_live_result("fallback_empty")

        usage = _extract_usage(getattr(resp, "usage", None))
        return _normalize_live_result(data, usage)

    except Exception:
        return _fallback_live_result("fallback_error")

