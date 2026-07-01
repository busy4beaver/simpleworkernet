# simpleworkernet/utils/topology.py
"""
Модуль для построения графа коммутаций от заданного порта OLT с использованием API WorkerNet.
Реализован как наследник igraph.Graph для максимальной производительности и совместимости.

Используются только строковые типы объектов:
- TYPE_CUSTOMER = 'customer'
- TYPE_FIBER = 'fiber'
- TYPE_SPLITTER = 'splitter'
- TYPE_CROSS = 'cross'
- TYPE_SWITCH = 'switch'
- TYPE_OLT = 'olt'
- TYPE_ONU = 'onu'

Содержит классы: ObjKey, Interface, CommutationGraph.
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union
from collections import deque
from dataclasses import dataclass
import igraph as ig

# Импорты клиента и моделей
from ..core.client import WorkerNetClient
from ..models.categories import Commutation, Device, Cross, Splitter, Fiber, Customer

_logger = None

def _get_logger():
    """Ленивый импорт логгера"""
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger


# ===========================================================================
# Константы типов объектов
# ===========================================================================

TYPE_CUSTOMER = 'customer'
TYPE_FIBER = 'fiber'
TYPE_SPLITTER = 'splitter'
TYPE_CROSS = 'cross'
TYPE_SWITCH = 'switch'
TYPE_OLT = 'olt'
TYPE_ONU = 'onu'

# Множество типов, которые считаются активным оборудованием (устройствами)
DEVICE_TYPES = {TYPE_SWITCH, TYPE_OLT, TYPE_ONU}

# Типы, у которых есть стороны (direction 1 и 2) — кросс, кабель, сплиттер
SIDE_TYPES = {TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER}


# ===========================================================================
# Вспомогательные классы
# ===========================================================================

@dataclass(frozen=True)
class ObjKey:
    """
    Уникальный ключ объекта сети.
    Состоит из строкового типа (одна из констант TYPE_*) и идентификатора.
    Для кроссов идентификатор — UUID (строка), для остальных — число.
    """
    obj_type: str
    id: Union[int, str]

    def __str__(self) -> str:
        return f"{self.obj_type}:{self.id}"


@dataclass(frozen=True)
class Interface:
    """
    Интерфейс объекта — точка подключения в коммутации.
    Содержит ссылку на объект, сторону (clps_first) и порт/волокно (clps_mid).
    """
    obj: ObjKey
    side: int          # clps_first из Commutation.Get_data
    port: int          # clps_mid из Commutation.Get_data

    def __str__(self) -> str:
        return f"{self.obj} side={self.side} port={self.port}"


# ===========================================================================
# Основной класс графа (наследник igraph.Graph)
# ===========================================================================

class CommutationGraph(ig.Graph):
    """
    Граф коммутаций, построенный на основе данных API WorkerNet.
    Наследует igraph.Graph, поэтому все методы igraph доступны напрямую.

    Хранит кэши загруженных данных для минимизации API-запросов.
    Предоставляет методы для построения графа от заданного порта OLT,
    поиска абонентов, маршрутов и экспорта в GraphML.
    """

    def __init__(self, client: WorkerNetClient, additional_data = False, **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self._additional_data = additional_data
        self.logger = _get_logger()

        # Кэш: объект -> список моделей Commutation.Get_data
        self._comm_cache: Dict[ObjKey, List[Commutation.Get_data]] = {}
        # Кэш: объект -> информация (node_id)
        self._obj_info_cache: Dict[ObjKey, Dict[str, Optional[int]]] = {}

        # Словарь для сопоставления ObjKey с индексом вершины в графе
        self._vertex_index: Dict[ObjKey, int] = {}

        # Максимальная глубина обхода для предотвращения бесконечных циклов
        self._max_depth = 100

    # ------------------------------------------------------------------------
    # Внутренние методы для загрузки данных (API-запросы)
    # ------------------------------------------------------------------------

    def _load_object_info(self, obj_key: ObjKey, side: int  = None, parent: Interface = None) -> Dict[str, Optional[int]]:
        """Загружает node_id для объекта."""
        if obj_key in self._obj_info_cache:
            return self._obj_info_cache[obj_key]

        info = {'node_id': None}
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        self.logger.debug(f"Загрузка информации для {obj_type}:{obj_id}")

        try:
            if obj_type == TYPE_OLT:
                result = self.client.Device.get_data(object_type=TYPE_OLT, object_id=int(obj_id))
                if result and len(result) > 0:
                    dev = result[0]
                    info['node_id'] = dev.node_id
            elif obj_type in (TYPE_SWITCH, TYPE_ONU):
                result = self.client.Device.get_data(object_type=obj_type, object_id=int(obj_id))
                if result and len(result) > 0:
                    dev = result[0]
                    info['node_id'] = getattr(dev, 'node_id', None)
            elif obj_type == TYPE_CROSS:
                result = self.client.Cross.get_list(id=str(obj_id))
                if result and len(result) > 0:
                    cross = result[0]
                    info['node_id'] = getattr(cross, 'node_id', None)
            elif obj_type == TYPE_SPLITTER:
                result = self.client.Splitter.get(id=int(obj_id))
                if result and len(result) > 0:
                    splitter = result[0]
                    info['node_id'] = getattr(splitter, 'node_id', None)
            elif obj_type == TYPE_FIBER:
                result = self.client.Fiber.get_list(object_id=int(obj_id))
                if result and len(result) > 0:
                    cable = result[0]
                    print(cable, side)
                    info['node_id'] = getattr(cable, f"node{side if side else parent.side}_id", None)
                    print(info)
            elif obj_type == TYPE_CUSTOMER:
                if parent: 
                    info['node_id'] = self._load_object_info(parent.obj, parent.side, None)['node_id']
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить информацию для {obj_key}: {e}")

        self._obj_info_cache[obj_key] = info
        return info

    def _make_obj_key(self, type_str: str, obj_id: Optional[int],
                      obj_uuid: Optional[str] = None) -> Optional[ObjKey]:
        """Создаёт ObjKey из строкового типа и идентификатора."""
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

    def _load_commutations(self, obj_key: ObjKey) -> List[Commutation.Get_data]:
        """
        Загружает коммутации для объекта через API и кэширует их.
        Для всех устройств (olt, switch, onu) использует object_type='switch'.
        """
        if obj_key in self._comm_cache:
            return self._comm_cache[obj_key]

        # Определяем строковый тип для API-запроса
        if obj_key.obj_type in DEVICE_TYPES:
            api_type = TYPE_SWITCH
        else:
            api_type = obj_key.obj_type

        if not api_type:
            return []

        if obj_key.obj_type == TYPE_CROSS:
            object_id = str(obj_key.id)
        else:
            object_id = int(obj_key.id)

        try:
            result = self.client.Commutation.get_data(
                object_type=api_type,
                object_id=object_id
            )
            comms = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки коммутаций для {obj_key}: {e}")
            comms = []

        self._comm_cache[obj_key] = comms
        return comms

    # ------------------------------------------------------------------------
    # Методы для работы с графом (добавление вершин и рёбер)
    # ------------------------------------------------------------------------

    def _add_vertex(self, obj_key: ObjKey, parent: Interface = None) -> int: #, node_id: Optional[int] = None) -> int:
        """Добавляет вершину в граф, если её ещё нет, и возвращает её индекс."""
        if obj_key in self._vertex_index:
            return self._vertex_index[obj_key]

        is_customer = (obj_key.obj_type == TYPE_CUSTOMER)

        inf = self._load_object_info(obj_key, parent=parent)

        if is_customer: print (parent)

        idx = self.add_vertex(
            obj_type=obj_key.obj_type,
            obj_id=str(obj_key.id),
            node_id=inf['node_id'],
            # is_customer=is_customer,
            name=str(obj_key)
        ).index

        self._vertex_index[obj_key] = idx
        return idx

    def _add_edge(self, obj1: ObjKey, obj2: ObjKey,
                  side: int, port: int, connect_id: int) -> None:
        """Добавляет ребро между двумя вершинами, если его ещё нет."""
        idx1 = self._add_vertex(obj1)
        idx2 = self._add_vertex(obj2, parent=Interface(obj1,side,port))

        if self.are_connected(idx1, idx2):
            return

        self.add_edge(idx1, idx2, side=side, port=port, connect_id=connect_id)

    # ------------------------------------------------------------------------
    # Вспомогательные методы для обхода по коммутациям
    # ------------------------------------------------------------------------

    def _find_record_for_interface(self, comms: List[Commutation.Get_data],
                                   obj: ObjKey, side: int, port: int) -> Optional[Commutation.Get_data]:
        """
        Находит запись в коммутациях для заданного интерфейса (сторона+порт).
        Для устройств (OLT/switch/ONU) используется только порт (clps_first).
        Для объектов со сторонами (кросс, кабель, сплиттер) — сторона и порт.
        """
        is_device = obj.obj_type in DEVICE_TYPES
        for rec in comms:
            if is_device:
                # Для устройств: clps_first = порт
                if rec.clps_first is not None and int(rec.clps_first) == port:
                    return rec
            else:
                # Для объектов со сторонами: сравниваем и сторону, и порт
                if (rec.clps_first is not None and int(rec.clps_first) == side and
                    rec.clps_mid is not None and int(rec.clps_mid) == port):
                    return rec
        return None

    def _find_record_by_connect_id(self, comms: List[Commutation.Get_data],
                                   connect_id: int) -> Optional[Commutation.Get_data]:
        """Ищет запись с заданным connect_id в списке коммутаций."""
        for rec in comms:
            if int(rec.connect_id) == int(connect_id):
                return rec
        return None

    def _get_opposite_side_record(self, comms: List[Commutation.Get_data],
                                  side: int, port: int) -> Optional[Commutation.Get_data]:
        """
        В списке коммутаций ищет запись на противоположной стороне (side меняется 1↔2)
        с тем же портом (clps_mid).
        Возвращает найденную запись или None.
        """
        opposite_side = 2 if side == 1 else 1
        for rec in comms:
            if (rec.clps_first is not None and int(rec.clps_first) == opposite_side and
                rec.clps_mid is not None and int(rec.clps_mid) == port):
                return rec
        return None

    def _extract_neighbor_from_record(self, record: Commutation.Get_data) -> Tuple[Optional[ObjKey], int, int]:
        """
        Из записи Commutation.Get_data извлекает:
        - ObjKey соседа
        - connect_id
        - порт соседа (interface)
        Возвращает кортеж (obj_key, connect_id, neighbor_port).
        """
        obj_type_str = record.object_type
        obj_id = record.object_id
        obj_uuid = record.object_uuid
        connect_id = record.connect_id
        neighbor_port = record.interface  # порт соседа

        if not obj_type_str:
            return None, 0, 0

        obj_key = self._make_obj_key(obj_type_str, obj_id, obj_uuid)
        return obj_key, connect_id, neighbor_port

    def _process_neighbor(self, neighbor_obj: ObjKey, neighbor_side: int, neighbor_port: int,
                          connect_id: int, current_iface: Interface,
                          visited_interfaces: Set[Interface], queue: deque,
                          parent_obj: ObjKey) -> None:
        """
        Обрабатывает соседа: загружает его коммутации, определяет его интерфейс
        и добавляет в очередь для дальнейшего обхода.
        """
        # Убедимся, что вершина для соседа существует
        # info = self._load_object_info(neighbor_obj)
        self._add_vertex(neighbor_obj, parent = current_iface) #, node_id=info.get('node_id'))

        # Если сосед — устройство или абонент, дальше не идём
        if neighbor_obj.obj_type in DEVICE_TYPES or neighbor_obj.obj_type == TYPE_CUSTOMER:
            return

        # Для кроссов, кабелей, сплиттеров: создаём интерфейс и добавляем в очередь
        if neighbor_obj.obj_type in SIDE_TYPES:
            next_iface = Interface(neighbor_obj, neighbor_side, neighbor_port)
            self.logger.debug(f"  Интерфейс соседа: {next_iface}")

            if next_iface not in visited_interfaces:
                queue.append((next_iface, neighbor_obj))

    # ------------------------------------------------------------------------
    # Обработчики для каждого типа объекта
    # ------------------------------------------------------------------------

    def _process_device(self, obj: ObjKey, comms: List[Commutation.Get_data],
                             current_iface: Interface, visited_interfaces: Set[Interface],
                             queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """
        Общая логика для устройств (OLT/switch/ONU).
        Для OLT (is_olt=True) продолжаем обход, для остальных — останавливаемся.
        """
        if parent_obj is not None:
            self.logger.debug(f"Устройство {obj} не OLT, останавливаемся")
            return

        # Для OLT находим запись по порту (clps_first)
        record = self._find_record_for_interface(comms, obj, current_iface.side, current_iface.port)
        if record is None:
            self.logger.debug(f"  Не найдена запись для порта {current_iface.port}")
            return

        # Извлекаем соседа
        neighbor_obj, connect_id, neighbor_port = self._extract_neighbor_from_record(record)
        if neighbor_obj is None:
            return

        # Добавляем ребро
        self._add_edge(obj, neighbor_obj, current_iface.side, neighbor_port, connect_id)

        # Если сосед — абонент или устройство, останавливаемся
        if neighbor_obj.obj_type == TYPE_CUSTOMER or neighbor_obj.obj_type in DEVICE_TYPES:
            return

        # Иначе сосед — кросс, кабель или сплиттер — продолжаем
        # Загружаем коммутации соседа, чтобы найти его сторону и порт
        neighbor_comms = self._load_commutations(neighbor_obj)
        if not neighbor_comms:
            return

        # Находим запись соседа по connect_id
        neighbor_rec = self._find_record_by_connect_id(neighbor_comms, connect_id)
        if neighbor_rec is None:
            self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj}")
            return

        # Получаем сторону и порт соседа
        neighbor_side = int(neighbor_rec.clps_first) if neighbor_rec.clps_first is not None else 1
        neighbor_port_rec = int(neighbor_rec.clps_mid) if neighbor_rec.clps_mid is not None else 0

        # Обрабатываем соседа
        self._process_neighbor(neighbor_obj, neighbor_side, neighbor_port_rec, connect_id,
                               current_iface, visited_interfaces, queue, obj)

    def _process_cross(self, obj: ObjKey, comms: List[Commutation.Get_data],
                       current_iface: Interface, visited_interfaces: Set[Interface],
                       queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """Обрабатывает кросс (cross)."""
        self.logger.debug(f"Обработка кросса {obj}")

        # Ищем запись на текущей стороне с текущим портом
        record = self._find_record_for_interface(comms, obj, current_iface.side, current_iface.port)
        if record is None:
            self.logger.debug(f"  Не найдена запись для стороны {current_iface.side}, порт {current_iface.port}")
            return

        # Из записи извлекаем соседа
        neighbor_obj, connect_id, neighbor_port = self._extract_neighbor_from_record(record)
        if neighbor_obj is None:
            return

        # Добавляем ребро
        self._add_edge(obj, neighbor_obj, current_iface.side, neighbor_port, connect_id)

        # Переходим на противоположную сторону с тем же портом
        opposite_side = 2 if current_iface.side == 1 else 1
        self.logger.debug(f"  Кросс: переход на сторону {opposite_side}, порт {current_iface.port}")

        # Ищем запись на противоположной стороне с тем же портом
        opposite_rec = self._get_opposite_side_record(comms, current_iface.side, current_iface.port)
        if opposite_rec is None:
            self.logger.debug(f"  Нет записи на противоположной стороне для порта {current_iface.port}")
            return

        # Из этой записи извлекаем соседа на противоположной стороне
        neighbor_obj_opp, connect_id_opp, neighbor_port_opp = self._extract_neighbor_from_record(opposite_rec)
        if neighbor_obj_opp is None:
            return

        # Добавляем ребро от текущего объекта к соседу на противоположной стороне
        self._add_edge(obj, neighbor_obj_opp, opposite_side, neighbor_port_opp, connect_id_opp)

        # Теперь обрабатываем соседа: загружаем его коммутации, определяем его интерфейс
        neighbor_comms_opp = self._load_commutations(neighbor_obj_opp)
        if not neighbor_comms_opp:
            self.logger.debug(f"  Нет коммутаций для соседа {neighbor_obj_opp}")
            return

        # Находим запись соседа по connect_id_opp
        neighbor_rec_opp = self._find_record_by_connect_id(neighbor_comms_opp, connect_id_opp)
        if neighbor_rec_opp is None:
            self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id_opp} у соседа {neighbor_obj_opp}")
            return

        # Получаем сторону и порт соседа
        neighbor_side_opp = int(neighbor_rec_opp.clps_first) if neighbor_rec_opp.clps_first is not None else 1
        neighbor_port_opp_rec = int(neighbor_rec_opp.clps_mid) if neighbor_rec_opp.clps_mid is not None else 0

        # Обрабатываем соседа
        self._process_neighbor(neighbor_obj_opp, neighbor_side_opp, neighbor_port_opp_rec, connect_id_opp,
                               current_iface, visited_interfaces, queue, obj)

    def _process_fiber(self, obj: ObjKey, comms: List[Commutation.Get_data],
                       current_iface: Interface, visited_interfaces: Set[Interface],
                       queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """Обрабатывает кабель (fiber)."""
        self.logger.debug(f"Обработка кабеля {obj}")

        # Ищем запись на текущей стороне с текущим портом
        record = self._find_record_for_interface(comms, obj, current_iface.side, current_iface.port)
        if record is None:
            self.logger.debug(f"  Не найдена запись для стороны {current_iface.side}, порт {current_iface.port}")
            return

        # Из записи извлекаем соседа
        neighbor_obj, connect_id, neighbor_port = self._extract_neighbor_from_record(record)
        if neighbor_obj is None:
            return

        # Добавляем ребро
        self._add_edge(obj, neighbor_obj, current_iface.side, neighbor_port, connect_id)

        # Переходим на противоположную сторону с тем же портом
        opposite_side = 2 if current_iface.side == 1 else 1
        self.logger.debug(f"  Кабель: переход на сторону {opposite_side}, порт {current_iface.port}")

        # Ищем запись на противоположной стороне с тем же портом
        opposite_rec = self._get_opposite_side_record(comms, current_iface.side, current_iface.port)
        if opposite_rec is None:
            self.logger.debug(f"  Нет записи на противоположной стороне для порта {current_iface.port}")
            return

        # Из этой записи извлекаем соседа на противоположной стороне
        neighbor_obj_opp, connect_id_opp, neighbor_port_opp = self._extract_neighbor_from_record(opposite_rec)
        if neighbor_obj_opp is None:
            return

        # Добавляем ребро от текущего объекта к соседу на противоположной стороне
        self._add_edge(obj, neighbor_obj_opp, opposite_side, neighbor_port_opp, connect_id_opp)

        # Теперь обрабатываем соседа: загружаем его коммутации, определяем его интерфейс
        neighbor_comms_opp = self._load_commutations(neighbor_obj_opp)
        if not neighbor_comms_opp:
            self.logger.debug(f"  Нет коммутаций для соседа {neighbor_obj_opp}")
            return

        # Находим запись соседа по connect_id_opp
        neighbor_rec_opp = self._find_record_by_connect_id(neighbor_comms_opp, connect_id_opp)
        if neighbor_rec_opp is None:
            self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id_opp} у соседа {neighbor_obj_opp}")
            return

        # Получаем сторону и порт соседа
        neighbor_side_opp = int(neighbor_rec_opp.clps_first) if neighbor_rec_opp.clps_first is not None else 1
        neighbor_port_opp_rec = int(neighbor_rec_opp.clps_mid) if neighbor_rec_opp.clps_mid is not None else 0

        # Обрабатываем соседа
        self._process_neighbor(neighbor_obj_opp, neighbor_side_opp, neighbor_port_opp_rec, connect_id_opp,
                               current_iface, visited_interfaces, queue, obj)

    def _process_splitter(self, obj: ObjKey, comms: List[Commutation.Get_data],
                          current_iface: Interface, visited_interfaces: Set[Interface],
                          queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """Обрабатывает сплиттер (splitter)."""
        self.logger.debug(f"Обработка сплиттера {obj}")

        if current_iface.side == 1:
            # Пришли на вход (side=1) — обходим все выходы (side=2)
            self._process_splitter_outputs(obj, comms, visited_interfaces, queue)
        else:
            # Пришли на выход (side=2) — останавливаемся
            self.logger.debug("  Сплиттер: пришли на выход (side=2), останавливаемся")

    def _process_splitter_outputs(self, splitter_obj: ObjKey, splitter_comms: List[Commutation.Get_data],
                                  visited_interfaces: Set[Interface], queue: deque) -> None:
        """
        Обходит все выходы сплиттера (direction == 2).
        Для каждого выхода добавляет ребро и обрабатывает соседа.
        """
        # Для сплиттера записи со стороны 2 — это выходы (clps_first == 2)
        out_records = [rec for rec in splitter_comms if rec.clps_first is not None and int(rec.clps_first) == 2]
        self.logger.debug(f"Сплиттер {splitter_obj}: найдено выходов: {len(out_records)}")

        for rec in out_records:
            neighbor_info = self._extract_neighbor_from_record(rec)
            neighbor_obj, connect_id, neighbor_port = neighbor_info
            if neighbor_obj is None:
                continue

            # Создаём интерфейс для выхода
            out_iface = Interface(neighbor_obj, 2, neighbor_port)  # side=2 (выход), порт из записи
            self.logger.debug(f"  Выход: {out_iface}")

            if out_iface in visited_interfaces:
                continue

            # Добавляем ребро от сплиттера к соседу
            self._add_edge(splitter_obj, neighbor_obj, 2, neighbor_port, connect_id)

            # Если сосед — абонент или устройство, останавливаемся
            if neighbor_obj.obj_type == TYPE_CUSTOMER or neighbor_obj.obj_type in DEVICE_TYPES:
                continue

            # Для кроссов, кабелей или других сплиттеров — продолжаем
            # Загружаем коммутации соседа, чтобы найти его сторону и порт
            neighbor_comms = self._load_commutations(neighbor_obj)
            if not neighbor_comms:
                continue

            # Находим запись соседа по connect_id
            neighbor_rec = self._find_record_by_connect_id(neighbor_comms, connect_id)
            if neighbor_rec is None:
                self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj}")
                continue

            # Получаем сторону и порт соседа
            neighbor_side = int(neighbor_rec.clps_first) if neighbor_rec.clps_first is not None else 1
            neighbor_port_rec = int(neighbor_rec.clps_mid) if neighbor_rec.clps_mid is not None else 0

            # Обрабатываем соседа
            self._process_neighbor(neighbor_obj, neighbor_side, neighbor_port_rec, connect_id,
                                   out_iface, visited_interfaces, queue, splitter_obj)

    def _process_customer(self, obj: ObjKey, comms: List[Commutation.Get_data],
                          current_iface: Interface, visited_interfaces: Set[Interface],
                          queue: deque, parent_obj: Optional[ObjKey]) -> None:
        """Обрабатывает абонента (customer) — конечная точка."""
        self.logger.debug(f"Обработка абонента {obj}")
        # Абонент уже имеет is_customer=True при создании вершины
        # Ничего не делаем, просто не продолжаем обход

    # ------------------------------------------------------------------------
    # Основной метод обхода (BFS)
    # ------------------------------------------------------------------------

    def build(self, olt_id: int, pon_port: int) -> 'CommutationGraph':
        """
        Строит граф коммутаций, начиная с заданного порта OLT.
        Использует BFS для обхода всех достижимых объектов.
        """
        self.logger.info("=== НАЧАЛО ПОСТРОЕНИЯ ГРАФА КОММУТАЦИЙ ===")

        olt_obj = ObjKey(TYPE_SWITCH, olt_id)
        # Для OLT стартовый интерфейс: сторона=1, порт=pon_port
        # (у OLT нет сторон, clps_first = номер порта)
        start_iface = Interface(olt_obj, side=1, port=pon_port)

        # Добавляем корневую вершину
        # info = self._load_object_info(olt_obj)
        self._add_vertex(olt_obj) #, node_id=info.get('node_id'))

        # Очередь BFS: (текущий интерфейс, родительский объект)
        queue = deque([(start_iface, None)])
        visited_interfaces: Set[Interface] = set()

        while queue:
            current_iface, parent_obj = queue.popleft()
            self.logger.debug(f"--- Обработка интерфейса {current_iface} ---")

            if current_iface in visited_interfaces:
                self.logger.debug("  Интерфейс уже посещён, пропускаем")
                continue
            visited_interfaces.add(current_iface)

            obj = current_iface.obj
            current_side = current_iface.side
            current_port = current_iface.port

            # Убеждаемся, что вершина для объекта существует
            # info = self._load_object_info(obj)
            self._add_vertex(obj) #, node_id=info.get('node_id'))

            # Загружаем коммутации для текущего объекта
            comms = self._load_commutations(obj)
            if not comms:
                self.logger.debug(f"  Нет коммутаций для {obj}")
                continue

            # ===== Обработка в зависимости от типа объекта =====
            obj_type = obj.obj_type

            # if obj_type == TYPE_OLT:
            #     self._process_device_like(obj, comms, current_iface, visited_interfaces, queue, parent_obj, is_olt=True)
            if obj_type in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU):
                self._process_device(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type == TYPE_CROSS:
                self._process_cross(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type == TYPE_FIBER:
                self._process_fiber(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type == TYPE_SPLITTER:
                self._process_splitter(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            elif obj_type == TYPE_CUSTOMER:
                self._process_customer(obj, comms, current_iface, visited_interfaces, queue, parent_obj)
            else:
                self.logger.warning(f"  Неизвестный тип объекта: {obj_type}")

        self.logger.info("=== ПОСТРОЕНИЕ ГРАФА ЗАВЕРШЕНО ===")
        return self

    # ------------------------------------------------------------------------
    # Аналитические методы (используют родительские методы igraph)
    # ------------------------------------------------------------------------

    def find_customers(self) -> List[Dict[str, Any]]:
        """Находит все вершины, являющиеся абонентами."""
        customer_vs = self.vs.select(obj_type='customer')
        result = []
        for v in customer_vs:
            result.append({
                'vertex_index': v.index,
                'obj_type': v['obj_type'],
                'obj_id': v['obj_id'],
                'node_id': v['node_id'],
                'name': v['name'],
            })
        return result

    def get_path(self, obj_key1: ObjKey, obj_key2: ObjKey) -> Optional[List[Dict[str, Any]]]:
        """Находит кратчайший путь между двумя объектами в графе."""
        if obj_key1 not in self._vertex_index or obj_key2 not in self._vertex_index:
            return None
        idx1 = self._vertex_index[obj_key1]
        idx2 = self._vertex_index[obj_key2]
        paths = self.get_shortest_paths(idx1, to=idx2, output='vpath')
        if not paths or not paths[0]:
            return None
        path_vertices = paths[0]
        result = []
        for v_idx in path_vertices:
            v = self.vs[v_idx]
            result.append({
                'vertex_index': v_idx,
                'obj_type': v['obj_type'],
                'obj_id': v['obj_id'],
                'node_id': v['node_id'],
                'name': v['name'],
            })
        return result

    def get_vertex_by_obj_key(self, obj_key: ObjKey) -> Optional[ig.Vertex]:
        """Возвращает вершину igraph по её ObjKey."""
        if obj_key not in self._vertex_index:
            return None
        return self.vs[self._vertex_index[obj_key]]

    def stats(self) -> Dict[str, Any]:
        """Возвращает основную статистику по графу."""
        return {
            'num_vertices': self.vcount(),
            'num_edges': self.ecount(),
            'customers_count': len(self.find_customers()),
            'is_connected': self.is_connected(),
            'components': self.components().membership,
        }

    def export_graphml(self, filename: str) -> None:
        """Сохраняет граф в формате GraphML."""
        self.write_graphml(filename)

    def __repr__(self) -> str:
        return f"CommutationGraph(nodes={self.vcount()}, edges={self.ecount()})"