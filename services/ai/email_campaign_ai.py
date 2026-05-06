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
        "subject": "Et si ce n’était pas trop tard ?",
        "preheader": "Le bon moment n’arrive pas tout seul.",
    },
    4: {
        "role": "solution claire",
        "subject": "Le plus simple pour avancer",
        "preheader": "Une offre simple vaut mieux qu’un plan parfait.",
    },
    5: {
        "role": "projection concrète",
        "subject": "Imagine dans 7 jours",
        "preheader": "Pas un rêve. Une prochaine étape claire.",
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


# ============================================================
# LGD HUMAN LIFE ENGINE V1.3
# Objectif : éviter la répétition "Stripe / zéro vente / écran" en injectant
# des scènes humaines variées, des contextes de vie, des tensions concrètes
# et des CTA naturels adaptés au marché.
# ============================================================
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
        "laisse trois prospects chauds sans relance parce qu’il ne sait pas quoi dire",
        "relit sa page de vente en boucle au lieu de la montrer à quelqu’un",
        "poste pour se rassurer, puis vérifie les vues toutes les dix minutes",
        "prépare une nouvelle idée alors que l’offre actuelle n’a jamais été testée",
    ],
    "fitness": [
        "promet de reprendre lundi puis craque le soir devant le frigo",
        "compte les calories deux jours puis abandonne au premier repas social",
        "évite le miroir après une journée trop longue",
        "cherche un nouveau programme au lieu de refaire la séance prévue",
        "se pèse le matin et laisse ce chiffre décider de toute sa journée",
        "sait quoi manger mais perd le contrôle quand la fatigue arrive",
        "remplit son panier de courses propres puis commande quand même à 21h",
        "ouvre une appli de sport et referme avant la première série",
    ],
    "crypto": [
        "ouvre son exchange à minuit après une bougie rouge",
        "vend trop tôt puis regarde le marché repartir sans lui",
        "achète parce qu’un groupe Telegram s’agite",
        "confond urgence et opportunité dès que le prix bouge",
        "cache ses pertes derrière l’idée qu’il va se refaire au prochain trade",
        "rafraîchit le graphique au lieu de respecter son plan",
        "promet de réduire le levier puis recommence au prochain signal",
        "coupe son stop pour ne pas accepter que le trade est mauvais",
    ],
    "productivity": [
        "déplace encore les mêmes tâches dans son agenda",
        "ouvre Notion pour réorganiser au lieu de terminer",
        "répond à trois notifications et perd le fil de sa vraie priorité",
        "finit la journée fatigué avec rien de vraiment livré",
        "commence par les petites tâches pour éviter celle qui compte",
        "se couche avec la sensation d’avoir été occupé, pas efficace",
        "change de méthode chaque semaine sans finir le travail engagé",
        "ouvre quinze onglets et oublie pourquoi il avait commencé",
    ],
    "confidence": [
        "réécrit son message dix fois puis ne l’envoie pas",
        "prépare sa prise de parole et coupe la caméra au dernier moment",
        "dit oui trop vite puis regrette dans la voiture",
        "évite de demander le prix juste pour ne pas déranger",
        "sourit en réunion alors qu’il voulait défendre son idée",
        "laisse quelqu’un d’autre décider parce que s’affirmer paraît trop risqué",
        "efface une phrase honnête pour remettre une version plus acceptable",
        "repousse un appel parce qu’il sait qu’il devra dire ce qu’il veut vraiment",
    ],
    "saas_tech": [
        "regarde sa courbe de churn grimper sans comprendre où ça fuit",
        "ajoute une énième feature alors que les utilisateurs n’ont pas fini l’onboarding",
        "voit des inscrits en essai, mais presque aucun ne sort sa carte bancaire",
        "passe ses journées à fixer des bugs au lieu de parler aux vrais utilisateurs",
        "regarde Hotjar et voit les visiteurs partir dès la première étape de configuration",
        "repousse la sortie officielle parce qu’il veut peaufiner l’infrastructure technique",
        "relit les retours support en cherchant une excuse technique au manque de conversion",
        "répond aux tickets faciles pendant que les comptes à risque disparaissent en silence",
        "prépare une roadmap produit alors que trois utilisateurs n’ont toujours pas activé la valeur",
        "ouvre Slack et voit le canal sales vide depuis plusieurs jours",
        "décale encore l’appel utilisateur parce qu’il préfère livrer une correction de plus",
        "voit un essai gratuit expirer sans avoir envoyé un seul message personnel",
    ],
    "coaching_life": [
        "dit que tout va bien à ses proches alors qu’il se sent s’éteindre dans son job actuel",
        "ouvre les sites d’offres d’emploi par habitude, soupire, puis referme l’onglet",
        "écoute un énième podcast de développement personnel sans changer son quotidien",
        "se lève à reculons en comptant les heures qui le séparent du week-end",
        "dit oui à des projets qui l’épuisent juste pour ne pas décevoir son entourage",
        "remet son projet de reconversion à plus tard en se disant que ce n’est jamais le bon moment",
        "garde une note intitulée nouveau départ sans jamais prendre de rendez-vous",
        "rentre chez lui vidé et prétend que c’est juste une mauvaise période",
    ],
    "real_estate": [
        "scrolle sur SeLoger dès qu’une alerte mail tombe",
        "calcule son plan de financement sur Excel pour la dixième fois en espérant que les chiffres changent",
        "rappelle des agents immobiliers qui promettent de recontacter et disparaissent",
        "visite un bien parfait sur les photos et découvre un défaut majeur en cinq minutes",
        "hésite à faire une offre et regarde le bien se vendre sous ses yeux en 48 heures",
        "laisse son dossier de prêt traîner sur le bureau par peur du refus de la banque",
        "compare deux quartiers pendant que les opportunités sérieuses partent déjà",
        "ouvre le simulateur bancaire au lieu d’appeler le courtier",
    ],
}

HUMAN_LIFE_CONTEXT_BANK = {
    "business": [
        "dans la cuisine, téléphone posé à côté de l’assiette froide",
        "dans la voiture, avant de rentrer, en relisant une réponse jamais envoyée",
        "au café, devant un ordinateur ouvert et une page de vente encore invisible",
        "dans le lit, écran éclairé trop fort, avec l’idée de tout reprendre demain",
        "entre deux rendez-vous, en regardant un concurrent vendre avec moins de contenu",
        "sur WhatsApp, avec un message prospect ouvert depuis vingt minutes",
        "dans un coworking, casque sur les oreilles, pendant que rien ne part vraiment",
    ],
    "fitness": [
        "devant le frigo, encore debout alors que la journée est finie",
        "dans les vestiaires, en évitant le miroir sans le dire",
        "au supermarché, entre deux rayons, avec la fatigue qui décide à ta place",
        "sur le canapé, tenue de sport déjà prête mais séance repoussée",
    ],
    "crypto": [
        "dans le noir, écran du téléphone collé au visage",
        "au bureau, onglet graphique caché derrière une fenêtre de travail",
        "sur Telegram, pendant que tout le monde crie au signal",
        "après une perte, en cherchant déjà le trade qui va réparer le précédent",
    ],
    "productivity": [
        "à 18h47, liste de tâches pleine et vrai livrable toujours vide",
        "dans Notion, avec une belle organisation qui ne livre rien",
        "dans le train, en déplaçant encore une tâche au lendemain",
        "à la pause déjeuner, en ouvrant trois outils au lieu d’un seul fichier",
    ],
    "confidence": [
        "juste avant l’appel, doigt au-dessus du bouton rejoindre",
        "dans la voiture, en rejouant la phrase qu’il aurait dû dire",
        "devant un message prêt à partir, puis supprimé phrase après phrase",
        "en réunion, sourire poli pendant qu’une idée importante reste bloquée",
    ],
    "saas_tech": [
        "dans Slack, avec le canal ventes silencieux depuis lundi",
        "sur le dashboard produit, entre une courbe d’activation plate et trois tickets support",
        "dans Linear, en déplaçant une carte qui n’a jamais touché le vrai problème",
        "sur Hotjar, à regarder des sessions où les utilisateurs quittent au même endroit",
        "dans l’onglet Stripe, pendant qu’un essai gratuit expire sans bruit",
        "en appel interne, à parler roadmap alors qu’aucun utilisateur n’a atteint la valeur",
        "dans le changelog, à écrire une amélioration que personne ne demandait",
    ],
    "coaching_life": [
        "dans la voiture, moteur coupé, avant de rentrer faire semblant que tout va bien",
        "à la pause déjeuner, en scrollant des offres d’emploi sans conviction",
        "le dimanche soir, quand la semaine qui arrive serre déjà la poitrine",
        "devant un carnet, avec une page blanche intitulée nouvelle vie",
    ],
    "real_estate": [
        "sur le parking après une visite, avec le doute qui remplace l’enthousiasme",
        "devant Excel, prêt immobilier ouvert et calculs recommencés pour la dixième fois",
        "dans la cuisine, alerte SeLoger reçue et déjà trois appels en retard",
        "au téléphone avec un agent, en sentant que le bien est déjà presque parti",
    ],
}

NATURAL_CTA_BANK = {
    "business": [
        "Demain matin, tu peux avoir une offre envoyée au lieu d’une idée de plus.",
        "Le test à 1€ sert à ça : arrêter de deviner et regarder ce qui répond vraiment.",
        "Tu peux garder ton offre en brouillon, ou la mettre devant quelqu’un aujourd’hui.",
        "Le premier signal ne viendra pas d’un nouveau logo. Il viendra d’un envoi réel.",
        "Si tu veux une preuve, commence par créer quelque chose que quelqu’un peut acheter.",
        "La prochaine réponse ne viendra pas d’un ajustement invisible. Elle viendra d’un message envoyé.",
    ],
    "fitness": [
        "Le prochain repas peut redevenir une décision, pas une compensation.",
        "Tu n’as pas besoin d’un lundi parfait. Tu as besoin d’un premier choix propre.",
        "Commence par la prochaine assiette. Le reste suivra.",
        "Ce soir, tu peux arrêter la négociation et reprendre une règle simple.",
    ],
    "crypto": [
        "Le prochain trade doit suivre un plan, pas une panique.",
        "Avant d’acheter encore, reprends la règle que tu avais décidé d’ignorer.",
        "Tu peux chercher un signal de plus, ou reprendre le contrôle du risque.",
        "Le marché bougera encore demain. Ton plan, lui, doit exister avant.",
    ],
    "productivity": [
        "Ferme le tableau. Termine la tâche qui change vraiment ta journée.",
        "La prochaine heure peut produire un livrable, pas une nouvelle organisation.",
        "Choisis une tâche qui se voit quand elle est finie.",
        "Demain, le système parfait comptera moins que le fichier réellement terminé.",
    ],
    "confidence": [
        "Le prochain message peut rester en brouillon, ou devenir une vraie demande.",
        "Ta voix ne prendra pas plus de place tant que tu la gardes pour toi.",
        "Commence par dire clairement ce que tu voulais déjà dire.",
        "Le respect que tu attends commence souvent par une phrase que tu évites.",
    ],
    "saas_tech": [
        "Tu peux coder une option de plus, ou simplifier l’accès à ta valeur dès aujourd’hui.",
        "Le prochain utilisateur ne veut pas plus de boutons. Il veut comprendre quoi faire en premier.",
        "Ferme ton éditeur deux minutes. Regarde quelqu’un utiliser ton produit sans l’aider.",
        "La prochaine preuve ne viendra pas d’une feature. Elle viendra d’un utilisateur qui atteint la valeur.",
        "Avant la prochaine release, regarde où les essais gratuits abandonnent vraiment.",
        "Le MRR ne monte pas parce que la roadmap est belle. Il monte quand la valeur devient évidente.",
    ],
    "coaching_life": [
        "La semaine prochaine ressemblera exactement à celle-ci, à moins de changer le premier geste.",
        "Tu n’as pas besoin de tout quitter demain. Tu as besoin de poser ta première vraie limite.",
        "Arrête d’attendre le déclic idéal. Choisis simplement par où tu commences.",
        "Le bon moment ne viendra pas te chercher. Il commence par une décision visible.",
    ],
    "real_estate": [
        "Le bon investissement ne vient pas de la chance. Il vient du premier dossier validé.",
        "Tu peux continuer à simuler des scénarios, ou bloquer ta prochaine visite constructive.",
        "Avant de chercher le bien parfait, assure-toi d’avoir une offre que personne ne peut ignorer.",
        "Le prochain bien sérieux ne t’attendra pas. Ton dossier doit être prêt avant l’alerte.",
    ],
}

PERSONALITY_MODES = {
    "mentor": "voix calme, précise, lucide, jamais agressive",
    "brutal_honest": "voix directe, vérité sèche, phrases courtes, aucune consolation vide",
    "premium": "voix premium, sobre, maîtrisée, avec tension commerciale élégante",
    "analytical": "voix froide, factuelle, orientée diagnostic et décision",
    "human": "voix proche, intime, réaliste, sans lyrisme",
}


# ============================================================
# LGD HUMAN CHAOS ENGINE V1.4
# Objectif : casser le rendu trop propre en ajoutant contradictions,
# micro-habitudes, pensées honteuses et ruptures de rythme contrôlées.
# ============================================================
HUMAN_CHAOS_BANK = {
    "business": {
        "contradictions": [
            "veut vendre, mais évite précisément les conversations qui peuvent vendre",
            "dit chercher des clients, puis passe une heure à changer sa bannière",
            "veut être pris au sérieux, mais garde son offre dans un brouillon",
            "parle de lancement, mais ne montre rien à personne",
            "veut des preuves, mais refuse de provoquer le premier vrai signal",
        ],
        "micro_habits": [
            "ouvre ChatGPT pour reformuler au lieu d’envoyer",
            "change trois mots sur sa page puis appelle ça avancer",
            "relit un vieux témoignage au lieu de relancer le prospect",
            "scrolle LinkedIn en disant que c’est de la veille",
            "rafraîchit sa boîte mail avant même d’avoir écrit à quelqu’un",
        ],
        "shame_thoughts": [
            "a peur que quelqu’un voie que son activité ne décolle pas vraiment",
            "n’ose pas dire depuis combien de temps il prépare ce lancement",
            "sent qu’il commence à se mentir quand il dit que ça avance",
            "évite les questions simples parce que les réponses seraient trop visibles",
        ],
        "ruptures": [
            "Le pire ? Tu sais déjà quoi envoyer.",
            "Ce n’est pas compliqué. C’est exposant.",
            "Une idée ne vend rien tant qu’elle reste propre dans un dossier.",
            "Tu n’as pas besoin d’un meilleur angle. Tu as besoin d’un vrai contact avec le marché.",
        ],
    },
    "saas_tech": {
        "contradictions": [
            "veut augmenter le MRR, mais ajoute encore une option que personne n’a demandée",
            "dit écouter les utilisateurs, puis évite l’appel avec celui qui a churné",
            "cherche la conversion, mais optimise une interface que les essais gratuits ne comprennent pas",
            "veut scaler, mais ne sait pas pourquoi les trois derniers inscrits ont disparu",
            "parle activation, mais repousse le moment de regarder une session utilisateur jusqu’au bout",
        ],
        "micro_habits": [
            "déplace une carte Linear pour sentir que le produit avance",
            "lit les tickets support faciles avant d’ouvrir le vrai problème",
            "ouvre Stripe, ferme Stripe, puis retourne dans le code",
            "réécrit le changelog alors que personne n’a atteint la valeur",
            "corrige un détail de wording au lieu d’appeler un utilisateur bloqué",
        ],
        "shame_thoughts": [
            "a peur que le produit soit utile en théorie mais pas assez clair pour être payé",
            "redoute que les utilisateurs ne voient pas la valeur aussi vite que lui",
            "n’ose pas admettre que la roadmap sert parfois à éviter les conversations difficiles",
            "se demande si le MRR stagne à cause du produit, pas du marché",
        ],
        "ruptures": [
            "Une feature peut cacher le problème. Elle ne le résout pas toujours.",
            "Le churn ne ment pas. Il part juste sans faire de bruit.",
            "Ton produit n’a pas besoin d’être plus grand. Il doit devenir plus évident.",
            "Si l’utilisateur abandonne avant la valeur, la roadmap arrive trop tard.",
        ],
    },
    "confidence": {
        "contradictions": [
            "veut être respecté, mais retire la phrase qui le rend clair",
            "veut vendre, mais écrit comme s’il demandait pardon",
            "veut prendre sa place, puis laisse encore quelqu’un décider",
            "veut être visible, mais efface le message juste avant l’envoi",
        ],
        "micro_habits": [
            "réécrit la première phrase jusqu’à ne plus savoir ce qu’il voulait dire",
            "verrouille son téléphone après avoir ouvert la conversation",
            "sourit en réunion puis rumine dans la voiture",
            "prépare une phrase ferme et l’adoucit au dernier moment",
        ],
        "shame_thoughts": [
            "a peur d’être perçu comme trop insistant",
            "n’ose pas demander clairement parce qu’il imagine déjà le refus",
            "se sent ridicule avant même d’avoir essayé",
            "préférerait qu’on devine son besoin plutôt que de le formuler",
        ],
        "ruptures": [
            "Le silence protège sur le moment. Il coûte après.",
            "Tu ne manques pas toujours d’arguments. Parfois tu retires juste ta voix.",
            "La phrase que tu évites est souvent celle qui change la relation.",
            "Ce n’est pas trop direct. C’est enfin clair.",
        ],
    },
    "productivity": {
        "contradictions": [
            "veut gagner du temps, mais reconstruit encore son système",
            "veut terminer, mais commence par renommer les dossiers",
            "veut avancer, mais choisit la tâche qui ne l’expose pas",
            "veut moins de charge mentale, mais ajoute une nouvelle méthode",
        ],
        "micro_habits": [
            "ouvre Notion pour se donner l’impression de reprendre le contrôle",
            "déplace une tâche au lendemain avec une justification très raisonnable",
            "répond à une notification facile pour éviter le vrai fichier",
            "range son bureau numérique avant de produire quoi que ce soit",
        ],
        "shame_thoughts": [
            "sait que la journée a été pleine mais pas utile",
            "redoute qu’on demande ce qui a vraiment été livré",
            "se sent occupé pour ne pas se sentir bloqué",
            "voit très bien quelle tâche compte et l’évite quand même",
        ],
        "ruptures": [
            "Être occupé peut devenir une cachette très confortable.",
            "Le système parfait ne livrera pas à ta place.",
            "La tâche qui compte est souvent celle que tu contournes le mieux.",
            "Tu n’as pas besoin d’une nouvelle organisation. Tu as besoin d’une fin visible.",
        ],
    },
    "fitness": {
        "contradictions": [
            "veut reprendre le contrôle, mais négocie avec lui-même dès que la fatigue arrive",
            "veut changer, puis transforme un écart en abandon complet",
            "cherche un plan parfait, mais fuit le prochain repas simple",
            "veut des résultats, mais laisse une mauvaise soirée décider de la semaine",
        ],
        "micro_habits": [
            "ouvre l’application de sport puis referme avant l’échauffement",
            "regarde le frigo comme si la réponse allait changer",
            "se promet de compenser demain",
            "cache la balance puis y pense toute la matinée",
        ],
        "shame_thoughts": [
            "se sent nul pour un choix qu’il n’aurait même pas remarqué chez quelqu’un d’autre",
            "évite le miroir parce qu’il sait déjà ce qu’il va se dire",
            "a peur que les autres voient le manque de discipline",
            "confond un craquage avec une preuve qu’il n’y arrivera pas",
        ],
        "ruptures": [
            "Un écart n’est pas une identité.",
            "La fatigue adore négocier à ta place.",
            "Le prochain choix compte plus que la dernière erreur.",
            "Tu n’as pas besoin de te punir. Tu as besoin de reprendre une règle simple.",
        ],
    },
    "crypto": {
        "contradictions": [
            "veut suivre un plan, mais obéit à la dernière bougie rouge",
            "parle gestion du risque, puis déplace son stop en silence",
            "veut trader froidement, mais regarde Telegram avant sa propre règle",
            "cherche la liberté, mais laisse le marché décider de son humeur",
        ],
        "micro_habits": [
            "rafraîchit le graphique comme si le mouvement allait s’expliquer",
            "ouvre l’exchange sans intention claire",
            "relit un message Telegram pour justifier une entrée trop tardive",
            "calcule ce qu’il aurait gagné au lieu de protéger ce qui reste",
        ],
        "shame_thoughts": [
            "n’ose pas regarder la perte en face",
            "se raconte qu’il va se refaire pour éviter d’admettre l’erreur",
            "cache la position parce qu’elle ne respecte déjà plus son plan",
            "sait que ce trade est émotionnel mais veut quand même y croire",
        ],
        "ruptures": [
            "Le marché ne te doit pas une réparation.",
            "Un plan ignoré devient juste une décoration.",
            "La panique ressemble souvent à une opportunité quand tu veux te refaire.",
            "Le prochain bon trade commence parfois par ne rien faire.",
        ],
    },
    "coaching_life": {
        "contradictions": [
            "veut changer de vie, mais répond encore oui à ce qui l’épuise",
            "cherche du sens, puis remet la décision à un lundi plus calme",
            "veut respirer, mais protège l’image de quelqu’un qui tient le coup",
            "parle de nouveau départ, mais garde la première action dans un carnet fermé",
        ],
        "micro_habits": [
            "ouvre une offre d’emploi puis ferme l’onglet avant de lire jusqu’au bout",
            "écoute un podcast pour sentir que quelque chose bouge",
            "écrit deux lignes dans un carnet puis retourne à l’urgence des autres",
            "dit que ça va avec une voix qui dit l’inverse",
        ],
        "shame_thoughts": [
            "a honte d’être fatigué alors que tout semble fonctionner de l’extérieur",
            "redoute de décevoir en disant enfin non",
            "se demande combien de temps il peut encore faire semblant",
            "n’ose pas avouer que la stabilité commence à ressembler à une cage",
        ],
        "ruptures": [
            "Tenir bon n’est pas toujours une victoire.",
            "Parfois, le courage commence par une limite très simple.",
            "Tu peux réussir extérieurement et disparaître intérieurement.",
            "Le déclic ne remplace pas une décision visible.",
        ],
    },
    "real_estate": {
        "contradictions": [
            "veut investir, mais repousse encore le dossier bancaire",
            "cherche le bien parfait, mais n’a pas encore sécurisé sa capacité d’achat",
            "veut être rapide, puis hésite jusqu’à voir le bien partir",
            "compare les quartiers au lieu d’appeler le courtier",
        ],
        "micro_habits": [
            "ouvre SeLoger dès l’alerte puis attend trop longtemps",
            "recalcule le même Excel en espérant une autre réponse",
            "relit l’annonce déjà vendue comme si elle allait revenir",
            "garde le dossier de prêt ouvert sans envoyer les pièces",
        ],
        "shame_thoughts": [
            "a peur que la banque dise non et confirme ses doutes",
            "n’ose pas faire une offre parce qu’il imagine déjà s’être trompé",
            "se sent en retard quand les autres parlent patrimoine",
            "redoute de passer pour un amateur devant l’agent",
        ],
        "ruptures": [
            "Le bien parfait attend rarement un dossier incomplet.",
            "L’hésitation coûte parfois plus cher qu’une négociation ratée.",
            "Un simulateur ne remplace pas une capacité validée.",
            "La bonne affaire commence souvent avant l’alerte.",
        ],
    },
}



# ============================================================
# LGD NARRATIVE CONSISTENCY ENGINE V1.5
# Objectif : figer une seule voix par séquence : tu OU vous,
# une même intensité narrative et une cohérence CTA du jour 1 au dernier email.
# ============================================================
CAMPAIGN_VOICE_MODES = {
    "tu": {
        "pronoun": "tu",
        "address_rule": "Tutoiement strict : utiliser tu / ton / ta / tes. Ne jamais utiliser vous / votre / vos.",
        "cta_rule": "CTA naturel, direct, intime, jamais corporate.",
    },
    "vous": {
        "pronoun": "vous",
        "address_rule": "Vouvoiement strict : utiliser vous / votre / vos. Ne jamais utiliser tu / ton / ta / tes.",
        "cta_rule": "CTA sobre, professionnel, précis, jamais familier.",
    },
}

VOICE_STYLE_BANK = {
    "brutal_honest": {
        "instruction": "voix directe, vérité sèche, phrases courtes, aucune consolation vide",
        "rhythm": "ruptures courtes, silences, phrases qui restent en tête",
        "explain_rule": "montrer le geste plutôt que commenter l’émotion",
    },
    "premium_human": {
        "instruction": "voix premium, humaine, sobre, précise, sans lyrisme",
        "rhythm": "rythme élégant, lignes aérées, tension maîtrisée",
        "explain_rule": "éviter les diagnostics évidents et préférer les observations fines",
    },
    "analytical_cold": {
        "instruction": "voix froide, lucide, orientée diagnostic et décision",
        "rhythm": "phrases nettes, logique commerciale, pas d’emphase",
        "explain_rule": "relier les comportements aux conséquences sans moraliser",
    },
    "intimate_real": {
        "instruction": "voix proche, intime, réaliste, comme quelqu’un qui a vu la scène",
        "rhythm": "phrases simples, micro-silences, détails concrets",
        "explain_rule": "ne pas nommer les émotions quand un détail suffit à les faire sentir",
    },
}

EXPLANATORY_PHRASE_SCORES = {
    "cette micro-habitude révèle": 4,
    "cela révèle": 3,
    "un vrai enjeu": 3,
    "la vérité est simple": 2,
    "c’est là que": 2,
    "la vraie question est": 2,
    "ce qui te coûte": 2,
    "ce qui vous coûte": 2,
    "il est temps": 3,
    "prêt à": 2,
    "regardez par vous-même": 3,
    "découvre": 3,
    "clique": 4,
}

FORBIDDEN_CLICHE_SCORES = {
    "qu’attendez-vous": 3,
    "qu’attends-tu": 3,
    "cesse d’attendre": 4,
    "c’est maintenant ou jamais": 4,
    "prends cette décision maintenant": 4,
    "pas plus compliqué que ça": 2,
    "et c’est ça qui fatigue": 3,
    "le pire ?": 2,
    "imagine": 2,
    "et si": 2,
    "passe à l’action": 3,
    "passer à l’action": 2,
    "crois en toi": 4,
    "rêve": 2,
    "transformer ton business": 4,
    "solution complète": 4,
    "outil puissant": 4,
    "opportunité unique": 3,
    "ne laisse pas passer": 3,
    "il est temps d’agir": 4,
    "fais le premier pas": 4,
    "commence à avancer": 4,
    "transforme ces pensées en actions concrètes": 4,
    "regardez par vous-même": 4,
    "découvre la démo": 4,
    "clique": 4,
    "prêt à voir": 3,
    "c’est le moment": 2,
    "tu peux continuer": 2,
    "personne ne va le faire à ta place": 4,
    "maintenant tu sais": 4,
    "rien ne changera si tu ne changes rien": 4,
    "ne laisse pas ça redevenir une idée": 4,
}




# ============================================================
# LGD HUMAN SUBTEXT ENGINE V1.6
# Objectif : réduire le rendu trop explicatif et casser les schémas IA
# sans supprimer les moteurs V1.3, V1.4 et V1.5.
# ============================================================
SUBTEXT_OPENERS = [
    "Le canal Slack est vide.",
    "Tu regardes encore le dashboard.",
    "Tu repousses encore ce message.",
    "Le produit est ouvert. Pas les conversations.",
    "Tu modifies encore un détail.",
    "Stripe est ouvert depuis vingt minutes.",
    "Tu sais déjà quelle tâche tu évites.",
    "L’essai gratuit expire demain.",
]

SUBTEXT_ENDINGS = [
    "Tu connais déjà la conversation que tu repousses.",
    "Le problème n’est probablement plus dans le produit.",
    "La roadmap ne répondra pas à ta place.",
    "Tu n’as pas besoin d’une autre feature aujourd’hui.",
    "Le silence finit toujours par coûter plus cher.",
    "Tu sais déjà quoi faire après avoir fermé cet email.",
]

SUBTEXT_EXPLANATION_PATTERNS = [
    r"(?i)cette micro-habitude révèle[^.?!]*[.?!]",
    r"(?i)cela révèle[^.?!]*[.?!]",
    r"(?i)la vérité est simple\s*:?\s*",
    r"(?i)c['’]est là que[^.?!]*[.?!]",
    r"(?i)ce faux travail[^.?!]*[.?!]",
    r"(?i)il est temps d['’]agir[^.?!]*[.?!]?",
    r"(?i)fais le premier pas[^.?!]*[.?!]?",
    r"(?i)prends cette décision maintenant[^.?!]*[.?!]?",
    r"(?i)c['’]est maintenant ou jamais[^.?!]*[.?!]?",
]

SUBTEXT_TEMPLATE_PHRASES = [
    "Le pire ?",
    "Et c’est ça qui fatigue.",
    "Pas plus compliqué que ça.",
    "Pendant ce temps,",
    "Pendant ce temps",
]


def _subtext_cleanup(text_value: str) -> str:
    cleaned = _clean_text(text_value, "")

    for pattern in SUBTEXT_EXPLANATION_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned).strip()

    for phrase in SUBTEXT_TEMPLATE_PHRASES:
        cleaned = cleaned.replace(phrase, "").strip()

    cleaned = re.sub(r"(?im)^\s*(alors,?\s*)?prêt à voir[^\n]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?im)^\s*regardez par vous-même[^\n]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?im)^\s*découvre(?:z)?[^\n]*$", "", cleaned).strip()
    cleaned = re.sub(r"(?im)^\s*clique(?:z)?[^\n]*$", "", cleaned).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _subtext_score(text_value: str) -> int:
    normalized = _normalize_text(text_value).lower()
    score = 0

    for phrase in SUBTEXT_TEMPLATE_PHRASES:
        if phrase.lower() in normalized:
            score += 1

    for pattern in SUBTEXT_EXPLANATION_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            score += 2

    return score



# ============================================================
# LGD VARIATION ENGINE V1.7
# ============================================================
EMOTIONAL_CURVES_V17 = {
    "early": ["prise de conscience", "friction invisible", "fatigue mentale"],
    "middle": ["contradiction", "micro-échec", "réalité terrain", "preuve silencieuse"],
    "late": ["décision", "projection réaliste", "perte du statu quo", "mouvement concret"],
}

SOFT_CLICHE_REPLACEMENTS_V17 = {
    r"\b[Ii]magine\b": "Pense à",
    r"\b[Ii]maginez\b": "Pensez à",
    r"\b[Pp]asse à l’action\b": "avance vraiment",
    r"\b[Pp]asser à l’action\b": "avancer réellement",
    r"\b[Ss]olution complète\b": "système concret",
}

def _campaign_pick_without_replacement(items, seed, count):
    if not items:
        return []
    pool = list(dict.fromkeys(items))
    while len(pool) < count:
        pool.extend(items)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:count]

def _soft_cliche_cleanup_v17(text_value):
    cleaned = _clean_text(text_value, "")
    for pattern, replacement in SOFT_CLICHE_REPLACEMENTS_V17.items():
        cleaned = re.sub(pattern, replacement, cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def _cross_email_repetition_score_v17(emails):
    openings = []
    endings = []
    score = 0

    for email in emails:
        body = _normalize_text(email.get("body", ""))
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

        if paragraphs:
            openings.append(paragraphs[0][:140].lower())
            endings.append(paragraphs[-1][-140:].lower())

    if len(openings) != len(set(openings)):
        score += 3

    if len(endings) != len(set(endings)):
        score += 2

    return score

def _emotional_stage_v17(day, total_days):
    ratio = day / max(total_days, 1)
    if ratio <= 0.33:
        return random.choice(EMOTIONAL_CURVES_V17["early"])
    if ratio <= 0.66:
        return random.choice(EMOTIONAL_CURVES_V17["middle"])
    return random.choice(EMOTIONAL_CURVES_V17["late"])

REPETITIVE_MOTIF_PATTERNS = [
    r"\bstripe\b",
    r"\bzéro vente\b",
    r"\btoujours zéro\b",
    r"\bnotification",
    r"\bécran\b",
    r"\bchurn\b",
    r"\bhotjar\b",
    r"\béditeur\b",
]


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return text or fallback


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



def _infer_market_key(payload: Any) -> str:
    raw = " ".join(
        [
            _clean_text(_get(payload, "niche"), ""),
            _clean_text(_get(payload, "target_audience"), ""),
            _clean_text(_get(payload, "offer_name"), ""),
            _clean_text(_get(payload, "main_promise"), ""),
            _clean_text(_get(payload, "main_objective"), ""),
            _clean_text(_get(payload, "product_context"), ""),
            _clean_text(_get(payload, "main_objection"), ""),
        ]
    ).lower()

    if any(word in raw for word in ["sport", "fitness", "poids", "mincir", "muscle", "nutrition", "repas"]):
        return "fitness"
    if any(word in raw for word in ["crypto", "trading", "bitcoin", "btc", "exchange", "invest", "trade"]):
        return "crypto"
    if any(word in raw for word in ["productivité", "temps", "agenda", "organisation", "notion", "tâche", "efficacité"]):
        return "productivity"
    if any(word in raw for word in ["confiance", "timidité", "oser", "prise de parole", "affirmation", "s'affirmer"]):
        return "confidence"
    if any(word in raw for word in ["saas", "logiciel", "app", "application", "tech", "churn", "code", "développeur", "mrr", "onboarding", "hotjar", "stripe", "feature"]):
        return "saas_tech"
    if any(word in raw for word in ["coaching", "vie", "reconversion", "sens", "burnout", "épanouissement", "changer de vie", "job"]):
        return "coaching_life"
    if any(word in raw for word in ["immo", "immobilier", "appartement", "achat", "locatif", "bien", "visite", "crédit", "se loger", "seloger"]):
        return "real_estate"
    return "business"


def _cycle_pick(items: List[str], day: int, offset: int = 0) -> str:
    if not items:
        return ""
    return items[(max(day, 1) - 1 + offset) % len(items)]


def _infer_requested_pronoun(payload: Any) -> str:
    raw = " ".join(
        [
            _clean_text(_get(payload, "tone"), ""),
            _clean_text(_get(payload, "voice"), ""),
            _clean_text(_get(payload, "pronoun"), ""),
            _clean_text(_get(payload, "address_mode"), ""),
            _clean_text(_get(payload, "product_context"), ""),
            _clean_text(_get(payload, "target_audience"), ""),
        ]
    ).lower()

    if any(word in raw for word in ["vouvoiement", "vouvoyer", "vous", "b2b", "corporate", "professionnel", "dirigeant", "ceo"]):
        return "vous"
    return "tu"


def _build_campaign_voice(payload: Any, nonce: str) -> Dict[str, Any]:
    pronoun = _infer_requested_pronoun(payload)
    market_key = _infer_market_key(payload)
    seed = sum(ord(ch) for ch in f"{market_key}-{pronoun}-{nonce}")

    style_keys = list(VOICE_STYLE_BANK.keys())
    style_key = style_keys[seed % len(style_keys)]
    style = VOICE_STYLE_BANK[style_key]
    pronoun_rules = CAMPAIGN_VOICE_MODES[pronoun]

    return {
        "pronoun": pronoun,
        "style_key": style_key,
        "style_instruction": style["instruction"],
        "rhythm": style["rhythm"],
        "explain_rule": style["explain_rule"],
        "address_rule": pronoun_rules["address_rule"],
        "cta_rule": pronoun_rules["cta_rule"],
    }


def _contains_mixed_pronouns(text: str, campaign_voice: Dict[str, Any]) -> bool:
    normalized = f" {_normalize_text(text).lower()} "
    pronoun = _clean_text(campaign_voice.get("pronoun"), "tu")

    tu_markers = [" tu ", " ton ", " ta ", " tes ", " toi ", " t’", " t'", " te "]
    vous_markers = [" vous ", " votre ", " vos ", " vôtre "]

    has_tu = any(marker in normalized for marker in tu_markers)
    has_vous = any(marker in normalized for marker in vous_markers)

    if pronoun == "tu":
        return has_vous
    return has_tu


def _explanatory_score(text: str) -> int:
    normalized = _normalize_text(text).lower()
    score = 0
    for marker, weight in EXPLANATORY_PHRASE_SCORES.items():
        if marker in normalized:
            score += weight
    return score


def _select_human_material(payload: Any, day: int, nonce: str, campaign_voice: Dict[str, Any] | None = None) -> Dict[str, Any]:
    market_key = _infer_market_key(payload)
    pains = HUMAN_PAIN_BANK.get(market_key, HUMAN_PAIN_BANK["business"])
    contexts = HUMAN_LIFE_CONTEXT_BANK.get(market_key, HUMAN_LIFE_CONTEXT_BANK["business"])
    ctas = NATURAL_CTA_BANK.get(market_key, NATURAL_CTA_BANK["business"])

    seed = sum(ord(ch) for ch in f"{market_key}-{day}-{nonce}")
    pain_offset = seed % max(1, len(pains))
    context_offset = (seed // 3) % max(1, len(contexts))
    cta_offset = (seed // 7) % max(1, len(ctas))

    selected_pains = _campaign_pick_without_replacement(
        pains,
        seed + day,
        min(4, len(pains)),
    )

    selected_context = _campaign_pick_without_replacement(
        contexts,
        seed + (day * 3),
        1,
    )[0]

    selected_cta = _campaign_pick_without_replacement(
        ctas,
        seed + (day * 7),
        1,
    )[0]

    if campaign_voice:
        personality_key = _clean_text(campaign_voice.get("style_key"), "human")
        personality_instruction = _clean_text(campaign_voice.get("style_instruction"), PERSONALITY_MODES.get("human", "voix humaine"))
    else:
        personality_keys = list(PERSONALITY_MODES.keys())
        personality_key = personality_keys[(day + seed) % len(personality_keys)]
        personality_instruction = PERSONALITY_MODES[personality_key]

    chaos = HUMAN_CHAOS_BANK.get(market_key, HUMAN_CHAOS_BANK["business"])
    contradictions = chaos.get("contradictions", [])
    micro_habits = chaos.get("micro_habits", [])
    shame_thoughts = chaos.get("shame_thoughts", [])
    ruptures = chaos.get("ruptures", [])

    selected_contradiction = _cycle_pick(contradictions, day, seed % max(1, len(contradictions)))
    selected_micro_habit = _cycle_pick(micro_habits, day, (seed // 5) % max(1, len(micro_habits)))
    selected_shame_thought = _cycle_pick(shame_thoughts, day, (seed // 11) % max(1, len(shame_thoughts)))
    selected_rupture = _cycle_pick(ruptures, day, (seed // 13) % max(1, len(ruptures)))

    return {
        "market_key": market_key,
        "pains": selected_pains,
        "life_context": selected_context,
        "natural_cta": selected_cta,
        "personality_key": personality_key,
        "personality_instruction": personality_instruction,
        "contradiction": selected_contradiction,
        "micro_habit": selected_micro_habit,
        "shame_thought": selected_shame_thought,
        "rupture": selected_rupture,
    }


def _ai_cliche_score(text: str) -> int:
    normalized = _normalize_text(text).lower()
    score = 0
    for marker, weight in FORBIDDEN_CLICHE_SCORES.items():
        if marker in normalized:
            score += weight
    return score


def _looks_like_ai_cliche(text: str) -> bool:
    return _ai_cliche_score(text) >= 6


def _repetitive_motif_score(emails: List[Dict[str, Any]]) -> int:
    combined = "\n".join(_clean_text(email.get("body"), "").lower() for email in emails)
    score = 0
    for pattern in REPETITIVE_MOTIF_PATTERNS:
        count = len(re.findall(pattern, combined, flags=re.IGNORECASE))
        if count >= max(4, len(emails) // 2):
            score += 1
    return score


def _natural_cta_for_payload(payload: Any, day: int, nonce: str, campaign_voice: Dict[str, Any] | None = None) -> str:
    return _clean_text(_select_human_material(payload, day, nonce, campaign_voice).get("natural_cta"), "")


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
    ai_cliche = any(_looks_like_ai_cliche(str(e.get("body") or "")) for e in emails)
    repetitive_motif = _repetitive_motif_score(emails) >= 3
    cross_email_repetition = _cross_email_repetition_score_v17(emails) >= 3

    return (
        repeated_subjects
        or repeated_prefixes
        or bad_template
        or ai_cliche
        or repetitive_motif
        or cross_email_repetition
    )


def _build_prompt(*, payload: Any, day: int, email_type: str, angle: str, nonce: str, campaign_voice: Dict[str, Any]) -> str:
    offer_name = _clean_text(_get(payload, "offer_name"), "Votre offre")
    target_audience = _clean_text(_get(payload, "target_audience"), "votre audience")
    main_promise = _clean_text(_get(payload, "main_promise"), "atteindre un meilleur résultat")
    main_objective = _clean_text(_get(payload, "main_objective"), "passer à l'action")
    primary_cta = _clean_text(_get(payload, "primary_cta"), "")
    tone = _clean_text(_get(payload, "tone"), "premium")
    sender_name = _clean_text(_get(payload, "sender_name"), "Le Générateur Digital")
    campaign_type = _clean_text(_get(payload, "campaign_type"), "vente")
    campaign_name = _clean_text(_get(payload, "name"), "Campagne E-mailing IA")
    product_context = _clean_text(_get(payload, "product_context"), "")
    objection = _clean_text(_get(payload, "main_objection"), "")
    proof = _clean_text(_get(payload, "proof"), "")
    niche = _clean_text(_get(payload, "niche"), "")
    level = _clean_text(_get(payload, "level"), _clean_text(_get(payload, "prospectLevel"), ""))
    archetype = DAY_ARCHETYPES.get(day, DAY_ARCHETYPES[((day - 1) % 7) + 1])
    human_material = _select_human_material(payload, day, nonce, campaign_voice)
    pains_block = "\n".join(f"    - {pain}" for pain in human_material["pains"])

    prompt = f"""
    Tu es Emailing IA LGD.

    Tu écris des emails commerciaux humains, directs, mobiles et convertissants.
    Tu ne rédiges pas un template.
    Tu transformes une situation humaine précise en décision commerciale.

    MISSION
    Écris EXACTEMENT UN SEUL email pour le jour {day}.
    Ne fais jamais référence aux autres emails.
    Ne génère jamais plusieurs versions.
    Ne réutilise jamais la même ouverture d’un email à l’autre.

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
    Marché détecté : {human_material["market_key"]}
    Niveau prospect : {level or "intermediate"}
    Promesse : {main_promise}
    Objectif : {main_objective}
    Blocage : {objection or "à inférer à partir du contexte"}
    Preuve : {proof or "non précisée"}
    Contexte : {product_context or "non précisé"}
    CTA fourni : {primary_cta or "à reformuler naturellement"}
    CTA naturel recommandé : {human_material["natural_cta"]}
    Ton : {tone}
    Expéditeur : {sender_name}
    Voix à utiliser : {human_material["personality_instruction"]}
    Voix de séquence globale : {campaign_voice["style_instruction"]}
    Pronom obligatoire pour toute la séquence : {campaign_voice["pronoun"]}
    Règle de pronom : {campaign_voice["address_rule"]}
    Rythme global : {campaign_voice["rhythm"]}
    Règle anti-explication : {campaign_voice["explain_rule"]}
    Règle CTA globale : {campaign_voice["cta_rule"]}
    Variation : {nonce}
    Stade émotionnel V1.7 : {_emotional_stage_v17(day, int(_get(payload, "duration_days"), 7))}

    MATIÈRE HUMAINE OBLIGATOIRE

    Tu dois utiliser cette matière pour éviter tout email générique.

    Comportements réels du prospect :
{pains_block}

    Moment de vie / décor imposé :
    - {human_material["life_context"]}

    HUMAN CHAOS ENGINE V1.4 — À UTILISER OBLIGATOIREMENT

    Contradiction humaine :
    - {human_material["contradiction"]}

    Micro-habitude révélatrice :
    - {human_material["micro_habit"]}

    Pensée honteuse / vérité non dite :
    - {human_material["shame_thought"]}

    Rupture de rythme recommandée :
    - {human_material["rupture"]}

    RÈGLE HUMAN CHAOS

    Tu dois intégrer au moins DEUX éléments du Human Chaos Engine.
    Tu ne dois pas les recopier mécaniquement.
    Tu les transformes en scène ou en phrase qui ressemble à une pensée réelle.

    L’email doit contenir au moins une rupture courte du type :
    - Le pire ?
    - Tu le sais déjà.
    - Comme hier.
    - Et c’est ça qui fatigue.
    - Pas plus compliqué que ça.

    Tu ne dois pas tout expliquer.
    Tu dois montrer le comportement, puis laisser la gêne faire le travail.

    RÈGLE FONDAMENTALE

    L’email doit donner l’impression que LGD comprend la scène exacte vécue par la cible.
    Si le texte peut fonctionner pour trois marchés différents, il est mauvais.

    ARCHITECTURE D’ÉCRITURE

    1. Ouvre avec une scène observable, concrète, située.
       Pas de formule abstraite.
       Pas de "Imagine".
       Pas de "Et si".

    2. Montre le faux travail ou l’évitement.
       Exemple : corriger une interface, acheter un outil, réorganiser un tableau, lire encore, repousser l’envoi.

    3. Fais monter la tension commerciale.
       Ce qui coûte : temps, ventes, confiance, énergie, crédibilité.
       Mais ne nomme pas toujours l’émotion. Montre-la par un geste.

    4. Ajoute une contradiction ou une micro-habitude.
       Exemple : vouloir vendre mais éviter le message, vouloir scaler mais fuir l’appel utilisateur, vouloir être clair mais adoucir la phrase importante.

    5. Introduis LGD comme déclencheur concret.
       Pas comme "outil puissant".
       Pas comme "solution complète".
       LGD aide à créer / envoyer / tester quelque chose de visible.

    6. Termine par une phrase de décision naturelle.
       Le CTA doit être une continuation de la scène, pas un bouton marketing.
       Si le CTA ressemble à une injonction marketing, il est mauvais.

    INTERDIT ABSOLU

    - Imagine
    - Et si
    - Passe à l’action
    - Crois en toi
    - Opportunité unique
    - Solution complète
    - Outil puissant
    - Transformer ton business
    - Personne ne va le faire à ta place
    - Maintenant tu sais
    - Rien ne changera si tu ne changes rien
    - Tu peux continuer… ou changer
    - Ne laisse pas ça redevenir une idée
    - Il est temps d’agir
    - Fais le premier pas
    - Commence à avancer
    - Transforme ces pensées en actions concrètes

    VARIATION OBLIGATOIRE

    Tu dois varier :
    - l’heure ou le lieu
    - le support observé : téléphone, mail, Slack, dashboard, conversation, café, voiture, cuisine, appel, onglet, brouillon
    - la tension principale
    - la phrase de fin

    Ne commence pas systématiquement par "Il est...".
    Tu peux commencer par un geste, une notification, un silence, un objet, une phrase que la cible évite.

    STYLE

    - phrases courtes
    - lignes coupées
    - rythme mobile
    - vocabulaire simple
    - aucune grandiloquence
    - aucune motivation vide
    - aucun markdown
    - pas de signature

    HUMAN SUBTEXT ENGINE V1.6 — OBLIGATOIRE

    Tu dois réduire les explications visibles.
    Tu dois montrer le comportement et laisser le lecteur comprendre.

    Interdit de structurer tous les emails avec :
    - Le pire ?
    - Pendant ce temps
    - Et c’est ça qui fatigue
    - Ce faux travail
    - C’est maintenant ou jamais

    Le produit doit arriver plus tard.
    L’email doit rester plus longtemps dans la scène vécue par le prospect.
    Si tu peux supprimer une phrase d’explication et garder le sens, supprime-la.

    Exemple de direction :
    Mauvais : "Ce faux travail te coûte des ventes."
    Meilleur : "Tu passes plus de temps dans Linear qu’avec un utilisateur réel."

    NARRATIVE CONSISTENCY ENGINE V1.5 — OBLIGATOIRE

    Toute la séquence utilise la même voix.
    Cet email doit donc respecter strictement :
    - le même pronom : {campaign_voice["pronoun"]}
    - le même niveau de tension
    - le même style de CTA
    - la même posture narrative

    Interdit de mélanger tu et vous.
    Interdit de passer d’un ton intime à un ton corporate.
    Interdit d’expliquer le comportement avec des phrases comme :
    - cette micro-habitude révèle
    - cela révèle un vrai enjeu
    - la vérité est simple
    - c’est là que
    - prêt à voir
    - regardez par vous-même

    Tu dois remplacer ces explications par des observations concrètes.

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

def _generate_one_email(*, payload: Any, day: int, email_type: str, angle: str, nonce: str, campaign_voice: Dict[str, Any]) -> Dict[str, Any]:
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
        nonce=nonce,
        campaign_voice=campaign_voice
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
    cta = _clean_text(parts.get("cta"), "")
    body = _soft_cliche_cleanup_v17(_subtext_cleanup(_strip_cta_from_body(_clean_text(parts.get("body"), ""), cta)))

    if _is_bad_template(body):
        body = _sanitize_body(body)

    if _looks_like_ai_cliche(body):
        raise ValueError(f"Email IA jour {day} rejeté : cliché IA détecté.")

    if _contains_mixed_pronouns(body, campaign_voice) or _contains_mixed_pronouns(cta, campaign_voice):
        raise ValueError(f"Email IA jour {day} rejeté : mélange tu/vous détecté.")

    if _explanatory_score(body) >= 5:
        raise ValueError(f"Email IA jour {day} rejeté : texte trop explicatif.")

    if _subtext_score(body) >= 4:
        raise ValueError(f"Email IA jour {day} rejeté : structure trop template.")

    if not cta or _ai_cliche_score(cta) >= 3:
        cta = _natural_cta_for_payload(payload, day, nonce, campaign_voice)

    return {
        "day": day,
        "email_type": email_type,
        "subject": _clean_text(parts.get("subject"), f"Jour {day} — {offer_name}"),
        "preheader": _clean_text(parts.get("preheader"), offer_name),
        "body": _clean_text(body, ""),
        "cta": _clean_text(cta, _natural_cta_for_payload(payload, day, nonce, campaign_voice)),
    }


def _dedupe_final_emails(emails: List[Dict[str, Any]], payload: Any, email_types: List[str], campaign_voice: Dict[str, Any]) -> List[Dict[str, Any]]:
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

        email_cta = _clean_text(email.get("cta"), "")
        if not email_cta or _ai_cliche_score(email_cta) >= 3:
            email_cta = _natural_cta_for_payload(payload, day, f"dedupe-{day}", campaign_voice)

        if _looks_like_ai_cliche(str(email.get("body") or "")):
            raise ValueError(f"Email IA jour {day} rejeté : cliché IA détecté.")

        if _contains_mixed_pronouns(str(email.get("body") or ""), campaign_voice) or _contains_mixed_pronouns(email_cta, campaign_voice):
            raise ValueError(f"Email IA jour {day} rejeté : mélange tu/vous détecté.")

        if _explanatory_score(str(email.get("body") or "")) >= 5:
            raise ValueError(f"Email IA jour {day} rejeté : texte trop explicatif.")

        if _subtext_score(str(email.get("body") or "")) >= 4:
            raise ValueError(f"Email IA jour {day} rejeté : structure trop template.")

        email["cta"] = email_cta

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
    campaign_voice = _build_campaign_voice(payload, base_nonce)

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
                    campaign_voice=campaign_voice,
                )
            )

        return _dedupe_final_emails(generated, payload, email_types, campaign_voice)

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
        "campaign_voice": campaign_voice,
        "emails": emails,
    }
