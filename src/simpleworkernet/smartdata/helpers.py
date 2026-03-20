# simpleworkernet/smartdata/helpers.py
"""
Вспомогательные функции для SmartData.
Содержит утилиты для работы с типами, метаданными и структурами данных.
"""

import html
import re
from typing import Any, List, Dict, Tuple, Optional, Set, Union
from urllib.parse import unquote_plus
from dataclasses import is_dataclass, fields
from typing import get_origin, get_args, List as ListType, Dict as DictType, Union as UnionType

from ..core.logger import log
from .metadata import MetaData, META_KEY, PathSegment, SegmentType

# ------------------------------------------------------------------------
# Константы
# ------------------------------------------------------------------------

DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# ------------------------------------------------------------------------
# Базовые проверки и преобразования
# ------------------------------------------------------------------------

def is_primitive(value: Any) -> bool:
    """
    Проверяет, является ли значение простым типом.
    
    Args:
        value: Значение для проверки
        
    Returns:
        True для None, int, float, str, bool
    """
    return value is None or isinstance(value, (int, float, str, bool))


def decode_string(value: Any) -> str:
    """
    Декодирует строку из URL и HTML entities.
    
    Args:
        value: Значение для декодирования
        
    Returns:
        Декодированная строка
    """
    if value is None:
        return ""
    return unquote_plus(html.unescape(str(value)), encoding="utf-8")


# ------------------------------------------------------------------------
# Работа с типами
# ------------------------------------------------------------------------

def is_union_type(tp) -> bool:
    """
    Проверяет, является ли тип Union (включая Optional).
    
    Args:
        tp: Тип для проверки
        
    Returns:
        True если тип является Union или Optional
    """
    origin = get_origin(tp)
    return origin is UnionType or (hasattr(tp, "__origin__") and tp.__origin__ is UnionType)


def is_list_type(tp) -> bool:
    """
    Проверяет, является ли тип списком.
    
    Args:
        tp: Тип для проверки
        
    Returns:
        True если тип является List (или list)
    """
    origin = get_origin(tp)
    return origin is list or origin is ListType


def get_list_inner_type(tp):
    """
    Возвращает внутренний тип для списка.
    
    Args:
        tp: Тип списка (List[T])
        
    Returns:
        Внутренний тип T или Any, если тип не определен
    """
    if not is_list_type(tp):
        return Any
    args = get_args(tp)
    return args[0] if args else Any


def is_optional_type(tp) -> bool:
    """
    Проверяет, является ли тип Optional (Union с None).
    
    Args:
        tp: Тип для проверки
        
    Returns:
        True если тип является Optional
    """
    if not is_union_type(tp):
        return False
    args = get_args(tp)
    return type(None) in args


def get_union_types(tp):
    """
    Возвращает список типов из Union (исключая None).
    
    Args:
        tp: Union тип
        
    Returns:
        Список типов
    """
    if not is_union_type(tp):
        return [tp]
    return [t for t in get_args(tp) if t is not type(None)]


def unwrap_type(tp):
    """
    Извлекает базовый тип из Optional, List, Union.
    
    Args:
        tp: Тип для распаковки
        
    Returns:
        Базовый тип или исходный тип
    """
    origin = get_origin(tp)
    if origin is UnionType:
        args = get_args(tp)
        if len(args) == 2 and type(None) in args:
            return unwrap_type(args[0] if args[1] is type(None) else args[1])
        return unwrap_type(args[0])
    
    if origin in (list, ListType):
        args = get_args(tp)
        if args:
            return unwrap_type(args[0])
        return Any
    
    return tp


def get_base_type(target_type: Any) -> Tuple[Any, bool]:
    """
    Возвращает базовый тип и флаг, является ли исходный тип списком.
    
    Args:
        target_type: Целевой тип (может быть List[T] или T)
        
    Returns:
        Кортеж (базовый тип, является_ли_списком)
    """
    if is_list_type(target_type):
        return get_list_inner_type(target_type), True
    return target_type, False


# ------------------------------------------------------------------------
# Работа с ключами
# ------------------------------------------------------------------------

def is_numeric_key(key: str) -> bool:
    """Проверяет, является ли ключ числовым."""
    if not key:
        return False
    return key.isdigit() or (key.startswith('-') and key[1:].isdigit())


def is_date_key(key: str) -> bool:
    """Проверяет, является ли ключ датой."""
    return bool(DATE_PATTERN.match(key))


def get_key_type(key: str, cache_func=None) -> SegmentType:
    """
    Определяет тип ключа для пути.
    
    Args:
        key: Ключ для анализа
        cache_func: Функция проверки валидности ключа
        
    Returns:
        Тип сегмента
    """
    if is_date_key(key):
        return SegmentType.DAT
    if is_numeric_key(key):
        return SegmentType.NUM
    
    if cache_func:
        is_valid = cache_func(key)
    else:
        is_valid = key.isidentifier()
    
    if is_valid:
        return SegmentType.FLD
    return SegmentType.COL


def all_keys_numeric(data: Dict, skip_meta: bool = True) -> bool:
    """
    Проверяет, все ли ключи числовые.
    
    Args:
        data: Словарь для проверки
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если все ключи числовые
    """
    for key in data.keys():
        if skip_meta and key == META_KEY:
            continue
        if not is_numeric_key(str(key)):
            return False
    return True


def all_keys_valid(data: Dict, cache_func=None, skip_meta: bool = True) -> bool:
    """
    Проверяет, все ли ключи валидные.
    
    Args:
        data: Словарь для проверки
        cache_func: Функция проверки валидности
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если все ключи валидные
    """
    for key in data.keys():
        if skip_meta and key == META_KEY:
            continue
        
        if cache_func:
            if not cache_func(str(key)):
                return False
        else:
            if not str(key).isidentifier():
                return False
    return True


def keys_equal_values(data: Dict, skip_meta: bool = True) -> bool:
    """
    Проверяет, совпадают ли строковые представления ключей со значениями.
    
    Args:
        data: Словарь для проверки
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если каждый ключ равен своему значению
    """
    for key, value in data.items():
        if skip_meta and key == META_KEY:
            continue
        if str(key) != str(value):
            return False
    return True


def all_values_are_primitives(data: Dict, skip_meta: bool = True) -> bool:
    """
    Проверяет, все ли значения - примитивы.
    
    Args:
        data: Словарь для проверки
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если все значения примитивные
    """
    for value in data.values():
        if not is_primitive(value):
            return False
    return True


def all_values_are_dicts(data: Dict, skip_meta: bool = True) -> bool:
    """
    Проверяет, все ли значения - словари.
    
    Args:
        data: Словарь для проверки
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если все значения словари
    """
    for value in data.values():
        if not isinstance(value, dict):
            return False
    return True


def all_values_are_lists_of_dicts(data: Dict, skip_meta: bool = True) -> bool:
    """
    Проверяет, все ли значения - списки словарей.
    
    Args:
        data: Словарь для проверки
        skip_meta: Пропускать ключ META_KEY
        
    Returns:
        True если все значения списки словарей
    """
    for value in data.values():
        if not isinstance(value, list):
            return False
        for item in value:
            if not isinstance(item, dict):
                return False
    return True


def sort_dict_items(data: Dict) -> List[Tuple]:
    """
    Сортирует элементы словаря: сначала числовые ключи, затем строковые.
    
    Args:
        data: Словарь для сортировки
        
    Returns:
        Отсортированный список пар (ключ, значение)
    """
    items = list(data.items())
    numeric = []
    other = []
    
    for key, val in items:
        if key == META_KEY:
            continue
        s = str(key)
        if s.isdigit():
            numeric.append((int(s), key, val))
        else:
            other.append((s, key, val))
    
    numeric.sort(key=lambda x: x[0])
    other.sort(key=lambda x: x[0])
    
    result = []
    for _, k, v in numeric:
        result.append((k, v))
    for _, k, v in other:
        result.append((k, v))
    
    return result


# ------------------------------------------------------------------------
# Работа с метаданными
# ------------------------------------------------------------------------

def build_metadata(path: List[Tuple[SegmentType, str]]) -> MetaData:
    """
    Строит объект MetaData из пути.
    
    Args:
        path: Список кортежей (тип, значение)
        
    Returns:
        Объект MetaData
    """
    segments = [PathSegment(seg_type, key) for seg_type, key in path]
    return MetaData(path=segments)


def attach_metadata(obj: Any, metadata: MetaData) -> Any:
    """
    Прикрепляет метаданные к объекту.
    
    Args:
        obj: Объект (словарь, список или примитив)
        metadata: Метаданные для прикрепления
        
    Returns:
        Объект с прикрепленными метаданными
    """
    if isinstance(obj, dict):
        obj[META_KEY] = metadata
        return obj
    return obj


def extract_metadata(obj: Any) -> Tuple[Any, Optional[MetaData]]:
    """
    Извлекает метаданные из объекта.
    
    Args:
        obj: Объект с возможными метаданными
        
    Returns:
        Кортеж (объект без метаданных, метаданные или None)
    """
    if isinstance(obj, dict) and META_KEY in obj:
        metadata = obj[META_KEY]
        clean_obj = {k: v for k, v in obj.items() if k != META_KEY}
        return clean_obj, metadata
    return obj, None


def has_metadata(obj: Any) -> bool:
    """Проверяет, есть ли у объекта метаданные."""
    return isinstance(obj, dict) and META_KEY in obj


def clear_metadata(obj: Any) -> Any:
    """Очищает метаданные из объекта."""
    if isinstance(obj, dict) and META_KEY in obj:
        return {k: v for k, v in obj.items() if k != META_KEY}
    return obj


# ------------------------------------------------------------------------
# Работа со списками
# ------------------------------------------------------------------------

def collapse_list(lst: Any, mode: str = 'auto', depth: int = 0, max_depth: int = 100) -> Any:
    """
    Универсальная функция схлопывания списков.
    
    Режимы:
    - 'auto': автоматическое определение по типам элементов
    - 'aggressive': полное схлопывание матрешек
    - 'preserve': сохранение структуры
    
    Args:
        lst: Входной список
        mode: Режим схлопывания
        depth: Текущая глубина рекурсии
        max_depth: Максимальная глубина рекурсии
        
    Returns:
        Обработанный список
    """
    if not isinstance(lst, list):
        return lst
    
    if len(lst) == 0:
        return lst
    
    if depth > max_depth:
        log.warning(f"Превышена глубина {max_depth} в collapse_list")
        return lst

    # Всегда разворачиваем одинарные матрешки
    while len(lst) == 1 and isinstance(lst[0], list):
        lst = lst[0]
        if len(lst) == 0:
            break
    
    if mode == 'preserve':
        result = []
        for item in lst:
            if isinstance(item, list):
                result.append(collapse_list(item, 'preserve', depth + 1, max_depth))
            else:
                result.append(item)
        return result
    
    if mode == 'aggressive':
        while len(lst) == 1 and isinstance(lst[0], list):
            lst = lst[0]
        
        result = []
        for item in lst:
            if isinstance(item, list):
                item = collapse_list(item, 'aggressive', depth + 1, max_depth)
                if isinstance(item, list):
                    result.extend(item)
                else:
                    result.append(item)
            else:
                result.append(item)
        
        while len(result) == 1 and isinstance(result[0], list):
            result = result[0]
        
        return result
    
    # Режим 'auto'
    all_primitives = all(is_primitive(item) for item in lst)
    
    if all_primitives:
        return collapse_list(lst, 'preserve', depth + 1, max_depth)
    else:
        return collapse_list(lst, 'aggressive', depth + 1, max_depth)


def flatten_list(lst: List[Any], max_depth: int = 100) -> List[Any]:
    """
    Распрямляет вложенные списки в плоский список.
    
    Args:
        lst: Входной список
        max_depth: Максимальная глубина рекурсии
        
    Returns:
        Плоский список
    """
    result = []
    
    def _flatten(item: Any, depth: int = 0):
        if depth > max_depth:
            log.warning(f"Превышена глубина {max_depth} в flatten_list")
            result.append(item)
            return
        
        if isinstance(item, list):
            for subitem in item:
                _flatten(subitem, depth + 1)
        else:
            result.append(item)
    
    _flatten(lst)
    return result


# ------------------------------------------------------------------------
# Работа с моделями
# ------------------------------------------------------------------------

def is_model_class(cls) -> bool:
    """
    Проверяет, является ли класс моделью BaseModel.
    
    Args:
        cls: Класс для проверки
        
    Returns:
        True если это класс, наследующий BaseModel
    """
    from ..models.base import BaseModel
    
    if not isinstance(cls, type):
        return False
    
    try:
        return issubclass(cls, BaseModel)
    except (TypeError, AttributeError):
        return False


def get_model_fields(model_type: Any) -> Set[str]:
    """
    Возвращает имена полей модели.
    
    Args:
        model_type: Класс модели или тип
        
    Returns:
        Множество имен полей
    """
    if not model_type or model_type is Any:
        return set()
    
    if hasattr(model_type, '__annotations__'):
        return set(model_type.__annotations__.keys())
    
    if is_dataclass(model_type):
        return {f.name for f in fields(model_type)}
    
    return set()


def get_model_fields_with_types(model_type: Any) -> Dict[str, Any]:
    """
    Возвращает словарь {имя_поля: тип_поля} для модели.
    
    Args:
        model_type: Тип модели
        
    Returns:
        Словарь с полями и их типами
    """
    if model_type is None or model_type is Any:
        return {}
    
    if not is_model_class(model_type):
        return {}
    
    if hasattr(model_type, '__annotations__'):
        return model_type.__annotations__
    
    return {}


def dict_matches_model(dct: Dict, model_type: Any) -> bool:
    """
    Проверяет, соответствует ли словарь модели.
    
    Args:
        dct: Словарь для проверки
        model_type: Тип модели
        
    Returns:
        True если все ключи словаря есть в модели
    """
    fields = get_model_fields(model_type)
    dict_keys = set(dct.keys())
    return dict_keys.issubset(fields)


def is_list_of_models_type(field_type: Any) -> bool:
    """
    Проверяет, является ли тип List[Model].
    
    Args:
        field_type: Тип поля для проверки
        
    Returns:
        True если это List[Model]
    """
    if not is_list_type(field_type):
        return False
    
    inner_type = get_list_inner_type(field_type)
    return is_model_class(inner_type)


# ------------------------------------------------------------------------
# Работа со словарями
# ------------------------------------------------------------------------

def safe_get(data: Union[Dict, List, Any], *keys: Any, default: Any = None) -> Any:
    """
    Безопасно получает значение из вложенной структуры.
    
    Args:
        data: Словарь или список
        *keys: Ключи для доступа
        default: Значение по умолчанию
        
    Returns:
        Значение или default
    """
    current = data
    
    for key in keys:
        if current is None:
            return default
        
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, (list, tuple)) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        elif hasattr(current, key):
            current = getattr(current, key)
        else:
            return default
    
    return current if current is not None else default