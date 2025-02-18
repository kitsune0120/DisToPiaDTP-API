# distopia_api/models/models.py

from sqlalchemy import Column, Integer, String, Boolean
from distopia_api.database import Base

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    species = Column(String)
    ability = Column(String)
    attack_power = Column(Integer)
    defense_power = Column(Integer)
    new = Column(Boolean, default=True)

class Species(Base):
    __tablename__ = "species"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    abilities = Column(String)
    new = Column(Boolean, default=True)

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    climate = Column(String)
    new = Column(Boolean, default=True)
