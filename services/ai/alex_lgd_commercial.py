"""S3.C.4.1 — données commerciales officielles, calcul en centimes."""
import re
import unicodedata

PLANS = (("Essentiel", 2900), ("Pro", 6700), ("Ultime", 9700))
COMMISSION_PERCENT = 60


def _euros(cents: int) -> str:
    return f"{cents // 100},{cents % 100:02d} €"


def commercial_facts() -> str:
    rows = [f"- {name} : {_euros(price)}/mois → {_euros(price * COMMISSION_PERCENT // 100)}/mois de commission éligible." for name, price in PLANS]
    return "\n".join(["**Programme Ambassadeur LGD — conditions officielles**", *rows,
        "Inscription gratuite, sans abonnement LGD obligatoire. Commission récurrente de 60 %, validée après 30 jours d’abonnement actif; paiement le 10 du mois suivant la validation. Aucun revenu garanti.",
        "Essai LGD : 7 jours sans carte bancaire ni engagement.",
        "Inscription : https://legenerateurdigital.systeme.io/affiliation-lgd. Compte Systeme.io gratuit et identifiant affilié personnel; générer le lien dans le Centre de Croissance Ambassadeur."])


def commercial_question(message: str, context=None) -> bool:
    msg = ''.join(c for c in unicodedata.normalize('NFKD', message.lower()) if not unicodedata.combining(c))
    project = (context or {}).get('alex_business_project') or {}
    explicit = bool(re.search(r'\b(ambassadeur|ambassadrice|lgd)\b', msg))
    active = isinstance(project, dict) and project.get('project_type') == 'lgd_ambassador'
    pricing = bool(re.search(r'\b(tarifs?|prix|commissions?|formules?|percevoir|combien|abonnements?)\b', msg))
    # Narrow deterministic route: no unrelated project or hypothetical simulation.
    return pricing and (explicit or active) and not re.search(r'\b(ebook|e-book|autre produit|simul\w*|hypothet\w*)\b', msg)


def commercial_reply() -> str:
    return commercial_facts() + "\n\n**Première mission si tu n’es pas encore inscrit :** vérifie ton inscription gratuite, puis récupère ton lien personnel dans le Centre de Croissance Ambassadeur. Si ces étapes sont déjà terminées, indique-le pour poursuivre sans les refaire. L’Éditeur Intelligent aide à créer des publications, Lead Engine IA des supports visuels et Emailing IA des séquences à copier dans Systeme.io."
