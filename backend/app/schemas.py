from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cities import CITIES


class MessageCreate(BaseModel):
    sender: str = Field(max_length=50)
    recipient: str = Field(max_length=50)
    body: str = Field(min_length=1, max_length=500)
    origin: str
    destination: str

    @field_validator("sender", "recipient", "body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("origin", "destination")
    @classmethod
    def known_city(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CITIES:
            raise ValueError(
                f"unknown city {value!r}; valid cities: {', '.join(sorted(CITIES))}"
            )
        return value

    @model_validator(mode="after")
    def no_zero_length_flights(self) -> "MessageCreate":
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        return self


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: str
    recipient: str
    body: str
    origin: str
    destination: str
    distance_km: float
    status: str
    sent_at: datetime
    arrival_at: datetime
    resolved_at: datetime | None
