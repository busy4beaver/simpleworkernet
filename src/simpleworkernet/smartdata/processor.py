# simpleworkernet/smartdata/processor.py
"""
Процессор данных для SmartData - обработка данных от API до готовых объектов.
"""

from typing import Any, Set, List, Dict, Tuple, Optional, Callable, Type, Union, get_origin, get_args
from pathlib import Path
from dataclasses import dataclass, field

from ..core.logger import log
from ..core.cache import cache
from ..core.exceptions import WorkerNetRecursionError
from .metadata import MetaData, META_KEY, PathSegment, SegmentType
from . import helpers
from ..utils.decorators import timer


@dataclass
class ProcessingResult:
    """
    Результат обработки данных.
    
    Attributes:
        items: Список готовых объектов
        stats: Статистика обработки
    """
    items: List[Any]
    stats: Dict[str, int] = field(default_factory=dict)


class DataProcessor:
    """
    Процессор для обработки данных от API.
    
    Трехфазная обработка:
    - Фаза 1: Базовые структурные преобразования
    - Фаза 1.5: Правила с учетом модели
    - Фаза 2: Кастинг в модели
    """
    
    _cache = cache
    
    def __init__(self, max_depth: int = 100):
        self.max_depth = max_depth
        self._target_type = None
        self._cache_func = None
        self._stats = {
            'processed_items': 0,
            'copies_made': 0,
            'recursions': 0,
            'collapsed_levels': 0,
            'nested_lists_unpacked': 0,
            'models_created': 0
        }
    
    # ------------------------------------------------------------------------
    # Основной метод обработки
    # ------------------------------------------------------------------------
    @timer()
    def process(self, data: Any, target_type: Optional[Type] = None,
                cache_func: Optional[Callable] = None) -> ProcessingResult:
        """
        Основной метод обработки данных.
        """
        self.reset_stats()
        self._target_type = target_type
        self._cache_func = cache_func
        
        data = self._prepare_input(data)
        metadata_registry: Dict[int, MetaData] = {}
        
        # Фаза 1: Базовые структурные преобразования
        base_structured = self._basic_structural_transform(
            data=data, path=[], depth=0, metadata_registry=metadata_registry
        )
        
        # Фаза 1.5: Применение правил с учетом модели
        if target_type and target_type is not Any:
            model_aware_items = self._apply_model_aware_rules(
                items=base_structured,
                target_type=target_type,
                metadata_registry=metadata_registry
            )
        else:
            model_aware_items = base_structured
        
        flat_items = helpers.flatten_list(model_aware_items, self.max_depth)
        
        # Фаза 2: Кастинг в модели
        if target_type and target_type is not Any:
            final_items = self._cast_to_models(flat_items, target_type, metadata_registry)
        else:
            final_items = flat_items
        
        log.debug(f"Обработка завершена: {len(final_items)} объектов")
        return ProcessingResult(items=final_items, stats=self._stats.copy())
    
    # ------------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------------

    def _prepare_input(self, data: Any) -> Any:
        """Подготавливает входные данные."""
        if isinstance(data, tuple):
            return list(data)
        if hasattr(data, 'to_list') and callable(getattr(data, 'to_list')):
            return data.to_list()
        return data
    
    def _get_type_name(self, tp: Any) -> str:
        """Возвращает имя типа для логирования."""
        if tp is None:
            return "None"
        if tp is Any:
            return "Any"
        if hasattr(tp, '__name__'):
            return tp.__name__
        return str(tp)
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику обработки."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Сбрасывает статистику."""
        self._stats = {k: 0 for k in self._stats}
    
    # ------------------------------------------------------------------------
    # Методы для работы с кэшем
    # ------------------------------------------------------------------------
    
    @classmethod
    def get_cache_path(cls) -> Path:
        return cls._cache.get_cache_path()
    
    @classmethod
    def save_cache(cls, force: bool = False) -> bool:
        return cls._cache.save(force)
    
    @classmethod
    def load_cache(cls, preload_only: bool = False) -> bool:
        return cls._cache.load(preload_only)
    
    @classmethod
    def ensure_cache_saved(cls) -> bool:
        return cls._cache.ensure_saved()
    
    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()
    
    @classmethod
    def preload_from_models(cls, *model_classes, recursive: bool = True, **kwargs) -> None:
        cls._cache.preload_from_models(*model_classes, recursive=recursive, **kwargs)
    
    @classmethod
    def set_cache_max_size(cls, size: int) -> None:
        cls._cache.set_max_size(size)
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        return cls._cache.get_stats()
    
    # ------------------------------------------------------------------------
    # Фаза 1: Базовые структурные преобразования
    # ------------------------------------------------------------------------
    
    def _basic_structural_transform(self, data: Any, path: List[Tuple[SegmentType, str]],
                                    depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Базовое структурное преобразование данных."""
        if depth > self.max_depth:
            raise WorkerNetRecursionError(f"Превышена глубина {self.max_depth}")
        
        self._stats['recursions'] += 1
        self._stats['processed_items'] += 1
        
        if isinstance(data, list):
            return self._basic_transform_list(data, path, depth, metadata_registry)
        elif isinstance(data, dict):
            return self._basic_transform_dict(data, path, depth, metadata_registry)
        else:
            if path:
                metadata_registry[id(data)] = helpers.build_metadata(path)
            return [data]
    
    def _basic_transform_list(self, lst: List, path: List[Tuple[SegmentType, str]],
                              depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Базовая обработка списка."""
        lst = self._unpack_nested_lists(lst)
        
        all_primitives = all(
            helpers.is_primitive(item) or 
            (isinstance(item, list) and all(helpers.is_primitive(sub) for sub in item))
            for item in lst
        )
        
        if all_primitives:
            return self._process_primitive_list(lst, path, metadata_registry)
        
        return self._process_complex_list(lst, path, depth, metadata_registry)
    
    def _unpack_nested_lists(self, lst: List) -> List:
        """Распаковывает внешние матрешки."""
        if len(lst) == 1 and isinstance(lst[0], list):
            self._stats['nested_lists_unpacked'] += 1
            return lst[0]
        return lst
    
    def _process_primitive_list(self, lst: List, path: List[Tuple[SegmentType, str]],
                                 metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Обрабатывает список примитивов, сохраняя структуру."""
        result = []
        for idx, item in enumerate(lst):
            new_path = path + [(SegmentType.IDX, str(idx))]
            if isinstance(item, list):
                inner_result = []
                for inner_idx, inner_item in enumerate(item):
                    inner_path = new_path + [(SegmentType.IDX, str(inner_idx))]
                    if helpers.is_primitive(inner_item):
                        metadata_registry[id(inner_item)] = helpers.build_metadata(inner_path)
                        inner_result.append(inner_item)
                    else:
                        inner_result.append(inner_item)
                result.append(inner_result)
            else:
                metadata_registry[id(item)] = helpers.build_metadata(new_path)
                result.append(item)
        return result
    
    def _process_complex_list(self, lst: List, path: List[Tuple[SegmentType, str]],
                               depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Обрабатывает список со сложными элементами рекурсивно."""
        result = []
        for idx, item in enumerate(lst):
            new_path = path + [(SegmentType.IDX, str(idx))]
            if isinstance(item, list):
                processed = self._basic_transform_list(item, new_path, depth + 1, metadata_registry)
                result.extend(processed)
            else:
                processed = self._basic_structural_transform(item, new_path, depth + 1, metadata_registry)
                result.extend(processed if isinstance(processed, list) else [processed])
        return result
    
    def _basic_transform_dict(self, dct: Dict, path: List[Tuple[SegmentType, str]],
                              depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Базовая обработка словаря."""
        # Анализ словаря
        analysis = self._analyze_dict(dct)
        non_meta_keys = [k for k in dct.keys() if k != META_KEY]
        
        # Применение правил по порядку
        if self._apply_d1_rule(dct, analysis):
            self._stats['collapsed_levels'] += 1
            return list(dct.values())
        
        if self._apply_d2_1_rule(dct, analysis):
            self._stats['collapsed_levels'] += 1
            return self._process_d2_1_dict(dct, path, depth, metadata_registry)
        
        if self._apply_d2_2_rule(dct, analysis):
            self._stats['collapsed_levels'] += 1
            return self._process_d2_2_dict(dct, path, depth, metadata_registry)
        
        # Базовое D5: Один невалидный ключ
        if len(non_meta_keys) == 1:
            main_key = non_meta_keys[0]
            key_type = helpers.get_key_type(main_key, self._cache_func)
            
            if key_type != SegmentType.FLD:
                self._stats['collapsed_levels'] += 1
                return self._apply_basic_d5(dct, main_key, key_type, path, depth, metadata_registry)
        
        # Правило D3: Словарь с валидными ключами
        if analysis['all_keys_valid']:
            return self._apply_d3_rule(dct, path, depth, metadata_registry)
        
        # Смешанный случай
        return self._process_mixed_dict(dct, path, depth, metadata_registry)
    
    def _analyze_dict(self, dct: Dict) -> Dict[str, Any]:
        """Анализирует словарь и возвращает характеристики."""
        return {
            'all_numeric': helpers.all_keys_numeric(dct),
            'all_keys_valid': helpers.all_keys_valid(dct, self._cache_func),
            'all_values_are_dicts': helpers.all_values_are_dicts(dct),
            'all_values_are_list_of_dicts': helpers.all_values_are_lists_of_dicts(dct),
            'all_values_are_primitives': helpers.all_values_are_primitives(dct),
            'keys_equal_values': helpers.keys_equal_values(dct)
        }
    
    def _apply_d1_rule(self, dct: Dict, analysis: Dict[str, Any]) -> bool:
        """Проверяет применимость правила D1."""
        return (analysis['all_numeric'] and 
                analysis['all_values_are_primitives'] and 
                analysis['keys_equal_values'])
    
    def _apply_d2_1_rule(self, dct: Dict, analysis: Dict[str, Any]) -> bool:
        """Проверяет применимость правила D2.1."""
        return (not analysis['all_keys_valid'] and 
                analysis['all_values_are_dicts'])
    
    def _apply_d2_2_rule(self, dct: Dict, analysis: Dict[str, Any]) -> bool:
        """Проверяет применимость правила D2.2."""
        return (not analysis['all_keys_valid'] and 
                analysis['all_values_are_list_of_dicts'])
    
    def _process_d2_1_dict(self, dct: Dict, path: List[Tuple[SegmentType, str]],
                           depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Обрабатывает словарь по правилу D2.1."""
        result = []
        for key, value in dct.items():
            if key == META_KEY:
                continue
            key_type = helpers.get_key_type(str(key), self._cache_func)
            new_path = path + [(key_type, str(key))]
            processed = self._basic_transform_dict(value, new_path, depth + 1, metadata_registry)
            
            for item in processed:
                if isinstance(item, dict) and META_KEY not in item:
                    item[META_KEY] = helpers.build_metadata(new_path)
                    self._stats['copies_made'] += 1
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(item)
        return result
    
    def _process_d2_2_dict(self, dct: Dict, path: List[Tuple[SegmentType, str]],
                           depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Обрабатывает словарь по правилу D2.2."""
        result = []
        for key, value in dct.items():
            if key == META_KEY:
                continue
            key_type = helpers.get_key_type(str(key), self._cache_func)
            key_path = path + [(key_type, str(key))]
            
            for idx, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                item_path = key_path + [(SegmentType.IDX, str(idx))]
                processed = self._basic_transform_dict(item, item_path, depth + 1, metadata_registry)
                
                for p_item in processed:
                    if isinstance(p_item, dict) and META_KEY not in p_item:
                        p_item[META_KEY] = helpers.build_metadata(item_path)
                        self._stats['copies_made'] += 1
                        result.append(p_item)
                    elif isinstance(p_item, dict):
                        result.append(p_item)
        return result
    
    def _apply_basic_d5(self, dct: Dict, main_key: str, key_type: SegmentType,
                        path: List[Tuple[SegmentType, str]], depth: int,
                        metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Применяет базовое правило D5 для невалидных ключей."""
        new_path = path + [(key_type, main_key)]
        processed = self._basic_structural_transform(
            dct[main_key], new_path, depth + 1, metadata_registry
        )
        
        result = []
        for item in processed:
            if isinstance(item, dict):
                if META_KEY not in item:
                    item[META_KEY] = helpers.build_metadata(new_path)
                    self._stats['copies_made'] += 1
                result.append(item)
            elif isinstance(item, list):
                result.append(item)
            else:
                wrapped = {"value": item, META_KEY: helpers.build_metadata(new_path)}
                result.append(wrapped)
        return result
    
    def _apply_d3_rule(self, dct: Dict, path: List[Tuple[SegmentType, str]],
                       depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Применяет правило D3 для словаря с валидными ключами."""
        result = dct.copy()
        if path:
            result[META_KEY] = helpers.build_metadata(path)
            self._stats['copies_made'] += 1
        
        for key, value in result.items():
            if key == META_KEY:
                continue
            key_type = helpers.get_key_type(str(key), self._cache_func)
            new_path = [(key_type, str(key))]
            
            if isinstance(value, dict):
                processed = self._basic_transform_dict(value, new_path, depth + 1, metadata_registry)
                if processed:
                    result[key] = processed[0] if len(processed) == 1 else processed
            elif isinstance(value, list):
                processed = self._basic_transform_list(value, new_path, depth + 1, metadata_registry)
                if processed:
                    result[key] = processed
        return [result]
    
    def _process_mixed_dict(self, dct: Dict, path: List[Tuple[SegmentType, str]],
                            depth: int, metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Обрабатывает смешанный случай рекурсивно."""
        result = []
        for key, value in dct.items():
            if key == META_KEY:
                continue
            key_type = helpers.get_key_type(str(key), self._cache_func)
            new_path = path + [(key_type, str(key))]
            processed = self._basic_structural_transform(value, new_path, depth + 1, metadata_registry)
            result.extend(processed if isinstance(processed, list) else [processed])
        return result

    # ------------------------------------------------------------------------
    # Фаза 1.5: Правила с учетом модели
    # ------------------------------------------------------------------------
    
    def _apply_model_aware_rules(self, items: List[Any], target_type: Optional[Type],
                                  metadata_registry: Dict[int, MetaData],
                                  field_name: str = None) -> List[Any]:
        """Применяет правила с учетом целевой модели."""
        if target_type is None or target_type is Any:
            return items
        
        result = []
        
        for item_idx, item in enumerate(items):
            if isinstance(item, dict):
                processed = self._process_dict_with_model(
                    item, target_type, metadata_registry, field_name, item_idx
                )
                result.extend(processed if isinstance(processed, list) else [processed])
            
            elif isinstance(item, list):
                processed = self._process_list_with_model(
                    item, target_type, metadata_registry, field_name
                )
                result.append(processed)
            
            else:
                result.append(item)
        
        return result
    
    def _get_actual_target(self, target_type: Any) -> Any:
        """Распаковывает List[Model] в Model."""
        
        origin = get_origin(target_type)
        if origin is list or origin is List:
            args = get_args(target_type)
            if args:
                return args[0]
        return target_type

    def _process_dict_with_model(self, dct: Dict, target_type: Any,
                                  metadata_registry: Dict[int, MetaData],
                                  field_name: str, item_idx: int) -> Any:
        """Обрабатывает словарь с учетом модели."""
        # Сохраняем метаданные
        meta = dct.pop(META_KEY, None) if META_KEY in dct else None
        current_path = meta.path if meta else []
        
        # Распаковываем тип
        actual_target = self._get_actual_target(target_type)
        
        # Пробуем схлопнуть
        collapsed = self._maybe_collapse_dict(
            dct=dct,
            target_type=actual_target,
            current_path=current_path,
            metadata_registry=metadata_registry,
            field_name=field_name
        )
        
        if collapsed is not None:
            return self._process_collapsed_result(collapsed, meta)
        
        # Если не схлопнулось, обрабатываем как обычный словарь
        return self._process_regular_dict_with_model(
            dct, actual_target, current_path, metadata_registry, meta
        )
    
    def _process_collapsed_result(self, collapsed: Any, meta: Optional[MetaData]) -> Any:
        """Обрабатывает результат схлопывания."""
        if isinstance(collapsed, list):
            result = []
            for collapsed_item in collapsed:
                if meta and isinstance(collapsed_item, dict) and META_KEY not in collapsed_item:
                    collapsed_item[META_KEY] = meta
                result.append(collapsed_item)
            return result
        else:
            if meta and isinstance(collapsed, dict) and META_KEY not in collapsed:
                collapsed[META_KEY] = meta
            return collapsed
    
    def _process_regular_dict_with_model(self, dct: Dict, target_type: Any,
                                          current_path: List[PathSegment],
                                          metadata_registry: Dict[int, MetaData],
                                          meta: Optional[MetaData]) -> Dict:
        """Обрабатывает обычный словарь с учетом модели."""
        # Получаем поля модели
        fields_with_types = helpers.get_model_fields_with_types(target_type)
        
        # Обрабатываем каждое значение словаря
        processed_dict = {}
        for key, value in dct.items():
            if key in fields_with_types:
                field_type = fields_with_types[key]
                
                if isinstance(value, dict):
                    processed_dict[key] = self._apply_model_aware_rules(
                        items=[value],
                        target_type=field_type,
                        metadata_registry=metadata_registry,
                        field_name=key
                    )[0]
                elif isinstance(value, list):
                    processed_list = []
                    for idx, subitem in enumerate(value):
                        if isinstance(subitem, dict):
                            sub_processed = self._apply_model_aware_rules(
                                items=[subitem],
                                target_type=field_type,
                                metadata_registry=metadata_registry,
                                field_name=f"{key}[{idx}]"
                            )[0]
                            processed_list.append(sub_processed)
                        else:
                            processed_list.append(subitem)
                    processed_dict[key] = processed_list
                else:
                    processed_dict[key] = value
            else:
                processed_dict[key] = value
        
        # Возвращаем метаданные
        if meta:
            processed_dict[META_KEY] = meta
        
        return processed_dict
    
    def _process_list_with_model(self, lst: List, target_type: Any,
                                  metadata_registry: Dict[int, MetaData],
                                  field_name: str) -> List:
        """Обрабатывает список с учетом модели."""
        # Распаковываем тип для элементов списка
        element_target = self._get_actual_target(target_type)
        
        processed_list = []
        for idx, subitem in enumerate(lst):
            if isinstance(subitem, dict):
                sub_processed = self._apply_model_aware_rules(
                    items=[subitem],
                    target_type=element_target,
                    metadata_registry=metadata_registry,
                    field_name=f"{field_name}[{idx}]" if field_name else f"[{idx}]"
                )[0]
                processed_list.append(sub_processed)
            else:
                processed_list.append(subitem)
        
        return processed_list
    
    def _maybe_collapse_dict(self, dct: Dict, target_type: Any,
                             current_path: List[PathSegment],
                             metadata_registry: Dict[int, MetaData],
                             field_name: str = None) -> Optional[Any]:
        """Проверяет, нужно ли схлопнуть словарь, и возвращает результат."""
        if not helpers.is_model_class(target_type):
            return None
        
        fields = helpers.get_model_fields(target_type)
        dict_keys = set(k for k in dct.keys() if k != META_KEY)
        
        if len(dict_keys) != 1:
            return None
        
        main_key = next(iter(dict_keys))
        main_value = dct[main_key]
        
        if main_key in fields:
            return None
        
        key_type = helpers.get_key_type(main_key, self._cache_func)
        
        if isinstance(main_value, dict):
            return self._collapse_dict_value(
                main_value, main_key, key_type, target_type,
                current_path, metadata_registry, fields
            )
        
        elif isinstance(main_value, list) and all(isinstance(item, dict) for item in main_value):
            return self._collapse_list_value(
                main_value, main_key, key_type, target_type,
                current_path, metadata_registry, fields
            )
        
        return None
    
    def _collapse_dict_value(self, main_value: Dict, main_key: str, key_type: SegmentType,
                              target_type: Any, current_path: List[PathSegment],
                              metadata_registry: Dict[int, MetaData],
                              fields: set) -> Optional[Dict]:
        """Схлопывает значение-словарь."""
        value_keys = set(main_value.keys())
        if value_keys & fields:
            new_path = current_path + [PathSegment(key_type, main_key)]
            meta = helpers.build_metadata([(seg.type, seg.key) for seg in new_path])
            
            result = self._apply_model_aware_to_dict(
                dct=main_value,
                target_type=target_type,
                current_path=new_path,
                metadata_registry=metadata_registry,
                field_name=main_key
            )
            
            if isinstance(result, dict) and META_KEY not in result:
                result[META_KEY] = meta
                self._stats['copies_made'] += 1
            
            return result
        return None
    
    def _collapse_list_value(self, main_value: List, main_key: str, key_type: SegmentType,
                              target_type: Any, current_path: List[PathSegment],
                              metadata_registry: Dict[int, MetaData],
                              fields: set) -> Optional[List]:
        """Схлопывает значение-список словарей."""
        has_common = any(set(item.keys()) & fields for item in main_value)
        
        if has_common:
            new_path = current_path + [PathSegment(key_type, main_key)]
            result = []
            
            for idx, item in enumerate(main_value):
                item_path = new_path + [PathSegment(SegmentType.IDX, str(idx))]
                item_meta = helpers.build_metadata([(seg.type, seg.key) for seg in item_path])
                
                processed = self._apply_model_aware_to_dict(
                    dct=item,
                    target_type=target_type,
                    current_path=item_path,
                    metadata_registry=metadata_registry,
                    field_name=f"{main_key}[{idx}]"
                )
                
                if isinstance(processed, dict) and META_KEY not in processed:
                    processed[META_KEY] = item_meta
                    self._stats['copies_made'] += 1
                
                result.append(processed)
            
            return result
        return None
    
    def _apply_model_aware_to_dict(self, dct: Dict, target_type: Any,
                                   current_path: List[PathSegment],
                                   metadata_registry: Dict[int, MetaData],
                                   field_name: str = None) -> Any:
        """Применяет правила с учетом модели к словарю (без схлопывания)."""
        
        if target_type is None or target_type is Any:
            return dct
        
        origin = get_origin(target_type)
        
        # Обработка списков
        if origin is list or origin is List:
            return self._process_list_target(dct, target_type, current_path, metadata_registry, field_name)
        
        # Обработка Union
        if origin is Union:
            return self._process_union_target(dct, target_type, current_path, metadata_registry, field_name)
        
        # Проверка, является ли тип моделью
        if not helpers.is_model_class(target_type):
            return dct
        
        # Обработка словаря как модели
        return self._process_dict_as_model(dct, target_type, current_path, metadata_registry)
    
    def _process_list_target(self, dct: Dict, target_type: Any,
                              current_path: List[PathSegment],
                              metadata_registry: Dict[int, MetaData],
                              field_name: str) -> Any:
        """Обрабатывает случай, когда целевой тип - список."""
        
        args = get_args(target_type)
        if not args:
            return dct
        
        element_type = args[0]
        
        if isinstance(dct, list):
            result = []
            for idx, item in enumerate(dct):
                if isinstance(item, dict):
                    processed = self._apply_model_aware_to_dict(
                        dct=item,
                        target_type=element_type,
                        current_path=current_path + [PathSegment(SegmentType.IDX, str(idx))],
                        metadata_registry=metadata_registry,
                        field_name=f"{field_name}[{idx}]" if field_name else f"[{idx}]"
                    )
                    result.append(processed)
                else:
                    result.append(item)
            return result
        elif isinstance(dct, dict):
            return self._apply_model_aware_to_dict(
                dct=dct,
                target_type=element_type,
                current_path=current_path,
                metadata_registry=metadata_registry,
                field_name=field_name
            )
        return dct
    
    def _process_union_target(self, dct: Dict, target_type: Any,
                               current_path: List[PathSegment],
                               metadata_registry: Dict[int, MetaData],
                               field_name: str) -> Any:
        """Обрабатывает случай, когда целевой тип - Union."""

        for arg in get_args(target_type):
            if arg is type(None):
                continue
            result = self._apply_model_aware_to_dict(
                dct=dct,
                target_type=arg,
                current_path=current_path,
                metadata_registry=metadata_registry,
                field_name=field_name
            )
            if result != dct:
                return result
        return dct
    
    def _process_dict_as_model(self, dct: Dict, target_type: Any,
                                current_path: List[PathSegment],
                                metadata_registry: Dict[int, MetaData]) -> Dict:
        """Обрабатывает словарь как модель."""
        fields_with_types = helpers.get_model_fields_with_types(target_type)
        field_names = set(fields_with_types.keys())
        dict_keys = set(k for k in dct.keys() if k != META_KEY)
        
        if not dict_keys.issubset(field_names):
            return dct
        
        result = {}
        for key, value in dct.items():
            if key == META_KEY:
                result[key] = value
                continue
            
            field_type = fields_with_types.get(key, Any)
            new_path = current_path + [PathSegment(SegmentType.FLD, key)]
            
            if isinstance(value, dict):
                result[key] = self._apply_model_aware_to_dict(
                    dct=value,
                    target_type=field_type,
                    current_path=new_path,
                    metadata_registry=metadata_registry,
                    field_name=key
                )
            elif isinstance(value, list):
                processed_list = []
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        item_path = new_path + [PathSegment(SegmentType.IDX, str(idx))]
                        processed = self._apply_model_aware_to_dict(
                            dct=item,
                            target_type=field_type,
                            current_path=item_path,
                            metadata_registry=metadata_registry,
                            field_name=f"{key}[{idx}]"
                        )
                        processed_list.append(processed)
                    else:
                        processed_list.append(item)
                result[key] = processed_list
            else:
                result[key] = value
        
        return result
    
    # ------------------------------------------------------------------------
    # Фаза 2: Кастинг в модели
    # ------------------------------------------------------------------------
    
    def _cast_to_models(self, items: List[Any], target_type: Type,
                        metadata_registry: Dict[int, MetaData]) -> List[Any]:
        """Фаза 2: Преобразование словарей в объекты моделей."""
        log.debug(f"Кастинг данных {target_type}")
        result = []
        
        for item in items:
            if isinstance(item, dict):
                meta = item.pop(META_KEY, None) if META_KEY in item else None
                
                try:
                    instance = target_type(**item)
                    if meta:
                        setattr(instance, META_KEY, meta)
                    self._stats['models_created'] += 1
                    result.append(instance)
                except Exception:
                    if meta:
                        item[META_KEY] = meta
                    result.append(item)
            
            elif isinstance(item, list):
                processed = self._cast_to_models(item, target_type, metadata_registry)
                result.append(processed)
            
            else:
                result.append(item)
        
        return result