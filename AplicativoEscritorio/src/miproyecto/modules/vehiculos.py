import customtkinter as ctk
from tkinter import messagebox
import traceback
import threading
import time
from modules.forms_inlines import VehiculoInlineForm
from modules.base import BaseModuleFrame


class VehiculosView(BaseModuleFrame):
    """Vista del módulo Vehículos — Gestión de automóviles de la academia."""
    DEBOUNCE_MS = 250
    ROW_BATCH_SIZE = 30
    ROW_BATCH_DELAY = 4
    MIN_REFRESH_INTERVAL = 500  # ms
    RENDER_DELAY_MS = 16

    # -------------------- Resolver de APP (auto) --------------------
    @staticmethod
    def _resolve_app(master):
 
        if hasattr(master, "api") or hasattr(master, "COLOR_BG") or hasattr(master, "_info"):
            return master
 
        if hasattr(master, "app"):
            return master.app

 
        cur = getattr(master, "master", None)
        hops = 0
        while cur is not None and hops < 20:
            if hasattr(cur, "api") or hasattr(cur, "COLOR_BG") or hasattr(cur, "_info"):
                return cur
            if hasattr(cur, "app"):
                return cur.app
            cur = getattr(cur, "master", None)
            hops += 1

 
        try:
            top = master.winfo_toplevel()
            if hasattr(top, "api") or hasattr(top, "COLOR_BG") or hasattr(top, "_info"):
                return top
            if hasattr(top, "app"):
                return top.app
        except Exception:
            pass

 
        class _AppShim:
            def __init__(self):
 
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
    
        app = app or self._resolve_app(master)

 
        super().__init__(master, "Vehículos", "Gestione los automóviles de la academia")


        if not hasattr(self, "app") or self.app is None:
            self.app = app

        # ===== Estado para filtros =====
        self._all_data = []      # todo lo de API
        self._data = []          # filtrado
        self._rows = []
        self._selected_idx = None
        self._debounce_id = None
        self._render_after_id = None
        self._render_seq = 0
        self._row_pool = []
        self._empty_label = None
        self._loading_overlay = None
        self._last_refresh_ts = 0

        # ===== Estado edición =====
        self._editing_placa = None
        self._editing_id = None

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

        # ===== Filtros PRO (nuevo) =====
        self.filters = self._make_filters_bar(self)
        self.filters.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")

        # Tabla
        self.table = ctk.CTkScrollableFrame(self, fg_color=self.app.COLOR_BG, corner_radius=12)
        self.table.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
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




 
        self._render_table()
        self.after(150, self._refrescar)

    # =====================================================
    #                    FILTROS (PRO)
    # =====================================================
    def _make_filters_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.app.COLOR_PANEL, corner_radius=12)
        # 0 placa, 1 marca, 2 modelo, 3 año, 4 estado, 5 botones
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=1)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=0)
        bar.grid_columnconfigure(5, weight=0)

        def entry(ph, w=None):
            return ctk.CTkEntry(
                bar, placeholder_text=ph, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, text_color=self.app.COLOR_TEXT,
                border_width=2, border_color=self.app.COLOR_DIVIDER,
                width=w if w else 140
            )

        # Placa
        ctk.CTkLabel(bar, text="Placa", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=0, padx=(12, 8), pady=(10, 4), sticky="w")
        self.f_placa = entry("ABC123")
        self.f_placa.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="ew")

        # Marca
        ctk.CTkLabel(bar, text="Marca", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=1, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_marca = entry("Chevrolet")
        self.f_marca.grid(row=1, column=1, padx=(8, 8), pady=(0, 10), sticky="ew")

        # Modelo
        ctk.CTkLabel(bar, text="Modelo", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=2, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_modelo = entry("Spark")
        self.f_modelo.grid(row=1, column=2, padx=(8, 8), pady=(0, 10), sticky="ew")

        # Año
        ctk.CTkLabel(bar, text="Año", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=3, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_anio = entry("2020", w=110)
        self.f_anio.grid(row=1, column=3, padx=(8, 8), pady=(0, 10), sticky="w")

        # Estado
        ctk.CTkLabel(bar, text="Estado", text_color=self.app.COLOR_TEXT)\
            .grid(row=0, column=4, padx=(8, 8), pady=(10, 4), sticky="w")
        self.f_estado = ctk.CTkComboBox(
            bar,
            values=["Todos", "Activo", "Inactivo", "Mantenimiento", "Suspendido"],
            width=170
        )
        self.f_estado.set("Todos")
        self.f_estado.grid(row=1, column=4, padx=(8, 8), pady=(0, 10), sticky="w")

        # Botones
        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=1, column=5, padx=(8, 12), pady=(0, 10), sticky="e")

        def light_btn(text, cmd):
            return ctk.CTkButton(
                btns, text=text, height=36, corner_radius=10,
                fg_color=self.app.COLOR_INPUT_BG, hover_color=self.app.COLOR_DIVIDER,
                text_color=self.app.COLOR_TEXT, command=cmd
            )

        light_btn("Limpiar", self._clear_filters).grid(row=0, column=0, padx=6)
        light_btn("Buscar", self._apply_filters_now).grid(row=0, column=1, padx=6)

        # Bindings (búsqueda en vivo + debounce)
        for w in (self.f_placa, self.f_marca, self.f_modelo, self.f_anio):
            w.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.f_estado.bind("<<ComboboxSelected>>", lambda e: self._apply_filters_now())

        return bar

    def _collect_filters(self):
        return {
            "placa": (self.f_placa.get() or "").strip(),
            "marca": (self.f_marca.get() or "").strip(),
            "modelo": (self.f_modelo.get() or "").strip(),
            "anio": (self.f_anio.get() or "").strip(),
            "estado": (self.f_estado.get() or "Todos").strip(),
        }

    def _clear_filters(self):
        self.f_placa.delete(0, "end")
        self.f_marca.delete(0, "end")
        self.f_modelo.delete(0, "end")
        self.f_anio.delete(0, "end")
        self.f_estado.set("Todos")
        self._apply_filters_now()

    def _debounced_apply_filters(self):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._apply_filters_now)

    def _apply_filters_now(self):
        src = self._all_data or []
        self._data = self._apply_filters(src, self._collect_filters())
        self._queue_render(self._data)

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

    def _apply_filters(self, data_list, f):
        """Filtra localmente por placa, marca, modelo, año y estado. Insensible a mayúsculas."""
        if not data_list:
            return []

        placa_sub = f["placa"].lower()
        marca_sub = f["marca"].lower()
        modelo_sub = f["modelo"].lower()
        anio_sub = f["anio"].lower()
        estado = f["estado"]

        out = []
        for vh in data_list:
            placa = str(vh.get("placa", "") or "").strip().lower()
            marca = str(vh.get("marca", "") or "").strip().lower()
            modelo = str(vh.get("modelo", "") or "").strip().lower()
            anio = str(vh.get("anio", "") or "").strip().lower()
            est = str(vh.get("estado", "") or "").strip()

            if placa_sub and placa_sub not in placa:
                continue
            if marca_sub and marca_sub not in marca:
                continue
            if modelo_sub and modelo_sub not in modelo:
                continue
            if anio_sub and anio_sub not in anio:
                continue
            if estado != "Todos" and est != estado:
                continue

            out.append(vh)
        return out

    # -------------------- Renderizado --------------------
    def _row_values(self, vh):
        return [
            vh.get("placa", ""),
            vh.get("marca", ""),
            vh.get("modelo", ""),
            vh.get("anio", ""),
            vh.get("estado", ""),
        ]

    def _render_table(self):
        self._queue_render(self._data)

    def _build_table_shell(self):
        if getattr(self, "_table_header", None) and self._table_header.winfo_exists():
            return

        for w in self.table.winfo_children():
            w.destroy()
        self._row_pool = []

        self._table_header = ctk.CTkFrame(self.table, fg_color=self.app.COLOR_INPUT_BG, corner_radius=10)
        self._table_header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self._table_header.grid_columnconfigure(tuple(range(len(self._COLS))), weight=0)

        for i, (nombre, width) in enumerate(self._COLS):
            ctk.CTkLabel(
                self._table_header, text=nombre, text_color=self.app.COLOR_MUTED,
                anchor="w", justify="left", width=width
            ).grid(row=0, column=i, padx=8, pady=10, sticky="w")

        self._rows_container = ctk.CTkFrame(self.table, fg_color="transparent")
        self._rows_container.grid(row=1, column=0, sticky="nsew")
        self.table.grid_rowconfigure(1, weight=1)
        self._rows_container.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._rows_container,
            text="Sin resultados",
            text_color=self.app.COLOR_MUTED
        )
        self._empty_label.grid(row=0, column=0, padx=8, pady=12, sticky="w")
        self._empty_label.grid_remove()

    def _create_row_widget(self):
        row = ctk.CTkFrame(self._rows_container, fg_color=self.app.COLOR_PANEL, corner_radius=10)
        row.grid_columnconfigure(tuple(range(len(self._COLS))), weight=0)

        labels = []
        for i in range(len(self._COLS) - 1):
            lbl = ctk.CTkLabel(
                row,
                text="",
                text_color=self.app.COLOR_TEXT,
                anchor="w",
                justify="left",
                width=self._col_widths[i]
            )
            lbl.grid(row=0, column=i, padx=8, pady=10, sticky="w")
            labels.append(lbl)

        actions = ctk.CTkFrame(row, fg_color="transparent", width=self._col_widths[-1])
        actions.grid(row=0, column=len(self._COLS) - 1, padx=8, pady=6, sticky="e")

        btn_edit = ctk.CTkButton(
            actions, text="✎", width=36, height=32, corner_radius=10,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_edit.grid(row=0, column=0, padx=4)

        btn_delete = ctk.CTkButton(
            actions, text="🗑️", width=36, height=32, corner_radius=10,
            fg_color=self.app.COLOR_RED, hover_color=self.app.COLOR_YELLOW,
            text_color="#ffffff"
        )
        btn_delete.grid(row=0, column=1, padx=4)

        return {
            "frame": row,
            "labels": labels,
            "actions": actions,
            "edit_btn": btn_edit,
            "delete_btn": btn_delete,
        }

    def _update_row_widget(self, row_info, vh, idx):
        row = row_info["frame"]
        row.configure(fg_color=self.app.COLOR_PANEL)
        values = self._row_values(vh)

        for col, val in enumerate(values):
            lbl = row_info["labels"][col]
            lbl.configure(text=str(val), width=self._col_widths[col])
            lbl.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

        row_info["actions"].configure(width=self._col_widths[-1])
        row_info["edit_btn"].configure(command=lambda i=idx: self._edit_row(i))
        row_info["delete_btn"].configure(command=lambda i=idx: self._delete_row(i))
        row.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

    def _set_data(self, rows):
        self._build_table_shell()
        self._selected_idx = None
        self._rows.clear()
        data = list(rows or [])

        self._render_seq += 1
        render_seq = self._render_seq

        for row_info in self._row_pool:
            try:
                row_info["frame"].grid_remove()
            except Exception:
                pass

        if not data:
            if self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.grid()
            return

        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.grid_remove()

        def paint_batch(start=0):
            if render_seq != self._render_seq:
                return
            if not self._rows_container.winfo_exists():
                return

            end = min(start + self.ROW_BATCH_SIZE, len(data))
            for idx in range(start, end):
                if idx >= len(self._row_pool):
                    self._row_pool.append(self._create_row_widget())
                row_info = self._row_pool[idx]
                self._update_row_widget(row_info, data[idx], idx)
                row_info["frame"].grid(row=idx + 1, column=0, padx=8, pady=4, sticky="ew")
                self._rows.append(row_info["frame"])

            if end < len(data):
                self.after(self.ROW_BATCH_DELAY, lambda: paint_batch(end))
            else:
                self.after(100, self._sync_column_widths)

        paint_batch(0)

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



    def _edit_row(self, idx):
        self._select_row(idx)
        item = self._data[idx]
        self._editing_placa = (item.get("placa") or "").strip()
        self.form.show_edit(item)


    def _cancel_inline(self):
        self._editing_placa = None
        self.form.hide()



    # -------------------- API / Datos --------------------
    def _extract_id(self, vh: dict):
        if not isinstance(vh, dict):
            return None
        for k in ("id", "idVehiculo", "vehiculoId", "id_vehiculo", "vehiculo_id", "idvehiculo"):
            v = vh.get(k)
            if v not in (None, "", 0):
                return v
        return None

    def _refrescar(self, force_refresh=True):
        now = int(time.time() * 1000)
        if now - self._last_refresh_ts < self.MIN_REFRESH_INTERVAL:
            return
        self._last_refresh_ts = now

        if not getattr(self.app, "api", None):
            self.app._info("No hay cliente API activo.")
            return

        def worker():
            try:
                self.after(0, lambda: self._show_loading(True))
                raw = self.app.api.get_all("vehiculos", force_refresh=force_refresh) or []
                if isinstance(raw, dict):
                    for key in ("content", "items", "vehiculos", "data", "results"):
                        if isinstance(raw.get(key), list):
                            raw = raw[key]
                            break
                    else:
                        raw = []

                data = raw or []
                for it in data:
                    if "id" not in it:
                        iid = self._extract_id(it)
                        if iid is not None:
                            it["id"] = iid

                def apply_data():
                    self._all_data = data
                    self._data = self._apply_filters(self._all_data, self._collect_filters())
                    self._queue_render(self._data)

                self.after(0, apply_data)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Vehículos", f"No se pudo consultar la API:\n{e}", parent=self))
            finally:
                self.after(0, lambda: self._show_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_loading(self, on=True, text="Actualizando..."):
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
                if idx is None or not (0 <= idx < len(self._data)):
                    self.app._info("Selecciona un vehículo para actualizar.")
                    return


                placa_path = (self._editing_placa or self._data[idx].get("placa") or "").strip()
                if not placa_path:
                    self.app._info("No se encontró la placa del vehículo.")
                    return


                self.app.api.update("vehiculos", placa_path, payload)
                self.app._info("Vehículo actualizado.")
                self._editing_placa = None



            self._last_refresh_ts = 0
            self._refrescar()

        except Exception as e:
            print("\n[ERROR Vehículos] _submit_inline():")
            traceback.print_exc()
            messagebox.showerror("Vehículos", f"Operación fallida:\n{e}", parent=self)

    def _delete_row(self, idx):
        self._select_row(idx)
        vh = self._data[idx]
        placa = (vh.get("placa") or "").strip()
        if not placa:
            self.app._info("No se encontró la placa del vehículo.")
            return

        if not messagebox.askyesno("Confirmar", f"¿Eliminar el vehículo con placa {placa}"):
            self.app._info("Operación cancelada.")
            return

        try:

            if getattr(self.app, "api", None):
                self.app.api.delete("vehiculos", placa)
                self.app._info("Vehículo eliminado.")
                self._last_refresh_ts = 0
                self._refrescar()
            else:
                self.app._info("No hay cliente API activo.")
        except Exception as e:
            print("\n[ERROR Vehículos] _delete_row():")
            traceback.print_exc()
            messagebox.showerror("Vehículos", f"No se pudo eliminar:\n{e}", parent=self)
