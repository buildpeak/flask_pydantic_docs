import functools
from typing import Callable, Optional
from flask import Flask, Blueprint, jsonify, abort, render_template
from flask.views import MethodView
from pydantic import BaseModel
from werkzeug.exceptions import HTTPException
from .utils import parse_url, get_summary_desc


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


class OpenAPI:
    def __init__(self) -> None:
        self.name: str = "docs"
        self.mode: str = "normal"
        self.endpoint: str = "/docs/"
        self.url_prefix: Optional[str] = None
        self.template_folder: str = "templates"
        self.filename: str = "openapi.json"
        self.openapi_version: str = "3.0.2"
        self.info: dict = dict(title="Service Documents", version="latest")
        self.ui: str = "swagger"

        self.models = {}
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
        @blueprint.route(f"{self.endpoint}/<filename>")
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

    def bypass(self, func) -> bool:
        if self.mode == "greedy":
            return False
        elif self.mode == "strict":
            if getattr(func, "_decorator", None) == self:
                return False
            return True
        else:
            decorator = getattr(func, "_decorator", None)
            if decorator and decorator != self:
                return True
            return False

    def generate_spec(self):
        """
        generate OpenAPI spec JSON file
        """

        routes = {}
        tags = {}
        for rule in self.app.url_map.iter_rules():
            if str(rule).startswith(self.endpoint) or str(rule).startswith("/static"):
                continue

            func = self.app.view_functions[rule.endpoint]
            path, parameters = parse_url(str(rule))

            # bypass the function decorated by others
            if self.bypass(func):
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
                if hasattr(func, "exc"):
                    for code, msg in func.exc.items():
                        if code.startswith("2"):
                            has_2xx = True
                        spec["responses"][code] = {
                            "description": msg,
                        }

                if hasattr(func, "resp"):
                    spec["responses"]["200"] = {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{func.resp}"}
                            }
                        },
                    }
                elif not has_2xx:
                    spec["responses"]["200"] = {"description": "Successful Response"}

                if any([hasattr(func, schema) for schema in ("query", "data", "resp")]):
                    spec["responses"]["400"] = {
                        "description": "Validation Error",
                    }

                routes[path][method.lower()] = spec

        definitions = {}
        for _, schema in self.models.items():
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
                "schemas": {name: schema for name, schema in self.models.items()},
            },
            "definitions": definitions,
        }

        return data

    def docs(self, resp=None, exc=[], tags=[]):
        def decorate(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                res = func(*args, **kwargs)
                return res

            query = func.__annotations__.get("query")
            body = func.__annotations__.get("body")

            # register schemas to this function
            for schema, name in zip((query, body, resp), ("query", "body", "resp")):
                if schema:
                    assert issubclass(schema, BaseModel)
                    self.models[schema.__name__] = schema.schema()
                    setattr(wrapper, name, schema.__name__)

            # store exception for doc
            code_msg = {}
            for e in exc:
                assert isinstance(e, HTTPException)
                code_msg[str(e.code)] = str(e)
            if code_msg:
                wrapper.exc = code_msg

            if tags:
                setattr(wrapper, "tags", tags)

            setattr(wrapper, "_decorator", self)

            return wrapper

        return decorate
