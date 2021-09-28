# Flask-Pydantic-Docs


## Installation

`python3 -m pip install Flask-Pydantic-Docs`

## Usage

### Example

```python
# necessary imports

app = Flask(__name___)
openapi = OpenAPI()

access_denied = APIError(code=403, msg="Access Denied")

@app.route("/post", methods=["POST"])
@openapi_docs(response=ResponseModel, tags=["demo"], exceptions=[access_denied])
@validate()
def post(body: BodyModel, query: QueryModel):
    return ResponseModel(
        id=id_,
        age=query.age,
        name=body.name,
        nickname=body.nickname,
    )
...

openapi.register(app)
```

**NOTE**:

- Since the `openapi_docs` decorator is to register the schemas based on the models used by the view function, so the models have to be put in the view function arguments with annotations as shown in the above example. Otherwise, the schemas cannot be captured.

- The statement `openapi.register` needs to be run after all view functions or `register_blueprint`.

### Add Auth Security Schemes

```python
# necessary imports, app and model definition

openapi = OpenAPI(
    extra_props={
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "in": "header",
                }
            }
        },
        "security": [{"bearerAuth": []}]
    },
)

...

openapi.register(app)

```
