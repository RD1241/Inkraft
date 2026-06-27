import os
import logging
import threading
from typing import Optional, Dict, Any
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

# Cache Supabase clients by (url, key) so we create ONE client per credential set
# for the whole process instead of a fresh one (with a "Connected" log line) on
# every request — SupabaseAuth() is instantiated per-request in many routes.
_client_cache: Dict[tuple, Client] = {}
_client_cache_lock = threading.Lock()


def _get_cached_client(url: str, key: str) -> Client:
    cache_key = (url, key)
    client = _client_cache.get(cache_key)
    if client is None:
        with _client_cache_lock:
            client = _client_cache.get(cache_key)
            if client is None:
                client = create_client(url, key)
                _client_cache[cache_key] = client
                print(f"[SupabaseAuth] Connected to {url}")
    return client


def _to_dict(obj) -> Optional[Dict[str, Any]]:
    """
    Safely convert a Supabase/GoTrue response object to a plain dict.
    Handles: Pydantic v1 (.dict()), Pydantic v2 (.model_dump()),
             dataclasses (__dict__), and plain dicts.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    # dataclass / plain object
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return None


class SupabaseAuth:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_SECRET_KEY or settings.SUPABASE_PUBLISHABLE_KEY
        if not self.url or not self.key:
            self.url = os.environ.get("SUPABASE_URL", "")
            self.key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")

        self.enabled = bool(self.url and self.key)
        if self.enabled:
            try:
                # Reuse the process-wide cached client (created + logged once).
                self.client: Client = _get_cached_client(self.url, self.key)
            except Exception as e:
                print(f"[SupabaseAuth] Failed to initialize: {e}. Falling back to mock auth.")
                self.enabled = False
                self.client = None
        else:
            print("[SupabaseAuth] Supabase URL or Key not set. Using local offline mock auth.")
            self.client = None

    def _ensure_client(self):
        if not self.client:
            raise ValueError("Supabase authentication is not configured.")

    def _build_auth_response(self, response) -> Dict[str, Any]:
        """
        Build a consistent auth response dict from a Supabase AuthResponse object.
        Always returns: { user: {...}, session: { access_token: str, ... } }
        """
        user_dict    = _to_dict(getattr(response, "user", None))
        session_obj  = getattr(response, "session", None)
        session_dict = _to_dict(session_obj)

        # Fallback: if session serialization failed but the object has access_token
        if session_dict is None and session_obj is not None:
            session_dict = {
                "access_token": getattr(session_obj, "access_token", None),
                "refresh_token": getattr(session_obj, "refresh_token", None),
                "expires_in":    getattr(session_obj, "expires_in", None),
                "token_type":    getattr(session_obj, "token_type", "bearer"),
            }

        # Promote access_token to top level for easy frontend access
        result = {
            "user":    user_dict,
            "session": session_dict,
        }
        if session_dict and session_dict.get("access_token"):
            result["access_token"] = session_dict["access_token"]

        return result

    # ------------------------------------------------------------------
    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        if not self.enabled:
            mock_id = "00000000-0000-0000-0000-000000000000"
            return {
                "access_token": "mock-token",
                "user":    {"id": mock_id, "email": email},
                "session": {"access_token": "mock-token", "user": {"id": mock_id, "email": email}},
            }
        self._ensure_client()
        response = self.client.auth.sign_up({"email": email, "password": password})
        return self._build_auth_response(response)

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        if not self.enabled:
            mock_id = "00000000-0000-0000-0000-000000000000"
            return {
                "access_token": "mock-token",
                "user":    {"id": mock_id, "email": email},
                "session": {"access_token": "mock-token", "user": {"id": mock_id, "email": email}},
            }
        self._ensure_client()
        response = self.client.auth.sign_in_with_password({"email": email, "password": password})
        result = self._build_auth_response(response)
        if not result.get("access_token"):
            raise ValueError("Login succeeded but no session was returned. "
                             "The account may require email confirmation.")
        return result

    def sign_out(self, token: str) -> None:
        if not self.enabled or not self.client:
            return
        try:
            self.client.auth.set_session(access_token=token, refresh_token="")
            self.client.auth.sign_out()
        except Exception:
            pass

    def get_user(self, token: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return {
                "id":    "00000000-0000-0000-0000-000000000000",
                "email": "mock@example.com",
                "role":  "authenticated",
            }
        if not self.client:
            return None
        try:
            response = self.client.auth.get_user(token)
            if response and response.user:
                return _to_dict(response.user)
            return None
        except Exception:
            return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        return self.get_user(token)

