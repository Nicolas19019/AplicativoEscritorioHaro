import customtkinter as ctk
from tkinter import messagebox, filedialog, ttk
from modules.base import BaseModuleFrame
from datetime import datetime, date
from pathlib import Path
import threading
from collections import Counter, defaultdict

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


def _solid_color(value, fallback):
    if isinstance(value, (tuple, list)) and value:
        return str(value[0] or fallback)
    if value in (None, ""):
        return fallback
    return str(value)


class ReportesView(BaseModuleFrame):
    """
    Vista del módulo de Reportes
    Reportes especializados por área (cada uno con su propio PDF):
      - Estudiantes
      - Estado de cuenta
      - Clases prácticas
    """
    def __init__(self, master):
        super().__init__(master, "Reportes", "Visualización de estadísticas y reportes del sistema")

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure(4, weight=1)

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

        action_btn("📊 Generar", self._generar, self.app.MUSTARD_MAIN, self.app.MUSTARD_HOVER, txt="#111111")\
            .grid(row=0, column=0, padx=(0, 8))
        action_btn("💾 Exportar PDF", self._exportar, self.app.COLOR_BLUE, self.app.BLUE_HOVER)\
            .grid(row=0, column=1, padx=8)
        action_btn("↻ Refrescar", self._refrescar, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER)\
            .grid(row=0, column=2, padx=8)

        self.btn_toggle_table = action_btn(
            "Mostrar tabla",
            self._toggle_table_mode,
            self.app.COLOR_RED,
            self.app.COLOR_YELLOW,
        )
        self.btn_toggle_table.grid(row=0, column=3, padx=8)

        # ===== Filtros =====
        self._build_filtros()

        # ===== Resumen / análisis =====
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.summary.grid_columnconfigure(0, weight=1)

        # Mantener el resumen en un alto fijo (scroll) para que la tabla siempre quede visible
        # (CTkScrollableFrame no soporta grid_propagate(False), así que usamos un wrapper con alto fijo)
        self.summary_wrap = ctk.CTkFrame(self.summary, fg_color="transparent", height=330)
        self.summary_wrap.grid(row=0, column=0, sticky="ew")
        self.summary_wrap.grid_columnconfigure(0, weight=1)
        self.summary_wrap.grid_rowconfigure(0, weight=1)
        self.summary_wrap.grid_propagate(False)

        self.summary_body = ctk.CTkScrollableFrame(
            self.summary_wrap,
            fg_color="transparent",
            corner_radius=0,
        )
        self.summary_body.grid(row=0, column=0, sticky="nsew")
        self.summary_body.grid_columnconfigure(0, weight=1)

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== Data interna =====
        self._data = []
        self._analysis = {"kpis": [], "insights": [], "tops": {}}
        self._tipo = "Estudiantes"
        self._report_month = datetime.now().month
        self._report_year = datetime.now().year
        self._table_mode = False
        self._table_query = ""

        # Tree state
        self._COLS = []
        self.tree = None
        self._iid_to_index = {}
        self._empty_label = None
        self._loading_overlay = None

        # Render inicial (vacío) + autogenerar
        self._apply_report_state(self._empty_report_state())
        self._update_view_mode()
        self.after(150, self._generar)

    # =====================================================
    #                 HELPERS PDF (PRO)
    # =====================================================
    def _get_logo_path(self) -> str | None:
        """
        Busca un logo "grande" para PDF.
        Puedes dejar 'LogoGrande.png' o cambiar a 'LogoHARO.png' según tengas en /media.
        """
        base = Path(__file__).resolve().parent.parent  # modules/ -> raíz proyecto (ajusta si cambia)
        candidates = [
            base / "media" / "LogoGrande.png",
            base / "media" / "LogoHARO.png",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def _make_doc(self, path: str) -> SimpleDocTemplate:
        # Márgenes tipo carta y espacio arriba para el logo
        return SimpleDocTemplate(
            path,
            pagesize=LETTER,
            leftMargin=2.2 * cm,
            rightMargin=2.2 * cm,
            topMargin=4.2 * cm,     # deja aire para el header + logo (evita que quede pegado arriba)
            bottomMargin=2.0 * cm
        )

    def _styles(self):
        styles = getSampleStyleSheet()

        title = ParagraphStyle(
            "TitlePro",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
            spaceAfter=6
        )
        meta = ParagraphStyle(
            "MetaPro",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=10
        )
        normal = ParagraphStyle(
            "BodyPro",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#111827")
        )
        return {"base": styles, "title": title, "meta": meta, "normal": normal}

    def _header_canvas(self, right_logo: bool = True):
        """
        Header tipo carta:
        - Logo grande arriba derecha (proporción real)
        - Línea sutil bajo el encabezado
        """
        logo_path = self._get_logo_path()

        def _draw(canvas, doc):
            canvas.saveState()

            # --- Logo grande arriba derecha ---
            if right_logo and logo_path:
                try:
                    img = ImageReader(logo_path)
                    iw, ih = img.getSize()
                    aspect = ih / float(iw)

                    # tamaño tipo “como la imagen de ejemplo”
                    logo_w = 6.5 * cm
                    logo_h = logo_w * aspect

                    x = doc.pagesize[0] - doc.rightMargin - logo_w
                    # Coloca el logo dentro del margen superior con padding para que no quede pegado arriba.
                    top_pad = 1.0 * cm
                    y = doc.pagesize[1] - top_pad - logo_h
                    min_y = doc.pagesize[1] - doc.topMargin + 0.15 * cm
                    if y < min_y:
                        y = min_y
                    canvas.drawImage(img, x, y, width=logo_w, height=logo_h, mask="auto")
                except Exception as e:
                    print(f"[PDF] No se pudo dibujar logo: {e}")

            # --- línea sutil separadora ---
            line_y = doc.pagesize[1] - doc.topMargin + 0.25 * cm
            canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
            canvas.setLineWidth(1)
            canvas.line(doc.leftMargin, line_y, doc.pagesize[0] - doc.rightMargin, line_y)

            canvas.restoreState()

        return _draw

    def _table_pro(self, rows, col_widths=None):
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, 0), 10),
            ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),

            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F9FAFB")]),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 1), (-1, -1), 8),
            ("RIGHTPADDING", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))
        return t

    # =====================================================
    #                     FILTROS
    # =====================================================
    def _build_filtros(self):
        filtros = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        filtros.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        filtros.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(filtros, text="Tipo de reporte:", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=0, padx=8, pady=10, sticky="w")

        self.cb_tipo = ctk.CTkComboBox(
            filtros,
            values=["Estudiantes", "Estado de cuenta", "Clases prácticas"],
            width=200,
            state="readonly"
        )
        self.cb_tipo.set("Estudiantes")
        self.cb_tipo.grid(row=0, column=1, padx=8, pady=10, sticky="w")

        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        self._MESES = meses
        ctk.CTkLabel(filtros, text="Mes:", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=2, padx=8, pady=10, sticky="w")

        self.cb_mes = ctk.CTkComboBox(filtros, values=meses, width=140, state="readonly")
        self.cb_mes.set(meses[datetime.now().month - 1])
        self.cb_mes.grid(row=0, column=3, padx=8, pady=10, sticky="w")

        ctk.CTkLabel(filtros, text="Año:", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=4, padx=8, pady=10, sticky="w")

        años = [str(y) for y in range(2022, datetime.now().year + 2)]
        self.cb_anio = ctk.CTkComboBox(filtros, values=años, width=100, state="readonly")
        self.cb_anio.set(str(datetime.now().year))
        self.cb_anio.grid(row=0, column=5, padx=8, pady=10, sticky="w")

        ctk.CTkButton(
            filtros, text="🔍 Buscar", height=36, corner_radius=12,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff", command=self._generar
        ).grid(row=0, column=6, padx=10, pady=10, sticky="e")

    # =====================================================
    #                 RESUMEN / ANÁLISIS
    # =====================================================
    def _empty_report_state(self):
        tipo = getattr(self, "_tipo", "Estudiantes")
        return {"tipo": tipo, "data": [], "analysis": {"kpis": [], "insights": [], "tops": {}}}

    def _toggle_table_mode(self):
        self._table_mode = not bool(getattr(self, "_table_mode", False))
        self._update_view_mode()

    def _update_view_mode(self):
        showing_table = bool(getattr(self, "_table_mode", False))
        if showing_table:
            self.summary.grid_remove()
            self.table.grid()
            if hasattr(self, "btn_toggle_table"):
                self.btn_toggle_table.configure(text="Volver al resumen")
        else:
            self.table.grid_remove()
            self.summary.grid()
            if hasattr(self, "btn_toggle_table"):
                self.btn_toggle_table.configure(text="Mostrar tabla")

    @staticmethod
    def _kpi_description(title_text: str, value_text: str) -> str:
        t = str(title_text or "").strip().lower()
        value = str(value_text or "").strip()

        if "total estudiantes" in t:
            return f"{value} registros visibles"
        if "activos" == t or t.endswith(" activos"):
            return f"{value} con estado activo"
        if "inactivos" in t:
            return f"{value} fuera de actividad"
        if "nuevos" in t:
            return f"{value} ingresos del periodo"
        if "matric" in t and "chatbot" in t:
            return f"{value} cierres estimados"
        if "prospect" in t and "chatbot" in t:
            return f"{value} leads en seguimiento"
        if "convers" in t and "chatbot" in t:
            return "Paso de prospecto a matricula"
        if "cuentas" in t:
            return f"{value} cuentas registradas"
        if "monto total" in t:
            return "Valor acumulado"
        if "pagado" == t or t.endswith(" pagado"):
            return "Recaudo confirmado"
        if "saldo" in t:
            return "Pendiente por cobrar"
        if "clases" in t:
            return f"{value} sesiones encontradas"
        if "horas" in t:
            return "Carga horaria del periodo"
        if "programadas" in t:
            return "Pendientes de ejecutar"
        if "canceladas" in t:
            return "Sesiones anuladas"
        return ""

    def _render_summary(self):
        container = getattr(self, "summary_body", None) or self.summary
        # Limpia y vuelve a pintar el resumen (KPIs + análisis)
        for w in container.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        kpis = (self._analysis or {}).get("kpis") or []
        insights = (self._analysis or {}).get("insights") or []
        tops = (self._analysis or {}).get("tops") or {}

        def C(name, default):
            return getattr(self.app, name, default)

        # Paleta suave (light/dark) para darle color al resumen
        RED_BG = C("RED_SOFT_BG", ("#FEF2F2", "#2a1515"))
        RED_BORDER = C("RED_SOFT_BORDER", ("#FDE3E3", "#3a1f1f"))
        RED = C("COLOR_RED", ("#E53935", "#ff4c4c"))

        MUST_BG = C("MUSTARD_SOFT_BG", ("#FFF8E1", "#2a2618"))
        MUST_BORDER = C("MUSTARD_SOFT_BORDER", ("#F7EAC1", "#3a3420"))
        MUST = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))

        BLUE_BG = ("#EFF6FF", "#0b1e35")
        BLUE_BORDER = ("#BFDBFE", "#1e3a8a")
        BLUE = ("#2563eb", "#60a5fa")

        GREEN_BG = ("#ECFDF5", "#0d2a1a")
        GREEN_BORDER = ("#A7F3D0", "#14532d")
        GREEN = ("#16a34a", "#22c55e")

        PURPLE_BG = ("#F5F3FF", "#24143a")
        PURPLE_BORDER = ("#DDD6FE", "#4c1d95")
        PURPLE = ("#7c3aed", "#a78bfa")

        def pick_kpi_style(title_text: str):
            t = str(title_text or "").strip().lower()

            # icono
            if "total" in t and "estudiante" in t:
                icon = "👥"
            elif "activo" in t:
                icon = "✅"
            elif "inactivo" in t:
                icon = "⛔"
            elif "nuevo" in t:
                icon = "🆕"
            elif "cuenta" in t:
                icon = "🧾"
            elif "monto" in t:
                icon = "💰"
            elif "pagado" in t:
                icon = "✅"
            elif "saldo" in t:
                icon = "⚠️"
            elif "clase" in t:
                icon = "📅"
            elif "hora" in t:
                icon = "⏱️"
            elif "program" in t:
                icon = "🟡"
            elif "cancel" in t:
                icon = "❌"
            else:
                icon = "📌"

            # colores
            if any(k in t for k in ("saldo", "inactivo", "cancel", "deuda", "pendiente")):
                return icon, RED_BG, RED_BORDER, RED
            if any(k in t for k in ("pagado", "activo", "dictada", "recaudo")):
                return icon, GREEN_BG, GREEN_BORDER, GREEN
            if any(k in t for k in ("monto", "horas", "program", "nuevo")):
                return icon, MUST_BG, MUST_BORDER, MUST
            if any(k in t for k in ("clase", "cuenta", "total")):
                return icon, BLUE_BG, BLUE_BORDER, BLUE
            return icon, PURPLE_BG, PURPLE_BORDER, PURPLE

        if not kpis and not insights:
            ctk.CTkLabel(
                container,
                text="Genera un reporte para ver el análisis.",
                text_color=self.app.COLOR_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=2, pady=2)
            return

        cards = ctk.CTkFrame(container, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform="kpi")

        for i in range(4):
            title, value = ("—", "—")
            if i < len(kpis):
                title, value = kpis[i]

            icon, bg, border, accent = pick_kpi_style(title)
            card = ctk.CTkFrame(
                cards,
                fg_color=bg,
                corner_radius=12,
                border_width=1,
                border_color=border,
            )
            card.grid(row=0, column=i, padx=6, pady=(0, 6), sticky="ew")
            card.grid_columnconfigure(2, weight=1)

            bar = ctk.CTkFrame(card, fg_color=accent, corner_radius=10, width=6, height=1)
            bar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 8), pady=8)
            bar.grid_propagate(False)

            ctk.CTkLabel(
                card,
                text=icon,
                text_color=accent,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, padx=(0, 8), pady=(8, 2), sticky="w")
            ctk.CTkLabel(
                card,
                text=str(value),
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=18, weight="bold"),
                anchor="w",
            ).grid(row=0, column=2, padx=(0, 12), pady=(8, 2), sticky="w")
            ctk.CTkLabel(
                card,
                text=str(title),
                text_color=self.app.COLOR_MUTED,
                anchor="w",
            ).grid(row=1, column=1, columnspan=2, padx=(0, 12), pady=(0, 8), sticky="w")

        ana = ctk.CTkFrame(
            container,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=PURPLE_BORDER,
        )
        ana.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))
        ana.grid_columnconfigure(1, weight=1)

        bar = ctk.CTkFrame(ana, fg_color=PURPLE, corner_radius=10, width=6, height=1)
        bar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 8), pady=8)
        bar.grid_propagate(False)

        head = ctk.CTkFrame(ana, fg_color="transparent")
        head.grid(row=0, column=1, padx=(0, 12), pady=(10, 4), sticky="ew")
        ctk.CTkLabel(
            head,
            text="🧠",
            text_color=PURPLE,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            head,
            text="Análisis",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(8, 0))

        insights_txt = "\n".join([f"• {s}" for s in insights]) if insights else "—"
        ctk.CTkLabel(
            ana,
            text=insights_txt,
            text_color=self.app.COLOR_TEXT,
            justify="left",
            anchor="w",
            wraplength=980,
        ).grid(row=1, column=1, padx=(0, 12), pady=(0, 10), sticky="ew")

        if tops:
            topf = ctk.CTkFrame(
                container,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=12,
                border_width=1,
                border_color=MUST_BORDER,
            )
            topf.grid(row=2, column=0, sticky="ew", padx=6, pady=(6, 0))
            topf.grid_columnconfigure(1, weight=1)
            topf.grid_columnconfigure(2, weight=1)

            bar = ctk.CTkFrame(topf, fg_color=MUST, corner_radius=10, width=6, height=1)
            bar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 8), pady=8)
            bar.grid_propagate(False)

            head = ctk.CTkFrame(topf, fg_color="transparent")
            head.grid(row=0, column=1, columnspan=2, padx=(0, 12), pady=(10, 4), sticky="ew")
            ctk.CTkLabel(
                head,
                text="🏆",
                text_color=MUST,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(side="left")
            ctk.CTkLabel(
                head,
                text="Top",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", padx=(8, 0))

            for col, (title, items) in enumerate(list(tops.items())[:2]):
                box = ctk.CTkFrame(
                    topf,
                    fg_color=self.app.COLOR_INPUT_BG,
                    corner_radius=10,
                    border_width=1,
                    border_color=self.app.COLOR_DIVIDER,
                )
                box.grid(row=1, column=1 + col, padx=10, pady=(0, 10), sticky="ew")
                box.grid_columnconfigure(0, weight=1)
                box.grid_columnconfigure(1, weight=0)

                ctk.CTkLabel(box, text=str(title), text_color=self.app.COLOR_MUTED, anchor="w")\
                    .grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

                for i, (name, val) in enumerate((items or [])[:5], start=1):
                    ctk.CTkLabel(box, text=str(name), text_color=self.app.COLOR_TEXT, anchor="w")\
                        .grid(row=i, column=0, padx=10, pady=4, sticky="w")
                    ctk.CTkLabel(box, text=str(val), text_color=self.app.COLOR_TEXT, anchor="e")\
                        .grid(row=i, column=1, padx=10, pady=4, sticky="e")

    def _render_summary(self):
        container = getattr(self, "summary_body", None) or self.summary
        for w in container.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        kpis = (self._analysis or {}).get("kpis") or []
        insights = (self._analysis or {}).get("insights") or []
        tops = (self._analysis or {}).get("tops") or {}

        def C(name, default):
            return getattr(self.app, name, default)

        red_bg = C("RED_SOFT_BG", ("#FEF2F2", "#2a1515"))
        red_border = C("RED_SOFT_BORDER", ("#FDE3E3", "#3a1f1f"))
        red = C("COLOR_RED", ("#E53935", "#ff4c4c"))

        must_bg = C("MUSTARD_SOFT_BG", ("#FFF8E1", "#2a2618"))
        must_border = C("MUSTARD_SOFT_BORDER", ("#F7EAC1", "#3a3420"))
        must = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))

        blue_bg = ("#FFF7E0", "#2B2209")
        blue_border = ("#F5D98A", "#4A3A12")
        blue = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))

        green_bg = ("#FFF1F1", "#2a1515")
        green_border = ("#F3C0C0", "#442020")
        green = red

        purple_bg = C("COLOR_PANEL", ("#FFFFFF", "#151515"))
        purple_border = C("COLOR_DIVIDER", ("#E7E7E7", "#303030"))
        purple = C("COLOR_TEXT", ("#111111", "#F3F3F3"))

        if not kpis and not insights:
            ctk.CTkLabel(
                container,
                text="Genera un reporte para ver el analisis.",
                text_color=self.app.COLOR_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=2, pady=2)
            return

        cards = ctk.CTkFrame(container, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform="kpi")

        total_cards = max(len(kpis), 4)
        rows_needed = (total_cards + 3) // 4

        for i in range(total_cards):
            title, value = ("-", "-")
            if i < len(kpis):
                title, value = kpis[i]

            if i % 2 == 0:
                bg, border, accent = red_bg, red_border, red
            else:
                bg, border, accent = must_bg, must_border, must
            card = ctk.CTkFrame(
                cards,
                fg_color=bg,
                corner_radius=18,
                border_width=1,
                border_color=border,
            )
            card.grid(row=i // 4, column=i % 4, padx=6, pady=(0, 8), sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=str(title),
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, padx=14, pady=(12, 8), sticky="w")
            ctk.CTkLabel(
                card,
                text=str(value),
                text_color=accent,
                font=ctk.CTkFont(size=28, weight="bold"),
                anchor="w",
            ).grid(row=1, column=0, padx=14, pady=(0, 14), sticky="w")

        ana = ctk.CTkFrame(
            container,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=18,
            border_width=1,
            border_color=purple_border,
        )
        ana.grid(row=rows_needed, column=0, sticky="ew", padx=6, pady=(0, 2))
        ana.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            ana,
            text="Analisis",
            text_color=self.app.COLOR_TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        insights_txt = "\n".join([f"- {s}" for s in insights]) if insights else "-"
        ctk.CTkLabel(
            ana,
            text=insights_txt,
            text_color=self.app.COLOR_TEXT,
            justify="left",
            anchor="w",
            wraplength=980,
        ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")

        if tops:
            topf = ctk.CTkFrame(
                container,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=18,
                border_width=1,
                border_color=must_border,
            )
            topf.grid(row=rows_needed + 1, column=0, sticky="ew", padx=6, pady=(6, 0))
            topf.grid_columnconfigure(0, weight=1)
            topf.grid_columnconfigure(1, weight=1)

            for col, (title, items) in enumerate(list(tops.items())[:2]):
                box = ctk.CTkFrame(
                    topf,
                    fg_color=self.app.COLOR_INPUT_BG,
                    corner_radius=14,
                    border_width=1,
                    border_color=self.app.COLOR_DIVIDER,
                )
                box.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
                box.grid_columnconfigure(0, weight=1)
                box.grid_columnconfigure(1, weight=0)

                ctk.CTkLabel(
                    box,
                    text=str(title),
                    text_color=self.app.COLOR_TEXT,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w",
                ).grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 6), sticky="w")

                for idx, (name, val) in enumerate((items or [])[:5], start=1):
                    ctk.CTkLabel(
                        box,
                        text=str(name),
                        text_color=self.app.COLOR_TEXT,
                        anchor="w",
                    ).grid(row=idx, column=0, padx=10, pady=4, sticky="w")
                    ctk.CTkLabel(
                        box,
                        text=str(val),
                        text_color=self.app.COLOR_MUTED,
                        anchor="e",
                    ).grid(row=idx, column=1, padx=10, pady=4, sticky="e")

    def _apply_report_state(self, state):
        if not isinstance(state, dict):
            state = self._empty_report_state()
        self._tipo = state.get("tipo", getattr(self, "_tipo", "Estudiantes"))
        self._data = list(state.get("data") or [])
        self._analysis = state.get("analysis") or {"kpis": [], "insights": [], "tops": {}}

        self._render_summary()
        self._render_table()
        self._update_view_mode()

    @staticmethod
    def _tipo_norm(tipo: str) -> str:
        return str(tipo or "").strip().lower()

    @staticmethod
    def _unwrap_list(raw, prefer_keys=()):
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in list(prefer_keys) + ["content", "items", "data", "results"]:
                lst = raw.get(key)
                if isinstance(lst, list):
                    return lst
            for v in raw.values():
                if isinstance(v, list):
                    return v
        return []

    @staticmethod
    def _parse_date(value):
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
        if len(s) >= 10:
            s = s[:10]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None

    def _remaining_days_report(self, rec):
        start_date = self._parse_date(rec.get("fechaCreacion") or rec.get("fechaIngreso") or rec.get("createdAt"))
        if not start_date:
            return "—"
        elapsed = (date.today() - start_date).days
        return str(max(0, 85 - max(0, elapsed)))

    @staticmethod
    def _extract_sede_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for k in ("nombre", "name", "sede", "descripcion"):
                v = value.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
            if value.get("id") not in ("", None):
                return str(value.get("id")).strip()
            return ""
        return str(value).strip()

    def _record_sede(self, rec) -> str:
        if not isinstance(rec, dict):
            return ""
        for key in ("sede", "sedePrincipal", "sede_principal", "sedeNombre", "nombreSede", "campus"):
            val = rec.get(key)
            if val not in ("", None):
                return self._extract_sede_value(val)
        for key in ("idSede", "sedeId", "sede_id"):
            val = rec.get(key)
            if val not in ("", None):
                return str(val).strip()
        return ""

    @staticmethod
    def _normalize_doc(doc_value):
        invalid = {"-1", "-2", "-3", "0", "None", "null", ""}
        if doc_value is None:
            return "—"
        if isinstance(doc_value, (int, float)):
            try:
                doc_value = str(int(doc_value))
            except Exception:
                doc_value = str(doc_value)
        doc = str(doc_value).strip()
        if doc in invalid or doc.startswith("-"):
            return "—"
        return doc

    @staticmethod
    def _format_money(value) -> str:
        try:
            v = float(value or 0)
        except Exception:
            return str(value or "")
        sign = "-" if v < 0 else ""
        v = abs(v)
        return f"{sign}${v:,.0f}"

    @staticmethod
    def _duration_hours(h_ini: str, h_fin: str) -> float:
        try:
            t1 = datetime.strptime(str(h_ini or "").strip(), "%H:%M")
            t2 = datetime.strptime(str(h_fin or "").strip(), "%H:%M")
            delta = (t2 - t1).total_seconds() / 3600.0
            if delta < 0:
                delta += 24.0
            return max(0.0, float(delta))
        except Exception:
            return 0.0

    def _filter_by_month(self, records, month: int, year: int, date_keys):
        if not month or not year:
            return list(records or [])
        out = []
        for rec in (records or []):
            for key in (date_keys or []):
                d = self._parse_date((rec or {}).get(key))
                if d and d.month == month and d.year == year:
                    out.append(rec)
                    break
        return out

    def _show_loading(self, on=True, text="Generando..."):
        if on:
            if getattr(self, "_loading_overlay", None) and self._loading_overlay.winfo_exists():
                return
            self._loading_overlay = ctk.CTkLabel(
                self.table,
                text=text,
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            self._loading_overlay.place(relx=0.5, rely=0.03, anchor="n")
        else:
            if getattr(self, "_loading_overlay", None) and self._loading_overlay.winfo_exists():
                self._loading_overlay.destroy()
            self._loading_overlay = None

    # ==============================
    #   Construcción de reportes
    # ==============================
    def _build_report_state(self, tipo: str, month: int, year: int, force_refresh: bool = True):
        api = getattr(self.app, "api", None)
        if not api:
            return {
                "tipo": tipo,
                "data": [],
                "analysis": {
                    "kpis": [],
                    "insights": ["Inicia sesión para generar reportes con datos reales."],
                    "tops": {},
                },
            }

        t = self._tipo_norm(tipo)
        if "estudiante" in t:
            return self._build_estudiantes_report_state(tipo, month, year, force_refresh=force_refresh)
        if "estado" in t:
            return self._build_estado_cuenta_report_state(tipo, force_refresh=force_refresh)
        # Clases prácticas
        return self._build_clases_report_state(tipo, month, year, force_refresh=force_refresh)

    def _build_estudiantes_report_state(self, tipo: str, month: int, year: int, force_refresh: bool = True):
        raw = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []
        estudiantes = self._unwrap_list(raw, prefer_keys=("estudiantes",))

        nuevos = self._filter_by_month(estudiantes, month, year, ("fechaCreacion", "fechaIngreso", "createdAt"))

        detalle = []
        for e in nuevos:
            sid = e.get("id") or e.get("idEstudiante") or ""
            nombre = f"{e.get('nombre','')} {e.get('apellido','')}".strip() or str(sid)
            doc = (
                e.get("numeroDocumento") or e.get("numDocumento")
                or e.get("documento") or e.get("documentoEstudiante")
                or e.get("cc") or e.get("CC") or e.get("cedula") or e.get("dni")
            )
            estado = (e.get("estado") or "").strip() or "—"
            categoria = (
                e.get("categoria")
                or e.get("categoriaLicencia")
                or e.get("licenciaCategoria")
                or ""
            )
            sede = self._record_sede(e) or "—"
            horas = e.get("horas", "")

            ingreso_dt = self._parse_date(e.get("fechaCreacion") or e.get("fechaIngreso") or e.get("createdAt"))
            ingreso_txt = ingreso_dt.strftime("%Y-%m-%d") if ingreso_dt else (str(e.get("fechaCreacion") or "")[:10] or "—")

            detalle.append({
                "ID": sid,
                "Nombre": nombre,
                "Documento": self._normalize_doc(doc),
                "Estado": estado,
                "Categoría": str(categoria or "").strip().upper() or "—",
                "Sede": sede,
                "Horas": horas if horas not in (None, "") else "—",
                "Ingreso": ingreso_txt,
            })

        total = len(estudiantes)
        activos = sum(1 for e in estudiantes if str(e.get("estado") or "").strip().lower() == "activo")
        inactivos = max(0, total - activos)

        sede_counts = Counter([self._record_sede(e) or "Sin sede" for e in nuevos])
        cat_counts = Counter([str((e or {}).get("categoria") or "").strip().upper() or "—" for e in nuevos])

        top_sede, top_sede_n = ("—", 0)
        if sede_counts:
            top_sede, top_sede_n = sede_counts.most_common(1)[0]

        top_cat, top_cat_n = ("—", 0)
        if cat_counts:
            top_cat, top_cat_n = cat_counts.most_common(1)[0]

        try:
            horas_vals = [float(e.get("horas") or 0) for e in nuevos]
            avg_h = (sum(horas_vals) / len(horas_vals)) if horas_vals else 0.0
        except Exception:
            avg_h = 0.0

        analysis = {
            "kpis": [
                ("Total estudiantes", str(total)),
                ("Activos", str(activos)),
                ("Inactivos", str(inactivos)),
                ("Nuevos (mes)", str(len(nuevos))),
            ],
            "insights": [
                f"Sede con más matrículas (mes): {top_sede} ({top_sede_n})" if top_sede_n else "Sin matrículas para este periodo.",
                f"Categoría más común (mes): {top_cat} ({top_cat_n})" if top_cat_n else "—",
                f"Activos en el sistema: {activos}/{total}",
                f"Promedio de horas (mes): {avg_h:.1f}",
            ],
            "tops": {
                "Top sedes": [(k, str(v)) for k, v in sede_counts.most_common(5)],
                "Top categorías": [(k, str(v)) for k, v in cat_counts.most_common(5)],
            },
        }

        return {"tipo": tipo, "data": detalle, "analysis": analysis}

    def _build_estudiantes_report_state(self, tipo: str, month: int, year: int, force_refresh: bool = True):
        raw = self.app.api.get_all("estudiantes", force_refresh=force_refresh) or []
        estudiantes = self._unwrap_list(raw, prefer_keys=("estudiantes",))

        nuevos = self._filter_by_month(estudiantes, month, year, ("fechaCreacion", "fechaIngreso", "createdAt"))
        conversion_types = {"inscrito", "matriculado", "activo"}
        raw_estados = self.app.api.get_all("estados-cuenta", force_refresh=False) or []
        estados_cuenta = self._unwrap_list(raw_estados, prefer_keys=("estados-cuenta", "estadosCuenta", "estados"))

        detalle = []
        for e in nuevos:
            sid = e.get("id") or e.get("idEstudiante") or ""
            nombre = f"{e.get('nombre','')} {e.get('apellido','')}".strip() or str(sid)
            doc = (
                e.get("numeroDocumento") or e.get("numDocumento")
                or e.get("documento") or e.get("documentoEstudiante")
                or e.get("cc") or e.get("CC") or e.get("cedula") or e.get("dni")
            )
            estado = (e.get("estado") or "").strip() or "—"
            categoria = (
                e.get("categoria")
                or e.get("categoriaLicencia")
                or e.get("licenciaCategoria")
                or ""
            )
            sede = self._record_sede(e) or "—"
            horas = e.get("horas", "")
            ingreso_dt = self._parse_date(e.get("fechaCreacion") or e.get("fechaIngreso") or e.get("createdAt"))
            ingreso_txt = ingreso_dt.strftime("%Y-%m-%d") if ingreso_dt else (str(e.get("fechaCreacion") or "")[:10] or "—")

            detalle.append({
                "ID": sid,
                "Nombre": nombre,
                "Documento": self._normalize_doc(doc),
                "Estado": estado,
                "Categoría": str(categoria or "").strip().upper() or "—",
                "Sede": sede,
                "Horas": horas if horas not in (None, "") else "—",
                "Días restantes": self._remaining_days_report(e),
                "Ingreso": ingreso_txt,
            })

        total = len(estudiantes)
        activos = sum(1 for e in estudiantes if str(e.get("estado") or "").strip().lower() == "activo")
        inactivos = max(0, total - activos)

        sede_counts = Counter([self._record_sede(e) or "Sin sede" for e in nuevos])
        cat_counts = Counter([str((e or {}).get("categoria") or "").strip().upper() or "—" for e in nuevos])

        prospectos_total = sum(1 for e in estudiantes if str(e.get("tipoEstudiante") or "").strip().lower() == "prospecto")
        prospectos_mes = sum(1 for e in nuevos if str(e.get("tipoEstudiante") or "").strip().lower() == "prospecto")
        matriculas_chatbot = sum(1 for e in estudiantes if str(e.get("tipoEstudiante") or "").strip().lower() in conversion_types)
        matriculas_chatbot_mes = sum(1 for e in nuevos if str(e.get("tipoEstudiante") or "").strip().lower() in conversion_types)
        estudiantes_en_mora = 0
        for estado in estados_cuenta:
            try:
                monto_total = float(estado.get("montoTotal") or 0)
                monto_pagado = float(estado.get("montoPagado") or 0)
                saldo = monto_total - monto_pagado
                estado_txt = str(estado.get("estado") or "").strip().lower()
                if saldo > 0 or estado_txt in {"en deuda", "pendiente", "mora"}:
                    estudiantes_en_mora += 1
            except Exception:
                continue

        top_sede, top_sede_n = ("—", 0)
        if sede_counts:
            top_sede, top_sede_n = sede_counts.most_common(1)[0]

        top_cat, top_cat_n = ("—", 0)
        if cat_counts:
            top_cat, top_cat_n = cat_counts.most_common(1)[0]

        try:
            horas_vals = [float(e.get("horas") or 0) for e in nuevos]
            avg_h = (sum(horas_vals) / len(horas_vals)) if horas_vals else 0.0
        except Exception:
            avg_h = 0.0

        analysis = {
            "kpis": [
                ("Total estudiantes", str(total)),
                ("Activos", str(activos)),
                ("Inactivos", str(inactivos)),
                ("Nuevos (mes)", str(len(nuevos))),
                ("Matrículas chatbot", str(matriculas_chatbot_mes)),
                ("Prospectos chatbot", str(prospectos_total)),
                ("Estudiantes en mora", str(estudiantes_en_mora)),
                ("Prospectos chatbot (mes)", str(prospectos_mes)),
            ],
            "insights": [
                "Las métricas de chatbot se estiman con tipoEstudiante porque hoy Reportes no consume un endpoint separado del bot.",
                f"Sede con más matrículas (mes): {top_sede} ({top_sede_n})" if top_sede_n else "Sin matrículas para este periodo.",
                f"Categoría más común (mes): {top_cat} ({top_cat_n})" if top_cat_n else "—",
                f"Activos en el sistema: {activos}/{total}",
                f"Promedio de horas (mes): {avg_h:.1f}",
            ],
            "tops": {
                "Top sedes": [(k, str(v)) for k, v in sede_counts.most_common(5)],
                "Top categorías": [(k, str(v)) for k, v in cat_counts.most_common(5)],
            },
        }

        return {"tipo": tipo, "data": detalle, "analysis": analysis}

    def _build_estado_cuenta_report_state(self, tipo: str, force_refresh: bool = True):
        raw_ec = self.app.api.get_all("estados-cuenta", force_refresh=force_refresh) or []
        estados = self._unwrap_list(raw_ec, prefer_keys=("estados-cuenta", "estadosCuenta", "estados"))

        raw_est = self.app.api.get_all("estudiantes", force_refresh=False) or []
        estudiantes = self._unwrap_list(raw_est, prefer_keys=("estudiantes",))
        id_to_student = {}
        for e in estudiantes:
            eid = e.get("id") or e.get("idEstudiante")
            if eid is not None:
                id_to_student[str(eid)] = e

        def estado_calc(total, pagado):
            try:
                total = float(total or 0)
                pagado = float(pagado or 0)
                if pagado <= 0:
                    return "Pendiente"
                if abs(pagado - total) < 1e-6:
                    return "Pagado"
                if 0 < pagado < total:
                    return "En deuda"
            except Exception:
                pass
            return "—"

        detalle = []
        total_total = 0.0
        total_pagado = 0.0
        saldo_total = 0.0
        estado_counts = Counter()
        saldo_por_sede = defaultdict(float)
        saldos = []

        for r in estados:
            eid = r.get("idEstudiante") or r.get("id_estudiante") or r.get("estudianteId")
            stu = id_to_student.get(str(eid)) or {}
            nombre = f"{stu.get('nombre','')} {stu.get('apellido','')}".strip() or str(eid or "—")
            sede = self._record_sede(stu) or "—"

            total = float(r.get("montoTotal") or 0)
            pagado = float(r.get("montoPagado") or 0)
            saldo = total - pagado
            estado = (r.get("estado") or "").strip() or estado_calc(total, pagado)

            total_total += total
            total_pagado += pagado
            saldo_total += saldo
            estado_counts[estado] += 1

            if sede and sede != "—":
                saldo_por_sede[sede] += saldo

            if saldo > 0:
                saldos.append((nombre, saldo))

            detalle.append({
                "Estudiante": nombre,
                "Sede": sede,
                "Monto total": self._format_money(total),
                "Pagado": self._format_money(pagado),
                "Saldo": self._format_money(saldo),
                "Estado": estado,
            })

        top_deudor = max(saldos, key=lambda x: x[1]) if saldos else ("—", 0.0)
        top_sede = max(saldo_por_sede.items(), key=lambda x: x[1]) if saldo_por_sede else ("—", 0.0)

        ratio = (total_pagado / total_total) if total_total > 0 else 0.0
        estados_txt = " | ".join([f"{k}: {v}" for k, v in estado_counts.most_common(4)]) if estado_counts else "—"

        analysis = {
            "kpis": [
                ("Cuentas", str(len(estados))),
                ("Monto total", self._format_money(total_total)),
                ("Pagado", self._format_money(total_pagado)),
                ("Saldo", self._format_money(saldo_total)),
            ],
            "insights": [
                f"Nivel de recaudo: {ratio:.0%}",
                f"Estados: {estados_txt}",
                f"Mayor saldo: {top_deudor[0]} ({self._format_money(top_deudor[1])})" if top_deudor[1] else "Sin saldos pendientes.",
                f"Sede con mayor cartera: {top_sede[0]} ({self._format_money(top_sede[1])})" if top_sede[1] else "—",
            ],
            "tops": {
                "Top saldos": [(n, self._format_money(v)) for n, v in sorted(saldos, key=lambda x: x[1], reverse=True)[:5]],
                "Top sedes": [(s, self._format_money(v)) for s, v in sorted(saldo_por_sede.items(), key=lambda x: x[1], reverse=True)[:5]],
            },
        }

        return {"tipo": tipo, "data": detalle, "analysis": analysis}

    def _build_clases_report_state(self, tipo: str, month: int, year: int, force_refresh: bool = True):
        raw_cl = self.app.api.get_all("clases-practicas", force_refresh=force_refresh) or []
        clases = self._unwrap_list(raw_cl, prefer_keys=("clases", "clases-practicas", "items"))
        clases_mes = self._filter_by_month(clases, month, year, ("fecha",))

        raw_est = self.app.api.get_all("estudiantes", force_refresh=False) or []
        estudiantes = self._unwrap_list(raw_est, prefer_keys=("estudiantes",))
        id_to_student = {}
        for e in estudiantes:
            eid = e.get("id") or e.get("idEstudiante")
            if eid is not None:
                id_to_student[str(eid)] = e

        raw_prof = self.app.api.get_all("profesores", force_refresh=False) or []
        profesores = self._unwrap_list(raw_prof, prefer_keys=("profesores",))
        id_to_prof = {}
        for p in profesores:
            pid = p.get("id") or p.get("idProfesor")
            if pid is not None:
                id_to_prof[str(pid)] = p

        raw_veh = self.app.api.get_all("vehiculos", force_refresh=False) or []
        vehiculos = self._unwrap_list(raw_veh, prefer_keys=("vehiculos",))
        placa_to_veh = {}
        for v in vehiculos:
            placa = str(v.get("placa") or "").strip().upper()
            if placa:
                placa_to_veh[placa] = v

        detalle = []
        estado_counts = Counter()
        inst_counts = Counter()
        sede_counts = Counter()
        hour_counts = Counter()
        total_horas = 0.0

        for c in clases_mes:
            eid = c.get("id_estudiante") or c.get("idEstudiante") or c.get("estudianteId")
            pid = (
                c.get("id_profesor") or c.get("idProfesor")
                or c.get("id_instructor") or c.get("idInstructor")
            )
            placa = str(c.get("placa_vehiculo") or c.get("placaVehiculo") or "").strip().upper()

            stu = id_to_student.get(str(eid)) or {}
            prof = id_to_prof.get(str(pid)) or {}
            veh = placa_to_veh.get(placa) or {}

            stu_name = f"{stu.get('nombre','')} {stu.get('apellido','')}".strip() or str(eid or "—")
            prof_name = f"{prof.get('nombre','')} {prof.get('apellido','')}".strip() or str(pid or "—")

            fecha = str(c.get("fecha") or "")[:10] or "—"
            hi = str(c.get("horaInicio") or "").strip() or "—"
            hf = str(c.get("horaFin") or "").strip() or "—"
            dur = self._duration_hours(hi, hf)
            total_horas += dur

            sede = self._record_sede(c) or self._record_sede(stu) or self._record_sede(veh) or "—"
            estado = str(c.get("estado") or c.get("estadoClase") or "").strip() or "—"

            estado_counts[estado] += 1
            inst_counts[prof_name] += 1
            sede_counts[sede] += 1
            if hi and hi != "—":
                hour_counts[hi] += 1

            detalle.append({
                "Fecha": fecha,
                "Inicio": hi,
                "Fin": hf,
                "Duración (h)": f"{dur:.2f}",
                "Estudiante": stu_name,
                "Instructor": prof_name,
                "Placa": placa or "—",
                "Sede": sede,
                "Estado": estado,
            })

        top_inst, top_inst_n = ("—", 0)
        if inst_counts:
            top_inst, top_inst_n = inst_counts.most_common(1)[0]

        top_sede, top_sede_n = ("—", 0)
        if sede_counts:
            top_sede, top_sede_n = sede_counts.most_common(1)[0]

        top_hour, top_hour_n = ("—", 0)
        if hour_counts:
            top_hour, top_hour_n = hour_counts.most_common(1)[0]

        programadas = 0
        canceladas = 0
        for k, v in estado_counts.items():
            lk = str(k).lower()
            if lk == "programada":
                programadas += v
            if "cancel" in lk:
                canceladas += v

        estados_txt = " | ".join([f"{k}: {v}" for k, v in estado_counts.most_common(4)]) if estado_counts else "—"

        analysis = {
            "kpis": [
                ("Clases (mes)", str(len(clases_mes))),
                ("Horas", f"{total_horas:.2f}"),
                ("Programadas", str(programadas)),
                ("Canceladas", str(canceladas)),
            ],
            "insights": [
                f"Instructor con más clases: {top_inst} ({top_inst_n})" if top_inst_n else "Sin clases para este periodo.",
                f"Sede más usada: {top_sede} ({top_sede_n})" if top_sede_n else "—",
                f"Hora pico: {top_hour} ({top_hour_n})" if top_hour_n else "—",
                f"Estados: {estados_txt}",
            ],
            "tops": {
                "Top instructores": [(k, str(v)) for k, v in inst_counts.most_common(5)],
                "Top horarios": [(k, str(v)) for k, v in hour_counts.most_common(5)],
                "Top sedes": [(k, str(v)) for k, v in sede_counts.most_common(5)],
            },
        }

        return {"tipo": tipo, "data": detalle, "analysis": analysis}

    # =====================================================
    #                     RENDER TABLA (LEGACY)
    # =====================================================
    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()

        def C(name, default):
            return getattr(self.app, name, default)

        RED = C("COLOR_RED", ("#E53935", "#ff4c4c"))
        MUST = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))
        BLUE = ("#2563eb", "#60a5fa")
        GREEN = ("#16a34a", "#22c55e")

        RED_BG = C("RED_SOFT_BG", ("#FEF2F2", "#2a1515"))
        MUST_BG = C("MUSTARD_SOFT_BG", ("#FFF8E1", "#2a2618"))
        GREEN_BG = ("#DCFCE7", "#0d2a1a")
        BLUE_BG = ("#EFF6FF", "#0b1e35")

        def badge_style(text: str):
            s = str(text or "").strip().lower()
            if not s or s in {"—", "-"}:
                return self.app.COLOR_INPUT_BG, self.app.COLOR_TEXT

            if any(k in s for k in ("pagado", "activo", "dictada")):
                return GREEN_BG, GREEN
            if any(k in s for k in ("program", "pend")):
                return MUST_BG, MUST
            if any(k in s for k in ("en deuda", "deuda")):
                return RED_BG, RED
            if any(k in s for k in ("cancel", "inactivo")):
                return RED_BG, RED
            return self.app.COLOR_INPUT_BG, self.app.COLOR_MUTED

        def parse_money_str(value):
            try:
                s = str(value or "").strip()
                if not s:
                    return None
                sign = -1 if s.startswith("-") else 1
                s = s.replace("$", "").replace(",", "").replace(" ", "").replace("\u00A0", "")
                s = s.replace("-", "")
                return sign * float(s)
            except Exception:
                return None

        tipo = getattr(self, "_tipo", "") or ""
        t = self._tipo_norm(tipo)

        if "estado" in t:
            colspec = [
                ("Estudiante", 280, 1, "w"),
                ("Sede", 160, 0, "w"),
                ("Monto total", 120, 0, "e"),
                ("Pagado", 120, 0, "e"),
                ("Saldo", 120, 0, "e"),
                ("Estado", 120, 0, "center"),
            ]
            accent = RED
        elif "clase" in t:
            colspec = [
                ("Fecha", 120, 0, "center"),
                ("Inicio", 80, 0, "center"),
                ("Fin", 80, 0, "center"),
                ("Duración (h)", 110, 0, "center"),
                ("Estudiante", 260, 1, "w"),
                ("Instructor", 220, 1, "w"),
                ("Placa", 90, 0, "center"),
                ("Sede", 160, 0, "w"),
                ("Estado", 120, 0, "center"),
            ]
            accent = MUST
        else:
            colspec = [
                ("ID", 70, 0, "center"),
                ("Nombre", 260, 1, "w"),
                ("Documento", 150, 0, "w"),
                ("Estado", 120, 0, "center"),
                ("Categoría", 110, 0, "center"),
                ("Sede", 160, 0, "w"),
                ("Horas", 80, 0, "center"),
                ("Ingreso", 120, 0, "center"),
            ]
            accent = BLUE

        if not self._data:
            card = ctk.CTkFrame(
                self.table,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=14,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )
            card.pack(fill="x", padx=12, pady=12)
            ctk.CTkLabel(
                card,
                text="📭 Sin resultados",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(padx=14, pady=(14, 4), anchor="w")
            ctk.CTkLabel(
                card,
                text="Cambia el mes/año o el tipo de reporte y vuelve a generar.",
                text_color=self.app.COLOR_MUTED,
            ).pack(padx=14, pady=(0, 14), anchor="w")
            return

        strip = ctk.CTkFrame(self.table, fg_color=accent, corner_radius=999, height=6)
        strip.pack(fill="x", padx=12, pady=(10, 6))

        header = ctk.CTkFrame(
            self.table,
            fg_color=self.app.COLOR_INPUT_BG,
            corner_radius=12,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        header.pack(fill="x", padx=12, pady=(0, 6))

        for i, (name, minw, weight, _anchor) in enumerate(colspec):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)
            ctk.CTkLabel(
                header,
                text=name,
                text_color=self.app.COLOR_MUTED,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
            ).grid(row=0, column=i, padx=10, pady=10, sticky="ew")

        for idx, rec in enumerate(self._data):
            row_bg = self.app.COLOR_PANEL if idx % 2 == 0 else self.app.COLOR_BG
            row = ctk.CTkFrame(
                self.table,
                fg_color=row_bg,
                corner_radius=12,
                border_width=1,
                border_color=self.app.COLOR_DIVIDER,
            )
            row.pack(fill="x", padx=12, pady=4)

            for i, (name, minw, weight, anchor) in enumerate(colspec):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)
                val = rec.get(name, "")

                # Badge para "Estado"
                if name == "Estado":
                    b_bg, b_txt = badge_style(val)
                    badge = ctk.CTkLabel(
                        row,
                        text=str(val if val is not None else ""),
                        fg_color=b_bg,
                        text_color=b_txt,
                        corner_radius=999,
                        height=28,
                        padx=12,
                    )
                    badge.grid(row=0, column=i, padx=10, pady=10, sticky="w")
                    continue

                # Colores por columnas clave
                txt_color = self.app.COLOR_TEXT
                if "estado" in t and name in {"Pagado"}:
                    txt_color = GREEN
                if "estado" in t and name in {"Saldo"}:
                    saldo_v = parse_money_str(val)
                    txt_color = RED if (saldo_v or 0) > 0 else GREEN
                if "clase" in t and name in {"Duración (h)"}:
                    txt_color = MUST

                wrap = 0
                justify = "left"
                if name in {"Nombre", "Estudiante", "Instructor"}:
                    wrap = 360

                ctk.CTkLabel(
                    row,
                    text=str(val if val is not None else ""),
                    text_color=txt_color,
                    anchor=anchor,
                    justify=justify,
                    wraplength=wrap,
                ).grid(row=0, column=i, padx=10, pady=10, sticky="ew")

    def _render_table(self):
        def C(name, default):
            return getattr(self.app, name, default)

        red = C("COLOR_RED", ("#E53935", "#ff4c4c"))
        must = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))
        dark = C("COLOR_TEXT", ("#111111", "#F3F3F3"))
        soft_red = C("RED_SOFT_BG", ("#FEF2F2", "#2a1515"))
        soft_must = C("MUSTARD_SOFT_BG", ("#FFF8E1", "#2a2618"))
        neutral_bg = C("COLOR_INPUT_BG", ("#F5F5F5", "#202020"))

        if not hasattr(self, "_table_toolbar") or not self._table_toolbar.winfo_exists():
            self._table_toolbar = ctk.CTkFrame(
                self.table,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=16,
                border_width=1,
                border_color=self.app.COLOR_DIVIDER,
            )
            self._table_toolbar.pack(fill="x", padx=12, pady=(10, 8))
            self._table_toolbar.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                self._table_toolbar,
                text="Buscar estudiante",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=0, column=0, padx=(14, 10), pady=(12, 4), sticky="w")

            self.en_table_search = ctk.CTkEntry(
                self._table_toolbar,
                placeholder_text="Escribe nombre, documento, sede o estado",
                height=42,
                corner_radius=14,
                border_width=2,
                border_color=self.app.COLOR_YELLOW,
            )
            self.en_table_search.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
            self.en_table_search.bind("<KeyRelease>", self._on_table_search)

            ctk.CTkButton(
                self._table_toolbar,
                text="Limpiar",
                height=42,
                width=120,
                corner_radius=16,
                fg_color=self.app.COLOR_RED,
                hover_color=self.app.COLOR_YELLOW,
                command=self._clear_table_search,
            ).grid(row=1, column=2, padx=(0, 14), pady=(0, 12), sticky="e")

        if not hasattr(self, "_table_rows_host") or not self._table_rows_host.winfo_exists():
            self._table_rows_host = ctk.CTkFrame(self.table, fg_color="transparent")
            self._table_rows_host.pack(fill="both", expand=True, padx=0, pady=0)
        else:
            for w in self._table_rows_host.winfo_children():
                w.destroy()

        def badge_style(text: str):
            s = str(text or "").strip().lower()
            if not s or s in {"—", "-"}:
                return neutral_bg, self.app.COLOR_TEXT
            if any(k in s for k in ("pagado", "activo", "dictada")):
                return soft_red, red
            if any(k in s for k in ("program", "pend")):
                return soft_must, must
            if any(k in s for k in ("en deuda", "deuda", "cancel", "inactivo")):
                return soft_red, red
            return neutral_bg, self.app.COLOR_MUTED

        def parse_money_str(value):
            try:
                s = str(value or "").strip()
                if not s:
                    return None
                sign = -1 if s.startswith("-") else 1
                s = s.replace("$", "").replace(",", "").replace(" ", "").replace("\u00A0", "")
                s = s.replace("-", "")
                return sign * float(s)
            except Exception:
                return None

        tipo = getattr(self, "_tipo", "") or ""
        t = self._tipo_norm(tipo)

        if "estado" in t:
            colspec = [
                ("Estudiante", 280, 1, "w"),
                ("Sede", 160, 0, "w"),
                ("Monto total", 120, 0, "e"),
                ("Pagado", 120, 0, "e"),
                ("Saldo", 120, 0, "e"),
                ("Estado", 120, 0, "center"),
            ]
            accent = red
        elif "clase" in t:
            colspec = [
                ("Fecha", 120, 0, "center"),
                ("Inicio", 80, 0, "center"),
                ("Fin", 80, 0, "center"),
                ("Duración (h)", 110, 0, "center"),
                ("Estudiante", 260, 1, "w"),
                ("Instructor", 220, 1, "w"),
                ("Placa", 90, 0, "center"),
                ("Sede", 160, 0, "w"),
                ("Estado", 120, 0, "center"),
            ]
            accent = must
        else:
            colspec = [
                ("ID", 70, 0, "center"),
                ("Nombre", 260, 1, "w"),
                ("Documento", 150, 0, "w"),
                ("Estado", 120, 0, "center"),
                ("Categoría", 110, 0, "center"),
                ("Sede", 160, 0, "w"),
                ("Horas", 80, 0, "center"),
                ("Días restantes", 110, 0, "center"),
                ("Ingreso", 120, 0, "center"),
            ]
            accent = dark

        query = str(getattr(self, "_table_query", "") or "").lower()
        filtered_data = []
        for rec in self._data:
            if not query:
                filtered_data.append(rec)
                continue
            haystack = " ".join(
                str(v)
                for k, v in (rec or {}).items()
                if not str(k).startswith("_") and v not in (None, "")
            ).lower()
            if query in haystack:
                filtered_data.append(rec)

        if not filtered_data:
            card = ctk.CTkFrame(
                self._table_rows_host,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=14,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )
            card.pack(fill="x", padx=12, pady=12)
            ctk.CTkLabel(
                card,
                text="Sin resultados",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(padx=14, pady=(14, 4), anchor="w")
            ctk.CTkLabel(
                card,
                text="Ajusta la búsqueda o genera otro reporte para ver datos.",
                text_color=self.app.COLOR_MUTED,
            ).pack(padx=14, pady=(0, 14), anchor="w")
            return

        strip = ctk.CTkFrame(self._table_rows_host, fg_color=accent, corner_radius=999, height=6)
        strip.pack(fill="x", padx=12, pady=(2, 6))

        header = ctk.CTkFrame(
            self._table_rows_host,
            fg_color=self.app.COLOR_INPUT_BG,
            corner_radius=12,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        header.pack(fill="x", padx=12, pady=(0, 6))

        for i, (name, minw, weight, _anchor) in enumerate(colspec):
            header.grid_columnconfigure(i, minsize=minw, weight=weight)
            ctk.CTkLabel(
                header,
                text=name,
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=i, padx=10, pady=12, sticky="ew")

        for idx, rec in enumerate(filtered_data):
            row_bg = self.app.COLOR_PANEL if idx % 2 == 0 else self.app.COLOR_BG
            row = ctk.CTkFrame(
                self._table_rows_host,
                fg_color=row_bg,
                corner_radius=12,
                border_width=1,
                border_color=self.app.COLOR_DIVIDER,
            )
            row.pack(fill="x", padx=12, pady=4)

            for i, (name, minw, weight, anchor) in enumerate(colspec):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)
                val = rec.get(name, "")

                if name == "Estado":
                    b_bg, b_txt = badge_style(val)
                    ctk.CTkLabel(
                        row,
                        text=str(val if val is not None else ""),
                        fg_color=b_bg,
                        text_color=b_txt,
                        corner_radius=999,
                        height=28,
                        padx=12,
                    ).grid(row=0, column=i, padx=10, pady=10, sticky="w")
                    continue

                txt_color = self.app.COLOR_TEXT
                if "estado" in t and name in {"Pagado"}:
                    txt_color = red
                if "estado" in t and name in {"Saldo"}:
                    saldo_v = parse_money_str(val)
                    txt_color = red if (saldo_v or 0) > 0 else dark
                if "clase" in t and name in {"Duración (h)"}:
                    txt_color = must

                wrap = 0
                if name in {"Nombre", "Estudiante", "Instructor"}:
                    wrap = 360

                ctk.CTkLabel(
                    row,
                    text=str(val if val is not None else ""),
                    text_color=txt_color,
                    anchor=anchor,
                    justify="left",
                    wraplength=wrap,
                ).grid(row=0, column=i, padx=10, pady=10, sticky="ew")

    def _render_table(self):
        def C(name, default):
            return getattr(self.app, name, default)

        def solid(value, fallback):
            if isinstance(value, (tuple, list)) and value:
                return str(value[0] or fallback)
            if value in (None, ""):
                return fallback
            return str(value)

        red = C("COLOR_RED", ("#E53935", "#ff4c4c"))
        must = C("COLOR_YELLOW", ("#D4A017", "#E0B43F"))
        dark = C("COLOR_TEXT", ("#111111", "#F3F3F3"))

        if not hasattr(self, "_table_toolbar") or not self._table_toolbar.winfo_exists():
            self._table_toolbar = ctk.CTkFrame(
                self.table,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=16,
                border_width=1,
                border_color=self.app.COLOR_DIVIDER,
            )
            self._table_toolbar.pack(fill="x", padx=12, pady=(10, 8))
            self._table_toolbar.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                self._table_toolbar,
                text="Buscar estudiante",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=0, column=0, padx=(14, 10), pady=(12, 4), sticky="w")

            self.en_table_search = ctk.CTkEntry(
                self._table_toolbar,
                placeholder_text="Escribe nombre, documento, sede o estado",
                height=42,
                corner_radius=14,
                border_width=2,
                border_color=self.app.COLOR_YELLOW,
            )
            self.en_table_search.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
            self.en_table_search.bind("<KeyRelease>", self._on_table_search)

            ctk.CTkButton(
                self._table_toolbar,
                text="Limpiar",
                height=42,
                width=120,
                corner_radius=16,
                fg_color=self.app.COLOR_RED,
                hover_color=self.app.COLOR_YELLOW,
                command=self._clear_table_search,
            ).grid(row=1, column=2, padx=(0, 14), pady=(0, 12), sticky="e")

        if not hasattr(self, "_table_rows_host") or not self._table_rows_host.winfo_exists():
            self._table_rows_host = ctk.CTkFrame(self.table, fg_color="transparent")
            self._table_rows_host.pack(fill="both", expand=True, padx=0, pady=0)
        else:
            for w in self._table_rows_host.winfo_children():
                w.destroy()

        tipo = getattr(self, "_tipo", "") or ""
        t = self._tipo_norm(tipo)

        if "estado" in t:
            colspec = [
                ("Estudiante", 320, "w"),
                ("Sede", 170, "w"),
                ("Monto total", 130, "e"),
                ("Pagado", 130, "e"),
                ("Saldo", 130, "e"),
                ("Estado", 130, "center"),
            ]
            accent = red
        elif "clase" in t:
            colspec = [
                ("Fecha", 120, "center"),
                ("Inicio", 80, "center"),
                ("Fin", 80, "center"),
                ("Duración (h)", 120, "center"),
                ("Estudiante", 320, "w"),
                ("Instructor", 260, "w"),
                ("Placa", 100, "center"),
                ("Sede", 170, "w"),
                ("Estado", 130, "center"),
            ]
            accent = must
        else:
            colspec = [
                ("ID", 70, "center"),
                ("Nombre", 420, "w"),
                ("Documento", 150, "w"),
                ("Estado", 120, "center"),
                ("Categoría", 120, "center"),
                ("Sede", 170, "w"),
                ("Horas", 90, "center"),
                ("Días restantes", 120, "center"),
                ("Ingreso", 120, "center"),
            ]
            accent = dark

        query = str(getattr(self, "_table_query", "") or "").lower()
        filtered_data = []
        for rec in self._data:
            if not query:
                filtered_data.append(rec)
                continue
            haystack = " ".join(
                str(v)
                for k, v in (rec or {}).items()
                if not str(k).startswith("_") and v not in (None, "")
            ).lower()
            if query in haystack:
                filtered_data.append(rec)

        if not filtered_data:
            card = ctk.CTkFrame(
                self._table_rows_host,
                fg_color=self.app.COLOR_PANEL,
                corner_radius=14,
                border_width=2,
                border_color=self.app.COLOR_DIVIDER,
            )
            card.pack(fill="x", padx=12, pady=12)
            ctk.CTkLabel(
                card,
                text="Sin resultados",
                text_color=self.app.COLOR_TEXT,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(padx=14, pady=(14, 4), anchor="w")
            ctk.CTkLabel(
                card,
                text="Ajusta la búsqueda o genera otro reporte para ver datos.",
                text_color=self.app.COLOR_MUTED,
            ).pack(padx=14, pady=(0, 14), anchor="w")
            return

        strip = ctk.CTkFrame(self._table_rows_host, fg_color=accent, corner_radius=999, height=6)
        strip.pack(fill="x", padx=12, pady=(2, 6))

        tree_wrap = ctk.CTkFrame(
            self._table_rows_host,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=self.app.COLOR_DIVIDER,
        )
        tree_wrap.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Reportes.Treeview",
            background=_solid_color(self.app.COLOR_PANEL, "#FFFFFF"),
            fieldbackground=_solid_color(self.app.COLOR_PANEL, "#FFFFFF"),
            foreground=_solid_color(self.app.COLOR_TEXT, "#111111"),
            bordercolor=_solid_color(self.app.COLOR_DIVIDER, "#E5E7EB"),
            lightcolor=_solid_color(self.app.COLOR_DIVIDER, "#E5E7EB"),
            darkcolor=_solid_color(self.app.COLOR_DIVIDER, "#E5E7EB"),
            rowheight=30,
        )
        style.map(
            "Reportes.Treeview",
            background=[("selected", _solid_color(self.app.MUSTARD_SOFT_BG, "#FFF8E1"))],
            foreground=[("selected", _solid_color(self.app.COLOR_TEXT, "#111111"))],
        )
        style.configure(
            "Reportes.Treeview.Heading",
            background=_solid_color(self.app.COLOR_BG, "#F5F7FB"),
            foreground=_solid_color(self.app.COLOR_TEXT, "#111111"),
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )

        cols = [name for name, _width, _anchor in colspec]
        tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", style="Reportes.Treeview")
        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for name, width, anchor in colspec:
            tree.heading(name, text=name)
            tree.column(name, width=width, minwidth=max(70, int(width * 0.8)), stretch=False, anchor=anchor)

        tree.tag_configure("even", background=_solid_color(self.app.COLOR_PANEL, "#FFFFFF"), foreground=_solid_color(self.app.COLOR_TEXT, "#111111"))
        tree.tag_configure("odd", background=_solid_color(self.app.COLOR_BG, "#F8F8F8"), foreground=_solid_color(self.app.COLOR_TEXT, "#111111"))

        for idx, rec in enumerate(filtered_data):
            values = [str(rec.get(name, "") if rec.get(name, "") is not None else "") for name, _width, _anchor in colspec]
            tree.insert("", "end", values=values, tags=("even" if idx % 2 == 0 else "odd",))

    def _on_table_search(self, _event=None):
        if hasattr(self, "en_table_search"):
            self._table_query = self.en_table_search.get()
        job = getattr(self, "_table_search_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._table_search_job = self.after(120, self._apply_table_search)

    def _apply_table_search(self):
        self._table_search_job = None
        self._render_table()

    def _restore_table_search_focus(self, cursor_pos=None):
        if not hasattr(self, "en_table_search"):
            return
        try:
            self.en_table_search.focus_set()
            if cursor_pos is None:
                cursor_pos = len(self.en_table_search.get())
            self.en_table_search.icursor(cursor_pos)
        except Exception:
            pass

    def _clear_table_search(self):
        job = getattr(self, "_table_search_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            self._table_search_job = None
        self._table_query = ""
        if hasattr(self, "en_table_search"):
            self.en_table_search.delete(0, "end")
            self.after_idle(self.en_table_search.focus_set)
        self._render_table()

    # =====================================================
    #                     ACCIONES
    # =====================================================
    def _generar(self, force_refresh=True):
        tipo = self.cb_tipo.get()
        mes_nombre = self.cb_mes.get()
        anio_txt = self.cb_anio.get()

        try:
            year = int(anio_txt)
        except Exception:
            year = datetime.now().year

        month = None
        try:
            if hasattr(self, "_MESES") and mes_nombre in (self._MESES or []):
                month = self._MESES.index(mes_nombre) + 1
        except Exception:
            month = None
        month = month or datetime.now().month

        self._tipo = tipo
        self._report_month = month
        self._report_year = year

        self.app._info(f"Generando reporte de {tipo} para {mes_nombre} {year}...")

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                state = self._build_report_state(tipo, month, year, force_refresh=force_refresh)
                self.after(0, lambda: self._apply_report_state(state))
                self.after(0, lambda: self.app._info(f"Reporte de {tipo} generado correctamente."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Reportes", f"No fue posible generar el reporte:\n{e}", parent=self))
                self.after(0, lambda: self._apply_report_state(self._empty_report_state()))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _exportar(self):
        if not self._data:
            messagebox.showinfo("Exportar", "Primero genera un reporte.", parent=self)
            return

        t = self._tipo_norm(self._tipo)
        if "estudiante" in t:
            self._exportar_estudiantes_pdf()
        elif "estado" in t:
            self._exportar_estado_cuenta_pdf()
        else:
            self._exportar_clases_pdf()

    def _refrescar(self):
        self._generar(force_refresh=True)
        self.app._info("Vista de reportes actualizada.")

    # =====================================================
    #                 REPORTES PDF INDIVIDUALES
    # =====================================================
    def _exportar_estudiantes_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="Reporte_Estudiantes.pdf"
        )
        if not path:
            return

        doc = self._make_doc(path)
        st = self._styles()

        elems = []
        elems.append(Paragraph("Reporte de Estudiantes", st["title"]))

        mes_nombre = ""
        try:
            mes_nombre = self._MESES[self._report_month - 1]
        except Exception:
            mes_nombre = str(getattr(self, "_report_month", ""))

        elems.append(Paragraph(
            f"Periodo: {mes_nombre} {getattr(self, '_report_year', '')} — Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            st["meta"]
        ))

        # Resumen (KPIs)
        kpis = (self._analysis or {}).get("kpis") or []
        if kpis:
            resumen = [[k, v] for k, v in kpis]
            resumen_table = Table(resumen, colWidths=[6.0 * cm, 9.0 * cm])
            resumen_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]))
            elems.append(resumen_table)
            elems.append(Spacer(1, 12))

        # Análisis
        insights = (self._analysis or {}).get("insights") or []
        if insights:
            elems.append(Paragraph("Análisis", st["base"]["Heading2"]))
            txt = "<br/>".join([f"- {s}" for s in insights])
            elems.append(Paragraph(txt, st["normal"]))
            elems.append(Spacer(1, 12))

        # Tabla detalle (compacta para PDF)
        headers = ["ID", "Nombre", "Documento", "Estado", "Sede", "Días restantes", "Ingreso"]
        rows = [headers] + [[r.get(h, "") for h in headers] for r in (self._data or [])]
        elems.append(self._table_pro(rows, col_widths=[1.2*cm, 4.8*cm, 2.4*cm, 2.0*cm, 2.2*cm, 2.2*cm, 2.2*cm]))

        header_draw = self._header_canvas()
        doc.build(elems, onFirstPage=header_draw, onLaterPages=header_draw)
        messagebox.showinfo("PDF", f"Reporte de estudiantes exportado:\n{path}")

    def _exportar_estado_cuenta_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="Reporte_Estado_Cuenta.pdf"
        )
        if not path:
            return

        doc = self._make_doc(path)
        st = self._styles()

        elems = []
        elems.append(Paragraph("Estado de Cuenta", st["title"]))
        elems.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", st["meta"]))

        # Resumen (KPIs)
        kpis = (self._analysis or {}).get("kpis") or []
        if kpis:
            resumen = [[k, v] for k, v in kpis]
            resumen_table = Table(resumen, colWidths=[6.0 * cm, 9.0 * cm])
            resumen_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]))
            elems.append(resumen_table)
            elems.append(Spacer(1, 12))

        # Análisis
        insights = (self._analysis or {}).get("insights") or []
        if insights:
            elems.append(Paragraph("Análisis", st["base"]["Heading2"]))
            txt = "<br/>".join([f"- {s}" for s in insights])
            elems.append(Paragraph(txt, st["normal"]))
            elems.append(Spacer(1, 12))

        # Tabla detalle
        headers = ["Estudiante", "Sede", "Monto total", "Pagado", "Saldo", "Estado"]
        rows = [headers] + [[r.get(h, "") for h in headers] for r in (self._data or [])]
        elems.append(self._table_pro(rows, col_widths=[5.7*cm, 2.3*cm, 2.4*cm, 2.4*cm, 2.4*cm, 1.8*cm]))

        header_draw = self._header_canvas()
        doc.build(elems, onFirstPage=header_draw, onLaterPages=header_draw)
        messagebox.showinfo("PDF", f"Reporte de estado de cuenta exportado:\n{path}")

    def _exportar_clases_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="Reporte_Clases_Practicas.pdf"
        )
        if not path:
            return

        doc = self._make_doc(path)
        st = self._styles()

        elems = []
        elems.append(Paragraph("Reporte de Clases Prácticas", st["title"]))

        mes_nombre = ""
        try:
            mes_nombre = self._MESES[self._report_month - 1]
        except Exception:
            mes_nombre = str(getattr(self, "_report_month", ""))

        elems.append(Paragraph(
            f"Periodo: {mes_nombre} {getattr(self, '_report_year', '')} — Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            st["meta"]
        ))

        # Resumen (KPIs)
        kpis = (self._analysis or {}).get("kpis") or []
        if kpis:
            resumen = [[k, v] for k, v in kpis]
            resumen_table = Table(resumen, colWidths=[6.0 * cm, 9.0 * cm])
            resumen_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]))
            elems.append(resumen_table)
            elems.append(Spacer(1, 12))

        # Análisis
        insights = (self._analysis or {}).get("insights") or []
        if insights:
            elems.append(Paragraph("Análisis", st["base"]["Heading2"]))
            txt = "<br/>".join([f"- {s}" for s in insights])
            elems.append(Paragraph(txt, st["normal"]))
            elems.append(Spacer(1, 12))

        # Tabla detalle
        headers = ["Fecha", "Hora", "Estudiante", "Instructor", "Placa", "Sede", "Estado"]
        rows = [headers]
        for r in (self._data or []):
            hi = str(r.get("Inicio") or "").strip()
            hf = str(r.get("Fin") or "").strip()
            hora = (f"{hi} - {hf}".strip(" -")) if (hi or hf) else "—"
            rows.append([
                r.get("Fecha", ""),
                hora,
                r.get("Estudiante", ""),
                r.get("Instructor", ""),
                r.get("Placa", ""),
                r.get("Sede", ""),
                r.get("Estado", ""),
            ])
        elems.append(self._table_pro(rows, col_widths=[2.2*cm, 2.4*cm, 4.0*cm, 3.3*cm, 1.5*cm, 2.6*cm, 1.0*cm]))

        header_draw = self._header_canvas()
        doc.build(elems, onFirstPage=header_draw, onLaterPages=header_draw)
        messagebox.showinfo("PDF", f"Reporte de clases prácticas exportado:\n{path}")
