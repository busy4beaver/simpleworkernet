# simpleworkernet/smartdata/__init__.py
"""
SmartData - интеллектуальный контейнер для обработки сложных JSON-структур
"""

from .core import SmartData
from .metadata import MetaData, PathSegment, META_KEY, SegmentType
from .processor import DataProcessor
from . import helpers

__all__ = [
    'SmartData',
    'MetaData',
    'PathSegment',
    'META_KEY',
    'SegmentType',
    'DataProcessor',
    'helpers',
]