# simpleworkernet/smartdata/metadata.py
"""
Классы для работы с метаданными SmartData
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class SegmentType(Enum):
    """
    Типы сегментов пути в метаданных.
    
    Значения:
        FLD: валидное имя поля (identifier)
        NUM: числовой ключ
        DAT: ключ-дата (ГГГГ-ММ-ДД)
        IDX: индекс в списке
        COL: схлопнутый ключ (контейнер)
    """
    FLD = 'fld'
    NUM = 'num'
    DAT = 'dat'
    IDX = 'idx'
    COL = 'col'
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> 'SegmentType':
        """Создает тип из строкового представления."""
        try:
            return cls(value)
        except ValueError:
            # Если неизвестный тип, возвращаем COL как наиболее общий
            return cls.COL


@dataclass
class PathSegment:
    """
    Сегмент пути с информацией о трансформации.
    
    Attributes:
        type: Тип сегмента (SegmentType)
        key: Исходный ключ или индекс
    """
    type: SegmentType
    key: str
    
    def __str__(self) -> str:
        """Строковое представление для отладки"""
        return f"{self.type.value}:{self.key}"
    
    def to_dict(self) -> Dict[str, str]:
        """Сериализация в словарь"""
        return {'type': self.type.value, 'key': self.key}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'PathSegment':
        """Десериализация из словаря"""
        return cls(
            type=SegmentType.from_string(data['type']),
            key=data['key']
        )


@dataclass
class MetaData:
    """
    Метаданные элемента с информацией о пути в исходной структуре.
    
    Attributes:
        path: Список сегментов пути
    """
    path: List[PathSegment] = field(default_factory=list)
    
    def get_path_string(self) -> str:
        """
        Возвращает строковое представление пути.
        
        Returns:
            Строка вида 'type1:key1/type2:key2/...'
        """
        if not self.path:
            return ''
        return '/'.join(str(seg) for seg in self.path)
    
    def get_last_segment(self) -> Optional[PathSegment]:
        """Возвращает последний сегмент пути"""
        return self.path[-1] if self.path else None
    
    def get_segments_by_type(self, type_filter: SegmentType) -> List[PathSegment]:
        """
        Возвращает сегменты указанного типа.
        
        Args:
            type_filter: Тип сегмента для поиска
            
        Returns:
            Список сегментов указанного типа
        """
        return [seg for seg in self.path if seg.type == type_filter]
    
    def get_segments_by_types(self, *type_filters: SegmentType) -> List[PathSegment]:
        """
        Возвращает сегменты любого из указанных типов.
        
        Args:
            *type_filters: Типы сегментов для поиска
            
        Returns:
            Список сегментов указанных типов
        """
        if not type_filters:
            return self.path.copy()
        return [seg for seg in self.path if seg.type in type_filters]
    
    def get_keys_by_type(self, type_filter: SegmentType) -> List[str]:
        """
        Возвращает ключи сегментов указанного типа.
        
        Args:
            type_filter: Тип сегмента для поиска
            
        Returns:
            Список ключей
        """
        return [seg.key for seg in self.path if seg.type == type_filter]
    
    def get_parent_path(self) -> str:
        """
        Возвращает путь к родительскому элементу.
        
        Returns:
            Строка пути без последнего сегмента
        """
        if len(self.path) <= 1:
            return ''
        return '/'.join(str(seg) for seg in self.path[:-1])
    
    def is_root(self) -> bool:
        """Проверяет, является ли элемент корневым"""
        return len(self.path) == 0
    
    def depth(self) -> int:
        """Возвращает глубину вложенности"""
        return len(self.path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'path': [seg.to_dict() for seg in self.path]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaData':
        """Десериализация из словаря"""
        path = [PathSegment.from_dict(p) for p in data.get('path', [])]
        return cls(path=path)
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение через строковое представление"""
        if not isinstance(other, MetaData):
            return False
        return self.get_path_string() == other.get_path_string()
    
    def __str__(self) -> str:
        return f"MetaData(path='{self.get_path_string()}')"
    
    def __repr__(self) -> str:
        return self.__str__()


# Константа для ключа метаданных в словарях
META_KEY = '__meta__'


__all__ = [
    'SegmentType',
    'MetaData',
    'PathSegment',
    'META_KEY'
]