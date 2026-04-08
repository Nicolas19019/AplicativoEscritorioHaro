import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk
import threading
import time

from modules.base import BaseModuleFrame
from modules.forms_inlines import InstructorInlineForm
from modules.treeview_theme import configure_treeview_style


def _normalize_sede_label(value) -> str:
    txt = str(value or "").strip().lower()
    if not txt:
        return str(value or "").strip()

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
    return str(value or "").strip()


class InstructoresView(BaseModuleFrame):
    DEBOUNCE_MS = 250
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16
    TREE_INSERT_CHUNK = 250
    TREE_INSERT_DELAY = 1  # ms

    def __init__(self, master):
        super().__init__(master, "Instructores", "Gestione los profesores registrados en el sistema")

        # ===== Estado para filtros =====
        self._all_data = []      # todo lo que viene de API
        self._data = []          # filtrado para pintar
        self._selected_idx = None
        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._loading_overlay = None
        self._last_refresh_ts = 0

        # mapeo Tree IID -> idx actual en self._data
        self._iid_to_index = {}

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0, 1, 2, 3, 4), weight=0)
        tb.grid_columnconfigure(5, weight=1)

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

        # ===== Formulario inline =====
        self.form = InstructorInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()

        # ===== Filtros (con búsqueda en vivo) =====
        self.filters = self._make_filters_bar(self)
        self.filters.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        # ===== Tabla (Treeview) =====
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Cédula", 120),
            ("Nombre", 260),
            ("Especialidad", 180),
            ("Categoría", 110),
            ("Sede", 170),
            ("Teléfono", 130),
            ("Email", 220),
            ("Usuario", 140),
            ("Visible", 90),
        ]

        self._build_tree()
        self._queue_render(self._data)
        self.after(150, self._refrescar)

    # =====================================================
    #                    FILTROS (PRO)
    # =====================================================
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        # Fila 1: cedula/nombre/apellido (responsivos)
        # Fila 2: estado/especialidad/categoria + botones
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=1)

        def entry(ph):
            return ctk.CTkEntry(
                bar, placeholder_text=ph, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER
            )

        ctk.CTkLabel(bar, text="Cédula").grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_cedula = entry("Ej: 1012345678")
        self.f_cedula.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Nombre").grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_nombre = entry("Nombre")
        self.f_nombre.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Apellido").grid(row=0, column=2, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_apellido = entry("Apellido")
        self.f_apellido.grid(row=1, column=2, padx=(8, 8), pady=(0, 10), sticky="ew")

        row2 = ctk.CTkFrame(bar, fg_color="transparent")
        row2.grid(row=2, column=0, columnspan=3, padx=(12, 12), pady=(0, 10), sticky="ew")
        row2.grid_columnconfigure(0, weight=0)
        row2.grid_columnconfigure(1, weight=0)
        row2.grid_columnconfigure(2, weight=0)
        row2.grid_columnconfigure(3, weight=1)  # separador flexible
        row2.grid_columnconfigure(4, weight=0)

        ctk.CTkLabel(row2, text="Estado").grid(row=0, column=0, padx=(0, 8), pady=(0, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(row2, values=["Todos", "Activo", "Inactivo", "Suspendido"], width=150)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=0, padx=(0, 8), pady=(0, 0), sticky="w")

        ctk.CTkLabel(row2, text="Especialidad").grid(row=0, column=1, padx=(8, 8), pady=(0, 4), sticky="w")
        self.f_especialidad = ctk.CTkComboBox(row2, values=["Todas"], width=170)
        self.f_especialidad.set("Todas")
        self.f_especialidad.grid(row=1, column=1, padx=(8, 8), pady=(0, 0), sticky="w")

        ctk.CTkLabel(row2, text="Categoría").grid(row=0, column=2, padx=(8, 8), pady=(0, 4), sticky="w")
        self.f_categoria = ctk.CTkComboBox(row2, values=["Todas"], width=130)
        self.f_categoria.set("Todas")
        self.f_categoria.grid(row=1, column=2, padx=(8, 8), pady=(0, 0), sticky="w")

        btns = ctk.CTkFrame(row2, fg_color="transparent")
        btns.grid(row=1, column=4, padx=(12, 0), pady=(0, 0), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
                text_color=self.app.COLOR_TEXT, command=cmd
            )

        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=(0, 8))
        light_btn("Buscar", self._apply_filters_now).grid(row=0, column=1, padx=(8, 0))

        for w in (self.f_cedula, self.f_nombre, self.f_apellido):
            w.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_especialidad.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())
        self.f_categoria.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())

        return bar

    def _collect_filters(self):
        return {
            "cedula": (self.f_cedula.get() or "").strip(),
            "nombre": (self.f_nombre.get() or "").strip(),
            "apellido": (self.f_apellido.get() or "").strip(),
            "estado": (self.f_estado.get() or "Todos").strip(),
            "especialidad": (self.f_especialidad.get() or "Todas").strip(),
            "categoria": (self.f_categoria.get() or "Todas").strip(),
        }

    def _clear_filters(self):
        self.f_cedula.delete(0, "end")
        self.f_nombre.delete(0, "end")
        self.f_apellido.delete(0, "end")
        self.f_estado.set("Todos")
        self.f_especialidad.set("Todas")
        self.f_categoria.set("Todas")
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

    @staticmethod
    def _categoria_value(prof):
        categoria = (
            prof.get("categoria")
            or prof.get("categoriaLicencia")
            or prof.get("licenciaCategoria")
            or ""
        )
        return str(categoria).strip().upper()

    @staticmethod
    def _email_value(prof):
        return str(prof.get("email") or "").strip()

    @staticmethod
    def _usuario_value(prof):
        return str(prof.get("usuario") or "").strip()

    @staticmethod
    def _sede_value(prof):
        for key in ("sede", "sedePrincipal", "sede_principal", "sedeNombre", "nombreSede", "campus"):
            if key not in prof:
                continue
            val = prof.get(key)
            if val in ("", None):
                continue
            if isinstance(val, dict):
                for k2 in ("nombre", "name", "descripcion", "sede"):
                    v2 = val.get(k2)
                    if v2 not in ("", None):
                        return str(v2).strip()
                if val.get("id") not in ("", None):
                    return str(val.get("id")).strip()
                return ""
            return str(val).strip()

        for key in ("idSede", "sedeId", "sede_id"):
            val = prof.get(key)
            if val not in ("", None):
                return str(val).strip()
        return ""

    @staticmethod
    def _visible_value(prof):
        raw = str(prof.get("visible", True)).strip().lower()
        return "Sí" if raw in {"true", "1", "si", "yes"} else "No"

    @staticmethod
    def _to_bool(v, default=True):
        if isinstance(v, bool):
            return v
        if v is None:
            return default
        return str(v).strip().lower() in {"true", "1", "si", "yes"}

    def _normalize_profesor_payload(self, payload):
        src = dict(payload or {})

        cedula = str(src.get("cedula", "") or "").strip()
        nombre = str(src.get("nombre", "") or "").strip().upper()
        apellido = str(src.get("apellido", "") or "").strip().upper()
        telefono = str(src.get("telefono", "") or "").strip()
        usuario = str(src.get("usuario", "") or "").strip()

        sede_raw = src.get("sede", "") or ""
        if isinstance(sede_raw, dict):
            sede_raw = sede_raw.get("nombre") or sede_raw.get("name") or sede_raw.get("descripcion") or ""
        sede = str(sede_raw or "").strip()

        email = str(src.get("email", "") or "").strip()

        especialidad = str(src.get("especialidad", "") or "").strip().lower()
        categoria = str(src.get("categoria", "") or "").strip().lower()
        if especialidad not in {"carro", "moto"}:
            especialidad = "moto" if "moto" in especialidad else "carro"
        if categoria not in {"carro", "moto"}:
            categoria = "moto" if "moto" in categoria else especialidad

        visible = self._to_bool(src.get("visible"), default=True)

        out = {
            "cedula": cedula,
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "especialidad": especialidad,
            "categoria": categoria,
            "telefono": telefono,
            "usuario": usuario,
            "visible": visible,
            "contrasena": src.get("contrasena", None),
        }
        if sede:
            out["sede"] = sede
        return out

    @staticmethod
    def _assert_email_updated(server_obj, expected_email):
        if not isinstance(server_obj, dict):
            return
        exp = str(expected_email or "").strip().lower()
        got = str(server_obj.get("email") or "").strip().lower()
        if exp and got and exp != got:
            raise RuntimeError(
                f"El servidor no actualizó 'email'. Esperado: {expected_email} | Recibido: {server_obj.get('email')}"
            )

    def _apply_filters(self, data_list, f):
        if not data_list:
            return []
        allowed_sede = "" if getattr(self.app, "is_superadmin", False) else _normalize_sede_label(getattr(self.app, "current_admin_sede", None))

        ced_sub = f["cedula"].lower()
        nom_sub = f["nombre"].lower()
        ape_sub = f["apellido"].lower()
        estado = f["estado"]
        esp = f["especialidad"].strip().lower()
        cat = f["categoria"].strip().upper()

        out = []
        for prof in data_list:
            ced = str(prof.get("cedula", "") or "").lower()
            nom = str(prof.get("nombre", "") or "").strip().lower()
            ape = str(prof.get("apellido", "") or "").strip().lower()
            est = str(prof.get("estado", "") or "").strip()
            especialidad = str(prof.get("especialidad", "") or "").strip().lower()
            categoria = self._categoria_value(prof)
            sede_label = _normalize_sede_label(self._sede_value(prof))

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
            if cat != "TODAS" and categoria != cat:
                continue
            if allowed_sede and sede_label != allowed_sede:
                continue

            out.append(prof)
        return out

    def _refresh_especialidad_options(self):
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

    def _refresh_categoria_options(self):
        cats = set()
        for p in (self._all_data or []):
            c = self._categoria_value(p)
            if c:
                cats.add(c)
        values = ["Todas"] + sorted(cats)
        try:
            self.f_categoria.configure(values=values)
            if self.f_categoria.get() not in values:
                self.f_categoria.set("Todas")
        except Exception:
            pass

    # =====================================================
    #                    TREEVIEW (TABLA RÁPIDA)
    # =====================================================
    def _build_tree(self):
        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "Haro.Treeview", rowheight=30)

        cols = [c[0] for c in self._COLS]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Haro.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, w in self._COLS:
            self.tree.heading(name, text=name)
            anchor = "w"
            if name in {"Cédula", "Categoría", "Visible"}:
                anchor = "center"
            self.tree.column(name, width=w, minwidth=max(60, int(w * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        self._empty_label = ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _on_tree_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            self._selected_idx = None
            return
        iid = sel[0]
        self._selected_idx = self._iid_to_index.get(iid)

    def _row_values(self, prof):
        full_name = f"{prof.get('nombre', '')} {prof.get('apellido', '')}".strip()
        return (
            prof.get("cedula", ""),
            full_name,
            str(prof.get("especialidad", "") or "").strip().upper(),
            self._categoria_value(prof),
            self._sede_value(prof),
            prof.get("telefono", ""),
            self._email_value(prof),
            self._usuario_value(prof),
            self._visible_value(prof),
        )

    def _set_data(self, rows):
        data = list(rows or [])

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
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                self.tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=self._row_values(data[idx]),
                    tags=("even" if idx % 2 == 0 else "odd",),
                )
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    # =====================================================
    #                    ACCIONES
    # =====================================================
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un profesor en la tabla primero.")
            return
        self.form.show_edit(self._data[self._selected_idx])

    def _eliminar_seleccionado(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un profesor en la tabla primero.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        self.form.hide()

    # =====================================================
    #                    API
    # =====================================================
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
                raw = self.app.api.get_all("profesores", force_refresh=force_refresh) or []
                if isinstance(raw, dict):
                    for key in ("content", "items", "profesores", "data", "results"):
                        lst = raw.get(key)
                        if isinstance(lst, list):
                            raw = lst
                            break
                    else:
                        raw = []

                def apply_data():
                    allowed_sede = "" if getattr(self.app, "is_superadmin", False) else _normalize_sede_label(getattr(self.app, "current_admin_sede", None))
                    if allowed_sede:
                        filtered_raw = [prof for prof in (raw or []) if _normalize_sede_label(self._sede_value(prof)) == allowed_sede]
                    else:
                        filtered_raw = raw or []
                    self._all_data = filtered_raw
                    self._refresh_especialidad_options()
                    self._refresh_categoria_options()
                    self._data = self._apply_filters(self._all_data, self._collect_filters())
                    self._queue_render(self._data)

                self.after(0, apply_data)
            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: messagebox.showerror("Profesores", f"No fue posible consultar la API:\n{err}", parent=self))
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

            payload = self._normalize_profesor_payload(payload)
            allowed_sede = "" if getattr(self.app, "is_superadmin", False) else _normalize_sede_label(getattr(self.app, "current_admin_sede", None))
            if allowed_sede:
                payload["sede"] = allowed_sede

            if mode == "create":
                created = self.app.api.create("profesores", payload)
                self._assert_email_updated(created, payload.get("email"))
                self.app._info("Profesor creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un profesor para actualizar.")
                    return
                prof_id = self._data[idx].get("id") or self._data[idx].get("idProfesor")
                if not prof_id:
                    self.app._info("No se encontró el ID del profesor.")
                    return
                self.app.api.ensure_not_modified(
                    "profesores",
                    prof_id,
                    self._data[idx],
                    compare_fields=[
                        "cedula", "nombre", "apellido", "correo", "especialidad",
                        "categoria", "telefono", "email", "usuario", "visible",
                    ],
                    label="profesor",
                )
                updated = self.app.api.update("profesores", prof_id, payload)
                self._assert_email_updated(updated, payload.get("email"))
                self.app._info("Profesor actualizado.")

            self._last_refresh_ts = 0
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Profesores", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        prof = self._data[idx]
        name = f"{prof.get('nombre','')} {prof.get('apellido','')}".strip()
        ced = prof.get("cedula", "")

        if not messagebox.askyesno("Confirmar", f"¿Eliminar al profesor:\n{name} (Cédula: {ced})", parent=self):
            self.app._info("Operación cancelada.")
            return

        try:
            prof_id = prof.get("id") or prof.get("idProfesor")
            if not prof_id:
                self.app._info("No se encontró el ID del profesor.")
                return
            self.app.api.delete("profesores", prof_id)
            self.app._info("Profesor eliminado.")
            self._last_refresh_ts = 0
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Profesores", f"No fue posible eliminar:\n{e}", parent=self)
