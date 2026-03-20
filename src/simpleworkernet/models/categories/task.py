from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, BaseItem, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Task(BaseCategory):
    """Работа с заданиями"""

    @api_method(int)
    def add(self, *, 
            work_typer: int, 
            apart: int = None, 
            address_id: int = None, 
            author_employee_id: int = None, 
            customer_id: int = None, 
            deadline_hour: int = None, 
            device_id: int = None, 
            division_id: int | str = None, 
            dopf_N: Any = None, 
            employee_id: int = None, 
            fio: int = None, 
            is_high_priority: vFlag = None, 
            node_id: int = None, 
            opis: str = None, 
            parent_task_id: int = None, 
            work_amount: int = None, 
            work_datedo: str = None, 
        ) -> ApiRetSData[int]:
        """Создание задания

            Обязательные параметры:
                work_typer - ID ТИПА задания

            Необязательные параметры:
                apart - номер квартиры
                address_id - id адресной единицы
                author_employee_id - ID сотрудника-автора задания
                customer_id - ID абонента
                deadline_hour - время на выполнение задания (с даты принятия. В часах)
                device_id - ID оборудования
                division_id - ID подразделения (допускается несколько значений через запятую)
                dopf_N - значение дополнительного поля для поля ID N
                employee_id - ID исполнителя (допускается несколько значений через запятую)
                fio - ФИО клиента (имеется в виду, что "клиент" еще не является абонентом)
                is_high_priority - флаг - высокий приоритет
                node_id - ID сооружения связи
                opis - заметки к заданию
                parent_task_id - ID родительского задания
                work_amount - объем работ
                work_datedo - дата на которую назначено выполнение задания
        """
        ...
    
    @api_method(bool)
    def add_customer_to_task(self, *, task_id: int, customer_id: int) -> ApiRetBool:
        """Добавление абонента к заданию

            Обязательные параметры:
                task_id - id задания
                customer_id - id абонента
        """
        ...
    
    @api_method(bool)
    def change_date_work(self, *, id: int, value: str, employee_id: int = None) -> ApiRetBool:
        """Изменение даты и времени выполнения задания (дата, на которую назначены работы)

            Обязательные параметры:
                id - id задания
                value - дата
            Необязательные параметры:
                employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...
    
    @api_method(bool)
    def change_state(self, *, id: int, state_id: int, employee_id: int = None) -> ApiRetBool:
        """Изменения состояния (статуса) задания

            Обязательные параметры:
                id - id задания
                state_id - id состояния задания
            Необязательные параметры:
                employee_id - id сотрудника, от имени которого изменять состояние
        """
        ...
    
    @api_method(bool)
    def check_verify_code(self, *, id: int, verify_code: str) -> ApiRetBool:
        """Проверка кода подтверждения для выполнения заявки

            Обязательные параметры:
                id - ID задания
                verify_code - код подтверждения
        """
        ...
    
    @api_method(bool)
    def checklist_item_check(self, *, id: int, task_id: int, employee_id: int) -> ApiRetBool:
        """Отметка пункта чек-листа в задании

            Обязательные параметры:
                id - id пункта чек-листа
                task_id - id задания
                employee_id - id сотрудника, от имени которого помечается пункт
        """
        ...
    
    @api_method(bool)
    def checklist_item_uncheck(self, *, id: int, task_id: int) -> ApiRetBool:
        """Снятие отметки с пункта чек-листа в задании

            Обязательные параметры:
                id - id пункта чек-листа
                task_id - id задания
        """
        ...
    
    @api_method(int)
    def comment_add(self, *, id: int, comment: str, dateadd: str = None, employee_id: int = None, reply_comment_id: int = None) -> ApiRetSData[int]:
        """Добавление комментария

            Обязательные параметры:
                id - ID задания
                comment - текст
            Необязательные параметры:
                dateadd - дата-время комментария
                employee_id - id сотрудника, от имени которого комментарий
                reply_comment_id - id комментария, на который отвечаем
        """
        ...
    
    @api_method(bool)
    def comment_edit(self, *, id: int, task_id: int, body: str) -> ApiRetBool:
        """Изменение комментария

            Обязательные параметры:
                id - ID комментария
                task_id - ID задания
                body - текст
        """
        ...
    
    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление задания

            Обязательные параметры:
                id - id задания
        """
        ...
    
    @api_method(bool)
    def division_add(self, *, id: int, division_id: int, employee_id: int = None) -> ApiRetBool:
        """Добавление подразделения

            Обязательные параметры:
                id - id задания
                division_id - id подразделения
            Необязательные параметры:
                employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...
    
    @api_method(bool)
    def division_delete(self, *, id: int, division_id: int, employee_id: int = None) -> ApiRetBool:
        """Исключение подразделения

            Обязательные параметры:
                id - id задания
                division_id - id подразделения
            Необязательные параметры:
                employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...
    
    @api_method(bool)
    def edit(self, *, id: int, address_id: int = None, body: str = None, deadline_hour: int = None, parent_task_id: int = None, type_id: int = None) -> ApiRetBool:
        """Изменение задания

            Обязательные параметры:
                id - id задания
            Необязательные параметры:
                address_id - id адресной единицы
                body - текст задания (описательная часть)
                deadline_hour - время на выполнение задания (с даты принятия. В часах)
                parent_task_id - id родительского задания
                type_id - id типа задания
        """
        ...
    
    @api_method(bool)
    def employee_add(self, *, id: int, employee_id: int, author_employee_id: int = None) -> ApiRetBool:
        """Добавление исполнителя

            Обязательные параметры:
                id - id задания
                employee_id - id исполнителя
            Необязательные параметры:
                author_employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...
    
    @api_method(bool)
    def employee_delete(self, *, id: int, employee_id: int, author_employee_id: int = None) -> ApiRetBool:
        """Исключение исполнителя

            Обязательные параметры:
                id - id задания
                employee_id - id исполнителя
            Необязательные параметры:
                author_employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...
    
    @smart_model
    class Get_allow_staff(BaseModel):
        division: List[int]
        staff: List[int]

    @api_method(Get_allow_staff)
    def get_allow_staff(self, *, id: int) -> ApiRetSData[Get_allow_staff]:
        """Список исполнителей и подразделений, которые доступны для назначение на задание (согласно настроек)

            Обязательные параметры:
                id - id задания
        """
        ...

    @smart_model
    class Get_catalog_type(BaseModel):
        id: int
        name: vStr
        group_id: int
        allow_state: List[int]
        amount: Any
        price_for_customer: Any
        description: vStr
        is_amount_multiply: int
        is_amount_custom: int
        position: int
        additional_field: List[int]
        additional_field_finalize: List[int]
        special_type: Any
        @smart_model
        class Tmescale(BaseModel):
            add_task_additional_hour: int
            must_doing_hour_after_add: int
            hour_on_doing: int
            notify_hour_before_deadline: Any
            notify_hour_before_finish: Any
        timescale: Tmescale
        @smart_model
        class Access(BaseModel):
            is_add: bool
            is_edit: bool
            is_view: bool
            is_delete: bool
            is_change_date: bool
            is_change_state: bool
            is_change_works: bool
            is_change_assigned: bool
            employee_profile_id: int
        access: List[Access]

    @api_method(Get_catalog_type)
    def get_catalog_type(self, *, id: int | str = None) -> ApiRetSData[Get_catalog_type]:
        """Типы заданий

            Необязательные параметры:
                id - id типа заданий (можно через запятую)
        """
        ...

    @smart_model
    class Get_catalog_type_group(BaseModel):
        id: int
        name: vStr
        order: int

    @api_method(Get_catalog_type_group)
    def get_catalog_type_group(self) -> ApiRetSData[Get_catalog_type_group]:
        """Группы типов заданий"""
        ...

    @smart_model
    class Get_catalog_state(BaseModel):
        id: int
        name: vStr
        system_role: vStr

    @api_method(Get_catalog_state)
    def get_catalog_state(self, *, state_id: int | str = None) -> ApiRetSData[Get_catalog_state]:
        """Классификатор состояний заданий

            Необязательные параметры:
                state_id - id состояния (можно через запятую)
        """
        ...

    @smart_model
    class Get_comment(BaseModel):
        task_id: int
        comment_id: int
        date_add: vStr
        text: vStr
        employee_id: int
    
    @overload
    def get_comment(self, *, id: int | str, task_id: int | str = None, date_add_from: str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Get_comment]: ...
    @overload
    def get_comment(self, *, task_id: int | str, id: int | str= None, date_add_from: str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Get_comment]: ...
    @overload
    def get_comment(self, *, date_add_from: str, id: int | str = None, task_id: int | str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Get_comment]: ...
    @overload
    def get_comment(self, *, date_add_to: str, id: int | str = None, task_id: int | str = None, date_add_from: str = None, employee_id: int = None) -> ApiRetSData[Get_comment]: ...
    @overload
    def get_comment(self, *, employee_id: int, id: int | str = None, task_id: int | str = None, date_add_from: str = None, date_add_to: str = None) -> ApiRetSData[Get_comment]: ...

    @api_method(Get_comment)
    def get_comment(self, *, id: int | str = None, task_id: int | str = None, date_add_from: str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Get_comment]:
        """Комментарии

            Необязательные параметры (но должен быть хотя-бы один):
                id - id комментария (можно через запятую)
                task_id - id заданий (можно через запятую)
                date_add_from - дата добавления комментария (с)
                date_add_to - дата добавления комментария (до)
                employee_id - id сотрудника-автора комментария
        """
        ...

    @smart_model
    class Get_list(BaseModel):
        list: List[int]
        @staticmethod
        def preprocess_response(data: Any) -> Any:
            """Предобработчик"""
            if isinstance(data, dict):
                return {**data, 'list': list(map(int, data['list'].split(',')))}
            return data

    @api_method(Get_list,preprocessor=Get_list.preprocess_response)
    def get_list(self, *, 
            address_id: int | str = None, 
            apart: str = None, 
            author_employee_id: int | str = None, 
            change_employee_id: int = None, 
            change_operation_type: Literal['add_comment', 'change_state'] = None, 
            closer_employee_id: int | str = None, 
            customer_id: int | str = None, 
            date_add_from: str = None, 
            date_add_to: str = None, 
            date_change_from: str = None, 
            date_change_to: str = None, 
            date_do_from: str = None, 
            date_do_to: str = None, 
            date_finish_from: str = None, 
            date_finish_to: str = None, 
            device_id: int | str = None, 
            division_id: int | str = None, 
            division_id_with_staff: int | str = None, 
            employee_id: int | str = None, 
            house_id: int = None, 
            is_expired: vFlag = None, 
            node_id: int = None, 
            state_id: int | str = None, 
            task_position: str = None, 
            task_position_radius: int = None, 
            type_id: int | str = None, 
            watcher_employee_id: int | str = None, 
            order_by: Literal['date_add', 'date_change', 'date_do', 'date_finish', 'state_id', 'type_id'] = None, 
            limit: int = None, 
            offset: int = None 
        ) -> ApiRetSData[Get_list]:
        """Список заданий (идентификаторы)

            Необязательные параметры (условия выборки):
                address_id - ID адресного объекта (можно через запятую)
                apart - номер квартиры/помещения
                author_employee_id - ID сотрудника - автора задания (можно через запятую)
                change_employee_id - ID сотрудника - автора изменений по заданию
                change_operation_type - тип действий по изменению задания (возможные значения: add_comment, change_state)
                closer_employee_id - ID сотрудника, который закрыл (выполнил) задание (можно через запятую)
                customer_id - ID абонента (можно через запятую)
                date_add_from - дата создания задания (с)
                date_add_to - дата создания задания (до)
                date_change_from - дата обновления задания (с)
                date_change_to - дата обновления задания (до)
                date_do_from - дата на которую назначено выполнение задания (с)
                date_do_to - дата на которую назначено выполнение задания (до)
                date_finish_from - дата выполнения задания (с)
                date_finish_to - дата выполнения задания (до)
                device_id - ID оборудования (можно через запятую)
                division_id - ID подразделения (можно через запятую)
                division_id_with_staff - ID подразделения (в т.ч. с заданиями сотрудников этого подразделения) (можно через запятую)
                employee_id - ID исполнителя (можно через запятую, используйте -1 для получения заданий без исполнителей)
                house_id - ID дома работ
                is_expired - флаг - выводить только просроченные задания
                node_id - ID объекта размещения
                state_id - ID статуса заданий (можно через запятую)
                task_position - координаты задания (там где это возможно. В формате lat,lng. Напр: 40.245218,52.333384)
                task_position_radius - радиус от task_position (в метрах)
                type_id - ID типа заданий (можно через запятую)
                watcher_employee_id - ID сотрудника-наблюдателя за заданием (можно через запятую)
                order_by - поле для сортировки (возможные варианты: date_add, date_change, date_do, date_finish, state_id, type_id)
                limit - лимит выборки записей
                offset - смещение выборки
        """
        ...
    
    @api_method(int)
    def get_related_task_id(self, *, id: int) -> ApiRetSData[int]:
        """Список связанных заданий с текущим заданием (идентификаторы)

            Обязательные параметры:
                id - ID задания
        """
        ...
    
    @smart_model
    class Get_typical_comments(BaseModel):
        id: int
        text: vStr
        task_type_ids: List[int]
    
    @api_method(Get_typical_comments)
    def get_typical_comments(self) -> ApiRetSData[Get_typical_comments]:
        """Получение списка типовых комментариев"""
        ...
    
    @api_method(bool)
    def remove_customer_from_task(self, *, task_id: int, customer_id: int) -> ApiRetBool:
        """Исключение абонента с задания

            Обязательные параметры:
                task_id - id задания
                customer_id - id абонента
        """
        ...
    
    @api_method(bool)
    def set_rate(self, *, task_id: int, rate) -> ApiRetBool:
        """Указание индивидуального тарифа (для сотрудников) по заданию

            Обязательные параметры:
                task_id - ID задания
                rate - тариф
        """
        ...
    
    @smart_model
    class Show(BaseModel):
        id: int
        parentTaskId: int
        optional_customer_name: vStr
        priority: int
        type: BaseItem
        @smart_model
        class Date(BaseModel):
            create: vStr
            todo: vStr
            update: vStr
            complete: Any
            deadline_individual_hour: int
            runtime_individual_hour: int
        date: Date
        @smart_model
        class State(BaseModel):
            id: int
            name: vStr
            system_role: int
            system_role_text: vStr
        state: State
        @smart_model
        class Address(BaseModel):
            text: vStr
            addressId: int
            apartament: vStr
        address: Address
        node: List[int]
        description: vStr
        description_short: vStr
        author_employee_id: int
        tags: List[Any]
        priceCustomv: int
        volumeCustom: int
        @smart_model
        class Comments(BaseModel):
            id: int
            dateAdd: vStr
            employee_id: int
            comment: vStr
        comments: List[Comments]
        @smart_model
        class Additional_data(BaseModel):
            id: int
            caption: vStr
            value: vStr
        additional_data: List[Additional_data]
        @smart_model
        class Staff(BaseModel):
            employee: List[int]
        staff: Staff
        @smart_model
        class History(BaseModel):
            type_id: int
            date: vStr
            employee_id: int
            comment: vStr
        history: List[History]
        @smart_model
        class Task_status_history(BaseModel):
            start_time: int
            end_time: int
            percentage: int
            task_status_id: int
            task_status_name: vStr
        task_status_history: List[Task_status_history]

    @api_method(Show)
    def show(self, *, id: int, employee_id: int = None, is_without_comments: vFlag = None) -> ApiRetSData[Show]:
        """Информация о задании

            Обязательные параметры:
                id - id задания (можно через запятую)
            Необязательные параметры:
                employee_id - id сотрудника, который просматривает это задание (для фиксации в историю по заданию)
                is_without_comments - флаг - не выводить комментарии в информации по заданию
        """
        ...

    @api_method(bool)
    def watcher_add(self, *, id: int, employee_id: int, author_employee_id: int = None) -> ApiRetBool:
        """Добавление наблюдателя

            Обязательные параметры:
                id - id задания
                employee_id - id наблюдателя
            Необязательные параметры:
                author_employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...

    @api_method(bool)
    def watcher_delete(self, *, id: int, employee_id: int, author_employee_id: int = None) -> ApiRetBool:
        """Исключение наблюдателя

            Обязательные параметры:
                id - id задания
                employee_id - id наблюдателя
            Необязательные параметры:
                author_employee_id - id сотрудника-инициатора (для фиксации в историю по заданию)
        """
        ...