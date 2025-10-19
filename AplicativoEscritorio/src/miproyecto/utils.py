def centrar_ventana(win, ancho=None, alto=None):
    """
    Centra una ventana de CustomTkinter/Tkinter. Respeta el diseño y tamaños.
    """
    def _do_center(_=None):
        win.update_idletasks()
        w = ancho or win.winfo_width()
        h = alto or win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.update()
    win.bind("<Map>", _do_center)
