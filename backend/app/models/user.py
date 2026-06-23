from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class UserDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    username: str
    email: str
    password_hash: str
    approved: str = "N"  # "N" = pending approval, "Y" = can log in
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
