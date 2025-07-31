from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.declarative import declared_attr


class Base(DeclarativeBase):
    """基础模型类，所有模型都继承此类"""
    
    @declared_attr
    def __tablename__(cls) -> str:
        """自动生成表名：将类名转换为小写下划线格式"""
        name = cls.__name__
        # 将大写字母前加下划线（除了第一个字母）
        result = []
        for i, char in enumerate(name):
            if i > 0 and char.isupper():
                result.append('_')
            result.append(char.lower())
        return ''.join(result)
    
    # 通用时间戳字段
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )
    
    def __repr__(self):
        """通用的 repr 方法"""
        attrs = []
        for key in self.__mapper__.columns.keys():
            value = getattr(self, key)
            if value is not None:
                attrs.append(f"{key}={value!r}")
        return f"{self.__class__.__name__}({', '.join(attrs[:3])}...)"