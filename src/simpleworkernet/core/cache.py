# simpleworkernet/core/cache.py
"""
Менеджер кэша для SmartData
"""
import time
import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .exceptions import WorkerNetCacheError

# Ленивый импорт
_logger = None
_config_manager = None


def _get_logger():
    """Ленивый импорт логгера"""
    global _logger
    if _logger is None:
        from .logger import log
        _logger = log
    return _logger


def _get_config_manager():
    """Ленивый импорт ConfigManager (экземпляра)"""
    global _config_manager
    if _config_manager is None:
        from .config import config_manager
        _config_manager = config_manager
    return _config_manager


@dataclass
class CacheStats:
    """Статистика кэша"""
    hits: int = 0
    misses: int = 0
    numeric_hits: int = 0
    access_count: Dict[str, int] = field(default_factory=dict)
    total_operations: int = 0
    last_save_time: float = 0
    last_load_time: float = 0


class SmartDataCache:
    """
    Менеджер кэша для SmartData.
    Синглтон для текущего процесса, использует имя текущего приложения.
    """
    
    _instance: Optional['SmartDataCache'] = None
    
    def __new__(cls) -> 'SmartDataCache':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Получаем информацию из ConfigManager
        config_manager = _get_config_manager()
        self.app_name = config_manager.app_name
        
        self._field_name_cache: Dict[str, bool] = {}
        self._numeric_cache: Dict[str, bool] = {}
        self._stats = CacheStats()
        
        self._cache_dir: Optional[Path] = None
        self._cache_file: Optional[Path] = None
        self._enabled = True
        self._max_size = 500000
        self._auto_save_enabled = True
        self._cache_version = "1.0"
        
        # Флаг "грязный" - были ли изменения с последнего сохранения
        self._dirty = False
        
        # Применяем конфигурацию
        self._apply_config()
        
        self._initialized = True
    
    def _apply_config(self):
        """Применяет текущую конфигурацию"""
        config_manager = _get_config_manager()
        config = config_manager.get_cache_config()
        
        self._enabled = config.get('enabled', True)
        self._max_size = config.get('max_size', 50000)
        self._auto_save_enabled = config.get('auto_save', True)
        
        cache_dir = config.get('cache_dir')
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._generate_cache_path()
    
    def _generate_cache_path(self):
        """Генерирует путь к файлу кэша"""
        if not self._cache_dir:
            return
        
        # Создаем хеш от пути для уникальности
        import inspect
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == '<module>':
                module_path = Path(frame.f_code.co_filename).parent
                break
            frame = frame.f_back
        else:
            module_path = Path.cwd()
        
        hash_str = hashlib.md5(str(module_path).encode()).hexdigest()[:8]
        self._cache_file = self._cache_dir / f"cache_{hash_str}.pkl"
    
    def enable(self):
        self._enabled = True
        _get_logger().info(f"Кэширование включено")
    
    def disable(self):
        self._enabled = False
        _get_logger().info(f"Кэширование отключено")
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def get_cache_path(self) -> Optional[Path]:
        return self._cache_file
    
    def save(self, force: bool = False) -> bool:
        """
        Сохраняет кэш в файл, только если были изменения.
        
        Args:
            force: Если True, сохраняет даже если нет изменений
        """
        if not self._enabled:
            return False
        
        if not self._auto_save_enabled and not force:
            return False
        
        # Проверяем, были ли изменения
        if not self._dirty and not force:
            _get_logger().debug("Кэш не изменялся, пропускаем сохранение")
            return False
        
        if not self._cache_file:
            return False
        
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        cache_data = {
            'version': self._cache_version,
            'timestamp': time.time(),
            'field_name_cache': dict(self._field_name_cache),
            'numeric_cache': dict(self._numeric_cache),
            'access_count': dict(self._stats.access_count),
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'numeric_hits': self._stats.numeric_hits,
        }
        
        try:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            self._stats.last_save_time = time.time()
            size_kb = self._cache_file.stat().st_size / 1024
            
            # Сбрасываем флаг изменений
            self._dirty = False
            
            _get_logger().info(
                f"Кэш сохранён: {len(self._field_name_cache)} полей, {size_kb:.1f} КБ"
            )
            return True
            
        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка сохранения кэша: {e}")

    def preload_from_models(self, *model_classes, recursive: bool = True, max_depth: int = 10):
        """
        Предварительно загружает поля из моделей в кэш.
        
        Args:
            *model_classes: Классы моделей для загрузки
            recursive: Загружать рекурсивно вложенные модели
            max_depth: Максимальная глубина рекурсии
        """
        if not self._enabled:
            _get_logger().debug("Кэширование отключено, предзагрузка пропущена")
            return
        
        from typing import get_type_hints, get_origin, get_args, List, Dict, Union
        from ..models.base import BaseModel
        
        _get_logger().info(f"Предзагрузка {len(model_classes)} моделей в кэш...")
        
        if not model_classes:
            _get_logger().warning("Нет моделей для предзагрузки")
            return
        
        before = len(self._field_name_cache)
        processed = set()
        
        def _unwrap_type(typ) -> type:
            """Извлекает внутренний тип из Generic"""
            origin = get_origin(typ)
            args = get_args(typ)
            if origin is Union:
                for arg in args:
                    if arg is not type(None):
                        return _unwrap_type(arg)
                return typ
            if origin in (list, List) and args:
                return _unwrap_type(args[0])
            if origin in (dict, Dict) and len(args) > 1:
                return _unwrap_type(args[1])
            return typ
        
        def _get_fields(model_class) -> list:
            """Возвращает список полей модели"""
            try:
                if hasattr(model_class, '__annotations__'):
                    return list(model_class.__annotations__.keys())
                elif hasattr(model_class, '__dataclass_fields__'):
                    return list(model_class.__dataclass_fields__.keys())
            except:
                pass
            return []
        
        def process_model(model_class, depth=0):
            """Рекурсивно обрабатывает модель"""
            if id(model_class) in processed:
                return
            processed.add(id(model_class))
            
            fields = _get_fields(model_class)
            _get_logger().debug(f"Обработка модели {model_class.__name__}: {len(fields)} полей")
            
            # Добавляем поля в кэш
            for field in fields:
                if field not in self._field_name_cache:
                    self._field_name_cache[field] = True
                    if field not in self._stats.access_count:
                        self._stats.access_count[field] = 0
                    self._dirty = True  # Отмечаем изменения
            
            if not recursive or depth >= max_depth:
                return
            
            # Обрабатываем вложенные модели
            try:
                hints = get_type_hints(model_class)
                for field_name, field_type in hints.items():
                    inner_type = _unwrap_type(field_type)
                    if (isinstance(inner_type, type) and
                        hasattr(inner_type, '__base__') and
                        inner_type.__base__ == BaseModel):
                        _get_logger().debug(f"  Вложенная модель: {inner_type.__name__}")
                        process_model(inner_type, depth + 1)
            except Exception as e:
                _get_logger().error(f"Ошибка при обработке {model_class.__name__}: {e}")
        
        # Обрабатываем каждую модель
        for i, model_class in enumerate(model_classes, 1):
            _get_logger().debug(f"Обработка модели {i}/{len(model_classes)}: {model_class.__name__}")
            try:
                process_model(model_class)
            except Exception as e:
                _get_logger().error(f"Ошибка предзагрузки {model_class.__name__}: {e}")
        
        added = len(self._field_name_cache) - before
        if added:
            _get_logger().info(f"Добавлено {added} новых полей в кэш (всего: {len(self._field_name_cache)})")

    def load(self) -> bool:
        """Загружает кэш из файла"""
        if not self._enabled or not self._cache_file or not self._cache_file.exists():
            return False
        
        try:
            with open(self._cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            if cache_data.get('version') != self._cache_version:
                _get_logger().warning("Версия кэша не совпадает")
                return False
            
            self._field_name_cache = cache_data.get('field_name_cache', {})
            self._numeric_cache = cache_data.get('numeric_cache', {})
            self._stats.access_count = cache_data.get('access_count', {})
            self._stats.hits = cache_data.get('hits', 0)
            self._stats.misses = cache_data.get('misses', 0)
            self._stats.numeric_hits = cache_data.get('numeric_hits', 0)
            self._stats.last_load_time = time.time()
            
            # После загрузки кэш чистый (нет изменений)
            self._dirty = False
            
            _get_logger().info(
                f"Кэш загружен: {len(self._field_name_cache)} полей"
            )
            return True
            
        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка загрузки кэша: {e}")
    
    def ensure_saved(self) -> bool:
        """
        Гарантирует сохранение кэша, если были изменения.
        """
        if not self._enabled:
            return False
        
        # Сохраняем только если есть изменения
        if self._dirty and (self._field_name_cache or self._numeric_cache):
            return self.save(force=True)
        
        return False
    
    def clear(self):
        """Очищает кэш"""
        fields_before = len(self._field_name_cache)
        numbers_before = len(self._numeric_cache)
        
        self._field_name_cache.clear()
        self._numeric_cache.clear()
        self._stats.access_count.clear()
        self._stats.hits = 0
        self._stats.misses = 0
        self._stats.numeric_hits = 0
        
        # Очистка - это изменение
        self._dirty = True
        
        _get_logger().info(
            f"Кэш очищен: удалено {fields_before} полей, {numbers_before} чисел"
        )
    
    def is_valid_field_name(self, name: str) -> bool:
        """Проверяет валидность имени поля с кэшированием"""
        if not self._enabled:
            return name and isinstance(name, str) and name.isidentifier()
        
        if not name or not isinstance(name, str):
            return False
        
        self._stats.total_operations += 1
        
        if name.isdigit():
            if name not in self._numeric_cache:
                self._numeric_cache[name] = False
                self._stats.misses += 1
                self._dirty = True  # Новое число в кэше
                self._check_size()
            else:
                self._stats.numeric_hits += 1
            return False
        
        cached = self._field_name_cache.get(name)
        if cached is not None:
            self._stats.hits += 1
            self._track_access(name)
            return cached
        
        result = name.isidentifier()
        self._field_name_cache[name] = result
        self._stats.misses += 1
        self._track_access(name)
        self._dirty = True  # Новое поле в кэше
        self._check_size()
        
        return result
    
    def _track_access(self, name: str):
        if name not in self._stats.access_count:
            self._stats.access_count[name] = 0
        self._stats.access_count[name] += 1
        # Изменение счетчика доступа не считаем изменением кэша
        # так как это не влияет на содержимое
    
    def _check_size(self):
        total_size = len(self._field_name_cache) + len(self._numeric_cache)
        if total_size >= self._max_size:
            self._evict_least_used()
    
    def _evict_least_used(self):
        if not self._stats.access_count:
            return
        
        sorted_items = sorted(self._stats.access_count.items(), key=lambda x: x[1])
        total_to_remove = max(1, int(len(sorted_items) * 0.2))
        to_remove = {name for name, _ in sorted_items[:total_to_remove]}
        
        removed = 0
        for name in to_remove:
            if name in self._field_name_cache:
                del self._field_name_cache[name]
                removed += 1
            if name in self._numeric_cache:
                del self._numeric_cache[name]
                removed += 1
            if name in self._stats.access_count:
                del self._stats.access_count[name]
        
        if removed > 0:
            self._dirty = True  # Удаление записей - это изменение
            _get_logger().debug(f"Кэш очищен: удалено {removed} записей")
    
    def get_stats(self) -> Dict[str, Any]:
        total = self._stats.hits + self._stats.misses
        return {
            'enabled': self._enabled,
            'total_operations': self._stats.total_operations,
            'total': total,
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'numeric_hits': self._stats.numeric_hits,
            'field_cache_size': len(self._field_name_cache),
            'numeric_cache_size': len(self._numeric_cache),
            'max_size': self._max_size,
            'hit_rate': (self._stats.hits / total * 100) if total > 0 else 0,
            'last_save': self._stats.last_save_time,
            'last_load': self._stats.last_load_time,
            'dirty': self._dirty,  # Добавляем информацию о наличии изменений
        }
    
    def set_max_size(self, size: int):
        old_size = self._max_size
        self._max_size = max(1000, min(size, 100000))
        # Изменение максимального размера не влияет на содержимое кэша
        _get_logger().info(
            f"Максимальный размер кэша изменён: {old_size} -> {self._max_size}"
        )


# Глобальный экземпляр (синглтон для текущего процесса)
cache = SmartDataCache()