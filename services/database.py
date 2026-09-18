#imports
import asyncio
import asyncpg
from sqlalchemy import select, update, delete, or_, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, SmallInteger, Date, func, CheckConstraint, Sequence, ForeignKey, UniqueConstraint, ARRAY, String, TypeDecorator
from dotenv import load_dotenv
from os import getenv
from enum import IntEnum
from datetime import date
from typing import List, TypeVar, Generic, Sequence
from cryptography.fernet import Fernet

load_dotenv()


DB_URL = f"postgresql+asyncpg://{getenv('DB_USER')}:{getenv('DB_PASS')}@127.0.0.1:{getenv('DB_PORT')}/test_db"
engine = create_async_engine(DB_URL, echo=True)


async_session = async_sessionmaker(engine, expire_on_commit=False)

SECRET_KEY = getenv("DB_ENC_KEY").encode()
cipher = Fernet(SECRET_KEY)

#----------Encryption-------------

class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            enc_bytes = cipher.encrypt(value.encode("utf-8"))
            return enc_bytes.decode("utf-8")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            dec_bytes = cipher.decrypt(value.encode("utf-8"))
            return dec_bytes.decode("utf-8")
        return value

#-----------------TABLES--------------------

class BaseModel(DeclarativeBase):
    pass

class AcademicRole(IntEnum):
    USER = 0
    STUDENT = 1
    PRAEPOSITOR = 2
    TEACHER = 3
    DEPUTY = 4

class AdminRole(IntEnum):
    NONE = 0
    HELPER = 1
    ADMIN = 2

class UserModel(BaseModel):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=False,
        nullable=True
    )
    full_name: Mapped[str] = mapped_column(
        nullable=True,
        unique=False
    )
    tg_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True
    )
    vk_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True
    )
    academic_role: Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "academic_role BETWEEN 0 AND 4",
            name="academic_role_range"
        ),
        nullable=False,
        unique=False,
        default=AcademicRole.USER
    )
    admin_role:Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "admin_role BETWEEN 0 AND 2",
            name="admin_role_range"
        ),
        default=AdminRole.NONE,
        nullable=False,
        unique=False
    )

    __table_args__ = (
        CheckConstraint(
            "tg_id IS NOT NULL OR vk_id IS NOT NULL",
            name="check_user_tg_vk"
        )
    )

class GroupModel(BaseModel):
    __tablename__="groups"

    id: Mapped[int] = mapped_column(
        autoincrement=True,
        primary_key=True
    )
    designation: Mapped[str] = mapped_column(
        unique=True,
        nullable=False
    )
    tg_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True
    )
    vk_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "tg_id IS NOT NULL OR vk_id IS NOT NULL",
            name="check_group_tg_vk"
        )
    )

class SubjectModel(BaseModel):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(
        autoincrement=True,
        primary_key=True
    )
    title: Mapped[str] = mapped_column(
        nullable=False,
        unique=False
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey(
            "groups.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "group_id","title", 
            name="uniq_subj_groupid_title"
        )
    )

class ScheduleModel(BaseModel):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(
        autoincrement=True,
        primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey(
            "groups.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    subj_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subjects.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    period: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        unique=False
    )
    classroom:Mapped[str] = mapped_column(
        nullable=True,
        unique=False
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=False
    )

    __table_args__ = (
        UniqueConstraint(
            "group_id","period","date",
            name="uniq_schedule_groupid_period_date"
        )
    )

class GradeModel(BaseModel):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(
        autoincrement=True,
        primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey(
            "schedule.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    grade: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        unique=False
    )

    __table_args__ = (
        CheckConstraint(
            "grade BETWEEN 1 AND 5",
            name="check_grade"
        )
    )

class HomeworkModel(BaseModel):
    __tablename__ = "homework"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subjects.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    task: Mapped[str] = mapped_column(
        EncryptedString,
        unique=False,
        nullable=False
    )
    attachment: Mapped[list[str]] = mapped_column(
        ARRAY(EncryptedString),
        default=list,
        nullable=False
    )

class ArchiveHomeworkModel(BaseModel):
    __tablename__ = "archive_homework"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey(
            "schedule.id",
            ondelete="CASCADE"
        )
    )
    task: Mapped[str] = mapped_column(
        EncryptedString,
        unique=False,
        nullable=False
    )
    attachment: Mapped[list[str]] = mapped_column(
        ARRAY(EncryptedString),
        default=list,
        nullable=False
    )

class DownloadHistoryModel(BaseModel):
    __tablename__ = "download_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    doc_id:Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True
    )


#----------REPOS-----------

T = TypeVar('T')
        
class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by(self, **kwargs) -> T | None:
        filters = [getattr(self.model, k) == v for k,v in kwargs.items() if v is not None]
        stmt = select(self.model).where(and_(*filters))
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all_by(self, **kwargs) -> Sequence[T]:
        stmt = select(self.model)
        filters = [getattr(self.model,k) == v for k,v in kwargs.items() if v is not None]

        if not filters:
            return []
        
        stmt.where(and_(*filters))
        result = await self.session.execute(stmt)

        return result.scalars().all()

    async def delete_by(self, **kwargs) -> bool:
        filters = [getattr(self.model,k) == v for k,v in kwargs.items() if v is not None]

        if not filters:
            return False
        
        stmt = delete(self.model).where(and_(*filters))
        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    async def add(self, **kwargs) -> T:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.commit()

        return obj

    async def update_by(self, filters:dict, values:dict) -> int:
        filters_stand = [getattr(self.model, k) == v for k,v in filters.items() if v is not None]

        if not filters_stand:
            return 0
        
        stmt = self.session.update(self.model).where(and_(*filters_stand)).values(**values)

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount
    

class UserRepository(BaseRepository[UserModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(UserModel, session)

    async def ensure(self,
        group_id:int | None = None,
        full_name:str | None = None,
        tg_id:int | None = None,
        vk_id:int | None = None,
        academic_role:int | None = None,
        admin_role:int | None = None
    ) -> UserModel:
        
        if not any((tg_id,vk_id)):
            raise ValueError("Нужно указать хотя-бы одно из полей: tg_id, vk_id")

        search_ids = {k:v for k,v in {"tg_id":tg_id, "vk_id":vk_id}.items() if v is not None}

        user = await self.get_by(**search_ids)

        if user:
            if not user.group_id and group_id:
                user.group_id = group_id

            if not user.full_name and full_name:
                user.full_name = full_name

            if not user.tg_id and tg_id:
                user.tg_id = tg_id

            if not user.vk_id and vk_id:
                user.vk_id = vk_id

            if not user.academic_role and academic_role:
                user.academic_role = academic_role

            if not admin_role and admin_role:
                user.admin_role = admin_role

            await self.session.commit()
            return user

        params = locals()
        params.pop("self")
        params_clean = {k:v for k,v in params.items() if v is not None}

        return await self.add(**params_clean)
    

        
        

        

        

class GroupRepository(BaseRepository[GroupModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(GroupModel, session)

    



class SubjectRepository(BaseRepository[SubjectModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(SubjectModel, session)


class ScheduleRepository(BaseRepository[ScheduleModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(ScheduleModel, session)


class GradeRepository(BaseRepository[GradeModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(GradeModel, session)


class HomeworkRepository(BaseRepository[HomeworkModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(HomeworkModel, session)


class ArchiveRepository(BaseRepository[ArchiveHomeworkModel]):
    def __init__(self, session:AsyncSession):
        super().__init__(ArchiveHomeworkModel, session)

class DownloadHistoryRepository(BaseRepository[DownloadHistoryModel]):
    def __init__(self, session:AsyncSession):
        super().__init__(DownloadHistoryModel, session)

class Database:
    def __init__(self, session: AsyncSession):
        self.session = session

        self.users = UserRepository(session=self.session)
        self.groups = GroupRepository(session=self.session)
        self.subjects = SubjectRepository(session=self.session)
        self.schedule = ScheduleRepository(session=self.session)
        self.grades = GradeRepository(session=self.session)
        self.homework = HomeworkRepository(session=self.session)
        self.archive_homework = ArchiveRepository(session=self.session)
        self.download_history = DownloadHistoryRepository(session=self.session)