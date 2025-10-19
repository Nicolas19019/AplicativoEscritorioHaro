import sys
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

from utils import centrar_ventana
from api_client import ApiClient
from modules.login import LoginDialog
from modules.estudiantes import EstudiantesView
from modules.instructores import InstructoresView
from modules.vehiculos import VehiculosView
from modules.clases import ClasesView
from modules.estados_cuenta import EstadosCuentaView
from modules.reportes import ReportesView


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

    # Marca y logo
    BRAND_TEXT = "CEA HARO"
    LOGO_SIZE  = (50, 40)

    # Ruta del logo (resuelta desde este archivo)
    _SCRIPT_DIR = Path(__file__).resolve().parent
    _LOGO_PATH  = _SCRIPT_DIR / "media" / "LogoHARO.png"

    # API
    API_BASE_URL = "http://localhost:8081/api"
    AUTH_MODE = "basic"
    JWT_LOGIN_PATH = "auth/login"
    JWT_USER_FIELD = "username"
    JWT_PASS_FIELD = "password"
    JWT_TOKEN_FIELD = "token"

    API_USER_DEFAULT = ""
    API_PASS_DEFAULT = ""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(self.APP_TITLE)
        self.geometry(f"{self.APP_W}x{self.APP_H}")
        centrar_ventana(self, self.APP_W, self.APP_H)

        # --- Ícono de la ventana / barra de tareas ---
        try:
            import tkinter as tk
            ico_path = self.resource_path(self._SCRIPT_DIR / "media" / "LogoHARO.ico")
            if ico_path.exists():
                self.iconbitmap(str(ico_path))
                print("[OK] Icono de ventana establecido correctamente.")
            else:
                print(f"[Icono] No se encontró el archivo: {ico_path}")
        except Exception as e:
            print(f"[Icono] Error al establecer ícono: {e}")

 
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
        dlg = LoginDialog(self, on_success=self._on_login_ok, brand=self.BRAND_TEXT)
        if self.API_USER_DEFAULT:
            dlg.en_user.insert(0, self.API_USER_DEFAULT)
        if self.API_PASS_DEFAULT:
            dlg.en_pass.insert(0, self.API_PASS_DEFAULT)

    def _on_login_ok(self, user, password):
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
        if messagebox.askyesno("Sesión", "¿Está seguro que desea salir?"):
            self.api = None
            self.api_user = None
            self.api_pass = None
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
        print(msg)


if __name__ == "__main__":
    app = HaroDesktopApp()
    app.mainloop()
