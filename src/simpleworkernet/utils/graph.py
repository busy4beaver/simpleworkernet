# =============================================================================
# graph.py
# =============================================================================
"""
Модуль graph.py — построение графов коммутаций (CGraph) и сооружений связи (FNGraph).

Содержит:
- DataCache: глобальный кэш для объектов API и коммутаций.
- Классы ObjKey, Interface для идентификации вершин.
- CGraph: граф коммутаций (наследник igraph.Graph).
- FNGraph: граф сооружений связи (наследник igraph.Graph).

Все данные, загруженные по API, проходят через DataCache и сохраняются для повторного использования.
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from collections import deque, defaultdict
from dataclasses import dataclass
import igraph as ig

from ..core.client import WorkerNetClient
from ..models.categories import Commutation, Device, Cross, Splitter, Fiber, Customer, Node, Module, Cwdm

_logger = None

def _get_logger():
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger

# =============================================================================
# Константы типов объектов
# =============================================================================

TYPE_CUSTOMER = 'customer'
TYPE_FIBER = 'fiber'
TYPE_SPLITTER = 'splitter'
TYPE_CROSS = 'cross'
TYPE_CWDM = 'cwdm'
TYPE_SWITCH = 'switch'
TYPE_OLT = 'olt'
TYPE_ONU = 'onu'
TYPE_RADIO = 'radio'

DEVICE_TYPES = {TYPE_SWITCH, TYPE_OLT, TYPE_ONU, TYPE_RADIO}          # устройства
SIDE_TYPES = {TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER, TYPE_CWDM}  # объекты со сторонами
TERMINAL_TYPES = {TYPE_CUSTOMER} | DEVICE_TYPES           # конечные объекты (не транзитные)

# =============================================================================
# Глобальный кэш данных
# =============================================================================

class DataCache:
    """
    Глобальный кэш для объектов и коммутаций. Синглтон.

    Хранит:
    - _objects: {(тип, id): объект} — единый кэш для всех объектов.
      Для устройств дополнительно сохраняется под ключом ('device', id).
    - _commutations: {(тип, id): [коммутации]} — кэш списков коммутаций.
    - _all_objects: {тип: {id: объект}} — кэш всех объектов по типу (массовая загрузка).

    Все вызовы API должны проходить через методы этого класса.
    """
    _instance = None
    _objects: Dict[Tuple[str, Union[int, str]], Any] = {}
    _commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}
    _all_objects: Dict[str, Dict[Union[int, str], Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------------
    # Базовые методы кэширования
    # ------------------------------------------------------------------------

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        """Возвращает объект из кэша. Для устройств ищет альтернативный ключ."""
        obj = self._objects.get((obj_type, obj_id))
        if obj is None and obj_type in DEVICE_TYPES:
            obj = self._objects.get(('device', obj_id))
        return obj

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        """Сохраняет объект в кэш. Для устройств добавляет альтернативный ключ."""
        self._objects[(obj_type, obj_id)] = obj
        if obj_type in DEVICE_TYPES:
            self._objects[('device', obj_id)] = obj

    def get_or_load_object(self, obj_type: str, obj_id: Union[int, str],
                           loader: Callable[[], Any]) -> Any:
        """
        Возвращает объект из кэша или загружает через loader и сохраняет.
        Для устройств использует альтернативный ключ.
        """
        obj = self.get_object(obj_type, obj_id)
        if obj is None:
            obj = loader()
            if obj is not None:
                self.set_object(obj_type, obj_id, obj)
        return obj

    def get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> Optional[List[Any]]:
        return self._commutations.get((obj_type, obj_id))

    def set_commutations(self, obj_type: str, obj_id: Union[int, str],
                         comms: List[Any]) -> None:
        self._commutations[(obj_type, obj_id)] = comms

    def get_or_load_commutations(self, obj_type: str, obj_id: Union[int, str],
                                 loader: Callable[[], List[Any]]) -> List[Any]:
        key = (obj_type, obj_id)
        comms = self._commutations.get(key)
        if comms is None:
            comms = loader()
            if comms is not None:
                self._commutations[key] = comms
            else:
                comms = []
        return comms

    def get_all_objects(self, object_type: str, loader: Callable[[], List[Any]]) -> Dict[Union[int, str], Any]:
        """
        Загружает все объекты указанного типа и сохраняет их в кэш.
        Возвращает словарь {id: объект}.
        """
        if object_type in self._all_objects:
            return self._all_objects[object_type]

        try:
            result = loader()
            objects = result.to_list() if result else []
        except Exception as e:
            _logger.error(f"Ошибка загрузки всех объектов типа {object_type}: {e}")
            objects = []

        obj_dict = {}
        for obj in objects:
            obj_id = getattr(obj, 'id', None) or getattr(obj, 'code', None) or getattr(obj, 'uuid', None)
            if obj_id is not None:
                obj_dict[obj_id] = obj
                self.set_object(object_type, obj_id, obj)

        self._all_objects[object_type] = obj_dict
        return obj_dict

    # ========================================================================
    # Массовые загрузчики (все объекты определённого типа)
    # ========================================================================

    def get_all_splitters(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects('splitter', lambda: client.Splitter.get())

    def get_all_crosses(self, client: WorkerNetClient) -> Dict[str, Any]:
        return self.get_all_objects('cross', lambda: client.Cross.get_list())

    def get_all_cwdms(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects('cwdm', lambda: client.Cwdm.get())

    def get_all_nodes(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects('node', lambda: client.Node.get())

    def get_all_fibers(self, client: WorkerNetClient) -> Dict[int, Any]:
        catalog = client.Fiber.catalog_types_get()
        result = {}
        for cab_type in catalog.to_list() if catalog else []:
            type_id = getattr(cab_type, 'id', None)
            if type_id is not None:
                fibers = self.get_all_objects(
                    'fiber',
                    lambda: client.Fiber.get_list(cable_line_type_id=type_id)
                )
                result.update(fibers)
        return result

    def get_all_devices(self, client: WorkerNetClient) -> Dict[int, Any]:
        result = {}
        for dev_type in ['olt', 'switch']:#, 'onu']:#, 'radio']:
            devices = self.get_all_objects(
                dev_type,
                lambda: client.Device.get_data(object_type=dev_type)
            )
            result.update(devices)
        return result

    def get_all_customers(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects('customer', lambda: client.Module.get_user_list())

    # ========================================================================
    # Одиночные загрузчики (по ID)
    # ========================================================================

    def get_device(self, client: WorkerNetClient, obj_type: str, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Device.get_data(object_type=obj_type, object_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить устройство {obj_type}:{obj_id}: {e}")
                return None
        return self.get_or_load_object(obj_type, obj_id, loader)

    def get_cross(self, client: WorkerNetClient, obj_id: str) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Cross.get_list(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить кросс {obj_id}: {e}")
                return None
        return self.get_or_load_object('cross', obj_id, loader)

    def get_splitter(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Splitter.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить сплиттер {obj_id}: {e}")
                return None
        return self.get_or_load_object('splitter', obj_id, loader)

    def get_fiber(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Fiber.get_list(object_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить кабель {obj_id}: {e}")
                return None
        return self.get_or_load_object('fiber', obj_id, loader)

    def get_customer(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Customer.get_data(customer_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить абонента {obj_id}: {e}")
                return None
        return self.get_or_load_object('customer', obj_id, loader)

    def get_node(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Node.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить узел {obj_id}: {e}")
                return None
        return self.get_or_load_object('node', obj_id, loader)

    def get_cwdm(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Cwdm.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _logger.warning(f"Не удалось загрузить CWDM {obj_id}: {e}")
                return None
        return self.get_or_load_object('cwdm', obj_id, loader)

    def get_commutations_by_object(self, client: WorkerNetClient,
                                   obj_type: str, obj_id: Union[int, str],
                                   is_finish_data: int = 0) -> List[Any]:
        """
        Загружает коммутации для объекта.
        Для устройств сохраняет под ключом ('switch', obj_id).
        """
        actual_type = TYPE_SWITCH if obj_type in DEVICE_TYPES else obj_type
        key = (actual_type, obj_id)

        def loader() -> List[Any]:
            api_type = actual_type
            api_id = str(obj_id) if api_type == TYPE_CROSS else int(obj_id)
            try:
                result = client.Commutation.get_data(
                    object_type=api_type,
                    object_id=api_id,
                    is_finish_data=is_finish_data
                )
                return result.to_list() if result else []
            except Exception as e:
                _logger.error(f"Ошибка загрузки коммутаций для {actual_type}:{obj_id}: {e}")
                return []
        return self.get_or_load_commutations(actual_type, obj_id, loader)

    def to_dict(self) -> dict:
        """Сериализует кэш в словарь для сохранения."""
        return {
            'objects': self._objects,
            'commutations': self._commutations,
            'all_objects': self._all_objects,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DataCache':
        """Восстанавливает кэш из словаря."""
        cache = cls()
        cache._objects = data.get('objects', {})
        cache._commutations = data.get('commutations', {})
        cache._all_objects = data.get('all_objects', {})
        return cache

# Глобальный экземпляр кэша (синглтон)
_data_cache = DataCache()

# =============================================================================
# Вспомогательные классы
# =============================================================================

@dataclass(frozen=True)
class ObjKey:
    """
    Уникальный ключ объекта сети (тип + ID).
    Используется для идентификации объекта при построении графа.
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
    Для устройств (OLT, switch, ONU) и абонентов сторона не имеет значения,
    но для единообразия используется side=1.
    """
    obj: ObjKey
    side: int
    port: int

    def __str__(self) -> str:
        return f"{self.obj} side={self.side} port={self.port}"


# =============================================================================
# Граф коммутаций (CGraph)
# =============================================================================

class CGraph(ig.Graph):
    """
    Граф коммутаций, где вершины — интерфейсы, рёбра — коммутации.
    Поддерживает фильтрацию по волокнам (included_fibers, excluded_fibers)
    и по узлам (excluded_nodes) при построении.

    Атрибуты вершин:
        obj_type : str               — тип объекта
        obj_id   : str               — ID объекта (всегда строка)
        side     : int               — сторона (1 или 2)
        port     : int               — номер порта
        node_id  : Optional[int]     — ID узла (сооружения), к которому относится объект
        api_obj  : Any               — полный объект из API (модель)
        terminate_vertex : bool      — является ли вершина конечной в исходной топологии
        finish_data : List[Commutation.Get_data] — finish-коммутации (clps_last == 'finish')
    """
    def __init__(self, client: WorkerNetClient, cache: Optional[DataCache] = None, **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self._cache: DataCache = cache if cache is not None else _data_cache
        self._vertex_index: Dict[Interface, int] = {}          # Interface -> индекс в igraph
        self._directed: bool = False

        # Фильтры, устанавливаемые при вызове build()
        self._included_fibers: Optional[Set[int]] = None
        self._excluded_fibers: Optional[Set[int]] = None
        self._excluded_nodes: Optional[Set[int]] = None
        self._start_node_id: Optional[int] = None
        self._start_obj_key: Optional[ObjKey] = None
        self._start_iface: Optional[Interface] = None

        # finish-данные (clps_last == 'finish') для объектов
        self._finish_data: Dict[ObjKey, List[Commutation.Get_data]] = {}

    # ------------------------------------------------------------------------
    # Загрузка данных через DataCache
    # ------------------------------------------------------------------------

    def _load_object(self, obj_key: ObjKey) -> Optional[Any]:
        """Загружает объект из кэша (или через API) по его ObjKey."""
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        if obj_type in DEVICE_TYPES:
            return self._cache.get_device(self.client, obj_type, int(obj_id))
        elif obj_type == TYPE_CROSS:
            return self._cache.get_cross(self.client, str(obj_id))
        elif obj_type == TYPE_SPLITTER:
            return self._cache.get_splitter(self.client, int(obj_id))
        elif obj_type == TYPE_FIBER:
            return self._cache.get_fiber(self.client, int(obj_id))
        elif obj_type == TYPE_CUSTOMER:
            return self._cache.get_customer(self.client, int(obj_id))
            return None
        else:
            return None

    def _load_commutations(self, obj_key: ObjKey) -> List[Commutation.Get_data]:
        """Загружает коммутации для объекта (включая finish-записи)."""
        obj_type = obj_key.obj_type
        obj_id = obj_key.id
        return self._cache.get_commutations_by_object(self.client, obj_type, obj_id, is_finish_data=1)

    # ------------------------------------------------------------------------
    # Вспомогательные методы для извлечения информации из объектов
    # ------------------------------------------------------------------------

    def _get_node_id_from_obj(self, obj: Any, side: Optional[int] = None) -> Optional[int]:
        """Извлекает node_id из объекта. Для кабелей учитывает сторону."""
        if obj is None:
            return None
        if hasattr(obj, 'node1_id') and hasattr(obj, 'node2_id'):
            if side == 1:
                return getattr(obj, 'node1_id', None)
            elif side == 2:
                return getattr(obj, 'node2_id', None)
            else:
                return getattr(obj, 'node1_id', None)
        elif hasattr(obj, 'node_id'):
            return getattr(obj, 'node_id', None)
        return None

    def _get_splitter_type_from_obj(self, obj: Any) -> Optional[str]:
        """Возвращает тип сплиттера (например, '1x8') по количеству портов."""
        if obj is None:
            return None
        port_in = getattr(obj, 'port_count_in', 0)
        port_out = getattr(obj, 'port_count_out', 0)
        if port_in == 0 or port_out == 0:
            return None
        return f"{port_in}x{port_out}"

    def _get_node_id_for_interface(self, iface: Interface) -> Optional[int]:
        """Возвращает node_id из атрибутов вершины, соответствующей интерфейсу."""
        idx = self._vertex_index.get(iface)
        if idx is None:
            return None
        return self.vs[idx]['node_id']

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, iface: Interface, obj: Optional[Any] = None,
                    node_id_override: Optional[int] = None) -> int:
        """
        Добавляет вершину в граф, если её ещё нет.
        При создании задаются начальные атрибуты (terminate_vertex, finish_data будут заполнены позже).
        """
        if iface in self._vertex_index:
            return self._vertex_index[iface]

        if obj is None:
            obj = self._load_object(iface.obj)

        node_id = node_id_override
        if node_id is None and obj is not None:
            side_for_node = iface.side if iface.obj.obj_type == TYPE_FIBER else None
            node_id = self._get_node_id_from_obj(obj, side_for_node)

        splitter_type = None
        if iface.obj.obj_type == TYPE_SPLITTER and obj is not None:
            splitter_type = self._get_splitter_type_from_obj(obj)

        attrs = {
            'obj_type': iface.obj.obj_type,
            'obj_id': str(iface.obj.id),
            'side': iface.side,
            'port': iface.port,
            'node_id': node_id,
            'name': str(iface),
            'api_obj': obj,
            'splitter_type': splitter_type,
            'terminate_vertex': False,   # будет проставлен позже
            'finish_data': [],           # будет проставлен позже
        }

        idx = self.add_vertex(**attrs).index
        self._vertex_index[iface] = idx
        return idx

    def _add_edge(self, iface1: Interface, iface2: Interface, connect_id: int,
                  node_id_for_vertex2: Optional[int] = None,
                  is_internal: bool = False) -> None:
        """
        Добавляет ребро между двумя интерфейсами (коммутацию).
        Если ребро уже существует, не добавляет повторно.
        """
        obj1 = self._load_object(iface1.obj)
        obj2 = self._load_object(iface2.obj)

        idx1 = self._add_vertex(iface1, obj=obj1)
        idx2 = self._add_vertex(iface2, obj=obj2, node_id_override=node_id_for_vertex2)

        if self.are_connected(idx1, idx2):
            return

        self.add_edge(idx1, idx2,
                      connect_id=connect_id,
                      is_internal=is_internal,
                      api_obj=None)

    # ------------------------------------------------------------------------
    # Фильтры
    # ------------------------------------------------------------------------

    def _should_stop_at_fiber(self, fiber_id: int, current_node_id: Optional[int]) -> bool:
        """
        Определяет, следует ли остановить обход на данном волокне.
        - excluded_fibers применяется всегда.
        - included_fibers применяется только на стартовом узле.
        """
        if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
            return True

        if self._included_fibers is not None:
            if self._start_node_id is not None and current_node_id == self._start_node_id:
                if fiber_id not in self._included_fibers:
                    return True
        return False

    def _should_stop_at_node(self, node_id: int) -> bool:
        """Проверяет, есть ли узел в excluded_nodes."""
        if self._excluded_nodes is not None and node_id in self._excluded_nodes:
            return True
        return False

    # ------------------------------------------------------------------------
    # Обработчики объектов при построении
    # ------------------------------------------------------------------------

    def _process_terminal_object(self, obj: ObjKey, comms: List[Commutation.Get_data],
                                 current_iface: Interface, visited_interfaces: Set[Interface],
                                 queue: deque) -> None:
        """
        Обрабатывает терминальные объекты (устройства, абоненты).
        Отделяет finish-записи от обычных коммутаций и строит ребро к соседу.
        """
        self.logger.debug(f"Обработка терминального объекта {obj}")

        # Разделяем записи на обычные и finish
        normal_records = []
        finish_records = []
        for rec in comms:
            if getattr(rec, 'clps_last', None) == 'finish':
                finish_records.append(rec)
            else:
                normal_records.append(rec)

        if finish_records:
            self._finish_data.setdefault(obj, []).extend(finish_records)

        # Проверка фильтра на узел
        current_node_id = self._get_node_id_for_interface(current_iface)
        if current_node_id is not None and self._should_stop_at_node(current_node_id):
            self.logger.debug(f"  Узел {current_node_id} в excluded_nodes, останавливаемся")
            return

        # Ищем запись для текущего интерфейса
        record = self._find_record_for_interface(normal_records, current_iface)
        if record is None:
            self.logger.debug(f"  Не найдена запись для {current_iface}")
            return

        neighbor_obj_key = self._get_neighbor_obj_key(record)
        if neighbor_obj_key is None:
            self.logger.warning(f"  Не удалось получить ключ соседа из записи {record}")
            return

        connect_id = record.connect_id
        self.logger.debug(f"  Сосед: {neighbor_obj_key}, connect_id={connect_id}")

        parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
        neighbor_iface = self._get_interface_for_neighbor(neighbor_obj_key, connect_id, parent_node_id)
        if neighbor_iface is None:
            self.logger.warning(f"  Не удалось получить интерфейс соседа {neighbor_obj_key}, создаём запасной")
            neighbor_iface = Interface(neighbor_obj_key, side=1, port=0)

        node_id_for_vertex2 = parent_node_id if neighbor_obj_key.obj_type == TYPE_CUSTOMER else None
        self._add_edge(current_iface, neighbor_iface, connect_id,
                       node_id_for_vertex2=node_id_for_vertex2)

        # Проверка фильтров для соседа
        if neighbor_obj_key.obj_type == TYPE_FIBER:
            fiber_id = int(neighbor_obj_key.id)
            neighbor_node_id = self._get_node_id_for_interface(neighbor_iface)
            if self._should_stop_at_fiber(fiber_id, neighbor_node_id):
                self.logger.debug(f"  Волокно {fiber_id} под фильтром, не продолжаем")
                return

        neighbor_obj = self._load_object(neighbor_obj_key)
        neighbor_node_id = self._get_node_id_from_obj(neighbor_obj)
        if neighbor_node_id is not None and self._should_stop_at_node(neighbor_node_id):
            self.logger.debug(f"  Узел {neighbor_node_id} соседа в excluded_nodes, не продолжаем")
            return

        if (neighbor_obj_key.obj_type != TYPE_CUSTOMER and
            neighbor_iface not in visited_interfaces):
            visited_interfaces.add(neighbor_iface)
            queue.append((neighbor_iface, obj))

    def _process_side_object(self, obj: ObjKey, comms: List[Commutation.Get_data],
                             current_iface: Interface, visited_interfaces: Set[Interface],
                             queue: deque) -> None:
        """
        Обрабатывает объекты со сторонами (кросс, кабель, сплиттер, CWDM).
        Для кроссов — только активный порт (тот, через который пришли).
        Для кабелей — транзит через противоположную сторону.
        Для сплиттеров и CWDM — полносвязные внутренние рёбра и обработка всех внешних коммутаций.
        """
        self.logger.debug(f"Обработка объекта со сторонами {obj}")

        # Разделяем записи на обычные и finish
        normal_records = []
        finish_records = []
        for rec in comms:
            if getattr(rec, 'clps_last', None) == 'finish':
                finish_records.append(rec)
            else:
                normal_records.append(rec)

        if finish_records:
            self._finish_data.setdefault(obj, []).extend(finish_records)

        current_node_id = self._get_node_id_for_interface(current_iface)
        if current_node_id is not None and self._should_stop_at_node(current_node_id):
            self.logger.debug(f"  Узел {current_node_id} в excluded_nodes, останавливаемся")
            return

        # ----- КРОССЫ (только активный порт) -----
        if obj.obj_type == TYPE_CROSS:
            # Определяем активный порт
            if self._start_obj_key == obj and self._start_iface is not None:
                active_port = self._start_iface.port
                self.logger.debug(f"  Кросс является стартовым, активный порт: {active_port}")
            else:
                active_port = current_iface.port
                self.logger.debug(f"  Кросс не стартовый, активный порт: {active_port} (порт входа)")

            # Внутреннее ребро только для активного порта
            iface1 = Interface(obj, 1, active_port)
            iface2 = Interface(obj, 2, active_port)
            self.logger.debug(f"  Внутреннее ребро между {iface1} и {iface2}")
            self._add_edge(iface1, iface2, 0, is_internal=True)

            # Обрабатываем только внешние коммутации с портом == active_port
            parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
            for rec in normal_records:
                port = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if port != active_port:
                    continue

                neighbor_key = self._get_neighbor_obj_key(rec)
                if neighbor_key is None:
                    continue
                connect_id = rec.connect_id
                side = int(rec.clps_first) if rec.clps_first is not None else 1
                obj_iface = Interface(obj, side, active_port)

                neighbor_iface = self._get_interface_for_neighbor(neighbor_key, connect_id, parent_node_id)
                if neighbor_iface is None:
                    self.logger.warning(f"  Не удалось получить интерфейс для соседа {neighbor_key}, создаём запасной")
                    neighbor_iface = Interface(neighbor_key, side=1, port=0)

                node_id_for_vertex2 = parent_node_id if neighbor_key.obj_type == TYPE_CUSTOMER else None
                self._add_edge(obj_iface, neighbor_iface, connect_id,
                               node_id_for_vertex2=node_id_for_vertex2)

                # Проверка фильтров
                if neighbor_key.obj_type == TYPE_FIBER:
                    fiber_id = int(neighbor_key.id)
                    neigh_node_id = self._get_node_id_for_interface(neighbor_iface)
                    if self._should_stop_at_fiber(fiber_id, neigh_node_id):
                        self.logger.debug(f"  Волокно {fiber_id} под фильтром, не продолжаем")
                        continue

                neigh_obj = self._load_object(neighbor_key)
                neigh_node_id = self._get_node_id_from_obj(neigh_obj)
                if neigh_node_id is not None and self._should_stop_at_node(neigh_node_id):
                    self.logger.debug(f"  Узел {neigh_node_id} соседа в excluded_nodes, не продолжаем")
                    continue

                if (neighbor_key.obj_type != TYPE_CUSTOMER and
                    neighbor_iface not in visited_interfaces):
                    visited_interfaces.add(neighbor_iface)
                    queue.append((neighbor_iface, obj))
            return

        # ----- КАБЕЛИ (транзит) -----
        if obj.obj_type == TYPE_FIBER:
            if self._should_stop_at_fiber(int(obj.id), current_node_id):
                self.logger.debug(f"  Волокно {obj.id} под фильтром, не продолжаем")
                return

            record = self._find_record_for_interface(normal_records, current_iface)
            if record is None:
                self.logger.debug(f"  Не найдена запись для {current_iface}")
                return

            neighbor_obj_key = self._get_neighbor_obj_key(record)
            if neighbor_obj_key is None:
                self.logger.warning(f"  Не удалось получить ключ соседа из записи {record}")
                return

            connect_id = record.connect_id
            self.logger.debug(f"  Сосед по текущей стороне: {neighbor_obj_key}, connect_id={connect_id}")

            parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
            neighbor_iface = self._get_interface_for_neighbor(neighbor_obj_key, connect_id, parent_node_id)
            if neighbor_iface is None:
                self.logger.warning(f"  Не удалось получить интерфейс соседа {neighbor_obj_key}, создаём запасной")
                neighbor_iface = Interface(neighbor_obj_key, side=1, port=0)

            node_id_for_vertex2 = parent_node_id if neighbor_obj_key.obj_type == TYPE_CUSTOMER else None
            self._add_edge(current_iface, neighbor_iface, connect_id,
                           node_id_for_vertex2=node_id_for_vertex2)

            # Проверка фильтров для соседа
            if neighbor_obj_key.obj_type == TYPE_FIBER:
                neigh_fiber_id = int(neighbor_obj_key.id)
                neigh_node_id = self._get_node_id_for_interface(neighbor_iface)
                if self._should_stop_at_fiber(neigh_fiber_id, neigh_node_id):
                    self.logger.debug(f"  Волокно {neigh_fiber_id} под фильтром, не продолжаем")
                    return

            neighbor_obj = self._load_object(neighbor_obj_key)
            neighbor_node_id = self._get_node_id_from_obj(neighbor_obj)
            if neighbor_node_id is not None and self._should_stop_at_node(neighbor_node_id):
                self.logger.debug(f"  Узел {neighbor_node_id} соседа в excluded_nodes, не продолжаем")
                return

            if (neighbor_obj_key.obj_type != TYPE_CUSTOMER and
                neighbor_iface not in visited_interfaces):
                visited_interfaces.add(neighbor_iface)
                queue.append((neighbor_iface, obj))

            # Внутреннее ребро на противоположную сторону
            opposite_side = 2 if current_iface.side == 1 else 1
            opposite_iface = Interface(obj, opposite_side, current_iface.port)
            self.logger.debug(f"  Внутреннее ребро между {current_iface} и {opposite_iface}")
            self._add_edge(current_iface, opposite_iface, 0, is_internal=True)

            # Сосед по противоположной стороне
            opposite_record = self._find_record_for_interface(normal_records, opposite_iface)
            if opposite_record is None:
                self.logger.debug(f"  Нет записи на противоположной стороне")
                return

            neighbor_obj_opp = self._get_neighbor_obj_key(opposite_record)
            if neighbor_obj_opp is None:
                self.logger.warning(f"  Не удалось получить ключ соседа из записи {opposite_record}")
                return

            connect_id_opp = opposite_record.connect_id
            self.logger.debug(f"  Сосед на противоположной стороне: {neighbor_obj_opp}, connect_id={connect_id_opp}")

            parent_node_id_opp = parent_node_id
            neighbor_iface_opp = self._get_interface_for_neighbor(neighbor_obj_opp, connect_id_opp, parent_node_id_opp)
            if neighbor_iface_opp is None:
                self.logger.warning(f"  Не удалось получить интерфейс соседа {neighbor_obj_opp}, создаём запасной")
                neighbor_iface_opp = Interface(neighbor_obj_opp, side=1, port=0)

            node_id_for_vertex2_opp = parent_node_id_opp if neighbor_obj_opp.obj_type == TYPE_CUSTOMER else None
            self._add_edge(opposite_iface, neighbor_iface_opp, connect_id_opp,
                           node_id_for_vertex2=node_id_for_vertex2_opp)

            # Фильтры для соседа на противоположной стороне
            if neighbor_obj_opp.obj_type == TYPE_FIBER:
                opp_fiber_id = int(neighbor_obj_opp.id)
                opp_node_id = self._get_node_id_for_interface(neighbor_iface_opp)
                if self._should_stop_at_fiber(opp_fiber_id, opp_node_id):
                    self.logger.debug(f"  Волокно {opp_fiber_id} под фильтром, не продолжаем")
                    return

            opp_neighbor_obj = self._load_object(neighbor_obj_opp)
            opp_neighbor_node_id = self._get_node_id_from_obj(opp_neighbor_obj)
            if opp_neighbor_node_id is not None and self._should_stop_at_node(opp_neighbor_node_id):
                self.logger.debug(f"  Узел {opp_neighbor_node_id} соседа в excluded_nodes, не продолжаем")
                return

            if (neighbor_obj_opp.obj_type != TYPE_CUSTOMER and
                neighbor_iface_opp not in visited_interfaces):
                visited_interfaces.add(neighbor_iface_opp)
                queue.append((neighbor_iface_opp, obj))
            return

        # ----- СПЛИТТЕРЫ И CWDM (полносвязные) -----
        if obj.obj_type in (TYPE_SPLITTER, TYPE_CWDM):
            # Собираем все порты сторон 1 и 2
            ports_side1 = set()
            ports_side2 = set()
            for rec in normal_records:
                side = int(rec.clps_first) if rec.clps_first is not None else 0
                port = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if side == 1:
                    ports_side1.add(port)
                elif side == 2:
                    ports_side2.add(port)

            # Внутренние рёбра между всеми входами и выходами
            for p1 in ports_side1:
                iface1 = Interface(obj, 1, p1)
                for p2 in ports_side2:
                    iface2 = Interface(obj, 2, p2)
                    self.logger.debug(f"  Внутреннее ребро между {iface1} и {iface2}")
                    self._add_edge(iface1, iface2, 0, is_internal=True)

            # Обрабатываем все внешние коммутации
            parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
            for rec in normal_records:
                neighbor_key = self._get_neighbor_obj_key(rec)
                if neighbor_key is None:
                    continue
                connect_id = rec.connect_id
                side = int(rec.clps_first) if rec.clps_first is not None else 1
                port = int(rec.clps_mid) if rec.clps_mid is not None else 0
                obj_iface = Interface(obj, side, port)

                neighbor_iface = self._get_interface_for_neighbor(neighbor_key, connect_id, parent_node_id)
                if neighbor_iface is None:
                    self.logger.warning(f"  Не удалось получить интерфейс для соседа {neighbor_key}, создаём запасной")
                    neighbor_iface = Interface(neighbor_key, side=1, port=0)

                node_id_for_vertex2 = parent_node_id if neighbor_key.obj_type == TYPE_CUSTOMER else None
                self._add_edge(obj_iface, neighbor_iface, connect_id,
                               node_id_for_vertex2=node_id_for_vertex2)

                # Проверка фильтров
                if neighbor_key.obj_type == TYPE_FIBER:
                    fiber_id = int(neighbor_key.id)
                    neigh_node_id = self._get_node_id_for_interface(neighbor_iface)
                    if self._should_stop_at_fiber(fiber_id, neigh_node_id):
                        self.logger.debug(f"  Волокно {fiber_id} под фильтром, не продолжаем")
                        continue

                neigh_obj = self._load_object(neighbor_key)
                neigh_node_id = self._get_node_id_from_obj(neigh_obj)
                if neigh_node_id is not None and self._should_stop_at_node(neigh_node_id):
                    self.logger.debug(f"  Узел {neigh_node_id} соседа в excluded_nodes, не продолжаем")
                    continue

                if (neighbor_key.obj_type != TYPE_CUSTOMER and
                    neighbor_iface not in visited_interfaces):
                    visited_interfaces.add(neighbor_iface)
                    queue.append((neighbor_iface, obj))
            return

    # ------------------------------------------------------------------------
    # Вспомогательные методы для поиска записей и соседей
    # ------------------------------------------------------------------------

    def _find_record_for_interface(self, comms: List[Commutation.Get_data],
                                   iface: Interface) -> Optional[Commutation.Get_data]:
        """Находит запись в списке коммутаций, соответствующую интерфейсу."""
        is_terminal = (iface.obj.obj_type in TERMINAL_TYPES)
        for rec in comms:
            if is_terminal:
                if rec.clps_first is not None and int(rec.clps_first) == iface.port:
                    return rec
            else:
                if (rec.clps_first is not None and int(rec.clps_first) == iface.side and
                    rec.clps_mid is not None and int(rec.clps_mid) == iface.port):
                    return rec
        return None

    def _get_neighbor_obj_key(self, record: Commutation.Get_data) -> Optional[ObjKey]:
        """Извлекает ObjKey соседа из записи коммутации."""
        obj_type_str = record.object_type
        obj_id = record.object_id
        obj_uuid = record.object_uuid
        if not obj_type_str:
            return None
        return self._make_obj_key(obj_type_str, obj_id, obj_uuid)

    def _make_obj_key(self, type_str: str, obj_id: Optional[int],
                      obj_uuid: Optional[str] = None) -> Optional[ObjKey]:
        """Создаёт ObjKey из строки типа и ID (для кроссов — UUID)."""
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
        В коммутациях соседа ищет запись с данным connect_id и возвращает Interface.
        Для абонента всегда возвращает side=1, port=0.
        Для устройств ищет реальный порт по connect_id.
        """
        # Абонент – всегда порт 0
        if neighbor_obj_key.obj_type == TYPE_CUSTOMER:
            return Interface(neighbor_obj_key, side=1, port=0)

        # Устройства (OLT, switch, ONU) – ищем реальный порт
        if neighbor_obj_key.obj_type in DEVICE_TYPES:
            neighbor_comms = self._load_commutations(neighbor_obj_key)
            if not neighbor_comms:
                self.logger.warning(f"Нет коммутаций для устройства {neighbor_obj_key}")
                return Interface(neighbor_obj_key, side=1, port=0)
            for rec in neighbor_comms:
                if int(rec.connect_id) == int(connect_id):
                    port = int(rec.clps_first) if rec.clps_first is not None else 0
                    return Interface(neighbor_obj_key, side=1, port=port)
            self.logger.warning(f"Не найден порт для устройства {neighbor_obj_key} по connect_id {connect_id}")
            return Interface(neighbor_obj_key, side=1, port=0)

        # Объекты со сторонами
        neighbor_comms = self._load_commutations(neighbor_obj_key)
        if not neighbor_comms:
            self.logger.debug(f"Нет коммутаций для соседа {neighbor_obj_key}")
            return None

        for rec in neighbor_comms:
            if int(rec.connect_id) == int(connect_id):
                side = int(rec.clps_first) if rec.clps_first is not None else 1
                port = int(rec.clps_mid) if rec.clps_mid is not None else 0
                return Interface(neighbor_obj_key, side, port)

        self.logger.debug(f"Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj_key}")
        return None

    # ------------------------------------------------------------------------
    # Определение конечных вершин и finish-данных
    # ------------------------------------------------------------------------

    def _mark_terminate_vertices(self) -> None:
        """
        Определяет для каждой вершины, является ли она конечной в исходной топологии
        (без учёта фильтров). Для конечных вершин сохраняет finish-данные.
        Логика:
        - OLT, switch, терминальные объекты (абоненты, ONU) – всегда конечны.
        - Кроссы и кабели – конечны, если на противоположной стороне нет коммутации или сосед терминальный.
        - Сплиттеры и CWDM – конечны, если нет внешних коммутаций к не-терминальным объектам.
        """
        for v in self.vs:
            obj_type = v['obj_type']
            obj_id = v['obj_id']
            side = v['side'] if 'side' in v.attributes() else 1
            port = v['port'] if 'port' in v.attributes() else 0

            # OLT, switch, терминальные объекты (абоненты, ONU) – всегда конечны
            if obj_type in (TYPE_OLT, TYPE_SWITCH) or obj_type in TERMINAL_TYPES:
                v['terminate_vertex'] = True
                obj_key = ObjKey(obj_type, obj_id)
                v['finish_data'] = self._finish_data.get(obj_key, [])
                continue

            obj_key = ObjKey(obj_type, obj_id)
            comms = self._load_commutations(obj_key)
            if not comms:
                v['terminate_vertex'] = True
                v['finish_data'] = self._finish_data.get(obj_key, [])
                continue

            # --- КРОССЫ И КАБЕЛИ ---
            if obj_type in (TYPE_CROSS, TYPE_FIBER):
                opposite_side = 2 if side == 1 else 1
                opposite_record = None
                for rec in comms:
                    if rec.clps_first is not None and int(rec.clps_first) == opposite_side and \
                       rec.clps_mid is not None and int(rec.clps_mid) == port:
                        opposite_record = rec
                        break

                if opposite_record is None:
                    v['terminate_vertex'] = True
                    v['finish_data'] = self._finish_data.get(obj_key, [])
                    continue

                neighbor_obj_key = self._get_neighbor_obj_key(opposite_record)
                if neighbor_obj_key is None:
                    v['terminate_vertex'] = True
                    v['finish_data'] = self._finish_data.get(obj_key, [])
                    continue

                v['terminate_vertex'] = (neighbor_obj_key.obj_type in TERMINAL_TYPES)
                if v['terminate_vertex']:
                    v['finish_data'] = self._finish_data.get(obj_key, [])
                else:
                    v['finish_data'] = []
                continue

            # --- СПЛИТТЕРЫ И CWDM ---
            if obj_type in (TYPE_SPLITTER, TYPE_CWDM):
                has_non_terminal_neighbor = False
                for rec in comms:
                    neighbor_key = self._get_neighbor_obj_key(rec)
                    if neighbor_key is not None and neighbor_key.obj_type not in TERMINAL_TYPES:
                        has_non_terminal_neighbor = True
                        break
                v['terminate_vertex'] = not has_non_terminal_neighbor
                if v['terminate_vertex']:
                    v['finish_data'] = self._finish_data.get(obj_key, [])
                else:
                    v['finish_data'] = []
                continue

            # Остальные объекты – конечны по умолчанию
            v['terminate_vertex'] = True
            v['finish_data'] = self._finish_data.get(obj_key, [])

    # ------------------------------------------------------------------------
    # Построение графа
    # ------------------------------------------------------------------------

    def build(self, object_type: str, object_id: Union[int, str], 
              port: Optional[int] = None,
              side: Optional[int] = None,
              included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'CGraph':
        """
        Строит полный граф коммутаций от заданного объекта с учётом фильтров.

        Args:
            object_type: тип начального объекта (olt, switch, fiber, cross, splitter, cwdm, customer)
            object_id: идентификатор объекта
            port: номер порта (для кабеля – порядковый номер волокна)
            side: сторона (1 или 2). Если None, для объектов со сторонами строится от обеих сторон.
            included_fibers: ID кабелей, через которые разрешён проход (только на стартовом узле)
            excluded_fibers: ID кабелей, на которых обход останавливается (всегда)
            excluded_nodes: ID узлов, на которых обход останавливается (всегда)
        """
        self.logger.info(f"=== ПОСТРОЕНИЕ ГРАФА CGraph ОТ {object_type}:{object_id} (port={port}, side={side}) ===")

        # Приводим фильтры к множествам
        self._included_fibers = self._normalize_set(included_fibers)
        self._excluded_fibers = self._normalize_set(excluded_fibers)
        self._excluded_nodes = self._normalize_set(excluded_nodes)

        start_interfaces: List[Interface] = []

        # Определяем стартовый узел
        start_obj_key = ObjKey(object_type, object_id)
        start_obj = self._load_object(start_obj_key)
        self._start_node_id = self._get_node_id_from_obj(start_obj) if start_obj else None
        self.logger.debug(f"Стартовый node_id: {self._start_node_id}")

        # Специальная обработка для OLT без порта – все PON-порты
        if object_type == TYPE_OLT and port is None:
            olt_obj = self._load_object(ObjKey(TYPE_OLT, object_id))
            if olt_obj is None:
                self.logger.error(f"Не удалось загрузить OLT {object_id}")
                return self
            ifaces = getattr(olt_obj, 'ifaces', {})
            pon_ports = []
            if isinstance(ifaces, dict):
                for port_num, iface_info in ifaces.items():
                    if iface_info.get('ifType') == 6 or iface_info.get('ifTypeText') == 'gpon':
                        pon_ports.append(int(port_num))
            if not pon_ports:
                self.logger.warning(f"Не найдены PON-порты для OLT {object_id}")
                return self
            self.logger.info(f"Найдено {len(pon_ports)} PON-портов: {pon_ports}")
            for p in pon_ports:
                start_interfaces.append(Interface(ObjKey(TYPE_OLT, object_id), side=1, port=p))

        # Абонент без порта – все его коммутации
        elif object_type == TYPE_CUSTOMER and port is None:
            obj_key = ObjKey(TYPE_CUSTOMER, object_id)
            comms = self._load_commutations(obj_key)
            if not comms:
                self.logger.warning(f"У абонента {object_id} нет коммутаций")
                return self
            self.logger.info(f"Найдено {len(comms)} коммутаций абонента")
            for rec in comms:
                if getattr(rec, 'clps_last', None) == 'finish':
                    continue
                p = int(rec.clps_first) if rec.clps_first is not None else 0
                start_interfaces.append(Interface(obj_key, side=1, port=p))

        # Кабель – ищем записи с указанным порядковым номером волокна
        elif object_type == TYPE_FIBER:
            obj_key = ObjKey(TYPE_FIBER, object_id)
            comms = self._load_commutations(obj_key)
            if not comms:
                self.logger.warning(f"У кабеля {object_id} нет коммутаций")
                return self

            if port is not None:
                found = False
                for rec in comms:
                    if getattr(rec, 'clps_last', None) == 'finish':
                        continue
                    iface_num = None
                    if hasattr(rec, 'interface'):
                        iface_num = getattr(rec, 'interface')
                    elif hasattr(rec, 'iface'):
                        iface_num = getattr(rec, 'iface')
                    elif hasattr(rec, 'number'):
                        iface_num = getattr(rec, 'number')

                    if iface_num is not None and int(iface_num) == port:
                        if side is None:
                            s = int(rec.clps_first) if rec.clps_first is not None else 1
                        else:
                            s = side
                        fiber_id = int(rec.clps_mid) if rec.clps_mid is not None else 0
                        start_interfaces.append(Interface(obj_key, side=s, port=fiber_id))
                        found = True
                        self.logger.info(f"Найдена коммутация кабеля {object_id} для волокна #{port} (ID={fiber_id}) side={s}")
                        break

                if not found:
                    self.logger.warning(f"Не найдена коммутация для кабеля {object_id} с порядковым номером волокна {port}")
                    return self
            else:
                self.logger.info(f"Порт не указан, строим от всех волокон кабеля {object_id}")
                for rec in comms:
                    if getattr(rec, 'clps_last', None) == 'finish':
                        continue
                    s = int(rec.clps_first) if rec.clps_first is not None else 1
                    fiber_id = int(rec.clps_mid) if rec.clps_mid is not None else 0
                    start_interfaces.append(Interface(obj_key, side=s, port=fiber_id))

        # Общий случай – один интерфейс
        else:
            obj_key = ObjKey(object_type, object_id)
            if object_type in SIDE_TYPES and side is not None:
                s = side
            else:
                s = 1
            default_port = 0 if object_type == TYPE_CUSTOMER else 1
            p = port if port is not None else default_port
            start_interfaces.append(Interface(obj_key, side=s, port=p))

        if not start_interfaces:
            self.logger.warning("Нет стартовых интерфейсов для построения графа")
            return self

        # Запоминаем стартовый объект и интерфейс для логики кросса
        self._start_obj_key = start_interfaces[0].obj
        self._start_iface = start_interfaces[0]

        # Запускаем BFS-обход
        self._build_from_interfaces(start_interfaces)

        # Определяем конечные вершины и finish-данные
        self._mark_terminate_vertices()

        self._update_directed_flag()
        self.logger.info("=== ПОСТРОЕНИЕ ЗАВЕРШЕНО ===")
        return self

    @staticmethod
    def _normalize_set(value: Optional[Union[int, List[int], Set[int]]]) -> Optional[Set[int]]:
        if value is None:
            return None
        if isinstance(value, (int, str)):
            return {int(value)}
        return set(value)

    def _build_from_interfaces(self, start_interfaces: List[Interface]) -> None:
        """BFS-обход от стартовых интерфейсов."""
        queue = deque()
        visited_interfaces: Set[Interface] = set()

        # Сортировка для детерминизма
        for iface in sorted(start_interfaces, key=lambda x: (x.obj.obj_type, x.obj.id, x.side, x.port)):
            if iface not in visited_interfaces:
                visited_interfaces.add(iface)
                queue.append((iface, None))

        while queue:
            current_iface, parent_obj = queue.popleft()
            if current_iface not in visited_interfaces:
                continue

            obj = current_iface.obj
            comms = self._load_commutations(obj)
            if not comms:
                continue

            # Отфильтровываем finish-записи для построения рёбер
            normal_comms = [r for r in comms if getattr(r, 'clps_last', None) != 'finish']

            if obj.obj_type in TERMINAL_TYPES:
                self._process_terminal_object(obj, comms, current_iface, visited_interfaces, queue)
            elif obj.obj_type in SIDE_TYPES:
                self._process_side_object(obj, comms, current_iface, visited_interfaces, queue)
            else:
                self.logger.warning(f"Неизвестный тип объекта: {obj.obj_type}")

    # ------------------------------------------------------------------------
    # Направление графа (directed)
    # ------------------------------------------------------------------------

    def _update_directed_flag(self) -> None:
        """Определяет, является ли граф направленным (наличие сплиттеров, CWDM, абонентов)."""
        has_splitter = any(v['obj_type'] == TYPE_SPLITTER for v in self.vs)
        has_cwdm = any(v['obj_type'] == TYPE_CWDM for v in self.vs)
        has_customer = any(v['obj_type'] == TYPE_CUSTOMER for v in self.vs)
        self._directed = has_splitter or has_cwdm or has_customer

    @property
    def directed(self) -> bool:
        return self._directed

    def to_dict(self) -> dict:
        """
        Преобразует граф в сериализуемый словарь.
        Сохраняет вершины, рёбра, _vertex_index, _directed, _finish_data.
        """
        vertices = []
        for v in self.vs:
            attrs = {key: v[key] for key in v.attributes()}
            # Удаляем несериализуемые объекты (например, api_obj может содержать ссылки на клиент)
            if 'api_obj' in attrs:
                # Пытаемся сохранить api_obj как словарь, если это возможно
                try:
                    # Если это модель, можно попробовать преобразовать в dict
                    if hasattr(attrs['api_obj'], 'dict'):
                        attrs['api_obj'] = attrs['api_obj'].dict()
                    else:
                        attrs['api_obj'] = str(attrs['api_obj'])
                except:
                    attrs['api_obj'] = None
            vertices.append(attrs)

        edges = []
        for e in self.es:
            attrs = {key: e[key] for key in e.attributes()}
            attrs['source'] = e.source
            attrs['target'] = e.target
            edges.append(attrs)

        vertex_index = {}
        for iface, idx in self._vertex_index.items():
            # Преобразуем Interface в сериализуемый кортеж
            vertex_index[(iface.obj.obj_type, iface.obj.id, iface.side, iface.port)] = idx

        finish_data = {}
        for obj_key, comms in self._finish_data.items():
            # Преобразуем ObjKey в кортеж, а коммутации в словари
            key = (obj_key.obj_type, obj_key.id)
            finish_data[key] = [rec.dict() if hasattr(rec, 'dict') else str(rec) for rec in comms]

        return {
            'vertices': vertices,
            'edges': edges,
            'vertex_index': vertex_index,
            'directed': self._directed,
            'finish_data': finish_data,
        }

    @classmethod
    def from_dict(cls, data: dict, client: WorkerNetClient, cache: DataCache) -> 'CGraph':
        """Восстанавливает граф из словаря."""
        cgraph = cls(client, cache=cache)
        cgraph._directed = data.get('directed', False)

        # Восстанавливаем вершины
        for attrs in data.get('vertices', []):
            # Если api_obj был сохранён как dict, можно попытаться восстановить модель
            # Просто сохраняем как есть
            idx = cgraph.add_vertex(**attrs).index

        # Восстанавливаем рёбра
        for edge_attrs in data.get('edges', []):
            source = edge_attrs.pop('source')
            target = edge_attrs.pop('target')
            cgraph.add_edge(source, target, **edge_attrs)

        # Восстанавливаем _vertex_index
        vertex_index = data.get('vertex_index', {})
        for (obj_type, obj_id, side, port), idx in vertex_index.items():
            iface = Interface(ObjKey(obj_type, obj_id), side, port)
            cgraph._vertex_index[iface] = idx

        # Восстанавливаем _finish_data
        finish_data = data.get('finish_data', {})
        for (obj_type, obj_id), comms_data in finish_data.items():
            obj_key = ObjKey(obj_type, obj_id)
            # Восстанавливаем объекты Commutation из словарей
            # Здесь нужно использовать модель Commutation.Get_data.from_dict или создать вручную
            # Для простоты пропустим, так как finish_data не критична для структуры графа
            cgraph._finish_data[obj_key] = []  # пока пустой список

        return cgraph

    def __repr__(self) -> str:
        return f"CGraph(interfaces={self.vcount()}, commutations={self.ecount()}, directed={self._directed})"


# =============================================================================
# Граф сооружений связи (FNGraph)
# =============================================================================

class FNGraph(ig.Graph):
    """
    Граф сооружений связи и кабелей.
    Вершины — node_id (сооружения связи), рёбра — кабели (fiber_id).
    Поддерживает фильтрацию по волокнам и узлам при построении.
    Может быть построен как из CGraph, так и напрямую через API (BFS по узлам).
    """
    def __init__(self, client: WorkerNetClient,
                 commutation_graph: Optional[CGraph] = None,
                 cache: Optional[DataCache] = None,
                 **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self._cache = cache if cache is not None else _data_cache
        self._commutation_graph = commutation_graph
        self._vertex_index: Dict[int, int] = {}           # node_id -> индекс в igraph
        self._node_fibers_cache: Dict[int, List[Any]] = {}  # кэш кабелей для узлов
        self._built = False

        self._included_fibers: Optional[Set[int]] = None
        self._excluded_fibers: Optional[Set[int]] = None
        self._excluded_nodes: Optional[Set[int]] = None

    # ------------------------------------------------------------------------
    # Загрузка данных через DataCache
    # ------------------------------------------------------------------------

    def _load_node(self, node_id: int) -> Optional[Any]:
        return self._cache.get_node(self.client, node_id)

    def _load_fiber(self, fiber_id: int) -> Optional[Any]:
        return self._cache.get_fiber(self.client, fiber_id)

    def _load_fibers_for_node(self, node_id: int) -> List[Any]:
        """
        Загружает все кабели, связанные с узлом, через API (с локальным кэшированием).
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
        # Сохраняем каждый кабель в общий кэш
        for fiber in fibers:
            fiber_id = getattr(fiber, 'code', None)
            if fiber_id is not None:
                self._cache.set_object('fiber', fiber_id, fiber)
        return fibers

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, node_id: int) -> int:
        if node_id in self._vertex_index:
            return self._vertex_index[node_id]
        node_obj = self._load_node(node_id)
        attrs = {
            'node_id': node_id,
            'name': f"node:{node_id}",
            'api_obj': node_obj,
        }
        if node_obj is not None:
            # Копируем полезные атрибуты узла
            for attr in ['address_id', 'coordinates', 'type', 'number', 'comment', 'location', 'is_planned']:
                if hasattr(node_obj, attr):
                    attrs[attr] = getattr(node_obj, attr)
        idx = self.add_vertex(**attrs).index
        self._vertex_index[node_id] = idx
        return idx

    def _add_edge(self, node1_id: int, node2_id: int, fiber_id: int) -> None:
        if node1_id == node2_id:
            self.logger.debug(f"Петля для кабеля {fiber_id}, пропускаем")
            return
        idx1 = self._add_vertex(node1_id)
        idx2 = self._add_vertex(node2_id)
        fiber_obj = self._load_fiber(fiber_id)
        self.add_edge(idx1, idx2, fiber_id=fiber_id, api_obj=fiber_obj)

    # ------------------------------------------------------------------------
    # Построение из CGraph
    # ------------------------------------------------------------------------

    def _build_from_commutation_graph(self) -> None:
        if self._commutation_graph is None:
            self.logger.error("CGraph не передан")
            return

        cg = self._commutation_graph
        fiber_groups: Dict[int, Set[int]] = defaultdict(set)

        for v in cg.vs:
            if v['obj_type'] != 'fiber':
                continue
            fiber_id = int(v['obj_id'])
            node_id = v['node_id'] if 'node_id' in v.attributes() else None
            if node_id is None:
                self.logger.warning(f"У вершины кабеля {fiber_id} нет node_id")
                continue

            # Применяем фильтры
            if self._included_fibers is not None and fiber_id not in self._included_fibers:
                continue
            if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
                continue
            if self._excluded_nodes is not None and node_id in self._excluded_nodes:
                continue

            fiber_groups[fiber_id].add(node_id)

        for fiber_id, nodes in fiber_groups.items():
            node_list = list(nodes)
            if len(node_list) == 2:
                self._add_edge(node_list[0], node_list[1], fiber_id)
            elif len(node_list) == 1:
                self.logger.debug(f"Кабель {fiber_id} имеет только один узел")
            else:
                self.logger.warning(f"Кабель {fiber_id} имеет более двух узлов")

    # ------------------------------------------------------------------------
    # Построение через API (BFS по узлам)
    # ------------------------------------------------------------------------

    def _build_from_api(self, start_node_id: int) -> None:
        visited_nodes: Set[int] = set()
        queue = deque([start_node_id])

        while queue:
            current_node = queue.popleft()
            if current_node in visited_nodes:
                continue
            visited_nodes.add(current_node)

            if self._excluded_nodes is not None and current_node in self._excluded_nodes:
                self.logger.debug(f"Узел {current_node} в excluded_nodes, останавливаемся")
                continue

            self._add_vertex(current_node)

            fibers = self._load_fibers_for_node(current_node)
            for fiber in fibers:
                fiber_id = getattr(fiber, 'code', None)
                if fiber_id is None:
                    continue

                if self._included_fibers is not None and fiber_id not in self._included_fibers:
                    continue
                if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
                    continue

                node1 = getattr(fiber, 'node1_id', None)
                node2 = getattr(fiber, 'node2_id', None)
                if node1 is None or node2 is None:
                    continue

                if node1 == current_node:
                    neighbor = node2
                elif node2 == current_node:
                    neighbor = node1
                else:
                    continue

                if self._excluded_nodes is not None and neighbor in self._excluded_nodes:
                    self.logger.debug(f"Соседний узел {neighbor} в excluded_nodes, не добавляем ребро")
                    continue

                self._add_edge(current_node, neighbor, fiber_id)
                if neighbor not in visited_nodes:
                    queue.append(neighbor)

    # ------------------------------------------------------------------------
    # Основной метод построения
    # ------------------------------------------------------------------------

    def build(self, start_node_id: int,
              included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'FNGraph':
        """
        Строит граф сооружений связи.

        Args:
            start_node_id: ID начального узла.
            included_fibers: ID кабелей, которые разрешены (если None – все).
            excluded_fibers: ID кабелей, которые запрещены.
            excluded_nodes: ID узлов, на которых обход останавливается.
        """
        self.logger.info("=== ПОСТРОЕНИЕ ГРАФА FN ===")

        self._included_fibers = self._normalize_set(included_fibers)
        self._excluded_fibers = self._normalize_set(excluded_fibers)
        self._excluded_nodes = self._normalize_set(excluded_nodes)

        if self._commutation_graph is not None:
            self.logger.info("Построение из CGraph")
            self._build_from_commutation_graph()
        else:
            self.logger.info("Построение через API")
            self._build_from_api(start_node_id)

        self._built = True
        self.logger.info("=== ПОСТРОЕНИЕ FN ЗАВЕРШЕНО ===")
        return self

    @staticmethod
    def _normalize_set(value: Optional[Union[int, List[int], Set[int]]]) -> Optional[Set[int]]:
        if value is None:
            return None
        if isinstance(value, (int, str)):
            return {int(value)}
        return set(value)

    # ------------------------------------------------------------------------
    # Аналитические методы
    # ------------------------------------------------------------------------

    def find_fibers_for_node(self, node_id: int) -> List[int]:
        idx = self._vertex_index.get(node_id)
        if idx is None:
            return []
        fiber_ids = []
        for eid in self.incident(idx, mode='all'):
            fiber_id = self.es[eid]['fiber_id']
            if fiber_id is not None:
                fiber_ids.append(fiber_id)
        return fiber_ids

    def get_fiber_edges(self) -> List[Dict[str, Any]]:
        edges = []
        for edge in self.es:
            v1, v2 = edge.tuple
            edges.append({
                'node1_id': self.vs[v1]['node_id'],
                'node2_id': self.vs[v2]['node_id'],
                'fiber_id': edge['fiber_id'],
            })
        return edges

    def stats(self) -> Dict[str, Any]:
        return {
            'num_vertices': self.vcount(),
            'num_edges': self.ecount(),
            'start_node_id': self.vs[0]['node_id'] if self.vcount() > 0 else None,
        }

    def export_graphml(self, filename: str) -> None:
        self.write_graphml(filename)

    # ------------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------------

    def to_dict(self) -> dict:
        vertices = []
        for v in self.vs:
            attrs = {key: v[key] for key in v.attributes()}
            vertices.append(attrs)
        edges = []
        for e in self.es:
            attrs = {key: e[key] for key in e.attributes()}
            attrs['source'] = e.source
            attrs['target'] = e.target
            edges.append(attrs)
        return {
            'vertices': vertices,
            'edges': edges,
            'vertex_index': self._vertex_index,
        }

    @classmethod
    def from_dict(cls, data: dict, client: WorkerNetClient, cache: DataCache) -> 'FNGraph':
        fngraph = cls(client, cache=cache)
        fngraph._vertex_index = data.get('vertex_index', {})
        for attrs in data.get('vertices', []):
            idx = fngraph.add_vertex(**attrs).index
        for edge_attrs in data.get('edges', []):
            source = edge_attrs.pop('source')
            target = edge_attrs.pop('target')
            fngraph.add_edge(source, target, **edge_attrs)
        return fngraph

    def __repr__(self) -> str:
        return f"FNGraph(nodes={self.vcount()}, fibers={self.ecount()})"