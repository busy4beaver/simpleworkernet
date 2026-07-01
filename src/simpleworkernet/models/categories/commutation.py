from typing import overload, List, Any, Literal
from ..base import BaseCategory, BaseModel, CollapsedField, SegmentType, smart_model
from ..primitives import vStr, vFlag
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Commutation(BaseCategory):
    """Коммутация объектов"""

    @api_method(int)
    def add(self, *, object_type: Literal['customer','switch','fiber','cross','splitter'], object_id: int, object1_side: int, object1_port: int, \
            object2_type: Literal['switch','fiber','cross','splitter'], object2_id:int , object2_side: int, object2_port: int) -> ApiRetSData[int]:
        """Коммутация объектов

            Обязательные параметры:
                object_type - тип объекта [customer|switch|fiber|cross|splitter]
                object_id - id/uuid объекта
                object1_side - сторона объекта 1 (для кабельных линий)
                object1_port - порт объекта 1
                object2_type - тип объекта 2 [switch|fiber|cross|splitter]
                object2_id - id/uuid объекта 2
                object2_side - сторона объекта 2 (для кабельных линий)
                object2_port - порт объекта 2
        """
        ...

    @api_method(bool)
    def delete(self, *, object_type: Literal['customer','device'], object_id: int, object_port: int = None) -> ApiRetBool:
        """Очистка коммутации

            Обязательные параметры:
                object_type - Тип объекта [customer|device]
                object_id - id объекта
            Небязательные параметры:
                object_port - Номер порта (для device)
        """
        ...

    @smart_model
    class Get_data(BaseModel):
        object_type: vStr
        object_id: int
        object_uuid: vStr | None
        direction: int
        interface: int
        comment: vStr
        connect_id: int
        
        length_by_cable: int = None
        length_by_fiber: int = None
        is_geo_length: int = None

        clps_first: CollapsedField = CollapsedField(pos=0)
        clps_mid: CollapsedField = CollapsedField(pos=1)
        clps_last: CollapsedField = CollapsedField()

    @api_method(Get_data)
    def get_data(self, *, object_type: Literal['customer','switch','radio','cross','fiber','splitter'], object_id: int = None, is_finish_data: vFlag = None) -> ApiRetSData[Get_data]:
        """Получение массива коммутации

            Обязательные параметры:
                object_type - Тип объекта для выборки [customer|switch|radio|cross|fiber|splitter]
            Необязательные параметры:
                object_id - id объекта для выборки
                is_finish_data - Флаг - выводить конечную точку коммутации
            Дополнительно возвращаемые данные:
                array(
                [data] = array(
                    [object_type] => Тип объекта
                    [object_id] => id объекта
                    [direction] => Сторона коммутации (например для ВОЛС)
                    [interface] => Номер интерфейса
                    [comment] => Заметки
                    [connect_id] => id записи о коммутации
                )
        """
        ...
