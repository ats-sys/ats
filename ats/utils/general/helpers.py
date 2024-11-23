import importlib.util
import os
from ats.utils.string_processing.processor import snake_to_camel

def get_class_from_namespace(namespace: str):
    """
    Get a class given a namespace.
    Supported namespaces:
        Exchange:
            - "exchange:<module_name>"
        Fee class:
            - "fees:<module_name>"
        Strategy:
            - "strategy:<module_name>"
        Indicator:
            - "indicator:<module_name>"
    Args:
        namespace: Namespace as a string, separated by ":"

    Returns:
        Module's class (not the object)
    """
    namespace_parts = namespace.split(':')
    if len(namespace_parts) <= 1:
        raise Exception('Namespace is invalid. It must have at least 2 parts separated by ":"')

    # Paths for custom and default modules
    custom_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../custom_modules'))
    ats_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

    sub_dir_map = {
        'strategies': ['strategies', 'strategies'],
        'exchanges': ['exchanges', os.path.join('exchanges', 'exchanges')],
        'fees': ['fees', os.path.join('exchanges', 'fees')],
        'indicators': ['indicators', 'indicators']
    }

    category = namespace_parts[0]
    module_name = namespace_parts[1]

    if category not in sub_dir_map:
        raise ValueError(f"Invalid namespace category: {category}")

    # Paths to check for the module
    custom_dir = os.path.join(custom_base_path, sub_dir_map[category][0])
    ats_dir = os.path.join(ats_base_path, sub_dir_map[category][1])

    if category == 'exchanges':
        # exchange has exchange.py
        custom_module_path = os.path.join(custom_dir, os.path.join(module_name, 'exchange.py'))
        ats_module_path = os.path.join(ats_dir, os.path.join(module_name, 'exchange.py'))
    elif category == 'strategies':
        # exchange has exchange.py
        custom_module_path = os.path.join(custom_dir, os.path.join(module_name, 'strategy.py'))
        ats_module_path = os.path.join(ats_dir, os.path.join(module_name, 'strategy.py'))
    else:
        # Resolve module paths
        custom_module_path = os.path.join(custom_dir, f"{module_name}.py")
        ats_module_path = os.path.join(ats_dir, f"{module_name}.py")

    print(custom_module_path)
    print(ats_module_path)

    # Check custom modules first
    if os.path.isfile(custom_module_path):
        module_path = custom_module_path
    elif os.path.isfile(ats_module_path):
        module_path = ats_module_path
    else:
        raise FileNotFoundError(
            f"Module '{module_name}' not found in either '{custom_dir}' or '{ats_dir}'."
        )

    # Dynamically load the module
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Determine the class name
    class_name_map = {
        'strategies': 'Strategy',
        'exchanges': 'Exchange',
        'fees': ''.join([snake_to_camel(word) for word in module_name.split('_')]),
        'indicators': snake_to_camel(module_name)
    }
    class_name = class_name_map[category]

    # Retrieve and return the class
    if not hasattr(module, class_name):
        raise AttributeError(f"Class '{class_name}' not found in module '{module_name}'.")

    return getattr(module, class_name)

def check_nested_property_in_dict(prop, dictionary) -> bool:
    """
    Check the existence of nested properties in a dict
    Args:
        prop: Nested properties are represented with a dot. Ex: "prop1.sub_prop2"
        dictionary: Dict to check

    Returns:
        True if the properties are found, else False
    """
    keys = prop.split('.')
    current_dict = dictionary

    try:
        for key in keys:
            current_dict = current_dict[key]
        return True
    except (KeyError, TypeError):
        return False
