"""Профиль горизонта из окна: что видно с фасада отеля на заданном этаже.

Метод описан в wiki/window-view-method.md. Кратко: из точки глаза пускаем лучи
через 1° по азимуту, вдоль луча берём высоту препятствия (рельеф DEM + здания OSM),
считаем угол возвышения с поправкой на кривизну Земли и рефракцию, запоминаем максимум.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import rasterio
from rasterio import features
from rasterio.merge import merge
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping

R_EARTH = 6_371_000.0
K_REFR = 0.13            # стандартный коэффициент атмосферной рефракции
FLOOR_H = 3.1            # м на этаж
EYE_ABOVE_FLOOR = 1.5    # глаза над полом
LOCAL_RADIUS = 700       # м: в этом радиусе учитываем здания
CELL = 2.0               # м: шаг растра зданий
MAX_DIST = 45_000        # м: дальность лучей (горы)
SEA_LEVEL_MAX = 0.5      # м: высота DEM, ниже которой считаем точку морем

DEFAULT_H = {            # оценка высоты здания без тегов (м)
    "house": 6, "detached": 6, "garage": 3, "garages": 3, "shed": 3, "hut": 3, "roof": 4,
    "apartments": 18, "residential": 12, "hotel": 18, "commercial": 10, "retail": 6,
    "industrial": 8, "church": 12, "school": 10, "yes": 7,
}


# ---------- геометрия ----------

class LocalFrame:
    """Плоская система координат в метрах вокруг точки (equirectangular, ок для ±50 км)."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.kx = math.cos(math.radians(lat0)) * math.pi * R_EARTH / 180
        self.ky = math.pi * R_EARTH / 180

    def to_xy(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * self.ky

    def to_latlon(self, x, y):
        return self.lat0 + np.asarray(y) / self.ky, self.lon0 + np.asarray(x) / self.kx


@dataclass
class Dem:
    arr: np.ndarray
    transform: object

    @classmethod
    def load(cls, paths: list[str], bounds: tuple[float, float, float, float]) -> "Dem":
        srcs = [rasterio.open(p) for p in paths]
        arr, tr = merge(srcs, bounds=bounds)
        for s in srcs:
            s.close()
        return cls(arr[0].astype(np.float32), tr)

    def sample(self, lat, lon):
        """Билинейная интерполяция высоты (м) в точках lat/lon."""
        inv = ~self.transform
        col, row = inv * (np.asarray(lon), np.asarray(lat))
        col, row = col - 0.5, row - 0.5
        c0, r0 = np.floor(col).astype(int), np.floor(row).astype(int)
        fc, fr = col - c0, row - r0
        h, w = self.arr.shape
        c0, r0 = np.clip(c0, 0, w - 2), np.clip(r0, 0, h - 2)
        a = self.arr
        return ((a[r0, c0] * (1 - fc) + a[r0, c0 + 1] * fc) * (1 - fr)
                + (a[r0 + 1, c0] * (1 - fc) + a[r0 + 1, c0 + 1] * fc) * fr)

    def ground(self, frame: "LocalFrame", x: float, y: float, radius: float = 60.0) -> float:
        """Оценка земли под зданием/деревьями: Copernicus — модель поверхности (DSM),
        в ней уже есть крыши и кроны. Берём низкий процентиль высот вокруг точки."""
        g = np.linspace(-radius, radius, 9)
        xx, yy = np.meshgrid(x + g, y + g)
        lat, lon = frame.to_latlon(xx.ravel(), yy.ravel())
        h = self.sample(lat, lon)
        land = h[h > SEA_LEVEL_MAX]          # у берега в круг попадает море — его не считаем землёй
        if land.size < 5:
            return float(max(np.median(h), 1.0))
        return float(np.percentile(land, 10))


@dataclass
class Building:
    osm_id: int
    poly_xy: Polygon
    height: float
    height_src: str       # height | levels | default
    ground: float = 0.0


def building_height(tags: dict) -> tuple[float, str]:
    def num(v):
        try:
            return float(str(v).replace(",", ".").split()[0].rstrip("m"))
        except (ValueError, IndexError):
            return None
    if (h := num(tags.get("height"))) is not None:
        return h, "height"
    if (lv := num(tags.get("building:levels"))) is not None:
        return lv * 3.0 + 1.0, "levels"
    return float(DEFAULT_H.get(tags.get("building", "yes"), 7)), "default"


@dataclass
class LocalBuildings:
    """Растр высот крыш (абсолютная высота над морем) вокруг точки."""
    top: np.ndarray       # м над морем; nan — нет здания
    bid: np.ndarray       # индекс здания в списке
    src: list[Building]
    x0: float
    y0: float

    def sample(self, x, y):
        c = ((np.asarray(x) - self.x0) / CELL).astype(int)
        r = ((self.y0 - np.asarray(y)) / CELL).astype(int)
        ok = (c >= 0) & (r >= 0) & (c < self.top.shape[1]) & (r < self.top.shape[0])
        top = np.full(np.shape(x), np.nan, dtype=np.float32)
        bid = np.full(np.shape(x), -1, dtype=np.int32)
        top[ok] = self.top[r[ok], c[ok]]
        bid[ok] = self.bid[r[ok], c[ok]]
        return top, bid


def build_local(buildings: list[Building], exclude_id: int | None) -> LocalBuildings:
    n = int(2 * LOCAL_RADIUS / CELL)
    x0, y0 = -LOCAL_RADIUS, LOCAL_RADIUS
    tr = from_origin(x0, y0, CELL, CELL)
    use = [b for b in buildings if b.osm_id != exclude_id]
    shapes_top = [(mapping(b.poly_xy), b.ground + b.height) for b in use]
    shapes_id = [(mapping(b.poly_xy), i) for i, b in enumerate(use)]
    top = features.rasterize(shapes_top, out_shape=(n, n), transform=tr, fill=np.nan,
                             dtype="float32", merge_alg=features.MergeAlg.replace)
    bid = features.rasterize(shapes_id, out_shape=(n, n), transform=tr, fill=-1, dtype="int32")
    return LocalBuildings(top, bid, use, x0, y0)


# ---------- лучи ----------

def ray_distances() -> np.ndarray:
    near = np.arange(3.0, LOCAL_RADIUS, 1.5)                       # плотно — здания
    far = np.geomspace(LOCAL_RADIUS, MAX_DIST, 500)                # рельеф и море
    return np.concatenate([near, far])


@dataclass
class RayResult:
    az: int
    angle: float          # угол горизонта, градусы
    kind: str             # building | terrain | sea
    dist: float           # м до препятствия, задающего горизонт
    building: int | None  # osm id
    sea_visible: bool     # видна ли поверхность моря на этом луче
    sea_from: float | None  # ближайшая дистанция видимого моря


NEAR_BLEND = 150.0   # м: ближе этого DSM не используем (там крыши — их даёт OSM), тянем землю линейно


def cast(frame: LocalFrame, dem: Dem, local: LocalBuildings, ex: float, ey: float,
         eye_h: float, azimuths, eye_ground: float) -> list[RayResult]:
    d = ray_distances()
    out = []
    for az in azimuths:
        a = math.radians(az)
        xs, ys = ex + d * math.sin(a), ey + d * math.cos(a)
        lat, lon = frame.to_latlon(xs, ys)
        ground = dem.sample(lat, lon)
        far_g = float(dem.sample(*frame.to_latlon(ex + NEAR_BLEND * math.sin(a), ey + NEAR_BLEND * math.cos(a))))
        near = d < NEAR_BLEND
        ground = np.where(near, eye_ground + (far_g - eye_ground) * d / NEAR_BLEND, ground)
        ground = np.where(near & (ground < SEA_LEVEL_MAX + 0.01) & (far_g > SEA_LEVEL_MAX), SEA_LEVEL_MAX + 0.01, ground)
        btop, bid = local.sample(xs, ys)
        is_bld = ~np.isnan(btop) & (btop > ground)
        h = np.where(is_bld, btop, ground)
        drop = d * d / (2 * R_EARTH) * (1 - K_REFR)
        ang = np.degrees(np.arctan2(h - drop - eye_h, d))
        run_max = np.maximum.accumulate(np.concatenate([[-90.0], ang[:-1]]))
        sea = (ground <= SEA_LEVEL_MAX) & ~is_bld
        sea_vis = sea & (ang >= run_max)
        i = int(np.argmax(ang))
        kind = "building" if is_bld[i] else ("sea" if sea[i] else "terrain")
        osm = local.src[bid[i]].osm_id if is_bld[i] and bid[i] >= 0 else None
        out.append(RayResult(int(az), float(ang[i]), kind, float(d[i]), osm,
                             bool(sea_vis.any()),
                             float(d[np.argmax(sea_vis)]) if sea_vis.any() else None))
    return out


# ---------- фасады ----------

@dataclass
class Facade:
    normal_az: float     # куда смотрят окна, градусы от севера
    x: float             # точка глаза (середина ребра, 1 м наружу)
    y: float
    length: float


def facades(poly_xy: Polygon, min_len: float = 1.5) -> list[Facade]:
    p = poly_xy.exterior
    if not p.is_ccw:
        p = type(p)(list(p.coords)[::-1])
    cs = list(p.coords)
    out = []
    for (x1, y1), (x2, y2) in zip(cs[:-1], cs[1:]):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < min_len:
            continue
        nx, ny = (y2 - y1) / L, -(x2 - x1) / L        # наружная нормаль для CCW
        az = (math.degrees(math.atan2(nx, ny)) + 360) % 360
        out.append(Facade(az, (x1 + x2) / 2 + nx, (y1 + y2) / 2 + ny, L))
    return out


def group_facades(fs: list[Facade], min_side: float = 8.0) -> dict[str, Facade]:
    """Объединяем рёбра в 4 стороны (С/В/Ю/З). Скруглённый фасад в OSM — это много
    коротких рёбер, поэтому длину стороны суммируем, а точку глаза берём у самого
    длинного ребра. Сторона короче min_side — не фасад (угол, выступ)."""
    names = {0: "N", 90: "E", 180: "S", 270: "W"}
    best: dict[str, Facade] = {}
    total: dict[str, float] = {}
    for f in fs:
        k = names[int(((f.normal_az + 45) % 360) // 90) * 90]
        total[k] = total.get(k, 0.0) + f.length
        if k not in best or f.length > best[k].length:
            best[k] = f
    return {k: Facade(f.normal_az, f.x, f.y, total[k]) for k, f in best.items() if total[k] >= min_side}
