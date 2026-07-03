# simpleworkernet/utils/graph.py
"""
Модуль для построения графа коммутаций (CGraph) и графа сооружений связи (FNGraph).
Реализованы как наследники igraph.Graph.

Вершины графа коммутаций — это интерфейсы (объект + сторона + порт).
Для устройств (OLT, switch, ONU) и абонентов (customer) сторона не имеет значения,
но для единообразия используется side=1.
Для объектов со сторонами (кросс, кабель, сплиттер, CWDM) сторона = 1 или 2.

Граф сооружений связи (FNGraph) — вершины: node_id, рёбра: fiber_id.

Все данные, загруженные по API, сохраняются в глобальный кэш DataCache.
Вершины и рёбра содержат атрибут 'api_obj' с полным объектом (моделью),
что позволяет получить любую информацию без дополнительных запросов.

Поддерживаются фильтры при построении CGraph:
- included_fibers (Set[int]): если не None, обход продолжается только через эти волокна,
  НО только пока мы находимся в стартовом узле (начальном сооружении связи).
  Как только переходим на другой узел, included_fibers игнорируется.
- excluded_fibers (Set[int]): если не None, обход останавливается на этих волокнах (они становятся конечными вершинами) – применяется всегда.
- excluded_nodes (Set[int]): если не None, обход останавливается на указанных узлах (сооружениях связи) – применяется всегда.
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
    _instance = None
    _objects: Dict[Tuple[str, Union[int, str]], Any] = {}
    _commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        return self._objects.get((obj_type, obj_id))

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        self._objects[(obj_type, obj_id)] = obj

    def get_or_load_object(self, obj_type: str, obj_id: Union[int, str],
                           loader: Callable[[], Any]) -> Any:
        key = (obj_type, obj_id)
        obj = self._objects.get(key)
        if obj is None:
            obj = loader()
            if obj is not None:
                self._objects[key] = obj
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

DEVICE_TYPES = {TYPE_SWITCH, TYPE_OLT, TYPE_ONU}
SIDE_TYPES = {TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER, TYPE_CWDM}
TERMINAL_TYPES = {TYPE_CUSTOMER} | DEVICE_TYPES


# ===========================================================================
# Вспомогательные классы
# ===========================================================================

@dataclass(frozen=True)
class ObjKey:
    obj_type: str
    id: Union[int, str]

    def __str__(self) -> str:
        return f"{self.obj_type}:{self.id}"


@dataclass(frozen=True)
class Interface:
    obj: ObjKey
    side: int
    port: int

    def __str__(self) -> str:
        return f"{self.obj} side={self.side} port={self.port}"


# ===========================================================================
# Граф коммутаций (CGraph) с поддержкой фильтров
# ===========================================================================

class CGraph(ig.Graph):
    """
    Граф коммутаций, где вершины — интерфейсы, рёбра — коммутации.
    Поддерживает фильтрацию по волокнам (included_fibers, excluded_fibers)
    и по узлам (excluded_nodes) при построении.
    """
    def __init__(self, client: WorkerNetClient, cache: Optional[DataCache] = None, **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self._cache = cache if cache is not None else _data_cache
        self._vertex_index: Dict[Interface, int] = {}
        self._directed: bool = False

        # Фильтры и стартовые данные, устанавливаемые при вызове build()
        self._included_fibers: Optional[Set[int]] = None
        self._excluded_fibers: Optional[Set[int]] = None
        self._excluded_nodes: Optional[Set[int]] = None
        self._start_node_id: Optional[int] = None
        self._start_obj_key: Optional[ObjKey] = None
        self._start_iface: Optional[Interface] = None

    # ------------------------------------------------------------------------
    # Загрузка данных
    # ------------------------------------------------------------------------

    def _load_object(self, obj_key: ObjKey) -> Optional[Any]:
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        def loader() -> Optional[Any]:
            try:
                if obj_type in DEVICE_TYPES:
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
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        if obj_type in DEVICE_TYPES:
            api_type = TYPE_SWITCH
        else:
            api_type = obj_type

        if not api_type:
            return []

        if obj_type == TYPE_CROSS:
            api_id = str(obj_id)
        else:
            api_id = int(obj_id)

        def loader() -> List[Commutation.Get_data]:
            try:
                result = self.client.Commutation.get_data(object_type=api_type, object_id=api_id)
                return result.to_list() if result else []
            except Exception as e:
                self.logger.error(f"Ошибка загрузки коммутаций для {obj_key}: {e}")
                return []

        return self._cache.get_or_load_commutations(api_type, api_id, loader)

    # ------------------------------------------------------------------------
    # Вспомогательные методы для извлечения информации
    # ------------------------------------------------------------------------

    def _get_node_id_from_obj(self, obj: Any, side: Optional[int] = None) -> Optional[int]:
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
        if obj is None:
            return None
        port_in = getattr(obj, 'port_count_in', 0)
        port_out = getattr(obj, 'port_count_out', 0)
        if port_in == 0 or port_out == 0:
            return None
        return f"{port_in}x{port_out}"

    def _get_node_id_for_interface(self, iface: Interface) -> Optional[int]:
        idx = self._vertex_index.get(iface)
        if idx is None:
            return None
        return self.vs[idx]['node_id']

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, iface: Interface, obj: Optional[Any] = None,
                    node_id_override: Optional[int] = None) -> int:
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
        }

        idx = self.add_vertex(**attrs).index
        self._vertex_index[iface] = idx
        return idx

    def _add_edge(self, iface1: Interface, iface2: Interface, connect_id: int,
                  node_id_for_vertex2: Optional[int] = None,
                  is_internal: bool = False) -> None:
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
    # Обработчики типов объектов с учётом фильтров
    # ------------------------------------------------------------------------

    def _should_stop_at_fiber(self, fiber_id: int, current_node_id: Optional[int]) -> bool:
        """
        Определяет, следует ли остановить обход на данном волокне.
        - excluded_fibers применяется всегда (если не None и fiber_id входит в него -> стоп).
        - included_fibers применяется только если current_node_id == self._start_node_id
          (т.е. мы всё ещё в стартовом узле). Если включено и fiber_id НЕ в included_fibers -> стоп.
        """
        if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
            return True

        if self._included_fibers is not None:
            if self._start_node_id is not None and current_node_id == self._start_node_id:
                if fiber_id not in self._included_fibers:
                    return True
        return False

    def _should_stop_at_node(self, node_id: int) -> bool:
        if self._excluded_nodes is not None and node_id in self._excluded_nodes:
            return True
        return False

    def _process_terminal_object(self, obj: ObjKey, comms: List[Commutation.Get_data],
                                 current_iface: Interface, visited_interfaces: Set[Interface],
                                 queue: deque) -> None:
        self.logger.debug(f"Обработка терминального объекта {obj}")

        current_node_id = self._get_node_id_for_interface(current_iface)
        if current_node_id is not None and self._should_stop_at_node(current_node_id):
            self.logger.debug(f"  Узел {current_node_id} в excluded_nodes, останавливаемся")
            return

        record = self._find_record_for_interface(comms, current_iface)
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
        Обрабатывает объекты со сторонами.
        Для кроссов: активен только один порт (тот, через который пришли или стартовый).
        Через другие порты обход не идёт.
        Для остальных (кабель, сплиттер, CWDM) проходим через все порты.
        """
        self.logger.debug(f"Обработка объекта со сторонами {obj}")

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

            # Внутреннее ребро только для активного порта (соединение сторон 1 и 2)
            iface1 = Interface(obj, 1, active_port)
            iface2 = Interface(obj, 2, active_port)
            self.logger.debug(f"  Внутреннее ребро между {iface1} и {iface2}")
            self._add_edge(iface1, iface2, 0, is_internal=True)

            # Обрабатываем только внешние коммутации, где порт == active_port
            parent_node_id = self._get_node_id_from_obj(self._load_object(obj))
            for rec in comms:
                port = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if port != active_port:
                    continue  # игнорируем другие порты

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

                # Проверка фильтров для соседа
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

            record = self._find_record_for_interface(comms, current_iface)
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
            opposite_record = self._find_record_for_interface(comms, opposite_iface)
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
            for rec in comms:
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
            for rec in comms:
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

                # Проверка фильтров для соседа
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
    # Вспомогательные методы поиска
    # ------------------------------------------------------------------------

    def _find_record_for_interface(self, comms: List[Commutation.Get_data],
                                   iface: Interface) -> Optional[Commutation.Get_data]:
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
        obj_type_str = record.object_type
        obj_id = record.object_id
        obj_uuid = record.object_uuid
        if not obj_type_str:
            return None
        return self._make_obj_key(obj_type_str, obj_id, obj_uuid)

    def _make_obj_key(self, type_str: str, obj_id: Optional[int],
                      obj_uuid: Optional[str] = None) -> Optional[ObjKey]:
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
        # Абонент – всегда порт 0
        if neighbor_obj_key.obj_type == TYPE_CUSTOMER:
            return Interface(neighbor_obj_key, side=1, port=0)

        # Устройства (OLT, switch, ONU) – нужно найти реальный порт по connect_id
        if neighbor_obj_key.obj_type in DEVICE_TYPES:
            neighbor_comms = self._load_commutations(neighbor_obj_key)
            if not neighbor_comms:
                self.logger.warning(f"Нет коммутаций для устройства {neighbor_obj_key}")
                return Interface(neighbor_obj_key, side=1, port=0)  # fallback
            for rec in neighbor_comms:
                if int(rec.connect_id) == int(connect_id):
                    port = int(rec.clps_first) if rec.clps_first is not None else 0
                    return Interface(neighbor_obj_key, side=1, port=port)
            # Если не нашли, fallback
            self.logger.warning(f"Не найден порт для устройства {neighbor_obj_key} по connect_id {connect_id}")
            return Interface(neighbor_obj_key, side=1, port=0)

        # Объекты со сторонами (кросс, кабель, сплиттер, CWDM)
        neighbor_comms = self._load_commutations(neighbor_obj_key)
        if not neighbor_comms:
            self.logger.debug(f"Нет коммутаций для соседа {neighbor_obj_key}")
            return None

        neighbor_rec = None
        for rec in neighbor_comms:
            if int(rec.connect_id) == int(connect_id):
                neighbor_rec = rec
                break
        if neighbor_rec is None:
            self.logger.debug(f"Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj_key}")
            return None

        side = int(neighbor_rec.clps_first) if neighbor_rec.clps_first is not None else 1
        port = int(neighbor_rec.clps_mid) if neighbor_rec.clps_mid is not None else 0
        return Interface(neighbor_obj_key, side, port)

    # ------------------------------------------------------------------------
    # Построение графа
    # ------------------------------------------------------------------------

    def build(self, object_type: str, object_id: Union[int, str], port: Optional[int] = None,
              side: Optional[int] = None,
              included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'CGraph':
        """
        Строит полный граф коммутаций с учётом фильтров.

        Args:
            object_type: тип начального объекта ('olt', 'switch', 'fiber', 'cross', 'splitter', 'cwdm', 'customer')
            object_id: идентификатор объекта
            port: номер порта (для кабеля – порядковый номер волокна)
            side: сторона (1 или 2). Если None, для объектов со сторонами строится от обеих сторон.
            included_fibers: множество ID волокон, через которые разрешён проход (только пока на стартовом узле)
            excluded_fibers: множество ID волокон, на которых обход останавливается (всегда)
            excluded_nodes: множество ID узлов, на которых обход останавливается (всегда)
        """
        self.logger.info(f"=== ПОСТРОЕНИЕ ГРАФА CGraph ОТ {object_type}:{object_id} (port={port}, side={side}) ===")

        self._included_fibers = self._normalize_set(included_fibers)
        self._excluded_fibers = self._normalize_set(excluded_fibers)
        self._excluded_nodes = self._normalize_set(excluded_nodes)

        start_interfaces: List[Interface] = []

        start_obj_key = ObjKey(object_type, object_id)
        start_obj = self._load_object(start_obj_key)
        self._start_node_id = self._get_node_id_from_obj(start_obj) if start_obj else None
        self.logger.debug(f"Стартовый node_id: {self._start_node_id}")

        # OLT без порта – все PON-порты
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
                p = int(rec.clps_first) if rec.clps_first is not None else 0
                start_interfaces.append(Interface(obj_key, side=1, port=p))

        # Кабель – ищем записи с указанным порядковым номером волокна (поле interface)
        elif object_type == TYPE_FIBER:
            obj_key = ObjKey(TYPE_FIBER, object_id)
            comms = self._load_commutations(obj_key)
            if not comms:
                self.logger.warning(f"У кабеля {object_id} нет коммутаций")
                return self

            if port is not None:
                found = False
                for rec in comms:
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

        # Сохраняем стартовый объект и интерфейс для логики кросса
        self._start_obj_key = start_interfaces[0].obj
        self._start_iface = start_interfaces[0]

        self._build_from_interfaces(start_interfaces)
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
        queue = deque()
        visited_interfaces: Set[Interface] = set()

        for iface in start_interfaces:
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

            if obj.obj_type in TERMINAL_TYPES:
                self._process_terminal_object(obj, comms, current_iface, visited_interfaces, queue)
            elif obj.obj_type in SIDE_TYPES:
                self._process_side_object(obj, comms, current_iface, visited_interfaces, queue)
            else:
                self.logger.warning(f"Неизвестный тип объекта: {obj.obj_type}")

    # ------------------------------------------------------------------------
    # Направление графа
    # ------------------------------------------------------------------------

    def _update_directed_flag(self) -> None:
        has_splitter = any(v['obj_type'] == TYPE_SPLITTER for v in self.vs)
        has_cwdm = any(v['obj_type'] == TYPE_CWDM for v in self.vs)
        has_customer = any(v['obj_type'] == TYPE_CUSTOMER for v in self.vs)
        self._directed = has_splitter or has_cwdm or has_customer

    @property
    def directed(self) -> bool:
        return self._directed

    def __repr__(self) -> str:
        return f"CGraph(interfaces={self.vcount()}, commutations={self.ecount()}, directed={self._directed})"


# ===========================================================================
# Граф сооружений связи (FNGraph) с поддержкой фильтров
# ===========================================================================

@dataclass(frozen=True)
class NodeKey:
    node_id: int


class FNGraph(ig.Graph):
    """
    Граф сооружений связи и кабелей.
    Вершины — node_id, рёбра — fiber_id.
    Поддерживает фильтрацию по волокнам и узлам при построении.
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
        self._vertex_index: Dict[int, int] = {}
        self._node_fibers_cache: Dict[int, List[Any]] = {}
        self._built = False

        self._included_fibers: Optional[Set[int]] = None
        self._excluded_fibers: Optional[Set[int]] = None
        self._excluded_nodes: Optional[Set[int]] = None

    # ------------------------------------------------------------------------
    # Загрузка информации о вершинах
    # ------------------------------------------------------------------------

    def _load_node(self, node_id: int) -> Optional[Any]:
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
        if node_id in self._node_fibers_cache:
            return self._node_fibers_cache[node_id]
        try:
            result = self.client.Fiber.get_list(node_id=node_id)
            fibers = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кабелей для узла {node_id}: {e}")
            fibers = []
        self._node_fibers_cache[node_id] = fibers
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
            node_id = v['node_id']
            if node_id is None:
                self.logger.warning(f"У вершины кабеля {fiber_id} нет node_id")
                continue

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
    # Построение через API (BFS)
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

    def __repr__(self) -> str:
        return f"FNGraph(nodes={self.vcount()}, fibers={self.ecount()})"