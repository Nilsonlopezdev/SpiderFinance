import calendar
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import date
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageOps, ImageDraw

from telarana import database as db
from telarana import visuals
from telarana import settings
from telarana import __version__
from telarana.finance import (
    money, status, committed_ratio, streak_info, streak_days, alerts
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# -----------------------------------------------------------------------------
# TELARAÑA - sistema visual
# -----------------------------------------------------------------------------
FONT = "Segoe UI"

BG = "#070A10"
SIDEBAR = "#080C13"
HEADER_BG = "#080C13"
CARD = "#0B1119"
PANEL = "#0E1620"
PANEL_HOVER = "#151F2C"
BORDER = "#223041"
BORDER_SOFT = "#18232F"
RED = "#FF3347"
RED_2 = "#C71932"
RED_DARK = "#2A1118"
RED_SOFT = "#7A2230"
GREEN = "#45E39A"
GREEN_DARK = "#0F3D2A"
BLUE = "#73A7FF"
BLUE_DARK = "#16315A"
PURPLE = "#A87CFF"
PURPLE_DARK = "#2B1F5E"
TEXT = "#F3F7FC"
MUTED = "#91A1B4"
DIM = "#5D6D80"
WHITE = "#FFFFFF"

CONTENT_MAX = 980  # ancho máximo del contenido en las páginas internas

SIDE_COMPACT = 78
SIDE_EXPANDED = 236

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSET_DIR = BASE_DIR / "assets"
STATE_IMAGES = {
    "NEGATIVO": ASSET_DIR / "estado_falta_dinero.png",
    "NEUTRO": ASSET_DIR / "estado_al_ras.png",
    "POSITIVO": ASSET_DIR / "estado_sobra_dinero.png",
    "SIN DATOS": ASSET_DIR / "estado_sin_datos.png",
}
STREAK_IMAGES = {
    "NEGATIVO": ASSET_DIR / "racha_falta_dinero.png",
    "NEUTRO": ASSET_DIR / "racha_al_ras.png",
    "POSITIVO": ASSET_DIR / "racha_sobra_dinero.jpg",
    "SIN DATOS": ASSET_DIR / "racha_al_ras.png",
}

SECTION_ART = {
    "Ingresos": ASSET_DIR / "seccion_ingresos.png",
    "Obligaciones": ASSET_DIR / "seccion_obligaciones.png",
    "Historial": ASSET_DIR / "seccion_historial.png",
    "Proyección": ASSET_DIR / "seccion_proyeccion.png",
    "Objetivos de ahorro": ASSET_DIR / "seccion_objetivos.png",
    "Mini juego": ASSET_DIR / "seccion_juego.png",
    "Configuración": ASSET_DIR / "seccion_ajustes.png",
}

MONTHS = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
MONTHS_ABBR = [
    "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
    "jul.", "ago.", "sep.", "oct.", "nov.", "dic."
]

# (nombre de página, ícono)
NAV_ITEMS = [
    ("Inicio", "home"),
    ("Ingresos", "chart"),
    ("Obligaciones", "card"),
    ("Historial", "clock"),
    ("Rachas", "flame"),
    ("Proyección", "trend"),
    ("Objetivos de ahorro", "target"),
    ("Mini juego", "gamepad"),
    ("Configuración", "gear"),
]


def month_label(key):
    y, m = map(int, key.split("-"))
    return f"{MONTHS[m - 1]} {y}"


def month_key(y, m):
    return f"{y:04d}-{m:02d}"


class Tooltip:
    """Globo de ayuda para la barra lateral compacta."""

    def __init__(self, widget, text, enabled=lambda: True):
        self.widget = widget
        self.text = text
        self.enabled = enabled
        self.tip = None
        self._job = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<Button-1>", self._hide)

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(400, self._show)

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        self._job = None
        if self.tip is not None or not self.enabled():
            return
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2 - 15
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry(f"+{x}+{y}")
            tk.Label(
                self.tip, text=self.text, bg=PANEL_HOVER, fg=TEXT, font=(FONT, 10),
                padx=10, pady=5, bd=1, relief="solid"
            ).pack()
        except tk.TclError:
            self.tip = None

    def _hide(self, _event=None):
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


class TelaranaApp(ctk.CTk):
    """TELARAÑA - aplicación de escritorio con diseño futurista unificado."""

    def __init__(self):
        super().__init__()
        db.init_db()

        self.title("TELARAÑA | No Hay Plata")
        try:
            self.iconbitmap(str(ASSET_DIR / "telarana.ico"))
        except Exception:
            pass
        self.geometry("1500x920")
        self.minsize(1180, 740)
        self.configure(fg_color=BG)

        self.current_month = date.today().strftime("%Y-%m")
        self.active_page = "Inicio"
        self.sidebar_expanded = False
        self.record_form = None
        self.goal_form = None
        self._image_refs = []
        self._ico_cache = {}
        self._ring_cache = {}
        self._glow_step = 0
        self.ring_label = None
        self.ring_frames = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.build_header()
        self.build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.bind("<Configure>", self.fit_body)

        if settings.get("sidebar_expanded"):
            self.toggle_sidebar()
        self.render_page()
        self.after(400, self.animate_ui)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def ico(self, name, size=22, color=TEXT):
        """CTkImage de un ícono vectorial (cacheado)."""
        key = (name, size, color)
        if key not in self._ico_cache:
            img = visuals.render_icon(name, size, color)
            self._ico_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        return self._ico_cache[key]

    def make_clickable(self, card, command, highlight=True):
        """Hace que una tarjeta completa (y todo lo que contiene) sea clicable."""
        def run(_event=None):
            command()

        def inside():
            try:
                x, y = card.winfo_pointerxy()
                return (card.winfo_rootx() <= x < card.winfo_rootx() + card.winfo_width()
                        and card.winfo_rooty() <= y < card.winfo_rooty() + card.winfo_height())
            except tk.TclError:
                return False

        def enter(_event=None):
            try:
                card.configure(border_color=RED_SOFT)
            except tk.TclError:
                pass

        def leave(_event=None):
            def check():
                try:
                    if not inside():
                        card.configure(border_color=BORDER)
                except tk.TclError:
                    pass
            card.after(30, check)

        def walk(widget):
            try:
                widget.bind("<Button-1>", run)
                if highlight:
                    widget.bind("<Enter>", enter)
                    widget.bind("<Leave>", leave)
            except Exception:
                pass
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass
            for child in widget.winfo_children():
                walk(child)

        walk(card)

    # ------------------------------------------------------------------
    # Cabecera superior
    # ------------------------------------------------------------------
    def build_header(self):
        self.header = ctk.CTkFrame(self, fg_color=HEADER_BG, height=80, corner_radius=0)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_rowconfigure(0, weight=1)
        self.header.grid_columnconfigure(4, weight=1)
        ctk.CTkFrame(self.header, height=1, fg_color=BORDER_SOFT, corner_radius=0).place(
            relx=0, rely=1.0, relwidth=1.0, anchor="sw"
        )

        # Logo + nombre
        logo = ctk.CTkFrame(self.header, fg_color="transparent")
        logo.grid(row=0, column=0, padx=(22, 0), sticky="w")
        ctk.CTkLabel(logo, text="", image=self.ico("web", 52, RED)).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(logo, text="TELARAÑA", font=(FONT, 19, "bold"), text_color=TEXT).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(logo, text="No Hay Plata", font=(FONT, 12), text_color=MUTED).grid(row=1, column=1, sticky="nw")

        # Selector de mes (píldora)
        self.month_pill = ctk.CTkFrame(
            self.header, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=24, height=48
        )
        self.month_pill.grid(row=0, column=1, padx=(70, 0))
        self.month_pill.grid_propagate(False)
        self.month_pill.configure(width=250)
        self.month_pill.grid_columnconfigure(1, weight=1)
        self.month_pill.grid_rowconfigure(0, weight=1)
        ctk.CTkLabel(self.month_pill, text="", image=self.ico("calendar", 22, TEXT)).grid(row=0, column=0, padx=(18, 12))
        self.month_text = ctk.CTkLabel(self.month_pill, text="", font=(FONT, 14, "bold"), text_color=TEXT, anchor="w")
        self.month_text.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(self.month_pill, text="", image=self.ico("chev_r", 16, TEXT)).grid(row=0, column=2, padx=(8, 18))
        self.make_clickable(self.month_pill, self.open_month_menu, highlight=False)

        # Separador + periodo
        ctk.CTkFrame(self.header, width=1, height=44, fg_color=BORDER).grid(row=0, column=2, padx=26)
        period = ctk.CTkFrame(self.header, fg_color="transparent")
        period.grid(row=0, column=3, sticky="w")
        ctk.CTkLabel(period, text="Periodo seleccionado:", font=(FONT, 12), text_color=MUTED).pack(anchor="w")
        self.period_range = ctk.CTkLabel(period, text="", font=(FONT, 12), text_color=TEXT)
        self.period_range.pack(anchor="w")

        # Acciones de la derecha
        ctk.CTkButton(
            self.header, text="", image=self.ico("bell", 24, TEXT), width=46, height=46,
            corner_radius=23, fg_color="transparent", hover_color=PANEL_HOVER,
            command=self.show_alerts
        ).grid(row=0, column=5, padx=(6, 6))
        ctk.CTkButton(
            self.header, text="", image=self.ico("user", 24, TEXT), width=48, height=48,
            corner_radius=24, fg_color="#1A2430", hover_color=PANEL_HOVER,
            border_width=1, border_color=BORDER,
            command=lambda: self.navigate("Configuración")
        ).grid(row=0, column=6, padx=(6, 24))

        self.update_period()

    def update_period(self):
        y, m = map(int, self.current_month.split("-"))
        last = calendar.monthrange(y, m)[1]
        ab = MONTHS_ABBR[m - 1]
        self.month_text.configure(text=month_label(self.current_month))
        self.period_range.configure(text=f"01 {ab} {y} – {last:02d} {ab} {y}")

    def month_options(self):
        y, m = map(int, self.current_month.split("-"))
        vals = []
        for offset in range(-12, 13):
            total = y * 12 + m - 1 + offset
            vals.append(month_key(total // 12, total % 12 + 1))
        return vals

    def open_month_menu(self):
        menu = tk.Menu(
            self, tearoff=0, bg=CARD, fg=TEXT, activebackground=RED_DARK,
            activeforeground=TEXT, bd=0, font=(FONT, 11)
        )
        for key in self.month_options():
            label = ("●  " if key == self.current_month else "     ") + month_label(key)
            menu.add_command(label=label, command=lambda k=key: self.set_month(k))
        x = self.month_pill.winfo_rootx()
        y = self.month_pill.winfo_rooty() + self.month_pill.winfo_height() + 4
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def set_month(self, key):
        self.current_month = key
        self.render_page()

    # ------------------------------------------------------------------
    # Barra lateral (compacta con íconos; se expande con «)
    # ------------------------------------------------------------------
    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=SIDE_COMPACT, fg_color=SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(0, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(self.sidebar, width=1, fg_color=BORDER_SOFT, corner_radius=0).place(
            relx=1.0, rely=0, relheight=1.0, anchor="ne"
        )

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="new", padx=10, pady=(18, 0))
        nav.grid_columnconfigure(0, weight=1)

        self.nav = {}
        for i, (name, icon) in enumerate(NAV_ITEMS):
            active = name == self.active_page
            button = ctk.CTkButton(
                nav, text="", image=self.ico(icon, 24, TEXT if active else MUTED),
                compound="left", anchor="center", height=48, corner_radius=12,
                fg_color=RED_DARK if active else "transparent",
                hover_color=PANEL_HOVER, text_color=TEXT, font=(FONT, 13),
                border_width=1 if active else 0, border_color=RED,
                command=lambda n=name: self.navigate(n),
            )
            button.grid(row=i, column=0, sticky="ew", pady=4)
            Tooltip(button, name, enabled=lambda: not self.sidebar_expanded)
            self.nav[name] = (button, icon)

        self.collapse_btn = ctk.CTkButton(
            self.sidebar, text="", image=self.ico("dchev_r", 20, TEXT), width=52, height=52,
            corner_radius=26, fg_color="#0A0F16", hover_color=RED_DARK,
            border_width=2, border_color=RED, command=self.toggle_sidebar
        )
        self.collapse_btn.grid(row=1, column=0, pady=(10, 22))

    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        self.sidebar.configure(width=SIDE_EXPANDED if self.sidebar_expanded else SIDE_COMPACT)
        self.collapse_btn.configure(image=self.ico("dchev_l" if self.sidebar_expanded else "dchev_r", 20, TEXT))
        for name, (button, _icon) in self.nav.items():
            if self.sidebar_expanded:
                button.configure(text=f"   {name}", anchor="w")
            else:
                button.configure(text="", anchor="center")

    def navigate(self, name):
        self.active_page = name
        self.record_form = None
        self.goal_form = None
        for n, (button, icon) in self.nav.items():
            active = n == name
            button.configure(
                fg_color=RED_DARK if active else "transparent",
                border_width=1 if active else 0,
                image=self.ico(icon, 24, TEXT if active else MUTED),
            )
        self.render_page()

    # ------------------------------------------------------------------
    # Contenido
    # ------------------------------------------------------------------
    def clear_content(self):
        self.ring_label = None
        self.ring_frames = []
        for w in self.content.winfo_children():
            w.destroy()
        self.update_period()
        self.scroll = ctk.CTkScrollableFrame(
            self.content, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#172432", scrollbar_button_hover_color="#273A4D"
        )
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=18, pady=(6, 14))
        # Tres columnas: espacio | contenido (ancho máximo) | espacio -> contenido centrado
        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=0)
        self.scroll.grid_columnconfigure(2, weight=1)
        self.body = ctk.CTkFrame(self.scroll, fg_color="transparent", corner_radius=0)
        self.body.grid(row=0, column=1, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.fit_body()

    def fit_body(self, _event=None):
        """Centra el contenido y limita su ancho en las páginas internas."""
        scroll = getattr(self, "scroll", None)
        if scroll is None or not scroll.winfo_exists():
            return
        avail = max(self.content.winfo_width() - 90, 600)
        width = avail if self.active_page == "Inicio" else min(avail, CONTENT_MAX)
        scroll.grid_columnconfigure(1, minsize=width)

    def render_page(self):
        self.clear_content()
        pages = {
            "Inicio": self.show_dashboard,
            "Ingresos": lambda: self.show_records("income"),
            "Obligaciones": lambda: self.show_records("obligation"),
            "Historial": self.show_history,
            "Rachas": self.show_streaks,
            "Proyección": self.show_projection,
            "Objetivos de ahorro": self.show_goals,
            "Mini juego": self.show_game,
            "Configuración": self.show_settings,
        }
        pages.get(self.active_page, self.show_dashboard)()

    # ------------------------------------------------------------------
    # Imágenes recortadas al círculo (sin deformar)
    # ------------------------------------------------------------------
    def load_art(self, path, size, circle=False):
        try:
            image = Image.open(path).convert("RGBA")
            if circle:
                image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                mask = Image.new("L", size, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                image.putalpha(mask)
            else:
                image = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=size)
        except Exception:
            return None

    def ring_image(self, state, accent, ratio, glow, size=330):
        """Anillo + imagen de estado compuestos en una sola imagen (cacheada)."""
        key = (state, accent, round(ratio, 2), glow)
        if key not in self._ring_cache:
            pil = visuals.render_ring(STATE_IMAGES[state], accent, ratio, BG, size * 2, glow)
            self._ring_cache[key] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
        return self._ring_cache[key]

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def show_dashboard(self):
        data = db.get_month_data(self.current_month)
        ratio = committed_ratio(data)
        has_data = data["income"] > 0 or data["obligations"] > 0
        state = status(data["result"]) if has_data else "SIN DATOS"
        accent = GREEN if state == "POSITIVO" else RED if state == "NEGATIVO" else BLUE
        streak_state, streak_count = streak_info()
        days = streak_days(streak_count)
        found_alerts = alerts(data, ratio)

        # --- zona superior: ingresos | anillo | obligaciones -----------------
        hero = ctk.CTkFrame(self.body, fg_color="transparent")
        hero.grid(row=0, column=0, sticky="ew", padx=6, pady=(10, 0))
        hero.grid_columnconfigure(0, weight=1, uniform="side")
        hero.grid_columnconfigure(1, weight=0)
        hero.grid_columnconfigure(2, weight=1, uniform="side")

        self.summary_card(
            hero, 0, "Ingresos totales", money(data["income"]), GREEN, "coins",
            GREEN_DARK, "#1F7A52", "Desglose de ingresos",
            [("Fijo mensual", money(data["fixed_total"])), ("Adicionales", money(data["extra_total"]))],
            has_data,
        )
        self.status_center(hero, state, accent, ratio, days)
        self.summary_card(
            hero, 2, "Obligaciones totales", money(data["obligations"]), RED, "wallet",
            RED_DARK, "#8A2233", "Desglose de obligaciones",
            [("Recurrentes", money(data["rec_total"])), ("Puntuales", money(data["one_total"]))],
            has_data,
        )

        # --- tarjetas inferiores ---------------------------------------------
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=6, pady=(18, 0))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform="feat")

        if streak_count >= 3:
            pretty = {"POSITIVO": "Te sobró dinero", "NEGATIVO": "Te faltó dinero", "NEUTRO": "Estás al ras"}.get(streak_state, "Racha activa")
            streak_sub, streak_note = pretty, f"{streak_count} meses consecutivos con el mismo resultado."
        else:
            streak_sub = "Sin racha activa"
            streak_note = (
                f"Llevas {streak_count} de 3 meses consecutivos con el mismo resultado."
                if streak_count else
                "Completa 3 meses consecutivos con el mismo resultado para iniciar una racha."
            )
        self.feature_card(row, 0, "flame", "Rachas", "#FF5A6E", RED_DARK, streak_sub, streak_note, lambda: self.navigate("Rachas"))
        self.feature_card(
            row, 1, "info", "Información financiera", BLUE, BLUE_DARK,
            f"Resultado del mes: {money(data['result'])}" if has_data else "Tu resumen financiero",
            f"{ratio * 100:.0f}% de tus ingresos comprometidos" if has_data else "",
            lambda: self.navigate("Historial"),
        )
        self.feature_card(
            row, 2, "bell", "Alertas", PURPLE, PURPLE_DARK,
            f"{len(found_alerts)} alerta(s)" if found_alerts else "Sin alertas",
            found_alerts[0] if found_alerts else "Todo en orden por ahora.",
            self.show_alerts,
        )
        self.feature_card(row, 3, "bolt", "Accesos rápidos", GREEN, GREEN_DARK, "Herramientas útiles", "", self.quick_menu)

        # --- panel reservado ---------------------------------------------------
        reserved = ctk.CTkFrame(
            self.body, fg_color=CARD, border_width=1, border_color=BORDER_SOFT,
            corner_radius=18, height=120
        )
        reserved.grid(row=2, column=0, sticky="ew", padx=13, pady=(20, 18))
        reserved.grid_propagate(False)
        reserved.grid_columnconfigure(2, weight=1)
        reserved.grid_rowconfigure((0, 3), weight=1)
        ctk.CTkLabel(reserved, text="", image=self.ico("chart_up", 64, RED)).grid(row=0, column=0, rowspan=4, padx=(46, 26))
        ctk.CTkFrame(reserved, width=2, height=64, fg_color=RED_SOFT).grid(row=0, column=1, rowspan=4)
        ctk.CTkLabel(
            reserved, text="Espacio reservado para una futura función",
            text_color=TEXT, font=(FONT, 19, "bold")
        ).grid(row=1, column=2, sticky="sw", padx=26)
        ctk.CTkLabel(
            reserved, text="Aquí aparecerá una nueva característica de la aplicación.",
            text_color=MUTED, font=(FONT, 13)
        ).grid(row=2, column=2, sticky="nw", padx=26)

    def summary_card(self, parent, col, title, value, accent, icon, tile_bg, tile_border,
                     breakdown_title, rows, has_data):
        card = ctk.CTkFrame(
            parent, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=18, height=310
        )
        card.grid(row=0, column=col, sticky="new", padx=(0, 6) if col == 0 else (6, 0), pady=(44, 0))
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)

        tile = ctk.CTkFrame(card, width=60, height=60, corner_radius=18, fg_color=tile_bg, border_width=1, border_color=tile_border)
        tile.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(22, 16), pady=(22, 0))
        tile.grid_propagate(False)
        ctk.CTkLabel(tile, text="", image=self.ico(icon, 32, accent)).place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(card, text=title, font=(FONT, 17, "bold"), text_color=TEXT).grid(row=0, column=1, sticky="sw", pady=(22, 0))
        ctk.CTkLabel(card, text=value, font=(FONT, 34, "bold"), text_color=TEXT).grid(row=1, column=1, sticky="nw")
        ctk.CTkLabel(
            card, text="Resumen del periodo" if has_data else "Sin datos todavía",
            font=(FONT, 13), text_color=MUTED
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=(98, 0), pady=(0, 14))

        ctk.CTkFrame(card, height=1, fg_color=BORDER_SOFT).grid(row=3, column=0, columnspan=2, sticky="ew", padx=22, pady=(4, 0))
        ctk.CTkLabel(card, text=breakdown_title, font=(FONT, 15, "bold"), text_color=TEXT).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=24, pady=(16, 8)
        )
        for i, (label, amount) in enumerate(rows):
            line = ctk.CTkFrame(card, fg_color="transparent")
            line.grid(row=5 + i, column=0, columnspan=2, sticky="ew", padx=24, pady=3)
            line.grid_columnconfigure(1, weight=1)
            ctk.CTkFrame(line, width=10, height=10, corner_radius=5, fg_color=accent).grid(row=0, column=0, padx=(0, 14))
            ctk.CTkLabel(line, text=label, font=(FONT, 13), text_color=TEXT).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(line, text=amount, font=(FONT, 13, "bold"), text_color=TEXT).grid(row=0, column=2, sticky="e")

    def status_center(self, parent, state, accent, ratio, days):
        center = ctk.CTkFrame(parent, fg_color="transparent")
        center.grid(row=0, column=1, padx=22, sticky="n")

        # Una sola imagen contiene aro + progreso + foto circular.
        glow_levels = (1.0, 0.7, 0.4, 0.7)
        self.ring_frames = [self.ring_image(state, accent, ratio, g) for g in glow_levels]
        self._glow_step = 0
        self.ring_label = ctk.CTkLabel(
            center, text="", image=self.ring_frames[0], fg_color=BG, width=330, height=330
        )
        self.ring_label.pack()

        pill = ctk.CTkFrame(
            center, fg_color=CARD, border_width=1, border_color="#4A1B25",
            corner_radius=28, width=290, height=76
        )
        pill.pack(pady=(2, 0))
        pill.pack_propagate(False)
        inner = ctk.CTkFrame(pill, fg_color="transparent")
        inner.place(relx=.5, rely=.5, anchor="center")
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack()
        ctk.CTkLabel(top, text="", image=self.ico("flame", 28, "#FF4D63")).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            top, text=f"Racha: {days} día{'s' if days != 1 else ''}",
            font=(FONT, 20, "bold"), text_color=TEXT
        ).pack(side="left")
        ctk.CTkLabel(
            inner, text="¡Sigue así!" if days else "¡Tú puedes lograrlo!",
            font=(FONT, 12), text_color=MUTED
        ).pack(pady=(1, 0))

    def feature_card(self, parent, col, icon, title, accent, tile_bg, sub, note, command):
        card = ctk.CTkFrame(
            parent, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=16, height=170
        )
        card.grid(row=0, column=col, sticky="nsew", padx=7)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)

        tile = ctk.CTkFrame(card, width=54, height=54, corner_radius=27, fg_color=tile_bg)
        tile.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(18, 12), pady=(20, 0))
        tile.grid_propagate(False)
        ctk.CTkLabel(tile, text="", image=self.ico(icon, 28, accent)).place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(card, text=title, font=(FONT, 14, "bold"), text_color=TEXT).grid(row=0, column=1, sticky="sw", pady=(20, 0))
        ctk.CTkLabel(card, text="", image=self.ico("chev_r", 16, TEXT)).grid(row=0, column=2, sticky="se", padx=(0, 18), pady=(0, 2))
        ctk.CTkLabel(card, text=sub, font=(FONT, 12), text_color=MUTED, anchor="w", justify="left").grid(
            row=1, column=1, columnspan=2, sticky="nw", pady=(2, 0)
        )
        if note:
            ctk.CTkLabel(
                card, text=note, font=(FONT, 11), text_color=MUTED, anchor="w",
                justify="left", wraplength=230
            ).grid(row=2, column=0, columnspan=3, sticky="nw", padx=20, pady=(12, 0))

        self.make_clickable(card, command)

    def quick_menu(self):
        menu = tk.Menu(
            self, tearoff=0, bg=CARD, fg=TEXT, activebackground=RED_DARK,
            activeforeground=TEXT, bd=0, font=(FONT, 11)
        )
        menu.add_command(label="＋  Agregar ingreso", command=lambda: self.open_entry("income"))
        menu.add_command(label="＋  Agregar obligación", command=lambda: self.open_entry("obligation"))
        menu.add_separator()
        menu.add_command(label="Objetivos de ahorro", command=lambda: self.navigate("Objetivos de ahorro"))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Records
    # ------------------------------------------------------------------
    def section_title(self, title, subtitle=""):
        head = ctk.CTkFrame(self.body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(16, 12))
        head.grid_columnconfigure(0, weight=1)
        text = ctk.CTkFrame(head, fg_color="transparent")
        text.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(text, text=title, font=("Segoe UI", 25, "bold"), text_color=TEXT).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(text, text=subtitle, font=("Segoe UI", 10), text_color=MUTED, wraplength=760, justify="left").pack(anchor="w", pady=(3, 0))
        art_path = SECTION_ART.get(title)
        if art_path:
            art = self.load_art(art_path, (84, 84), circle=True)
            if art:
                self._image_refs.append(art)
                ctk.CTkLabel(head, text="", image=art).grid(row=0, column=1, sticky="e", padx=(12, 4))
        ctk.CTkFrame(head, height=2, fg_color=RED).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(11, 0))

    # ------------------------------------------------------------------
    # Interactividad común: hover, barras animadas, tarjetas de resumen
    # ------------------------------------------------------------------
    def add_hover(self, card, base=BORDER, hover=RED_SOFT, bg=PANEL, bg_hover=PANEL_HOVER):
        """Resalta la tarjeta al pasar el cursor (sin romper el hover de sus botones)."""
        base_cls = getattr(ctk, "CTkBaseClass", None)

        def inside():
            try:
                x, y = card.winfo_pointerxy()
                return (card.winfo_rootx() <= x < card.winfo_rootx() + card.winfo_width()
                        and card.winfo_rooty() <= y < card.winfo_rooty() + card.winfo_height())
            except tk.TclError:
                return False

        def enter(_event=None):
            try:
                card.configure(border_color=hover, fg_color=bg_hover)
            except tk.TclError:
                pass

        def leave(_event=None):
            def check():
                try:
                    if not inside():
                        card.configure(border_color=base, fg_color=bg)
                except tk.TclError:
                    pass
            card.after(30, check)

        def walk(widget):
            try:
                widget.bind("<Enter>", enter)
                widget.bind("<Leave>", leave)
            except Exception:
                pass
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if base_cls is None or isinstance(child, base_cls):
                        walk(child)

        walk(card)

    def animate_bar(self, bar, target, steps=20, delay=16):
        """La barra se llena con una animación suave al abrir la página."""
        target = max(0.0, min(float(target), 1.0))
        if not settings.get("animations"):
            try:
                bar.set(target)
            except tk.TclError:
                pass
            return

        def tick(i=1):
            try:
                if not bar.winfo_exists():
                    return
                eased = 1 - (1 - i / steps) ** 3
                bar.set(target * eased)
                if i < steps:
                    bar.after(delay, tick, i + 1)
            except tk.TclError:
                pass

        try:
            bar.set(0)
        except tk.TclError:
            return
        tick()

    def kpi_tile(self, parent, col, icon, label, value, color, tile_bg):
        parent.grid_columnconfigure(col, weight=1, uniform="kpi")
        f = ctk.CTkFrame(parent, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=14, height=88)
        f.grid(row=0, column=col, sticky="ew", padx=5, pady=4)
        f.grid_propagate(False)
        f.grid_columnconfigure(1, weight=1)
        f.grid_rowconfigure((0, 1), weight=1)
        tile = ctk.CTkFrame(f, width=46, height=46, corner_radius=23, fg_color=tile_bg)
        tile.grid(row=0, column=0, rowspan=2, padx=(16, 12))
        tile.grid_propagate(False)
        ctk.CTkLabel(tile, text="", image=self.ico(icon, 22, color)).place(relx=.5, rely=.5, anchor="center")
        ctk.CTkLabel(f, text=label.upper(), text_color=MUTED, font=(FONT, 9, "bold"), anchor="w").grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(f, text=value, text_color=color, font=(FONT, 17, "bold"), anchor="w").grid(row=1, column=1, sticky="nw")
        self.add_hover(f)
        return f

    def kpi_row(self, row):
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        return frame

    # ------------------------------------------------------------------
    # Ingresos / Obligaciones
    # ------------------------------------------------------------------
    def show_records(self, kind):
        is_income = kind == "income"
        title = "Ingresos" if is_income else "Obligaciones"
        accent = GREEN if is_income else RED
        accent_dark = GREEN_DARK if is_income else RED_DARK
        self.section_title(title, "Administra tus movimientos. Los cambios recurrentes se aplican desde el siguiente mes.")

        data = db.get_month_data(self.current_month)
        total = data["income"] if is_income else data["obligations"]
        first_total = data["fixed_total"] if is_income else data["rec_total"]
        second_total = data["extra_total"] if is_income else data["one_total"]
        first_name = "Fijos mensuales" if is_income else "Recurrentes"
        second_name = "Adicionales" if is_income else "Puntuales"

        kpis = self.kpi_row(1)
        self.kpi_tile(kpis, 0, "coins" if is_income else "wallet", "Total del mes", money(total), accent, accent_dark)
        self.kpi_tile(kpis, 1, "clock", first_name, money(first_total), TEXT, "#172331")
        self.kpi_tile(kpis, 2, "bolt", second_name, money(second_total), TEXT, "#172331")

        # barra de composición
        comp = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=14, height=74)
        comp.grid(row=2, column=0, sticky="ew", pady=(2, 8))
        comp.grid_propagate(False)
        comp.grid_columnconfigure(0, weight=1)
        share = first_total / total if total else 0
        ctk.CTkLabel(comp, text="COMPOSICIÓN DEL MES", text_color=MUTED, font=(FONT, 9, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(12, 0))
        ctk.CTkLabel(
            comp, text=(f"{first_name} {share * 100:.0f}%  ·  {second_name} {(1 - share) * 100:.0f}%" if total else "Sin movimientos"),
            text_color=TEXT, font=(FONT, 11, "bold")
        ).grid(row=0, column=1, sticky="e", padx=18, pady=(12, 0))
        bar = ctk.CTkProgressBar(comp, height=10, progress_color=accent, fg_color="#1B2735")
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 14))
        self.animate_bar(bar, share if total else 0)

        form = self.record_form if self.record_form and self.record_form["kind"] == kind else None
        adding = bool(form and form["mode"] == "add")
        add_btn = ctk.CTkButton(
            self.body,
            text=("✕  Cerrar formulario" if adding else "＋  Agregar " + ("ingreso" if is_income else "obligación")),
            height=42, width=220, fg_color="#172331" if adding else RED, hover_color="#223449" if adding else RED_2,
            font=(FONT, 12, "bold"), command=lambda: self.open_entry(kind)
        )
        add_btn.grid(row=3, column=0, sticky="w", pady=(0, 4))
        if form:
            self.build_record_form(4, kind, accent, form)

        sections = [
            (first_name, data["fixed"] if is_income else data["recurring"], True),
            (second_name, data["extras"] if is_income else data["oneoffs"], False),
        ]
        row = 5
        for heading, records, recurrent in sections:
            ctk.CTkLabel(self.body, text=heading.upper(), text_color=TEXT, font=(FONT, 12, "bold")).grid(row=row, column=0, sticky="w", pady=(14, 7))
            row += 1
            if not records:
                empty = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER_SOFT, corner_radius=12, height=62)
                empty.grid(row=row, column=0, sticky="ew", pady=3)
                empty.grid_propagate(False)
                ctk.CTkLabel(empty, text="Sin registros en este periodo.", text_color=MUTED).place(relx=0.5, rely=0.5, anchor="center")
                row += 1
            for rec in records:
                card = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=12, height=70)
                card.grid(row=row, column=0, sticky="ew", pady=3)
                card.grid_propagate(False)
                card.grid_columnconfigure(1, weight=1)
                card.grid_columnconfigure(2, minsize=150)
                card.grid_rowconfigure(0, weight=1)
                ctk.CTkFrame(card, width=4, height=34, corner_radius=2, fg_color=accent).grid(row=0, column=0, padx=(14, 0))
                info = ctk.CTkFrame(card, fg_color="transparent")
                info.grid(row=0, column=1, sticky="w", padx=14)
                ctk.CTkLabel(info, text=rec["concept"], text_color=TEXT, font=(FONT, 12, "bold"), anchor="w").pack(anchor="w")
                pct = rec["amount"] / total * 100 if total else 0
                ctk.CTkLabel(info, text=f"{pct:.0f}% del total del mes", text_color=MUTED, font=(FONT, 9), anchor="w").pack(anchor="w")
                ctk.CTkLabel(card, text=money(rec["amount"]), text_color=accent, font=(FONT, 13, "bold"), anchor="e").grid(row=0, column=2, sticky="e", padx=15)
                if recurrent:
                    ctk.CTkButton(card, text="Editar próximo mes", width=145, height=30, fg_color="#172331", hover_color="#223449", command=lambda k=kind, i=rec["id"], c=rec["concept"], a=rec["amount"]: self.edit_recurring_dialog(k, i, c, a)).grid(row=0, column=3, padx=4)
                    ctk.CTkButton(card, text="Desactivar", width=90, height=30, fg_color=RED_DARK, hover_color="#51202A", command=lambda k=kind, i=rec["id"]: self.deactivate(k, i)).grid(row=0, column=4, padx=10)
                else:
                    ctk.CTkButton(card, text="Eliminar", width=90, height=30, fg_color=RED_DARK, hover_color="#51202A", command=lambda k=kind, i=rec["id"]: self.delete_monthly(k, i)).grid(row=0, column=3, padx=10)
                self.add_hover(card)
                row += 1

    def open_entry(self, kind):
        """Abre (o cierra) el formulario de nuevo registro dentro de la misma página."""
        if self.record_form and self.record_form["kind"] == kind and self.record_form["mode"] == "add":
            self.record_form = None
        else:
            self.record_form = {"kind": kind, "mode": "add"}
        self.render_page()

    def build_record_form(self, row, kind, accent, form):
        is_income = kind == "income"
        editing = form["mode"] == "edit"
        panel = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=accent, corner_radius=14)
        panel.grid(row=row, column=0, sticky="ew", pady=(4, 8))
        panel.grid_columnconfigure((0, 1), weight=1, uniform="f")

        title = (f"MODIFICAR DESDE {month_label(self.next_month(self.current_month)).upper()}" if editing
                 else "NUEVO " + ("INGRESO" if is_income else "OBLIGACIÓN"))
        ctk.CTkLabel(panel, text=title, font=(FONT, 13, "bold"), text_color=TEXT).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            panel, text=("El cambio aplicará desde el siguiente mes." if editing else "Completa los datos del movimiento."),
            font=(FONT, 10), text_color=MUTED
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 10))

        concept = ctk.CTkEntry(panel, placeholder_text="Concepto", height=40)
        concept.grid(row=2, column=0, sticky="ew", padx=(20, 8), pady=5)
        amount = ctk.CTkEntry(panel, placeholder_text="Valor (ej. 850000)", height=40)
        amount.grid(row=2, column=1, sticky="ew", padx=(8, 20), pady=5)

        typ = ctk.StringVar(value="Fijo mensual" if is_income else "Recurrente")
        start = ctk.StringVar(value="Mes actual")
        duration = None
        if editing:
            concept.insert(0, form["concept"])
            amount.insert(0, form["amount"])
        else:
            type_menu = ctk.CTkOptionMenu(panel, values=["Fijo mensual", "Adicional"] if is_income else ["Recurrente", "Puntual"], variable=typ, height=40)
            type_menu.grid(row=3, column=0, sticky="ew", padx=(20, 8), pady=5)
            start_menu = ctk.CTkOptionMenu(panel, values=["Mes actual", "Mes siguiente"], variable=start, height=40)
            start_menu.grid(row=3, column=1, sticky="ew", padx=(8, 20), pady=5)
            duration = ctk.CTkEntry(panel, placeholder_text="Duración en meses (opcional)", height=40)
            duration.grid(row=4, column=0, columnspan=2, sticky="ew", padx=20, pady=5)

            def on_type(*_):
                recurrent = typ.get() in ("Recurrente", "Fijo mensual")
                state = "normal" if recurrent else "disabled"
                try:
                    start_menu.configure(state=state)
                    duration.configure(state=state)
                except Exception:
                    pass
            typ.trace_add("write", on_type)

        error = ctk.CTkLabel(panel, text="", text_color=RED, font=(FONT, 10), anchor="w")
        error.grid(row=5, column=0, columnspan=2, sticky="w", padx=20, pady=(2, 0))

        def cancel():
            self.record_form = None
            self.render_page()

        def save():
            try:
                name = concept.get().strip()
                val = float(amount.get().replace(".", "").replace(",", "."))
                if not name or val <= 0:
                    raise ValueError()
                if editing:
                    db.edit_recurring(kind, form["rid"], name, val, self.next_month(self.current_month))
                elif typ.get() in ("Recurrente", "Fijo mensual"):
                    start_month = self.current_month if start.get() == "Mes actual" else self.next_month(self.current_month)
                    dur = duration.get().strip()
                    months = int(dur) if dur else None
                    if months is not None and months <= 0:
                        raise ValueError()
                    db.add_recurring(kind, name, val, start_month, months)
                else:
                    db.add_monthly(kind, self.current_month, name, val, date.today().isoformat())
            except Exception:
                error.configure(text="Escribe un concepto y un valor mayor que cero. La duración debe ser un número entero.")
                return
            self.record_form = None
            self.render_page()

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", padx=20, pady=(8, 16))
        ctk.CTkButton(buttons, text="Cancelar", width=110, height=38, fg_color="#172331", hover_color="#223449", command=cancel).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Guardar", width=140, height=38, fg_color=accent if is_income else RED, hover_color=RED_2, text_color=BG if is_income else TEXT, font=(FONT, 12, "bold"), command=save).pack(side="left")
        concept.focus_set()

    def next_month(self, key):
        y, m = map(int, key.split("-"))
        return month_key(y + 1, 1) if m == 12 else month_key(y, m + 1)

    def edit_recurring_dialog(self, kind, rid, old_concept, old_amount):
        """Edita un movimiento recurrente en el formulario de la misma página."""
        shown = f"{old_amount:.0f}" if float(old_amount).is_integer() else str(old_amount)
        self.record_form = {"kind": kind, "mode": "edit", "rid": rid, "concept": old_concept, "amount": shown}
        self.render_page()

    def deactivate(self, kind, rid):
        if messagebox.askyesno("Desactivar", "Se desactivará desde el siguiente mes. ¿Continuar?"):
            db.deactivate_recurring(kind, rid, self.next_month(self.current_month))
            self.render_page()

    def delete_monthly(self, kind, rid):
        if messagebox.askyesno("Eliminar", "¿Eliminar este registro del mes seleccionado?"):
            db.delete_monthly(kind, rid)
            self.render_page()

    # ------------------------------------------------------------------
    # Other pages - same visual system
    # ------------------------------------------------------------------
    def show_history(self):
        self.section_title("Historial", "Consulta la evolución de tus ingresos, obligaciones y resultado mensual.")
        rows = db.history(24)
        recent = rows[-12:]

        # gráfica de los últimos 12 meses
        chart = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=16)
        chart.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        chart.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(chart, text="ÚLTIMOS 12 MESES", text_color=MUTED, font=(FONT, 9, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        legend = ctk.CTkFrame(chart, fg_color="transparent")
        legend.grid(row=0, column=1, sticky="e", padx=18, pady=(14, 0))
        for color, text in ((GREEN, "Ingresos"), (RED, "Obligaciones")):
            ctk.CTkFrame(legend, width=10, height=10, corner_radius=5, fg_color=color).pack(side="left", padx=(10, 5))
            ctk.CTkLabel(legend, text=text, text_color=MUTED, font=(FONT, 10)).pack(side="left")
        try:
            labels = [MONTHS_ABBR[int(m.split("-")[1]) - 1] for m, *_ in recent]
            pil = visuals.render_history_chart(recent, labels, size=(900, 190), bg=PANEL)
            img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(900, 190))
            self._image_refs.append(img)
            ctk.CTkLabel(chart, text="", image=img).grid(row=1, column=0, columnspan=2, padx=14, pady=(6, 14))
        except Exception:
            pass
        self.add_hover(chart, hover=BORDER, bg_hover=PANEL)

        cols = {1: 190, 2: 190, 3: 150}

        def align(frame):
            frame.grid_columnconfigure(0, weight=1)
            for c, w in cols.items():
                frame.grid_columnconfigure(c, minsize=w)

        head = ctk.CTkFrame(self.body, fg_color="transparent", height=26)
        head.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        align(head)
        for c, t in ((0, "MES"), (1, "INGRESOS"), (2, "OBLIGACIONES"), (3, "RESULTADO")):
            ctk.CTkLabel(head, text=t, text_color=DIM, font=(FONT, 9, "bold"), anchor="w" if c == 0 else "e").grid(
                row=0, column=c, sticky="w" if c == 0 else "e", padx=18 if c in (0, 3) else 12)

        for i, (month, inc, obl, res) in enumerate(reversed(rows), start=3):
            has = bool(inc or obl)
            state = status(res) if has else "NEUTRO"
            accent = GREEN if state == "POSITIVO" else RED if state == "NEGATIVO" else BLUE
            arrow = "▲ " if state == "POSITIVO" else "▼ " if state == "NEGATIVO" else "● "
            f = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=12, height=60)
            f.grid(row=i, column=0, sticky="ew", pady=3)
            f.grid_propagate(False)
            align(f)
            f.grid_rowconfigure(0, weight=1)
            ctk.CTkLabel(f, text=month_label(month), text_color=TEXT if has else DIM, font=(FONT, 12, "bold")).grid(row=0, column=0, padx=18, sticky="w")
            ctk.CTkLabel(f, text=money(inc) if has else "—", text_color=GREEN if has else DIM, font=(FONT, 11), anchor="e").grid(row=0, column=1, padx=12, sticky="e")
            ctk.CTkLabel(f, text=money(obl) if has else "—", text_color=RED if has else DIM, font=(FONT, 11), anchor="e").grid(row=0, column=2, padx=12, sticky="e")
            ctk.CTkLabel(f, text=(arrow + money(res)) if has else "—", text_color=accent if has else DIM, font=(FONT, 12, "bold"), anchor="e").grid(row=0, column=3, padx=18, sticky="e")
            self.add_hover(f)

    # ------------------------------------------------------------------
    # Rachas
    # ------------------------------------------------------------------
    def show_streaks(self):
        state, count = streak_info()
        pretty = {"POSITIVO": "Te sobró dinero", "NEGATIVO": "Te faltó dinero", "NEUTRO": "Estás al ras", "SIN DATOS": "Sin datos"}.get(state, state)
        accent = RED if state == "NEGATIVO" else GREEN if state == "POSITIVO" else BLUE
        self.section_title("Rachas", "Mantén el mismo resultado financiero durante tres meses consecutivos para activar una racha.")
        card = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=18, height=270)
        card.grid(row=1, column=0, sticky="ew", pady=5)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)
        art = self.load_art(STREAK_IMAGES.get(state, STREAK_IMAGES["NEUTRO"]), (200, 200), circle=True)
        label = ctk.CTkLabel(card, text="", image=art)
        label._telarana_image = art
        self._image_refs.append(art)
        label.grid(row=0, column=0, padx=30, pady=25)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", padx=(0, 30))
        ctk.CTkLabel(info, text="RACHA ACTUAL", text_color=MUTED, font=(FONT, 10, "bold")).pack(anchor="w")
        ctk.CTkLabel(info, text=pretty, text_color=TEXT, font=(FONT, 26, "bold")).pack(anchor="w", pady=(2, 8))

        steps = ctk.CTkFrame(info, fg_color="transparent")
        steps.pack(anchor="w", pady=(0, 10))
        for n in range(3):
            done = n < min(count, 3)
            dot = ctk.CTkFrame(
                steps, width=38, height=38, corner_radius=19,
                fg_color=accent if done else "#121B26", border_width=2, border_color=accent if done else BORDER
            )
            dot.pack(side="left", padx=(0, 10))
            dot.pack_propagate(False)
            ctk.CTkLabel(dot, text="✓" if done else str(n + 1), text_color=BG if done else MUTED, font=(FONT, 14, "bold")).place(relx=.5, rely=.5, anchor="center")
        bar = ctk.CTkProgressBar(info, width=320, height=10, progress_color=accent, fg_color="#1B2735")
        bar.pack(anchor="w", pady=(0, 8))
        self.animate_bar(bar, min(count, 3) / 3)
        ctk.CTkLabel(
            info, text=f"{count} mes(es) consecutivos  ·  " + ("¡Racha activa!" if count >= 3 else f"faltan {3 - count} para la racha"),
            text_color=accent, font=(FONT, 12, "bold")
        ).pack(anchor="w")
        self.add_hover(card)

        tiles = self.kpi_row(2)
        self.kpi_tile(tiles, 0, "flame", "Meses seguidos", str(count), accent, "#172331")
        self.kpi_tile(tiles, 1, "clock", "Días de racha", str(streak_days(count)), TEXT, "#172331")
        self.kpi_tile(tiles, 2, "target", "Meta", "3 meses", TEXT, "#172331")

    # ------------------------------------------------------------------
    # Proyección
    # ------------------------------------------------------------------
    def show_projection(self):
        self.section_title("Proyección", "Estimación basada en ingresos y obligaciones recurrentes del periodo seleccionado.")
        data = db.get_month_data(self.current_month)
        ratio = committed_ratio(data)
        has = data["income"] > 0 or data["obligations"] > 0
        result_color = GREEN if data["result"] > 0.005 else RED if data["result"] < -0.005 else BLUE

        tiles = self.kpi_row(1)
        self.kpi_tile(tiles, 0, "coins", "Ingresos estimados", money(data["income"]), GREEN, GREEN_DARK)
        self.kpi_tile(tiles, 1, "wallet", "Obligaciones estimadas", money(data["obligations"]), RED, RED_DARK)
        self.kpi_tile(tiles, 2, "trend", "Resultado estimado", money(data["result"]), result_color, BLUE_DARK)

        panel = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=16)
        panel.grid(row=2, column=0, sticky="ew", pady=(6, 6))
        panel.grid_columnconfigure(0, weight=1)
        limit = settings.get("alert_threshold") / 100
        bar_color = RED if ratio >= limit else "#FFB84D" if ratio >= limit - 0.2 else GREEN
        ctk.CTkLabel(panel, text="INGRESOS COMPROMETIDOS", text_color=MUTED, font=(FONT, 9, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(panel, text=f"{ratio * 100:.0f}%" if has else "—", text_color=bar_color if has else MUTED, font=(FONT, 22, "bold")).grid(row=0, column=1, sticky="e", padx=20, pady=(12, 0))
        bar = ctk.CTkProgressBar(panel, height=12, progress_color=bar_color, fg_color="#1B2735")
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 8))
        self.animate_bar(bar, ratio if has else 0)
        found = alerts(data, ratio)
        if not has:
            note = "Aún no hay datos en este periodo. Agrega ingresos y obligaciones para ver la proyección."
        elif found:
            note = "⚠  " + found[0]
        else:
            note = "Todo en orden: tus obligaciones están por debajo del límite recomendado."
        ctk.CTkLabel(panel, text=note, text_color=TEXT if has else MUTED, font=(FONT, 11), anchor="w", justify="left", wraplength=820).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 6))
        ctk.CTkLabel(panel, text="La proyección no crea ni modifica registros: sirve para anticipar el resultado con la información ya guardada.", text_color=DIM, font=(FONT, 9), anchor="w", wraplength=820, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 16))
        self.add_hover(panel, hover=BORDER, bg_hover=PANEL)

    # ------------------------------------------------------------------
    # Objetivos de ahorro
    # ------------------------------------------------------------------
    def show_goals(self):
        self.section_title("Objetivos de ahorro", "Crea metas y registra aportes sin alterar el resultado de ingresos menos obligaciones.")
        goals = db.list_goals()
        saved_total = sum(g["saved"] for g in goals)
        target_total = sum(g["target"] for g in goals)

        tiles = self.kpi_row(1)
        self.kpi_tile(tiles, 0, "target", "Objetivos activos", str(len(goals)), TEXT, "#172331")
        self.kpi_tile(tiles, 1, "coins", "Total ahorrado", money(saved_total), GREEN, GREEN_DARK)
        self.kpi_tile(tiles, 2, "trend", "Progreso general", f"{(saved_total / target_total * 100) if target_total else 0:.0f}%", BLUE, BLUE_DARK)

        form = self.goal_form
        creating = bool(form and form["mode"] == "new")
        ctk.CTkButton(
            self.body, text="✕  Cerrar formulario" if creating else "＋  Crear objetivo", height=42, width=200,
            fg_color="#172331" if creating else RED, hover_color="#223449" if creating else RED_2,
            font=(FONT, 12, "bold"), command=self.add_goal_dialog
        ).grid(row=2, column=0, sticky="w", pady=(6, 6))

        row = 3
        if creating:
            self.goal_panel(
                row, "NUEVO OBJETIVO", "Ponle un nombre y define cuánto quieres ahorrar.",
                ["Nombre del objetivo", "Meta en pesos (ej. 2000000)"], "Crear objetivo", self.save_new_goal
            )
            row += 1

        for g in goals:
            ratio = min(g["saved"] / g["target"], 1) if g["target"] else 0
            done = ratio >= 1
            color = GREEN if done else BLUE if ratio < 0.5 else "#FFB84D" if ratio < 0.8 else GREEN
            f = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=14, height=92)
            f.grid(row=row, column=0, sticky="ew", pady=4)
            f.grid_propagate(False)
            f.grid_columnconfigure(0, weight=1)
            f.grid_columnconfigure(2, minsize=60)
            f.grid_rowconfigure((0, 1), weight=1)
            ctk.CTkLabel(f, text=("✓  " if done else "") + g["name"], font=(FONT, 13, "bold"), text_color=GREEN if done else TEXT, anchor="w").grid(row=0, column=0, sticky="sw", padx=18)
            ctk.CTkLabel(f, text=f"{money(g['saved'])} de {money(g['target'])}" + ("  ·  ¡Meta cumplida!" if done else f"  ·  faltan {money(g['target'] - g['saved'])}"), text_color=MUTED, font=(FONT, 10), anchor="w").grid(row=1, column=0, sticky="nw", padx=18)
            bar = ctk.CTkProgressBar(f, width=230, height=10, progress_color=color, fg_color="#1B2735")
            bar.grid(row=0, column=1, rowspan=2, padx=12)
            self.animate_bar(bar, ratio)
            ctk.CTkLabel(f, text=f"{ratio * 100:.0f}%", text_color=color, font=(FONT, 14, "bold"), anchor="e").grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 8))
            ctk.CTkButton(f, text="＋ Aportar", width=100, height=34, fg_color=RED, hover_color=RED_2, command=lambda gid=g["id"]: self.contribute_dialog(gid)).grid(row=0, column=3, rowspan=2, padx=(8, 6))
            ctk.CTkButton(f, text="✕", width=34, height=34, fg_color="#172331", hover_color=RED_DARK, command=lambda gid=g["id"]: self.remove_goal(gid, "")).grid(row=0, column=4, rowspan=2, padx=(0, 14))
            self.add_hover(f)
            row += 1

            if form and form.get("gid") == g["id"]:
                if form["mode"] == "contribute":
                    self.goal_panel(
                        row, f"APORTAR A «{g['name'].upper()}»", f"Faltan {money(max(g['target'] - g['saved'], 0))} para completar la meta.",
                        ["Valor del aporte"], "Guardar aporte", lambda vals, gid=g["id"]: self.save_contribution(gid, vals)
                    )
                else:
                    self.goal_panel(
                        row, f"ELIMINAR «{g['name'].upper()}»", "El objetivo dejará de mostrarse. Tus ingresos y obligaciones no cambian.",
                        [], "Sí, eliminar", lambda vals, gid=g["id"]: self.confirm_remove_goal(gid), danger=True
                    )
                row += 1

        if not goals:
            empty = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER_SOFT, corner_radius=14, height=110)
            empty.grid(row=row, column=0, sticky="ew", pady=8)
            empty.grid_propagate(False)
            ctk.CTkLabel(empty, text="Todavía no tienes objetivos de ahorro.\nCrea el primero con el botón de arriba.", text_color=MUTED, font=(FONT, 12), justify="center").place(relx=0.5, rely=0.5, anchor="center")

    # --- formularios dentro de la página (sin ventanas extra) ---------------
    @staticmethod
    def parse_amount(text):
        return float(text.replace(".", "").replace(",", "."))

    def goal_panel(self, row, title, hint, placeholders, save_text, on_save, danger=False):
        panel = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=RED if danger else BLUE, corner_radius=14)
        panel.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=title, font=(FONT, 13, "bold"), text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(panel, text=hint, font=(FONT, 10), text_color=MUTED, anchor="w").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        entries = []
        for i, ph in enumerate(placeholders):
            e = ctk.CTkEntry(panel, placeholder_text=ph, height=40)
            e.grid(row=2 + i, column=0, sticky="ew", padx=20, pady=5)
            entries.append(e)
        error = ctk.CTkLabel(panel, text="", text_color=RED, font=(FONT, 10), anchor="w")
        error.grid(row=10, column=0, sticky="w", padx=20)

        def cancel():
            self.goal_form = None
            self.render_page()

        def save():
            message = on_save([e.get().strip() for e in entries])
            if message:
                error.configure(text=message)

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=11, column=0, sticky="e", padx=20, pady=(8, 16))
        ctk.CTkButton(buttons, text="Cancelar", width=110, height=38, fg_color="#172331", hover_color="#223449", command=cancel).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=save_text, width=150, height=38, fg_color=RED if danger else BLUE, hover_color=RED_2 if danger else "#5E92E8", text_color=TEXT if danger else BG, font=(FONT, 12, "bold"), command=save).pack(side="left")
        if entries:
            entries[0].focus_set()

    def add_goal_dialog(self):
        """Abre (o cierra) el formulario de nuevo objetivo dentro de la página."""
        self.goal_form = None if (self.goal_form and self.goal_form["mode"] == "new") else {"mode": "new"}
        self.render_page()

    def save_new_goal(self, values):
        try:
            name, target = values[0], self.parse_amount(values[1])
            if not name or target <= 0:
                raise ValueError()
        except Exception:
            return "Escribe un nombre y una meta mayor que cero."
        db.add_goal(name, target)
        self.goal_form = None
        self.render_page()

    def contribute_dialog(self, gid):
        same = self.goal_form and self.goal_form["mode"] == "contribute" and self.goal_form["gid"] == gid
        self.goal_form = None if same else {"mode": "contribute", "gid": gid}
        self.render_page()

    def save_contribution(self, gid, values):
        try:
            amount = self.parse_amount(values[0])
            if amount <= 0:
                raise ValueError()
        except Exception:
            return "Escribe un valor mayor que cero."
        db.add_goal_contribution(gid, amount)
        self.goal_form = None
        self.render_page()

    def remove_goal(self, gid, _name=""):
        same = self.goal_form and self.goal_form["mode"] == "delete" and self.goal_form["gid"] == gid
        self.goal_form = None if same else {"mode": "delete", "gid": gid}
        self.render_page()

    def confirm_remove_goal(self, gid):
        db.delete_goal(gid)
        self.goal_form = None
        self.render_page()

    def show_game(self):
        self.section_title("Mini juego", "Un pequeño reto para poner a prueba tu criterio financiero.")
        self.panel(self.body, 1, 0, 1, "Reto rápido", "Si recibes $1.000.000 y tus obligaciones son $750.000, ¿cuánto te queda?")
        box = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=15, height=96)
        box.grid(row=2, column=0, sticky="ew", pady=6)
        box.pack_propagate(False)
        answer = ctk.CTkEntry(box, placeholder_text="Tu respuesta en pesos", width=300, height=40)
        answer.pack(side="left", padx=18)
        feedback = ctk.CTkLabel(box, text="", text_color=GREEN, font=("Segoe UI", 11, "bold"))
        feedback.pack(side="left", padx=10)

        def check():
            try:
                ok = float(answer.get().replace(".", "").replace(",", ".")) == 250000
            except Exception:
                ok = False
            feedback.configure(text="¡Correcto! Te quedan $250.000." if ok else "Inténtalo de nuevo.")

        ctk.CTkButton(box, text="Comprobar", fg_color=RED, command=check).pack(side="left", padx=8)

    def show_settings(self):
        self.section_title("Configuración", "Personaliza la aplicación. Los cambios se aplican al instante y se guardan automáticamente.")

        def card(row, title, subtitle):
            f = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=16)
            f.grid(row=row, column=0, sticky="ew", pady=6)
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=title.upper(), text_color=TEXT, font=(FONT, 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=22, pady=(18, 2))
            ctk.CTkLabel(f, text=subtitle, text_color=MUTED, font=(FONT, 10), anchor="w", justify="left", wraplength=640).grid(row=1, column=0, columnspan=2, sticky="w", padx=22, pady=(0, 10))
            self.add_hover(f)
            return f

        def option_row(parent, row, label, hint, widget_factory):
            ctk.CTkFrame(parent, height=1, fg_color=BORDER_SOFT).grid(row=row * 2, column=0, columnspan=2, sticky="ew", padx=22)
            text = ctk.CTkFrame(parent, fg_color="transparent")
            text.grid(row=row * 2 + 1, column=0, sticky="w", padx=22, pady=12)
            ctk.CTkLabel(text, text=label, text_color=TEXT, font=(FONT, 12, "bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(text, text=hint, text_color=MUTED, font=(FONT, 9), anchor="w").pack(anchor="w")
            widget = widget_factory(parent)
            widget.grid(row=row * 2 + 1, column=1, sticky="e", padx=22)
            return widget

        # --- Alertas ---------------------------------------------------------
        alerts_card = card(1, "Alertas", "Define cuándo la aplicación te avisa que tus obligaciones consumen demasiados ingresos.")
        threshold_label = {}

        def make_slider(parent):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            value = ctk.CTkLabel(box, text=f"{settings.get('alert_threshold')}%", text_color=RED, font=(FONT, 14, "bold"), width=52)
            threshold_label["w"] = value

            def changed(v):
                v = int(round(float(v) / 5) * 5)
                value.configure(text=f"{v}%")
                settings.set("alert_threshold", v)

            slider = ctk.CTkSlider(box, from_=50, to=100, number_of_steps=10, width=220, progress_color=RED, button_color=RED, button_hover_color=RED_2, command=changed)
            slider.set(settings.get("alert_threshold"))
            slider.pack(side="left", padx=(0, 10))
            value.pack(side="left")
            return box

        option_row(alerts_card, 1, "Umbral de alerta", "Se avisa cuando las obligaciones alcanzan este porcentaje de tus ingresos.", make_slider)
        ctk.CTkFrame(alerts_card, height=10, fg_color="transparent").grid(row=4, column=0)

        # --- Formato ---------------------------------------------------------
        fmt = card(2, "Formato", "Cómo se muestran los valores de dinero en toda la aplicación.")

        def make_currency(parent):
            def changed(value):
                settings.set("currency", value)
                self.render_page()
            menu = ctk.CTkOptionMenu(parent, values=settings.CURRENCIES, width=130, height=36, command=changed)
            menu.set(settings.get("currency"))
            return menu

        option_row(fmt, 1, "Símbolo de moneda", f"Ejemplo: {money(1250000)}", make_currency)
        ctk.CTkFrame(fmt, height=10, fg_color="transparent").grid(row=4, column=0)

        # --- Comportamiento --------------------------------------------------
        behavior = card(3, "Comportamiento", "Preferencias de la interfaz.")

        def make_switch(key, after=None):
            def factory(parent):
                var = ctk.BooleanVar(value=bool(settings.get(key)))

                def changed():
                    settings.set(key, bool(var.get()))
                    if after:
                        after()
                sw = ctk.CTkSwitch(parent, text="", variable=var, onvalue=True, offvalue=False, progress_color=RED, command=changed, width=48)
                return sw
            return factory

        option_row(behavior, 1, "Animaciones", "Anillo de estado que respira y barras de progreso que se llenan.", make_switch("animations"))
        option_row(behavior, 2, "Barra lateral abierta al iniciar", "Muestra los nombres de las secciones cada vez que abres la aplicación.", make_switch("sidebar_expanded"))
        ctk.CTkFrame(behavior, height=10, fg_color="transparent").grid(row=6, column=0)

        # --- Acceso directo --------------------------------------------------
        shortcut = card(4, "Acceso directo", "Crea un icono de TELARAÑA en tu escritorio para abrir la aplicación con doble clic.")
        status_label = ctk.CTkLabel(shortcut, text="", text_color=MUTED, font=(FONT, 10), anchor="w", wraplength=520, justify="left")

        def make_shortcut_button(parent):
            def run():
                ok, message = self.create_desktop_shortcut()
                status_label.configure(text=message, text_color=GREEN if ok else RED)
            return ctk.CTkButton(parent, text="Crear en el escritorio", width=190, height=38, fg_color=RED, hover_color=RED_2, font=(FONT, 12, "bold"), command=run)

        option_row(shortcut, 1, "Escritorio", "Si mueves la carpeta del programa, vuelve a crearlo.", make_shortcut_button)
        status_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=22, pady=(0, 6))
        ctk.CTkFrame(shortcut, height=8, fg_color="transparent").grid(row=5, column=0)

        # --- Restablecer -----------------------------------------------------
        def restore():
            if messagebox.askyesno("Restablecer ajustes", "¿Volver todos los ajustes a sus valores originales? Tus ingresos, obligaciones y objetivos no se modifican."):
                settings.reset()
                self.render_page()

        ctk.CTkButton(self.body, text="Restablecer ajustes", height=40, width=200, fg_color="#172331", hover_color=RED_DARK, command=restore).grid(row=5, column=0, sticky="w", pady=(8, 4))
        ctk.CTkLabel(self.body, text=f"TELARAÑA v{__version__}", text_color=MUTED, font=(FONT, 10, "bold"), anchor="w").grid(row=6, column=0, sticky="w", pady=(10, 0))
        ctk.CTkLabel(self.body, text=f"Base de datos local: {db.DB_PATH}", text_color=DIM, font=(FONT, 9), wraplength=900, anchor="w", justify="left").grid(row=7, column=0, sticky="w", pady=(4, 14))

    def create_desktop_shortcut(self):
        """Crea TELARAÑA.lnk en el escritorio (Windows). Devuelve (ok, mensaje)."""
        if sys.platform != "win32":
            return False, "El acceso directo solo se puede crear en Windows."
        import os
        import subprocess
        try:
            if getattr(sys, "frozen", False):
                target, args, workdir = sys.executable, "", str(Path(sys.executable).parent)
            else:
                exe = Path(sys.executable)
                pyw = exe.with_name("pythonw.exe")
                target = str(pyw if pyw.exists() else exe)
                args = f'"{BASE_DIR / "main.py"}"'
                workdir = str(BASE_DIR)
            env = dict(os.environ, TL_TARGET=target, TL_ARGS=args, TL_WORKDIR=workdir, TL_ICON=str(ASSET_DIR / "telarana.ico"))
            script = (
                "$d=[Environment]::GetFolderPath('Desktop');"
                "$f=Join-Path $d ('TELARA'+[char]0xD1+'A.lnk');"
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($f);"
                "$s.TargetPath=$env:TL_TARGET;$s.Arguments=$env:TL_ARGS;"
                "$s.WorkingDirectory=$env:TL_WORKDIR;$s.IconLocation=$env:TL_ICON;"
                "$s.Description='TELARANA';$s.Save();Write-Output $f"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                env=env, capture_output=True, text=True, timeout=30, creationflags=0x08000000
            )
            if result.returncode != 0:
                return False, "No se pudo crear el acceso directo. Créalo manualmente con clic derecho en el escritorio."
            return True, "Listo: ya tienes el icono TELARAÑA en tu escritorio."
        except Exception:
            return False, "No se pudo crear el acceso directo. Créalo manualmente con clic derecho en el escritorio."

    def show_alerts(self):
        data = db.get_month_data(self.current_month)
        found = alerts(data, committed_ratio(data))
        messagebox.showinfo(
            "Alertas | TELARAÑA",
            "\n\n".join(found) if found else "No hay alertas pendientes para el periodo seleccionado."
        )

    def panel(self, parent, row, col, span, title, body):
        f = ctk.CTkFrame(parent, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=15, height=125)
        f.grid(row=row, column=col, columnspan=span, sticky="ew", pady=6)
        f.grid_propagate(False)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 14, "bold"), text_color=TEXT).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(f, text=body, font=("Segoe UI", 10), text_color=MUTED, justify="left").pack(anchor="w", padx=18, pady=(0, 18))

    # ------------------------------------------------------------------
    # Animación: el anillo "respira" cambiando entre fotogramas precalculados
    # ------------------------------------------------------------------
    def animate_ui(self):
        label = self.ring_label
        if label is not None and self.ring_frames and settings.get("animations"):
            try:
                if label.winfo_exists():
                    self._glow_step = (self._glow_step + 1) % len(self.ring_frames)
                    label.configure(image=self.ring_frames[self._glow_step])
                else:
                    self.ring_label = None
            except tk.TclError:
                self.ring_label = None
        self.after(450, self.animate_ui)


if __name__ == "__main__":
    app = TelaranaApp()
    app.mainloop()
