# modules/clases.py
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import datetime, calendar, threading, time

from modules.base import BaseModuleFrame
from modules.forms_inlines import ClaseInlineForm


class ClasesView(BaseModuleFrame):
    """
    Clases:
      • Vista normal: tabla con columnas Estudiante, Documento, Instructor, Placa, Fecha, Estado, Acciones.
      • Vista calendario: calendario + tarjetas verticales con mini "tabla" del estudiante (sin ID).
    """
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 5
    MIN_REFRESH_INTERVAL = 500  # ms

    # === Tamaños/padding (↑ más espacio por fila ≈ 0.5 cm ~ 19 px) ===
    ROW_HEIGHT = 56
    ROW_PADY   = (8, 8)     # separación entre filas
    CELL_PADY  = (8, 8)     # padding vertical de cada celda
    HEADER_PADY = (10, 6)

    def __init__(self, master):
        super().__init__(master, "Clases", "Gestión de clases teóricas y prácticas")
        self.app = self.winfo_toplevel()

        # ===== Estado =====
        self._data = []
        self._row_frames = {}
        self._rows_widgets = {}
        self._row_order = []
        self._selected_id = None
        self._last_refresh_ts = 0
        self.fecha_filtrada = None
        self._calendar_mode = False

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

        # Zebra
        self._ROW_1 = "#FFFFFF"
        self._ROW_2 = "#FAFAFB"

        # ===== Layout raíz =====
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")
        tb.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(tb, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="w")

        def red_btn(text, cmd):
            return ctk.CTkButton(
                bar, text=text, height=36, corner_radius=12,
                fg_color=self._ACCENT, hover_color=self._YELLOW,
                text_color="#ffffff", command=cmd
            )

        self.btn_calendar = ctk.CTkButton(
            bar, text="📅 Calendario", height=36, corner_radius=12,
            fg_color=self._INPUT, hover_color=self._DIV,
            text_color=self._TEXT, command=self._toggle_calendar_mode
        )
        self.btn_calendar.grid(row=0, column=0, padx=(0, 8))

        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=1, padx=(0, 8))
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=(0, 8))

        # ===== Form inline =====
        try:
            self.form = ClaseInlineForm(self, self.app, self._on_submit, self._on_cancel)
            self.form.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
            self.form.hide()
        except Exception as e:
            print(f("[Clases] No se pudo crear el formulario: {e}"))
            self.form = None

        # ===== Contenedor principal =====
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Vistas
        self._build_normal_view()    # tabla
        self._build_calendar_view()  # calendario + tarjetas
        self._show_view("normal")

        # Overlay de carga
        self._loading_overlay = None

        # Carga inicial
        self.after(150, self._cargar_catalogos_y_listar)
        self._set_data(self._data)
        self._show_loading(False)

    # ============================
    # VISTA NORMAL: TABLA
    # ============================
    def _build_normal_view(self):
        self.view_normal = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_normal.grid(row=0, column=0, sticky="nsew")
        self.view_normal.grid_columnconfigure(0, weight=1)
        self.view_normal.grid_rowconfigure(0, weight=1)

        self.table = ctk.CTkScrollableFrame(self.view_normal, fg_color=self._BG, corner_radius=12)
        self.table.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        inner = getattr(self.table, "_scrollable_frame", None) or getattr(self.table, "scrollable_frame", None)
        if inner:
            inner.grid_columnconfigure(0, weight=1)

        # Columnas (sin horas)
        self._COLS = [
            ("Estudiante", 260, 2),
            ("Documento",  160, 1),
            ("Instructor", 220, 2),
            ("Placa",      100, 1),
            ("Fecha",      120, 1),
            ("Estado",     140, 1),
            ("Acciones",   140, 0),
        ]

        self._rows = []
        self._selected_id = None
        self._render_table()
        self.table.bind("<Configure>", lambda e: self._resize_columns())

    def _render_table(self):
        # Limpia
        for w in self.table.winfo_children():
            w.destroy()
        self._rows = []

        # Encabezado
        header = ctk.CTkFrame(self.table, fg_color=self._INPUT, corner_radius=12)
        header.grid(row=0, column=0, padx=8, pady=self.HEADER_PADY, sticky="ew")
        for i, (_, minw, weight) in enumerate(self._COLS):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)

        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(
                header, text=nombre, text_color=self._MUTED,
                anchor="w", justify="left", font=ctk.CTkFont(size=13, weight="bold")
            ).grid(row=0, column=i, padx=12, pady=6, sticky="ew")

        # Sin datos
        if not self._data:
            ctk.CTkLabel(self.table, text="Sin registros de clases", text_color=self._MUTED)\
                .grid(row=1, column=0, padx=12, pady=8, sticky="w")
            return

        # Filas
        for r, rec in enumerate(self._data, start=1):
            rid = self._row_key(rec)  # <- key interno, NO se muestra

            zebra = self._ROW_2 if (r % 2 == 0) else self._ROW_1
            row = ctk.CTkFrame(self.table, fg_color=zebra, corner_radius=12, height=self.ROW_HEIGHT)
            row.grid(row=r, column=0, padx=8, pady=self.ROW_PADY, sticky="ew")
            row.grid_propagate(False)

            # Misma cuadrícula que el header
            for i, (_, minw, weight) in enumerate(self._COLS):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)

            values = self._row_values(rec)  # [est, doc, prof, placa, fecha, estado, 'acciones']

            # Estudiante, Documento, Instructor, Placa, Fecha
            for i, val in enumerate(values[:-2]):  # hasta antes de Estado
                lbl = ctk.CTkLabel(
                    row, text=str(val or ""), text_color=self._TEXT,
                    anchor="w", justify="left",
                    font=ctk.CTkFont(size=13)
                )
                lbl.grid(row=0, column=i, padx=12, pady=self.CELL_PADY, sticky="ew")
                lbl.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))

            # Estado (badge)
            badge = self._status_badge(row, values[-2])
            badge.grid(row=0, column=len(self._COLS) - 2, padx=12, pady=self.CELL_PADY, sticky="w")

            # Acciones
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=0, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(
                    actions, text=symbol, width=36, height=28, corner_radius=10,
                    fg_color=self._ACCENT, hover_color=self._YELLOW,
                    text_color="#ffffff", command=cmd
                )
            icon_btn("✎", lambda r_id=rid: (self._select_row(r_id), self._editar())).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda r_id=rid: (self._select_row(r_id), self._eliminar())).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
            self._rows.append(row)

    def _resize_columns(self):
        """Mantiene proporción de columnas al redimensionar (vista normal)."""
        try:
            total_weight = max(1, sum(c[2] for c in self._COLS))
            total_width = self.table.winfo_width()
            for w in self._rows:
                for i, (_, _minw, weight) in enumerate(self._COLS):
                    new_width = int(total_width * (weight / total_weight))
                    w.grid_columnconfigure(i, minsize=new_width, weight=weight)
        except Exception:
            pass

    # ============================
    # VISTA CALENDARIO + TARJETAS
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
        ctk.CTkLabel(header, text="Clases del día", text_color=self._MUTED,
                     anchor="w", font=ctk.CTkFont(size=13, weight="bold"))\
            .grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.cards_container_right = ctk.CTkFrame(self.table_right, fg_color="transparent")
        self.cards_container_right.grid(row=1, column=0, sticky="nsew")
        self.table_right.grid_rowconfigure(1, weight=1)
        self.cards_container_right.grid_columnconfigure(0, weight=1)

    def _render_vertical_cards(self, parent, records):
        for w in parent.winfo_children():
            try: w.destroy()
            except Exception: pass

        if not records:
            ctk.CTkLabel(parent, text="Sin clases programadas para este día.",
                         text_color=self._MUTED, anchor="w")\
                .grid(row=0, column=0, padx=16, pady=16, sticky="w")
            return

        for i, rec in enumerate(records):
            rid = self._row_key(rec)  # key interna, NO se muestra

            card = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=14,
                                border_width=2, border_color=self._DIV)
            card.grid(row=i, column=0, padx=8, pady=(6 if i else 4, 8), sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            # Cabecera
            strip = ctk.CTkFrame(card, fg_color=self._ACCENT, height=6, corner_radius=14)
            strip.grid(row=0, column=0, sticky="ew")

            est = rec.get("nombre_estudiante") or self.estudiantes_id_to_name.get(self._take_id_est(rec), "Estudiante")
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.grid(row=1, column=0, padx=12, pady=(8, 6), sticky="ew")
            head.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(head, text=est, text_color=self._TEXT,
                         font=ctk.CTkFont(size=16, weight="bold"), anchor="w")\
                .grid(row=0, column=0, sticky="w")
            self._status_badge(head, rec.get("estado", "")).grid(row=0, column=1, padx=6, sticky="e")

            # Mini "tabla" del estudiante (SIN ID)
            std = self._find_estudiante_info(self._take_id_est(rec))
            std_wrap = ctk.CTkFrame(card, fg_color=self._PANEL, corner_radius=10)
            std_wrap.grid(row=2, column=0, padx=12, pady=(2, 10), sticky="ew")

            th = ctk.CTkFrame(std_wrap, fg_color=self._INPUT, corner_radius=10)
            th.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
            for c in range(3): th.grid_columnconfigure(c, weight=1)
            self._th(th, "Documento", 0); self._th(th, "Teléfono", 1); self._th(th, "Email", 2)

            tr = ctk.CTkFrame(std_wrap, fg_color="transparent")
            tr.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
            for c in range(3): tr.grid_columnconfigure(c, weight=1)
            self._td(tr, std.get("documento") or "—", 0)
            self._td(tr, std.get("telefono")  or "—", 1)
            self._td(tr, std.get("email")     or "—", 2)

            # Detalle de clase
            body = ctk.CTkFrame(card, fg_color="transparent")
            body.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")
            for c in range(3): body.grid_columnconfigure(c, weight=1)

            def kv(r, c, label, value):
                box = ctk.CTkFrame(body, fg_color="#FBFBFD", corner_radius=10)
                box.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
                box.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(box, text=label, text_color=self._MUTED, anchor="w")\
                    .grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
                ctk.CTkLabel(box, text=value or "—", text_color=self._TEXT, anchor="w",
                             font=ctk.CTkFont(size=13, weight="bold"))\
                    .grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

            pid = rec.get("id_profesor") or rec.get("id_instructor")
            pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "—")

            kv(0, 0, "Instructor", pro)
            kv(0, 1, "Placa", rec.get("placa_vehiculo", ""))
            kv(0, 2, "Fecha", rec.get("fecha", ""))

            # Notas (opcional)
            notas = rec.get("notas") or rec.get("observaciones")
            if notas:
                notes = ctk.CTkFrame(card, fg_color="#FFF9E6", corner_radius=10)
                notes.grid(row=4, column=0, padx=12, pady=(0, 10), sticky="ew")
                ctk.CTkLabel(notes, text="Notas", text_color="#7A5B00",
                             font=ctk.CTkFont(size=13, weight="bold"), anchor="w")\
                    .grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
                ctk.CTkLabel(notes, text=notas, text_color="#4B3E1D", anchor="w", justify="left")\
                    .grid(row=1, column=0, padx=10, pady=(2, 10), sticky="ew")

            # Acciones
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.grid(row=5, column=0, padx=12, pady=(0, 12), sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(
                    actions, text=symbol, width=40, height=32, corner_radius=12,
                    fg_color=self._ACCENT, hover_color=self._YELLOW,
                    text_color="#ffffff", command=cmd
                )
            icon_btn("✎ Editar",   lambda r_id=rid: (self._select_row(r_id), self._editar())).grid(row=0, column=0, padx=6)
            icon_btn("🗑️ Eliminar", lambda r_id=rid: (self._select_row(r_id), self._eliminar())).grid(row=0, column=1, padx=6)

            card.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))

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

    # ============================
    # Catálogos y datos
    # ============================
    def _cargar_catalogos_y_listar(self):
        try:
            if not (self.app and getattr(self.app, "api", None)):
                self.app._info("Modo local: sin conexión a API.")
                self._refrescar(local_only=True)
                return

            self._estudiantes = self.app.api.get_all("estudiantes") or []
            self._profesores  = self.app.api.get_all("profesores")  or []
            self._vehiculos   = self.app.api.get_all("vehiculos")   or []

            self.estudiantes_id_to_name = {}
            self.profesores_id_to_name = {}
            self.estudiantes_id_to_doc = {}

            for e in self._estudiantes:
                key = e.get("id") or e.get("idEstudiante")
                if key is None: 
                    continue
                nombre = f"{e.get('nombre','')} {e.get('apellido','')}".strip() or str(key)
                self.estudiantes_id_to_name[key] = nombre

                # documento con múltiples aliases
                doc = (
                    e.get("documento") or e.get("documentoEstudiante") or
                    e.get("cc") or e.get("CC") or e.get("cedula") or e.get("dni") or
                    e.get("numeroDocumento") or e.get("numDocumento") or
                    e.get("identificacion") or e.get("identificación")
                )
                self.estudiantes_id_to_doc[key] = self._normalize_doc(doc)

            for p in self._profesores:
                key = p.get("id") or p.get("idProfesor")
                if key is None: 
                    continue
                nombre = f"{p.get('nombre','')} {p.get('apellido','')}".strip() or str(key)
                self.profesores_id_to_name[key] = nombre

            if self.form:
                self.form.set_options(self._estudiantes, self._profesores, self._vehiculos)

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible cargar catálogos:\n{e}", parent=self)

    # ============================
    # CRUD
    # ============================
    def _nuevo(self):
        if self.form: self.form.show_create()

    def _on_cancel(self):
        if self.form: self.form.hide()

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
        if not messagebox.askyesno("Confirmar", f"¿Eliminar la clase de {rec.get('nombre_estudiante','este estudiante')} del {rec.get('fecha','día')}?"):
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("clases", rec["id"])
                self.app._info("Clase eliminada.")
            else:
                self._data = [d for d in self._data if self._row_key(d) != self._selected_id]
                self.app._info("Clase eliminada (local).")
            self._selected_id = None
            self._set_data(self._data)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    def _on_submit(self, payload, mode):
        try:
            if self.app and getattr(self.app, "api", None):
                if mode == "create":
                    self.app.api.create("clases", payload)
                    self.app._info("Clase creada.")
                else:
                    rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
                    if rec and rec.get("id"):
                        self.app.api.update("clases", rec["id"], payload)
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
            self._set_data(self._data)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar la clase:\n{e}", parent=self)

    # ============================
    # Refresh (debounced + bg)
    # ============================
    def _refrescar(self, local_only=False):
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if local_only or not (self.app and getattr(self.app, "api", None)):
            self._set_data(self._apply_current_filters(self._data))
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                raw = self.app.api.get_all("clases") or []
                if isinstance(raw, dict):
                    for key in ("content","items","clases","data","results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]; break
                    else:
                        raw = []
                self._data = raw
                self.after(0, lambda: self._set_data(self._apply_current_filters(self._data)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Clases", f"No fue posible consultar la API:\n{e}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_current_filters(self, data):
        return [d for d in data if (not self.fecha_filtrada or d.get("fecha") == self.fecha_filtrada)]

    # ============================
    # Tabla incremental / sincronización
    # ============================
    def _row_key(self, rec):
        # Clave interna (no visible)
        return rec.get("id") or rec.get("_local_id") or (self._take_id_est(rec), rec.get("fecha"), rec.get("horaInicio"))

    def _sync_rows_to(self, _where: str):
        data = self._apply_current_filters(self._data)
        self._set_data(data)

    def _set_data(self, new_data):
        if not hasattr(self, "main") or not self.main.winfo_exists():
            return

        cont = self.table if not self._calendar_mode else getattr(self, "table_right", None)
        if not cont or not cont.winfo_exists():
            return

        # Limpia contenedor visible
        for w in cont.winfo_children():
            try: w.destroy()
            except Exception: pass

        if not self._calendar_mode:
            # ===== VISTA NORMAL (tabla) =====
            header = ctk.CTkFrame(cont, fg_color=self._INPUT, corner_radius=12)
            header.grid(row=0, column=0, padx=8, pady=self.HEADER_PADY, sticky="ew")
            for i, (_, minw, weight) in enumerate(self._COLS):
                header.grid_columnconfigure(i, minsize=minw, weight=weight)
            for i, (title, _, _) in enumerate(self._COLS):
                ctk.CTkLabel(header, text=title, text_color=self._MUTED,
                             anchor="w", justify="left", font=ctk.CTkFont(size=13, weight="bold"))\
                    .grid(row=0, column=i, padx=12, pady=6, sticky="ew")

            rows_parent = ctk.CTkFrame(cont, fg_color="transparent")
            rows_parent.grid(row=1, column=0, sticky="nsew")
            cont.grid_rowconfigure(1, weight=1)
            rows_parent.grid_columnconfigure(0, weight=1)

            # Reinicia referencias de filas
            self._row_frames, self._rows_widgets, self._row_order = {}, {}, []

            data = list(new_data)
            new_ids = [self._row_key(r) for r in data]

            def paint_batch(start=0):
                if not rows_parent or not rows_parent.winfo_exists():
                    return
                end = min(start + self.ROW_BATCH_SIZE, len(data))
                for i in range(start, end):
                    rec = data[i]
                    rid = new_ids[i]
                    zebra = self._ROW_2 if ((i + 1) % 2 == 0) else self._ROW_1
                    self._create_row_widgets(i, rid, rec, zebra, rows_parent)
                    fr = self._row_frames.get(rid)
                    if fr and fr.winfo_exists():
                        fr.grid(row=i, column=0, padx=8, pady=self.ROW_PADY, sticky="ew")
                    self._row_order.append(rid)
                if end < len(data):
                    self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))

            paint_batch(0)

        else:
            # ===== VISTA CALENDARIO (tarjetas) =====
            header = ctk.CTkFrame(cont, fg_color=self._INPUT, corner_radius=12)
            header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
            ctk.CTkLabel(header, text="Clases del día", text_color=self._MUTED,
                         anchor="w", font=ctk.CTkFont(size=13, weight="bold"))\
                .grid(row=0, column=0, padx=12, pady=8, sticky="w")

            self.cards_container_right = ctk.CTkFrame(cont, fg_color="transparent")
            self.cards_container_right.grid(row=1, column=0, sticky="nsew")
            cont.grid_rowconfigure(1, weight=1)
            self.cards_container_right.grid_columnconfigure(0, weight=1)

            clases_filtradas = list(new_data) if self.fecha_filtrada else []
            self._render_vertical_cards(self.cards_container_right, clases_filtradas)
            self._update_calendar_highlights()

    def _create_row_widgets(self, visual_index, rid, rec, bg, container):
        """Fila de la tabla (vista normal)."""
        row = ctk.CTkFrame(container, fg_color=bg, corner_radius=12, height=self.ROW_HEIGHT)
        row.grid_propagate(False)

        # misma cuadrícula que el header
        for i, (_, minw, weight) in enumerate(self._COLS):
            row.grid_columnconfigure(i, minsize=minw, weight=weight)

        widgets = {}
        values = self._row_values(rec)  # [est, doc, prof, placa, fecha, estado, 'acciones']

        # Texto (alineado y con mismo padding)
        for col, val in enumerate(values[:-2]):  # hasta antes de Estado
            lbl = ctk.CTkLabel(
                row, text=str(val or ""), text_color=self._TEXT,
                anchor="w", justify="left", font=ctk.CTkFont(size=13)
            )
            lbl.grid(row=0, column=col, padx=12, pady=self.CELL_PADY, sticky="ew")
            lbl.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
            widgets[col] = lbl

        # Estado (badge)
        badge = self._status_badge(row, values[-2])
        badge.grid(row=0, column=len(self._COLS) - 2, padx=12, pady=self.CELL_PADY, sticky="w")
        widgets[len(self._COLS) - 2] = badge

        # Acciones
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=0, sticky="e")

        def icon_btn(symbol, cmd):
            return ctk.CTkButton(
                actions, text=symbol, width=36, height=28, corner_radius=10,
                fg_color=self._ACCENT, hover_color=self._YELLOW,
                text_color="#ffffff", command=cmd
            )
        icon_btn("✎", lambda r_id=rid: (self._select_row(r_id), self._editar())).grid(row=0, column=0, padx=4)
        icon_btn("🗑️", lambda r_id=rid: (self._select_row(r_id), self._eliminar())).grid(row=0, column=1, padx=4)

        row.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
        self._row_frames[rid] = row
        self._rows_widgets[rid] = widgets

    def _update_row_widgets(self, rid, rec, bg):
        row = self._row_frames.get(rid)
        if not row:
            return
        try:
            if not str(row) or not row.winfo_exists():
                return
        except Exception:
            return
        try:
            row.configure(fg_color=self._DIV if self._selected_id == rid else bg)
        except Exception:
            return

        widgets = self._rows_widgets.get(rid, {})
        values = self._row_values(rec)
        for col, val in enumerate(values[:-2]):  # celdas de texto
            w = widgets.get(col)
            if not w:
                continue
            try:
                if isinstance(w, ctk.CTkLabel) and w.cget("text") != str(val or ""):
                    w.configure(text=str(val or ""))
            except Exception:
                continue
        # badge se repinta en refresh completo si cambia el estado

    # ============================
    # Valores por fila
    # ============================
    def _row_values(self, rec):
        id_est = self._take_id_est(rec)
        est = rec.get("nombre_estudiante") or self.estudiantes_id_to_name.get(id_est, "")
        doc = self._get_documento_from(rec)
        pid = rec.get("id_profesor") or rec.get("id_instructor")
        pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "")
        return [
            est,
            doc,
            pro,
            rec.get("placa_vehiculo", ""),
            rec.get("fecha", ""),
            rec.get("estado", ""),
            "acciones",
        ]

    def _take_id_est(self, rec):
        return rec.get("id_estudiante") or rec.get("idEstudiante") or rec.get("estudianteId")

    # Documento robusto
    def _normalize_doc(self, doc_value):
        """Normaliza documento evitando solo placeholders inválidos."""
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
        """
        Obtiene documento del registro o de catálogos.
        Orden:
          1) Campos presentes en el registro de la clase (muchos aliases)
          2) Catálogo de estudiantes por id
          3) Búsqueda lenta en self._estudiantes
        """
        # 1) Busca en el propio registro con múltiples aliases
        for key in (
            "documento", "documento_estudiante", "documentoEstudiante",
            "cc", "CC", "cedula", "cédula", "dni", "DNI",
            "numeroDocumento", "numDocumento", "num_documento",
            "identificacion", "identificación", "idNumero", "nroDocumento"
        ):
            if key in rec and rec.get(key):
                return self._normalize_doc(rec.get(key))

        # 2) Catálogo por id_estudiante
        id_est = self._take_id_est(rec)
        if id_est in self.estudiantes_id_to_doc:
            return self.estudiantes_id_to_doc.get(id_est, "—")

        # 3) Búsqueda lenta una vez
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
    # Selección
    # ============================
    def _select_row(self, rid):
        if self._selected_id and self._selected_id in self._row_frames:
            fr_prev = self._row_frames.get(self._selected_id)
            try:
                if fr_prev and fr_prev.winfo_exists():
                    idx = self._row_order.index(self._selected_id) if self._selected_id in self._row_order else 0
                    prev_bg = self._ROW_2 if ((idx + 1) % 2 == 0) else self._ROW_1
                    fr_prev.configure(fg_color=prev_bg)
            except Exception:
                pass

        self._selected_id = rid
        fr_new = self._row_frames.get(rid)
        try:
            if fr_new and fr_new.winfo_exists():
                fr_new.configure(fg_color=self._DIV)
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
            return ctk.CTkButton(header, text=text, width=36, height=28, corner_radius=10,
                                 fg_color=self._ACCENT, hover_color=self._YELLOW,
                                 text_color="#ffffff", command=cb)
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
            self._cal_month -= 12; self._cal_year += 1
        while self._cal_month < 1:
            self._cal_month += 12; self._cal_year -= 1

    def _build_calendar_grid(self):
        for w in self.cal_grid.winfo_children():
            w.destroy()

        hoy = datetime.date.today()
        mes_nombre = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{mes_nombre} {self._cal_year}")

        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for i, d in enumerate(dias_semana):
            ctk.CTkLabel(self.cal_grid, text=d, text_color=self._MUTED)\
                .grid(row=0, column=i, padx=6, pady=4)

        self._cal_day_buttons = {}
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(self._cal_year, self._cal_month)

        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day.month != self._cal_month:
                    ctk.CTkLabel(self.cal_grid, text=str(day.day), text_color=self._MUTED)\
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
            f = item.get("fecha")
            if not f:
                continue
            try:
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
                    sel = datetime.datetime.strptime(self.fecha_filtrada, "%Y-%m-%d").date()
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
        self.fecha_filtrada = day.strftime("%Y-%m-%d")
        self._update_calendar_highlights()
        clases_dia = [c for c in (self._data or []) if c.get("fecha") == self.fecha_filtrada]
        self._render_vertical_cards(self.cards_container_right, clases_dia)

    # ============================
    # Loading overlay
    # ============================
    def _show_loading(self, on=True, text="Actualizando…"):
        target = self.table_right if self._calendar_mode else self.table
        if on:
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                try: self._loading_overlay.destroy()
                except Exception: pass
            self._loading_overlay = ctk.CTkLabel(
                target, text=text, text_color=self._MUTED,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            self._loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        else:
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                try: self._loading_overlay.destroy()
                except Exception: pass
                self._loading_overlay = None

    # ============================
    # Helpers UI
    # ============================
    def _status_badge(self, parent, estado: str):
        text = (estado or "").strip().capitalize()
        bg = "#F1C40F"; fg = "#1F2937"           # default amarillo
        low = text.lower()
        if low in ("completada", "asistida", "aprobada", "hecha"):
            bg, fg = "#2ECC71", "#ffffff"        # verde
        elif low in ("cancelada", "fallida", "no asistida"):
            bg, fg = "#E74C3C", "#ffffff"        # rojo
        elif text == "":
            text = "—"

        pill = ctk.CTkFrame(parent, fg_color=bg, corner_radius=999)
        lbl = ctk.CTkLabel(pill, text=text, text_color=fg, padx=10, pady=6, anchor="center")
        lbl.pack(padx=6, pady=4)
        return pill

    def _find_estudiante_info(self, id_est):
        """Busca en self._estudiantes; retorna dict (sin ID visible)."""
        res = {}
        try:
            e = next((x for x in self._estudiantes if (x.get("id") or x.get("idEstudiante")) == id_est), None)
            if not e:
                return {}
            res["documento"] = self._normalize_doc(
                e.get("documento") or e.get("documentoEstudiante") or
                e.get("cc") or e.get("cedula") or e.get("dni") or
                e.get("numeroDocumento") or e.get("numDocumento") or
                e.get("identificacion")
            )
            res["telefono"]  = e.get("telefono") or e.get("celular") or e.get("phone")
            res["email"]     = e.get("email") or e.get("correo")
            return res
        except Exception:
            return {}

    def _th(self, parent, text, col):
        ctk.CTkLabel(parent, text=text, text_color=self._MUTED, anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold"))\
            .grid(row=0, column=col, padx=10, pady=8, sticky="ew")

    def _td(self, parent, text, col):
        box = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color=self._DIV)
        box.grid(row=0, column=col, padx=6, pady=2, sticky="ew")
        ctk.CTkLabel(box, text=str(text or "—"), text_color=self._TEXT, anchor="w")\
            .grid(row=0, column=0, padx=8, pady=6, sticky="w")
