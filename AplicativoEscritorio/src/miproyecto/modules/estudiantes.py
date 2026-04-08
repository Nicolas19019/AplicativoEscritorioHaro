import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk
import threading
from datetime import datetime, date
import time

from modules.base import BaseModuleFrame
from modules.treeview_theme import configure_treeview_style, solid_color

SEDES_DISPONIBLES = ["1 de Mayo", "El Eden"]


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


def _upper_text(value):
    return str(value or "").strip().upper()

def _extract_sede(data: dict) -> str:
    """
    Devuelve la sede en formato texto, soportando variaciones de la API:
      - "sede" como string / id
      - "sede" como objeto (p.ej. {"id": 1, "nombre": "..."})
      - campos alternos: sedePrincipal, sedeNombre, nombreSede, campus...
    """
    if not isinstance(data, dict):
        return ""

    for key in ("sede", "sedePrincipal", "sede_principal", "sedeNombre", "nombreSede", "campus"):
        if key not in data:
            continue
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, dict):
            for k2 in ("nombre", "name", "descripcion", "sede"):
                v2 = val.get(k2)
                if v2 is not None and str(v2).strip():
                    return str(v2).strip()
            txt = str(val).strip()
            return txt
        if isinstance(val, str):
            if val.strip():
                return val.strip()
            continue
        txt = str(val).strip()
        if txt:
            return txt
    return ""


def _normalize_sede_label(value) -> str:
    txt = str(value or "").strip().lower()
    if not txt:
        return ""

    # Normaliza acentos y espacios para comparar mejor valores que vienen de distintas fuentes
    # (p. ej. "CC El Edén", "Centro Comercial El Eden", "Kennedy", etc.).
    txt = (
        txt.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    txt = " ".join(txt.split())
    compact = txt.replace(" ", "")

    if compact in {"1demayo", "1mayo", "1rodemayo", "1erdemayo"} or "mayo" in txt or "kennedy" in txt:
        return "1 de Mayo"
    if "eden" in txt:
        return "El Eden"
    return ""


def _normalize_tipo_estudiante(value) -> str:
    txt = str(value or "").strip().lower()
    if not txt:
        return ""
    if txt in {"matricula", "matrícula", "matriculado", "matriculada"}:
        return "matriculado"
    if txt in {"prospecto", "prospect"}:
        return "prospecto"
    if txt in {"inscrito", "inscrita", "inscripcion", "inscripción"}:
        return "inscrito"
    if txt in {"activo", "activa"}:
        return "activo"
    if txt in {"egresado", "egresada"}:
        return "egresado"
    return txt


def _extract_consecutivo(data: dict) -> str:
    if not isinstance(data, dict):
        return ""
    val = data.get("consecutivo")
    if val is None or val == "":
        val = data.get("consecutivoEstudiante")
    if val is None:
        return ""
    return str(val).strip()


# === StudentInlineForm (idéntico al tuyo original) ===
class StudentInlineForm(ctk.CTkFrame):
    """
    Formulario en línea (colapsable) para crear/editar estudiante.
    Devuelve SIEMPRE campos en camelCase como los pide la API.

    NOTA: ahora incluye "categoria".
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

        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        # --------- Fila 0: Documento ---------
        ctk.CTkLabel(self, text="Tipo Documento").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        self.cb_tipo = ctk.CTkComboBox(self, values=["CC", "TI", "CE", "PA"], width=120)
        self.cb_tipo.set("CC")
        self.cb_tipo.grid(row=0, column=1, padx=12, pady=(12, 6), sticky="w")

        ctk.CTkLabel(self, text="Número Documento").grid(row=0, column=2, padx=12, pady=(12, 6), sticky="w")
        self.en_doc = BorderedEntry(self, placeholder_text="1012345678")
        self.en_doc.grid(row=0, column=3, padx=12, pady=(12, 6), sticky="ew")

        # --------- Fila 1: Consecutivo / Nombre ---------
        ctk.CTkLabel(self, text="Consecutivo").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_consecutivo = BorderedEntry(self, placeholder_text="Ej: 000123")
        self.en_consecutivo.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_nombre = BorderedEntry(self, placeholder_text="Andres")
        self.en_nombre.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 2: Apellido / Contacto ---------
        ctk.CTkLabel(self, text="Apellido").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_apellido = BorderedEntry(self, placeholder_text="Agudelo")
        self.en_apellido.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 3: Email / Dirección ---------
        ctk.CTkLabel(self, text="Email").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=3, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Dirección").grid(row=3, column=2, padx=12, pady=6, sticky="w")
        self.en_dir = BorderedEntry(self, placeholder_text="Calle 68")
        self.en_dir.grid(row=3, column=3, padx=12, pady=6, sticky="ew")

        # --------- Fila 4: Estado / Categoría ---------
        ctk.CTkLabel(self, text="Estado").grid(row=4, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Pendiente", "Activo", "Inactivo", "Suspendido"], width=140)
        self.cb_estado.set("Pendiente")
        self.cb_estado.grid(row=4, column=1, padx=12, pady=6, sticky="w")

        ctk.CTkLabel(self, text="Categoría").grid(row=4, column=2, padx=12, pady=6, sticky="w")
        self.cb_categoria = ctk.CTkComboBox(self, values=["A2", "B1", "C1", "A2 y B1", "A2 - C1"], width=140)
        self.cb_categoria.set("A2")
        self.cb_categoria.grid(row=4, column=3, padx=12, pady=6, sticky="w")

        # --------- Fila 5: Tipo Estudiante / Sede ---------
        ctk.CTkLabel(self, text="Tipo Estudiante").grid(row=5, column=0, padx=12, pady=6, sticky="w")
        self.cb_tipo_estudiante = ctk.CTkComboBox(
            self,
            values=["prospecto", "matriculado", "inscrito", "activo", "egresado"],
            width=160
        )
        self.cb_tipo_estudiante.set("prospecto")
        self.cb_tipo_estudiante.grid(row=5, column=1, padx=12, pady=6, sticky="w")

        ctk.CTkLabel(self, text="Sede").grid(row=5, column=2, padx=12, pady=6, sticky="w")
        self.cb_sede = ctk.CTkComboBox(self, values=SEDES_DISPONIBLES, width=180)
        self.cb_sede.set(SEDES_DISPONIBLES[0])
        self.cb_sede.grid(row=5, column=3, padx=12, pady=6, sticky="w")

        # --------- Fila 6: Horas / Tipo Pase ---------
        ctk.CTkLabel(self, text="Horas").grid(row=6, column=0, padx=12, pady=6, sticky="w")
        self.en_horas = BorderedEntry(self, placeholder_text="0")
        self.en_horas.grid(row=6, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Tipo Pase").grid(row=6, column=2, padx=12, pady=6, sticky="w")
        tipo_pase_wrap = ctk.CTkFrame(self, fg_color="transparent")
        tipo_pase_wrap.grid(row=6, column=3, padx=12, pady=6, sticky="w")

        self.ck_tipo_pase_carro = ctk.CTkCheckBox(tipo_pase_wrap, text="Carro")
        self.ck_tipo_pase_carro.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.ck_tipo_pase_moto = ctk.CTkCheckBox(tipo_pase_wrap, text="Moto")
        self.ck_tipo_pase_moto.grid(row=0, column=1, padx=(0, 8), sticky="w")

        bool_wrap = ctk.CTkFrame(self, fg_color="transparent")
        bool_wrap.grid(row=7, column=0, columnspan=4, padx=12, pady=6, sticky="w")

        self.sw_aprobo_teorico = ctk.CTkSwitch(bool_wrap, text="Aprobó teórico")
        self.sw_aprobo_teorico.grid(row=0, column=0, padx=(0, 16), sticky="w")
        self.sw_visible = ctk.CTkSwitch(bool_wrap, text="Visible")
        self.sw_visible.grid(row=0, column=1, padx=(0, 16), sticky="w")

        # --------- Fila 8: Botones ---------
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=8, column=0, columnspan=4, padx=12, pady=(8, 12), sticky="e")

        def form_btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                btns,
                text=text,
                height=36,
                corner_radius=12,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
            )

        form_btn("Cancelar", self._cancel, self.app.COLOR_INPUT_BG, self.app.COLOR_DIVIDER, txt=self.app.COLOR_TEXT)\
            .grid(row=0, column=0, padx=6)
        form_btn("Guardar", self._save, self.app.COLOR_GREEN, self.app.GREEN_HOVER).grid(row=0, column=1, padx=6)

        self.mode = "create"
        self.sw_visible.select()

    def _assigned_admin_sede(self) -> str:
        raw = getattr(self.app, "current_admin_sede", None)
        return _normalize_sede_label(raw) or str(raw or "").strip()

    def _apply_admin_sede_restriction(self):
        assigned_sede = self._assigned_admin_sede()
        if getattr(self.app, "is_superadmin", False) or not assigned_sede:
            self.cb_sede.configure(values=SEDES_DISPONIBLES, state="normal")
            return
        self.cb_sede.configure(values=[assigned_sede], state="disabled")
        self.cb_sede.set(assigned_sede)

    def _apply_admin_tipo_estudiante_restriction(self):
        # La opción "prospecto" solo debe estar visible para el superadministrador.
        if getattr(self.app, "is_superadmin", False):
            values = ["prospecto", "matriculado", "inscrito", "activo", "egresado"]
        else:
            values = ["matriculado", "inscrito", "activo", "egresado"]

        try:
            self.cb_tipo_estudiante.configure(values=values)
        except Exception:
            return

        current = _normalize_tipo_estudiante(self.cb_tipo_estudiante.get())
        if current not in values:
            self.cb_tipo_estudiante.set(values[0])

    def _force_entry_placeholders(self):
        try:
            for attr in dir(self):
                widget = getattr(self, attr)
                if isinstance(widget, ctk.CTkEntry):
                    widget.focus()
                    widget.master.focus()
            self.update_idletasks()
        except Exception as e:
            print(f"[WARN] Error forzando placeholders en {self.__class__.__name__}: {e}")

    def show_create(self):
        self.mode = "create"
        self._fill({})
        self._apply_admin_sede_restriction()
        self._apply_admin_tipo_estudiante_restriction()
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self._apply_admin_sede_restriction()
        self._apply_admin_tipo_estudiante_restriction()
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def hide(self):
        self.grid_remove()

    def _fill(self, d):
        for w in (
            self.en_doc, self.en_consecutivo, self.en_nombre, self.en_apellido, self.en_tel,
            self.en_mail, self.en_dir, self.en_horas
        ):
            w.delete(0, "end")
        self.cb_tipo.set(d.get("tipoDocumento", "CC"))
        self.en_doc.insert(0, d.get("numeroDocumento", ""))
        self.en_consecutivo.insert(0, _extract_consecutivo(d))
        self.en_nombre.insert(0, d.get("nombre", ""))
        self.en_apellido.insert(0, d.get("apellido", ""))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))
        self.en_dir.insert(0, d.get("direccion", ""))
        self.cb_estado.set(d.get("estado", "Pendiente"))

        tipo_estudiante = _normalize_tipo_estudiante(d.get("tipoEstudiante") or "prospecto") or "prospecto"
        self.cb_tipo_estudiante.set(tipo_estudiante)

        self.cb_sede.set(_normalize_sede_label(_extract_sede(d)) or SEDES_DISPONIBLES[0])

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
            "consecutivo": (self.en_consecutivo.get() or "").strip() or None,
            "nombre": _upper_text(self.en_nombre.get()),
            "apellido": _upper_text(self.en_apellido.get()),
            "tipoEstudiante": (self.cb_tipo_estudiante.get() or "prospecto").strip().lower(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
            "direccion": self.en_dir.get().strip(),
            "sede": self.cb_sede.get().strip(),
            "horas": horas,
            "tipoPase": ",".join(tipo_pase),
            "aproboExamenTeorico": _to_bool(self.sw_aprobo_teorico.get()),
            "visible": _to_bool(self.sw_visible.get(), default=True),
            "estado": self.cb_estado.get().strip(),
            "categoria": categoria,
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
        allowed = {"A2", "B1", "C1", "A2 Y B1", "A2 - C1"}
        if d["categoria"].strip().upper() not in allowed:
            return False, "La categoría debe ser A2, B1, C1, A2 y B1 o A2 - C1."
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


# === EstudiantesView (render optimizado con Treeview) ===
class EstudiantesView(BaseModuleFrame):
    DEBOUNCE_MS = 250
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16
    TREE_INSERT_CHUNK = 250      # inserta por trozos para no congelar si escala
    TREE_INSERT_DELAY = 1        # ms

    def _form_scroll_height(self):
        try:
            screen_h = int(self.winfo_screenheight() or 900)
        except Exception:
            screen_h = 900
        if screen_h <= 768:
            return 250
        if screen_h <= 900:
            return 300
        return 360

    def __init__(self, master):
        super().__init__(master, "Estudiantes", "Gestione matrículas y datos del alumno")
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)

        # ---------- Estado ----------
        self._all_data = []
        self._data = []
        self._selected_idx = None
        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._loading_overlay = None
        self._last_refresh_ts = 0
        self._initial_layout_done = False
        self._initial_data_reflow_done = False

        # mapeo Tree IID -> idx actual en self._data
        self._iid_to_index = {}
        self.bind("<Map>", self._on_first_map, add="+")

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=0)
        tb.grid_columnconfigure(6, weight=1)

        def action_btn(parent, text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                parent,
                text=text,
                height=40,
                corner_radius=18,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
                anchor="w",
            )

        action_btn(tb, "＋ Nuevo", self._nuevo, self.app.COLOR_GREEN, self.app.GREEN_HOVER)\
            .grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        action_btn(tb, "✎ Editar", self._editar, self.app.COLOR_BLUE, self.app.BLUE_HOVER)\
            .grid(row=0, column=1, padx=8, pady=6, sticky="w")
        action_btn(tb, "🗑️ Eliminar", self._eliminar_seleccionado, self.app.COLOR_RED, self.app.RED_HOVER)\
            .grid(row=0, column=2, padx=8, pady=6, sticky="w")
        action_btn(tb, "↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER)\
            .grid(row=0, column=3, padx=8, pady=6, sticky="w")

        # ===== Resumen =====
        self._build_summary()

        # ===== Form inline =====
        self.form_host = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=12,
            height=self._form_scroll_height(),
        )
        self.form_host.grid_columnconfigure(0, weight=1)
        self.form = StudentInlineForm(self.form_host, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=0, column=0, sticky="ew")
        self.form_host.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()
        self.form_host.grid_remove()

        # ===== Filtros =====
        self.filters = self._make_filters_bar(self)
        self.filters.grid(row=4, column=0, padx=16, pady=(0, 10), sticky="ew")
        self._refresh_category_options()

        # ===== Tabla (Treeview) =====
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(5, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Documento", 130),
            ("Consecutivo", 110),
            ("Nombre completo", 320),
            ("Tipo estudiante", 130),
            ("Categoría", 90),
            ("Sede", 140),
            ("Horas", 70),
            ("Tipo pase", 110),
            ("Días restantes", 120),
            ("Ingreso", 120),
            ("Teórico", 90),
            ("Estado", 110),
        ]

        self._build_tree()

        self.after(150, self._refrescar)
        self.after(380, self._ensure_table_layout)

    def _build_summary(self):
        self.summary = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.summary.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        for col in range(4):
            self.summary.grid_columnconfigure(col, weight=1)

        self._summary_cards = {}
        cards = (
            ("total", "Total estudiantes"),
            ("activos", "Activos"),
            ("pendientes", "Pendientes"),
            ("teorico", "Teórico aprobado"),
        )
        for idx, (key, label) in enumerate(cards):
            if idx % 2 == 0:
                card_bg = self.app.RED_SOFT_BG
                card_border = self.app.RED_SOFT_BORDER
                value_color = self.app.COLOR_RED
            else:
                card_bg = self.app.MUSTARD_SOFT_BG
                card_border = self.app.MUSTARD_SOFT_BORDER
                value_color = self.app.MUSTARD_MAIN

            card = ctk.CTkFrame(
                self.summary,
                fg_color=card_bg,
                corner_radius=18,
                border_width=1,
                border_color=card_border,
            )
            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(
                card,
                text=label,
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(anchor="w", padx=12, pady=(10, 2))
            value = ctk.CTkLabel(
                card,
                text="0",
                text_color=value_color,
                font=ctk.CTkFont(size=22, weight="bold"),
            )
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self._summary_cards[key] = value

    def _refresh_summary(self):
        rows = list(getattr(self, "_all_data", []) or [])
        total = len(rows)
        activos = 0
        pendientes = 0
        teorico = 0

        for stu in rows:
            estado = str(stu.get("estado", "") or "").strip().lower()
            if estado == "activo":
                activos += 1
            if estado == "pendiente":
                pendientes += 1
            if _to_bool(stu.get("aproboExamenTeorico"), default=False):
                teorico += 1

        values = {
            "total": total,
            "activos": activos,
            "pendientes": pendientes,
            "teorico": teorico,
        }
        for key, value in values.items():
            try:
                self._summary_cards[key].configure(text=str(value))
            except Exception:
                pass

    def _on_first_map(self, _event=None):
        if self._initial_layout_done:
            return
        self._initial_layout_done = True
        self.after(120, self._ensure_table_layout)
        self.after(420, self._ensure_table_layout)

    def _ensure_table_layout(self):
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            if hasattr(self, "table") and self.table.winfo_exists():
                self.table.update_idletasks()
            if hasattr(self, "tree") and self.tree.winfo_exists():
                self.tree.update_idletasks()
        except Exception:
            pass
        if getattr(self, "_data", None):
            self._queue_render(self._data)

    # ---------- Treeview (rápido) ----------
    def _build_tree(self):
        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "Haro.Treeview", rowheight=30)

        cols = [c[0] for c in self._COLS]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Haro.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        # Scrollbars
        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Config columnas
        for name, w in self._COLS:
            self.tree.heading(name, text=name)
            anchor = "w"
            if name in {"Horas", "Teórico", "Estado", "Días restantes", "Categoría", "Ingreso", "Tipo estudiante", "Consecutivo"}:
                anchor = "center"
            self.tree.column(name, width=w, minwidth=max(60, int(w * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])
        self.tree.tag_configure("days_warn_30", foreground=solid_color(getattr(self.app, "MUSTARD_MAIN", "#D4A017"), "#D4A017"))
        self.tree.tag_configure("days_warn_14", foreground="#F97316")
        self.tree.tag_configure("days_warn_7", foreground=solid_color(getattr(self.app, "COLOR_RED", "#E53935"), "#E53935"))

        # Eventos
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        # Label “vacío”
        self._empty_label = ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _on_tree_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            self._selected_idx = None
            return
        iid = sel[0]
        idx = self._iid_to_index.get(iid)
        self._selected_idx = idx

    # ---------- UI: Filtros ----------
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=1)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=0)
        bar.grid_columnconfigure(5, weight=0)
        bar.grid_columnconfigure(6, weight=0)

        def entry(ph, width=None):
            # customtkinter no acepta width=None (rompe el escalado interno).
            kw = {}
            if width is not None:
                kw["width"] = width
            return ctk.CTkEntry(
                bar, placeholder_text=ph, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                **kw
            )

        ctk.CTkLabel(bar, text="Consecutivo").grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_consecutivo = entry("Ej: 000123", width=140)
        self.f_consecutivo.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="w")

        ctk.CTkLabel(bar, text="Documento").grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_doc = entry("Ej: 1012345678", width=160)
        self.f_doc.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="w")

        ctk.CTkLabel(bar, text="Nombre").grid(row=0, column=2, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_nombre = entry("Nombre o apellido")
        self.f_nombre.grid(row=1, column=2, padx=(8, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Estado").grid(row=0, column=3, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(
            bar,
            values=["Todos", "Pendiente", "Activo", "Inactivo", "Suspendido"],
            width=160
        )
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=3, padx=(8, 8), pady=(0, 10), sticky="w")

        ctk.CTkLabel(bar, text="Categoría").grid(row=0, column=4, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_categoria = ctk.CTkComboBox(
            bar,
            values=["Todas", "A2", "B1", "C1"],
            width=160
        )
        self.f_categoria.set("Todas")
        self.f_categoria.grid(row=1, column=4, padx=(8, 8), pady=(0, 10), sticky="w")

        ctk.CTkLabel(bar, text="Tipo estudiante").grid(row=0, column=5, padx=(8, 8), pady=(10, 4), sticky="w")
        tipo_values = ["Todos", "Matriculado", "Inscrito", "Activo", "Egresado"]
        if getattr(self.app, "is_superadmin", False):
            tipo_values.insert(1, "Prospecto")
        self.f_tipo_estudiante = ctk.CTkComboBox(bar, values=tipo_values, width=170)
        self.f_tipo_estudiante.set("Todos")
        self.f_tipo_estudiante.grid(row=1, column=5, padx=(8, 8), pady=(0, 10), sticky="w")

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=1, column=6, padx=(8, 12), pady=(0, 10), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
                text_color=self.app.COLOR_TEXT, command=cmd
            )

        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=6)
        light_btn("Buscar", self._apply_filters_now).grid(row=0, column=1, padx=6)

        for w in (self.f_consecutivo, self.f_doc, self.f_nombre):
            w.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_categoria.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_tipo_estudiante.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())

        return bar

    def _collect_filters(self):
        return {
            "consecutivo": (self.f_consecutivo.get() or "").strip(),
            "doc": (self.f_doc.get() or "").strip(),
            "nombre": (self.f_nombre.get() or "").strip(),
            "estado": (self.f_estado.get() or "Todos").strip(),
            "categoria": (self.f_categoria.get() or "Todas").strip(),
            "tipo_estudiante": (self.f_tipo_estudiante.get() or "Todos").strip(),
        }

    def _clear_filters(self):
        self.f_consecutivo.delete(0, "end")
        self.f_doc.delete(0, "end")
        self.f_nombre.delete(0, "end")
        self.f_estado.set("Todos")
        self.f_categoria.set("Todas")
        self.f_tipo_estudiante.set("Todos")
        self._apply_filters_now()

    def _allowed_admin_sede(self) -> str:
        raw = getattr(self.app, "current_admin_sede", None)
        return _normalize_sede_label(raw) or str(raw or "").strip()

    def _debounced_apply_filters(self):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._apply_filters_now)

    def _apply_filters_now(self):
        src = getattr(self, "_all_data", []) or []
        self._data = self._apply_filters(src, self._collect_filters())
        self._refresh_summary()
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
        if not data_list:
            return []
        allowed_sede = "" if getattr(self.app, "is_superadmin", False) else self._allowed_admin_sede()
        c_sub = f["consecutivo"].lower()
        d_sub = f["doc"].lower()
        n_sub = f["nombre"].lower()
        estado = f["estado"]
        cat = f["categoria"].upper()
        tipo_sel_raw = (f.get("tipo_estudiante") or "Todos").strip().lower()
        tipo_sel = _normalize_tipo_estudiante(tipo_sel_raw)

        out = []
        for stu in data_list:
            consec = _extract_consecutivo(stu).lower()
            doc = str(stu.get("numeroDocumento", "") or "").lower()
            nombre = (stu.get("nombre", "") or "").strip()
            apellido = (stu.get("apellido", "") or "").strip()
            full = f"{nombre} {apellido}".strip().lower()
            est = (stu.get("estado", "") or "").strip()
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
            sede_label = _normalize_sede_label(_extract_sede(stu)) or _extract_sede(stu)
            tipo_est = _normalize_tipo_estudiante(stu.get("tipoEstudiante"))

            if not getattr(self.app, "is_superadmin", False) and tipo_est == "prospecto":
                continue
            if c_sub and c_sub not in consec:
                continue
            if d_sub and d_sub not in doc:
                continue
            if n_sub and n_sub not in full:
                continue
            if allowed_sede and sede_label != allowed_sede:
                continue
            if estado != "Todos" and est != estado:
                continue
            if cat != "TODAS" and categoria_up != cat:
                continue
            if tipo_sel_raw not in ("", "todos") and tipo_est != tipo_sel:
                continue
            out.append(stu)
        return out

    def _refresh_category_options(self):
        base = {"A2", "B1", "C1"}
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
    def _student_row_values(self, stu):
        full_name = "{} {}".format(stu.get("nombre", ""), stu.get("apellido", "")).strip()
        consecutivo = _extract_consecutivo(stu)
        consecutivo_disp = consecutivo if consecutivo else "—"
        tipo_estudiante = _normalize_tipo_estudiante(stu.get("tipoEstudiante"))
        tipo_estudiante_disp = tipo_estudiante.capitalize() if tipo_estudiante else "—"
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
        dias_restantes_txt, _days_color = self._remaining_days_display(stu)
        ingreso_dt = self._parse_student_date(
            stu.get("fechaCreacion") or stu.get("fechaIngreso") or stu.get("createdAt")
        )
        ingreso_txt = ingreso_dt.strftime("%Y-%m-%d") if ingreso_dt else "—"

        return (
            stu.get("numeroDocumento", ""),
            consecutivo_disp,
            full_name,
            tipo_estudiante_disp,
            categoria_disp,
            _extract_sede(stu),
            horas_disp,
            tipo_pase_disp or "-",
            dias_restantes_txt,
            ingreso_txt,
            "Aprobado" if teorico_ok else "Pendiente",
            stu.get("estado", ""),
        )

    @staticmethod
    def _parse_student_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if not s:
            return None
        if "T" in s:
            s = s.split("T", 1)[0]
        if " " in s:
            s = s.split(" ", 1)[0]
        s = s[:10]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None

    def _remaining_days_info(self, stu):
        start_date = self._parse_student_date(
            stu.get("fechaCreacion") or stu.get("fechaIngreso") or stu.get("createdAt")
        )
        if not start_date:
            return None, None
        elapsed = (date.today() - start_date).days
        remaining = max(0, 85 - max(0, elapsed))
        if remaining <= 7:
            return remaining, "days_warn_7"
        if remaining <= 14:
            return remaining, "days_warn_14"
        if remaining <= 30:
            return remaining, "days_warn_30"
        return remaining, ""

    def _remaining_days_display(self, stu):
        remaining, tag = self._remaining_days_info(stu)
        if remaining is None:
            return "—", ""
        return str(remaining), tag

    def _set_data(self, rows):
        data = list(rows or [])

        # cancelar inserciones previas
        self._render_seq += 1
        render_seq = self._render_seq

        # limpiar tree
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_index.clear()
        self._selected_idx = None

        if not data:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return

        self._empty_label.place_forget()

        def insert_chunk(start=0):
            if render_seq != self._render_seq:
                return
            end = min(start + self.TREE_INSERT_CHUNK, len(data))
            for idx in range(start, end):
                stu = data[idx]
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                _remaining, tag = self._remaining_days_info(stu)
                stripe = "even" if idx % 2 == 0 else "odd"
                tags = (stripe, tag) if tag else (stripe,)
                self.tree.insert("", "end", iid=iid, values=self._student_row_values(stu), tags=tags)
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    # ---------- acciones UI ----------
    def _nuevo(self):
        self.form_host.grid()
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un estudiante en la tabla primero.")
            return
        self.form_host.grid()
        self.form.show_edit(self._data[self._selected_idx])

    def _eliminar_seleccionado(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un estudiante en la tabla primero.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        self.form.hide()
        self.form_host.grid_remove()

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
                if can_query and (
                    q["consecutivo"]
                    or q["doc"]
                    or q["nombre"]
                    or q["estado"] not in ("", "Todos")
                    or q["categoria"] != "Todas"
                    or q.get("tipo_estudiante") not in ("", "Todos")
                ):
                    params = {}
                    if q["consecutivo"]:
                        params["consecutivo"] = q["consecutivo"]
                    if q["doc"]:
                        params["doc"] = q["doc"]
                    if q["nombre"]:
                        params["nombre"] = q["nombre"]
                    if q["estado"] != "Todos":
                        params["estado"] = q["estado"]
                    if q["categoria"] != "Todas":
                        params["categoria"] = q["categoria"]
                    if q.get("tipo_estudiante") not in ("", "Todos"):
                        params["tipoEstudiante"] = _normalize_tipo_estudiante(q.get("tipo_estudiante"))
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
                    is_superadmin = getattr(self.app, "is_superadmin", False)
                    allowed_sede = "" if is_superadmin else self._allowed_admin_sede()
                    raw_filtered = []
                    for stu in (raw or []):
                        tipo_est = _normalize_tipo_estudiante(stu.get("tipoEstudiante"))
                        # Prospectos solo visibles para superadministrador
                        if not is_superadmin and tipo_est == "prospecto":
                            continue
                        if allowed_sede:
                            sede_label = _normalize_sede_label(_extract_sede(stu)) or _extract_sede(stu)
                            if sede_label != allowed_sede:
                                continue
                        raw_filtered.append(stu)
                    self._all_data = raw_filtered
                    self._refresh_category_options()
                    self._refresh_summary()
                    self._data = self._apply_filters(self._all_data, self._collect_filters())
                    self._queue_render(self._data)
                    if not self._initial_data_reflow_done:
                        self._initial_data_reflow_done = True
                        self.after(90, self._ensure_table_layout)
                        self.after(280, self._ensure_table_layout)

                self.after(0, apply_data)
            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: messagebox.showerror("Estudiantes", f"No fue posible consultar la API:\n{err}", parent=self))
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

            payload = dict(payload)
            allowed_sede = "" if getattr(self.app, "is_superadmin", False) else self._allowed_admin_sede()
            if allowed_sede:
                payload["sede"] = allowed_sede
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

                student_id = self._data[idx].get("id") or self._data[idx].get("idEstudiante")
                if not student_id:
                    self.app._info("No se encontró el ID del estudiante.")
                    return

                merged = dict(self._data[idx])
                merged.update(payload)

                cat = (payload.get("categoria") or merged.get("categoria") or "").strip().upper()
                if not cat:
                    cat = str(
                        merged.get("categoriaLicencia")
                        or merged.get("licenciaCategoria")
                        or merged.get("tipoLicencia")
                        or ""
                    ).strip().upper()
                if cat:
                    merged["categoria"] = cat
                    merged["categoriaLicencia"] = cat
                    merged["licenciaCategoria"] = cat
                    merged["tipoLicencia"] = cat

                body = {k: v for k, v in merged.items() if k not in ("id", "idEstudiante")}
                self.app.api.ensure_not_modified(
                    "estudiantes",
                    student_id,
                    self._data[idx],
                    compare_fields=[
                        "nombre", "apellido", "tipoEstudiante", "tipoDocumento", "numeroDocumento",
                        "consecutivo", "categoria", "sede", "horas", "tipoPase", "aproboExamenTeorico",
                        "telefono", "email", "direccion", "estado", "visible", "usuario",
                    ],
                    label="estudiante",
                )
                self.app.api.update("estudiantes", student_id, body)
                self.app._info("Estudiante actualizado.")

            self._last_refresh_ts = 0
            self._refrescar()
            self.form.hide()
            self.form_host.grid_remove()

        except Exception as e:
            messagebox.showerror("Estudiantes", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        stu = self._data[idx]
        full_name = "{} {}".format(stu.get("nombre", ""), stu.get("apellido", "")).strip()
        doc = stu.get("numeroDocumento", "")
        if not doc:
            self.app._info("El registro no tiene 'numeroDocumento'.")
            return

        if not messagebox.askyesno("Confirmar", f"¿Eliminar al estudiante:\n{full_name} (Doc: {doc})", parent=self):
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
            messagebox.showerror("Estudiantes", f"No fue posible eliminar:\n{e}", parent=self)
