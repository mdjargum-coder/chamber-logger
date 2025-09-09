from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
from datetime import datetime

class ChamberLog(Base):
    __tablename__ = "chamber_logs"

    id = Column(Integer, primary_key=True, index=True)
    tanggal = Column(String, index=True)
    waktu = Column(String, index=True)
    humidity1 = Column(Float)
    temperature1 = Column(Float)
    humidity2 = Column(Float)
    temperature2 = Column(Float)
    status = Column(String, default="OFF")
    created_at = Column(DateTime, default=datetime.utcnow)
