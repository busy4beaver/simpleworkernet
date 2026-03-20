from ..base import BaseCategory, BaseModel, smart_model
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method
from ..primitives import vStr

class Billing(BaseCategory):
    """Биллинги"""

    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr

    @api_method(BaseModel)
    def get(self) -> ApiRetSData[BaseModel]:
        """Информация о биллингах

            Обязательные параметры:
                нет
        """
        ...
    
    # @api_method(None)
    # def refresh_date_update(self, *, id: int) -> ApiRet:
    #     """Обновление даты синхронизации данных с биллингом

    #         Обязательные параметры:
    #             id - ID биллинга
    #     """
    #     ...

