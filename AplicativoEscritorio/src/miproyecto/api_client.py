import base64
import json
try:
    import requests
except Exception:
    requests = None

class AuthError(RuntimeError):
    pass

class ApiClient:
    def __init__(self, app, base_url: str, user: str, password: str,
                 auth_mode: str = "basic",
                 jwt_login_path: str = "auth/login",
                 user_field: str = "username",
                 pass_field: str = "password",
                 token_field: str = "token"):
        self.app = app
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.auth_mode = auth_mode
        self.jwt_login_path = jwt_login_path
        self.user_field = user_field
        self.pass_field = pass_field
        self.token_field = token_field

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
                raise AuthError("Credenciales inválidas.")
            token = r.json().get(self.token_field) if r.text else None
        else:
            import urllib.request, urllib.error, json as _json
            req = urllib.request.Request(
                url, data=_json.dumps(payload).encode("utf-8"), method="POST"
            )
            req.add_header("Accept", "application/json")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    txt = resp.read().decode("utf-8")
                    token = _json.loads(txt).get(self.token_field) if txt else None
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise AuthError("Credenciales inválidas.")
                raise
        if not token:
            raise AuthError("No se recibió token JWT.")
        self._bearer = f"Bearer {token}"

    def _request(self, method, path, data=None, params=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.auth_mode == "jwt":
            if not self._bearer:
                raise AuthError("No autenticado: falta Bearer token.")
            headers["Authorization"] = self._bearer
        else:
            headers["Authorization"] = self._basic_header

        if requests:
            func = getattr(requests, method.lower())
            resp = func(url, headers=headers, json=data, params=params, timeout=15)
            if resp.status_code in (401, 403):
                raise AuthError(f"No autorizado (HTTP {resp.status_code}).")
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            if resp.text and resp.headers.get("Content-Type", "").startswith("application/json"):
                return resp.json()
            return None
        else:
            import urllib.request, urllib.error, json as _json
            payload = None if data is None else _json.dumps(data).encode("utf-8")
            if params:
                from urllib.parse import urlencode
                qs = urlencode(params)
                url = url + ("&" if "?" in url else "?") + qs
            req = urllib.request.Request(url, data=payload, method=method.upper())
            for k, v in headers.items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read().decode("utf-8")
                    if content:
                        try:
                            return json.loads(content)
                        except Exception:
                            return content
                    return None
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                if e.code in (401, 403):
                    raise AuthError(f"No autorizado (HTTP {e.code}): {body}")
                raise RuntimeError(f"HTTP {e.code}: {body}")

    # CRUD helpers
    def get_all(self, resource, params=None): return self._request("GET", resource, params=params)
    def get_by_id(self, resource, _id): return self._request("GET", f"{resource}/{_id}")
    def create(self, resource, payload): return self._request("POST", resource, data=payload)
    def update(self, resource, _id, payload): return self._request("PUT", f"{resource}/{_id}", data=payload)
    def delete(self, resource, _id): return self._request("DELETE", f"{resource}/{_id}")
