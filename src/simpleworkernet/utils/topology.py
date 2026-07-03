# simpleworkernet/utils/topology.py
"""
Модуль Topology — высокоуровневый API для построения и работы с графами.
Использует общий глобальный кэш DataCache из модуля graph.py.
CGraph (граф коммутаций) хранится в виде списка связных графов.
FNGraph (граф сооружений) — один связный граф.

Поддерживаются фильтры:
- included_fibers (Set[int]): ID кабелей, через которые разрешён проход
- excluded_fibers (Set[int]): ID кабелей, на которых обход останавливается
- excluded_nodes (Set[int]): ID узлов, на которых обход останавливается
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
    _data_cache  # глобальный синглтон-кэш
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

    def __init__(self, client: WorkerNetClient):
        self.client = client
        self.logger = _get_logger()
        self._cache = _data_cache
        self.cgraphs: List[CGraph] = []
        self.fngraph: Optional[FNGraph] = None
        self._objects_cache: Dict[str, Dict[Union[int, str], Any]] = {
            'customer': {}, 'node': {}, 'fiber': {}, 'device': {},
            'splitter': {}, 'cwdm': {}, 'cross': {},
        }

    # ------------------------------------------------------------------------
    # Внутренние методы для загрузки объектов (используют DataCache)
    # ------------------------------------------------------------------------

    def _load_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        cache_key = (obj_type, obj_id)
        if cache_key in self._objects_cache.get(obj_type, {}):
            return self._objects_cache[obj_type][obj_id]

        def loader() -> Optional[Any]:
            try:
                if obj_type == TYPE_CUSTOMER:
                    result = self.client.Customer.get_data(customer_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == 'node':
                    result = self.client.Node.get(id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_FIBER:
                    result = self.client.Fiber.get_list(object_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type in DEVICE_TYPES:
                    result = self.client.Device.get_data(object_type=obj_type, object_id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_SPLITTER:
                    result = self.client.Splitter.get(id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_CWDM:
                    result = self.client.Cwdm.get(id=int(obj_id))
                    return result[0] if result and len(result) > 0 else None
                elif obj_type == TYPE_CROSS:
                    result = self.client.Cross.get_list(id=str(obj_id))
                    return result[0] if result and len(result) > 0 else None
                else:
                    return None
            except Exception as e:
                self.logger.warning(f"Не удалось загрузить {obj_type}:{obj_id}: {e}")
                return None

        obj = self._cache.get_or_load_object(obj_type, obj_id, loader)
        if obj is not None:
            if obj_type not in self._objects_cache:
                self._objects_cache[obj_type] = {}
            self._objects_cache[obj_type][obj_id] = obj
        return obj

    def _get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> List[Commutation.Get_data]:
        def loader() -> List[Commutation.Get_data]:
            if obj_type in DEVICE_TYPES:
                api_type = TYPE_SWITCH
            else:
                api_type = obj_type
            api_id = str(obj_id) if obj_type == TYPE_CROSS else int(obj_id)
            try:
                result = self.client.Commutation.get_data(object_type=api_type, object_id=api_id)
                return result.to_list() if result else []
            except Exception as e:
                self.logger.error(f"Ошибка загрузки коммутаций для {obj_type}:{obj_id}: {e}")
                return []

        return self._cache.get_or_load_commutations(obj_type, obj_id, loader)

    # ------------------------------------------------------------------------
    # Внутренние методы для работы со списками графов
    # ------------------------------------------------------------------------

    def _normalize_set(self, value: Optional[Union[int, List[int], Set[int]]]) -> Optional[Set[int]]:
        if value is None:
            return None
        if isinstance(value, (int, str)):
            return {int(value)}
        return set(value)

    def _add_cgraph(self, cgraph: CGraph) -> None:
        if cgraph is None or cgraph.vcount() == 0:
            return
        if not cgraph.is_connected():
            self.logger.warning("Граф не связный, не добавляем")
            return
        self.cgraphs.append(cgraph)

    def _set_fngraph(self, fngraph: FNGraph) -> None:
        if fngraph is None or fngraph.vcount() == 0:
            return
        if not fngraph.is_connected():
            self.logger.warning("FNGraph не связный, не устанавливаем")
            return
        self.fngraph = fngraph

    def _build_fngraph_from_cgraph(self, cgraph: CGraph) -> Optional[FNGraph]:
        if cgraph is None or cgraph.vcount() == 0:
            return None
        fngraph = FNGraph(self.client, commutation_graph=cgraph, cache=self._cache)
        fngraph.build(0)
        return fngraph if fngraph.vcount() > 0 else None

    def _merge_cgraphs(self, graphs: List[CGraph]) -> Optional[CGraph]:
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
        cgraph = CGraph(self.client, cache=self._cache)

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
    # Основные методы построения (кратко)
    # ------------------------------------------------------------------------

    def _reset(self) -> None:
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
            comms = self._get_commutations(TYPE_CROSS, object_id)
            if not comms:
                self.logger.warning(f"У кросса {object_id} нет коммутаций")
                return self
            ports = set()
            for rec in comms:
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

        fngraph = FNGraph(self.client, cache=self._cache)
        fngraph.build(object_id,
                      included_fibers=included_fibers_set,
                      excluded_fibers=excluded_fibers_set,
                      excluded_nodes=excluded_nodes_set)
        if fngraph.vcount() == 0:
            self.logger.warning(f"Не удалось построить FNGraph от узла {object_id}")
            return self
        self._set_fngraph(fngraph)

        node_ids = [v['node_id'] for v in fngraph.vs]
        for node_id in node_ids:
            if excluded_nodes_set is not None and node_id in excluded_nodes_set:
                continue
            self.logger.debug(f"Поиск объектов в узле {node_id}")
            objects_in_node = self._get_objects_for_node(node_id)
            if not objects_in_node:
                continue
            for obj_type, obj_id, port_info in objects_in_node:
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
    # Метод trace_from_commutation (исправлен)
    # ------------------------------------------------------------------------
    def trace_from_commutation(self,
                               last_object_type: Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer'],
                               last_object_id: Union[int, str],
                               port: Optional[int] = None,
                               side: Optional[int] = None,
                               first_object_type: Optional[Literal['switch', 'cross', 'splitter', 'cwdm', 'fiber', 'customer']] = None,
                               first_object_id: Optional[Union[int, str]] = None) -> CGraph:
        """
        Строит линейный граф (цепочку) от указанного последнего объекта в направлении к начальному объекту.

        Args:
            last_object_type: тип последнего объекта в трассе
            last_object_id: идентификатор последнего объекта
            port: номер порта (для объектов со сторонами обязателен, если неоднозначно)
            side: сторона (1 или 2) для объектов со сторонами
            first_object_type: тип первого объекта (если не указан, то до корневого)
            first_object_id: идентификатор первого объекта

        Returns:
            CGraph: линейный граф (цепочка вершин и рёбер)

        Raises:
            ValueError: если невозможно построить однозначный линейный граф
        """
        self.logger.info(f"=== TRACE FROM COMMUTATION: last={last_object_type}:{last_object_id} (port={port}, side={side}) ===")

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

        # --- Поиск целевых вершин (корней) ---
        start_idx = selected_cgraph._vertex_index[last_iface]
        target_indices = []

        if first_object_type is not None and first_object_id is not None:
            for v in selected_cgraph.vs:
                if v['obj_type'] == first_object_type and str(v['obj_id']) == str(first_object_id):
                    target_indices.append(v.index)
        else:
            # 1. Ищем OLT
            for v in selected_cgraph.vs:
                if v['obj_type'] == TYPE_OLT:
                    target_indices.append(v.index)
            # 2. Если OLT нет, ищем switch (не OLT)
            if not target_indices:
                for v in selected_cgraph.vs:
                    if v['obj_type'] == TYPE_SWITCH:
                        target_indices.append(v.index)
            # 3. Если switch нет, ищем любые устройства (ONU) - но ONU обычно не корень, поэтому лучше исключить
            # Вместо этого выбрасываем исключение, если нет OLT или switch
            if not target_indices:
                raise ValueError(
                    "В графе нет OLT или switch. Невозможно автоматически определить корневую вершину. "
                    "Укажите first_object явно."
                )

        if not target_indices:
            raise ValueError(
                "Не удалось определить целевую вершину (корень). "
                "Попробуйте указать first_object явно."
            )

        # Если несколько кандидатов (например, несколько switch), выбираем тот, который дальше от start
        if len(target_indices) > 1:
            distances = []
            for idx in target_indices:
                try:
                    path_len = len(selected_cgraph.get_shortest_paths(start_idx, idx, mode='all')[0])
                    distances.append((idx, path_len))
                except:
                    distances.append((idx, -1))
            distances.sort(key=lambda x: x[1], reverse=True)
            target_indices = [distances[0][0]]
            self.logger.info(f"Выбрана корневая вершина: {selected_cgraph.vs[target_indices[0]]['obj_type']}:{selected_cgraph.vs[target_indices[0]]['obj_id']} (расстояние {distances[0][1]})")
        elif len(target_indices) == 1:
            self.logger.info(f"Найдена корневая вершина: {selected_cgraph.vs[target_indices[0]]['obj_type']}:{selected_cgraph.vs[target_indices[0]]['obj_id']}")

        # --- Поиск кратчайшего пути до целевой вершины ---
        path = None
        for target_idx in target_indices:
            try:
                paths = selected_cgraph.get_shortest_paths(start_idx, target_idx, mode='all')
                if paths and paths[0]:
                    path = paths[0]
                    break
            except:
                continue

        if not path:
            raise ValueError(f"Не удалось найти путь от {last_object_type}:{last_object_id} до целевой вершины")

        return self._build_linear_graph_from_path(selected_cgraph, path, last_iface)

    def _trace_from_terminal_with_multiple_comms(self,
                                                 obj_key: ObjKey,
                                                 first_object_type: Optional[str],
                                                 first_object_id: Optional[Union[int, str]]) -> CGraph:
        if first_object_type is None or first_object_id is None:
            raise ValueError("Для объекта с несколькими коммутациями необходимо указать first_object")

        comms = self._get_commutations(obj_key.obj_type, obj_key.id)
        for rec in comms:
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
        linear_cgraph = CGraph(self.client, cache=self._cache)
        vertex_indices = {}

        for idx in path_vertices:
            v_attrs = cgraph.vs[idx]
            new_idx = linear_cgraph.add_vertex(**{key: v_attrs[key] for key in v_attrs.attributes()}).index
            vertex_indices[idx] = new_idx

        for i in range(len(path_vertices) - 1):
            idx1 = path_vertices[i]
            idx2 = path_vertices[i+1]
            eid = cgraph.get_eid(idx1, idx2, error=False)
            if eid == -1:
                eid = cgraph.get_eid(idx2, idx1, error=False)
            if eid != -1:
                e_attrs = cgraph.es[eid]
                new_i = vertex_indices[idx1]
                new_j = vertex_indices[idx2]
                linear_cgraph.add_edge(new_i, new_j, **{key: e_attrs[key] for key in e_attrs.attributes()})

        linear_cgraph._update_directed_flag()
        return linear_cgraph

    # ------------------------------------------------------------------------
    # Вспомогательные методы для поиска объектов в узле
    # ------------------------------------------------------------------------

    def _get_objects_for_node(self, node_id: int) -> List[Tuple[str, Union[int, str], Optional[Any]]]:
        objects = []
        try:
            devices = self.client.Device.get_list(node_id=node_id)
            for dev in devices.to_list() if devices else []:
                obj_type = getattr(dev, 'object_type', None)
                obj_id = getattr(dev, 'id', None)
                if obj_type and obj_id:
                    objects.append((obj_type, obj_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска устройств в узле {node_id}: {e}")

        try:
            splitters = self.client.Splitter.get_list(node_id=node_id)
            for sp in splitters.to_list() if splitters else []:
                obj_id = getattr(sp, 'id', None)
                if obj_id:
                    objects.append((TYPE_SPLITTER, obj_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска сплиттеров в узле {node_id}: {e}")

        try:
            cwdms = self.client.Cwdm.get_list(node_id=node_id)
            for cw in cwdms.to_list() if cwdms else []:
                obj_id = getattr(cw, 'id', None)
                if obj_id:
                    objects.append((TYPE_CWDM, obj_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска CWDM в узле {node_id}: {e}")

        try:
            crosses = self.client.Cross.get_list(node_id=node_id)
            for cr in crosses.to_list() if crosses else []:
                obj_uuid = getattr(cr, 'uuid', None)
                if obj_uuid:
                    objects.append((TYPE_CROSS, obj_uuid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кроссов в узле {node_id}: {e}")

        try:
            fibers = self.client.Fiber.get_list(node_id=node_id)
            for fib in fibers.to_list() if fibers else []:
                fiber_id = getattr(fib, 'code', None)
                if fiber_id:
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
    # Методы получения объектов по ID
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

    # ------------------------------------------------------------------------
    # Представление
    # ------------------------------------------------------------------------

    def __repr__(self) -> str:
        cgraph_info = f"CGraphs: {len(self.cgraphs)}"
        fngraph_info = f"FNGraph: {'None' if self.fngraph is None else f'{self.fngraph.vcount()} nodes, {self.fngraph.ecount()} fibers'}"
        return f"Topology({cgraph_info}, {fngraph_info})"