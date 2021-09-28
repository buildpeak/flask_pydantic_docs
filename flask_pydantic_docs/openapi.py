import functools
from typing import Callable, List, Optional, Type
from flask import Flask, Blueprint, jsonify, abort, render_template
from flask.views import MethodView
from pydantic import BaseModel
from .utils import parse_url, get_summary_desc, merge_dicts

OPENAPI_VERSION = "3.0.2"
OPENAPI_INFO = dict(
    title="Service Documents",
    version="latest",
)

OPENAPI_NAME = "docs"
OPENAPI_ENDPOINT = "/docs/"
OPENAPI_URL_PREFIX = None
OPENAPI_MODE = "normal"

OPENAPI_TEMPLATE_FOLDER = "templates"
OPENAPI_FILENAME = "openapi.json"
OPENAPI_UI = "swagger"


class APIView(MethodView):
    def __init__(self, *args, **kwargs):
        view_args = kwargs.pop("view_args", {})
        self.ui = view_args.get("ui")
        self.filename = view_args.get("filename")
        super().__init__(*args, **kwargs)

    def get(self):
        assert self.ui in {"redoc", "swagger"}
        ui_file = f"{self.ui}.html"
        return render_template(ui_file, spec_url=self.filename)


class APIError:
    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg = msg

    def __repr__(self) -> str:
        return f"{self.code} {self.msg}"


class OpenAPI:
    _models = {}

    def __init__(
        self,
        name: str = OPENAPI_NAME,
        mode: str = OPENAPI_MODE,
        endpoint: str = OPENAPI_ENDPOINT,
        url_prefix: Optional[str] = OPENAPI_URL_PREFIX,
        template_folder: str = OPENAPI_TEMPLATE_FOLDER,
        filename: str = OPENAPI_FILENAME,
        openapi_version: str = OPENAPI_VERSION,
        openai_info: dict = OPENAPI_INFO,
        ui: str = OPENAPI_UI,
        extra_props: dict = {},
    ) -> None:
        self.name: str = name
        self.mode: str = mode
        self.endpoint: str = endpoint
        self.url_prefix: Optional[str] = url_prefix
        self.template_folder: str = template_folder
        self.filename: str = filename
        self.openapi_version: str = openapi_version
        self.info: dict = openai_info
        self.ui: str = ui
        self.extra_props: dict = extra_props

        self._spec = None

    def register(self, app: Flask) -> None:
        assert isinstance(app, Flask)
        self.app = app
        blueprint = Blueprint(
            self.name,
            __name__,
            url_prefix=self.url_prefix,
            template_folder=self.template_folder,
        )

        # docs
        blueprint.add_url_rule(
            self.endpoint,
            self.name,
            view_func=APIView().as_view(
                self.name, view_args=dict(ui=self.ui, filename=self.filename)
            ),
        )

        # docs/openapi.json
        @blueprint.route(f"{self.endpoint}<filename>")
        def ___jsonfile___(filename: str):
            if filename == self.filename:
                return jsonify(self.spec)
            abort(404)

        self.app.register_blueprint(blueprint)

    @property
    def spec(self):
        if self._spec is None:
            self._spec = self.generate_spec()
        return self._spec

    def _bypass(self, func) -> bool:
        if self.mode == "greedy":
            return False
        elif self.mode == "strict":
            if getattr(func, "_openapi", None) == self.__class__:
                return False
            return True
        else:
            decorator = getattr(func, "_openapi", None)
            if decorator and decorator != self.__class__:
                return True
            return False

    def generate_spec(self):
        """
        generate OpenAPI spec JSON file
        """

        routes = {}
        tags = {}

        for rule in self.app.url_map.iter_rules():
            if str(rule).startswith(
                (f"{self.url_prefix or ''}{self.endpoint}", "/static")
            ):
                continue

            func = self.app.view_functions[rule.endpoint]
            path, parameters = parse_url(str(rule))

            # bypass the function decorated by others
            if self._bypass(func):
                continue

            # multiple methods (with different func) may bond to the same path
            if path not in routes:
                routes[path] = {}

            for method in rule.methods:
                if method in ["HEAD", "OPTIONS"]:
                    continue

                if hasattr(func, "tags"):
                    for tag in func.tags:
                        if tag not in tags:
                            tags[tag] = {"name": tag}

                summary, desc = get_summary_desc(func)
                spec = {
                    "summary": summary or func.__name__.capitalize(),
                    "description": desc or "",
                    "operationID": func.__name__ + "__" + method.lower(),
                    "tags": getattr(func, "tags", []),
                }

                if hasattr(func, "body"):
                    spec["requestBody"] = {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{func.body}"}
                            }
                        }
                    }

                params = parameters[:]
                if hasattr(func, "query"):
                    params.append(
                        {
                            "name": func.query,
                            "in": "query",
                            "required": True,
                            "schema": {
                                "$ref": f"#/components/schemas/{func.query}",
                            },
                        }
                    )
                spec["parameters"] = params

                spec["responses"] = {}
                has_2xx = False
                if hasattr(func, "exceptions"):
                    for code, msg in func.exceptions.items():
                        if code.startswith("2"):
                            has_2xx = True
                        spec["responses"][code] = {
                            "description": msg,
                        }

                if hasattr(func, "response"):
                    spec["responses"]["200"] = {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": f"#/components/schemas/{func.response}"
                                }
                            }
                        },
                    }
                elif not has_2xx:
                    spec["responses"]["200"] = {"description": "Successful Response"}

                if any(
                    [hasattr(func, schema) for schema in ("query", "body", "response")]
                ):
                    spec["responses"]["400"] = {
                        "description": "Validation Error",
                    }

                routes[path][method.lower()] = spec

        definitions = {}
        for _, schema in self._models.items():
            if "definitions" in schema:
                for key, value in schema["definitions"].items():
                    definitions[key] = value
                del schema["definitions"]

        data = {
            "openapi": self.openapi_version,
            "info": self.info,
            "tags": list(tags.values()),
            "paths": {**routes},
            "components": {
                "schemas": {name: schema for name, schema in self._models.items()},
            },
            "definitions": definitions,
        }

        merge_dicts(data, self.extra_props)

        return data

    @classmethod
    def add_model(cls, model):
        cls._models[model.__name__] = model.schema()


def openapi_docs(
    response: Optional[Type[BaseModel]] = None,
    exceptions: List[APIError] = [],
    tags: List[str] = [],
):
    def decorate(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            res = func(*args, **kwargs)
            return res

        query = func.__annotations__.get("query") or getattr(func, "_query", None)
        body = func.__annotations__.get("body") or getattr(func, "_body", None)

        # register schemas to this function
        for schema, name in zip((query, body, response), ("query", "body", "response")):
            if schema:
                assert issubclass(schema, BaseModel)
                OpenAPI.add_model(schema)
                setattr(wrapper, name, schema.__name__)

        # store exception for doc
        api_errs = {}
        for e in exceptions:
            assert isinstance(e, APIError)
            api_errs[str(e.code)] = e.msg
        if api_errs:
            setattr(wrapper, "exceptions", api_errs)

        if tags:
            setattr(wrapper, "tags", tags)

        # register OpenAPI class
        setattr(wrapper, "_openapi", OpenAPI)

        return wrapper

    return decorate
