import customtkinter as ctk
from tkinter import messagebox
from utils import centrar_ventana

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
        bullets = ["Gestión integral de estudiantes"]
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
            right, text="¿Olvidaste tu contraseña?", height=28, corner_radius=8,
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
            cb(u, p)
            self.grab_release()
            self.destroy()
        except Exception as e:
            self._show_error(f"Error de autenticación:\n{e}")

    def _cancel(self):
        self.grab_release()
        self.destroy()
