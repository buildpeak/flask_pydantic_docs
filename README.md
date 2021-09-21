# Flask-Pydantic-Docs


## Installation

`python3 -m pip install Flask-Pydantic-Docs`

## Usage

### Example 1

```python

@app.route("/users/<user_id>", methods=["GET"])
@docs()
@validate()
def get_user(user_id: str)
    return User(...)
```
