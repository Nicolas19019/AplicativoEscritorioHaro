from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk

from modules.base import BaseModuleFrame
from modules.treeview_theme import configure_treeview_style

SEDES_ADMIN = ["1 de Mayo", "El Eden"]


def _normalize_sede(value) -> str:
    txt = str(value or "").strip().lower()
    if txt in {"1 de mayo", "1demayo"}:
        return "1 de Mayo"
    if txt in {"el eden", "el edén", "eden", "edén"}:
        return "El Eden"
    return str(value or "").strip()


class AdminInlineForm(ctk.CTkFrame):
    def __init__(self, master, app, on_submit, on_cancel):
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
        self.mode = "create"
        self.record = {}

        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def entry(ph="", show=None):
            kwargs = {
                "height": 36,
                "corner_radius": 10,
                "fg_color": self.app.COLOR_INPUT_BG,
                "text_color": self.app.COLOR_TEXT,
                "border_width": 2,
                "border_color": self.app.COLOR_DIVIDER,
                "placeholder_text": ph,
            }
            if show is not None:
                kwargs["show"] = show
            return ctk.CTkEntry(self, **kwargs)

        ctk.CTkLabel(self, text="Nombre").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        self.en_nombre = entry("Nombre completo")
        self.en_nombre.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Usuario").grid(row=0, column=1, padx=12, pady=(12, 4), sticky="w")
        self.en_usuario = entry("usuario")
        self.en_usuario.grid(row=1, column=1, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Correo").grid(row=0, column=2, padx=12, pady=(12, 4), sticky="w")
        self.en_correo = entry("correo@dominio.com")
        self.en_correo.grid(row=1, column=2, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Cédula").grid(row=0, column=3, padx=12, pady=(12, 4), sticky="w")
        self.en_cedula = entry("123456789")
        self.en_cedula.grid(row=1, column=3, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Sede").grid(row=2, column=0, padx=12, pady=(4, 4), sticky="w")
        self.cb_sede = ctk.CTkComboBox(
            self,
            values=SEDES_ADMIN,
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            button_color=self.app.COLOR_RED,
            button_hover_color=self.app.COLOR_YELLOW,
            border_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            dropdown_fg_color=self.app.COLOR_PANEL,
            dropdown_hover_color=self.app.MUSTARD_SOFT_BG,
            dropdown_text_color=self.app.COLOR_TEXT,
        )
        self.cb_sede.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Estado").grid(row=2, column=1, padx=12, pady=(4, 4), sticky="w")
        self.cb_estado = ctk.CTkComboBox(
            self,
            values=["Activo", "Inactivo"],
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            button_color=self.app.COLOR_RED,
            button_hover_color=self.app.COLOR_YELLOW,
            border_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            dropdown_fg_color=self.app.COLOR_PANEL,
            dropdown_hover_color=self.app.MUSTARD_SOFT_BG,
            dropdown_text_color=self.app.COLOR_TEXT,
        )
        self.cb_estado.grid(row=3, column=1, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(self, text="Contraseña").grid(row=2, column=2, padx=12, pady=(4, 4), sticky="w")
        self.en_password = entry("Contraseña inicial o nueva", show="*")
        self.en_password.grid(row=3, column=2, columnspan=2, padx=12, pady=(0, 8), sticky="ew")

        self.lbl_info = ctk.CTkLabel(
            self,
            text="La contraseña es opcional al editar. La sede define qué estudiantes puede gestionar ese administrador.",
            text_color=self.app.COLOR_MUTED,
            justify="left",
            wraplength=700,
        )
        self.lbl_info.grid(row=4, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=4, padx=12, pady=(0, 12), sticky="e")
        ctk.CTkButton(
            btns,
            text="Cancelar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self._cancel,
        ).grid(row=0, column=0, padx=6)
        ctk.CTkButton(
            btns,
            text="Guardar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_RED,
            hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff",
            command=self._save,
        ).grid(row=0, column=1, padx=6)

    def show_create(self):
        self.mode = "create"
        self.record = {}
        self._fill({})
        self.grid()

    def show_edit(self, record):
        self.mode = "edit"
        self.record = dict(record or {})
        self._fill(self.record)
        self.grid()

    def hide(self):
        self.grid_remove()

    def _fill(self, record):
        for entry in (self.en_nombre, self.en_usuario, self.en_correo, self.en_cedula, self.en_password):
            entry.delete(0, "end")
        self.en_nombre.insert(0, record.get("nombre") or "")
        self.en_usuario.insert(0, record.get("usuario") or "")
        self.en_correo.insert(0, record.get("correo") or "")
        self.en_cedula.insert(0, record.get("cedula") or "")
        self.cb_sede.set(_normalize_sede(record.get("sede")) or SEDES_ADMIN[0])
        self.cb_estado.set("Activo" if bool(record.get("activo", True)) else "Inactivo")

    def _collect(self):
        payload = {
            "nombre": str(self.en_nombre.get() or "").strip(),
            "usuario": str(self.en_usuario.get() or "").strip(),
            "correo": str(self.en_correo.get() or "").strip().lower(),
            "cedula": str(self.en_cedula.get() or "").strip(),
            "sede": _normalize_sede(self.cb_sede.get()),
            "activo": self.cb_estado.get() == "Activo",
        }
        password = str(self.en_password.get() or "").strip()
        if password:
            payload["contrasenaHash"] = password
        return payload

    def _validate(self, payload):
        if not all([payload.get("nombre"), payload.get("usuario"), payload.get("correo"), payload.get("cedula"), payload.get("sede")]):
            return False, "Completa nombre, usuario, correo, cédula y sede."
        if "@" not in payload["correo"] or "." not in payload["correo"].split("@")[-1]:
            return False, "El correo no es válido."
        if not payload["cedula"].isdigit():
            return False, "La cédula debe ser numérica."
        return True, ""

    def _save(self):
        payload = self._collect()
        ok, msg = self._validate(payload)
        if not ok:
            messagebox.showerror("Administradores", msg, parent=self)
            return
        self.on_submit(payload, self.mode, dict(self.record or {}))

    def _cancel(self):
        self.hide()
        if callable(self.on_cancel):
            self.on_cancel()


class AdministradoresView(BaseModuleFrame):
    RESOURCE = "administradores"

    def __init__(self, master):
        super().__init__(master, "Administradores", "Controle perfiles administrativos y su estado")
        self._all_data = []
        self._data = []
        self._selected_id = None

        self._build_toolbar()
        self._build_form()
        self._build_summary()
        self._build_filters()
        self._build_table()
        self.after(120, self._refrescar)

    def _is_superadmin_record(self, item) -> bool:
        correo = str((item or {}).get("correo") or "").strip().lower()
        return correo == str(self.app.SUPERADMIN_EMAIL or "").strip().lower()

    def _selected_admin_item(self):
        if self._selected_id in (None, ""):
            messagebox.showinfo("Administradores", "Selecciona un administrador primero.", parent=self)
            return None
        for item in self._all_data:
            if str(item.get("id")) == str(self._selected_id):
                return item
        return None

    def _build_toolbar(self):
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure(6, weight=1)

        def btn(text, cmd):
            return ctk.CTkButton(
                tb,
                text=text,
                height=40,
                corner_radius=18,
                fg_color=self.app.COLOR_RED,
                hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff",
                command=cmd,
                anchor="w",
            )

        btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        btn("✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        btn("🗑 Eliminar", self._eliminar).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        btn("✓ Activar", self._activar_seleccionado).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        btn("⏸ Desactivar", self._desactivar_seleccionado).grid(row=0, column=4, padx=8, pady=6, sticky="w")
        btn("↻ Refrescar", self._refrescar).grid(row=0, column=5, padx=8, pady=6, sticky="w")

    def _build_form(self):
        self.form = AdminInlineForm(self, self.app, on_submit=self._save_admin, on_cancel=self._cancel_form)
        self.form.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()

    def _build_summary(self):
        self.summary = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=14, border_width=1, border_color=self.app.COLOR_DIVIDER)
        self.summary.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        for col in range(4):
            self.summary.grid_columnconfigure(col, weight=1)

        cards = (
            ("total", "Total admins"),
            ("activos", "Activos"),
            ("mayo", "Sede 1 de Mayo"),
            ("eden", "Sede El Eden"),
        )
        self._summary_cards = {}
        for idx, (key, label) in enumerate(cards):
            fg = self.app.RED_SOFT_BG if idx % 2 == 0 else self.app.MUSTARD_SOFT_BG
            border = self.app.RED_SOFT_BORDER if idx % 2 == 0 else self.app.MUSTARD_SOFT_BORDER
            text_color = self.app.COLOR_RED if idx % 2 == 0 else self.app.MUSTARD_MAIN
            card = ctk.CTkFrame(self.summary, fg_color=fg, corner_radius=12, border_width=1, border_color=border)
            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(card, text=label, text_color=text_color, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
            value = ctk.CTkLabel(card, text="0", text_color=self.app.COLOR_TEXT, font=ctk.CTkFont(size=22, weight="bold"))
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self._summary_cards[key] = value

    def _build_filters(self):
        bar = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        bar.grid(row=4, column=0, padx=16, pady=(0, 10), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)

        self.f_buscar = ctk.CTkEntry(
            bar,
            placeholder_text="Busca por nombre, usuario, correo, cédula o sede",
            height=38,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.f_buscar.grid(row=1, column=0, padx=(12, 8), pady=(0, 12), sticky="ew")
        ctk.CTkLabel(bar, text="Buscar", text_color=self.app.COLOR_TEXT).grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")

        self.f_estado = ctk.CTkComboBox(bar, values=["Todos", "Activo", "Inactivo"], width=150)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="w")
        ctk.CTkLabel(bar, text="Estado", text_color=self.app.COLOR_TEXT).grid(row=0, column=1, padx=8, pady=(10, 4), sticky="w")

        self.f_sede = ctk.CTkComboBox(bar, values=["Todas"] + SEDES_ADMIN, width=160)
        self.f_sede.set("Todas")
        self.f_sede.grid(row=1, column=2, padx=8, pady=(0, 12), sticky="w")
        ctk.CTkLabel(bar, text="Sede", text_color=self.app.COLOR_TEXT).grid(row=0, column=2, padx=8, pady=(10, 4), sticky="w")

        ctk.CTkButton(
            bar,
            text="Limpiar",
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self._clear_filters,
        ).grid(row=1, column=3, padx=(8, 12), pady=(0, 12), sticky="e")

        self.f_buscar.bind("<KeyRelease>", lambda _e: self._apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())
        self.f_sede.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

    def _build_table(self):
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(5, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "Admins.Treeview", rowheight=30)
        self._cols = [
            ("ID", 60, "center"),
            ("Nombre", 220, "w"),
            ("Usuario", 150, "w"),
            ("Correo", 260, "w"),
            ("Cédula", 120, "w"),
            ("Sede", 130, "w"),
            ("Estado", 90, "center"),
            ("Creado", 140, "w"),
            ("Actualizado", 140, "w"),
        ]
        cols = [c[0] for c in self._cols]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Admins.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, width, anchor in self._cols:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, minwidth=max(60, int(width * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._empty_label = ctk.CTkLabel(self.table, text="Sin administradores", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _unwrap(self, raw):
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in ("content", "items", "administradores", "data", "results"):
                val = raw.get(key)
                if isinstance(val, list):
                    return val
        return []

    def _format_dt(self, value):
        if not value:
            return "—"
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text[:16].replace("T", " ")

    def _on_select(self, _evt=None):
        selection = self.tree.selection()
        if not selection:
            self._selected_id = None
            return
        values = self.tree.item(selection[0], "values")
        self._selected_id = values[0] if values else None

    def _clear_filters(self):
        self.f_buscar.delete(0, "end")
        self.f_estado.set("Todos")
        self.f_sede.set("Todas")
        self._apply_filters()

    def _apply_filters(self):
        term = str(self.f_buscar.get() or "").strip().lower()
        estado = str(self.f_estado.get() or "Todos").strip().lower()
        sede = _normalize_sede(self.f_sede.get())
        data = list(self._all_data or [])
        if term:
            data = [
                item for item in data
                if term in str(item.get("nombre") or "").lower()
                or term in str(item.get("usuario") or "").lower()
                or term in str(item.get("correo") or "").lower()
                or term in str(item.get("cedula") or "").lower()
                or term in str(item.get("sede") or "").lower()
            ]
        if estado == "activo":
            data = [item for item in data if bool(item.get("activo"))]
        elif estado == "inactivo":
            data = [item for item in data if not bool(item.get("activo"))]
        if sede and sede != "Todas":
            data = [item for item in data if _normalize_sede(item.get("sede")) == sede]
        self._data = data
        self._render_summary()
        self._render_table()

    def _render_summary(self):
        total = len(self._data)
        activos = sum(1 for item in self._data if bool(item.get("activo")))
        mayo = sum(1 for item in self._data if _normalize_sede(item.get("sede")) == "1 de Mayo")
        eden = sum(1 for item in self._data if _normalize_sede(item.get("sede")) == "El Eden")
        self._summary_cards["total"].configure(text=str(total))
        self._summary_cards["activos"].configure(text=str(activos))
        self._summary_cards["mayo"].configure(text=str(mayo))
        self._summary_cards["eden"].configure(text=str(eden))

    def _render_table(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._selected_id = None
        if not self._data:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        self._empty_label.place_forget()
        for idx, item in enumerate(self._data):
            self.tree.insert(
                "",
                "end",
                values=(
                    item.get("id", "—"),
                    item.get("nombre") or "—",
                    item.get("usuario") or "—",
                    item.get("correo") or "—",
                    item.get("cedula") or "—",
                    _normalize_sede(item.get("sede")) or "—",
                    "Activo" if bool(item.get("activo")) else "Inactivo",
                    self._format_dt(item.get("creadoEn")),
                    self._format_dt(item.get("actualizadoEn")),
                ),
                tags=("even" if idx % 2 == 0 else "odd",),
            )

    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        item = self._selected_admin_item()
        if not item:
            return
        self.form.show_edit(item)

    def _cancel_form(self):
        self.form.hide()

    def _save_admin(self, payload, mode, record):
        try:
            if mode == "edit" and record.get("id"):
                self.app.api.ensure_not_modified(
                    self.RESOURCE,
                    record.get("id"),
                    record,
                    compare_fields=["correo", "cedula", "usuario", "nombre", "sede", "activo"],
                    label="administrador",
                )
                self.app.api.update(self.RESOURCE, record.get("id"), payload)
                self.app._info("Administrador actualizado.")
            else:
                self.app.api.create(self.RESOURCE, payload)
                self.app._info("Administrador creado.")
            self.form.hide()
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible guardar el administrador:\n{e}", parent=self)

    def _eliminar(self):
        item = self._selected_admin_item()
        if not item:
            return
        if self._is_superadmin_record(item):
            messagebox.showwarning("Administradores", "El superadministrador no se puede eliminar.", parent=self)
            return
        if not messagebox.askyesno("Administradores", f"¿Eliminar a {item.get('nombre') or 'este administrador'}?", parent=self):
            return
        try:
            self.app.api.delete(self.RESOURCE, item.get("id"))
            self.app._info("Administrador eliminado.")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible eliminar el administrador:\n{e}", parent=self)

    def _activar_seleccionado(self):
        item = self._selected_admin_item()
        if not item:
            return
        try:
            self.app.api.patch(self.RESOURCE, item.get("id"), suffix="activar")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible activar el administrador:\n{e}", parent=self)

    def _desactivar_seleccionado(self):
        item = self._selected_admin_item()
        if not item:
            return
        if self._is_superadmin_record(item):
            messagebox.showwarning("Administradores", "El superadministrador no se puede desactivar.", parent=self)
            return
        try:
            self.app.api.patch(self.RESOURCE, item.get("id"), suffix="desactivar")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible desactivar el administrador:\n{e}", parent=self)

    def _refrescar(self, force_refresh=True):
        try:
            raw = self.app.api.get_all(self.RESOURCE, force_refresh=force_refresh) or []
            self._all_data = self._unwrap(raw)
            self._apply_filters()
        except Exception as e:
            messagebox.showerror("Administradores", f"No fue posible consultar la API:\n{e}", parent=self)
