import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk
import threading
import time

from modules.base import BaseModuleFrame
from modules.forms_inlines import InstructorInlineForm


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

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(
                parent, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        red_btn(tb, "✎ Editar", self._editar).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        red_btn(tb, "🗑️ Eliminar", self._eliminar_seleccionado).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=8, pady=6, sticky="w")

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
            ("Teléfono", 130),
            ("Email", 240),
        ]

        self._build_tree()
        self._queue_render(self._data)
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

        ctk.CTkLabel(bar, text="Cédula").grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_cedula = entry("Ej: 1012345678")
        self.f_cedula.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Nombre").grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_nombre = entry("Nombre")
        self.f_nombre.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Apellido").grid(row=0, column=2, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_apellido = entry("Apellido")
        self.f_apellido.grid(row=1, column=2, padx=(8, 8), pady=(0, 10), sticky="ew")

        ctk.CTkLabel(bar, text="Estado").grid(row=0, column=3, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(bar, values=["Todos", "Activo", "Inactivo", "Suspendido"], width=160)
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=3, padx=(8, 8), pady=(0, 10), sticky="w")

        ctk.CTkLabel(bar, text="Especialidad").grid(row=0, column=4, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_especialidad = ctk.CTkComboBox(bar, values=["Todas"], width=170)
        self.f_especialidad.set("Todas")
        self.f_especialidad.grid(row=1, column=4, padx=(8, 8), pady=(0, 10), sticky="w")

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
    #                    TREEVIEW (TABLA RÁPIDA)
    # =====================================================
    def _build_tree(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Igual que en Estudiantes: adaptar a Light/Dark
        mode = ctk.get_appearance_mode()  # "Light" o "Dark"

        if mode == "Light":
            bg = "#ffffff"
            panel = "#ffffff"
            text = "#111111"
            muted = "#444444"
            divider = "#e5e7eb"
            sel_bg = "#f1f5f9"
        else:
            bg = getattr(self.app, "COLOR_BG", "#111111")
            panel = getattr(self.app, "COLOR_PANEL", "#1b1b1b")
            text = getattr(self.app, "COLOR_TEXT", "#ffffff")
            muted = getattr(self.app, "COLOR_MUTED", "#cfcfcf")
            divider = getattr(self.app, "COLOR_DIVIDER", "#2a2a2a")
            sel_bg = divider

        style.configure(
            "Haro.Treeview",
            background=panel,
            fieldbackground=panel,
            foreground=text,
            bordercolor=divider,
            lightcolor=divider,
            darkcolor=divider,
            rowheight=28,
        )
        style.map(
            "Haro.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", text)],
        )
        style.configure(
            "Haro.Treeview.Heading",
            background=bg,
            foreground=muted,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )

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
            self.tree.column(name, width=w, minwidth=max(60, int(w * 0.7)), stretch=True, anchor="w")

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
            prof.get("especialidad", ""),
            prof.get("telefono", ""),
            prof.get("email", ""),
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
                self.tree.insert("", "end", iid=iid, values=self._row_values(data[idx]))
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
                    self._all_data = raw or []
                    self._refresh_especialidad_options()
                    self._data = self._apply_filters(self._all_data, self._collect_filters())
                    self._queue_render(self._data)

                self.after(0, apply_data)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Profesores", f"No fue posible consultar la API:\n{e}", parent=self))
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
            prof_id = prof.get("id")
            if not prof_id:
                self.app._info("No se encontró el ID del profesor.")
                return
            self.app.api.delete("profesores", prof_id)
            self.app._info("Profesor eliminado.")
            self._last_refresh_ts = 0
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Profesores", f"No fue posible eliminar:\n{e}", parent=self)