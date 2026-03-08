# -*- coding: utf-8 -*-
import calendar
from calendar import Calendar
import sys
import base64
import json
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
from pathlib import Path

import json
import re
import tkinter as tk
from tkinter import messagebox
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

try:
    import requests  # opcional; si no está, usa urllib
except Exception:
    requests = None

def centrar_ventana(win, ancho=None, alto=None):
    """
    Centra una ventana de CustomTkinter/Tkinter en cualquier resolución.
    Compatible con escalado DPI y tamaños grandes (p. ej. 1180x720).
    """
    def _do_center(_=None):
        win.update_idletasks()

        # Usa el tamaño actual o el especificado
        w = ancho or win.winfo_width()
        h = alto or win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()

        try:
            # Ajuste DPI
            scale = float(win.tk.call('tk', 'scaling'))
            if scale and scale != 1.0:
                sw = int(sw * (1 / scale))
                sh = int(sh * (1 / scale))
        except Exception:
            pass

        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.update()

    # Espera a que la ventana se "dibuje" realmente antes de centrar
    win.bind("<Map>", _do_center)

class AuthError(RuntimeError):
    pass



# ==========================================
#  Cliente REST con Basic Auth (y JWT opc.)
# ==========================================
class ApiClient:
    """
    Cliente REST simple:
      - auth_mode="basic": usa Authorization: Basic <base64(user:pass)>
      - auth_mode="jwt": hace POST {jwt_login_path} y usa Bearer <token>
    """
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

        def do_post(u, data):
            if requests:
                r = requests.post(
                    u, json=data, timeout=15,
                    headers={"Accept": "application/json", "Content-Type": "application/json"}
                )
                # 401/403 => credenciales inválidas o sin permisos
                if r.status_code in (401, 403):
                    raise AuthError(f"Credenciales inválidas (HTTP {r.status_code}).")
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
                return r.json() if r.text else {}
            else:
                import urllib.request, urllib.error, json as _json
                req = urllib.request.Request(
                    u, data=_json.dumps(data).encode("utf-8"), method="POST"
                )
                req.add_header("Accept", "application/json")
                req.add_header("Content-Type", "application/json")
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        txt = resp.read().decode("utf-8")
                        return _json.loads(txt) if txt else {}
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8")
                    if e.code in (401, 403):
                        raise AuthError(f"Credenciales inválidas (HTTP {e.code}): {body}")
                    raise RuntimeError(f"HTTP {e.code}: {body}")

        resp = do_post(url, payload) or {}
        token = resp.get(self.token_field)
        if not token:
            # Tratamos ausencia de token como fallo de autenticación
            raise AuthError("No se recibió token JWT en la respuesta.")
        self._bearer = f"Bearer {token}"


    def _request(self, method, path, data=None, params=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        if self.auth_mode == "jwt":
            if not self._bearer:
                # No se ha autenticado correctamente
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
            # Fallback urllib
            import urllib.request, urllib.error, json as _json
            payload = None if data is None else _json.dumps(data).encode("utf-8")
            if params:
                from urllib.parse import urlencode
                qs = urlencode(params)
                url = url + ("&" if "" in url else "") + qs
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


# =============== LOGIN MODAL =================
class LoginDialog(ctk.CTkToplevel):
    def __init__(self, master, on_success, brand="CEA HARO"):
        super().__init__(master)
        self.app = master
        self.title("Inicio de sesión")

        # Tamaño más grande y centrado
        W, H = 720, 460
        self.geometry(f"{W}x{H}")
        try:
            centrar_ventana(self, W, H)
        except Exception:
            pass

        self.resizable(False, False)
        self.transient(master)
        self.grab_set()   # modal
        self.focus_set()

        # Paleta tomada desde la app (colores ya definidos en HaroDesktopApp)
        fg_bg      = getattr(self.app, "COLOR_BG", ("#FFFFFF", "#0f0f10"))
        fg_panel   = getattr(self.app, "COLOR_PANEL", ("#FFFFFF", "#151517"))
        fg_text    = getattr(self.app, "COLOR_TEXT", ("#111111", "#F5F7FA"))
        fg_muted   = getattr(self.app, "COLOR_MUTED", ("#5A5F6A", "#AAB2C0"))
        fg_divider = getattr(self.app, "COLOR_DIVIDER", ("#EFEFF2", "#24262b"))
        fg_input   = getattr(self.app, "COLOR_INPUT_BG", ("#F6F7F9", "#1b1d22"))
        fg_red     = getattr(self.app, "COLOR_RED", ("#E53935", "#ff4c4c"))
        fg_yellow  = getattr(self.app, "COLOR_YELLOW", ("#FFC107", "#FFD54F"))

        self.configure(fg_color=fg_bg)

        # Layout principal (2 columnas): izquierda brand / derecha formulario
        self.grid_columnconfigure(0, weight=1, minsize=280)
        self.grid_columnconfigure(1, weight=1, minsize=440)
        self.grid_rowconfigure(0, weight=1)

        # -------- Columna Izquierda (branding) --------
        left = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                            border_width=2, border_color=fg_divider)
        left.grid(row=0, column=0, padx=(16,8), pady=16, sticky="nsew")
        left.grid_rowconfigure((0,1,2,3,4), weight=0)
        left.grid_rowconfigure(5, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Logo si ya lo cargó la app (opcional)
        logo_img = getattr(self.app, "logo_image", None)
        if logo_img:
            ctk.CTkLabel(left, image=logo_img, text="").grid(row=0, column=0, pady=(20,10))

        ctk.CTkLabel(
            left, text=brand, text_color=fg_text,
            font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=1, column=0, padx=18, pady=(6,2), sticky="n")

        ctk.CTkLabel(
            left, text="Sistema de Información",
            text_color=fg_muted, font=ctk.CTkFont(size=13)
        ).grid(row=2, column=0, padx=18, pady=(2, 16), sticky="n")

        # Highlights
        bullets = [
            "Gestión integral de estudiantes"
        ]
        for i, t in enumerate(bullets):
            ctk.CTkLabel(left, text=f"• {t}", text_color=fg_text, anchor="w")\
                .grid(row=3+i, column=0, padx=18, pady=2, sticky="w")

        # -------- Columna Derecha (formulario) --------
        right = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                             border_width=2, border_color=fg_divider)
        right.grid(row=0, column=1, padx=(8,16), pady=16, sticky="nsew")
        for c in range(2):
            right.grid_columnconfigure(c, weight=1)
        r = 0

        ctk.CTkLabel(
            right, text="Bienvenido",
            text_color=fg_text, font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=r, column=0, columnspan=2, padx=20, pady=(18,6), sticky="w"); r += 1

        ctk.CTkLabel(
            right, text="Ingresa con tus credenciales para continuar",
            text_color=fg_muted, font=ctk.CTkFont(size=12)
        ).grid(row=r, column=0, columnspan=2, padx=20, pady=(0,16), sticky="w"); r += 1

        # Usuario
        ctk.CTkLabel(right, text="Usuario", text_color=fg_text)\
            .grid(row=r, column=0, columnspan=2, padx=20, pady=(0,6), sticky="w"); r += 1
        self.en_user = ctk.CTkEntry(
            right, height=40, corner_radius=12, fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider, placeholder_text="usuario"
        )
        self.en_user.grid(row=r, column=0, columnspan=2, padx=20, pady=(0,12), sticky="ew"); r += 1

        # Contraseña con botón "mostrar"
        ctk.CTkLabel(right, text="Contraseña", text_color=fg_text)\
            .grid(row=r, column=0, columnspan=2, padx=20, pady=(0,6), sticky="w"); r += 1

        pass_wrap = ctk.CTkFrame(right, fg_color="transparent")
        pass_wrap.grid(row=r, column=0, columnspan=2, padx=20, pady=(0,12), sticky="ew")
        pass_wrap.grid_columnconfigure(0, weight=1)
        self.en_pass = ctk.CTkEntry(
            pass_wrap, height=40, corner_radius=12, show="*",
            fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider, placeholder_text="********"
        )
        self.en_pass.grid(row=0, column=0, sticky="ew", padx=(0,8))
        self._pass_visible = False
        ctk.CTkButton(
            pass_wrap, text="👁", width=40, height=40, corner_radius=12,
            fg_color=fg_divider, hover_color=fg_input, text_color=fg_text,
            command=self._toggle_pass
        ).grid(row=0, column=1, sticky="e")

        # Recordarme / ayuda
        self.cb_remember = ctk.CTkCheckBox(
            right, text="Recordar usuario en este equipo", text_color=fg_text,
            fg_color=fg_input, border_color=fg_divider, hover_color=fg_divider
        )
        self.cb_remember.grid(row=r+1, column=0, padx=20, pady=(0, 10), sticky="w")

        ctk.CTkButton(
            right, text="¿Olvidaste tu contraseña", height=28, corner_radius=8,
            fg_color="transparent", hover_color=fg_divider, text_color=fg_muted,
            command=lambda: messagebox.showinfo("Ayuda", "Contacta al administrador del sistema.")
        ).grid(row=r+1, column=1, padx=20, pady=(0,10), sticky="e"); r += 2

        # Mensaje de error (oculto por defecto)
        self.err = ctk.CTkLabel(
            right, text="", text_color=fg_red, anchor="w", justify="left",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.err.grid(row=r, column=0, columnspan=2, padx=20, pady=(0,4), sticky="ew"); r += 1

        # Botones
        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=2, padx=20, pady=(8,18), sticky="e"); r += 1

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=40, corner_radius=14,
                                 fg_color=fg_red, hover_color=fg_yellow,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Ingresar", lambda: self._ok(on_success)).grid(row=0, column=1, padx=6)

        # Atajos / foco
        self.bind("<Return>", lambda e: self._ok(on_success))
        self.en_user.focus_set()

    # ---- Métodos propios del diálogo ----
    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self.en_pass.configure(show="" if self._pass_visible else "*")

    def _show_error(self, msg: str):
        try:
            self.err.configure(text=msg or "")
        except Exception:
            messagebox.showerror("Login", msg, parent=self)

    def _ok(self, cb):
        u = self.en_user.get().strip()
        p = self.en_pass.get().strip()
        if not u or not p:
            self._show_error("Usuario y contraseña son obligatorios.")
            return
        try:
            # Si quieres, aquí podrías persistir "remember me"
            cb(u, p)
            self.grab_release()
            self.destroy()
        except Exception as e:
            self._show_error(f"Error de autenticación:\n{e}")

    def _cancel(self):
        self.grab_release()
        self.destroy()


# ================================
#  Formulario inline (Estudiantes)
# ================================
class StudentInlineForm(ctk.CTkFrame):
    """
    Formulario en línea (colapsable) para crear/editar estudiante.
    Devuelve SIEMPRE campos en camelCase como los pide la API.
    - on_submit(data: dict, mode: "create" | "edit")
    - on_cancel()
    """
    def __init__(self, master, app, on_submit, on_cancel):
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        # Fila 0: Documento
        ctk.CTkLabel(self, text="Tipo Documento").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.cb_tipo = ctk.CTkComboBox(self, values=["CC","TI","CE","PA"], width=120)
        self.cb_tipo.set("CC")
        self.cb_tipo.grid(row=0, column=1, padx=12, pady=(12,6), sticky="w")

        ctk.CTkLabel(self, text="Número Documento").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_doc = BorderedEntry(self, placeholder_text="1012345678")
        self.en_doc.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Nombre / Apellido
        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nombre = BorderedEntry(self, placeholder_text="Nombre")
        self.en_nombre.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_apellido = BorderedEntry(self, placeholder_text="Apellido")
        self.en_apellido.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # Fila 2: Contacto
        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # Fila 3: Dirección / Estado
        ctk.CTkLabel(self, text="Dirección").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.en_dir = BorderedEntry(self, placeholder_text="Dirección")
        self.en_dir.grid(row=3, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Estado").grid(row=3, column=2, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Inactivo","Suspendido"], width=140)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=3, column=3, padx=12, pady=6, sticky="w")

        # Fila 4: Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # API pública
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self): self.grid_remove()

    # Internos
    def _fill(self, d):
        for w in (self.en_doc, self.en_nombre, self.en_apellido, self.en_tel, self.en_mail, self.en_dir):
            w.delete(0, "end")
        self.cb_tipo.set(d.get("tipoDocumento", "CC"))
        self.en_doc.insert(0, d.get("numeroDocumento", ""))
        self.en_nombre.insert(0, d.get("nombre", ""))
        self.en_apellido.insert(0, d.get("apellido", ""))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))
        self.en_dir.insert(0, d.get("direccion", ""))
        self.cb_estado.set(d.get("estado", "Activo"))

    def _collect(self):
        # Devuelve CAMELCASE, exactamente como tu API
        return {
            "tipoDocumento": self.cb_tipo.get().strip(),
            "numeroDocumento": self.en_doc.get().strip(),
            "nombre": self.en_nombre.get().strip(),
            "apellido": self.en_apellido.get().strip(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
            "direccion": self.en_dir.get().strip(),
            "estado": self.cb_estado.get().strip(),
            # si algún día quieres usarlos desde UI, agrega inputs;
            # por ahora deben ir null según tu solicitud:
            "usuario": None,
            "contrasena": None,
        }

    def _validate(self, d):
        req = ["tipoDocumento","numeroDocumento","nombre","apellido","telefono","email","estado"]
        for k in req:
            if not d.get(k):
                return False, "El campo '{}' es obligatorio.".format(k)
        if not d["numeroDocumento"].isdigit():
            return False, "El Número de Documento debe ser numérico."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El Teléfono debe ser numérico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no válido."
        return True, ""

    def _save(self):
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()

class InstructorInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar instructor.
    Usa las claves EXACTAS del JSON del backend:
    { "id", "cedula", "nombre", "apellido", "especialidad", "telefono", "email" }
    """
    def __init__(self, master, app, on_submit, on_cancel):
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        # Fila 0: Cédula
        ctk.CTkLabel(self, text="Cédula").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.en_ced = BorderedEntry(self, placeholder_text="1012345678")
        self.en_ced.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        # Fila 0b: Especialidad
        ctk.CTkLabel(self, text="Especialidad").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_esp = BorderedEntry(self, placeholder_text="Categoría B1 / Teoría / etc.")
        self.en_esp.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Nombre / Apellido
        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nom = BorderedEntry(self, placeholder_text="Nombre")
        self.en_nom.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_ape = BorderedEntry(self, placeholder_text="Apellido")
        self.en_ape.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # Fila 2: Teléfono / Email
        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # Fila 3: Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # API pública
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self):
        self.grid_remove()

    # Internos
    def _fill(self, d):
        for w in (self.en_ced, self.en_nom, self.en_ape, self.en_esp, self.en_tel, self.en_mail):
            w.delete(0, "end")
        self.en_ced.insert(0, d.get("cedula", ""))
        self.en_nom.insert(0, d.get("nombre", ""))
        self.en_ape.insert(0, d.get("apellido", ""))
        self.en_esp.insert(0, d.get("especialidad", ""))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))

    def _collect(self):
        # EXACTAMENTE las claves del backend
        return {
            "cedula": self.en_ced.get().strip(),
            "nombre": self.en_nom.get().strip(),
            "apellido": self.en_ape.get().strip(),
            "especialidad": self.en_esp.get().strip(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
        }

    def _validate(self, d):
        req = ["cedula","nombre","apellido","telefono","email"]
        for k in req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."
        if not d["cedula"].isdigit():
            return False, "La Cédula debe ser numérica."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El Teléfono debe ser numérico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no válido."
        return True, ""

    def _save(self):
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()

class VehiculoInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar vehículo.
    Claves EXACTAS del backend:
    { "placa", "marca", "modelo", "anio", "estado" }
    """
    def __init__(self, master, app, on_submit, on_cancel):
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        # Fila 0: Placa / Marca
        ctk.CTkLabel(self, text="Placa").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.en_placa = BorderedEntry(self, placeholder_text="ABC123")
        self.en_placa.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        ctk.CTkLabel(self, text="Marca").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_marca = BorderedEntry(self, placeholder_text="Chevrolet / Renault / etc.")
        self.en_marca.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Modelo / Año
        ctk.CTkLabel(self, text="Modelo").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_modelo = BorderedEntry(self, placeholder_text="Spark / Logan / etc.")
        self.en_modelo.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Año").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_anio = BorderedEntry(self, placeholder_text="2021")
        self.en_anio.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # Fila 2: Estado
        ctk.CTkLabel(self, text="Estado").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Mantenimiento","Baja"], width=180)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=2, column=1, padx=12, pady=6, sticky="w")

        # Fila 3: Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # API pública
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self): self.grid_remove()

    # Internos
    def _fill(self, d):
        for w in (self.en_placa, self.en_marca, self.en_modelo, self.en_anio):
            w.delete(0, "end")
        self.en_placa.insert(0, d.get("placa", ""))
        self.en_marca.insert(0, d.get("marca", ""))
        self.en_modelo.insert(0, d.get("modelo", ""))
        self.en_anio.insert(0, str(d.get("anio","") or ""))
        self.cb_estado.set(d.get("estado","Activo") or "Activo")

    def _collect(self):
        # EXACTAMENTE las claves del backend
        anio_raw = (self.en_anio.get() or "").strip()
        return {
            "placa": (self.en_placa.get() or "").strip(),
            "marca": (self.en_marca.get() or "").strip(),
            "modelo": (self.en_modelo.get() or "").strip(),
            "anio": int(anio_raw) if anio_raw.isdigit() else anio_raw,
            "estado": (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        req = ["placa","marca","modelo","anio","estado"]
        for k in req:
            if d.get(k) in ("", None):
                return False, f"El campo '{k}' es obligatorio."
        if not isinstance(d["anio"], int):
            return False, "El campo 'anio' debe ser un número entero."
        if not (1970 <= d["anio"] <= 2100):
            return False, "El campo 'anio' debe estar entre 1970 y 2100."
        return True, ""

    def _save(self):
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()


class ClaseInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar clases.
    UI muestra nombres; payload EXACTO para backend:
    { id_estudiante, id_profesor, placa_vehiculo, fecha, horaInicio, horaFin, estado }
    """
    def __init__(self, master, app, on_submit, on_cancel):
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        # catálogos
        self._est_opts = []   # [(id, "Nombre Apellido")]
        self._prof_opts = []  # [(id, "Nombre Apellido")] (API: profesores)
        self._veh_opts  = []  # [("ABC123","ABC123")]

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def L(t): return ctk.CTkLabel(self, text=t, text_color=self.app.COLOR_TEXT)
        def E(ph=""): 
            return ctk.CTkEntry(self, height=36, corner_radius=10,
                                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                                border_width=2, border_color=self.app.COLOR_DIVIDER,
                                placeholder_text=ph)

        # Fila 0: Estudiante / Profesor
        L("Estudiante").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.cb_est = ctk.CTkComboBox(self, values=[], width=280)
        self.cb_est.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        L("Instructor").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.cb_prof = ctk.CTkComboBox(self, values=[], width=280)
        self.cb_prof.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Vehículo / Fecha
        L("Vehículo (placa)").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.cb_veh = ctk.CTkComboBox(self, values=[], width=180)
        self.cb_veh.grid(row=1, column=1, padx=12, pady=6, sticky="w")

        L("Fecha (YYYY-MM-DD)").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_fecha = E("2025-10-01")
        self.en_fecha.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # Fila 2: Horas / Estado
        L("Hora inicio (HH:mm)").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_hi = E("08:00")
        self.en_hi.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        L("Hora fin (HH:mm)").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_hf = E("10:00")
        self.en_hf.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        L("Estado").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Programada","Dictada","Cancelada"], width=180)
        self.cb_estado.set("Programada")
        self.cb_estado.grid(row=3, column=1, padx=12, pady=6, sticky="w")

        # Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")
        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)
        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # Cargar catálogos desde la vista
    def set_options(self, estudiantes, profesores, vehiculos):
        # estudiantes: list[{"id"/"idEstudiante","nombre","apellido"}]
        self._est_opts = []
        for e in estudiantes or []:
            _id = e.get("id") or e.get("idEstudiante")
            if _id is not None:
                self._est_opts.append((str(_id), f"{e.get('nombre','')} {e.get('apellido','')}".strip()))
        # profesores: list[{"id","nombre","apellido"}]
        self._prof_opts = []
        for p in profesores or []:
            _id = p.get("id") or p.get("idProfesor")
            if _id is not None:
                self._prof_opts.append((str(_id), f"{p.get('nombre','')} {p.get('apellido','')}".strip()))
        # vehículos: list[{"placa",...}]
        self._veh_opts = []
        for v in vehiculos or []:
            placa = v.get("placa")
            if placa:
                self._veh_opts.append((placa, placa))

        # Poblar combos (solo los textos visibles)
        self.cb_est.configure(values=[txt for _, txt in self._est_opts])
        self.cb_prof.configure(values=[txt for _, txt in self._prof_opts])
        self.cb_veh.configure(values=[txt for _, txt in self._veh_opts])

    # Público
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, d):
        self.mode = "edit"
        self._fill(d or {})
        self.grid()

    def hide(self): self.grid_remove()

    # Internos
    def _fill(self, d):
        # reset
        for w in (self.en_fecha, self.en_hi, self.en_hf):
            w.delete(0, "end")
        self.cb_estado.set(d.get("estado","Programada") or "Programada")

        # seleccionar combos por valor
        def _sel(cb, opts, key, is_id=True):
            val = d.get(key)
            if val is None: 
                return
            wanted = str(val) if is_id else val
            texts = [txt for v, txt in opts if str(v) == wanted]
            if texts: cb.set(texts[0])

        _sel(self.cb_est,  self._est_opts, "id_estudiante", True)
        _sel(self.cb_prof, self._prof_opts, "id_profesor",   True)
        _sel(self.cb_veh,  self._veh_opts,  "placa_vehiculo", False)

        self.en_fecha.insert(0, d.get("fecha","") or "")
        self.en_hi.insert(0,   d.get("horaInicio","") or "")
        self.en_hf.insert(0,   d.get("horaFin","") or "")

    def _collect(self):
        # mapear selección → ids/placa
        def _val(cb, opts):
            txt = cb.get()
            for v, t in opts:
                if t == txt:
                    return v
            return None

        return {
            "id_estudiante":  int(_val(self.cb_est,  self._est_opts)) if _val(self.cb_est,  self._est_opts) else None,
            "id_profesor":    int(_val(self.cb_prof, self._prof_opts)) if _val(self.cb_prof, self._prof_opts) else None,
            "placa_vehiculo": _val(self.cb_veh, self._veh_opts),
            "fecha":          (self.en_fecha.get() or "").strip(),
            "horaInicio":     (self.en_hi.get() or "").strip(),
            "horaFin":        (self.en_hf.get() or "").strip(),
            "estado":         (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        req = ["id_estudiante","id_profesor","placa_vehiculo","fecha","horaInicio","horaFin","estado"]
        for k in req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."

        # validaciones simples
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["fecha"]):
            return False, "La fecha debe tener formato YYYY-MM-DD."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaInicio"]):
            return False, "Hora inicio debe ser HH:mm."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaFin"]):
            return False, "Hora fin debe ser HH:mm."

        # horaFin > horaInicio
        hi = d["horaInicio"]; hf = d["horaFin"]
        try:
            h1 = int(hi[:2]) * 60 + int(hi[3:])
            h2 = int(hf[:2]) * 60 + int(hf[3:])
            if h2 <= h1:
                return False, "La hora de fin debe ser mayor que la hora de inicio."
        except:
            return False, "Horas inválidas."

        return True, ""

    def _save(self):
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()

# ===================================
#  Base para módulos (botones en rojo)
# ===================================
class BaseModuleFrame(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = ""):
        app = self._find_app(master)
        self.app = app
        super().__init__(master, fg_color=getattr(app, "COLOR_BG", ("#FFFFFF", "#0f0f10")))
        # filas: 0 header / 1 toolbar / 2 form / 3 filtros / 4 tabla
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = self._make_header_bar(title, subtitle)
        header.grid(row=0, column=0, padx=16, pady=(16, 10), sticky="ew")

    def _find_app(self, widget):
        w = widget
        while w is not None:
            if hasattr(w, "APP_TITLE") and hasattr(w, "COLOR_BG"):
                return w
            w = getattr(w, "master", None)
        return widget

    def _make_header_bar(self, title: str, subtitle: str = ""):
        bar = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=16)
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text=title,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=self.app.COLOR_TEXT, anchor="w").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        if subtitle:
            ctk.CTkLabel(bar, text=subtitle, font=ctk.CTkFont(size=12),
                         text_color=self.app.COLOR_MUTED, anchor="w").grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        return bar

    def _make_toolbar(self, master, on_new, on_edit, on_delete, on_refresh):
        tb = ctk.CTkFrame(master, fg_color="transparent")
        tb.grid_columnconfigure((0,1,2,3), weight=0)
        tb.grid_columnconfigure(4, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn("＋ Nuevo", on_new).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn("✎ Editar", on_edit).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn("🗑 Eliminar", on_delete).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn("↻ Refrescar", on_refresh).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        
        return tb

    # --- versión simple
    def _make_filters(self, master, p1="Buscar…", p2="Filtro"):
        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid_columnconfigure((0,1,2,3), weight=0)
        bar.grid_columnconfigure(4, weight=1)

        e1 = ctk.CTkEntry(
            bar, placeholder_text=p1, height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT, border_width=0
        )
        e1.grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")

        e2 = ctk.CTkEntry(
            bar, placeholder_text=p2, height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT, border_width=0
        )
        e2.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        def red_small(text, cmd):
            return ctk.CTkButton(
                bar, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_small("Aplicar", lambda: self.app._info(f"Aplicar filtros: {e1.get()} / {e2.get()}"))\
            .grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_small("Limpiar", lambda: (e1.delete(0, "end"), e2.delete(0, "end")))\
            .grid(row=0, column=3, padx=8, pady=6, sticky="w")

        return bar

    # --- versión mejorada
    def _make_filters_pro(self, master, campos=("Documento","Nombre","Apellidos"),
                          estados=("Todos","Activo","Inactivo","Suspendido")):
        panel = ctk.CTkFrame(
            master,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER
        )
        for c in range(8):
            panel.grid_columnconfigure(c, weight=0)
        panel.grid_columnconfigure(7, weight=1)

        ctk.CTkLabel(
            panel, text="Filtros", text_color=self.app.COLOR_MUTED,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")

        r = 1
        ctk.CTkLabel(panel, text="Buscar por").grid(row=r, column=0, padx=(12,8), pady=8, sticky="w")
        cb_campo = ctk.CTkComboBox(panel, values=list(campos), width=140)
        cb_campo.set(campos[0])
        cb_campo.grid(row=r, column=1, padx=(0,12), pady=8, sticky="w")

        ctk.CTkLabel(panel, text="Valor").grid(row=r, column=2, padx=(12,8), pady=8, sticky="w")
        wrap = ctk.CTkFrame(panel, fg_color="transparent")
        wrap.grid(row=r, column=3, padx=(0,12), pady=8, sticky="ew")
        wrap.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(wrap, text="🔎", width=24, text_color=self.app.COLOR_MUTED)\
            .grid(row=0, column=0, padx=(0,6), pady=0, sticky="w")
        en_valor = ctk.CTkEntry(
            wrap, height=36, corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
            border_width=2, border_color=self.app.COLOR_DIVIDER,
            placeholder_text="Escribe aquí…"
        )
        en_valor.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(panel, text="Estado").grid(row=r, column=4, padx=(12,8), pady=8, sticky="w")
        cb_estado = ctk.CTkComboBox(panel, values=list(estados), width=150)
        cb_estado.set(estados[0])
        cb_estado.grid(row=r, column=5, padx=(0,12), pady=8, sticky="w")

        def red_btn(text, cmd):
            return ctk.CTkButton(
                panel, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_btn("Aplicar", lambda: self.app._info(
            f"Filtrar: {cb_campo.get()} ~ '{en_valor.get()}' / Estado={cb_estado.get()}"
        )).grid(row=r, column=6, padx=(0,8), pady=8, sticky="w")

        red_btn("Limpiar", lambda: (cb_campo.set(campos[0]), en_valor.delete(0, "end"), cb_estado.set(estados[0])))\
            .grid(row=r, column=7, padx=(0,12), pady=8, sticky="e")

        return panel


class EstudiantesView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Estudiantes", "Gestione matrículas y datos del alumno")

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0,1,2), weight=0)
        tb.grid_columnconfigure(3, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(parent, text=text, height=40, corner_radius=18,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd, anchor="w")
        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn(tb, "✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8, pady=6, sticky="w")

        # Form inline (ya devuelve CAMELCASE)
        self.form = StudentInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # Filtros
        filters = self._make_filters_pro(self, campos=("Documento","Nombre","Apellidos"),
                                         estados=("Todos","Activo","Inactivo","Suspendido"))
        filters.grid(row=3, column=0, padx=16, pady=(0,10), sticky="ew")

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Documento",   160,  0),
            ("Nombre",      320,  1),
            ("Estado",      140,  0),
            ("Email",       220,  0),
            ("Acciones",    120,  0),
        ]

        # Los datos se mantienen en CAMELCASE (igual que la API)
        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # -------- helpers de tabla --------
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, stu in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            full_name = "{} {}".format(stu.get("nombre",""), stu.get("apellido","")).strip()
            values = [
                stu.get("numeroDocumento",""),
                full_name,
                stu.get("estado",""),
                stu.get("email",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=4, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=10,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    # -------- acciones UI --------
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un estudiante en la tabla primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])  # el form espera camelCase

    def _cancel_inline(self):
        pass

    # -------- API: listar / crear / actualizar / eliminar --------
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            raw = self.app.api.get_all("estudiantes") or []
            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []
            self._data = raw or []
            self._render_table()
            
        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible consultar la API:\n{}".format(e), parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            payload = dict(payload)

            # --- FIX RÁPIDO: si son None, genera valores no nulos ---
            doc = (payload.get("numeroDocumento") or "").strip()
            if not doc:
                messagebox.showerror("Validación", "El Número de Documento es obligatorio.", parent=self)
                return

            if payload.get("usuario") in (None, ""):
                payload["usuario"] = doc  # p.ej. "1128962248"
            if payload.get("contrasena") in (None, ""):
                payload["contrasena"] = doc  # temporal (o "Temp"+doc[-4:])

            if mode == "create":
                self.app.api.create("estudiantes", payload)
                self.app._info("Estudiante creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un estudiante para actualizar.")
                    return
                original_doc = self._data[idx].get("numeroDocumento", "")
                if not original_doc:
                    self.app._info("No se pudo determinar el número de documento original.")
                    return
                # 🔧 CAMBIO AQUÍ: usa la ruta con /documento/
                student_id = self._data[idx].get("id") or self._data[idx].get("idEstudiante")
                if not student_id:
                    self.app._info("No se encontró el ID del estudiante.")
                    return
                self.app.api.update("estudiantes", student_id, payload)
                self.app._info("Estudiante actualizado.")
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Estudiantes", f"Operación fallida:\n{e}", parent=self)


    def _delete_row(self, idx):
        self._select_row(idx)
        stu = self._data[idx]
        full_name = "{} {}".format(stu.get("nombre",""), stu.get("apellido","")).strip()
        doc = stu.get("numeroDocumento", "")
        if not doc:
            self.app._info("El registro no tiene 'numeroDocumento'.")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar al estudiante:\n{} (Doc: {})".format(full_name, doc)):
            self.app._info("Operación cancelada.")
            return

        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            # 🔧 CAMBIO AQUÍ: usa la ruta con /documento/
            student_id = stu.get("id") or stu.get("idEstudiante")
            if not student_id:
                self.app._info("No se encontró el ID del estudiante.")
                return
            self.app.api.delete("estudiantes", student_id)

            self.app._info("Estudiante eliminado.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible eliminar:\n{}".format(e), parent=self)

class InstructoresView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Instructores", "Gestione los datos del instructor")

        # Toolbar completa
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        for c in (0,1,2,3,4): tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(parent, text=text, height=40, corner_radius=18,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd, anchor="w")
        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn(tb, "✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn(tb, "👁 Ver", self._ver).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn(tb, "🗑 Eliminar", self._eliminar).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=4, padx=8, pady=6, sticky="w")

        # Formulario inline (mismo patrón que Estudiantes)
        self.form = InstructorInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Cédula",       140, 0),
            ("Nombre",       300, 1),
            ("Especialidad", 200, 0),
            ("Teléfono",     160, 0),
            ("Email",        240, 0),
            ("Acciones",     120, 0),
        ]

        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # -------- helpers de tabla --------
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, inst in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            full_name = "{} {}".format(inst.get("nombre",""), inst.get("apellido","")).strip()
            values = [
                inst.get("cedula",""),
                full_name,
                inst.get("especialidad",""),
                inst.get("telefono",""),
                inst.get("email",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=10,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    # -------- acciones UI --------
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un instructor en la tabla primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _ver(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un instructor para ver.")
            return
        inst = self._data[self._selected_idx]
        info = (
            f"Cédula: {inst.get('cedula','')}\n"
            f"Nombre: {inst.get('nombre','')} {inst.get('apellido','')}\n"
            f"Especialidad: {inst.get('especialidad','')}\n"
            f"Teléfono: {inst.get('telefono','')}\n"
            f"Email: {inst.get('email','')}"
        )
        messagebox.showinfo("Detalle del Instructor", info, parent=self)

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un instructor para eliminar.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        pass

    # -------- API: listar / crear / actualizar / eliminar --------
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            raw = self.app.api.get_all("profesores") or []
            if isinstance(raw, dict):
                for key in ("content","items","profesores","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []
            self._data = raw or []
            self._render_table()
            
        except Exception as e:
            messagebox.showerror("Instructores", "No fue posible consultar la API:\n{}".format(e), parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            payload = dict(payload)  # {"cedula","nombre","apellido","especialidad","telefono","email"}

            if mode == "create":
                # POST /instructores
                self.app.api.create("profesores", payload)
                self.app._info("Instructor creado.")
                print(payload)
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un instructor para actualizar.")
                    return
                _id = self._data[idx].get("id")
                if not _id:
                    self.app._info("No se encontró el ID del instructor.")
                    return
                # PUT /instructores/{id}
                self.app.api.update("profesores", _id, payload)
                self.app._info("Instructor actualizado.")
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Instructores", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        inst = self._data[idx]
        full_name = "{} {}".format(inst.get("nombre",""), inst.get("apellido","")).strip()
        ced = inst.get("cedula", "")
        if not messagebox.askyesno("Confirmar", f"¿Eliminar al instructor:\n{full_name} (Cédula: {ced})"):
            self.app._info("Operación cancelada.")
            return

        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            _id = inst.get("id")
            if not _id:
                self.app._info("No se encontró el ID del instructor.")
                return
            # DELETE /instructores/{id}
            self.app.api.delete("profesores", _id)
            self.app._info("Instructor eliminado.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Instructores", "No fue posible eliminar:\n{}".format(e), parent=self)

class VehiculosView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Vehículos", "Documentación, mantenimiento y disponibilidad")

        # Toolbar (sin acciones en la tabla; todo por botones)
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        for c in (0,1,2,3): tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(4, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(parent, text=text, height=40, corner_radius=18,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd, anchor="w")
        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn(tb, "✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn(tb, "🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8, pady=6, sticky="w")

        # Formulario inline
        self.form = VehiculoInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # Tabla (SIN columna "Acciones")
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Placa", 120, 0),
            ("Marca", 160, 0),
            ("Modelo", 160, 0),
            ("Año",   100, 0),
            ("Estado",140, 1),
            ("Acciones",120, 0),
        ]

        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # Helpers de tabla
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, v in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            values = [
                v.get("placa",""),
                v.get("marca",""),
                v.get("modelo",""),
                str(v.get("anio","")),
                v.get("estado",""),
            ]
            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)
        
                    # Columna de acciones (col = 5)
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(
                    actions, text=symbol, width=36, height=32, corner_radius=10,
                    fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                    text_color="#ffffff", command=cmd
                )

            icon_btn("✎",  lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)


    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    # Acciones UI
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo en la tabla primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo para eliminar.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        pass

    # API: listar / crear / actualizar / eliminar
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            data = self.app.api.get_all("vehiculos") or []
            if isinstance(data, dict):
                for key in ("content","items","vehiculos","data","results"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    data = []
            self._data = data
            self._render_table()
         
        except Exception as e:
            messagebox.showerror("Vehículos", f"No fue posible consultar la API:\n{e}", parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            payload = dict(payload)  # {"placa","marca","modelo","anio","estado"}

            if mode == "create":
                # POST /vehiculos  (SIN id en el body)
                self.app.api.create("vehiculos", payload)
                self.app._info("Vehículo creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un vehículo para actualizar.")
                    return
                _id = self._data[idx].get("id") or self._data[idx].get("idVehiculo")
                if not _id:
                    self.app._info("No se encontró el ID del vehículo.")
                    return
                # PUT /vehiculos/{id}
                self.app.api.update("vehiculos", _id, payload)
                self.app._info("Vehículo actualizado.")
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Vehículos", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        v = self._data[idx]
        placa = v.get("placa","")
        if not messagebox.askyesno("Confirmar", f"¿Eliminar el vehículo con placa: {placa}"):
            self.app._info("Operación cancelada.")
            return

        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            placa = v.get("placa")
            if not placa:
                self.app._info("No se encontró la placa del vehículo.")
                return
            # DELETE /vehiculos/{placa}
            self.app.api.delete("vehiculos", placa)

            self.app._info("Vehículo eliminado.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Vehículos", f"No fue posible eliminar:\n{e}", parent=self)


# ------------------ imports necesarios (pegarlos al inicio del módulo) ------------------
import re
import json
import datetime
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

# Import seguro de tkcalendar (si no está instalado, queda en None)
try:
    from tkcalendar import Calendar, DateEntry
except Exception:
    Calendar = None
    DateEntry = None

# Asegúrate de tener, al inicio del archivo:
# import calendar
# import datetime
# import tkinter as tk

class ClasesView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Clases", "Agendamiento y control de asistencia")

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        for c in (0,1,2,3,4): tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )
        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn("✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn("🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        red_btn("📆 Calendario", self._toggle_calendar).grid(row=0, column=4, padx=8, pady=6, sticky="w")


        # Formulario (encima de la tabla)
        self._build_form()
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self._hide_form()

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Estudiante",    260, 1),
            ("Instructor",    260, 1),
            ("Placa",         120, 0),
            ("Fecha",         130, 0),
            ("Hora inicio",   120, 0),
            ("Hora fin",      120, 0),
            ("Estado",        150, 0),
            ("Acciones",      120, 0),
        ]

        # Data/mapeos
        self._data = []          # lista de clases crudas
        self._rows = []
        self._selected_idx = None

        # catálogos
        self.estudiantes = []    # lista estudiantes
        self.profesores = []     # lista profesores (API) = instructores (UI)

        # mapas id <-> nombre completo
        self.estudiantes_id_to_name = {}
        self.estudiantes_name_to_id = {}
        self.profesores_id_to_name = {}
        self.profesores_name_to_id = {}

        self._render_table()

        # Inicializa widgets del calendario (robusto)
        # Nota: este init crea cal_frame que se posiciona cuando se togglea
        self._init_calendar_widgets()

        # Carga catálogos luego (pequeño delay para evitar bloqueos en constructor)
        self.after(150, self._cargar_catalogos_y_listar)


    # ============ Formulario ============

    def _build_form(self):
        self.form = ctk.CTkFrame(
            self, fg_color=self.app.COLOR_PANEL,
            corner_radius=16, border_width=2, border_color=self.app.COLOR_DIVIDER
        )
        for c in range(8):
            self.form.grid_columnconfigure(c, weight=1)

        def label(r, c, text):
            ctk.CTkLabel(self.form, text=text, text_color=self.app.COLOR_TEXT)\
                .grid(row=r, column=c, padx=12, pady=(12,6), sticky="w")

        def entry(ph=""):
            return ctk.CTkEntry(
                self.form, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                placeholder_text=ph
            )

        # Fila 0: Estudiante / Instructor
        label(0, 0, "Estudiante")
        self.cb_estudiante = ctk.CTkComboBox(self.form, values=[], width=280)
        self.cb_estudiante.grid(row=1, column=0, padx=12, pady=(0,8), sticky="w")

        label(0, 1, "Instructor")
        self.cb_profesor = ctk.CTkComboBox(self.form, values=[], width=280)
        self.cb_profesor.grid(row=1, column=1, padx=12, pady=(0,8), sticky="w")

        # Fila 1: Placa / Fecha
        label(2, 0, "Placa vehículo")
        self.cb_placa = ctk.CTkComboBox(self.form, values=[], width=180)
        self.cb_placa.grid(row=3, column=0, padx=12, pady=(0,8), sticky="w")


        label(2, 1, "Fecha (YYYY-MM-DD)")
        self.en_fecha = entry("2025-10-01")
        self.en_fecha.grid(row=3, column=1, padx=12, pady=(0,8), sticky="ew")

        # Fila 2: Horas / Estado
        label(4, 0, "Hora inicio (HH:mm)")
        self.en_hora_ini = entry("07:00")
        self.en_hora_ini.grid(row=5, column=0, padx=12, pady=(0,8), sticky="ew")

        label(4, 1, "Hora fin (HH:mm)")
        self.en_hora_fin = entry("09:00")
        self.en_hora_fin.grid(row=5, column=1, padx=12, pady=(0,8), sticky="ew")

        label(4, 2, "Estado")
        self.cb_estado = ctk.CTkComboBox(self.form, values=["Programada","Dictada","Cancelada"], width=180)
        self.cb_estado.set("Programada")
        self.cb_estado.grid(row=5, column=2, padx=12, pady=(0,8), sticky="w")

        # Botones
        btns = ctk.CTkFrame(self.form, fg_color="transparent")
        btns.grid(row=6, column=0, columnspan=8, padx=12, pady=(4,12), sticky="e")

        def red_btn(text, cb):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cb
            )
        red_btn("Cancelar", self._cancelar).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._guardar).grid(row=0, column=1, padx=6)

        self._form_mode = "create"
        self._editing_idx = None

    def _show_form(self, mode="create", data=None):
        self._form_mode = mode
        if mode == "edit" and data:
            self._fill_form(data)
        elif mode == "create":
            self._fill_form({})
        self.form.grid()

    def _hide_form(self):
        self.form.grid_remove()

    def _fill_form(self, d: dict):
        # Selección estudiante
        est_id = d.get("id_estudiante")
        est_name = self.estudiantes_id_to_name.get(est_id, "")
        self.cb_estudiante.set(est_name if est_name else (self.cb_estudiante.cget("values")[0] if self.cb_estudiante.cget("values") else ""))

        # Selección instructor (acepta id_profesor o id_instructor)
        pro_id = d.get("id_profesor") or d.get("id_instructor")
        pro_name = self.profesores_id_to_name.get(pro_id, "")
        self.cb_profesor.set(pro_name if pro_name else (self.cb_profesor.cget("values")[0] if self.cb_profesor.cget("values") else ""))

        # Entrys
        def set_entry(widget, value):
            widget.delete(0, "end")
            widget.insert(0, value or "")

        placa_val = d.get("placa_vehiculo", "")
        self.cb_placa.set(placa_val if placa_val else (self.cb_placa.cget("values")[0] if self.cb_placa.cget("values") else ""))

        set_entry(self.en_fecha, d.get("fecha", ""))
        set_entry(self.en_hora_ini, d.get("horaInicio", ""))
        set_entry(self.en_hora_fin, d.get("horaFin", ""))
        self.cb_estado.set(d.get("estado", "Programada") or "Programada")

    def _collect_form(self) -> dict:
        def norm_time(s: str) -> str:
            s = (s or "").strip()
            if not s:
                return s
            parts = s.split(":")
            if len(parts) >= 2:
                h = parts[0].zfill(2)
                m = parts[1].zfill(2)
                return f"{h}:{m}"
            return s

        nombre_est = self.cb_estudiante.get().strip()
        nombre_prof = self.cb_profesor.get().strip()

        id_est = self.estudiantes_name_to_id.get(nombre_est)
        id_prof = self.profesores_name_to_id.get(nombre_prof)

        payload = {
            "id_estudiante":  id_est,
            "id_profesor":    id_prof,            # enviamos SOLO id_profesor
            "placa_vehiculo": self.cb_placa.get().strip(),
            "fecha":          self.en_fecha.get().strip(),
            "horaInicio":     norm_time(self.en_hora_ini.get()),
            "horaFin":        norm_time(self.en_hora_fin.get()),
            "estado":         self.cb_estado.get().strip(),
        }
        return payload


    def _validate(self, d: dict):
        base_req = ["id_estudiante", "fecha", "horaInicio", "horaFin", "estado"]
        for k in base_req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."

        # comprobar que haya instructor seleccionado mediante id_profesor
        if not d.get("id_profesor"):
            return False, "Debe seleccionar un instructor."

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["fecha"]):
            return False, "La fecha debe tener formato YYYY-MM-DD (ej. 2025-10-01)."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaInicio"]):
            return False, "Hora inicio inválida. Usa HH:mm (ej. 07:00)."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaFin"]):
            return False, "Hora fin inválida. Usa HH:mm (ej. 09:00)."
        return True, ""


    # ============ Acciones UI ============

    def _nuevo(self):
        self._editing_idx = None
        self._show_form("create", {})

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona una clase en la tabla primero.")
            return
        self._editing_idx = self._selected_idx
        self._show_form("edit", self._data[self._editing_idx])

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona una clase para eliminar.")
            return
        self._delete_row(self._selected_idx)

    def _cancelar(self):
        self._hide_form()

    def _guardar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            payload = self._collect_form()
            ok, msg = self._validate(payload)
            if not ok:
                messagebox.showerror("Validación", msg, parent=self)
                return

            # ----- DEBUG: mostrar payload en consola (JSON pretty) -----
            print("DEBUG: payload a enviar a la API:")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            # ------------------------------------------------------------

            if self._form_mode == "create":
                self.app.api.create("clases", payload)
                self.app._info("Clase creada.")
            else:
                if self._editing_idx is None:
                    self.app._info("No se seleccionó clase para actualizar.")
                    return
                _id = self._data[self._editing_idx].get("id")
                if not _id:
                    self.app._info("No se encontró el ID de la clase.")
                    return

                print(f"DEBUG: update id={_id} payload:")
                print(json.dumps(payload, ensure_ascii=False, indent=2))

                self.app.api.update("clases", _id, payload)
                self.app._info("Clase actualizada.")

            self._hide_form()
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Clases", f"Operación fallida:\n{e}", parent=self)


    # ============ Catálogos y lista ============

    def _cargar_catalogos_y_listar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            # Estudiantes
            raw_est = self.app.api.get_all("estudiantes") or []
            if isinstance(raw_est, dict):
                for key in ("content","items","estudiantes","data","results"):
                    if isinstance(raw_est.get(key), list):
                        raw_est = raw_est[key]
                        break
                else:
                    raw_est = []
            self.estudiantes = raw_est

            self.estudiantes_id_to_name = {}
            self.estudiantes_name_to_id = {}
            for e in self.estudiantes:
                eid = e.get("id") or e.get("idEstudiante")
                full = "{} {}".format(e.get("nombre",""), e.get("apellido","")).strip()
                if eid and full:
                    self.estudiantes_id_to_name[eid] = full
                    self.estudiantes_name_to_id[full] = eid

            # Profesores (instructores)
            raw_prof = self.app.api.get_all("profesores") or []
            if isinstance(raw_prof, dict):
                for key in ("content","items","profesores","data","results"):
                    if isinstance(raw_prof.get(key), list):
                        raw_prof = raw_prof[key]
                        break
                else:
                    raw_prof = []
            self.profesores = raw_prof

            self.profesores_id_to_name = {}
            self.profesores_name_to_id = {}
            for p in self.profesores:
                pid = p.get("id")
                full = "{} {}".format(p.get("nombre",""), p.get("apellido","")).strip()
                if pid and full:
                    self.profesores_id_to_name[pid] = full
                    self.profesores_name_to_id[full] = pid

            raw_veh = self.app.api.get_all("vehiculos") or []
            if isinstance(raw_veh, dict):
                for key in ("content","items","vehiculos","data","results"):
                    if isinstance(raw_veh.get(key), list):
                        raw_veh = raw_veh[key]
                        break
                else:
                    raw_veh = []

            veh_disponibles = []
            for v in raw_veh:
                estado = (v.get("estado") or "").strip().lower()
                if estado in ("activo", "disponible"):
                    placa = v.get("placa")
                    if placa:
                        veh_disponibles.append(placa)

            veh_disponibles = sorted(set(veh_disponibles))
            self.cb_placa.configure(values=veh_disponibles)
            if veh_disponibles and not self.cb_placa.get():
                self.cb_placa.set(veh_disponibles[0])

            # Cargar combos con nombres legibles
            self.cb_estudiante.configure(values=sorted(list(self.estudiantes_name_to_id.keys())))
            self.cb_profesor.configure(values=sorted(list(self.profesores_name_to_id.keys())))

            # Lista de clases
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible cargar catálogos:\n{e}", parent=self)

    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            raw = self.app.api.get_all("clases") or []
            if isinstance(raw, dict):
                for key in ("content","items","clases","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []
            self._data = raw or []
            self._render_table()
            self.app._info(f"Clases: {len(self._data)} registros.")
            # Si calendario visible, repoblar marcadores
            try:
                if getattr(self, "_calendar_visible", False):
                    self._render_month()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible consultar la API:\n{e}", parent=self)


    # ============ Tabla ============

    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, c in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            est_name = self.estudiantes_id_to_name.get(c.get("id_estudiante"), str(c.get("id_estudiante") or ""))
            pro_id   = c.get("id_profesor") or c.get("id_instructor")
            pro_name = self.profesores_id_to_name.get(pro_id, str(pro_id or ""))

            values = [
                est_name,
                pro_name,
                c.get("placa_vehiculo",""),
                c.get("fecha",""),
                c.get("horaInicio",""),
                c.get("horaFin",""),
                c.get("estado",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=7, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=10,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    def _edit_row(self, idx):
        self._select_row(idx)
        self._editing_idx = idx
        self._show_form("edit", self._data[idx])

    def _delete_row(self, idx):
        self._select_row(idx)
        d = self._data[idx]
        est_name = self.estudiantes_id_to_name.get(d.get("id_estudiante"), "¿")
        pro_id   = d.get("id_profesor") or d.get("id_instructor")
        pro_name = self.profesores_id_to_name.get(pro_id, "¿")

        if not messagebox.askyesno("Confirmar", f"¿Eliminar la clase\nEstudiante: {est_name}\nInstructor: {pro_name}\nFecha: {d.get('fecha','')}"):
            self.app._info("Operación cancelada.")
            return

        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            _id = d.get("id")
            if not _id:
                self.app._info("No se encontró el ID de la clase.")
                return
            self.app.api.delete("clases", _id)
            self.app._info("Clase eliminada.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible eliminar:\n{e}", parent=self)


    # ----------------- Calendario y utilidades (personalizado, sin tkcalendar) -----------------

    def _init_calendar_widgets(self):
        """Inicializa un calendario simple basado en grid (no requiere tkcalendar)."""
        self._calendar_visible = False
        self._cal_container = None
        self._cal_year = datetime.date.today().year
        self._cal_month = datetime.date.today().month

        # frame que contendrá todo el calendario (usa pack internamente)
        self.cal_frame = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12,
                                    border_width=2, border_color=self.app.COLOR_DIVIDER)

        # header con navegación
        header = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8,4))
        # botones prev / next y label mes-año
        def btn(text, cb):
            return ctk.CTkButton(header, text=text, width=36, height=28, corner_radius=8,
                                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                text_color="#ffffff", command=cb)
        btn("<", lambda: (setattr(self, "_cal_month", self._cal_month-1), self._normalize_month_year(), self._render_month()))\
            .pack(side="left", padx=(0,6))
        btn(">", lambda: (setattr(self, "_cal_month", self._cal_month+1), self._normalize_month_year(), self._render_month()))\
            .pack(side="right", padx=(6,0))

        self.lbl_month = ctk.CTkLabel(header, text="", text_color=self.app.COLOR_TEXT)
        self.lbl_month.pack(side="left", expand=True)

        # frame para días (grid 7 columnas)
        self.cal_grid_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.cal_grid_frame.pack(fill="both", expand=False, padx=8, pady=(0,8))

        # leyenda / info
        self.lbl_cal_info = ctk.CTkLabel(self.cal_frame, text="", text_color=self.app.COLOR_MUTED, anchor="w")
        self.lbl_cal_info.pack(fill="x", padx=8, pady=(0,8))

        # botón para cerrar el calendario
        ctk.CTkButton(self.cal_frame, text="Ocultar calendario", command=self._toggle_calendar,
                    height=32, corner_radius=10, fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                    text_color="#ffffff").pack(padx=8, pady=(0,8), anchor="e")

        # inicial render del mes actual
        self._normalize_month_year()
        self._render_month()


    def _normalize_month_year(self):
        """Normaliza mes/año cuando incrementas/decrementas mes (ej. mes=13 => año+1, mes=0 => año-1)."""
        while self._cal_month > 12:
            self._cal_month -= 12
            self._cal_year += 1
        while self._cal_month < 1:
            self._cal_month += 12
            self._cal_year -= 1


    def _render_month(self):
        """Dibuja la cuadrícula del mes actual y resalta días que tienen clases."""
        # limpiar grid anterior
        for w in self.cal_grid_frame.winfo_children():
            w.destroy()

        # actualizar label mes/año y leyenda
        month_name = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{month_name} {self._cal_year}")

        # encabezados de semana (Lun..Dom) empezando por lunes
        dias_semana = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
        for i, d in enumerate(dias_semana):
            lbl = ctk.CTkLabel(self.cal_grid_frame, text=d, text_color=self.app.COLOR_MUTED)
            lbl.grid(row=0, column=i, padx=6, pady=4)

        # obtener estructura de semanas (lista de semanas; cada semana es lista de ints donde 0 = día vacío)
        cal = calendar.Calendar(firstweekday=0)  # 0 = lunes
        month_weeks = cal.monthdayscalendar(self._cal_year, self._cal_month)

        # preparar set de días con clases (para resaltar)
        dias_con_clases = set()
        for item in (self._data or []):
            f = item.get("fecha")
            if not f:
                continue
            try:
                dt = datetime.datetime.strptime(f, "%Y-%m-%d").date()
                if dt.year == self._cal_year and dt.month == self._cal_month:
                    dias_con_clases.add(dt.day)
            except Exception:
                continue

        # dibujar filas (comenzando en row=1)
        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day == 0:
                    # celda vacía
                    spacer = ctk.CTkLabel(self.cal_grid_frame, text=" ", text_color=self.app.COLOR_MUTED)
                    spacer.grid(row=r, column=ccol, padx=6, pady=6, ipadx=6, ipady=6)
                else:
                    # botón del día
                    is_has = (day in dias_con_clases)
                    fg = self.app.COLOR_TEXT
                    if is_has:
                        b = ctk.CTkButton(self.cal_grid_frame, text=str(day), width=44, height=34, corner_radius=8,
                                        fg_color=self.app.COLOR_YELLOW, hover_color=self.app.COLOR_RED,
                                        text_color=fg,
                                        command=lambda d=day: self._on_day_selected_custom(d))
                    else:
                        b = ctk.CTkButton(self.cal_grid_frame, text=str(day), width=44, height=34, corner_radius=8,
                                        fg_color=self.app.COLOR_PANEL, hover_color=self.app.COLOR_DIVIDER,
                                        text_color=fg,
                                        command=lambda d=day: self._on_day_selected_custom(d))
                    b.grid(row=r, column=ccol, padx=4, pady=4)

        # actualizar info (recuento de fechas con clases en el mes)
        try:
            self.lbl_cal_info.configure(text=f"{len(dias_con_clases)} día(s) con clases en {month_name} {self._cal_year}")
        except Exception:
            pass


    def _on_day_selected_custom(self, day:int):
        """Handler cuando el usuario pulsa un día: abre popup con las clases del día."""
        sel_date = datetime.date(self._cal_year, self._cal_month, day)
        sel_str = sel_date.strftime("%Y-%m-%d")
        filtered = [c for c in (self._data or []) if (c.get("fecha") or "") == sel_str]

        try:
            popup = tk.Toplevel(self)
            popup.title(f"Clases - {sel_str}")
            popup.geometry("520x320")
            popup.transient(self.winfo_toplevel())
            popup.grab_set()

            frame = ctk.CTkFrame(popup, fg_color=self.app.COLOR_PANEL, corner_radius=8)
            frame.pack(fill="both", expand=True, padx=8, pady=8)

            hdr = ctk.CTkLabel(frame, text=f"Clases el {sel_str} — {len(filtered)}", text_color=self.app.COLOR_TEXT, anchor="w")
            hdr.pack(fill="x", padx=8, pady=(4,8))

            if not filtered:
                ctk.CTkLabel(frame, text="No hay clases para esta fecha.", text_color=self.app.COLOR_MUTED).pack(padx=8, pady=8)
            else:
                list_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
                list_frame.pack(fill="both", expand=True, padx=8, pady=4)
                for c in filtered:
                    est_name = self.estudiantes_id_to_name.get(c.get("id_estudiante"), str(c.get("id_estudiante") or ""))
                    pro_id = c.get("id_profesor") or c.get("id_instructor")
                    pro_name = self.profesores_id_to_name.get(pro_id, str(pro_id or ""))
                    txt = f"{est_name} — {pro_name} — {c.get('horaInicio','')} - {c.get('horaFin','')} — {c.get('estado','')}"
                    lbl = ctk.CTkLabel(list_frame, text=txt, text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
                    lbl.pack(fill="x", padx=6, pady=6)

            btns = ctk.CTkFrame(frame, fg_color="transparent")
            btns.pack(fill="x", padx=8, pady=(6,8))
            ctk.CTkButton(btns, text="Cerrar", command=lambda: popup.destroy(), height=32,
                        corner_radius=8, fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                        text_color="#ffffff").pack(side="right", padx=6)

        except Exception:
            pass


    def _toggle_calendar(self):
        """
        Versión más robusta / forzada para mostrar/ocultar el calendario.
        - Reserva minsize en la columna del contenedor para que no colapse a 0.
        - Fuerza ancho de cal_frame y desactiva grid_propagate() temporalmente.
        - Usa lift() y update_idletasks() para forzar repintado.
        - Contiene DEBUG prints.
        """
        try:
            print("DEBUG: _toggle_calendar called; _calendar_visible=", getattr(self, "_calendar_visible", False))
        except Exception:
            pass

        # Asegura que cal_frame existe
        if not getattr(self, "cal_frame", None):
            try:
                self._init_calendar_widgets()
            except Exception as e:
                print("DEBUG: fallo init_calendar:", e)

        # Si ya visible -> ocultar
        if getattr(self, "_calendar_visible", False):
            try:
                if getattr(self, "_cal_container", None):
                    self._cal_container.grid_remove()
                else:
                    self.cal_frame.grid_remove()
                # devolver la tabla al layout principal
                try:
                    self.table.grid_forget()
                    self.table.grid(in_=self, row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
                except Exception:
                    try:
                        self.table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
                    except Exception:
                        pass
            except Exception:
                pass

            self._calendar_visible = False
            try:
                print("DEBUG: calendario ocultado")
            except Exception:
                pass
            return

        # Mostrar: crear contenedor si no existe
        if not getattr(self, "_cal_container", None):
            container = ctk.CTkFrame(self, fg_color="transparent")
            # reservar espacio para la columna del calendario (ajusta minsize según lo necesites)
            MIN_CAL_W = 420
            container.grid_columnconfigure(0, weight=0, minsize=MIN_CAL_W)
            container.grid_columnconfigure(1, weight=1)
            container.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")

            # mover tabla al container en columna 1
            try:
                self.table.grid_forget()
                self.table.grid(in_=container, row=0, column=1, sticky="nsew")
            except Exception:
                try:
                    self.table.grid(in_=container, row=0, column=1, padx=0, pady=0, sticky="nsew")
                except Exception:
                    pass

            # Forzar tamaño del cal_frame antes de gridear
            try:
                # ancho fijo razonable
                try:
                    self.cal_frame.configure(width=MIN_CAL_W)
                except Exception:
                    pass

                # Opcional: para depuración visual, descomenta la siguiente línea
                # self.cal_frame.configure(border_width=2, border_color="red")

                # evitar que el container reduzca el tamaño automáticamente (temporal)
                try:
                    container.grid_propagate(False)
                except Exception:
                    pass
                try:
                    self.cal_frame.grid_propagate(False)
                except Exception:
                    pass

                # forzar cálculo de geometría
                try:
                    self.update_idletasks()
                    self.cal_frame.update_idletasks()
                except Exception:
                    pass

                # gridear cal_frame en la columna 0
                try:
                    self.cal_frame.grid(in_=container, row=0, column=0, padx=(0,12), pady=0, sticky="ns")
                except Exception:
                    try:
                        self.cal_frame.grid(row=0, column=0, padx=(0,12), pady=0, sticky="ns")
                    except Exception:
                        pass
            except Exception as e:
                print("DEBUG: fallo al preparar cal_frame:", e)

            self._cal_container = container
        else:
            # si ya existe contenedor, asegurar minsize y volver a posicionar
            try:
                # reasegurar minsize (por si se perdió)
                try:
                    self._cal_container.grid_columnconfigure(0, weight=0, minsize=420)
                except Exception:
                    pass

                # asegurar que cal_frame está dentro del container
                try:
                    self.cal_frame.grid(in_=self._cal_container, row=0, column=0, padx=(0,12), pady=0, sticky="ns")
                except Exception:
                    try:
                        self.cal_frame.grid(row=0, column=0, padx=(0,12), pady=0, sticky="ns")
                    except Exception:
                        pass

                # asegurar que la tabla está en la columna 1
                try:
                    self.table.grid(in_=self._cal_container, row=0, column=1, sticky="nsew")
                except Exception:
                    try:
                        self.table.grid(in_=self._cal_container, row=0, column=1, padx=0, pady=0, sticky="nsew")
                    except Exception:
                        pass
            except Exception as e:
                print("DEBUG: fallo al mostrar contenedor existente:", e)

        # Marcar visible
        self._calendar_visible = True

        # Forzar repintado y subir al frente
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            # intentar lift para traer al frente
            try:
                self._cal_container.lift()
            except Exception:
                pass
            try:
                self.cal_frame.lift()
            except Exception:
                pass
            try:
                self.table.lift()
            except Exception:
                pass
        except Exception:
            pass

        # Repintar mes actual (por si cambió self._data)
        try:
            # si usas la versión personalizada, llama al renderer
            self._render_month()
        except Exception:
            pass

        try:
            print("DEBUG: calendario mostrado (container exists)", getattr(self, "_cal_container", None) is not None)
        except Exception:
            pass





class ReportesView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Reportes", "Indicadores y exportaciones")
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, padx=16, pady=(0,10), sticky="ew")
        controls.grid_columnconfigure((0,1,2,3), weight=0)
        controls.grid_columnconfigure(4, weight=1)

        cmb = ctk.CTkComboBox(
            controls, values=["Matrículas", "Clases", "Cartera", "Instructores", "Vehículos"],
            height=36, corner_radius=12, fg_color=self.app.COLOR_INPUT_BG,
            button_color=self.app.COLOR_DIVIDER, text_color=self.app.COLOR_TEXT
        )
        cmb.set("Matrículas")
        cmb.grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")

        def red_btn(text, cb):
            return ctk.CTkButton(controls, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cb)

        red_btn("Generar", lambda: self.app._info("Generar reporte")).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn("Exportar XLSX", lambda: self.app._info("Exportar XLSX")).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn("Exportar PDF",  lambda: self.app._info("Exportar PDF")).grid(row=0, column=3, padx=8, pady=6, sticky="w")

        card = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=16)
        card.grid(row=2, column=0, padx=16, pady=(0,16), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Resumen (placeholder)",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=self.app.COLOR_TEXT, anchor="w").grid(row=0, column=0, padx=16, pady=(16,8), sticky="w")
        ctk.CTkLabel(card, text="Aquí va el gráfico / KPI.",
                     text_color=self.app.COLOR_MUTED, anchor="w").grid(row=1, column=0, padx=16, pady=(0,16), sticky="w")


# Usa customtkinter como ctk (ya importado en tu proyecto)
# from customtkinter import CTkFrame, CTkButton, CTkLabel, CTkEntry, CTkComboBox, CTkScrollableFrame

class EstadosCuentaView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Estados de cuenta", "Gestión de saldos y pagos")

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0,6), sticky="ew")
        for c in (0,1,2,3,4): tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8))
        red_btn("✎ Editar", self._editar).grid(row=0, column=1, padx=8)
        red_btn("🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=8)
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8)

        # Formulario (oculto inicialmente)
        self._build_form()
        self.form.grid(row=2, column=0, padx=16, pady=(8,10), sticky="ew")
        self._hide_form()

        # Tabla (lista)
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,8), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        # Data / mappings
        self._data = []              # lista de estados de cuenta (dicts)
        self._rows = []
        self._selected_idx = None

        # Catálogo estudiantes
        self.estudiantes = []
        self.estudiantes_id_to_name = {}
        self.estudiantes_name_to_id = {}

        # Totals frame handle
        self._totals_frame = None

        # Render inicial
        self._render_table()

        # Cargar catálogos y datos con pequeño delay
        self.after(150, self._cargar_catalogos_y_listar)


    # ============ Formulario ============
    def _build_form(self):
        self.form = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL,
                                corner_radius=12, border_width=2, border_color=self.app.COLOR_DIVIDER)
        for c in range(4):
            self.form.grid_columnconfigure(c, weight=1)

        # helper
        def label(r, c, text):
            ctk.CTkLabel(self.form, text=text, text_color=self.app.COLOR_TEXT)\
                .grid(row=r, column=c, padx=10, pady=(10,4), sticky="w")
        def entry(ph=""):
            return ctk.CTkEntry(self.form, height=34, corner_radius=8,
                                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                                border_width=1, border_color=self.app.COLOR_DIVIDER,
                                placeholder_text=ph)

        # Estudiante (combo con nombres)
        label(0, 0, "Estudiante")
        self.cb_estudiante = ctk.CTkComboBox(self.form, values=[], width=360)
        self.cb_estudiante.grid(row=1, column=0, padx=10, pady=(0,6), sticky="w", columnspan=2)

        # Montos y estado
        label(0, 2, "Monto total")
        self.en_total = entry("0.00")
        self.en_total.grid(row=1, column=2, padx=10, pady=(0,6), sticky="ew")

        label(0, 3, "Monto pagado")
        self.en_pagado = entry("0.00")
        self.en_pagado.grid(row=1, column=3, padx=10, pady=(0,6), sticky="ew")

        label(2, 2, "Estado")
        self.cb_estado = ctk.CTkComboBox(self.form, values=["pendiente","parcial","pagado"], width=180)
        self.cb_estado.set("pendiente")
        self.cb_estado.grid(row=3, column=2, padx=10, pady=(0,8), sticky="w")

        # Botones
        btns = ctk.CTkFrame(self.form, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=10, pady=(6,12), sticky="e")
        def red_btn_small(text, cb):
            return ctk.CTkButton(btns, text=text, height=34, corner_radius=10,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cb)
        red_btn_small("Cancelar", self._cancelar).grid(row=0, column=0, padx=6)
        red_btn_small("Guardar", self._guardar).grid(row=0, column=1, padx=6)

        self._form_mode = "create"
        self._editing_idx = None


    def _show_form(self, mode="create", data=None):
        self._form_mode = mode
        if mode == "edit" and data:
            # rellenar campos
            est_name = self.estudiantes_id_to_name.get(data.get("idEstudiante"), str(data.get("idEstudiante") or ""))
            self.cb_estudiante.set(est_name)
            self.en_total.delete(0, "end"); self.en_total.insert(0, f"{(data.get('montoTotal') or 0):.2f}")
            self.en_pagado.delete(0, "end"); self.en_pagado.insert(0, f"{(data.get('montoPagado') or 0):.2f}")
            self.cb_estado.set(data.get("estado","pendiente"))
            # set editing index
            try:
                self._editing_idx = self._data.index(data)
            except Exception:
                self._editing_idx = None
        else:
            self._editing_idx = None
            # valores por defecto
            if self.cb_estudiante.cget("values"):
                try:
                    self.cb_estudiante.set(self.cb_estudiante.cget("values")[0])
                except Exception:
                    pass
            self.en_total.delete(0, "end"); self.en_total.insert(0, "0.00")
            self.en_pagado.delete(0, "end"); self.en_pagado.insert(0, "0.00")
            self.cb_estado.set("pendiente")
        self.form.grid()


    def _hide_form(self):
        self.form.grid_remove()


    # ============ Validación / recolección ============
    def _collect_form(self):
        est_val = self.cb_estudiante.get().strip()
        id_est = self.estudiantes_name_to_id.get(est_val)
        # si entraron id directo:
        if id_est is None and est_val.isdigit():
            id_est = int(est_val)

        def parse_float(s):
            try:
                return float((s or "").strip() or 0.0)
            except Exception:
                return None

        payload = {
            "idEstudiante": id_est,
            "montoTotal": parse_float(self.en_total.get()),
            "montoPagado": parse_float(self.en_pagado.get()),
            "estado": self.cb_estado.get().strip()
        }
        return payload

    def _validate(self, p: dict):
        # campos requeridos
        if p.get("idEstudiante") is None:
            return False, "Debe seleccionar un estudiante válido."
        if p.get("montoTotal") is None or p.get("montoPagado") is None:
            return False, "Montos inválidos."
        if p["montoTotal"] < 0 or p["montoPagado"] < 0:
            return False, "Los montos no pueden ser negativos."
        if p["montoPagado"] > p["montoTotal"]:
            return False, "El monto pagado no puede superar al monto total."
        if not p.get("estado"):
            return False, "Seleccione un estado."
        return True, ""


    # ============ Acciones UI (CRUD) ============
    def _nuevo(self):
        self._show_form("create", {})

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un registro primero.")
            return
        rec = self._data[self._selected_idx]
        self._show_form("edit", rec)

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un registro para eliminar.")
            return
        rec = self._data[self._selected_idx]
        est_name = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), rec.get("idEstudiante"))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar estado de cuenta de: {est_name}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
            else:
                # borrar localmente
                del self._data[self._selected_idx]
                self.app._info("Registro eliminado (local).")
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)


    def _cancelar(self):
        self._hide_form()


    def _guardar(self):
        try:
            payload = self._collect_form()
            ok, msg = self._validate(payload)
            if not ok:
                messagebox.showerror("Validación", msg, parent=self)
                return

            if self._form_mode == "create":
                if self.app and getattr(self.app, "api", None):
                    self.app.api.create("estados-cuenta", payload)
                    self.app._info("Estado de cuenta creado.")
                else:
                    # local: asignar id local incremental
                    payload["_local_id"] = (max([r.get("_local_id",0) for r in self._data] or [0]) + 1)
                    self._data.append(payload)
                    self.app._info("Estado de cuenta creado (local).")
            else:
                if self._editing_idx is None:
                    self.app._info("No se seleccionó registro para actualizar.")
                    return
                rec = self._data[self._editing_idx]
                if self.app and getattr(self.app, "api", None) and rec.get("id"):
                    self.app.api.update("estados-cuenta", rec.get("id"), payload)
                    self.app._info("Estado de cuenta actualizado.")
                else:
                    # actualizar local
                    self._data[self._editing_idx].update(payload)
                    self.app._info("Registro actualizado (local).")

            self._hide_form()
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar:\n{e}", parent=self)


    # ============ Carga catálogos y listado ============
    def _cargar_catalogos_y_listar(self):
        """Carga estudiantes desde la API y luego lista estados de cuenta."""
        try:
            if not (self.app and getattr(self.app, "api", None)):
                # sin API, solo refrescar vista local
                self._refrescar(local_only=True)
                return

            # Estudiantes
            raw = self.app.api.get_all("estudiantes") or []
            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    if isinstance(raw.get(key), list):
                        raw = raw[key]
                        break
                else:
                    raw = []
            self.estudiantes = raw
            self.estudiantes_id_to_name.clear()
            self.estudiantes_name_to_id.clear()
            for e in self.estudiantes:
                eid = e.get("id") or e.get("idEstudiante")
                nombre = "{} {}".format(e.get("nombre",""), e.get("apellido","")).strip()
                if eid is not None and nombre:
                    self.estudiantes_id_to_name[eid] = nombre
                    self.estudiantes_name_to_id[nombre] = eid

            # actualizar combo
            try:
                self.cb_estudiante.configure(values=sorted(list(self.estudiantes_name_to_id.keys())))
                if self.cb_estudiante.cget("values") and not self.cb_estudiante.get():
                    self.cb_estudiante.set(self.cb_estudiante.cget("values")[0])
            except Exception:
                pass

            # finalmente listar estados de cuenta
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible cargar catálogos:\n{e}", parent=self)


    def _refrescar(self, local_only=False):
        """Trae datos desde API (si existe) o refresca la vista local."""
        try:
            if self.app and getattr(self.app, "api", None) and not local_only:
                raw = self.app.api.get_all("estados-cuenta") or []
                if isinstance(raw, dict):
                    for key in ("content","items","estados-cuenta","data","results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []
                self._data = raw or []
            # si no hay API, se espera que _data contenga registros locales
            self._render_table()
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible consultar la API:\n{e}", parent=self)


    # ============ Helpers para render (alineación / totales) ============
    def _apply_colspecs(self, container):
        """
        Configura columnas con anchos mínimos y pesos para que encabezado y filas
        compartan la misma distribución y queden alineadas.
        Devuelve la lista de specs usadas.
        """
        col_specs = [
            ("Estudiante",   260, 1),
            ("Monto total",  120, 0),
            ("Monto pagado", 120, 0),
            ("Saldo",        120, 0),
            ("Estado",       120, 0),
            ("Acciones",     120, 0),
        ]
        for i, (_, minw, weight) in enumerate(col_specs):
            try:
                container.grid_columnconfigure(i, minsize=minw, weight=weight)
            except Exception:
                pass
        return col_specs


    # ============ Render tabla ============
    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        col_specs = self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(col_specs):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin registros", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            # actualizar totales (vacío)
            self._render_totals()
            return

        for r, rec in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            # aplicar misma config de columnas en la fila
            for i, (_, minw, weight) in enumerate(col_specs):
                try:
                    row.grid_columnconfigure(i, minsize=minw, weight=weight)
                except Exception:
                    pass

            est_name = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), str(rec.get("idEstudiante") or ""))
            try:
                total = float(rec.get("montoTotal") or 0.0)
            except Exception:
                total = 0.0
            try:
                pagado = float(rec.get("montoPagado") or 0.0)
            except Exception:
                pagado = 0.0
            saldo = total - pagado
            estado = str(rec.get("estado","")).capitalize()

            vals = [
                est_name,
                f"{total:,.2f}",
                f"{pagado:,.2f}",
                f"{saldo:,.2f}",
                estado,
            ]

            # Estudiante (col 0)
            lbl0 = ctk.CTkLabel(row, text=vals[0], text_color=self.app.COLOR_TEXT, anchor="w")
            lbl0.grid(row=0, column=0, padx=12, pady=10, sticky="w")
            lbl0.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            # Monto total (col 1)
            lbl1 = ctk.CTkLabel(row, text=vals[1], text_color=self.app.COLOR_TEXT, anchor="w")
            lbl1.grid(row=0, column=1, padx=12, pady=10, sticky="ew")
            lbl1.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            # Monto pagado (col 2)
            lbl2 = ctk.CTkLabel(row, text=vals[2], text_color=self.app.COLOR_TEXT, anchor="w")
            lbl2.grid(row=0, column=2, padx=12, pady=10, sticky="ew")
            lbl2.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            # Saldo (col 3) con color
            saldo_color = self.app.COLOR_MUTED
            try:
                if saldo > 0:
                    saldo_color = "#d9534f"   # rojo
                else:
                    saldo_color = "#28a745"   # verde
            except Exception:
                saldo_color = self.app.COLOR_TEXT

            lbl3 = ctk.CTkLabel(row, text=vals[3], text_color=saldo_color, anchor="w")
            lbl3.grid(row=0, column=3, padx=12, pady=10, sticky="ew")
            lbl3.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            # Estado (col 4)
            lbl4 = ctk.CTkLabel(row, text=vals[4], text_color=self.app.COLOR_TEXT, anchor="w")
            lbl4.grid(row=0, column=4, padx=12, pady=10, sticky="ew")
            lbl4.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            # Acciones (col 5)
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")
            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=8,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

        # Totales al final
        self._render_totals()


    def _render_totals(self):
        """
        Muestra un pequeño footer con los totales de montoTotal, montoPagado y saldo.
        Se coloca justo debajo de la tabla (row 4).
        """
        # borrar footer previo si existe
        try:
            if hasattr(self, "_totals_frame") and self._totals_frame is not None:
                try:
                    self._totals_frame.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        # calcular totales
        total_total = 0.0
        total_pagado = 0.0
        for rec in (self._data or []):
            try:
                total_total += float(rec.get("montoTotal") or 0.0)
            except Exception:
                pass
            try:
                total_pagado += float(rec.get("montoPagado") or 0.0)
            except Exception:
                pass
        total_saldo = total_total - total_pagado

        # crear marco de totales
        self._totals_frame = ctk.CTkFrame(self, fg_color="transparent")
        try:
            self._totals_frame.grid(row=4, column=0, padx=16, pady=(0,12), sticky="ew")
        except Exception:
            try:
                self._totals_frame.pack(fill="x", padx=16, pady=(0,12))
            except Exception:
                pass

        # mostrar los valores
        lbl_info = ctk.CTkLabel(self._totals_frame, text=f"Totales — Registros: {len(self._data)}", text_color=self.app.COLOR_MUTED)
        lbl_info.grid(row=0, column=0, padx=(8,12), pady=8, sticky="w")

        lbl_total = ctk.CTkLabel(self._totals_frame, text=f"Monto total: {total_total:,.2f}", text_color=self.app.COLOR_TEXT)
        lbl_total.grid(row=0, column=1, padx=12, pady=8, sticky="e")

        lbl_pag = ctk.CTkLabel(self._totals_frame, text=f"Pagado: {total_pagado:,.2f}", text_color=self.app.COLOR_TEXT)
        lbl_pag.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        saldo_color = "#d9534f" if total_saldo > 0 else "#28a745"
        lbl_saldo = ctk.CTkLabel(self._totals_frame, text=f"Saldo: {total_saldo:,.2f}", text_color=saldo_color)
        lbl_saldo.grid(row=0, column=3, padx=12, pady=8, sticky="e")


    # ============ Selección / acciones de fila ============
    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    def _edit_row(self, idx):
        self._select_row(idx)
        self._editing_idx = idx
        self._show_form("edit", self._data[idx])

    def _delete_row(self, idx):
        self._select_row(idx)
        rec = self._data[idx]
        est = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), rec.get("idEstudiante"))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar registro de {est}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
            else:
                del self._data[idx]
                self.app._info("Registro eliminado (local).")
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

# ======================
#  App principal
# ======================
class HaroDesktopApp(ctk.CTk):
    # -------- Paleta (light, dark) -------- #
    COLOR_BG          = ("#FFFFFF", "#0f0f10")
    COLOR_PANEL       = ("#FFFFFF", "#151517")
    COLOR_TEXT        = ("#111111", "#F5F7FA")
    COLOR_MUTED       = ("#5A5F6A", "#AAB2C0")
    COLOR_RED         = ("#E53935", "#ff4c4c")
    COLOR_YELLOW      = ("#FFC107", "#FFD54F")
    COLOR_DIVIDER     = ("#EFEFF2", "#24262b")
    COLOR_INPUT_BG    = ("#F6F7F9", "#1b1d22")

    APP_TITLE = "CEA HARO — Sistema de Información"
    APP_W, APP_H = 1180, 720
    SIDEBAR_W = 260
    TOPBAR_H  = 64

    # === Marca y logo (según tu indicación) ===
    BRAND_TEXT = "CEA HARO"
    LOGO_SIZE  = (50, 40)

    # --- Ruta FIJA del logo: RELATIVA al archivo .py actual, no al cwd ---
    _SCRIPT_DIR = Path(__file__).resolve().parent
    _LOGO_PATH  = _SCRIPT_DIR / "media" / "LogoHARO.png"

    # API
    API_BASE_URL = "https://harorepositoty2-590358146556.europe-west1.run.app/api"
    AUTH_MODE = "basic"         # si usas JWT, cambia a "jwt"
    JWT_LOGIN_PATH = "auth/login"
    JWT_USER_FIELD = "username"
    JWT_PASS_FIELD = "password"
    JWT_TOKEN_FIELD = "token"

    # No hardcodees credenciales:
    API_USER_DEFAULT = ""   # opcional autollenar
    API_PASS_DEFAULT = ""   # opcional

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(self.APP_TITLE)
        self.geometry(f"{self.APP_W}x{self.APP_H}")
        centrar_ventana(self, self.APP_W, self.APP_H)

        self.minsize(1060, 640)
        self.configure(fg_color=self.COLOR_BG)

        # Estado UI / credenciales
        self.current_view = None
        self.sidebar_visible = True
        self.logo_image = None
        self.api_user = None
        self.api_pass = None
        self.api: ApiClient | None = None

        # Atajos
        self.bind_all("<Escape>", self._on_escape)
        self.bind_all("<Control-f>", self._focus_search)
        self.bind_all("<Control-F>", self._focus_search)

        # Layout raíz
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # Construcción UI fija
        self._build_topbar()
        self._build_sidebar()
        self._build_content_area()

        # Mostrar login antes de todo
        self.withdraw()
        self.after(50, self._show_login)

    # ----------------------- Helpers de recursos ----------------------- #
    @staticmethod
    def resource_path(p) -> Path:
        p = Path(p)
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base) / p.name if p.is_file() else Path(base) / p
        return p

    def _set_default_logo(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        for x in range(64):
            for y in range(64):
                dx, dy = x-32, y-32
                if dx*dx + dy*dy <= 30*30:
                    img.putpixel((x, y), (229, 57, 53, 255))
        self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=self.LOGO_SIZE)

    def _load_fixed_logo(self):
        try:
            path = self.resource_path(self._LOGO_PATH)
            if not path.exists():
                print(f"[Logo] No existe: {path}")
                self._set_default_logo()
                return
            img = Image.open(path)
            w, h = img.size
            side = min(w, h)
            left, top = (w - side) // 2, (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=self.LOGO_SIZE)
        except Exception as e:
            print(f"[Logo] Error cargando: {e}")
            self._set_default_logo()

    # ----------------------- Topbar ----------------------- #
    def _build_topbar(self):
        self.topbar = ctk.CTkFrame(self, height=self.TOPBAR_H, fg_color=self.COLOR_PANEL, corner_radius=0)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        for col in (0,1,2,3,4,5,6,7):
            self.topbar.grid_columnconfigure(col, weight=0)
        self.topbar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(self.topbar, text="☰", width=44, height=36, corner_radius=10,
                      fg_color=self.COLOR_INPUT_BG, hover_color=self.COLOR_DIVIDER,
                      text_color=self.COLOR_TEXT, command=self._toggle_sidebar)\
                      .grid(row=0, column=0, padx=(12, 6), pady=12, sticky="w")

        self.brand_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.brand_frame.grid(row=0, column=1, padx=(6, 8), pady=0, sticky="w")
        self.brand_frame.grid_columnconfigure(0, weight=0)
        self.brand_frame.grid_columnconfigure(1, weight=0)

        self._load_fixed_logo()
        ctk.CTkLabel(self.brand_frame, image=self.logo_image, text="")\
            .grid(row=0, column=0, padx=(0,8), pady=12, sticky="w")
        ctk.CTkLabel(self.brand_frame, text=self.BRAND_TEXT,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=self.COLOR_TEXT)\
            .grid(row=0, column=1, padx=(0,0), pady=12, sticky="w")

        self.search_entry = ctk.CTkEntry(
            self.topbar, placeholder_text="Buscar…  (Ctrl+F)",
            height=36, corner_radius=12, fg_color=self.COLOR_INPUT_BG,
            text_color=self.COLOR_TEXT, border_width=0
        )
        self.search_entry.grid(row=0, column=2, padx=(8,8), pady=12, sticky="ew")
        self.search_entry.bind("<Return>", self._do_search)

        ctk.CTkButton(self.topbar, text="⟳ Sincronizar", height=36, corner_radius=18,
                      fg_color=self.COLOR_RED, hover_color=self.COLOR_YELLOW,
                      text_color="#ffffff", command=self._sync)\
            .grid(row=0, column=4, padx=(8, 8), pady=12, sticky="e")

        ctk.CTkButton(self.topbar, text="● Tema", height=36, corner_radius=12,
                      fg_color=self.COLOR_INPUT_BG, hover_color=self.COLOR_DIVIDER,
                      text_color=self.COLOR_TEXT, command=self._toggle_theme)\
            .grid(row=0, column=5, padx=(0, 12), pady=12, sticky="e")

        # Botón de sesión
        ctk.CTkButton(self.topbar, text="Cerrar sesión", height=36, corner_radius=12,
                      fg_color=self.COLOR_RED, hover_color=self.COLOR_YELLOW,
                      text_color="#ffffff", command=self._logout)\
            .grid(row=0, column=6, padx=(0, 12), pady=12, sticky="e")

    # ----------------------- Sidebar ----------------------- #
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=self.SIDEBAR_W, fg_color=self.COLOR_PANEL, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        for r in range(10):
            self.sidebar.grid_rowconfigure(r, weight=0)
        self.sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(self.sidebar, text="Módulos", text_color=self.COLOR_MUTED,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self.nav_buttons = {}
        def add_nav(row, name, icon):
            b = ctk.CTkButton(self.sidebar, text=f"{icon}  {name}", height=44, corner_radius=12,
                              fg_color="transparent", hover_color=self.COLOR_DIVIDER,
                              text_color=self.COLOR_TEXT, anchor="w",
                              command=lambda n=name: self._nav_callback(n),
                              font=ctk.CTkFont(size=14, weight="normal"))
            b.grid(row=row, column=0, padx=10, pady=6, sticky="ew")
            self.nav_buttons[name] = b

        specs = [("Estudiantes","👤"),("Instructores","🧑‍🏫"),("Vehículos","🚗"),
                 ("Clases","📅"),("Estados de Cuenta","💳"),("Reportes","📊")]
        for i, (n, ic) in enumerate(specs, start=1):
            add_nav(i, n, ic)

        ctk.CTkFrame(self.sidebar, height=1, fg_color=self.COLOR_DIVIDER, corner_radius=0)\
            .grid(row=len(specs)+1, column=0, padx=12, pady=(16, 8), sticky="ew")
        ctk.CTkLabel(self.sidebar, text="© CEA HARO\nSistema de Información",
                     justify="left", text_color=self.COLOR_MUTED, font=ctk.CTkFont(size=11))\
                     .grid(row=len(specs)+2, column=0, padx=16, pady=(0, 12), sticky="sw")

    # ----------------------- Content ----------------------- #
    def _build_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color=self.COLOR_BG, corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _register_views(self):
        self.views = {
            "Estudiantes": EstudiantesView(self.content),
            "Instructores": InstructoresView(self.content),
            "Vehículos": VehiculosView(self.content),
            "Clases": ClasesView(self.content),
            "Estados de Cuenta": EstadosCuentaView(self.content),
            "Reportes": ReportesView(self.content),
        }

    # ----------------------- Login / Sesión ----------------------- #
    def _show_login(self):
        # Diálogo modal
        dlg = LoginDialog(self, on_success=self._on_login_ok, brand=self.BRAND_TEXT)
        # Autollenado opcional:
        if self.API_USER_DEFAULT:
            dlg.en_user.insert(0, self.API_USER_DEFAULT)
        if self.API_PASS_DEFAULT:
            dlg.en_pass.insert(0, self.API_PASS_DEFAULT)

    def _on_login_ok(self, user, password):
        # Si ApiClient falla, deja que la excepción suba al modal
        self.api_user = user
        self.api_pass = password
        self.api = ApiClient(
            self, self.API_BASE_URL, user, password,
            auth_mode=self.AUTH_MODE,
            jwt_login_path=self.JWT_LOGIN_PATH,
            user_field=self.JWT_USER_FIELD,
            pass_field=self.JWT_PASS_FIELD,
            token_field=self.JWT_TOKEN_FIELD
        )
        if not hasattr(self, "views"):
            self._register_views()
        self.deiconify()
        self.switch_view("Estudiantes")


    def _logout(self):
        if messagebox.askyesno("Sesión", "¿Está seguro que desea salir"):
            self.api = None
            self.api_user = None
            self.api_pass = None
            # Oculta vistas actuales
            if hasattr(self, "current_view") and self.current_view:
                self.current_view.grid_remove()
                self.current_view = None
            self.withdraw()
            self.after(50, self._show_login)

    # ----------------------- Navegación ----------------------- #
    def _nav_callback(self, name):
        self.switch_view(name)

    def switch_view(self, name: str):
        if getattr(self, "views", None) is None:
            return
        if self.current_view is not None:
            self.current_view.grid_remove()
        for _, b in self.nav_buttons.items():
            b.configure(fg_color="transparent", text_color=self.COLOR_TEXT)

        btn = self.nav_buttons.get(name)
        if btn:
            btn.configure(fg_color=self.COLOR_DIVIDER, text_color=self.COLOR_TEXT)

        view = self.views.get(name)
        if view:
            view.grid(row=0, column=0, sticky="nsew")
            self.current_view = view
        else:
            self._info(f"Vista '{name}' no encontrada")

    # ----------------------- Acciones genéricas ----------------------- #
    def _on_escape(self, _event=None):
        if messagebox.askyesno("Salir", "¿Deseas cerrar la aplicación"):
            self.destroy()

    def _focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, 'end')

    def _do_search(self, _event=None):
        q = self.search_entry.get().strip()
        if q:
            self._info(f"Buscar: {q}")

    def _sync(self):
        self._info("Sincronizando datos…")

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if current == "Dark" else "dark")

    def _confirm_delete(self, what="registro"):
        if messagebox.askyesno("Confirmar", f"¿Eliminar {what}"):
            self._info(f"{what.capitalize()} eliminado.")
        else:
            self._info("Operación cancelada.")

    def _toggle_sidebar(self):
        if not hasattr(self, "sidebar"):
            return
        if getattr(self, "sidebar_visible", True):
            self.sidebar.grid_remove()
            self.grid_columnconfigure(0, minsize=0, weight=0)
            self.grid_columnconfigure(1, weight=1)
            self.sidebar_visible = False
        else:
            self.sidebar.grid(row=1, column=0, sticky="nsew")
            self.grid_columnconfigure(0, minsize=self.SIDEBAR_W, weight=0)
            self.grid_columnconfigure(1, weight=1)
            self.sidebar_visible = True

    # Util
    def _info(self, msg: str):
        # Reemplaza messagebox por un log silencioso o una etiqueta de estado
        print(msg)  # o actualiza una status bar si tienes una



# ----------------------- Ejecución ----------------------- #
if __name__ == "__main__":
    app = HaroDesktopApp()
    app.mainloop()
