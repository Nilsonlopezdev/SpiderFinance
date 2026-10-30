import calendar
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import date
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageOps, ImageDraw

from telarana import database as db
from telarana import visuals
from telarana.finance import (
    money, status, committed_ratio, streak_info, streak_days, projection, alerts
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

ASSET_DIR = Path(__file__).resolve().parent / "assets"
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
    ("Simulador", "calc"),
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
        self.geometry("1500x920")
        self.minsize(1180, 740)
        self.configure(fg_color=BG)

        self.current_month = date.today().strftime("%Y-%m")
        self.active_page = "Inicio"
        self.sidebar_expanded = False
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
            "Simulador": self.show_simulator,
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
        menu.add_command(label="Simulador", command=lambda: self.navigate("Simulador"))
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
        ctk.CTkLabel(head, text=title, font=("Segoe UI", 25, "bold"), text_color=TEXT).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(head, text=subtitle, font=("Segoe UI", 10), text_color=MUTED).pack(anchor="w", pady=(3, 0))
        ctk.CTkFrame(head, height=2, fg_color=RED).pack(anchor="w", fill="x", pady=(11, 0))

    def show_records(self, kind):
        is_income = kind == "income"
        title = "Ingresos" if is_income else "Obligaciones"
        accent = GREEN if is_income else RED
        self.section_title(title, "Administra tus movimientos con el mismo sistema visual del inicio. Los cambios recurrentes se aplican desde el siguiente mes.")

        toolbar = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=14, height=66)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_propagate(False)
        ctk.CTkButton(toolbar, text="＋  Agregar " + ("ingreso" if is_income else "obligación"), height=38, fg_color=RED, hover_color=RED_2, command=lambda: self.open_entry(kind)).pack(side="left", padx=14, pady=13)
        data = db.get_month_data(self.current_month)
        total = data["income"] if is_income else data["obligations"]
        ctk.CTkLabel(toolbar, text=f"TOTAL DEL MES  {money(total)}", text_color=accent, font=("Segoe UI", 12, "bold")).pack(side="right", padx=18)

        sections = [
            ("Fijos mensuales" if is_income else "Recurrentes", data["fixed"] if is_income else data["recurring"], True),
            ("Adicionales" if is_income else "Puntuales", data["extras"] if is_income else data["oneoffs"], False),
        ]
        row = 2
        for heading, records, recurrent in sections:
            ctk.CTkLabel(self.body, text=heading.upper(), text_color=TEXT, font=("Segoe UI", 12, "bold")).grid(row=row, column=0, sticky="w", pady=(12, 7))
            row += 1
            if not records:
                empty = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER_SOFT, corner_radius=12, height=62)
                empty.grid(row=row, column=0, sticky="ew", pady=3)
                empty.grid_propagate(False)
                ctk.CTkLabel(empty, text="Sin registros en este periodo.", text_color=MUTED).place(relx=0.5, rely=0.5, anchor="center")
                row += 1
            for rec in records:
                card = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=12, height=64)
                card.grid(row=row, column=0, sticky="ew", pady=3)
                card.grid_propagate(False)
                card.grid_columnconfigure(0, weight=1)
                card.grid_columnconfigure(1, minsize=150)
                card.grid_rowconfigure(0, weight=1)
                ctk.CTkLabel(card, text=rec["concept"], text_color=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=18)
                ctk.CTkLabel(card, text=money(rec["amount"]), text_color=accent, font=("Segoe UI", 12, "bold"), anchor="e").grid(row=0, column=1, sticky="e", padx=15)
                if recurrent:
                    ctk.CTkButton(card, text="Editar próximo mes", width=145, height=30, fg_color="#172331", hover_color="#223449", command=lambda k=kind, i=rec["id"], c=rec["concept"], a=rec["amount"]: self.edit_recurring_dialog(k, i, c, a)).grid(row=0, column=2, padx=4)
                    ctk.CTkButton(card, text="Desactivar", width=90, height=30, fg_color=RED_DARK, hover_color="#51202A", command=lambda k=kind, i=rec["id"]: self.deactivate(k, i)).grid(row=0, column=3, padx=10)
                else:
                    ctk.CTkButton(card, text="Eliminar", width=90, height=30, fg_color=RED_DARK, hover_color="#51202A", command=lambda k=kind, i=rec["id"]: self.delete_monthly(k, i)).grid(row=0, column=2, padx=10)
                row += 1

    def open_entry(self, kind):
        win = ctk.CTkToplevel(self)
        win.title("Nuevo registro | TELARAÑA")
        win.geometry("460x550")
        win.configure(fg_color=BG)
        win.grab_set()

        is_income = kind == "income"
        accent = GREEN if is_income else RED
        ctk.CTkLabel(win, text="NUEVO " + ("INGRESO" if is_income else "OBLIGACIÓN"), font=("Segoe UI", 20, "bold"), text_color=TEXT).pack(pady=(26, 4))
        ctk.CTkLabel(win, text="Completa los datos del movimiento.", text_color=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 18))
        concept = ctk.CTkEntry(win, placeholder_text="Concepto", width=350, height=40)
        concept.pack(pady=7)
        amount = ctk.CTkEntry(win, placeholder_text="Valor (ej. 850000)", width=350, height=40)
        amount.pack(pady=7)
        typ = ctk.StringVar(value="Recurrente" if not is_income else "Fijo mensual")
        ctk.CTkOptionMenu(win, values=["Recurrente", "Puntual"] if not is_income else ["Fijo mensual", "Adicional"], variable=typ, width=350, height=40).pack(pady=7)
        start = ctk.StringVar(value="Mes actual")
        ctk.CTkOptionMenu(win, values=["Mes actual", "Mes siguiente"], variable=start, width=350, height=40).pack(pady=7)
        duration = ctk.CTkEntry(win, placeholder_text="Duración en meses (opcional)", width=350, height=40)
        duration.pack(pady=7)
        ctk.CTkLabel(win, text="Deja la duración vacía si no tiene fecha de finalización.", text_color=MUTED, font=("Segoe UI", 9)).pack(pady=3)

        def save():
            try:
                name = concept.get().strip()
                val = float(amount.get().replace(".", "").replace(",", "."))
                if not name or val <= 0:
                    raise ValueError()
                if typ.get() in ("Recurrente", "Fijo mensual"):
                    start_month = self.current_month if start.get() == "Mes actual" else self.next_month(self.current_month)
                    dur = duration.get().strip()
                    months = int(dur) if dur else None
                    if months is not None and months <= 0:
                        raise ValueError()
                    db.add_recurring(kind, name, val, start_month, months)
                else:
                    db.add_monthly(kind, self.current_month, name, val, date.today().isoformat())
                win.destroy()
                self.render_page()
            except Exception:
                messagebox.showerror("Datos inválidos", "Escribe un concepto y un valor mayor que cero. La duración debe ser un número entero.")

        ctk.CTkButton(win, text="Guardar registro", fg_color=accent, hover_color=RED_2, width=350, height=42, command=save).pack(pady=22)

    def next_month(self, key):
        y, m = map(int, key.split("-"))
        return month_key(y + 1, 1) if m == 12 else month_key(y, m + 1)

    def edit_recurring_dialog(self, kind, rid, old_concept, old_amount):
        win = ctk.CTkToplevel(self)
        win.title("Modificar desde el siguiente mes")
        win.geometry("430x300")
        win.configure(fg_color=BG)
        win.grab_set()
        c = ctk.CTkEntry(win, width=330, height=40)
        c.insert(0, old_concept)
        c.pack(pady=(30, 10))
        a = ctk.CTkEntry(win, width=330, height=40)
        a.insert(0, str(old_amount))
        a.pack(pady=10)
        ctk.CTkLabel(win, text=f"El cambio aplicará desde {month_label(self.next_month(self.current_month))}.", text_color=MUTED).pack(pady=8)

        def save():
            try:
                val = float(a.get().replace(".", "").replace(",", "."))
                if not c.get().strip() or val <= 0:
                    raise ValueError()
                db.edit_recurring(kind, rid, c.get().strip(), val, self.next_month(self.current_month))
                win.destroy()
                self.render_page()
            except Exception:
                messagebox.showerror("Error", "Verifica el concepto y el valor.")

        ctk.CTkButton(win, text="Guardar cambios", fg_color=RED, command=save).pack(pady=15)

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
        cols = {1: 190, 2: 190, 3: 150}

        def align(frame):
            frame.grid_columnconfigure(0, weight=1)
            for c, w in cols.items():
                frame.grid_columnconfigure(c, minsize=w)

        head = ctk.CTkFrame(self.body, fg_color="transparent", height=26)
        head.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        align(head)
        for c, t in ((0, "MES"), (1, "INGRESOS"), (2, "OBLIGACIONES"), (3, "RESULTADO")):
            ctk.CTkLabel(head, text=t, text_color=DIM, font=("Segoe UI", 9, "bold"), anchor="w" if c == 0 else "e").grid(
                row=0, column=c, sticky="w" if c == 0 else "e", padx=18 if c in (0, 3) else 12)
        for i, (month, inc, obl, res) in enumerate(rows, start=2):
            state = status(res) if inc or obl else "NEUTRO"
            accent = GREEN if state == "POSITIVO" else RED if state == "NEGATIVO" else BLUE
            f = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=12, height=60)
            f.grid(row=i, column=0, sticky="ew", pady=3)
            f.grid_propagate(False)
            align(f)
            f.grid_rowconfigure(0, weight=1)
            ctk.CTkLabel(f, text=month_label(month), text_color=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, padx=18, sticky="w")
            ctk.CTkLabel(f, text=money(inc), text_color=GREEN, font=("Segoe UI", 11), anchor="e").grid(row=0, column=1, padx=12, sticky="e")
            ctk.CTkLabel(f, text=money(obl), text_color=RED, font=("Segoe UI", 11), anchor="e").grid(row=0, column=2, padx=12, sticky="e")
            ctk.CTkLabel(f, text=money(res), text_color=accent, font=("Segoe UI", 12, "bold"), anchor="e").grid(row=0, column=3, padx=18, sticky="e")

    def show_streaks(self):
        state, count = streak_info()
        pretty = {"POSITIVO": "Te sobró dinero", "NEGATIVO": "Te faltó dinero", "NEUTRO": "Estás al ras", "SIN DATOS": "Sin datos"}.get(state, state)
        self.section_title("Rachas", "Mantén el mismo resultado financiero durante tres meses consecutivos para activar una racha.")
        card = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=18, height=260)
        card.grid(row=1, column=0, sticky="ew", pady=5)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        art = self.load_art(STREAK_IMAGES.get(state, STREAK_IMAGES["NEUTRO"]), (190, 190), circle=True)
        label = ctk.CTkLabel(card, text="", image=art)
        label._telarana_image = art
        self._image_refs.append(art)
        label.grid(row=0, column=0, rowspan=4, padx=28, pady=25)
        ctk.CTkLabel(card, text="RACHA ACTUAL", text_color=MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="sw", pady=(30, 2))
        ctk.CTkLabel(card, text=pretty, text_color=TEXT, font=("Segoe UI", 22, "bold")).grid(row=1, column=1, sticky="nw")
        ctk.CTkLabel(card, text=f"{count} mes(es) consecutivos", text_color=RED if state == "NEGATIVO" else GREEN if state == "POSITIVO" else BLUE, font=("Segoe UI", 14, "bold")).grid(row=2, column=1, sticky="nw", pady=3)
        ctk.CTkLabel(card, text=f"Meta: 3 meses · faltan {max(0, 3 - count)}", text_color=MUTED, font=("Segoe UI", 10)).grid(row=3, column=1, sticky="nw")

    def show_projection(self):
        self.section_title("Proyección", "Estimación basada en ingresos y obligaciones recurrentes del periodo seleccionado.")
        data = db.get_month_data(self.current_month)
        cards = [("Ingresos estimados", money(data["income"]), GREEN), ("Obligaciones estimadas", money(data["obligations"]), RED), ("Resultado estimado", money(data["result"]), BLUE)]
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="ew")
        for i, (title, value, color) in enumerate(cards):
            grid.grid_columnconfigure(i, weight=1, uniform="metric")
            self.metric_card(grid, 0, i, title, value, color)
        self.panel(self.body, 2, 0, 1, "Lectura del periodo", "La proyección no crea ni modifica registros. Sirve para anticipar el resultado usando la información ya guardada.")

    def metric_card(self, parent, row, col, title, value, color):
        f = ctk.CTkFrame(parent, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=15, height=125)
        f.grid(row=row, column=col, sticky="ew", padx=5, pady=5)
        f.grid_propagate(False)
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(inner, text=title.upper(), text_color=MUTED, font=("Segoe UI", 9, "bold")).pack(pady=(0, 6))
        ctk.CTkLabel(inner, text=value, text_color=color, font=("Segoe UI", 23, "bold")).pack()

    def show_simulator(self):
        self.section_title("Simulador", "Prueba una nueva obligación sin guardarla en tus registros.")
        data = db.get_month_data(self.current_month)
        self.panel(self.body, 1, 0, 1, "Resultado actual", f"Ingresos: {money(data['income'])}\nObligaciones: {money(data['obligations'])}\nResultado: {money(data['result'])}")
        box = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=15, height=96)
        box.grid(row=2, column=0, sticky="ew", pady=6)
        box.pack_propagate(False)
        amount = ctk.CTkEntry(box, placeholder_text="Valor hipotético", width=320, height=40)
        amount.pack(side="left", padx=18)
        result = ctk.CTkLabel(box, text="Resultado simulado: —", font=("Segoe UI", 15, "bold"), text_color=TEXT)
        result.pack(side="left", padx=10)

        def calc():
            try:
                val = float(amount.get().replace(".", "").replace(",", "."))
                result.configure(text="Resultado simulado: " + money(projection(self.current_month, data, val)))
            except Exception:
                messagebox.showerror("Dato inválido", "Escribe un valor numérico.")

        ctk.CTkButton(box, text="Calcular", width=110, height=38, fg_color=RED, command=calc).pack(side="left", padx=10)

    def show_goals(self):
        self.section_title("Objetivos de ahorro", "Crea metas y registra aportes sin alterar el resultado de ingresos menos obligaciones.")
        ctk.CTkButton(self.body, text="＋  Crear objetivo", height=40, fg_color=RED, command=self.add_goal_dialog).grid(row=1, column=0, sticky="w", pady=5)
        goals = db.list_goals()
        for i, g in enumerate(goals, start=2):
            f = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=13, height=85)
            f.grid(row=i, column=0, sticky="ew", pady=4)
            f.grid_propagate(False)
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure((0, 1), weight=1)
            ctk.CTkLabel(f, text=g["name"], font=("Segoe UI", 12, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="sw", padx=18, pady=(0, 0))
            ctk.CTkLabel(f, text=f"{money(g['saved'])} de {money(g['target'])}", text_color=MUTED, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="nw", padx=18)
            bar = ctk.CTkProgressBar(f, width=220)
            bar.set(min(g["saved"] / g["target"], 1))
            bar.grid(row=0, column=1, rowspan=2, padx=12)
            ctk.CTkButton(f, text="＋ Aportar", width=100, height=32, fg_color=RED, command=lambda gid=g["id"]: self.contribute_dialog(gid)).grid(row=0, column=2, rowspan=2, padx=15)
        if not goals:
            empty = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER_SOFT, corner_radius=14, height=110)
            empty.grid(row=2, column=0, sticky="ew", pady=8)
            empty.grid_propagate(False)
            ctk.CTkLabel(empty, text="Todavía no tienes objetivos de ahorro.", text_color=MUTED, font=("Segoe UI", 12)).place(relx=0.5, rely=0.5, anchor="center")

    def add_goal_dialog(self):
        win = ctk.CTkToplevel(self)
        win.geometry("400x280")
        win.title("Nuevo objetivo")
        win.configure(fg_color=BG)
        win.grab_set()
        name = ctk.CTkEntry(win, placeholder_text="Nombre del objetivo", width=300, height=40)
        name.pack(pady=(35, 12))
        target = ctk.CTkEntry(win, placeholder_text="Meta en pesos", width=300, height=40)
        target.pack(pady=12)

        def save():
            try:
                v = float(target.get().replace(".", "").replace(",", "."))
                if not name.get().strip() or v <= 0:
                    raise ValueError()
                db.add_goal(name.get().strip(), v)
                win.destroy()
                self.render_page()
            except Exception:
                messagebox.showerror("Error", "Completa nombre y meta válida.")

        ctk.CTkButton(win, text="Crear", fg_color=RED, command=save).pack(pady=15)

    def contribute_dialog(self, gid):
        win = ctk.CTkToplevel(self)
        win.geometry("360x210")
        win.title("Aportar ahorro")
        win.configure(fg_color=BG)
        win.grab_set()
        e = ctk.CTkEntry(win, placeholder_text="Valor del aporte", width=280, height=40)
        e.pack(pady=30)

        def save():
            try:
                v = float(e.get().replace(".", "").replace(",", "."))
                if v <= 0:
                    raise ValueError()
                db.add_goal_contribution(gid, v)
                win.destroy()
                self.render_page()
            except Exception:
                messagebox.showerror("Error", "Escribe un valor mayor que cero.")

        ctk.CTkButton(win, text="Guardar aporte", fg_color=RED, command=save).pack()

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
        self.section_title("Configuración", "Herramientas locales de mantenimiento. Tus datos siguen guardados en la base local del proyecto.")
        card = ctk.CTkFrame(self.body, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=16, height=220)
        card.grid(row=1, column=0, sticky="ew", pady=6)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text="COPIA DE SEGURIDAD", text_color=TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=22, pady=(20, 6))
        ctk.CTkLabel(card, text="Guarda una copia de tu base SQLite en la ubicación que tú elijas.", text_color=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 12))
        ctk.CTkButton(card, text="▣  Crear copia de seguridad", height=42, width=270, fg_color=RED, hover_color=RED_2, command=self.backup).pack(anchor="w", padx=22, pady=6)
        ctk.CTkLabel(card, text=f"Base de datos local: {db.DB_PATH}", text_color=DIM, font=("Segoe UI", 9), wraplength=900).pack(anchor="w", padx=22, pady=(10, 0))

    def backup(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Base SQLite", "*.db")],
            initialfile="respaldo_telarana.db"
        )
        if path:
            try:
                db.backup_database(path)
                messagebox.showinfo("Copia creada", "La copia de seguridad se creó correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

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
        if label is not None and self.ring_frames:
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
