import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from src.models import User, TokenData, UserSession

logger = logging.getLogger("ruta_clara.auth")

_DEFAULT_SECRET = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"


def _resolve_secret_key() -> str:
    configured_secret = os.getenv("SECRET_KEY", "").strip()
    environment = os.getenv("RAILWAY_ENVIRONMENT_NAME", os.getenv("ENVIRONMENT", "")).strip().lower()
    is_production = environment in {"production", "prod"}
    if is_production and (len(configured_secret) < 32 or configured_secret == _DEFAULT_SECRET):
        raise RuntimeError("SECRET_KEY debe configurarse en producción con un valor único de al menos 32 caracteres.")
    if not configured_secret:
        logger.warning("SECRET_KEY no configurada. Se usa un valor de desarrollo inseguro; no desplegar así en producción.")
        return _DEFAULT_SECRET
    if configured_secret == _DEFAULT_SECRET:
        logger.warning("Se está usando la SECRET_KEY de desarrollo insegura.")
    return configured_secret


SECRET_KEY = _resolve_secret_key()
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        truncated_password = plain_password[:72] if plain_password else ""
        return pwd_context.verify(truncated_password, hashed_password)
    except Exception:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    try:
        truncated_password = password[:72] if password else ""
        return pwd_context.hash(truncated_password)
    except Exception:
        from passlib.hash import pbkdf2_sha256
        return pbkdf2_sha256.hash(password)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    identifier = (username or "").strip()
    user = db.query(User).filter((User.username == identifier) | (User.email == identifier.lower())).first()
    if not user:
        return None
    if user.disabled or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        persistent_session = db.query(UserSession).filter(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None)
        ).first()
        if persistent_session is None:
            raise credentials_exception
        user = db.query(User).filter(User.id == persistent_session.user_id).first()
        if user is None:
            raise credentials_exception
        return user

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario desactivado")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren permisos de administrador")
    return current_user
