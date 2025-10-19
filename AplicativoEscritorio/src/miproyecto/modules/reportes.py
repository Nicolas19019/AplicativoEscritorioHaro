import customtkinter as ctk
from tkinter import messagebox, filedialog
from modules.base import BaseModuleFrame
from datetime import datetime
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


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
    #                     FILTROS
    # =====================================================
    def _build_filtros(self):
        filtros = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        filtros.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        filtros.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(filtros, text="Tipo de reporte:", text_color=self.app.COLOR_TEXT).grid(row=0, column=0, padx=8, pady=10, sticky="w")
        self.cb_tipo = ctk.CTkComboBox(filtros, values=["Estudiantes", "Estado de cuenta", "Clases prácticas"], width=200)
        self.cb_tipo.set("Estudiantes")
        self.cb_tipo.grid(row=0, column=1, padx=8, pady=10, sticky="w")

        ctk.CTkLabel(filtros, text="Rango de fechas:", text_color=self.app.COLOR_TEXT).grid(row=0, column=2, padx=8, pady=10, sticky="w")
        self.en_fecha_ini = ctk.CTkEntry(filtros, placeholder_text="Desde (YYYY-MM-DD)", width=160)
        self.en_fecha_fin = ctk.CTkEntry(filtros, placeholder_text="Hasta (YYYY-MM-DD)", width=160)
        self.en_fecha_ini.grid(row=0, column=3, padx=4, pady=10)
        self.en_fecha_fin.grid(row=0, column=4, padx=4, pady=10)

        ctk.CTkButton(
            filtros, text="🔍 Buscar", height=36, corner_radius=12,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff", command=self._generar
        ).grid(row=0, column=5, padx=10, pady=10, sticky="e")

    # =====================================================
    #                     RENDER TABLA
    # =====================================================
    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED).pack(pady=20)
            return

        # Encabezados
        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.pack(fill="x", padx=8, pady=(8, 4))

        for col in self._data[0].keys():
            ctk.CTkLabel(header, text=col, text_color=self.app.COLOR_MUTED, anchor="w").pack(side="left", padx=12, pady=6, expand=True)

        # Filas
        for rec in self._data:
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.pack(fill="x", padx=8, pady=4)
            for val in rec.values():
                ctk.CTkLabel(row, text=str(val), text_color=self.app.COLOR_TEXT, anchor="w").pack(side="left", padx=12, pady=8, expand=True)

    # =====================================================
    #                     ACCIONES
    # =====================================================
    def _generar(self):
        """Simula la generación de datos."""
        tipo = self.cb_tipo.get()
        self._tipo = tipo

        if tipo == "Estudiantes":
            self._data = [
                {"ID": 1, "Nombre": "Juan Pérez", "Estado": "Activo", "Ingreso": "2025-08-10"},
                {"ID": 2, "Nombre": "Ana López", "Estado": "Inactivo", "Ingreso": "2025-09-12"},
            ]
        elif tipo == "Estado de cuenta":
            self._data = [
                {"Fecha": "2025-09-01", "Concepto": "Pago matrícula", "Tipo": "Ingreso", "Monto": 200000},
                {"Fecha": "2025-09-05", "Concepto": "Compra combustible", "Tipo": "Egreso", "Monto": -50000},
            ]
        elif tipo == "Clases prácticas":
            self._data = [
                {"Fecha": "2025-10-01", "Instructor": "Carlos Ruiz", "Estudiantes": 5, "Duración (h)": 3.0},
                {"Fecha": "2025-10-02", "Instructor": "María Díaz", "Estudiantes": 4, "Duración (h)": 2.5},
            ]

        self._render_table()
        self.app._info(f"Reporte de {tipo} generado correctamente.")

    def _exportar(self):
        """Selecciona el tipo de PDF según el reporte actual."""
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
        """Reporte especializado de estudiantes."""
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                            initialfile="Reporte_Estudiantes.pdf")
        if not path:
            return

        doc = SimpleDocTemplate(path, pagesize=LETTER)
        styles = getSampleStyleSheet()
        elems = [
            Paragraph("Reporte de Estudiantes", styles["Heading1"]),
            Paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 12)
        ]

        # Tabla
        headers = list(self._data[0].keys())
        rows = [headers] + [list(r.values()) for r in self._data]

        t = Table(rows)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2d42")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ]))
        elems.append(t)

        doc.build(elems)
        messagebox.showinfo("PDF", f"Reporte de estudiantes exportado:\n{path}")

    def _exportar_estado_cuenta_pdf(self):
        """Reporte de ingresos y egresos."""
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                            initialfile="Reporte_Estado_Cuenta.pdf")
        if not path:
            return

        ingresos = sum(r["Monto"] for r in self._data if r["Monto"] > 0)
        egresos = sum(-r["Monto"] for r in self._data if r["Monto"] < 0)
        balance = ingresos - egresos

        doc = SimpleDocTemplate(path, pagesize=LETTER)
        styles = getSampleStyleSheet()
        elems = [
            Paragraph("Estado de Cuenta", styles["Heading1"]),
            Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph(f"Ingresos: ${ingresos:,.2f}", styles["Normal"]),
            Paragraph(f"Egresos: ${egresos:,.2f}", styles["Normal"]),
            Paragraph(f"Balance neto: ${balance:,.2f}", styles["Normal"]),
            Spacer(1, 12)
        ]

        headers = list(self._data[0].keys())
        rows = [headers] + [list(r.values()) for r in self._data]
        t = Table(rows)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2d42")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ]))
        elems.append(t)
        doc.build(elems)
        messagebox.showinfo("PDF", f"Reporte de estado de cuenta exportado:\n{path}")

    def _exportar_clases_pdf(self):
        """Reporte de clases prácticas."""
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                            initialfile="Reporte_Clases_Practicas.pdf")
        if not path:
            return

        total_clases = len(self._data)
        total_horas = sum(r["Duración (h)"] for r in self._data)

        doc = SimpleDocTemplate(path, pagesize=LETTER)
        styles = getSampleStyleSheet()
        elems = [
            Paragraph("Reporte de Clases Prácticas", styles["Heading1"]),
            Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph(f"Total de clases: {total_clases}", styles["Normal"]),
            Paragraph(f"Duración total: {total_horas:.2f} horas", styles["Normal"]),
            Spacer(1, 12)
        ]

        headers = list(self._data[0].keys())
        rows = [headers] + [list(r.values()) for r in self._data]
        t = Table(rows)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2d42")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ]))
        elems.append(t)
        doc.build(elems)
        messagebox.showinfo("PDF", f"Reporte de clases prácticas exportado:\n{path}")
