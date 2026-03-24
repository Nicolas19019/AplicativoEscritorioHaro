import customtkinter as ctk

class BaseModuleFrame(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = ""):
        app = self._find_app(master)
        self.app = app
        super().__init__(master, fg_color=getattr(app, "COLOR_BG", ("#FFFFFF", "#0f0f10")))
        # filas: 0 header / 1 toolbar / 2 form / 3 filtros / 4 tabla
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = self._make_header_bar(title, subtitle)
        header.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")

    def _find_app(self, widget):
        w = widget
        while w is not None:
            if hasattr(w, "APP_TITLE") and hasattr(w, "COLOR_BG"):
                return w
            w = getattr(w, "master", None)
        return widget

    def _make_header_bar(self, title: str, subtitle: str = ""):
        try:
            accent, soft_bg, soft_border = self.app.module_theme(title)
        except Exception:
            accent, soft_bg, soft_border = (self.app.COLOR_RED, self.app.RED_SOFT_BG, self.app.RED_SOFT_BORDER)

        bar = ctk.CTkFrame(
            self,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=14,
            border_width=1,
            border_color=soft_border,
        )
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=1)

        strip = ctk.CTkFrame(bar, fg_color=accent, corner_radius=999, width=6, height=1)
        strip.grid(row=0, column=0, rowspan=2 if subtitle else 1, sticky="nsw", padx=(14, 10), pady=10)
        strip.grid_propagate(False)

        ctk.CTkLabel(
            bar,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.app.COLOR_TEXT,
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 14), pady=(10, 2), sticky="w")
        if subtitle:
            ctk.CTkLabel(
                bar,
                text=subtitle,
                font=ctk.CTkFont(size=11),
                text_color=self.app.COLOR_MUTED,
                anchor="w",
            ).grid(row=1, column=1, padx=(0, 14), pady=(0, 10), sticky="w")
        return bar

    def _make_toolbar(self, master, on_new, on_edit, on_delete, on_refresh):
        tb = ctk.CTkFrame(master, fg_color="transparent")
        tb.grid_columnconfigure((0,1,2,3), weight=0)
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
                anchor="w",
            )

        action_btn("＋ Nuevo", on_new, self.app.COLOR_GREEN, self.app.GREEN_HOVER).grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")
        action_btn("✎ Editar", on_edit, self.app.COLOR_BLUE, self.app.BLUE_HOVER).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        action_btn("🗑 Eliminar", on_delete, self.app.COLOR_RED, self.app.RED_HOVER).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        action_btn("↻ Refrescar", on_refresh, self.app.COLOR_PURPLE, self.app.PURPLE_HOVER).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        return tb

    def _make_filters(self, master, p1="Buscar…", p2="Filtro"):
        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid_columnconfigure((0,1,2,3), weight=0)
        bar.grid_columnconfigure(4, weight=1)

        e1 = ctk.CTkEntry(
            bar, placeholder_text=p1, height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT, border_width=0
        )
        e1.grid(row=0, column=0, padx=(0,8), pady=6, sticky="w")

        e2 = ctk.CTkEntry(
            bar, placeholder_text=p2, height=36, corner_radius=12,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT, border_width=0
        )
        e2.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        def small_btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                bar,
                text=text,
                height=36,
                corner_radius=12,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
            )

        small_btn("Aplicar", lambda: self.app._info(f"Aplicar filtros: {e1.get()} / {e2.get()}"), self.app.MUSTARD_MAIN, self.app.MUSTARD_HOVER, txt="#111111")\
            .grid(row=0, column=2, padx=8, pady=6, sticky="w")
        small_btn("Limpiar", lambda: (e1.delete(0, "end"), e2.delete(0, "end")), self.app.COLOR_PURPLE, self.app.PURPLE_HOVER)\
            .grid(row=0, column=3, padx=8, pady=6, sticky="w")
        return bar

    def _make_filters_pro(self, master, campos=("Documento","Nombre","Apellidos"),
                          estados=("Todos","Activo","Inactivo","Suspendido")):
        panel = ctk.CTkFrame(
            master,
            fg_color=self.app.COLOR_PANEL,
            corner_radius=16,
            border_width=2,
            border_color=self.app.COLOR_DIVIDER
        )
        # Permitir que las columnas se ajusten dinámicamente
        for c in range(8):
            # las columnas de entrada (valor, estado) y los botones se expanden
            panel.grid_columnconfigure(c, weight=1 if c in (3, 5, 6, 7) else 0)


        ctk.CTkLabel(
            panel, text="Filtros", text_color=self.app.COLOR_MUTED,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")

        r = 1
        ctk.CTkLabel(panel, text="Buscar por").grid(row=r, column=0, padx=(12,8), pady=8, sticky="w")
        cb_campo = ctk.CTkComboBox(panel, values=list(campos), width=140)
        cb_campo.set(campos[0])
        cb_campo.grid(row=r, column=1, padx=(0,12), pady=8, sticky="w")

        ctk.CTkLabel(panel, text="Valor").grid(row=r, column=2, padx=(12,8), pady=8, sticky="w")
        wrap = ctk.CTkFrame(panel, fg_color="transparent")
        wrap.grid(row=r, column=3, padx=(0,12), pady=8, sticky="ew")
        wrap.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(wrap, text="🔎", width=24, text_color=self.app.COLOR_MUTED)\
            .grid(row=0, column=0, padx=(0,6), pady=0, sticky="w")
        en_valor = ctk.CTkEntry(
            wrap, height=36, corner_radius=10,
            fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
            border_width=2, border_color=self.app.COLOR_DIVIDER,
            placeholder_text="Escribe aquí…"
        )
        en_valor.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(panel, text="Estado").grid(row=r, column=4, padx=(12,8), pady=8, sticky="w")
        cb_estado = ctk.CTkComboBox(panel, values=list(estados), width=150)
        cb_estado.set(estados[0])
        cb_estado.grid(row=r, column=5, padx=(0,12), pady=8, sticky="w")

        def action_btn(text, cmd, fg, hover, txt="#ffffff"):
            return ctk.CTkButton(
                panel,
                text=text,
                height=36,
                corner_radius=12,
                fg_color=fg,
                hover_color=hover,
                text_color=txt,
                command=cmd,
            )

        action_btn("Aplicar", lambda: self.app._info(
            f"Filtrar: {cb_campo.get()} ~ '{en_valor.get()}' / Estado={cb_estado.get()}"
        ), self.app.MUSTARD_MAIN, self.app.MUSTARD_HOVER, txt="#111111").grid(row=r, column=6, padx=(4,4), pady=8, sticky="ew")

        action_btn("Limpiar", lambda: (cb_campo.set(campos[0]), en_valor.delete(0, "end"), cb_estado.set(estados[0])), self.app.COLOR_PURPLE, self.app.PURPLE_HOVER)\
            .grid(row=r, column=7, padx=(4,12), pady=8, sticky="ew")


        return panel
