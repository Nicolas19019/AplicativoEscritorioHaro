import calendar
from datetime import date, datetime
import re
import customtkinter as ctk
from tkinter import messagebox


# ================= INSTRUCTOR FORM =================
class InstructorInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar instructor.
    Claves exactas del backend:
    { "id", "cedula", "nombre", "apellido", "especialidad", "telefono", "email" }
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

        # --- Campos del formulario ---
        ctk.CTkLabel(self, text="Cédula").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.en_ced = BorderedEntry(self, placeholder_text="1012345678")
        self.en_ced.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        # Fila 0b: Especialidad (Selector tipo ComboBox)
        ctk.CTkLabel(self, text="Especialidad").grid(row=0, column=2, padx=12, pady=(12, 6), sticky="w")
        self.cb_esp = ctk.CTkComboBox(
            self,
            values=["Práctica moto", "Práctica carro", "Teoría"],
            width=200,
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.cb_esp.set("Práctica carro")  # valor por defecto
        self.cb_esp.grid(row=0, column=3, padx=12, pady=(12, 6), sticky="ew")


        ctk.CTkLabel(self, text="Nombre").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.en_nom = BorderedEntry(self, placeholder_text="Nombre")
        self.en_nom.grid(row=1, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Apellido").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        self.en_ape = BorderedEntry(self, placeholder_text="Apellido")
        self.en_ape.grid(row=1, column=3, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Teléfono").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_tel = BorderedEntry(self, placeholder_text="3001234567")
        self.en_tel.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self, text="Email").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_mail = BorderedEntry(self, placeholder_text="correo@dominio.com")
        self.en_mail.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # --- Botones ---
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # -------- Métodos públicos --------
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self):
        self.grid_remove()

    # -------- Internos --------
    def _fill(self, d):
        for w in (self.en_ced, self.en_nom, self.en_ape, self.en_tel, self.en_mail):
            w.delete(0, "end")
        self.en_ced.insert(0, d.get("cedula", ""))
        self.en_nom.insert(0, d.get("nombre", ""))
        self.en_ape.insert(0, d.get("apellido", ""))
        self.cb_esp.set(d.get("especialidad", "Práctica carro"))
        self.en_tel.insert(0, d.get("telefono", ""))
        self.en_mail.insert(0, d.get("email", ""))


    def _collect(self):
        return {
            "cedula": self.en_ced.get().strip(),
            "nombre": self.en_nom.get().strip(),
            "apellido": self.en_ape.get().strip(),
            "especialidad": self.cb_esp.get().strip(),
            "telefono": self.en_tel.get().strip(),
            "email": self.en_mail.get().strip(),
        }

    def _validate(self, d):
        req = ["cedula","nombre","apellido","telefono","email"]
        for k in req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."
        if not d["cedula"].isdigit():
            return False, "La Cédula debe ser numérica."
        if d["telefono"] and not d["telefono"].isdigit():
            return False, "El Teléfono debe ser numérico."
        if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
            return False, "Email no válido."
        return True, ""

    def _save(self):
        d = self._collect()

        # 🔍 Verifica que se esté capturando la cédula
        print("[DEBUG] Colectado:", d)

        ok, msg = self._validate(d)
        if not ok:
            messagebox.showerror("Validación", msg, parent=self)
            return

        # 🔧 Bloqueador absoluto: no permite guardar sin cédula
        cedula = d.get("cedula", "").strip()
        if not cedula:
            messagebox.showerror("Error", "El campo 'Cédula' es obligatorio.", parent=self)
            return

        # Confirmar envío final
        print("[DEBUG] Enviando profesor:", d)

        if self.on_submit:
            self.on_submit(d, mode=self.mode)

        self.hide()



    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.hide()


# ================= VEHÍCULO FORM =================
class VehiculoInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar vehículo.
    Claves exactas del backend:
    { "placa", "marca", "modelo", "anio", "estado" }
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

        ctk.CTkLabel(self, text="Estado").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Activo","Mantenimiento","Baja"], width=180)
        self.cb_estado.set("Activo")
        self.cb_estado.grid(row=2, column=1, padx=12, pady=6, sticky="w")

        # --- Botones ---
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(btns, text=text, height=36, corner_radius=12,
                                 fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                                 text_color="#ffffff", command=cmd)

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # -------- API pública --------
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, data):
        self.mode = "edit"
        self._fill(data or {})
        self.grid()

    def hide(self):
        self.grid_remove()

    # -------- Internos --------
    def _fill(self, d):
        for w in (self.en_placa, self.en_marca, self.en_modelo, self.en_anio):
            w.delete(0, "end")
        self.en_placa.insert(0, d.get("placa", ""))
        self.en_marca.insert(0, d.get("marca", ""))
        self.en_modelo.insert(0, d.get("modelo", ""))
        self.en_anio.insert(0, str(d.get("anio", "") or ""))
        self.cb_estado.set(d.get("estado", "Activo") or "Activo")

    def _collect(self):
        anio_raw = (self.en_anio.get() or "").strip()
        return {
            "placa": (self.en_placa.get() or "").strip(),
            "marca": (self.en_marca.get() or "").strip(),
            "modelo": (self.en_modelo.get() or "").strip(),
            "anio": int(anio_raw) if anio_raw.isdigit() else anio_raw,
            "estado": (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        req = ["placa","marca","modelo","anio","estado"]
        for k in req:
            if d.get(k) in ("", None):
                return False, f"El campo '{k}' es obligatorio."
        if not isinstance(d["anio"], int):
            return False, "El campo 'anio' debe ser un número entero."
        if not (1970 <= d["anio"] <= 2100):
            return False, "El campo 'anio' debe estar entre 1970 y 2100."
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

# =============== Calendario emergente ===============
class MiniCalendarDialog(ctk.CTkFrame):
    """Calendario embebido, reutilizable en cualquier vista."""
    def __init__(self, master, on_pick, start_date=None):
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
        self.lbl_month.configure(text=self.current.strftime("%B %Y").capitalize())

    def _prev_month(self):
        y, m = self.current.year, self.current.month
        self.current = date(y - 1, 12, 1) if m == 1 else date(y, m - 1, 1)
        self._render_days()

    def _next_month(self):
        y, m = self.current.year, self.current.month
        self.current = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
        self._render_days()

    def _go_today(self):
        t = date.today()
        self.current = date(t.year, t.month, 1)
        self._render_days()

    # =======================
    #   Renderizado
    # =======================
    def _render_days(self):
        for w in self.body.winfo_children(): 
            w.destroy()

        self._set_month_label()
        week_names = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
        for i, n in enumerate(week_names):
            ctk.CTkLabel(self.body, text=n, text_color=self.COLOR_MUTED)\
                .grid(row=0, column=i, padx=3, pady=(0, 6), sticky="ew")

        cal = calendar.Calendar(firstweekday=0)
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
class ClaseInlineForm(ctk.CTkFrame):
    """
    Formulario en línea para crear/editar clases.
    { id_estudiante, id_profesor, placa_vehiculo, fecha, horaInicio, horaFin, estado }
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

        # catálogos
        self._est_opts = []   # [(id, "Nombre Apellido")]
        self._prof_opts = []  # [(id, "Nombre Apellido")]
        self._veh_opts  = []  # [(placa, placa)]

        self.grid_columnconfigure((0,1,2,3), weight=1)

        def L(t): return ctk.CTkLabel(self, text=t, text_color=self.app.COLOR_TEXT)
        def E(ph=""):
            return ctk.CTkEntry(
                self, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                placeholder_text=ph
            )

        # Fila 0: Estudiante / Instructor
        L("Estudiante").grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")
        self.cb_est = ctk.CTkComboBox(self, values=[], width=280)
        self.cb_est.grid(row=0, column=1, padx=12, pady=(12,6), sticky="ew")

        L("Instructor").grid(row=0, column=2, padx=12, pady=(12,6), sticky="w")
        self.cb_prof = ctk.CTkComboBox(self, values=[], width=280)
        self.cb_prof.grid(row=0, column=3, padx=12, pady=(12,6), sticky="ew")

        # Fila 1: Vehículo / Fecha (con botón calendario)
        L("Vehículo (placa)").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.cb_veh = ctk.CTkComboBox(self, values=[], width=180)
        self.cb_veh.grid(row=1, column=1, padx=12, pady=6, sticky="w")

        L("Fecha (YYYY-MM-DD)").grid(row=1, column=2, padx=12, pady=6, sticky="w")
        fecha_wrap = ctk.CTkFrame(self, fg_color="transparent")
        fecha_wrap.grid(row=1, column=3, padx=12, pady=6, sticky="ew")
        fecha_wrap.grid_columnconfigure(0, weight=1)

        self.en_fecha = E("2025-10-18")
        self.en_fecha.grid(row=0, column=0, padx=(0,6), sticky="ew")

        ctk.CTkButton(
            fecha_wrap, text="📅", width=42, height=36, corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT, command=self._open_calendar
        ).grid(row=0, column=1, sticky="e")

        # Fila 2: Horas
        L("Hora inicio (HH:mm)").grid(row=2, column=0, padx=12, pady=6, sticky="w")
        self.en_hi = E("08:00")
        self.en_hi.grid(row=2, column=1, padx=12, pady=6, sticky="ew")

        L("Hora fin (HH:mm)").grid(row=2, column=2, padx=12, pady=6, sticky="w")
        self.en_hf = E("10:00")
        self.en_hf.grid(row=2, column=3, padx=12, pady=6, sticky="ew")

        # Fila 3: Estado
        L("Estado").grid(row=3, column=0, padx=12, pady=6, sticky="w")
        self.cb_estado = ctk.CTkComboBox(self, values=["Programada","Dictada","Cancelada"], width=180)
        self.cb_estado.set("Programada")
        self.cb_estado.grid(row=3, column=1, padx=12, pady=6, sticky="w")

        # Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=4, padx=12, pady=(8,12), sticky="e")

        def red_btn(text, cmd):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=12,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_btn("Cancelar", self._cancel).grid(row=0, column=0, padx=6)
        red_btn("Guardar", self._save).grid(row=0, column=1, padx=6)

        self.mode = "create"

    # ---------- Calendario ----------
    def _open_calendar(self):
        initial = (self.en_fecha.get() or "").strip() or None
        MiniCalendarDialog(self, on_pick=self._set_fecha_from_calendar, start_date=initial)

    def _set_fecha_from_calendar(self, yyyymmdd: str):
        try:
            self.en_fecha.delete(0, "end")
            self.en_fecha.insert(0, yyyymmdd)
        except Exception:
            pass

    # ---------- API pública ----------
    def set_options(self, estudiantes, profesores, vehiculos):
        self._est_opts = []
        for e in (estudiantes or []):
            _id = e.get("id") or e.get("idEstudiante")
            if _id is not None:
                self._est_opts.append((str(_id), f"{e.get('nombre','')} {e.get('apellido','')}".strip()))
        self._prof_opts = []
        for p in (profesores or []):
            _id = p.get("id") or p.get("idProfesor")
            if _id is not None:
                self._prof_opts.append((str(_id), f"{p.get('nombre','')} {p.get('apellido','')}".strip()))
        self._veh_opts = []
        for v in (vehiculos or []):
            placa = v.get("placa")
            if placa:
                self._veh_opts.append((placa, placa))

        self.cb_est.configure(values=[txt for _, txt in self._est_opts])
        self.cb_prof.configure(values=[txt for _, txt in self._prof_opts])
        self.cb_veh.configure(values=[txt for _, txt in self._veh_opts])

    # ---------- Mostrar/Ocultar ----------
    def show_create(self):
        self.mode = "create"
        self._fill({})
        self.grid()

    def show_edit(self, d):
        self.mode = "edit"
        self._fill(d or {})
        self.grid()

    def hide(self): self.grid_remove()

    # ---------- Internos ----------
    def _fill(self, d):
        for w in (self.en_fecha, self.en_hi, self.en_hf):
            w.delete(0, "end")
        self.cb_estado.set(d.get("estado","Programada") or "Programada")

        def _sel(cb, opts, key, is_id=True):
            val = d.get(key)
            if val is None: 
                return
            wanted = str(val) if is_id else val
            texts = [txt for v, txt in opts if str(v) == wanted]
            if texts: cb.set(texts[0])

        _sel(self.cb_est,  self._est_opts, "id_estudiante", True)
        _sel(self.cb_prof, self._prof_opts, "id_profesor",   True)
        _sel(self.cb_veh,  self._veh_opts,  "placa_vehiculo", False)

        self.en_fecha.insert(0, d.get("fecha","") or "")
        self.en_hi.insert(0,   d.get("horaInicio","") or "")
        self.en_hf.insert(0,   d.get("horaFin","") or "")

    def _collect(self):
        def _val(cb, opts):
            txt = cb.get()
            for v, t in opts:
                if t == txt:
                    return v
            return None

        return {
            "id_estudiante":  int(_val(self.cb_est,  self._est_opts)) if _val(self.cb_est,  self._est_opts) else None,
            "id_profesor":    int(_val(self.cb_prof, self._prof_opts)) if _val(self.cb_prof, self._prof_opts) else None,
            "placa_vehiculo": _val(self.cb_veh, self._veh_opts),
            "fecha":          (self.en_fecha.get() or "").strip(),
            "horaInicio":     (self.en_hi.get() or "").strip(),
            "horaFin":        (self.en_hf.get() or "").strip(),
            "estado":         (self.cb_estado.get() or "").strip(),
        }

    def _validate(self, d):
        req = ["id_estudiante","id_profesor","placa_vehiculo","fecha","horaInicio","horaFin","estado"]
        for k in req:
            if not d.get(k):
                return False, f"El campo '{k}' es obligatorio."

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["fecha"]):
            return False, "La fecha debe tener formato YYYY-MM-DD."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaInicio"]):
            return False, "Hora inicio debe ser HH:mm."
        if not re.fullmatch(r"\d{2}:\d{2}", d["horaFin"]):
            return False, "Hora fin debe ser HH:mm."

        try:
            h1 = int(d["horaInicio"][:2]) * 60 + int(d["horaInicio"][3:])
            h2 = int(d["horaFin"][:2]) * 60 + int(d["horaFin"][3:])
            if h2 <= h1:
                return False, "La hora de fin debe ser mayor que la de inicio."
        except:
            return False, "Horas inválidas."

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