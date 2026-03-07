from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SocialLogOut(BaseModel):
    id: int
    user_id: int
    post_id: Optional[int] = None

    network: str
    content: Optional[str] = None

    status: str
    message: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}
