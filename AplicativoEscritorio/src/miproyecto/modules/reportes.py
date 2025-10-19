import customtkinter as ctk
from tkinter import messagebox
from modules.base import BaseModuleFrame


class ReportesView(BaseModuleFrame):
    """
    Vista del módulo de Reportes.
    Permite consultar, filtrar y visualizar reportes del sistema.
    (estructura compatible con el resto del aplicativo)
    """
    def __init__(self, master):
        super().__init__(master, "Reportes", "Visualización de estadísticas y reportes del sistema")

        # ===== Toolbar =====
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        for c in range(5):
            tb.grid_columnconfigure(c, weight=0)
        tb.grid_columnconfigure(5, weight=1)

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn("📊 Generar", self._generar).grid(row=0, column=0, padx=(0, 8))
        red_btn("💾 Exportar", self._exportar).grid(row=0, column=1, padx=8)
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8)

        # ===== Filtros =====
        self._build_filtros()

        # ===== Tabla / resultados =====
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)

        # ===== Data interna =====
        self._data = []
        self._rows = []

        # Render inicial
        self._render_table()

    # =====================================================
    #                     FILTROS
    # =====================================================
    def _build_filtros(self):
        filtros = ctk.CTkFrame(self, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        filtros.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        for i in range(6):
            filtros.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(filtros, text="Tipo de reporte:", text_color=self.app.COLOR_TEXT).grid(row=0, column=0, padx=8, pady=10, sticky="w")
        self.cb_tipo = ctk.CTkComboBox(filtros, values=["Estudiantes", "Instructores", "Vehículos", "Clases", "Pagos"], width=180)
        self.cb_tipo.set("Estudiantes")
        self.cb_tipo.grid(row=0, column=1, padx=8, pady=10, sticky="w")

        ctk.CTkLabel(filtros, text="Rango de fechas:", text_color=self.app.COLOR_TEXT).grid(row=0, column=2, padx=8, pady=10, sticky="w")
        self.en_fecha_ini = ctk.CTkEntry(filtros, placeholder_text="Desde (YYYY-MM-DD)", width=160)
        self.en_fecha_fin = ctk.CTkEntry(filtros, placeholder_text="Hasta (YYYY-MM-DD)", width=160)
        self.en_fecha_ini.grid(row=0, column=3, padx=4, pady=10, sticky="w")
        self.en_fecha_fin.grid(row=0, column=4, padx=4, pady=10, sticky="w")

        red_btn = ctk.CTkButton(
            filtros, text="🔍 Buscar", height=36, corner_radius=12,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff", command=self._buscar
        )
        red_btn.grid(row=0, column=5, padx=10, pady=10, sticky="e")

    # =====================================================
    #                     TABLA
    # =====================================================
    def _apply_colspecs(self, container):
        specs = [
            ("ID", 80, 0),
            ("Nombre", 220, 1),
            ("Categoría", 180, 0),
            ("Estado", 120, 0),
            ("Monto", 120, 0),
            ("Fecha", 140, 0),
        ]
        for i, (_, minw, weight) in enumerate(specs):
            container.grid_columnconfigure(i, minsize=minw, weight=weight)
        return specs

    def _render_table(self):
        for w in self.table.winfo_children(): w.destroy()
        self._rows.clear()

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        specs = self._apply_colspecs(header)

        for i, (nombre, _, _) in enumerate(specs):
            ctk.CTkLabel(header, text=nombre, text_color=self.app.COLOR_MUTED,
                         anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, rec in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")

            for i, (_, minw, weight) in enumerate(specs):
                row.grid_columnconfigure(i, minsize=minw, weight=weight)

            vals = [
                str(rec.get("id", "")),
                rec.get("nombre", ""),
                rec.get("categoria", ""),
                rec.get("estado", ""),
                f"{rec.get('monto', 0):,.2f}",
                rec.get("fecha", ""),
            ]

            for i, val in enumerate(vals):
                ctk.CTkLabel(row, text=val, text_color=self.app.COLOR_TEXT,
                             anchor="w", justify="left").grid(row=0, column=i, padx=12, pady=10, sticky="ew")

            self._rows.append(row)

    # =====================================================
    #                     ACCIONES
    # =====================================================
    def _buscar(self):
        tipo = self.cb_tipo.get()
        f_ini = self.en_fecha_ini.get().strip()
        f_fin = self.en_fecha_fin.get().strip()
        self.app._info(f"Buscando reportes de tipo '{tipo}' entre {f_ini} y {f_fin}...")

        # Simulación de datos
        self._data = [
            {"id": 1, "nombre": "Juan Pérez", "categoria": "Estudiante", "estado": "Activo", "monto": 0, "fecha": "2025-10-01"},
            {"id": 2, "nombre": "Vehículo ABC123", "categoria": "Vehículo", "estado": "Mantenimiento", "monto": 150000, "fecha": "2025-09-30"},
        ]
        self._render_table()

    def _generar(self):
        tipo = self.cb_tipo.get()
        self.app._info(f"Generando reporte de {tipo}...")
        messagebox.showinfo("Reportes", f"Reporte de {tipo} generado correctamente.", parent=self)

    def _exportar(self):
        messagebox.showinfo("Exportar", "Exportación en desarrollo (CSV / PDF).", parent=self)

    def _refrescar(self):
        self._render_table()
        self.app._info("Vista de reportes actualizada.")
