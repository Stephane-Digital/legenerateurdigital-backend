
# LGD Emailing IA + Systeme.io — Architecture

## Vue globale

          LGD Frontend
               │
               ▼
      Emailing IA Generator
               │
               ▼
      Backend Emailing Module
               │
     ┌─────────┼──────────┐
     ▼         ▼          ▼
systeme_io_service   systeme_io_dispatcher   systeme_sync_service
     │                     │                     │
     ▼                     ▼                     ▼
systeme_io_client  →  Systeme.io API  ←  Sync contacts/tags/campaigns
                           │
                           ▼
                   Systeme.io Automation
                           │
                           ▼
                      Email Campaigns


## Flux principal

1. Génération campagne Emailing IA
2. Préparation payload Systeme.io
3. Envoi via dispatcher
4. Création contact
5. Application tags
6. Workflow Systeme.io
7. Inscription campagne email


## Synchronisation

LGD peut récupérer :

- contacts
- tags
- campagnes

via les routes :

/systeme-sync/contacts
/systeme-sync/tags
/systeme-sync/campaigns


## Avantages architecture

- isolation du module emailing
- aucune pollution du planner social
- extensible CRM
- base pour analytics LGD
