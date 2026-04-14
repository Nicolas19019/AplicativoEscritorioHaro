"""
Tema/estilos de Treeview para HaroGestion.

Homogeneiza colores, selección y alturas de fila para tablas en los módulos.
"""

import customtkinter as ctk


def solid_color(value, fallback):
    """
    Obtiene un color “plano” desde una tupla (light/dark) o un string.

    Args:
        value: Color como string o tupla/lista `(light, dark)`.
        fallback: Color por defecto si `value` no es válido.

    Returns:
        Color como string.
    """
    if isinstance(value, (tuple, list)) and value:
        return str(value[0] or fallback)
    if value in (None, ""):
        return fallback
    return str(value)


def configure_treeview_style(style, app, style_name, *, rowheight=30):
    """
    Configura estilo de `ttk.Treeview` usando la paleta de la app.

    Args:
        style: Instancia `ttk.Style`.
        app: Instancia de `HaroDesktopApp` (colores).
        style_name: Nombre del estilo (ej. `"Estudiantes.Treeview"`).
        rowheight: Alto de fila.

    Returns:
        Dict con colores calculados (bg/panel/text/selected/even/odd...).
    """
    try:
        style.theme_use("clam")
    except Exception:
        pass

    mode = ctk.get_appearance_mode()
    if mode == "Light":
        bg = "#FFFFFF"
        panel = solid_color(getattr(app, "COLOR_PANEL", "#FFFFFF"), "#FFFFFF")
        text = solid_color(getattr(app, "COLOR_TEXT", "#111111"), "#111111")
        muted = solid_color(getattr(app, "COLOR_MUTED", "#444444"), "#444444")
        divider = solid_color(getattr(app, "COLOR_DIVIDER", "#E5E7EB"), "#E5E7EB")
        sel_bg = solid_color(getattr(app, "MUSTARD_SOFT_BG", "#FFF8E1"), "#FFF8E1")
        even_bg = panel
        odd_bg = "#F8FAFC"
    else:
        bg = solid_color(getattr(app, "COLOR_BG", "#111111"), "#111111")
        panel = solid_color(getattr(app, "COLOR_PANEL", "#1B1B1B"), "#1B1B1B")
        text = solid_color(getattr(app, "COLOR_TEXT", "#F5F7FA"), "#F5F7FA")
        muted = solid_color(getattr(app, "COLOR_MUTED", "#CFCFCF"), "#CFCFCF")
        divider = solid_color(getattr(app, "COLOR_DIVIDER", "#2A2A2A"), "#2A2A2A")
        sel_bg = solid_color(getattr(app, "MUSTARD_SOFT_BG", "#2A2A2A"), "#2A2A2A")
        even_bg = panel
        odd_bg = "#222222"

    style.configure(
        style_name,
        background=panel,
        fieldbackground=panel,
        foreground=text,
        bordercolor=divider,
        lightcolor=divider,
        darkcolor=divider,
        rowheight=rowheight,
    )
    style.map(
        style_name,
        background=[("selected", sel_bg)],
        foreground=[("selected", text)],
    )
    style.configure(
        f"{style_name}.Heading",
        background=bg,
        foreground=muted,
        relief="flat",
        font=("Segoe UI", 10, "bold"),
    )
    return {
        "bg": bg,
        "panel": panel,
        "text": text,
        "muted": muted,
        "divider": divider,
        "selected": sel_bg,
        "even": even_bg,
        "odd": odd_bg,
    }
