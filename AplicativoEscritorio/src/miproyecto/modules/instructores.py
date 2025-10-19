import customtkinter as ctk
from tkinter import messagebox
from modules.base import BaseModuleFrame
from modules.forms_inlines import InstructorInlineForm


class InstructoresView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Instructores", "Gestione los profesores registrados en el sistema")

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0,1,2), weight=0)
        tb.grid_columnconfigure(3, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(parent, text=text, height=40, corner_radius=18,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd, anchor="w")

        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8, pady=6, sticky="w")

        # Formulario inline
        self.form = InstructorInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # Filtros
        filters = self._make_filters_pro(self, campos=("Cédula","Nombre","Apellido"),
                                         estados=("Todos","Activo","Inactivo","Suspendido"))
        filters.grid(row=3, column=0, padx=16, pady=(0,10), sticky="ew")

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)      # <--- IMPORTANTE (permite crecer)
        self.grid_columnconfigure(0, weight=1)   # <--- IMPORTANTE (permite ancho total)
        self.table.grid_columnconfigure(0, weight=1)


        self._COLS = [
            ("Cédula", 120, 0),
            ("Nombre", 220, 1),
            ("Especialidad", 160, 0),
            ("Teléfono", 120, 0),
            ("Email", 220, 0),
            ("Acciones", 120, 0),
        ]

        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # -------- helpers de tabla --------
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight or 1)

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        self._apply_colspecs(header)
        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, prof in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            full_name = "{} {}".format(prof.get("nombre",""), prof.get("apellido","")).strip()
            values = [
                prof.get("cedula",""),
                full_name,
                prof.get("especialidad",""),
                prof.get("telefono",""),
                prof.get("email",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(actions, text=symbol, width=36, height=32, corner_radius=10,
                                     fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                     text_color="#ffffff", command=cmd)
            icon_btn("✎", lambda idx=r-1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r-1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))
            self._rows.append(row)

    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    # -------- acciones UI --------
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un profesor en la tabla primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _cancel_inline(self):
        self.form.hide()

    # -------- API: listar / crear / actualizar / eliminar --------
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            raw = self.app.api.get_all("profesores") or []
            if isinstance(raw, dict):
                for key in ("content","items","profesores","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []

            self._data = raw or []
            self._render_table()
        except Exception as e:
            messagebox.showerror("Profesores", f"No fue posible consultar la API:\n{e}", parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            if mode == "create":
                print("[DEBUG] Creando profesor con:", payload)
                self.app.api.create("profesores", payload)
                self.app._info("Profesor creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un profesor para actualizar.")
                    return
                prof_id = self._data[idx].get("id")
                if not prof_id:
                    self.app._info("No se encontró el ID del profesor.")
                    return
                print("[DEBUG] Actualizando profesor con:", payload)
                self.app.api.update("profesores", prof_id, payload)
                self.app._info("Profesor actualizado.")

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Profesores", f"Operación fallida:\n{e}", parent=self)


    def _delete_row(self, idx):
        self._select_row(idx)
        prof = self._data[idx]
        name = "{} {}".format(prof.get("nombre",""), prof.get("apellido","")).strip()
        ced = prof.get("cedula","")
        if not messagebox.askyesno("Confirmar", f"¿Eliminar al profesor:\n{name} (Cédula: {ced})?"):
            self.app._info("Operación cancelada.")
            return
        try:
            prof_id = prof.get("id")
            if not prof_id:
                self.app._info("No se encontró el ID del profesor.")
                return
            self.app.api.delete("profesores", prof_id)
            self.app._info("Profesor eliminado.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Profesores", f"No fue posible eliminar:\n{e}", parent=self)
