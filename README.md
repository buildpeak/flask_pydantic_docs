# Flask-Pydantic-Docs


## Installation

`python3 -m pip install Flask-Pydantic-Docs`

## Usage

### Example 1

```python
app = Flask(__name__)
openapi = OpenAPI()

@app.route("/users/<user_id>", methods=["GET"])
@openapi_docs()
@validate()
def get_user(user_id: str)
    return User(...)


openapi.register(app)
```
