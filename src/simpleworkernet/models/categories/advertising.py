from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Advertising(BaseCategory):
    """Рекламные кампании"""

    link_cat = 'advert'

    @api_method(bool)
    def add_customer(self, *, advert_id: int, customer_id: int) -> ApiRetBool: 
        """Добавление рекламной кампании абоненту

            Обязательные параметры:
                advert_id - id рекламной кампании
                customer_id - id абонента
        """
        ...

    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        date_start: vStr
        date_finish: vStr

    @api_method(Get)
    def get(self, *, id: int | str =None) -> ApiRetSData[Get]: 
        """Список рекламных кампаний

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id кампаний (можно через запятую)
        """
        ...
    
    @api_method(bool)
    def remove_customer(self, *, advert_id, customer_id) -> ApiRetBool: 
        """Исключение абонента из рекламной кампании

            Обязательные параметры:
                advert_id - id рекламной кампании
                customer_id - id абонента
        """
        ...
