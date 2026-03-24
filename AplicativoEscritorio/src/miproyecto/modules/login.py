# ===================== modules/login.py =====================
__all__ = ["LoginDialog", "SimpleAPI", "AnimatedToggle"]

# ---------- IMPORTS ----------
from pathlib import Path
import sys
import os
import re
import hashlib
import traceback
import threading

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
ICON_ICO_PATH = SCRIPT_DIR.parent / "media" / "logoHARO.ico"     # respeta el nombre real
ICON_PNG_PATH = SCRIPT_DIR.parent / "media" / "logoHARO.png"     # fallback icono ventana
LOGO_GRANDE_PATH = SCRIPT_DIR.parent / "media" / "LogoGrande.png"

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
        # base_url: ej. "http://localhost:8082"
        # context_path: ej. "", "/cea" (sin barra final)
        self.base_url = (base_url or "").rstrip("/")
        self.context_path = (context_path or "").rstrip("/")
        self.last_error = None
        self.last_url = None  # para depurar

  
    def _join(self, path):
 
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
                # puede ser vacío (200 OK sin body) => r.json() falla
                if not r.text:
                    return {}
                return r.json()
            except Exception:
                return {"raw": r.text}
        except Exception as e:
            self.last_error = f"Error de red hacia {url}: {e}"
            return None

    def post(self, path, json, headers=None, timeout=25):
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


        self.idx = 0 if self.var.get() == self.values[0] else 1

 
        self.bar = ctk.CTkFrame(self, fg_color=self.bg_bar, corner_radius=self.cr, height=self.h)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.grid_columnconfigure(0, weight=1)

  
        self.inner = ctk.CTkFrame(self.bar, fg_color="transparent")
        self.inner.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.pill = ctk.CTkFrame(self.inner, fg_color=self.indicator, corner_radius=self.cr)
        self.lbl_left = ctk.CTkLabel(self.inner, text=self.values[0], text_color=self.txt)
        self.lbl_right = ctk.CTkLabel(self.inner, text=self.values[1], text_color=self.txt)

        self.lbl_left.bind("<Button-1>", lambda _e: self.select(0, animate=True))
        self.lbl_right.bind("<Button-1>", lambda _e: self.select(1, animate=True))
        self.inner.bind("<Configure>", self._layout)

        self.lbl_left.place(relx=0.0, rely=0.0, relwidth=0.5, relheight=1.0)
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
        end_x = self.pad + slot_w * index
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

    _re_usuario_tecla = re.compile(r"^[A-Za-z0-9._-]{0,20}$")
    _re_usuario_full  = re.compile(r"^[A-Za-z0-9._-]{3,20}$")
    _re_nombre_tecla  = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{0,80}$")
    _re_nombre_full   = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{2,80}$")
    _re_email_full    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _re_cedula_tecla  = re.compile(r"^[0-9]{0,20}$")
    _re_cedula_full   = re.compile(r"^[0-9]{5,20}$")
    _danger_chars     = set('<>"\'`$(){}[];')

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        raw = (base_url or "").strip().rstrip("/")
        if raw.lower().endswith("/api"):
            return raw[: len(raw) - 4]
        return raw

    def __init__(self, master, on_success=None, brand="CEA HARO", base_url=None, api_client=None):
        super().__init__(master)
        self.app = master
        self.title("Inicio de sesión")


        # ✅ Forzar que sea ventana normal (no "toolwindow/dialog") para habilitar minimizar
        try:
            self.overrideredirect(False)
        except Exception:
            pass

        # En Windows, si por alguna razón quedó como toolwindow, esto lo revierte
        try:
            if sys.platform.startswith("win"):
                self.wm_attributes("-toolwindow", 0)
        except Exception:
            pass

        # Asegura estado normal
        try:
            self.state("normal")
        except Exception:
            pass

        # ==== Config / endpoints ====
        self.ADMIN_OTP_EMAIL = getattr(self.app, "ADMIN_OTP_EMAIL", "haroacademiadecol@gmail.com")
        default_base = base_url or getattr(self.app, "API_BASE_URL", "http://localhost:8082")
        default_base = self._normalize_base_url(default_base)

        if api_client is not None:
            self.api = api_client
        elif hasattr(self.app, "api") and hasattr(self.app.api, "post"):
            self.api = self.app.api
        else:
            self.api = SimpleAPI(default_base)

 
        self.LOGIN_ENDPOINT = getattr(self.app, "LOGIN_ENDPOINT", "/api/auth/login")
 
        self.ADMIN_ENDPOINT = getattr(self.app, "ADMIN_ENDPOINT", "/api/administradores")
        self.OTP_SEND_ENDPOINT = getattr(self.app, "OTP_SEND_ENDPOINT", "/api/verification/email/send")
        self.OTP_VERIFY_ENDPOINT = getattr(self.app, "OTP_VERIFY_ENDPOINT", "/api/verification/email/verify")

        self.on_success = on_success

        # ==== Estado registro/OTP ====
        self._pending_admin_payload = None
        self._otp_dialog_open = False
        self._otp_target_email = ""
        self._otp_verified_email = ""

        # ==== Iconos ====
        self._ICON_ICO_PATH = ICON_ICO_PATH
        self._ICON_PNG_PATH = ICON_PNG_PATH

        self.set_window_icon()

        self._LOGO_GRANDE_PATH = LOGO_GRANDE_PATH

        # ==== Ventana ====
        W, H = 740, 620
        self.geometry(f"{W}x{H}")

        # ✅ Centrar cuando ya se dibujó (más confiable)
        self.after(50, lambda: centrar_ventana(self, W, H))

        self.resizable(False, False)
        self._login_modal_active = False
        self._enable_login_modal()
        self.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._quit_all)
        self.bind("<Escape>", lambda _e: self._quit_all())

        # Si minimizan el login, minimizamos también la ventana principal
        self.bind("<Unmap>", self._on_login_unmap)
        # Si restauran el login, restauramos también la principal
        self.bind("<Map>", self._on_login_map)


        # ==== Paleta (modo claro: textos negros, títulos rojos) ====
        fg_bg      = getattr(self.app, "COLOR_BG", ("#FFFFFF", "#0f0f10"))
        fg_panel   = getattr(self.app, "COLOR_PANEL", ("#FFFFFF", "#151517"))
 
        fg_divider = getattr(self.app, "COLOR_DIVIDER", ("#EFEFF2", "#24262b"))
        fg_input   = getattr(self.app, "COLOR_INPUT_BG", ("#F6F7F9", "#1b1d22"))

        # 🔥 según tu requerimiento
        fg_text  = "#000000"
        fg_muted = "#111111"
        fg_title = "#DC2626"

        self.PLACEHOLDER_YELLOW = "#FFC107"
        fg_red = "#DC2626"
        fg_dark = "#111827"

        self.configure(fg_color=fg_bg)

        self.grid_columnconfigure(0, weight=1, minsize=280)
        self.grid_columnconfigure(1, weight=1, minsize=460)
        self.grid_rowconfigure(0, weight=1)

        # ================= Left panel (logo grande centrado) =================
        left = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                           border_width=2, border_color=fg_divider)
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
 
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=0)
        left.grid_rowconfigure(2, weight=1)

        try:
            p = self._resolve_existing_path(self._LOGO_GRANDE_PATH)
            if p:
                img = Image.open(p)
                self._logo_big_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(260, 160))
                ctk.CTkLabel(left, image=self._logo_big_ref, text="").grid(row=1, column=0)
        except Exception as e:
            print("[UI] No se pudo cargar LogoGrande.png:", e)

        # ================= Right panel =================
        right = ctk.CTkFrame(self, fg_color=fg_panel, corner_radius=20,
                            border_width=2, border_color=fg_divider)
        right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=0)  # header
        right.grid_rowconfigure(1, weight=1)  # content
        right.grid_rowconfigure(2, weight=0)  # error box
        right.grid_rowconfigure(3, weight=0)  # actions

        # ===== Header (título + ayuda) =====
        header = ctk.CTkFrame(right, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)

        self.modo = ctk.StringVar(value="LOGIN")

        self.lbl_title = ctk.CTkLabel(
            header, text="Bienvenido",
            text_color=fg_title,
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.lbl_title.grid(row=0, column=0, sticky="w")

        self.lbl_help = ctk.CTkLabel(
            header, text="Ingresa con tus credenciales para continuar",
            text_color=fg_muted,
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=360
        )
        self.lbl_help.grid_remove()
        self.lbl_help.configure(justify="left", wraplength=360)

        # ===== Content =====
        content = ctk.CTkFrame(right, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 4))
        content.grid_columnconfigure(0, weight=1)


        # Validadores
        v_usuario = (self.register(lambda P: bool(self._re_usuario_tecla.match(P))), "%P")
        v_nombre  = (self.register(lambda P: bool(self._re_nombre_tecla.match(P))), "%P")
        v_cedula  = (self.register(lambda P: bool(self._re_cedula_tecla.match(P))), "%P")
        v_email   = (self.register(self._email_key_validator), "%P")
        v_otp     = (self.register(lambda P: (P.isdigit() and len(P) <= 6) or P == ""), "%P")

        # =================== LOGIN FRAME ===================
        self.frame_login = ctk.CTkFrame(content, fg_color="transparent")
        self.frame_login.grid(row=0, column=0, sticky="nsew")
        self.frame_login.grid_columnconfigure(0, weight=1)

        rr = 0
        ctk.CTkLabel(self.frame_login, text="Correo", text_color=fg_text)\
            .grid(row=rr, column=0, pady=(0, 4), sticky="w"); rr += 1

        self.en_user = ctk.CTkEntry(
            self.frame_login, height=44, corner_radius=12,
            fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider,
            placeholder_text="correo@dominio.com",
            placeholder_text_color="#4F4F4F",
            validate="key", validatecommand=v_email
        )
        self.en_user.grid(row=rr, column=0, pady=(0, 8), sticky="ew"); rr += 1
        self._decorate_entry(self.en_user)

        ctk.CTkLabel(self.frame_login, text="Contraseña", text_color=fg_text)\
            .grid(row=rr, column=0, pady=(0, 2), sticky="w"); rr += 1

        pass_wrap = ctk.CTkFrame(self.frame_login, fg_color="transparent")
        pass_wrap.grid(row=rr, column=0, pady=(0, 2), sticky="ew")
        pass_wrap.grid_columnconfigure(0, weight=1)

        self.en_pass = ctk.CTkEntry(
            pass_wrap, height=44, corner_radius=12, show="*",
            fg_color=fg_input, text_color=fg_text,
            border_width=2, border_color=fg_divider,
            placeholder_text="********",
            placeholder_text_color="#4F4F4F"
        )
        self.en_pass.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._decorate_entry(self.en_pass)

        ctk.CTkButton(
            pass_wrap, text="👁", width=44, height=44, corner_radius=12,
            fg_color=fg_divider, hover_color=fg_input, text_color=fg_text,
            command=self._toggle_pass
        ).grid(row=0, column=1, sticky="e")

 
        msg_wrap = ctk.CTkFrame(self.frame_login, fg_color="transparent")
        msg_wrap.grid(row=rr+1, column=0, sticky="w", pady=(6, 6))
        ctk.CTkLabel(msg_wrap, text="¿No tienes un perfil administrador", text_color=fg_muted,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            msg_wrap, text="Crea uno",
            fg_color="transparent",
            hover_color=fg_divider,
            text_color=self.PLACEHOLDER_YELLOW,
            font=ctk.CTkFont(size=11, weight="bold", underline=True),
            command=lambda: self._switch_mode("REG")
        ).grid(row=0, column=1, padx=(6, 0), sticky="w")


        self.cb_remember = ctk.CTkCheckBox(
            self.frame_login, text="Recordar usuario",
            text_color=fg_text,
            fg_color=fg_input, border_color=fg_divider, hover_color=fg_divider
        )
        self.cb_remember.grid(row=rr+2, column=0, pady=(0, 6), sticky="w")

        ctk.CTkButton(
            self.frame_login, text="¿Olvidaste tu contraseña",
            height=30, corner_radius=8,
            fg_color="transparent", hover_color=fg_divider,
            text_color=fg_muted,
            command=lambda: messagebox.showinfo("Ayuda", "Contacta al administrador del sistema.")
        ).grid(row=rr+2, column=0, pady=(0, 4), sticky="e")

        # =================== REG FRAME ===================
        self.frame_reg = ctk.CTkFrame(content, fg_color="transparent")
        self.frame_reg.grid_forget()
        self.frame_reg.grid_columnconfigure((0, 1), weight=1)

        # ✅ Link "¿ya tienes cuenta" JUSTO ARRIBA del formulario
        reg_link = ctk.CTkFrame(self.frame_reg, fg_color="transparent")
        reg_link.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 0))
        ctk.CTkLabel(reg_link, text="¿Ya tienes una cuenta", text_color=fg_muted,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            reg_link, text="Ingresa aquí",
            fg_color="transparent", hover_color=fg_divider,
            text_color=self.PLACEHOLDER_YELLOW,
            font=ctk.CTkFont(size=11, weight="bold", underline=True),
            command=lambda: self._switch_mode("LOGIN")
        ).grid(row=0, column=1, padx=(1, 0), sticky="w")

        r2 = 1

        ctk.CTkLabel(self.frame_reg, text="Nombre", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 1), sticky="w")
        ctk.CTkLabel(self.frame_reg, text="Cédula", text_color=fg_text)\
            .grid(row=r2, column=1, padx=(10, 0), pady=(0, 1), sticky="w"); r2 += 1

        self.ca_nombre = ctk.CTkEntry(
            self.frame_reg, height=40, fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider,
            placeholder_text="Ana María Pérez",
            placeholder_text_color="#4F4F4F",
            validate="key", validatecommand=v_nombre
        )
        self.ca_cedula = ctk.CTkEntry(
            self.frame_reg, height=40, fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider,
            placeholder_text="1032456789",
            placeholder_text_color="#4F4F4F",
            validate="key", validatecommand=v_cedula
        )
        self.ca_nombre.grid(row=r2, column=0, padx=(0, 10), pady=(0, 2), sticky="ew")
        self.ca_cedula.grid(row=r2, column=1, padx=(10, 0), pady=(0, 2), sticky="ew"); r2 += 1
        self._decorate_entry(self.ca_nombre); self._decorate_entry(self.ca_cedula)

        ctk.CTkLabel(self.frame_reg, text="Usuario", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 2), sticky="w")
        ctk.CTkLabel(self.frame_reg, text="Correo", text_color=fg_text)\
            .grid(row=r2, column=1, padx=(10, 0), pady=(0, 2), sticky="w"); r2 += 1

        self.ca_usuario = ctk.CTkEntry(
            self.frame_reg, height=40, fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider,
            placeholder_text="aperez",
            placeholder_text_color="#4F4F4F",
            validate="key", validatecommand=v_usuario
        )
        self.ca_email = ctk.CTkEntry(
            self.frame_reg, height=40, fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider,
            placeholder_text="ana.perez@cea-haro.com",
            placeholder_text_color="#4F4F4F",
            validate="key", validatecommand=v_email
        )
        self.ca_usuario.grid(row=r2, column=0, padx=(0, 10), pady=(0, 2), sticky="ew")
        self.ca_email.grid(row=r2, column=1, padx=(10, 0), pady=(0, 2), sticky="ew"); r2 += 1
        self._decorate_entry(self.ca_usuario); self._decorate_entry(self.ca_email)

        ctk.CTkLabel(self.frame_reg, text="Contraseña", text_color=fg_text)\
            .grid(row=r2, column=0, padx=(0, 10), pady=(0, 0), sticky="w"); r2 += 1

        # ✅ reglas contraseña (cerca del campo)
        self.lbl_pass_rules = ctk.CTkLabel(
            self.frame_reg,
            text="La contraseña debe tener mínimo 8 caracteres e incluir letras y números.",
            text_color=fg_muted,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_pass_rules.grid(row=r2, column=0, columnspan=2, sticky="w", pady=(0, 0)); r2 += 1
        self.lbl_pass_rules.configure(
            text="Minimo 8 caracteres con letras y numeros.",
            justify="left",
            wraplength=340
        )

        self.ca_pass1 = ctk.CTkEntry(
            self.frame_reg, height=40, fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider, show="*",
            placeholder_text="Mín. 8 caracteres (letras y números)",
            placeholder_text_color="#4F4F4F"
        )
        self.ca_pass1.grid(row=r2, column=0, columnspan=2, pady=(0, 3), sticky="ew"); r2 += 1
        self._decorate_entry(self.ca_pass1)

        self.pw_bar_reg = ctk.CTkProgressBar(self.frame_reg, height=8)
        self.pw_bar_reg.grid(row=r2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.pw_bar_reg.set(0.05)
        self.pw_bar_reg.configure(progress_color="#ff4c4c"); r2 += 1

        self.pw_lbl_reg = ctk.CTkLabel(self.frame_reg, text="Seguridad: Muy débil",
                                       text_color="#ff4c4c", font=ctk.CTkFont(size=10))
        self.pw_lbl_reg.grid(row=r2, column=0, columnspan=2, sticky="w", pady=(0, 2)); r2 += 1
        self.ca_pass1.bind("<KeyRelease>", lambda _e: self._update_strength_meter(
            self.ca_pass1.get(), self.pw_bar_reg, self.pw_lbl_reg
        ))

        # OTP block (oculto) - se muestra después de enviar
        self.otp_block = ctk.CTkFrame(self.frame_reg, fg_color="transparent")
        self.otp_block.grid(row=r2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.otp_block.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.otp_block, text="Código de verificación (OTP)", text_color=fg_text)\
            .grid(row=0, column=0, pady=(0, 2), sticky="w")

        self.lbl_otp_help = ctk.CTkLabel(
            self.otp_block,
            text="Primero escribe un correo vÃ¡lido. Luego pulsa Solicitar OTP, revisa tu correo e ingresa el cÃ³digo para validar la cuenta antes de crearla.",
            text_color=fg_muted,
            justify="left",
            wraplength=360,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_otp_help.grid_forget()

        self.otp_help_row = ctk.CTkFrame(self.otp_block, fg_color="transparent")
        self.otp_help_row.grid(row=1, column=0, sticky="w", pady=(0, 3))

        self.lbl_otp_help = ctk.CTkLabel(
            self.otp_help_row,
            text="Solicita tu OTP para crear el administrador",
            text_color=fg_muted,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_otp_help.grid(row=0, column=0, sticky="w")

        self.btn_send_otp = ctk.CTkButton(
            self.otp_help_row,
            text="solicitalo aqui",
            fg_color="transparent",
            hover_color=fg_divider,
            text_color=self.PLACEHOLDER_YELLOW,
            font=ctk.CTkFont(size=11, weight="bold", underline=True),
            width=100,
            height=24,
            command=self._request_registration_otp
        )
        self.btn_send_otp.grid(row=0, column=1, padx=(6, 0), sticky="w")

        self.en_otp = ctk.CTkEntry(
            self.otp_block, height=44,
            fg_color=fg_input, text_color=fg_text,
            border_color=fg_divider,
            placeholder_text="Ingresa el código del correo",
            placeholder_text_color="#4F4F4F"
        )
        self.en_otp.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self._decorate_entry(self.en_otp)
        self.en_otp.configure(
            placeholder_text="123456",
            justify="center",
            validate="key",
            validatecommand=v_otp
        )

        self.lbl_otp_status = ctk.CTkLabel(
            self.otp_block,
            text="",
            text_color=fg_muted,
            justify="left",
            wraplength=360,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_otp_status.grid(row=3, column=0, sticky="w", pady=(2, 0))

        # ===== Error / info (fila 2) - panel centrado con borde (reserva espacio) =====
        self.err_box = ctk.CTkFrame(
            right,
            fg_color=("white", "#151517"),
            corner_radius=12,
            border_width=0,  # empieza sin borde
            border_color=("#FCA5A5", "#7F1D1D")
        )
        self.err_box.grid(row=2, column=0, padx=20, pady=(4, 6), sticky="ew")
        self.err_box.grid_columnconfigure(0, weight=1)
        self.err_box.grid_remove()

        self.err = ctk.CTkLabel(
            self.err_box,
            text="",
            text_color=("#B91C1C", "#FCA5A5"),
            justify="center",
            anchor="center",
            wraplength=380,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.err.grid(row=0, column=0, padx=12, pady=10, sticky="ew")

        # ===== Acciones (fila 3) =====
        self.actions_login = ctk.CTkFrame(right, fg_color="transparent")
        self.actions_login.grid(row=3, column=0, padx=20, pady=(4, 8), sticky="ew")
        self.actions_login.grid_columnconfigure(0, weight=1)

        # ✅ Botón Ingresar: borde rojo + texto rojo; hover amarillo (sin borde) + texto negro
        self.btn_accept = ctk.CTkButton(
            self.actions_login,
            text="Ingresar",
            height=44,
            corner_radius=12,
            fg_color="white",
            text_color=fg_red,
            border_width=2,
            border_color=fg_red,
            hover=False,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._ok
        )
        self.btn_accept.grid(row=0, column=0, sticky="ew")

        self.btn_accept.bind("<Enter>", lambda _e: self.btn_accept.configure(
            fg_color="#FACC15", text_color="#000000", border_width=0
        ))
        self.btn_accept.bind("<Leave>", lambda _e: self.btn_accept.configure(
            fg_color="white", text_color=fg_red, border_width=2, border_color=fg_red
        ))

        # Registro actions
        self.actions_reg = ctk.CTkFrame(right, fg_color="transparent")
        self.actions_reg.grid_columnconfigure(0, weight=1)

        # ✅ Botón Guardar: mismo estilo que Ingresar
        self.btn_guardar_enviar = ctk.CTkButton(
            self.actions_reg,
            text="Crear cuenta",
            height=44,
            corner_radius=12,
            fg_color="white",
            text_color=fg_red,
            border_width=2,
            border_color=fg_red,
            hover=False,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._create_admin_with_otp
        )
        self.btn_guardar_enviar.grid(row=0, column=0, sticky="ew")

        self.btn_guardar_enviar.bind("<Enter>", lambda _e: self.btn_guardar_enviar.configure(
            fg_color="#FACC15", text_color="#000000", border_width=0
        ))
        self.btn_guardar_enviar.bind("<Leave>", lambda _e: self.btn_guardar_enviar.configure(
            fg_color="white", text_color=fg_red, border_width=2, border_color=fg_red
        ))

        # ==== eventos ====
        self.bind("<Return>", lambda _e: self._enter_action())
        # ocultar error al cambiar de vista (reg/login) y al click general
        self.bind_all("<Button-1>", self._hide_error_on_any_click, add="+")
        self.bind("<Unmap>", lambda _e: self._clear_error_ui(), add="+")  # minimizar -> limpia

        # enfoque inicial
        self.en_user.focus_set()
        self._switch_mode("LOGIN")


    def _on_login_unmap(self, event=None):
        # En Windows, <Unmap> se dispara al minimizar
        try:
            if self.state() == "iconic" and self.app.winfo_exists():
                self._disable_login_modal()
                self.app.iconify()
        except Exception:
            pass

    def _on_login_map(self, event=None):
        # Se dispara al restaurar
        try:
            if self.app.winfo_exists() and self.app.state() == "iconic":
                self.app.deiconify()
                self.app.lift()
            if self.state() != "iconic":
                self._enable_login_modal()
        except Exception:
            pass

    def _enable_login_modal(self):
        if getattr(self, "_login_modal_active", False):
            return
        try:
            self.grab_set()
            self._login_modal_active = True
        except Exception:
            self._login_modal_active = False

    def _disable_login_modal(self):
        if not getattr(self, "_login_modal_active", False):
            return
        try:
            self.grab_release()
        except Exception:
            pass
        self._login_modal_active = False


    # ====================== Async helper ======================
    def _run_async(self, fn, on_ok=None, on_err=None):
        def runner():
            try:
                result = fn()
                if on_ok:
                    self.after(0, lambda r=result: on_ok(r))
            except Exception as exc:
                if on_err:
                    self.after(0, lambda err=exc: on_err(err))
                else:
                    self.after(0, lambda err=exc: self._show_error(technical=str(err)))
        threading.Thread(target=runner, daemon=True).start()

    def _is_smtp_error(self, err_text: str) -> bool:
        t = (err_text or "").lower()
        return (
            "smtp" in t
            or "mail server connection failed" in t
            or "app password" in t
            or "connect timed out" in t
        )

    def _probe_basic_credentials(self, user: str, password: str) -> bool:
        """
        Fallback para backends que aceptan Basic Auth con usuario,
        pero en /api/auth/login exigen correo.
        """
        if requests is None:
            return False

        try:
            if hasattr(self.api, "_join"):
                url = self.api._join("/api/estudiantes")
            else:
                base = str(getattr(self.app, "API_BASE_URL", "") or "").rstrip("/")
                if base.lower().endswith("/api"):
                    base = base[:-4]
                url = f"{base}/api/estudiantes"

            r = requests.get(url, auth=(user, password), timeout=12)
            if r.status_code < 400:
                return True

            if hasattr(self.api, "last_error"):
                self.api.last_error = f"HTTP {r.status_code} en {url}: {r.text}"
            return False
        except Exception as e:
            if hasattr(self.api, "last_error"):
                self.api.last_error = f"Error de red hacia {url}: {e}"
            return False

    def _create_admin_directly(self):
        """
        Fallback: crea administrador sin OTP cuando el servicio SMTP no está disponible.
        """
        if not self._pending_admin_payload:
            self._show_error("No hay datos pendientes para crear el administrador.")
            return

        def do_create():
            data = self.api.post(self.ADMIN_ENDPOINT, json=self._pending_admin_payload)
            if data is None:
                raise RuntimeError(self.api.last_error or "No se pudo crear el usuario.")
            return data

        def on_ok(_):
            messagebox.showinfo(
                "Bienvenido",
                "✅ Cuenta creada exitosamente.",
                parent=self
            )
            self._reset_fields(True)
            self._switch_mode("LOGIN")
            try:
                self._set_registration_buttons_state(True)
            except Exception:
                pass

        def on_err(err):
            self._show_error(technical=str(err))
            try:
                self._set_registration_buttons_state(True)
            except Exception:
                pass

        self._run_async(do_create, on_ok=on_ok, on_err=on_err)

    # ====================== UI helpers ======================
    def _decorate_entry(self, entry):
        normal = {"border_color": "#E5E7EB"}
        focus  = {"border_color": "#FFC107"}
        try:
            entry.configure(border_width=2, **normal)
            entry.bind("<FocusIn>",  lambda _e: entry.configure(**focus))
            entry.bind("<FocusOut>", lambda _e: entry.configure(**normal))
        except Exception:
            pass

    def _hide_error_on_any_click(self, _event=None):
        # solo limpia si está visible con texto
        if getattr(self, "_err_lock", False):
            return
        self._clear_error_ui()

    def _clear_error_ui(self):
        try:
            self.err.configure(text="")
            self.err_box.configure(border_width=0)
            self.err_box.grid_remove()
        except Exception:
            pass

    def _show_error(self, msg=None, *, technical=None):
        tech = (technical or msg or "").strip()
        title, user_msg, _sev = self._classify_error(tech)

        try:
            self.err_box.grid()
            self.err.configure(text=user_msg)
            self.err_box.configure(border_width=2)
            self._err_lock = True
            self.after(300, lambda: setattr(self, "_err_lock", False))
        except Exception:
            messagebox.showerror(title, user_msg, parent=self)

    def _classify_error(self, technical_err: str):
        """
        Devuelve: (titulo, mensaje_usuario, severity)
        severity: 'user' | 'system'
        """
        t = (technical_err or "").lower()

        # Mensajes de negocio/backend comunes en este flujo
        if "usuario ya existe" in t:
            return ("Registro", "Ese usuario ya existe. Usa otro nombre de usuario.", "user")

        if "correo ya existe" in t or "email ya existe" in t:
            return ("Registro", "Ese correo ya está registrado. Usa otro correo.", "user")

        if "mail server connection failed" in t or "smtp" in t or "app password" in t:
            return (
                "Correo no disponible",
                "No se pudo enviar el código OTP porque el servicio de correo no está disponible. Intenta más tarde o contacta al administrador.",
                "system",
            )

        if "send.email" in t:
            return ("Correo", "No fue posible validar el correo para enviar el OTP. Verifica el formato del correo.", "user")

        if (
            "http 401" in t
            or "unauthorized" in t
            or "no autorizado" in t
            or "credenciales invalidas" in t
            or "credenciales inválidas" in t
            or "incorrect password" in t
            or "bad credentials" in t
        ):
            return ("Acceso", "Correo o contraseña inválidos.", "user")

        if "código inválido" in t or "codigo invalido" in t or "vencido" in t:
            return ("Verificación", "El código es inválido o ya venció. Solicita uno nuevo e inténtalo otra vez.", "user")

        if "correo inválido" in t or "correo invalido" in t or "email inválido" in t or "email invalido" in t:
            return ("Datos", "El correo no es válido. Verifica el formato e inténtalo nuevamente.", "user")

        if "usuario inválido" in t or "usuario invalido" in t:
            return ("Datos", "El usuario no es válido. Revisa que cumpla los requisitos.", "user")

        if "contraseña" in t and ("mínimo" in t or "minimo" in t or "debe" in t):
            return ("Datos", "La contraseña no cumple los requisitos. Revisa la longitud y vuelve a intentarlo.", "user")

        if "bad request" in t or "http 400" in t:
            return ("Datos", "Hay un dato inválido o faltante. Revisa la información e inténtalo de nuevo.", "user")

        if "http 500" in t:
            return ("Error del sistema", "Ocurrió un problema interno. Intenta nuevamente y, si persiste, contacta a soporte.", "system")

        if "http 404" in t:
            return ("Servicio no disponible", "No se encontró el servicio. Si el problema continúa, contacta a soporte.", "system")

        if "http 502" in t or "http 503" in t or "http 504" in t:
            return ("Servicio no disponible", "El servidor no está disponible en este momento. Intenta más tarde.", "system")

        if "timeout" in t:
            return ("Conexión", "La conexión tardó demasiado. Revisa tu internet e inténtalo nuevamente.", "system")

        if "connection" in t or "error de red" in t or "failed to establish" in t:
            return ("Conexión", "No fue posible conectarse al servidor. Verifica que la API esté encendida.", "system")

        return ("Error", "No se pudo completar la operación. Intenta de nuevo.", "system")

    # ====================== Login / Registro flow ======================
    def _switch_mode(self, mode):
       
        self._clear_error_ui()

        if mode == "REG":
            self.modo.set("REG")
            self.lbl_title.configure(text="Registrar administrador")
            self.lbl_help.configure(text="")
            self.lbl_help.grid_remove()

            self.frame_login.grid_forget()
            self.frame_reg.grid(row=0, column=0, sticky="nsew")

            self.actions_login.grid_forget()
            self.actions_reg.grid(row=3, column=0, padx=20, pady=(2, 6), sticky="ew")

            # reset otp ui
            try:
                
                self.en_otp.delete(0, "end")
            except Exception:
                pass
            try:
                self._set_registration_buttons_state(True)
            except Exception:
                pass
            self._pending_admin_payload = None
            self._otp_target_email = ""
            self._otp_verified_email = ""
            self._set_otp_status("")

        else:
            self.modo.set("LOGIN")
            self.lbl_title.configure(text="Bienvenido")
            self.lbl_help.configure(text="")
            self.lbl_help.grid_remove()

            self.frame_reg.grid_forget()
            self.frame_login.grid(row=0, column=0, sticky="nsew")

            self.actions_reg.grid_forget()
            self.actions_login.grid(row=3, column=0, padx=20, pady=(4, 8), sticky="ew")

    def _enter_action(self):
        if self.modo.get() == "REG":
            admin_otp_email = (self.ADMIN_OTP_EMAIL or "").strip().lower()
            if self.en_otp.get().strip() or self._otp_target_email == admin_otp_email:
                self._create_admin_with_otp()
            else:
                self._request_registration_otp()
        else:
            self._ok()

    def _toggle_pass(self):
        self._pass_visible = not getattr(self, "_pass_visible", False)
        self.en_pass.configure(show="" if self._pass_visible else "*")

    # ====================== OTP UI (popup) ======================
    def _show_otp_dialog(self):
        if self._otp_dialog_open:
            return
        self._otp_dialog_open = True

        dialog = ctk.CTkToplevel(self)
        dialog.title("Verificación")
        dialog.geometry("420x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        centrar_ventana(dialog, 420, 230)

        fg_panel = getattr(self.app, "COLOR_PANEL", ("#FFFFFF", "#151517"))
        dialog.configure(fg_color=fg_panel)

        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(
            container,
            text=f"📩 Código enviado al correo administrativo:\n{self.ADMIN_OTP_EMAIL}",
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="center"
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            container,
            text="Ingresa el código para continuar:",
            text_color="#111111"
        ).pack(pady=(0, 8))

        otp_entry = ctk.CTkEntry(
            container,
            height=40,
            corner_radius=10,
            placeholder_text="Ej: 123456",
            placeholder_text_color="#4F4F4F"
        )
        otp_entry.pack(fill="x", pady=(0, 15))
        otp_entry.focus_set()

        def close_dialog():
            self._otp_dialog_open = False
            try:
                dialog.destroy()
            except Exception:
                pass

        def verify_action():
            codigo = otp_entry.get().strip()
            if not codigo:
                messagebox.showerror("Error", "Debes ingresar el código.", parent=dialog)
                return
            close_dialog()
            self._verify_otp_and_create_with_code(codigo)

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame,
            text="Cerrar",
            fg_color="transparent",
            border_width=1,
            border_color="#E5E7EB",
            text_color="#000000",
            command=close_dialog
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Verificar",
            fg_color="#111827",
            text_color="#FFFFFF",
            command=verify_action
        ).pack(side="right", expand=True, fill="x", padx=(5, 0))

        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    # ====================== OTP send/verify helpers ======================
    def _set_otp_status(self, msg="", kind="info"):
        colors = {
            "info": "#111111",
            "success": "#2e7d32",
            "error": "#B91C1C",
        }
        try:
            self.lbl_otp_status.configure(text=msg, text_color=colors.get(kind, "#111111"))
        except Exception:
            pass

    def _set_registration_buttons_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget_name in ("btn_guardar_enviar", "btn_send_otp"):
            try:
                getattr(self, widget_name).configure(state=state)
            except Exception:
                pass

    def _build_pending_admin_payload(self):
        nombre = self.ca_nombre.get().strip()
        cedula = self.ca_cedula.get().strip()
        usuario = self.ca_usuario.get().strip()
        correo = self.ca_email.get().strip().lower()
        p1 = self.ca_pass1.get().strip()

        if not (nombre and cedula and usuario and correo and p1):
            raise ValueError("Completa nombre, cÃ©dula, usuario, correo y contraseÃ±a.")
        if not self._re_nombre_full.fullmatch(nombre):
            raise ValueError("Nombre invÃ¡lido.")
        if not self._re_cedula_full.fullmatch(cedula):
            raise ValueError("CÃ©dula invÃ¡lida.")
        if not self._re_usuario_full.fullmatch(usuario):
            raise ValueError("Usuario invÃ¡lido.")
        if not self._re_email_full.fullmatch(correo):
            raise ValueError("Correo invÃ¡lido.")
        if len(p1) < 8 or not re.search(r"[A-Za-z]", p1) or not re.search(r"[0-9]", p1):
            raise ValueError("La contraseÃ±a no cumple los requisitos.")

        otp_admin_email = (self.ADMIN_OTP_EMAIL or "").strip().lower()
        if self._otp_target_email and otp_admin_email and self._otp_target_email != otp_admin_email:
            self._otp_target_email = ""
        if self._otp_verified_email and otp_admin_email and self._otp_verified_email != otp_admin_email:
            self._otp_verified_email = ""
            self._set_otp_status("El correo cambiÃ³. Debes solicitar y verificar un nuevo OTP.", "info")

        self._pending_admin_payload = {
            "correo": correo,
            "cedula": cedula,
            "usuario": usuario,
            "contrasenaHash": p1,
            "nombre": nombre,
            "activo": True
        }
        return self._pending_admin_payload

    def _send_otp_to_email(self, correo: str) -> bool:
        correo = (correo or "").strip().lower()
        if not correo:
            self._show_error("Correo vacío.")
            return False

        data = self.api.post(self.OTP_SEND_ENDPOINT, json=correo)
        if data is not None:
            return True
        return False

    def _guardar_y_enviar_otp(self):
        self._clear_error_ui()

        try:
            nombre  = self.ca_nombre.get().strip()
            cedula  = self.ca_cedula.get().strip()
            usuario = self.ca_usuario.get().strip()
            correo  = self.ca_email.get().strip()
            p1      = self.ca_pass1.get().strip()

            if not (nombre and cedula and usuario and correo and p1):
                self._show_error("Completa nombre, cédula, usuario, correo y contraseña.")
                return
            if not self._re_nombre_full.fullmatch(nombre):
                self._show_error("Nombre inválido.")
                return
            if not self._re_cedula_full.fullmatch(cedula):
                self._show_error("Cédula inválida.")
                return
            if not self._re_usuario_full.fullmatch(usuario):
                self._show_error("Usuario inválido.")
                return
            if not self._re_email_full.fullmatch(correo):
                self._show_error("Correo inválido.")
                return
            if len(p1) < 8 or not re.search(r"[A-Za-z]", p1) or not re.search(r"[0-9]", p1):
                self._show_error("La contraseña no cumple los requisitos.")
                return

            contrasena_hex = hashlib.sha256(p1.encode("utf-8")).hexdigest()
            self._pending_admin_payload = {
                "correo": correo,
                "cedula": cedula,
                "usuario": usuario,
                "contrasenaHash": contrasena_hex,
                "nombre": nombre,
                "activo": True
            }

            try:
                self.btn_guardar_enviar.configure(state="disabled")
            except Exception:
                pass

            # Registro directo sin OTP (modo revisión)
            self._create_admin_directly()

        except Exception as e:
            self._show_error(technical=str(e))
            try:
                self.btn_guardar_enviar.configure(state="normal")
            except Exception:
                pass

    def _verify_otp_and_create_with_code(self, codigo):
        self._clear_error_ui()

        def do_verify():
            data = self.api.post(self.OTP_VERIFY_ENDPOINT, json={"email": self.ADMIN_OTP_EMAIL, "code": str(codigo).strip()})
            if data is None:
                raise RuntimeError(self.api.last_error or "Código inválido o vencido.")
            return True

        def on_ok(_):
            # crear admin
            data = self.api.post(self.ADMIN_ENDPOINT, json=self._pending_admin_payload)
            if data is None:
                raise RuntimeError(self.api.last_error or "No se pudo crear el usuario.")

            messagebox.showinfo(
                "Bienvenido",
                "✅ Verificación correcta.\n\nTu cuenta ha sido creada exitosamente.",
                parent=self
            )
            self._reset_fields(True)
            self._switch_mode("LOGIN")

        def on_err(err):
            messagebox.showerror("Verificación", self._classify_error(str(err))[1], parent=self)

        self._run_async(do_verify, on_ok=on_ok, on_err=on_err)

    def _verify_otp_and_create(self):
        codigo = self.en_otp.get().strip()
        if not codigo:
            self._show_error("Ingresa el código que llegó al correo.")
            return
        self._verify_otp_and_create_with_code(codigo)

    def _request_registration_otp(self):
        self._clear_error_ui()

        try:
            correo = (self.ADMIN_OTP_EMAIL or "").strip().lower()
            if not correo:
                raise ValueError("No hay correo configurado para el superadministrador.")
        except Exception as e:
            self._show_error(technical=str(e))
            return

        self._set_registration_buttons_state(False)
        self._set_otp_status("Enviando OTP al correo indicado...", "info")

        def do_send():
            data = self.api.post(self.OTP_SEND_ENDPOINT, json=correo)
            if data is None:
                raise RuntimeError(self.api.last_error or "No se pudo enviar el OTP.")
            return correo

        def on_ok(sent_email):
            self._otp_target_email = sent_email
            self._otp_verified_email = ""
            try:
                self.en_otp.delete(0, "end")
                self.en_otp.focus_set()
            except Exception:
                pass
            messagebox.showinfo(
                "OTP enviado",
                f"OTP enviado al correo del superadministrador:\n{sent_email}",
                parent=self
            )
            self._set_otp_status(
                f"Se envio un codigo a {sent_email}. Revisalo en ese correo, escribelo en este campo y luego pulsa Crear cuenta.",
                "success",
            )
            self._set_registration_buttons_state(True)

        def on_err(err):
            self._set_otp_status(self._classify_error(str(err))[1], "error")
            self._show_error(technical=str(err))
            self._set_registration_buttons_state(True)

        self._run_async(do_send, on_ok=on_ok, on_err=on_err)

    def _verify_otp_with_code(self, codigo):
        self._clear_error_ui()

        try:
            payload = self._build_pending_admin_payload()
        except Exception as e:
            self._show_error(technical=str(e))
            return

        correo = payload["correo"]
        if not self._otp_target_email or self._otp_target_email != correo:
            self._set_otp_status("Primero debes solicitar un OTP para este correo.", "error")
            self._show_error("Primero solicita el OTP del correo que deseas registrar.")
            return

        self._set_registration_buttons_state(False)
        self._set_otp_status("Verificando el codigo OTP...", "info")

        def do_verify():
            data = self.api.post(self.OTP_VERIFY_ENDPOINT, json={"email": correo, "code": str(codigo).strip()})
            if data is None:
                raise RuntimeError(self.api.last_error or "Codigo invalido o vencido.")
            return correo

        def on_ok(verified_email):
            self._otp_verified_email = verified_email
            self._set_otp_status(
                f"Correo verificado correctamente para {verified_email}. Ya puedes pulsar Crear cuenta.",
                "success",
            )
            self._set_registration_buttons_state(True)

        def on_err(err):
            self._set_otp_status(self._classify_error(str(err))[1], "error")
            self._show_error(technical=str(err))
            self._set_registration_buttons_state(True)

        self._run_async(do_verify, on_ok=on_ok, on_err=on_err)

    def _verify_otp(self):
        codigo = self.en_otp.get().strip()
        if not codigo:
            self._show_error("Ingresa el codigo que llego al correo.")
            self._set_otp_status("Debes escribir el codigo recibido para validar el correo.", "error")
            return
        self._verify_otp_with_code(codigo)

    def _create_admin_with_otp(self):
        self._clear_error_ui()

        try:
            payload = self._build_pending_admin_payload()
        except Exception as e:
            self._show_error(technical=str(e))
            return

        correo = (self.ADMIN_OTP_EMAIL or "").strip().lower()
        if self._otp_target_email != correo:
            self._set_otp_status("Primero solicita el OTP del correo del superadministrador.", "error")
            self._show_error("Primero solicita el OTP del correo del superadministrador.")
            return

        codigo = self.en_otp.get().strip()
        if len(codigo) != 6 or not codigo.isdigit():
            self._set_otp_status("Escribe el codigo OTP de 6 digitos antes de crear la cuenta.", "error")
            self._show_error("Ingresa un codigo OTP valido de 6 digitos.")
            return

        self._set_registration_buttons_state(False)

        def do_verify_and_create():
            verify = self.api.post(self.OTP_VERIFY_ENDPOINT, json={"email": correo, "code": codigo})
            if verify is None:
                raise RuntimeError(self.api.last_error or "Codigo invalido o vencido.")

            self._otp_verified_email = correo
            created = self.api.post(self.ADMIN_ENDPOINT, json=self._pending_admin_payload)
            if created is None:
                raise RuntimeError(self.api.last_error or "No se pudo crear el usuario.")
            return created

        def on_ok(_):
            self._set_otp_status("Correo verificado correctamente. La cuenta fue creada.", "success")
            messagebox.showinfo(
                "Bienvenido",
                "Cuenta creada exitosamente.",
                parent=self
            )
            self._reset_fields(True)
            self._switch_mode("LOGIN")

        def on_err(err):
            self._set_otp_status(self._classify_error(str(err))[1], "error")
            self._show_error(technical=str(err))
            self._set_registration_buttons_state(True)

        self._run_async(do_verify_and_create, on_ok=on_ok, on_err=on_err)

    # ====================== Login ======================
    def _credential_for_on_success(self, plain_password: str, hashed_password: str) -> str:
        mode = str(getattr(self.app, "AUTH_MODE", "basic") or "basic").strip().lower()
        # Para basic, enviar la clave en texto (el backend ya aplica su prehash interno).
        # Para jwt, mantenemos el hash SHA-256 que usa el endpoint /api/auth/login.
        return hashed_password if mode == "jwt" else plain_password

    def _ok(self):
        self._clear_error_ui()

        if self.modo.get() != "LOGIN":
            self._show_error("Estás en registro. Cambia a inicio de sesión para ingresar.")
            return

        correo = self._sanitize_login_for_submit(self.en_user.get().strip())
        p = self.en_pass.get().strip()
        if not correo or not p:
            self._show_error("Correo y contraseña son obligatorios.")
            return

        if not self._re_email_full.fullmatch(correo):
            self._show_error("Correo inválido.")
            return

        p_hex = hashlib.sha256(p.encode("utf-8")).hexdigest()
        on_success_secret = self._credential_for_on_success(p, p_hex)

        if callable(self.on_success):
            try:
                if hasattr(self.app, "_matches_superadmin") and self.app._matches_superadmin(correo, p):
                    self.on_success(correo, on_success_secret)
                    if hasattr(self.app, "api") and getattr(self.app.api, "last_error", None):
                        self._show_error(technical=str(self.app.api.last_error))
                        return
                    self._reset_fields(True)
                    self.grab_release()
                    self.destroy()
                    return

                # Valida credenciales por correo (contrato actual del backend).
                test = self.api.post(self.LOGIN_ENDPOINT, json={"correo": correo, "contrasena": p})
                if test is None:
                    self._show_error(technical=self.api.last_error or "Correo o contraseña inválidos.")
                    return

                try:
                    self.grab_release()
                except Exception:
                    pass
                self.on_success(correo, on_success_secret)
                if hasattr(self.app, "api") and getattr(self.app.api, "last_error", None):
                    self._show_error(technical=str(self.app.api.last_error))
                    return
                self._reset_fields(True)
                self.destroy()
                return
            except Exception as e:
                traceback.print_exc()
                self._show_error(technical=f"Error de autenticación: {e}")
                return

        data = self.api.post(self.LOGIN_ENDPOINT, json={"correo": correo, "contrasena": p})
        if data is None:
            self._show_error(technical=self.api.last_error or "Error desconocido")
            return

        self._reset_fields(True)
        self.grab_release()
        self.destroy()

    # ====================== Validación / fuerza ======================
    def _email_key_validator(self, new_text):
        for ch in new_text:
            if ch in self._danger_chars or ch.isspace():
                return False
        return True

    def _sanitize_login_for_submit(self, text):
        return "".join(ch for ch in text if ch not in self._danger_chars)

    def _password_strength_score(self, pwd):
        if not pwd:
            return 0
        score = 0
        if len(pwd) >= 8:
            score += 1
        if len(pwd) >= 12:
            score += 1
        if re.search(r"[A-Z]", pwd):
            score += 1
        if re.search(r"[a-z]", pwd) and re.search(r"[0-9]", pwd):
            score += 1
        if re.search(r"[^A-Za-z0-9]", pwd):
            score += 1
        return min(score, 4)

    def _strength_to_ui(self, score):
        mapping = {
            0: (0.05, "Muy débil", "#ff4c4c"),
            1: (0.25, "Débil", "#ff7a59"),
            2: (0.50, "Media", "#f4c542"),
            3: (0.75, "Fuerte", "#4caf50"),
            4: (1.00, "Muy fuerte", "#2e7d32")
        }
        return mapping.get(score, (0.05, "Muy débil", "#ff4c4c"))

    def _update_strength_meter(self, pwd, bar, lbl):
        val, text, color = self._strength_to_ui(self._password_strength_score(pwd))
        try:
            bar.set(val)
            bar.configure(progress_color=color)
            lbl.configure(text=f"Seguridad: {text}", text_color=color)
        except Exception:
            pass

    def _reset_fields(self, clear_errors=True):
        try:
            self.en_user.delete(0, "end")
            self.en_pass.delete(0, "end")
            self.cb_remember.deselect()

            for w in ("ca_nombre", "ca_cedula", "ca_usuario", "ca_email", "ca_pass1"):
                if hasattr(self, w):
                    getattr(self, w).delete(0, "end")

            if hasattr(self, "pw_bar_reg"):
                self.pw_bar_reg.set(0.05)
            if hasattr(self, "pw_lbl_reg"):
                self.pw_lbl_reg.configure(text="Seguridad: Muy débil", text_color="#ff4c4c")

            self._pending_admin_payload = None
            self._otp_target_email = ""
            self._otp_verified_email = ""

            try:
                self.en_otp.delete(0, "end")
            except Exception:
                pass
            try:
                self._set_otp_status("")
            except Exception:
                pass
            try:
                self._set_registration_buttons_state(True)
            except Exception:
                pass

            if clear_errors:
                self._clear_error_ui()
        except Exception:
            pass

    # ====================== Icono y recursos ======================
    def set_window_icon(self, window=None):
        win = window or self
        ico = self._resolve_existing_path(self._ICON_ICO_PATH)
        png = self._resolve_existing_path(self._ICON_PNG_PATH)

        try:
            if sys.platform.startswith("win") and ico:
                win.iconbitmap(str(ico))
                print("[OK] Icono .ico aplicado con iconbitmap")
                return
        except Exception as e:
            print(f"[Icono] iconbitmap falló: {e}")

        try:
            if png:
                from PIL import ImageTk
                img = Image.open(png)
                photo = ImageTk.PhotoImage(img)
                if not hasattr(self, "_icon_refs"):
                    self._icon_refs = []
                self._icon_refs.append(photo)
                win.iconphoto(True, photo)
                print("[OK] Icono PNG aplicado con iconphoto")
        except Exception as e:
            print(f"[Icono] iconphoto falló: {e}")

    def _resolve_existing_path(self, p: Path):
        try:
            if not isinstance(p, Path):
                p = Path(p)
            if p.exists():
                return p
            base = Path(getattr(sys, "_MEIPASS", SCRIPT_DIR))
            cand = base / p if not p.is_absolute() else base / p.name
            if cand.exists():
                return cand
            cand2 = SCRIPT_DIR / p.name
            return cand2 if cand2.exists() else None
        except Exception:
            return p if isinstance(p, Path) and p.exists() else None

    # ====================== Salida ======================
    def _quit_all(self):
        self._reset_fields(True)
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            if hasattr(self.app, "quit"):
                self.app.quit()
        except Exception:
            pass
        try:
            if hasattr(self.app, "destroy"):
                self.app.destroy()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

    def _cancel(self):
        self._quit_all()
