from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from pydantic import BaseModel, ConfigDict, EmailStr, Field

Base = declarative_base()

# =====================================================================
# SQLAlchemy Models
# =====================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String, nullable=True)

    references = relationship("Reference", back_populates="location", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', latitude={self.latitude}, longitude={self.longitude})>"


class Reference(Base):
    __tablename__ = "references"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    location = relationship("Location", back_populates="references")

    def __repr__(self):
        return f"<Reference(id={self.id}, description='{self.description}', location_id={self.location_id})>"


# =====================================================================
# Pydantic Schemas (API DTOs)
# =====================================================================

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    disabled: Optional[bool] = False


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ReferenceBase(BaseModel):
    description: str
    location_id: int


class ReferenceCreate(ReferenceBase):
    pass


class ReferenceResponse(ReferenceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class LocationBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None


class LocationCreate(LocationBase):
    name: str = Field(min_length=1, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)


class LocationResponse(LocationBase):
    id: int
    references: List[ReferenceResponse] = []

    model_config = ConfigDict(from_attributes=True)
