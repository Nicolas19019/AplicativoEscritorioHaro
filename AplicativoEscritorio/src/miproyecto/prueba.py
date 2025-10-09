# -*- coding: utf-8 -*-
import sys
import base64
import json
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
from pathlib import Path

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
                r = requests.post(u, json=data, timeout=15,
                                  headers={"Accept":"application/json","Content-Type":"application/json"})
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
                return r.json() if r.text else {}
            else:
                import urllib.request, json as _json
                req = urllib.request.Request(u, data=_json.dumps(data).encode("utf-8"), method="POST")
                req.add_header("Accept","application/json")
                req.add_header("Content-Type","application/json")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    txt = resp.read().decode("utf-8")
                    return _json.loads(txt) if txt else {}
        resp = do_post(url, payload) or {}
        token = resp.get(self.token_field)
        if not token:
            raise RuntimeError("No se recibió token JWT en la respuesta.")
        self._bearer = f"Bearer {token}"

    def _request(self, method, path, data=None, params=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept":"application/json","Content-Type":"application/json"}
        if self.auth_mode == "jwt":
            headers["Authorization"] = self._bearer
        else:
            headers["Authorization"] = self._basic_header

        if requests:
            func = getattr(requests, method.lower())
            resp = func(url, headers=headers, json=data, params=params, timeout=15)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            if resp.text and resp.headers.get("Content-Type","").startswith("application/json"):
                return resp.json()
            return None
        else:
            # Fallback urllib
            import urllib.request, urllib.error, json as _json
            payload = None if data is None else _json.dumps(data).encode("utf-8")
            if params:
                from urllib.parse import urlencode
                qs = urlencode(params)
                url = url + ("&" if "?" in url else "?") + qs
            req = urllib.request.Request(url, data=payload, method=method.upper())
            for k,v in headers.items(): req.add_header(k, v)
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
        self.title("Inicio de sesión")
        self.geometry("380x300")
        centrar_ventana(self, 380, 300)

        self.resizable(False, False)
        self.transient(master)
        self.grab_set()  # modal
        self.focus_set()

        # Estilos del master si existen
        self.app = master
        fg_panel = getattr(master, "COLOR_PANEL", "#151517")
        fg_input = getattr(master, "COLOR_INPUT_BG", "#1b1d22")
        txt_color = getattr(master, "COLOR_TEXT", "#F5F7FA")
        div_color = getattr(master, "COLOR_DIVIDER", "#24262b")
        red = getattr(master, "COLOR_RED", "#ff4c4c")
        yellow = getattr(master, "COLOR_YELLOW", "#FFD54F")

        self.configure(fg_color=fg_panel)

        # Layout
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text=f"{brand} — Acceso",
                             font=ctk.CTkFont(size=18, weight="bold"),
                             text_color=txt_color)
        title.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="n")

        card = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=16,
                            border_width=2, border_color=div_color)
        card.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")
        for i in range(2): card.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(card, text="Usuario", text_color=txt_color).grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        self.en_user = ctk.CTkEntry(card, height=36, corner_radius=10,
                                    fg_color=fg_input, text_color=txt_color,
                                    border_width=2, border_color=div_color, placeholder_text="usuario")
        self.en_user.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(card, text="Contraseña", text_color=txt_color).grid(row=2, column=0, padx=12, pady=(0, 6), sticky="w")
        self.en_pass = ctk.CTkEntry(card, height=36, corner_radius=10,
                                    fg_color=fg_input, text_color=txt_color,
                                    border_width=2, border_color=div_color, placeholder_text="********",
                                    show="*")
        self.en_pass.grid(row=3, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="ew")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=red, hover_color=yellow,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Ingresar", lambda: self._ok(on_success)).grid(row=0, column=1, padx=6)

        # ENTER = Ingresar
        self.bind("<Return>", lambda e: self._ok(on_success))
        self.en_user.focus_set()

    def _ok(self, cb):
        u = self.en_user.get().strip()
        p = self.en_pass.get().strip()
        if not u or not p:
            messagebox.showerror("Login", "Usuario y contraseña son obligatorios.", parent=self)
            return
        try:
            cb(u, p)
            self.grab_release()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Login", f"Error de autenticación:\n{e}", parent=self)

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
            self.app._info("Estudiantes: {} registros.".format(len(self._data)))
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
        if not messagebox.askyesno("Confirmar", "¿Eliminar al estudiante:\n{} (Doc: {})?".format(full_name, doc)):
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

# --- Otras vistas (placeholders con botones rojos y filtros) ---
class InstructoresView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Instructores", "Disponibilidad y asignaciones")
        toolbar = self._make_toolbar(
            self,
            on_new=lambda: self.app._info("Nuevo instructor"),
            on_edit=lambda: self.app._info("Editar instructor"),
            on_delete=lambda: self.app._confirm_delete("instructor"),
            on_refresh=lambda: self.app._info("Refrescar instructores")
        )
        toolbar.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        filters = self._make_filters_pro(self, campos=("Nombre","Licencia"), estados=("Todos","Activo","Inactivo"))
        filters.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")


class VehiculosView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Vehículos", "Documentación, mantenimiento y disponibilidad")
        toolbar = self._make_toolbar(
            self,
            on_new=lambda: self.app._info("Nuevo vehículo"),
            on_edit=lambda: self.app._info("Editar vehículo"),
            on_delete=lambda: self.app._confirm_delete("vehículo"),
            on_refresh=self._refrescar
        )
        toolbar.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        filters = self._make_filters_pro(self, campos=("Placa","Marca"), estados=("Todos","Activo","Baja"))
        filters.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")

        # Tabla simple para lista de vehículos desde API (si hay)
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Placa", 120, 0),
            ("Marca", 160, 0),
            ("Modelo", 160, 0),
            ("Año",   100, 0),
            ("Estado",140, 1),
        ]
        self._data = []
        self._render_table()

    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()

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

            values = [v.get("placa",""), v.get("marca",""), v.get("modelo",""),
                      str(v.get("anio","")), v.get("estado","")]
            for i, val in enumerate(values):
                ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                             anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

    def _refrescar(self):
        try:
            # GET /api/vehiculos
            data = self.app.api.get_all("vehiculos") or []
            # Asegurar lista
            if isinstance(data, dict):  # por si backend devuelve {content:[...]} etc.
                # Intenta extraer una lista
                for key in ("content","items","vehiculos","data"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    data = []
            self._data = data
            self._render_table()
            self.app._info(f"Vehículos: {len(self._data)} registros.")
        except Exception as e:
            messagebox.showerror("Vehículos", f"No fue posible consultar la API:\n{e}", parent=self)


class ClasesView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Clases", "Agendamiento y control de asistencia")
        toolbar = self._make_toolbar(
            self,
            on_new=lambda: self.app._info("Nueva clase"),
            on_edit=lambda: self.app._info("Editar clase"),
            on_delete=lambda: self.app._confirm_delete("clase"),
            on_refresh=lambda: self.app._info("Refrescar clases")
        )
        toolbar.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        filters = self._make_filters_pro(self, campos=("Alumno","Instructor"), estados=("Todos","Programada","Dictada","Cancelada"))
        filters.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")


class EstadosView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Estados de Cuenta", "Pagos, saldos y cartera")
        toolbar = self._make_toolbar(
            self,
            on_new=lambda: self.app._info("Registrar pago"),
            on_edit=lambda: self.app._info("Editar pago"),
            on_delete=lambda: self.app._confirm_delete("registro"),
            on_refresh=lambda: self.app._info("Refrescar estados")
        )
        toolbar.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        filters = self._make_filters_pro(self, campos=("Documento","Alumno"), estados=("Todos","Al día","Mora"))
        filters.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        table.grid(row=3, column=0, padx=16, pady=(0,16), sticky="nsew")


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
    API_BASE_URL = "http://localhost:8081/api"
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
            "Estados de Cuenta": EstadosView(self.content),
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
        # Construir cliente API según modo
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
        # Si autenticó (o Basic), mostramos app y registramos vistas
        if not hasattr(self, "views"):
            self._register_views()
        self.deiconify()
        self.switch_view("Estudiantes")

    def _logout(self):
        if messagebox.askyesno("Sesión", "¿Cerrar sesión y volver a ingresar?"):
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
        if messagebox.askyesno("Salir", "¿Deseas cerrar la aplicación?"):
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
        if messagebox.askyesno("Confirmar", f"¿Eliminar {what}?"):
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
        messagebox.showinfo("Información", msg)


# ----------------------- Ejecución ----------------------- #
if __name__ == "__main__":
    app = HaroDesktopApp()
    app.mainloop()
