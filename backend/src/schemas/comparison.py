from pydantic import BaseModel,Field,ConfigDict
class ComparisonInput(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 name:str=Field(min_length=2,max_length=160)
 baseline_run_id:str
 retest_run_id:str
