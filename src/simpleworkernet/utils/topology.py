# simpleworkernet/utils/topology.py
"""
Модуль для построения графа коммутаций и графа сооружений связи (узлов и кабелей).
Реализован как наследник igraph.Graph.

Вершины графа коммутаций — это интерфейсы (объект + сторона + порт).
Для устройств (OLT, switch, ONU, CWDM) и абонентов (customer) сторона = None.
Для объектов со сторонами (кросс, кабель, сплиттер, CWDM) сторона = 1 или 2.

Граф сооружений связи (FNGraph) — вершины: node_id, рёбра: fiber_id.
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union
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
    obj_type: str
    id: Union[int, str]

    def __str__(self) -> str:
        return f"{self.obj_type}:{self.id}"


@dataclass(frozen=True)
class Interface:
    """Вершина графа коммутаций — интерфейс объекта."""
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
    """

    def __init__(self, client: WorkerNetClient, **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()

        self._comm_cache: Dict[ObjKey, List[Commutation.Get_data]] = {}
        self._obj_info_cache: Dict[ObjKey, Dict[str, Any]] = {}

        self._vertex_index: Dict[Interface, int] = {}
        self._visited_interfaces: Set[Interface] = set()

        self._max_depth = 100

        # Флаг направления графа (устанавливается после построения)
        self._directed: bool = False

        # Данные по затуханиям (загружаются отдельно)
        self._attenuation_data: Dict[str, Any] = {}

    # ------------------------------------------------------------------------
    # Загрузка данных
    # ------------------------------------------------------------------------

    def _load_object_info(self, obj_key: ObjKey) -> Dict[str, Any]:
        if obj_key in self._obj_info_cache:
            return self._obj_info_cache[obj_key]

        info = {}
        obj_type = obj_key.obj_type
        obj_id = obj_key.id

        try:
            if obj_type in DEVICE_TYPES:
                result = self.client.Device.get_data(object_type=obj_type, object_id=int(obj_id))
                if result and len(result) > 0:
                    dev = result[0]
                    info['node_id'] = getattr(dev, 'node_id', None)
                    if obj_type == TYPE_OLT:
                        info['ifaces'] = getattr(dev, 'ifaces', {})
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
                    info['splitter_type'] = self._determine_splitter_type(splitter)
            elif obj_type == TYPE_FIBER:
                result = self.client.Fiber.get_list(object_id=int(obj_id))
                if result and len(result) > 0:
                    cable = result[0]
                    info['node1_id'] = getattr(cable, 'node1_id', None)
                    info['node2_id'] = getattr(cable, 'node2_id', None)
                    info['optical_length'] = getattr(cable, 'optical_length', None)
                    info['building_length'] = getattr(cable, 'building_length', None)
            elif obj_type == TYPE_CWDM:
                result = self.client.Device.get_data(object_type=obj_type, object_id=int(obj_id))
                if result and len(result) > 0:
                    dev = result[0]
                    info['node_id'] = getattr(dev, 'node_id', None)
                    info['ifaces'] = getattr(dev, 'ifaces', {})
            elif obj_type == TYPE_CUSTOMER:
                pass
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить информацию для {obj_key}: {e}")

        self._obj_info_cache[obj_key] = info
        return info

    def _determine_splitter_type(self, splitter) -> str:
        port_count_in = getattr(splitter, 'port_count_in', 0)
        port_count_out = getattr(splitter, 'port_count_out', 0)
        if port_count_in == 1 and port_count_out > 0:
            return f"1x{port_count_out}"
        elif port_count_in == 2 and port_count_out > 0:
            return f"2x{port_count_out}"
        else:
            return f"{port_count_in}x{port_count_out}"

    def _get_node_id_for_interface(self, iface: Interface) -> Optional[int]:
        info = self._load_object_info(iface.obj)
        obj_type = iface.obj.obj_type

        if obj_type == TYPE_FIBER:
            if iface.side == 1:
                return info.get('node1_id')
            elif iface.side == 2:
                return info.get('node2_id')
            else:
                return info.get('node1_id')
        else:
            return info.get('node_id')

    def _get_fiber_length_km(self, iface: Interface) -> Optional[float]:
        if iface.obj.obj_type != TYPE_FIBER:
            return None
        info = self._load_object_info(iface.obj)
        length = info.get('optical_length')
        if length is not None:
            return float(length) / 1000.0
        length = info.get('building_length')
        if length is not None:
            return float(length) / 1000.0
        return None

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

    def _load_commutations(self, obj_key: ObjKey) -> List[Commutation.Get_data]:
        if obj_key in self._comm_cache:
            return self._comm_cache[obj_key]

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
            result = self.client.Commutation.get_data(object_type=api_type, object_id=object_id)
            comms = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки коммутаций для {obj_key}: {e}")
            comms = []

        self._comm_cache[obj_key] = comms
        return comms

    # ------------------------------------------------------------------------
    # Управление затуханиями
    # ------------------------------------------------------------------------

    def load_attenuation_data(self, data: Dict[str, Any]) -> None:
        self._attenuation_data = data
        if self.vcount() > 0 and self.ecount() > 0:
            self._recompute_attenuation()

    def _recompute_attenuation(self) -> None:
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
        for iface, v_idx in self._vertex_index.items():
            if v_idx == idx:
                return iface
        return None

    def _compute_attenuation(self, iface1: Interface, iface2: Interface,
                             is_internal: bool, connect_id: int) -> Optional[float]:
        if not self._attenuation_data:
            return None

        if is_internal:
            if iface1.obj != iface2.obj:
                return None
            obj_type = iface1.obj.obj_type

            if obj_type == TYPE_CROSS:
                return self._attenuation_data.get('connector')
            elif obj_type == TYPE_SPLITTER:
                splitter_info = self._load_object_info(iface1.obj)
                splitter_type = splitter_info.get('splitter_type')
                splitter_data = self._attenuation_data.get('splitter', {})
                if splitter_type and splitter_type in splitter_data:
                    port_losses = splitter_data[splitter_type]
                    if iface2.side == 2 and iface2.port in port_losses:
                        return port_losses[iface2.port]
                    if port_losses:
                        return sum(port_losses.values()) / len(port_losses)
                return None
            elif obj_type == TYPE_CWDM:
                cwdm_data = self._attenuation_data.get('cwdm', {})
                cwdm_type = self._load_object_info(iface1.obj).get('cwdm_type')
                if cwdm_type and cwdm_type in cwdm_data:
                    port_losses = cwdm_data[cwdm_type]
                    if iface2.side == 2 and iface2.port in port_losses:
                        return port_losses[iface2.port]
                    if port_losses:
                        return sum(port_losses.values()) / len(port_losses)
                return None
            else:
                return None
        else:
            fiber_iface = None
            other_iface = None
            if iface1.obj.obj_type == TYPE_FIBER:
                fiber_iface = iface1
                other_iface = iface2
            elif iface2.obj.obj_type == TYPE_FIBER:
                fiber_iface = iface2
                other_iface = iface1

            if fiber_iface is not None:
                length_km = self._get_fiber_length_km(fiber_iface)
                fiber_per_km = self._attenuation_data.get('fiber_per_km')
                if fiber_per_km is not None and length_km is not None:
                    fiber_atten = length_km * fiber_per_km
                else:
                    fiber_atten = None
                splice_atten = self._attenuation_data.get('splice') if other_iface is not None else 0.0
                if fiber_atten is not None:
                    return fiber_atten + (splice_atten if splice_atten is not None else 0.0)
                else:
                    return splice_atten if splice_atten is not None else None
            else:
                return None

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, iface: Interface, node_id_override: Optional[int] = None) -> int:
        if iface in self._vertex_index:
            return self._vertex_index[iface]

        node_id = node_id_override if node_id_override is not None else self._get_node_id_for_interface(iface)

        idx = self.add_vertex(
            obj_type=iface.obj.obj_type,
            obj_id=str(iface.obj.id),
            side=iface.side,
            port=iface.port,
            node_id=node_id,
            name=str(iface)
        ).index

        self._vertex_index[iface] = idx
        return idx

    def _add_edge(self, iface1: Interface, iface2: Interface, connect_id: int,
                  node_id_for_vertex2: Optional[int] = None,
                  attenuation_override: Optional[float] = None,
                  is_internal: bool = False) -> None:
        idx1 = self._add_vertex(iface1)
        idx2 = self._add_vertex(iface2, node_id_override=node_id_for_vertex2)

        if self.are_connected(idx1, idx2):
            return

        if attenuation_override is not None:
            attenuation = attenuation_override
        else:
            attenuation = self._compute_attenuation(iface1, iface2, is_internal, connect_id)

        self.add_edge(idx1, idx2, connect_id=connect_id, attenuation=attenuation, is_internal=is_internal)

    # ------------------------------------------------------------------------
    # Вспомогательные методы для обхода
    # ------------------------------------------------------------------------

    def _find_record_for_interface(self, comms: List[Commutation.Get_data],
                                   iface: Interface) -> Optional[Commutation.Get_data]:
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

    def _find_record_by_connect_id(self, comms: List[Commutation.Get_data],
                                   connect_id: int) -> Optional[Commutation.Get_data]:
        for rec in comms:
            if int(rec.connect_id) == int(connect_id):
                return rec
        return None

    def _get_neighbor_obj_from_record(self, record: Commutation.Get_data) -> Optional[ObjKey]:
        obj_type_str = record.object_type
        obj_id = record.object_id
        obj_uuid = record.object_uuid
        if not obj_type_str:
            return None
        return self._make_obj_key(obj_type_str, obj_id, obj_uuid)

    def _get_interface_for_neighbor(self, neighbor_obj: ObjKey, connect_id: int,
                                    parent_node_id: Optional[int] = None) -> Optional[Interface]:
        if neighbor_obj.obj_type == TYPE_CUSTOMER:
            return Interface(neighbor_obj, side=1, port=0)

        if neighbor_obj.obj_type in DEVICE_TYPES:
            return Interface(neighbor_obj, side=1, port=0)

        neighbor_comms = self._load_commutations(neighbor_obj)
        if not neighbor_comms:
            self.logger.debug(f"  Нет коммутаций для соседа {neighbor_obj}")
            return None

        neighbor_rec = self._find_record_by_connect_id(neighbor_comms, connect_id)
        if neighbor_rec is None:
            self.logger.debug(f"  Не найден интерфейс для connect_id {connect_id} у соседа {neighbor_obj}")
            return None

        side = int(neighbor_rec.clps_first) if neighbor_rec.clps_first is not None else 1
        port = int(neighbor_rec.clps_mid) if neighbor_rec.clps_mid is not None else 0
        return Interface(neighbor_obj, side, port)

    # ------------------------------------------------------------------------
    # Обработчики для разных типов объектов
    # ------------------------------------------------------------------------

    def _process_device(self, obj: ObjKey, comms: List[Commutation.Get_data],
                        current_iface: Interface, visited_interfaces: Set[Interface],
                        queue: deque, parent_obj: Optional[ObjKey],
                        stop_on_olt: bool = True) -> None:
        if obj.obj_type != TYPE_OLT:
            if stop_on_olt:
                self.logger.debug(f"Устройство {obj} не OLT, останавливаемся")
                return
            if obj.obj_type == TYPE_CWDM:
                return

        record = self._find_record_for_interface(comms, current_iface)
        if record is None:
            self.logger.debug(f"  Не найдена запись для {current_iface}")
            return

        neighbor_obj = self._get_neighbor_obj_from_record(record)
        if neighbor_obj is None:
            return

        connect_id = record.connect_id
        self.logger.debug(f"  Сосед: {neighbor_obj}, connect_id={connect_id}")

        parent_node_id = self._get_node_id_for_interface(current_iface)
        neighbor_iface = self._get_interface_for_neighbor(neighbor_obj, connect_id, parent_node_id)
        if neighbor_iface is None:
            return

        node_id_for_vertex2 = parent_node_id if neighbor_obj.obj_type == TYPE_CUSTOMER else None
        self._add_edge(current_iface, neighbor_iface, connect_id, node_id_for_vertex2)

        if neighbor_obj.obj_type in SIDE_TYPES:
            if neighbor_iface not in visited_interfaces:
                queue.append((neighbor_iface, neighbor_obj))

    def _process_side_object(self, obj: ObjKey, comms: List[Commutation.Get_data],
                             current_iface: Interface, visited_interfaces: Set[Interface],
                             queue: deque, parent_obj: Optional[ObjKey]) -> None:
        self.logger.debug(f"Обработка объекта со сторонами {obj}")

        record = self._find_record_for_interface(comms, current_iface)
        if record is None:
            self.logger.debug(f"  Не найдена запись для {current_iface}")
            return

        neighbor_obj = self._get_neighbor_obj_from_record(record)
        if neighbor_obj is None:
            return

        connect_id = record.connect_id
        self.logger.debug(f"  Сосед: {neighbor_obj}, connect_id={connect_id}")

        parent_node_id = self._get_node_id_for_interface(current_iface)
        neighbor_iface = self._get_interface_for_neighbor(neighbor_obj, connect_id, parent_node_id)
        if neighbor_iface is None:
            return

        node_id_for_vertex2 = parent_node_id if neighbor_obj.obj_type == TYPE_CUSTOMER else None
        self._add_edge(current_iface, neighbor_iface, connect_id, node_id_for_vertex2)

        # Для кроссов и кабелей — внутреннее ребро на противоположную сторону
        if obj.obj_type in (TYPE_CROSS, TYPE_FIBER):
            opposite_side = 2 if current_iface.side == 1 else 1
            opposite_iface = Interface(obj, opposite_side, current_iface.port)
            self.logger.debug(f"  Внутреннее ребро между {current_iface} и {opposite_iface}")
            self._add_edge(current_iface, opposite_iface, 0, is_internal=True)

            opposite_record = self._find_record_for_interface(comms, opposite_iface)
            if opposite_record is None:
                self.logger.debug(f"  Нет записи на противоположной стороне")
                return

            neighbor_obj_opp = self._get_neighbor_obj_from_record(opposite_record)
            if neighbor_obj_opp is None:
                return

            connect_id_opp = opposite_record.connect_id
            self.logger.debug(f"  Сосед на противоположной стороне: {neighbor_obj_opp}, connect_id={connect_id_opp}")

            parent_node_id_opp = self._get_node_id_for_interface(opposite_iface)
            neighbor_iface_opp = self._get_interface_for_neighbor(neighbor_obj_opp, connect_id_opp, parent_node_id_opp)
            if neighbor_iface_opp is None:
                return

            node_id_for_vertex2_opp = parent_node_id_opp if neighbor_obj_opp.obj_type == TYPE_CUSTOMER else None
            self._add_edge(opposite_iface, neighbor_iface_opp, connect_id_opp, node_id_for_vertex2_opp)

            if neighbor_obj_opp.obj_type in SIDE_TYPES:
                if neighbor_iface_opp not in visited_interfaces:
                    queue.append((neighbor_iface_opp, neighbor_obj_opp))

        # Для сплиттера и CWDM — внутренние рёбра от входа ко всем выходам
        elif obj.obj_type in (TYPE_SPLITTER, TYPE_CWDM):
            if current_iface.side == 1:
                out_records = [rec for rec in comms if rec.clps_first is not None and int(rec.clps_first) == 2]
                self.logger.debug(f"  Найдено выходов: {len(out_records)}")

                for rec in out_records:
                    out_port = rec.clps_mid
                    out_iface = Interface(obj, 2, out_port)
                    self._add_edge(current_iface, out_iface, 0, is_internal=True)

                for rec in out_records:
                    neighbor_obj_out = self._get_neighbor_obj_from_record(rec)
                    if neighbor_obj_out is None:
                        continue

                    connect_id_out = rec.connect_id
                    out_port = rec.clps_mid
                    out_iface = Interface(obj, 2, out_port)

                    parent_node_id_out = self._get_node_id_for_interface(out_iface)
                    neighbor_iface_out = self._get_interface_for_neighbor(neighbor_obj_out, connect_id_out, parent_node_id_out)
                    if neighbor_iface_out is None:
                        continue

                    node_id_for_vertex2_out = parent_node_id_out if neighbor_obj_out.obj_type == TYPE_CUSTOMER else None
                    self._add_edge(out_iface, neighbor_iface_out, connect_id_out, node_id_for_vertex2_out)

                    if neighbor_obj_out.obj_type in SIDE_TYPES:
                        if neighbor_iface_out not in visited_interfaces:
                            queue.append((neighbor_iface_out, neighbor_obj_out))
            else:
                self.logger.debug("  Пришли на выход (side=2), останавливаемся")

    # ------------------------------------------------------------------------
    # Основной метод построения
    # ------------------------------------------------------------------------

    def build(self, object_type: str, object_id: Union[int, str], port: Optional[int] = None) -> 'CommutationGraph':
        self.logger.info(f"=== ПОСТРОЕНИЕ ГРАФА ОТ {object_type}:{object_id} (port={port}) ===")

        if object_type == TYPE_OLT:
            if port is not None:
                return self._build_from_olt(object_id, port)
            else:
                return self._build_all_ports(object_id)

        obj_key = ObjKey(object_type, object_id)
        start_port = port if port is not None else 0
        start_side = 1 if object_type in SIDE_TYPES else 0
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
        self.logger.info(f"--- Построение от всех портов OLT {olt_id}")

        olt_info = self._load_object_info(ObjKey(TYPE_OLT, olt_id))
        ifaces = olt_info.get('ifaces', {})
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
        has_splitter = any(v['obj_type'] == TYPE_SPLITTER for v in self.vs)
        has_cwdm = any(v['obj_type'] == TYPE_CWDM for v in self.vs)
        has_customer = any(v['obj_type'] == TYPE_CUSTOMER for v in self.vs)
        self._directed = has_splitter or has_cwdm or has_customer

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
    node_id: int


@dataclass(frozen=True)
class FiberEdge:
    fiber_id: int
    node1_id: int
    node2_id: int


class FNGraph(ig.Graph):
    """
    Граф сооружений связи и кабелей.
    Вершины — node_id, рёбра — fiber_id.

    Использует общие кэши для данных Node.get и Fiber.get_list,
    чтобы ускорить построение при повторных вызовах.
    """

    # Общие кэши для всех экземпляров (для экономии времени)
    _global_node_cache: Dict[int, Dict[str, Any]] = {}
    _global_fiber_cache: Dict[int, List[Any]] = {}

    def __init__(self, client: WorkerNetClient,
                 commutation_graph: Optional[CommutationGraph] = None,
                 **kwargs):
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()

        self._commutation_graph = commutation_graph

        # Сопоставление node_id -> индекс вершины в этом графе
        self._vertex_index: Dict[int, int] = {}

        self._built = False

    # ------------------------------------------------------------------------
    # Загрузка информации о вершинах (использует глобальный кэш)
    # ------------------------------------------------------------------------

    def _load_node_info(self, node_id: int) -> Dict[str, Any]:
        if node_id in self._global_node_cache:
            return self._global_node_cache[node_id]

        info = {}
        try:
            result = self.client.Node.get(id=node_id)
            if result and len(result) > 0:
                node = result[0]
                info['node_id'] = getattr(node, 'id', None)
                info['address_id'] = getattr(node, 'address_id', None)
                info['coordinates'] = getattr(node, 'coordinates', None)
                info['type'] = getattr(node, 'type', None)
                info['number'] = getattr(node, 'number', None)
                info['comment'] = getattr(node, 'comment', None)
                info['location'] = getattr(node, 'location', None)
                info['is_planned'] = getattr(node, 'is_planned', None)
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить информацию для node {node_id}: {e}")

        self._global_node_cache[node_id] = info
        return info

    def get_node_info(self, node_id: int) -> Dict[str, Any]:
        return self._load_node_info(node_id)

    # ------------------------------------------------------------------------
    # Загрузка кабелей для узла (использует глобальный кэш)
    # ------------------------------------------------------------------------

    def _load_fibers_for_node(self, node_id: int) -> List[Any]:
        if node_id in self._global_fiber_cache:
            return self._global_fiber_cache[node_id]

        try:
            result = self.client.Fiber.get_list(node_id=node_id)
            fibers = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кабелей для узла {node_id}: {e}")
            fibers = []

        self._global_fiber_cache[node_id] = fibers
        return fibers

    # ------------------------------------------------------------------------
    # Добавление вершин и рёбер
    # ------------------------------------------------------------------------

    def _add_vertex(self, node_id: int) -> int:
        if node_id in self._vertex_index:
            return self._vertex_index[node_id]

        info = self._load_node_info(node_id)
        # print(info.get('number'))

        idx = self.add_vertex(
            node_id=node_id,
            address_id=info.get('address_id'),
            coordinates=str(info.get('coordinates')) if info.get('coordinates') else None,
            type=info.get('type'),
            number=info.get('number'),
            comment=info.get('comment'),
            location=info.get('location'),
            is_planned=info.get('is_planned'),
            name=f"node:{node_id}"
        ).index

        self._vertex_index[node_id] = idx
        return idx

    def _add_edge(self, node1_id: int, node2_id: int, fiber_id: int) -> None:
        if node1_id == node2_id:
            self.logger.debug(f"Петля для кабеля {fiber_id} (node1=node2={node1_id}), пропускаем")
            return

        idx1 = self._add_vertex(node1_id)
        idx2 = self._add_vertex(node2_id)

        if self.are_connected(idx1, idx2):
            # добавляем параллельное ребро
            pass

        self.add_edge(idx1, idx2, fiber_id=fiber_id)

    # ------------------------------------------------------------------------
    # Построение из CommutationGraph (использует его кэши, если возможно)
    # ------------------------------------------------------------------------

    def _build_from_commutation_graph(self, included_fibers: Optional[Set[int]] = None,
                                      excluded_fibers: Optional[Set[int]] = None) -> None:
        if self._commutation_graph is None:
            self.logger.error("CommutationGraph не передан, невозможно построить граф")
            return

        cg = self._commutation_graph
        fiber_groups: Dict[int, Set[int]] = defaultdict(set)

        # Проходим по вершинам кабелей в CommutationGraph
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
                # Кабель висит на одном узле — тупик, не добавляем ребро (но можно было бы добавить петлю)
                self.logger.debug(f"Кабель {fiber_id} имеет только один узел {node_list[0]}, тупик")
            else:
                self.logger.warning(f"Кабель {fiber_id} имеет более двух узлов: {nodes}, пропускаем")

    # ------------------------------------------------------------------------
    # Построение через API (BFS от стартового узла) с общими кэшами
    # ------------------------------------------------------------------------

    def _build_from_api(self, start_node_id: int,
                        included_fibers: Optional[Set[int]] = None,
                        excluded_fibers: Optional[Set[int]] = None) -> None:
        visited_nodes: Set[int] = set()
        queue = deque([start_node_id])

        while queue:
            current_node = queue.popleft()
            if current_node in visited_nodes:
                continue
            visited_nodes.add(current_node)

            self._add_vertex(current_node)

            fibers = self._load_fibers_for_node(current_node)
            for fiber in fibers:
                fiber_id = getattr(fiber, 'code', None)
                if fiber_id is None:
                    self.logger.warning("Пропущен кабель без code")
                    continue

                if included_fibers is not None and fiber_id not in included_fibers:
                    continue
                if excluded_fibers is not None and fiber_id in excluded_fibers:
                    continue

                node1 = getattr(fiber, 'node1_id', None)
                node2 = getattr(fiber, 'node2_id', None)
                if node1 is None or node2 is None:
                    self.logger.warning(f"Кабель {fiber_id} без node1_id или node2_id")
                    continue

                if node1 == current_node:
                    neighbor = node2
                elif node2 == current_node:
                    neighbor = node1
                else:
                    self.logger.warning(f"Кабель {fiber_id} не связан с узлом {current_node}")
                    continue

                self._add_edge(current_node, neighbor, fiber_id)

                if neighbor not in visited_nodes:
                    queue.append(neighbor)

    # ------------------------------------------------------------------------
    # Основной метод построения
    # ------------------------------------------------------------------------

    def build(self, start_node_id: int,
              included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
              excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None) -> 'FNGraph':
        self.logger.info("=== ПОСТРОЕНИЕ ГРАФА FN ===")

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
        return {
            'num_vertices': self.vcount(),
            'num_edges': self.ecount(),
            'start_node_id': self.vs[0]['node_id'] if self.vcount() > 0 else None,
        }

    def export_graphml(self, filename: str) -> None:
        self.write_graphml(filename)

    def __repr__(self) -> str:
        return f"FNGraph(nodes={self.vcount()}, fibers={self.ecount()})"