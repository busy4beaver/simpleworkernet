from typing import overload, List, Any
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Address(BaseCategory):
    """Действие с адресами"""

    @api_method(int)
    def add_locality_type(self, *, name: str, token: str) -> ApiRetSData[int]: 
        """Добавление типа адресной единицы

        Обязательные параметры:
            name - наименование
            token - токен
        """
        ...

    @api_method(bool)
    def edit_locality_type(self, *, id: int, name: str = None, token: str = None) -> ApiRetBool: 
        """Редактирование типа адресной единицы

        Обязательные параметры:
            id - id

        Необязательные параметры:
            name - наименование
            token - токен
        """
        ...

    @smart_model
    class Get_locality_type(BaseModel):
        id: int
        name: vStr
        token: vStr
        prefix: vStr
        postfix: vStr
        order: int

    @api_method(Get_locality_type)
    def get_locality_type(self, *, token: str = None) -> ApiRetSData[Get_locality_type]: 
        """Информация о типах адресных единиц

        Необязательные параметры:
            token - токен
        """
        ...

    @smart_model
    class Get_alias(BaseModel):
        id: int
        name: vStr
        token: vStr

    @api_method(Get_alias)
    def get_alias(self) -> ApiRetSData[Get_alias]:
        """Информация об алиасах"""
        ...

    @api_method(int)
    def add_address(self, *, locality_type_id: int, name: str, parent_id: int = None) -> ApiRetSData[int]: 
        """Добавление адресной единицы

            Обязательные параметры:
                locality_type_id - id типа адресной единицы
                name - название

            Необязательные параметры:
                parent_id - id родительской адресной единицы
        """
        ...

    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        full_name: vStr = None
        locality_type_id: int = None
        parent_id: int = None
        parent_ids: List[int] = None
        building_id: int = None
        additional_data: Any = None

    @overload
    def get(self, *, id: int, locality_type_id: int = None, parent_id: int = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get]: ...
    @overload
    def get(self, *, locality_type_id: int, id: int = None, parent_id: int = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get]: ...
    @overload
    def get(self, *, parent_id: int, id: int = None, locality_type_id: int = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get]: ...

    @api_method(Get)
    def get(self, *, id: int | str = None, locality_type_id: int | str = None, parent_id: int | str = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get]:
        """Информация об адресных единицах

            Обязательные параметры (должно быть хотя-бы одно):
                id - id объектов (можно через запятую)
                locality_type_id - тип объектов (можно через запятую)
                parent_id - id родительского объекта (можно через запятую)
            Необязательные параметры:
                is_disable_hidden - флаг - не отображать скрытые адресные единицы
        """
        ...

    @api_method(bool)
    def edit_address(self, *, id: int, map_color: str = None, parent_id: int = None) -> ApiRetBool: 
        """Редактирование адресной единицы

            Обязательные параметры:
                id - id объекта
            Необязательные параметры:
                map_color - HTML-цвет полигона на карте
                parent_id - id родительской адресной единицы
        """
        ...

    @api_method(int)
    def add_province(self, *, name: str) -> ApiRetSData[int]: 
        """Добавление области

            Обязательные параметры:
                name - Наименование
            Дополнительно возвращаемые данные:
                array(
                [Id] => ID добавленной области в случае успеха
                )
        """
        ...

    @api_method(int)
    def edit_province(self, *, id: int, name: str = None) -> ApiRetSData[int]: 
        """Редактирование области

            Обязательные параметры:
                id - ID области
            Необязательные параметры:
                Перечень параметров используется аналогично методу add_province
        """
        ...

    @api_method(int)
    def del_province(self, *, id: int) -> ApiRetSData[int]: 
        """Удаление области

            Обязательные параметры:
                id - ID области
        """
        ...

    @smart_model
    class Get_province(BaseModel):
        id: int
        name: vStr
        parent_ids: List[int] = None
        parent_id: int = None

    @api_method(Get_province)
    def get_province(self, *, id: int | str) -> ApiRetSData[Get_province]: 
        """Список областей

            Необязательные параметры:
                id - ID областей (можно через запятую)
            Дополнительно возвращаемые данные:
                array(
                [data] => Данные об объектах
                )
        """
        ...

    @api_method(int)
    def add_district(self, *, name: str) -> ApiRetSData[int]: 
        """Добавление района

            Обязательные параметры:
                name - наименование
        """
        ...

    @api_method(int)
    def edit_district(self, *, id: int, name: str = None) -> ApiRetSData[int]: 
        """Редактирование района

            Обязательные параметры:
                id - id района
            Необязательные параметры:
                Перечень параметров используется аналогично методу add_province
        """
        ...

    @api_method(int)
    def del_district(self, *, id: int) -> ApiRetSData[int]: 
        """Удаление района

            Обязательные параметры:
                id - id района
        """
        ...

    @smart_model
    class Get_district(BaseModel):
        id: int
        name: vStr
        parent_ids: List[int] = None
        parent_id: int = None
    
    @api_method(Get_district)
    def get_district(self, *, id: int | str) -> ApiRetSData[Get_district]: 
        """Список районов

            Необязательные параметры:
                id - id районов (можно через запятую)
        """
        ...

    @api_method(int)
    def add_city(self, name: str, *, province_id: int = None, district_id: int = None) -> ApiRetSData[int]:
        """Добавление населенного пункта

            Обязательные параметры:
                name - Наименование населенного пункта
            Необязательные параметры:
                province_id - ID области
                district_id - ID района в области
            Дополнительно возвращаемые данные:
                array(
                [Id] => ID добавленного населенного пункта в случае успеха
                )
        """
        ...

    @smart_model
    class Get_city(BaseModel):
        @smart_model
        class Coordinates(BaseModel):
            type: vStr
            coordinates: List[GeoPoint]
        id: int
        name: vStr
        parent_ids: List[int]
        parent_id: int
        coordinates: Coordinates

    @api_method(Get_city)
    def get_city(self, *, id: int | str = None, province_id: int | str = None, district_id: int | str = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get_city]: 
        """Список населённых пунктов

            Необязательные параметры:
                id - id населённого пункта (можно через запятую)
                district_id - id района (можно через запятую)
                province_id - id области (можно через запятую)
                is_disable_hidden - флаг - не отображать скрытые населенные пункты
        """
        ...

    @api_method(int)
    def edit_city(self, *, id: int, name: str = None, province_id: int | str = None, district_id: int | str = None) -> ApiRetSData[int]: 
        """Редактирование населённого пункта

            Обязательные параметры:
                id - ID населённого пункта
            Необязательные параметры:
                district_id - id района (можно через запятую)
                province_id - id области (можно через запятую)
        """
        ...

    @api_method(int)
    def del_city(self, *, id: int) -> ApiRetSData[int]:
        """Удаление населённого пункта

            Обязательные параметры:
                id - ID населённого пункта
        """
        ...
    
    @api_method(int)
    def add_area(self, *, city_id: int, name: str) -> ApiRetSData[int]:
        """Добавление района в населённом пункте

            Обязательные параметры:
                city_id - ID населенного пункта
                name - Наименование
            Дополнительно возвращаемые данные:
                array(
                [Id] => ID добавленного района в случае успеха
                )
        """
        ...

    @smart_model
    class Get_area(BaseModel):
        id: int
        name: vStr
        parent_ids: List[int]
        parent_id: int

    @api_method(Get_area)
    def get_area(self, *, id: int | str = None, city_id: int | str = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get_area]: 
        """Список районов населённых пунктов

            Необязательные параметры:
                id - ID районов (можно через запятую)
                city_id - ID городов (можно через запятую)
                is_disable_hidden - флаг - не отображать скрытые районы
        """
        ...
    
    @api_method(int)
    def edit_area(self, *, id: int, city_id: int = None, name: str = None) -> ApiRetSData[int]:
        """Редактирование района населённого пункта

            Обязательные параметры:
                id - ID района населённого пункта
            Необязательные параметры:
                Перечень параметров используется аналогично методу add_area
        """
        ...

    @api_method(int)
    def del_area(self, *, id: int) -> ApiRetSData[int]:
        """Удаление района населённого пункта

            Обязательные параметры:
                id - ID района населённого пункта
        """
        ...

    @api_method(int)
    def add_street(self, *, city_id: int, name: str, area_id: int = None) -> ApiRetSData[int]:
        """Добавление улицы

            Обязательные параметры:
                city_id - ID населенного пункта
                name - Наименование
            Необязательные параметры:
                area_id - ID района населенного пункта
            Дополнительно возвращаемые данные:
                array(
                [Id] => ID добавленной улицы в случае успеха
                )
        """
        ...

    @smart_model
    class Get_street(BaseModel):
        id: int
        name: vStr
        parent_ids: List[int]
        parent_id: int

    @api_method(Get_street)
    def get_street(self, *, id: int | str = None, city_id: int | str = None, area_id: int | str = None, is_disable_hidden: vFlag = None) -> ApiRetSData[Get_street]: 
        """Список улиц

            Необязательные параметры:
                id - ID улиц (можно через запятую)
                city_id - ID населённых пунктов (можно через запятую)
                area_id - ID районов населенных пунктов (можно через запятую)
                is_disable_hidden - флаг - не отображать скрытые улицы
        """
        ...

    @api_method(int)
    def edit_street(self, *, id: int, city_id: int = None, name: str = None, area_id: int = None) -> ApiRetSData[int]: 
        """Редактирование улицы

            Обязательные параметры:
                id - ID улицы
            Необязательные параметры:
                Перечень параметров используется аналогично методу add_street
        """
        ...

    @api_method(int)
    def del_street(self, id: int) -> ApiRetSData[int]: 
        """Удаление улицы

            Обязательные параметры:
                id - ID улицы
        """
        ...

    @api_method(int)
    def add_house(self, *, city_id: int, street_id: int, number: str, area_id: int = None, apart_count: int = None, comment: str = None, entrance_count: int = None, level_count: int = None, task_comment: str = None, type_id: int = None) -> ApiRetSData[int]: 
        """Добавление здания

            Обязательные параметры:
                city_id - id населенного пункта
                street_id - id улицы
                number - номер здания
            Необязательные параметры:
                area_id - id района в населенному пункте
                apart_count - количество домохозяйств в здании
                comment - заметки 
                entrance_count - количество входов/подъездов в здании
                level_count - количество этажей в здании
                task_comment - рабочая заметка по зданию
                type_id - id типа здания
        """
        ...

    @api_method(bool)
    def add_house_mark(self, *, house_id: int, mark_id: int) -> ApiRetBool:
        """Добавление метки на доме

            Обязательные параметры:
                house_id - ID дома
                mark_id - ID метки
        """
        ...

    @api_method(int)
    def del_house(self, *, id: int) -> ApiRetSData[int]: 
        """Удаление дома

            Обязательные параметры:
                id - ID дома
        """
        ...

    @api_method(bool)
    def delete_house_mark(self, *, house_id: int, mark_id: int) -> ApiRetBool: 
        """Снятие метки с дома

            Обязательные параметры:
                house_id - ID дома
                mark_id - ID метки
        """
        ...

    @api_method(bool)
    def edit_building_coord(self, *, id: int, coord: GeoPoint | str) -> ApiRetBool: 
        """Изменение географических координат у здания/сооружения

            Обязательные параметры:
                id - id здания
                coord - координаты вершин полигона здания
        """
        return {'id':id,'coord':str(coord)}

    @smart_model
    class Get_building_structure(BaseModel):
        @smart_model
        class Structure(BaseModel):
            level_id: int
            entrance_id: int
            position: int
            caption: Any
        entrance_count: int
        level_count: int
        structure: Structure

    @api_method(Get_building_structure)
    def get_building_structure(self, *, id: int) -> ApiRetSData[Get_building_structure]:
        """Просмотр структуры здания

            Обязательные параметры:
                id - id здания
        """
        ...

    @api_method(bool)
    def edit_building_structure(self, *, id: int, level_list: str = None) -> ApiRetBool: 
        """Редактирование структуры здания

            Обязательные параметры:
                id - id здания
            Необязательные параметры:
                level_list - список типов уровней (этажей) через запятую
        """
        ...

    @overload
    def edit_house(self, *, id: int, area_id: int = None, apart_count: int = None, city_id: int = None, comment: str = None, entrance_count: int = None, \
        is_not_connected: vFlag = None, level_count: int = None, number: str = None, street_id: int = None, task_comment: int = None, task_interval: str = None, type_id: int = None): ...
    @overload
    def edit_house(self, *, building_id: int, area_id: int = None, apart_count: int = None, city_id: int = None, comment: str = None, entrance_count: int = None, \
        is_not_connected: vFlag = None, level_count: int = None, number: str = None, street_id: int = None, task_comment: str = None, task_interval: str = None, type_id: int = None): ...

    @api_method(int)
    def edit_house(self, *, id: int = None, building_id: int = None, area_id: int = None, apart_count: int = None, city_id: int = None, comment: str = None, entrance_count: int = None, \
        is_not_connected: vFlag = None, level_count: int = None, number: str = None, street_id: int = None, task_comment: str = None, task_interval: str = None, type_id: int=None) -> ApiRetSData[int]:
        """Редактирование здания

            Обязательные параметры:
                id - id адресной единицы
                или
                building_id - id здания
            Необязательные параметры:
                area_id - id района в населенному пункте
                apart_count - количество домохозяйств в здании
                city_id - id населенного пункта
                comment - заметки
                entrance_count - количество входов/подъездов в здании
                is_not_connected - флаг - здание не подключено
                level_count - количество этажей в здании
                number - номер здания
                street_id - id улицы
                task_comment - рабочая заметка по зданию
                task_interval - возможные интервалы времени для проведения работ (например: {"day":[[0,23],[0,23],[0,23],[0,23],[0,23],[0,23],[0,23]]})
                type_id - id типа здания
        """
        ...

    @smart_model
    class Get_house(BaseModel):
        id: int
        name: vStr
        building_id: int
        type_id: int
        floor: int
        parent_id: int
        parent_ids: List[int]
        entrance: int
        apart: Any
        full_name: vStr
        comment: vStr
        task_comment: vStr
        coordinates: GeoPoint
        is_not_use: int
        is_show_on_map: bool
        manager_employee_id: int
        additional_data: List
        owners: List
        mark: List
        taskInterval: List

    @api_method(Get_house)
    def get_house(self, *, id: int | str = None, building_id: int | str = None, area_id: int | str = None, city_id: int | str = None, street_id: int | str = None, is_disable_hidden: vFlag = None, \
        mark_id: int = None, name: str = None, limit: int = None, is_like: vFlag = None) -> ApiRetSData[Get_house]:
        """Список домов

            Обязательные параметры:
                нет
            Необязательные параметры:
                id - id адресной единицы (Можно через запятую)
                building_id - id здания (Можно через запятую)
                city_id - ID населённых пунктов (можно через запятую)
                area_id - ID районов населённых пунктов (можно через запятую)
                street_id - ID улиц (можно через запятую)
                is_disable_hidden - флаг - не отображать скрытые дома
                mark_id - id метки
                name - полный адрес здания (согласно шаблона)
                limit - максимальное количество записей, что вернуть в ответе
                is_like - флаг - использовать сравнение подстроки там где это возможно (а не полное совпадение)
        """
        ...

    # @api_method()
    # def get_building_type(self): 
    #     """Справочник типов зданий
    #         Обязательные параметры:
    #             нет
    #     """
    #     ...

    @smart_model
    class Get_level(BaseModel):
        id: int
        name: vStr
        position: int
        is_default: int
        color: str

    @api_method(Get_level)
    def get_level(self) -> ApiRetSData[Get_level]:
        """Справочник типов уровней (этажей)

            Обязательные параметры:
                нет
        """
        ...

    @api_method(bool)
    def move_child_object(self, *, src_building_id: int, dst_building_id: int) -> ApiRetBool: 
        """Перенос дочерних объектов с здания на другое здание

            Обязательные параметры:
                src_building_id - id исходного здания
                dst_building_id - id здания-получателя
        """
        ...
