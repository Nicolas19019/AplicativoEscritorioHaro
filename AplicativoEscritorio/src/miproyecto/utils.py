"""
Utilidades generales de UI (Tk/CustomTkinter).

Se mantiene pequeño a propósito: helpers reutilizables sin dependencias de negocio.
"""

def centrar_ventana(win, ancho=None, alto=None):
    """
    Centra una ventana de CustomTkinter/Tkinter.

    Args:
        win: Ventana (Tk/Toplevel/CTk/CTkToplevel).
        ancho: Ancho deseado (si `None`, usa el ancho actual).
        alto: Alto deseado (si `None`, usa el alto actual).
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
