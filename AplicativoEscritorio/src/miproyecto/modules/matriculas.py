"""
Módulo de Matrículas / Solicitudes.
"""

import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from modules.base import BaseModuleFrame
from modules.treeview_theme import configure_treeview_style, solid_color


def _normalize_sede_label(value) -> str:
    txt = str(value or "").strip().lower()
    if not txt:
        return str(value or "").strip()

    txt_fold = (
        txt.replace("á", "a").replace("Ã¡", "a")
        .replace("é", "e").replace("Ã©", "e")
        .replace("í", "i").replace("Ã­", "i")
        .replace("ó", "o").replace("Ã³", "o")
        .replace("ú", "u").replace("Ãº", "u")
        .replace("ü", "u").replace("Ã¼", "u")
        .replace("ñ", "n").replace("Ã±", "n")
    )
    txt_fold = " ".join(txt_fold.split())
    compact = txt_fold.replace(" ", "")

    if compact in {"1demayo", "1mayo", "1rodemayo", "1erdemayo"} or "mayo" in txt_fold or "kennedy" in txt_fold:
        return "1 de Mayo"
    if "eden" in txt_fold:
        return "El Eden"
    if txt in {"1 de mayo", "1demayo"}:
        return "1 de Mayo"
    if txt in {"el eden", "el edén", "el edÃ©n", "eden", "edén", "edÃ©n"}:
        return "El Eden"
    return str(value or "").strip()


def _norm_enum(value) -> str:
    return str(value or "").strip().upper()


def _format_date(value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    s = str(value).strip()
    if not s:
        return "—"
    if "T" in s:
        s = s.split("T", 1)[0]
    if " " in s:
        s = s.split(" ", 1)[0]
    return s[:10] if len(s) >= 10 else s


def _parse_datetime(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    s = str(value).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_money(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    for ch in (",", ".", "$", " "):
        s = s.replace(ch, "")
    try:
        return float(s)
    except Exception:
        return 0.0


class _ConfirmarPagoDialog(ctk.CTkToplevel):
    def __init__(self, master, app, *, on_confirm):
        super().__init__(master)
        self.app = app
        self.on_confirm = on_confirm

        self.title("Confirmar pago (efectivo)")
        self.geometry("520x360")
        self.minsize(480, 320)
        try:
            self.configure(fg_color=self.app.COLOR_BG)
        except Exception:
            pass
        try:
            self.transient(master.winfo_toplevel())
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass

        wrap = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        wrap.pack(fill="both", expand=True, padx=16, pady=16)
        wrap.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            wrap,
            text="Confirmar pago en efectivo",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(14, 8), sticky="w")

        ctk.CTkLabel(wrap, text="Valor pagado", text_color=self.app.COLOR_MUTED, anchor="w") \
            .grid(row=1, column=0, padx=14, pady=(6, 4), sticky="w")
        self.en_valor = ctk.CTkEntry(
            wrap,
            placeholder_text="Ej: 250000",
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.en_valor.grid(row=1, column=1, padx=14, pady=(6, 4), sticky="ew")

        ctk.CTkLabel(wrap, text="Observación (opcional)", text_color=self.app.COLOR_MUTED, anchor="w") \
            .grid(row=2, column=0, padx=14, pady=(10, 4), sticky="w")
        self.en_obs = ctk.CTkEntry(
            wrap,
            placeholder_text="Ej: pagó en caja / recibo #123",
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            text_color=self.app.COLOR_TEXT,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        self.en_obs.grid(row=2, column=1, padx=14, pady=(10, 4), sticky="ew")

        note = (
            "Escribe el valor sin letras.\n"
            "Al confirmar, se habilitará el proceso de contratos (según backend)."
        )
        ctk.CTkLabel(wrap, text=note, text_color=self.app.COLOR_MUTED, justify="left", anchor="w") \
            .grid(row=3, column=0, columnspan=2, padx=14, pady=(10, 0), sticky="w")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=2, padx=14, pady=(16, 14), sticky="e")

        ctk.CTkButton(
            btns,
            text="Cancelar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self.destroy,
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btns,
            text="Confirmar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_GREEN,
            hover_color=self.app.GREEN_HOVER,
            text_color="#ffffff",
            command=self._confirm,
        ).grid(row=0, column=1, padx=6)

    def _confirm(self):
        valor = _parse_money(self.en_valor.get())
        obs = (self.en_obs.get() or "").strip()
        if valor <= 0:
            messagebox.showwarning(
                "Confirmar pago",
                "Ingresa un valor pagado válido (> 0).",
                parent=self,
            )
            return
        try:
            if callable(self.on_confirm):
                self.on_confirm(valor, obs)
        finally:
            try:
                self.destroy()
            except Exception:
                pass


class _NuevaSolicitudDialog(ctk.CTkToplevel):
    def __init__(self, master, app, *, sedes, on_create):
        super().__init__(master)
        self.app = app
        self.sedes = list(sedes or [])
        self.on_create = on_create

        self.title("Nueva solicitud (HaroGestion)")
        self.geometry("640x520")
        self.minsize(620, 500)
        try:
            self.configure(fg_color=self.app.COLOR_BG)
        except Exception:
            pass
        try:
            self.transient(master.winfo_toplevel())
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass

        wrap = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        wrap.pack(fill="both", expand=True, padx=16, pady=16)
        wrap.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            wrap,
            text="Registrar solicitud de matrícula",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, padx=14, pady=(14, 8), sticky="w")

        def label(text, r, c):
            ctk.CTkLabel(wrap, text=text, text_color=self.app.COLOR_MUTED, anchor="w") \
                .grid(row=r, column=c, padx=14, pady=(8, 4), sticky="w")

        def entry(ph, r, c, span=1):
            e = ctk.CTkEntry(
                wrap,
                placeholder_text=ph,
                height=36,
                corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                text_color=self.app.COLOR_TEXT,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )
            e.grid(row=r, column=c, columnspan=span, padx=14, pady=(0, 6), sticky="ew")
            return e

        label("Documento", 1, 0)
        self.en_doc = entry("Ej: 1012345678", 2, 0)
        label("Nombre", 1, 1)
        self.en_nombre = entry("Ej: Laura", 2, 1)
        label("Apellido", 1, 2)
        self.en_apellido = entry("Ej: Gómez", 2, 2)
        label("Teléfono", 1, 3)
        self.en_tel = entry("Ej: 3001234567", 2, 3)

        label("Correo", 3, 0)
        self.en_correo = entry("correo@dominio.com", 4, 0, span=2)
        label("Categoría", 3, 2)
        self.cb_cat = ctk.CTkComboBox(wrap, values=["A2", "B1", "C1", "A2 y B1", "A2 - C1"], width=120)
        self.cb_cat.set("A2")
        self.cb_cat.grid(row=4, column=2, padx=14, pady=(0, 6), sticky="ew")
        label("Sede", 3, 3)
        self.cb_sede = ctk.CTkComboBox(wrap, values=self.sedes or ["—"], width=160)
        self.cb_sede.set((self.sedes or ["—"])[0])
        self.cb_sede.grid(row=4, column=3, padx=14, pady=(0, 6), sticky="ew")

        label("Método de pago", 5, 0)
        self.cb_metodo = ctk.CTkComboBox(wrap, values=["EFECTIVO"], width=160)
        self.cb_metodo.set("EFECTIVO")
        try:
            self.cb_metodo.configure(state="disabled")
        except Exception:
            pass
        self.cb_metodo.grid(row=6, column=0, padx=14, pady=(0, 6), sticky="ew")

        label("Estado pago", 5, 1)
        self.cb_estado_pago = ctk.CTkComboBox(wrap, values=["PENDIENTE", "CONFIRMADO"], width=160)
        self.cb_estado_pago.set("PENDIENTE")
        self.cb_estado_pago.grid(row=6, column=1, padx=14, pady=(0, 6), sticky="ew")

        label("Valor pagado", 5, 2)
        self.en_valor = entry("0", 6, 2)
        label("Observación", 5, 3)
        self.en_obs = entry("", 6, 3)

        ctk.CTkLabel(
            wrap,
            text="Origen registro: HAROGESTION",
            text_color=self.app.COLOR_MUTED,
            anchor="w",
        ).grid(row=7, column=0, columnspan=4, padx=14, pady=(10, 0), sticky="w")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.grid(row=8, column=0, columnspan=4, padx=14, pady=(18, 14), sticky="e")

        ctk.CTkButton(
            btns,
            text="Cancelar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self.destroy,
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btns,
            text="Crear",
            height=36,
            corner_radius=12,
            fg_color=self.app.MUSTARD_MAIN,
            hover_color=self.app.MUSTARD_HOVER,
            text_color="#111111",
            command=self._create,
        ).grid(row=0, column=1, padx=6)

    def _create(self):
        doc = (self.en_doc.get() or "").strip()
        if not doc:
            messagebox.showwarning("Nueva solicitud", "El documento es obligatorio.", parent=self)
            return
        nombre = (self.en_nombre.get() or "").strip()
        apellido = (self.en_apellido.get() or "").strip()
        tel = (self.en_tel.get() or "").strip()
        correo = (self.en_correo.get() or "").strip()
        categoria = (self.cb_cat.get() or "").strip()
        sede = (self.cb_sede.get() or "").strip()
        metodo = _norm_enum(self.cb_metodo.get())
        estado_pago = _norm_enum(self.cb_estado_pago.get())
        valor = _parse_money(self.en_valor.get())
        obs = (self.en_obs.get() or "").strip()

        payload = {
            "origenRegistro": "HAROGESTION",
            "metodoPago": metodo,
            "estadoPago": estado_pago,
            "valorPagado": valor,
            "observacionPago": obs,
            "sede": sede,
            "categoria": categoria,
            "estudiante": {
                "numeroDocumento": doc,
                "nombre": nombre,
                "apellido": apellido,
                "telefono": tel,
                "email": correo,
            },
        }
        try:
            if callable(self.on_create):
                self.on_create(payload)
        finally:
            try:
                self.destroy()
            except Exception:
                pass


class MatriculasView(BaseModuleFrame):
    """
    Solicitudes / prematrículas:
      - Confirmar pago manual (efectivo) + habilitar contratos
      - Enviar / reenviar link de contratos por correo
      - Enviar link de contratos por chatbot (solo si prospecto activo)
      - Generar link de contratos (copiar al portapapeles)
    """

    # Intenta con y sin prefijo "api/" (dependiendo de cómo se haya configurado base_url).
    RESOURCE_CANDIDATES = (
        "procesos-matricula",
        "solicitudes-matricula",
        "prematriculas",
        "pre-matriculas",
        "matriculas",
        "api/procesos-matricula",
        "api/solicitudes-matricula",
        "api/prematriculas",
        "api/pre-matriculas",
        "api/matriculas",
    )

    # Sufijos que intentará (PATCH o POST) para cada acción
    ACTIONS = {
        "confirmar_pago": (
            "confirmar-pago-manual-y-contratos",
            "confirmar-pago-manual",
            "confirmar-pago",
            "confirmarPagoManualYHabilitarContratos",
            "confirmarPagoManual",
            "confirmarPago",
        ),
        "enviar_correo": (
            "enviar-enlace-contratos-correo",
            "enviar-enlace-contrato-correo",
            "enviar-contratos-correo",
            "enviar-contrato-correo",
            "enviarEnlaceContratosCorreo",
        ),
        "enviar_chatbot": (
            "enviar-enlace-contratos-chatbot",
            "enviar-enlace-contrato-chatbot",
            "enviar-contratos-chatbot",
            "enviar-contrato-chatbot",
            "enviarEnlaceContratosChatbot",
        ),
        "es_prospecto": (
            "prospectos/activo",
            "prospectos-activos",
            "chatbot/prospectos/activo",
        ),
    }

    MIN_REFRESH_INTERVAL = 500
    DEBOUNCE_MS = 250
    RENDER_DELAY_MS = 16
    TREE_INSERT_CHUNK = 250
    TREE_INSERT_DELAY = 1
    # Back-end: solicitudes de EFECTIVO vencen en ~1 hora. Aquí solo mostramos alerta (no borramos desde el desktop).
    PAYMENT_EXPIRY_MINUTES = 60
    PAYMENT_WARNING_MINUTES = 15
    AUTO_SWEEP_MS = 60_000

    def __init__(self, master):
        super().__init__(master, "matrículas", "Solicitudes de matrícula y gestión de contratos")

        self._resource = None

        self._all_data = []
        self._data = []
        self._selected_idx = None
        self._iid_to_index = {}

        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._loading_overlay = None
        self._last_refresh_ts = 0
        self._auto_sweep_after_id = None
        self._expiry_delete_inflight = set()
        self._expiry_alert_text = None

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure(6, weight=1)

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

        action_btn("＋ Nueva", self._nuevo, self.app.COLOR_GREEN, self.app.GREEN_HOVER).grid(row=0, column=0, padx=6)
        action_btn("✔ Confirmar pago", self._confirmar_pago, self.app.MUSTARD_MAIN, self.app.MUSTARD_HOVER, txt="#111111")\
            .grid(row=0, column=1, padx=6)
        action_btn("✉ Enviar correo", self._enviar_correo, self.app.COLOR_BLUE, self.app.BLUE_HOVER).grid(row=0, column=2, padx=6)
        action_btn("💬 Enviar chatbot", self._enviar_chatbot, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER).grid(row=0, column=3, padx=6)
        action_btn("🔗 Generar link", self._generar_link_contratos, self.app.COLOR_BLUE, self.app.BLUE_HOVER).grid(row=0, column=4, padx=6)
        action_btn("↻ Refrescar", self._refrescar, self.app.COLOR_RED, self.app.RED_HOVER).grid(row=0, column=5, padx=6)

        # ===== Filtros =====
        self.filters = self._make_filters_bar(self)
        self.filters.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")

        self.expiry_alert = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            justify="left",
            corner_radius=10,
            fg_color=self.app.COLOR_PANEL,
            text_color=self.app.COLOR_MUTED,
            padx=12,
            pady=8,
        )
        self.expiry_alert.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.expiry_alert.grid_remove()

        # ===== Tabla =====
        self.table = ctk.CTkFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.table.grid_rowconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        self._COLS = [
            ("Estudiante", 240),
            ("Documento", 130),
            ("Correo", 210),
            ("Teléfono", 130),
            ("Categoría", 90),
            ("Sede", 140),
            ("Origen", 120),
            ("Método pago", 120),
            ("Estado pago", 120),
            ("Contrato", 140),
            ("Creación", 120),
        ]
        self._build_tree()

        self.after(150, self._refrescar)
        self.after(1000, self._schedule_auto_sweep)

    def destroy(self):
        if self._auto_sweep_after_id:
            try:
                self.after_cancel(self._auto_sweep_after_id)
            except Exception:
                pass
            self._auto_sweep_after_id = None
        return super().destroy()

    # =====================================================
    #                    FILTROS
    # =====================================================
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        bar.grid_columnconfigure(0, weight=1)
        for c in range(1, 7):
            bar.grid_columnconfigure(c, weight=0)

        def entry(ph):
            return ctk.CTkEntry(
                bar,
                placeholder_text=ph,
                height=36,
                corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG,
                text_color=self.app.COLOR_TEXT,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )

        self.f_buscar = entry("Nombre, documento, correo o Teléfono")
        self.f_buscar.grid(row=0, column=0, padx=(12, 8), pady=10, sticky="ew")

        self.f_origen = ctk.CTkComboBox(bar, values=["Todos", "CHATBOT", "HAROGESTION"], width=140)
        self.f_origen.set("Todos")
        self.f_origen.grid(row=0, column=1, padx=8, pady=10, sticky="w")

        # Filtro mejorado: el backend ahora maneja EFECTIVO y también pagos en estado PENDIENTE.
        # Permitimos filtrar por Método si el admin necesita ver solo EFECTIVO o solo EPAYCO.
        self.f_metodo = ctk.CTkComboBox(bar, values=["Todos", "EFECTIVO", "EPAYCO"], width=140)
        self.f_metodo.set("Todos")
        self.f_metodo.grid(row=0, column=2, padx=8, pady=10, sticky="w")

        self.f_pago = ctk.CTkComboBox(bar, values=["Todos", "PENDIENTE", "CONFIRMADO", "RECHAZADO"], width=140)
        self.f_pago.set("Todos")
        self.f_pago.grid(row=0, column=3, padx=8, pady=10, sticky="w")

        self.f_contrato = ctk.CTkComboBox(
            bar,
            values=["Todos", "NO_HABILITADO", "PENDIENTE_FIRMA", "FIRMADO"],
            width=160,
        )
        self.f_contrato.set("Todos")
        self.f_contrato.grid(row=0, column=4, padx=8, pady=10, sticky="w")

        # Por defecto esta vista muestra solo "Caja": EFECTIVO + pagos PENDIENTE (por si el webhook falla).
        self.ck_solo_caja = ctk.CTkCheckBox(
            bar,
            text="Solo caja",
            text_color=self.app.COLOR_TEXT,
            fg_color=getattr(self.app, "MUSTARD_MAIN", "#D4A017"),
            border_color=self.app.COLOR_DIVIDER,
            hover_color=self.app.COLOR_DIVIDER,
        )
        try:
            self.ck_solo_caja.select()
        except Exception:
            pass
        self.ck_solo_caja.grid(row=0, column=5, padx=8, pady=10, sticky="w")

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=0, column=6, padx=(8, 12), pady=10, sticky="e")

        ctk.CTkButton(
            btns,
            text="Limpiar",
            height=36,
            corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=self._clear_filters,
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btns,
            text="Buscar",
            height=36,
            corner_radius=10,
            fg_color=self.app.MUSTARD_MAIN,
            hover_color=self.app.MUSTARD_HOVER,
            text_color="#111111",
            command=self._apply_filters_now,
        ).grid(row=0, column=1, padx=6)

        self.f_buscar.bind("<KeyRelease>", lambda _e: self._debounced_apply_filters())
        self.f_origen.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters_now())
        self.f_metodo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters_now())
        self.f_pago.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters_now())
        self.f_contrato.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters_now())
        self.ck_solo_caja.configure(command=self._apply_filters_now)
        return bar

    def _collect_filters(self):
        return {
            "q": (self.f_buscar.get() or "").strip(),
            "origen": _norm_enum(self.f_origen.get()),
            "metodo": _norm_enum(self.f_metodo.get()),
            "pago": _norm_enum(self.f_pago.get()),
            "contrato": _norm_enum(self.f_contrato.get()),
            "solo_caja": bool(getattr(self, "ck_solo_caja", None) and self.ck_solo_caja.get()),
        }

    def _clear_filters(self):
        self.f_buscar.delete(0, "end")
        self.f_origen.set("Todos")
        self.f_metodo.set("Todos")
        self.f_pago.set("Todos")
        self.f_contrato.set("Todos")
        try:
            self.ck_solo_caja.select()
        except Exception:
            pass
        self._apply_filters_now()

    def _debounced_apply_filters(self):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._apply_filters_now)

    def _apply_filters_now(self):
        self._data = self._apply_filters(self._all_data, self._collect_filters())
        self._refresh_expiry_alert()
        self._queue_render(self._data)

    def _allowed_admin_sede(self) -> str:
        if getattr(self.app, "is_superadmin", False):
            return ""
        return _normalize_sede_label(getattr(self.app, "current_admin_sede", None))

    def _apply_filters(self, data_list, f):
        term = (f.get("q") or "").strip().lower()
        origen = f.get("origen") or ""
        metodo = f.get("metodo") or ""
        pago = f.get("pago") or ""
        contrato = f.get("contrato") or ""
        solo_caja = bool(f.get("solo_caja"))
        allowed_sede = self._allowed_admin_sede()

        out = []
        for rec in (data_list or []):
            sede = _normalize_sede_label(self._take_sede(rec))
            if allowed_sede and sede != allowed_sede:
                continue

            # "Solo caja" = EFECTIVO + pagos en estado PENDIENTE (cualquier medio).
            if solo_caja:
                mp = self._take_metodo_pago(rec)
                ep = self._take_estado_pago(rec)
                if mp != "EFECTIVO" and ep != "PENDIENTE":
                    continue

            if origen not in ("", "TODOS") and self._take_origen(rec) != origen:
                continue
            if metodo not in ("", "TODOS") and self._take_metodo_pago(rec) != metodo:
                continue
            if pago not in ("", "TODOS") and self._take_estado_pago(rec) != pago:
                continue
            if contrato not in ("", "TODOS") and self._take_estado_contrato(rec) != contrato:
                continue

            if term:
                hay = " ".join(
                    [
                        self._take_student_name(rec),
                        self._take_doc(rec),
                        self._take_email(rec),
                        self._take_phone(rec),
                        self._take_sede(rec),
                    ]
                ).lower()
                if term not in hay:
                    continue
            out.append(rec)
        return out

    # =====================================================
    #                     TREEVIEW
    # =====================================================
    def _build_tree(self):
        style = ttk.Style()
        palette = configure_treeview_style(style, self.app, "Haro.Matriculas.Treeview", rowheight=30)

        cols = [c[0] for c in self._COLS]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Haro.Matriculas.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(self.table, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(self.table, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, w in self._COLS:
            self.tree.heading(name, text=name)
            anchor = "w"
            if name in {"Categoría", "Origen", "Método pago", "Estado pago", "Contrato", "Creación"}:
                anchor = "center"
            self.tree.column(name, width=w, minwidth=max(70, int(w * 0.8)), stretch=False, anchor=anchor)

        self.tree.tag_configure("even", background=palette["even"], foreground=palette["text"])
        self.tree.tag_configure("odd", background=palette["odd"], foreground=palette["text"])
        self.tree.tag_configure(
            "pago_pendiente",
            foreground=solid_color(getattr(self.app, "MUSTARD_MAIN", "#D4A017"), "#D4A017"),
        )
        self.tree.tag_configure(
            "pago_confirmado",
            foreground=solid_color(getattr(self.app, "COLOR_GREEN", "#2e7d32"), "#2e7d32"),
        )
        self.tree.tag_configure(
            "pago_rechazado",
            foreground=solid_color(getattr(self.app, "COLOR_RED", "#E53935"), "#E53935"),
        )
        self.tree.tag_configure(
            "expira_pronto",
            background="#FFF3CD",
            foreground="#7A4E00",
        )
        self.tree.tag_configure(
            "expirada",
            background="#FDE2E1",
            foreground="#8B1E1E",
        )

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _e: self._ver_detalle())

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

    def _set_data(self, rows):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_index.clear()
        self._selected_idx = None

        data = list(rows or [])
        if not data:
            if self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.place_forget()

        def insert_chunk(start=0):
            end = min(start + self.TREE_INSERT_CHUNK, len(data))
            for idx in range(start, end):
                rec = data[idx]
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                pago_tag = self._payment_tag(self._take_estado_pago(rec))
                timing_tag = self._timing_tag(rec)
                tags = ("even" if idx % 2 == 0 else "odd", pago_tag, timing_tag)
                self.tree.insert("", "end", iid=iid, values=self._row_values(rec), tags=tags)
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    @staticmethod
    def _payment_tag(estado_pago: str) -> str:
        ep = _norm_enum(estado_pago)
        if ep in {"CONFIRMADO", "PAGADO", "OK"}:
            return "pago_confirmado"
        if ep in {"RECHAZADO", "CANCELADO", "ANULADO"}:
            return "pago_rechazado"
        return "pago_pendiente"

    def _timing_tag(self, rec) -> str:
        status = self._payment_deadline_status(rec)
        if status == "expired":
            return "expirada"
        if status == "warning":
            return "expira_pronto"
        return ""

    # =====================================================
    #                     HELPERS
    # =====================================================
    @staticmethod
    def _unwrap_list(raw):
        if isinstance(raw, dict):
            for key in ("content", "items", "data", "results", "solicitudes", "prematriculas", "matriculas"):
                val = raw.get(key)
                if isinstance(val, list):
                    return val
            return []
        if isinstance(raw, list):
            return raw
        return []

    @staticmethod
    def _take_id(rec) -> Optional[Any]:
        if not isinstance(rec, dict):
            return None
        return rec.get("id") or rec.get("procesoId") or rec.get("idProceso") or rec.get("solicitudId")

    def _take_student_obj(self, rec) -> Dict[str, Any]:
        if not isinstance(rec, dict):
            return {}
        stu = rec.get("estudiante")
        return stu if isinstance(stu, dict) else {}

    def _take_student_name(self, rec) -> str:
        if not isinstance(rec, dict):
            return "—"
        for key in ("nombreEstudiante", "estudianteNombre", "nombre_estudiante"):
            val = rec.get(key)
            if val:
                return str(val).strip()
        stu = self._take_student_obj(rec)
        nombre = str(stu.get("nombre") or "").strip()
        apellido = str(stu.get("apellido") or "").strip()
        full = f"{nombre} {apellido}".strip()
        return full or "—"

    def _take_doc(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("numeroDocumento", "documento", "doc", "dni", "cc"):
            val = rec.get(key)
            if val:
                return str(val).strip()
        stu = self._take_student_obj(rec)
        for key in ("numeroDocumento", "documento", "doc", "dni", "cc", "cedula"):
            val = stu.get(key)
            if val:
                return str(val).strip()
        return ""

    def _take_email(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("correo", "email", "correoEstudiante", "emailEstudiante"):
            val = rec.get(key)
            if val:
                return str(val).strip()
        stu = self._take_student_obj(rec)
        val = stu.get("email") or stu.get("correo")
        return str(val).strip() if val else ""

    def _take_phone(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("telefono", "tel", "celular", "phone", "telefonoEstudiante"):
            val = rec.get(key)
            if val:
                return str(val).strip()
        stu = self._take_student_obj(rec)
        val = stu.get("telefono") or stu.get("celular") or stu.get("phone")
        return str(val).strip() if val else ""

    def _take_categoria(self, rec) -> str:
        if not isinstance(rec, dict):
            return "—"
        for key in ("categoria", "categoriaLicencia", "licenciaCategoria"):
            val = rec.get(key)
            if val:
                return str(val).strip().upper()
        stu = self._take_student_obj(rec)
        for key in ("categoria", "categoriaLicencia", "licenciaCategoria"):
            val = stu.get(key)
            if val:
                return str(val).strip().upper()
        return "—"

    def _take_sede(self, rec) -> str:
        if not isinstance(rec, dict):
            return "—"
        for key in ("sede", "sedeNombre", "nombreSede", "campus"):
            val = rec.get(key)
            if val:
                return str(val.get("nombre") if isinstance(val, dict) else val).strip()
        stu = self._take_student_obj(rec)
        val = stu.get("sede") or stu.get("sedeNombre") or stu.get("nombreSede")
        if isinstance(val, dict):
            for k2 in ("nombre", "name", "descripcion"):
                v2 = val.get(k2)
                if v2:
                    return str(v2).strip()
        return str(val).strip() if val else "—"

    def _take_origen(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("origenRegistro", "origen", "origenMatricula", "origen_matricula"):
            val = rec.get(key)
            if val:
                return _norm_enum(val)
        return ""

    def _take_metodo_pago(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("metodoPago", "metodo_pago", "medioPago", "medio_pago"):
            val = rec.get(key)
            if val:
                return self._map_metodo_pago(val)
        return ""

    def _map_metodo_pago(self, raw) -> str:
        v = _norm_enum(raw)
        if not v:
            return ""
        # Normaliza valores antiguos o alternos.
        if v in {"CASH"}:
            return "EFECTIVO"
        compact = v.replace("-", "").replace("_", "").replace(" ", "")
        if "EPAYCO" in compact:
            return "EPAYCO"
        if "EFECTIVO" in compact:
            return "EFECTIVO"
        return v

    def _take_estado_pago(self, rec) -> str:
        if not isinstance(rec, dict):
            return "PENDIENTE"
        for key in ("estadoPago", "estado_pago", "pagoEstado", "paymentStatus"):
            val = rec.get(key)
            if val is not None and str(val).strip() != "":
                return self._map_estado_pago(val)
        return "PENDIENTE"

    def _map_estado_pago(self, raw) -> str:
        v = _norm_enum(raw)
        if not v:
            return "PENDIENTE"
        # Mapea estados internos (APPROVED, PENDING, etc.) a los estados UI.
        if v in {"APPROVED", "PAID", "CONFIRMED", "OK", "APROBADO", "CONFIRMADO"}:
            return "CONFIRMADO"
        if v in {"PENDING", "PENDIENTE"}:
            return "PENDIENTE"
        if v in {"REJECTED", "RECHAZADO"}:
            return "RECHAZADO"
        if v in {"CANCELLED", "CANCELADO"}:
            return "CANCELADO"
        return v

    def _take_estado_contrato(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("estadoContrato", "estado_contrato", "contractStatus"):
            val = rec.get(key)
            if val:
                return _norm_enum(val)
        return ""

    def _take_fecha_creacion(self, rec) -> str:
        if not isinstance(rec, dict):
            return "—"
        for key in ("fechaCreacion", "createdAt", "fecha", "fechaRegistro"):
            val = rec.get(key)
            if val:
                return _format_date(val)
        return "—"

    def _take_created_at_dt(self, rec) -> Optional[datetime]:
        if not isinstance(rec, dict):
            return None
        for key in ("createdAt", "fechaCreacion", "fecha", "fechaRegistro"):
            dt = _parse_datetime(rec.get(key))
            if dt:
                return dt
        return None

    def _is_pending_payment(self, rec) -> bool:
        return self._take_estado_pago(rec) == "PENDIENTE"

    def _payment_deadline_status(self, rec, now_utc: Optional[datetime] = None) -> str:
        if not self._is_pending_payment(rec):
            return ""
        # La expiración automática aplica principalmente para solicitudes en EFECTIVO.
        if self._take_metodo_pago(rec) != "EFECTIVO":
            return ""
        created_at = self._take_created_at_dt(rec)
        if not created_at:
            return ""
        now_utc = now_utc or datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=self.PAYMENT_EXPIRY_MINUTES)
        warning_at = expires_at - timedelta(minutes=self.PAYMENT_WARNING_MINUTES)
        if now_utc >= expires_at:
            return "expired"
        if now_utc >= warning_at:
            return "warning"
        return ""

    def _minutes_until_expiry(self, rec, now_utc: Optional[datetime] = None) -> Optional[int]:
        created_at = self._take_created_at_dt(rec)
        if not created_at:
            return None
        now_utc = now_utc or datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=self.PAYMENT_EXPIRY_MINUTES)
        seconds_left = (expires_at - now_utc).total_seconds()
        return int(seconds_left // 60)

    def _build_expiry_alert_text(self, data_list) -> str:
        now_utc = datetime.now(timezone.utc)
        warning_count = 0
        expired_count = 0
        nearest_minutes = None
        for rec in data_list or []:
            status = self._payment_deadline_status(rec, now_utc=now_utc)
            if status == "expired":
                expired_count += 1
                continue
            if status == "warning":
                warning_count += 1
                minutes_left = self._minutes_until_expiry(rec, now_utc=now_utc)
                if minutes_left is not None:
                    nearest_minutes = minutes_left if nearest_minutes is None else min(nearest_minutes, minutes_left)

        parts = []
        if expired_count:
            parts.append(f"{expired_count} solicitud(es) vencidas (se eliminarán automáticamente)")
        if warning_count:
            detail = f"{warning_count} por vencer"
            if nearest_minutes is not None:
                detail += f" (la más próxima vence en {max(0, nearest_minutes)} min)"
            parts.append(detail)
        return " | ".join(parts)

    def _refresh_expiry_alert(self):
        text = self._build_expiry_alert_text(self._data)
        self._expiry_alert_text = text
        if not text:
            self.expiry_alert.grid_remove()
            return
        is_critical = "vencidas" in text
        self.expiry_alert.configure(
            text=f"Alerta de pagos: {text}",
            fg_color="#FDE2E1" if is_critical else "#FFF3CD",
            text_color="#8B1E1E" if is_critical else "#7A4E00",
        )
        self.expiry_alert.grid()

    def _schedule_auto_sweep(self):
        if self._auto_sweep_after_id:
            try:
                self.after_cancel(self._auto_sweep_after_id)
            except Exception:
                pass
        self._auto_sweep_after_id = self.after(self.AUTO_SWEEP_MS, self._run_auto_sweep)

    def _run_auto_sweep(self):
        self._auto_sweep_after_id = None
        self._refrescar(force_refresh=True)
        self._schedule_auto_sweep()

    def _delete_expired_pending_async(self):
        rows = list(self._all_data or [])
        now_utc = datetime.now(timezone.utc)
        expired = []
        for rec in rows:
            if self._payment_deadline_status(rec, now_utc=now_utc) != "expired":
                continue
            proceso_id = self._take_id(rec)
            if proceso_id is None or proceso_id in self._expiry_delete_inflight:
                continue
            expired.append((proceso_id, rec))

        if not expired or not self.app.api or not self._resource:
            return

        def worker():
            removed_ids = []
            for proceso_id, _rec in expired:
                self._expiry_delete_inflight.add(proceso_id)
                try:
                    self.app.api.delete(self._resource, proceso_id)
                    removed_ids.append(proceso_id)
                except Exception:
                    pass
                finally:
                    self._expiry_delete_inflight.discard(proceso_id)

            if removed_ids:
                def apply_local_cleanup():
                    self._all_data = [r for r in self._all_data if self._take_id(r) not in removed_ids]
                    self._apply_filters_now()

                self.after(0, apply_local_cleanup)

        threading.Thread(target=worker, daemon=True).start()

    def _row_values(self, rec):
        return (
            self._take_student_name(rec),
            self._take_doc(rec) or "—",
            self._take_email(rec) or "—",
            self._take_phone(rec) or "—",
            self._take_categoria(rec),
            _normalize_sede_label(self._take_sede(rec)) or self._take_sede(rec),
            self._take_origen(rec) or "—",
            self._take_metodo_pago(rec) or "—",
            self._take_estado_pago(rec) or "—",
            self._take_estado_contrato(rec) or "—",
            self._take_fecha_creacion(rec),
        )

    def _selected_record(self) -> Optional[Dict[str, Any]]:
        if self._selected_idx is None:
            return None
        try:
            return self._data[self._selected_idx]
        except Exception:
            return None

    # =====================================================
    #                     API
    # =====================================================
    def _show_loading(self, on=True, text="Actualizando..."):
        if on:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                return
            self._loading_overlay = ctk.CTkLabel(
                self.table,
                text=text,
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            self._loading_overlay.place(relx=0.5, rely=0.03, anchor="n")
        else:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                self._loading_overlay.destroy()
            self._loading_overlay = None

    def _fetch_resource_and_data(self, force_refresh: bool):
        if not self.app.api:
            raise RuntimeError("No hay cliente API activo. Inicia sesión.")

        errors = []
        if self._resource:
            raw = self.app.api.get_all(self._resource, force_refresh=force_refresh) or []
            return self._resource, raw

        for cand in self.RESOURCE_CANDIDATES:
            try:
                raw = self.app.api.get_all(cand, force_refresh=force_refresh) or []
                self._resource = cand
                return cand, raw
            except Exception as e:
                errors.append(f"{cand}: {e}")
                continue
        detail = "\n".join(errors[:6])
        if len(errors) > 6:
            detail += f"\n... {len(errors) - 6} más"
        raise RuntimeError(
            "No se encontró un endpoint compatible para solicitudes de matrícula.\n\n"
            f"Probé: {', '.join(self.RESOURCE_CANDIDATES)}\n\n"
            f"Errores:\n{detail or '—'}"
        )

    def _refrescar(self, force_refresh=True):
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                _resource, raw = self._fetch_resource_and_data(force_refresh=force_refresh)
                rows = self._unwrap_list(raw)

                def apply_data():
                    self._all_data = rows
                    self._apply_filters_now()

                self.after(0, apply_data)
            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: messagebox.showerror("matrículas", f"No fue posible consultar la API:\n{err}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _call_action(self, action: str, proceso_id, payload: Optional[Dict[str, Any]] = None):
        suffixes = self.ACTIONS.get(action) or ()
        if not suffixes:
            raise RuntimeError("Acción no soportada por la API.")

        # Robustez: el listado puede venir de un endpoint y las acciones existir en otro.
        resources = []
        if self._resource:
            resources.append(self._resource)
        for cand in self.RESOURCE_CANDIDATES:
            if cand not in resources:
                resources.append(cand)

        last_err = None
        for res in resources:
            for suf in suffixes:
                # PATCH
                try:
                    out = self.app.api.patch(res, proceso_id, payload=payload, suffix=suf)
                    self._resource = res
                    return out
                except Exception as e:
                    last_err = e
                # POST (fallback)
                try:
                    path = f"{res}/{proceso_id}/{suf}"
                    out = self.app.api.create(path, payload or {})
                    self._resource = res
                    return out
                except Exception as e:
                    last_err = e

        raise RuntimeError(last_err or "Acción no soportada por la API.")

    # =====================================================
    #                     ACCIONES
    # =====================================================
    def _nuevo(self):
        sedes = ["1 de Mayo", "El Eden"]
        allowed = self._allowed_admin_sede()
        if allowed:
            sedes = [allowed]

        def do_create(payload):
            try:
                if not self._resource:
                    self._fetch_resource_and_data(force_refresh=False)
                self.app.api.create(self._resource, payload)
                self.app._info("Solicitud creada.")
                self._refrescar(force_refresh=True)
            except Exception as e:
                messagebox.showerror("matrículas", f"No fue posible crear la solicitud:\n{e}", parent=self)

        _NuevaSolicitudDialog(self, self.app, sedes=sedes, on_create=do_create)

    def _ver_detalle(self):
        rec = self._selected_record()
        if not rec:
            return
        pid = self._take_id(rec)
        title = f"Solicitud {pid}" if pid is not None else "Solicitud"
        top = ctk.CTkToplevel(self)
        top.title(title)
        top.geometry("720x520")
        top.minsize(680, 480)
        try:
            top.configure(fg_color=self.app.COLOR_BG)
        except Exception:
            pass
        try:
            top.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            top.grab_set()
        except Exception:
            pass

        wrap = ctk.CTkFrame(
            top,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER,
        )
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 6))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text=self._take_student_name(rec),
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        meta = f"Doc: {self._take_doc(rec) or '—'} | Sede: {self._take_sede(rec) or '—'} | Origen: {self._take_origen(rec) or '—'}"
        ctk.CTkLabel(head, text=meta, text_color=self.app.COLOR_MUTED, anchor="w") \
            .grid(row=1, column=0, pady=(2, 0), sticky="w")

        body = ctk.CTkScrollableFrame(wrap, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        inner = getattr(body, "_scrollable_frame", None) or getattr(body, "scrollable_frame", None) or body
        inner.grid_columnconfigure(1, weight=1)

        def field(r, label, value):
            ctk.CTkLabel(inner, text=label, text_color=self.app.COLOR_MUTED, anchor="w") \
                .grid(row=r, column=0, padx=(10, 8), pady=6, sticky="w")
            ctk.CTkLabel(inner, text=str(value or "—"), text_color=self.app.COLOR_TEXT, anchor="w", wraplength=460) \
                .grid(row=r, column=1, padx=(0, 10), pady=6, sticky="ew")

        field(0, "ID", pid)
        field(1, "Correo", self._take_email(rec) or "—")
        field(2, "Teléfono", self._take_phone(rec) or "—")
        field(3, "Categoría", self._take_categoria(rec))
        field(4, "Método pago", self._take_metodo_pago(rec) or "—")
        field(5, "Estado pago", self._take_estado_pago(rec) or "—")
        field(6, "Estado contrato", self._take_estado_contrato(rec) or "—")
        field(7, "Creación", self._take_fecha_creacion(rec))

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(
            btns,
            text="Cerrar",
            height=36,
            corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG,
            hover_color=self.app.COLOR_DIVIDER,
            text_color=self.app.COLOR_TEXT,
            command=top.destroy,
        ).pack(side="right", padx=6)

    def _confirmar_pago(self):
        rec = self._selected_record()
        if not rec:
            self.app._info("Selecciona una solicitud primero.")
            return
        if not self._resource:
            try:
                self._fetch_resource_and_data(force_refresh=False)
            except Exception as e:
                messagebox.showerror("matrículas", str(e), parent=self)
                return

        proceso_id = self._take_id(rec)
        if proceso_id in (None, ""):
            messagebox.showwarning("matrículas", "La solicitud seleccionada no tiene ID.", parent=self)
            return

        metodo = self._take_metodo_pago(rec)
        if metodo and metodo != "EFECTIVO":
            messagebox.showwarning("Validación", "Esta acción es solo para pagos en EFECTIVO.", parent=self)
            return

        estado_pago = self._take_estado_pago(rec)
        if estado_pago in {"CONFIRMADO", "PAGADO", "OK"}:
            messagebox.showinfo("Pago", "Esta solicitud ya tiene el pago confirmado.", parent=self)
            return

        def do_confirm(valor: float, obs: str):
            origen = self._take_origen(rec)
            is_chatbot_origin = (origen == "CHATBOT")
            payload = {
                "valorPagado": float(valor),
                "observacionPago": obs,
                "validadoPorAdminId": getattr(self.app, "current_admin_id", None),
                # Si la solicitud viene del chatbot (pago en efectivo), al confirmar se debe
                # notificar por WhatsApp el enlace de contratos al estudiante.
                "sendEmail": True,
                "sendChatbot": bool(is_chatbot_origin),
                # Para solicitudes del chatbot NO exigimos prospecto (el usuario ya está en el flujo).
                "requireProspect": False if is_chatbot_origin else True,
            }
            try:
                out = self._call_action("confirmar_pago", proceso_id, payload)
                msg = out.get("message") if isinstance(out, dict) else ""
                if msg:
                    self.app._info(msg)
                else:
                    self.app._info("Pago confirmado y contratos habilitados.")
                self._refrescar(force_refresh=True)
            except Exception as e:
                messagebox.showerror("matrículas", f"No fue posible confirmar el pago:\n{e}", parent=self)

        _ConfirmarPagoDialog(self, self.app, on_confirm=do_confirm)

    def _enviar_correo(self):
        rec = self._selected_record()
        if not rec:
            self.app._info("Selecciona una solicitud primero.")
            return
        if not self._resource:
            try:
                self._fetch_resource_and_data(force_refresh=False)
            except Exception as e:
                messagebox.showerror("matrículas", str(e), parent=self)
                return

        proceso_id = self._take_id(rec)
        if proceso_id in (None, ""):
            messagebox.showwarning("matrículas", "La solicitud seleccionada no tiene ID.", parent=self)
            return

        estado_pago = self._take_estado_pago(rec)
        if estado_pago not in {"CONFIRMADO", "PAGADO", "OK"}:
            messagebox.showwarning(
                "Validación",
                "No se puede enviar el enlace de contratos si el pago no está confirmado.",
                parent=self,
            )
            return

        try:
            out = self._call_action("enviar_correo", proceso_id, payload=None)
            msg = out.get("message") if isinstance(out, dict) else ""
            self.app._info(msg or "Enlace de contratos enviado por correo.")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("matrículas", f"No fue posible enviar el correo:\n{e}", parent=self)

    def _backend_root_url(self) -> str:
        api = getattr(self.app, "api", None)
        base = str(getattr(api, "base_url", "") or "").strip().rstrip("/")
        if not base:
            return ""
        if base.lower().endswith("/api"):
            base = base[:-4]
        return base.rstrip("/")

    def _append_query_params(self, url: str, params: Dict[str, str]) -> str:
        parsed = urlparse(url or "")
        current = dict(parse_qsl(parsed.query, keep_blank_values=True))
        for k, v in (params or {}).items():
            if v is None:
                continue
            s = str(v).strip()
            if not s:
                continue
            current[str(k)] = s
        query = urlencode(current, doseq=True)
        return urlunparse(parsed._replace(query=query))

    def _resolve_contract_ui_url(self, verification_url: str, api_root: str) -> str:
        raw = str(verification_url or "").strip()
        if raw:
            try:
                u = urlparse(raw)
                if u.scheme and u.netloc:
                    return f"{u.scheme}://{u.netloc}/Contratos/contrato.html"
            except Exception:
                pass
        root = str(api_root or "").strip().rstrip("/")
        return f"{root}/Contratos/contrato.html" if root else ""

    def _generar_link_contratos(self):
        rec = self._selected_record()
        if not rec:
            self.app._info("Selecciona una solicitud primero.")
            return

        estado_pago = self._take_estado_pago(rec)
        if estado_pago not in {"CONFIRMADO", "PAGADO", "OK"}:
            messagebox.showwarning(
                "Validación",
                "No se puede generar el enlace de contratos si el pago no está confirmado.",
                parent=self,
            )
            return

        email = (self._take_email(rec) or "").strip()
        if not email:
            messagebox.showwarning("Validación", "La solicitud no tiene correo registrado.", parent=self)
            return

        if not messagebox.askyesno(
            "Generar enlace",
            "Esto generará un nuevo enlace de contratos y el anterior dejará de funcionar.\n\n¿Deseas continuar?",
            parent=self,
        ):
            return

        try:
            api_root = self._backend_root_url()
            payload = {"email": email, "baseUrl": api_root}

            out = None
            last_err = None
            for endpoint in ("verification/contract/link", "api/verification/contract/link"):
                try:
                    out = self.app.api.create(endpoint, payload)
                    break
                except Exception as e:
                    last_err = e
                    continue

            if not isinstance(out, dict):
                raise RuntimeError(last_err or "No fue posible generar el enlace de contratos.")

            email_out = (out.get("email") or email).strip()
            code = str(out.get("code") or "").strip()
            verification_url = str(out.get("url") or "").strip()
            if not code:
                raise RuntimeError("La API no devolvió el código del enlace de contratos.")

            ui_url = self._resolve_contract_ui_url(verification_url, api_root)
            if not ui_url:
                raise RuntimeError("No pude construir la URL del formulario de contratos.")

            params = {"email": email_out, "code": code}
            if api_root:
                params["apiBase"] = api_root
            link = self._append_query_params(ui_url, params)

            try:
                root = self.winfo_toplevel()
                root.clipboard_clear()
                root.clipboard_append(link)
                root.update()
            except Exception:
                pass

            self.app._info("Enlace de contratos copiado al portapapeles:\n\n" + link)
        except Exception as e:
            messagebox.showerror("matrículas", f"No fue posible generar el enlace:\n{e}", parent=self)

    def _is_prospecto_activo(self, rec) -> bool:
        # 1) Si el backend ya lo trae calculado, úsalo.
        if isinstance(rec, dict):
            val = rec.get("prospectoChatbotActivo")
            if isinstance(val, bool):
                return val
            if val is not None and str(val).strip().lower() in {"1", "true", "si", "sí", "yes"}:
                return True

        # 2) Endpoint dedicado (si existe)
        doc = self._take_doc(rec)
        email = self._take_email(rec)
        tel = self._take_phone(rec)

        for endpoint in (self.ACTIONS.get("es_prospecto") or ()):
            try:
                params = {}
                if doc:
                    params["documento"] = doc
                if email:
                    params["correo"] = email
                if tel:
                    params["telefono"] = tel
                data = self.app.api.get_all(endpoint, params=params, force_refresh=True)
                if isinstance(data, dict):
                    for k in ("activo", "isActive", "prospectoActivo", "prospectoChatbotActivo"):
                        if k in data and bool(data.get(k)):
                            return True
                    for k in ("found", "exists"):
                        if k in data and bool(data.get(k)):
                            return True
                if isinstance(data, list) and len(data) > 0:
                    return True
            except Exception:
                continue

        # 3) Fallback: validar contra estudiantes (sin exponer la lista)
        try:
            raw = self.app.api.get_all("estudiantes", force_refresh=False) or []
            estudiantes = self._unwrap_list(raw)
            for e in estudiantes:
                tipo = str((e or {}).get("tipoEstudiante") or "").strip().lower()
                if tipo != "prospecto":
                    continue
                e_doc = str(e.get("numeroDocumento") or "").strip()
                e_email = str(e.get("email") or "").strip().lower()
                e_tel = str(e.get("telefono") or "").strip()
                if (doc and e_doc == doc) or (email and e_email == email.strip().lower()) or (tel and e_tel == tel):
                    return True
        except Exception:
            pass
        return False

    def _enviar_chatbot(self):
        rec = self._selected_record()
        if not rec:
            self.app._info("Selecciona una solicitud primero.")
            return
        if not self._resource:
            try:
                self._fetch_resource_and_data(force_refresh=False)
            except Exception as e:
                messagebox.showerror("matrículas", str(e), parent=self)
                return

        proceso_id = self._take_id(rec)
        if proceso_id in (None, ""):
            messagebox.showwarning("matrículas", "La solicitud seleccionada no tiene ID.", parent=self)
            return

        origen = self._take_origen(rec)
        if origen and origen != "HAROGESTION":
            messagebox.showwarning(
                "Validación",
                "El envío por chatbot desde HaroGestion solo aplica a solicitudes creadas desde HAROGESTION.",
                parent=self,
            )
            return

        estado_pago = self._take_estado_pago(rec)
        if estado_pago not in {"CONFIRMADO", "PAGADO", "OK"}:
            messagebox.showwarning(
                "Validación",
                "No se puede enviar el enlace por chatbot si el pago no está confirmado.",
                parent=self,
            )
            return

        if not self._is_prospecto_activo(rec):
            messagebox.showwarning(
                "Prospecto no activo",
                "No es posible enviar el enlace de contratos por chatbot porque el estudiante no se encuentra en prospectos activos. "
                "Indíquele al estudiante que escriba primero al chatbot para habilitar este canal de envío.",
                parent=self,
            )
            return

        try:
            out = self._call_action("enviar_chatbot", proceso_id, payload=None)
            msg = out.get("message") if isinstance(out, dict) else ""
            self.app._info(msg or "Enlace de contratos enviado por chatbot.")
            self._refrescar(force_refresh=True)
        except Exception as e:
            messagebox.showerror("matrículas", f"No fue posible enviar por chatbot:\n{e}", parent=self)

