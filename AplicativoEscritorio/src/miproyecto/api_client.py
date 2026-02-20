import base64
import copy
import json
import threading
import time

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
        self.last_error = None

        # Cache simple para GET: ayuda a que el cambio de modulos se vea fluido.
        self._cache_ttl_seconds = 25
        self._get_cache = {}
        self._cache_lock = threading.Lock()

        self._basic_header = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self._bearer = None
        if self.auth_mode == "jwt":
            self._login_jwt()

    def _login_jwt(self):
        payload = {self.user_field: self.user, self.pass_field: self.password}
        url = f"{self.base_url}/{self.jwt_login_path.lstrip('/')}"
        if requests:
            r = requests.post(url, json=payload, timeout=15)
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
                with urllib.request.urlopen(req, timeout=15) as resp:
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
            func = getattr(requests, method.lower())
            resp = func(url, headers=headers, json=data, params=params, timeout=4)

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
            raise RuntimeError(self.last_error)
        except requests.exceptions.Timeout:
            self.last_error = "La API tardo demasiado en responder."
            raise RuntimeError(self.last_error)
        except requests.exceptions.RequestException as e:
            self.last_error = f"Error en la solicitud: {e}"
            raise RuntimeError(self.last_error) from e
        except AuthError:
            raise
        except Exception as e:
            self.last_error = f"Error inesperado: {e}"
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
