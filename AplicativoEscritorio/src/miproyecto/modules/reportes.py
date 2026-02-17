import customtkinter as ctk
from tkinter import messagebox, filedialog
from modules.base import BaseModuleFrame
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


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

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd
            )

        red_btn("📊 Generar", self._generar).grid(row=0, column=0, padx=(0, 8))
        red_btn("💾 Exportar PDF", self._exportar).grid(row=0, column=1, padx=8)
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8)

        # ===== Filtros =====
        self._build_filtros()

        # ===== Tabla =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="nsew")

        # ===== Data interna =====
        self._data = []
        self._tipo = "Estudiantes"
        self._render_table()

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
            topMargin=3.0 * cm,     # deja aire para el header + logo
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
                    y = doc.pagesize[1] - doc.topMargin + 0.75 * cm  # sube un poco
                    canvas.drawImage(img, x, y, width=logo_w, height=logo_h, mask="auto")
                except Exception as e:
                    print(f"[PDF] No se pudo dibujar logo: {e}")

            # --- línea sutil separadora ---
            line_y = doc.pagesize[1] - doc.topMargin + 0.35 * cm
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
    #                     RENDER TABLA
    # =====================================================
    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED).pack(pady=20)
            return

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.pack(fill="x", padx=8, pady=(8, 4))

        for col in self._data[0].keys():
            ctk.CTkLabel(header, text=col, text_color=self.app.COLOR_MUTED, anchor="w")\
                .pack(side="left", padx=12, pady=6, expand=True)

        for rec in self._data:
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.pack(fill="x", padx=8, pady=4)
            for val in rec.values():
                ctk.CTkLabel(row, text=str(val), text_color=self.app.COLOR_TEXT, anchor="w")\
                    .pack(side="left", padx=12, pady=8, expand=True)

    # =====================================================
    #                     ACCIONES
    # =====================================================
    def _generar(self):
        tipo = self.cb_tipo.get()
        self._tipo = tipo
        mes = self.cb_mes.get()
        anio = self.cb_anio.get()

        self.app._info(f"Generando reporte de {tipo} para {mes} {anio}...")

        if tipo == "Estudiantes":
            self._data = [
                {"ID": 1, "Nombre": "Juan Pérez", "Estado": "Activo", "Ingreso": f"{anio}-08-10"},
                {"ID": 2, "Nombre": "Ana López", "Estado": "Inactivo", "Ingreso": f"{anio}-09-12"},
            ]
        elif tipo == "Estado de cuenta":
            self._data = [
                {"Fecha": f"{anio}-09-01", "Concepto": "Pago matrícula", "Tipo": "Ingreso", "Monto": 200000},
                {"Fecha": f"{anio}-09-05", "Concepto": "Compra combustible", "Tipo": "Egreso", "Monto": -50000},
            ]
        elif tipo == "Clases prácticas":
            self._data = [
                {"Fecha": f"{anio}-10-01", "Instructor": "Carlos Ruiz", "Estudiantes": 5, "Duración (h)": 3.0},
                {"Fecha": f"{anio}-10-02", "Instructor": "María Díaz", "Estudiantes": 4, "Duración (h)": 2.5},
            ]

        self._render_table()
        self.app._info(f"Reporte de {tipo} para {mes} {anio} generado correctamente.")

    def _exportar(self):
        if not self._data:
            messagebox.showinfo("Exportar", "Primero genera un reporte.", parent=self)
            return

        if self._tipo == "Estudiantes":
            self._exportar_estudiantes_pdf()
        elif self._tipo == "Estado de cuenta":
            self._exportar_estado_cuenta_pdf()
        elif self._tipo == "Clases prácticas":
            self._exportar_clases_pdf()
        else:
            messagebox.showwarning("Exportar", "Tipo de reporte no reconocido.", parent=self)

    def _refrescar(self):
        self._render_table()
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
        elems.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", st["meta"]))
        elems.append(Spacer(1, 6))

        headers = list(self._data[0].keys())
        rows = [headers] + [list(r.values()) for r in self._data]
        elems.append(self._table_pro(rows, col_widths=[2.0*cm, 7.5*cm, 3.0*cm, 3.8*cm]))

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

        ingresos = sum(r["Monto"] for r in self._data if r["Monto"] > 0)
        egresos  = sum(-r["Monto"] for r in self._data if r["Monto"] < 0)
        balance  = ingresos - egresos

        doc = self._make_doc(path)
        st = self._styles()

        elems = []
        elems.append(Paragraph("Estado de Cuenta", st["title"]))
        elems.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", st["meta"]))

        # Resumen tipo tarjeta
        resumen = [
            ["Ingresos", f"${ingresos:,.0f}"],
            ["Egresos",  f"${egresos:,.0f}"],
            ["Balance neto", f"${balance:,.0f}"],
        ]
        resumen_table = Table(resumen, colWidths=[5.0*cm, 10.0*cm])
        resumen_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F9FAFB")),
            ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E5E7EB")),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 11),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#111827")),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ]))
        elems.append(resumen_table)
        elems.append(Spacer(1, 14))

        # Movimientos
        headers = list(self._data[0].keys())
        rows = [headers]
        for r in self._data:
            monto = r.get("Monto", 0)
            rows.append([r.get("Fecha",""), r.get("Concepto",""), r.get("Tipo",""), f"{monto:,.0f}"])

        t = self._table_pro(rows, col_widths=[3.0*cm, 8.3*cm, 3.0*cm, 3.2*cm])
        # Ajustes finos de alineación por columna
        t.setStyle(TableStyle([
            ("ALIGN", (0,1), (0,-1), "LEFT"),
            ("ALIGN", (1,1), (1,-1), "LEFT"),
            ("ALIGN", (2,1), (2,-1), "CENTER"),
            ("ALIGN", (3,1), (3,-1), "RIGHT"),
            ("RIGHTPADDING", (3,1), (3,-1), 10),
        ]))
        elems.append(t)

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

        total_clases = len(self._data)
        total_horas = sum(r["Duración (h)"] for r in self._data)

        doc = self._make_doc(path)
        st = self._styles()

        elems = []
        elems.append(Paragraph("Reporte de Clases Prácticas", st["title"]))
        elems.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", st["meta"]))

        # Resumen
        resumen = [
            ["Total de clases", str(total_clases)],
            ["Duración total (h)", f"{total_horas:.2f}"],
        ]
        resumen_table = Table(resumen, colWidths=[6.0*cm, 9.0*cm])
        resumen_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F9FAFB")),
            ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E5E7EB")),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 11),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#6B7280")),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#111827")),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ]))
        elems.append(resumen_table)
        elems.append(Spacer(1, 14))

        headers = list(self._data[0].keys())
        rows = [headers] + [list(r.values()) for r in self._data]
        elems.append(self._table_pro(rows, col_widths=[3.0*cm, 6.5*cm, 3.0*cm, 3.5*cm]))

        header_draw = self._header_canvas()
        doc.build(elems, onFirstPage=header_draw, onLaterPages=header_draw)
        messagebox.showinfo("PDF", f"Reporte de clases prácticas exportado:\n{path}")
