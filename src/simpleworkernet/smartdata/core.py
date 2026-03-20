# simpleworkernet/smartdata/core.py
"""
Основной класс SmartData - контейнер для готовых обработанных данных.
"""

import json
import pickle
import gzip
from typing import (
    TypeVar, Generic, List, Dict, Tuple, Any, Union, Optional, Callable, Iterator,
    overload, Type
)
from pathlib import Path

from ..core.logger import log
from ..core.config import config_manager

from .metadata import MetaData, META_KEY, PathSegment, SegmentType
from .processor import DataProcessor

from ..models.operators import Operator, Where


T = TypeVar('T')

class SmartData(Generic[T]):
    """
    Контейнер для готовых обработанных данных.
    
    Основные возможности:
    - Хранение готовых объектов моделей
    - Fluent-интерфейс для фильтрации и трансформации
    - Статистические методы (count, sum, avg, etc.)
    - Сериализация в различные форматы с восстановлением исходной структуры
    - Доступ к метаданным элементов
    """
    
    __slots__ = ('_items', '_target_type', '_stats')
    
    def __init__(self, data: Any, target_type: Type[T] = Any):
        """
        Инициализирует SmartData, передавая данные в DataProcessor.
        
        Args:
            data: Входные данные от API
            target_type: Целевой тип для преобразования элементов
        """
        smartdata_config = config_manager.get_smartdata_config()
        max_depth = smartdata_config.get('max_depth', 100)
        
        self._target_type = target_type
        self._items: List[T] = []
        self._stats: Dict[str, int] = {}
        
        if data is not None:
            log.debug(f"SmartData инициализация: data type={type(data)}, target={target_type}")
            
            processor = DataProcessor(max_depth=max_depth)
            result = processor.process(
                data=data,
                target_type=target_type,
                cache_func=self._is_valid_field_name
            )
            
            self._items = result.items
            self._stats = result.stats
            
            log.info(f"SmartData инициализирован: {len(self._items)} элементов")
    
    def _is_valid_field_name(self, name: str) -> bool:
        """Проверяет валидность имени поля с использованием кэша."""
        return DataProcessor._cache.is_valid_field_name(name)
    
    # ------------------------------------------------------------------------
    # Методы работы с метаданными
    # ------------------------------------------------------------------------
    
    def get_metadata(self, item: Any) -> Optional[MetaData]:
        """Возвращает метаданные для элемента."""
        if hasattr(item, META_KEY):
            return getattr(item, META_KEY)
        return None
    
    def get_item_path(self, item: Any) -> str:
        """Возвращает путь к элементу в исходной структуре."""
        meta = self.get_metadata(item)
        return meta.get_path_string() if meta else ''
    
    # ------------------------------------------------------------------------
    # Методы для работы с кэшем
    # ------------------------------------------------------------------------
    
    @classmethod
    def get_cache_path(cls) -> Path:
        return DataProcessor.get_cache_path()
    
    @classmethod
    def save_cache(cls, force: bool = False) -> bool:
        return DataProcessor.save_cache(force)
    
    @classmethod
    def load_cache(cls, preload_only: bool = False) -> bool:
        return DataProcessor.load_cache(preload_only)
    
    @classmethod
    def ensure_cache_saved(cls) -> bool:
        return DataProcessor.ensure_cache_saved()
    
    @classmethod
    def clear_cache(cls) -> None:
        DataProcessor.clear_cache()
    
    @classmethod
    def preload_from_models(cls, *model_classes, recursive: bool = True, **kwargs) -> None:
        DataProcessor.preload_from_models(*model_classes, recursive=recursive, **kwargs)
    
    @classmethod
    def set_cache_max_size(cls, size: int) -> None:
        DataProcessor.set_cache_max_size(size)
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        return DataProcessor.get_cache_stats()
    
    # ------------------------------------------------------------------------
    # Fluent-интерфейс
    # ------------------------------------------------------------------------
    
    def _derived(self, items: List[T]) -> 'SmartData[T]':
        """Создает новый экземпляр с теми же настройками."""
        new = self.__class__.__new__(self.__class__)
        new._target_type = self._target_type
        new._items = items
        new._stats = self._stats.copy()
        return new
    
    def filter(self, *conditions: Where, join: str = 'AND') -> 'SmartData[T]':
        """Фильтрует элементы по условиям Where."""
        filtered = [
            item for item in self._items
            if (join.upper() == 'AND' and all(c.check(item) for c in conditions)) or
               (join.upper() == 'OR' and any(c.check(item) for c in conditions))
        ]
        return self._derived(filtered)
    
    def where(self, key: str, value: Any = None, op: Operator = Operator.EQ) -> 'SmartData[T]':
        """Фильтрует по простому условию."""
        return self.filter(Where(key, value, op))
    
    def sort(self, key: Optional[Callable[[T], Any]] = None, reverse: bool = False) -> 'SmartData[T]':
        """Сортирует элементы."""
        return self._derived(sorted(self._items, key=key, reverse=reverse))
    
    def limit(self, count: int) -> 'SmartData[T]':
        """Ограничивает количество элементов."""
        return self._derived(self._items[:count])
    
    def skip(self, count: int) -> 'SmartData[T]':
        """Пропускает первые N элементов."""
        return self._derived(self._items[count:])
    
    def map(self, func: Callable[[T], Any]) -> List[Any]:
        """Применяет функцию к каждому элементу."""
        return [func(item) for item in self._items]
    
    def group_by(self, key_func: Callable[[T], Any]) -> Dict[Any, 'SmartData[T]']:
        """Группирует элементы по ключу."""
        groups = {}
        for item in self._items:
            key = key_func(item)
            if key not in groups:
                groups[key] = self._derived([])
            groups[key]._items.append(item)
        return groups
    
    def unique(self, key_func: Optional[Callable[[T], Any]] = None) -> 'SmartData[T]':
        """Возвращает уникальные элементы."""
        seen = set()
        unique_items = []
        
        if key_func:
            for item in self._items:
                key = key_func(item)
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)
        else:
            for item in self._items:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
        
        return self._derived(unique_items)
    
    # ------------------------------------------------------------------------
    # Статистические методы
    # ------------------------------------------------------------------------
    
    def count(self) -> int:
        return len(self._items)
    
    def first(self) -> Optional[T]:
        return self._items[0] if self._items else None
    
    def last(self) -> Optional[T]:
        return self._items[-1] if self._items else None
    
    def min(self, key_func: Optional[Callable[[T], Any]] = None) -> Optional[T]:
        if not self._items:
            return None
        if key_func:
            return min(self._items, key=key_func)
        return min(self._items)
    
    def max(self, key_func: Optional[Callable[[T], Any]] = None) -> Optional[T]:
        if not self._items:
            return None
        if key_func:
            return max(self._items, key=key_func)
        return max(self._items)
    
    def sum(self, key_func: Callable[[T], Union[int, float]]) -> Union[int, float]:
        total = 0
        for item in self._items:
            total += key_func(item)
        return total
    
    def avg(self, key_func: Callable[[T], Union[int, float]]) -> float:
        if not self._items:
            return 0.0
        return self.sum(key_func) / len(self._items)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_items': len(self._items),
            'target_type': getattr(self._target_type, '__name__', str(self._target_type)),
            'processor_stats': self._stats.copy()
        }
    
    # ------------------------------------------------------------------------
    # Сериализация с восстановлением структуры по метаданным
    # ------------------------------------------------------------------------
    
    def to_list(self) -> List[T]:
        """Возвращает список элементов."""
        return self._items.copy()

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует все данные в единый словарь.
        
        Для каждого элемента вызывается его to_dict() (который уже применил все метаданные),
        затем все полученные словари объединяются в один результирующий словарь.
        
        Returns:
            Словарь, объединяющий все элементы по их корневым ключам
        """
         
        result = {}
        
        for item in self._items:
            # Получаем словарь от элемента
            if hasattr(item, 'to_dict') and callable(getattr(item, 'to_dict')):
                item_dict = item.to_dict()
            else:
                item_dict = item
            
            # Объединяем с общим результатом
            if isinstance(item_dict, dict):
                result.update(item_dict)
            else:
                # Если элемент не словарь, используем его как значение
                pass
        
        return result

    def to_file(self, filename: str, format: Optional[str] = None) -> None:
        """Сохраняет данные в файл с восстановленной структурой."""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format is None:
            format = path.suffix.lstrip('.') or 'json'
        
        data = self.to_dict()
        
        if format == 'json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        elif format == 'pkl':
            with open(path, 'wb') as f:
                pickle.dump(data, f)
        elif format == 'gz':
            with gzip.open(path, 'wb') as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")
        
        log.info(f"Данные сохранены в {path}")
    
    @classmethod
    def from_file(cls, filename: str, target_type: Type[T] = Any) -> 'SmartData[T]':
        """Загружает данные из файла."""
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {filename}")
        
        if path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif path.suffix == '.pkl':
            with open(path, 'rb') as f:
                data = pickle.load(f)
        elif path.suffix == '.gz':
            with gzip.open(path, 'rb') as f:
                data = pickle.load(f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {path.suffix}")
        
        return cls(data, target_type)
    
    def _is_path_processed(self, path: str, processed_paths: set) -> bool:
        """Проверяет, обработан ли путь."""
        return path in processed_paths or not path
    
    def _get_child_paths(self, path: str, groups: dict) -> List[str]:
        """Возвращает дочерние пути для заданного пути."""
        prefix = path + '/' if path else ''
        return [p for p in groups.keys() if p.startswith(prefix) and p != path]
    
    # ------------------------------------------------------------------------
    # Магические методы
    # ------------------------------------------------------------------------
    
    def __len__(self) -> int:
        return len(self._items)
    
    @overload
    def __getitem__(self, key: int) -> T: ...
    
    @overload
    def __getitem__(self, key: slice) -> 'SmartData[T]': ...
    
    @overload
    def __getitem__(self, key: str) -> List[Any]: ...
    
    def __getitem__(self, key):
        if isinstance(key, int):
            if key < 0 or key >= len(self._items):
                raise IndexError(f"Индекс {key} вне диапазона")
            return self._items[key]
        
        if isinstance(key, slice):
            return self._derived(self._items[key])
        
        if isinstance(key, str):
            result = []
            for item in self._items:
                if hasattr(item, key):
                    result.append(getattr(item, key, None))
                elif isinstance(item, dict):
                    result.append(item.get(key))
                else:
                    result.append(None)
            return result
        
        raise TypeError(f"Неподдерживаемый тип ключа: {type(key).__name__}")
    
    def __getattr__(self, name: str) -> List[Any]:
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self[name]
    
    def __iter__(self) -> Iterator[T]:
        return iter(self._items)
    
    def __contains__(self, item: T) -> bool:
        return item in self._items
    
    def __add__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        if isinstance(other, SmartData):
            return self._derived(self._items + other._items)
        if isinstance(other, list):
            return self._derived(self._items + other)
        raise TypeError(f"Нельзя сложить SmartData с {type(other)}")
    
    def __iadd__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        if isinstance(other, SmartData):
            self._items.extend(other._items)
        elif isinstance(other, list):
            self._items.extend(other)
        else:
            raise TypeError(f"Нельзя сложить SmartData с {type(other)}")
        return self
    
    def __bool__(self) -> bool:
        return bool(self._items)
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SmartData):
            return False
        return self.to_dict(clear_meta=True) == other.to_dict(clear_meta=True)
    
    def __repr__(self) -> str:
        return f"SmartData[{self._target_type}](count={len(self._items)}, items={self._items})"