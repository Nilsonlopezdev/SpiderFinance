"""Recursos visuales de TELARAÑA dibujados con PIL (sin depender de fuentes).

* ``render_icon``  -> íconos vectoriales suavizados (supersampling).
* ``render_ring``  -> anillo de estado con la imagen recortada en círculo,
                      todo compuesto en UNA sola imagen (sin canvas encima).
"""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

SS = 4  # factor de supersampling de los íconos


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def _hex(color, alpha=255):
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def _spline(points, steps=10):
    """Spline Catmull-Rom cerrada: suaviza polígonos hechos a mano."""
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = points[(i - 1) % n], points[i], points[(i + 1) % n], points[(i + 2) % n]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    return out


class _Pen:
    """Dibuja en un lienzo de 100x100 unidades lógicas."""

    def __init__(self, size, color):
        self.n = size * SS
        self.k = self.n / 100.0
        self.im = Image.new("RGBA", (self.n, self.n), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.c = _hex(color)
        self.clear = (0, 0, 0, 0)

    def px(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def box(self, b):
        return [v * self.k for v in b]

    def line(self, pts, w=7):
        p = self.px(pts)
        wk = w * self.k
        self.d.line(p, fill=self.c, width=int(wk), joint="curve")
        r = wk / 2
        for x, y in (p[0], p[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=self.c)

    def poly(self, pts, fill=True):
        self.d.polygon(self.px(pts), fill=self.c if fill else self.clear)

    def ellipse(self, b, fill=True, w=0):
        if w:
            self.d.ellipse(self.box(b), outline=self.c, width=int(w * self.k))
        else:
            self.d.ellipse(self.box(b), fill=self.c if fill else self.clear)

    def rrect(self, b, r=4, fill=True, w=0):
        if w:
            self.d.rounded_rectangle(self.box(b), radius=r * self.k, outline=self.c, width=int(w * self.k))
        else:
            self.d.rounded_rectangle(self.box(b), radius=r * self.k, fill=self.c if fill else self.clear)

    def arc(self, b, a0, a1, w=7):
        self.d.arc(self.box(b), a0, a1, fill=self.c, width=int(w * self.k))

    def done(self, size):
        return self.im.resize((size, size), Image.Resampling.LANCZOS)


# ----------------------------------------------------------------------------
# íconos (cuadrícula de 100x100)
# ----------------------------------------------------------------------------
def _ic_home(p):
    p.poly([(50, 8), (6, 48), (18, 48), (18, 90), (40, 90), (40, 62), (60, 62), (60, 90), (82, 90), (82, 48), (94, 48)])


def _ic_chart(p):
    p.rrect((12, 50, 34, 90), 4)
    p.rrect((39, 28, 61, 90), 4)
    p.rrect((66, 10, 88, 90), 4)


def _ic_card(p):
    p.rrect((10, 14, 90, 86), 9, w=7)
    p.rrect((10, 14, 90, 38), 9)
    p.line([(26, 56), (74, 56)], 7)
    p.line([(26, 70), (58, 70)], 7)


def _ic_clock(p):
    p.ellipse((8, 8, 92, 92), w=8)
    p.line([(50, 50), (50, 26)], 8)
    p.line([(50, 50), (68, 62)], 8)


def _ic_flame(p):
    p.poly(_spline([(50, 2), (60, 24), (76, 40), (86, 62), (78, 84), (58, 96), (38, 96), (20, 84), (14, 62), (22, 44), (34, 34), (38, 50), (44, 28)], 10))
    p.poly(_spline([(50, 54), (62, 70), (60, 82), (50, 90), (40, 82), (38, 70)], 10), fill=False)


def _ic_trend(p):
    p.rrect((10, 72, 24, 92), 3)
    p.rrect((32, 62, 46, 92), 3)
    p.rrect((54, 50, 68, 92), 3)
    p.rrect((76, 38, 90, 92), 3)
    p.line([(10, 46), (34, 30), (52, 38), (86, 10)], 7)
    p.line([(70, 10), (86, 10), (86, 26)], 7)


def _ic_calc(p):
    p.rrect((16, 6, 84, 94), 10, w=7)
    p.rrect((28, 18, 72, 34), 3)
    for y in (46, 61, 76):
        for x in (29, 45, 61):
            p.rrect((x, y, x + 11, y + 10), 3)


def _ic_target(p):
    p.ellipse((6, 6, 94, 94), w=8)
    p.ellipse((26, 26, 74, 74), w=8)
    p.ellipse((42, 42, 58, 58))


def _ic_gamepad(p):
    p.rrect((4, 28, 96, 78), 24)
    p.rrect((20, 49, 42, 58), 2, fill=False)
    p.rrect((26, 43, 36, 64), 2, fill=False)
    p.ellipse((62, 46, 72, 56), fill=False)
    p.ellipse((74, 56, 84, 66), fill=False)
    p.rrect((18, 16, 38, 30), 5)
    p.rrect((62, 16, 82, 30), 5)


def _ic_gear(p):
    pts = []
    for i in range(8):
        a = math.radians(i * 45)
        for off, r in ((-14, 33), (-9, 46), (9, 46), (14, 33)):
            t = a + math.radians(off)
            pts.append((50 + r * math.cos(t), 50 + r * math.sin(t)))
    p.poly(pts)
    p.ellipse((18, 18, 82, 82))
    p.ellipse((36, 36, 64, 64), fill=False)


def _ic_coins(p):
    p.line([(16, 20), (16, 78)], 7)
    p.line([(84, 20), (84, 78)], 7)
    for y in (34, 56, 78):
        p.arc((16, y - 12, 84, y + 12), 0, 180, 7)
    p.ellipse((14, 8, 86, 36))


def _ic_wallet(p):
    p.rrect((8, 26, 92, 88), 10, w=7)
    p.line([(18, 26), (62, 12), (72, 26)], 7)
    p.rrect((58, 46, 92, 68), 6)
    p.ellipse((69, 53, 81, 65), fill=False)


def _ic_info(p):
    p.ellipse((4, 4, 96, 96))
    p.ellipse((43, 20, 57, 34), fill=False)
    p.rrect((43, 41, 57, 78), 4, fill=False)


def _ic_bell(p):
    p.ellipse((24, 8, 76, 60))
    p.poly([(24, 34), (76, 34), (78, 58), (90, 76), (90, 82), (10, 82), (10, 76), (22, 58)])
    p.ellipse((38, 80, 62, 96))
    p.rrect((44, 2, 56, 12), 4)


def _ic_bolt(p):
    p.poly([(60, 4), (20, 56), (46, 56), (38, 96), (80, 40), (54, 40)])


def _ic_chev_r(p):
    p.line([(34, 14), (70, 50), (34, 86)], 10)


def _ic_chev_l(p):
    p.line([(66, 14), (30, 50), (66, 86)], 10)


def _ic_dchev_l(p):
    p.line([(50, 18), (22, 50), (50, 82)], 9)
    p.line([(82, 18), (54, 50), (82, 82)], 9)


def _ic_dchev_r(p):
    p.line([(18, 18), (46, 50), (18, 82)], 9)
    p.line([(50, 18), (78, 50), (50, 82)], 9)


def _ic_calendar(p):
    p.rrect((8, 16, 92, 92), 12, w=7)
    p.line([(10, 40), (90, 40)], 7)
    p.line([(30, 6), (30, 26)], 8)
    p.line([(70, 6), (70, 26)], 8)
    for y in (52, 68):
        for x in (22, 43, 64):
            p.rrect((x, y, x + 14, y + 10), 3)


def _ic_user(p):
    p.ellipse((30, 8, 70, 48))
    p.ellipse((12, 56, 88, 132))


def _ic_chart_up(p):
    for i, top in enumerate((74, 60, 46, 32)):
        x = 8 + i * 22
        p.rrect((x, top, x + 15, 94), 3, w=5)
    p.line([(8, 52), (30, 36), (50, 42), (88, 10)], 5)
    p.line([(72, 10), (88, 10), (88, 26)], 5)


def _ic_web(p):
    cx = cy = 50
    for i in range(8):
        a = math.radians(i * 45 + 22.5)
        p.line([(cx, cy), (cx + 46 * math.cos(a), cy + 46 * math.sin(a))], 3.2)
    for r in (13, 25, 37, 47):
        pts = []
        for i in range(8):
            a = math.radians(i * 45 + 22.5)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        # hilos ligeramente curvados hacia el centro (aspecto de telaraña)
        for i in range(8):
            a0, a1 = pts[i], pts[(i + 1) % 8]
            mx, my = (a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2
            mx += (cx - mx) * 0.14
            my += (cy - my) * 0.14
            p.line([a0, (mx, my), a1], 2.6)
    p.ellipse((43, 43, 57, 57))


ICONS = {
    "home": _ic_home, "chart": _ic_chart, "card": _ic_card, "clock": _ic_clock,
    "flame": _ic_flame, "trend": _ic_trend, "calc": _ic_calc, "target": _ic_target,
    "gamepad": _ic_gamepad, "gear": _ic_gear, "coins": _ic_coins, "wallet": _ic_wallet,
    "info": _ic_info, "bell": _ic_bell, "bolt": _ic_bolt, "chev_r": _ic_chev_r,
    "chev_l": _ic_chev_l, "dchev_l": _ic_dchev_l, "dchev_r": _ic_dchev_r,
    "calendar": _ic_calendar, "user": _ic_user, "chart_up": _ic_chart_up, "web": _ic_web,
}


@lru_cache(maxsize=256)
def render_icon(name, size=24, color="#FFFFFF"):
    """Devuelve un ``PIL.Image`` RGBA del ícono (2x para pantallas HiDPI)."""
    px = size * 2
    pen = _Pen(px, color)
    ICONS[name](pen)
    return pen.done(px)


# ----------------------------------------------------------------------------
# anillo de estado
# ----------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _art(path, diameter):
    img = Image.open(path).convert("RGB")
    img = ImageOps.fit(img, (diameter, diameter), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    return img


def render_ring(art_path, accent, ratio, bg, size=320, glow=1.0):
    """Anillo HUD con la imagen DENTRO del círculo, sobre el color ``bg``.

    Todo (brillo, aro, progreso, imagen) se compone en una sola imagen opaca,
    así no hay esquinas cuadradas ni desajuste de color con el fondo.
    """
    S = 2  # supersampling
    n = size * S
    c = n / 2
    base = Image.new("RGBA", (n, n), _hex(bg))

    # resplandor rojo exterior
    halo = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((c - n * .47, c - n * .47, c + n * .47, c + n * .47), outline=_hex("#FF2D45", int(255 * glow)), width=int(n * .03))
    halo = halo.filter(ImageFilter.GaussianBlur(n * .03))
    base.alpha_composite(halo)
    base.alpha_composite(halo)

    d = ImageDraw.Draw(base)

    def ring(r, width, color):
        d.ellipse((c - r, c - r, c + r, c + r), outline=color, width=int(width))

    ring(n * .470, n * .0045, _hex("#FF3347", int(255 * (.55 + .45 * glow))))   # filo rojo exterior
    ring(n * .445, n * .030, _hex("#202A38"))                                   # pista gris
    ring(n * .445, n * .0045, _hex("#5A6677"))                                  # borde claro de la pista

    # progreso (porcentaje de ingresos comprometidos)
    r = n * .445
    box = (c - r, c - r, c + r, c + r)
    if ratio and ratio > 0:
        d.arc(box, -90, -90 + 359.9 * min(ratio, 1.0), fill=_hex(accent), width=int(n * .026))
    else:
        d.arc(box, -90, -62, fill=_hex("#FF3347", int(255 * (.6 + .4 * glow))), width=int(n * .026))

    # marcas HUD en los cuatro puntos cardinales
    tick = _hex("#8793A5")
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        x0, y0 = c + (n * .415) * math.cos(a), c + (n * .415) * math.sin(a)
        x1, y1 = c + (n * .475) * math.cos(a), c + (n * .475) * math.sin(a)
        d.line((x0, y0, x1, y1), fill=tick, width=int(n * .006))

    # imagen circular
    diameter = int(n * .78)
    art = _art(str(art_path), diameter).convert("RGBA")
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(S * .6))
    off = int((n - diameter) / 2)
    base.paste(art, (off, off), mask)
    ImageDraw.Draw(base).ellipse((off, off, off + diameter - 1, off + diameter - 1), outline=_hex("#0A0F16"), width=int(n * .006))

    return base.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
