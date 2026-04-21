from pydantic import BaseModel


class AnkiSearchResult(BaseModel):
    note_id: int
    front: str
    back: str
    tags: list[str]


class AnkiCardMaturity(BaseModel):
    topic: str
    young: int
    mature: int
