# simpleworkernet/utils/coordinates.py
"""
Модуль для точного преобразования географических координат WGS84
в плоские координаты с сохранением расстояний.

Использует проекцию UTM (Universal Transverse Mercator) через библиотеку pyproj,
которая автоматически выбирает зону по долготе точки. Это даёт точные расстояния.

Если pyproj не установлен, используется Web Mercator (EPSG:3857),
но расстояния в этом случае искажены, особенно на средних широтах.
Для Web Mercator можно включить автоматическую коррекцию масштаба.

Координаты возвращаются в метрах.

Поддерживаются различные форматы входных данных:
- GeoPoint (с атрибутами lat, lon)
- Словарь с ключами 'lat', 'lon' (или 'latitude', 'longitude')
- Кортеж/список (lat, lon) или (lat, lon, z)
- Строка "lat, lon" или "lat lon"
- Список/кортеж таких объектов

Если center не указан, координаты возвращаются абсолютными в проекции (без центрирования).
Для центрирования передайте параметр center.
"""

import math
from typing import List, Tuple, Union, Optional, Any, Literal, Sequence

# Попытка импортировать pyproj для точных преобразоваций
try:
    import pyproj
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

# Радиус Земли для Web Mercator (EPSG:3857)
MERCATOR_RADIUS = 6378137.0


# ============================================================================
# Парсер координат (2D и 3D)
# ============================================================================

def _parse_coordinates(
    points: Any,
    allow_single: bool = True
) -> Tuple[List[Tuple[float, float, Optional[float]]], bool]:
    """
    Универсальный парсер координат. Преобразует входные данные в список кортежей (lat, lon, z).
    z по умолчанию None, если не указана.

    Поддерживаемые форматы:
    - GeoPoint (с атрибутами lat, lon)
    - Словарь с ключами 'lat', 'lon' (и опционально 'z' или 'altitude')
    - Кортеж/список (lat, lon) или (lat, lon, z)
    - Строка "lat, lon" или "lat lon"
    - Список/кортеж любых из вышеперечисленных

    Args:
        points: Входные данные.
        allow_single: Если True, то одиночный объект может быть передан без обёртки.

    Returns:
        Кортеж (список_координат, был_ли_одиночным_вход).
        Если был передан один объект, was_single=True.
    """
    # Если points — это строка, пытаемся распарсить
    if isinstance(points, str):
        s = points.strip()
        # Пробуем разделить по запятой, затем по пробелу, затем по точке с запятой
        for sep in [',', ';', ' ']:
            parts = s.split(sep)
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    return [(lat, lon, None)], True
                except ValueError:
                    continue
            elif len(parts) == 3:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    z = float(parts[2].strip())
                    return [(lat, lon, z)], True
                except ValueError:
                    continue
        raise ValueError(f"Не удалось распарсить строку координат: {points}")

    # Если points — не список/кортеж, и allow_single=True, считаем это одной точкой
    if not isinstance(points, (list, tuple)) and allow_single:
        return _parse_single_point(points), True

    # Иначе это список/кортеж
    parsed = []
    for p in points:
        if isinstance(p, str):
            s = p.strip()
            for sep in [',', ';', ' ']:
                parts = s.split(sep)
                if len(parts) == 2:
                    try:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        parsed.append((lat, lon, None))
                        break
                    except ValueError:
                        continue
                elif len(parts) == 3:
                    try:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        z = float(parts[2].strip())
                        parsed.append((lat, lon, z))
                        break
                    except ValueError:
                        continue
            else:
                raise ValueError(f"Не удалось распарсить строку координат: {p}")
        else:
            parsed.extend(_parse_single_point(p))

    return parsed, False


def _parse_single_point(p: Any) -> List[Tuple[float, float, Optional[float]]]:
    """Парсит один объект как точку (lat, lon, z)."""
    # GeoPoint или подобный объект с атрибутами lat, lon
    if hasattr(p, 'lat') and hasattr(p, 'lon'):
        z = None
        if hasattr(p, 'z') and p.z is not None:
            z = float(p.z)
        elif hasattr(p, 'altitude') and p.altitude is not None:
            z = float(p.altitude)
        return [(float(p.lat), float(p.lon), z)]

    # Словарь
    if isinstance(p, dict):
        lat = None
        lon = None
        z = None
        for key in ['lat', 'latitude', 'y']:
            if key in p:
                lat = float(p[key])
                break
        for key in ['lon', 'longitude', 'x']:
            if key in p:
                lon = float(p[key])
                break
        for key in ['z', 'altitude', 'elevation']:
            if key in p:
                z = float(p[key])
                break
        if lat is not None and lon is not None:
            return [(lat, lon, z)]
        raise ValueError(f"Словарь не содержит ключи для координат: {p}")

    # Кортеж или список из двух или трёх чисел
    if isinstance(p, (list, tuple)):
        if len(p) == 2:
            try:
                return [(float(p[0]), float(p[1]), None)]
            except ValueError:
                raise ValueError(f"Не удалось преобразовать в числа: {p}")
        elif len(p) == 3:
            try:
                return [(float(p[0]), float(p[1]), float(p[2]))]
            except ValueError:
                raise ValueError(f"Не удалось преобразовать в числа: {p}")

    raise ValueError(f"Неизвестный формат координат: {p}")


# ============================================================================
# Вспомогательные функции для UTM
# ============================================================================

def utm_zone(lon: float) -> int:
    """Определяет номер зоны UTM по долготе."""
    return int((lon + 180) / 6) + 1


def get_utm_transformer(lat: float, lon: float) -> 'pyproj.Transformer':
    """Создаёт трансформер WGS84 -> UTM для указанной точки."""
    zone = utm_zone(lon)
    hemisphere = 'north' if lat >= 0 else 'south'
    proj_str = f"+proj=utm +zone={zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    return pyproj.Transformer.from_crs("EPSG:4326", proj_str, always_xy=True)


# ============================================================================
# Преобразование WGS84 -> плоские координаты (2D и 3D)
# ============================================================================

def lat_lon_to_xy(
    lat: float,
    lon: float,
    projection: str = 'utm',
    center: Optional[Tuple[float, float]] = None,
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0)
) -> Tuple[float, float]:
    """
    Преобразует одну географическую точку в плоские координаты (x, y) в метрах.
    (2D версия, z игнорируется)
    """
    if projection == 'utm':
        if not HAS_PYPROJ:
            raise ImportError(
                "Для проекции UTM требуется библиотека pyproj. "
                "Установите: pip install pyproj"
            )
        transformer = get_utm_transformer(lat, lon)
        x, y = transformer.transform(lon, lat)
    else:  # mercator
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        x = MERCATOR_RADIUS * lon_rad
        y = MERCATOR_RADIUS * math.log(math.tan(math.pi / 4 + lat_rad / 2))

    x = x * scale + offset[0]
    y = y * scale + offset[1]

    if center is not None:
        cx, cy = lat_lon_to_xy(center[0], center[1], projection=projection,
                               scale=scale, offset=offset)
        x -= cx
        y -= cy

    return x, y


def geo_to_xy(
    points: Any,
    center: Optional[Any] = None,
    scale: float = 1.0,
    absolute: bool = False,
    offset: Tuple[float, float] = (0.0, 0.0),
    projection: str = 'utm',
    auto_scale_mercator: bool = True
) -> Union[List[float], List[List[float]]]:
    """
    Преобразует географические координаты в плоские 2D координаты (x, y).

    Если center не указан, координаты возвращаются абсолютными в проекции.
    Если center указан, то при absolute=False выполняется центрирование.

    Args:
        points: Одна точка или список точек (любого формата).
        center: Центральная точка для центрирования (любой формат).
                Если None, центрирование не применяется.
        scale: Масштаб.
        absolute: Если True, возвращает абсолютные координаты (без центрирования).
                  Применяется только если center задан.
        offset: Смещение (x_offset, y_offset).
        projection: 'utm' или 'mercator'.
        auto_scale_mercator: Автокоррекция масштаба для Меркатора.

    Returns:
        Координаты в метрах. Если передан один объект — список [x, y],
        если список — список списков [[x1, y1], ...].
    """
    if projection == 'utm' and not HAS_PYPROJ:
        raise ImportError(
            "Для проекции UTM требуется библиотека pyproj. "
            "Установите: pip install pyproj"
        )

    # Парсим точки (z игнорируем)
    coords, was_single = _parse_coordinates(points, allow_single=True)
    if not coords:
        return []

    # Если center не задан, всегда возвращаем абсолютные координаты
    if center is None:
        result = []
        for lat, lon, _ in coords:
            x, y = lat_lon_to_xy(lat, lon, projection=projection,
                                 scale=scale, offset=offset)
            result.append([x, y])
        if was_single:
            return result[0]
        return result

    # center задан: парсим его
    center_coords, _ = _parse_coordinates(center, allow_single=True)
    if not center_coords:
        raise ValueError("Не удалось распарсить центр")
    lat_center, lon_center, _ = center_coords[0]

    if absolute:
        result = []
        for lat, lon, _ in coords:
            x, y = lat_lon_to_xy(lat, lon, projection=projection,
                                 scale=scale, offset=offset)
            result.append([x, y])
        if was_single:
            return result[0]
        return result

    # Центрирование
    effective_scale = scale
    if projection == 'mercator' and auto_scale_mercator:
        lat_rad = math.radians(lat_center)
        mercator_scale = 1.0 / math.cos(lat_rad)
        effective_scale = scale * mercator_scale

    cx, cy = lat_lon_to_xy(lat_center, lon_center, projection=projection,
                           scale=effective_scale, offset=offset)

    result = []
    for lat, lon, _ in coords:
        x, y = lat_lon_to_xy(lat, lon, projection=projection,
                             scale=effective_scale, offset=offset)
        dx = x - cx
        dy = y - cy
        result.append([dx, dy])

    if was_single:
        return result[0]
    return result


def geo_to_xyz(
    points: Any,
    center: Optional[Any] = None,
    scale: float = 1.0,
    absolute: bool = False,
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    projection: str = 'utm',
    auto_scale_mercator: bool = True,
    default_z: float = 0.0
) -> Union[List[float], List[List[float]]]:
    """
    Преобразует географические координаты в плоские 3D координаты (x, y, z).

    Если center не указан, координаты возвращаются абсолютными в проекции.
    Если center указан, то при absolute=False выполняется центрирование.

    z-координата:
    - Если во входных данных есть z (третья координата), она используется.
    - Иначе используется default_z (по умолчанию 0.0).

    Args:
        points: Одна точка или список точек (любого формата, включая 3D).
        center: Центральная точка для центрирования (любой формат, может быть 3D).
                Если None, центрирование не применяется.
        scale: Масштаб (применяется ко всем координатам).
        absolute: Если True, возвращает абсолютные координаты (без центрирования).
                  Применяется только если center задан.
        offset: Смещение (x_offset, y_offset, z_offset).
        projection: 'utm' или 'mercator'.
        auto_scale_mercator: Автокоррекция масштаба для Меркатора.
        default_z: Значение z по умолчанию, если z не указана во входных данных.

    Returns:
        Координаты в метрах. Если передан один объект — список [x, y, z],
        если список — список списков [[x1, y1, z1], ...].
    """
    if projection == 'utm' and not HAS_PYPROJ:
        raise ImportError(
            "Для проекции UTM требуется библиотека pyproj. "
            "Установите: pip install pyproj"
        )

    # Парсим точки (с z)
    coords, was_single = _parse_coordinates(points, allow_single=True)
    if not coords:
        return []

    # Если center не задан, всегда возвращаем абсолютные координаты
    if center is None:
        result = []
        for lat, lon, z in coords:
            x, y = lat_lon_to_xy(lat, lon, projection=projection,
                                 scale=scale, offset=(offset[0], offset[1]))
            z_out = (z if z is not None else default_z) * scale + offset[2]
            result.append([x, y, z_out])
        if was_single:
            return result[0]
        return result

    # center задан: парсим его (с z)
    center_coords, _ = _parse_coordinates(center, allow_single=True)
    if not center_coords:
        raise ValueError("Не удалось распарсить центр")
    lat_center, lon_center, z_center = center_coords[0]

    if absolute:
        result = []
        for lat, lon, z in coords:
            x, y = lat_lon_to_xy(lat, lon, projection=projection,
                                 scale=scale, offset=(offset[0], offset[1]))
            z_out = (z if z is not None else default_z) * scale + offset[2]
            result.append([x, y, z_out])
        if was_single:
            return result[0]
        return result

    # Центрирование
    effective_scale = scale
    if projection == 'mercator' and auto_scale_mercator:
        lat_rad = math.radians(lat_center)
        mercator_scale = 1.0 / math.cos(lat_rad)
        effective_scale = scale * mercator_scale

    cx, cy = lat_lon_to_xy(lat_center, lon_center, projection=projection,
                           scale=effective_scale, offset=(offset[0], offset[1]))
    cz = (z_center if z_center is not None else default_z) * effective_scale + offset[2]

    result = []
    for lat, lon, z in coords:
        x, y = lat_lon_to_xy(lat, lon, projection=projection,
                             scale=effective_scale, offset=(offset[0], offset[1]))
        z_out = (z if z is not None else default_z) * effective_scale + offset[2]
        dx = x - cx
        dy = y - cy
        dz = z_out - cz
        result.append([dx, dy, dz])

    if was_single:
        return result[0]
    return result


def xy_to_geo(
    xy: Any,
    center: Any,
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0),
    projection: str = 'utm'
) -> Union[Tuple[float, float], List[Tuple[float, float]]]:
    """Обратное преобразование: из плоских 2D координат в географические (2D)."""
    if projection == 'utm' and not HAS_PYPROJ:
        raise ImportError(
            "Для проекции UTM требуется библиотека pyproj. "
            "Установите: pip install pyproj"
        )

    center_coords, _ = _parse_coordinates(center, allow_single=True)
    if not center_coords:
        raise ValueError("Не удалось распарсить центр")
    lat_center, lon_center, _ = center_coords[0]

    xy_list, was_single = _parse_coordinates(xy, allow_single=True)
    if not xy_list:
        return []

    flat_xy = []
    for item in xy_list:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                flat_xy.append((float(item[0]), float(item[1])))
            except ValueError:
                raise ValueError(f"Не удалось преобразовать в числа: {item}")
        else:
            raise ValueError(f"Неверный формат плоских координат: {item}")

    cx, cy = lat_lon_to_xy(lat_center, lon_center, projection=projection,
                           scale=scale, offset=offset)

    result = []
    for x, y in flat_xy:
        mx = cx + x
        my = cy + y
        if projection == 'utm':
            transformer = get_utm_transformer(lat_center, lon_center)
            lon, lat = transformer.transform(mx, my, direction='INVERSE')
        else:
            lon = (mx / MERCATOR_RADIUS) * 180.0 / math.pi
            lat = (2.0 * math.atan(math.exp(my / MERCATOR_RADIUS)) - math.pi / 2.0) * 180.0 / math.pi
        result.append((lat, lon))

    if was_single:
        return result[0]
    return result


def xyz_to_geo(
    xyz: Any,
    center: Any,
    scale: float = 1.0,
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    projection: str = 'utm'
) -> Union[Tuple[float, float, float], List[Tuple[float, float, float]]]:
    """
    Обратное преобразование: из плоских 3D координат (x, y, z) в географические (lat, lon, z).
    """
    if projection == 'utm' and not HAS_PYPROJ:
        raise ImportError(
            "Для проекции UTM требуется библиотека pyproj. "
            "Установите: pip install pyproj"
        )

    center_coords, _ = _parse_coordinates(center, allow_single=True)
    if not center_coords:
        raise ValueError("Не удалось распарсить центр")
    lat_center, lon_center, z_center = center_coords[0]

    xyz_list, was_single = _parse_coordinates(xyz, allow_single=True)
    if not xyz_list:
        return []

    flat_xyz = []
    for item in xyz_list:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            try:
                flat_xyz.append((float(item[0]), float(item[1]), float(item[2])))
            except ValueError:
                raise ValueError(f"Не удалось преобразовать в числа: {item}")
        else:
            raise ValueError(f"Неверный формат плоских координат: {item}")

    cx, cy = lat_lon_to_xy(lat_center, lon_center, projection=projection,
                           scale=scale, offset=(offset[0], offset[1]))
    cz = (z_center if z_center is not None else 0.0) * scale + offset[2]

    result = []
    for x, y, z in flat_xyz:
        mx = cx + x
        my = cy + y
        mz = cz + z
        if projection == 'utm':
            transformer = get_utm_transformer(lat_center, lon_center)
            lon, lat = transformer.transform(mx, my, direction='INVERSE')
        else:
            lon = (mx / MERCATOR_RADIUS) * 180.0 / math.pi
            lat = (2.0 * math.atan(math.exp(my / MERCATOR_RADIUS)) - math.pi / 2.0) * 180.0 / math.pi
        # Обратное преобразование z: (mz - offset[2]) / scale
        z_out = (mz - offset[2]) / scale
        result.append((lat, lon, z_out))

    if was_single:
        return result[0]
    return result


def auto_center(points: Any) -> Tuple[float, float]:
    """Вычисляет среднюю географическую точку (lat, lon) для списка координат."""
    coords, _ = _parse_coordinates(points, allow_single=False)
    if not coords:
        return (0.0, 0.0)
    lat_sum = sum(c[0] for c in coords)
    lon_sum = sum(c[1] for c in coords)
    return (lat_sum / len(coords), lon_sum / len(coords))


__all__ = [
    'lat_lon_to_xy',
    'geo_to_xy',
    'geo_to_xyz',
    'xy_to_geo',
    'xyz_to_geo',
    'auto_center',
    'utm_zone',
]