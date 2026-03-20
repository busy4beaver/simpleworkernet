# simpleworkernet/models/operators.py
import re
from typing import Any, Union
from enum import StrEnum


class Operator(StrEnum):
    """Операторы сравнения"""
    EQ = '=='
    """Равно: =="""
    NE = '!='
    """Не равно: !="""
    GT = '>'
    """Больше: >"""
    LT = '<'
    """Меньше: <"""
    GTE = '>='
    """Больше или равно: >="""
    LTE = '<='
    """Меньше или равно: <="""
    LIKE = 'LIKE'
    """Частичное совпадение"""
    IN = 'IN'
    """Вхождение в список"""
    BETWEEN = 'BETWEEN'
    """проверка диапазона [min, max], включая значения min,max - в любом порядке"""
    REGEX = 'REGEX'
    """поиск по регулярному выражению"""


class Where:
    """Поиск по условиям"""

    def __init__(self, key: str, value: Any, op: Operator = Operator.EQ):
        self.key = key
        self.value = value
        self.op = op

    def check(self, item: Any) -> bool:
        """
        Проверяет, соответствует ли элемент условию.
        
        Args:
            item: Элемент для проверки (словарь или объект)
            
        Returns:
            True если условие выполняется
        """
        # Извлекаем значение (атрибут или ключ словаря)
        if hasattr(item, self.key):
            target = getattr(item, self.key)
        elif isinstance(item, dict):
            target = item.get(self.key)
        else:
            target = None

        # Вспомогательная функция для сравнения с приведением типов
        def compare(v1, v2, op_override=None):
            operation = op_override or self.op
            try:
                if operation == Operator.EQ:
                    return v1 == v2
                if operation == Operator.NE:
                    return v1 != v2
                if operation == Operator.GT:
                    return v1 > v2
                if operation == Operator.LT:
                    return v1 < v2
                if operation == Operator.GTE:
                    return v1 >= v2
                if operation == Operator.LTE:
                    return v1 <= v2
                return False
            except TypeError:
                try:
                    # Пробуем привести v2 к типу v1 и повторить
                    return compare(v1, type(v1)(v2), op_override=operation)
                except:
                    return False

        if self.op == Operator.LIKE:
            return str(self.value).lower() in str(target).lower()
        
        if self.op == Operator.IN:
            return target in self.value
        
        if self.op == Operator.REGEX:
            return bool(re.search(str(self.value), str(target)))
        
        if self.op == Operator.BETWEEN:
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                return False
            # Возвращаем True, если target >= v_min И target <= v_max
            v_min, v_max = sorted(map(float, self.value))
            return compare(target, v_min, Operator.GTE) and compare(target, v_max, Operator.LTE)
        
        return compare(target, self.value)