from idprop.types import IDPropertyArray
from typing import Type, Sequence, Any, Tuple


def is_typed_array(value: Any, desired_type: Type | Tuple[Type, ...]) -> bool:
    """
    Determines if the given value is a sequence (list or tuple) of the specified type.

    Args:
        value: The value to check.
        desired_type: The type that all elements in the sequence should be.

    Returns:
        bool: True if the value is a sequence of the specified type, False otherwise.
    """
    # Check if the value is a sequence or Blender array
    types = [Sequence, IDPropertyArray]
    if True not in [isinstance(value, t) for t in types]:
        return False

    # Check if all elements in the sequence are of the desired type
    return all(isinstance(item, desired_type) for item in value)
