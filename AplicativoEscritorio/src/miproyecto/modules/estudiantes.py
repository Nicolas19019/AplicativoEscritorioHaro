import customtkinter as ctk
from tkinter import messagebox

from modules.base import BaseModuleFrame

# === StudentInlineForm (idéntico al tuyo original) ===
class StudentInlineForm(ctk.CTkFrame):
    """
    Formulario en línea (colapsable) para crear/editar estudiante.
    Devuelve SIEMPRE campos en camelCase como los pide la API.

    NOTA: ahora incluye "categoria".
    Si tu backend usa otro nombre (p.ej. "categoriaLicencia"),
    puedes mapearlo en _collect() duplicando el valor.
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

        # --------- Fila 0: Documento ---------
        ctk.CTkLabel(self, text="Tipo Documento").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.cb_tipo = ctk.CTkComboBox(self, values=["CC","TI","CE","PA"], width=120)
        self.cb_tipo.set("CC")
        self.cb_tipo.grid(row=0, column=1, padx=12, pady=(12,6), sticky="w")

        ctk.CTkLabel(self, text="Número Documento").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_doc = BorderedEntry(self, placeholder_text="1012345678")
        self.en_doc.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # --------- Fila 1: Nombre / Apellido ---------
        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nombre = BorderedEntry(self, placeholder_text="Andres")
        self.en_nombre.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_apellido = BorderedEntry(self, placeholder_text="Agudelo")
        self.en_apellido.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 2: Contacto ---------
        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 3: Dirección / Estado ---------
        ctk.CTkLabel(self, text="Dirección").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.en_dir = BorderedEntry(self, placeholder_text="Calle 68")
        self.en_dir.grid(row=3, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Estado").grid(row=3, column=2, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Inactivo","Suspendido"], width=140)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=3, column=3, padx=12, pady=6, sticky="w")

        # --------- Fila 4: Categoría (NUEVO) ---------
        ctk.CTkLabel(self, text="Categoría").grid(row=4, column=0, padx=12, pady=6, sticky="w")
        self.cb_categoria = ctk.CTkComboBox(self, values=["A2","B1","C1"], width=140)
        self.cb_categoria.set("A2")
        self.cb_categoria.grid(row=4, column=1, padx=12, pady=6, sticky="w")

        # --------- Fila 5: Botones ---------
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    def _force_entry_placeholders(self):
        """Fuerza a que los placeholders de CTkEntry se muestren correctamente al cargar."""
        try:
            for attr in dir(self):
                widget = getattr(self, attr)
                if isinstance(widget, ctk.CTkEntry):
                    widget.focus()          # activa el entry
                    widget.master.focus()   # quita el foco inmediatamente
            self.update_idletasks()
        except Exception as e:
            print(f"[WARN] Error forzando placeholders en {self.__class__.__name__}: {e}")

    # -------- API pública --------
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def hide(self):
        self.grid_remove()

    # -------- Internos --------
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
        # categoría admite varios nombres que pueda traer tu API
        cat_val = (
            d.get("categoria")
            or d.get("categoriaLicencia")
            or d.get("licenciaCategoria")
            or d.get("programa")
            or d.get("category")
            or d.get("clase")
            or "A2"
        )
        self.cb_categoria.set(str(cat_val).upper())

    def _collect(self):
        # Devuelve CAMELCASE, exactamente como tu API + 'categoria'
        categoria = (self.cb_categoria.get() or "").strip().upper()
        data = {
            "tipoDocumento": self.cb_tipo.get().strip(),
            "numeroDocumento": self.en_doc.get().strip(),
            "nombre": self.en_nombre.get().strip(),
            "apellido": self.en_apellido.get().strip(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
            "direccion": self.en_dir.get().strip(),
            "estado": self.cb_estado.get().strip(),
            "categoria": categoria,                # <--- NUEVO (clave base)
            "usuario": None,
            "contrasena": None,
        }

        return data

    def _validate(self, d):
        req = ["tipoDocumento","numeroDocumento","nombre","apellido","telefono","email","estado","categoria"]
        for k in req:
            if not d.get(k):
                return False, "El campo '{}' es obligatorio.".format(k)
        if not d["numeroDocumento"].isdigit():
            return False, "El Número de Documento debe ser numérico."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El Teléfono debe ser numérico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no válido."
        if d["categoria"].upper() not in {"A2","B1","C1"}:
            return False, "La categoría debe ser A2, B1 o C1."
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
    DEBOUNCE_MS = 250  # retardo para búsqueda en vivo

    def __init__(self, master):
        super().__init__(master, "Estudiantes", "Gestione matrículas y datos del alumno")

        # ---------- Estado (DECLARAR PRIMERO para evitar carreras) ----------
        self._all_data = []   # todo lo que viene de la API
        self._data = []       # datos filtrados para pintar
        self._rows = []
        self._selected_idx = None
        self._debounce_id = None

        # ===== Toolbar =====
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

        # ===== Form inline =====
        self.form = StudentInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0,10), sticky="ew")
        self.form.hide()

        # ===== Filtros Pro =====
        self.filters = self._make_filters_bar(self)  # crea widgets y bindings
        self.filters.grid(row=3, column=0, padx=16, pady=(0,10), sticky="ew")
        self._refresh_category_options()  # inicializa opciones (A2/B1/C1 + las que vengan)

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Documento",   160,  0),
            ("Nombre completo",      320,  1),
            ("Categoría",        100, 0),
            ("Estado",      140,  0),
            ("Email",       220,  0),
            ("Acciones",    120,  0),
        
        ]

        
        self._render_table()
        self.after(150, self._refrescar)

    # ---------- UI: Filtros ----------
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        # 0: doc, 1: nombre, 2: estado, 3: categoria, 4: botones
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=0)

        def entry(ph):
            return ctk.CTkEntry(
                bar, placeholder_text=ph, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER
            )

        # Documento
        ctk.CTkLabel(bar, text="Documento").grid(row=0, column=0, padx=(12,8), pady=(10,4), sticky="w")
        self.f_doc = entry("Ej: 1012345678")
        self.f_doc.grid(row=1, column=0, padx=(12,8), pady=(0,10), sticky="ew")

        # Nombre
        ctk.CTkLabel(bar, text="Nombre").grid(row=0, column=1, padx=(8,8), pady=(10,4), sticky="w")
        self.f_nombre = entry("Nombre o apellido")
        self.f_nombre.grid(row=1, column=1, padx=(8,8), pady=(0,10), sticky="ew")

        # Estado
        ctk.CTkLabel(bar, text="Estado").grid(row=0, column=2, padx=(8,8), pady=(10,4), sticky="w")
        self.f_estado = ctk.CTkComboBox(bar, values=["Todos","Activo","Inactivo","Suspendido"], width=160)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=2, padx=(8,8), pady=(0,10), sticky="w")

        # Categoría
        ctk.CTkLabel(bar, text="Categoría").grid(row=0, column=3, padx=(8,8), pady=(10,4), sticky="w")
        self.f_categoria = ctk.CTkComboBox(
            bar,
            values=["Todas", "A2", "B1", "C1"],  # visibles desde el inicio
            width=160
        )
        self.f_categoria.set("Todas")
        self.f_categoria.grid(row=1, column=3, padx=(8,8), pady=(0,10), sticky="w")

        # Botones (columna 4 — no pises la 3)
        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=1, column=4, padx=(8,12), pady=(0,10), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=10,
                                 fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
                                 text_color=self.app.COLOR_TEXT, command=cmd)
        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=6)
        light_btn("Buscar", self._apply_filters_now).grid(row=0, column=1, padx=6)

        # Bindings (búsqueda en vivo con debounce)
        for w in (self.f_doc, self.f_nombre):
            w.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_categoria.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())

        return bar

    def _collect_filters(self):
        return {
            "doc": (self.f_doc.get() or "").strip(),
            "nombre": (self.f_nombre.get() or "").strip(),
            "estado": (self.f_estado.get() or "Todos").strip(),
            "categoria": (self.f_categoria.get() or "Todas").strip(),
        }

    def _clear_filters(self):
        self.f_doc.delete(0, "end")
        self.f_nombre.delete(0, "end")
        self.f_estado.set("Todos")
        self.f_categoria.set("Todas")
        self._apply_filters_now()

    def _debounced_apply_filters(self):
        if self._debounce_id:
            try: self.after_cancel(self._debounce_id)
            except Exception: pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._apply_filters_now)

    def _apply_filters_now(self):
        src = getattr(self, "_all_data", []) or []   # a prueba de inicialización temprana
        self._data = self._apply_filters(src, self._collect_filters())
        self._render_table()

    def _apply_filters(self, data_list, f):
        """Filtra localmente por documento, nombre, estado y categoría. Insensible a mayúsculas."""
        if not data_list:
            return []

        d_sub = f["doc"].lower()
        n_sub = f["nombre"].lower()
        estado = f["estado"]
        cat = f["categoria"].upper()

        out = []
        for stu in data_list:
            doc = str(stu.get("numeroDocumento","") or "").lower()
            nombre = (stu.get("nombre","") or "").strip()
            apellido = (stu.get("apellido","") or "").strip()
            full = f"{nombre} {apellido}".strip().lower()
            est = (stu.get("estado","") or "").strip()
            categoria = (
                stu.get("categoria")
                or stu.get("categoriaLicencia")
                or stu.get("licenciaCategoria")
                or stu.get("programa")
                or stu.get("category")
                or stu.get("clase")
                or ""
            )
            categoria_up = str(categoria).strip().upper()

            if d_sub and d_sub not in doc:
                continue
            if n_sub and n_sub not in full:
                continue
            if estado != "Todos" and est != estado:
                continue
            if cat != "TODAS" and categoria_up != cat:
                continue
            out.append(stu)
        return out

    def _refresh_category_options(self):
        """Completa el combo con categorías detectadas en los datos, sin perder A2/B1/C1."""
        base = {"A2","B1","C1"}
        cats = set()
        for stu in (getattr(self, "_all_data", []) or []):
            c = (
                stu.get("categoria")
                or stu.get("categoriaLicencia")
                or stu.get("licenciaCategoria")
                or stu.get("programa")
                or stu.get("category")
                or stu.get("clase")
                or ""
            )
            c = str(c).strip().upper()
            if c:
                cats.add(c)
        final = ["Todas"] + sorted(base | cats)
        try:
            self.f_categoria.configure(values=final)
            if self.f_categoria.get() not in final:
                self.f_categoria.set("Todas")
        except Exception:
            pass

    # ---------- helpers de tabla ----------
    def _apply_colspecs(self, container):
        
        for i, (_, minw, weight) in enumerate(self._COLS):
            
            container.grid_columnconfigure(i, minsize=minw, weight=weight or 1)

    
    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()
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
            categoria = (
                stu.get("categoria")
                or stu.get("categoriaLicencia")
                or stu.get("licenciaCategoria")
                or stu.get("programa")
                or stu.get("category")
                or stu.get("clase")
                or ""
            )
            categoria_disp = str(categoria).upper().strip()

            values = [
                stu.get("numeroDocumento",""),
                full_name,
                categoria_disp,
                stu.get("estado",""),
                stu.get("email",""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                                   anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")


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

    # ---------- acciones UI ----------
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
        self.form.hide()

    # ---------- API: listar / crear / actualizar / eliminar ----------
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            # 1) intento: server-side si tu ApiClient soporta query 'q'
            q = self._collect_filters()
            can_query = hasattr(self.app.api, "get_all") and getattr(self.app.api, "supports_query", False)
            if can_query and (q["doc"] or q["nombre"] or q["estado"] not in ("","Todos") or q["categoria"] != "Todas"):
                params = {}
                if q["doc"]: params["doc"] = q["doc"]
                if q["nombre"]: params["nombre"] = q["nombre"]
                if q["estado"] != "Todos": params["estado"] = q["estado"]
                if q["categoria"] != "Todas": params["categoria"] = q["categoria"]
                raw = self.app.api.get_all("estudiantes", params=params) or []
            else:
                raw = self.app.api.get_all("estudiantes") or []

            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []

            self._all_data = raw or []
            self._refresh_category_options()  # actualiza valores del combo con lo recibido
            self._data = self._apply_filters(self._all_data, self._collect_filters())
            self._render_table()

        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible consultar la API:\n{}".format(e), parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

        # --- payload base ---
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

                # id del estudiante
                student_id = self._data[idx].get("id") or self._data[idx].get("idEstudiante")
                if not student_id:
                    self.app._info("No se encontró el ID del estudiante.")
                    return

                # --- MUY IMPORTANTE ---
                # Algunos backends esperan el objeto completo. Mergeamos el registro original + payload nuevo
                merged = dict(self._data[idx])   # copia del registro actual
                merged.update(payload)           # aplica cambios del form

                # Asegurar que categoria va en el body (por si el form no la trae por alguna razón)
                cat = (payload.get("categoria") or merged.get("categoria") or "").strip().upper()
                if not cat:
                    # intenta leer de aliases del registro existente
                    cat = str(merged.get("categoriaLicencia") or merged.get("licenciaCategoria")
                            or merged.get("tipoLicencia") or "").strip().upper()
                if cat:
                    merged["categoria"] = cat
                    # también replicas de cortesía
                    merged["categoriaLicencia"] = cat
                    merged["licenciaCategoria"] = cat
                    merged["tipoLicencia"] = cat

                # No mandes el id en el cuerpo si tu backend no lo necesita
                body = {k: v for k, v in merged.items() if k not in ("id", "idEstudiante")}

                # PUT /api/estudiantes/{id}
                self.app.api.update("estudiantes", student_id, body)
                self.app._info("Estudiante actualizado.")


            self._refrescar()  # refrescar conservando filtros

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
