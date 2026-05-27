"""
LGD COMPAT BRIDGE — SocialPost

Compatibilité legacy pour les anciens imports :
    from models.social_post import SocialPost

Le vrai modèle reste :
    models.social_post_model.SocialPost
"""

from models.social_post_model import SocialPost

__all__ = ["SocialPost"]
