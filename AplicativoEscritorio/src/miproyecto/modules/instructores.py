import customtkinter as ctk
from tkinter import messagebox
from modules.base import BaseModuleFrame
from modules.forms_inlines import InstructorInlineForm


class InstructoresView(BaseModuleFrame):
    DEBOUNCE_MS = 250

    def __init__(self, master):
        super().__init__(master, "Instructores", "Gestione los profesores registrados en el sistema")

        # ===== Estado para filtros =====
        self._all_data = []      # todo lo que viene de API
        self._data = []          # filtrado para pintar
        self._rows = []
        self._selected_idx = None
        self._debounce_id = None

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0, 1, 2), weight=0)
        tb.grid_columnconfigure(3, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(
                parent, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8, pady=6, sticky="w")

        # ===== Formulario inline =====
        self.form = InstructorInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()

        # ===== Filtros (con búsqueda en vivo) =====
        self.filters = self._make_filters_bar(self)
        self.filters.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Cédula",        120, 0),
            ("Nombre",        260, 1),
            ("Especialidad",  180, 0),
            ("Teléfono",      130, 0),
            ("Email",         240, 0),
            ("Acciones",      120, 0),
        ]

        self._render_table()
        self.after(150, self._refrescar)

    # =====================================================
    #                    FILTROS (PRO)
    # =====================================================
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        # 0 cedula, 1 nombre, 2 apellido, 3 estado, 4 especialidad, 5 botones
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=1)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=0)
        bar.grid_columnconfigure(5, weight=0)

        def entry(ph):
            return ctk.CTkEntry(
                bar, placeholder_text=ph, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER
            )

        # Cédula
        ctk.CTkLabel(bar, text="Cédula").grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_cedula = entry("Ej: 1012345678")
        self.f_cedula.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="ew")

        # Nombre
        ctk.CTkLabel(bar, text="Nombre").grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_nombre = entry("Nombre")
        self.f_nombre.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="ew")

        # Apellido
        ctk.CTkLabel(bar, text="Apellido").grid(row=0, column=2, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_apellido = entry("Apellido")
        self.f_apellido.grid(row=1, column=2, padx=(8, 8), pady=(0, 10), sticky="ew")

        # Estado
        ctk.CTkLabel(bar, text="Estado").grid(row=0, column=3, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(bar, values=["Todos", "Activo", "Inactivo", "Suspendido"], width=160)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=3, padx=(8, 8), pady=(0, 10), sticky="w")

        # Especialidad
        ctk.CTkLabel(bar, text="Especialidad").grid(row=0, column=4, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_especialidad = ctk.CTkComboBox(bar, values=["Todas"], width=170)
        self.f_especialidad.set("Todas")
        self.f_especialidad.grid(row=1, column=4, padx=(8, 8), pady=(0, 10), sticky="w")

        # Botones
        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=1, column=5, padx=(8, 12), pady=(0, 10), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
                text_color=self.app.COLOR_TEXT, command=cmd
            )

        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=6)
        light_btn("Buscar", self._apply_filters_now).grid(row=0, column=1, padx=6)

        # Bindings: Entry -> debounce; Combos -> apply inmediato
        for w in (self.f_cedula, self.f_nombre, self.f_apellido):
            w.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())

        self.f_estado.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_especialidad.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())

        return bar

    def _collect_filters(self):
        return {
            "cedula": (self.f_cedula.get() or "").strip(),
            "nombre": (self.f_nombre.get() or "").strip(),
            "apellido": (self.f_apellido.get() or "").strip(),
            "estado": (self.f_estado.get() or "Todos").strip(),
            "especialidad": (self.f_especialidad.get() or "Todas").strip(),
        }

    def _clear_filters(self):
        self.f_cedula.delete(0, "end")
        self.f_nombre.delete(0, "end")
        self.f_apellido.delete(0, "end")
        self.f_estado.set("Todos")
        self.f_especialidad.set("Todas")
        self._apply_filters_now()

    def _debounced_apply_filters(self):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._apply_filters_now)

    def _apply_filters_now(self):
        src = self._all_data or []
        self._data = self._apply_filters(src, self._collect_filters())
        self._render_table()

    def _apply_filters(self, data_list, f):
        """Filtra por cédula, nombre, apellido, estado y especialidad (case-insensitive)."""
        if not data_list:
            return []

        ced_sub = f["cedula"].lower()
        nom_sub = f["nombre"].lower()
        ape_sub = f["apellido"].lower()
        estado = f["estado"]
        esp = f["especialidad"].strip().lower()

        out = []
        for prof in data_list:
            ced = str(prof.get("cedula", "") or "").lower()
            nom = str(prof.get("nombre", "") or "").strip().lower()
            ape = str(prof.get("apellido", "") or "").strip().lower()
            est = str(prof.get("estado", "") or "").strip()
            especialidad = str(prof.get("especialidad", "") or "").strip().lower()

            if ced_sub and ced_sub not in ced:
                continue
            if nom_sub and nom_sub not in nom:
                continue
            if ape_sub and ape_sub not in ape:
                continue
            if estado != "Todos" and est != estado:
                continue
            if esp != "todas" and especialidad != esp:
                continue

            out.append(prof)
        return out

    def _refresh_especialidad_options(self):
        """Llena el combo de especialidad con lo que venga del backend."""
        esps = set()
        for p in (self._all_data or []):
            e = str(p.get("especialidad", "") or "").strip()
            if e:
                esps.add(e)
        values = ["Todas"] + sorted(esps, key=lambda s: s.lower())
        try:
            self.f_especialidad.configure(values=values)
            if self.f_especialidad.get() not in values:
                self.f_especialidad.set("Todas")
        except Exception:
            pass

    # =====================================================
    #                    TABLA
    # =====================================================
    def _apply_colspecs(self, container):
        for i, (_, minw, weight) in enumerate(self._COLS):
            container.grid_columnconfigure(i, minsize=minw, weight=weight or 1)

    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self._apply_colspecs(header)

        for i, (nombre, _, _) in enumerate(self._COLS):
            ctk.CTkLabel(
                header, text=nombre, text_color=self.app.COLOR_MUTED,
                anchor="w", justify="left"
            ).grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, prof in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            self._apply_colspecs(row)

            full_name = f"{prof.get('nombre','')} {prof.get('apellido','')}".strip()
            values = [
                prof.get("cedula", ""),
                full_name,
                prof.get("especialidad", ""),
                prof.get("telefono", ""),
                prof.get("email", ""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT, anchor="w", justify="left")
                lbl.grid(row=0, column=i, padx=12, pady=10, sticky="ew")
                lbl.bind("<Button-1>", lambda e, idx=r-1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(
                    actions, text=symbol, width=36, height=32, corner_radius=10,
                    fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                    text_color="#ffffff", command=cmd
                )

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

    # =====================================================
    #                    ACCIONES
    # =====================================================
    def _nuevo(self):
        self.form.show_create()

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _cancel_inline(self):
        self.form.hide()

    # =====================================================
    #                    API
    # =====================================================
    def _refrescar(self):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            raw = self.app.api.get_all("profesores") or []
            if isinstance(raw, dict):
                for key in ("content", "items", "profesores", "data", "results"):
                    lst = raw.get(key)
                    if isinstance(lst, list):
                        raw = lst
                        break
                else:
                    raw = []

            self._all_data = raw or []
            self._refresh_especialidad_options()
            self._data = self._apply_filters(self._all_data, self._collect_filters())
            self._render_table()

        except Exception as e:
            messagebox.showerror("Profesores", f"No fue posible consultar la API:\n{e}", parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not self.app.api:
                self.app._info("No hay cliente API activo. Inicia sesión.")
                return

            if mode == "create":
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
                self.app.api.update("profesores", prof_id, payload)
                self.app._info("Profesor actualizado.")

            self._refrescar()

        except Exception as e:
            messagebox.showerror("Profesores", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        prof = self._data[idx]
        name = f"{prof.get('nombre','')} {prof.get('apellido','')}".strip()
        ced = prof.get("cedula", "")

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
