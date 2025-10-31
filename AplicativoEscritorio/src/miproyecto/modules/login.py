# ===================== modules/login.py =====================
__all__ = ["LoginDialog", "SimpleAPI", "AnimatedToggle"]

# ---------- IMPORTS ----------
import sys
import os
import re
import hashlib
import traceback

import customtkinter as ctk
from tkinter import messagebox

# HTTP (opcional, con fallback si no está instalado)
try:
    import requests
except ImportError:
    requests = None

# Centrar ventana (intenta traerlo de utils y si no, fallback)
try:
    from utils import centrar_ventana
except Exception:
    def centrar_ventana(win, w, h):
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = max(0, (sw // 2) - (w // 2))
        y = max(0, (sh // 2) - (h // 2))
        win.geometry(f"{w}x{h}+{x}+{y}")


# ---------- SimpleAPI (cliente HTTP mínimo) ----------
class SimpleAPI:
    """Cliente HTTP mínimo con manejo de errores, last_error y URL efectiva."""
    def __init__(self, base_url, context_path=""):
        # base_url: ej. "http://localhost:8081"
        # context_path: ej. "", "/cea" (sin barra final)
        self.base_url = (base_url or "").rstrip("/")
        self.context_path = (context_path or "").rstrip("/")
        self.last_error = None
        self.last_url = None  # para depurar

    def _join(self, path):
        # path puede venir absoluto ("http://...") o relativo ("/api/...").
        if not path:
            path = "/"
        if path.startswith("http://") or path.startswith("https://"):
            return path
        left = self.base_url
        if self.context_path:
            left += self.context_path
        return f"{left}{path if path.startswith('/') else '/'+path}"

    def _do_post(self, url, json, headers, timeout):
        if requests is None:
            self.last_error = "La librería 'requests' no está instalada."
            return None
        try:
            r = requests.post(url, json=json, headers=headers or {"Content-Type": "application/json"}, timeout=timeout)
            if r.status_code >= 400:
                try:
                    data = r.json()
                except Exception:
                    data = r.text
                self.last_error = f"HTTP {r.status_code} en {url}: {data}"
                return None
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        except Exception as e:
            self.last_error = f"Error de red hacia {url}: {e}"
            return None

    def post(self, path, json, headers=None, timeout=12):
        self.last_error = None
        url = self._join(path)
        self.last_url = url
        data = self._do_post(url, json, headers, timeout)

        # Fallback si 404 y el path empieza por "/api/": reintenta sin "/api"
        if data is None and self.last_error and "HTTP 404" in self.last_error and path.startswith("/api/"):
            alt_path = path[4:]  # quita "/api"
            alt_url = self._join(alt_path)
            self.last_url = alt_url
            data = self._do_post(alt_url, json, headers, timeout)
            if data is None and self.last_error:
                self.last_error += " | Intento alterno: " + alt_url
        return data


# ---------- TOGGLE ANIMADO ----------
class AnimatedToggle(ctk.CTkFrame):
    """
    Toggle animado (slider) con dos opciones tipo web.
    - values: ["Iniciar sesión", "Registrar admin"]
    - on_change: callback(texto_seleccionado) tras terminar animación
    """
    def __init__(self, master, values, variable=None, on_change=None,
                 height=38, corner_radius=12,
                 bg_color_bar="#E5E7EB", indicator_color="#111827", text_color="#000000",
                 pad=4, speed_ms=10, steps=16):
        super().__init__(master, fg_color="transparent")
        assert isinstance(values, (list, tuple)) and len(values) == 2, "values debe tener 2 opciones"
        self.values = list(values)
        self.var = variable or ctk.StringVar(value=self.values[0])
        self.on_change = on_change

        self.h = height
        self.cr = corner_radius
        self.pad = pad
        self.speed_ms = speed_ms
        self.steps = steps

        self.bg_bar = bg_color_bar
        self.indicator = indicator_color
        self.txt = text_color

        # índice inicial según variable
        self.idx = 0 if self.var.get() == self.values[0] else 1

        # Barra contenedora
        self.bar = ctk.CTkFrame(self, fg_color=self.bg_bar, corner_radius=self.cr, height=self.h)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.grid_columnconfigure(0, weight=1)

        # Capa interna y "píldora" deslizante
        self.inner = ctk.CTkFrame(self.bar, fg_color="transparent")
        self.inner.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.pill = ctk.CTkFrame(self.inner, fg_color=self.indicator, corner_radius=self.cr)
        self.lbl_left  = ctk.CTkLabel(self.inner, text=self.values[0], text_color=self.txt)
        self.lbl_right = ctk.CTkLabel(self.inner, text=self.values[1], text_color=self.txt)

        # Clics
        self.lbl_left.bind("<Button-1>",  lambda _e: self.select(0, animate=True))
        self.lbl_right.bind("<Button-1>", lambda _e: self.select(1, animate=True))
        self.inner.bind("<Configure>", self._layout)

        # Labels ocupan mitades
        self.lbl_left.place(relx=0.0,  rely=0.0, relwidth=0.5, relheight=1.0)
        self.lbl_right.place(relx=0.5, rely=0.0, relwidth=0.5, relheight=1.0)

    def _layout(self, _e=None):
        w = self.inner.winfo_width()
        h = self.inner.winfo_height()
        if w <= 2 or h <= 2:
            return
        slot_w = (w - 2*self.pad) // 2
        slot_h = self.h - 2*self.pad
        slot_h = max(2, slot_h)
        self.pill.configure(width=slot_w, height=slot_h)
        x0 = self.pad + (slot_w * self.idx)
        self.pill.place(x=x0, y=self.pad)

    def select(self, index, animate=True):
        index = 0 if index <= 0 else 1
        if index == self.idx:
            self.var.set(self.values[self.idx])
            if self.on_change:
                self.on_change(self.values[self.idx])
            return

        if not animate:
            self.idx = index
            self._layout()
            self.var.set(self.values[self.idx])
            if self.on_change:
                self.on_change(self.values[self.idx])
            return

        w = self.inner.winfo_width()
        if w <= 2:
            return self.select(index, animate=False)

        slot_w = (w - 2*self.pad) // 2
        start_x = self.pad + slot_w * self.idx
        end_x   = self.pad + slot_w * index
        dx = (end_x - start_x) / float(self.steps)

        def step(i=0, x=start_x):
            nx = x + dx
            self.pill.place_configure(x=int(nx))
            if i < self.steps - 1:
                self.after(self.speed_ms, lambda: step(i+1, nx))
            else:
                self.idx = index
                self._layout()
                self.var.set(self.values[self.idx])
                if self.on_change:
                    self.on_change(self.values[self.idx])

        step()


# ---------- LOGIN DIALOG ----------
class LoginDialog(ctk.CTkToplevel):
    """
    Login/Registro para ADMIN.
    - Usuario máx. 20, cédula numérica, email validado
    - Barra de fuerza de contraseña **solo en Registro**
    - Toggle animado entre Login y Registro
    - Al salir o cambiar de modo, limpia campos y oculta errores
    """
    # Patrones y validadores
    _re_usuario_tecla = re.compile(r"^[A-Za-z0-9._-]{0,20}$")
    _re_usuario_full  = re.compile(r"^[A-Za-z0-9._-]{3,20}$")
    _re_nombre_tecla  = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{0,80}$")
    _re_nombre_full   = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{2,80}$")
    _re_email_full    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _re_cedula_tecla  = re.compile(r"^[0-9]{0,20}$")
    _re_cedula_full   = re.compile(r"^[0-9]{5,20}$")
    _danger_chars     = set('<>"\'`$(){}[];')

    def __init__(self, master, on_success=None, brand="CEA HARO", base_url=None, api_client=None):
        super().__init__(master)
        self.app = master
        self.title("Inicio de sesión")

        # API: usa la de la app si existe, sino crea una
        default_base = base_url or getattr(self.app, "API_BASE_URL", "http://localhost:8081")
        if api_client is not None:
            self.api = api_client
        elif hasattr(self.app, "api") and hasattr(self.app.api, "post"):
            self.api = self.app.api
        else:
            self.api = SimpleAPI(default_base)

        # Endpoints
        self.LOGIN_ENDPOINT = getattr(self.app, "LOGIN_ENDPOINT", "/api/auth/login")
        self.ADMIN_ENDPOINT = getattr(self.app, "ADMIN_ENDPOINT", "/api/administradores")

        self.on_success = on_success

        # Tamaño y posición (más alto para pantallas con escalado)
        W, H = 720, 550
        self.geometry(f"{W}x{H}")
        try:
            centrar_ventana(self, W, H)
        except Exception:
            traceback.print_exc()

        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.focus_set()

        # Cerrar = apagar toda la app
        self.protocol("WM_DELETE_WINDOW", self._quit_all)
        self.bind("<Escape>", lambda e: self._quit_all())

        # Paleta desde la app (con fallback)
        fg_bg      = getattr(self.app, "COLOR_BG", ("#FFFFFF", "#0f0f10"))
        fg_panel   = getattr(self.app, "COLOR_PANEL", ("#FFFFFF", "#151517"))
        fg_text    = getattr(self.app, "COLOR_TEXT", ("#111111", "#F5F7FA"))
        fg_muted   = getattr(self.app, "COLOR_MUTED", ("#5A5F6A", "#AAB2C0"))
        fg_divider = getattr(self.app, "COLOR_DIVIDER", ("#EFEFF2", "#24262b"))
        fg_input   = getattr(self.app, "COLOR_INPUT_BG", ("#F6F7F9", "#1b1d22"))
        fg_red     = getattr(self.app, "COLOR_RED", ("#E53935", "#ff4c4c"))
        fg_yellow  = getattr(self.app, "COLOR_YELLOW", ("#FFC107", "#FFD54F"))

        self.configure(fg_color=fg_bg)

        # ====== Layout principal (2 columnas) ======
        self.grid_columnconfigure(0, weight=1, minsize=280)
        self.grid_columnconfigure(1, weight=1, minsize=440)
        self.grid_rowconfigure(0, weight=1)

        # -------- Columna Izquierda (branding) --------
        left = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                            border_width=2, border_color=fg_divider)
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left.grid_rowconfigure((0, 1, 2, 3, 4), weight=0)
        left.grid_rowconfigure(5, weight=1)
        left.grid_columnconfigure(0, weight=1)

        logo_img = getattr(self.app, "logo_image", None)
        if logo_img:
            ctk.CTkLabel(left, image=logo_img, text="").grid(row=0, column=0, pady=(20, 10))

        ctk.CTkLabel(left, text=brand, text_color=fg_text,
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).grid(row=1, column=0, padx=18, pady=(6, 2), sticky="n")

        ctk.CTkLabel(left, text="Sistema de Información", text_color=fg_muted,
                     font=ctk.CTkFont(size=13)
                     ).grid(row=2, column=0, padx=18, pady=(2, 16), sticky="n")

        bullets = ["Gestión integral de estudiantes"]
        for i, t in enumerate(bullets):
            ctk.CTkLabel(left, text=f"• {t}", text_color=fg_text, anchor="w")\
                .grid(row=3 + i, column=0, padx=18, pady=2, sticky="w")

        # -------- Columna Derecha (contenedor) --------
        right = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                             border_width=2, border_color=fg_divider)
        right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # --- Header con toggle animado ---
        header = ctk.CTkFrame(right, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        self.modo = ctk.StringVar(value="LOGIN")  # "LOGIN" | "REG"

        def _on_toggle(texto):
            # cada cambio de modo: limpia formularios y errores
            self._reset_fields(clear_errors=True)
            if texto == "Registrar admin":
                self.lbl_title.configure(text="Registrar administrador")
                self.lbl_help.configure(text="Completa los datos para crear un administrador")
                self.frame_login.grid_forget()
                self.frame_reg.grid(row=0, column=0, sticky="nsew")
                self.modo.set("REG")
            else:
                self.lbl_title.configure(text="Bienvenido")
                self.lbl_help.configure(text="Ingresa con tus credenciales para continuar")
                self.frame_reg.grid_forget()
                self.frame_login.grid(row=0, column=0, sticky="nsew")
                self.modo.set("LOGIN")

        toggle = AnimatedToggle(
            header, values=["Iniciar sesión", "Registrar admin"],
            variable=ctk.StringVar(value="Iniciar sesión"),
            on_change=_on_toggle,
            height=40, corner_radius=12,
            bg_color_bar=fg_divider,
            indicator_color="#111827",
            text_color="#000000",
            pad=4, speed_ms=10, steps=16
        )
        toggle.grid(row=0, column=0, sticky="w")

        self.lbl_title = ctk.CTkLabel(header, text="Bienvenido",
                                      text_color=fg_text, font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.grid(row=1, column=0, sticky="w", pady=(10, 4))

        self.lbl_help = ctk.CTkLabel(header, text="Ingresa con tus credenciales para continuar",
                                     text_color=fg_muted, font=ctk.CTkFont(size=12))
        self.lbl_help.grid(row=2, column=0, sticky="w")

        # --- Content (swap de formularios) ---
        content = ctk.CTkFrame(right, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(6, 6))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # ---------- Validadores por tecla ----------
        v_usuario = (self.register(lambda P: bool(self._re_usuario_tecla.match(P))), "%P")
        v_nombre  = (self.register(lambda P: bool(self._re_nombre_tecla.match(P))), "%P")
        v_cedula  = (self.register(lambda P: bool(self._re_cedula_tecla.match(P))), "%P")
        v_email   = (self.register(self._email_key_validator), "%P")

        # ================== LOGIN ==================
        self.frame_login = ctk.CTkFrame(content, fg_color="transparent")
        self.frame_login.grid(row=0, column=0, sticky="nsew")
        self.frame_login.grid_columnconfigure(0, weight=1)

        rr = 0
        ctk.CTkLabel(self.frame_login, text="Usuario o correo", text_color=fg_text)\
            .grid(row=rr, column=0, padx=0, pady=(0, 6), sticky="w"); rr += 1

        self.en_user = ctk.CTkEntry(
            self.frame_login, height=40, corner_radius=12, fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider, placeholder_text="usuario o correo",
            validate="key", validatecommand=v_usuario
        )
        self.en_user.grid(row=rr, column=0, padx=0, pady=(0, 12), sticky="ew"); rr += 1

        ctk.CTkLabel(self.frame_login, text="Contraseña", text_color=fg_text)\
            .grid(row=rr, column=0, padx=0, pady=(0, 6), sticky="w"); rr += 1

        pass_wrap = ctk.CTkFrame(self.frame_login, fg_color="transparent")
        pass_wrap.grid(row=rr, column=0, padx=0, pady=(0, 12), sticky="ew")
        pass_wrap.grid_columnconfigure(0, weight=1)

        self.en_pass = ctk.CTkEntry(
            pass_wrap, height=40, corner_radius=12, show="*",
            fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider, placeholder_text="********"
        )
        self.en_pass.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._pass_visible = False

        ctk.CTkButton(
            pass_wrap, text="👁", width=40, height=40, corner_radius=12,
            fg_color=fg_divider, hover_color=fg_input, text_color=fg_text,
            command=self._toggle_pass
        ).grid(row=0, column=1, sticky="e")

        opt_row = rr + 1
        self.cb_remember = ctk.CTkCheckBox(
            self.frame_login, text="Recordar usuario", text_color=fg_text,
            fg_color=fg_input, border_color=fg_divider, hover_color=fg_divider
        )
        self.cb_remember.grid(row=opt_row, column=0, padx=0, pady=(0, 10), sticky="w")

        ctk.CTkButton(
            self.frame_login, text="¿Olvidaste tu contraseña?", height=28, corner_radius=8,
            fg_color="transparent", hover_color=fg_divider, text_color=fg_muted,
            command=lambda: messagebox.showinfo("Ayuda", "Contacta al administrador del sistema.")
        ).grid(row=opt_row, column=0, padx=0, pady=(0, 10), sticky="e")

        # ================== REGISTRO (scrollable + barra fuerza) ==================
        self.frame_reg = ctk.CTkScrollableFrame(content, fg_color="transparent")
        self.frame_reg.grid_forget()
        self.frame_reg.grid_columnconfigure((0, 1), weight=1)

        r2 = 0
        ctk.CTkLabel(self.frame_reg, text="Nombre", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 6), sticky="w")
        ctk.CTkLabel(self.frame_reg, text="Cédula", text_color=fg_text)\
            .grid(row=r2, column=1, padx=(10, 0), pady=(0, 6), sticky="w"); r2 += 1

        self.ca_nombre = ctk.CTkEntry(self.frame_reg, height=36, fg_color=fg_input, text_color=fg_text, border_color=fg_divider,
                                      validate="key", validatecommand=v_nombre)
        self.ca_cedula = ctk.CTkEntry(self.frame_reg, height=36, fg_color=fg_input, text_color=fg_text, border_color=fg_divider,
                                      validate="key", validatecommand=v_cedula)
        self.ca_nombre.grid(row=r2, column=0, padx=(0, 10), pady=(0, 10), sticky="ew")
        self.ca_cedula.grid(row=r2, column=1, padx=(10, 0), pady=(0, 10), sticky="ew"); r2 += 1

        ctk.CTkLabel(self.frame_reg, text="Usuario", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 6), sticky="w")
        ctk.CTkLabel(self.frame_reg, text="Correo", text_color=fg_text)\
            .grid(row=r2, column=1, padx=(10, 0), pady=(0, 6), sticky="w"); r2 += 1

        self.ca_usuario = ctk.CTkEntry(self.frame_reg, height=36, fg_color=fg_input, text_color=fg_text, border_color=fg_divider,
                                       validate="key", validatecommand=v_usuario)
        self.ca_email   = ctk.CTkEntry(self.frame_reg, height=36, fg_color=fg_input, text_color=fg_text, border_color=fg_divider,
                                       validate="key", validatecommand=v_email)
        self.ca_usuario.grid(row=r2, column=0, padx=(0, 10), pady=(0, 10), sticky="ew")
        self.ca_email.grid(row=r2, column=1, padx=(10, 0), pady=(0, 10), sticky="ew"); r2 += 1

        ctk.CTkLabel(self.frame_reg, text="Contraseña", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 6), sticky="w"); r2 += 1

        self.ca_pass1 = ctk.CTkEntry(self.frame_reg, height=36, fg_color=fg_input, text_color=fg_text,
                                     border_color=fg_divider, show="*")
        self.ca_pass1.grid(row=r2, column=0, columnspan=2, padx=(0, 0), pady=(0, 10), sticky="ew"); r2 += 1

        # --- Barra fuerza SOLO EN REGISTRO ---
        self.pw_bar_reg = ctk.CTkProgressBar(self.frame_reg, height=8)
        self.pw_bar_reg.grid(row=r2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.pw_bar_reg.set(0.05)
        self.pw_bar_reg.configure(progress_color="#ff4c4c"); r2 += 1
        self.pw_lbl_reg = ctk.CTkLabel(self.frame_reg, text="Seguridad: Muy débil",
                                       text_color="#ff4c4c", font=ctk.CTkFont(size=10))
        self.pw_lbl_reg.grid(row=r2, column=0, columnspan=2, sticky="w", pady=(0, 10)); r2 += 1

        # Actualiza al teclear (REGISTRO)
        self.ca_pass1.bind("<KeyRelease>", lambda e: self._update_strength_meter(self.ca_pass1.get(),
                                                                                 self.pw_bar_reg, self.pw_lbl_reg))

        # Botón crear admin al final (no se corta por scroll)
        wrap_btn = ctk.CTkFrame(self.frame_reg, fg_color="transparent")
        wrap_btn.grid(row=r2, column=0, columnspan=2, sticky="e", pady=(6, 12))
        self.btn_crear_admin = ctk.CTkButton(
            wrap_btn, text="Registrar administrador", height=34, corner_radius=8,
            fg_color=fg_red, hover_color=fg_yellow, text_color="#ffffff",
            command=self._crear_admin
        )
        self.btn_crear_admin.grid(row=0, column=0, padx=0, pady=(4, 2), sticky="e")

        # --- Error / info ---
        self.err = ctk.CTkLabel(right, text="", text_color=fg_red, anchor="w", justify="left",
                                font=ctk.CTkFont(size=12, weight="bold"))
        self.err.grid(row=2, column=0, padx=20, pady=(0, 4), sticky="ew")

        # --- Botones abajo ---
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=3, column=0, padx=20, pady=(6, 16), sticky="e")

        self.btn_cancel = ctk.CTkButton(
            actions, text="Cancelar", height=40, corner_radius=12,
            fg_color=fg_red, hover_color=fg_yellow, text_color="#ffffff",
            command=self._cancel
        )
        self.btn_accept = ctk.CTkButton(
            actions, text="Ingresar", height=40, corner_radius=12,
            fg_color="#111827", hover_color="#333c49", text_color="#ffffff",
            command=self._ok
        )
        self.btn_cancel.grid(row=0, column=0, padx=(0, 8))
        self.btn_accept.grid(row=0, column=1)

        # Atajos
        self.bind("<Return>", lambda e: self._ok())
        self.en_user.focus_set()

    # -------- Helpers validación / fuerza / limpieza --------
    def _email_key_validator(self, new_text):
        """Bloquea caracteres peligrosos al escribir email; formato se valida al enviar."""
        for ch in new_text:
            if ch in self._danger_chars:
                return False
        return True

    def _sanitize_login_for_submit(self, text):
        """Limpia caracteres peligrosos por si llegan por pegado."""
        return "".join(ch for ch in text if ch not in self._danger_chars)

    def _password_strength_score(self, pwd):
        """Score 0..4 según longitud y variedad."""
        if not pwd:
            return 0
        score = 0
        if len(pwd) >= 8:  score += 1
        if len(pwd) >= 12: score += 1
        if re.search(r"[A-Z]", pwd): score += 1
        if re.search(r"[a-z]", pwd) and re.search(r"[0-9]", pwd): score += 1
        if re.search(r"[^A-Za-z0-9]", pwd): score += 1
        return min(score, 4)

    def _strength_to_ui(self, score):
        """Mapea score a (valor 0..1, texto, color)."""
        mapping = {
            0: (0.05, "Muy débil", "#ff4c4c"),
            1: (0.25, "Débil",     "#ff7a59"),
            2: (0.50, "Media",     "#f4c542"),
            3: (0.75, "Fuerte",    "#4caf50"),
            4: (1.00, "Muy fuerte","#2e7d32"),
        }
        return mapping.get(score, (0.05, "Muy débil", "#ff4c4c"))

    def _update_strength_meter(self, pwd, bar, lbl):
        score = self._password_strength_score(pwd)
        val, text, color = self._strength_to_ui(score)
        try:
            bar.set(val)
            bar.configure(progress_color=color)
            lbl.configure(text=f"Seguridad: {text}", text_color=color)
        except Exception:
            pass

    def _reset_fields(self, clear_errors=True):
        """Limpia todos los campos de ambos formularios y oculta errores/barras."""
        try:
            # Login
            self.en_user.delete(0, "end")
            self.en_pass.delete(0, "end")
            self.cb_remember.deselect()
            # Registro
            self.ca_nombre.delete(0, "end")
            self.ca_cedula.delete(0, "end")
            self.ca_usuario.delete(0, "end")
            self.ca_email.delete(0, "end")
            self.ca_pass1.delete(0, "end")
            # Barra de fuerza (reset visual)
            if hasattr(self, "pw_bar_reg"):
                self.pw_bar_reg.set(0.05)
            if hasattr(self, "pw_lbl_reg"):
                self.pw_lbl_reg.configure(text="Seguridad: Muy débil", text_color="#ff4c4c")
            # Error
            if clear_errors and hasattr(self, "err"):
                self.err.configure(text="")
        except Exception:
            pass

    # -------- Lógica de UI --------
    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self.en_pass.configure(show="" if self._pass_visible else "*")

    def _show_error(self, msg):
        # Añade URL efectiva si existe para depurar rápido
        if hasattr(self, "api") and getattr(self.api, "last_url", None):
            msg = f"{msg}\n\nURL: {self.api.last_url}"
        try:
            self.err.configure(text=msg or "")
        except Exception:
            traceback.print_exc()
            messagebox.showerror("Login", msg, parent=self)

    # -------- Lógica Login / Registro --------
    def _ok(self):
        if self.modo.get() != "LOGIN":
            self._show_error("Estás en 'Registrar admin'. Cambia a 'Iniciar sesión' para loguearte.")
            return

        # Oculta errores previos
        self.err.configure(text="")

        u = self._sanitize_login_for_submit(self.en_user.get().strip())
        p = self.en_pass.get().strip()
        if not u or not p:
            self._show_error("Usuario y contraseña son obligatorios.")
            return

        # Validación: email vs usuario
        if "@" in u:
            if not self._re_email_full.fullmatch(u):
                self._show_error("Correo inválido.")
                return
        else:
            if not self._re_usuario_full.fullmatch(u):
                self._show_error("Usuario inválido. Use letras, números, . _ - (3-20).")
                return

        p_hex = hashlib.sha256(p.encode("utf-8")).hexdigest()

        if callable(self.on_success):
            try:
                self.on_success(u, p_hex)
                if hasattr(self.app, "api") and getattr(self.app.api, "last_error", None):
                    self._show_error(self.app.api.last_error)
                    return
                # éxito: limpia antes de cerrar
                self._reset_fields(clear_errors=True)
                self.grab_release(); self.destroy()
                return
            except Exception as e:
                traceback.print_exc()
                self._show_error(f"Error de autenticación: {e}")
                return

        data = self.api.post(self.LOGIN_ENDPOINT, json={"login": u, "password": p_hex})
        if data is None:
            self._show_error(self.api.last_error or "Login falló.")
            return

        # éxito: limpia antes de cerrar
        self._reset_fields(clear_errors=True)
        self.grab_release()
        self.destroy()

    def _crear_admin(self):
        # Oculta errores previos
        self.err.configure(text="")

        nombre  = getattr(self, "ca_nombre", None).get().strip()
        cedula  = getattr(self, "ca_cedula", None).get().strip()
        usuario = getattr(self, "ca_usuario", None).get().strip()
        correo  = getattr(self, "ca_email",   None).get().strip()
        p1      = getattr(self, "ca_pass1",   None).get().strip()

        if not (nombre and cedula and usuario and correo and p1):
            self._show_error("Completa nombre, cédula, usuario, correo y contraseña.")
            return

        # Validaciones fuertes
        if not self._re_nombre_full.fullmatch(nombre):
            self._show_error("Nombre inválido. Solo letras, espacios, apóstrofo y guion (2-80).")
            return
        if not self._re_cedula_full.fullmatch(cedula):
            self._show_error("Cédula inválida. Solo números (5-20).")
            return
        if not self._re_usuario_full.fullmatch(usuario):
            self._show_error("Usuario inválido. Use letras, números, . _ - (3-20).")
            return
        if not self._re_email_full.fullmatch(correo):
            self._show_error("Correo inválido.")
            return
        # Reglas mínimas de contraseña
        if len(p1) < 8 or not re.search(r"[A-Za-z]", p1) or not re.search(r"[0-9]", p1):
            self._show_error("La contraseña debe tener mínimo 8 caracteres, con letras y números.")
            return

        contrasena_hex = hashlib.sha256(p1.encode("utf-8")).hexdigest()
        payload = {
            "correo":         correo,
            "cedula":         cedula,
            "usuario":        usuario,
            "contrasenaHash": contrasena_hex,
            "nombre":         nombre,
            "activo":         True
        }

        data = self.api.post(self.ADMIN_ENDPOINT, json=payload)
        if data is None:
            self._show_error(self.api.last_error or "No se pudo crear el administrador.")
            return

        # Mensaje corto de éxito y luego limpiar a fondo
        self.err.configure(text="Administrador creado correctamente.")

        # Regresar a LOGIN **vacío** (sin prellenar nada)
        self._reset_fields(clear_errors=True)
        self.modo.set("LOGIN")
        self.frame_reg.grid_forget()
        self.frame_login.grid(row=0, column=0, sticky="nsew")
        self.lbl_title.configure(text="Bienvenido")
        self.lbl_help.configure(text="Ingresa con tus credenciales para continuar")

    # -------- Salida total --------
    def _quit_all(self):
        # Limpia para que, si se vuelve a abrir, no queden rastros visuales
        self._reset_fields(clear_errors=True)
        try: self.grab_release()
        except Exception: pass
        try:
            if hasattr(self.app, "quit"): self.app.quit()
        except Exception: pass
        try:
            if hasattr(self.app, "destroy"): self.app.destroy()
        except Exception: pass
        try: self.destroy()
        except Exception: pass
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

    def _cancel(self):
        self._quit_all()
