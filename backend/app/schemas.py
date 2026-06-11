import re
from datetime import datetime

from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator,
)

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
    sent_at: datetime = Field(description="UTC")
    arrival_at: datetime = Field(description="UTC")
    resolved_at: datetime | None = Field(description="UTC")


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


class RegisterIn(BaseModel):
    username: str
    email: EmailStr = Field(max_length=255)  # SQLite won't enforce String(255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError(
                "username must be 3-30 characters: letters, digits, underscore"
            )
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Stored lowercase so plain equality works everywhere downstream.
        return value.strip().lower()


class LoginIn(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime
