import datetime

from bson.objectid import ObjectId
from ats.database.models.base_model import BaseModel
from pydantic import field_validator, model_validator
from typing import Literal
from typing import List, Optional, Union, Any
from ats.exceptions.model_exceptions import ValidationException
from datetime import datetime
from pydantic import Field


class GenericStorage(BaseModel):
    val: Any
    status: bool = True

    @classmethod
    def get_collection_name(cls):
        return 'generic_storage'
