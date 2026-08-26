from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    quantity: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=20)
    source: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=40)
    location: Optional[str] = Field(default=None, max_length=40)
    added_by: Optional[str] = None  # user name; server resolves to id


class ItemPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    quantity: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    photo_url: Optional[str] = None


class ItemOut(BaseModel):
    id: str
    name: str
    added_at: datetime
    added_by: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    photo_url: Optional[str] = None
    consumed_at: Optional[datetime] = None
    consumed_by: Optional[str] = None


class PrintJobOut(BaseModel):
    id: int
    item_id: str
    requested_at: datetime
    printed_at: Optional[datetime] = None
    error: Optional[str] = None
    attempts: int
