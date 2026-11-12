from sqlalchemy import String,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
from src.config.json_type import PreciseJSON as JSON
class RunComparison(Base):
 __tablename__='run_comparisons'
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 name:Mapped[str]=mapped_column(String(160),unique=True)
 baseline_run_id:Mapped[str]=mapped_column(ForeignKey('envelope_runs.id'))
 retest_run_id:Mapped[str]=mapped_column(ForeignKey('envelope_runs.id'))
 # 创建时冻结双方来源（运行/研究/测组/口径摘要）与完整差异结果，之后不随源数据重算。
 baseline_source:Mapped[dict]=mapped_column(JSON)
 retest_source:Mapped[dict]=mapped_column(JSON)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 checksum:Mapped[str]=mapped_column(String(96),default='')
 created_by:Mapped[str]=mapped_column(String(160))
 created_at:Mapped[str]=mapped_column(String(64))
