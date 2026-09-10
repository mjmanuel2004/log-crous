from typing import List, Optional

from pydantic import Field, HttpUrl, BaseModel


class Accommodation(BaseModel):
    id: int | None
    title: str | None
    price: float | str | None
    overview_details: str | None = None
    image_url: HttpUrl | None = None


class SearchResults(BaseModel):
    search_url: HttpUrl
    count: Optional[int]
    accommodations: List[Accommodation]
