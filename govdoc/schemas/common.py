"""GovDoc 领域模型共用基类。"""

from pydantic import BaseModel, ConfigDict


class GovDocModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

