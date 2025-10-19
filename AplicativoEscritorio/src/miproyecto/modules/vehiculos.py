import customtkinter as ctk
from tkinter import messagebox
import traceback
from modules.forms_inlines import VehiculoInlineForm
from modules.base import BaseModuleFrame


class VehiculosView(BaseModuleFrame):
    """Vista del módulo Vehículos — Gestión de automóviles de la academia."""

    # -------------------- Resolver de APP (auto) --------------------
    @staticmethod
    def _resolve_app(master):
        """
        Intenta obtener el objeto 'app' desde:
          1) master si ya es la app,
          2) master.app,
          3) ascendiendo por master.master,
          4) la ventana toplevel,
        y si no lo encuentra, crea un shim con colores y métodos mínimos.
        """
        # 1) ¿master ya es la app?
        if hasattr(master, "api") or hasattr(master, "COLOR_BG") or hasattr(master, "_info"):
            return master

        # 2) ¿master.app?
        if hasattr(master, "app"):
            return master.app

        # 3) Subir por la cadena master.master
        cur = getattr(master, "master", None)
        hops = 0
        while cur is not None and hops < 20:
            if hasattr(cur, "api") or hasattr(cur, "COLOR_BG") or hasattr(cur, "_info"):
                return cur
            if hasattr(cur, "app"):
                return cur.app
            cur = getattr(cur, "master", None)
            hops += 1

        # 4) Probar con toplevel
        try:
            top = master.winfo_toplevel()
            if hasattr(top, "api") or hasattr(top, "COLOR_BG") or hasattr(top, "_info"):
                return top
            if hasattr(top, "app"):
                return top.app
        except Exception:
            pass

        # 5) Shim mínimo para no reventar
        class _AppShim:
            def __init__(self):
                # Colores por defecto (modo oscuro)
                self.COLOR_BG       = "#0f0f10"
                self.COLOR_PANEL    = "#151517"
                self.COLOR_TEXT     = "#F5F7FA"
                self.COLOR_MUTED    = "#AAB2C0"
                self.COLOR_DIVIDER  = "#24262b"
                self.COLOR_INPUT_BG = "#1b1d22"
                self.COLOR_RED      = "#ff4c4c"
                self.COLOR_YELLOW   = "#FFD54F"
                self.api = None

            def _info(self, msg: str):
                print(f"[INFO Vehículos] {msg}")

        print("[WARN] VehiculosView: no se encontró 'app' en la jerarquía. Usando AppShim.")
        return _AppShim()

    # -------------------- Constructor --------------------
    def __init__(self, master, app=None):
        """
        Compatible con:
          - VehiculosView(master, app)
          - VehiculosView(master)  # se auto-resuelve el 'app'
        """
        app = app or self._resolve_app(master)

        # ⚠️ BaseModuleFrame NO recibe 'app'. Solo (master, titulo, subtitulo?)
        super().__init__(master, "Vehículos", "Gestione los automóviles de la academia")

        # Asegurar que self.app exista (por si BaseModuleFrame no lo definió)
        if not hasattr(self, "app") or self.app is None:
            self.app = app

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        tb.grid_columnconfigure((0, 1, 2), weight=0)
        tb.grid_columnconfigure(3, weight=1)

        def red_btn(parent, text, cmd):
            return ctk.CTkButton(
                parent, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff", command=cmd, anchor="w"
            )

        red_btn(tb, "＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        red_btn(tb, "↻ Refrescar", self._refrescar).grid(row=0, column=2, padx=8, pady=6, sticky="w")

        # Formulario inline
        self.form = VehiculoInlineForm(self, self.app, on_submit=self._submit_inline, on_cancel=self._cancel_inline)
        self.form.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.form.hide()

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.table.grid_columnconfigure(0, weight=1)

        # Columnas: (nombre, ancho fijo)
        self._COLS = [
            ("Placa", 120),
            ("Marca", 160),
            ("Modelo", 160),
            ("Año", 90),
            ("Estado", 120),
            ("Acciones", 140),
        ]

        self._col_widths = [w for _, w in self._COLS]
        self._data = []
        self._rows = []
        self._selected_idx = None

        self._render_table()
        self.after(150, self._refrescar)

    # -------------------- Renderizado --------------------
    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        self._rows.clear()
        self._selected_idx = None

        header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        header.grid_columnconfigure(tuple(range(len(self._COLS))), weight=0)

        for i, (nombre, width) in enumerate(self._COLS):
            ctk.CTkLabel(
                header, text=nombre, text_color=self.app.COLOR_MUTED,
                anchor="w", justify="left", width=width
            ).grid(row=0, column=i, padx=8, pady=10, sticky="w")

        if not self._data:
            ctk.CTkLabel(self.table, text="Sin resultados", text_color=self.app.COLOR_MUTED)\
                .grid(row=1, column=0, padx=8, pady=12, sticky="w")
            return

        for r, vh in enumerate(self._data, start=1):
            row = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_PANEL, corner_radius=10)
            row.grid(row=r, column=0, padx=8, pady=4, sticky="ew")
            row.grid_columnconfigure(tuple(range(len(self._COLS))), weight=0)

            values = [
                vh.get("placa", ""),
                vh.get("marca", ""),
                vh.get("modelo", ""),
                vh.get("anio", ""),
                vh.get("estado", ""),
            ]

            for i, val in enumerate(values):
                lbl = ctk.CTkLabel(
                    row, text=val, text_color=self.app.COLOR_TEXT,
                    anchor="w", justify="left", width=self._col_widths[i]
                )
                lbl.grid(row=0, column=i, padx=8, pady=10, sticky="w")
                lbl.bind("<Button-1>", lambda e, idx=r - 1: self._select_row(idx))

            actions = ctk.CTkFrame(row, fg_color="transparent", width=self._col_widths[-1])
            actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")

            def icon_btn(symbol, cmd):
                return ctk.CTkButton(
                    actions, text=symbol, width=36, height=32, corner_radius=10,
                    fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
                    text_color="#ffffff", command=cmd
                )

            icon_btn("✎", lambda idx=r - 1: self._edit_row(idx)).grid(row=0, column=0, padx=4)
            icon_btn("🗑️", lambda idx=r - 1: self._delete_row(idx)).grid(row=0, column=1, padx=4)

            row.bind("<Button-1>", lambda e, idx=r - 1: self._select_row(idx))
            self._rows.append(row)

        self.after(100, self._sync_column_widths)

    def _sync_column_widths(self):
        try:
            for i in range(len(self._COLS)):
                max_width = self._col_widths[i]
                for row in self._rows:
                    w = row.grid_slaves(row=0, column=i)
                    if w:
                        lbl = w[0]
                        lbl.update_idletasks()
                        max_width = max(max_width, lbl.winfo_width())
                self._col_widths[i] = max_width

            for row in self._rows:
                for i, width in enumerate(self._col_widths[:-1]):
                    w = row.grid_slaves(row=0, column=i)
                    if w:
                        w[0].configure(width=width)
        except Exception:
            print("\n[ERROR Vehículos] _sync_column_widths():")
            traceback.print_exc()

    # -------------------- Acciones UI --------------------
    def _select_row(self, idx):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].configure(fg_color=self.app.COLOR_PANEL)
        if 0 <= idx < len(self._rows):
            self._rows[idx].configure(fg_color=self.app.COLOR_DIVIDER)
            self._selected_idx = idx

    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo primero.")
            return
        self._edit_row(self._selected_idx)

    def _edit_row(self, idx):
        self._select_row(idx)
        self.form.show_edit(self._data[idx])

    def _cancel_inline(self):
        self.form.hide()

    # -------------------- API / Datos --------------------
    def _refrescar(self):
        try:
            if not getattr(self.app, "api", None):
                self.app._info("No hay cliente API activo.")
                return

            raw = self.app.api.get_all("vehiculos") or []
            if isinstance(raw, dict):
                for key in ("content", "items", "vehiculos", "data", "results"):
                    if isinstance(raw.get(key), list):
                        raw = raw[key]
                        break
                else:
                    raw = []

            self._data = raw or []
            self._render_table()

        except Exception as e:
            print("\n[ERROR Vehículos] _refrescar():")
            traceback.print_exc()
            messagebox.showerror("Vehículos", f"No se pudo consultar la API:\n{e}", parent=self)

    def _submit_inline(self, payload, mode):
        try:
            if not getattr(self.app, "api", None):
                self.app._info("No hay cliente API activo.")
                return

            if mode == "create":
                self.app.api.create("vehiculos", payload)
                self.app._info("Vehículo creado.")
            else:
                idx = self._selected_idx
                if idx is None:
                    self.app._info("Selecciona un vehículo para actualizar.")
                    return
                vid = self._data[idx].get("id") or self._data[idx].get("idVehiculo")
                if not vid:
                    self.app._info("No se encontró el ID del vehículo.")
                    return
                self.app.api.update("vehiculos", vid, payload)
                self.app._info("Vehículo actualizado.")

            self._refrescar()

        except Exception as e:
            print("\n[ERROR Vehículos] _submit_inline():")
            traceback.print_exc()
            messagebox.showerror("Vehículos", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        vh = self._data[idx]
        placa = vh.get("placa", "")
        if not messagebox.askyesno("Confirmar", f"¿Eliminar el vehículo con placa {placa}?"):
            self.app._info("Operación cancelada.")
            return
        try:
            vid = vh.get("id") or vh.get("idVehiculo")
            if not vid:
                self.app._info("No se encontró el ID del vehículo.")
                return

            if getattr(self.app, "api", None):
                self.app.api.delete("vehiculos", vid)
                self.app._info("Vehículo eliminado.")
                self._refrescar()
            else:
                self.app._info("No hay cliente API activo.")

        except Exception as e:
            print("\n[ERROR Vehículos] _delete_row():")
            traceback.print_exc()
            messagebox.showerror("Vehículos", f"No se pudo eliminar:\n{e}", parent=self)
