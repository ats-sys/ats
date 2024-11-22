import datetime

from ats.database.models.job import Job
from ats.database.models.generic_storage import GenericStorage
from ats.exceptions.query_exceptions import NoDataFoundException, QueryFormatException
from ats.exceptions.job_config_exception import OperationNotAllowedException


def create(val: dict) -> dict:
    """
    Creates a key val pair and returns the key
    Args:
        val: Config as a dict

    Returns:
        Returns the config ID
    """
    model_obj = GenericStorage(val=val)

    id = model_obj.create()

    return {"id": id}


def update(id: str, val: dict):
    model_obj = GenericStorage(val=val)

    is_updated = model_obj.update(id)

    if is_updated:
        return {"message": "Updated."}

    raise NoDataFoundException(f"No records found for {id}.")


def delete(id_str: str):
    if id_str is None:
        raise QueryFormatException("'id' is not defined.")

    record = GenericStorage.find_one(id_str=id_str);

    if record is None:
        raise NoDataFoundException(f"No records found for {id_str}.")

    is_deleted = GenericStorage.delete(id_str)

    if is_deleted:
        return {"message": "Deleted."}

    raise NoDataFoundException(f"Couldn't delete the record")


def get(id_str: str):
    record = GenericStorage.find_one(id_str)

    if record is None:
        raise NoDataFoundException(f"No records found for {id_str}.")
    data = dict(record.val)
    data['id'] = record.id
    return data


def get_list():
    val_list = []

    for config_model_obj in GenericStorage.find():
        val = dict(config_model_obj.val)
        val['id'] = config_model_obj.id
        val_list.append(val)
    return val_list
