"""Session factory bound to a durable-state engine."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .engine import DbEngine


class DbSessionFactory:
    """Produce short-lived SQLAlchemy sessions for a data home."""

    def __init__(
        self,
        home: Optional[Path] = None,
        *,
        engine: Optional[Engine] = None,
    ) -> None:
        self._engine = engine or DbEngine(home).create()
        self._factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def session(self) -> Session:
        return self._factory()

    @contextmanager
    def begin(self) -> Iterator[Session]:
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
