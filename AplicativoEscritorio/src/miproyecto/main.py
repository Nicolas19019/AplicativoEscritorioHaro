import customtkinter as ctk
from tkinter import messagebox

APP_TITLE = "CEA HARO — Inicio"
APP_W, APP_H = 1180, 720

# -------- Paleta con soporte Light/Dark (tuplas: (light, dark)) -------- #
# Base
BG          = ("#FFFFFF", "#121212")
PANEL       = ("#FFFFFF", "#1B1B1B")
TEXT        = ("#111111", "#F5F5F5")
TEXT_MUTED  = ("#585858", "#C9C9C9")
MUTED_BG    = ("#F4F6F8", "#161A1D")

# HARO (rojos) + acentos por tarjeta
RED         = ("#E53935", "#EF5350")
RED_DARK    = ("#C62828", "#D32F2F")
RED_SOFT    = ("#FDECEC", "#2A1616")

ACCENTS = [
    # (bg_soft, ring, hover)
    (("#FFF1F1", "#2A1717"), ("#FF6B6B", "#EF5350"), ("#FFD6D6", "#3A1F1F")),   # Estudiantes (rojo)
    (("#FFF5E6", "#261E12"), ("#FFA000", "#FFB74D"), ("#FFE4BD", "#3A2B16")),   # Profesores (ámbar)
    (("#E6F7FF", "#0F1F26"), ("#29B6F6", "#4FC3F7"), ("#CFEFFF", "#142833")),   # Vehículos (celeste)
    (("#EAF7F1", "#112118"), ("#26A69A", "#4DB6AC"), ("#D6F0E4", "#143226")),   # Clases (teal)
    (("#F3E8FF", "#1E1629"), ("#AB47BC", "#BA68C8"), ("#EAD7FF", "#271D36")),   # Estados de cuenta (púrpura)
    (("#EEF2FF", "#161A26"), ("#5C6BC0", "#7986CB"), ("#DCE2FF", "#1E2638")),   # Reportes (indigo)
]

CARDS = [
    ("Gestión de Estudiantes", "🎓"),
    ("Profesores",             "👩‍🏫"),
    ("Vehículos",              "🚗"),
    ("Clases",                 "📚"),
    ("Estados de Cuenta",      "💳"),
    ("Reportes",               "📊"),
]

class HaroHome(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_W}x{APP_H}")
        self.minsize(1024, 640)

        # Tema
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")  # neutro; usamos colores propios

        # Grid raíz
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.configure(fg_color=BG)

        self._build_topbar()
        self._build_home()
        self._build_statusbar()
        self._bind_shortcuts()

        self.after(150, lambda: self.card_btns[0].focus_set())

    # ---------------- Topbar ---------------- #
    def _build_topbar(self):
        # Cinta superior “brand”
        brand = ctk.CTkFrame(self, height=6, fg_color=RED)
        brand.grid(row=0, column=0, sticky="new")

        top = ctk.CTkFrame(self, corner_radius=0, fg_color=PANEL)
        top.grid(row=0, column=0, sticky="nsew", pady=(6, 0))
        top.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            top, text="HARO", text_color=TEXT,
            font=ctk.CTkFont(size=22, weight="bold")
        )
        subtitle = ctk.CTkLabel(
            top, text="Inicio • Selecciona un módulo",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=13)
        )
        title.grid(row=0, column=0, padx=18, pady=(10, 0), sticky="w")
        subtitle.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        # Botón primario
        start_btn = ctk.CTkButton(
            top, text="Empezar",
            fg_color=RED, hover_color=RED_DARK, text_color="white",
            corner_radius=10, height=40, width=120,
            command=lambda: self._open("Gestión de Estudiantes"),
        )
        start_btn.grid(row=0, column=2, rowspan=2, padx=18, pady=12, sticky="e")

        # Switch modo
        self.dark_switch = ctk.CTkSwitch(
            top, text="Modo oscuro", command=self._toggle_mode,
            progress_color=RED, fg_color=RED_DARK, text_color=TEXT
        )
        self.dark_switch.grid(row=0, column=3, rowspan=2, padx=(0, 18), pady=12, sticky="e")

    # ---------------- Home ---------------- #
    def _build_home(self):
        wrapper = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        wrapper.grid(row=1, column=0, sticky="nsew")
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(1, weight=1)

        # Hero
        hero = ctk.CTkFrame(wrapper, fg_color=BG)
        hero.grid(row=0, column=0, padx=24, pady=(18, 8), sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        h1 = ctk.CTkLabel(hero, text="Bienvenido 👋", text_color=TEXT,
                          font=ctk.CTkFont(size=26, weight="bold"))
        h2 = ctk.CTkLabel(hero, text="Usa 1–6 o Alt+1–Alt+6 para atajos.",
                          text_color=TEXT_MUTED, font=ctk.CTkFont(size=13))
        h1.grid(row=0, column=0, sticky="w")
        h2.grid(row=1, column=0, sticky="w")

        # Lienzo con “glass” y sombra suave
        canvas = ctk.CTkFrame(wrapper, corner_radius=22, fg_color=MUTED_BG)
        canvas.grid(row=1, column=0, padx=24, pady=10, sticky="nsew")
        canvas.grid_rowconfigure(0, weight=1)
        canvas.grid_columnconfigure(0, weight=1)

        grid = ctk.CTkFrame(canvas, corner_radius=22, fg_color=PANEL)
        grid.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        for r in range(2):
            grid.grid_rowconfigure(r, weight=1)
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)

        self.card_btns = []
        for i, (title, emoji) in enumerate(CARDS):
            r, c = divmod(i, 3)
            soft, ring, hover = ACCENTS[i]
            btn = self._card(grid, r, c, title, emoji, soft, ring, hover)
            self.card_btns.append(btn)

        help_lbl = ctk.CTkLabel(
            wrapper,
            text="Consejo: puedes volver aquí con la tecla Esc.",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)
        )
        help_lbl.grid(row=2, column=0, padx=24, pady=(4, 12), sticky="w")

    def _card(self, parent, row, col, title, emoji, soft_bg, ring, hover_bg):
        # Capa de sombra
        shadow = ctk.CTkFrame(parent, corner_radius=20, fg_color=soft_bg)
        shadow.grid(row=row, column=col, padx=16, pady=16, sticky="nsew")

        # Tarjeta
        card = ctk.CTkFrame(shadow, corner_radius=20, fg_color=PANEL)
        card.pack(expand=True, fill="both", padx=3, pady=3)
        card.grid_rowconfigure(3, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # “Anillo” superior decorativo
        ring_bar = ctk.CTkFrame(card, height=6, fg_color=ring, corner_radius=6)
        ring_bar.grid(row=0, column=0, padx=16, pady=(14, 10), sticky="ew")

        # Icono & título
        icon = ctk.CTkLabel(card, text=emoji, text_color=TEXT,
                            font=ctk.CTkFont(size=46))
        icon.grid(row=1, column=0, pady=(0, 6))
        lbl = ctk.CTkLabel(card, text=title, text_color=TEXT,
                           font=ctk.CTkFont(size=16, weight="bold"))
        lbl.grid(row=2, column=0)

        # Botón primario
        btn = ctk.CTkButton(
            card, text="Abrir", height=42, corner_radius=12,
            fg_color=RED, hover_color=RED_DARK, text_color="white",
            command=lambda t=title: self._open(t)
        )
        btn.grid(row=4, column=0, padx=18, pady=(12, 16), sticky="ew")

        # Hover sutil en toda la tarjeta
        def on_enter(_): card.configure(fg_color=hover_bg)
        def on_leave(_): card.configure(fg_color=PANEL)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        btn.bind("<Return>", lambda _: self._open(title))
        return btn

    # ---------------- Statusbar ---------------- #
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=PANEL, height=42)
        bar.grid(row=2, column=0, sticky="nsew")
        bar.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            bar, text="Listo", text_color=TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=12)
        )
        self.status.grid(row=0, column=0, padx=16, pady=8, sticky="w")

    # ---------------- Behavior ---------------- #
    def _toggle_mode(self):
        # Cambia apariencia y deja que las tuplas (light, dark) hagan el resto
        is_dark = self.dark_switch.get()
        ctk.set_appearance_mode("dark" if is_dark else "light")
        # CTk actualiza automáticamente los colores definidos como tuplas.
        # Refrescamos estado para dar feedback.
        self.status.configure(text="Modo: oscuro" if is_dark else "Modo: claro")

    def _open(self, name):
        self.status.configure(text=f"Abriste: {name}")
        messagebox.showinfo("Navegación", f"Se abrirá la sección: {name}")

    def _bind_shortcuts(self):
        # 1–6 y Alt+1–6
        for idx, (name, _) in enumerate(CARDS, start=1):
            self.bind(f"<Key-{idx}>", lambda e, n=name: self._open(n))
            self.bind_all(f"<Alt-KeyPress-{idx}>", lambda e, n=name: self._open(n))
        # Esc
        self.bind("<Escape>", lambda e: self.status.configure(text="Volviste a Inicio"))

if __name__ == "__main__":
    app = HaroHome()
    app.mainloop()
