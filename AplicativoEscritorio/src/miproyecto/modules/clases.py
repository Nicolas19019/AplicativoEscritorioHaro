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
      • Modo normal: Tabla arriba (ancho completo) + Detalle abajo
      • Modo calendario: Calendario (izq.) + Tabla (der.) en la misma vista
    Render incremental, sin parpadeos.
    """
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 5
    MIN_REFRESH_INTERVAL = 500  # ms

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
        self._calendar_mode = False  # <<-- alterna la vista

        self._estudiantes, self._profesores, self._vehiculos = [], [], []
        self.estudiantes_id_to_name, self.profesores_id_to_name = {}, {}

        self._ROW_1 = self.app.COLOR_PANEL
        self._ROW_2 = self.app.COLOR_DIVIDER

        # ===== Layout raíz =====
        self.grid_rowconfigure(3, weight=1)   # el área principal crece
        self.grid_columnconfigure(0, weight=1)

        # ===== Toolbar (compacta) =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")
        tb.grid_columnconfigure(0, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(tb, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        bar = ctk.CTkFrame(tb, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="w")

        # Botones con separación corta
        px = 6
        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0, px))
        red_btn("✎ Editar", self._editar).grid(row=0, column=1, padx=px)
        red_btn("🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=px)
        self.btn_refresh = red_btn("↻ Refrescar", self._refrescar)
        self.btn_refresh.grid(row=0, column=3, padx=px)

        # Botón Calendario: alterna la vista
        self.btn_calendar = ctk.CTkButton(
            bar, text="📅 Calendario", height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT, command=self._toggle_calendar_mode
        )
        self.btn_calendar.grid(row=0, column=4, padx=(px, 0))

        # ===== Form inline (opcional) =====
        self.form = ClaseInlineForm(self, self.app, self._on_submit, self._on_cancel)
        self.form.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.form.hide()

        # ===== Contenedor principal (se reusa en ambos modos) =====
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Vistas
        self._build_normal_view()     # tabla + detalle
        self._build_calendar_view()   # calendario + tabla
        self._show_view("normal")

        # Overlay “cargando”
        self._loading_overlay = None

        # Carga inicial
        self.after(150, self._cargar_catalogos_y_listar)

    # ============================
    # Construcción de vistas
    # ============================
    def _build_normal_view(self):
        """Tabla arriba (ancho completo) + tarjeta de detalle abajo."""
        self.view_normal = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_normal.grid_columnconfigure(0, weight=1)
        self.view_normal.grid_rowconfigure(0, weight=1)  # tabla crece

        # Tabla (arriba)
        self.table_top = ctk.CTkScrollableFrame(self.view_normal, fg_color=self.app.COLOR_BG, corner_radius=12, height=480)
        self.table_top.grid(row=0, column=0, sticky="nsew")
        self._stretch_scrollable(self.table_top)

        # Header + contenedor de filas
        self._specs = [
            ("Estudiante", 240, 1, "estudiante"),
            ("Instructor", 220, 1, "instructor"),
            ("Placa",      110, 0, "placa"),
            ("Fecha",      120, 0, "fecha"),
            ("Inicio",     100, 0, "horaInicio"),
            ("Fin",        100, 0, "horaFin"),
            ("Estado",     120, 0, "estado"),
            ("Acciones",   140, 0, "_acciones"),
        ]
        self._build_table_header(self.table_top)

        # Detalle (abajo)
        self.detail_card = self._build_detail_card(self.view_normal)
        self.detail_card.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def _build_calendar_view(self):
        """Calendario a la izquierda + tabla a la derecha (misma fila)."""
        self.view_calendar = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_calendar.grid_rowconfigure(0, weight=1)
        self.view_calendar.grid_columnconfigure(0, weight=0, minsize=360)  # calendario
        self.view_calendar.grid_columnconfigure(1, weight=1)               # tabla

        # Calendario (izq)
        self.cal_frame = ctk.CTkFrame(
            self.view_calendar, fg_color=self.app.COLOR_PANEL, corner_radius=12,
            border_width=2, border_color=self.app.COLOR_DIVIDER
        )
        self.cal_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._init_calendar()  # crea estructura de calendario

        # Tabla (der) — otra instancia de scrollable que comparte motor de filas
        self.table_right = ctk.CTkScrollableFrame(self.view_calendar, fg_color=self.app.COLOR_BG, corner_radius=12, height=520)
        self.table_right.grid(row=0, column=1, sticky="nsew")
        self._stretch_scrollable(self.table_right)

        # Header + contenedor de filas (para esta vista)
        self._build_table_header(self.table_right, is_right=True)

    def _build_table_header(self, where, is_right=False):
        hdr = ctk.CTkFrame(where, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        hdr.grid(row=0, column=0, padx=8, pady=(8, 6), sticky="ew")
        for i, (_, minw, weight, _) in enumerate(self._specs):
            hdr.grid_columnconfigure(i, minsize=minw, weight=weight)
        for i, (title, _, _, _) in enumerate(self._specs):
            ctk.CTkLabel(hdr, text=title, text_color=self.app.COLOR_MUTED, anchor="w")\
                .grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        cont = ctk.CTkFrame(where, fg_color="transparent")
        cont.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        cont.grid_columnconfigure(0, weight=1)

        if is_right:
            self.rows_container_right = cont
        else:
            self.rows_container = cont

    def _build_detail_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12,
                            border_width=2, border_color=self.app.COLOR_DIVIDER)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(card, text="Detalle de la clase", text_color=self.app.COLOR_TEXT,
                             font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        title.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="ew")

        self.d_estudiante = self._detail_row(card, "Estudiante", 1, 0)
        self.d_instructor = self._detail_row(card, "Instructor", 2, 0)
        self.d_fecha     = self._detail_row(card, "Fecha",      1, 1)
        self.d_horario   = self._detail_row(card, "Horario",    2, 1)
        self.d_placa     = self._detail_row(card, "Placa",      3, 0)
        self.d_estado    = self._detail_row(card, "Estado",     3, 1)

        ctk.CTkLabel(card, text="Notas", text_color=self.app.COLOR_MUTED, anchor="w")\
            .grid(row=4, column=0, padx=12, pady=(10, 0), sticky="w")
        self.d_notas = ctk.CTkTextbox(card, height=80, corner_radius=10,
                                      fg_color=self.app.COLOR_INPUT_BG,
                                      text_color=self.app.COLOR_TEXT)
        self.d_notas.grid(row=5, column=0, columnspan=2, padx=12, pady=(4, 12), sticky="ew")
        self.d_notas.insert("1.0", "Selecciona una clase para ver el detalle.")
        self.d_notas.configure(state="disabled")
        return card

    def _detail_row(self, parent, label, row, col):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=row, column=col, padx=12, pady=6, sticky="ew")
        wrap.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(wrap, text=f"{label}:", text_color=self.app.COLOR_MUTED, width=90, anchor="w")\
            .grid(row=0, column=0, sticky="w")
        val = ctk.CTkLabel(wrap, text="—", text_color=self.app.COLOR_TEXT, anchor="w")
        val.grid(row=0, column=1, sticky="ew")
        return val

    def _show_view(self, name: str):
        """Alterna entre 'normal' y 'calendar' sin recrear todo."""
        for w in self.main.winfo_children():
            w.grid_forget()
        if name == "calendar":
            self.view_calendar.grid(row=0, column=0, sticky="nsew")
            self._calendar_mode = True
            self.btn_calendar.configure(text="⬅ Volver")
            # sincroniza filas en la tabla derecha
            self._sync_rows_to("right")
        else:
            self.view_normal.grid(row=0, column=0, sticky="nsew")
            self._calendar_mode = False
            self.btn_calendar.configure(text="📅 Calendario")
            # sincroniza filas en la tabla superior
            self._sync_rows_to("top")

    def _toggle_calendar_mode(self):
        self._show_view("calendar" if not self._calendar_mode else "normal")

    # ============================
    # Utilidades de tabla
    # ============================
    def _stretch_scrollable(self, sf):
        try: sf.grid_columnconfigure(0, weight=1)
        except Exception: pass
        try:
            inner = getattr(sf, "_scrollable_frame", None) or getattr(sf, "scrollable_frame", None)
            if inner: inner.grid_columnconfigure(0, weight=1)
        except Exception: pass

    def _container(self):
        return self.rows_container_right if self._calendar_mode else self.rows_container

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

            self.estudiantes_id_to_name = {
                (e.get("id") or e.get("idEstudiante")):
                f"{e.get('nombre','')} {e.get('apellido','')}".strip() or str(e.get("id"))
                for e in self._estudiantes if (e.get("id") or e.get("idEstudiante")) is not None
            }
            self.profesores_id_to_name = {
                (p.get("id") or p.get("idProfesor")):
                f"{p.get('nombre','')} {p.get('apellido','')}".strip() or str(p.get("id"))
                for p in self._profesores if (p.get("id") or p.get("idProfesor")) is not None
            }

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible cargar catálogos:\n{e}", parent=self)

    # ============================
    # CRUD
    # ============================
    def _nuevo(self): self.form.show_create()
    def _on_cancel(self): self.form.hide()

    def _editar(self):
        if not self._selected_id:
            self.app._info("Selecciona un registro primero.")
            return
        rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
        if rec: self.form.show_edit(rec)

    def _eliminar(self):
        if not self._selected_id:
            self.app._info("Selecciona una clase para eliminar.")
            return
        rec = next((r for r in self._data if self._row_key(r) == self._selected_id), None)
        if not rec: return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar la clase del estudiante ID {rec.get('id_estudiante')}?"):
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("clases", rec["id"])
                self.app._info("Clase eliminada.")
            else:
                self._data = [d for d in self._data if self._row_key(d) != self._selected_id]
                self.app._info("Clase eliminada (local).")
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
    # Tabla incremental (compartida por ambas vistas)
    # ============================
    def _row_key(self, rec):
        return rec.get("id") or rec.get("_local_id") or (rec.get("id_estudiante"), rec.get("fecha"), rec.get("horaInicio"))

    def _sync_rows_to(self, where: str):
        """Re-pinta filas actuales en la vista activa sin consultar API."""
        data = self._apply_current_filters(self._data)
        self._set_data(data)

    def _set_data(self, new_data):
        current_ids = set(self._row_order)
        new_ids = [self._row_key(r) for r in new_data]
        new_set = set(new_ids)

        # eliminar filas que ya no están
        for removed_id in list(current_ids - new_set):
            fr = self._row_frames.pop(removed_id, None)
            if fr: fr.destroy()
            self._rows_widgets.pop(removed_id, None)
            if removed_id in self._row_order: self._row_order.remove(removed_id)
            if self._selected_id == removed_id: self._selected_id = None

        # pintar / actualizar en lotes
        def paint_batch(start=0):
            cont = self._container()
            end = min(start + self.ROW_BATCH_SIZE, len(new_data))
            for i in range(start, end):
                rec = new_data[i]
                rid = new_ids[i]
                zebra = self._ROW_2 if ((i + 1) % 2 == 0) else self._ROW_1

                if rid in self._row_frames:
                    self._update_row_widgets(rid, rec, zebra)
                else:
                    self._create_row_widgets(i, rid, rec, zebra, cont)

                if rid not in self._row_order:
                    self._row_order.insert(i, rid)

            # posicionar visualmente hasta end
            for i, rid in enumerate(new_ids[:end]):
                fr = self._row_frames.get(rid)
                if fr: fr.grid(row=i + 1, column=0, padx=8, pady=4, sticky="ew")

            if end < len(new_data):
                self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))
            else:
                self._update_calendar_highlights()

        # Si cambio de vista, vaciar contenedor activo pero conservar frames
        cont = self._container()
        for w in cont.winfo_children(): w.destroy()

        paint_batch(0)

    def _create_row_widgets(self, visual_index, rid, rec, bg, container):
        row = ctk.CTkFrame(container, fg_color=bg, corner_radius=10)
        row.grid(row=visual_index + 1, column=0, padx=8, pady=4, sticky="ew")
        row.grid_columnconfigure(tuple(range(len(self._specs))), weight=1)

        widgets = {}
        values = self._row_values(rec)
        # columnas de texto
        for col, val in enumerate(values[:-1]):
            lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
            lbl.grid(row=0, column=col, padx=12, pady=8, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
            widgets[col] = lbl

        # Acciones
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=len(self._specs) - 1, padx=8, pady=6, sticky="e")
        def icon_btn(symbol, cmd):
            return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=8,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)
        icon_btn("✎", lambda r_id=rid: self._select_row(r_id) or self._editar()).grid(row=0, column=0, padx=4)
        icon_btn("🗑️", lambda r_id=rid: self._select_row(r_id) or self._eliminar()).grid(row=0, column=1, padx=4)

        row.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
        self._row_frames[rid] = row
        self._rows_widgets[rid] = widgets

    def _update_row_widgets(self, rid, rec, bg):
        row = self._row_frames.get(rid)
        if not row: return
        row.configure(fg_color=self.app.COLOR_DIVIDER if self._selected_id == rid else bg)
        widgets = self._rows_widgets.get(rid, {})
        values = self._row_values(rec)
        for col, val in enumerate(values[:-1]):
            lbl = widgets.get(col)
            if lbl and lbl.cget("text") != val:
                lbl.configure(text=val)

    def _row_values(self, rec):
        est = rec.get("nombre_estudiante") or self.estudiantes_id_to_name.get(rec.get("id_estudiante"), "")
        pid = rec.get("id_profesor") or rec.get("id_instructor")
        pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "")
        return [
            est,
            pro,
            rec.get("placa_vehiculo", ""),
            rec.get("fecha", ""),
            rec.get("horaInicio", ""),
            rec.get("horaFin", ""),
            rec.get("estado", ""),
            "acciones",
        ]

    # ============================
    # Selección + detalle
    # ============================
    def _select_row(self, rid):
        if self._selected_id and self._selected_id in self._row_frames:
            # restaurar zebra
            idx = (self._row_order.index(self._selected_id) if self._selected_id in self._row_order else 0)
            prev_bg = self._ROW_2 if ((idx + 1) % 2 == 0) else self._ROW_1
            self._row_frames[self._selected_id].configure(fg_color=prev_bg)

        self._selected_id = rid
        if rid in self._row_frames:
            self._row_frames[rid].configure(fg_color=self.app.COLOR_DIVIDER)

        rec = next((r for r in self._data if self._row_key(r) == rid), None)
        if rec: self._update_detail(rec)

    # ============================
    # Calendario embebido
    # ============================
    def _init_calendar(self):
        self._cal_year = datetime.date.today().year
        self._cal_month = datetime.date.today().month

        header = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        def nav_btn(text, cb):
            return ctk.CTkButton(header, text=text, width=36, height=28, corner_radius=8,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cb)
        nav_btn("◀", lambda: (self._shift_month(-1), self._build_calendar_grid())).pack(side="left", padx=(0, 6))
        nav_btn("▶", lambda: (self._shift_month(+1), self._build_calendar_grid())).pack(side="right", padx=(6, 0))

        self.lbl_month = ctk.CTkLabel(header, text="", text_color=self.app.COLOR_TEXT,
                                      font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_month.pack(side="left", expand=True)

        self.cal_grid = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.cal_grid.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.lbl_cal_info = ctk.CTkLabel(self.cal_frame, text="", text_color=self.app.COLOR_MUTED, anchor="w")
        self.lbl_cal_info.pack(fill="x", padx=8, pady=(0, 8))

        self._build_calendar_grid()

    def _shift_month(self, delta):
        self._cal_month += delta
        while self._cal_month > 12:
            self._cal_month -= 12; self._cal_year += 1
        while self._cal_month < 1:
            self._cal_month += 12; self._cal_year -= 1

    def _build_calendar_grid(self):
        for w in self.cal_grid.winfo_children(): w.destroy()
        month_name = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{month_name} {self._cal_year}")

        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for i, d in enumerate(dias_semana):
            ctk.CTkLabel(self.cal_grid, text=d, text_color=self.app.COLOR_MUTED)\
                .grid(row=0, column=i, padx=6, pady=4)

        self._cal_day_buttons = {}
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdayscalendar(self._cal_year, self._cal_month)
        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self.cal_grid, text=" ").grid(row=r, column=ccol, padx=6, pady=6)
                else:
                    btn = ctk.CTkButton(
                        self.cal_grid, text=str(day), width=44, height=34, corner_radius=8,
                        fg_color=self.app.COLOR_PANEL, hover_color=self.app.COLOR_RED,
                        text_color=self.app.COLOR_TEXT,
                        command=lambda d=day: self._on_calendar_day_click(d)
                    )
                    btn.grid(row=r, column=ccol, padx=4, pady=4, sticky="nsew")
                    self._cal_day_buttons[day] = btn

        self._update_calendar_highlights()

    def _update_calendar_highlights(self):
        dias_con_clases = set()
        for item in (self._apply_current_filters(self._data) or []):
            f = item.get("fecha")
            if not f: continue
            try:
                dt = datetime.datetime.strptime(f, "%Y-%m-%d").date()
                if dt.year == self._cal_year and dt.month == self._cal_month:
                    dias_con_clases.add(dt.day)
            except Exception:
                pass

        for day, btn in self._cal_day_buttons.items():
            btn.configure(fg_color=self.app.COLOR_YELLOW if day in dias_con_clases else self.app.COLOR_PANEL)

        month_name = calendar.month_name[self._cal_month]
        self.lbl_cal_info.configure(text=f"{len(dias_con_clases)} día(s) con clases en {month_name} {self._cal_year}")

    def _on_calendar_day_click(self, day: int):
        sel = datetime.date(self._cal_year, self._cal_month, day)
        self.fecha_filtrada = sel.strftime("%Y-%m-%d")
        self._set_data(self._apply_current_filters(self._data))

    # ============================
    # Loading overlay
    # ============================
    def _show_loading(self, on=True, text="Actualizando…"):
        target = self.table_right if self._calendar_mode else self.table_top
        if on and not hasattr(self, "_loading_overlay") or (on and self._loading_overlay is None):
            self._loading_overlay = ctk.CTkLabel(
                target, text=text, text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=14, weight="bold"))
            self._loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        elif not on and self._loading_overlay:
            self._loading_overlay.destroy()
            self._loading_overlay = None

    # ============================
    # Form
    # ============================
    def _on_cancel(self): self.form.hide()
