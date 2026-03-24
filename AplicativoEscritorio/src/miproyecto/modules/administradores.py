from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk

from modules.base import BaseModuleFrame


class AdministradoresView(BaseModuleFrame):
    RESOURCE = "administradores"

    def __init__(self, master):
        super().__init__(master, "Administradores", "Controle perfiles administrativos y su estado")

        self._all_data = []
        self._data = []
        self._selected_id = None

        self._build_toolbar()
        self._build_summary()
        self._build_filters()
        self._build_table()

        self.after(120, self._refrescar)

    def _build_toolbar(self):
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure(3, weight=1)

        def btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                tb,
                text=text,
                height=40,
                corner_radius=18,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
                anchor="w",
            )

        btn("✓ Activar", self._activar_seleccionado, self.app.COLOR_GREEN, self.app.GREEN_HOVER)\
            .grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        btn("⏸ Desactivar", self._desactivar_seleccionado, self.app.COLOR_RED, self.app.RED_HOVER)\
            .grid(row=0, column=1, padx=8, pady=6, sticky="w")
        btn("↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER)\
            .grid(row=0, column=2, padx=8, pady=6, sticky="w")

    def _build_summary(self):
        self.summary = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.summary.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        for col in range(4):
            self.summary.grid_columnconfigure(col, weight=1)

        self._summary_cards = {}
        cards = (
            ("total", "Total admins"),
            ("activos", "Activos"),
            ("inactivos", "Inactivos"),
            ("recientes", "Actualizados hoy"),
        )
        for idx, (key, label) in enumerate(cards):
            card = ctk.CTkFrame(
                self.summary,
                fg_color=self.app.COLOR_INPUT_BG,
                corner_radius=12,
                border_width=1,
                border_color=self.app.COLOR_DIVIDER,
            )
            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(
                card,
                text=label,
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=12, pady=(10, 2))
            value = ctk.CTkLabel(
                card,
                text="0",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=22, weight="bold"),
            )
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self._summary_cards[key] = value

    def _build_filters(self):
        bar = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        bar.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)

        def entry(ph):
            return ctk.CTkEntry(
                bar,
                placeholder_text=ph,
                height=36,
                corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                text_color=self.app.COLOR_TEXT,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )

        ctk.CTkLabel(bar, text="Buscar").grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_buscar = entry("Nombre, usuario, correo o cédula")
        self.f_buscar.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Estado").grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(bar, values=["Todos", "Activo", "Inactivo"], width=180)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="w")

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=1, column=2, columnspan=2, padx=(8, 12), pady=(0, 10), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(
                btns,
                text=text,
                height=36,
                corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                hover_color=self.app.COLOR_DIVIDER,
                text_color=self.app.COLOR_TEXT,
                command=cmd,
            )

        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=6)
        light_btn("Buscar", self._apply_filters).grid(row=0, column=1, padx=6)

        self.f_buscar.bind("<KeyRelease>", lambda _e: self._apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

    def _build_table(self):
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        mode = ctk.get_appearance_mode()
        if mode == "Light":
            bg = "#ffffff"
            panel = "#ffffff"
            text = "#111111"
            muted = "#444444"
            divider = "#e5e7eb"
            sel_bg = "#FFF8E1"
        else:
            bg = getattr(self.app, "COLOR_BG", "#111111")
            panel = getattr(self.app, "COLOR_PANEL", "#1b1b1b")
            text = getattr(self.app, "COLOR_TEXT", "#ffffff")
            muted = getattr(self.app, "COLOR_MUTED", "#cfcfcf")
            divider = getattr(self.app, "COLOR_DIVIDER", "#2a2a2a")
            sel_bg = divider

        style.configure(
            "Admins.Treeview",
            background=panel,
            fieldbackground=panel,
            foreground=text,
            bordercolor=divider,
            lightcolor=divider,
            darkcolor=divider,
            rowheight=28,
        )
        style.map(
            "Admins.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", text)],
        )
        style.configure(
            "Admins.Treeview.Heading",
            background=bg,
            foreground=muted,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )

        self._cols = [
            ("ID", 60),
            ("Nombre", 180),
            ("Usuario", 140),
            ("Correo", 220),
            ("Cédula", 120),
            ("Estado", 90),
            ("Creado", 140),
            ("Actualizado", 140),
        ]

        cols = [c[0] for c in self._cols]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Admins.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, width in self._cols:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, minwidth=max(60, int(width * 0.7)), stretch=True, anchor="w")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._empty_label = ctk.CTkLabel(self.table, text="Sin administradores", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _on_select(self, _evt=None):
        selection = self.tree.selection()
        if not selection:
            self._selected_id = None
            return
        values = self.tree.item(selection[0], "values")
        self._selected_id = values[0] if values else None

    def _clear_filters(self):
        self.f_buscar.delete(0, "end")
        self.f_estado.set("Todos")
        self._apply_filters()

    def _unwrap(self, raw):
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in ("content", "items", "administradores", "data", "results"):
                val = raw.get(key)
                if isinstance(val, list):
                    return val
        return []

    def _format_dt(self, value):
        if not value:
            return "—"
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text[:16].replace("T", " ")

    def _apply_filters(self):
        term = (self.f_buscar.get() or "").strip().lower()
        estado = (self.f_estado.get() or "Todos").strip().lower()

        data = list(self._all_data)
        if term:
            data = [
                item for item in data
                if term in str(item.get("nombre") or "").lower()
                or term in str(item.get("usuario") or "").lower()
                or term in str(item.get("correo") or "").lower()
                or term in str(item.get("cedula") or "").lower()
            ]
        if estado == "activo":
            data = [item for item in data if bool(item.get("activo"))]
        elif estado == "inactivo":
            data = [item for item in data if not bool(item.get("activo"))]

        self._data = data
        self._render_table()
        self._render_summary()

    def _render_summary(self):
        total = len(self._data)
        activos = sum(1 for item in self._data if bool(item.get("activo")))
        inactivos = total - activos
        today = datetime.now().date()
        recientes = 0
        for item in self._data:
            raw = item.get("actualizadoEn") or item.get("creadoEn")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.date() == today:
                    recientes += 1
            except Exception:
                continue

        self._summary_cards["total"].configure(text=str(total))
        self._summary_cards["activos"].configure(text=str(activos))
        self._summary_cards["inactivos"].configure(text=str(inactivos))
        self._summary_cards["recientes"].configure(text=str(recientes))

    def _render_table(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        if not self._data:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self._selected_id = None
            return

        self._empty_label.place_forget()
        for item in self._data:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.get("id", "—"),
                    item.get("nombre") or "—",
                    item.get("usuario") or "—",
                    item.get("correo") or "—",
                    item.get("cedula") or "—",
                    "Activo" if bool(item.get("activo")) else "Inactivo",
                    self._format_dt(item.get("creadoEn")),
                    self._format_dt(item.get("actualizadoEn")),
                ),
            )

    def _selected_admin(self):
        if self._selected_id in (None, ""):
            messagebox.showinfo("Administradores", "Selecciona un administrador primero.", parent=self)
            return None
        return self._selected_id

    def _activar_seleccionado(self):
        admin_id = self._selected_admin()
        if admin_id is None:
            return
        try:
            self.app.api.patch(self.RESOURCE, admin_id, suffix="activar")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible activar el administrador:\n{e}", parent=self)

    def _desactivar_seleccionado(self):
        admin_id = self._selected_admin()
        if admin_id is None:
            return
        try:
            self.app.api.patch(self.RESOURCE, admin_id, suffix="desactivar")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible desactivar el administrador:\n{e}", parent=self)

    def _refrescar(self, force_refresh=True):
        try:
            raw = self.app.api.get_all(self.RESOURCE, force_refresh=force_refresh) or []
            self._all_data = self._unwrap(raw)
            self._apply_filters()
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible consultar la API:\n{e}", parent=self)
