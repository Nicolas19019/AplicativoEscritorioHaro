import customtkinter as ctk
from tkinter import messagebox

from modules.base import BaseModuleFrame

# === StudentInlineForm (idéntico al tuyo original) ===
class StudentInlineForm(ctk.CTkFrame):
    """
    Formulario en línea (colapsable) para crear/editar estudiante.
    Devuelve SIEMPRE campos en camelCase como los pide la API.
    - on_submit(data: dict, mode: "create" | "edit")
    - on_cancel()
    """
    def __init__(self, master, app, on_submit, on_cancel):
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        # Fila 0: Documento
        ctk.CTkLabel(self, text="Tipo Documento").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.cb_tipo = ctk.CTkComboBox(self, values=["CC","TI","CE","PA"], width=120)
        self.cb_tipo.set("CC")
        self.cb_tipo.grid(row=0, column=1, padx=12, pady=(12,6), sticky="w")

        ctk.CTkLabel(self, text="Número Documento").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_doc = BorderedEntry(self, placeholder_text="1012345678")
        self.en_doc.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Nombre / Apellido
        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nombre = BorderedEntry(self, placeholder_text="Nombre")
        self.en_nombre.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_apellido = BorderedEntry(self, placeholder_text="Apellido")
        self.en_apellido.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # Fila 2: Contacto
        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # Fila 3: Dirección / Estado
        ctk.CTkLabel(self, text="Dirección").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.en_dir = BorderedEntry(self, placeholder_text="Dirección")
        self.en_dir.grid(row=3, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Estado").grid(row=3, column=2, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Inactivo","Suspendido"], width=140)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=3, column=3, padx=12, pady=6, sticky="w")

        # Fila 4: Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # API pública
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self): self.grid_remove()

    # Internos
    def _fill(self, d):
        for w in (self.en_doc, self.en_nombre, self.en_apellido, self.en_tel, self.en_mail, self.en_dir):
            w.delete(0, "end")
        self.cb_tipo.set(d.get("tipoDocumento", "CC"))
        self.en_doc.insert(0, d.get("numeroDocumento", ""))
        self.en_nombre.insert(0, d.get("nombre", ""))
        self.en_apellido.insert(0, d.get("apellido", ""))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))
        self.en_dir.insert(0, d.get("direccion", ""))
        self.cb_estado.set(d.get("estado", "Activo"))

    def _collect(self):
        # Devuelve CAMELCASE, exactamente como tu API
        return {
            "tipoDocumento": self.cb_tipo.get().strip(),
            "numeroDocumento": self.en_doc.get().strip(),
            "nombre": self.en_nombre.get().strip(),
            "apellido": self.en_apellido.get().strip(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
            "direccion": self.en_dir.get().strip(),
            "estado": self.cb_estado.get().strip(),
            "usuario": None,
            "contrasena": None,
        }

    def _validate(self, d):
        req = ["tipoDocumento","numeroDocumento","nombre","apellido","telefono","email","estado"]
        for k in req:
            if not d.get(k):
                return False, "El campo '{}' es obligatorio.".format(k)
        if not d["numeroDocumento"].isdigit():
            return False, "El Número de Documento debe ser numérico."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El Teléfono debe ser numérico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no válido."
        return True, ""

    def _save(self):
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()


# === EstudiantesView (tu clase exacta) ===
class EstudiantesView(BaseModuleFrame):
    def __init__(self, master):
        super().__init__(master, "Estudiantes", "Gestione matrículas y datos del alumno")

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

        # Form inline (ya devuelve CAMELCASE)
        self.form = StudentInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # Filtros
        filters = self._make_filters_pro(self, campos=("Documento","Nombre","Apellidos"),
                                         estados=("Todos","Activo","Inactivo","Suspendido"))
        filters.grid(row=3, column=0, padx=16, pady=(0,10), sticky="ew")

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Documento",   160,  0),
            ("Nombre",      320,  1),
            ("Estado",      140,  0),
            ("Email",       220,  0),
            ("Acciones",    120,  0),
        ]

        # Los datos se mantienen en CAMELCASE (igual que la API)
        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # -------- helpers de tabla --------
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            # si la columna tiene weight 1, se expande con la ventana
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

        for r, stu in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            full_name = "{} {}".format(stu.get("nombre",""), stu.get("apellido","")).strip()
            values = [
                stu.get("numeroDocumento",""),
                full_name,
                stu.get("estado",""),
                stu.get("email",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=4, padx=8, pady=6, sticky="e")

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
            self.app._info("Selecciona un estudiante en la tabla primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])  # el form espera camelCase

    def _cancel_inline(self):
        pass

    # -------- API: listar / crear / actualizar / eliminar --------
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            raw = self.app.api.get_all("estudiantes") or []
            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []
            self._data = raw or []
            self._render_table()
        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible consultar la API:\n{}".format(e), parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            payload = dict(payload)

            doc = (payload.get("numeroDocumento") or "").strip()
            if not doc:
                messagebox.showerror("Validación", "El Número de Documento es obligatorio.", parent=self)
                return

            if payload.get("usuario") in (None, ""):
                payload["usuario"] = doc
            if payload.get("contrasena") in (None, ""):
                payload["contrasena"] = doc

            if mode == "create":
                self.app.api.create("estudiantes", payload)
                self.app._info("Estudiante creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un estudiante para actualizar.")
                    return
                student_id = self._data[idx].get("id") or self._data[idx].get("idEstudiante")
                if not student_id:
                    self.app._info("No se encontró el ID del estudiante.")
                    return
                self.app.api.update("estudiantes", student_id, payload)
                self.app._info("Estudiante actualizado.")
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Estudiantes", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        stu = self._data[idx]
        full_name = "{} {}".format(stu.get("nombre",""), stu.get("apellido","")).strip()
        doc = stu.get("numeroDocumento", "")
        if not doc:
            self.app._info("El registro no tiene 'numeroDocumento'.")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar al estudiante:\n{} (Doc: {})?".format(full_name, doc)):
            self.app._info("Operación cancelada.")
            return

        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return
            student_id = stu.get("id") or stu.get("idEstudiante")
            if not student_id:
                self.app._info("No se encontró el ID del estudiante.")
                return
            self.app.api.delete("estudiantes", student_id)
            self.app._info("Estudiante eliminado.")
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible eliminar:\n{}".format(e), parent=self)
