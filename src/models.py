
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import declarative_base, relationship

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

Base = declarative_base()


# =========================================================
# MODELOS SQLALCHEMY
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)
    role = Column(String(20), nullable=False, default="operator", server_default="operator")


class DeliveryRoute(Base):
    """Agrupador de paradas en una ruta específica (ej. Mañana, Tarde, Envigado)."""
    __tablename__ = "delivery_routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    locations = relationship(
        "Location",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="Location.id"
    )

    def __repr__(self):
        return f"<DeliveryRoute(id={self.id}, name='{self.name}')>"


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)

    # Ruta a la que pertenece la parada
    route_id = Column(
        Integer,
        ForeignKey("delivery_routes.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Nombre de unidad, empresa o establecimiento
    name = Column(String(500), nullable=False)

    # Dirección física
    address = Column(String(500), nullable=True)

    # Información adicional
    municipality = Column(String(150), nullable=True)
    neighborhood = Column(String(150), nullable=True)
    unit_number = Column(String(150), nullable=True)
    entrance_name = Column(String(150), nullable=True)
    entrance_confirmed = Column(Boolean, nullable=False, default=False, server_default="0")
    location_source = Column(String(30), nullable=True)

    # Estado de entrega y trazabilidad
    delivered = Column(Boolean, default=False)
    status = Column(String(30), nullable=False, default="pending", server_default="pending")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status_updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Coordenadas internas para mapas y rutas
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    route = relationship("DeliveryRoute", back_populates="locations")
    created_by = relationship("User", foreign_keys=[created_by_id])
    status_updated_by = relationship("User", foreign_keys=[status_updated_by_id])
    status_history = relationship("LocationStatusHistory", back_populates="location", cascade="all, delete-orphan", order_by="LocationStatusHistory.changed_at")

    @property
    def created_by_username(self):
        return self.created_by.username if self.created_by else None

    @property
    def status_updated_by_username(self):
        return self.status_updated_by.username if self.status_updated_by else None

    references = relationship(
        "Reference",
        back_populates="location",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', route_id={self.route_id})>"


class LocationStatusHistory(Base):
    __tablename__ = "location_status_history"
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    location = relationship("Location", back_populates="status_history")
    changed_by = relationship("User")
    @property
    def changed_by_username(self):
        return self.changed_by.username if self.changed_by else "Sistema"


class Reference(Base):
    __tablename__ = "references"

    id = Column(Integer, primary_key=True, index=True)

    description = Column(String, nullable=False)

    location_id = Column(
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False
    )

    location = relationship(
        "Location",
        back_populates="references"
    )


# =========================================================
# ESQUEMAS PYDANTIC
# =========================================================

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    disabled: Optional[bool] = False


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    role: str = "operator"

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# =========================================================
# RUTAS DE ENTREGA (DELIVERY ROUTES)
# =========================================================

class DeliveryRouteBase(BaseModel):
    name: str


class DeliveryRouteCreate(DeliveryRouteBase):
    pass


class DeliveryRouteUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class DeliveryRouteResponse(DeliveryRouteBase):
    id: int
    created_at: Optional[datetime] = None
    is_active: bool = True
    stops_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# REFERENCIAS
# =========================================================

class ReferenceBase(BaseModel):
    description: str
    location_id: int


class ReferenceCreate(ReferenceBase):
    pass


class ReferenceResponse(ReferenceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# UBICACIONES
# =========================================================

class LocationBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    municipality: Optional[str] = None
    neighborhood: Optional[str] = None
    unit_number: Optional[str] = None
    entrance_name: Optional[str] = None
    entrance_confirmed: bool = False
    location_source: Optional[str] = None
    route_id: Optional[int] = None
    delivered: Optional[bool] = False


class LocationCreate(LocationBase):

    name: str = Field(
        min_length=1,
        max_length=500
    )

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )

    address: Optional[str] = Field(
        default=None,
        max_length=500
    )

    municipality: Optional[str] = Field(
        default=None,
        max_length=150
    )

    neighborhood: Optional[str] = Field(
        default=None,
        max_length=150
    )

    unit_number: Optional[str] = Field(
        default=None,
        max_length=150
    )

    entrance_name: Optional[str] = Field(default=None, max_length=150)
    entrance_confirmed: bool = False
    location_source: Optional[str] = Field(default=None, max_length=30)
    route_id: Optional[int] = None
    delivered: Optional[bool] = False


class LocationUpdateDelivered(BaseModel):
    delivered: bool


class LocationResponse(LocationBase):
    id: int
    route_id: Optional[int] = None
    delivered: bool = False
    status: str = "pending"
    created_by_id: Optional[int] = None
    created_by_username: Optional[str] = None
    status_updated_by_id: Optional[int] = None
    status_updated_by_username: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    references: List[ReferenceResponse] = Field(
        default_factory=list
    )

    model_config = ConfigDict(from_attributes=True)
