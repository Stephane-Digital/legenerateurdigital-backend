
# LGD Bloc 6 — Dashboard Analytics Emailing IA

## Endpoint

GET /email-analytics/dashboard

## Données retournées

- contacts capturés
- campagnes lancées
- ventes générées

## Exemple réponse

{
  "module": "LGD Emailing IA",
  "stats": {
    "contacts_captured": 10,
    "campaigns_started": 3,
    "sales_generated": 2
  },
  "events_tracked": 15
}

## Utilisation frontend

Le dashboard LGD peut appeler :

/email-analytics/dashboard

et afficher :

- nombre de leads
- campagnes lancées
- revenus générés
