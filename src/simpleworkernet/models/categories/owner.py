from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Owner(BaseCategory):
    """Действие с собственниками объектов"""
    
    @api_method(int)
    def add(self, *, name: str, comment: str = None, cost: int = None) -> ApiRetSData[int]:
        """Добавление 

            Обязательные параметры:
                name - наименование
            Дополнительные параметры:
                comment - заметки
                cost - размер оплаты собственнику
        """
        ...

    @api_method(bool)
    def bind_building(self, *, owner_id: int, building_id: int) -> ApiRetBool:
        """Указание собственника для здания

            Обязательные параметры:
                owner_id - id собственника
                building_id - id здания
        """
        ...
    
    @api_method(bool)
    def bind_fiber(self, *, owner_id: int, fiber_id: int) -> ApiRetBool:
        """Указание собственника для ВОЛС

            Обязательные параметры:
                owner_id - id собственника
                fiber_id - id ВОЛС
        """
        ...
    
    @api_method(bool)
    def bind_node(self, *, owner_id: int, node_id: int) -> ApiRetBool:
        """Указание собственника для объекта инфраструктуры

            Обязательные параметры:
                owner_id - id собственника
                node_id - id объекта инфраструктуры
        """
        ...
    
    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление объекта

            Обязательные параметры:
                id - id объекта
        """
        ...
    
    @api_method()
    def edit(self, *, id: int, name: str = None, comment: str = None, cost: int = None):
        """Редактирование объекта

            Обязательные параметры:
                id - id объекта
            Дополнительные параметры:
                name - наименование
                comment - заметки
                cost - размер оплаты собственнику
        """
        ...
    
    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        address: Any
        director: Any
        phone: Any
        requisites: Any
        @smart_model
        class Agreement(BaseModel):
            number: vStr
            date: vStr
        agreement: Agreement
        @smart_model
        class Object(BaseModel):
            node: List[int]
            fiber: List[int]
            rack: List[int]
            @smart_model
            class Building(BaseModel):
                value: vStr
                building_id = CollapsedField()
            building: List[Building]
        object: Object

    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список объектов

            Необязательные параметры:
                id - перечень id объектов (через запятую)
        """
        ...
    
    @api_method(bool)
    def unbind_building(self, *, owner_id: int, building_id: int) -> ApiRetBool:
        """Исключение собственника у здания

            Обязательные параметры:
                owner_id - id собственника
                building_id - id здания
        """
        ...
    
    @api_method(bool)
    def unbind_fiber(self, *, fiber_id: int) -> ApiRetBool:
        """Исключение собственника у ВОЛС

            Обязательные параметры:
                fiber_id - id ВОЛС
        """
        ...

    @api_method(bool)
    def unbind_node(self, *, node_id : int) -> ApiRetBool:
        """Исключение собственника у объекта инфраструктуры

            Обязательные параметры:
                node_id - id объекта инфраструктуры
        """
        ...
    