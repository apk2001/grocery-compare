from __future__ import annotations

from pydantic import BaseModel


class ListItem(BaseModel):
    id: str
    query: str
    qty: int = 1
    size_hint: str | None = None


class Location(BaseModel):
    lat: float
    lng: float
    city: str | None = None


class Candidate(BaseModel):
    sku_id: str
    name: str
    price: float
    mrp: float | None = None
    pack_size: str | None = None
    in_stock: bool = True


class MatchedItem(BaseModel):
    id: str
    sku_id: str | None
    name: str | None
    unit_price: float | None
    qty: int
    confidence: float


class PlatformResult(BaseModel):
    platform: str
    items: list[MatchedItem]
    subtotal: float
    missing: list[str]
    error: str | None = None


class CompareRequest(BaseModel):
    items: list[ListItem]
    location: Location
