def infer(value):
    """
    Infers a JSON Schema (draft-07 compatible) from a parsed Python dictionary/list.
    """
    if value is None:
        return {"type": ["string", "null"]}
    if isinstance(value, dict):
        return _infer_object(value)
    if isinstance(value, list):
        return _infer_array(value)
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": "string"}

def _infer_object(obj_dict):
    schema = {"type": "object"}
    required = []
    properties = {}
    
    for key, val in obj_dict.items():
        key_str = str(key)
        required.append(key_str)
        properties[key_str] = infer(val)
        
    schema["required"] = required
    schema["properties"] = properties
    return schema

def _infer_array(arr_list):
    schema = {"type": "array"}
    if len(arr_list) > 0:
        schema["items"] = infer(arr_list[0])
    return schema
