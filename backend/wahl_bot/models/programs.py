from db.session import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="program")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    program_name = Column(String, ForeignKey("programs.name"), index=True)
    page = Column(Integer, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # Assuming 384-dimensional embeddings
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    program = relationship("Program", back_populates="document")
