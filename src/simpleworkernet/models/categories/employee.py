from typing import overload, List, Any, Literal, Annotated
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Employee(BaseCategory):
    """Сотрудники"""

    link_cat = 'employee'

    @api_method(bool)
    def add_notification(self, *, employee_id: int, body: str, color: str = None) -> ApiRetBool: 
        """Создание PUSH-уведомления для сотрудника

            Обязательные параметры:
                employee_id - ID сотрудника
                body - текст
            Необязательные параметры:
                color - HTML-цвет окна с уведомлением
        """
        ...
    
    @api_method(bool)
    def address_access_add(self, *, employee_id: int, address_id: int, is_write: vFlag) -> ApiRetBool:
        """Добавление адресного объекта в доступные адреса для сотрудника

            Обязательные параметры:
                employee_id - id сотрудника
                address_id - id адресного объекта (-1 для всех адресов, -2 для объектов без адреса)
                is_write - флаг - доступ на запись
        """
        ...
    
    @api_method(int)
    def address_access_list(self, *, employee_id: int, is_write: vFlag) -> ApiRetSData[int]:
        """Список доступных адресных объектов для сотрудника

            Обязательные параметры:
                employee_id - id сотрудника
                is_write - флаг - доступ на запись
        """
    ...
    
    @api_method(bool)
    def address_access_remove(self, *, employee_id: int, address_id: int) -> ApiRetBool:
        """Удаление адресного объекта из доступных адресов для сотрудника

            Обязательные параметры:
                employee_id - id сотрудника
                address_id - id адресного объекта (-1 для всех адресов, -2 для объектов без адреса)
        """
        ...
    
    @api_method(bool)
    def check_pass(self, *, login: str, passwd: str) -> ApiRetBool:
        """Проверка совпадения логина и пароля на вход в WorkerNet

            Обязательные параметры:
                login - логин
                pass - пароль
        """
        return {'login':login,'pass':passwd}
    
    # @api_method()
    # def division_employee_add(self, *, division_id: int, employee_id: int, position_type: Literal['head','deputy','worker'] = None, position_name: str = None, date_add: str = None):
    #     """Назначение сотрудника в подразделение

    #         Обязательные параметры:
    #             division_id - ID подразделения
    #             employee_id - ID сотрудника
    #         Необязательные параметры:
    #             position_type - тип должности [head|deputy|worker]
    #             position_name - должность в подразделении
    #             date_add - дата назначения
    #     """
    #     ...

    # @api_method()
    # def division_employee_remove(self, *, division_id: int, employee_id: int, date_remove: str = None):
    #     """Исключение сотрудника из подразделения

    #         Обязательные параметры:
    #             division_id - ID подразделения
    #             employee_id - ID сотрудника
    #         Необязательные параметры:
    #             date_remove - дата исключения
    #     """
    #     ...

    @api_method(bool)
    def edit(self, *, 
            id: int, 
            date_birthday: str = None, 
            date_in: str = None, 
            date_out: str = None, 
            first_name: str = None, 
            gps_id: str = None, 
            ip_phone: str = None, 
            is_blocked: vFlag = None, 
            middle_name: str = None, 
            last_name: str = None, 
            position: str = None, 
            short_name: str = None, 
            messenger_chat_id: str = None) -> ApiRetBool:
        """Редактирование записи о сотруднике

            Обязательные параметры:
                id - id сотрудника
            Необязательные параметры:
                date_birthday - дата рождения
                date_in - дата принятия на работу
                date_out - дата увольнения
                first_name - имя
                gps_id - IMEI gps-треккера
                ip_phone - номер IP-телефона
                is_blocked - флаг - заблокировать/разблокировать учётную запись
                middle_name - отчество
                last_name - фамилия
                position - должность
                short_name - сокращенное имя/фамилия
                messenger_chat_id - telegram/messenger chat_id
        """
        ...
    

    @smart_model
    class Get_data(BaseModel):
        @smart_model
        class Division(BaseModel):
            division_id: int
            position: vStr
            date_add: vStr
            date_out: vStr | None
            is_work: int
        id: int
        name: vStr
        position: vStr
        gps_imei: Any
        image_uuid: vStr
        is_work: int
        division: List[Division | None]
        login: vStr
        short_name: vStr
        date_birthday: vStr
        is_blocked: int
        profile_id: int
        last_activity_time: vStr
        asterisk_phone: vStr
        email: vStr
        phone: vStr
        messenger_chat_id: vStr
        rights: List[int]
        access_address_id: List[int]
        task_allow_assign_address_id: List[int]
        additional_data: Any

    @api_method(Get_data)
    def get_data(self, *, id: int | str = None) -> ApiRetSData[Get_data]: 
        """Получение информации о сотруднике

            Необязательные параметры:
                id - id сотрудника для выборки (можно через запятую)
        """
        ...

    @smart_model
    class Get_division(BaseModel):
        @smart_model
        class Staff(BaseModel):
            @smart_model
            class Employee(BaseModel):
                employee_id: int
                position: vStr
                date_add: vStr
                position_type: vStr
                date_out: vStr
            work: List[Employee]
            ex: List[Employee]
        id: int
        name: vStr
        parent_id: int
        comment: vStr
        date_add: vStr
        staff: List[Staff]

    @api_method(Get_division)
    def get_division(self, *, id: int | str = None) -> ApiRetSData[Get_division]:
        """Получение информации о подразделении

            Необязательные параметры:
                id - ID подразделения (можно через запятую)
        """
        ...
    
    @smart_model
    class Get_division_list(BaseModel):
        id: int
        name: vStr
        parent_id: int
        comment: vStr
        date_add: vStr
    
    @api_method(Get_division_list)
    def get_division_list(self) -> ApiRetSData[Get_division_list]:
        """Список подразделений"""
        ...
    
    class In_data_typer(StrEnum):
        name = 'name'
        login = 'login'
        messenger_chat_id = 'messenger_chat_id'
        additional_field_ = additional_field

    @api_method(int)
    def get_employee_id(self, *, data_typer: Literal['name','login','messenger_chat_id'] | Annotated[str, "pattern: additional_field_\\d+"] | In_data_typer, data_value: str) -> ApiRetSData[int]:
        """Получение ID сотрудника по входящим данным

            Обязательные параметры:
                data_typer - тип данных, которые проверяем (возможные значения: additional_field_XXX, name, login, messenger_chat_id)
                data_value - значение
        """
        ...
    
    @smart_model
    class Get_history(BaseModel):
        employee_id: int
        operator_ip: vStr
        date: vStr
        history_type_id: int
        object_type_id: int
        object_id: int
        description: vStr | None

    @api_method(Get_history)
    def get_history(self, *, date_from: str, date_to: str, employee_id: int | str = None, type_id: int | str = None, object_id: int | str = None) -> ApiRetSData[Get_history]:
        """История действий (лимит 10000 записей в результатах выборки)

            Обязательные параметры:
                date_from - дата начала выборки (с)
                date_to - дата окончания выборки (по)
            Необязательные параметры:
                employee_id - id сотрудника (можно через запятую) 
                type_id - id типа действий (можно через запятую)
                object_id - id связанного объекта (можно через запятую)
        """
        ...
    
    @smart_model
    class Get_history_type(BaseModel):
        id: int
        description: vStr

    @api_method(Get_history_type)
    def get_history_type(self, *, id: int = None) -> ApiRetSData[Get_history_type]:
        """Типы действий в истории

            Необязательные параметры:
                id - id типа действий
        """
        ...
    
    @smart_model
    class Get_timesheet_data(BaseModel):
        normal: vStr
        overtime: vStr
        emergency: vStr

    @api_method(Get_timesheet_data)
    def get_timesheet_data(self, *, date_from: str, date_to: str, employee_id: int | str = None, division_id: int | str = None) -> ApiRetSData[Get_timesheet_data]:
        """Получение информации из табеля работ

            Обязательные параметры:
                date_from - дата начала выборки
                date_to - дата окончания выборки
            Необязательные параметры:
                employee_id - id сотрудника (можно через запятую)
                division_id - id подразделения (можно через запятую)
        """
        ...
    
    @api_method()
    def get_work_time_data(self, *, date_from: str, date_to: str, employee_id: int | str = None):
        """Получение информации о рабочем времени сотрудников

            Обязательные параметры:
                date_from - дата начала выборки
                date_to - дата окончания выборки
            Необязательные параметры:
                employee_id - id сотрудника (можно через запятую)
        """
        ...

    @api_method()
    def get_unavailable_data(self, *, employee_id: int=None, date_from=None, date_to=None):
        """Получение информации о недоступности сотрудника (отпуск, больничный)

            Обязательные параметры:
                нет
            Необязательные параметры:
                employee_id - id сотрудника
                date_from - дата начала периода
                date_to - дата окончания периода
        """
        ...
    
    class In_timesheet_type_id(IntEnum):
        main_time = 1
        overtime = 2
        other = 3

    @api_method(bool)
    def set_timesheet_data(self, *, employee_id: int, date, type_id: int | In_timesheet_type_id, value: int | str | Any) -> ApiRetBool:
        """Добавление/изменение/удаление записи в табель работ

            Обязательные параметры:
                employee_id - id сотрудника
                date - дата
                type_id - id типа записи (1 - основное время, 2 - сверхурочное, 3 - прочее)
                value - количество часов (после 3.17dev1: количество часов или текстовая буква для отметки нерабочего периода, либо пустое значение для удаления записи; до 3.17dev1: целое значение, либо: 994 - дежурный, 995 - не вышел, 996 - отпуск, 997 - выходной, 998 - больничный, 999 - командировка, либо 0 для удаления записи)
        """
        ...
    
    class In_unavailable_type_id(StrEnum):
        vacation = '1'
        hospital = '2'
        delete_record = ''

    @api_method(bool)
    def set_unavailable_data(self, *, employee_id: int, date_from: str, date_to: str, type_id: int | str | In_unavailable_type_id = None) -> ApiRetBool:
        """Добавление/изменение/удаление записи о недоступности сотрудника (отпуск, больничный)

            Обязательные параметры:
                employee_id - ID сотрудника
                date_from - дата начала периода
                date_to - дата окончания периода
            Необязательные параметры:
                type_id - id типа записи (1 - отпуск, 2 - больничный, не заполнено - удалить запись)
        """
        ...
    
    @api_method(bool)
    def task_address_access_add(self, *, employee_id: int, address_id: int) -> ApiRetBool:
        """Добавление адресного объекта в список адресов, куда может быть назначен сотрудник на работы

            Обязательные параметры:
                employee_id - id сотрудника
                address_id - id адресного объекта (-1 для всех адресов, -2 для объектов без адреса)
        """
        ...
    
    @api_method(int)
    def task_address_access_list(self, *, employee_id: int) -> ApiRetSData[int]:
        """Список адресов, куда может быть назначен сотрудник на работы

            Обязательные параметры:
                employee_id - id сотрудника
        """
        ...

    @api_method(bool)
    def task_address_access_remove(self, *, employee_id: int, address_id: int ) -> ApiRetBool:
        """Удаление адресного объекта из списка адресов, куда может быть назначен сотрудник на работы

            Обязательные параметры:
                employee_id - id сотрудника
                address_id - id адресного объекта (-1 для всех адресов, -2 для объектов без адреса)
        """
        ...
    
    @api_method(bool)
    def work_time_finish(self, *, employee_id: int, date: str, comment: str = None) -> ApiRetBool:
        """Фиксация момента окончания рабочего времени сотрудника 

            Обязательные параметры:
                employee_id - id сотрудника
                date - дата и время
            Необязательные параметры:
                comment - заметки
        """
        ...
    
    @api_method(bool)
    def work_time_start(self, *, employee_id: int, date: str, comment: str = None) -> ApiRetBool:
        """Фиксация момента окончания рабочего времени сотрудника 

            Обязательные параметры:
                employee_id - id сотрудника
                date - дата и время
            Необязательные параметры:
                comment - заметки
        """
        ...