# simpleworkernet/core/cache.py
"""
Менеджер кэша для SmartData.
Поддерживает стратегии: LRU, LFU, FIFO.
Настройки управляются через ConfigManager.
"""
import time
import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import OrderedDict, deque

from .exceptions import WorkerNetCacheError

# Ленивый импорт
_logger = None
_config_manager = None


def _get_logger():
    global _logger
    if _logger is None:
        from .logger import log
        _logger = log
    return _logger


def _get_config_manager():
    global _config_manager
    if _config_manager is None:
        from .config import config_manager
        _config_manager = config_manager
    return _config_manager


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    numeric_hits: int = 0
    access_count: Dict[str, int] = field(default_factory=dict)
    total_operations: int = 0
    last_save_time: float = 0
    last_load_time: float = 0


class SmartDataCache:
    _instance: Optional['SmartDataCache'] = None

    def __new__(cls) -> 'SmartDataCache':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        config_manager = _get_config_manager()
        self.app_name = config_manager.app_name

        self._field_name_cache: Dict[str, bool] = {}
        self._numeric_cache: Dict[str, bool] = {}
        self._stats = CacheStats()

        # Структуры для стратегий
        self._order = None
        self._strategy = None

        self._cache_dir: Optional[Path] = None
        self._cache_file: Optional[Path] = None
        self._cache_version = "1.0"
        self._dirty = False

        self._apply_config()
        self._initialized = True

    def _apply_config(self):
        config_manager = _get_config_manager()
        config = config_manager.get_cache_config()
        cache_cfg = config_manager.get().cache

        self._enabled = cache_cfg.enabled
        self._max_size = max(1000, cache_cfg.max_size)
        self._auto_save_enabled = cache_cfg.auto_save
        self._evict_threshold = max(0.1, min(1.0, cache_cfg.evict_threshold))
        self._evict_percent = max(0.01, min(1.0, cache_cfg.evict_percent))
        new_strategy = cache_cfg.evict_strategy.lower()

        if new_strategy != self._strategy:
            self._strategy = new_strategy
            if self._strategy == 'lru':
                self._order = OrderedDict()
            elif self._strategy == 'fifo':
                self._order = deque()
            else:  # lfu
                self._order = None

        cache_dir = config.get('cache_dir')
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._generate_cache_path()

    def _generate_cache_path(self):
        if not self._cache_dir:
            return
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
        config_manager = _get_config_manager()
        config_manager.cache_enabled = True

    def disable(self):
        config_manager = _get_config_manager()
        config_manager.cache_enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def get_cache_path(self) -> Optional[Path]:
        return self._cache_file

    def save(self, force: bool = False) -> bool:
        if not self._enabled:
            return False
        if not self._auto_save_enabled and not force:
            return False
        if not self._dirty and not force:
            _get_logger().debug("Кэш не изменялся, пропускаем сохранение")
            return False
        if not self._cache_file:
            return False

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        order_data = None
        if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
            order_data = list(self._order.keys())
        elif self._strategy == 'fifo' and isinstance(self._order, deque):
            order_data = list(self._order)

        cache_data = {
            'version': self._cache_version,
            'timestamp': time.time(),
            'field_name_cache': dict(self._field_name_cache),
            'numeric_cache': dict(self._numeric_cache),
            'access_count': dict(self._stats.access_count),
            'order_data': order_data,
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'numeric_hits': self._stats.numeric_hits,
        }

        try:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            self._stats.last_save_time = time.time()
            size_kb = self._cache_file.stat().st_size / 1024
            self._dirty = False

            total_entries = len(self._field_name_cache) + len(self._numeric_cache)
            _get_logger().info(
                f"Кэш сохранён: {len(self._field_name_cache)} полей, "
                f"{len(self._numeric_cache)} чисел, "
                f"всего записей={total_entries}, "
                f"размер={size_kb:.1f} КБ"
            )
            return True

        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка сохранения кэша: {e}")

    def load(self) -> bool:
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

            order_data = cache_data.get('order_data')
            if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
                self._order.clear()
                if order_data:
                    for key in order_data:
                        self._order[key] = None
            elif self._strategy == 'fifo' and isinstance(self._order, deque):
                self._order.clear()
                if order_data:
                    self._order.extend(order_data)

            self._dirty = False

            _get_logger().info(
                f"Кэш загружен: {len(self._field_name_cache)} полей, {len(self._numeric_cache)} чисел"
            )
            return True

        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка загрузки кэша: {e}")

    def ensure_saved(self) -> bool:
        """Гарантирует сохранение кэша, если были изменения."""
        if not self._enabled:
            return False
        if self._dirty and (self._field_name_cache or self._numeric_cache):
            return self.save(force=True)
        return False

    def clear(self):
        fields_before = len(self._field_name_cache)
        numbers_before = len(self._numeric_cache)

        self._field_name_cache.clear()
        self._numeric_cache.clear()
        self._stats.access_count.clear()
        self._stats.hits = 0
        self._stats.misses = 0
        self._stats.numeric_hits = 0
        if isinstance(self._order, OrderedDict):
            self._order.clear()
        elif isinstance(self._order, deque):
            self._order.clear()
        self._dirty = True

        _get_logger().info(
            f"Кэш очищен: удалено {fields_before} полей, {numbers_before} чисел"
        )

    def preload_from_models(self, *model_classes, recursive: bool = True, max_depth: int = 10):
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
            try:
                if hasattr(model_class, '__annotations__'):
                    return list(model_class.__annotations__.keys())
                elif hasattr(model_class, '__dataclass_fields__'):
                    return list(model_class.__dataclass_fields__.keys())
            except:
                pass
            return []

        def process_model(model_class, depth=0):
            if id(model_class) in processed:
                return
            processed.add(id(model_class))

            fields = _get_fields(model_class)
            _get_logger().debug(f"Обработка модели {model_class.__name__}: {len(fields)} полей")

            for field in fields:
                if field not in self._field_name_cache:
                    self._field_name_cache[field] = True
                    if field not in self._stats.access_count:
                        self._stats.access_count[field] = 0
                    self._dirty = True
                    self._add_to_order(field)

            if not recursive or depth >= max_depth:
                return

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

        for i, model_class in enumerate(model_classes, 1):
            _get_logger().debug(f"Обработка модели {i}/{len(model_classes)}: {model_class.__name__}")
            try:
                process_model(model_class)
            except Exception as e:
                _get_logger().error(f"Ошибка предзагрузки {model_class.__name__}: {e}")

        added = len(self._field_name_cache) - before
        if added:
            _get_logger().info(f"Добавлено {added} новых полей в кэш (всего: {len(self._field_name_cache)})")

    def is_valid_field_name(self, name: str) -> bool:
        if not self._enabled:
            return name and isinstance(name, str) and name.isidentifier()

        if not name or not isinstance(name, str):
            return False

        self._stats.total_operations += 1

        if name.isdigit():
            if name not in self._numeric_cache:
                self._numeric_cache[name] = False
                self._stats.misses += 1
                self._dirty = True
                self._add_to_order(name)
                self._check_size()
            else:
                self._stats.numeric_hits += 1
                self._track_access(name)
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
        self._add_to_order(name)
        self._dirty = True
        self._check_size()

        return result

    def _add_to_order(self, name: str):
        if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
            self._order[name] = None
        elif self._strategy == 'fifo' and isinstance(self._order, deque):
            self._order.append(name)

    def _track_access(self, name: str):
        if name not in self._stats.access_count:
            self._stats.access_count[name] = 0
        self._stats.access_count[name] += 1

        if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
            if name in self._order:
                self._order.move_to_end(name)

    def _check_size(self):
        total_size = len(self._field_name_cache) + len(self._numeric_cache)
        if total_size >= self._max_size * self._evict_threshold:
            self._evict_least_used()

    def _evict_least_used(self):
        total_size = len(self._field_name_cache) + len(self._numeric_cache)
        if total_size == 0:
            return

        to_remove_count = max(1, int(total_size * self._evict_percent))

        if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
            to_remove = []
            for _ in range(to_remove_count):
                if not self._order:
                    break
                key, _ = self._order.popitem(last=False)
                to_remove.append(key)
        elif self._strategy == 'fifo' and isinstance(self._order, deque):
            to_remove = []
            for _ in range(to_remove_count):
                if not self._order:
                    break
                key = self._order.popleft()
                to_remove.append(key)
        else:  # lfu
            sorted_items = sorted(self._stats.access_count.items(), key=lambda x: x[1])
            to_remove = [name for name, _ in sorted_items[:to_remove_count]]

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
            if self._strategy == 'lru' and isinstance(self._order, OrderedDict):
                if name in self._order:
                    del self._order[name]
            elif self._strategy == 'fifo' and isinstance(self._order, deque):
                try:
                    self._order.remove(name)
                except ValueError:
                    pass

        if removed > 0:
            self._dirty = True
            _get_logger().debug(
                f"Кэш очищен (стратегия {self._strategy.upper()}): "
                f"удалено {removed} записей (размер до: {total_size}, после: {total_size - removed})"
            )

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
            'evict_strategy': self._strategy,
            'evict_percent': self._evict_percent,
            'evict_threshold': self._evict_threshold,
            'hit_rate': (self._stats.hits / total * 100) if total > 0 else 0,
            'last_save': self._stats.last_save_time,
            'last_load': self._stats.last_load_time,
            'dirty': self._dirty,
        }

    def set_max_size(self, size: int):
        config_manager = _get_config_manager()
        config_manager.cache_max_size = max(1000, size)


cache = SmartDataCache()