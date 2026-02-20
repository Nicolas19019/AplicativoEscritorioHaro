import customtkinter as ctk
from tkinter import messagebox
import threading
import time

from modules.base import BaseModuleFrame

def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    value_str = str(value).strip().lower()
    if value_str in {"1", "true", "t", "yes", "si", "sí", "on"}:
        return True
    if value_str in {"0", "false", "f", "no", "off"}:
        return False
    return default

def _normalize_tipo_pase(raw_value):
    if raw_value is None:
        return ""
    tokens = []
    text = str(raw_value).strip().lower()
    for part in text.replace(";", ",").replace("|", ",").replace("/", ",").split(","):
        p = part.strip()
        if not p:
            continue
        if p == "carro" and "carro" not in tokens:
            tokens.append("carro")
        if p == "moto" and "moto" not in tokens:
            tokens.append("moto")
    return ",".join(tokens)

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
        self.cb_estado = ctk.CTkComboBox(self, values=["Pendiente", "Activo", "Inactivo", "Suspendido"], width=140)
        self.cb_estado.set("Pendiente")
        self.cb_estado.grid(row=3, column=3, padx=12, pady=6, sticky="w")

        # --------- Fila 4: Categoría / Tipo Estudiante ---------
        ctk.CTkLabel(self, text="Categoría").grid(row=4, column=0, padx=12, pady=6, sticky="w")
        self.cb_categoria = ctk.CTkComboBox(self, values=["A2","B1","C1"], width=140)
        self.cb_categoria.set("A2")
        self.cb_categoria.grid(row=4, column=1, padx=12, pady=6, sticky="w")

        ctk.CTkLabel(self, text="Tipo Estudiante").grid(row=4, column=2, padx=12, pady=6, sticky="w")
        self.cb_tipo_estudiante = ctk.CTkComboBox(
            self,
            values=["prospecto", "inscrito", "activo", "egresado"],
            width=160
        )
        self.cb_tipo_estudiante.set("prospecto")
        self.cb_tipo_estudiante.grid(row=4, column=3, padx=12, pady=6, sticky="w")

        # --------- Fila 5: Sede / Horas ---------
        ctk.CTkLabel(self, text="Sede").grid(row=5, column=0, padx=12, pady=6, sticky="w")
        self.en_sede = BorderedEntry(self, placeholder_text="Sede principal")
        self.en_sede.grid(row=5, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Horas").grid(row=5, column=2, padx=12, pady=6, sticky="w")
        self.en_horas = BorderedEntry(self, placeholder_text="0")
        self.en_horas.grid(row=5, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 6: Tipo Pase / Estados booleanos ---------
        ctk.CTkLabel(self, text="Tipo Pase").grid(row=6, column=0, padx=12, pady=6, sticky="w")
        tipo_pase_wrap = ctk.CTkFrame(self, fg_color="transparent")
        tipo_pase_wrap.grid(row=6, column=1, padx=12, pady=6, sticky="w")

        self.ck_tipo_pase_carro = ctk.CTkCheckBox(tipo_pase_wrap, text="Carro")
        self.ck_tipo_pase_carro.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.ck_tipo_pase_moto = ctk.CTkCheckBox(tipo_pase_wrap, text="Moto")
        self.ck_tipo_pase_moto.grid(row=0, column=1, padx=(0, 8), sticky="w")

        bool_wrap = ctk.CTkFrame(self, fg_color="transparent")
        bool_wrap.grid(row=6, column=2, columnspan=2, padx=12, pady=6, sticky="w")

        self.sw_aprobo_teorico = ctk.CTkSwitch(bool_wrap, text="Aprobó teórico")
        self.sw_aprobo_teorico.grid(row=0, column=0, padx=(0, 16), sticky="w")
        self.sw_visible = ctk.CTkSwitch(bool_wrap, text="Visible")
        self.sw_visible.grid(row=0, column=1, padx=(0, 16), sticky="w")

        # --------- Fila 7: Botones ---------
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=7, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"
        self.sw_visible.select()

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
        for w in (
            self.en_doc, self.en_nombre, self.en_apellido, self.en_tel,
            self.en_mail, self.en_dir, self.en_sede, self.en_horas
        ):
            w.delete(0, "end")
        self.cb_tipo.set(d.get("tipoDocumento", "CC"))
        self.en_doc.insert(0, d.get("numeroDocumento", ""))
        self.en_nombre.insert(0, d.get("nombre", ""))
        self.en_apellido.insert(0, d.get("apellido", ""))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))
        self.en_dir.insert(0, d.get("direccion", ""))
        self.cb_estado.set(d.get("estado", "Pendiente"))

        tipo_estudiante = (d.get("tipoEstudiante") or "prospecto").strip().lower()
        self.cb_tipo_estudiante.set(tipo_estudiante or "prospecto")

        self.en_sede.insert(0, d.get("sede", "") or "")

        horas = d.get("horas", 0)
        self.en_horas.insert(0, "" if horas is None else str(horas))

        tipo_pase = _normalize_tipo_pase(d.get("tipoPase"))
        if not tipo_pase:
            tipo_pase = "carro"
        if "carro" in tipo_pase:
            self.ck_tipo_pase_carro.select()
        else:
            self.ck_tipo_pase_carro.deselect()
        if "moto" in tipo_pase:
            self.ck_tipo_pase_moto.select()
        else:
            self.ck_tipo_pase_moto.deselect()

        if _to_bool(d.get("aproboExamenTeorico"), default=False):
            self.sw_aprobo_teorico.select()
        else:
            self.sw_aprobo_teorico.deselect()

        if _to_bool(d.get("visible"), default=True):
            self.sw_visible.select()
        else:
            self.sw_visible.deselect()

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
        tipo_pase = []
        if _to_bool(self.ck_tipo_pase_carro.get()):
            tipo_pase.append("carro")
        if _to_bool(self.ck_tipo_pase_moto.get()):
            tipo_pase.append("moto")

        horas_raw = (self.en_horas.get() or "").strip()
        horas = None
        if horas_raw:
            try:
                horas = int(horas_raw)
            except ValueError:
                horas = horas_raw

        data = {
            "tipoDocumento": self.cb_tipo.get().strip(),
            "numeroDocumento": self.en_doc.get().strip(),
            "nombre": self.en_nombre.get().strip(),
            "apellido": self.en_apellido.get().strip(),
            "tipoEstudiante": (self.cb_tipo_estudiante.get() or "prospecto").strip().lower(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
            "direccion": self.en_dir.get().strip(),
            "sede": self.en_sede.get().strip(),
            "horas": horas,
            "tipoPase": ",".join(tipo_pase),
            "aproboExamenTeorico": _to_bool(self.sw_aprobo_teorico.get()),
            "visible": _to_bool(self.sw_visible.get(), default=True),
            "estado": self.cb_estado.get().strip(),
            "categoria": categoria,                # <--- NUEVO (clave base)
            "usuario": None,
            "contrasena": None,
        }

        return data

    def _validate(self, d):
        req = [
            "tipoDocumento", "numeroDocumento", "nombre", "apellido",
            "telefono", "email", "estado", "categoria", "sede"
        ]
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
        if d.get("tipoPase") not in {"carro", "moto", "carro,moto"}:
            return False, "Tipo Pase debe ser carro, moto o ambos."
        horas = d.get("horas")
        if horas is None:
            d["horas"] = 0
        elif not isinstance(horas, int):
            return False, "Horas debe ser un número entero."
        elif horas < 0:
            return False, "Horas no puede ser negativo."
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
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 4
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16

    def __init__(self, master):
        super().__init__(master, "Estudiantes", "Gestione matrículas y datos del alumno")

        # ---------- Estado (DECLARAR PRIMERO para evitar carreras) ----------
        self._all_data = []   # todo lo que viene de la API
        self._data = []       # datos filtrados para pintar
        self._rows = []
        self._selected_idx = None
        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._row_pool = []
        self._empty_label = None
        self._loading_overlay = None
        self._last_refresh_ts = 0

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
            ("Documento",   130,  0),
            ("Nombre completo", 220,  1),
            ("Categoría",   90, 0),
            ("Sede",       120, 0),
            ("Horas",       70, 0),
            ("Tipo pase",  100, 0),
            ("Teórico",     90, 0),
            ("Estado",     110, 0),
            ("Acciones",   120, 0),
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
        self.f_estado = ctk.CTkComboBox(
            bar,
            values=["Todos", "Pendiente", "Activo", "Inactivo", "Suspendido"],
            width=160
        )
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
        self._queue_render(self._data)

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

    def _student_row_values(self, stu):
        full_name = "{} {}".format(stu.get("nombre", ""), stu.get("apellido", "")).strip()
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
        tipo_pase_disp = _normalize_tipo_pase(stu.get("tipoPase"))
        teorico_ok = _to_bool(stu.get("aproboExamenTeorico"), default=False)
        horas = stu.get("horas")
        horas_disp = "-" if horas is None else str(horas)
        return [
            stu.get("numeroDocumento", ""),
            full_name,
            categoria_disp,
            stu.get("sede", "") or "",
            horas_disp,
            tipo_pase_disp or "-",
            "Aprobado" if teorico_ok else "Pendiente",
            stu.get("estado", ""),
        ]

    def _render_table(self):
        self._queue_render(self._data)

    def _build_table_shell(self):
        if getattr(self, "_table_header", None) and self._table_header.winfo_exists():
            return

        for w in self.table.winfo_children():
            w.destroy()
        self._row_pool = []

        self._table_header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        self._table_header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self._apply_colspecs(self._table_header)
        for i, (nombre, _, _) in enumerate(self._COLS):
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
            text="Sin resultados",
            text_color=self.app.COLOR_MUTED
        )
        self._empty_label.grid(row=0, column=0, padx=8, pady=12, sticky="w")
        self._empty_label.grid_remove()

    def _create_row_widget(self):
        row = ctk.CTkFrame(self._rows_container, fg_color=self.app.COLOR_PANEL, corner_radius=10)
        self._apply_colspecs(row)

        labels = []
        for i in range(len(self._COLS) - 1):
            lbl = ctk.CTkLabel(row, text="", text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
            lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
            labels.append(lbl)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")

        btn_edit = ctk.CTkButton(
            actions, text="✎", width=36, height=32, corner_radius=10,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_edit.grid(row=0, column=0, padx=4)

        btn_delete = ctk.CTkButton(
            actions, text="🗑️", width=36, height=32, corner_radius=10,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_delete.grid(row=0, column=1, padx=4)

        return {
            "frame": row,
            "labels": labels,
            "edit_btn": btn_edit,
            "delete_btn": btn_delete,
        }

    def _update_row_widget(self, row_info, stu, idx):
        row = row_info["frame"]
        row.configure(fg_color=self.app.COLOR_PANEL)
        values = self._student_row_values(stu)

        for col, val in enumerate(values):
            lbl = row_info["labels"][col]
            lbl.configure(text=str(val))
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

        paint_batch(0)

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
    def _refrescar(self, force_refresh=True):
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if not self.app.api:
            self.app._info("No hay cliente API activo. Inicia sesión.")
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                q = self._collect_filters()
                can_query = hasattr(self.app.api, "get_all") and getattr(self.app.api, "supports_query", False)
                if can_query and (q["doc"] or q["nombre"] or q["estado"] not in ("", "Todos") or q["categoria"] != "Todas"):
                    params = {}
                    if q["doc"]:
                        params["doc"] = q["doc"]
                    if q["nombre"]:
                        params["nombre"] = q["nombre"]
                    if q["estado"] != "Todos":
                        params["estado"] = q["estado"]
                    if q["categoria"] != "Todas":
                        params["categoria"] = q["categoria"]
                    raw = self.app.api.get_all("estudiantes", params=params, force_refresh=force_refresh) or []
                else:
                    raw = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []

                if isinstance(raw, dict):
                    for key in ("content", "items", "estudiantes", "data", "results"):
                        lst = raw.get(key)
                        if isinstance(lst, list):
                            raw = lst
                            break
                    else:
                        raw = []

                def apply_data():
                    self._all_data = raw or []
                    self._refresh_category_options()
                    self._data = self._apply_filters(self._all_data, self._collect_filters())
                    self._queue_render(self._data)

                self.after(0, apply_data)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Estudiantes", "No fue posible consultar la API:\n{}".format(e), parent=self))
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

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

        # --- payload base ---
            payload = dict(payload)
            payload["tipoPase"] = _normalize_tipo_pase(payload.get("tipoPase"))
            payload["aproboExamenTeorico"] = _to_bool(payload.get("aproboExamenTeorico"), default=False)
            payload["visible"] = _to_bool(payload.get("visible"), default=True)
            doc = (payload.get("numeroDocumento") or "").strip()
            if not doc:
                messagebox.showerror("Validación", "El Número de Documento es obligatorio.", parent=self)
                return
            if payload.get("usuario") in (None, ""):
                payload["usuario"] = doc
            if payload.get("contrasena") in (None, ""):
                payload["contrasena"] = doc

            if mode == "create":
                payload["visible"] = True
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


            self._last_refresh_ts = 0
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
        if not messagebox.askyesno("Confirmar", "¿Eliminar al estudiante:\n{} (Doc: {})".format(full_name, doc)):
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
            self._last_refresh_ts = 0
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Estudiantes", "No fue posible eliminar:\n{}".format(e), parent=self)
