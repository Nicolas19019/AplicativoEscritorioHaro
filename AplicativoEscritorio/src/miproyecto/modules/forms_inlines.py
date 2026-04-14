"""
Componentes UI reutilizables (formularios inline y mini-diálogos).

Centraliza widgets usados por múltiples módulos (estudiantes, instructores, vehículos, clases).
"""

import calendar as _cal
from datetime import date, datetime
import re
import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
import datetime as _dt

SEDES_DISPONIBLES = ["1 de Mayo", "El Eden"]


def _normalize_sede_label(value):
    """Normaliza valores de sede a etiquetas estandar (`1 de Mayo` / `El Eden`)."""
    txt = str(value or "").strip().lower()
    if not txt:
        return ""

    txt_fold = (
        txt.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    txt_fold = " ".join(txt_fold.split())
    compact = txt_fold.replace(" ", "")

    if compact in {"1demayo", "1mayo", "1rodemayo", "1erdemayo"} or "mayo" in txt_fold or "kennedy" in txt_fold:
        return "1 de Mayo"
    if "eden" in txt_fold:
        return "El Eden"
    if txt in {"1 de mayo", "1demayo"}:
        return "1 de Mayo"
    if txt in {"el eden", "el edén", "eden", "edén"}:
        return "El Eden"
    return ""


def _upper_text(value):
    """Convierte un valor a texto en mayusculas, limpiando espacios."""
    return str(value or "").strip().upper()


def _assigned_admin_sede(app) -> str:
    """Obtiene la sede asignada al administrador actual (si aplica)."""
    raw = getattr(app, "current_admin_sede", None)
    return _normalize_sede_label(raw) or str(raw or "").strip()


def _apply_admin_sede_to_combobox(app, combo):
    """Restringe el combobox de sede segun el rol/sede asignada del administrador."""
    assigned_sede = _assigned_admin_sede(app)
    if getattr(app, "is_superadmin", False) or not assigned_sede:
        combo.configure(values=SEDES_DISPONIBLES, state="normal")
        current = (combo.get() or "").strip()
        if current not in SEDES_DISPONIBLES:
            combo.set(SEDES_DISPONIBLES[0])
        return
    combo.configure(values=[assigned_sede], state="disabled")
    combo.set(assigned_sede)


# ================= INSTRUCTOR FORM =================
class InstructorInlineForm(ctk.CTkFrame):
    """
    Formulario en linea para crear/editar instructor.
    Claves exactas del backend:
    {
      "cedula", "nombre", "apellido", "email", "especialidad", "categoria",
      "telefono", "usuario", "sede", "visible", "contrasena"
    }
    """
    def __init__(self, master, app, on_submit, on_cancel):
        """Crea el formulario inline para registrar/editar instructores."""
        super().__init__(
            master,
            fg_color=app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=app.COLOR_DIVIDER,
        )
        self.app = app
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        def BorderedEntry(parent, **kw):
            return ctk.CTkEntry(
                parent,
                height=36,
                corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                text_color=self.app.COLOR_TEXT,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
                **kw,
            )
        ctk.CTkLabel(self, text="Cedula").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        self.en_ced = BorderedEntry(self, placeholder_text="1012345678")
        self.en_ced.grid(row=0, column=1, padx=12, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(self, text="Especialidad").grid(row=0, column=2, padx=12, pady=(12, 6), sticky="w")
        self.cb_esp = ctk.CTkComboBox(
            self,
            values=["carro", "moto"],
            width=200,
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.cb_esp.set("carro")
        self.cb_esp.grid(row=0, column=3, padx=12, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nom = BorderedEntry(self, placeholder_text="Andres")
        self.en_nom.grid(row=1, column=1, padx=12, pady=6, sticky="ew")
        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_ape = BorderedEntry(self, placeholder_text="Agudelo")
        self.en_ape.grid(row=1, column=3, padx=12, pady=6, sticky="ew")
        ctk.CTkLabel(self, text="Telefono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")
        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_email = BorderedEntry(self, placeholder_text="email@dominio.com")
        self.en_email.grid(row=2, column=3, padx=12, pady=6, sticky="ew")
        ctk.CTkLabel(self, text="Usuario").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.en_usuario = BorderedEntry(self, placeholder_text="usuario")
        self.en_usuario.grid(row=3, column=1, padx=12, pady=6, sticky="ew")
        ctk.CTkLabel(self, text="Categoria").grid(row=3, column=2, padx=12, pady=6, sticky="w")
        self.cb_categoria = ctk.CTkComboBox(self, values=["carro", "moto"], width=180)
        self.cb_categoria.set("carro")
        self.cb_categoria.grid(row=3, column=3, padx=12, pady=6, sticky="w")
        ctk.CTkLabel(self, text="Visible").grid(row=4, column=0, padx=12, pady=6, sticky="w")
        self.cb_visible = ctk.CTkComboBox(self, values=["true", "false"], width=120)
        self.cb_visible.set("true")
        self.cb_visible.grid(row=4, column=1, padx=12, pady=6, sticky="w")
        ctk.CTkLabel(self, text="Sede").grid(row=4, column=2, padx=12, pady=6, sticky="w")
        self.cb_sede = ctk.CTkComboBox(self, values=SEDES_DISPONIBLES, width=180)
        self.cb_sede.set(SEDES_DISPONIBLES[0])
        self.cb_sede.grid(row=4, column=3, padx=12, pady=6, sticky="w")
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=4, padx=12, pady=(8, 12), sticky="e")
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
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
    def _reset_fields(self):
        """Limpia los campos y restablece valores por defecto del formulario."""
        try:
            for w in (
                self.en_ced,
                self.en_nom,
                self.en_ape,
                self.en_tel,
                self.en_email,
                self.en_usuario,
            ):
                w.delete(0, "end")
            self.cb_esp.set("carro")
            self.cb_categoria.set("carro")
            self.cb_visible.set("true")
            _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        except Exception as e:
            print(f"[WARN] Error al reiniciar campos en InstructorInlineForm: {e}")
    def _force_entry_placeholders(self):
        """Fuerza el pintado de placeholders en CTkEntry (workaround visual)."""
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
        """Muestra el formulario en modo creacion."""
        self.mode = "create"
        self._reset_fields()
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        self.grid()
        self.after(100, self._force_entry_placeholders)
    def show_edit(self, data):
        """Muestra el formulario en modo edicion y carga los datos existentes."""
        self.mode = "edit"
        self._fill(data or {})
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        self.grid()
        self.after(100, self._force_entry_placeholders)
    def hide(self):
        """Oculta el formulario (sin destruirlo)."""
        self.grid_remove()
    def _fill(self, d):
        """Rellena campos del formulario con un dict del backend."""
        for w in (
            self.en_ced,
            self.en_nom,
            self.en_ape,
            self.en_tel,
            self.en_email,
            self.en_usuario,
        ):
            w.delete(0, "end")
        self.en_ced.insert(0, d.get("cedula", ""))
        self.en_nom.insert(0, d.get("nombre", ""))
        self.en_ape.insert(0, d.get("apellido", ""))
        esp_raw = str(d.get("especialidad", "") or "").strip().lower()
        esp_val = "moto" if "moto" in esp_raw else "carro"
        self.cb_esp.set(esp_val)
        self.en_tel.insert(0, d.get("telefono", ""))
        email_val = d.get("email", "")
        self.en_email.insert(0, email_val)
        self.en_usuario.insert(0, d.get("usuario", ""))
        sede_val = d.get("sede", "") or ""
        if isinstance(sede_val, dict):
            sede_val = sede_val.get("nombre") or sede_val.get("name") or sede_val.get("descripcion") or ""
        self.cb_sede.set(_normalize_sede_label(sede_val) or SEDES_DISPONIBLES[0])
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        categoria_raw = (
            d.get("categoria")
            or d.get("categoriaLicencia")
            or d.get("licenciaCategoria")
            or esp_val
        )
        categoria_str = str(categoria_raw).strip().lower()
        self.cb_categoria.set("moto" if "moto" in categoria_str else "carro")
        visible_val = d.get("visible", True)
        visible_str = str(visible_val).strip().lower()
        self.cb_visible.set("true" if visible_str in {"true", "1", "si", "yes"} else "false")
    def _collect(self):
        """Recolecta valores del formulario y arma el payload del backend."""
        email = self.en_email.get().strip()
        especialidad = (self.cb_esp.get() or "").strip().lower()
        categoria = (self.cb_categoria.get() or "").strip().lower()
        especialidad = "moto" if "moto" in especialidad else "carro"
        categoria = "moto" if "moto" in categoria else "carro"
        visible_raw = (self.cb_visible.get() or "true").strip().lower()
        return {
            "cedula": self.en_ced.get().strip(),
            "nombre": _upper_text(self.en_nom.get()),
            "apellido": _upper_text(self.en_ape.get()),
            "email": email,
            "especialidad": especialidad,
            "categoria": categoria,
            "telefono": self.en_tel.get().strip(),
            "usuario": self.en_usuario.get().strip(),
            "sede": (self.cb_sede.get() or "").strip(),
            "visible": visible_raw in {"true", "1", "si", "yes"},
            "contrasena": None,
        }
    def _validate(self, d):
        """Valida el payload recolectado y retorna (ok, mensaje)."""
        req = [
            "cedula", "nombre", "apellido", "email", "especialidad",
            "categoria", "telefono", "usuario"
        ]
        if getattr(self, "mode", "create") == "create":
            req.append("sede")
        for k in req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."
        if d["especialidad"] not in {"carro", "moto"}:
            return False, "La especialidad solo permite: carro o moto."
        if d["categoria"] not in {"carro", "moto"}:
            return False, "La categoria solo permite: carro o moto."
        if not d["cedula"].isdigit():
            return False, "La cedula debe ser numerica."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El telefono debe ser numerico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no valido."
        return True, ""
    def _save(self):
        """Valida y envia el payload via `on_submit`."""
        d = self._collect()
        print("[DEBUG] Colectado:", d)
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validacion", msg, parent=self)
            return
        cedula = d.get("cedula", "").strip()
        if not cedula:
            messagebox.showerror("Error", "El campo 'Cedula' es obligatorio.", parent=self)
            return
        print("[DEBUG] Enviando profesor:", d)
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()
    def _cancel(self):
        """Cancela el formulario y ejecuta `on_cancel` si existe."""
        if self.on_cancel:
            self.on_cancel()
        self.hide()

# ================= VEHÍCULO FORM =================
class VehiculoInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar vehículo.
    Claves exactas del backend:
    { "placa", "marca", "modelo", "anio", "sede", "estado" }
    """
    def __init__(self, master, app, on_submit, on_cancel):
        """Crea el formulario inline para registrar/editar vehiculos."""
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

        # --- Campos del formulario ---
        ctk.CTkLabel(self, text="Placa").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.en_placa = BorderedEntry(self, placeholder_text="ABC123")
        self.en_placa.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        ctk.CTkLabel(self, text="Marca").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.en_marca = BorderedEntry(self, placeholder_text="Chevrolet / Renault / etc.")
        self.en_marca.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        ctk.CTkLabel(self, text="Modelo").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_modelo = BorderedEntry(self, placeholder_text="Spark / Logan / etc.")
        self.en_modelo.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Año").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_anio = BorderedEntry(self, placeholder_text="2021")
        self.en_anio.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Sede").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.cb_sede = ctk.CTkComboBox(self, values=SEDES_DISPONIBLES, width=180)
        self.cb_sede.set(SEDES_DISPONIBLES[0])
        self.cb_sede.grid(row=2, column=1, padx=12, pady=6, sticky="w")

        ctk.CTkLabel(self, text="Estado").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Mantenimiento","Baja"], width=180)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=2, column=3, padx=12, pady=6, sticky="w")

        # --- Botones ---
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

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
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)

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
        """Muestra el formulario en modo creacion."""
        self.mode = "create"
        self._fill({})
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def show_edit(self, data):
        """Muestra el formulario en modo edicion y carga los datos existentes."""
        self.mode = "edit"
        self._fill(data or {})
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        self.grid()
        self.after(100, self._force_entry_placeholders)

    def hide(self):
        """Oculta el formulario (sin destruirlo)."""
        self.grid_remove()

    # -------- Internos --------
    def _fill(self, d):
        """Rellena campos del formulario con un dict del backend."""
        for w in (self.en_placa, self.en_marca, self.en_modelo, self.en_anio):
            w.delete(0, "end")
        self.en_placa.insert(0, d.get("placa", ""))
        self.en_marca.insert(0, d.get("marca", ""))
        self.en_modelo.insert(0, d.get("modelo", ""))
        self.en_anio.insert(0, str(d.get("anio", "") or ""))
        self.cb_sede.set(_normalize_sede_label(d.get("sede", "")) or SEDES_DISPONIBLES[0])
        _apply_admin_sede_to_combobox(self.app, self.cb_sede)
        self.cb_estado.set(d.get("estado", "Activo") or "Activo")

    def _collect(self):
        """Recolecta valores del formulario y arma el payload del backend."""
        anio_raw = (self.en_anio.get() or "").strip()
        return {
            "placa": _upper_text(self.en_placa.get()),
            "marca": _upper_text(self.en_marca.get()),
            "modelo": _upper_text(self.en_modelo.get()),
            "anio": int(anio_raw) if anio_raw.isdigit() else anio_raw,
            "sede": (self.cb_sede.get() or "").strip(),
            "estado": (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        """Valida el payload recolectado y retorna (ok, mensaje)."""
        req = ["placa","marca","modelo","anio","sede","estado"]
        for k in req:
            if d.get(k) in ("", None):
                return False, f"El campo '{k}' es obligatorio."
        if not isinstance(d["anio"], int):
            return False, "El campo 'anio' debe ser un número entero."
        if not (1970 <= d["anio"] <= 2100):
            return False, "El campo 'anio' debe estar entre 1970 y 2100."
        return True, ""

    def _save(self):
        """Valida y envia el payload via `on_submit`."""
        d = self._collect()
        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(d, mode=self.mode)
        self.hide()

    def _cancel(self):
        """Cancela el formulario y ejecuta `on_cancel` si existe."""
        if self.on_cancel:
            self.on_cancel()
        self.hide()

# =============== Calendario emergente ===============
class MiniCalendarDialog(ctk.CTkFrame):
    """Calendario embebido, reutilizable en cualquier vista."""
    def __init__(self, master, on_pick, start_date=None):
        """Inicializa el calendario y configura el callback `on_pick` (YYYY-MM-DD)."""
        super().__init__(master)

        # Detectar app o definir colores por defecto
        self.app = getattr(master, "app", getattr(master.winfo_toplevel(), "app", None))
        def C(name, default): 
            return getattr(self.app, name, default) if self.app else default

        self.COLOR_PANEL    = C("COLOR_PANEL", "#1a1a1a")
        self.COLOR_INPUT_BG = C("COLOR_INPUT_BG", "#2a2a2a")
        self.COLOR_TEXT     = C("COLOR_TEXT", "#ffffff")
        self.COLOR_MUTED    = C("COLOR_MUTED", "#aaaaaa")
        self.COLOR_DIVIDER  = C("COLOR_DIVIDER", "#333333")
        self.COLOR_RED      = C("COLOR_RED", "#ff4c4c")
        self.COLOR_YELLOW   = C("COLOR_YELLOW", "#ffd54f")

        self.configure(fg_color=self.COLOR_PANEL)

        # Callback
        self.on_pick = on_pick

        # Fecha inicial
        if isinstance(start_date, (date, datetime)):
            self.current = start_date if isinstance(start_date, date) else start_date.date()
        else:
            try:
                self.current = datetime.strptime((start_date or ""), "%Y-%m-%d").date()
            except Exception:
                self.current = date.today()

        self.current = date(self.current.year, self.current.month, 1)

        # === Encabezado ===
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(10, 4))

        self.lbl_month = ctk.CTkLabel(
            head,
            text=self.current.strftime("%B %Y").capitalize(),
            text_color=self.COLOR_TEXT,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.lbl_month.pack(side="top", pady=(0, 6))

        nav = ctk.CTkFrame(head, fg_color="transparent")
        nav.pack(fill="x", pady=(2, 4))

        def btn(text, cmd, fg=None):
            return ctk.CTkButton(
                nav, text=text, width=38, height=30, corner_radius=8,
                fg_color=fg or self.COLOR_INPUT_BG,
                hover_color=self.COLOR_DIVIDER,
                text_color=self.COLOR_TEXT,
                command=cmd
            )

        btn("◀", self._prev_month).pack(side="left", padx=2)
        ctk.CTkButton(
            nav, text="Hoy", height=30, corner_radius=8,
            fg_color=self.COLOR_RED, hover_color=self.COLOR_YELLOW,
            text_color="#ffffff", command=self._go_today
        ).pack(side="left", padx=6)
        btn("▶", self._next_month).pack(side="left", padx=2)

        # === Cuerpo (días) ===
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=10, pady=10)
        self._render_days()

    # =======================
    #   Navegación de meses
    # =======================
    def _set_month_label(self):
        """Actualiza el label del mes actual."""
        self.lbl_month.configure(text=self.current.strftime("%B %Y").capitalize())

    def _prev_month(self):
        """Navega al mes anterior y re-renderiza el calendario."""
        y, m = self.current.year, self.current.month
        self.current = date(y - 1, 12, 1) if m == 1 else date(y, m - 1, 1)
        self._render_days()

    def _next_month(self):
        """Navega al siguiente mes y re-renderiza el calendario."""
        y, m = self.current.year, self.current.month
        self.current = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
        self._render_days()

    def _go_today(self):
        """Posiciona el calendario en el mes actual (hoy)."""
        t = date.today()
        self.current = date(t.year, t.month, 1)
        self._render_days()

    # =======================
    #   Renderizado
    # =======================
    def _render_days(self):
        """Renderiza la grilla de dias del mes actual y enlaza el callback por dia."""
        for w in self.body.winfo_children(): 
            w.destroy()

        self._set_month_label()
        week_names = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
        for i, n in enumerate(week_names):
            ctk.CTkLabel(self.body, text=n, text_color=self.COLOR_MUTED)\
                .grid(row=0, column=i, padx=3, pady=(0, 6), sticky="ew")

        cal = _cal.Calendar(firstweekday=0)
        y, m = self.current.year, self.current.month
        row = 1
        today = date.today()

        for week in cal.monthdatescalendar(y, m):
            for col, d in enumerate(week):
                is_other = d.month != m
                txt_color = self.COLOR_MUTED if is_other else self.COLOR_TEXT
                bg = self.COLOR_INPUT_BG if d != today else self.COLOR_DIVIDER

                def _cmd(_d=d):
                    if callable(self.on_pick):
                        self.on_pick(_d.strftime("%Y-%m-%d"))

                ctk.CTkButton(
                    self.body, text=str(d.day), width=36, height=32, corner_radius=8,
                    fg_color=bg, hover_color=self.COLOR_DIVIDER,
                    text_color=txt_color, command=_cmd
                ).grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            row += 1

        for c in range(7):
            self.body.grid_columnconfigure(c, weight=1)


# =============== Formulario de Clases (con calendario) ===============
# =============== Formulario de Clases (con calendario embebido) ===============

class ClaseInlineForm(ctk.CTkFrame):
    """
    Formulario para crear/editar clases.
    """
    def __init__(self, master, app, on_submit, on_cancel):
        """Crea el formulario inline para programar/editar clases practicas."""
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

        self.mode = "create"
        self._est_opts = []
        self._prof_opts = []
        self._veh_opts = []

        # --- Layout base ---
        self.grid_columnconfigure((0,1,2,3), weight=1)

        def L(t): 
            return ctk.CTkLabel(self, text=t, text_color=self.app.COLOR_TEXT)

        def E(ph=""):
            return ctk.CTkEntry(
                self, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                placeholder_text=ph
            )

        # === FILA 0 ===
        L("Estudiante").grid(row=0, column=0, padx=12, pady=(10,6), sticky="w")
        self.cb_est = ctk.CTkComboBox(self, values=[], width=280, state="readonly")
        self.cb_est.set("Seleccione un estudiante")
        self.cb_est.grid(row=0, column=1, padx=12, pady=(10,6), sticky="ew")

        L("Instructor").grid(row=0, column=2, padx=12, pady=(10,6), sticky="w")
        self.cb_prof = ctk.CTkComboBox(self, values=[], width=280, state="readonly")
        self.cb_prof.set("Seleccione un instructor")
        self.cb_prof.grid(row=0, column=3, padx=12, pady=(10,6), sticky="ew")

        # === FILA 1 ===
        L("Vehículo (placa)").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.cb_veh = ctk.CTkComboBox(self, values=[], width=180, state="readonly")
        self.cb_veh.set("Seleccione vehículo")
        self.cb_veh.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        L("Fecha (YYYY-MM-DD)").grid(row=1, column=2, padx=12, pady=6, sticky="w")

        fecha_wrap = ctk.CTkFrame(self, fg_color="transparent")
        fecha_wrap.grid(row=1, column=3, padx=12, pady=6, sticky="ew")
        fecha_wrap.grid_columnconfigure(0, weight=1)

        # Variable que guarda la fecha seleccionada
        self.fecha_var = tk.StringVar(value="Seleccionar fecha")

        # Campo de texto (solo lectura)
        self.lb_fecha = ctk.CTkLabel(
            fecha_wrap, textvariable=self.fecha_var,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
            corner_radius=10, height=36, anchor="w", padx=12
        )
        self.lb_fecha.grid(row=0, column=0, padx=(0,6), sticky="ew")

        # Botón de calendario
        ctk.CTkButton(
            fecha_wrap, text="📅", width=42, height=36, corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT, command=self._open_calendar
        ).grid(row=0, column=1, sticky="e")

        # === FILA 2 ===
        L("Hora inicio (HH:mm)").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.cb_hi = ctk.CTkComboBox(
            self, values=["06:00","08:00","10:00","12:00","14:00","16:00","18:00"],
            width=180, state="readonly", command=self._auto_set_hf
        )
        self.cb_hi.set("Seleccione hora")
        self.cb_hi.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        L("Hora fin (HH:mm)").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_hf = E("Calculado automáticamente")
        self.en_hf.configure(state="readonly")
        self.en_hf.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # === FILA 3 ===
        L("Estado").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(
            self, values=["Programada","Dictada","Cancelada"], width=180, state="readonly"
        )
        self.cb_estado.set("Programada")
        self.cb_estado.grid(row=3, column=1, padx=12, pady=6, sticky="w")

        # === BOTONES ===
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

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

    def _has_class_on(self, date_obj):
        """
        Devuelve True si existe alguna clase programada en la fecha dada.
        Usa la API del app si está disponible, o los datos ya cargados en memoria.
        """
        try:
            # Verificar si la app y los datos existen
            if hasattr(self.app, "_data_clases"):
                for c in self.app._data_clases:
                    if str(c.get("fecha")) == date_obj.strftime("%Y-%m-%d"):
                        return True

            # Si no hay cache local, intentar con la API (opcional)
            if getattr(self.app, "api", None):
                clases = self.app.api.get_all("clases-practicas") or []
                for c in clases:
                    if str(c.get("fecha")) == date_obj.strftime("%Y-%m-%d"):
                        return True
        except Exception:
            pass

        return False


    # === Calendario ===
    def _open_calendar(self):
        """Abre el calendario en una ventana emergente centrada."""
        import datetime, calendar
        from tkinter import messagebox

        try:
            top = ctk.CTkToplevel(self)
            top.title("Seleccionar fecha")
            top.transient(self.winfo_toplevel())
            top.grab_set()

            # Centrar la ventana
            w, h = 360, 360
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
            x, y = int((sw - w) / 2), int((sh - h) / 2)
            top.geometry(f"{w}x{h}+{x}+{y}")

            # ---- CONFIGURAR FECHA BASE ----
            today = datetime.date.today()
            try:
                selected_date = datetime.datetime.strptime(self.fecha_var.get(), "%Y-%m-%d").date()
                year, month = selected_date.year, selected_date.month
            except Exception:
                year, month = today.year, today.month

            # ---- CONTENEDOR PRINCIPAL ----
            frame = ctk.CTkFrame(top, fg_color=self.app.COLOR_BG)
            frame.pack(fill="both", expand=True, padx=10, pady=10)

            lbl_month = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=18, weight="bold"))
            lbl_month.pack(pady=(5, 10))

            grid = ctk.CTkFrame(frame, fg_color="transparent")
            grid.pack(fill="both", expand=True)

            # ---- FUNCIONES INTERNAS ----
            def draw_calendar():
                """Dibuja los días del mes."""
                for w in grid.winfo_children():
                    w.destroy()

                lbl_month.configure(text=f"{calendar.month_name[month]} {year}")

                days = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
                for i, d in enumerate(days):
                    ctk.CTkLabel(grid, text=d, text_color=self.app.COLOR_MUTED)\
                        .grid(row=0, column=i, padx=4, pady=4)

                cal = calendar.Calendar(firstweekday=0)
                weeks = cal.monthdayscalendar(year, month)

                for r, week in enumerate(weeks, start=1):
                    for c, day in enumerate(week):
                        if day == 0:
                            ctk.CTkLabel(grid, text=" ").grid(row=r, column=c)
                            continue

                        date_obj = datetime.date(year, month, day)
                        # Colores según estado
                        fg = self.app.COLOR_RED if self._has_class_on(date_obj) else self.app.COLOR_PANEL
                        if date_obj == today:
                            fg = self.app.COLOR_YELLOW
                        elif self.fecha_var.get() == date_obj.strftime("%Y-%m-%d"):
                            fg = self.app.COLOR_YELLOW

                        btn = ctk.CTkButton(
                            grid, text=str(day), width=42, height=36, corner_radius=8,
                            fg_color=fg, hover_color=self.app.COLOR_RED,
                            command=lambda d=date_obj: select_date(d)
                        )
                        btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

            def select_date(dia):
                """Selecciona la fecha y cierra la ventana."""
                self.fecha_var.set(dia.strftime("%Y-%m-%d"))
                top.destroy()

            def prev_month():
                nonlocal year, month
                month -= 1
                if month < 1:
                    month, year = 12, year - 1
                draw_calendar()

            def next_month():
                nonlocal year, month
                month += 1
                if month > 12:
                    month, year = 1, year + 1
                draw_calendar()

            # ---- BOTONES DE NAVEGACIÓN ----
            nav = ctk.CTkFrame(frame, fg_color="transparent")
            nav.pack(fill="x", pady=(0, 8))
            ctk.CTkButton(nav, text="◀", width=36, height=28, command=prev_month).pack(side="left", padx=6)
            ctk.CTkButton(nav, text="▶", width=36, height=28, command=next_month).pack(side="right", padx=6)

            draw_calendar()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el calendario:\n{e}", parent=self)



    def _set_fecha_from_calendar(self, yyyymmdd: str):
        """Recibe la fecha del calendario existente."""
        self.fecha_seleccionada = yyyymmdd
        messagebox.showinfo("Fecha seleccionada", f"Has seleccionado: {yyyymmdd}")

    # === Lógica de horas ===
    def _auto_set_hf(self, selected):
        """Calcula automaticamente la hora fin cuando se elige hora inicio."""
        try:
            if not selected or "hora" in selected.lower():
                return
            h, m = map(int, selected.split(":"))
            h2 = (h + 2) % 24
            self.en_hf.configure(state="normal")   # abre para escribir
            self.en_hf.delete(0, "end")
            self.en_hf.insert(0, f"{h2:02d}:{m:02d}")
            self.en_hf.configure(state="readonly") # vuelve a readonly
        except Exception as e:
            print("[WARN] cálculo hora fin:", e)

    # === API pública ===
    def set_options(self, estudiantes, profesores, vehiculos):
        """Configura las opciones de los combobox (estudiantes, instructores, vehiculos)."""
        self._est_opts = [(str(e.get("id")), f"{e.get('nombre','')} {e.get('apellido','')}".strip())
                          for e in (estudiantes or []) if e.get("id")]
        self._prof_opts = [(str(p.get("id")), f"{p.get('nombre','')} {p.get('apellido','')}".strip())
                           for p in (profesores or []) if p.get("id")]
        self._veh_opts = [(v.get("placa"), v.get("placa")) for v in (vehiculos or []) if v.get("placa")]

        self.cb_est.configure(values=[t for _, t in self._est_opts])
        self.cb_prof.configure(values=[t for _, t in self._prof_opts])
        self.cb_veh.configure(values=[t for _, t in self._veh_opts])

    def _save(self):
        """Valida y envia el payload via `on_submit`."""
        data = self._collect()
        ok, msg = self._validate(data)
        if not ok:
            messagebox.showerror("Error", msg, parent=self)
            return
        if self.on_submit:
            self.on_submit(data, self.mode)
        self.hide()

    def _cancel(self):
        """Cancela el formulario y ejecuta `on_cancel` si existe."""
        if self.on_cancel:
            self.on_cancel()
        self.hide()

    def _collect(self):
        """Recolecta valores del formulario y arma el payload del backend."""
        def val(cb, opts):
            txt = cb.get()
            for v, t in opts:
                if t == txt:
                    return v
            return None
        
        return {
            "id_estudiante":  int(val(self.cb_est,  self._est_opts)) if val(self.cb_est,  self._est_opts) else None,
            "id_profesor":    int(val(self.cb_prof, self._prof_opts)) if val(self.cb_prof, self._prof_opts) else None,
            "placa_vehiculo": val(self.cb_veh, self._veh_opts),
            "fecha":          (self.fecha_var.get() or "").strip(),
            "horaInicio":     (self.cb_hi.get() or "").strip(),
            "horaFin":        (self.en_hf.get() or "").strip(),
            "estado":         (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        """Valida el payload recolectado y retorna (ok, mensaje)."""
        for k in ("id_estudiante","id_profesor","placa_vehiculo","fecha","horaInicio","horaFin","estado"):
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."
        
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["fecha"]):
            return False, "La fecha debe tener formato YYYY-MM-DD."
        
        return True, ""

    def show_create(self):
        """Muestra el formulario en modo creacion y reinicia campos."""
        self.mode = "create"
        self._reset_fields()
        self.grid()


    def _reset_fields(self):
        """Limpia campos del formulario y restablece valores por defecto."""
        try:
            self.cb_est.set("Seleccione un estudiante")
            self.cb_prof.set("Seleccione un instructor")
            self.cb_veh.set("Seleccione un vehículo")
            self.cb_hi.set("Seleccione hora")
            self.en_hf.configure(state="normal")
            self.en_hf.delete(0, "end")
            self.en_hf.insert(0, "Calculado automáticamente")
            self.en_hf.configure(state="readonly")   # ← readonly, no disabled
            self.cb_estado.set("Programada")
            self.fecha_var.set("Seleccionar fecha")
        except Exception as e:
            print("[WARN] Error al reiniciar campos:", e)



    def show_edit(self, d):
        """Muestra el formulario en modo edicion y carga los valores del registro."""
        self.mode = "edit"
        try:
            self.cb_est.set(next((t for v,t in self._est_opts if str(v)==str(d.get("id_estudiante"))),"Seleccione un estudiante"))
            self.cb_prof.set(next((t for v,t in self._prof_opts if str(v)==str(d.get("id_profesor"))),"Seleccione un instructor"))
            self.cb_veh.set(d.get("placa_vehiculo","Seleccione vehículo"))
            self.fecha_seleccionada = d.get("fecha","")
            self.cb_hi.set(d.get("horaInicio","Seleccione hora"))
            self._auto_set_hf(self.cb_hi.get())
            self.cb_estado.set(d.get("estado","Programada"))
        except Exception as e:
            print("[WARN] show_edit:", e)
        self.grid()

    def hide(self): 
        """Oculta el formulario (sin destruirlo)."""
        self.grid_remove()
