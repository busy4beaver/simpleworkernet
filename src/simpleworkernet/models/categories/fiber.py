import json
from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Fiber(BaseCategory):
    """Кабельные линии"""

    @overload
    def add(self, *, 
            object_a_id: int, 
            object_b_id: int, 
            building_date: str = None,
            building_length: int = None,
            cableline_type_id: int = None,
            cabletype_id: int = None,
            comment: str = None,
            custom_color: str = None,
            fibers_count: int = None,
            is_planned: vFlag = None,
            is_change_color_by_cabletype: vFlag = None,
            marking_a: str = None,
            marking_b: str = None,
            optical_length: int = None): ...
    @overload
    def add(self, *, 
            object_a_id: int, 
            house_b_id: int, 
            building_date: str = None,
            building_length: int = None,
            cableline_type_id: int = None,
            cabletype_id: int = None,
            comment: str = None,
            custom_color: str = None,
            fibers_count: int = None,
            is_planned: vFlag = None,
            is_change_color_by_cabletype: vFlag = None,
            marking_a: str = None,
            marking_b: str = None,
            optical_length: int = None): ...

    @api_method(int)
    def add(self, *, 
            object_a_id: int, 
            object_b_id: int = None, 
            house_b_id: int = None, 
            building_date: str = None,
            building_length: int = None,
            cableline_type_id: int = None,
            cabletype_id: int = None,
            comment: str = None,
            custom_color: str = None,
            fibers_count: int = None,
            is_planned: vFlag = None,
            is_change_color_by_cabletype: vFlag = None,
            marking_a: str = None,
            marking_b: str = None,
            optical_length: int = None) -> ApiRetSData[int]:
        """Добавление линии

            Обязательные параметры:
                object_a_id - ID начального объекта
                object_b_id - ID конечного объекта (либо house_b_id - ID конечного здания)
            Дополнительные параметры:
                building_date - Дата прокладки
                building_length - строительная длина
                cableline_type_id - ID типа кабельной линии
                cabletype_id - ID типа кабеля
                comment - Заметки
                custom_color - Собственный цвет для линии
                customer_b_id - ID конечного абонента
                fibers_count - количество ОВ
                house_b_id - ID конечного здания
                is_planned - Флаг - объект только запланирован
                is_change_color_by_cabletype - Флаг - Изменить цвета ОВ согласно свойств типа кабеля
                marking_a - Маркировка линии на стороне А
                marking_b - Маркировка линии на стороне Б
                object_a_id - ID начального объекта
                object_b_id - ID конечного объекта
                optical_length - оптическая длина
        """
        ...

    @api_method(bool)
    def add_mark(self, *, fiber_id: int, mark_id: int) -> ApiRetBool:
        """Добавление метки

            Обязательные параметры:
                fiber_id - id линии
                mark_id - id метки
        """
        ...
    
    @api_method(bool)
    def add_route_object(self, *, id: int, object_id: int, reserve: int = None) -> ApiRetBool:
        """Добавление объекта на маршрут линии

            Обязательные параметры:
                id - id линии
                object_id - id объекта
            Необязательные параметры:
                reserve - запас кабеля (в метрах)
        """
        ...
        
    @api_method(int)
    def catalog_cables_add(self, *, cable_line_type_id: int, brand: str, name: str, core_count: int) -> ApiRetSData[int]:
        """Добавление записи в каталог кабелей

            Обязательные параметры:
                cable_line_type_id - id типа кабельной линии
                brand - наименование производителя
                name - марка кабеля
                core_count - количество проводников (волокон/жил)
        """
        ...
    
    @smart_model
    class Catalog_cables_get(BaseModel):
        id: int
        cable_line_type_id: int
        brand: vStr
        model: vStr
        fiber_count: int

    @api_method(Catalog_cables_get)
    def catalog_cables_get(self, *, cable_line_type_id: int = None) -> ApiRetSData[Catalog_cables_get]:
        """Каталог кабелей

            Необязательные параметры:
                cable_line_type_id - id типа кабельной линии
        """
        ...
    @smart_model
    class Catalog_types_get(BaseModel):
        id: int
        name: vStr
    
    @api_method(Catalog_types_get)
    def catalog_types_get(self) -> ApiRetSData[Catalog_types_get]:
        """Каталог типов кабельных линий"""
        ...
    
    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление кабельной линии

            Обязательные параметры:
                id - id объекта
        """
        ...

    @api_method(bool)
    def delete_mark(self, *, fiber_id: int, mark_id: int) -> ApiRetBool:
        """Снятие метки

            Обязательные параметры:
                fiber_id - id линии
                mark_id - id метки
        """
        ...
    
    @api_method(bool)
    def edit(self, *, 
            id: int, 
            object_a_id: int = None, 
            object_b_id: int = None, 
            house_b_id: int = None, 
            building_date: str = None,
            building_length: int = None,
            cabletype_id: int = None,
            comment: str = None,
            custom_color: str = None,
            fibers_count: int = None,
            is_planned: vFlag = None,
            is_change_color_by_cabletype: vFlag = None,
            marking_a: str = None,
            marking_b: str = None,
            optical_length: int = None) -> ApiRetBool:
        """Редактирование линии

            Обязательные параметры:
                id - id линии
            Необязательные параметры:
                object_a_id - id начального объекта
                object_b_id - id конечного объекта 
                house_b_id - id конечного дома
                building_date - дата прокладки
                building_length - строительная длина
                cabletype_id - id типа кабеля
                comment - заметки
                custom_color - собственный цвет для линии
                fibers_count - количество ОВ
                is_planned - флаг - объект только запланирован
                is_change_color_by_cabletype - флаг - Изменить цвета ОВ согласно свойств типа кабеля
                marking_a - маркировка линии на стороне А
                marking_b - маркировка линии на стороне Б
                optical_length - оптическая длина
        """
        ...

    @smart_model
    class Get_fiber(BaseModel):
        id: int
        fiber_id: int 
        number: int
        color_id: int
        module_color_id: int
        att: Any
        mark_a: vStr
        mark_b: vStr

    @api_method(Get_fiber)
    def get_fiber(self, *, fiber_id: int = None, id: int = None) -> ApiRetSData[Get_fiber]:
        """Список волокон

            Обязательные параметры:
                нет
            Дополнительные параметры:
                fiber_id - id кабельной линии (можно через запятую)
                id - id волокна (можно через запятую)
        """
        ...

    @api_method(int)
    def get_geo_length(self, *, id: int) -> ApiRetSData[int]: 
        """Расчёт длины линии согласно географических координат конечных точек (приблизительный расчёт)

            Обязательные параметры:
                id - id линии
        """
        ...

    @smart_model
    class Get_list(BaseModel):
        @smart_model
        class Properties(BaseModel):
            module_custom_label: dict
            coordinates_on_scheme: dict
        @smart_model
        class Fibers(BaseModel):
            @smart_model
            class Color(BaseModel):
                name: vStr
                htmlCode: vStr
                tag_count: int | None
                tag_color: vStr | None
            number: int
            id: int
            moduleColor: Color
            color: Color
        code: int
        comment: vStr
        port: int
        dateadd: vStr
        node1_id: int
        node2_id: int
        node1_rotation: int
        node1_position: int
        node2_rotation: int
        node2_position: int
        properties: Properties
        ishide: int
        cablecode: int
        color: Any
        isplan: int
        marking1: Any
        marking2: Any
        building2_id: int | None
        owner_id: int | None
        cable_line_type_id: int
        opticalen: int
        opticalen2: int
        start_point_name: vStr
        finish_port_name: vStr
        object_a_name: vStr
        object_b_name: vStr
        object_a_id: int
        object_a_type: int
        layers: List[int]
        object_b_id: int
        object_b_type: int
        path: List[GeoPoint]
        fibers: List[Fibers]

    @api_method(Get_list)
    def get_list(self, *, cable_line_type_id: int = None, mark_id: int = None, node_id = None, object_id: int = None) -> ApiRetSData[Get_list]:
        """Список линий

            Обязательные параметры:
                нет
            Необязательные параметры:
                cable_line_type_id - id типа кабельной линии
                mark_id - id метки
                node_id - id объекта размещения (можно через запятую)
                object_id - id конкретной линии
        """
        ...

    @smart_model
    class Map_color_get(BaseModel):
        fiber_count:int
        htmlColor:vStr
    
    @api_method(Map_color_get)
    def map_color_get(self) -> ApiRetSData[Map_color_get]:
        """Цвета кабелей на карте"""
        ...
    
    @api_method(bool)
    def remove_route_object(self, *, id: int, object_id: int = None) -> ApiRetBool:
        """Исключение объектов на маршруте линии

            Обязательные параметры:
                id - id линии
            Необязательные параметры:
                object_id - id объекта
        """
        ...
        
    @api_method(int)
    def set_geo_route(self, *, id: int, route: List[GeoPoint] | Any) -> ApiRetSData[int]:
        """Описание: Установка географического маршрута линии

            Обязательные параметры:
                id - id линии
                route - массив географических точек (lat,lon) маршрута линии в формате json
        """
        if isinstance(route,list) and all(isinstance(item, GeoPoint) for item in route):
            path = {}
            for i, pt in enumerate(route, start=1):
                path[f'pt{i}'] = {"lat": pt.lat, "lon": pt.lon}
            return {'id':id,'route':json.dumps(path)}
        return {'id':id,'route':route}
