import base64
import copy
import json
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except Exception:
    requests = None


class AuthError(RuntimeError):
    pass


class ApiClient:
    def __init__(
        self,
        app,
        base_url: str,
        user: str,
        password: str,
        auth_mode: str = "basic",
        jwt_login_path: str = "auth/login",
        user_field: str = "username",
        pass_field: str = "password",
        token_field: str = "token",
        request_timeout: float = 25.0,
    ):
        self.app = app
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.auth_mode = auth_mode
        self.jwt_login_path = jwt_login_path
        self.user_field = user_field
        self.pass_field = pass_field
        self.token_field = token_field
        self.request_timeout = max(float(request_timeout), 4.0)
        self.last_error = None

        # Cache simple para GET: ayuda a que el cambio de modulos se vea fluido.
        self._cache_ttl_seconds = 25
        self._get_cache = {}
        self._cache_lock = threading.Lock()

        self._basic_header = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self._bearer = None

        # Debug HTTP: registra intercambio request/response para diagnostico.
        self._debug_http = True
        self._debug_console = True
        self._debug_log_file = Path(__file__).resolve().parent / "logs" / "api_debug.log"
        try:
            self._debug_log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        if self.auth_mode == "jwt":
            self._login_jwt()

    def _log_debug(self, message: str):
        if not self._debug_http:
            return
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {message}"
        if self._debug_console:
            try:
                print(line)
            except Exception:
                pass
        try:
            with self._debug_log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    @staticmethod
    def _short_text(value, max_len=1800):
        txt = str(value or "")
        if len(txt) <= max_len:
            return txt
        return txt[:max_len] + f"... [truncado {len(txt) - max_len} chars]"

    def _login_jwt(self):
        payload = {self.user_field: self.user, self.pass_field: self.password}
        url = f"{self.base_url}/{self.jwt_login_path.lstrip('/')}"
        if requests:
            r = requests.post(url, json=payload, timeout=self.request_timeout)
            if r.status_code in (401, 403):
                raise AuthError("Credenciales invalidas.")
            token = r.json().get(self.token_field) if r.text else None
        else:
            import urllib.request
            import urllib.error
            import json as _json

            req = urllib.request.Request(url, data=_json.dumps(payload).encode("utf-8"), method="POST")
            req.add_header("Accept", "application/json")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    txt = resp.read().decode("utf-8")
                    token = _json.loads(txt).get(self.token_field) if txt else None
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise AuthError("Credenciales invalidas.")
                raise

        if not token:
            raise AuthError("No se recibio token JWT.")
        self._bearer = f"Bearer {token}"

    def _cache_key(self, resource, params=None):
        frozen_params = tuple(sorted((params or {}).items()))
        return (resource, frozen_params)

    def _cache_get(self, key):
        now = time.time()
        with self._cache_lock:
            item = self._get_cache.get(key)
            if not item:
                return None
            ts, value = item
            if now - ts > self._cache_ttl_seconds:
                self._get_cache.pop(key, None)
                return None
            return copy.deepcopy(value)

    def _cache_set(self, key, value):
        with self._cache_lock:
            self._get_cache[key] = (time.time(), copy.deepcopy(value))

    def _cache_clear(self):
        with self._cache_lock:
            self._get_cache.clear()

    def _request(self, method, path, data=None, params=None):
        """Envia una peticion HTTP al backend y levanta excepciones si falla."""
        self.last_error = None
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        if self.auth_mode == "jwt":
            if not self._bearer:
                self.last_error = "No autenticado: falta Bearer token."
                raise AuthError(self.last_error)
            headers["Authorization"] = self._bearer
        else:
            headers["Authorization"] = self._basic_header

        if not requests:
            self.last_error = "La libreria 'requests' no esta instalada."
            raise RuntimeError(self.last_error)

        try:
            if self._debug_http:
                safe_headers = dict(headers)
                if "Authorization" in safe_headers:
                    safe_headers["Authorization"] = "***REDACTED***"
                self._log_debug(f"HTTP REQUEST -> {method.upper()} {url}")
                self._log_debug(f"Headers: {safe_headers}")
                if params:
                    self._log_debug(f"Params: {self._short_text(json.dumps(params, ensure_ascii=False))}")
                if data is not None:
                    self._log_debug(f"Payload: {self._short_text(json.dumps(data, ensure_ascii=False))}")

            func = getattr(requests, method.lower())
            resp = func(url, headers=headers, json=data, params=params, timeout=self.request_timeout)

            if self._debug_http:
                content_type = resp.headers.get("Content-Type", "")
                self._log_debug(f"HTTP RESPONSE <- {resp.status_code} {method.upper()} {url}")
                self._log_debug(f"Content-Type: {content_type}")
                self._log_debug(f"Body: {self._short_text(resp.text)}")

            if resp.status_code in (401, 403):
                self.last_error = f"No autorizado (HTTP {resp.status_code})."
                raise AuthError(self.last_error)

            if resp.status_code >= 400:
                self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                raise RuntimeError(self.last_error)

            if not resp.text:
                return {}

            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                return resp.json()

            return {"raw": resp.text}

        except requests.exceptions.ConnectionError:
            self.last_error = "No se pudo conectar con la API. Verifique el servidor."
            self._log_debug(f"HTTP ERROR ConnectionError: {self.last_error} | {method.upper()} {url}")
            raise RuntimeError(self.last_error)
        except requests.exceptions.Timeout:
            self.last_error = "La API tardo demasiado en responder. Intenta de nuevo en unos segundos."
            self._log_debug(f"HTTP ERROR Timeout: {self.last_error} | {method.upper()} {url}")
            raise RuntimeError(self.last_error)
        except requests.exceptions.RequestException as e:
            self.last_error = f"Error en la solicitud: {e}"
            self._log_debug(f"HTTP ERROR RequestException: {self.last_error} | {method.upper()} {url}")
            raise RuntimeError(self.last_error) from e
        except AuthError:
            self._log_debug(f"HTTP ERROR AuthError: {self.last_error} | {method.upper()} {url}")
            raise
        except Exception as e:
            self.last_error = f"Error inesperado: {e}"
            self._log_debug(f"HTTP ERROR Exception: {self.last_error} | {method.upper()} {url}")
            raise RuntimeError(self.last_error) from e

    # CRUD helpers
    def get_all(self, resource, params=None, force_refresh=False):
        key = self._cache_key(resource, params=params)
        if not force_refresh:
            cached = self._cache_get(key)
            if cached is not None:
                return cached
        data = self._request("GET", resource, params=params)
        self._cache_set(key, data)
        return copy.deepcopy(data)

    def get_by_id(self, resource, _id):
        return self._request("GET", f"{resource}/{_id}")

    def create(self, resource, payload):
        data = self._request("POST", resource, data=payload)
        self._cache_clear()
        return data

    def update(self, resource, _id, payload):
        data = self._request("PUT", f"{resource}/{_id}", data=payload)
        self._cache_clear()
        return data

    def delete(self, resource, _id):
        data = self._request("DELETE", f"{resource}/{_id}")
        self._cache_clear()
        return data
