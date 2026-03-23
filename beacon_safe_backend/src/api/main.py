import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.db import load_db_config, try_connect_once

logger = logging.getLogger("beacon_safe_backend.api")


def _configure_logging() -> None:
    """Configure basic logging once for the API container."""
    # Keep logging simple and deterministic. Runtime (uvicorn) may override handlers.
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


_configure_logging()

openapi_tags = [
    {
        "name": "Health",
        "description": "Service health and basic diagnostics.",
    },
    {
        "name": "Auth",
        "description": "Mock authentication (accepts any username/password) and mock JWT issuance.",
    },
    {
        "name": "Devices",
        "description": "IoT device data used by the dashboard (hardcoded in this MVP).",
    },
    {
        "name": "Settings",
        "description": "User profile and system preference settings (mock persistence in-memory for this MVP).",
    },
]


app = FastAPI(
    title="Beacon-Safe Backend API",
    description=(
        "Beacon-Safe backend providing mock authentication, dashboard device data, "
        "and basic user settings APIs for the Beacon-Safe frontend."
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# Optional DB connectivity (Postgres). The app remains functional without DB for this MVP,
# but we log a one-time diagnostic at startup to ensure the database container wiring is correct.
_db_cfg = load_db_config()
if _db_cfg:
    ok, msg = try_connect_once(_db_cfg)
    if ok:
        logger.info("DBConnectivityFlow success")
    else:
        logger.warning("DBConnectivityFlow failed detail=%s", msg)
else:
    logger.info("DBConnectivityFlow skipped (DATABASE_URL not set)")


def _get_allowed_origins() -> List[str]:
    """
    Return allowed origins for CORS.

    Contract:
    - Reads `VITE_FRONTEND_URL` if present (may contain a single origin).
    - If absent, falls back to wildcard `*` for local/dev convenience.
    """
    frontend_url = os.getenv("VITE_FRONTEND_URL", "").strip()
    if frontend_url:
        return [frontend_url]
    return ["*"]


# CORS for the Vite frontend.
# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] in browsers.
# We keep allow_credentials disabled for widest compatibility with mock auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Models
# -----------------------------
class LoginRequest(BaseModel):
    """Request body for the mock login endpoint."""

    username: str = Field(..., min_length=1, description="Username (any non-empty value is accepted).")
    password: str = Field(..., min_length=1, description="Password (any non-empty value is accepted).")


class LoginResponse(BaseModel):
    """Response payload for mock login.

    NOTE: This shape is intentionally flat to match the existing frontend `User` type:
      { username, email, token }
    """

    username: str = Field(..., description="Authenticated username (frontend-compatible).")
    email: str = Field(..., description="User email (frontend-compatible).")
    token: str = Field(..., description="Mock JWT token to be used as Bearer token in Authorization header.")


DeviceStatus = Literal["Online", "Offline", "Warning"]


class Device(BaseModel):
    """Device model for the dashboard."""

    id: str = Field(..., description="Unique device identifier.")
    name: str = Field(..., description="Human-friendly device name.")
    location: str = Field(..., description="Device physical location.")
    status: DeviceStatus = Field(..., description="Current device status.")
    battery: int = Field(..., ge=0, le=100, description="Battery level percentage (0-100).")


class Settings(BaseModel):
    """Settings returned by /settings endpoints.

    NOTE: This shape is intentionally flat to match the existing frontend `ProfileSettings` type:
      { name, email, theme }
    """

    name: str = Field(..., description="User display name.")
    email: str = Field(..., description="User email address.")
    theme: Literal["light", "dark"] = Field("dark", description="UI theme preference.")


class SettingsUpdateRequest(BaseModel):
    """PUT request payload for /settings."""

    name: Optional[str] = Field(default=None, description="Optional display name update.")
    email: Optional[str] = Field(default=None, description="Optional email update.")
    theme: Optional[Literal["light", "dark"]] = Field(default=None, description="Optional theme update.")


class AuthContext(BaseModel):
    """Authenticated request context created by the mock JWT verifier."""

    username: str = Field(..., description="Authenticated username extracted from the token.")
    token: str = Field(..., description="Raw token string (mock JWT).")


# -----------------------------
# Mock data store (in-memory)
# -----------------------------
# NOTE: This is an MVP mock implementation. Persistence can be swapped later with DB storage.
_SETTINGS_STORE: Dict[str, Settings] = {}


def _utc_now_iso() -> str:
    """Return ISO timestamp in UTC for token generation."""
    return datetime.now(timezone.utc).isoformat()


def _issue_mock_jwt(username: str) -> str:
    """
    Issue a deterministic, inspectable mock JWT string.

    Contract:
    - Input: username (non-empty)
    - Output: string token that includes username and issue time for debuggability
    - Security: NOT a real JWT. Do not use in production.
    """
    return f"mockjwt::{username}::{_utc_now_iso()}"


def _parse_mock_jwt(token: str) -> Optional[str]:
    """
    Parse the mock JWT token and return the username if valid.

    Expected token format:
      mockjwt::<username>::<iso_timestamp>

    Returns:
      username if format valid, otherwise None
    """
    if not token.startswith("mockjwt::"):
        return None
    parts = token.split("::", maxsplit=2)
    # parts should be ["mockjwt", "<username>", "<timestamp>"]
    if len(parts) != 3:
        return None
    _, username, _ts = parts
    if not username.strip():
        return None
    return username.strip()


# PUBLIC_INTERFACE
def verify_mock_jwt(authorization: Annotated[Optional[str], Header()] = None) -> AuthContext:
    """
    Verify a mock JWT from `Authorization: Bearer <token>` header.

    Contract:
    - Inputs:
        - authorization header (optional)
    - Output:
        - AuthContext(username, token)
    - Errors:
        - 401 if header missing/invalid or token malformed
    - Side effects:
        - none
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'.",
        )
    token = authorization.split(" ", 1)[1].strip()
    username = _parse_mock_jwt(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
    return AuthContext(username=username, token=token)


def _get_or_init_settings_for_user(username: str) -> Settings:
    """Return settings for a user; initialize defaults if absent."""
    if username in _SETTINGS_STORE:
        return _SETTINGS_STORE[username]

    # Default values derived from username.
    settings = Settings(
        name=username.title(),
        email=f"{username}@beacon-safe.local",
        theme="dark",
    )
    _SETTINGS_STORE[username] = settings
    return settings


def _get_devices_hardcoded() -> List[Device]:
    """
    Return the hardcoded list of devices shown in the dashboard.

    Invariants:
    - Exactly 4 devices
    - Battery is 0..100
    - Status is one of Online/Offline/Warning
    """
    return [
        Device(
            id="dev-001",
            name="Beacon Gate A",
            location="Warehouse - North Entrance",
            status="Online",
            battery=86,
        ),
        Device(
            id="dev-002",
            name="Beacon Gate B",
            location="Warehouse - South Entrance",
            status="Warning",
            battery=41,
        ),
        Device(
            id="dev-003",
            name="Cold Storage Monitor",
            location="Facility - Cold Room 2",
            status="Online",
            battery=73,
        ),
        Device(
            id="dev-004",
            name="Perimeter Sensor",
            location="Outdoor - West Fence",
            status="Offline",
            battery=12,
        ),
    ]


# -----------------------------
# Routes
# -----------------------------
@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Basic health endpoint used for uptime checks.",
    operation_id="health_check",
)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"message": "Healthy"}


@app.get(
    "/healthz",
    tags=["Health"],
    summary="Health check (platform)",
    description="Health endpoint used by the deployment/preview platform readiness probes.",
    operation_id="health_check_platform",
)
def health_check_platform() -> Dict[str, str]:
    """Health check endpoint for platform readiness probes (alias of `/`)."""
    return health_check()


@app.get(
    "/db-status",
    tags=["Health"],
    summary="Database status",
    description="Checks whether the API can connect to Postgres using DATABASE_URL. DB is optional for this MVP.",
    operation_id="db_status",
)
def db_status() -> Dict[str, str]:
    """Return simple DB connectivity status for integration diagnostics."""
    cfg = load_db_config()
    if not cfg:
        return {"status": "skipped", "detail": "DATABASE_URL not set"}
    ok, msg = try_connect_once(cfg)
    return {"status": "ok" if ok else "error", "detail": msg}


@app.post(
    "/login",
    tags=["Auth"],
    summary="Mock login (issues mock JWT)",
    description="Accepts any non-empty username/password and returns a mock JWT + user info.",
    operation_id="login",
    response_model=LoginResponse,
)
def login(payload: LoginRequest) -> LoginResponse:
    """
    Mock login endpoint.

    Contract:
    - Input: LoginRequest with non-empty username and password
    - Output: LoginResponse including a mock token and default user fields
    - Side effects:
        - initializes settings store defaults for this user (in-memory)
    """
    username = payload.username.strip()
    logger.info("LoginFlow start username=%s", username)

    token = _issue_mock_jwt(username)
    settings = _get_or_init_settings_for_user(username)

    resp = LoginResponse(token=token, username=username, email=settings.email)
    logger.info("LoginFlow success username=%s", username)
    return resp


@app.get(
    "/devices",
    tags=["Devices"],
    summary="List devices (hardcoded)",
    description="Returns a hardcoded list of 4 IoT devices for the dashboard UI.",
    operation_id="list_devices",
    response_model=List[Device],
)
def list_devices(_auth: Annotated[AuthContext, Depends(verify_mock_jwt)]) -> List[Device]:
    """
    List devices for the authenticated user.

    Contract:
    - Requires Authorization Bearer token
    - Output: list of Device objects (hardcoded)
    - Errors: 401 if token missing/invalid
    """
    logger.info("DevicesFlow start username=%s", _auth.username)
    devices = _get_devices_hardcoded()
    logger.info("DevicesFlow success username=%s count=%d", _auth.username, len(devices))
    return devices


@app.get(
    "/dashboard",
    tags=["Devices"],
    summary="List devices (dashboard alias)",
    description="Alias endpoint for frontend compatibility. Returns the same payload as /devices.",
    operation_id="list_devices_dashboard_alias",
    response_model=List[Device],
)
def dashboard_devices(_auth: Annotated[AuthContext, Depends(verify_mock_jwt)]) -> List[Device]:
    """Alias for list_devices; kept to support the frontend /dashboard call."""
    return list_devices(_auth)


@app.get(
    "/settings",
    tags=["Settings"],
    summary="Get settings",
    description="Returns profile info and system preferences for the authenticated user.",
    operation_id="get_settings",
    response_model=Settings,
)
def get_settings(_auth: Annotated[AuthContext, Depends(verify_mock_jwt)]) -> Settings:
    """
    Get settings for the authenticated user.

    Contract:
    - Requires Authorization Bearer token
    - Output: Settings object
    - Errors: 401 if token missing/invalid
    """
    logger.info("SettingsGetFlow start username=%s", _auth.username)
    settings = _get_or_init_settings_for_user(_auth.username)
    logger.info("SettingsGetFlow success username=%s theme=%s", _auth.username, settings.theme)
    return settings


@app.put(
    "/settings",
    tags=["Settings"],
    summary="Update settings",
    description="Updates name/email/theme for the authenticated user (in-memory).",
    operation_id="update_settings",
    response_model=Settings,
)
def update_settings(
    payload: SettingsUpdateRequest,
    _auth: Annotated[AuthContext, Depends(verify_mock_jwt)],
) -> Settings:
    """
    Update settings for the authenticated user.

    Contract:
    - Requires Authorization Bearer token
    - Input: SettingsUpdateRequest (name/email/theme all optional)
    - Output: updated Settings object
    - Errors: 401 if token missing/invalid
    - Side effects: mutates in-memory settings store
    """
    logger.info("SettingsUpdateFlow start username=%s", _auth.username)
    current = _get_or_init_settings_for_user(_auth.username)

    updated = Settings(
        name=payload.name if payload.name is not None else current.name,
        email=payload.email if payload.email is not None else current.email,
        theme=payload.theme if payload.theme is not None else current.theme,
    )
    _SETTINGS_STORE[_auth.username] = updated

    logger.info(
        "SettingsUpdateFlow success username=%s theme=%s",
        _auth.username,
        updated.theme,
    )
    return updated
