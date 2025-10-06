# main.py
# CEA HARO — App de Escritorio (CustomTkinter)
# Incluye las 6 opciones con sus ventanas dedicadas

import customtkinter as ctk
from tkinter import messagebox

APP_TITLE = "CEA HARO — Inicio"
APP_W, APP_H = 1280, 780

# -------- Paleta (light, dark) -------- #
BG           = ("#0B1020", "#050915")   # fondo principal
PANEL        = ("#0F162D", "#0A1124")   # paneles
TEXT         = ("#EAF2FF", "#EAF2FF")
TEXT_MUTED   = ("#98A2B3", "#9AA6B2")
CARD_BG      = ("#0E142A", "#0A1022")

# Acentos por tarjeta (color principal por opción)
CARDS = [
    ("Gestión de Estudiantes", "🎓", "#A855F7"),  # PLUM
    ("Instructores",           "👩‍🏫", "#F59E0B"),  # GOLD
    ("Vehículos",              "🚗",  "#38BDF8"),  # SKY
    ("Clases",                 "📚",  "#10B981"),  # MINT
    ("Estados de Cuenta",      "💳",  "#F43F5E"),  # ROSE
    ("Reportes",               "📊",  "#6366F1"),  # INDIGO
]

# ---------------------------------------------------------------------------

class HaroHome(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_W}x{APP_H}")
        self.minsize(1150, 680)

        ctk.set_appearance_mode("dark")   # base oscuro
        ctk.set_default_color_theme("dark-blue")

        # Grid raíz
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.configure(fg_color=BG)

        self.child_windows: list[ctk.CTkToplevel] = []

        self._build_topbar()
        self._build_hero()
        self._cards_area()
        self._build_statusbar()

        self.after(150, self._focus_first_card)

        # ESC: cierra ventana hija si hay, si no, vuelve a inicio (status)
        self.bind("<Escape>", self._on_esc)

    # ---------------- Topbar ---------------- #
    def _build_topbar(self):
        # Banda superior decorativa
        brand = ctk.CTkFrame(self, height=6, fg_color="#6EE7F9")
        brand.grid(row=0, column=0, sticky="new")

        top = ctk.CTkFrame(self, corner_radius=0, fg_color=PANEL)
        top.grid(row=0, column=0, sticky="nsew", pady=(6, 0))
        top.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            top, text="HARO • Centro de Enseñanza Automovilística",
            text_color=TEXT, font=ctk.CTkFont(size=22, weight="bold")
        )
        subtitle = ctk.CTkLabel(
            top, text="Inicio · Selecciona un módulo (1–6 o Alt+1–Alt+6)",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=13)
        )
        title.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        # Botón primario
        start_btn = ctk.CTkButton(
            top, text="Empezar",
            fg_color="#22D3EE", hover_color="#06B6D4", text_color="black",
            corner_radius=10, height=44, width=140,
            command=lambda: self._open("Gestión de Estudiantes"),
        )
        start_btn.grid(row=0, column=2, rowspan=2, padx=18, pady=12, sticky="e")

        # Switch modo
        self.dark_switch = ctk.CTkSwitch(
            top, text="Modo oscuro", command=self._toggle_mode,
            progress_color="#8B5CF6", fg_color="#1F2937", text_color=TEXT
        )
        self.dark_switch.select()  # inicia oscuro
        self.dark_switch.grid(row=0, column=3, rowspan=2, padx=(0, 18), pady=12, sticky="e")

    # ---------------- Hero ---------------- #
    def _build_hero(self):
        hero_wrap = ctk.CTkFrame(self, fg_color="transparent")
        hero_wrap.grid(row=1, column=0, sticky="ew", padx=18, pady=(10, 0))
        hero_wrap.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(hero_wrap, corner_radius=16, fg_color=("#0B1228", "#060B1A"))
        hero.grid(row=0, column=0, sticky="ew")
        hero.grid_columnconfigure(0, weight=1)

        h1 = ctk.CTkLabel(
            hero, text="Bienvenido 👋",
            text_color=TEXT, font=ctk.CTkFont(size=28, weight="bold")
        )
        h2 = ctk.CTkLabel(
            hero, text="Tu hub de gestión CEA HARO. Elige un módulo para empezar.",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=14)
        )
        h1.grid(row=0, column=0, padx=20, pady=(14, 2), sticky="w")
        h2.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

    # ---------------- Cards Area ---------------- #
    def _cards_area(self):
        area = ctk.CTkFrame(self, fg_color="transparent")
        area.grid(row=2, column=0, sticky="nsew")
        area.grid_rowconfigure(0, weight=1)
        area.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(
            area, fg_color=CARD_BG, corner_radius=18,
            label_text="Módulos del sistema",
            label_font=ctk.CTkFont(size=16, weight="bold"),
            label_text_color=TEXT
        )
        self.scroll.grid(row=0, column=0, padx=18, pady=12, sticky="nsew")

        # 6 tarjetas (siempre 3 columnas x 2 filas)
        self.cards = []
        for idx, (title, emoji, color) in enumerate(CARDS, start=1):
            frm = self._build_card(self.scroll, title, emoji, color, index=idx)
            self.cards.append((frm, title))

        self._reflow(ncols=3)

    def _build_card(self, parent, title, emoji, color, index: int):
        # Contenedor de tarjeta (más grande)
        card = ctk.CTkFrame(parent, corner_radius=18, fg_color=PANEL)
        card.grid_rowconfigure(6, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # Accento (barra arriba)
        accent = ctk.CTkFrame(card, height=8, corner_radius=8, fg_color=color)
        accent.grid(row=0, column=0, padx=18, pady=(18, 12), sticky="ew")

        # Ícono y título
        icon = ctk.CTkLabel(card, text=emoji, text_color=TEXT, font=ctk.CTkFont(size=60))
        icon.grid(row=1, column=0, pady=(0, 8))
        lbl = ctk.CTkLabel(card, text=title, text_color=TEXT, font=ctk.CTkFont(size=18, weight="bold"))
        lbl.grid(row=2, column=0, pady=(0, 4))

        sub = ctk.CTkLabel(
            card, text="Administra la información y acciones de este módulo.",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=13), wraplength=400, justify="center"
        )
        sub.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="ew")

        # Botón grande "Abrir"
        btn = ctk.CTkButton(
            card, text=f"Abrir ({index})", height=50, corner_radius=14,
            fg_color=color, hover_color=self._darken(color, 0.88),
            text_color="black" if self._is_light(color) else "white",
            command=lambda t=title: self._open(t)
        )
        btn.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="ew")

        # Hover sutil en el card
        def on_enter(_): card.configure(fg_color=self._mix(PANEL, color, 0.08))
        def on_leave(_): card.configure(fg_color=PANEL)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        # Atajos del 1–6
        self.bind(f"<Key-{index}>", lambda e, n=title: self._open(n))
        self.bind_all(f"<Alt-KeyPress-{index}>", lambda e, n=title: self._open(n))

        return card

    def _reflow(self, ncols=3):
        # Limpia colocación
        for frm, _ in self.cards:
            frm.grid_forget()

        # Distribuye 6 tarjetas en 3 columnas (2 filas)
        for i, (frm, _title) in enumerate(self.cards):
            r, c = divmod(i, ncols)  # ncols=3 -> 0..2 (2 filas)
            frm.grid(row=r, column=c, padx=18, pady=18, sticky="nsew")

        for c in range(ncols):
            self.scroll.grid_columnconfigure(c, weight=1, minsize=380)

    # ---------------- Statusbar ---------------- #
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=PANEL, height=46)
        bar.grid(row=3, column=0, sticky="nsew")
        bar.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            bar, text="Listo", text_color=TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=12)
        )
        self.status.grid(row=0, column=0, padx=16, pady=8, sticky="w")

    # ---------------- Behavior ---------------- #
    def _toggle_mode(self):
        is_dark = self.dark_switch.get()
        ctk.set_appearance_mode("dark" if is_dark else "light")
        self.status.configure(text="Modo: oscuro" if is_dark else "Modo: claro")

    def _open(self, name):
        self.status.configure(text=f"Abriste: {name}")

        # Mapa de ventanas por módulo
        windows_map = {
            "Gestión de Estudiantes": StudentsWindow,
            "Instructores":           InstructorsWindow,
            "Vehículos":              VehiclesWindow,
            "Clases":                 ClassesWindow,
            "Estados de Cuenta":      AccountsWindow,
            "Reportes":               ReportsWindow,
        }
        cls = windows_map.get(name, ModuleWindow)  # fallback
        win = cls(self, name)
        self.child_windows.append(win)
        win.bind("<Destroy>", lambda e, w=win: self._on_child_close(w))

    def _on_child_close(self, win):
        if win in self.child_windows:
            self.child_windows.remove(win)
        self.status.configure(text="Volviste a Inicio")

    def _on_esc(self, _evt=None):
        # Si hay ventanas hijas, cierra la última
        if self.child_windows:
            self.child_windows[-1].destroy()
            return
        # Si no hay hijas, solo feedback
        self.status.configure(text="Volviste a Inicio")

    def _focus_first_card(self):
        if hasattr(self, "cards") and self.cards:
            try:
                widgets = self.cards[0][0].winfo_children()
                for w in widgets[::-1]:
                    if isinstance(w, ctk.CTkButton):
                        w.focus_set()
                        return
            except Exception:
                pass

    # ---- Helpers de color ---- #
    def _is_light(self, hexcolor: str) -> bool:
        r, g, b = self._hex_to_rgb(hexcolor)
        return (0.299*r + 0.587*g + 0.114*b) > 186

    def _darken(self, hexcolor: str, factor: float) -> str:
        r, g, b = self._hex_to_rgb(hexcolor)
        r, g, b = int(r*factor), int(g*factor), int(b*factor)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _mix(self, base_hex: tuple[str, str] | str, accent_hex: str, alpha: float) -> str:
        if isinstance(base_hex, tuple):
            base_hex = base_hex[0]
        br, bg, bb = self._hex_to_rgb(base_hex)
        ar, ag, ab = self._hex_to_rgb(accent_hex)
        r = int((1-alpha)*br + alpha*ar)
        g = int((1-alpha)*bg + alpha*ag)
        b = int((1-alpha)*bb + alpha*ab)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _hex_to_rgb(self, hexcolor: str):
        hexcolor = hexcolor.lstrip("#")
        return tuple(int(hexcolor[i:i+2], 16) for i in (0, 2, 4))

# ---------------------------------------------------------------------------
# Ventana base
# ---------------------------------------------------------------------------

class ModuleWindow(ctk.CTkToplevel):
    """Ventana hija base para cada módulo."""
    def __init__(self, master: HaroHome, title: str):
        super().__init__(master)
        self.title(title)
        self.geometry("980x640")
        self.minsize(860, 560)
        self.configure(fg_color=("#0B1228", "#060B1A"))

        # Cerrar con ESC
        self.bind("<Escape>", lambda _e: self.destroy())

        # Layout
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=("#0F162D", "#0A1124"))
        header.grid(row=0, column=0, sticky="new")
        header.grid_columnconfigure(1, weight=1)

        h1 = ctk.CTkLabel(header, text=title, text_color=TEXT, font=ctk.CTkFont(size=20, weight="bold"))
        h1.grid(row=0, column=0, padx=18, pady=12, sticky="w")

        search = ctk.CTkEntry(header, placeholder_text="Buscar…", height=36, width=280)
        search.grid(row=0, column=1, padx=8, pady=12, sticky="e")

        close_btn = ctk.CTkButton(header, text="Cerrar (Esc)", width=140, height=36, corner_radius=10,
                                  fg_color="#F43F5E", hover_color="#E11D48",
                                  command=self.destroy)
        close_btn.grid(row=0, column=2, padx=12, pady=12, sticky="e")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=("#0E142A", "#0A1022"))
        toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 6))
        for i in range(6):
            toolbar.grid_columnconfigure(i, weight=0)
        toolbar.grid_columnconfigure(6, weight=1)

        self.btn_new = ctk.CTkButton(toolbar, text="Nuevo", width=120, height=38, corner_radius=10)
        self.btn_edit = ctk.CTkButton(toolbar, text="Editar", width=120, height=38, corner_radius=10)
        self.btn_delete = ctk.CTkButton(toolbar, text="Eliminar", width=120, height=38, corner_radius=10)
        self.btn_refresh = ctk.CTkButton(toolbar, text="Refrescar", width=120, height=38, corner_radius=10)
        self.btn_export = ctk.CTkButton(toolbar, text="Exportar", width=120, height=38, corner_radius=10)
        self.btn_help = ctk.CTkButton(toolbar, text="Ayuda", width=120, height=38, corner_radius=10)

        self.btn_new.grid(row=0, column=0, padx=6, pady=8)
        self.btn_edit.grid(row=0, column=1, padx=6, pady=8)
        self.btn_delete.grid(row=0, column=2, padx=6, pady=8)
        self.btn_refresh.grid(row=0, column=3, padx=6, pady=8)
        self.btn_export.grid(row=0, column=4, padx=6, pady=8)
        self.btn_help.grid(row=0, column=5, padx=6, pady=8)

        # Body (placeholder para cada módulo)
        self.body = ctk.CTkFrame(self, corner_radius=14, fg_color=("#0E142A", "#0A1022"))
        self.body.grid(row=2, column=0, padx=16, pady=12, sticky="nsew")
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        info = ctk.CTkLabel(
            self.body,
            text="Aquí irán tus formularios, tablas y acciones específicas.",
            text_color=TEXT, font=ctk.CTkFont(size=16)
        )
        info.grid(row=0, column=0, padx=16, pady=16, sticky="n")

# ---------------------------------------------------------------------------
# Ventanas de cada módulo (con contenido ejemplo)
# ---------------------------------------------------------------------------

class StudentsWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        # Recolorea botones de toolbar
        self.btn_new.configure(fg_color="#A855F7", hover_color="#7C3AED")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        # Layout específico
        self.body.grid_columnconfigure(1, weight=1)
        form = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        table = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#0F162D", "#0A1124"))
        form.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsw")
        table.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        # Formulario
        ctk.CTkLabel(form, text="Nuevo/Editar Estudiante", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        for i in range(8): form.grid_rowconfigure(i, weight=0)
        labels = ["Nombre", "Apellido", "Tipo Documento", "Número Documento", "Teléfono", "Email", "Dirección", "Usuario"]
        self.entries = []
        for i, lb in enumerate(labels, start=1):
            ctk.CTkLabel(form, text=lb, text_color=TEXT_MUTED).grid(row=i, column=0, padx=14, pady=(6, 0), sticky="w")
            e = ctk.CTkEntry(form, width=260, height=34, placeholder_text=f"Ingrese {lb.lower()}")
            e.grid(row=i, column=0, padx=14, pady=(2, 6), sticky="w")
            self.entries.append(e)
        save = ctk.CTkButton(form, text="Guardar", fg_color="#A855F7", hover_color="#7C3AED", width=260, height=40)
        save.grid(row=10, column=0, padx=14, pady=12, sticky="w")

        # Tabla placeholder
        ctk.CTkLabel(table, text="Estudiantes (placeholder tabla)", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=14, pady=(14, 8), anchor="w")
        placeholder = ctk.CTkTextbox(table, width=560, height=420)
        placeholder.insert("end", "Aquí iría una tabla (usa ttk.Treeview si lo deseas).\n\nMuestra listado de estudiantes, con filtros y paginación.")
        placeholder.configure(state="disabled")
        placeholder.pack(padx=14, pady=12, fill="both", expand=True)

class InstructorsWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        self.btn_new.configure(fg_color="#F59E0B", hover_color="#D97706")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        self.body.grid_columnconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        wrap.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="Instructores — Gestión", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        grid = ctk.CTkFrame(wrap, corner_radius=10, fg_color=("#0F162D", "#0A1124"))
        grid.grid(row=1, column=0, padx=14, pady=14, sticky="nsew")
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)

        fields = [("Nombres", ""), ("Apellidos", ""), ("Documento", ""), ("Teléfono", ""), ("Email", "")]
        for idx, (label, _) in enumerate(fields):
            ctk.CTkLabel(grid, text=label, text_color=TEXT_MUTED).grid(row=idx, column=0, padx=12, pady=(8,0), sticky="w")
            ctk.CTkEntry(grid, placeholder_text=f"Ingrese {label.lower()}", height=34).grid(row=idx, column=1, padx=12, pady=(6,6), sticky="ew")

        ctk.CTkButton(grid, text="Guardar Instructor", fg_color="#F59E0B", hover_color="#D97706", height=40).grid(row=len(fields)+1, column=0, columnspan=2, padx=12, pady=12, sticky="ew")

class VehiclesWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        self.btn_new.configure(fg_color="#38BDF8", hover_color="#0EA5E9")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        self.body.grid_columnconfigure(1, weight=1)
        form = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        table = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#0F162D", "#0A1124"))
        form.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsw")
        table.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        ctk.CTkLabel(form, text="Vehículo", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        labels = ["Placa", "Marca", "Modelo", "Año", "Estado"]
        for i, lb in enumerate(labels, start=1):
            ctk.CTkLabel(form, text=lb, text_color=TEXT_MUTED).grid(row=i, column=0, padx=14, pady=(6, 0), sticky="w")
            ctk.CTkEntry(form, width=260, height=34, placeholder_text=f"Ingrese {lb.lower()}").grid(row=i, column=0, padx=14, pady=(2, 6), sticky="w")
        ctk.CTkButton(form, text="Guardar", fg_color="#38BDF8", hover_color="#0EA5E9", width=260, height=40).grid(row=10, column=0, padx=14, pady=12, sticky="w")

        ctk.CTkLabel(table, text="Vehículos (placeholder tabla)", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=14, pady=(14, 8), anchor="w")
        placeholder = ctk.CTkTextbox(table)
        placeholder.insert("end", "Tabla de vehículos.\nPuedes listar placa, marca, año, estado, instructor asignado, etc.")
        placeholder.configure(state="disabled")
        placeholder.pack(padx=14, pady=12, fill="both", expand=True)

class ClassesWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        self.btn_new.configure(fg_color="#10B981", hover_color="#059669")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        self.body.grid_columnconfigure(1, weight=1)
        form = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        table = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#0F162D", "#0A1124"))
        form.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsw")
        table.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        ctk.CTkLabel(form, text="Clase", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        items = ["ID Estudiante", "ID Instructor", "Placa Vehículo", "Fecha (YYYY-MM-DD)", "Hora Inicio (HH:MM)", "Hora Fin (HH:MM)", "Estado"]
        for i, lb in enumerate(items, start=1):
            ctk.CTkLabel(form, text=lb, text_color=TEXT_MUTED).grid(row=i, column=0, padx=14, pady=(6, 0), sticky="w")
            ctk.CTkEntry(form, width=280, height=34, placeholder_text=f"Ingrese {lb.lower()}").grid(row=i, column=0, padx=14, pady=(2, 6), sticky="w")
        ctk.CTkButton(form, text="Programar Clase", fg_color="#10B981", hover_color="#059669", width=280, height=40).grid(row=10, column=0, padx=14, pady=12, sticky="w")

        ctk.CTkLabel(table, text="Calendario / Lista de clases", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=14, pady=(14, 8), anchor="w")
        placeholder = ctk.CTkTextbox(table)
        placeholder.insert("end", "Aquí puedes mostrar las clases programadas con filtros por fecha e instructor.")
        placeholder.configure(state="disabled")
        placeholder.pack(padx=14, pady=12, fill="both", expand=True)

class AccountsWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        self.btn_new.configure(fg_color="#F43F5E", hover_color="#E11D48")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        self.body.grid_columnconfigure(1, weight=1)
        left = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        right = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#0F162D", "#0A1124"))
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsw")
        right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        ctk.CTkLabel(left, text="Estado de Cuenta", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        fields = ["ID Estudiante", "Monto Total", "Monto Pagado", "Estado"]
        for i, lb in enumerate(fields, start=1):
            ctk.CTkLabel(left, text=lb, text_color=TEXT_MUTED).grid(row=i, column=0, padx=14, pady=(6, 0), sticky="w")
            ctk.CTkEntry(left, width=280, height=34, placeholder_text=f"Ingrese {lb.lower()}").grid(row=i, column=0, padx=14, pady=(2, 6), sticky="w")
        ctk.CTkButton(left, text="Guardar Estado", fg_color="#F43F5E", hover_color="#E11D48", width=280, height=40).grid(row=10, column=0, padx=14, pady=12, sticky="w")

        ctk.CTkLabel(right, text="Pagos / Saldos", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=14, pady=(14, 8), anchor="w")
        placeholder = ctk.CTkTextbox(right)
        placeholder.insert("end", "Lista de pagos del estudiante, saldo pendiente y acciones para registrar nuevos pagos.")
        placeholder.configure(state="disabled")
        placeholder.pack(padx=14, pady=12, fill="both", expand=True)

class ReportsWindow(ModuleWindow):
    def __init__(self, master, title):
        super().__init__(master, title)
        self.btn_new.configure(fg_color="#6366F1", hover_color="#4F46E5")
        self.btn_refresh.configure(fg_color="#22D3EE", hover_color="#06B6D4")

        self.body.grid_columnconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("#101735", "#0B1228"))
        wrap.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(wrap, text="Reportes — Consultas", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        filt = ctk.CTkFrame(wrap, corner_radius=10, fg_color=("#0F162D", "#0A1124"))
        filt.grid(row=1, column=0, padx=14, pady=10, sticky="ew")
        for i in range(5): filt.grid_columnconfigure(i, weight=1)

        ctk.CTkEntry(filt, placeholder_text="Desde (YYYY-MM-DD)", height=34).grid(row=0, column=0, padx=8, pady=10, sticky="ew")
        ctk.CTkEntry(filt, placeholder_text="Hasta (YYYY-MM-DD)", height=34).grid(row=0, column=1, padx=8, pady=10, sticky="ew")
        ctk.CTkOptionMenu(filt, values=["Clases", "Pagos", "Estados", "Vehículos", "Instructores", "Estudiantes"]).grid(row=0, column=2, padx=8, pady=10, sticky="ew")
        ctk.CTkButton(filt, text="Generar", fg_color="#6366F1", hover_color="#4F46E5").grid(row=0, column=3, padx=8, pady=10, sticky="ew")

        out = ctk.CTkTextbox(wrap)
        out.insert("end", "Resultados del reporte aparecerán aquí.\nPuedes exportar a CSV/Excel/PDF.")
        out.configure(state="disabled")
        out.grid(row=2, column=0, padx=14, pady=(10, 14), sticky="nsew")

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = HaroHome()
    app.mainloop()
