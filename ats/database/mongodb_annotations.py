from ats.exceptions.model_exceptions import InvalidRelationConfigException
from ats.database.models.base_model import BaseModel


class AnnotatedVariableMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        # Get the metadata for the variable.
        metadata = attrs.pop("metadata", {})

        # Create a new class with the metadata attached.
        new_class = type.__new__(mcs, name, bases, attrs)

        # Set the metadata property on the new class.
        new_class.metadata = metadata

        return new_class


def relation_config(relation: dict):
    """
    Relation config definition metaclass
    Args:
        relation: Relation is defined as a dict containing model and type
                    - model: class extending from the BaseModel
                    - type: "many_to_one" or "one_to_many" ("one_to_one" is handled as a special case of many_to_one)
                        TODO: Implement "one_to_many"
    Returns:
        Returns the same variable that was decorated using the decorator
    """
    def decorator(variable):
        if not isinstance(relation, dict) or 'model' not in relation or 'type' not in relation:
            raise InvalidRelationConfigException("'relation' must be a dict with keys 'mode' and 'type'")
        if not issubclass(relation["model"], BaseModel):
            raise InvalidRelationConfigException("'model' must be a subclass of BaseModel.")
        variable.__class__ = AnnotatedVariableMetaclass(variable.__name__, (object,), {"relation": relation})
        return variable
    return decorator

