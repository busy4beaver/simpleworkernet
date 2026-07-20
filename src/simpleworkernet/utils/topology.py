# simpleworkernet/utils/topology.py
"""
Модуль Topology — высокоуровневый API для построения и анализа топологии сети.

Использует общий глобальный кэш DataCache из graph.py.
Хранит список связных CGraph (каждый — отдельная компонента связности) и один связный FNGraph.
Предоставляет методы для построения графов от различных объектов сети, получения статистики,
а также построения линейных графов (topology_from_commutation).

Все данные загружаются через DataCache, что обеспечивает единое кэширование.
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable, Literal
from collections import deque, defaultdict
import igraph as ig

from ..core.client import WorkerNetClient
from ..models.categories import Commutation, Device, Cross, Splitter, Fiber, Customer, Node, Cwdm
from .graph import (
    CGraph, FNGraph, DataCache, ObjKey, Interface,
    TYPE_CUSTOMER, TYPE_FIBER, TYPE_SPLITTER, TYPE_CROSS, TYPE_CWDM,
    TYPE_SWITCH, TYPE_OLT, TYPE_ONU,
    DEVICE_TYPES, SIDE_TYPES, TERMINAL_TYPES,
    _data_cache
)

_logger = None

def _get_logger():
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger


class Topology:
    """
    Класс для построения и анализа топологии сети.
    Содержит список связных CGraph и один связный FNGraph.
    Использует общий глобальный кэш DataCache.
    """

    _data_version = '1.0'

    def __init__(self, client: WorkerNetClient):
        self.client: WorkerNetClient = client
        self.logger = _get_logger()
        self._cache:DataCache = _data_cache
        # self._cache.load_all(client)
        self.cgraphs: List[CGraph] = []          # список связных графов коммутаций
        self.fngraph: Optional[FNGraph] = None   # единственный связный граф сооружений

    # ------------------------------------------------------------------------
    # Внутренние методы для загрузки объектов (используют DataCache)
    # ------------------------------------------------------------------------

    def _load_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        """
        Загружает объект по типу и ID через DataCache.
        Используется в методах customer, node, cable, fiber, device, splitter, cwdm, cross.
        """
        if obj_type == TYPE_CUSTOMER:
            return self._cache.get_customer(self.client, int(obj_id))
        elif obj_type == 'node':
            return self._cache.get_node(self.client, int(obj_id))
        elif obj_type == TYPE_FIBER:
            return self._cache.get_fiber(self.client, int(obj_id))
        elif obj_type in DEVICE_TYPES:
            return self._cache.get_device(self.client, obj_type, int(obj_id))
        elif obj_type == TYPE_SPLITTER:
            return self._cache.get_splitter(self.client, int(obj_id))
        elif obj_type == TYPE_CWDM:
            return self._cache.get_cwdm(self.client, int(obj_id))
        elif obj_type == TYPE_CROSS:
            return self._cache.get_cross(self.client, str(obj_id))
        else:
            return None

    def _get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> List[Commutation.Get_data]:
        """Загружает коммутации для объекта через DataCache (без finish-записей)."""
        return self._cache.get_commutations_by_object(self.client, obj_type, obj_id, is_finish_data=0)

    # ------------------------------------------------------------------------
    # Внутренние методы для работы с графами
    # ------------------------------------------------------------------------

    def _normalize_set(self, value: Optional[Union[int, List[int], Set[int]]]) -> Optional[Set[int]]:
        """Приводит значение к множеству int."""
        if value is None:
            return None
        if isinstance(value, (int, str)):
            return {int(value)}
        return set(value)

    def _add_cgraph(self, cgraph: CGraph) -> None:
        """Добавляет связный CGraph в список."""
        if cgraph is None or cgraph.vcount() == 0:
            return
        if not cgraph.is_connected():
            self.logger.warning("Граф не связный, не добавляем")
            return
        self.cgraphs.append(cgraph)

    def _set_fngraph(self, fngraph: FNGraph) -> None:
        """Устанавливает единственный связный FNGraph."""
        if fngraph is None or fngraph.vcount() == 0:
            return
        if not fngraph.is_connected():
            self.logger.warning("FNGraph не связный, не устанавливаем")
            return
        self.fngraph = fngraph

    def _build_fngraph_from_cgraph(self, cgraph: CGraph) -> Optional[FNGraph]:
        """Строит FNGraph из CGraph."""
        if cgraph is None or cgraph.vcount() == 0:
            return None
        fngraph = FNGraph(self.client, commutation_graph=cgraph, cache=self._cache)
        fngraph.build(0)  # start_node_id не используется при построении из CGraph
        return fngraph if fngraph.vcount() > 0 else None

    def _merge_cgraphs(self, graphs: List[CGraph]) -> Optional[CGraph]:
        """
        Объединяет несколько CGraph в один, если они пересекаются по вершинам.
        Если объединённый граф связный, возвращает его, иначе None.
        """
        if not graphs:
            return None
        if len(graphs) == 1:
            return graphs[0]

        merged = CGraph(self.client, cache=self._cache)
        merged._vertex_index = {}
        iface_to_idx: Dict[Interface, int] = {}
        obj_cache: Dict[ObjKey, Any] = {}

        for g in graphs:
            for v in g.vs:
                iface = None
                for iface_candidate, idx in g._vertex_index.items():
                    if idx == v.index:
                        iface = iface_candidate
                        break
                if iface is None:
                    continue

                if iface not in iface_to_idx:
                    obj = v['api_obj']
                    if obj is not None and iface.obj not in obj_cache:
                        obj_cache[iface.obj] = obj
                    attrs = {key: v[key] for key in v.attributes()}
                    idx = merged.add_vertex(**attrs).index
                    iface_to_idx[iface] = idx
                    merged._vertex_index[iface] = idx

            for e in g.es:
                v1 = g.vs[e.source]
                v2 = g.vs[e.target]
                iface1 = None
                iface2 = None
                for iface_candidate, idx in g._vertex_index.items():
                    if idx == e.source:
                        iface1 = iface_candidate
                    if idx == e.target:
                        iface2 = iface_candidate
                    if iface1 is not None and iface2 is not None:
                        break

                if iface1 is None or iface2 is None:
                    continue

                if iface1 in iface_to_idx and iface2 in iface_to_idx:
                    idx1 = iface_to_idx[iface1]
                    idx2 = iface_to_idx[iface2]
                    if not merged.are_connected(idx1, idx2):
                        attrs = {key: e[key] for key in e.attributes()}
                        merged.add_edge(idx1, idx2, **attrs)

        merged._update_directed_flag()
        if merged.is_connected():
            return merged
        else:
            self.logger.warning("Объединённый граф не связный, возвращаем None")
            return None

    def _merge_fngraphs(self, graphs: List[FNGraph]) -> Optional[FNGraph]:
        """Объединяет несколько FNGraph в один, если они пересекаются по узлам."""
        if not graphs:
            return None
        if len(graphs) == 1:
            return graphs[0]

        merged = FNGraph(self.client, cache=self._cache)
        merged._vertex_index = {}
        node_to_idx: Dict[int, int] = {}

        for g in graphs:
            for v in g.vs:
                node_id = v['node_id']
                if node_id not in node_to_idx:
                    attrs = {key: v[key] for key in v.attributes()}
                    idx = merged.add_vertex(**attrs).index
                    node_to_idx[node_id] = idx
                    merged._vertex_index[node_id] = idx

            for e in g.es:
                v1 = g.vs[e.source]
                v2 = g.vs[e.target]
                node1 = v1['node_id']
                node2 = v2['node_id']
                if node1 in node_to_idx and node2 in node_to_idx:
                    idx1 = node_to_idx[node1]
                    idx2 = node_to_idx[node2]
                    if not merged.are_connected(idx1, idx2):
                        attrs = {key: e[key] for key in e.attributes()}
                        merged.add_edge(idx1, idx2, **attrs)

        if merged.is_connected():
            return merged
        else:
            self.logger.warning("Объединённый FNGraph не связный, возвращаем None")
            return None

    def _build_cgraph_from_object(self, obj_type: str, obj_id: Union[int, str],
                                   port: Optional[int] = None,
                                   side: Optional[int] = None,
                                   included_fibers: Optional[Set[int]] = None,
                                   excluded_fibers: Optional[Set[int]] = None,
                                   excluded_nodes: Optional[Set[int]] = None) -> Optional[CGraph]:
        """
        Строит один связный CGraph от указанного объекта.
        Фильтры передаются в CGraph.build.
        """
        cgraph = CGraph(self.client, cache=self._cache)

        # Для кабеля с side=None строим от обеих сторон и объединяем
        if obj_type == TYPE_FIBER and side is None and port is not None:
            graphs = []
            for s in [1, 2]:
                try:
                    g = CGraph(self.client, cache=self._cache)
                    g.build(obj_type, obj_id, port=port, side=s,
                            included_fibers=included_fibers,
                            excluded_fibers=excluded_fibers,
                            excluded_nodes=excluded_nodes)
                    if g.vcount() > 0 and g.is_connected():
                        graphs.append(g)
                except Exception as e:
                    self.logger.warning(f"Ошибка построения от кабеля {obj_id} side={s}: {e}")
            if graphs:
                if len(graphs) == 1:
                    return graphs[0]
                else:
                    merged = self._merge_cgraphs(graphs)
                    if merged is not None and merged.is_connected():
                        return merged
                    else:
                        self.logger.warning("Не удалось объединить графы кабеля в один связный, возвращаем первый")
                        return graphs[0]
            return None

        # Общий случай
        try:
            cgraph.build(obj_type, obj_id, port=port, side=side,
                         included_fibers=included_fibers,
                         excluded_fibers=excluded_fibers,
                         excluded_nodes=excluded_nodes)
            if cgraph.vcount() == 0 or not cgraph.is_connected():
                return None
            return cgraph
        except Exception as e:
            self.logger.error(f"Ошибка построения CGraph от {obj_type}:{obj_id}: {e}")
            return None

    # ------------------------------------------------------------------------
    # Методы получения finish-данных
    # ------------------------------------------------------------------------

    def get_finish_by_node(self, node_id: int) -> List[Commutation.Get_data]:
        """
        Возвращает список уникальных finish-объектов (clps_last == 'finish')
        для конечных вершин (terminate_vertex=True) в указанном узле.
        """
        result: List[Commutation.Get_data] = []
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v['node_id'] != node_id:
                    continue
                if 'terminate_vertex' in v.attributes() and v['terminate_vertex']:
                    if 'finish_data' in v.attributes():
                        finish_data = v['finish_data']
                        if finish_data:
                            result.extend(finish_data)
        # Удаляем дубликаты по connect_id
        seen = set()
        unique = []
        for item in result:
            if item.connect_id not in seen:
                seen.add(item.connect_id)
                unique.append(item)
        return unique

    def get_finish_by_object(self, object_type: str, object_id: Union[int, str]) -> Optional[Commutation.Get_data]:
        """
        Возвращает finish-объект для указанного объекта, если он есть в графе.
        terminate_vertex не проверяется.
        """
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v['obj_type'] == object_type and str(v['obj_id']) == str(object_id):
                    if 'finish_data' in v.attributes():
                        finish_data = v['finish_data']
                        if finish_data:
                            return finish_data[0]
                    return None
        return None

    # ------------------------------------------------------------------------
    # Основные методы построения
    # ------------------------------------------------------------------------

    def _reset(self) -> None:
        """Сбрасывает текущие графы перед новым построением."""
        self.cgraphs = []
        self.fngraph = None

    def build_from_device(self, object_type: str, object_id: int, port: Optional[int] = None,
                          included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                          excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                          excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM DEVICE: {object_type}:{object_id} (port={port}) ===")
        cgraph = self._build_cgraph_from_object(
            object_type, object_id, port=port,
            included_fibers=self._normalize_set(included_fibers),
            excluded_fibers=self._normalize_set(excluded_fibers),
            excluded_nodes=self._normalize_set(excluded_nodes)
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                if self.fngraph is None:
                    self._set_fngraph(fngraph)
                else:
                    merged = self._merge_fngraphs([self.fngraph, fngraph])
                    if merged is not None:
                        self._set_fngraph(merged)
        return self

    def build_from_customer(self, object_id: int,
                            included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                            excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                            excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM CUSTOMER: {object_id} ===")
        cgraph = self._build_cgraph_from_object(
            TYPE_CUSTOMER, object_id, port=None,
            included_fibers=self._normalize_set(included_fibers),
            excluded_fibers=self._normalize_set(excluded_fibers),
            excluded_nodes=self._normalize_set(excluded_nodes)
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                self._set_fngraph(fngraph)
        return self

    def build_from_cross(self, object_id: str, port: Optional[int] = None, side: Optional[int] = None,
                         included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM CROSS: {object_id} (port={port}, side={side}) ===")
        included_fibers_set = self._normalize_set(included_fibers)
        excluded_fibers_set = self._normalize_set(excluded_fibers)
        excluded_nodes_set = self._normalize_set(excluded_nodes)

        if port is None:
            # Строим от всех портов кросса
            comms = self._get_commutations(TYPE_CROSS, object_id)
            if not comms:
                self.logger.warning(f"У кросса {object_id} нет коммутаций")
                return self
            ports = set()
            for rec in comms:
                if getattr(rec, 'clps_last', None) == 'finish':
                    continue
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if p > 0:
                    ports.add(p)
            if not ports:
                self.logger.warning(f"У кросса {object_id} нет портов с ID")
                return self
            for p in ports:
                cgraph = self._build_cgraph_from_object(
                    TYPE_CROSS, object_id, port=p, side=None,
                    included_fibers=included_fibers_set,
                    excluded_fibers=excluded_fibers_set,
                    excluded_nodes=excluded_nodes_set
                )
                if cgraph is not None:
                    self._add_cgraph(cgraph)
                    fngraph = self._build_fngraph_from_cgraph(cgraph)
                    if fngraph is not None:
                        if self.fngraph is None:
                            self._set_fngraph(fngraph)
                        else:
                            merged = self._merge_fngraphs([self.fngraph, fngraph])
                            if merged is not None:
                                self._set_fngraph(merged)
            return self

        cgraph = self._build_cgraph_from_object(
            TYPE_CROSS, object_id, port=port, side=side,
            included_fibers=included_fibers_set,
            excluded_fibers=excluded_fibers_set,
            excluded_nodes=excluded_nodes_set
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                self._set_fngraph(fngraph)
        return self

    def build_from_splitter(self, object_id: int, port: Optional[int] = None, side: Optional[int] = None,
                            included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                            excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                            excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM SPLITTER: {object_id} (port={port}, side={side}) ===")
        if port is None and side is None:
            comms = self._get_commutations(TYPE_SPLITTER, object_id)
            if not comms:
                self.logger.warning(f"У сплиттера {object_id} нет коммутаций")
                return self
            interfaces = set()
            for rec in comms:
                if getattr(rec, 'clps_last', None) == 'finish':
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph_from_object(
                    TYPE_SPLITTER, object_id, port=p, side=s,
                    included_fibers=self._normalize_set(included_fibers),
                    excluded_fibers=self._normalize_set(excluded_fibers),
                    excluded_nodes=self._normalize_set(excluded_nodes)
                )
                if g is not None and g.is_connected():
                    graphs.append(g)
            if graphs:
                merged = self._merge_cgraphs(graphs)
                if merged is not None and merged.is_connected():
                    self._add_cgraph(merged)
                    fngraph = self._build_fngraph_from_cgraph(merged)
                    if fngraph is not None:
                        self._set_fngraph(fngraph)
            return self

        cgraph = self._build_cgraph_from_object(
            TYPE_SPLITTER, object_id, port=port, side=side,
            included_fibers=self._normalize_set(included_fibers),
            excluded_fibers=self._normalize_set(excluded_fibers),
            excluded_nodes=self._normalize_set(excluded_nodes)
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                self._set_fngraph(fngraph)
        return self

    def build_from_cwdm(self, object_id: int, port: Optional[int] = None, side: Optional[int] = None,
                        included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                        excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                        excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM CWDM: {object_id} (port={port}, side={side}) ===")
        if port is None and side is None:
            comms = self._get_commutations(TYPE_CWDM, object_id)
            if not comms:
                self.logger.warning(f"У CWDM {object_id} нет коммутаций")
                return self
            interfaces = set()
            for rec in comms:
                if getattr(rec, 'clps_last', None) == 'finish':
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph_from_object(
                    TYPE_CWDM, object_id, port=p, side=s,
                    included_fibers=self._normalize_set(included_fibers),
                    excluded_fibers=self._normalize_set(excluded_fibers),
                    excluded_nodes=self._normalize_set(excluded_nodes)
                )
                if g is not None and g.is_connected():
                    graphs.append(g)
            if graphs:
                merged = self._merge_cgraphs(graphs)
                if merged is not None and merged.is_connected():
                    self._add_cgraph(merged)
                    fngraph = self._build_fngraph_from_cgraph(merged)
                    if fngraph is not None:
                        self._set_fngraph(fngraph)
            return self

        cgraph = self._build_cgraph_from_object(
            TYPE_CWDM, object_id, port=port, side=side,
            included_fibers=self._normalize_set(included_fibers),
            excluded_fibers=self._normalize_set(excluded_fibers),
            excluded_nodes=self._normalize_set(excluded_nodes)
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                self._set_fngraph(fngraph)
        return self

    def build_from_fiber(self, object_id: int, port: int, side: Optional[int] = None,
                         included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM FIBER: cable={object_id}, port={port}, side={side} ===")
        cgraph = self._build_cgraph_from_object(
            TYPE_FIBER, object_id, port=port, side=side,
            included_fibers=self._normalize_set(included_fibers),
            excluded_fibers=self._normalize_set(excluded_fibers),
            excluded_nodes=self._normalize_set(excluded_nodes)
        )
        if cgraph is not None:
            self._add_cgraph(cgraph)
            fngraph = self._build_fngraph_from_cgraph(cgraph)
            if fngraph is not None:
                self._set_fngraph(fngraph)
        return self

    def build_from_node(self, object_id: int,
                        included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                        excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                        excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM NODE: {object_id} ===")
        included_fibers_set = self._normalize_set(included_fibers)
        excluded_fibers_set = self._normalize_set(excluded_fibers)
        excluded_nodes_set = self._normalize_set(excluded_nodes)

        # Строим FNGraph от узла (через API)
        fngraph = FNGraph(self.client, cache=self._cache)
        fngraph.build(object_id,
                      included_fibers=included_fibers_set,
                      excluded_fibers=excluded_fibers_set,
                      excluded_nodes=excluded_nodes_set)
        if fngraph.vcount() == 0:
            self.logger.warning(f"Не удалось построить FNGraph от узла {object_id}")
            return self
        self._set_fngraph(fngraph)

        # Для каждого узла в FNGraph находим объекты и строим CGraph
        node_ids = [v['node_id'] for v in fngraph.vs]
        for node_id in node_ids:
            if excluded_nodes_set is not None and node_id in excluded_nodes_set:
                continue
            self.logger.debug(f"Поиск объектов в узле {node_id}")
            objects_in_node = self._get_objects_for_node(node_id)
            if not objects_in_node:
                continue
            for obj_type, obj_id, port_info in objects_in_node:
                # Проверяем, есть ли объект уже в каком-либо CGraph
                obj_key = ObjKey(obj_type, obj_id)
                if self._find_cgraph_for_object(obj_key) is not None:
                    self.logger.debug(f"Объект {obj_key} уже есть в графе, пропускаем")
                    continue
                try:
                    if obj_type == TYPE_CROSS:
                        if port_info is None:
                            continue
                        if port_info.get('port') is not None:
                            cgraph = self._build_cgraph_from_object(
                                obj_type, obj_id, port=port_info['port'], side=port_info.get('side'),
                                included_fibers=included_fibers_set,
                                excluded_fibers=excluded_fibers_set,
                                excluded_nodes=excluded_nodes_set
                            )
                            if cgraph is not None:
                                self._add_cgraph(cgraph)
                    else:
                        cgraph = self._build_cgraph_from_object(
                            obj_type, obj_id, port=port_info,
                            included_fibers=included_fibers_set,
                            excluded_fibers=excluded_fibers_set,
                            excluded_nodes=excluded_nodes_set
                        )
                        if cgraph is not None:
                            self._add_cgraph(cgraph)
                except Exception as e:
                    self.logger.warning(f"Ошибка построения от {obj_type}:{obj_id}: {e}")
        return self

    def build_from_cable(self, object_id: int,
                         included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
                         excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None) -> 'Topology':
        self._reset()
        self.logger.info(f"=== BUILD FROM CABLE: {object_id} ===")
        included_fibers_set = self._normalize_set(included_fibers)
        excluded_fibers_set = self._normalize_set(excluded_fibers)
        excluded_nodes_set = self._normalize_set(excluded_nodes)

        comms = self._get_commutations(TYPE_FIBER, object_id)
        if not comms:
            self.logger.warning(f"У кабеля {object_id} нет волокон")
            return self
        if included_fibers_set is not None and object_id not in included_fibers_set:
            self.logger.warning(f"Кабель {object_id} не в included_fibers")
            return self
        if excluded_fibers_set is not None and object_id in excluded_fibers_set:
            self.logger.warning(f"Кабель {object_id} в excluded_fibers")
            return self

        fiber_ports = set()
        for rec in comms:
            if getattr(rec, 'clps_last', None) == 'finish':
                continue
            fiber_id = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if fiber_id > 0:
                fiber_ports.add(fiber_id)
        if not fiber_ports:
            self.logger.warning(f"В кабеле {object_id} нет волокон с ID")
            return self

        for fiber_port in fiber_ports:
            cgraph = self._build_cgraph_from_object(
                TYPE_FIBER, object_id, port=fiber_port, side=None,
                included_fibers=included_fibers_set,
                excluded_fibers=excluded_fibers_set,
                excluded_nodes=excluded_nodes_set
            )
            if cgraph is not None:
                self._add_cgraph(cgraph)
                fngraph = self._build_fngraph_from_cgraph(cgraph)
                if fngraph is not None:
                    if self.fngraph is None:
                        self._set_fngraph(fngraph)
                    else:
                        merged = self._merge_fngraphs([self.fngraph, fngraph])
                        if merged is not None:
                            self._set_fngraph(merged)
        return self

    # ------------------------------------------------------------------------
    # Метод topology_from_commutation (построение линейного графа)
    # ------------------------------------------------------------------------

    def topology_from_commutation(self,
                                  last_object_type: Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer'],
                                  last_object_id: Union[int, str],
                                  port: Optional[int] = None,
                                  side: Optional[int] = None,
                                  first_object_type: Optional[Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer']] = None,
                                  first_object_id: Optional[Union[int, str]] = None) -> 'Topology':
        """
        Строит линейный граф (цепочку) от указанного последнего объекта в направлении к начальному объекту
        и возвращает новый Topology, содержащий этот линейный граф.
        """
        self.logger.info(f"=== TOPOLOGY FROM COMMUTATION: last={last_object_type}:{last_object_id} (port={port}, side={side}) ===")

        linear_cgraph = self._trace_from_commutation_internal(
            last_object_type, last_object_id, port, side, first_object_type, first_object_id
        )

        new_topology = Topology(self.client)
        new_topology._add_cgraph(linear_cgraph)
        fngraph = new_topology._build_fngraph_from_cgraph(linear_cgraph)
        if fngraph is not None:
            new_topology._set_fngraph(fngraph)

        self.logger.info(f"Создан новый Topology с линейным графом: {linear_cgraph.vcount()} вершин, {linear_cgraph.ecount()} рёбер")
        return new_topology

    def _trace_from_commutation_internal(self,
                                         last_object_type: Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer'],
                                         last_object_id: Union[int, str],
                                         port: Optional[int] = None,
                                         side: Optional[int] = None,
                                         first_object_type: Optional[Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer']] = None,
                                         first_object_id: Optional[Union[int, str]] = None) -> CGraph:
        """
        Внутренний метод, реализующий построение линейного графа.
        Проходит по одному соседу, выбирая внешнее ребро, если есть, иначе внутреннее.
        При ветвлении использует кратчайший путь до first_object (если задан).
        """
        self.logger.debug(f"=== INTERNAL LINEAR TRACE: last={last_object_type}:{last_object_id} (port={port}, side={side}) ===")

        if not self.cgraphs:
            raise ValueError("Нет построенных графов. Сначала вызовите один из методов build_from_*")

        last_obj_key = ObjKey(last_object_type, last_object_id)

        # --- Проверка обязательности параметров ---
        if last_object_type == TYPE_SPLITTER and port is None:
            raise ValueError("Для сплиттера порт обязателен")

        if last_object_type in SIDE_TYPES and side is None:
            raise ValueError(f"Для объекта {last_object_type} необходимо указать сторону (side)")

        if last_object_type not in SIDE_TYPES and last_object_type not in TERMINAL_TYPES:
            raise ValueError(f"Неподдерживаемый тип объекта: {last_object_type}")

        # --- Определение стартового интерфейса ---
        if last_object_type in TERMINAL_TYPES:
            if port is None:
                comms = self._get_commutations(last_object_type, last_object_id)
                if len(comms) > 1 and (first_object_type is None or first_object_id is None):
                    raise ValueError(
                        f"Объект {last_object_type}:{last_object_id} имеет несколько коммутаций, "
                        "необходимо указать first_object для выбора направления"
                    )
                if len(comms) == 1:
                    p = int(comms[0].clps_first) if comms[0].clps_first is not None else 1
                    last_iface = Interface(last_obj_key, side=1, port=p)
                else:
                    return self._trace_from_terminal_with_multiple_comms(
                        last_obj_key, first_object_type, first_object_id
                    )
            else:
                last_iface = Interface(last_obj_key, side=1, port=port)
        else:
            if port is None:
                raise ValueError(f"Для объекта {last_object_type} необходимо указать порт")
            if side is None:
                raise ValueError(f"Для объекта {last_object_type} необходимо указать сторону (side)")
            last_iface = Interface(last_obj_key, side=side, port=port)

        # --- Поиск графа, содержащего интерфейс ---
        candidate_graphs = [cg for cg in self.cgraphs if last_iface in cg._vertex_index]
        if not candidate_graphs:
            raise ValueError(f"Интерфейс {last_iface} не найден ни в одном из построенных графов")

        if len(candidate_graphs) > 1 and (first_object_type is None or first_object_id is None):
            raise ValueError(
                f"Интерфейс {last_iface} найден в нескольких графах. "
                "Укажите first_object для выбора."
            )

        selected_cgraph = None
        if first_object_type is not None and first_object_id is not None:
            first_obj_key = ObjKey(first_object_type, first_object_id)
            for cg in candidate_graphs:
                for v in cg.vs:
                    if v['obj_type'] == first_object_type and str(v['obj_id']) == str(first_object_id):
                        selected_cgraph = cg
                        break
                if selected_cgraph is not None:
                    break
            if selected_cgraph is None:
                raise ValueError(
                    f"Граф с объектом {first_object_type}:{first_object_id} не найден "
                    "среди графов, содержащих last интерфейс"
                )
        else:
            selected_cgraph = candidate_graphs[0]

        # --- Линейный обход от last_iface ---
        current = last_iface
        prev = None
        path = [current]
        self.logger.debug(f"Начинаем линейный обход от {current}")

        while True:
            current_idx = selected_cgraph._vertex_index[current]
            current_attrs = selected_cgraph.vs[current_idx]
            current_type = current_attrs['obj_type']

            incident_edges = selected_cgraph.incident(current_idx, mode='all')
            external_neighbors = []
            internal_neighbors = []

            for eid in incident_edges:
                edge = selected_cgraph.es[eid]
                if edge.source == current_idx:
                    neighbor_idx = edge.target
                else:
                    neighbor_idx = edge.source

                n_iface = None
                for iface, idx in selected_cgraph._vertex_index.items():
                    if idx == neighbor_idx:
                        n_iface = iface
                        break
                if n_iface is None:
                    continue
                if n_iface == prev:
                    continue

                if edge['is_internal']:
                    internal_neighbors.append(n_iface)
                else:
                    external_neighbors.append(n_iface)

            # Определяем следующего соседа
            next_iface = None
            if external_neighbors:
                if len(external_neighbors) == 1:
                    next_iface = external_neighbors[0]
                    self.logger.debug(f"Выбрано внешнее ребро к {next_iface}")
                else:
                    # Ветвление – пытаемся найти путь до first_object
                    if first_object_type is not None and first_object_id is not None:
                        self.logger.debug(f"Несколько внешних рёбер, ищем путь до first_object")
                        target_idx = None
                        for v in selected_cgraph.vs:
                            if v['obj_type'] == first_object_type and str(v['obj_id']) == str(first_object_id):
                                target_idx = v.index
                                break
                        if target_idx is None:
                            raise ValueError(f"Целевой объект {first_object_type}:{first_object_id} не найден в графе")
                        try:
                            paths = selected_cgraph.get_shortest_paths(current_idx, target_idx, mode='all')
                            if not paths or not paths[0]:
                                raise ValueError("Путь не найден")
                            shortest_path = paths[0]
                            for idx in shortest_path[1:]:
                                n_iface = None
                                for iface, i in selected_cgraph._vertex_index.items():
                                    if i == idx:
                                        n_iface = iface
                                        break
                                if n_iface is None:
                                    raise ValueError(f"Не удалось найти интерфейс для вершины {idx}")
                                path.append(n_iface)
                            self.logger.info(f"Построен путь до first_object: {len(path)} вершин")
                            break
                        except Exception as e:
                            raise ValueError(f"Ошибка при поиске пути до first_object: {e}")
                    else:
                        raise ValueError(
                            f"Обнаружено ветвление на объекте {current_type}:{current_attrs['obj_id']}. "
                            "Невозможно построить линейный граф. Укажите first_object явно."
                        )
            elif internal_neighbors:
                if len(internal_neighbors) == 1:
                    next_iface = internal_neighbors[0]
                    self.logger.debug(f"Выбрано внутреннее ребро к {next_iface}")
                else:
                    # Ветвление на внутренних рёбрах (например, несколько выходов сплиттера)
                    if first_object_type is not None and first_object_id is not None:
                        self.logger.debug(f"Несколько внутренних рёбер, ищем путь до first_object")
                        target_idx = None
                        for v in selected_cgraph.vs:
                            if v['obj_type'] == first_object_type and str(v['obj_id']) == str(first_object_id):
                                target_idx = v.index
                                break
                        if target_idx is None:
                            raise ValueError(f"Целевой объект {first_object_type}:{first_object_id} не найден в графе")
                        try:
                            paths = selected_cgraph.get_shortest_paths(current_idx, target_idx, mode='all')
                            if not paths or not paths[0]:
                                raise ValueError("Путь не найден")
                            shortest_path = paths[0]
                            for idx in shortest_path[1:]:
                                n_iface = None
                                for iface, i in selected_cgraph._vertex_index.items():
                                    if i == idx:
                                        n_iface = iface
                                        break
                                if n_iface is None:
                                    raise ValueError(f"Не удалось найти интерфейс для вершины {idx}")
                                path.append(n_iface)
                            self.logger.info(f"Построен путь до first_object: {len(path)} вершин")
                            break
                        except Exception as e:
                            raise ValueError(f"Ошибка при поиске пути до first_object: {e}")
                    else:
                        raise ValueError(
                            f"Обнаружено ветвление на объекте {current_type}:{current_attrs['obj_id']} (несколько внутренних рёбер). "
                            "Невозможно построить линейный граф. Укажите first_object явно."
                        )
            else:
                # Нет соседей – достигнут тупик
                if first_object_type is not None and first_object_id is not None:
                    if current_type == first_object_type and str(current_attrs['obj_id']) == str(first_object_id):
                        self.logger.info(f"Достигнут first_object: {current_type}:{current_attrs['obj_id']}")
                        break
                    else:
                        raise ValueError(
                            f"Достигнут тупик на объекте {current_type}:{current_attrs['obj_id']}, "
                            f"не совпадающем с first_object {first_object_type}:{first_object_id}"
                        )
                else:
                    if current_type in (TYPE_OLT, TYPE_SWITCH):
                        self.logger.info(f"Достигнут корень: {current_type}:{current_attrs['obj_id']}")
                        break
                    else:
                        raise ValueError(
                            f"Достигнут тупик на объекте {current_type}:{current_attrs['obj_id']}, "
                            "не являющемся OLT или switch"
                        )

            if next_iface is None:
                # Если мы вышли из цикла через break, то next_iface будет None
                break

            next_type = next_iface.obj.obj_type
            if next_type == TYPE_CWDM:
                raise ValueError(
                    f"Обнаружен CWDM на пути построения. "
                    f"Линейный граф через CWDM не поддерживается."
                )

            # Если достигли OLT или switch – завершаем
            if next_type in (TYPE_OLT, TYPE_SWITCH):
                path.append(next_iface)
                self.logger.info(f"Достигнут корень: {next_type}:{next_iface.obj.id}")
                break

            if next_type in DEVICE_TYPES:
                raise ValueError(
                    f"Обнаружено устройство {next_type}:{next_iface.obj.id} на пути, "
                    "не являющееся OLT или switch. Остановка."
                )

            # Если достигли first_object – завершаем
            if first_object_type is not None and first_object_id is not None:
                if next_type == first_object_type and str(next_iface.obj.id) == str(first_object_id):
                    path.append(next_iface)
                    self.logger.info(f"Достигнут first_object: {next_type}:{next_iface.obj.id}")
                    break

            # Переходим к следующему
            prev = current
            current = next_iface
            path.append(current)
            self.logger.debug(f"Переход к {current}")

        # Строим линейный граф из path
        path_indices = [selected_cgraph._vertex_index[iface] for iface in path]
        return self._build_linear_graph_from_path(selected_cgraph, path_indices, last_iface)

    def _trace_from_terminal_with_multiple_comms(self,
                                                 obj_key: ObjKey,
                                                 first_object_type: Optional[str],
                                                 first_object_id: Optional[Union[int, str]]) -> CGraph:
        """
        Для терминального объекта с несколькими коммутациями пытается найти путь до first_object.
        """
        if first_object_type is None or first_object_id is None:
            raise ValueError("Для объекта с несколькими коммутациями необходимо указать first_object")

        comms = self._get_commutations(obj_key.obj_type, obj_key.id)
        for rec in comms:
            if getattr(rec, 'clps_last', None) == 'finish':
                continue
            p = int(rec.clps_first) if rec.clps_first is not None else 1
            test_iface = Interface(obj_key, side=1, port=p)
            for cg in self.cgraphs:
                if test_iface in cg._vertex_index:
                    start_idx = cg._vertex_index[test_iface]
                    for v in cg.vs:
                        if v['obj_type'] == first_object_type and str(v['obj_id']) == str(first_object_id):
                            target_idx = v.index
                            try:
                                paths = cg.get_shortest_paths(start_idx, target_idx, mode='all')
                                if paths and paths[0]:
                                    path = paths[0]
                                    return self._build_linear_graph_from_path(cg, path, test_iface)
                            except:
                                continue
        raise ValueError(
            f"Не удалось найти путь от {obj_key.obj_type}:{obj_key.id} "
            f"до {first_object_type}:{first_object_id}"
        )

    def _build_linear_graph_from_path(self, cgraph: CGraph, path_vertices: List[int], start_iface: Interface) -> CGraph:
        """Строит линейный граф из списка индексов вершин."""
        linear_cgraph = CGraph(self.client, cache=self._cache)
        vertex_indices = {}

        for idx in path_vertices:
            v_attrs = cgraph.vs[idx]
            attrs = {key: v_attrs[key] for key in v_attrs.attributes()}
            new_idx = linear_cgraph.add_vertex(**attrs).index
            vertex_indices[idx] = new_idx

        for i in range(len(path_vertices) - 1):
            idx1 = path_vertices[i]
            idx2 = path_vertices[i+1]
            eid = cgraph.get_eid(idx1, idx2, error=False)
            if eid == -1:
                eid = cgraph.get_eid(idx2, idx1, error=False)
            if eid != -1:
                e_attrs = cgraph.es[eid]
                attrs = {key: e_attrs[key] for key in e_attrs.attributes()}
                new_i = vertex_indices[idx1]
                new_j = vertex_indices[idx2]
                linear_cgraph.add_edge(new_i, new_j, **attrs)

        linear_cgraph._update_directed_flag()
        return linear_cgraph

    # ------------------------------------------------------------------------
    # Вспомогательные методы для поиска объектов в узле
    # ------------------------------------------------------------------------

    def _find_cgraph_for_object(self, obj_key: ObjKey) -> Optional[CGraph]:
        """Возвращает первый CGraph, содержащий вершину с данным obj_key."""
        for cg in self.cgraphs:
            for v in cg.vs:
                if v['obj_type'] == obj_key.obj_type and str(v['obj_id']) == str(obj_key.id):
                    return cg
        return None

    def _get_objects_for_node(self, node_id: int) -> List[Tuple[str, Union[int, str], Optional[Any]]]:
        """
        Возвращает список объектов в узле, используя кэш DataCache.
        Каждый элемент: (obj_type, obj_id, port_info)
        """
        objects = []

        # Устройства – загружаем все через DataCache
        try:
            all_devices = self._cache.get_all_devices(self.client)
            for dev_id, dev in all_devices.items():
                if getattr(dev, 'node_id', None) == node_id:
                    obj_type = getattr(dev, 'object_type', None)
                    if obj_type and dev_id:
                        objects.append((obj_type, dev_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска устройств в узле {node_id}: {e}")

        # Сплиттеры
        try:
            all_splitters = self._cache.get_all_splitters(self.client)
            for splitter_id, sp in all_splitters.items():
                if getattr(sp, 'node_id', None) == node_id:
                    objects.append((TYPE_SPLITTER, splitter_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска сплиттеров в узле {node_id}: {e}")

        # CWDM
        try:
            all_cwdms = self._cache.get_all_cwdms(self.client)
            for cwdm_id, cw in all_cwdms.items():
                if getattr(cw, 'node_id', None) == node_id:
                    objects.append((TYPE_CWDM, cwdm_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска CWDM в узле {node_id}: {e}")

        # Кроссы
        try:
            all_crosses = self._cache.get_all_crosses(self.client)
            for cross_uuid, cr in all_crosses.items():
                if getattr(cr, 'node_id', None) == node_id:
                    objects.append((TYPE_CROSS, cross_uuid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кроссов в узле {node_id}: {e}")

        # Кабели (волокна)
        try:
            all_fibers = self._cache.get_all_fibers(self.client)
            for fiber_id, fib in all_fibers.items():
                if getattr(fib, 'node1_id', None) == node_id or getattr(fib, 'node2_id', None) == node_id:
                    objects.append((TYPE_FIBER, fiber_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кабелей в узле {node_id}: {e}")

        return objects

    # ------------------------------------------------------------------------
    # Методы получения списков объектов из графов
    # ------------------------------------------------------------------------

    def _collect_from_cgraphs(self, attr_name: str, obj_type: Optional[str] = None) -> Set:
        result = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if obj_type is not None and v['obj_type'] != obj_type:
                    continue
                result.add(v[attr_name])
        return result

    def _collect_from_fngraph(self, attr_name: str) -> Set:
        if self.fngraph is None:
            return set()
        return {v[attr_name] for v in self.fngraph.vs}

    def get_customers(self) -> List[int]:
        ids = self._collect_from_cgraphs('obj_id', TYPE_CUSTOMER)
        return [int(i) for i in ids if i is not None]

    def get_nodes(self) -> List[int]:
        ids = self._collect_from_fngraph('node_id')
        return [int(i) for i in ids if i is not None]

    def get_cables(self) -> List[int]:
        if self.fngraph is None:
            return []
        cable_ids = set()
        for e in self.fngraph.es:
            fiber_id = e['fiber_id']
            if fiber_id is not None:
                cable_ids.add(int(fiber_id))
        return list(cable_ids)

    def get_fibers(self) -> List[int]:
        ids = self._collect_from_cgraphs('obj_id', TYPE_FIBER)
        return [int(i) for i in ids if i is not None]

    def get_devices(self) -> List[int]:
        ids = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if v['obj_type'] in DEVICE_TYPES:
                    ids.add(int(v['obj_id']))
        return list(ids)

    def get_splitters(self) -> List[int]:
        ids = self._collect_from_cgraphs('obj_id', TYPE_SPLITTER)
        return [int(i) for i in ids if i is not None]

    def get_cwdms(self) -> List[int]:
        ids = self._collect_from_cgraphs('obj_id', TYPE_CWDM)
        return [int(i) for i in ids if i is not None]

    def get_crosses(self) -> List[str]:
        ids = self._collect_from_cgraphs('obj_id', TYPE_CROSS)
        return [str(i) for i in ids if i is not None]

    # ------------------------------------------------------------------------
    # Методы получения объектов по ID (используют DataCache)
    # ------------------------------------------------------------------------

    def customer(self, customer_id: int) -> Optional[Customer.Get_data]:
        return self._load_object(TYPE_CUSTOMER, customer_id)

    def node(self, node_id: int) -> Optional[Node.Get]:
        return self._load_object('node', node_id)

    def cable(self, cable_id: int) -> Optional[Fiber.Get_list]:
        return self._load_object(TYPE_FIBER, cable_id)

    def fiber(self, fiber_id: int) -> Optional[Fiber.Get_fiber]:
        return self._load_object(TYPE_FIBER, fiber_id)

    def device(self, device_id: int) -> Optional[Device.Get_data]:
        for dev_type in DEVICE_TYPES:
            obj = self._load_object(dev_type, device_id)
            if obj is not None:
                return obj
        return None

    def splitter(self, splitter_id: int) -> Optional[Splitter.Get]:
        return self._load_object(TYPE_SPLITTER, splitter_id)

    def cwdm(self, cwdm_id: int) -> Optional[Cwdm.Get]:
        return self._load_object(TYPE_CWDM, cwdm_id)

    def cross(self, cross_uuid: str) -> Optional[Cross.Get_list]:
        return self._load_object(TYPE_CROSS, cross_uuid)

    def save_to_file(self, filepath: str) -> None:
        """Сохраняет сериализованное состояние топологии в файл."""
        import pickle
        data = {
            'client': {'url':self.client._url, 'apikey': self.client._apikey},
            'cgraphs': [cg.to_dict() for cg in self.cgraphs],
            'fngraph': self.fngraph.to_dict() if self.fngraph else None,
            'cache': self._cache.to_dict(),
            'version': Topology._data_version,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        self.logger.info(f"Топология сохранена в {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> 'Topology':
        """Загружает топологию из файла."""
        import pickle
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        if data['version'] != Topology._data_version:
            raise ValueError(f"Неподдерживаемая версия данных {data['version']}, текущая версия {Topology._data_version}")

        # Восстанавливаем кэш
        cache = DataCache.from_dict(data.get('cache', {}))

        client = WorkerNetClient('',data['client']['apikey'])
        client._url = data['client']['url']

        # Создаём экземпляр Topology
        topology = cls(client)
        topology._cache = cache
        topology.logger = _get_logger()

        # Восстанавливаем CGraph
        cgraphs_data = data.get('cgraphs', [])
        for cg_data in cgraphs_data:
            cg = CGraph.from_dict(cg_data, client, cache)
            topology.cgraphs.append(cg)

        # Восстанавливаем FNGraph
        fngraph_data = data.get('fngraph')
        if fngraph_data:
            topology.fngraph = FNGraph.from_dict(fngraph_data, client, cache)

        # Обновляем глобальный кэш (чтобы другие экземпляры использовали восстановленный)
        DataCache._objects = cache._objects
        DataCache._commutations = cache._commutations
        DataCache._all_objects = cache._all_objects

        topology.logger.info(f"Топология загружена из {filepath}")
        return topology

    # ------------------------------------------------------------------------
    # Представление
    # ------------------------------------------------------------------------

    def __repr__(self) -> str:
        cgraph_info = f"CGraphs: {len(self.cgraphs)}"
        fngraph_info = f"FNGraph: {'None' if self.fngraph is None else f'{self.fngraph.vcount()} nodes, {self.fngraph.ecount()} fibers'}"
        return f"Topology({cgraph_info}, {fngraph_info})"