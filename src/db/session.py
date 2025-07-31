from contextlib import contextmanager
from typing import Iterator
from sqlalchemy.orm import Session
from .config import SessionLocal


@contextmanager
def get_db() -> Iterator[Session]:
    """
    获取数据库会话的上下文管理器
    
    使用示例:
        with get_db() as db:
            # 使用 db 进行数据库操作
            pass
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    获取数据库会话（需要手动关闭）
    
    使用示例:
        db = get_db_session()
        try:
            # 使用 db 进行数据库操作
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    """
    return SessionLocal()