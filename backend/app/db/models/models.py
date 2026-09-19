from sqlalchemy import Column, Integer, String, DateTime, Text, func, ForeignKey

from app.db.engine import Base


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    # JSON text: {"thinking": {"mode","capability","strategy","notes"}}
    config = Column(Text, nullable=True, default=None)