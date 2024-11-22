from typing import List, Optional
from pydantic import BaseModel as PyDanticBaseModel, field_validator, json, Extra
from ats.database.mongodb_connection import MongodbConnection
from ats.exceptions.model_exceptions import ValidationException, InvalidRelationConfigException, InvalidRelationException

from bson.objectid import ObjectId

mongo_db = MongodbConnection()


from pydantic import BaseModel, json
from typing import Union


class BaseModel(PyDanticBaseModel):
    id: Optional[str] = None

    class Config:
        from_attributes = True
        extra = Extra.allow

    # def dict(self, **kwargs):
    #     d = super().dict(**kwargs)
    #     if hasattr(self, 'id'):
    #         d['id'] = str(d['id'])  # Convert _id to a string
    #     return d

    @classmethod
    def is_embedded_model(cls):
        return False

    @classmethod
    def get_collection_name(cls):
        return 'root'

    @classmethod
    def get_mongo_connection(cls):
        return mongo_db

    @classmethod
    def get_mongo_collection(cls):
        return cls.get_mongo_connection().db[cls.get_collection_name()]

    @classmethod
    def str_to_mongo_id(cls, id_str: str):
        return ObjectId(id_str)

    def create(self):
        """
        Creates an entry in mongodb
        Returns:
            Returns the mongo id as a string
        """
        if self.is_embedded_model():
            raise ValidationException('Embedded models cannot be inserted directly.')

        data_dict = self.model_dump()

        if 'id' in data_dict:
            del data_dict['id']

        return str(self.get_mongo_collection().insert_one(data_dict).inserted_id)

    def update(self, id_str: str = None):
        """
        Updates a record with a given data
        Args:
            id_str: Mongo ID as a string

        Returns:
            True if updated
        """
        if id_str is None:
            id_str = self.id

        if self.is_embedded_model():
            raise ValidationException('Embedded models cannot be updated directly.')

        data_dict = self.model_dump()

        if 'id' in data_dict:
            del data_dict['id']

        # Delete None values
        data_dict = {key: value for key, value in data_dict.items() if value is not None}

        result = self.get_mongo_collection().update_one(
            {'_id': self.str_to_mongo_id(id_str), 'status': True},
            {"$set": data_dict}
        )

        return True if result.matched_count > 0 else False

    @classmethod
    def delete(cls, id_str: str):
        """
        Delete a record by putting status = False for a given Mongo Id
        Args:
            id_str: Mongo Id as a string

        Returns:
            True if deleted, else False

        """
        if cls.is_embedded_model():
            raise ValidationException('Embedded models cannot be deleted directly.')

        # Use the collection.update_one method to update the document with the specified _id
        result = cls.get_mongo_collection().update_one(
            {'_id': cls.str_to_mongo_id(id_str), 'status': True},
            {"$set": {'status': False}}
        )
        return True if result.modified_count > 0 else False

    @classmethod
    def find_one(cls, id_str: str, include_relations: bool = False):
        """
        Find a single record for a given Mongo ID
        Args:
            id_str: Mongo ID as a string
            include_relations: bool, if set to True, the models referred by relations will be part of the returned object

        Returns:
            Object if found or else None
        """
        if cls.is_embedded_model():
            raise ValidationException('Embedded models cannot be queried directly.')

        data = cls.get_mongo_collection().find_one({'_id': cls.str_to_mongo_id(id_str), 'status': True})

        if data is None:
            return None

        data['id'] = str(data['_id'])
        del data['_id']
        model_obj =  cls(**data)

        if include_relations:
            relations = cls.get_relations()
            for relation in relations:
                cls._add_relation_field(relation, model_obj)

        return model_obj

    @classmethod
    def find(cls, criteria: dict = None, include_relations: bool = False):
        """
        Find a record by a given criteria
        Args:
            criteria: Criteria as a dict
            include_relations: bool, if set to True, the models referred by relations will be part of the returned objects

        Returns:
            List of found objects
        """
        if cls.is_embedded_model():
            raise ValidationException('Embedded models cannot be queried directly.')

        cls._validate_relations()

        items = []

        criteria_query = criteria if isinstance(criteria, dict) else {}

        criteria_query['status'] = True

        cursor = cls.get_mongo_collection().find(criteria_query)
        for item_data in cursor:
            # Parse and validate the document using the Pydantic model
            item_data['id'] = str(item_data['_id'])
            del item_data['_id']

            item = cls(**item_data)

            if include_relations:
                relations = cls.get_relations()
                for relation in relations:
                    cls._add_relation_field(relation, item)
            items.append(item)
        return items

    @classmethod
    def get_required_fields(cls):
        # Get the JSON schema for the Pydantic model
        model_schema = cls.schema()

        # Extract the list of required fields from the schema
        required_fields = [field for field, props in model_schema['properties'].items() if field in model_schema.get('required', [])]

        return required_fields

    @classmethod
    def get_all_fields(cls):
        # Get the JSON schema for the Pydantic model
        model_schema = cls.schema()

        # Extract the list of all fields from the schema
        all_fields = [field for field, props in model_schema['properties'].items()]

        return all_fields

    @staticmethod
    def get_relations():
        """
        Returns the list of relations
        Returns:
            list, containing relation config dicts. The structure of a dic is as follows
                {"model": <class extended from BaseModel>, "type": "many_to_one"}
                    - type: "many_to_one" or "one_to_many" ("one_to_one" is handled as a special case of many_to_one)
                        TODO: Implement "one_to_many"
        """
        return []

    @classmethod
    def _validate_relations(cls):
        """Validates relation configs"""
        relations = cls.get_relations()

        for relation in relations:
            if not isinstance(relation, dict) or 'model' not in relation or 'type' not in relation or 'field' not in relation:
                raise InvalidRelationConfigException("'relation' must be a dict with keys 'model', 'field' and 'type'")
            if relation['field'] not in cls.model_fields:
                raise InvalidRelationConfigException(f"The 'field' {relation['field']} is not in the model {cls.__name__}")
            if not relation['field'].endswith('_id'):
                raise InvalidRelationConfigException(f"All relation fields must end with '_id'. {relation['field']} violates this format.")
            if not issubclass(relation["model"], BaseModel):
                raise InvalidRelationConfigException("'model' must be a subclass of BaseModel.")


    @classmethod
    def _add_relation_field(cls, relation: dict, model_object: BaseModel):
        """Add a new property to the model based on relations"""
        field = relation['field']
        related_model_cls = relation['model']
        field_val = getattr(model_object, field)

        related_model_obj = related_model_cls.find_one(field_val)

        if related_model_obj is None:
            raise InvalidRelationException(f"There is not relation for the entry: {field_val} in model {related_model_cls.__name__}")


        new_property = field[:-3]
        if len(new_property) == 0:
            new_property = 'unk_relation_prop'

        setattr(model_object, new_property, related_model_obj)

