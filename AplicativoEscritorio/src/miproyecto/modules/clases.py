# modules/clases.py
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk
import datetime, calendar, threading, time

from modules.base import BaseModuleFrame
from modules.forms_inlines import ClaseInlineForm
from modules.treeview_theme import configure_treeview_style


class ClasesView(BaseModuleFrame):
    """
    Clases:
      • Vista normal: tabla con columnas Estudiante, Documento, Instructor, Placa, Fecha, Estado, Acciones.
      • Vista calendario: calendario + tarjetas verticales con mini "tabla" del estudiante (sin ID).
    """

    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 5
    TREE_INSERT_CHUNK = 250
    TREE_INSERT_DELAY = 1  # ms
    MIN_REFRESH_INTERVAL = 500  # ms
    CLASES_RESOURCE = "clases-practicas"

    # Layout general
    HEADER_PADY = (10, 6)

    def __init__(self, master):
        super().__init__(master, "Clases", "Gestión de clases teóricas y prácticas")
        self.app = self.winfo_toplevel()

        # ===== Estado =====
        self._data = []
        self._selected_id = None
        self._last_refresh_ts = 0
        self.fecha_filtrada = None
        self._calendar_mode = False
        self._filter_after_id = None

        self._estudiantes, self._profesores, self._vehiculos = [], [], []
        self.estudiantes_id_to_name, self.profesores_id_to_name = {}, {}
        self.estudiantes_id_to_doc = {}

        # Paleta
        self._ACCENT = getattr(self.app, "COLOR_RED", "#D9042B")
        self._YELLOW = getattr(self.app, "COLOR_YELLOW", "#F1C40F")
        self._TEXT   = getattr(self.app, "COLOR_TEXT", "#111827")
        self._MUTED  = getattr(self.app, "COLOR_MUTED", "#6B7280")
        self._PANEL  = getattr(self.app, "COLOR_PANEL", "#F6F7F9")
        self._INPUT  = getattr(self.app, "COLOR_INPUT_BG", "#EFEFF2")
        self._DIV    = getattr(self.app, "COLOR_DIVIDER", "#E5E7EB")
        self._BG     = getattr(self.app, "COLOR_BG", "#F5F7FB")

        # ===== Layout raíz =====
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")
        tb.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(tb, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="w")

        def action_btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                bar,
                text=text,
                height=36,
                corner_radius=12,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
            )

        self.btn_calendar = ctk.CTkButton(
            bar, text="📅 Calendario", height=36, corner_radius=12,
            fg_color=self.app.BLUE_SOFT_BG, hover_color=self.app.BLUE_SOFT_BORDER,
            text_color=self.app.COLOR_BLUE, command=self._toggle_calendar_mode
        )
        self.btn_calendar.grid(row=0, column=0, padx=(0, 8))

        action_btn("＋ Nuevo", self._nuevo, self.app.COLOR_GREEN, self.app.GREEN_HOVER).grid(row=0, column=1, padx=(0, 8))
        action_btn("✎ Editar", self._editar, self.app.COLOR_BLUE, self.app.BLUE_HOVER).grid(row=0, column=2, padx=(0, 8))
        action_btn("🗑️ Eliminar", self._eliminar, self.app.COLOR_RED, self.app.RED_HOVER).grid(row=0, column=3, padx=(0, 8))
        action_btn("↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER).grid(row=0, column=4, padx=(0, 8))
        ctk.CTkButton(
            bar, text="Restablecer filtros", height=36, corner_radius=12,
            fg_color=self._INPUT, hover_color=self._DIV,
            text_color=self._TEXT, command=self._restablecer_filtros
        ).grid(row=0, column=5, padx=(0, 8))

        self._build_filters_bar(tb)

        # ===== Form inline =====
        try:
            self.form = ClaseInlineForm(self, self.app, self._on_submit, self._on_cancel)
            self.form.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
            self.form.hide()
        except Exception as e:
            print(f"[Clases] No se pudo crear el formulario: {e}")
            self.form = None

        # ===== Contenedor principal =====
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Vistas
        self._build_normal_view()    # tabla PRO
        self._build_calendar_view()  # calendario + tarjetas
        self._show_view("normal")

        # Overlay de carga
        self._loading_overlay = None

        # Carga inicial
        self._build_table_shell()      # asegura shell tabla
        self._set_table_data([])       # vacío al inicio
        self._show_loading(False)
        self.after(150, lambda: self._cargar_catalogos_y_listar(force_refresh=True))

    def _build_filters_bar(self, parent):
        filt = ctk.CTkFrame(
            parent,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        filt.grid(row=1, column=0, pady=(10, 0), sticky="ew")
        filt.grid_columnconfigure(1, weight=1)
        filt.grid_columnconfigure(3, weight=0)

        ctk.CTkLabel(
            filt,
            text="Buscar clase",
            text_color=self._TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(14, 10), pady=(12, 4), sticky="w")

        self.f_buscar = ctk.CTkEntry(
            filt,
            placeholder_text="Escribe estudiante, instructor, placa o sede",
            height=42,
            corner_radius=14,
            border_width=2,
            border_color=self.app.COLOR_YELLOW,
            fg_color=self._INPUT,
            text_color=self._TEXT,
        )
        self.f_buscar.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            filt,
            text="Estado",
            text_color=self._TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=2, padx=(0, 10), pady=(12, 4), sticky="w")

        self.f_estado = ctk.CTkComboBox(
            filt,
            values=["Todos", "Programada", "Pendiente", "Dictada", "Cancelada"],
            width=160,
            state="readonly",
        )
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=2, padx=(0, 10), pady=(0, 12), sticky="w")

        ctk.CTkButton(
            filt,
            text="Limpiar",
            height=42,
            width=120,
            corner_radius=16,
            fg_color=self.app.COLOR_RED,
            hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff",
            command=self._restablecer_filtros,
        ).grid(row=1, column=3, padx=(0, 14), pady=(0, 12), sticky="e")

        self.f_buscar.bind("<KeyRelease>", lambda _e: self._debounced_apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda _e: self._sync_rows_to("right" if self._calendar_mode else "top"))

    # ============================
    # VISTA NORMAL: TABLA PRO
    # ============================
    def _build_normal_view(self):
        self.view_normal = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_normal.grid(row=0, column=0, sticky="nsew")
        self.view_normal.grid_columnconfigure(0, weight=1)
        self.view_normal.grid_rowconfigure(0, weight=1)

        # Tabla optimizada (Treeview) como Vehículos/Instructores
        self.table = ctk.CTkFrame(self.view_normal, fg_color=self._BG, corner_radius=12)
        self.table.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        # Columnas: (nombre, width)
        self._COLS = [
            ("Estudiante", 260),
            ("Documento",  160),
            ("Instructor", 220),
            ("Placa",      110),
            ("Sede",       140),
            ("Fecha",      130),
            ("Estado",     150),
        ]
        self.tree = None
        self._iid_to_key = {}
        self._key_to_iid = {}
        self._empty_label = None

    def _build_table_shell(self):
        if getattr(self, "tree", None) and self.tree.winfo_exists():
            return

        for w in self.table.winfo_children():
            w.destroy()

        self._iid_to_key = {}
        self._key_to_iid = {}

        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "Haro.Treeview", rowheight=30)

        cols = [c[0] for c in self._COLS]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Haro.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, width in self._COLS:
            self.tree.heading(name, text=name)
            anchor = "center" if name in {"Placa", "Fecha", "Estado"} else "w"
            self.tree.column(name, width=width, minwidth=max(70, int(width * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        self._empty_label = ctk.CTkLabel(self.table, text="Sin registros de clases", text_color=self._MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _on_tree_select(self, _evt=None):
        try:
            sel = self.tree.selection()
            if not sel:
                self._selected_id = None
                return
            iid = sel[0]
            self._selected_id = self._iid_to_key.get(iid)
        except Exception:
            self._selected_id = None

    def _set_table_data(self, rows):
        """Set data SOLO para vista normal (Treeview)."""
        self._build_table_shell()

        data = list(rows or [])
        self._selected_id = None

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_key.clear()
        self._key_to_iid.clear()

        if not data:
            if self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return

        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.place_forget()

        def insert_chunk(start=0):
            end = min(start + self.TREE_INSERT_CHUNK, len(data))
            for idx in range(start, end):
                rec = data[idx]
                rid = self._row_key(rec)
                iid = f"r{idx}"
                self._iid_to_key[iid] = rid
                self._key_to_iid[rid] = iid
                self.tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=self._row_values(rec),
                    tags=("even" if idx % 2 == 0 else "odd",),
                )
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    # ============================
    # VISTA CALENDARIO
    # ============================
    def _build_calendar_view(self):
        self.view_calendar = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_calendar.grid_rowconfigure(0, weight=1)
        self.view_calendar.grid_columnconfigure(0, weight=0, minsize=360)
        self.view_calendar.grid_columnconfigure(1, weight=1)

        # Calendario
        self.cal_frame = ctk.CTkFrame(
            self.view_calendar,
            fg_color=self._PANEL,
            corner_radius=12,
            border_width=2,
            border_color=self._DIV
        )
        self.cal_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._init_calendar()

        # Panel derecho
        self.table_wrap = ctk.CTkFrame(self.view_calendar, fg_color="transparent")
        self.table_wrap.grid(row=0, column=1, sticky="nsew")
        self.table_wrap.grid_rowconfigure(0, weight=1)
        self.table_wrap.grid_columnconfigure(0, weight=1)

        self.table_right = ctk.CTkScrollableFrame(self.table_wrap, fg_color=self._PANEL, corner_radius=12)
        self.table_right.grid(row=0, column=0, sticky="nsew")
        self.table_right.grid_columnconfigure(0, weight=1)

        inner_r = getattr(self.table_right, "_scrollable_frame", None) or getattr(self.table_right, "scrollable_frame", None)
        if inner_r:
            inner_r.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.table_right, fg_color=self._INPUT, corner_radius=12)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self.lbl_day_header = ctk.CTkLabel(
            header, text="Clases del día", text_color=self._MUTED,
            anchor="w", font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_day_header.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.cards_container_right = ctk.CTkFrame(self.table_right, fg_color="transparent")
        self.cards_container_right.grid(row=1, column=0, sticky="nsew")
        self.table_right.grid_rowconfigure(1, weight=1)
        self.cards_container_right.grid_columnconfigure(0, weight=1)

    def _render_vertical_cards(self, parent, records):
        for w in parent.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Header dinámico (fecha + conteos)
        try:
            if hasattr(self, "lbl_day_header") and self.lbl_day_header.winfo_exists():
                if self.fecha_filtrada:
                    self.lbl_day_header.configure(text=f"Clases del día — {self.fecha_filtrada}")
                else:
                    self.lbl_day_header.configure(text="Clases del día")
        except Exception:
            pass

        if not records:
            empty_text = (
                "Selecciona un día en el calendario para ver clases."
                if not self.fecha_filtrada else
                "Sin clases programadas para este día."
            )
            ctk.CTkLabel(parent, text=empty_text, text_color=self._MUTED, anchor="w") \
                .grid(row=0, column=0, padx=16, pady=16, sticky="w")
            return

        # Agrupar por área (Carro/Moto) y por estudiante para que el resumen sea más compacto.
        grouped = {"carro": {}, "moto": {}, "mixto": {}, "otros": {}}
        for rec in (records or []):
            sid = self._take_id_est(rec)
            area_key, _ = self._student_area(sid)
            grouped.setdefault(area_key, {}).setdefault(sid, []).append(rec)

        counts = {k: sum(len(v) for v in (grouped.get(k) or {}).values()) for k in grouped.keys()}
        try:
            if hasattr(self, "lbl_day_header") and self.lbl_day_header.winfo_exists() and self.fecha_filtrada:
                parts = []
                if counts.get("carro"):
                    parts.append(f"Carro: {counts['carro']}")
                if counts.get("moto"):
                    parts.append(f"Moto: {counts['moto']}")
                if counts.get("mixto"):
                    parts.append(f"Mixto: {counts['mixto']}")
                if counts.get("otros"):
                    parts.append(f"Otros: {counts['otros']}")
                if parts:
                    self.lbl_day_header.configure(text=f"Clases del día — {self.fecha_filtrada} ({' | '.join(parts)})")
        except Exception:
            pass

        def time_sort_key(r):
            return (str(r.get("horaInicio") or ""), str(r.get("horaFin") or ""))

        row = 0
        area_order = [
            ("carro", "Carro"),
            ("moto", "Moto"),
            ("mixto", "Carro + Moto"),
            ("otros", "Otros"),
        ]

        for area_key, area_title in area_order:
            stu_map = grouped.get(area_key) or {}
            if not stu_map:
                continue

            area_count = sum(len(v) for v in stu_map.values())
            ctk.CTkLabel(
                parent,
                text=f"{area_title} ({area_count})",
                text_color=self._MUTED,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=row, column=0, padx=16, pady=(10 if row else 4, 4), sticky="w")
            row += 1

            def student_sort_key(item):
                sid, clases = item
                earliest = min((str(x.get("horaInicio") or "") for x in (clases or [])), default="")
                return (self._student_name(sid).lower(), earliest)

            for sid, clases in sorted(stu_map.items(), key=student_sort_key):
                clases_sorted = sorted(list(clases or []), key=time_sort_key)

                card = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=14,
                                    border_width=2, border_color=self._DIV)
                card.grid(row=row, column=0, padx=8, pady=(6, 8), sticky="ew")
                card.grid_columnconfigure(0, weight=1)
                row += 1

                strip = ctk.CTkFrame(card, fg_color=self._ACCENT, height=6, corner_radius=14)
                strip.grid(row=0, column=0, sticky="ew")

                est = self._student_name(sid)
                head = ctk.CTkFrame(card, fg_color="transparent")
                head.grid(row=1, column=0, padx=12, pady=(8, 6), sticky="ew")
                head.grid_columnconfigure(0, weight=1)
                name_lbl = ctk.CTkLabel(
                    head, text=est, text_color=self._TEXT,
                    font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
                )
                name_lbl.grid(row=0, column=0, sticky="w")
                try:
                    name_lbl.configure(cursor="hand2")
                except Exception:
                    pass
                name_lbl.bind("<Button-1>", lambda e, _sid=sid: self._open_student_popup(_sid))
                ctk.CTkLabel(
                    head,
                    text=f"{len(clases_sorted)} clase(s)",
                    fg_color=self._INPUT,
                    text_color=self._TEXT,
                    corner_radius=999,
                    padx=12,
                    pady=6
                ).grid(row=0, column=1, padx=6, sticky="e")
                ctk.CTkButton(
                    head,
                    text="Ver",
                    width=60,
                    height=30,
                    corner_radius=10,
                    fg_color=self._INPUT,
                    hover_color=self._DIV,
                    text_color=self._TEXT,
                    command=lambda _sid=sid: self._open_student_popup(_sid),
                ).grid(row=0, column=2, padx=(0, 2), sticky="e")

                # Mini tabla estudiante (SIN ID)
                std = self._find_estudiante_info(sid)
                std_wrap = ctk.CTkFrame(card, fg_color=self._PANEL, corner_radius=10)
                std_wrap.grid(row=2, column=0, padx=12, pady=(2, 10), sticky="ew")

                th = ctk.CTkFrame(std_wrap, fg_color=self._INPUT, corner_radius=10)
                th.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
                for c in range(3):
                    th.grid_columnconfigure(c, weight=1)
                self._th(th, "Documento", 0)
                self._th(th, "Teléfono", 1)
                self._th(th, "Email", 2)

                tr = ctk.CTkFrame(std_wrap, fg_color="transparent")
                tr.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
                for c in range(3):
                    tr.grid_columnconfigure(c, weight=1)
                self._td(tr, std.get("documento") or "—", 0)
                self._td(tr, std.get("telefono") or "—", 1)
                self._td(tr, std.get("email") or "—", 2)

                # Lista de clases del estudiante en el día (compacta)
                clases_wrap = ctk.CTkFrame(card, fg_color="transparent")
                clases_wrap.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="ew")
                clases_wrap.grid_columnconfigure(0, weight=1)

                hdr = ctk.CTkFrame(clases_wrap, fg_color=self._INPUT, corner_radius=10)
                hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
                hdr.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(hdr, text="Hora", text_color=self._MUTED, anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="w")
                ctk.CTkLabel(hdr, text="Instructor", text_color=self._MUTED, anchor="w").grid(row=0, column=1, padx=10, pady=8, sticky="w")
                ctk.CTkLabel(hdr, text="Placa", text_color=self._MUTED, anchor="w").grid(row=0, column=2, padx=10, pady=8, sticky="w")
                ctk.CTkLabel(hdr, text="Sede", text_color=self._MUTED, anchor="w").grid(row=0, column=3, padx=10, pady=8, sticky="w")
                ctk.CTkLabel(hdr, text="Estado", text_color=self._MUTED, anchor="w").grid(row=0, column=4, padx=10, pady=8, sticky="w")
                ctk.CTkLabel(hdr, text="", text_color=self._MUTED, anchor="w").grid(row=0, column=5, padx=10, pady=8, sticky="e")

                for j, r in enumerate(clases_sorted, start=1):
                    rid = self._row_key(r)

                    hi = (r.get("horaInicio") or "").strip()
                    hf = (r.get("horaFin") or "").strip()
                    hora = f"{hi} - {hf}".strip(" -") or "—"

                    pid = r.get("id_profesor") or r.get("id_instructor")
                    pro = r.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "—")
                    placa = (r.get("placa_vehiculo") or "").strip() or "—"
                    sede = self._class_sede(r)

                    line = ctk.CTkFrame(clases_wrap, fg_color="#FBFBFD", corner_radius=10, border_width=1, border_color=self._DIV)
                    line.grid(row=j, column=0, sticky="ew", pady=4)
                    line.grid_columnconfigure(1, weight=1)

                    ctk.CTkLabel(line, text=hora, text_color=self._TEXT, anchor="w",
                                 font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
                    ctk.CTkLabel(line, text=pro, text_color=self._TEXT, anchor="w").grid(row=0, column=1, padx=10, pady=10, sticky="w")
                    ctk.CTkLabel(line, text=placa, text_color=self._TEXT, anchor="w").grid(row=0, column=2, padx=10, pady=10, sticky="w")
                    ctk.CTkLabel(line, text=sede, text_color=self._TEXT, anchor="w").grid(row=0, column=3, padx=10, pady=10, sticky="w")
                    self._status_badge(line, r.get("estado", "")).grid(row=0, column=4, padx=10, pady=6, sticky="w")

                    actions = ctk.CTkFrame(line, fg_color="transparent")
                    actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

                    ctk.CTkButton(
                        actions, text="✎", width=36, height=30, corner_radius=10,
                        fg_color=self._ACCENT, hover_color=self._YELLOW, text_color="#ffffff",
                        command=lambda r_id=rid: (self._select_row(r_id), self._editar())
                    ).grid(row=0, column=0, padx=(0, 6))

                    ctk.CTkButton(
                        actions, text="🗑️", width=36, height=30, corner_radius=10,
                        fg_color=self._ACCENT, hover_color=self._YELLOW, text_color="#ffffff",
                        command=lambda r_id=rid: (self._select_row(r_id), self._eliminar())
                    ).grid(row=0, column=1)

                    line.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))

    # ============================
    # Mostrar vista
    # ============================
    def _show_view(self, name: str):
        for w in self.main.winfo_children():
            w.grid_forget()

        if name == "calendar":
            self.view_calendar.grid(row=0, column=0, sticky="nsew")
            self._calendar_mode = True
            self.btn_calendar.configure(text="⬅ Volver")
            self._sync_rows_to("right")
        else:
            self.view_normal.grid(row=0, column=0, sticky="nsew")
            self._calendar_mode = False
            self.btn_calendar.configure(text="📅 Calendario")
            self._sync_rows_to("top")

    def _toggle_calendar_mode(self):
        self._show_view("calendar" if not self._calendar_mode else "normal")

    def _restablecer_filtros(self):
        self.fecha_filtrada = None
        if hasattr(self, "f_buscar"):
            self.f_buscar.delete(0, "end")
        if hasattr(self, "f_estado"):
            self.f_estado.set("Todos")
        self._update_calendar_highlights()
        self._sync_rows_to("right" if self._calendar_mode else "top")
        self.app._info("Filtros restablecidos. Mostrando todas las clases.")

    def _debounced_apply_filters(self):
        if self._filter_after_id:
            try:
                self.after_cancel(self._filter_after_id)
            except Exception:
                pass
        self._filter_after_id = self.after(180, lambda: self._sync_rows_to("right" if self._calendar_mode else "top"))

    def _allowed_admin_sede(self) -> str:
        if getattr(self.app, "is_superadmin", False):
            return ""
        return self._normalize_admin_sede(getattr(self.app, "current_admin_sede", None))

    @staticmethod
    def _normalize_admin_sede(value) -> str:
        txt = str(value or "").strip().lower()
        if txt in {"1 de mayo", "1demayo"}:
            return "1 de Mayo"
        if txt in {"el eden", "el edén", "eden", "edén"}:
            return "El Eden"
        return str(value or "").strip()

    # ============================
    # Catálogos y datos
    # ============================
    def _cargar_catalogos_y_listar(self, force_refresh=False):
        try:
            if not (self.app and getattr(self.app, "api", None)):
                self.app._info("Modo local: sin conexión a API.")
                self._refrescar(local_only=True)
                return

            self._estudiantes = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []
            self._profesores  = self.app.api.get_all("profesores", force_refresh=force_refresh)  or []
            self._vehiculos   = self.app.api.get_all("vehiculos", force_refresh=force_refresh)   or []

            allowed_sede = self._allowed_admin_sede()
            if allowed_sede:
                self._estudiantes = [e for e in self._estudiantes if self._normalize_admin_sede(self._extract_sede_value((e or {}).get("sede") or (e or {}).get("sedePrincipal"))) == allowed_sede]
                self._profesores = [p for p in self._profesores if self._normalize_admin_sede(self._record_sede(p)) == allowed_sede]
                self._vehiculos = [v for v in self._vehiculos if self._normalize_admin_sede(self._record_sede(v)) == allowed_sede]

            self.estudiantes_id_to_name = {}
            self.profesores_id_to_name = {}
            self.estudiantes_id_to_doc = {}

            for e in self._estudiantes:
                key = e.get("id") or e.get("idEstudiante")
                if key is None:
                    continue
                nombre = f"{e.get('nombre','')} {e.get('apellido','')}".strip() or str(key)
                self.estudiantes_id_to_name[key] = nombre
                self.estudiantes_id_to_name[str(key)] = nombre

                doc = (
                    e.get("documento") or e.get("documentoEstudiante") or
                    e.get("cc") or e.get("CC") or e.get("cedula") or e.get("dni") or
                    e.get("numeroDocumento") or e.get("numDocumento") or
                    e.get("identificacion") or e.get("identificación")
                )
                self.estudiantes_id_to_doc[key] = self._normalize_doc(doc)
                self.estudiantes_id_to_doc[str(key)] = self.estudiantes_id_to_doc[key]

            for p in self._profesores:
                key = p.get("id") or p.get("idProfesor")
                if key is None:
                    continue
                nombre = f"{p.get('nombre','')} {p.get('apellido','')}".strip() or str(key)
                self.profesores_id_to_name[key] = nombre
                self.profesores_id_to_name[str(key)] = nombre

            if self.form:
                self.form.set_options(self._estudiantes, self._profesores, self._vehiculos)

            self._refrescar(force_refresh=force_refresh)
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible cargar catálogos:\n{e}", parent=self)

    # ============================
    # CRUD
    # ============================
    def _nuevo(self):
        if self.form:
            self.form.show_create()

    def _on_cancel(self):
        if self.form:
            self.form.hide()

    def _editar(self):
        if not self._selected_id:
            self.app._info("Selecciona un registro primero.")
            return
        rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
        if rec and self.form:
            self.form.show_edit(rec)

    def _eliminar(self):
        if not self._selected_id:
            self.app._info("Selecciona una clase para eliminar.")
            return
        rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
        if not rec:
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la clase de {rec.get('nombre_estudiante','este estudiante')} del {rec.get('fecha','día')}?",
            parent=self
        ):
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete(self.CLASES_RESOURCE, rec["id"])
                self.app._info("Clase eliminada.")
            else:
                self._data = [d for d in self._data if self._row_key(d) != self._selected_id]
                self.app._info("Clase eliminada (local).")
            self._selected_id = None
            self._sync_rows_to("right" if self._calendar_mode else "top")
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    def _on_submit(self, payload, mode):
        try:
            if mode == "create":
                ok, msg = self._validate_same_sede_on_create(payload or {})
                if not ok:
                    messagebox.showerror("Validación de sede", msg, parent=self)
                    return

            if self.app and getattr(self.app, "api", None):
                if mode == "create":
                    self.app.api.create(self.CLASES_RESOURCE, payload)
                    self.app._info("Clase creada.")
                    self._try_sync_google_calendar(payload)
                else:
                    rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
                    if rec and rec.get("id"):
                        self.app.api.ensure_not_modified(
                            self.CLASES_RESOURCE,
                            rec["id"],
                            rec,
                            compare_fields=[
                                "id_estudiante", "id_profesor", "placa_vehiculo", "fecha",
                                "horaInicio", "horaFin", "estado", "estadoClase",
                            ],
                            label="clase",
                        )
                        self.app.api.update(self.CLASES_RESOURCE, rec["id"], payload)
                        self.app._info("Clase actualizada.")
            else:
                if mode == "create":
                    payload["_local_id"] = int(time.time() * 1000)
                    self._data.append(payload)
                    self.app._info("Clase creada (local).")
                else:
                    for i, r in enumerate(self._data):
                        if self._row_key(r) == self._selected_id:
                            self._data[i] = {**r, **payload}
                            break
                    self.app._info("Clase actualizada (local).")

            if self.form:
                self.form.hide()
            self._sync_rows_to("right" if self._calendar_mode else "top")
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar la clase:\n{e}", parent=self)

    # ============================
    # Google Calendar sync
    # ============================
    def _try_sync_google_calendar(self, payload):
        if not getattr(self.app, "GOOGLE_CALENDAR_ENABLED", True):
            return
        if not (self.app and getattr(self.app, "api", None)):
            return

        req = self._build_google_calendar_request(payload)
        if not req:
            return

        endpoint = getattr(self.app, "GOOGLE_CALENDAR_ENDPOINT", "calendar/reuniones")
        try:
            created = self.app.api.create(endpoint, req) or {}
            meet_link = created.get("meetLink") if isinstance(created, dict) else None
            if meet_link:
                messagebox.showinfo("Google Calendar", f"Clase creada y reunión agendada.\nMeet: {meet_link}", parent=self)
            else:
                self.app._info("Clase creada y evento enviado a Google Calendar.")
        except Exception as e:
            err = str(e)
            service_account_block = ("forbiddenForServiceAccounts" in err or "cuenta de servicio" in err.lower())
            if service_account_block and req.get("asistentes"):
                try:
                    retry_req = dict(req)
                    retry_req["asistentes"] = []
                    created = self.app.api.create(endpoint, retry_req) or {}
                    meet_link = created.get("meetLink") if isinstance(created, dict) else None
                    if meet_link:
                        messagebox.showinfo(
                            "Google Calendar",
                            "Clase creada y reunión agendada sin invitados.\n"
                            f"Meet: {meet_link}",
                            parent=self
                        )
                    else:
                        self.app._info("Clase creada y evento de Calendar agendado sin invitados.")
                    return
                except Exception as retry_error:
                    err = str(retry_error)

            messagebox.showwarning(
                "Google Calendar",
                "La clase se guardó, pero no se pudo crear la reunión en Calendar:\n"
                f"{err}",
                parent=self
            )

    def _build_google_calendar_request(self, payload):
        fecha = str(payload.get("fecha") or "").strip()
        hora_inicio = str(payload.get("horaInicio") or "").strip()
        hora_fin = str(payload.get("horaFin") or "").strip()
        if not fecha or not hora_inicio or not hora_fin:
            return None

        tz_name = getattr(self.app, "GOOGLE_CALENDAR_TIMEZONE", "America/Bogota")
        calendar_id = getattr(self.app, "GOOGLE_CALENDAR_ID", "primary")

        inicio_iso = self._to_iso8601(fecha, hora_inicio, tz_name)
        fin_iso = self._to_iso8601(fecha, hora_fin, tz_name)
        if not inicio_iso or not fin_iso:
            return None

        est_id = payload.get("id_estudiante") or payload.get("idEstudiante")
        prof_id = payload.get("id_profesor") or payload.get("idProfesor")

        est = self._find_by_id(self._estudiantes, est_id, ("id", "idEstudiante"))
        prof = self._find_by_id(self._profesores, prof_id, ("id", "idProfesor"))
        vehiculo = self._find_by_placa(self._vehiculos, payload.get("placa_vehiculo"))

        est_nombre = self._person_name(est, fallback="Estudiante")
        prof_nombre = self._person_name(prof, fallback="Instructor")
        doc = self._normalize_doc((est or {}).get("numeroDocumento") or (est or {}).get("cedula"))
        placa = payload.get("placa_vehiculo") or "-"
        vehiculo_sede = (vehiculo or {}).get("sede") or "N/A"
        estado = payload.get("estado") or "Programada"

        descripcion = (
            "Clase CEA HARO\n"
            f"Estudiante: {est_nombre}\n"
            f"Documento: {doc}\n"
            f"Instructor: {prof_nombre}\n"
            f"Vehículo: {placa}\n"
            f"Sede vehículo: {vehiculo_sede}\n"
            f"Estado: {estado}"
        )

        asistentes = self._collect_attendees(est, prof)

        return {
            "titulo": f"Clase de conducción - {est_nombre}",
            "descripcion": descripcion,
            "inicio": inicio_iso,
            "fin": fin_iso,
            "zonaHoraria": tz_name,
            "calendarId": calendar_id,
            "asistentes": asistentes,
        }

    def _to_iso8601(self, fecha, hora, tz_name):
        try:
            dt_naive = datetime.datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            try:
                from zoneinfo import ZoneInfo
                dt_tz = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
                return dt_tz.isoformat(timespec="seconds")
            except Exception:
                return dt_naive.strftime("%Y-%m-%dT%H:%M:00-05:00")
        except Exception:
            return None

    def _find_by_id(self, records, expected_id, id_keys):
        if expected_id in (None, ""):
            return None
        target = str(expected_id)
        for rec in (records or []):
            for key in id_keys:
                val = rec.get(key)
                if val is not None and str(val) == target:
                    return rec
        return None

    def _find_by_placa(self, records, placa):
        p = str(placa or "").strip().upper()
        if not p:
            return None
        for rec in (records or []):
            if str(rec.get("placa") or "").strip().upper() == p:
                return rec
        return None

    def _person_name(self, person, fallback="Persona"):
        if not person:
            return fallback
        full = f"{person.get('nombre', '')} {person.get('apellido', '')}".strip()
        return full or fallback

    def _collect_attendees(self, est, prof):
        mails = []
        for person in (est, prof):
            if not person:
                continue
            mail = (person.get("email") or person.get("correo") or "").strip()
            if "@" in mail and mail not in mails:
                mails.append(mail)
        return mails

    # ============================
    # Refresh (bg)
    # ============================
    def _refrescar(self, local_only=False, force_refresh=True):
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if local_only or not (self.app and getattr(self.app, "api", None)):
            self._sync_rows_to("right" if self._calendar_mode else "top")
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                raw = self.app.api.get_all(self.CLASES_RESOURCE, force_refresh=force_refresh) or []
                if isinstance(raw, dict):
                    for key in ("content", "items", "clases", "data", "results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []
                allowed_sede = self._allowed_admin_sede()
                if allowed_sede:
                    raw = [rec for rec in (raw or []) if self._normalize_admin_sede(self._class_sede(rec)) == allowed_sede]
                self._data = raw
                self.after(0, lambda: self._sync_rows_to("right" if self._calendar_mode else "top"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Clases", f"No fue posible consultar la API:\n{e}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_current_filters(self, data):
        rows = list(data or [])
        query = (self.f_buscar.get() if hasattr(self, "f_buscar") else "" or "").strip().lower()
        estado = (self.f_estado.get() if hasattr(self, "f_estado") else "Todos" or "Todos").strip().lower()

        filtered = []
        allowed_sede = self._allowed_admin_sede()
        for rec in rows:
            if self.fecha_filtrada:
                target = self._normalize_ymd(self.fecha_filtrada)
                if self._normalize_ymd(rec.get("fecha")) != target:
                    continue

            if estado not in ("", "todos"):
                rec_estado = str(rec.get("estado") or "").strip().lower()
                if rec_estado != estado:
                    continue

            if query:
                haystack = " ".join(
                    [
                        str(rec.get("nombre_estudiante") or self._student_name(self._take_id_est(rec)) or ""),
                        str(self._get_documento_from(rec) or ""),
                        str(rec.get("nombre_instructor") or self.profesores_id_to_name.get(rec.get("id_profesor") or rec.get("id_instructor"), "") or ""),
                        str(rec.get("placa_vehiculo") or ""),
                        str(self._class_sede(rec) or ""),
                        str(rec.get("estado") or ""),
                        str(rec.get("fecha") or ""),
                    ]
                ).lower()
                if query not in haystack:
                    continue

            if allowed_sede and self._normalize_admin_sede(self._class_sede(rec)) != allowed_sede:
                continue

            filtered.append(rec)

        return filtered

    # ============================
    # Sync rows -> vista actual
    # ============================
    def _row_key(self, rec):
        return rec.get("id") or rec.get("_local_id") or (self._take_id_est(rec), rec.get("fecha"), rec.get("horaInicio"))

    def _sync_rows_to(self, where: str):
        filtered_rows = self._apply_current_filters(self._data)
        if where == "top":
            self._set_table_data(filtered_rows)
        else:
            clases_dia = filtered_rows if self.fecha_filtrada else []
            if hasattr(self, "cards_container_right") and self.cards_container_right.winfo_exists():
                self._render_vertical_cards(self.cards_container_right, clases_dia)
            self._update_calendar_highlights()

    def _normalize_ymd(self, value):
        if value is None:
            return ""
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")

        s = str(value).strip()
        if not s:
            return ""

        if "T" in s:
            s = s.split("T", 1)[0]
        if " " in s:
            s = s.split(" ", 1)[0]
        if len(s) >= 10:
            s = s[:10]

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return s

    # ============================
    # Valores por fila
    # ============================
    def _row_values(self, rec):
        id_est = self._take_id_est(rec)
        est = rec.get("nombre_estudiante") or self._student_name(id_est)
        doc = self._get_documento_from(rec)
        pid = rec.get("id_profesor") or rec.get("id_instructor")
        pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "")
        sede = self._class_sede(rec)
        return [
            est,
            doc,
            pro,
            rec.get("placa_vehiculo", ""),
            sede,
            rec.get("fecha", ""),
            rec.get("estado", ""),
        ]

    def _take_id_est(self, rec):
        return rec.get("id_estudiante") or rec.get("idEstudiante") or rec.get("estudianteId")

    def _student_name(self, id_est):
        if id_est in (None, ""):
            return "Estudiante"
        return (
            self.estudiantes_id_to_name.get(id_est)
            or self.estudiantes_id_to_name.get(str(id_est))
            or "Estudiante"
        )

    def _student_area(self, id_est):
        e = self._find_by_id(self._estudiantes, id_est, ("id", "idEstudiante"))
        tipo = str((e or {}).get("tipoPase") or "").strip().lower()
        cat = str(
            (e or {}).get("categoria")
            or (e or {}).get("categoriaLicencia")
            or (e or {}).get("licenciaCategoria")
            or ""
        ).strip().upper()

        if "carro" in tipo and "moto" in tipo:
            return ("mixto", "Carro + Moto")
        if "carro" in tipo:
            return ("carro", "Carro")
        if "moto" in tipo:
            return ("moto", "Moto")

        if cat:
            if cat.startswith("A"):
                return ("moto", "Moto")
            if cat in {"B1", "C1"}:
                return ("carro", "Carro")

        return ("otros", "Otros")

    @staticmethod
    def _extract_sede_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for k in ("nombre", "name", "sede", "descripcion"):
                v = value.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
            if value.get("id") not in ("", None):
                return str(value.get("id")).strip()
            return ""
        txt = str(value).strip()
        return txt

    def _class_sede(self, rec) -> str:
        try:
            sid = self._take_id_est(rec)
            est = self._find_by_id(self._estudiantes, sid, ("id", "idEstudiante"))
            sede_est = self._extract_sede_value((est or {}).get("sede") or (est or {}).get("sedePrincipal"))

            veh = self._find_by_placa(self._vehiculos, rec.get("placa_vehiculo"))
            sede_veh = self._extract_sede_value((veh or {}).get("sede"))

            sede = sede_est or sede_veh
            return sede or "—"
        except Exception:
            return "—"

    def _record_sede(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""

        for key in ("sede", "sedePrincipal", "sede_principal", "sedeNombre", "nombreSede", "campus"):
            val = rec.get(key)
            if val not in ("", None):
                return self._extract_sede_value(val)

        for key in ("idSede", "sedeId", "sede_id"):
            val = rec.get(key)
            if val not in ("", None):
                return str(val).strip()

        return ""

    @staticmethod
    def _norm_sede(sede: str) -> str:
        return str(sede or "").strip().lower()

    def _validate_same_sede_on_create(self, payload):
        """
        Valida que estudiante, instructor y vehículo pertenezcan a la misma sede.
        Retorna (ok: bool, msg: str).
        """
        try:
            est_id = payload.get("id_estudiante") or payload.get("idEstudiante")
            prof_id = (
                payload.get("id_profesor") or payload.get("idProfesor")
                or payload.get("id_instructor") or payload.get("idInstructor")
            )
            placa = payload.get("placa_vehiculo") or payload.get("placaVehiculo")

            est = self._find_by_id(self._estudiantes, est_id, ("id", "idEstudiante"))
            prof = self._find_by_id(self._profesores, prof_id, ("id", "idProfesor"))
            veh = self._find_by_placa(self._vehiculos, placa)

            sede_est = self._record_sede(est)
            sede_prof = self._record_sede(prof)
            sede_veh = self._record_sede(veh)

            missing = []
            if not sede_est:
                missing.append("estudiante")
            if not sede_prof:
                missing.append("instructor")
            if not sede_veh:
                missing.append("vehículo")

            if missing:
                return (
                    False,
                    "No se pudo validar la sede porque falta en: "
                    + ", ".join(missing)
                    + ".\n\n"
                    "Asigna la sede en Estudiantes/Instructores/Vehículos y vuelve a intentar.",
                )

            if len({self._norm_sede(sede_est), self._norm_sede(sede_prof), self._norm_sede(sede_veh)}) != 1:
                est_name = self._person_name(est, fallback=str(est_id or "Estudiante"))
                prof_name = self._person_name(prof, fallback=str(prof_id or "Instructor"))
                placa_txt = str(placa or "").strip().upper() or "—"
                return (
                    False,
                    "La clase práctica debe quedar en una sola sede.\n\n"
                    f"Estudiante ({est_name}): {sede_est or '—'}\n"
                    f"Instructor ({prof_name}): {sede_prof or '—'}\n"
                    f"Vehículo ({placa_txt}): {sede_veh or '—'}\n\n"
                    "Selecciona estudiante/instructor/vehículo de la misma sede.",
                )

            return True, ""
        except Exception as e:
            return False, f"No fue posible validar la sede:\n{e}"

    # ============================
    # Documento robusto
    # ============================
    def _normalize_doc(self, doc_value):
        invalid = {"-1", "-2", "-3", "0", "None", "null", ""}
        if doc_value is None:
            return "—"
        if isinstance(doc_value, (int, float)):
            try:
                doc_value = str(int(doc_value))
            except Exception:
                doc_value = str(doc_value)
        doc = str(doc_value).strip()
        if doc in invalid or doc.startswith("-"):
            return "—"
        return doc

    def _get_documento_from(self, rec):
        for key in (
            "documento", "documento_estudiante", "documentoEstudiante",
            "cc", "CC", "cedula", "cédula", "dni", "DNI",
            "numeroDocumento", "numDocumento", "num_documento",
            "identificacion", "identificación", "idNumero", "nroDocumento"
        ):
            if key in rec and rec.get(key):
                return self._normalize_doc(rec.get(key))

        id_est = self._take_id_est(rec)
        if id_est in self.estudiantes_id_to_doc:
            return self.estudiantes_id_to_doc.get(id_est, "—")

        try:
            e = next((x for x in self._estudiantes if (x.get("id") or x.get("idEstudiante")) == id_est), None)
            if e:
                for key in (
                    "documento", "documentoEstudiante",
                    "cc", "cedula", "dni", "numeroDocumento", "numDocumento",
                    "identificacion"
                ):
                    if key in e and e.get(key):
                        doc = self._normalize_doc(e.get(key))
                        self.estudiantes_id_to_doc[id_est] = doc
                        return doc
        except Exception:
            pass

        return "—"

    # ============================
    # Selección / highlight
    # ============================
    def _select_row(self, rid):
        self._selected_id = rid
        if not self._calendar_mode:
            try:
                if getattr(self, "tree", None) and self.tree.winfo_exists():
                    iid = (self._key_to_iid or {}).get(rid)
                    if iid:
                        self.tree.selection_set(iid)
                        self.tree.see(iid)
            except Exception:
                pass

    # ============================
    # Calendario
    # ============================
    def _init_calendar(self):
        self._cal_year = datetime.date.today().year
        self._cal_month = datetime.date.today().month

        header = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        def nav_btn(text, cb):
            return ctk.CTkButton(
                header, text=text, width=36, height=28, corner_radius=10,
                fg_color=self._ACCENT, hover_color=self._YELLOW,
                text_color="#ffffff", command=cb
            )

        nav_btn("◀", lambda: (self._shift_month(-1), self._build_calendar_grid())).pack(side="left", padx=(0, 6))
        nav_btn("▶", lambda: (self._shift_month(+1), self._build_calendar_grid())).pack(side="right", padx=(6, 0))

        self.lbl_month = ctk.CTkLabel(header, text="", text_color=self._TEXT,
                                      font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_month.pack(side="left", expand=True)

        self.cal_grid = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.cal_grid.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.lbl_cal_info = ctk.CTkLabel(self.cal_frame, text="", text_color=self._MUTED, anchor="w")
        self.lbl_cal_info.pack(fill="x", padx=8, pady=(0, 8))

        self._build_calendar_grid()

    def _shift_month(self, delta):
        self._cal_month += delta
        while self._cal_month > 12:
            self._cal_month -= 12
            self._cal_year += 1
        while self._cal_month < 1:
            self._cal_month += 12
            self._cal_year -= 1

    def _build_calendar_grid(self):
        for w in self.cal_grid.winfo_children():
            w.destroy()

        hoy = datetime.date.today()
        mes_nombre = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{mes_nombre} {self._cal_year}")

        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for i, d in enumerate(dias_semana):
            ctk.CTkLabel(self.cal_grid, text=d, text_color=self._MUTED) \
                .grid(row=0, column=i, padx=6, pady=4)

        self._cal_day_buttons = {}
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(self._cal_year, self._cal_month)

        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day.month != self._cal_month:
                    ctk.CTkLabel(self.cal_grid, text=str(day.day), text_color=self._MUTED) \
                        .grid(row=r, column=ccol, padx=4, pady=4)
                else:
                    btn = ctk.CTkButton(
                        self.cal_grid, text=str(day.day),
                        width=44, height=34, corner_radius=10,
                        fg_color=self._PANEL, hover_color=self._ACCENT,
                        text_color=self._TEXT,
                        command=lambda d=day: self._on_calendar_day_click(d)
                    )
                    btn.grid(row=r, column=ccol, padx=4, pady=4, sticky="nsew")
                    self._cal_day_buttons[day] = btn

        self._update_calendar_highlights()

    def _update_calendar_highlights(self):
        hoy = datetime.date.today()
        dias_con_clases = set()

        for item in (self._data or []):
            try:
                f = self._normalize_ymd(item.get("fecha"))
                if not f:
                    continue
                dt = datetime.datetime.strptime(f, "%Y-%m-%d").date()
                if dt.year == self._cal_year and dt.month == self._cal_month:
                    dias_con_clases.add(dt)
            except Exception:
                pass

        for day, btn in self._cal_day_buttons.items():
            try:
                if day == hoy:
                    btn.configure(fg_color="#FFD966", text_color="#000000")
                elif self.fecha_filtrada:
                    sel = datetime.datetime.strptime(self._normalize_ymd(self.fecha_filtrada), "%Y-%m-%d").date()
                    if day == sel:
                        btn.configure(fg_color="#FFD966", text_color="#000000")
                        continue

                if day in dias_con_clases:
                    btn.configure(fg_color=self._ACCENT, text_color="#ffffff")
                elif day != hoy:
                    btn.configure(fg_color=self._PANEL, text_color=self._TEXT)
            except Exception:
                pass

        month_name = datetime.date(self._cal_year, self._cal_month, 1).strftime("%B")
        self.lbl_cal_info.configure(text=f"{len(dias_con_clases)} día(s) con clases en {month_name} {self._cal_year}")

    def _on_calendar_day_click(self, day: datetime.date):
        clicked = day.strftime("%Y-%m-%d")
        self.fecha_filtrada = None if self.fecha_filtrada == clicked else clicked
        self._update_calendar_highlights()
        clases_dia = self._apply_current_filters(self._data) if self.fecha_filtrada else []
        self._render_vertical_cards(self.cards_container_right, clases_dia)

    # ============================
    # Loading overlay
    # ============================
    def _show_loading(self, on=True, text="Actualizando…"):
        target = self.table_right if self._calendar_mode else self.table
        if on:
            if getattr(self, "_loading_overlay", None):
                try:
                    self._loading_overlay.destroy()
                except Exception:
                    pass
            self._loading_overlay = ctk.CTkLabel(
                target, text=text, text_color=self._MUTED,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            self._loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        else:
            if getattr(self, "_loading_overlay", None):
                try:
                    self._loading_overlay.destroy()
                except Exception:
                    pass
                self._loading_overlay = None

    # ============================
    # Helpers UI
    # ============================
    def _status_badge(self, parent, estado: str):
        raw = (estado or "").strip()
        low = raw.lower()
        text = raw.capitalize() if raw else "—"

        bg = self._YELLOW
        fg = "#111111"

        if low in ("cancelada", "cancelado", "anulada", "no realizada"):
            bg, fg = self._ACCENT, "#ffffff"
        elif low in ("completada", "asistida", "aprobada", "hecha"):
            bg, fg = "#2ECC71", "#ffffff"

        return ctk.CTkLabel(
            parent,
            text=text,
            fg_color=bg,
            text_color=fg,
            corner_radius=999,
            padx=14,
            pady=6
        )

    def _find_estudiante_info(self, id_est):
        res = {}
        try:
            e = self._find_by_id(self._estudiantes, id_est, ("id", "idEstudiante"))
            if not e:
                return {}
            res["documento"] = self._normalize_doc(
                e.get("documento") or e.get("documentoEstudiante") or
                e.get("cc") or e.get("cedula") or e.get("dni") or
                e.get("numeroDocumento") or e.get("numDocumento") or
                e.get("identificacion")
            )
            res["telefono"] = e.get("telefono") or e.get("celular") or e.get("phone")
            res["email"] = e.get("email") or e.get("correo")
            res["tipoPase"] = e.get("tipoPase")
            res["categoria"] = e.get("categoria") or e.get("categoriaLicencia") or e.get("licenciaCategoria")
            return res
        except Exception:
            return {}

    def _open_student_popup(self, id_est):
        est = self._find_by_id(self._estudiantes, id_est, ("id", "idEstudiante"))
        if not est:
            messagebox.showinfo("Estudiante", "No se encontró el estudiante en los catálogos.", parent=self)
            return

        name = self._student_name(id_est)
        sede = self._extract_sede_value(est.get("sede") or est.get("sedePrincipal")) or "—"
        tipo = str(est.get("tipoPase") or "").strip() or "—"
        categoria = str(
            est.get("categoria")
            or est.get("categoriaLicencia")
            or est.get("licenciaCategoria")
            or ""
        ).strip().upper() or "—"

        doc = (
            est.get("numeroDocumento")
            or est.get("documento")
            or est.get("documentoEstudiante")
            or est.get("cc")
            or est.get("cedula")
            or est.get("dni")
            or est.get("identificacion")
        )
        doc = self._normalize_doc(doc)

        tel = est.get("telefono") or est.get("celular") or est.get("phone") or "—"
        email = est.get("email") or est.get("correo") or "—"
        direccion = est.get("direccion") or est.get("dirección") or est.get("dir") or "—"
        estado = est.get("estado") or "—"

        top = ctk.CTkToplevel(self)
        top.title(f"Estudiante — {name}")
        top.geometry("560x440")
        top.minsize(520, 420)
        try:
            top.configure(fg_color=self._BG)
        except Exception:
            pass
        try:
            top.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            top.grab_set()
        except Exception:
            pass

        wrap = ctk.CTkFrame(
            top,
            fg_color=self._PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self._DIV,
        )
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        strip = ctk.CTkFrame(wrap, fg_color=self._ACCENT, height=6, corner_radius=16)
        strip.pack(fill="x")

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 6))
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head, text=name, text_color=self._TEXT,
            font=ctk.CTkFont(size=18, weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="w")

        meta = f"Sede: {sede} | Categoría: {categoria} | Tipo: {tipo}"
        ctk.CTkLabel(head, text=meta, text_color=self._MUTED, anchor="w").grid(row=1, column=0, pady=(2, 0), sticky="w")

        body = ctk.CTkScrollableFrame(wrap, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        inner = getattr(body, "_scrollable_frame", None) or getattr(body, "scrollable_frame", None) or body
        inner.grid_columnconfigure(1, weight=1)

        def field(r, label, value):
            ctk.CTkLabel(inner, text=label, text_color=self._MUTED, anchor="w") \
                .grid(row=r, column=0, padx=(10, 8), pady=6, sticky="w")
            ctk.CTkLabel(
                inner,
                text=str(value or "—"),
                text_color=self._TEXT,
                anchor="w",
                justify="left",
                wraplength=360
            ).grid(row=r, column=1, padx=(0, 10), pady=6, sticky="ew")

        field(0, "Documento", doc)
        field(1, "Teléfono", tel)
        field(2, "Email", email)
        field(3, "Dirección", direccion)
        field(4, "Sede", sede)
        field(5, "Categoría", categoria)
        field(6, "Tipo pase", tipo)
        field(7, "Estado", estado)

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(
            btns,
            text="Cerrar",
            height=36,
            corner_radius=12,
            fg_color=self._ACCENT,
            hover_color=self._YELLOW,
            text_color="#ffffff",
            command=top.destroy,
        ).pack(side="right")

    def _th(self, parent, text, col):
        ctk.CTkLabel(
            parent, text=text, text_color=self._MUTED, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=col, padx=10, pady=8, sticky="ew")

    def _td(self, parent, text, col):
        box = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color=self._DIV)
        box.grid(row=0, column=col, padx=6, pady=2, sticky="ew")
        wrap = 120 if col == 0 else 140 if col == 1 else 260
        ctk.CTkLabel(
            box,
            text=str(text or "—"),
            text_color=self._TEXT,
            anchor="w",
            justify="left",
            wraplength=wrap
        ).grid(row=0, column=0, padx=8, pady=6, sticky="w")
