# modules/estados_cuenta.py
from typing import Tuple, Dict, Any, Optional
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
from modules.base import BaseModuleFrame

class EstadosCuentaView(BaseModuleFrame):
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 4
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16

    def __init__(self, master):
        super().__init__(master, "Estados de cuenta", "Gestión de saldos y pagos")

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0,6), sticky="ew")
        for c in range(6):
            tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8))
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8)

        # Buscador (por nombre de estudiante)
        self.en_buscar = ctk.CTkEntry(
            tb,
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
            placeholder_text="Buscar estudiante…"
        )
        self.en_buscar.grid(row=0, column=5, padx=(8, 0), sticky="e")

        # ===== Formulario =====
        self._build_form()
        self.form.grid(row=2, column=0, padx=16, pady=(8,10), sticky="ew")
        self._hide_form()

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        # Usa la fila 4 (la que expande BaseModuleFrame) para que se vean más filas.
        self.table.grid(row=4, column=0, padx=16, pady=(0, 8), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        # ===== Variables =====
        self._all_data = []               # fuente sin filtrar
        self._data = []                   # type: list[Dict[str, Any]]
        self._rows = []                   # type: list[ctk.CTkFrame]
        self._selected_idx = None         # type: Optional[int]
        self.estudiantes = []             # type: list[Dict[str, Any]]
        self.estudiantes_id_to_name = {}  # type: Dict[Any, str]
        self.estudiantes_name_to_id = {}  # type: Dict[str, Any]
        self._totals_frame = None
        self._render_after_id = None
        self._render_seq = 0
        self._row_pool = []
        self._empty_label = None
        self._loading_overlay = None
        self._last_refresh_ts = 0
        self._search_after_id = None

        self._render_table()
        self.en_buscar.bind("<KeyRelease>", self._on_search_key)
        self.after(150, self._cargar_catalogos_y_listar)

    def _take_estudiante_id(self, rec):
        return rec.get("idEstudiante") or rec.get("id_estudiante") or rec.get("estudianteId")

    def _student_name_for(self, estudiante_id) -> str:
        if estudiante_id in (None, ""):
            return "—"
        name = self.estudiantes_id_to_name.get(estudiante_id)
        if not name:
            name = self.estudiantes_id_to_name.get(str(estudiante_id))
        return name or "—"

    def _apply_search(self, rows):
        term = (self.en_buscar.get() or "").strip().lower()
        if not term:
            return list(rows or [])
        out = []
        for rec in (rows or []):
            name = self._student_name_for(self._take_estudiante_id(rec))
            if term in (name or "").lower():
                out.append(rec)
        return out

    def _on_search_key(self, _evt=None):
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(200, lambda: self._queue_render(self._apply_search(self._all_data)))

    # ===================== FORMULARIO =====================
    def _build_form(self):
        self.form = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL,
                                 corner_radius=12, border_width=2, border_color=self.app.COLOR_DIVIDER)
        for c in range(4):
            self.form.grid_columnconfigure(c, weight=1)

        def label(r, c, text):
            ctk.CTkLabel(self.form, text=text, text_color=self.app.COLOR_TEXT)\
                .grid(row=r, column=c, padx=10, pady=(10,4), sticky="w")

        def entry(ph=""):
            return ctk.CTkEntry(
                self.form, height=34, corner_radius=8,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=1, border_color=self.app.COLOR_DIVIDER,
                placeholder_text=ph
            )

        # Campos
        label(0, 0, "Estudiante")
        self.cb_estudiante = ctk.CTkComboBox(self.form, values=[], width=360)
        self.cb_estudiante.grid(row=1, column=0, padx=10, pady=(0,6), sticky="w", columnspan=2)

        label(0, 2, "Monto total")
        self.en_total = entry("0.00")
        self.en_total.grid(row=1, column=2, padx=10, pady=(0,6), sticky="ew")

        label(0, 3, "Monto pagado")
        self.en_pagado = entry("0.00")
        self.en_pagado.grid(row=1, column=3, padx=10, pady=(0,6), sticky="ew")

        # ---- Estado calculado (solo visual; NO se envía al backend) ----
        label(2, 2, "Estado (calculado)")
        self.lbl_estado_calc = ctk.CTkLabel(self.form, text="Pendiente", text_color=self.app.COLOR_MUTED)
        self.lbl_estado_calc.grid(row=3, column=2, padx=10, pady=(0,8), sticky="w")

        # Preview en vivo del estado según montos (opcional, para UX)
        def _update_preview(_=None):
            try:
                total = self._parse_money(self.en_total.get())
                pagado = self._parse_money(self.en_pagado.get())
                if total < 0 or pagado < 0:
                    self.lbl_estado_calc.configure(text="Inválido")
                elif pagado == 0:
                    self.lbl_estado_calc.configure(text="Pendiente")
                elif abs(pagado - total) < 1e-6:
                    self.lbl_estado_calc.configure(text="Pagado")
                elif 0 < pagado < total:
                    self.lbl_estado_calc.configure(text="En deuda")
                else:
                    self.lbl_estado_calc.configure(text="Inválido")
            except Exception:
                self.lbl_estado_calc.configure(text="Inválido")

        self.en_total.bind("<KeyRelease>", _update_preview)
        self.en_pagado.bind("<KeyRelease>", _update_preview)

        # Botones
        btns = ctk.CTkFrame(self.form, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=10, pady=(6,12), sticky="e")

        def red_btn_small(text, cb):
            return ctk.CTkButton(
                btns, text=text, height=34, corner_radius=10,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cb
            )

        red_btn_small("Cancelar", self._cancelar).grid(row=0, column=0, padx=6)
        red_btn_small("Guardar", self._guardar).grid(row=0, column=1, padx=6)

        self._form_mode = "create"
        self._editing_idx = None

    def _show_form(self, mode="create", data=None):
        self._form_mode = mode
        if mode == "edit" and data:
            est_name = self.estudiantes_id_to_name.get(data.get("idEstudiante"), str(data.get("idEstudiante") or ""))
            self.cb_estudiante.set(est_name)
            self.en_total.delete(0, "end"); self.en_total.insert(0, f"{(data.get('montoTotal') or 0):.2f}")
            self.en_pagado.delete(0, "end"); self.en_pagado.insert(0, f"{(data.get('montoPagado') or 0):.2f}")
            self.lbl_estado_calc.configure(text=(data.get("estado") or "Pendiente"))
            try:
                self._editing_idx = self._data.index(data)
            except Exception:
                self._editing_idx = None
        else:
            self._editing_idx = None
            if self.cb_estudiante.cget("values"):
                self.cb_estudiante.set(self.cb_estudiante.cget("values")[0])
            self.en_total.delete(0, "end"); self.en_total.insert(0, "0.00")
            self.en_pagado.delete(0, "end"); self.en_pagado.insert(0, "0.00")
            self.lbl_estado_calc.configure(text="Pendiente")
        self.form.grid()

    def _hide_form(self):
        self.form.grid_remove()

    # ===================== CRUD =====================
    def _nuevo(self): self._show_form("create", {})
    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un registro primero.")
            return
        rec = self._data[self._selected_idx]
        self._show_form("edit", rec)

    def _eliminar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un registro para eliminar.")
            return
        rec = self._data[self._selected_idx]
        est_name = self._student_name_for(self._take_estudiante_id(rec))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar estado de cuenta de {est_name}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
                self._last_refresh_ts = 0
                self._refrescar(force_refresh=True)
            else:
                if rec in self._all_data:
                    self._all_data.remove(rec)
                else:
                    del self._data[self._selected_idx]
                self.app._info("Registro eliminado (local).")
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    def _cancelar(self): self._hide_form()

    def _guardar(self):
        try:
            payload = self._collect_form()
            ok, msg = self._validate(payload)
            if not ok:
                messagebox.showerror("Validación", msg, parent=self)
                return

            if self._form_mode == "create":
                if getattr(self.app, "api", None):
                    created = self.app.api.create("estados-cuenta", payload)  # <- backend calcula 'estado'
                    self.app._info("Estado de cuenta creado.")
                    self._last_refresh_ts = 0
                    self._refrescar(force_refresh=True)
                else:
                    payload["_local_id"] = (max([r.get("_local_id", 0) for r in self._all_data] or [0]) + 1)
                    payload["estado"] = self._preview_estado(payload)  # local-only
                    self._all_data.append(payload)
            else:
                if self._editing_idx is None:
                    self.app._info("No se seleccionó registro para actualizar.")
                    return
                rec = self._data[self._editing_idx]
                if getattr(self.app, "api", None) and rec.get("id"):
                    updated = self.app.api.update("estados-cuenta", rec.get("id"), payload)
                    self.app._info("Estado de cuenta actualizado.")
                    self._last_refresh_ts = 0
                    self._refrescar(force_refresh=True)
                else:
                    payload["estado"] = self._preview_estado(payload)  # local-only
                    self._data[self._editing_idx].update(payload)

            self._hide_form()
            if not getattr(self.app, "api", None):
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar:\n{e}", parent=self)

    # ===================== CARGA DATOS =====================
    def _cargar_catalogos_y_listar(self, force_refresh=False):
        try:
            if not getattr(self.app, "api", None):
                self._refrescar(local_only=True)
                return

            raw = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []
            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    if isinstance(raw.get(key), list):
                        raw = raw[key]
                        break
                else:
                    raw = []

            self.estudiantes = raw
            self.estudiantes_id_to_name = {}
            self.estudiantes_name_to_id = {}

            for e in self.estudiantes:
                eid = e.get("id") or e.get("idEstudiante")
                nombre = "{} {}".format(e.get("nombre",""), e.get("apellido","")).strip()
                if eid is not None and nombre:
                    self.estudiantes_id_to_name[eid] = nombre
                    self.estudiantes_id_to_name[str(eid)] = nombre
                    self.estudiantes_name_to_id[nombre] = eid

            self.cb_estudiante.configure(values=sorted(list(self.estudiantes_name_to_id.keys())))
            if self.cb_estudiante.cget("values") and not self.cb_estudiante.get():
                self.cb_estudiante.set(self.cb_estudiante.cget("values")[0])

            self._refrescar(force_refresh=force_refresh)
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible cargar catálogos:\n{e}", parent=self)

    def _refrescar(self, local_only=False, force_refresh=True):
        if local_only:
            base = self._all_data or self._data
            self._queue_render(self._apply_search(base))
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
            return

        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if not getattr(self.app, "api", None):
            base = self._all_data or self._data
            self._queue_render(self._apply_search(base))
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                raw = self.app.api.get_all("estados-cuenta", force_refresh=force_refresh) or []
                if isinstance(raw, dict):
                    for key in ("content", "items", "estados-cuenta", "data", "results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []

                def apply_data():
                    self._all_data = raw or []
                    self._queue_render(self._apply_search(self._all_data))
                    self.app._info(f"Estados de cuenta: {len(self._data)} registros.")

                self.after(0, apply_data)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Estados de cuenta", f"No fue posible consultar la API:\n{e}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_loading(self, on=True, text="Actualizando..."):
        if on:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                return
            self._loading_overlay = ctk.CTkLabel(
                self.table,
                text=text,
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=13, weight="bold")
            )
            self._loading_overlay.place(relx=0.5, rely=0.03, anchor="n")
        else:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                self._loading_overlay.destroy()
            self._loading_overlay = None

    # ===================== RENDER =====================
    def _apply_colspecs(self, container):
        specs = [
            ("Estudiante",   260, 1),
            ("Monto total",  120, 0),
            ("Monto pagado", 120, 0),
            ("Saldo",        120, 0),
            ("Estado",       120, 0),
            ("Acciones",     120, 0),
        ]
        for i, (_, minw, weight) in enumerate(specs):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)
        return specs

    def _queue_render(self, rows):
        self._data = list(rows or [])
        if self._render_after_id:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
        self._render_after_id = self.after(self.RENDER_DELAY_MS, self._flush_render)

    def _flush_render(self):
        self._render_after_id = None
        self._set_data(self._data)

    def _render_table(self):
        self._queue_render(self._data)

    def _row_values(self, rec):
        est = self._student_name_for(self._take_estudiante_id(rec))
        total = float(rec.get("montoTotal") or 0)
        pagado = float(rec.get("montoPagado") or 0)
        saldo = total - pagado
        estado = (rec.get("estado", "Pendiente") or "Pendiente")
        return {
            "est": est,
            "total": total,
            "pagado": pagado,
            "saldo": saldo,
            "estado": estado,
            "saldo_color": "#d9534f" if saldo > 0 else "#28a745",
        }

    def _build_table_shell(self):
        if getattr(self, "_table_header", None) and self._table_header.winfo_exists():
            return

        for w in self.table.winfo_children():
            w.destroy()
        self._row_pool = []

        self._table_header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        self._table_header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        specs = self._apply_colspecs(self._table_header)

        for i, (nombre, _, _) in enumerate(specs):
            ctk.CTkLabel(
                self._table_header,
                text=nombre,
                text_color=self.app.COLOR_MUTED,
                anchor="w",
                justify="left"
            ).grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        self._rows_container = ctk.CTkFrame(self.table, fg_color="transparent")
        self._rows_container.grid(row=1, column=0, sticky="nsew")
        self.table.grid_rowconfigure(1, weight=1)
        self._rows_container.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._rows_container,
            text="Sin registros",
            text_color=self.app.COLOR_MUTED
        )
        self._empty_label.grid(row=0, column=0, padx=8, pady=12, sticky="w")
        self._empty_label.grid_remove()

    def _create_row_widget(self):
        row = ctk.CTkFrame(self._rows_container, fg_color=self.app.COLOR_PANEL, corner_radius=10)
        specs = self._apply_colspecs(row)

        lbl_est = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
        lbl_est.grid(row=0, column=0, padx=12, pady=10, sticky="ew")

        lbl_total = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
        lbl_total.grid(row=0, column=1, padx=12, pady=10, sticky="ew")

        lbl_pagado = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
        lbl_pagado.grid(row=0, column=2, padx=12, pady=10, sticky="ew")

        lbl_saldo = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
        lbl_saldo.grid(row=0, column=3, padx=12, pady=10, sticky="ew")

        lbl_estado = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
        lbl_estado.grid(row=0, column=4, padx=12, pady=10, sticky="ew")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

        btn_edit = ctk.CTkButton(
            actions, text="✎", width=36, height=32, corner_radius=8,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_edit.grid(row=0, column=0, padx=4)

        btn_delete = ctk.CTkButton(
            actions, text="🗑️", width=36, height=32, corner_radius=8,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_delete.grid(row=0, column=1, padx=4)

        labels = [lbl_est, lbl_total, lbl_pagado, lbl_saldo, lbl_estado]

        return {
            "frame": row,
            "labels": labels,
            "edit_btn": btn_edit,
            "delete_btn": btn_delete,
        }

    def _update_row_widget(self, row_info, rec, idx):
        row = row_info["frame"]
        row.configure(fg_color=self.app.COLOR_PANEL)
        values = self._row_values(rec)

        row_info["labels"][0].configure(text=values["est"], text_color=self.app.COLOR_TEXT)
        row_info["labels"][1].configure(text=f"{values['total']:,.2f}", text_color=self.app.COLOR_TEXT)
        row_info["labels"][2].configure(text=f"{values['pagado']:,.2f}", text_color=self.app.COLOR_TEXT)
        row_info["labels"][3].configure(text=f"{values['saldo']:,.2f}", text_color=values["saldo_color"])
        row_info["labels"][4].configure(text=values["estado"], text_color=self.app.COLOR_TEXT)

        for lbl in row_info["labels"]:
            lbl.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

        row_info["edit_btn"].configure(command=lambda i=idx: self._edit_row(i))
        row_info["delete_btn"].configure(command=lambda i=idx: self._delete_row(i))
        row.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

    def _set_data(self, rows):
        self._build_table_shell()
        self._selected_idx = None
        self._rows.clear()
        data = list(rows or [])

        self._render_seq += 1
        render_seq = self._render_seq

        for row_info in self._row_pool:
            try:
                row_info["frame"].grid_remove()
            except Exception:
                pass

        if not data:
            if self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.grid()
            self._render_totals()
            return

        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.grid_remove()

        def paint_batch(start=0):
            if render_seq != self._render_seq:
                return
            if not self._rows_container.winfo_exists():
                return

            end = min(start + self.ROW_BATCH_SIZE, len(data))
            for idx in range(start, end):
                if idx >= len(self._row_pool):
                    self._row_pool.append(self._create_row_widget())
                row_info = self._row_pool[idx]
                self._update_row_widget(row_info, data[idx], idx)
                row_info["frame"].grid(row=idx + 1, column=0, padx=8, pady=4, sticky="ew")
                self._rows.append(row_info["frame"])

            if end < len(data):
                self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))
            else:
                self._render_totals()

        paint_batch(0)

    def _render_totals(self):
        try:
            if hasattr(self, "_totals_frame") and self._totals_frame is not None:
                self._totals_frame.destroy()
        except Exception:
            pass

        total_total = sum(float(r.get("montoTotal") or 0) for r in self._data)
        total_pagado = sum(float(r.get("montoPagado") or 0) for r in self._data)
        total_saldo = total_total - total_pagado
        saldo_color = "#d9534f" if total_saldo > 0 else "#28a745"

        self._totals_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._totals_frame.grid(row=5, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._totals_frame.grid_columnconfigure(0, weight=1)

        box = ctk.CTkFrame(
            self._totals_frame,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=2,
            border_color=self.app.COLOR_RED
        )
        box.grid(row=0, column=0, padx=8, pady=0)
        box.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            box,
            text=f"Totales — Registros: {len(self._data)}",
            text_color=self.app.COLOR_MUTED,
            anchor="center",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 6), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Monto total: {total_total:,.2f}",
            text_color=self.app.COLOR_TEXT,
            anchor="center",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Pagado: {total_pagado:,.2f}",
            text_color=self.app.COLOR_TEXT,
            anchor="center",
        ).grid(row=1, column=1, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Saldo: {total_saldo:,.2f}",
            text_color=saldo_color,
            anchor="center",
        ).grid(row=1, column=2, padx=16, pady=(0, 12), sticky="ew")

    # ===================== SELECCIÓN =====================
    def _select_row(self, idx: int):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            try:
                self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
            except Exception:
                pass
        if 0 <= idx < len(self._rows):
            try:
                self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            except Exception:
                pass
            self._selected_idx = idx

    def _edit_row(self, idx: int):
        self._select_row(idx)
        self._editing_idx = idx
        self._show_form("edit", self._data[idx])

    def _delete_row(self, idx: int):
        self._select_row(idx)
        rec = self._data[idx]
        est = self._student_name_for(self._take_estudiante_id(rec))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar registro de {est}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
                self._last_refresh_ts = 0
                self._refrescar(force_refresh=True)
            else:
                if rec in self._all_data:
                    self._all_data.remove(rec)
                else:
                    del self._data[idx]
                self.app._info("Registro eliminado (local).")
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    # ===================== HELPERS FORM =====================
    def _parse_money(self, s: str) -> float:
        """
        Acepta: "1.234,56" | "1,234.56" | "1234.56" | "1234".
        Limpia símbolos y normaliza separadores antes de convertir a float.
        """
        if s is None:
            return 0.0
        s = str(s).strip()
        if s == "":
            return 0.0
        for ch in "$₱€£% ":
            s = s.replace(ch, "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            try:
                return float(s.replace(",", ""))
            except Exception:
                raise ValueError("Valor numérico inválido")

    def _collect_form(self) -> Dict[str, Any]:
        """
        JSON esperado por el backend:
        {
          "idEstudiante": int,
          "montoTotal": float,
          "montoPagado": float
        }
        (el 'estado' lo calcula el servidor; NO se envía)
        """
        # Estudiante -> id
        est_name = (self.cb_estudiante.get() or "").strip()
        id_est = self.estudiantes_name_to_id.get(est_name)
        if id_est is None:
            try:
                id_est = int(est_name)  # permitir escribir el ID directo
            except Exception:
                id_est = None

        total = self._parse_money(self.en_total.get())
        pagado = self._parse_money(self.en_pagado.get())

        return {
            "idEstudiante": id_est,
            "montoTotal": total,
            "montoPagado": pagado
        }

    def _validate(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Reglas mínimas en el front (el back valida de nuevo):
          - idEstudiante obligatorio (>0)
          - montos >= 0
          - montoPagado <= montoTotal
        """
        # idEstudiante
        id_est = payload.get("idEstudiante")
        if id_est in (None, "", 0):
            return (False, "Debes seleccionar un estudiante válido.")

        # montos
        try:
            total = float(payload.get("montoTotal", 0))
            pagado = float(payload.get("montoPagado", 0))
        except Exception:
            return (False, "Los montos deben ser numéricos.")

        if total < 0 or pagado < 0:
            return (False, "Los montos no pueden ser negativos.")
        if pagado > total:
            return (False, "El monto pagado no puede superar el monto total.")

        return (True, "")

    def _preview_estado(self, payload: Dict[str, Any]) -> str:
        """Solo para modo local sin API: emula el cálculo del backend."""
        try:
            total = float(payload.get("montoTotal") or 0)
            pagado = float(payload.get("montoPagado") or 0)
            if pagado == 0:
                return "Pendiente"
            if abs(pagado - total) < 1e-6:
                return "Pagado"
            if 0 < pagado < total:
                return "En deuda"
        except Exception:
            pass
        return "Inválido"

# Export explícito por si usas import *
__all__ = ["EstadosCuentaView"]
