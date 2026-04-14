# modules/estados_cuenta.py
"""
Módulo de Estados de Cuenta.

Consulta y gestión de saldos/pagos, con render por lotes para mejorar rendimiento en UI.
"""

from typing import Tuple, Dict, Any, Optional
import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import time
from modules.base import BaseModuleFrame
from modules.treeview_theme import configure_treeview_style

class EstadosCuentaView(BaseModuleFrame):
    """Vista de estados de cuenta (consulta, edición y totales según permisos)."""
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 4
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16
    _student_combo_placeholder = "Seleccionar nombre del estudiante"
    student_combo_placeholder = _student_combo_placeholder

    def __init__(self, master):
        """Inicializa la vista de estados de cuenta (filtros, formulario y tabla)."""
        super().__init__(master, "Estados de cuenta", "Gestión de saldos y pagos")
        self.can_edit = bool(getattr(self.app, "is_superadmin", False))

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0,6), sticky="ew")
        for c in range(6):
            tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

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
                anchor="w",
            )

        self.btn_nuevo = action_btn("＋ Nuevo", self._nuevo, self.app.COLOR_GREEN, self.app.GREEN_HOVER)
        self.btn_nuevo.grid(row=0, column=0, padx=(0,8))
        self.btn_editar = action_btn("✎ Editar", self._editar, self.app.COLOR_BLUE, self.app.BLUE_HOVER)
        self.btn_editar.grid(row=0, column=1, padx=8)
        self.btn_eliminar = action_btn("🗑 Eliminar", self._eliminar, self.app.COLOR_RED, self.app.RED_HOVER)
        self.btn_eliminar.grid(row=0, column=2, padx=8)
        action_btn("↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER).grid(row=0, column=3, padx=8)

        if not self.can_edit:
            self.btn_nuevo.configure(state="disabled")
            self.btn_editar.configure(state="disabled")
            self.btn_eliminar.configure(state="disabled")
            ctk.CTkLabel(
                tb,
                text="Solo lectura para administradores",
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=0, column=4, padx=(8, 0), sticky="w")

        # ===== Formulario =====
        self._build_form()
        self.form.grid(row=2, column=0, padx=16, pady=(8,10), sticky="ew")
        self._hide_form()

        # ===== Filtros =====
        self._build_filters_bar()
        self.filters_bar.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        # ===== Tabla =====
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 8), sticky="nsew")
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        # ===== Variables =====
        self._all_data = []               # fuente sin filtrar
        self._data = []                   # type: list[Dict[str, Any]]
        self._rows = []                   # type: list[ctk.CTkFrame]
        self._selected_idx = None         # type: Optional[int]
        self.estudiantes = []             # type: list[Dict[str, Any]]
        self.estudiantes_id_to_name = {}  # type: Dict[Any, str]
        self.estudiantes_name_to_id = {}  # type: Dict[str, Any]
        self._totals_frame = None
        self._render_after_id = None
        self._render_seq = 0
        self._row_pool = []
        self._empty_label = None
        self._loading_overlay = None
        self._last_refresh_ts = 0
        self._search_after_id = None
        self._student_filter_after_id = None
        self._current_paid_base = 0.0
        self.tree = None
        self._iid_to_index = {}
        self._student_combo_placeholder = self.__class__._student_combo_placeholder
        self.student_combo_placeholder = self._student_combo_placeholder

        self._render_table()
        self.en_buscar.bind("<KeyRelease>", self._on_search_key)
        self.after(150, self._cargar_catalogos_y_listar)

    def _take_estudiante_id(self, rec):
        """Obtiene el id del estudiante desde un registro de estado de cuenta."""
        return rec.get("idEstudiante") or rec.get("id_estudiante") or rec.get("estudianteId")

    def _student_name_from_record(self, rec) -> str:
        """Extrae el nombre del estudiante desde el registro (si viene embebido)."""
        if not isinstance(rec, dict):
            return ""

        for key in ("nombreEstudiante", "estudianteNombre", "nombre_estudiante"):
            val = rec.get(key)
            if val not in (None, ""):
                return str(val).strip()

        estudiante = rec.get("estudiante")
        if isinstance(estudiante, dict):
            nombre = str(estudiante.get("nombre", "") or "").strip()
            apellido = str(estudiante.get("apellido", "") or "").strip()
            full = f"{nombre} {apellido}".strip()
            if full:
                return full

        return ""

    def _student_name_for(self, estudiante_id) -> str:
        """Resuelve un id de estudiante a nombre usando el cache `estudiantes_id_to_name`."""
        if estudiante_id in (None, ""):
            return "—"
        name = self.estudiantes_id_to_name.get(estudiante_id)
        if not name:
            name = self.estudiantes_id_to_name.get(str(estudiante_id))
        return name or "—"

    def _apply_search(self, rows):
        """Filtra filas por termino de busqueda (por nombre del estudiante)."""
        term = (self.en_buscar.get() or "").strip().lower()
        if not term:
            return list(rows or [])
        out = []
        for rec in (rows or []):
            name = self._student_name_for(self._take_estudiante_id(rec))
            if term in (name or "").lower():
                out.append(rec)
        return out

    def _on_search_key(self, _evt=None):
        """Maneja el input de busqueda con debounce para evitar renders excesivos."""
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(200, lambda: self._queue_render(self._apply_search(self._all_data)))

    def _build_filters_bar(self):
        """Construye la barra de filtros (busqueda y acciones) de la vista."""
        self.filters_bar = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.filters_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.filters_bar,
            text="Buscar estudiante",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(14, 10), pady=(12, 4), sticky="w")

        self.en_buscar = ctk.CTkEntry(
            self.filters_bar,
            height=42,
            corner_radius=14,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_width=2,
            border_color=self.app.COLOR_YELLOW,
            placeholder_text="Escribe nombre del estudiante"
        )
        self.en_buscar.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")

        ctk.CTkButton(
            self.filters_bar,
            text="Limpiar",
            height=42,
            width=120,
            corner_radius=16,
            fg_color=self.app.COLOR_RED,
            hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff",
            command=self._clear_search,
        ).grid(row=1, column=2, padx=(0, 14), pady=(0, 12), sticky="e")

    def _clear_search(self):
        """Limpia el termino de busqueda y re-renderiza la tabla."""
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
            self._search_after_id = None
        self.en_buscar.delete(0, "end")
        self._queue_render(self._apply_search(self._all_data))
        self.after_idle(self.en_buscar.focus_set)

    def _normalize_text_filter(self, value: str) -> str:
        """Normaliza texto para filtros (lowercase y espacios compactados)."""
        return " ".join(str(value or "").lower().split())

    def _used_student_ids(self, exclude_record: Optional[Dict[str, Any]] = None):
        """Retorna ids de estudiantes ya usados (evita duplicar estados de cuenta)."""
        used = set()
        exclude_id = self._take_estudiante_id(exclude_record or {}) if exclude_record else None
        for rec in (self._all_data or []):
            current_id = self._take_estudiante_id(rec)
            if current_id in (None, "", 0):
                continue
            if exclude_id not in (None, "", 0) and str(current_id) == str(exclude_id):
                continue
            used.add(str(current_id))
        return used

    def _refresh_student_combo_values(self, typed_text: str = ""):
        """Refresca las opciones del combobox de estudiantes segun lo que se escribe."""
        values = []
        if self._form_mode == "edit":
            current_rec = None
            if self._editing_idx is not None and 0 <= self._editing_idx < len(self._data):
                current_rec = self._data[self._editing_idx]
            used_ids = self._used_student_ids(exclude_record=current_rec)
        else:
            used_ids = self._used_student_ids()
        for name in sorted(list(self.estudiantes_name_to_id.keys())):
            student_id = self.estudiantes_name_to_id.get(name)
            if self._form_mode == "edit" or str(student_id) not in used_ids:
                values.append(name)
        raw_term = str(typed_text or "")
        clean_term = raw_term.strip()
        normalized_term = self._normalize_text_filter(clean_term)
        if clean_term and clean_term.lower() not in {
            "selecciona un estudiante",
            "sin coincidencias",
            self._student_combo_placeholder.lower(),
        }:
            filtered = [
                name for name in values
                if normalized_term in self._normalize_text_filter(name)
            ]
            if filtered:
                values = filtered
        if not values:
            values = sorted(list(self.estudiantes_name_to_id.keys()))
        try:
            self.cb_estudiante.configure(values=values)
        except Exception:
            pass
        self._restore_student_combo_text(raw_term)

    def _restore_student_combo_text(self, text: str):
        """Restaura el texto tecleado en el combobox y la posicion del cursor."""
        try:
            self.cb_estudiante.set(text)
            entry = getattr(self.cb_estudiante, "_entry", None)
            if entry is not None:
                entry.focus_set()
                entry.icursor(len(text))
        except Exception:
            pass

    def _apply_student_filter(self, typed: str):
        """Aplica el filtro de estudiantes (debounce) y actualiza opciones."""
        self._student_filter_after_id = None
        self._refresh_student_combo_values(typed)

    def _on_student_filter_key(self, _evt=None):
        """Maneja la escritura en el combobox de estudiante con debounce."""
        typed = self.cb_estudiante.get() if hasattr(self, "cb_estudiante") else ""
        if self._student_filter_after_id:
            try:
                self.after_cancel(self._student_filter_after_id)
            except Exception:
                pass
        self._student_filter_after_id = self.after(120, lambda value=typed: self._apply_student_filter(value))

    # ===================== FORMULARIO =====================
    def _build_form(self):
        """Construye el formulario de creacion/edicion de estados de cuenta."""
        self.form = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL,
                                 corner_radius=12, border_width=2, border_color=self.app.COLOR_DIVIDER)
        for c in range(4):
            self.form.grid_columnconfigure(c, weight=1)

        def label(r, c, text):
            ctk.CTkLabel(self.form, text=text, text_color=self.app.COLOR_TEXT)\
                .grid(row=r, column=c, padx=10, pady=(10,4), sticky="w")

        def entry(ph=""):
            return ctk.CTkEntry(
                self.form, height=34, corner_radius=8,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=1, border_color=self.app.COLOR_DIVIDER,
                placeholder_text=ph
            )

        # Campos
        label(0, 0, "Estudiante")
        self.cb_estudiante = ctk.CTkComboBox(
            self.form,
            values=[self._student_combo_placeholder],
            width=360,
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
        self.cb_estudiante.grid(row=1, column=0, padx=10, pady=(0,6), sticky="w", columnspan=2)
        self.cb_estudiante.bind("<KeyRelease>", self._on_student_filter_key)

        label(0, 2, "Valor del curso")
        self.en_total = entry("0.00")
        self.en_total.grid(row=1, column=2, padx=10, pady=(0,6), sticky="ew")

        label(0, 3, "Nuevo abono")
        self.en_abono = entry("0.00")
        self.en_abono.grid(row=1, column=3, padx=10, pady=(0,6), sticky="ew")

        label(2, 0, "Multas")
        self.en_multas = entry("0.00")
        self.en_multas.grid(row=3, column=0, padx=10, pady=(0,6), sticky="ew")

        label(2, 1, "Pagado acumulado")
        self.lbl_pagado_actual = ctk.CTkLabel(self.form, text="0.00", text_color=self.app.COLOR_TEXT)
        self.lbl_pagado_actual.grid(row=3, column=1, padx=10, pady=(0,8), sticky="w")

        label(2, 2, "Total a pagar")
        self.lbl_total_exigible = ctk.CTkLabel(self.form, text="0.00", text_color=self.app.COLOR_TEXT)
        self.lbl_total_exigible.grid(row=3, column=2, padx=10, pady=(0,8), sticky="w")

        label(2, 3, "Saldo pendiente")
        self.lbl_saldo_calc = ctk.CTkLabel(self.form, text="0.00", text_color=self.app.COLOR_TEXT)
        self.lbl_saldo_calc.grid(row=3, column=3, padx=10, pady=(0,8), sticky="w")

        label(4, 0, "Estado (calculado)")
        self.lbl_estado_calc = ctk.CTkLabel(self.form, text="Pendiente", text_color=self.app.COLOR_MUTED)
        self.lbl_estado_calc.grid(row=5, column=0, padx=10, pady=(0,8), sticky="w")

        apto_wrap = ctk.CTkFrame(self.form, fg_color="transparent")
        apto_wrap.grid(row=5, column=1, columnspan=3, padx=10, pady=(2, 4), sticky="ew")
        ctk.CTkLabel(
            apto_wrap,
            text="Apto para agendar",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")
        self.lbl_apto_agendar = ctk.CTkLabel(
            apto_wrap,
            text="No apto",
            text_color=self.app.COLOR_RED,
            fg_color=self.app.RED_SOFT_BG,
            corner_radius=999,
            padx=12,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_apto_agendar.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            self.form,
            text="Escribe valores sin puntos ni letras. Al editar, el nuevo abono se suma al pago acumulado.",
            text_color=self.app.COLOR_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=6, column=0, columnspan=4, padx=10, pady=(0, 4), sticky="w")

        self.lbl_pagado_actual.configure(font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_total_exigible.configure(font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_saldo_calc.configure(font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_estado_calc.configure(font=ctk.CTkFont(size=18, weight="bold"))

        self.en_total.bind("<KeyRelease>", self._refresh_form_preview)
        self.en_abono.bind("<KeyRelease>", self._refresh_form_preview)
        self.en_multas.bind("<KeyRelease>", self._refresh_form_preview)
        self.en_total.bind("<KeyRelease>", self._validate_money_live, add="+")
        self.en_abono.bind("<KeyRelease>", self._validate_money_live, add="+")
        self.en_multas.bind("<KeyRelease>", self._validate_money_live, add="+")

        # Botones
        btns = ctk.CTkFrame(self.form, fg_color="transparent")
        btns.grid(row=7, column=0, columnspan=4, padx=10, pady=(6,12), sticky="e")

        def form_btn(text, cb, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                btns,
                text=text,
                height=34,
                corner_radius=10,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cb,
            )

        form_btn("Cancelar", self._cancelar, self.app.COLOR_INPUT_BG, self.app.COLOR_DIVIDER, txt=self.app.COLOR_TEXT)\
            .grid(row=0, column=0, padx=6)
        form_btn("Guardar", self._guardar, self.app.COLOR_GREEN, self.app.GREEN_HOVER)\
            .grid(row=0, column=1, padx=6)

        self._form_mode = "create"
        self._editing_idx = None

    def _show_form(self, mode="create", data=None):
        """Muestra el formulario en modo `create` o `edit` y precarga datos si aplica."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede modificar estados de cuenta.")
            return
        self._form_mode = mode
        if mode == "edit" and data:
            est_name = self._student_name_from_record(data) or self._student_name_for(self._take_estudiante_id(data))
            self.cb_estudiante.configure(state="disabled")
            self.cb_estudiante.set(est_name)
            self.en_total.delete(0, "end"); self.en_total.insert(0, f"{(data.get('montoTotal') or 0):.2f}")
            self._current_paid_base = float(data.get("montoPagado") or 0)
            self.en_abono.delete(0, "end"); self.en_abono.insert(0, "0.00")
            self.en_multas.delete(0, "end"); self.en_multas.insert(0, f"{(data.get('multas') or 0):.2f}")
            try:
                self._editing_idx = self._data.index(data)
            except Exception:
                self._editing_idx = None
        else:
            self._editing_idx = None
            self._current_paid_base = 0.0
            self.cb_estudiante.configure(state="normal")
            self.cb_estudiante.set(self._student_combo_placeholder)
            self.en_total.delete(0, "end"); self.en_total.insert(0, "0.00")
            self.en_abono.delete(0, "end"); self.en_abono.insert(0, "0.00")
            self.en_multas.delete(0, "end"); self.en_multas.insert(0, "0.00")
        self._refresh_student_combo_values("")
        self._refresh_form_preview()
        self.form.grid()

    def _hide_form(self):
        """Oculta el formulario y restablece estados de widgets si aplica."""
        try:
            self.cb_estudiante.configure(state="normal")
        except Exception:
            pass
        self.form.grid_remove()

    def _calc_financials(self, total: float, pagado: float, multas: float) -> Dict[str, Any]:
        """Calcula totales/estado (total exigible, saldo, estado y aptitud)."""
        total_exigible = total + multas
        saldo = total_exigible - pagado
        if total < 0 or pagado < 0 or multas < 0 or pagado > total_exigible:
            estado = "Inválido"
        elif abs(saldo) < 1e-6:
            estado = "Pagado"
            saldo = 0.0
        else:
            estado = "En deuda"
        apto = estado.lower() in {"pagado", "paz y salvo", "al dia", "al día"}
        return {
            "total_exigible": total_exigible,
            "saldo": saldo,
            "estado": estado,
            "apto": apto,
        }

    def _refresh_form_preview(self, _event=None):
        """Actualiza el panel de vista previa (pagado, saldo, estado) en el formulario."""
        try:
            total = self._parse_money(self.en_total.get())
            abono = self._parse_money(self.en_abono.get())
            multas = self._parse_money(self.en_multas.get())
            pagado = max(0.0, float(self._current_paid_base or 0.0) + abono)
            metrics = self._calc_financials(total, pagado, multas)
            self.lbl_pagado_actual.configure(text=f"{pagado:,.2f}")
            self.lbl_total_exigible.configure(text=f"{metrics['total_exigible']:,.2f}")
            self.lbl_saldo_calc.configure(
                text=f"{metrics['saldo']:,.2f}",
                text_color=self.app.COLOR_RED if metrics["saldo"] > 0 else self.app.COLOR_GREEN,
            )
            estado_color = self.app.COLOR_MUTED if metrics["estado"] == "Inválido" else self.app.COLOR_TEXT
            self.lbl_estado_calc.configure(text=metrics["estado"], text_color=estado_color)
            self.lbl_apto_agendar.configure(
                text="Apto" if metrics["apto"] else "No apto",
                fg_color=self.app.GREEN_SOFT_BG if metrics["apto"] else self.app.RED_SOFT_BG,
                text_color=self.app.COLOR_GREEN if metrics["apto"] else self.app.COLOR_RED,
            )
        except Exception:
            self.lbl_pagado_actual.configure(text="0.00")
            self.lbl_total_exigible.configure(text="0.00")
            self.lbl_saldo_calc.configure(text="0.00", text_color=self.app.COLOR_TEXT)
            self.lbl_estado_calc.configure(text="Inválido", text_color=self.app.COLOR_MUTED)
            self.lbl_apto_agendar.configure(text="No apto", fg_color=self.app.RED_SOFT_BG, text_color=self.app.COLOR_RED)

    # ===================== CRUD =====================
    def _nuevo(self):
        """Abre el formulario para crear un nuevo estado de cuenta."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede crear estados de cuenta.")
            return
        self._show_form("create", {})

    def _editar(self):
        """Abre el formulario para editar el registro seleccionado."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede editar estados de cuenta.")
            return
        if self._selected_idx is None:
            self.app._info("Selecciona un registro primero.")
            return
        rec = self._data[self._selected_idx]
        self._show_form("edit", rec)

    def _eliminar(self):
        """Elimina el registro seleccionado (API si existe, o local si no)."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede eliminar estados de cuenta.")
            return
        if self._selected_idx is None:
            self.app._info("Selecciona un registro para eliminar.")
            return
        rec = self._data[self._selected_idx]
        est_name = self._student_name_for(self._take_estudiante_id(rec))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar estado de cuenta de {est_name}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
                self._last_refresh_ts = 0
                self._refrescar(force_refresh=True)
            else:
                if rec in self._all_data:
                    self._all_data.remove(rec)
                else:
                    del self._data[self._selected_idx]
                self.app._info("Registro eliminado (local).")
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    def _cancelar(self):
        """Cancela la creacion/edicion actual y oculta el formulario."""
        self._hide_form()

    def _guardar(self):
        """Valida y guarda cambios del formulario (create/edit)."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede guardar cambios en estados de cuenta.")
            return
        try:
            payload = self._collect_form()
            ok, msg = self._validate(payload)
            if not ok:
                messagebox.showerror("Validación", msg, parent=self)
                return

            if self._form_mode == "create":
                if getattr(self.app, "api", None):
                    created = self.app.api.create("estados-cuenta", payload)  # <- backend calcula 'estado'
                    self.app._info("Estado de cuenta creado.")
                    self._last_refresh_ts = 0
                    self._refrescar(force_refresh=True)
                else:
                    payload["_local_id"] = (max([r.get("_local_id", 0) for r in self._all_data] or [0]) + 1)
                    payload["estado"] = self._preview_estado(payload)  # local-only
                    self._all_data.append(payload)
            else:
                if self._editing_idx is None:
                    self.app._info("No se seleccionó registro para actualizar.")
                    return
                rec = self._data[self._editing_idx]
                if getattr(self.app, "api", None) and rec.get("id"):
                    self.app.api.ensure_not_modified(
                        "estados-cuenta",
                        rec.get("id"),
                        rec,
                        compare_fields=["idEstudiante", "montoTotal", "montoPagado", "multas", "estado"],
                        label="estado de cuenta",
                    )
                    updated = self.app.api.update("estados-cuenta", rec.get("id"), payload)
                    self.app._info("Estado de cuenta actualizado.")
                    self._last_refresh_ts = 0
                    self._refrescar(force_refresh=True)
                else:
                    payload["estado"] = self._preview_estado(payload)  # local-only
                    self._data[self._editing_idx].update(payload)

            self._hide_form()
            if not getattr(self.app, "api", None):
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible guardar:\n{e}", parent=self)

    # ===================== CARGA DATOS =====================
    def _cargar_catalogos_y_listar(self, force_refresh=False):
        """Carga catalogos (estudiantes) y luego lista estados de cuenta desde la API."""
        try:
            if not getattr(self.app, "api", None):
                self._refrescar(local_only=True)
                return

            raw = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []
            if isinstance(raw, dict):
                for key in ("content","items","estudiantes","data","results"):
                    if isinstance(raw.get(key), list):
                        raw = raw[key]
                        break
                else:
                    raw = []

            self.estudiantes = raw
            self.estudiantes_id_to_name = {}
            self.estudiantes_name_to_id = {}

            for e in self.estudiantes:
                eid = e.get("id") or e.get("idEstudiante")
                nombre = "{} {}".format(e.get("nombre",""), e.get("apellido","")).strip()
                if eid is not None and nombre:
                    self.estudiantes_id_to_name[eid] = nombre
                    self.estudiantes_id_to_name[str(eid)] = nombre
                    self.estudiantes_name_to_id[nombre] = eid

            self._refresh_student_combo_values()
            if not self.cb_estudiante.get():
                self.cb_estudiante.set(self._student_combo_placeholder)

            self._refrescar(force_refresh=force_refresh)
        except Exception as e:
            messagebox.showerror("Estados de cuenta", f"No fue posible cargar catálogos:\n{e}", parent=self)

    def _refrescar(self, local_only=False, force_refresh=True):
        """Refresca la data desde la API (o local) respetando un intervalo minimo."""
        if local_only:
            base = self._all_data or self._data
            self._queue_render(self._apply_search(base))
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
            return

        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if not getattr(self.app, "api", None):
            base = self._all_data or self._data
            self._queue_render(self._apply_search(base))
            self.app._info(f"Estados de cuenta: {len(self._data)} registros.")
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                raw = self.app.api.get_all("estados-cuenta", force_refresh=force_refresh) or []
                if isinstance(raw, dict):
                    for key in ("content", "items", "estados-cuenta", "data", "results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []

                def apply_data():
                    self._all_data = raw or []
                    self._queue_render(self._apply_search(self._all_data))
                    self.app._info(f"Estados de cuenta: {len(self._data)} registros.")

                self.after(0, apply_data)
            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: messagebox.showerror("Estados de cuenta", f"No fue posible consultar la API:\n{err}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_loading(self, on=True, text="Actualizando..."):
        """Muestra u oculta un indicador de carga sobre la tabla."""
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

    # ===================== RENDER =====================
    def _apply_colspecs(self, container):
        """Define columnas y configura el grid del contenedor con anchos/pesos."""
        specs = [
            ("Estudiante",   430, 4, "w"),
            ("Curso",        105, 1, "w"),
            ("Multas",        85, 1, "w"),
            ("Total a pagar", 120, 1, "w"),
            ("Pagado",       110, 1, "w"),
            ("Saldo",        100, 1, "w"),
            ("Estado",       110, 1, "w"),
            ("Apto",          90, 1, "w"),
            ("Acciones",     130, 0, "w"),
        ]
        for i, (_, minw, weight, _anchor) in enumerate(specs):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)
        return specs

    def _queue_render(self, rows):
        """Encola un render de tabla con delay (batch) y actualiza `self._data`."""
        self._data = list(rows or [])
        if self._render_after_id:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
        self._render_after_id = self.after(self.RENDER_DELAY_MS, self._flush_render)

    def _flush_render(self):
        """Ejecuta el render programado y limpia el id del job."""
        self._render_after_id = None
        self._set_data(self._data)

    def _render_table(self):
        """Dispara un render completo usando la data actual."""
        self._queue_render(self._data)

    def _row_values(self, rec):
        """Calcula valores derivados para una fila (saldo, estado, apto, colores)."""
        est = self._student_name_from_record(rec) or self._student_name_for(self._take_estudiante_id(rec))
        total = float(rec.get("montoTotal") or 0)
        pagado = float(rec.get("montoPagado") or 0)
        multas = float(rec.get("multas") or 0)
        metrics = self._calc_financials(total, pagado, multas)
        return {
            "est": est,
            "total": total,
            "multas": multas,
            "total_exigible": metrics["total_exigible"],
            "pagado": pagado,
            "saldo": metrics["saldo"],
            "estado": rec.get("estado", metrics["estado"]) or metrics["estado"],
            "apto": metrics["apto"],
            "saldo_color": self.app.COLOR_RED if metrics["saldo"] > 0 else self.app.COLOR_GREEN,
        }

    def _estado_badge_style(self, estado: str):
        """Retorna (bg, fg) para el badge de estado segun el texto del estado."""
        t = str(estado or "").strip().lower()
        if "pagado" in t:
            return self.app.GREEN_SOFT_BG, self.app.COLOR_GREEN
        if any(k in t for k in ("deuda", "mora", "saldo", "venc")):
            return self.app.RED_SOFT_BG, self.app.COLOR_RED
        if "pend" in t:
            return self.app.MUSTARD_SOFT_BG, self.app.MUSTARD_MAIN
        return self.app.COLOR_INPUT_BG, self.app.COLOR_TEXT

    def _apto_badge_style(self, apto: bool):
        """Retorna (bg, fg) para el badge de aptitud (apto/no apto)."""
        if apto:
            return self.app.GREEN_SOFT_BG, self.app.COLOR_GREEN
        return self.app.RED_SOFT_BG, self.app.COLOR_RED

    def _table_columns(self):
        """Define columnas visibles de la tabla (nombre, ancho y alineacion)."""
        return [
            ("Estudiante", 430, "w"),
            ("Curso", 110, "w"),
            ("Multas", 100, "w"),
            ("Total a pagar", 130, "w"),
            ("Pagado", 120, "w"),
            ("Saldo", 120, "w"),
            ("Estado", 120, "center"),
            ("Apto", 100, "center"),
        ]

    def _build_table_shell(self):
        """Crea el Treeview y scrollbars si no existen, y aplica el tema."""
        if getattr(self, "tree", None) and self.tree.winfo_exists():
            return

        for w in self.table.winfo_children():
            w.destroy()
        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "EstadoCuenta.Treeview", rowheight=30)
        cols = [name for name, _w, _a in self._table_columns()]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="EstadoCuenta.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, width, anchor in self._table_columns():
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, minwidth=max(80, int(width * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _e: self._editar())

        self._empty_label = ctk.CTkLabel(self.table, text="Sin registros", text_color=self.app.COLOR_MUTED)
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_label.place_forget()

    def _set_data(self, rows):
        """Carga `rows` en el Treeview por lotes y actualiza totales."""
        self._build_table_shell()
        self._selected_idx = None
        data = list(rows or [])

        self._render_seq += 1
        render_seq = self._render_seq

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_index.clear()

        if not data:
            if self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self._render_totals()
            return

        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.place_forget()

        def paint_batch(start=0):
            if render_seq != self._render_seq:
                return
            if not self.tree.winfo_exists():
                return

            end = min(start + self.ROW_BATCH_SIZE, len(data))
            for idx in range(start, end):
                rec = data[idx]
                values = self._row_values(rec)
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                self.tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        values["est"],
                        f"{values['total']:,.2f}",
                        f"{values['multas']:,.2f}",
                        f"{values['total_exigible']:,.2f}",
                        f"{values['pagado']:,.2f}",
                        f"{values['saldo']:,.2f}",
                        values["estado"],
                        "Apto" if values["apto"] else "No apto",
                    ),
                    tags=("even" if idx % 2 == 0 else "odd",),
                )

            if end < len(data):
                self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))
            else:
                self._render_totals()

        paint_batch(0)

    def _on_tree_select(self, _evt=None):
        """Actualiza el indice seleccionado al cambiar la seleccion del Treeview."""
        sel = self.tree.selection()
        if not sel:
            self._selected_idx = None
            return
        self._selected_idx = self._iid_to_index.get(sel[0])

    def _render_totals(self):
        """Renderiza el recuadro de totales (solo para superadmin)."""
        try:
            if hasattr(self, "_totals_frame") and self._totals_frame is not None:
                self._totals_frame.destroy()
        except Exception:
            pass

        if not getattr(self.app, "is_superadmin", False):
            self._totals_frame = None
            return

        total_total = sum(float(r.get("montoTotal") or 0) for r in self._data)
        total_multas = sum(float(r.get("multas") or 0) for r in self._data)
        total_exigible = total_total + total_multas
        total_pagado = sum(float(r.get("montoPagado") or 0) for r in self._data)
        total_saldo = total_exigible - total_pagado
        saldo_color = self.app.COLOR_RED if total_saldo > 0 else self.app.COLOR_GREEN

        self._totals_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._totals_frame.grid(row=5, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._totals_frame.grid_columnconfigure(0, weight=1)

        box = ctk.CTkFrame(
            self._totals_frame,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=2,
            border_color=self.app.COLOR_RED
        )
        box.grid(row=0, column=0, padx=8, pady=0)
        box.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            box,
            text=f"Totales — Registros: {len(self._data)}",
            text_color=self.app.COLOR_MUTED,
            anchor="center",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 6), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Monto total: {total_total:,.2f}",
            text_color=self.app.COLOR_TEXT,
            anchor="center",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Multas: {total_multas:,.2f}",
            text_color=self.app.COLOR_TEXT,
            anchor="center",
        ).grid(row=1, column=1, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Exigible: {total_exigible:,.2f}",
            text_color=self.app.COLOR_TEXT,
            anchor="center",
        ).grid(row=1, column=2, padx=16, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            box,
            text=f"Pagado / Saldo: {total_pagado:,.2f} / {total_saldo:,.2f}",
            text_color=saldo_color,
            anchor="center",
        ).grid(row=1, column=3, padx=16, pady=(0, 12), sticky="ew")

    # ===================== SELECCIÓN =====================
    def _edit_row(self, idx: int):
        """Atajo para editar una fila por indice (seleccion + abrir formulario)."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede editar estados de cuenta.")
            return
        if self.tree and self.tree.winfo_exists():
            iid = f"r{idx}"
            if iid in self._iid_to_index:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
        self._selected_idx = idx
        self._editing_idx = idx
        self._show_form("edit", self._data[idx])

    def _delete_row(self, idx: int):
        """Atajo para eliminar una fila por indice (seleccion + confirmacion)."""
        if not self.can_edit:
            self.app._info("Solo el superadministrador puede eliminar estados de cuenta.")
            return
        if self.tree and self.tree.winfo_exists():
            iid = f"r{idx}"
            if iid in self._iid_to_index:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
        self._selected_idx = idx
        rec = self._data[idx]
        est = self._student_name_for(self._take_estudiante_id(rec))
        if not messagebox.askyesno("Confirmar", f"¿Eliminar registro de {est}"):
            self.app._info("Operación cancelada.")
            return
        try:
            if getattr(self.app, "api", None) and rec.get("id"):
                self.app.api.delete("estados-cuenta", rec.get("id"))
                self.app._info("Registro eliminado.")
                self._last_refresh_ts = 0
                self._refrescar(force_refresh=True)
            else:
                if rec in self._all_data:
                    self._all_data.remove(rec)
                else:
                    del self._data[idx]
                self.app._info("Registro eliminado (local).")
                self._refrescar(local_only=True)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible eliminar:\n{e}", parent=self)

    # ===================== HELPERS FORM =====================
    def _parse_money(self, s: str) -> float:
        """
        Acepta: "1.234,56" | "1,234.56" | "1234.56" | "1234".
        Limpia símbolos y normaliza separadores antes de convertir a float.
        """
        if s is None:
            return 0.0
        s = str(s).strip()
        if s == "":
            return 0.0
        for ch in "$₱€£% ":
            s = s.replace(ch, "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            try:
                return float(s.replace(",", ""))
            except Exception:
                raise ValueError("Valor numérico inválido")

    def _collect_form(self) -> Dict[str, Any]:
        """
        JSON esperado por el backend:
        {
          "idEstudiante": int,
          "montoTotal": float,
          "montoPagado": float,
          "multas": float
        }
        (el 'estado' lo calcula el servidor; NO se envía)
        """
        # Estudiante -> id
        est_name = (self.cb_estudiante.get() or "").strip()
        if est_name.lower() == self._student_combo_placeholder.lower():
            est_name = ""
        id_est = self.estudiantes_name_to_id.get(est_name)

        total = self._parse_money(self.en_total.get())
        abono = self._parse_money(self.en_abono.get())
        multas = self._parse_money(self.en_multas.get())
        pagado = max(0.0, float(self._current_paid_base or 0.0) + abono)

        return {
            "idEstudiante": id_est,
            "montoTotal": total,
            "montoPagado": pagado,
            "multas": multas,
        }

    def _validate(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Reglas mínimas en el front (el back valida de nuevo):
          - idEstudiante obligatorio (>0)
          - montos >= 0
          - montoPagado <= montoTotal
        """
        # idEstudiante
        id_est = payload.get("idEstudiante")
        if id_est in (None, "", 0):
            return (False, "Debes seleccionar un estudiante válido.")
        if self._form_mode == "create":
            for rec in (self._all_data or []):
                current_id = self._take_estudiante_id(rec)
                if current_id not in (None, "", 0) and str(current_id) == str(id_est):
                    return (False, "Ese estudiante ya tiene un estado de cuenta registrado.")

        # montos
        try:
            total = float(payload.get("montoTotal", 0))
            pagado = float(payload.get("montoPagado", 0))
            multas = float(payload.get("multas", 0))
        except Exception:
            return (False, "Los montos deben ser numéricos.")

        if total < 0 or pagado < 0 or multas < 0:
            return (False, "Los montos no pueden ser negativos.")
        if pagado > (total + multas):
            return (False, "El monto pagado no puede superar el monto total + multas.")

        return (True, "")

    def _validate_money_live(self, event=None):
        """Filtra caracteres no numericos en vivo en inputs de dinero (., , y digitos)."""
        widget = getattr(event, "widget", None)
        if widget is None:
            return
        current = widget.get()
        filtered = "".join(ch for ch in current if ch.isdigit() or ch in ",.")
        if filtered != current:
            pos = widget.index("insert")
            widget.delete(0, "end")
            widget.insert(0, filtered)
            try:
                widget.icursor(min(pos - (len(current) - len(filtered)), len(filtered)))
            except Exception:
                pass

    def _preview_estado(self, payload: Dict[str, Any]) -> str:
        """Solo para modo local sin API: emula el cálculo del backend."""
        try:
            total = float(payload.get("montoTotal") or 0)
            pagado = float(payload.get("montoPagado") or 0)
            multas = float(payload.get("multas") or 0)
            return self._calc_financials(total, pagado, multas)["estado"]
        except Exception:
            pass
        return "Inválido"

# Export explícito por si usas import *
__all__ = ["EstadosCuentaView"]
