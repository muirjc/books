"""SQLAlchemy models for the nine tables in data-model.md.

Every constraint and index is named explicitly so services can map ``IntegrityError`` to a
conflict code by constraint name (research R9). Migration 0001 creates the same schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def _user_fk(name: str) -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="RESTRICT", name=name),
        nullable=False,
    )


# --------------------------------------------------------------------------- accounts


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('member', 'admin')", name="app_user_role_check"),
        Index("app_user_login_lower_uq", func.lower(sql_text("login")), unique=True),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    login: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(10), nullable=False, default="member", server_default="member"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (
        UniqueConstraint("token_hash", name="user_session_token_hash_key"),
        Index("user_session_user_id_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE", name="user_session_user_id_fkey"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    user: Mapped[AppUser] = relationship(lazy="joined", innerjoin=True)


class LoginThrottle(Base):
    __tablename__ = "login_throttle"
    __table_args__ = (
        CheckConstraint("failed_count >= 0", name="login_throttle_failed_count_check"),
    )

    login_key: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    failed_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- catalog


class Author(Base):
    __tablename__ = "author"
    __table_args__ = (
        CheckConstraint(
            "real_name IS NULL OR is_pen_name", name="author_real_name_requires_pen_name"
        ),
        Index("author_name_lower_uq", func.lower(sql_text("name")), unique=True),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_pen_name: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    real_name: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID] = _user_fk("author_created_by_fkey")
    updated_by: Mapped[uuid.UUID] = _user_fk("author_updated_by_fkey")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    created_by_user: Mapped[AppUser] = relationship(
        foreign_keys=[created_by], lazy="joined", innerjoin=True
    )
    updated_by_user: Mapped[AppUser] = relationship(
        foreign_keys=[updated_by], lazy="joined", innerjoin=True
    )


class Series(Base):
    __tablename__ = "series"
    __table_args__ = (Index("series_name_lower_uq", func.lower(sql_text("name")), unique=True),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[uuid.UUID] = _user_fk("series_created_by_fkey")
    updated_by: Mapped[uuid.UUID] = _user_fk("series_updated_by_fkey")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    created_by_user: Mapped[AppUser] = relationship(
        foreign_keys=[created_by], lazy="joined", innerjoin=True
    )
    updated_by_user: Mapped[AppUser] = relationship(
        foreign_keys=[updated_by], lazy="joined", innerjoin=True
    )


class Book(Base):
    __tablename__ = "book"
    __table_args__ = (
        CheckConstraint(
            "series_number IS NULL OR series_id IS NOT NULL",
            name="book_series_number_requires_series",
        ),
        CheckConstraint(
            "series_number IS NULL OR (series_number >= 0 AND series_number <= 999.99)",
            name="book_series_number_range",
        ),
        CheckConstraint("isbn_13 IS NULL OR isbn_13 ~ '^[0-9]{13}$'", name="book_isbn_13_format"),
        UniqueConstraint("isbn_13", name="book_isbn_13_key"),
        Index(
            "book_series_number_uq",
            "series_id",
            "series_number",
            unique=True,
            postgresql_where=sql_text("series_id IS NOT NULL AND series_number IS NOT NULL"),
        ),
        Index("book_series_id_idx", "series_id"),
        Index(
            "book_release_date_idx",
            "release_date",
            postgresql_where=sql_text("release_date IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="RESTRICT", name="book_series_id_fkey")
    )
    series_number: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    isbn_13: Mapped[str | None] = mapped_column(CHAR(13))
    release_date: Mapped[date | None] = mapped_column(Date)  # spec 007
    created_by: Mapped[uuid.UUID] = _user_fk("book_created_by_fkey")
    updated_by: Mapped[uuid.UUID] = _user_fk("book_updated_by_fkey")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    series: Mapped[Series | None] = relationship(lazy="joined")
    author_links: Mapped[list[BookAuthor]] = relationship(
        lazy="selectin",
        order_by="BookAuthor.position",
        cascade="all, delete-orphan",
        back_populates="book",
    )
    current_summary: Mapped[BookSummary | None] = relationship(
        primaryjoin="and_(BookSummary.book_id == Book.id, BookSummary.is_current)",
        viewonly=True,
        uselist=False,
        lazy="selectin",
    )
    created_by_user: Mapped[AppUser] = relationship(
        foreign_keys="Book.created_by", lazy="joined", innerjoin=True
    )
    updated_by_user: Mapped[AppUser] = relationship(
        foreign_keys="Book.updated_by", lazy="joined", innerjoin=True
    )


class BookAuthor(Base):
    __tablename__ = "book_author"
    __table_args__ = (
        CheckConstraint("position >= 1", name="book_author_position_check"),
        UniqueConstraint("book_id", "position", name="book_author_position_key"),
        Index("book_author_author_id_idx", "author_id"),
    )

    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book.id", ondelete="CASCADE", name="book_author_book_id_fkey"),
        primary_key=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("author.id", ondelete="RESTRICT", name="book_author_author_id_fkey"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    book: Mapped[Book] = relationship(back_populates="author_links")
    author: Mapped[Author] = relationship(lazy="joined", innerjoin=True)


class BookSummary(Base):
    __tablename__ = "book_summary"
    __table_args__ = (
        CheckConstraint(
            "origin IN ('ai', 'ai_edited', 'manual')", name="book_summary_origin_check"
        ),
        CheckConstraint(
            "origin = 'manual' OR model IS NOT NULL", name="book_summary_ai_model_check"
        ),
        Index(
            "book_summary_current_uq",
            "book_id",
            unique=True,
            postgresql_where=sql_text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book.id", ondelete="CASCADE", name="book_summary_book_id_fkey"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    source_urls: Mapped[list[Any] | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = _user_fk("book_summary_created_by_fkey")
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    created_by_user: Mapped[AppUser] = relationship(lazy="joined", innerjoin=True)


class BookSourceRef(Base):
    """Which external record a catalog book was imported from (spec 002 FR-009)."""

    __tablename__ = "book_source_ref"
    __table_args__ = (
        CheckConstraint("source IN ('open_library')", name="book_source_ref_source_check"),
        CheckConstraint(
            "source <> 'open_library' OR source_work_id ~ '^OL[0-9]+W$'",
            name="book_source_ref_open_library_id_format",
        ),
        UniqueConstraint("source", "source_work_id", name="book_source_ref_source_work_key"),
        UniqueConstraint("book_id", "source", name="book_source_ref_book_source_key"),
        Index("book_source_ref_book_id_idx", "book_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book.id", ondelete="CASCADE", name="book_source_ref_book_id_fkey"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_work_id: Mapped[str] = mapped_column(String(40), nullable=False)
    imported_by: Mapped[uuid.UUID] = _user_fk("book_source_ref_imported_by_fkey")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceLookupCache(Base):
    """Open Library answers reused for 24 hours; outside the catalog (spec 002 FR-017)."""

    __tablename__ = "source_lookup_cache"
    __table_args__ = (
        CheckConstraint("source IN ('open_library')", name="source_lookup_cache_source_check"),
        CheckConstraint(
            "kind IN ('author_search', 'author_works')", name="source_lookup_cache_kind_check"
        ),
        CheckConstraint("expires_at > fetched_at", name="source_lookup_cache_expiry_check"),
        Index("source_lookup_cache_expires_at_idx", "expires_at"),
    )

    source: Mapped[str] = mapped_column(String(20), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    lookup_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- personal


class ReadingEntry(Base):
    __tablename__ = "reading_entry"
    __table_args__ = (
        CheckConstraint(
            "status IN ('want_to_read', 'reading', 'finished')", name="reading_entry_status_check"
        ),
        CheckConstraint(
            "finished_on IS NULL OR finished_on >= DATE '1900-01-01'",
            name="reading_entry_finished_on_check",
        ),
        CheckConstraint("times_read BETWEEN 0 AND 99", name="reading_entry_times_read_check"),
        UniqueConstraint("user_id", "book_id", name="reading_entry_user_book_key"),
        Index("reading_entry_user_id_idx", "user_id"),
        Index("reading_entry_book_id_idx", "book_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="RESTRICT", name="reading_entry_user_id_fkey"),
        nullable=False,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book.id", ondelete="RESTRICT", name="reading_entry_book_id_fkey"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="finished", server_default="finished"
    )
    finished_on: Mapped[date | None] = mapped_column(Date)
    times_read: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    pre_ordered: Mapped[bool] = mapped_column(  # spec 007
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    book: Mapped[Book] = relationship(lazy="joined", innerjoin=True)
