# modules/clases.py
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import datetime, calendar

from modules.base import BaseModuleFrame
from modules.forms_inlines import ClaseInlineForm


class ClasesView(BaseModuleFrame):
    """
    Gestión de clases teóricas y prácticas, con calendario embebido (sin tkcalendar).
    """
    def __init__(self, master):
        super().__init__(master, "Clases", "Gestión de clases teóricas y prácticas")
        self.app = self.winfo_toplevel()

        # -------- estado --------
        self._data = []           # registros de clases
        self._rows = []
        self._selected_idx = None
        self.fecha_filtrada = None
        self._calendar_visible = False
        self._cal_container = None

        # Catálogos y mapas para nombres
        self._estudiantes = []
        self._profesores = []
        self._vehiculos = []
        self.estudiantes_id_to_name = {}
        self.profesores_id_to_name = {}

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0,6), sticky="ew")
        for c in range(6):
            tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(6, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8))
        red_btn("✎ Editar", self._editar).grid(row=0, column=1, padx=8)
        red_btn("🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=8)
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8)

        ctk.CTkButton(
            tb, text="📅 Calendario", height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self._toggle_calendar
        ).grid(row=0, column=4, padx=8)

        # ===== Calendario (estructura embebida) =====
        self._init_calendar_widgets()

        # ===== Formulario =====
        self.form = ClaseInlineForm(self, self.app, self._on_submit, self._on_cancel)
        self.form.grid(row=4, column=0, padx=16, pady=(8,10), sticky="ew")
        self.form.hide()

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=5, column=0, padx=16, pady=(0,8), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        # Cargar datos
        self.after(150, self._cargar_catalogos_y_listar)

    # ===========================================================
    #   CARGA DE CATÁLOGOS + LISTADO
    # ===========================================================
    def _cargar_catalogos_y_listar(self):
        try:
            if not (self.app and getattr(self.app, "api", None)):
                self.app._info("Modo local: sin conexión a API.")
                self._refrescar(local_only=True)
                return

            self._estudiantes = self.app.api.get_all("estudiantes") or []
            self._profesores  = self.app.api.get_all("profesores")  or []
            self._vehiculos   = self.app.api.get_all("vehiculos")   or []

            # Mapas de nombres (para popup y tabla si llega solo id)
            self.estudiantes_id_to_name = {}
            for e in self._estudiantes:
                eid = e.get("id") or e.get("idEstudiante")
                nombre = "{} {}".format(e.get("nombre",""), e.get("apellido","")).strip()
                if eid is not None:
                    self.estudiantes_id_to_name[eid] = nombre or str(eid)

            self.profesores_id_to_name = {}
            for p in self._profesores:
                pid = p.get("id") or p.get("idProfesor")
                nombre = "{} {}".format(p.get("nombre",""), p.get("apellido","")).strip()
                if pid is not None:
                    self.profesores_id_to_name[pid] = nombre or str(pid)

            # opciones para el form
            self.form.set_options(self._estudiantes, self._profesores, self._vehiculos)

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible cargar catálogos:\n{e}", parent=self)

    # ===========================================================
    #   CRUD
    # ===========================================================
    def _nuevo(self): self.form.show_create()
    def _on_cancel(self): self.form.hide()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un registro primero.")
            return
        self.form.show_edit(self._data[self._selected_idx])

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona una clase para eliminar.")
            return
        rec = self._data[self._selected_idx]
        est = rec.get("id_estudiante")
        if not messagebox.askyesno("Confirmar", f"¿Eliminar la clase del estudiante ID {est}?"):
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("clases", rec["id"])
                self.app._info("Clase eliminada correctamente.")
            else:
                del self._data[self._selected_idx]
                self.app._info("Clase eliminada (local).")
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    def _on_submit(self, payload, mode):
        try:
            if self.app and getattr(self.app, "api", None):
                if mode == "create":
                    self.app.api.create("clases", payload)
                    self.app._info("Clase creada.")
                else:
                    rec = self._data[self._selected_idx]
                    self.app.api.update("clases", rec["id"], payload)
                    self.app._info("Clase actualizada.")
            else:
                if mode == "create":
                    payload["_local_id"] = (max([r.get("_local_id",0) for r in self._data] or [0]) + 1)
                    self._data.append(payload)
                    self.app._info("Clase creada (local).")
                else:
                    self._data[self._selected_idx].update(payload)
                    self.app._info("Clase actualizada (local).")
            self._refrescar(local_only=True)
            self.form.hide()
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar la clase:\n{e}", parent=self)

    # ===========================================================
    #   TABLA
    # ===========================================================
    def _apply_colspecs(self, container):
        # (título, minsize, weight) — mismos specs para header y filas
        specs = [
            ("Estudiante", 220, 1),
            ("Instructor", 200, 1),
            ("Placa",      110, 0),
            ("Fecha",      120, 0),
            ("Inicio",     100, 0),
            ("Fin",        100, 0),
            ("Estado",     120, 0),
            ("Acciones",   140, 0),
        ]
        for i, (_, minw, weight) in enumerate(specs):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)
        return specs

    def _refrescar(self, local_only=False):
        try:
            if self.app and getattr(self.app, "api", None) and not local_only:
                raw = self.app.api.get_all("clases") or []
                if isinstance(raw, dict):
                    for key in ("content","items","clases","data","results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []
                self._data = raw

            # filtro por fecha si viene del calendario
            if self.fecha_filtrada:
                self._data = [d for d in self._data if (d.get("fecha") == self.fecha_filtrada)]

            self._render_table()
            # re-pintar resaltados del calendario (días con clases)
            try: self._render_month()
            except Exception: pass
        except Exception as e:
            messagebox.showerror("Clases", f"No fue posible consultar la API:\n{e}", parent=self)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        specs = self._apply_colspecs(self.table)

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        for i, (title, _, _) in enumerate(specs):
            ctk.CTkLabel(header, text=title, text_color=self.app.COLOR_MUTED,
                         anchor="w").grid(row=0, column=i, padx=10, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin registros", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, rec in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            for i, (_, minw, weight) in enumerate(specs):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)

            # valores visibles: intenta usar nombres si el backend no envía ya el nombre
            est = rec.get("nombre_estudiante") or self.estudiantes_id_to_name.get(rec.get("id_estudiante"), "")
            pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(rec.get("id_profesor"), "")
            vals = [
                est,
                pro,
                rec.get("placa_vehiculo",""),
                rec.get("fecha",""),
                rec.get("horaInicio",""),
                rec.get("horaFin",""),
                rec.get("estado","")
            ]

            # columnas de texto
            for i, val in enumerate(vals):
                if i == len(vals) - 1:
                    # Acciones
                    actions = ctk.CTkFrame(row, fg_color="transparent")
                    actions.grid(row=0, column=i, padx=6, pady=6, sticky="e")

                    def icon_btn(symbol, cmd):
                        return ctk.CTkButton(
                            actions, text=symbol, width=36, height=32, corner_radius=8,
                            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                            text_color="#ffffff", command=cmd
                        )
                    icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
                    icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)
                else:
                    lbl = ctk.CTkLabel(row, text=str(val), text_color=self.app.COLOR_TEXT,
                                       anchor="w", justify="left")
                    lbl.grid(row=0, column=i, padx=10, pady=8, sticky="nsew")
                    lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            self._rows.append(row)

    # ===========================================================
    #   SELECCIÓN / ACCIONES DE FILA
    # ===========================================================
    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _delete_row(self, idx):
        self._select_row(idx)
        rec = self._data[idx]
        if not messagebox.askyesno("Confirmar", f"¿Eliminar clase {rec.get('id', '?')}?"):
            return
        try:
            if self.app and getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("clases", rec["id"])
                self.app._info("Clase eliminada.")
            else:
                del self._data[idx]
                self.app._info("Clase eliminada (local).")
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    # ===========================================================
    #   CALENDARIO (versión personalizada como en prueba.py)
    # ===========================================================
    def _init_calendar_widgets(self):
        """Inicializa el calendario embebido y lo deja oculto al inicio."""
        self._calendar_visible = False
        self._cal_year = datetime.date.today().year
        self._cal_month = datetime.date.today().month

        # contenedor principal del calendario
        self.cal_frame = ctk.CTkFrame(
            self, fg_color=self.app.COLOR_PANEL, corner_radius=12,
            border_width=2, border_color=self.app.COLOR_DIVIDER
        )

        # header (navegación mes)
        header = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8,4))

        def nav_btn(text, cb):
            return ctk.CTkButton(
                header, text=text, width=36, height=28, corner_radius=8,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cb
            )

        nav_btn("<", lambda: (setattr(self, "_cal_month", self._cal_month-1), self._normalize_month_year(), self._render_month()))\
            .pack(side="left", padx=(0,6))
        nav_btn(">", lambda: (setattr(self, "_cal_month", self._cal_month+1), self._normalize_month_year(), self._render_month()))\
            .pack(side="right", padx=(6,0))

        self.lbl_month = ctk.CTkLabel(header, text="", text_color=self.app.COLOR_TEXT,
                                      font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_month.pack(side="left", expand=True)

        # grid de días
        self.cal_grid_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.cal_grid_frame.pack(fill="both", expand=False, padx=8, pady=(0,8))

        # leyenda / info
        self.lbl_cal_info = ctk.CTkLabel(self.cal_frame, text="", text_color=self.app.COLOR_MUTED, anchor="w")
        self.lbl_cal_info.pack(fill="x", padx=8, pady=(0,8))

        # botón ocultar
        ctk.CTkButton(
            self.cal_frame, text="Ocultar calendario", command=self._toggle_calendar,
            height=32, corner_radius=10, fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        ).pack(padx=8, pady=(0,8), anchor="e")

        # primer render
        self._normalize_month_year()
        self._render_month()

    def _normalize_month_year(self):
        while self._cal_month > 12:
            self._cal_month -= 12
            self._cal_year += 1
        while self._cal_month < 1:
            self._cal_month += 12
            self._cal_year -= 1

    def _render_month(self):
        """Dibuja el mes actual y resalta días con clases."""
        for w in self.cal_grid_frame.winfo_children():
            w.destroy()

        month_name = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{month_name} {self._cal_year}")

        dias_semana = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
        for i, d in enumerate(dias_semana):
            ctk.CTkLabel(self.cal_grid_frame, text=d, text_color=self.app.COLOR_MUTED)\
                .grid(row=0, column=i, padx=6, pady=4)

        cal = calendar.Calendar(firstweekday=0)  # lunes
        month_weeks = cal.monthdayscalendar(self._cal_year, self._cal_month)

        # días con clases del mes actual
        dias_con_clases = set()
        for item in (self._data or []):
            f = item.get("fecha")
            if not f:
                continue
            try:
                dt = datetime.datetime.strptime(f, "%Y-%m-%d").date()
                if dt.year == self._cal_year and dt.month == self._cal_month:
                    dias_con_clases.add(dt.day)
            except Exception:
                continue

        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self.cal_grid_frame, text=" ", text_color=self.app.COLOR_MUTED)\
                        .grid(row=r, column=ccol, padx=6, pady=6, ipadx=6, ipady=6)
                else:
                    has_cls = (day in dias_con_clases)
                    if has_cls:
                        btn = ctk.CTkButton(
                            self.cal_grid_frame, text=str(day), width=44, height=34, corner_radius=8,
                            fg_color=self.app.COLOR_YELLOW, hover_color=self.app.COLOR_RED,
                            text_color=self.app.COLOR_TEXT, command=lambda d=day: self._on_day_selected_custom(d)
                        )
                    else:
                        btn = ctk.CTkButton(
                            self.cal_grid_frame, text=str(day), width=44, height=34, corner_radius=8,
                            fg_color=self.app.COLOR_PANEL, hover_color=self.app.COLOR_DIVIDER,
                            text_color=self.app.COLOR_TEXT, command=lambda d=day: self._on_day_selected_custom(d)
                        )
                    btn.grid(row=r, column=ccol, padx=4, pady=4)

        try:
            self.lbl_cal_info.configure(text=f"{len(dias_con_clases)} día(s) con clases en {month_name} {self._cal_year}")
        except Exception:
            pass

    def _on_day_selected_custom(self, day: int):
        """Click en un día: filtra tabla y (opcional) muestra popup con el detalle."""
        sel_date = datetime.date(self._cal_year, self._cal_month, day)
        self.fecha_filtrada = sel_date.strftime("%Y-%m-%d")
        self._refrescar(local_only=True)

        # --- Popup (como en tu versión). Si NO lo quieres, elimina todo el bloque try…except ---
        try:
            filtered = [c for c in (self._data or []) if (c.get("fecha") or "") == self.fecha_filtrada]
            popup = tk.Toplevel(self)
            popup.title(f"Clases - {self.fecha_filtrada}")
            popup.geometry("520x320")
            popup.transient(self.winfo_toplevel()); popup.grab_set()

            frame = ctk.CTkFrame(popup, fg_color=self.app.COLOR_PANEL, corner_radius=8)
            frame.pack(fill="both", expand=True, padx=8, pady=8)

            hdr = ctk.CTkLabel(frame, text=f"Clases el {self.fecha_filtrada} — {len(filtered)}",
                               text_color=self.app.COLOR_TEXT, anchor="w")
            hdr.pack(fill="x", padx=8, pady=(4,8))

            if not filtered:
                ctk.CTkLabel(frame, text="No hay clases para esta fecha.", text_color=self.app.COLOR_MUTED)\
                    .pack(padx=8, pady=8)
            else:
                list_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
                list_frame.pack(fill="both", expand=True, padx=8, pady=4)
                for c in filtered:
                    est_name = self.estudiantes_id_to_name.get(c.get("id_estudiante"), str(c.get("id_estudiante") or ""))
                    pid = c.get("id_profesor") or c.get("id_instructor")
                    pro_name = self.profesores_id_to_name.get(pid, str(pid or ""))
                    txt = f"{est_name} — {pro_name} — {c.get('horaInicio','')} - {c.get('horaFin','')} — {c.get('estado','')}"
                    ctk.CTkLabel(list_frame, text=txt, text_color=self.app.COLOR_TEXT, anchor="w", justify="left")\
                        .pack(fill="x", padx=6, pady=6)

            btns = ctk.CTkFrame(frame, fg_color="transparent"); btns.pack(fill="x", padx=8, pady=(6,8))
            ctk.CTkButton(btns, text="Cerrar", command=popup.destroy, height=32,
                          corner_radius=8, fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                          text_color="#ffffff").pack(side="right", padx=6)
        except Exception:
            pass

    def _toggle_calendar(self):
        """
        Muestra/oculta el calendario embebido.
        Mantiene la tabla a la derecha reservando un minsize para la columna del calendario.
        """
        # Contenedor con dos columnas: [calendario][tabla]
        if not self._cal_container:
            container = ctk.CTkFrame(self, fg_color="transparent")
            container.grid(row=3, column=0, padx=16, pady=(0,10), sticky="nsew")
            container.grid_columnconfigure(0, weight=0, minsize=420)  # ancho del calendario
            container.grid_columnconfigure(1, weight=1)

            # mover tabla dentro del contenedor (col 1)
            self.table.grid_forget()
            self.table.grid(in_=container, row=0, column=1, sticky="nsew")

            # colocar calendario (col 0)
            self.cal_frame.grid(in_=container, row=0, column=0, padx=(0,12), sticky="ns")

            self._cal_container = container
            self._calendar_visible = True
            return

        # si ya hay contenedor, alternar visibilidad del calendario
        if self._calendar_visible:
            self.cal_frame.grid_remove()
            self._calendar_visible = False
        else:
            self.cal_frame.grid(in_=self._cal_container, row=0, column=0, padx=(0,12), sticky="ns")
            self._calendar_visible = True
