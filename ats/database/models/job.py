import datetime

from bson.objectid import ObjectId
from ats.database.models.base_model import BaseModel
from pydantic import field_validator, model_validator
from typing import Literal
from typing import List, Optional, Union
from ats.exceptions.model_exceptions import ValidationException
from datetime import datetime
from pydantic import Field


class Job(BaseModel):
    name: str
    datetime: Optional[datetime]
    config: dict
    status: bool = True
    state: Optional[Literal["RUNNING", "TERMINATED", "STOPPED", "IDLE"]] = None

    @classmethod
    def get_collection_name(cls):
        return 'job'
