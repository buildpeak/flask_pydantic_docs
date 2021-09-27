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

#### Add Auth Security Schemes

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
