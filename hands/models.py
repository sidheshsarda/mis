from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, DECIMAL, TIMESTAMP, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TblDailyHandCompData(Base):
    """Model for tbl_daily_hand_comp_data table in EMPMILL12 database."""
    
    __tablename__ = "tbl_daily_hand_comp_data"
    __table_args__ = {"schema": "EMPMILL12"}

    tran_date = Column(Date, primary_key=True)
    desig_id = Column(Integer, primary_key=True)
    shift_a = Column(DECIMAL(7, 2), default=0.00)
    shift_b = Column(DECIMAL(7, 2), default=0.00)
    shift_c = Column(DECIMAL(7, 2), default=0.00)
    shift_g = Column(DECIMAL(7, 2), default=0.00)
    ot_hands = Column(DECIMAL(7, 2), default=0.00)
    updated = Column(Integer, default=1)
    excess_hands = Column(DECIMAL(7, 2))
    short_hands = Column(DECIMAL(7, 2))
    updated_on = Column(TIMESTAMP)
    locked_data = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    company_id = Column(Integer)
    branch_id = Column(Integer)
    target_a = Column(DECIMAL(7, 2), default=0.00)
    target_b = Column(DECIMAL(7, 2), default=0.00)
    target_c = Column(DECIMAL(7, 2), default=0.00)

    def __repr__(self):
        return f"<TblDailyHandCompData(tran_date={self.tran_date}, desig_id={self.desig_id})>"


class OccupationMasterNorms(Base):
    """Model for OCCUPATION_MASTER_NORMS table in EMPMILL12 database."""
    
    __tablename__ = "OCCUPATION_MASTER_NORMS"
    __table_args__ = {"schema": "EMPMILL12"}

    HOCCU_ID = Column(Integer, primary_key=True)
    HOCCU_CODE = Column(String(6))
    OCCU_DESC = Column(String(40))
    DEPT_ID = Column(Integer)
    COST_DESC = Column(String(25))
    DIRECT_INDIRECT = Column(String(1))
    VARIABLE_FIXED = Column(String(20))
    SHIFT_A = Column(Integer)
    SHIFT_B = Column(Integer)
    SHIFT_C = Column(Integer)
    SHIFT_G = Column(Integer)
    NO_MC = Column(Integer)
    HANDS_MC = Column(Integer)
    RE_CALC = Column(String(1))
    MC_CODE = Column(String(6))
    ROUND_OFF = Column(DECIMAL(5, 2))
    TIME_PIECE = Column(String(1))
    NORMS = Column(String(40))
    ACTIVE = Column(String(1))
    desig_id = Column(Integer)
    company_id = Column(Integer)
    branch_id = Column(Integer)
    OCCU_CODE = Column(String(10))
    OCCU_SHR_NAME = Column(String(10))

    def __repr__(self):
        return f"<OccupationMasterNorms(HOCCU_ID={self.HOCCU_ID}, OCCU_DESC={self.OCCU_DESC})>"


class Designation(Base):
    """Model for designation table in vowsls database."""
    
    __tablename__ = "designation"
    __table_args__ = {"schema": "vowsls"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger)
    cost_code = Column(String(255))
    cost_description = Column(String(255))
    created_by = Column(BigInteger)
    auto_datetime_insert = Column(DateTime)
    department = Column(BigInteger)
    desig = Column(String(255))
    direct_indirect = Column(String(255))
    machine_type = Column(String(255))
    mod_by = Column(String(255))
    mod_on = Column(DateTime)
    no_of_machines = Column(String(255))
    norms = Column(String(255))
    on_machine = Column(String(255))
    piece_rate_type = Column(String(255))
    time_piece = Column(String(255))

    def __repr__(self):
        return f"<Designation(id={self.id}, desig={self.desig})>"


class DepartmentMaster(Base):
    """Model for department_master table in vowsls database."""
    
    __tablename__ = "department_master"
    __table_args__ = {"schema": "vowsls"}

    dept_id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    dept_code = Column(String(255))
    dept_desc = Column(String(255))
    mast_dept_code = Column(String(255))
    mdept_id = Column(Integer)
    org_id = Column(BigInteger)
    updated = Column(DateTime)
    user_id = Column(Float)
    auto_datetime_insert = Column(DateTime)
    created_by = Column(String(255))

    def __repr__(self):
        return f"<DepartmentMaster(dept_id={self.dept_id}, dept_desc={self.dept_desc})>"


class MasterDepartment(Base):
    """Model for master_department table in vowsls database."""
    
    __tablename__ = "master_department"
    __table_args__ = {"schema": "vowsls"}

    rec_id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    created_by = Column(String(255))
    dept_desc = Column(String(255))
    mdept_id = Column(BigInteger)
    dept_code = Column(String(255))
    updated = Column(DateTime)
    order_id = Column(Integer)
    user_id = Column(Integer)
    auto_datetime_insert = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<MasterDepartment(rec_id={self.rec_id}, dept_desc={self.dept_desc})>"
