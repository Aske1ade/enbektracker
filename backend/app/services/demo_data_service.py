from collections import defaultdict
from datetime import datetime, timedelta, timezone
import os
import random
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select, update

from app.core.security import get_password_hash
from app.models import (
    Department,
    DemoSeedEntity,
    DesktopEvent,
    GroupMembership,
    Item,
    Notification,
    OrgGroup,
    Organization,
    OrganizationMembership,
    Project,
    ProjectDepartment,
    ProjectMember,
    ProjectMemberRole,
    ProjectSubjectRole,
    ProjectStatus,
    Task,
    TaskAssignee,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    User,
    SystemRole,
    WorkBlock,
    WorkBlockDepartment,
    WorkBlockManager,
    WorkBlockProject,
)
from app.repositories import project_statuses as status_repo
from app.repositories import projects as project_repo
from app.schemas.demo_data import DemoDataCredential, DemoDataSummary
from app.services import project_service, system_settings_service, task_service

DEMO_MARKER = "demo-batch"
DEMO_USER_PASSWORD = os.getenv("DEMO_USERS_PASSWORD", "DemoPass123!")

DEMO_ORGANIZATIONS = [
    (
        "ORG_MTSZN",
        "Блок МТСЗН",
        "Организация для проектов блока МТСЗН",
    ),
    (
        "ORG_INFRA",
        "Блок Инфраструктура и безопасность",
        "Организация для инфраструктурных и ИБ-проектов",
    ),
]

DEMO_DEPARTMENTS = [
    ("DEP_LEGAL", "Департамент юридической службы", "ORG_MTSZN"),
    ("DEP_MIGRATION", "Комитет по миграции", "ORG_MTSZN"),
    (
        "DEP_INFOSEC",
        "Департамент информационной безопасности",
        "ORG_INFRA",
    ),
    (
        "DEP_AI_OFFICE",
        "Офис развития ИИ и архитектуры",
        "ORG_INFRA",
    ),
]

DEMO_BLOCKS = [
    (
        "BL_MTSZN",
        "Блок МТСЗН",
        ("DEP_LEGAL", "DEP_MIGRATION"),
        "ORG_MTSZN",
    ),
    (
        "BL_INFRA",
        "Блок Инфраструктура и безопасность",
        ("DEP_INFOSEC", "DEP_AI_OFFICE"),
        "ORG_INFRA",
    ),
]

DEMO_PROJECTS = [
    # Блок Инфраструктура и безопасность
    {
        "department_key": "DEP_INFOSEC",
        "name": "Внедрение новой системы управления событиями информационной безопасности (SIEM)",
        "description": "Операционные задачи департамента информационной безопасности",
    },
    {
        "department_key": "DEP_AI_OFFICE",
        "name": "Задачи QA",
        "description": "Операционные задачи QA команды",
    },
    {
        "department_key": "DEP_INFOSEC",
        "name": "ИКТ Инфраструктура",
        "description": "Операционные задачи по ИКТ инфраструктуре",
    },
    {
        "department_key": "DEP_INFOSEC",
        "name": "Интеграции",
        "description": "Операционные задачи по интеграциям",
    },
    {
        "department_key": "DEP_INFOSEC",
        "name": "Информ безопасность",
        "description": "Операционные задачи департамента ИБ",
    },
    {
        "department_key": "DEP_AI_OFFICE",
        "name": "Контакт Центр",
        "description": "Операционные задачи Контакт центра",
    },
    {
        "department_key": "DEP_AI_OFFICE",
        "name": "Офис ИИ и архитектуры",
        "description": "Постановка задач в части внедрения и использования инструментов искусственного интеллекта, архитектуры, DevOps и QA",
    },
    # Блок МТСЗН
    {
        "department_key": "DEP_LEGAL",
        "name": "Заключения Правительства",
        "description": "Подготовка и сопровождение заключений Правительства",
    },
    {
        "department_key": "DEP_LEGAL",
        "name": "Законопроекты",
        "description": "Сопровождение и согласование законопроектов",
    },
    {
        "department_key": "DEP_MIGRATION",
        "name": "Контрольные поручения Главы государства",
        "description": "Контроль исполнения поручений Главы государства",
    },
    {
        "department_key": "DEP_LEGAL",
        "name": "Поручения АП, АПр",
        "description": "Поручения Администрации Президента и Аппарата Правительства",
    },
]

DEMO_TASK_BLUEPRINTS = [
    {
        "title": "Подготовить еженедельный статус",
        "description": "<p>Собрать актуальный статус задач и рисков по направлению.</p>",
        "due_delta_days": 5,
        "status_code": "in_progress",
        "comment": "Черновик статуса подготовлен.",
    },
    {
        "title": "Проверить просроченные поручения",
        "description": "<p>Провести ревизию просроченных задач и обновить план закрытия.</p>",
        "due_delta_days": -2,
        "status_code": "in_progress",
        "comment": "Найдены критичные просрочки, назначены ответственные.",
    },
    {
        "title": "Согласовать рабочий документ",
        "description": "<p>Внести правки по замечаниям и передать документ на проверку.</p>",
        "due_delta_days": 2,
        "status_code": "review",
        "comment": "Документ передан на проверку контроллеру.",
    },
    {
        "title": "Обновить реестр рисков",
        "description": "<p>Актуализировать риск-регистр и статус мер реагирования.</p>",
        "due_delta_days": 2,
        "status_code": "done",
        "comment": "Реестр рисков обновлен и закрыт в срок.",
    },
    {
        "title": "Сформировать пакет материалов",
        "description": "<p>Собрать комплект материалов по проекту для руководства.</p>",
        "due_delta_days": 8,
        "status_code": "in_progress",
        "comment": "Пакет материалов в работе.",
    },
    {
        "title": "Закрыть контрольный этап",
        "description": "<p>Финализировать этап и оформить результат.</p>",
        "due_delta_days": 1,
        "status_code": "done",
        "comment": "Этап завершен и принят в срок.",
    },
    {
        "title": "Подготовить итоговую справку",
        "description": "<p>Сформировать итоговую аналитическую справку.</p>",
        "due_delta_days": 2,
        "status_code": "done",
        "comment": "Справка готова и закрыта в срок.",
    },
    {
        "title": "Сверить исполнителей и доступы",
        "description": "<p>Проверить корректность ролей, исполнителей и контроллеров.</p>",
        "due_delta_days": 6,
        "status_code": "in_progress",
        "comment": "Проверка доступов продолжается.",
    },
    {
        "title": "Проверить замечания контроллера",
        "description": "<p>Обработать замечания контроллера и обновить материалы.</p>",
        "due_delta_days": 1,
        "status_code": "review",
        "comment": "Замечания устранены и повторно отправлены на проверку.",
    },
    {
        "title": "Закрыть операционный цикл",
        "description": "<p>Подтвердить выполнение всех шагов операционного цикла.</p>",
        "due_delta_days": -5,
        "status_code": "done",
        "comment": "Цикл закрыт с просрочкой для демонстрации отчётности.",
    },
]

DEMO_SPECIAL_TASKS = [
    {
        "department_key": "DEP_LEGAL",
        "project_name": "Поручения АП, АПр",
        "title": "Для направления предложения о привлечении к дисциплинарной ответственности политического должностного лица",
        "description": (
            "<p>Поручение ЗПМ-РАПр РК Койшибаева Г.Т. № 22-06/7909-4 от 12.01.2026.</p>"
            "<p>Исполнено 13.01.2026, направлена информация в АПр РК № 01-1-13/Д-81//22-06/7909.</p>"
            "<p>Дата постановки: 12.01.2026</p><p>Сроки: 19.01.2026</p>"
        ),
        "creator_key": "gulmira_alieva",
        "controller_key": "gulmira_alieva",
        "assignee_key": "perizat_moldakhmetova",
        "due_date": datetime(2026, 1, 19, 18, 0, tzinfo=timezone.utc),
        "created_at": datetime(2026, 1, 12, 10, 0, tzinfo=timezone.utc),
        "closed_at": datetime(2026, 1, 18, 18, 0, tzinfo=timezone.utc),
        "close_comment": "Задача закрыта в срок (демо-сценарий).",
    },
    {
        "department_key": "DEP_MIGRATION",
        "project_name": "Контрольные поручения Главы государства",
        "title": (
            "Касательно Единого Социального Фонда: Министерству труда и социальной "
            "защиты населения до конца 2025 разработать законопроекты в части внесения "
            "изменений и дополнений в Социальный кодекс, а также некоторые законодательные "
            "акты по вопросам реструктуризации социальных трансфертов с переходом от "
            "категориального подхода к критериям нуждаемости."
        ),
        "description": (
            "<p>пункт 2.3. Министерству труда и социальной защиты населения до конца 2025 "
            "разработать законопроекты в части внесения изменений и дополнений в Социальный "
            "кодекс, а также некоторые законодательные акты по вопросам реструктуризации "
            "социальных трансфертов с переходом от категориального подхода к критериям "
            "нуждаемости.</p><p>Поручение Президента РК № 25-1380 қбп от 07.03.2025 года.</p>"
            "<p>Дата постановки: 07.03.2025</p><p>Сроки: 04.03.2026</p>"
        ),
        "creator_key": "gulmira_alieva",
        "controller_key": "gulmira_alieva",
        "assignee_key": "perizat_moldakhmetova",
        "due_date": datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc),
        "created_at": None,  # set dynamically to "about 20 days ago"
        "closed_at": None,
        "close_comment": "",
    },
]

DEMO_USERS = [
    {
        "key": "bakhytzhan_mynbaev",
        "username": "Бахытжан_Мынбаев",
        "full_name": "Бахытжан Мынбаев",
        "email": "b.mynbaev@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "elena_kim",
        "username": "Елена_Ким",
        "full_name": "Елена Ким",
        "email": "e.kim@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "zhandos_bapanov",
        "username": "Жандос_Бапанов",
        "full_name": "Жандос Бапанов",
        "email": "zh.bapanov@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "nurlan_yulimbetov",
        "username": "Нурлан_Юлимбетов",
        "full_name": "Нурлан Юлимбетов",
        "email": "n.yulimbetov@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "elvira_ibrayeva",
        "username": "Эльвира_Ибраева",
        "full_name": "Эльвира Ибраева",
        "email": "e.ibrayeva@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "perizat_moldakhmetova",
        "username": "Перизат_Молдахметова",
        "full_name": "Перизат Молдахметова",
        "email": "p.moldahmetova@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL"],
    },
    {
        "key": "gulmira_alieva",
        "username": "g.alieva@enbek.gov.kz",
        "full_name": "Гульмира Алиева",
        "email": "g.alieva@enbek.gov.kz",
        "primary_department": "DEP_LEGAL",
        "department_keys": ["DEP_LEGAL", "DEP_MIGRATION"],
    },
    {
        "key": "aray_sharafitdinova",
        "username": "Арай_Шарафитдинова",
        "full_name": "Арай Шарафитдинова",
        "email": "a.sharafitdinova@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "aset_shonov",
        "username": "Асет_Шонов",
        "full_name": "Асет Шонов",
        "email": "a.shonov@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "dina_temirbulat",
        "username": "Дина_Темирбулат",
        "full_name": "Дина Темирбулат",
        "email": "d.temirova@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "dinara_sarsembinova",
        "username": "Динара_Сарсембинова",
        "full_name": "Динара Сарсембинова",
        "email": "d.sarsembinova@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "miyrgul_baizhanova",
        "username": "Мийргуль_Байжанова",
        "full_name": "Мийргуль Байжанова",
        "email": "m.baizhanova@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "nurbol_baisynov",
        "username": "Нурбол_Байсынов",
        "full_name": "Нурбол Байсынов",
        "email": "n.baisynov@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "nurdan_ashimov",
        "username": "Нурдан_Ашимов",
        "full_name": "Нурдан Ашимов",
        "email": "n.ashimov@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "nurlan_tazhibaev",
        "username": "Нурлан_Тажибаев",
        "full_name": "Нурлан Тажибаев",
        "email": "nu.tazhibaev@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "elmira_tillabaikyzy",
        "username": "Эльмира_Тілләбайқызы",
        "full_name": "Эльмира Тілләбайқызы",
        "email": "e.tazhikhanova@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "amirzhan_tazhibekov",
        "username": "Әміржан_Тажибеков",
        "full_name": "Әміржан Тажибеков",
        "email": "aa.tazhibekov@enbek.gov.kz",
        "primary_department": "DEP_MIGRATION",
        "department_keys": ["DEP_MIGRATION"],
    },
    {
        "key": "adilbek_abdygaliev",
        "username": "Адильбек_Абдыгалиев",
        "full_name": "Адильбек Абдыгалиев",
        "email": "a.abdygaliev@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "bauyrzhan_alchimbayev",
        "username": "Бауыржан_Алчимбаев",
        "full_name": "Бауыржан Алчимбаев",
        "email": "b.alchimbayev@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC", "DEP_AI_OFFICE", "DEP_MIGRATION"],
    },
    {
        "key": "dias_akhmetov",
        "username": "Диас_Ахметов",
        "full_name": "Диас Ахметов",
        "email": "akhmetov-d@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "elzhan_kenzheshev",
        "username": "Елжан_Кенжешев",
        "full_name": "Елжан Кенжешев",
        "email": "y.kenzheshev@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "kuat_aliev",
        "username": "Куат_Алиев",
        "full_name": "Куат Алиев",
        "email": "K.Aliev@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "meirzhan_pernebek",
        "username": "Мейржан_Пернебек",
        "full_name": "Мейржан Пернебек",
        "email": "m.pernebek@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "nurbolat_usembaev",
        "username": "Усембаев_Нурболат",
        "full_name": "Усембаев Нурболат",
        "email": "n.usembaev@enbek.kz",
        "primary_department": "DEP_INFOSEC",
        "department_keys": ["DEP_INFOSEC"],
    },
    {
        "key": "abdrakhman_abdulkhak",
        "username": "Абдрахман_Абдулхақ",
        "full_name": "Абдрахман Абдулхақ",
        "email": "a.abdrakhman@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "abylai_alimzhanov",
        "username": "Абылай_Алимжанов",
        "full_name": "Абылай Алимжанов",
        "email": "a.alimzhanov@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "aigul_raimova",
        "username": "Айгуль_Раимова",
        "full_name": "Айгуль Раимова",
        "email": "a.raimova@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "aleksei_boikov",
        "username": "Алексей_Бойков",
        "full_name": "Алексей Бойков",
        "email": "a.boykov@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "alesiy_popov",
        "username": "Алесий_Попов",
        "full_name": "Алесий Попов",
        "email": "A.Popov@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "aliyar_azimsham",
        "username": "Алиар_Азимшам",
        "full_name": "Алиар Азимшам",
        "email": "A.Azimsham@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "alibek_seitbattalov",
        "username": "Алибек_Сейтбатталов",
        "full_name": "Алибек Сейтбатталов",
        "email": "a.seitbattalov@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "berik_smadyarov",
        "username": "Смадьяров_Берік",
        "full_name": "Смадьяров Берік",
        "email": "b.smadyarov@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "roman_stangrit",
        "username": "Стангрит_Роман",
        "full_name": "Стангрит Роман",
        "email": "r.stangrit@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "altynai_konakbayeva",
        "username": "Қонақбаева_Алтынай",
        "full_name": "Қонақбаева Алтынай",
        "email": "a.konakbayeva@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE"],
    },
    {
        "key": "olzhas_anafin",
        "username": "Олжас_Анафин",
        "full_name": "Олжас Анафин",
        "email": "o.anafin@enbek.kz",
        "primary_department": "DEP_AI_OFFICE",
        "department_keys": ["DEP_AI_OFFICE", "DEP_INFOSEC"],
    },
]

DEMO_USERNAME_BY_EMAIL = {
    str(entry["email"]).lower(): str(entry["username"]) for entry in DEMO_USERS
}
DEMO_USER_BY_KEY = {str(entry["key"]): entry for entry in DEMO_USERS}

ROLE_PRIORITY = {"member": 1, "manager": 2, "owner": 3}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _latest_batch_id(session: Session) -> str | None:
    return session.exec(
        select(DemoSeedEntity.batch_id)
        .order_by(DemoSeedEntity.created_at.desc(), DemoSeedEntity.id.desc())
        .limit(1)
    ).first()


def _all_batch_ids(session: Session) -> list[str]:
    rows = session.exec(
        select(DemoSeedEntity.batch_id)
        .distinct()
        .order_by(DemoSeedEntity.batch_id.desc())
    ).all()
    return [str(batch_id) for batch_id in rows if batch_id]


def _batch_entity_ids(session: Session, *, batch_id: str) -> dict[str, list[int]]:
    rows = session.exec(
        select(DemoSeedEntity.entity_type, DemoSeedEntity.entity_id).where(
            DemoSeedEntity.batch_id == batch_id
        )
    ).all()
    result: dict[str, list[int]] = {}
    for entity_type, entity_id in rows:
        result.setdefault(entity_type, []).append(entity_id)
    return result


def _register_entity(
    session: Session,
    *,
    batch_id: str,
    entity_type: str,
    entity_id: int,
) -> None:
    session.add(
        DemoSeedEntity(
            batch_id=batch_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


def _status_map(session: Session, project_id: int) -> dict[str, ProjectStatus]:
    statuses, _ = status_repo.list_project_statuses(session, project_id=project_id, limit=100)
    return {status_obj.code or "": status_obj for status_obj in statuses}


def _pick_weighted_assignee_key(user_keys: list[str], task_index: int) -> str:
    if not user_keys:
        raise ValueError("user_keys must not be empty")
    weighted_indices = [0, 0, 1, 0, 2, 1, 0, 3, 1, 4]
    target = weighted_indices[task_index % len(weighted_indices)]
    return user_keys[target % len(user_keys)]


def _role_max(left: str, right: str) -> str:
    return left if ROLE_PRIORITY.get(left, 0) >= ROLE_PRIORITY.get(right, 0) else right


def _upsert_organization_membership(
    session: Session,
    *,
    organization_id: int,
    user_id: int,
    role_name: str,
) -> None:
    existing = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).first()
    if existing is None:
        session.add(
            OrganizationMembership(
                organization_id=organization_id,
                user_id=user_id,
                role_name=role_name,
                is_active=True,
            )
        )
        return
    existing.role_name = _role_max(existing.role_name or "member", role_name)
    existing.is_active = True
    existing.updated_at = utcnow()
    session.add(existing)


def _upsert_group_membership(
    session: Session,
    *,
    group_id: int,
    user_id: int,
    role_name: str,
) -> None:
    existing = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    ).first()
    if existing is None:
        session.add(
            GroupMembership(
                group_id=group_id,
                user_id=user_id,
                role_name=role_name,
                is_active=True,
            )
        )
        return
    existing.role_name = _role_max(existing.role_name or "member", role_name)
    existing.is_active = True
    existing.updated_at = utcnow()
    session.add(existing)


def _upsert_demo_user(
    session: Session,
    *,
    email: str,
    full_name: str,
    department_id: int,
    primary_group_id: int,
) -> User:
    existing = session.exec(select(User).where(User.email == email)).first()
    hashed_password = get_password_hash(DEMO_USER_PASSWORD)
    if existing is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False,
            system_role=SystemRole.USER,
            department_id=department_id,
            primary_group_id=primary_group_id,
        )
        session.add(user)
        session.flush()
        return user

    existing.full_name = full_name
    existing.hashed_password = hashed_password
    existing.is_active = True
    existing.is_superuser = False
    existing.system_role = SystemRole.USER
    existing.department_id = department_id
    existing.primary_group_id = primary_group_id
    existing.updated_at = utcnow()
    session.add(existing)
    session.flush()
    return existing


def _ensure_global_registered_group(session: Session) -> tuple[Organization, OrgGroup]:
    global_org = session.exec(
        select(Organization).where(Organization.is_global.is_(True)).order_by(Organization.id.asc())
    ).first()
    if global_org is None:
        global_org = session.exec(
            select(Organization).where(Organization.name == "Global")
        ).first()
    if global_org is None:
        global_org = Organization(
            name="Global",
            code="GLOBAL",
            description="Глобальный контур",
            is_global=True,
        )
        session.add(global_org)
        session.flush()

    registered_group = session.exec(
        select(OrgGroup).where(
            OrgGroup.organization_id == global_org.id,
            OrgGroup.name == "Зарегистрированные пользователи",
        )
    ).first()
    if registered_group is None:
        registered_group = OrgGroup(
            organization_id=global_org.id,
            name="Зарегистрированные пользователи",
            code="REGISTERED-USERS",
            description="Служебная группа для всех пользователей",
        )
        session.add(registered_group)
        session.flush()

    return global_org, registered_group


def _demo_summary(session: Session) -> DemoDataSummary:
    is_locked = system_settings_service.get_bool(
        session,
        key=system_settings_service.DEMO_DATA_LOCKED_KEY,
        default=False,
    )
    batch_id = _latest_batch_id(session)
    if batch_id is None:
        return DemoDataSummary(
            enabled=False,
            marker=DEMO_MARKER,
            is_locked=is_locked,
            users_count=0,
            departments_count=0,
            projects_count=0,
            tasks_count=0,
            credentials=[],
        )

    ids = _batch_entity_ids(session, batch_id=batch_id)
    user_ids = sorted(set(ids.get("user", [])))
    department_ids = sorted(set(ids.get("department", [])))
    users: list[User] = []
    if user_ids:
        users = session.exec(select(User).where(User.id.in_(user_ids))).all()

    department_name_map: dict[int, str] = {}
    if department_ids:
        department_name_map = {
            row[0]: row[1]
            for row in session.exec(
                select(Department.id, Department.name).where(Department.id.in_(department_ids))
            ).all()
        }

    org_names_by_user: dict[int, set[str]] = defaultdict(set)
    group_names_by_user: dict[int, set[str]] = defaultdict(set)
    group_roles_by_user: dict[int, set[str]] = defaultdict(set)

    if user_ids:
        org_rows = session.exec(
            select(
                OrganizationMembership.user_id,
                Organization.name,
            )
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .where(
                OrganizationMembership.user_id.in_(user_ids),
                OrganizationMembership.is_active.is_(True),
            )
        ).all()
        for user_id, org_name in org_rows:
            if org_name:
                org_names_by_user[int(user_id)].add(str(org_name))

        group_rows = session.exec(
            select(
                GroupMembership.user_id,
                OrgGroup.name,
                GroupMembership.role_name,
            )
            .join(OrgGroup, OrgGroup.id == GroupMembership.group_id)
            .where(
                GroupMembership.user_id.in_(user_ids),
                GroupMembership.is_active.is_(True),
            )
        ).all()
        for user_id, group_name, role_name in group_rows:
            if group_name:
                group_names_by_user[int(user_id)].add(str(group_name))
            if role_name:
                group_roles_by_user[int(user_id)].add(str(role_name))

    credentials = []
    for user in sorted(users, key=lambda item: item.email.lower()):
        credentials.append(
            DemoDataCredential(
                email=user.email,
                full_name=user.full_name,
                username=DEMO_USERNAME_BY_EMAIL.get(user.email.lower()),
                system_role=user.system_role,
                department_name=department_name_map.get(user.department_id),
                organization_names=sorted(org_names_by_user.get(int(user.id or 0), set())),
                group_names=sorted(group_names_by_user.get(int(user.id or 0), set())),
                group_roles=sorted(group_roles_by_user.get(int(user.id or 0), set())),
                password=DEMO_USER_PASSWORD,
            )
        )

    return DemoDataSummary(
        enabled=True,
        marker=batch_id,
        is_locked=is_locked,
        users_count=len(set(ids.get("user", []))),
        departments_count=len(set(ids.get("department", []))),
        projects_count=len(set(ids.get("project", []))),
        tasks_count=len(set(ids.get("task", []))),
        credentials=credentials,
    )


def _clear_demo_batch(session: Session, *, batch_id: str) -> None:
    ids = _batch_entity_ids(session, batch_id=batch_id)
    task_ids = sorted(set(ids.get("task", [])))
    project_ids = sorted(set(ids.get("project", [])))
    user_ids = sorted(set(ids.get("user", [])))
    department_ids = sorted(set(ids.get("department", [])))
    block_ids = sorted(set(ids.get("block", [])))
    organization_ids = sorted(set(ids.get("organization", [])))
    group_ids = sorted(set(ids.get("group", [])))

    try:
        if project_ids:
            project_task_ids = session.exec(
                select(Task.id).where(Task.project_id.in_(project_ids))
            ).all()
            if project_task_ids:
                task_ids = sorted(set(task_ids) | {int(task_id) for task_id in project_task_ids})

        # Safety: if demo users participated in additional tasks, remove those tasks as well
        # to avoid FK violations on user cleanup.
        if user_ids:
            user_task_ids = session.exec(
                select(Task.id).where(
                    or_(
                        Task.creator_id.in_(user_ids),
                        Task.id.in_(
                            select(TaskAssignee.task_id).where(TaskAssignee.user_id.in_(user_ids))
                        ),
                    )
                )
            ).all()
            if user_task_ids:
                task_ids = sorted(set(task_ids) | {int(task_id) for task_id in user_task_ids})

            # Detach non-demo tasks from demo users where nullable.
            if task_ids:
                session.exec(
                    update(Task)
                    .where(Task.assignee_id.in_(user_ids), Task.id.notin_(task_ids))
                    .values(assignee_id=None)
                )
                session.exec(
                    update(Task)
                    .where(Task.controller_id.in_(user_ids), Task.id.notin_(task_ids))
                    .values(controller_id=None)
                )
                session.exec(
                    delete(TaskAssignee).where(
                        TaskAssignee.user_id.in_(user_ids),
                        TaskAssignee.task_id.notin_(task_ids),
                    )
                )
            else:
                session.exec(update(Task).where(Task.assignee_id.in_(user_ids)).values(assignee_id=None))
                session.exec(update(Task).where(Task.controller_id.in_(user_ids)).values(controller_id=None))
                session.exec(delete(TaskAssignee).where(TaskAssignee.user_id.in_(user_ids)))

            # Comments/history/attachments authored by demo users must be removed prior to user delete.
            session.exec(delete(TaskHistory).where(TaskHistory.actor_id.in_(user_ids)))
            session.exec(delete(TaskComment).where(TaskComment.author_id.in_(user_ids)))
            session.exec(delete(TaskAttachment).where(TaskAttachment.uploaded_by_id.in_(user_ids)))

            # Demo users can be linked to any project memberships/roles.
            session.exec(delete(ProjectMember).where(ProjectMember.user_id.in_(user_ids)))
            session.exec(
                delete(ProjectSubjectRole).where(ProjectSubjectRole.subject_user_id.in_(user_ids))
            )

            # Detach projects created by demo users to avoid FK collisions.
            session.exec(
                update(Project).where(Project.created_by_id.in_(user_ids)).values(created_by_id=None)
            )

        desktop_filters = []
        if task_ids:
            desktop_filters.append(DesktopEvent.task_id.in_(task_ids))
        if project_ids:
            desktop_filters.append(DesktopEvent.project_id.in_(project_ids))
        if user_ids:
            desktop_filters.append(DesktopEvent.user_id.in_(user_ids))
        if desktop_filters:
            condition = desktop_filters[0]
            for item in desktop_filters[1:]:
                condition = condition | item
            session.exec(delete(DesktopEvent).where(condition))

        if user_ids:
            session.exec(delete(Notification).where(Notification.user_id.in_(user_ids)))
            session.exec(delete(Item).where(Item.owner_id.in_(user_ids)))

        if task_ids:
            session.exec(delete(TaskHistory).where(TaskHistory.task_id.in_(task_ids)))
            session.exec(delete(TaskComment).where(TaskComment.task_id.in_(task_ids)))
            session.exec(delete(TaskAttachment).where(TaskAttachment.task_id.in_(task_ids)))
            session.exec(delete(TaskAssignee).where(TaskAssignee.task_id.in_(task_ids)))
            session.exec(delete(Task).where(Task.id.in_(task_ids)))

        if project_ids:
            project_task_subquery = select(Task.id).where(Task.project_id.in_(project_ids))
            session.exec(delete(TaskHistory).where(TaskHistory.task_id.in_(project_task_subquery)))
            session.exec(delete(TaskComment).where(TaskComment.task_id.in_(project_task_subquery)))
            session.exec(delete(TaskAttachment).where(TaskAttachment.task_id.in_(project_task_subquery)))
            session.exec(delete(TaskAssignee).where(TaskAssignee.task_id.in_(project_task_subquery)))
            session.exec(delete(Task).where(Task.project_id.in_(project_ids)))
            session.exec(delete(ProjectSubjectRole).where(ProjectSubjectRole.project_id.in_(project_ids)))
            session.exec(delete(ProjectStatus).where(ProjectStatus.project_id.in_(project_ids)))
            session.exec(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids)))
            session.exec(delete(ProjectDepartment).where(ProjectDepartment.project_id.in_(project_ids)))
            session.exec(delete(WorkBlockProject).where(WorkBlockProject.project_id.in_(project_ids)))
            session.exec(delete(Project).where(Project.id.in_(project_ids)))

        if group_ids:
            # Non-demo users may still reference these demo groups.
            if user_ids:
                session.exec(
                    update(User)
                    .where(User.primary_group_id.in_(group_ids), User.id.notin_(user_ids))
                    .values(primary_group_id=None)
                )
            else:
                session.exec(update(User).where(User.primary_group_id.in_(group_ids)).values(primary_group_id=None))

        if department_ids:
            # Some non-demo groups may still reference demo departments via legacy link.
            session.exec(
                update(OrgGroup)
                .where(OrgGroup.legacy_department_id.in_(department_ids))
                .values(legacy_department_id=None)
            )
            session.flush()

            if user_ids:
                session.exec(
                    update(User)
                    .where(User.department_id.in_(department_ids), User.id.notin_(user_ids))
                    .values(department_id=None)
                )
            else:
                session.exec(update(User).where(User.department_id.in_(department_ids)).values(department_id=None))

            if project_ids:
                session.exec(
                    update(Project)
                    .where(Project.department_id.in_(department_ids), Project.id.notin_(project_ids))
                    .values(department_id=None)
                )
            else:
                session.exec(
                    update(Project).where(Project.department_id.in_(department_ids)).values(department_id=None)
                )

        if organization_ids:
            if project_ids:
                session.exec(
                    update(Project)
                    .where(Project.organization_id.in_(organization_ids), Project.id.notin_(project_ids))
                    .values(organization_id=None)
                )
            else:
                session.exec(
                    update(Project)
                    .where(Project.organization_id.in_(organization_ids))
                    .values(organization_id=None)
                )

        if block_ids:
            session.exec(delete(WorkBlockDepartment).where(WorkBlockDepartment.block_id.in_(block_ids)))
            session.exec(delete(WorkBlockManager).where(WorkBlockManager.block_id.in_(block_ids)))
            session.exec(delete(WorkBlock).where(WorkBlock.id.in_(block_ids)))

        if group_ids:
            session.exec(delete(ProjectSubjectRole).where(ProjectSubjectRole.subject_group_id.in_(group_ids)))
            session.exec(delete(GroupMembership).where(GroupMembership.group_id.in_(group_ids)))
        if user_ids:
            session.exec(delete(GroupMembership).where(GroupMembership.user_id.in_(user_ids)))
            session.exec(delete(WorkBlockManager).where(WorkBlockManager.user_id.in_(user_ids)))

        if organization_ids:
            session.exec(
                delete(OrganizationMembership).where(
                    OrganizationMembership.organization_id.in_(organization_ids)
                )
            )
        if user_ids:
            session.exec(delete(OrganizationMembership).where(OrganizationMembership.user_id.in_(user_ids)))

        if user_ids:
            session.exec(delete(User).where(User.id.in_(user_ids)))

        if group_ids:
            session.exec(delete(OrgGroup).where(OrgGroup.id.in_(group_ids)))

        if organization_ids:
            session.exec(delete(Organization).where(Organization.id.in_(organization_ids)))

        if department_ids:
            session.exec(delete(WorkBlockDepartment).where(WorkBlockDepartment.department_id.in_(department_ids)))
            session.exec(delete(Department).where(Department.id.in_(department_ids)))

        session.exec(delete(DemoSeedEntity).where(DemoSeedEntity.batch_id == batch_id))

        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Demo data cleanup conflict for batch {batch_id}: {exc.orig}",
        ) from exc


def clear_demo_data(session: Session) -> DemoDataSummary:
    batch_ids = _all_batch_ids(session)
    if not batch_ids:
        return _demo_summary(session)

    # Remove all known demo batches, newest first.
    for batch_id in batch_ids:
        _clear_demo_batch(session, batch_id=batch_id)

    return _demo_summary(session)


def populate_demo_data(session: Session, actor: User) -> DemoDataSummary:
    clear_demo_data(session)
    batch_id = f"{DEMO_MARKER}-{uuid4().hex[:8]}"
    rng = random.Random()
    previous_allow_backdated = system_settings_service.get_bool(
        session,
        key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
        default=False,
    )
    toggled_backdated = False

    departments_by_key: dict[str, Department] = {}
    organizations_by_key: dict[str, Organization] = {}
    groups_by_department_key: dict[str, OrgGroup] = {}
    users_by_key: dict[str, User] = {}
    blocks_by_key: dict[str, WorkBlock] = {}

    try:
        if not previous_allow_backdated:
            system_settings_service.set_bool(
                session,
                key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
                value=True,
            )
            toggled_backdated = True

        global_org, registered_users_group = _ensure_global_registered_group(session)

        for dep_key, dep_name, _ in DEMO_DEPARTMENTS:
            department = Department(
                name=dep_name,
                code=f"{dep_key}-{batch_id[-4:]}",
                description=f"Демо-департамент: {dep_name}",
            )
            session.add(department)
            session.flush()
            departments_by_key[dep_key] = department
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="department",
                entity_id=department.id,
            )

        for org_key, org_name, org_description in DEMO_ORGANIZATIONS:
            organization = Organization(
                name=org_name,
                code=f"{org_key}-{batch_id[-4:]}",
                description=org_description,
                is_global=False,
            )
            session.add(organization)
            session.flush()
            organizations_by_key[org_key] = organization
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="organization",
                entity_id=organization.id,
            )

        org_key_by_department = {dep_key: org_key for dep_key, _, org_key in DEMO_DEPARTMENTS}

        for dep_key, dep_name, org_key in DEMO_DEPARTMENTS:
            department_id = departments_by_key[dep_key].id
            legacy_department_in_use = session.exec(
                select(OrgGroup.id).where(OrgGroup.legacy_department_id == department_id)
            ).first()
            group = OrgGroup(
                organization_id=organizations_by_key[org_key].id,
                name=dep_name,
                code=f"{dep_key}-GRP-{batch_id[-4:]}",
                description=f"Группа для {dep_name}",
                legacy_department_id=None if legacy_department_in_use is not None else department_id,
            )
            session.add(group)
            session.flush()
            groups_by_department_key[dep_key] = group
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="group",
                entity_id=group.id,
            )

        for block_key, block_name, department_keys, _org_key in DEMO_BLOCKS:
            block = WorkBlock(
                name=block_name,
                code=f"{block_key}-{batch_id[-4:]}",
                description="Демо-блок для проектов",
            )
            session.add(block)
            session.flush()
            blocks_by_key[block_key] = block
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="block",
                entity_id=block.id,
            )
            for department_key in department_keys:
                session.add(
                    WorkBlockDepartment(
                        block_id=block.id,
                        department_id=departments_by_key[department_key].id,
                    )
                )

        users_by_department: dict[str, list[str]] = defaultdict(list)
        for user_spec in DEMO_USERS:
            user_key = str(user_spec["key"])
            for dep_key in user_spec["department_keys"]:
                users_by_department[str(dep_key)].append(user_key)

            primary_department_key = str(user_spec["primary_department"])
            primary_group = groups_by_department_key[primary_department_key]
            user = _upsert_demo_user(
                session,
                email=str(user_spec["email"]),
                full_name=str(user_spec["full_name"]),
                department_id=departments_by_key[primary_department_key].id,
                primary_group_id=primary_group.id,
            )
            users_by_key[user_key] = user
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="user",
                entity_id=user.id,
            )

        department_leader_by_key: dict[str, str] = {}
        for dep_key in users_by_department:
            candidates = users_by_department[dep_key]
            if not candidates:
                continue
            department_leader_by_key[dep_key] = rng.choice(candidates)

        # Fixed demo leaders requested by business:
        # - Адильбек Абдыгалиев: руководитель ИБ
        # - Алексей Бойков: руководитель Офиса ИИ
        department_leader_by_key["DEP_INFOSEC"] = "adilbek_abdygaliev"
        department_leader_by_key["DEP_AI_OFFICE"] = "aleksei_boikov"

        mtszn_candidates = sorted(
            {
                *users_by_department.get("DEP_LEGAL", []),
                *users_by_department.get("DEP_MIGRATION", []),
            }
        )
        mtszn_director = (
            "gulmira_alieva"
            if "gulmira_alieva" in mtszn_candidates
            else (rng.choice(mtszn_candidates) if mtszn_candidates else None)
        )
        director_by_org = {
            "ORG_INFRA": "olzhas_anafin",
            "ORG_MTSZN": mtszn_director,
        }

        org_membership_roles: dict[tuple[int, int], str] = {}
        group_membership_roles: dict[tuple[int, int], str] = {}

        for user_spec in DEMO_USERS:
            user_key = str(user_spec["key"])
            user = users_by_key[user_key]
            user_org_keys = {
                org_key_by_department[str(dep_key)]
                for dep_key in user_spec["department_keys"]
            }
            user_org_keys.add(org_key_by_department[str(user_spec["primary_department"])])

            for org_key in sorted(user_org_keys):
                organization = organizations_by_key[org_key]
                role_name = "member"
                if director_by_org.get(org_key) == user_key:
                    role_name = "owner"
                else:
                    leads_this_org = any(
                        department_leader_by_key.get(dep_key) == user_key
                        and org_key_by_department.get(dep_key) == org_key
                        for dep_key in department_leader_by_key
                    )
                    if leads_this_org:
                        role_name = "manager"

                membership_key = (organization.id, user.id)
                current = org_membership_roles.get(membership_key, "member")
                org_membership_roles[membership_key] = _role_max(current, role_name)

            global_membership_key = (global_org.id, user.id)
            current_global = org_membership_roles.get(global_membership_key, "member")
            org_membership_roles[global_membership_key] = _role_max(current_global, "member")

            for dep_key in user_spec["department_keys"]:
                group = groups_by_department_key[str(dep_key)]
                role_name = "member"
                if department_leader_by_key.get(str(dep_key)) == user_key:
                    role_name = "manager"
                elif director_by_org.get(org_key_by_department[str(dep_key)]) == user_key:
                    role_name = "owner"

                membership_key = (group.id, user.id)
                current_role = group_membership_roles.get(membership_key, "member")
                group_membership_roles[membership_key] = _role_max(current_role, role_name)

            registered_membership_key = (registered_users_group.id, user.id)
            current_registered = group_membership_roles.get(registered_membership_key, "member")
            group_membership_roles[registered_membership_key] = _role_max(current_registered, "member")

        for (organization_id, user_id), role_name in org_membership_roles.items():
            _upsert_organization_membership(
                session,
                organization_id=organization_id,
                user_id=user_id,
                role_name=role_name,
            )

        for (group_id, user_id), role_name in group_membership_roles.items():
            _upsert_group_membership(
                session,
                group_id=group_id,
                user_id=user_id,
                role_name=role_name,
            )

        projects_by_department: dict[str, list[Project]] = defaultdict(list)

        for project_spec in DEMO_PROJECTS:
            dep_key = str(project_spec["department_key"])
            organization_key = org_key_by_department[dep_key]
            project = project_service.create_project_with_defaults(
                session,
                creator=actor,
                name=str(project_spec["name"]),
                icon=None,
                description=str(project_spec["description"]),
                organization_id=organizations_by_key[organization_key].id,
                department_id=departments_by_key[dep_key].id,
                require_close_comment=True,
                require_close_attachment=False,
                deadline_yellow_days=3,
                deadline_normal_days=5,
            )
            projects_by_department[dep_key].append(project)
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="project",
                entity_id=project.id,
            )

            block_key = next(
                key
                for key, _block_name, dep_keys, _org_key in DEMO_BLOCKS
                if dep_key in dep_keys
            )
            session.add(
                WorkBlockProject(
                    block_id=blocks_by_key[block_key].id,
                    project_id=project.id,
                )
            )

            project_member_keys = set(users_by_department.get(dep_key, []))
            if organization_key == "ORG_MTSZN":
                project_member_keys |= set(users_by_department.get("DEP_LEGAL", []))
                project_member_keys |= set(users_by_department.get("DEP_MIGRATION", []))
            director_key = director_by_org.get(organization_key)
            if director_key:
                project_member_keys.add(director_key)

            for member_key in sorted(project_member_keys):
                member_user = users_by_key[member_key]
                role = ProjectMemberRole.EXECUTOR
                if department_leader_by_key.get(dep_key) == member_key:
                    role = ProjectMemberRole.CONTROLLER
                if director_key == member_key:
                    role = ProjectMemberRole.CONTROLLER

                existing = project_repo.get_project_member(
                    session,
                    project_id=project.id,
                    user_id=member_user.id,
                )
                if existing:
                    continue
                project_repo.create_project_member(
                    session,
                    ProjectMember(
                        project_id=project.id,
                        user_id=member_user.id,
                        role=role,
                        is_active=True,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    ),
                )

            if actor.id is not None:
                existing_actor = project_repo.get_project_member(
                    session,
                    project_id=project.id,
                    user_id=actor.id,
                )
                if not existing_actor:
                    project_repo.create_project_member(
                        session,
                        ProjectMember(
                            project_id=project.id,
                            user_id=actor.id,
                            role=ProjectMemberRole.MANAGER,
                            is_active=True,
                            created_at=utcnow(),
                            updated_at=utcnow(),
                        ),
                    )

        for block_key, _block_name, dep_keys, org_key in DEMO_BLOCKS:
            manager_keys = set(
                key
                for dep_key in dep_keys
                for key in [department_leader_by_key.get(dep_key)]
                if key
            )
            director_key = director_by_org.get(org_key)
            if director_key:
                manager_keys.add(director_key)

            for manager_key in manager_keys:
                manager_user = users_by_key[manager_key]
                session.add(
                    WorkBlockManager(
                        block_id=blocks_by_key[block_key].id,
                        user_id=manager_user.id,
                        is_active=True,
                    )
                )

        for dep_key, projects in projects_by_department.items():
            if not projects:
                continue
            assignee_pool = sorted(users_by_department.get(dep_key, []))
            if not assignee_pool:
                continue

            organization_key = org_key_by_department[dep_key]
            fallback_controller_key = director_by_org.get(organization_key)
            controller_key = department_leader_by_key.get(dep_key) or fallback_controller_key
            if not controller_key:
                controller_key = assignee_pool[0]

            for task_index, blueprint in enumerate(DEMO_TASK_BLUEPRINTS):
                project = projects[task_index % len(projects)]
                statuses = _status_map(session, project.id)
                assignee_key = _pick_weighted_assignee_key(assignee_pool, task_index)
                assignee = users_by_key[assignee_key]
                controller = users_by_key[controller_key]

                due_date = utcnow() + timedelta(days=blueprint["due_delta_days"] + (task_index % 2))
                task = task_service.create_task(
                    session,
                    project=project,
                    creator=actor,
                    title=str(blueprint["title"]),
                    description=blueprint["description"],
                    assignee_id=assignee.id,
                    controller_id=controller.id,
                    due_date=due_date,
                )
                _register_entity(
                    session,
                    batch_id=batch_id,
                    entity_type="task",
                    entity_id=task.id,
                )

                task_service.add_task_comment(
                    session,
                    task=task,
                    actor=assignee,
                    comment=str(blueprint["comment"]),
                )

                status_code = str(blueprint["status_code"])
                if status_code == "review":
                    target_status = statuses.get("review")
                    if target_status and target_status.id != task.workflow_status_id:
                        task = task_service.update_task(
                            session,
                            task=task,
                            actor=controller,
                            project=project,
                            workflow_status_id=target_status.id,
                        )
                elif status_code == "done":
                    task_service.close_task(
                        session,
                        task=task,
                        actor=controller,
                        project=project,
                        close_comment="Задача закрыта в рамках демо-сценария",
                        attachment_ids=[],
                    )

        for special_task_spec in DEMO_SPECIAL_TASKS:
            dep_key = str(special_task_spec["department_key"])
            projects = projects_by_department.get(dep_key, [])
            if not projects:
                continue

            project = next(
                (
                    item
                    for item in projects
                    if item.name == str(special_task_spec["project_name"])
                ),
                projects[0],
            )

            assignee_key = str(special_task_spec["assignee_key"])
            controller_key = str(special_task_spec["controller_key"])
            creator_key = str(special_task_spec["creator_key"])
            assignee = users_by_key.get(assignee_key)
            controller = users_by_key.get(controller_key)
            creator = users_by_key.get(creator_key)
            if not assignee or not controller or not creator:
                continue

            due_date = special_task_spec["due_date"]
            task = task_service.create_task(
                session,
                project=project,
                creator=creator,
                title=str(special_task_spec["title"]),
                description=str(special_task_spec["description"]),
                assignee_id=assignee.id,
                controller_id=controller.id,
                due_date=due_date,
            )
            _register_entity(
                session,
                batch_id=batch_id,
                entity_type="task",
                entity_id=task.id,
            )

            close_comment = str(special_task_spec.get("close_comment") or "").strip()
            closed_at = special_task_spec.get("closed_at")
            if close_comment:
                task_service.add_task_comment(
                    session,
                    task=task,
                    actor=assignee,
                    comment=close_comment,
                )

            if closed_at is not None:
                task = task_service.close_task(
                    session,
                    task=task,
                    actor=controller,
                    project=project,
                    close_comment=close_comment or "Задача закрыта в рамках демо-сценария",
                    attachment_ids=[],
                )

            created_at = special_task_spec.get("created_at")
            if created_at is None:
                created_at = utcnow() - timedelta(days=20)
            task.created_at = created_at
            task.updated_at = closed_at or created_at
            if closed_at is not None:
                task.closed_at = closed_at
            session.add(task)

        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Demo data creation conflict: {exc.orig}",
        ) from exc
    finally:
        if toggled_backdated:
            system_settings_service.set_bool(
                session,
                key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
                value=previous_allow_backdated,
            )

    return _demo_summary(session)


def get_demo_data_summary(session: Session) -> DemoDataSummary:
    return _demo_summary(session)


def set_demo_data_enabled(
    session: Session,
    *,
    actor: User,
    enabled: bool,
) -> DemoDataSummary:
    if enabled:
        return populate_demo_data(session, actor)
    return clear_demo_data(session)
