import inspect
from werkzeug.routing import parse_rule, parse_converter_args


def get_summary_desc(func):
    """
    get summary, description from `func.__doc__`

    Summary and description are split by '\n\n'. If only one is provided,
    it will be used as summary.
    """
    doc = inspect.getdoc(func)
    if not doc:
        return None, None
    doc = doc.split("\n\n", 1)
    if len(doc) == 1:
        return doc[0], None
    return doc


def get_converter_schema(converter: str, *args, **kwargs):
    """
    Get conveter method from converter map

    https://werkzeug.palletsprojects.com/en/0.15.x/routing/#builtin-converter

    :param converter: str: converter type
    :param args:
    :param kwargs:
    :return: return schema dict

    """
    if converter == "any":
        return {"type": "array", "items": {"type": "string", "enum": args}}
    elif converter == "int":
        return {
            "type": "integer",
            "format": "int32",
            **{
                f"{prop}imum": kwargs[prop] for prop in ["min", "max"] if prop in kwargs
            },
        }
    elif converter == "float":
        return {"type": "number", "format": "float"}
    elif converter == "uuid":
        return {"type": "string", "format": "uuid"}
    elif converter == "path":
        return {"type": "string", "format": "path"}
    elif converter == "string":
        return {
            "type": "string",
            **{
                prop: kwargs[prop]
                for prop in ["length", "maxLength", "minLength"]
                if prop in kwargs
            },
        }
    else:
        return {"type": "string"}


def parse_url(path: str):
    """
    Parsing Flask route url to get the normal url path and parameter type.

    Based on Werkzeug_ builtin converters.

    .. _werkzeug: https://werkzeug.palletsprojects.com/en/0.15.x/routing/#builtin-converters
    """
    subs = []
    parameters = []

    for converter, arguments, variable in parse_rule(path):
        if converter is None:
            subs.append(variable)
            continue
        subs.append(f"{{{variable}}}")

        args, kwargs = [], {}

        if arguments:
            args, kwargs = parse_converter_args(arguments)

        schema = get_converter_schema(converter, *args, **kwargs)

        parameters.append(
            {
                "name": variable,
                "in": "path",
                "required": True,
                "schema": schema,
            }
        )

    return "".join(subs), parameters

def merge_dicts(d1, d2):
    for k, v in d1.items():
        if k in d2:
            v2 = d2.pop(k)
            if isinstance(v, dict):
                if isinstance(v2, dict):
                    merge_dicts(v, v2)
                else:
                    d1[k] = v2
            else:
                d1[k] = v2
    d1.update(d2)
    return d1
