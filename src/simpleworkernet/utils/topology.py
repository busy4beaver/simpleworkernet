# simpleworkernet/utils/topology.py
"""
Модуль для построения графа коммутаций и графа сооружений связи (узлов и кабелей).
Реализован как наследник igraph.Graph.

Вершины графа коммутаций — это интерфейсы (объект + сторона + порт).
Для устройств (OLT, switch, ONU, CWDM) и абонентов (customer) сторона = None.
Для объектов со сторонами (кросс, кабель, сплиттер, CWDM) сторона = 1 или 2.

Граф сооружений связи (FNGraph) — вершины: node_id, рёбра: fiber_id.

Все данные, загруженные по API, сохраняются в глобальный кэш DataCache.
Вершины и рёбра содержат атрибут 'api_obj' с полным объектом (моделью),
что позволяет получить любую информацию без дополнительных запросов.
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from collections import deque, defaultdict
from dataclasses import dataclass
import igraph as ig

from ..core.client import WorkerNetClient
from ..models.categories import Commutation, Device, Cross, Splitter, Fiber, Customer, Node

_logger = None

def _get_logger():
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger


# ===========================================================================
# Глобальный кэш данных
# ===========================================================================

class DataCache:
    """
    Глобальный кэш для объектов API.
    Хранит полные объекты (модели) по ключу (тип, id).
    Также кэширует коммутации для объектов.
    Реализован как синглтон, чтобы все экземпляры графов использовали общий кэш.
    """
    _instance = None
    _objects: Dict[Tuple[str, Union[int, str]], Any] = {}
    _commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        """
        Возвращает объект из кэша по типу и идентификатору.
        Возвращает None, если объект отсутствует.
        """
        return self._objects.get((obj_type, obj_id))

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        """Сохраняет объект в кэш."""
        self._objects[(obj_type, obj_id)] = obj

    def get_or_load_object(self, obj_type: str, obj_id: Union[int, str],
                           loader: Callable[[], Any]) -> Any:
        """
        Получает объект из кэша или загружает через переданную функцию loader.
        Если объект был загружен, сохраняет его в кэш.
        """
        key = (obj_type, obj_id)
        obj = self._objects.get(key)
        if obj is None:
            obj = loader()
            if obj is not None:
                self._objects[key] = obj
        return obj

    def get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> Optional[List[Any]]:
        """Возвращает список коммутаций для объекта из кэша или None."""
        return self._commutations.get((obj_type, obj_id))

    def set_commutations(self, obj_type: str, obj_id: Union[int, str],
                         comms: List[Any]) -> None:
        """Сохраняет коммутации в кэш."""
        self._commutations[(obj_type, obj_id)] = comms

    def get_or_load_commutations(self, obj_type: str, obj_id: Union[int, str],
                                 loader: Callable[[], List[Any]]) -> List[Any]:
        """
        Получает коммутации из кэша или загружает через loader.
        Возвращает список (пустой, если ничего нет).
        """
        key = (obj_type, obj_id)
        comms = self._commutations.get(key)
        if comms is None:
            comms = loader()
            if comms is not None:
                self._commutations[key] = comms
            else:
                comms = []
        return comms


# Глобальный экземпляр кэша (синглтон)
_data_cache = DataCache()


# ===========================================================================
# Константы типов объектов
# ===========================================================================

TYPE_CUSTOMER = 'customer'
TYPE_FIBER = 'fiber'
TYPE_SPLITTER = 'splitter'
TYPE_CROSS = 'cross'
TYPE_CWDM = 'cwdm'
TYPE_SWITCH = 'switch'
TYPE_OLT = 'olt'
TYPE_ONU = 'onu'

DEVICE_TYPES = {TYPE_SWITCH, TYPE_OLT, TYPE_ONU, TYPE_CWDM}
SIDE_TYPES = {TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER, TYPE_CWDM}


# ===========================================================================
# Вспомогательные классы (общие)
# ===========================================================================

@dataclass(frozen=True)
class ObjKey:
    """
    Уникальный ключ объекта сети.
    Используется для идентификации объектов при построении графа.
    """
    obj_type: str
    id: Union[int, str]

    def __str__(self) -> str:
        return f"{self.obj_type}:{self.id}"


@dataclass(frozen=True)
class Interface:
    """
    Вершина графа коммутаций — интерфейс объекта.
    Содержит ссылку на объект (ObjKey), сторону (side) и порт (port).
    Для устройств (OLT, switch, ONU, CWDM) и абонентов сторона не имеет значения,
    но для единообразия мы используем side=1 для устройств.
    """
    obj: ObjKey
    side: int          # clps_first (сторона или порт для устройств)
    port: int          # clps_mid (порт/волокно)

    def __str__(self) -> str:
        return f"{self.obj} side={self.side} port={self.port}"


# ===========================================================================
# Класс графа коммутаций
# ===========================================================================

class CommutationGraph(ig.Graph):
    """
    Граф коммутаций, где вершины — интерфейсы, рёбра — коммутации.
    Содержит только логику построения графа.
    Все данные загружаются через глобальный кэш DataCache.
    """

    def __init__(self, client: WorkerNetClient, cache: Optional[DataCache] = None, **kwargs):
        """
        Инициализация графа коммутаций.

        Args:
            client: экземпляр WorkerNetClient для вызовов API.
            cache: экземпляр DataCache (если не указан, используется глобальный).
            **kwargs: дополнительные параметры для igraph.Graph.
        """
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self._cache = cache if cache is not None else _data_cache

        # Сопоставление Interface -> индекс вершины в графе
        self._vertex_index: Dict[Interface, int] = {}

        # Множество посещённых интерфейсов (для предотвращения циклов)
        self._visited_interfaces: Set[Interface] = set()

        # Максимальная глубина обхода (защита от бесконечных циклов)
        self._max_depth = 100

        # Флаг направления графа (устанавливается после построения)
        self._directed: bool = False

        # Данные по затуханиям (загружаются отдельно через метод load_attenuation_data)
        self._attenuation_data: Dict[str, Any] = {}

    # ------------------------------------------------------------------------
    # Загрузка данных с использованием кэша
    # ------------------------------------------------------------------------

    def _load_object(self, obj_key: ObjKey) -> Optional[Any]:
        """
        Загружает полный объект из API или кэша.
        Возвращает модель (экземпляр соответствующей категории) или None.
        """
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        def loader() -> Optional[Any]:
            """Функция загрузки объекта из API."""
            try:
                if obj_type in DEVICE_TYPES:
                    # Для устройств используем Device.get_data
                    result = self.client.Device.get_data(object_type=obj_type, object_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_CROSS:
                    result = self.client.Cross.get_list(id=str(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_SPLITTER:
                    result = self.client.Splitter.get(id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_FIBER:
                    result = self.client.Fiber.get_list(object_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_CUSTOMER:
                    result = self.client.Customer.get_data(customer_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                else:
                    return None
            except Exception as e:
                self.logger.warning(f"Не удалось загрузить {obj_type}:{obj_id}: {e}")
                return None

        return self._cache.get_or_load_object(obj_type, obj_id, loader)

    def _load_commutations(self, obj_key: ObjKey) -> List[Commutation.Get_data]:
        """
        Загружает коммутации для объекта из API или кэша.
        Возвращает список моделей Commutation.Get_data.
        """
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        # Определяем API-тип для запроса коммутаций
        # Для всех устройств используем 'switch', так как API принимает 'switch' для OLT/ONU/коммутаторов
        if obj_type in DEVICE_TYPES:
            api_type = TYPE_SWITCH
        else:
            api_type = obj_type

        if not api_type:
            return []

        # Определяем ID для запроса (для кроссов это строка, для остальных — число)
        if obj_type == TYPE_CROSS:
            api_id = str(obj_id)
        else:
            api_id = int(obj_id)

        def loader() -> List[Commutation.Get_data]:
            """Функция загрузки коммутаций из API."""
            try:
                result = self.client.Commutation.get_data(object_type=api_type, object_id=api_id)
                return result.to_list() if result else []
            except Exception as e:
                self.logger.error(f"Ошибка загрузки коммутаций для {obj_key}: {e}")
                return []

        return self._cache.get_or_load_commutations(api_type, api_id, loader)

    # ------------------------------------------------------------------------
    # Вспомогательные методы для извлечения информации из объектов
    # ------------------------------------------------------------------------

    def _get_node_id_from_obj(self, obj: Any, side: Optional[int] = None) -> Optional[int]:
        """
        Извлекает node_id из объекта.
        Для кабелей учитывает сторону (side=1 -> node1_id, side=2 -> node2_id).
        Для остальных объектов просто возвращает node_id.
        """
        if obj is None:
            return None
        # Проверяем наличие атрибутов кабеля
        if hasattr(obj, 'node1_id') and hasattr(obj, 'node2_id'):
            if side == 1:
                return getattr(obj, 'node1_id', None)
            elif side == 2:
                return getattr(obj, 'node2_id', None)
            else:
                return getattr(obj, 'node1_id', None)
        # Для всех остальных объектов
        elif hasattr(obj, 'node_id'):
            return getattr(obj, 'node_id', None)
        return None

    def _get_splitter_type_from_obj(self, obj: Any) -> Optional[str]:
        """
        Определяет тип сплиттера по количеству входных и выходных портов.
        Возвращает строку вида "1xN" или "2xN".
        """
        if obj is None:
            return None
        port_in = getattr(obj, 'port_count_in', 0)
        port_out = getattr(obj, 'port_count_out', 0)
        if port_in == 0 or port_out == 0:
            return None
        return f"{port_in}x{port_out}"

    def _get_fiber_length_km_from_obj(self, obj: Any) -> Optional[float]:
        """
        Извлекает длину кабеля в километрах.
        Приоритет: optical_length (оптическая длина), затем building_length (строительная).
        """
        if obj is None:
            return None
        length = getattr(obj, 'optical_length', None)
        if length is not None:
            return float(length) / 1000.0
        length = getattr(obj, 'building_length', None)
        if length is not None:
            return float(length) / 1000.0
        return None

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, iface: Interface, obj: Optional[Any] = None,
                    node_id_override: Optional[int] = None) -> int:
        """
        Добавляет вершину в граф, если её ещё нет.
        Сохраняет в атрибутах вершины: obj_type, obj_id, side, port, node_id,
        полный объект api_obj, а также splitter_type для сплиттеров.

        Args:
            iface: интерфейс (ключ вершины).
            obj: готовый объект (если уже загружен, иначе будет загружен).
            node_id_override: принудительное значение node_id (используется для абонентов).

        Returns:
            Индекс вершины в графе.
        """
        if iface in self._vertex_index:
            return self._vertex_index[iface]

        # Если объект не передан, загружаем его из кэша
        if obj is None:
            obj = self._load_object(iface.obj)

        # Определяем node_id
        node_id = node_id_override
        if node_id is None and obj is not None:
            # Для кабелей учитываем сторону
            side_for_node = iface.side if iface.obj.obj_type == TYPE_FIBER else None
            node_id = self._get_node_id_from_obj(obj, side_for_node)

        # Определяем тип сплиттера (если применимо)
        splitter_type = None
        if iface.obj.obj_type == TYPE_SPLITTER and obj is not None:
            splitter_type = self._get_splitter_type_from_obj(obj)

        # Формируем атрибуты вершины
        attrs = {
            'obj_type': iface.obj.obj_type,
            'obj_id': str(iface.obj.id),
            'side': iface.side,
            'port': iface.port,
            'node_id': node_id,
            'name': str(iface),
            'api_obj': obj,               # полный объект (может быть None)
            'splitter_type': splitter_type,
        }

        # Добавляем вершину в граф
        idx = self.add_vertex(**attrs).index
        self._vertex_index[iface] = idx
        return idx

    def _add_edge(self, iface1: Interface, iface2: Interface, connect_id: int,
                  node_id_for_vertex2: Optional[int] = None,
                  attenuation_override: Optional[float] = None,
                  is_internal: bool = False) -> None:
        """
        Добавляет ребро между двумя интерфейсами (коммутацию).
        Сохраняет в атрибутах ребра: connect_id, attenuation, is_internal.

        Args:
            iface1, iface2: интерфейсы, которые соединяются.
            connect_id: идентификатор коммутации из API.
            node_id_for_vertex2: переопределение node_id для второй вершины (обычно для абонентов).
            attenuation_override: принудительное затухание (если None — вычисляется автоматически).
            is_internal: флаг внутреннего ребра (кросс, сплиттер, кабель).
        """
        # Загружаем объекты для вершин (если они есть в кэше)
        obj1 = self._load_object(iface1.obj)
        obj2 = self._load_object(iface2.obj)

        # Добавляем вершины
        idx1 = self._add_vertex(iface1, obj=obj1)
        idx2 = self._add_vertex(iface2, obj=obj2, node_id_override=node_id_for_vertex2)

        # Если ребро уже существует, не добавляем повторно
        if self.are_connected(idx1, idx2):
            return

        # Вычисляем затухание
        if attenuation_override is not None:
            attenuation = attenuation_override
        else:
            attenuation = self._compute_attenuation(iface1, iface2, is_internal, connect_id)

        # Добавляем ребро
        self.add_edge(idx1, idx2,
                      connect_id=connect_id,
                      attenuation=attenuation,
                      is_internal=is_internal,
                      api_obj=None)  # Для внешних рёбер можно сохранить коммутацию, но пока оставим None

    # ------------------------------------------------------------------------
    # Вычисление затухания (использует объекты из кэша)
    # ------------------------------------------------------------------------

    def _compute_attenuation(self, iface1: Interface, iface2: Interface,
                             is_internal: bool, connect_id: int) -> Optional[float]:
        """
        Вычисляет затухание для ребра на основе данных из _attenuation_data.
        Если данные не загружены или отсутствуют значения, возвращает None.
        """
        if not self._attenuation_data:
            return None

        # Внутренние рёбра (кросс, сплиттер, CWDM)
        if is_internal:
            if iface1.obj != iface2.obj:
                return None
            obj_type = iface1.obj.obj_type

            if obj_type == TYPE_CROSS:
                return self._attenuation_data.get('connector')
            elif obj_type == TYPE_SPLITTER:
                splitter_type = self._get_splitter_type_from_obj(self._load_object(iface1.obj))
                splitter_data = self._attenuation_data.get('splitter', {})
                if splitter_type and splitter_type in splitter_data:
                    port_losses = splitter_data[splitter_type]
                    # Если выход (side=2), используем порт iface2.port
                    if iface2.side == 2 and iface2.port in port_losses:
                        return port_losses[iface2.port]
                    # Если вход (side=1) или порт не найден, возвращаем среднее
                    if port_losses:
                        return sum(port_losses.values()) / len(port_losses)
                return None
            elif obj_type == TYPE_CWDM:
                cwdm_data = self._attenuation_data.get('cwdm', {})
                # Для CWDM можно определить тип, но пока упростим
                return None
            else:
                return None

        # Внешнее ребро (между разными объектами)
        else:
            # Проверяем, является ли один из интерфейсов кабелем
            fiber_iface = None
            other_iface = None
            if iface1.obj.obj_type == TYPE_FIBER:
                fiber_iface = iface1
                other_iface = iface2
            elif iface2.obj.obj_type == TYPE_FIBER:
                fiber_iface = iface2
                other_iface = iface1

            if fiber_iface is not None:
                # Загружаем объект кабеля для получения длины
                obj = self._load_object(fiber_iface.obj)
                length_km = self._get_fiber_length_km_from_obj(obj)
                fiber_per_km = self._attenuation_data.get('fiber_per_km')
                if fiber_per_km is not None and length_km is not None:
                    fiber_atten = length_km * fiber_per_km
                else:
                    fiber_atten = None
                # Затухание на сварке (если другой конец не кабель)
                splice_atten = self._attenuation_data.get('splice') if other_iface is not None else 0.0
                if fiber_atten is not None:
                    return fiber_atten + (splice_atten if splice_atten is not None else 0.0)
                else:
                    return splice_atten if splice_atten is not None else None
            else:
                # Если ни один интерфейс не кабель, затухание отсутствует
                return None

    # ------------------------------------------------------------------------
    # Обработчики для разных типов объектов (построение графа)
    # ------------------------------------------------------------------------

    def _process_device(self, obj: ObjKey, comms: List[Commutation.Get_data],
                        current_iface: Interface, visited_interfaces: Set[Interface],
                        queue: deque, parent_obj: Optional[ObjKey],
                        stop_on_olt: bool = True) -> None:
        """
        Обрабатывает устройство (OLT, switch, ONU, CWDM).
        Если stop_on_olt=True и это не OLT, обход останавливается.
        CWDM обрабатывается как side-объект, поэтому здесь он игнорируется.
        """
        # Если это не OLT и stop_on_olt=True, останавливаемся
        if obj.obj_type != TYPE_OLT:
            if stop_on_olt:
                self.logger.debug(f"Устройство {obj} не OLT, останавливаемся")
                return
            # CWDM обрабатывается в _process_side_object
            if obj.obj_type == TYPE_CWDM:
                return

        # Находим запись для текущего интерфейса
        record = self._find_record_for_interface(comms, current_iface)
        if record is None:
            self.logger.debug(f"  Не найдена запись для {current_iface}")
            return

        # Извлекаем соседа
        neighbor_obj_key = self._get_neighbor_obj_key(record)
        if neighbor_obj_key is None:
            return

        connect_id = record.connect_id
        self.logger.debug(f"  Сосед: {neighbor_obj_key}, connect_id={connect_id}")

        # Загружаем объект соседа для получения node_id
        neighbor_obj = self._load_object(neighbor_obj_key)
        parent_node_id = self._get_node_id_from_obj(self._load_object(obj))

        # Получаем интерфейс соседа (сторону и порт)
        neighbor_iface = self._get_interface_for_neighbor(neighbor_obj_key, connect_id, parent_node_id)
        if neighbor_iface is None:
            return

        # Для абонентов node_id берётся от родителя
        node_id_for_vertex2 = parent_node_id if neighbor_obj_key.obj_type == TYPE_CUSTOMER else None

        # Добавляем ребро
        self._add_edge(current_iface, neighbor_iface, connect_id,
                       node_id_for_vertex2=node_id_for_vertex2)

        # Если сосед — объект со сторонами, добавляем его интерфейс в очередь для продолжения обхода
        if neighbor_obj_key.obj_type in SIDE_TYPES:
            if neighbor_iface not in visited_interfaces:
                queue.append((neighbor_iface, neighbor_obj_key))

    def _process_side_object(self, obj: ObjKey, comms: List[Commutation.Get_data],
                             current_iface: Interface, visited_interfaces: Set[Interface],
                             queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """
        Обрабатывает объекты со сторонами: кросс, кабель, сплиттер, CWDM.
        Добавляет внутренние рёбра для связности сторон.
        """
        self.logger.debug(f"Обработка объекта со сторонами {obj}")

        # Запись на текущей стороне
        record = self._find_record_for_interface(comms, current_iface)
        if record is None:
            self.logger.debug(f"  Не найдена запись для {current_iface}")
            return

        # Извлекаем соседа
        neighbor_obj_key = self._get_neighbor_obj_key(record)
        if neighbor_obj_key is None:
            return

        connect_id = record.connect_id
        self.logger.debug(f"  Сосед: {neighbor_obj_key}, connect_id={connect_id}")

        parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
        neighbor_iface = self._get_interface_for_neighbor(neighbor_obj_key, connect_id, parent_node_id)
        if neighbor_iface is None:
            return

        node_id_for_vertex2 = parent_node_id if neighbor_obj_key.obj_type == TYPE_CUSTOMER else None
        self._add_edge(current_iface, neighbor_iface, connect_id,
                       node_id_for_vertex2=node_id_for_vertex2)

        # Для кроссов и кабелей — внутреннее ребро на противоположную сторону
        if obj.obj_type in (TYPE_CROSS, TYPE_FIBER):
            opposite_side = 2 if current_iface.side == 1 else 1
            opposite_iface = Interface(obj, opposite_side, current_iface.port)
            self.logger.debug(f"  Внутреннее ребро между {current_iface} и {opposite_iface}")
            self._add_edge(current_iface, opposite_iface, 0, is_internal=True)

            # Запись на противоположной стороне
            opposite_record = self._find_record_for_interface(comms, opposite_iface)
            if opposite_record is None:
                self.logger.debug(f"  Нет записи на противоположной стороне")
                return

            neighbor_obj_opp = self._get_neighbor_obj_key(opposite_record)
            if neighbor_obj_opp is None:
                return

            connect_id_opp = opposite_record.connect_id
            self.logger.debug(f"  Сосед на противоположной стороне: {neighbor_obj_opp}, connect_id={connect_id_opp}")

            parent_node_id_opp = self._get_node_id_from_obj(self._load_object(obj))
            neighbor_iface_opp = self._get_interface_for_neighbor(neighbor_obj_opp, connect_id_opp, parent_node_id_opp)
            if neighbor_iface_opp is None:
                return

            node_id_for_vertex2_opp = parent_node_id_opp if neighbor_obj_opp.obj_type == TYPE_CUSTOMER else None
            self._add_edge(opposite_iface, neighbor_iface_opp, connect_id_opp,
                           node_id_for_vertex2=node_id_for_vertex2_opp)

            if neighbor_obj_opp.obj_type in SIDE_TYPES:
                if neighbor_iface_opp not in visited_interfaces:
                    queue.append((neighbor_iface_opp, neighbor_obj_opp))

        # Для сплиттера и CWDM — внутренние рёбра от входа ко всем выходам
        elif obj.obj_type in (TYPE_SPLITTER, TYPE_CWDM):
            if current_iface.side == 1:  # вход
                # Находим все записи на стороне 2 (выходы)
                out_records = [rec for rec in comms if rec.clps_first is not None and int(rec.clps_first) == 2]
                self.logger.debug(f"  Найдено выходов: {len(out_records)}")

                # Внутренние рёбра от входа к каждому выходу
                for rec in out_records:
                    out_port = rec.clps_mid
                    out_iface = Interface(obj, 2, out_port)
                    self._add_edge(current_iface, out_iface, 0, is_internal=True)

                # Обрабатываем соседей на выходах
                for rec in out_records:
                    neighbor_obj_out = self._get_neighbor_obj_key(rec)
                    if neighbor_obj_out is None:
                        continue

                    connect_id_out = rec.connect_id
                    out_port = rec.clps_mid
                    out_iface = Interface(obj, 2, out_port)

                    parent_node_id_out = self._get_node_id_from_obj(self._load_object(obj))
                    neighbor_iface_out = self._get_interface_for_neighbor(neighbor_obj_out, connect_id_out, parent_node_id_out)
                    if neighbor_iface_out is None:
                        continue

                    node_id_for_vertex2_out = parent_node_id_out if neighbor_obj_out.obj_type == TYPE_CUSTOMER else None
                    self._add_edge(out_iface, neighbor_iface_out, connect_id_out,
                                   node_id_for_vertex2=node_id_for_vertex2_out)

                    if neighbor_obj_out.obj_type in SIDE_TYPES:
                        if neighbor_iface_out not in visited_interfaces:
                            queue.append((neighbor_iface_out, neighbor_obj_out))
            else:
                self.logger.debug("  Пришли на выход (side=2), останавливаемся")

    # ------------------------------------------------------------------------
    # Вспомогательные методы для поиска записей и соседей
    # ------------------------------------------------------------------------

    def _find_record_for_interface(self, comms: List[Commutation.Get_data],
                                   iface: Interface) -> Optional[Commutation.Get_data]:
        """
        Находит запись в списке коммутаций, соответствующую переданному интерфейсу.
        Для устройств и абонентов сравнивается только порт (clps_first).
        Для объектов со сторонами — сторона и порт.
        """
        is_device_or_customer = (iface.obj.obj_type in DEVICE_TYPES or iface.obj.obj_type == TYPE_CUSTOMER)
        for rec in comms:
            if is_device_or_customer:
                if rec.clps_first is not None and int(rec.clps_first) == iface.port:
                    return rec
            else:
                if (rec.clps_first is not None and int(rec.clps_first) == iface.side and
                    rec.clps_mid is not None and int(rec.clps_mid) == iface.port):
                    return rec
        return None

    def _get_neighbor_obj_key(self, record: Commutation.Get_data) -> Optional[ObjKey]:
        """
        Из записи коммутации извлекает ObjKey соседа.
        """
        obj_type_str = record.object_type
        obj_id = record.object_id
        obj_uuid = record.object_uuid
        if not obj_type_str:
            return None
        return self._make_obj_key(obj_type_str, obj_id, obj_uuid)

    def _make_obj_key(self, type_str: str, obj_id: Optional[int],
                      obj_uuid: Optional[str] = None) -> Optional[ObjKey]:
        """
        Создаёт ObjKey из строкового типа и идентификатора.
        Для кроссов используется obj_uuid, для остальных — obj_id.
        """
        if not type_str:
            return None
        if type_str == TYPE_CROSS:
            if obj_uuid is None:
                return None
            return ObjKey(type_str, obj_uuid)
        else:
            if obj_id is None:
                return None
            return ObjKey(type_str, obj_id)

    def _get_interface_for_neighbor(self, neighbor_obj_key: ObjKey, connect_id: int,
                                    parent_node_id: Optional[int] = None) -> Optional[Interface]:
        """
        В коммутациях соседа ищет запись с заданным connect_id и возвращает Interface соседа.
        Для абонентов и устройств возвращается интерфейс с side=1, port=0.
        """
        if neighbor_obj_key.obj_type == TYPE_CUSTOMER:
            return Interface(neighbor_obj_key, side=1, port=0)

        if neighbor_obj_key.obj_type in DEVICE_TYPES:
            return Interface(neighbor_obj_key, side=1, port=0)

        neighbor_comms = self._load_commutations(neighbor_obj_key)
        if not neighbor_comms:
            self.logger.debug(f"  Нет коммутаций для соседа {neighbor_obj_key}")
            return None

        # Ищем запись с нужным connect_id
        neighbor_rec = None
        for rec in neighbor_comms:
            if int(rec.connect_id) == int(connect_id):
                neighbor_rec = rec
                break
        if neighbor_rec is None:
            self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj_key}")
            return None

        side = int(neighbor_rec.clps_first) if neighbor_rec.clps_first is not None else 1
        port = int(neighbor_rec.clps_mid) if neighbor_rec.clps_mid is not None else 0
        return Interface(neighbor_obj_key, side, port)

    # ------------------------------------------------------------------------
    # Основные методы построения графа коммутаций
    # ------------------------------------------------------------------------

    def build(self, object_type: str, object_id: Union[int, str], port: Optional[int] = None) -> 'CommutationGraph':
        """
        Строит граф коммутаций от заданного объекта.
        Если object_type == 'olt' и port указан, строит от конкретного порта OLT.
        Если object_type == 'olt' и port не указан, строит от всех портов OLT.
        Иначе строит от указанного объекта (при необходимости используя порт).

        Args:
            object_type: строковый тип объекта ('olt', 'switch', 'fiber', 'cross', 'splitter', 'cwdm', 'customer').
            object_id: идентификатор объекта (число или UUID для кроссов).
            port: номер порта (для OLT, устройств и абонентов можно не указывать).

        Returns:
            self (CommutationGraph)
        """
        self.logger.info(f"=== ПОСТРОЕНИЕ ГРАФА ОТ {object_type}:{object_id} (port={port}) ===")

        # Если OLT
        if object_type == TYPE_OLT:
            if port is not None:
                return self._build_from_olt(object_id, port)
            else:
                return self._build_all_ports(object_id)

        # Для остальных объектов
        obj_key = ObjKey(object_type, object_id)
        start_port = port or 1
        start_side = 1
        start_iface = Interface(obj_key, side=start_side, port=start_port)

        self._add_vertex(start_iface)

        queue = deque([(start_iface, None)])
        visited_interfaces: Set[Interface] = set()

        while queue:
            current_iface, parent_obj = queue.popleft()
            self.logger.debug(f"--- Обработка интерфейса {current_iface} ---")

            if current_iface in visited_interfaces:
                continue
            visited_interfaces.add(current_iface)

            obj = current_iface.obj

            comms = self._load_commutations(obj)
            if not comms:
                continue

            obj_type_curr = obj.obj_type

            if obj_type_curr in DEVICE_TYPES:
                self._process_device(obj, comms, current_iface, visited_interfaces, queue, parent_obj, stop_on_olt=False)
            elif obj_type_curr in SIDE_TYPES:
                self._process_side_object(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type_curr == TYPE_CUSTOMER:
                continue
            else:
                self.logger.warning(f"  Неизвестный тип объекта: {obj_type_curr}")

        self._update_directed_flag()
        self.logger.info("=== ПОСТРОЕНИЕ ЗАВЕРШЕНО ===")
        return self

    def _build_from_olt(self, olt_id: int, pon_port: int) -> 'CommutationGraph':
        """Внутренний метод построения от конкретного порта OLT."""
        self.logger.info(f"--- Построение от OLT {olt_id}, порт {pon_port}")

        olt_obj = ObjKey(TYPE_OLT, olt_id)
        start_iface = Interface(olt_obj, side=1, port=pon_port)

        self._add_vertex(start_iface)

        queue = deque([(start_iface, None)])
        visited_interfaces: Set[Interface] = set()

        while queue:
            current_iface, parent_obj = queue.popleft()
            self.logger.debug(f"--- Обработка интерфейса {current_iface} ---")

            if current_iface in visited_interfaces:
                continue
            visited_interfaces.add(current_iface)

            obj = current_iface.obj

            comms = self._load_commutations(obj)
            if not comms:
                continue

            obj_type = obj.obj_type

            if obj_type in DEVICE_TYPES:
                self._process_device(obj, comms, current_iface, visited_interfaces, queue, parent_obj, stop_on_olt=True)
            elif obj_type in SIDE_TYPES:
                self._process_side_object(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type == TYPE_CUSTOMER:
                continue
            else:
                self.logger.warning(f"  Неизвестный тип объекта: {obj_type}")

        return self

    def _build_all_ports(self, olt_id: int) -> 'CommutationGraph':
        """Внутренний метод построения от всех портов OLT."""
        self.logger.info(f"--- Построение от всех портов OLT {olt_id}")

        olt_obj = self._load_object(ObjKey(TYPE_OLT, olt_id))
        ifaces = getattr(olt_obj, 'ifaces', {}) if olt_obj else {}
        pon_ports = []
        if isinstance(ifaces, dict):
            for port_num, iface_info in ifaces.items():
                if iface_info.get('ifType') == 6 or iface_info.get('ifTypeText') == 'gpon':
                    pon_ports.append(int(port_num))
        else:
            self.logger.warning(f"Нет информации о портах для OLT {olt_id}")
            return self

        if not pon_ports:
            self.logger.warning(f"Не найдены PON-порты для OLT {olt_id}")
            return self

        self.logger.info(f"Найдено {len(pon_ports)} PON-портов: {pon_ports}")
        for port in pon_ports:
            self._build_from_olt(olt_id, port)

        return self

    # ------------------------------------------------------------------------
    # Определение направления
    # ------------------------------------------------------------------------

    def _update_directed_flag(self) -> None:
        """Обновляет флаг _directed на основе наличия сплиттеров или абонентов."""
        has_splitter = any(v['obj_type'] == TYPE_SPLITTER for v in self.vs)
        has_cwdm = any(v['obj_type'] == TYPE_CWDM for v in self.vs)
        has_customer = any(v['obj_type'] == TYPE_CUSTOMER for v in self.vs)
        self._directed = has_splitter or has_cwdm or has_customer

    # ------------------------------------------------------------------------
    # Управление затуханиями
    # ------------------------------------------------------------------------

    def load_attenuation_data(self, data: Dict[str, Any]) -> None:
        """
        Загружает данные по затуханиям для пересчёта атрибутов рёбер.
        Формат данных:
        {
            'fiber_per_km': 0.4,          # затухание на 1 км волокна (дБ/км)
            'splice': 0.1,                # затухание на сварке (дБ)
            'connector': 0.2,             # затухание на адаптере кросса (дБ)
            'splitter': {
                '1x2': {1: 3.5, 2: 3.5},  # порт: затухание
                '1x4': {1: 7.0, 2: 7.0, 3: 7.0, 4: 7.0},
                ...
            },
            'cwdm': {
                '4ch': {1: 1.5, 2: 1.5, 3: 1.5, 4: 1.5},
                ...
            }
        }
        Если граф уже построен, пересчитывает затухания для всех рёбер.
        """
        self._attenuation_data = data
        if self.vcount() > 0 and self.ecount() > 0:
            self._recompute_attenuation()

    def _recompute_attenuation(self) -> None:
        """Пересчитывает затухания для всех существующих рёбер."""
        for edge in self.es:
            v1, v2 = edge.tuple
            iface1 = self._get_interface_by_vertex_index(v1)
            iface2 = self._get_interface_by_vertex_index(v2)
            if iface1 is None or iface2 is None:
                continue
            is_internal = edge['is_internal'] if 'is_internal' in edge.attributes() else False
            connect_id = edge['connect_id'] if 'connect_id' in edge.attributes() else 0
            attenuation = self._compute_attenuation(iface1, iface2, is_internal, connect_id)
            edge['attenuation'] = attenuation

    def _get_interface_by_vertex_index(self, idx: int) -> Optional[Interface]:
        """Возвращает Interface по индексу вершины (поиск по _vertex_index)."""
        for iface, v_idx in self._vertex_index.items():
            if v_idx == idx:
                return iface
        return None

    # ------------------------------------------------------------------------
    # Представление
    # ------------------------------------------------------------------------

    @property
    def directed(self) -> bool:
        return self._directed

    def __repr__(self) -> str:
        return f"CommutationGraph(interfaces={self.vcount()}, commutations={self.ecount()}, directed={self._directed})"


# ===========================================================================
# Класс графа сооружений связи и кабелей (FNGraph) с общими кэшами
# ===========================================================================

@dataclass(frozen=True)
class NodeKey:
    """Ключ вершины для FNGraph (просто node_id)."""
    node_id: int


@dataclass(frozen=True)
class FiberEdge:
    """Информация о ребре-кабеле в FNGraph."""
    fiber_id: int
    node1_id: int
    node2_id: int


class FNGraph(ig.Graph):
    """
    Граф сооружений связи и кабелей.
    Вершины — node_id, рёбра — fiber_id.

    Использует общий кэш DataCache для хранения объектов Node и Fiber,
    а также кэш списков кабелей для узлов для ускорения построения.
    """

    def __init__(self, client: WorkerNetClient,
                 commutation_graph: Optional[CommutationGraph] = None,
                 cache: Optional[DataCache] = None,
                 **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self._cache = cache if cache is not None else _data_cache

        self._commutation_graph = commutation_graph

        # Сопоставление node_id -> индекс вершины в этом графе
        self._vertex_index: Dict[int, int] = {}

        # Кэш списков кабелей для узлов (локальный для этого экземпляра)
        self._node_fibers_cache: Dict[int, List[Any]] = {}

        self._built = False

    # ------------------------------------------------------------------------
    # Загрузка информации о вершинах (использует кэш)
    # ------------------------------------------------------------------------

    def _load_node(self, node_id: int) -> Optional[Any]:
        """Загружает объект Node из кэша или API."""
        return self._cache.get_or_load_object('node', node_id,
                                              lambda: self._load_node_from_api(node_id))

    def _load_node_from_api(self, node_id: int) -> Optional[Any]:
        try:
            result = self.client.Node.get(id=node_id)
            return result[0] if result and len(result) > 0 else None
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить node {node_id}: {e}")
            return None

    def _load_fiber(self, fiber_id: int) -> Optional[Any]:
        """Загружает объект Fiber из кэша или API."""
        return self._cache.get_or_load_object('fiber', fiber_id,
                                              lambda: self._load_fiber_from_api(fiber_id))

    def _load_fiber_from_api(self, fiber_id: int) -> Optional[Any]:
        try:
            result = self.client.Fiber.get_list(object_id=fiber_id)
            return result[0] if result and len(result) > 0 else None
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить fiber {fiber_id}: {e}")
            return None

    def _load_fibers_for_node(self, node_id: int) -> List[Any]:
        """
        Загружает все кабели, связанные с узлом, через API (с кэшированием).
        Сохраняет результат в локальном кэше для ускорения повторных запросов.
        """
        if node_id in self._node_fibers_cache:
            return self._node_fibers_cache[node_id]

        try:
            result = self.client.Fiber.get_list(node_id=node_id)
            fibers = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кабелей для узла {node_id}: {e}")
            fibers = []

        self._node_fibers_cache[node_id] = fibers
        # Сохраняем каждый кабель в общий кэш для возможного использования в других местах
        for fiber in fibers:
            fiber_id = getattr(fiber, 'code', None)
            if fiber_id is not None:
                self._cache.set_object('fiber', fiber_id, fiber)
        return fibers

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, node_id: int) -> int:
        """
        Добавляет вершину в граф, если её ещё нет.
        Сохраняет в атрибутах node_id и полный объект api_obj.
        """
        if node_id in self._vertex_index:
            return self._vertex_index[node_id]

        node_obj = self._load_node(node_id)
        attrs = {
            'node_id': node_id,
            'name': f"node:{node_id}",
            'api_obj': node_obj,
        }
        if node_obj is not None:
            # Добавляем все значимые поля из объекта в атрибуты вершины
            for attr in ['address_id', 'coordinates', 'type', 'number', 'comment', 'location', 'is_planned']:
                if hasattr(node_obj, attr):
                    attrs[attr] = getattr(node_obj, attr)

        idx = self.add_vertex(**attrs).index
        self._vertex_index[node_id] = idx
        return idx

    def _add_edge(self, node1_id: int, node2_id: int, fiber_id: int) -> None:
        """
        Добавляет ребро между двумя узлами (кабель).
        Если ребро уже существует, добавляет параллельное ребро (мультиграф).
        """
        if node1_id == node2_id:
            self.logger.debug(f"Петля для кабеля {fiber_id} (node1=node2={node1_id}), пропускаем")
            return

        idx1 = self._add_vertex(node1_id)
        idx2 = self._add_vertex(node2_id)

        # Загружаем объект кабеля для сохранения в ребре
        fiber_obj = self._load_fiber(fiber_id)

        # Добавляем ребро (даже если параллельное — igraph поддерживает мультиграф)
        self.add_edge(idx1, idx2,
                      fiber_id=fiber_id,
                      api_obj=fiber_obj)

    # ------------------------------------------------------------------------
    # Построение из CommutationGraph
    # ------------------------------------------------------------------------

    def _build_from_commutation_graph(self, included_fibers: Optional[Set[int]] = None,
                                      excluded_fibers: Optional[Set[int]] = None) -> None:
        """
        Извлекает информацию о кабелях из переданного CommutationGraph.
        Группирует вершины кабелей по fiber_id и создаёт рёбра между узлами.
        """
        if self._commutation_graph is None:
            self.logger.error("CommutationGraph не передан, невозможно построить граф")
            return

        cg = self._commutation_graph
        fiber_groups: Dict[int, Set[int]] = defaultdict(set)

        for v in cg.vs:
            if v['obj_type'] != 'fiber':
                continue
            fiber_id = int(v['obj_id'])
            node_id = v['node_id']
            if node_id is None:
                self.logger.warning(f"У вершины кабеля {fiber_id} нет node_id, пропускаем")
                continue
            if included_fibers is not None and fiber_id not in included_fibers:
                continue
            if excluded_fibers is not None and fiber_id in excluded_fibers:
                continue
            fiber_groups[fiber_id].add(node_id)

        for fiber_id, nodes in fiber_groups.items():
            node_list = list(nodes)
            if len(node_list) == 2:
                node1, node2 = node_list
                self._add_edge(node1, node2, fiber_id)
            elif len(node_list) == 1:
                self.logger.debug(f"Кабель {fiber_id} имеет только один узел {node_list[0]}, тупик")
            else:
                self.logger.warning(f"Кабель {fiber_id} имеет более двух узлов: {nodes}, пропускаем")

    # ------------------------------------------------------------------------
    # Построение через API (BFS от стартового узла)
    # ------------------------------------------------------------------------

    def _build_from_api(self, start_node_id: int,
                        included_fibers: Optional[Set[int]] = None,
                        excluded_fibers: Optional[Set[int]] = None) -> None:
        """
        Рекурсивно (BFS) обходит узлы, начиная с start_node_id,
        и добавляет кабели с учётом фильтров.
        """
        visited_nodes: Set[int] = set()
        queue = deque([start_node_id])

        while queue:
            current_node = queue.popleft()
            if current_node in visited_nodes:
                continue
            visited_nodes.add(current_node)

            # Добавляем вершину для текущего узла
            self._add_vertex(current_node)

            # Загружаем все кабели для этого узла
            fibers = self._load_fibers_for_node(current_node)
            for fiber in fibers:
                fiber_id = getattr(fiber, 'code', None)
                if fiber_id is None:
                    self.logger.warning("Пропущен кабель без code")
                    continue

                # Проверяем фильтры
                if included_fibers is not None and fiber_id not in included_fibers:
                    continue
                if excluded_fibers is not None and fiber_id in excluded_fibers:
                    continue

                node1 = getattr(fiber, 'node1_id', None)
                node2 = getattr(fiber, 'node2_id', None)
                if node1 is None or node2 is None:
                    self.logger.warning(f"Кабель {fiber_id} без node1_id или node2_id")
                    continue

                # Определяем соседний узел
                if node1 == current_node:
                    neighbor = node2
                elif node2 == current_node:
                    neighbor = node1
                else:
                    self.logger.warning(f"Кабель {fiber_id} не связан с узлом {current_node}")
                    continue

                # Добавляем ребро
                self._add_edge(current_node, neighbor, fiber_id)

                # Если соседний узел ещё не посещён, добавляем его в очередь
                if neighbor not in visited_nodes:
                    queue.append(neighbor)

    # ------------------------------------------------------------------------
    # Основной метод построения
    # ------------------------------------------------------------------------

    def build(self, start_node_id: int,
              included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None) -> 'FNGraph':
        """
        Строит граф сооружений связи и кабелей.

        Args:
            start_node_id: ID начального узла (сооружения связи).
            included_fibers: Список (или множество) ID кабелей, которые разрешено использовать.
                             Если None, используются все кабели.
            excluded_fibers: Список (или множество) ID кабелей, которые запрещены.
                             Если кабель в этом списке, он не добавляется и обход не продолжается.

        Returns:
            FNGraph (self)
        """
        self.logger.info("=== ПОСТРОЕНИЕ ГРАФА FN ===")

        # Приводим фильтры к множествам для быстрой проверки
        if included_fibers is not None:
            if isinstance(included_fibers, (int, str)):
                included_fibers = {int(included_fibers)}
            else:
                included_fibers = set(included_fibers)
        if excluded_fibers is not None:
            if isinstance(excluded_fibers, (int, str)):
                excluded_fibers = {int(excluded_fibers)}
            else:
                excluded_fibers = set(excluded_fibers)

        if self._commutation_graph is not None:
            self.logger.info("Построение из CommutationGraph")
            self._build_from_commutation_graph(included_fibers, excluded_fibers)
        else:
            self.logger.info("Построение через API")
            self._build_from_api(start_node_id, included_fibers, excluded_fibers)

        self._built = True
        self.logger.info("=== ПОСТРОЕНИЕ FN ЗАВЕРШЕНО ===")
        return self

    # ------------------------------------------------------------------------
    # Аналитические методы
    # ------------------------------------------------------------------------

    def find_fibers_for_node(self, node_id: int) -> List[int]:
        """
        Возвращает список fiber_id для всех рёбер, инцидентных вершине.
        """
        idx = self._vertex_index.get(node_id)
        if idx is None:
            return []
        incident_edges = self.incident(idx, mode='all')
        fiber_ids = []
        for eid in incident_edges:
            fiber_id = self.es[eid]['fiber_id']
            if fiber_id is not None:
                fiber_ids.append(fiber_id)
        return fiber_ids

    def get_fiber_edges(self) -> List[Dict[str, Any]]:
        """
        Возвращает список всех рёбер с информацией (node1, node2, fiber_id).
        """
        edges = []
        for edge in self.es:
            v1, v2 = edge.tuple
            node1_id = self.vs[v1]['node_id']
            node2_id = self.vs[v2]['node_id']
            fiber_id = edge['fiber_id']
            edges.append({
                'node1_id': node1_id,
                'node2_id': node2_id,
                'fiber_id': fiber_id,
            })
        return edges

    def stats(self) -> Dict[str, Any]:
        """Возвращает базовую статистику графа."""
        return {
            'num_vertices': self.vcount(),
            'num_edges': self.ecount(),
            'start_node_id': self.vs[0]['node_id'] if self.vcount() > 0 else None,
        }

    def export_graphml(self, filename: str) -> None:
        """Сохраняет граф в формате GraphML."""
        self.write_graphml(filename)

    def __repr__(self) -> str:
        return f"FNGraph(nodes={self.vcount()}, fibers={self.ecount()})"