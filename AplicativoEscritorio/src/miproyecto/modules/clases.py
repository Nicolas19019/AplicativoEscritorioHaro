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

        # ===== Toolbar (alineada a la izquierda) =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")
        tb.grid_columnconfigure(0, weight=1)

        
        bar = ctk.CTkFrame(tb, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="w")

        def red_btn(text, cmd):
            return ctk.CTkButton(
                bar, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        # Botón Calendario
        self.btn_calendar = ctk.CTkButton(
            bar, text="📅 Calendario", height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT, command=self._toggle_calendar_mode
        )
        self.btn_calendar.grid(row=0, column=0, padx=(0, 8))

        # Botón Nuevo
        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=1, padx=(0, 8))

        # Botón Refrescar
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=(0, 8))

        # ===== Form inline (oculto al inicio) =====
        try:
            self.form = ClaseInlineForm(self, self.app, self._on_submit, self._on_cancel)
            self.form.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
            self.form.hide()
        except Exception as e:
            print(f"[Clases] No se pudo crear el formulario: {e}")
            self.form = None

        # ===== Contenedor principal de la vista (tabla / calendario) =====
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Construir vistas y mostrar la normal
        self._build_normal_view()     # define self.table_top, headers, detail_card (oculta)
        self._build_calendar_view()   # calendario + tabla derecha
        self._show_view("normal")

        # Overlay de carga
        self._loading_overlay = None

        # Carga inicial (catálogos + clases)
        self.after(150, self._cargar_catalogos_y_listar)

        self._set_data(self._data)
        self._show_loading(False)


    # ============================
    # Construcción de vistas
    # ============================

    def _build_normal_view(self):
        """Tabla de clases estilo Instructores: adaptable y limpia."""
        self.view_normal = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_normal.grid(row=0, column=0, sticky="nsew")
        self.view_normal.grid_columnconfigure(0, weight=1)
        self.view_normal.grid_rowconfigure(0, weight=1)

        # --- Tabla principal ---
        self.table = ctk.CTkScrollableFrame(
            self.view_normal,
            fg_color=self.app.COLOR_BG,
            corner_radius=12
        )
        self.table.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        # 🔧 Ajuste universal: si existe el atributo interno, úsalo; si no, prueba el nuevo API
        try:
            inner = getattr(self.table, "_scrollable_frame", None) or getattr(self.table, "scrollable_frame", None)
            if inner:
                inner.grid_propagate(False)
        except Exception:
            pass


        self.table.grid_columnconfigure(0, weight=1)

        # --- Cabeceras y columnas ---
        self._COLS = [
            ("Estudiante", 200, 1),
            ("Instructor", 200, 1),
            ("Placa", 100, 0),
            ("Fecha", 120, 0),
            ("Inicio", 90, 0),
            ("Fin", 90, 0),
            ("Estado", 120, 0),
            ("Acciones", 120, 0)
        ]

        self._rows = []
        self._selected_id = None
        self._render_table()

        # --- Redibujar cuando se cambia tamaño ---
        self.table.bind("<Configure>", lambda e: self._resize_columns())

    def _render_table(self):
        """Dibuja la tabla de clases (vista normal)."""
        for w in self.table.winfo_children():
            w.destroy()
        self._rows.clear()

        # --- Encabezado ---
        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        for i, (_, minw, weight) in enumerate(self._COLS):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                        anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin registros de clases", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        # --- Filas ---
        for r, rec in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            for i, (_, minw, weight) in enumerate(self._COLS):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)

            values = [
                rec.get("nombre_estudiante", ""),
                rec.get("nombre_instructor", ""),
                rec.get("placa_vehiculo", ""),
                rec.get("fecha", ""),
                rec.get("horaInicio", ""),
                rec.get("horaFin", ""),
                rec.get("estado", "")
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, rid=r-1: self._select_row(rid))

            # Acciones
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=len(values), padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=10,
                                    fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                    text_color="#ffffff", command=cmd)

            icon_btn("✎", lambda rid=r-1: self._edit_row(rid)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda rid=r-1: self._delete_row(rid)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, rid=r-1: self._select_row(rid))
            self._rows.append(row)

    def _resize_columns(self):
        """Mantiene proporción de columnas al redimensionar."""
        try:
            total_width = self.table.winfo_width()
            for w in self._rows:
                for i, (_, minw, weight) in enumerate(self._COLS):
                    new_width = int(total_width * (weight / max(1, sum(c[2] for c in self._COLS))))
                    w.grid_columnconfigure(i, minsize=new_width)
        except Exception:
            pass


    def _build_calendar_view(self):
        """Calendario + tabla (estilo limpio)."""
        self.view_calendar = ctk.CTkFrame(self.main, fg_color="transparent")
        self.view_calendar.grid_rowconfigure(0, weight=1)
        self.view_calendar.grid_columnconfigure(0, weight=0, minsize=360)
        self.view_calendar.grid_columnconfigure(1, weight=1)

        # Calendario (izquierda)
        self.cal_frame = ctk.CTkFrame(
            self.view_calendar,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER
        )
        self.cal_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._init_calendar()

        # Tabla derecha
        self.table_wrap = ctk.CTkFrame(self.view_calendar, fg_color="transparent")
        self.table_wrap.grid(row=0, column=1, sticky="nsew")
        self.table_wrap.grid_rowconfigure(0, weight=1)
        self.table_wrap.grid_columnconfigure(0, weight=1)

        self.table_right = ctk.CTkScrollableFrame(
            self.table_wrap,
            fg_color=self.app.COLOR_BG,
            corner_radius=12
        )
        self.table_right.grid(row=0, column=0, sticky="nsew")
        self.table_right.grid_columnconfigure(0, weight=1)

        self._render_table_header(self.table_right, is_right=True)

        self.table_right._parent_canvas.bind("<Configure>", self._check_scroll_needed)



    def _render_table_header(self, parent, is_right=False):
        header = ctk.CTkFrame(parent, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(0, 0), sticky="ew")
        header.configure(corner_radius=0)  # para que se fusione visualmente con la primera fila

        for i, (_, minw, weight) in enumerate(self._COLS):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)

        for i, (title, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=title, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if is_right:
            self.rows_container_right = ctk.CTkFrame(parent, fg_color="transparent")
            self.rows_container_right.grid(row=1, column=0, sticky="nsew")
        else:
            self.rows_container = ctk.CTkFrame(parent, fg_color="transparent")
            self.rows_container.grid(row=1, column=0, sticky="nsew")

    def _check_scroll_needed(self, event):
        """Muestra u oculta scroll horizontal si es necesario."""
        try:
            canvas = event.widget
            bbox = canvas.bbox("all")
            if not bbox:
                return
            width_total = bbox[2] - bbox[0]
            width_visible = canvas.winfo_width()

            # Si hay overflow, activar scroll horizontal
            canvas.configure(xscrollincrement=1)
            canvas.xview_moveto(0)
            if width_total > width_visible:
                canvas.configure(scrollregion=bbox)
            else:
                canvas.configure(scrollregion=(0, 0, width_visible, bbox[3]))
        except Exception:
            pass


    def _on_hscroll_top(self, *args):
        """Permite desplazamiento horizontal en la tabla superior (modo normal)."""
        try:
            self.table_top._parent_canvas.xview(*args)
        except Exception:
            pass

    def _on_hscroll_right(self, *args):
        """Permite desplazamiento horizontal en la tabla derecha (modo calendario)."""
        try:
            self.table_right._parent_canvas.xview(*args)
        except Exception:
            pass


    def _build_table_header(self, parent, is_right=False):
        header = ctk.CTkFrame(parent, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        for i, (_, minw, weight) in enumerate(self._COLS):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)

        for i, (title, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=title, text_color=self.app.COLOR_MUTED,
                        anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")


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

            # 📌 IMPORTANTE: llenar las opciones del formulario
            if self.form:
                self.form.set_options(self._estudiantes, self._profesores, self._vehiculos)

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
        """Actualiza las filas de la tabla de manera segura y sincronizada."""
        # Verificar que la vista aún existe
        if not hasattr(self, "main") or not self.main.winfo_exists():
            return

        # Contenedor activo
        cont = self.table if not self._calendar_mode else getattr(self, "table_right", None)
        if not cont or not cont.winfo_exists():
            return

        current_ids = set(self._row_order)
        new_ids = [self._row_key(r) for r in new_data]
        new_set = set(new_ids)

        # Eliminar filas que ya no están
        for removed_id in list(current_ids - new_set):
            fr = self._row_frames.pop(removed_id, None)
            if fr and fr.winfo_exists():
                try:
                    fr.destroy()
                except Exception:
                    pass
            self._rows_widgets.pop(removed_id, None)
            if removed_id in self._row_order:
                self._row_order.remove(removed_id)
            if self._selected_id == removed_id:
                self._selected_id = None

        # Vaciar contenedor antes de repintar
        for w in cont.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Reiniciar el orden de filas
        self._row_order.clear()
        # Volver a crear encabezado antes de las filas
        self._render_table_header(cont, is_right=self._calendar_mode)


        if not cont:
            print("[WARN] Contenedor de tabla no encontrado.")
            return


        def paint_batch(start=0):
            """Pinta las filas por lotes, verificando la existencia del contenedor."""
            if not cont or not cont.winfo_exists():
                return  # si se destruyó la vista, no seguimos

            end = min(start + self.ROW_BATCH_SIZE, len(new_data))
            for i in range(start, end):
                rec = new_data[i]
                rid = new_ids[i]
                zebra = self._ROW_2 if ((i + 1) % 2 == 0) else self._ROW_1

                if rid in self._row_frames and self._row_frames[rid].winfo_exists():
                    self._update_row_widgets(rid, rec, zebra)
                else:
                    try:
                        self._create_row_widgets(i, rid, rec, zebra, cont)
                    except Exception:
                        continue

                if rid not in self._row_order:
                    self._row_order.append(rid)

                # Posicionar visualmente
                fr = self._row_frames.get(rid)
                if fr and fr.winfo_exists():
                    try:
                        fr.grid(row=i + 1, column=0, padx=8, pady=(0, 2), sticky="ew")
                    except Exception:
                        pass

            # Continuar si faltan filas
            if end < len(new_data):
                self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))
            else:
                self._update_calendar_highlights()

        # Iniciar repintado
        paint_batch(0)


    def _create_row_widgets(self, visual_index, rid, rec, bg, container):
        # Fila contenedora
        row = ctk.CTkFrame(container, fg_color=bg, corner_radius=10)
        row.grid(row=visual_index + 1, column=0, padx=8, pady=(0, 1), sticky="ew")

        # Asegurar que las columnas coincidan con el encabezado
        for i, (_, minw, weight) in enumerate(self._COLS):
            row.grid_columnconfigure(i, minsize=minw, weight=weight)

        widgets = {}
        values = self._row_values(rec)

        # columnas de texto
        for col, val in enumerate(values[:-1]):
            lbl = ctk.CTkLabel(
                row, text=val, text_color=self.app.COLOR_TEXT,
                anchor="w", justify="left"
            )
            lbl.grid(row=0, column=col, padx=12, pady=8, sticky="ew")
            lbl.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
            widgets[col] = lbl

        # Acciones (última columna)
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")

        def icon_btn(symbol, cmd):
            return ctk.CTkButton(
                actions, text=symbol, width=36, height=32, corner_radius=8,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        icon_btn("✎", lambda r_id=rid: self._select_row(r_id) or self._editar()).grid(row=0, column=0, padx=4)
        icon_btn("🗑️", lambda r_id=rid: self._select_row(r_id) or self._eliminar()).grid(row=0, column=1, padx=4)

        row.bind("<Button-1>", lambda e, r_id=rid: self._select_row(r_id))
        self._row_frames[rid] = row
        self._rows_widgets[rid] = widgets


        # Acciones
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")
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
        if not row:
            return

        # Validar que el widget siga existiendo (no fue destruido)
        try:
            if not str(row) or not row.winfo_exists():
                return
        except Exception:
            return

        # Actualizar color de fondo según selección
        try:
            row.configure(fg_color=self.app.COLOR_DIVIDER if self._selected_id == rid else bg)
        except Exception:
            return  # si ya fue destruido entre líneas, simplemente lo ignoramos

        widgets = self._rows_widgets.get(rid, {})
        values = self._row_values(rec)

        for col, val in enumerate(values[:-1]):
            lbl = widgets.get(col)
            if lbl:
                try:
                    if lbl.cget("text") != val:
                        lbl.configure(text=val)
                except Exception:
                    continue  # si el label ya no existe


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
    # Actualización del detalle
    # ============================
    def _update_detail(self, rec):
        """Muestra la información del registro seleccionado en la tarjeta de detalle."""
        if not hasattr(self, "detail_card"):
            return

        # Si estaba oculto, mostrarlo
        try:
            self.detail_card.grid()
        except Exception:
            pass

        est = rec.get("nombre_estudiante") or self.estudiantes_id_to_name.get(rec.get("id_estudiante"), "—")
        pid = rec.get("id_profesor") or rec.get("id_instructor")
        pro = rec.get("nombre_instructor") or self.profesores_id_to_name.get(pid, "—")

        self.d_estudiante.configure(text=est or "—")
        self.d_instructor.configure(text=pro or "—")
        self.d_fecha.configure(text=rec.get("fecha", "—"))
        self.d_horario.configure(text=f"{rec.get('horaInicio', '—')} - {rec.get('horaFin', '—')}")
        self.d_placa.configure(text=rec.get("placa_vehiculo", "—"))
        self.d_estado.configure(text=rec.get("estado", "—"))

        self.d_notas.configure(state="normal")
        notas_text = rec.get("notas") or rec.get("observaciones") or "Sin notas registradas."
        self.d_notas.delete("1.0", "end")
        self.d_notas.insert("1.0", notas_text)
        self.d_notas.configure(state="disabled")


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
        """Dibuja el calendario mensual con colores personalizados."""
        for w in self.cal_grid.winfo_children(): 
            w.destroy()

        import datetime, calendar

        # Fecha actual
        hoy = datetime.date.today()
        mes_nombre = calendar.month_name[self._cal_month]
        self.lbl_month.configure(text=f"{mes_nombre} {self._cal_year}")

        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for i, d in enumerate(dias_semana):
            ctk.CTkLabel(
                self.cal_grid, text=d, text_color=self.app.COLOR_MUTED
            ).grid(row=0, column=i, padx=6, pady=4)

        self._cal_day_buttons = {}
        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(self._cal_year, self._cal_month)

        # Crear botones de días
        for r, week in enumerate(month_weeks, start=1):
            for ccol, day in enumerate(week):
                if day.month != self._cal_month:
                    # Días de otro mes → gris claro
                    ctk.CTkLabel(
                        self.cal_grid, text=str(day.day), text_color=self.app.COLOR_MUTED
                    ).grid(row=r, column=ccol, padx=4, pady=4)
                else:
                    btn = ctk.CTkButton(
                        self.cal_grid,
                        text=str(day.day),
                        width=44, height=34, corner_radius=8,
                        fg_color=self.app.COLOR_PANEL,
                        hover_color=self.app.COLOR_RED,
                        text_color=self.app.COLOR_TEXT,
                        command=lambda d=day: self._on_calendar_day_click(d)
                    )
                    btn.grid(row=r, column=ccol, padx=4, pady=4, sticky="nsew")
                    self._cal_day_buttons[day] = btn

        self._update_calendar_highlights()

    def _update_calendar_highlights(self):
        """Actualiza los colores del calendario según clases y selección."""
        import datetime

        hoy = datetime.date.today()
        dias_con_clases = set()

        # Buscar fechas con clases
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

        # Colorear botones según estado
        for day, btn in self._cal_day_buttons.items():
            try:
                if day == hoy:
                    # Día actual
                    btn.configure(fg_color="#FFD966", text_color="#000000")
                elif hasattr(self, "fecha_filtrada") and self.fecha_filtrada:
                    sel = datetime.datetime.strptime(self.fecha_filtrada, "%Y-%m-%d").date()
                    if day == sel:
                        btn.configure(fg_color="#FFD966", text_color="#000000")
                        continue
                if day in dias_con_clases:
                    # Día con clases → rojo
                    btn.configure(fg_color="#E74C3C", text_color="#ffffff")
                elif day != hoy:
                    # Día normal
                    btn.configure(fg_color=self.app.COLOR_PANEL, text_color=self.app.COLOR_TEXT)
            except Exception:
                pass

        month_name = datetime.date(self._cal_year, self._cal_month, 1).strftime("%B")
        self.lbl_cal_info.configure(
            text=f"{len(dias_con_clases)} día(s) con clases en {month_name} {self._cal_year}"
        )

    def _on_calendar_day_click(self, day: datetime.date):
        """Seleccionar un día en el calendario → resalta y actualiza tabla."""
        self.fecha_filtrada = day.strftime("%Y-%m-%d")

        # Refrescar colores del calendario
        self._update_calendar_highlights()

        # Filtrar las clases del día seleccionado
        clases_dia = [c for c in (self._data or []) if c.get("fecha") == self.fecha_filtrada]

        # Limpiar tabla derecha
        for w in self.table_right.winfo_children():
            w.destroy()

        # Cabecera
        header = ctk.CTkFrame(self.table_right, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        for i, (nombre, _, _) in enumerate(self._COLS):
            header.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED, anchor="w").grid(
                row=0, column=i, padx=12, pady=10, sticky="ew"
            )

        if not clases_dia:
            ctk.CTkLabel(
                self.table_right,
                text="Sin clases programadas para este día.",
                text_color=self.app.COLOR_MUTED,
                anchor="w",
            ).grid(row=1, column=0, padx=20, pady=20, sticky="w")
            return

        # Pintar filas
        for r, rec in enumerate(clases_dia, start=1):
            row = ctk.CTkFrame(self.table_right, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")

            values = [
                rec.get("nombre_estudiante", ""),
                rec.get("nombre_instructor", ""),
                rec.get("placa_vehiculo", ""),
                rec.get("fecha", ""),
                rec.get("horaInicio", ""),
                rec.get("horaFin", ""),
                rec.get("estado", ""),
            ]

            for i, val in enumerate(values):
                ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT, anchor="w").grid(
                    row=0, column=i, padx=12, pady=8, sticky="ew"
                )


    # ============================
    # Loading overlay
    # ============================
    def _show_loading(self, on=True, text="Actualizando…"):
        """Muestra u oculta el overlay de carga según la vista activa."""
        target = self.table_right if self._calendar_mode else self.table
        if on:
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                try:
                    self._loading_overlay.destroy()
                except Exception:
                    pass
            self._loading_overlay = ctk.CTkLabel(
                target, text=text, text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            self._loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        else:
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                try:
                    self._loading_overlay.destroy()
                except Exception:
                    pass
                self._loading_overlay = None




