import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import time
import traceback
from modules.forms_inlines import VehiculoInlineForm
from modules.base import BaseModuleFrame


class VehiculosView(BaseModuleFrame):
    DEBOUNCE_MS = 250
    MIN_REFRESH_INTERVAL = 500
    RENDER_DELAY_MS = 16
    TREE_INSERT_CHUNK = 250
    TREE_INSERT_DELAY = 1

    def __init__(self, master):
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

        def red_btn(text, cmd):
            return ctk.CTkButton(
                tb, text=text, height=40, corner_radius=18,
                fg_color=self.app.COLOR_RED,
                hover_color=self.app.COLOR_YELLOW,
                text_color="#ffffff",
                command=cmd
            )

        red_btn("＋ Nuevo", self._nuevo).grid(row=0, column=0, padx=6)
        red_btn("✎ Editar", self._editar).grid(row=0, column=1, padx=6)
        red_btn("🗑️ Eliminar", self._eliminar_seleccionado).grid(row=0, column=2, padx=6)
        red_btn("↻ Refrescar", self._refrescar).grid(row=0, column=3, padx=6)

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

        self._COLS = [
            ("Placa", 120),
            ("Marca", 160),
            ("Modelo", 160),
            ("Año", 90),
            ("Estado", 120),
        ]

        self._build_tree()
        self.after(150, self._refrescar)

    # =====================================================
    #                TREEVIEW (TABLA RÁPIDA)
    # =====================================================
    def _build_tree(self):
        style = ttk.Style()
        style.theme_use("clam")

        mode = ctk.get_appearance_mode()

        if mode == "Light":
            panel = "#ffffff"
            text = "#111111"
            muted = "#444444"
            divider = "#e5e7eb"
            sel_bg = "#f1f5f9"
        else:
            panel = self.app.COLOR_PANEL
            text = self.app.COLOR_TEXT
            muted = self.app.COLOR_MUTED
            divider = self.app.COLOR_DIVIDER
            sel_bg = divider

        style.configure(
            "Haro.Treeview",
            background=panel,
            fieldbackground=panel,
            foreground=text,
            rowheight=28,
            bordercolor=divider
        )

        style.map(
            "Haro.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", text)]
        )

        style.configure(
            "Haro.Treeview.Heading",
            background=panel,
            foreground=muted,
            font=("Segoe UI", 10, "bold")
        )

        cols = [c[0] for c in self._COLS]
        self.tree = ttk.Treeview(self.table, columns=cols, show="headings", style="Haro.Treeview")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        for name, width in self._COLS:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, anchor="w")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._editar())

    def _on_tree_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            self._selected_idx = None
            return
        iid = sel[0]
        self._selected_idx = self._iid_to_index.get(iid)

    def _set_data(self, rows):
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        self._iid_to_index.clear()
        self._selected_idx = None

        data = list(rows or [])
        if not data:
            return

        def insert_chunk(start=0):
            end = min(start + self.TREE_INSERT_CHUNK, len(data))
            for idx in range(start, end):
                vh = data[idx]
                iid = f"r{idx}"
                self._iid_to_index[iid] = idx
                self.tree.insert(
                    "", "end",
                    iid=iid,
                    values=(
                        vh.get("placa", ""),
                        vh.get("marca", ""),
                        vh.get("modelo", ""),
                        vh.get("anio", ""),
                        vh.get("estado", "")
                    )
                )
            if end < len(data):
                self.after(self.TREE_INSERT_DELAY, lambda: insert_chunk(end))

        insert_chunk(0)

    # =====================================================
    #                ACCIONES
    # =====================================================
    def _nuevo(self):
        self.form.show_create()

    def _editar(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo primero.")
            return
        self.form.show_edit(self._data[self._selected_idx])

    def _eliminar_seleccionado(self):
        if self._selected_idx is None:
            self.app._info("Selecciona un vehículo primero.")
            return
        self._delete_row(self._selected_idx)

    def _cancel_inline(self):
        self.form.hide()

    # =====================================================
    #                API
    # =====================================================
    def _refrescar(self, force_refresh=True):
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
                    self._all_data = raw
                    self._data = raw
                    self._set_data(self._data)

                self.after(0, apply_data)

            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Vehículos", str(e), parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _submit_inline(self, payload, mode):
        try:
            if mode == "create":
                self.app.api.create("vehiculos", payload)
            else:
                idx = self._selected_idx
                vh = self._data[idx]
                placa = vh.get("placa")
                self.app.api.update("vehiculos", placa, payload)

            self._last_refresh_ts = 0
            self._refrescar()

        except Exception as e:
            messagebox.showerror("Vehículos", str(e), parent=self)

    def _delete_row(self, idx):
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