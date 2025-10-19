import customtkinter as ctk
from tkinter import messagebox
from modules.base import BaseModuleFrame

class EstadosCuentaView(BaseModuleFrame):
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

        # ===== Formulario =====
        self._build_form()
        self.form.grid(row=2, column=0, padx=16, pady=(8,10), sticky="ew")
        self._hide_form()

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0,8), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        # ===== Variables =====
        self._data = []
        self._rows = []
        self._selected_idx = None
        self.estudiantes = []
        self.estudiantes_id_to_name = {}
        self.estudiantes_name_to_id = {}
        self._totals_frame = None

        self._render_table()
        self.after(150, self._cargar_catalogos_y_listar)

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

        label(2, 2, "Estado")
        self.cb_estado = ctk.CTkComboBox(self.form, values=["pendiente", "parcial", "pagado"], width=180)
        self.cb_estado.set("pendiente")
        self.cb_estado.grid(row=3, column=2, padx=10, pady=(0,8), sticky="w")

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
            self.cb_estado.set(data.get("estado", "pendiente"))
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
            self.cb_estado.set("pendiente")
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
        est_name = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), rec.get("idEstudiante"))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar estado de cuenta de {est_name}?"):
            self.app._info("Operación cancelada.")
            return
        try:
            if self.app.api and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
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
                if self.app.api:
                    self.app.api.create("estados-cuenta", payload)
                    self.app._info("Estado de cuenta creado.")
                else:
                    payload["_local_id"] = (max([r.get("_local_id",0) for r in self._data] or [0]) + 1)
                    self._data.append(payload)
            else:
                if self._editing_idx is None:
                    self.app._info("No se seleccionó registro para actualizar.")
                    return
                rec = self._data[self._editing_idx]
                if self.app.api and rec.get("id"):
                    self.app.api.update("estados-cuenta", rec.get("id"), payload)
                    self.app._info("Estado de cuenta actualizado.")
                else:
                    self._data[self._editing_idx].update(payload)

            self._hide_form()
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar:\n{e}", parent=self)

    # ===================== CARGA DATOS =====================
    def _cargar_catalogos_y_listar(self):
        try:
            if not self.app.api:
                self._refrescar(local_only=True)
                return

            raw = self.app.api.get_all("estudiantes") or []
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
                    self.estudiantes_name_to_id[nombre] = eid

            self.cb_estudiante.configure(values=sorted(list(self.estudiantes_name_to_id.keys())))
            if self.cb_estudiante.cget("values") and not self.cb_estudiante.get():
                self.cb_estudiante.set(self.cb_estudiante.cget("values")[0])

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible cargar catálogos:\n{e}", parent=self)

    def _refrescar(self, local_only=False):
        try:
            if self.app.api and not local_only:
                raw = self.app.api.get_all("estados-cuenta") or []
                if isinstance(raw, dict):
                    for key in ("content","items","estados-cuenta","data","results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []
                self._data = raw or []
            self._render_table()
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible consultar la API:\n{e}", parent=self)

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

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        specs = self._apply_colspecs(header)

        for i, (nombre, _, _) in enumerate(specs):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin registros", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            self._render_totals()
            return

        for r, rec in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            for i, (_, minw, weight) in enumerate(specs):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)

            est = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), str(rec.get("idEstudiante") or ""))
            total = float(rec.get("montoTotal") or 0)
            pagado = float(rec.get("montoPagado") or 0)
            saldo = total - pagado
            estado = rec.get("estado", "pendiente").capitalize()
            saldo_color = "#d9534f" if saldo > 0 else "#28a745"

            vals = [
                est, f"{total:,.2f}", f"{pagado:,.2f}", f"{saldo:,.2f}", estado
            ]

            for i, val in enumerate(vals):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")
            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=8,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

        self._render_totals()

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
        self._totals_frame.grid(row=4, column=0, padx=16, pady=(0,12), sticky="ew")

        ctk.CTkLabel(self._totals_frame, text=f"Totales — Registros: {len(self._data)}",
                     text_color=self.app.COLOR_MUTED).grid(row=0, column=0, padx=(8,12), pady=8, sticky="w")
        ctk.CTkLabel(self._totals_frame, text=f"Monto total: {total_total:,.2f}",
                     text_color=self.app.COLOR_TEXT).grid(row=0, column=1, padx=12, pady=8, sticky="e")
        ctk.CTkLabel(self._totals_frame, text=f"Pagado: {total_pagado:,.2f}",
                     text_color=self.app.COLOR_TEXT).grid(row=0, column=2, padx=12, pady=8, sticky="e")
        ctk.CTkLabel(self._totals_frame, text=f"Saldo: {total_saldo:,.2f}",
                     text_color=saldo_color).grid(row=0, column=3, padx=12, pady=8, sticky="e")

    # ===================== SELECCIÓN =====================
    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    def _edit_row(self, idx):
        self._select_row(idx)
        self._editing_idx = idx
        self._show_form("edit", self._data[idx])

    def _delete_row(self, idx):
        self._select_row(idx)
        rec = self._data[idx]
        est = self.estudiantes_id_to_name.get(rec.get("idEstudiante"), rec.get("idEstudiante"))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar registro de {est}?"):
            self.app._info("Operación cancelada.")
            return
        try:
            if self.app.api and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
            else:
                del self._data[idx]
                self.app._info("Registro eliminado (local).")
            self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)
