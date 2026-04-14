"""
Módulo de Vehículos.

Vista para crear/editar vehículos y consultar datos desde la API.
"""

import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import time
from modules.forms_inlines import VehiculoInlineForm
from modules.base import BaseModuleFrame
from modules.treeview_theme import configure_treeview_style


def _normalize_sede_label(value) -> str:
    """
    Normaliza el texto de sede para mostrar valores consistentes en UI.

    Args:
        value: Texto original (puede venir con acentos/variaciones).

    Returns:
        Sede normalizada (`"1 de Mayo"` / `"El Eden"` o el valor original).
    """
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


class VehiculosView(BaseModuleFrame):
    """Vista de gestión de vehículos (tabla, filtros y formulario)."""
    DEBOUNCE_MS = 250
    MIN_REFRESH_INTERVAL = 500
    RENDER_DELAY_MS = 16
    TREE_INSERT_CHUNK = 250
    TREE_INSERT_DELAY = 1

    def __init__(self, master):
        """Inicializa la vista (toolbar, formulario, tabla) y programa la carga inicial."""
        super().__init__(master, "Vehículos", "Gestione los automóviles de la academia")

        self._all_data = []
        self._data = []
        self._selected_idx = None
        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._loading_overlay = None
        self._last_refresh_ts = 0
        self._editing_placa = None

        self._iid_to_index = {}

        # ================= TOOLBAR =================
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")

        def action_btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                tb,
                text=text,
                height=40,
                corner_radius=18,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
            )

        action_btn("＋ Nuevo", self._nuevo, self.app.COLOR_GREEN, self.app.GREEN_HOVER).grid(row=0, column=0, padx=6)
        action_btn("✎ Editar", self._editar, self.app.COLOR_BLUE, self.app.BLUE_HOVER).grid(row=0, column=1, padx=6)
        action_btn("🗑️ Eliminar", self._eliminar_seleccionado, self.app.COLOR_RED, self.app.RED_HOVER).grid(row=0, column=2, padx=6)
        action_btn("↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER).grid(row=0, column=3, padx=6)

        # ================= FORM =================
        self.form = VehiculoInlineForm(
            self, self.app,
            on_submit=self._submit_inline,
            on_cancel=self._cancel_inline
        )
        self.form.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()

        # ================= TABLA =================
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Placa", 130),
            ("Marca", 190),
            ("Modelo", 190),
            ("Año", 100),
            ("Sede", 220),
            ("Estado", 140),
        ]

        self._build_tree()
        self.after(150, self._refrescar)

    # =====================================================
    #                TREEVIEW (TABLA RÁPIDA)
    # =====================================================
    def _build_tree(self):
        """Construye Treeview, columnas y estilos; enlaza selección y doble clic."""
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

        for name, width in self._COLS:
            self.tree.heading(name, text=name)
            anchor = "center" if name in {"Año", "Estado"} else "w"
            self.tree.column(name, width=width, minwidth=max(70, int(width * 0.8)), stretch=True, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        self._empty_label = ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _on_tree_select(self, _=None):
        """Evento de selección: mapea el IID seleccionado a índice de `_data`."""
        sel = self.tree.selection()
        if not sel:
            self._selected_idx = None
            return
        iid = sel[0]
        self._selected_idx = self._iid_to_index.get(iid)

    @staticmethod
    def _sede_value(vh):
        """Extrae la sede del vehículo desde llaves/estructuras variadas (string/dict/id)."""
        for key in ("sede", "sedePrincipal", "sede_principal", "sedeNombre", "nombreSede", "campus"):
            if key not in vh:
                continue
            val = vh.get(key)
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
            val = vh.get(key)
            if val not in ("", None):
                return str(val).strip()
        return ""

    def _row_values(self, vh):
        """Convierte un dict de vehículo a la tupla de valores de la fila."""
        estado = str(vh.get("estado", "") or "").strip()
        estado_disp = estado.capitalize() if estado else ""
        return (
            str(vh.get("placa", "") or "").strip().upper(),
            str(vh.get("marca", "") or "").strip().upper(),
            str(vh.get("modelo", "") or "").strip().upper(),
            vh.get("anio", "") if vh.get("anio", "") is not None else "",
            self._sede_value(vh),
            estado_disp,
        )

    def _set_data(self, rows):
        """Repinta el Treeview con la lista actual de vehículos."""
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        self._iid_to_index.clear()
        self._selected_idx = None

        data = list(rows or [])
        if not data:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        self._empty_label.place_forget()

        def insert_chunk(start=0):
            end = min(start + self.TREE_INSERT_CHUNK, len(data))
            for idx in range(start, end):
                vh = data[idx]
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                self.tree.insert(
                    "", "end",
                    iid=iid,
                    values=self._row_values(vh),
                    tags=("even" if idx % 2 == 0 else "odd",)
                )
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    # =====================================================
    #                ACCIONES
    # =====================================================
    def _nuevo(self):
        """Acción: abrir formulario para crear vehículo."""
        self.form.show_create()

    def _editar(self):
        """Acción: abrir formulario para editar el vehículo seleccionado."""
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo primero.")
            return
        self.form.show_edit(self._data[self._selected_idx])

    def _eliminar_seleccionado(self):
        """Acción: eliminar el vehículo seleccionado (confirmación + API)."""
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo primero.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        """Acción: ocultar el formulario inline."""
        self.form.hide()

    # =====================================================
    #                API
    # =====================================================
    def _refrescar(self, force_refresh=True):
        """Consulta la API de vehículos, aplica sede/permisos y repinta tabla."""
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if not self.app.api:
            self.app._info("No hay cliente API activo.")
            return

        def worker():
            try:
                raw = self.app.api.get_all("vehiculos", force_refresh=force_refresh) or []

                if isinstance(raw, dict):
                    for key in ("content", "items", "vehiculos", "data", "results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []

                def apply_data():
                    allowed_sede = "" if getattr(self.app, "is_superadmin", False) else _normalize_sede_label(getattr(self.app, "current_admin_sede", None))
                    if allowed_sede:
                        raw_filtered = [vh for vh in (raw or []) if _normalize_sede_label(self._sede_value(vh)) == allowed_sede]
                    else:
                        raw_filtered = raw or []
                    self._all_data = raw_filtered
                    self._data = raw_filtered
                    self._set_data(self._data)

                self.after(0, apply_data)

            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Vehículos", str(e), parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _submit_inline(self, payload, mode):
        """Callback del formulario: crea/actualiza vehículo y refresca datos."""
        try:
            payload = dict(payload or {})
            for key in ("placa", "marca", "modelo"):
                payload[key] = str(payload.get(key, "") or "").strip().upper()
            allowed_sede = "" if getattr(self.app, "is_superadmin", False) else _normalize_sede_label(getattr(self.app, "current_admin_sede", None))
            if allowed_sede:
                payload["sede"] = allowed_sede
            if mode == "create":
                self.app.api.create("vehiculos", payload)
            else:
                idx = self._selected_idx
                vh = self._data[idx]
                placa = vh.get("placa")
                self.app.api.ensure_not_modified(
                    "vehiculos",
                    placa,
                    vh,
                    compare_fields=["placa", "marca", "modelo", "anio", "sede", "estado", "visible"],
                    label="vehículo",
                )
                self.app.api.update("vehiculos", placa, payload)

            self._last_refresh_ts = 0
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Vehículos", str(e), parent=self)

    def _delete_row(self, idx):
        """Elimina un vehículo por índice (confirmación + delete en API)."""
        vh = self._data[idx]
        placa = vh.get("placa")

        if not messagebox.askyesno("Confirmar", f"¿Eliminar vehículo {placa}?"):
            return

        try:
            self.app.api.delete("vehiculos", placa)
            self._last_refresh_ts = 0
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Vehículos", str(e), parent=self)
