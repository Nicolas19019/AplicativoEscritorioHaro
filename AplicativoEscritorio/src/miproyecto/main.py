import sys
import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

from utils import centrar_ventana
from api_client import ApiClient
from modules.login import LoginDialog


class HaroDesktopApp(ctk.CTk):
    # -------- Paleta (light, dark) -------- #
    # Blancos y grises base
    COLOR_BG          = ("#FAFBFC", "#0f0f10")   # fondo app (blanco muy suave / casi negro)
    COLOR_PANEL       = ("#FFFFFF", "#151517")   # paneles (sidebar/topbar)
    COLOR_DIVIDER     = ("#EFF1F5", "#23262b")   # divisores / líneas
    COLOR_INPUT_BG    = ("#F6F7F9", "#1b1d22")   # campos de búsqueda
    COLOR_TEXT        = ("#111111", "#F5F7FA")   # texto principal
    COLOR_MUTED       = ("#5A5F6A", "#AAB2C0")   # texto atenuado

    # Rojos (suaves + acción)
    RED_SOFT_BG       = ("#FEF2F2", "#2a1515")   # fondo/hover sutil
    RED_SOFT_BORDER   = ("#FDE3E3", "#3a1f1f")
    COLOR_RED         = ("#E53935", "#ff4c4c")   # acción/danger
    RED_HOVER         = ("#D7322F", "#ff5f5f")
    GREEN_SOFT_BG     = RED_SOFT_BG
    GREEN_SOFT_BORDER = RED_SOFT_BORDER
    COLOR_GREEN       = COLOR_RED
    GREEN_HOVER       = ("#D4A017", "#E0B43F")
    BLUE_SOFT_BG      = ("#FFF8E1", "#2a2618")
    BLUE_SOFT_BORDER  = ("#F7EAC1", "#3a3420")
    COLOR_BLUE        = COLOR_RED
    BLUE_HOVER        = ("#D4A017", "#E0B43F")
    PURPLE_SOFT_BG    = ("#FFF8E1", "#2a2618")
    PURPLE_SOFT_BORDER = ("#F7EAC1", "#3a3420")
    COLOR_PURPLE      = COLOR_RED
    PURPLE_HOVER      = ("#D4A017", "#E0B43F")

   # Mostaza (sutil, no chillón)
    MUSTARD_SOFT_BG     = ("#FFF8E1", "#2a2618")
    MUSTARD_SOFT_BORDER = ("#F7EAC1", "#3a3420")
    MUSTARD_MAIN        = ("#D4A017", "#E0B43F")
    MUSTARD_HOVER       = ("#C29113", "#D1A737")

    # --- COMPATIBILIDAD LEGADA ---
    # Algunos módulos usan COLOR_YELLOW como hover de botones.
    # Alias al mostaza principal para no tocar esos módulos:
    COLOR_YELLOW = MUSTARD_MAIN


    APP_TITLE = "CEA HARO — Sistema de Información"
    APP_W, APP_H = 1210, 720
    SIDEBAR_W = 260
    TOPBAR_H  = 64

    # Marca y logof
    BRAND_TEXT = "CEA HARO"
    LOGO_SIZE  = (50, 40)

    # Ruta del logo (resuelta desde este archivo)
    _SCRIPT_DIR = Path(__file__).resolve().parent
    _LOGO_PATH  = _SCRIPT_DIR / "media" / "LogoHARO.png"
    _ICON_ICO_PATH = _SCRIPT_DIR / "media" / "LogoHARO.ico"
    _ICON_PNG_PATH = _SCRIPT_DIR / "media" / "LogoHARO.png"


    # API
    API_BASE_URL = "https://harorepositoty2-590358146556.europe-west1.run.app/api"
    AUTH_MODE = "basic"
    JWT_LOGIN_PATH = "auth/login"
    JWT_USER_FIELD = "username"
    JWT_PASS_FIELD = "password"
    JWT_TOKEN_FIELD = "token"
    API_TIMEOUT_SECONDS = 25
    GOOGLE_CALENDAR_ENABLED = False
    GOOGLE_CALENDAR_ENDPOINT = "calendar/reuniones"
    GOOGLE_CALENDAR_ID = "primary"
    GOOGLE_CALENDAR_TIMEZONE = "America/Bogota"

    API_USER_DEFAULT = ""
    API_PASS_DEFAULT = ""
    ADMIN_OTP_EMAIL = "haroacademiadecol@gmail.com"
    SUPERADMIN_EMAIL = "haroacademiadecol@gmail.com"
    SUPERADMIN_PASSWORD = "Harogestion2026"

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("dark-blue")

        self.title(self.APP_TITLE)
        self.geometry(f"{self.APP_W}x{self.APP_H}")
        centrar_ventana(self, self.APP_W, self.APP_H)

        # --- Ícono de la ventana / barra de tareas (cross-platform con fallback) ---
        self.set_window_icon(self)


        self.minsize(1060, 640)
        self.configure(fg_color=self.COLOR_BG)

        # Estado UI / credenciales
        self.current_view = None
        self.sidebar_visible = False
        self.logo_image = None
        self.api_user = None
        self.api_pass = None
        self.api: ApiClient | None = None
        self.is_superadmin = False
        self.views = {}
        self._view_factories = {}

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
        self._register_view_factories()

        # Ocultar sidebar inicialmente
        self.sidebar.grid_remove()
        self.grid_columnconfigure(0, minsize=0, weight=0)
        self.grid_columnconfigure(1, weight=1)


        # Mostrar login antes de todo
        self.withdraw()
        self.after(50, self._show_login)


    def minimizar(self):
        self.iconify()   # minimiza la ventana


    # ----------------------- Helpers de recursos ----------------------- #
    @staticmethod
    def resource_path(p) -> Path:
        p = Path(p)
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base) / p.name if p.is_file() else Path(base) / p
        return p

    def _resolve_existing_path(self, p: Path) -> Path:
        """Busca el recurso respetando PyInstaller (_MEIPASS) y retorna un Path existente o Path('') si no existe."""
        try:
            rp = self.resource_path(p)
            if Path(rp).exists():
                return Path(rp)
        except Exception:
            pass
        return Path("")  # inexistente

    def set_window_icon(self, window=None):
        """
        Aplica ícono a la ventana dada (o a self si no se pasa).
        1) En Windows: intenta .ico con iconbitmap (mejor integracion barra de tareas).
        2) En cualquier SO: usa iconphoto con PNG como fallback.
        """
        import tkinter as tk
        win = window or self

        ico = self._resolve_existing_path(self._ICON_ICO_PATH)
        png = self._resolve_existing_path(self._ICON_PNG_PATH)

        # 1) Windows: iconbitmap con .ico si existe
        try:
            if sys.platform.startswith("win") and ico:
                win.iconbitmap(str(ico))
                print("[OK] Icono .ico aplicado con iconbitmap")
                return
        except Exception as e:
            print(f"[Icono] iconbitmap falló: {e}")

        # 2) Fallback universal: iconphoto con PNG
        try:
            if png:
                from PIL import Image, ImageTk
                img = Image.open(png)
                photo = ImageTk.PhotoImage(img)
                # en Tk hay que mantener una referencia para que no lo recolecte GC
                if not hasattr(self, "_icon_refs"):
                    self._icon_refs = []
                self._icon_refs.append(photo)
                win.iconphoto(True, photo)
                print("[OK] Icono PNG aplicado con iconphoto")
            else:
                print("[Icono] No se encontró PNG de icono")
        except Exception as e:
            print(f"[Icono] iconphoto falló: {e}")


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
        for col in (0, 1, 2, 3, 4, 5, 6, 7):
            self.topbar.grid_columnconfigure(col, weight=0)
        self.topbar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            self.topbar, text="☰", width=44, height=36, corner_radius=10,
            fg_color=self.COLOR_INPUT_BG, hover_color=self.COLOR_DIVIDER,
            text_color=self.COLOR_TEXT, command=self._toggle_sidebar
        ).grid(row=0, column=0, padx=(12, 6), pady=12, sticky="w")

        self.brand_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.brand_frame.grid(row=0, column=1, padx=(6, 8), pady=0, sticky="w")
        self.brand_frame.grid_columnconfigure(0, weight=0)
        self.brand_frame.grid_columnconfigure(1, weight=0)

        self._load_fixed_logo()
        ctk.CTkLabel(self.brand_frame, image=self.logo_image, text="") \
            .grid(row=0, column=0, padx=(0, 8), pady=12, sticky="w")
        ctk.CTkLabel(
            self.brand_frame, text=self.BRAND_TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.COLOR_TEXT
        ).grid(row=0, column=1, padx=(0, 0), pady=12, sticky="w")

        # Entry de búsqueda con borde sutil y efecto focus mostaza
        self.search_entry = ctk.CTkEntry(
            self.topbar, placeholder_text="Buscar…  (Ctrl+F)",
            height=36, corner_radius=12, fg_color=self.COLOR_INPUT_BG,
            text_color=self.COLOR_TEXT, border_width=1, border_color=self.COLOR_DIVIDER
        )
        self.search_entry.grid(row=0, column=2, padx=(8, 8), pady=12, sticky="ew")
        self.search_entry.bind("<Return>", self._do_search)

        def _on_focus_in(_):
            self.search_entry.configure(border_color=self.MUSTARD_SOFT_BORDER)
        def _on_focus_out(_):
            self.search_entry.configure(border_color=self.COLOR_DIVIDER)
        self.search_entry.bind("<FocusIn>", _on_focus_in)
        self.search_entry.bind("<FocusOut>", _on_focus_out)

        # Botón primario (mostaza)
        ctk.CTkButton(
            self.topbar, text="⟳ Sincronizar", height=36, corner_radius=18,
            fg_color=self.MUSTARD_MAIN, hover_color=self.MUSTARD_HOVER,
            text_color="#111111", command=self._sync
        ).grid(row=0, column=4, padx=(8, 8), pady=12, sticky="e")

        # Neutro
        #ctk.CTkButton(
        #    self.topbar, text="● Tema", height=36, corner_radius=12,
        #    fg_color=self.COLOR_INPUT_BG, hover_color=self.COLOR_DIVIDER,
        #    text_color=self.COLOR_TEXT, command=self._toggle_theme
        #).grid(row=0, column=5, padx=(0, 12), pady=12, sticky="e")

        # Peligro (rojo)
        ctk.CTkButton(
            self.topbar, text="Cerrar sesión", height=36, corner_radius=12,
            fg_color=self.COLOR_RED, hover_color=self.RED_HOVER,
            text_color="#ffffff", command=self._logout
        ).grid(row=0, column=6, padx=(0, 12), pady=12, sticky="e")

    # ----------------------- Sidebar ----------------------- #
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=self.SIDEBAR_W, fg_color=self.COLOR_PANEL, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        for r in range(10):
            self.sidebar.grid_rowconfigure(r, weight=0)
        self.sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(
            self.sidebar, text="Módulos", text_color=self.COLOR_MUTED,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self.nav_buttons = {}

        def add_nav(row, name, icon):
            b = ctk.CTkButton(
                self.sidebar, text=f"{icon}  {name}", height=44, corner_radius=12,
                fg_color="transparent",
                hover_color=self.MUSTARD_SOFT_BG,
                text_color=self.COLOR_TEXT, anchor="w",
                border_color=self.MUSTARD_SOFT_BORDER,
                border_width=0,
                command=lambda n=name: self._nav_callback(n),
                font=ctk.CTkFont(size=14, weight="normal")
            )
            b.grid(row=row, column=0, padx=10, pady=6, sticky="ew")
            self.nav_buttons[name] = b

        specs = [
            ("Estudiantes", "👤"),
            ("Administradores", "🛡"),
            ("Instructores", "🧑‍🏫"),
            ("Vehículos", "🚗"),
            ("Clases", "📅"),
            ("Estados de Cuenta", "💳"),
            ("Reportes", "📊"),
        ]
        for i, (n, ic) in enumerate(specs, start=1):
            add_nav(i, n, ic)

        self._apply_nav_visibility()

        ctk.CTkFrame(self.sidebar, height=1, fg_color=self.COLOR_DIVIDER, corner_radius=0) \
            .grid(row=len(specs) + 1, column=0, padx=12, pady=(16, 8), sticky="ew")
        ctk.CTkLabel(
            self.sidebar, text="© CEA HARO\nSistema de Información",
            justify="left", text_color=self.COLOR_MUTED, font=ctk.CTkFont(size=11)
        ).grid(row=len(specs) + 2, column=0, padx=16, pady=(0, 12), sticky="sw")

    # ----------------------- Content ----------------------- #
    def _build_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color=self.COLOR_BG, corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self._loading_overlay = None
        self._loading_text = None

    def _show_loading(self, text="Cargando..."):
        try:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                if self._loading_text and self._loading_text.winfo_exists():
                    self._loading_text.configure(text=text)
                self._loading_overlay.lift()
                return

            self._loading_overlay = ctk.CTkFrame(
                self.content,
                fg_color=("#FFFFFF", "#151517"),
                corner_radius=16,
                border_width=1,
                border_color=self.COLOR_DIVIDER,
            )
            self._loading_overlay.place(relx=0.5, rely=0.08, anchor="n")

            self._loading_text = ctk.CTkLabel(
                self._loading_overlay,
                text=text,
                text_color=self.COLOR_TEXT,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            self._loading_text.pack(padx=18, pady=10)
            self._loading_overlay.lift()
        except Exception:
            pass

    def _hide_loading(self):
        try:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                self._loading_overlay.destroy()
        except Exception:
            pass
        self._loading_overlay = None
        self._loading_text = None

    def _register_view_factories(self):
        self._view_factories = {
            "Estudiantes": self._create_estudiantes_view,
            "Administradores": self._create_administradores_view,
            "Instructores": self._create_instructores_view,
            "Vehículos": self._create_vehiculos_view,
            "Clases": self._create_clases_view,
            "Estados de Cuenta": self._create_estados_cuenta_view,
            "Reportes": self._create_reportes_view,
        }
        self.views = {}

    def _create_estudiantes_view(self):
        from modules.estudiantes import EstudiantesView
        return EstudiantesView(self.content)

    def _create_administradores_view(self):
        from modules.administradores import AdministradoresView
        return AdministradoresView(self.content)

    def _create_instructores_view(self):
        from modules.instructores import InstructoresView
        return InstructoresView(self.content)

    def _create_vehiculos_view(self):
        from modules.vehiculos import VehiculosView
        return VehiculosView(self.content)

    def _create_clases_view(self):
        from modules.clases import ClasesView
        return ClasesView(self.content)

    def _create_estados_cuenta_view(self):
        from modules.estados_cuenta import EstadosCuentaView
        return EstadosCuentaView(self.content)

    def _create_reportes_view(self):
        from modules.reportes import ReportesView
        return ReportesView(self.content)

    def _show_login_error(self, msg: str):
        for w in self.winfo_children():
            if isinstance(w, LoginDialog):
                w._show_error(msg)
                return
        print(f"[WARN] {msg}")

    # ----------------------- Login / Sesión ----------------------- #

    def _show_login(self):
        self.login_window = LoginDialog(self, on_success=self._on_login_ok, brand=self.BRAND_TEXT)
        if self.API_USER_DEFAULT:
            self.login_window.en_user.insert(0, self.API_USER_DEFAULT)
        if self.API_PASS_DEFAULT:
            self.login_window.en_pass.insert(0, self.API_PASS_DEFAULT)

    def _matches_superadmin(self, user: str, password: str) -> bool:
        login = str(user or "").strip().lower()
        secret = str(password or "").strip()
        superadmin_email = str(self.SUPERADMIN_EMAIL or "").strip().lower()
        return login == superadmin_email and secret == str(self.SUPERADMIN_PASSWORD or "")

    def _apply_nav_visibility(self):
        btn = getattr(self, "nav_buttons", {}).get("Administradores")
        if not btn:
            return
        if getattr(self, "is_superadmin", False):
            btn.grid()
        else:
            btn.grid_remove()

    def _on_login_ok(self, user, password):
        from api_client import ApiClient

        try:
            self.api_user = user
            self.api_pass = password
            self.is_superadmin = self._matches_superadmin(user, password)
            self.api = ApiClient(
                self, self.API_BASE_URL, user, password,
                auth_mode=self.AUTH_MODE,
                jwt_login_path=self.JWT_LOGIN_PATH,
                user_field=self.JWT_USER_FIELD,
                pass_field=self.JWT_PASS_FIELD,
                token_field=self.JWT_TOKEN_FIELD,
                request_timeout=self.API_TIMEOUT_SECONDS
            )
        except Exception as e:
            self.api = None
            self.api_user = None
            self.api_pass = None
            self.is_superadmin = False
            self._show_login_error(f"No fue posible iniciar sesión: {e}")
            return

        self._apply_nav_visibility()
        self.deiconify()
        try:
            self.state("normal")
        except Exception:
            pass
        self.switch_view("Estudiantes")
        self.after(150, self._warm_api_cache_async)

    def _warm_api_cache_async(self):
        if not self.api:
            return

        # Prefetch de catalogos para evitar sensacion de recarga al abrir modulos.
        resources = ("profesores", "vehiculos", "clases-practicas", "estados-cuenta")

        def worker():
            unauthorized = False
            for resource in resources:
                try:
                    self.api.get_all(resource)
                except Exception as e:
                    msg = str(e)
                    if "HTTP 401" in msg or "No autorizado" in msg:
                        unauthorized = True
                        break
                    self._info(f"[cache] No se pudo precargar '{resource}': {e}")
            if unauthorized:
                self._info("[cache] Precarga omitida por sesion no autorizada.")

        threading.Thread(target=worker, daemon=True).start()

    def _logout(self):
        if messagebox.askyesno("Sesión", "¿Está seguro que desea salir"):
            self.api = None
            self.api_user = None
            self.api_pass = None
            self.is_superadmin = False
            self._apply_nav_visibility()
            if self.current_view:
                self.current_view.grid_remove()
                self.current_view = None
            for view in self.views.values():
                try:
                    view.destroy()
                except Exception:
                    pass
            self.views.clear()
            self.withdraw()
            self.after(50, self._show_login)

    # ----------------------- Navegación ----------------------- #
    def _nav_callback(self, name):
        self.switch_view(name)

    def switch_view(self, name: str):
        if name == "Administradores" and not getattr(self, "is_superadmin", False):
            messagebox.showwarning("Acceso restringido", "Solo el superadministrador puede ver esta vista.", parent=self)
            return
        if not self._view_factories:
            self._register_view_factories()

        factory = self._view_factories.get(name)
        if not factory:
            self._info(f"Vista '{name}' no encontrada")
            return

        self._show_loading(f"Cargando {name}...")
        view = self.views.get(name)
        if view is None:
            try:
                view = factory()
                self.views[name] = view
            except Exception as e:
                self._hide_loading()
                messagebox.showerror("Vista", f"No fue posible abrir '{name}':\n{e}", parent=self)
                return

        # limpiar estilo de todos
        for _, b in self.nav_buttons.items():
            b.configure(fg_color="transparent", text_color=self.COLOR_TEXT, border_width=0)

        # resaltar activo (suave mostaza)
        btn = self.nav_buttons.get(name)
        if btn:
            btn.configure(
                fg_color=self.MUSTARD_SOFT_BG,
                text_color=self.COLOR_TEXT,
                border_color=self.MUSTARD_SOFT_BORDER,
                border_width=1
            )

        if not view.winfo_ismapped():
            view.grid(row=0, column=0, sticky="nsew")
        view.tkraise()
        self.current_view = view
        self.after(120, self._hide_loading)

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
        if not self.api:
            self._info("No hay cliente API activo. Inicia sesión.")
            return

        self._info("Sincronizando datos con la base de datos...")
        self._show_loading("Sincronizando datos...")
        resources = ("estudiantes", "administradores", "profesores", "vehiculos", "clases-practicas", "estados-cuenta")

        def worker():
            errors = []
            try:
                self.api._cache_clear()
            except Exception:
                pass

            for resource in resources:
                try:
                    self.api.get_all(resource, force_refresh=True)
                except Exception as e:
                    errors.append(f"{resource}: {e}")

            def refresh_loaded_views():
                refreshed = 0
                for name, view in list(self.views.items()):
                    refresher = getattr(view, "_refrescar", None)
                    if not callable(refresher):
                        continue
                    try:
                        if hasattr(view, "_last_refresh_ts"):
                            view._last_refresh_ts = 0
                        try:
                            refresher(force_refresh=True)
                        except TypeError:
                            refresher()
                        refreshed += 1
                    except Exception as e:
                        errors.append(f"vista {name}: {e}")

                if errors:
                    self._info("Sincronización terminada con avisos:")
                    for err in errors[:5]:
                        self._info(f" - {err}")
                    if len(errors) > 5:
                        self._info(f" - ... {len(errors) - 5} error(es) adicional(es).")
                else:
                    self._info(f"Sincronización completada. Vistas actualizadas: {refreshed}.")
                self._hide_loading()

            self.after(0, refresh_loaded_views)

        threading.Thread(target=worker, daemon=True).start()

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
        print(msg)


if __name__ == "__main__":
    app = HaroDesktopApp()
    app.mainloop()
