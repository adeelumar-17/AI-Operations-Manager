'''
This file defines the base class for SQLAlchemy models using the Declarative system. All models in the application should inherit from this Base class to ensure they are properly registered with SQLAlchemy's ORM.

class: Base - A subclass of DeclarativeBase that serves as the base for all SQLAlchemy models in the application.
'''
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass