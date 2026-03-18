
# LGD Bloc 5 — Webhooks + Tracking + Analytics

## Objectif

Permettre à LGD de recevoir les événements provenant de Systeme.io.

## Webhook endpoint

POST /systeme-webhooks/events

## Événements suivis

- contact_tagged
- campaign_started
- purchase

## Utilisation

Systeme.io envoie un webhook vers LGD lorsqu'un événement marketing se produit.
LGD enregistre l'événement et peut alimenter des analytics marketing.

## Exemple flux

Systeme.io
     │
     ▼
Webhook → LGD
     │
     ▼
Tracking Service
     │
     ▼
Analytics
