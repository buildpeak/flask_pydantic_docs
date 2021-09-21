from setuptools import setup, find_packages
from pathlib import Path

cwd = Path(__file__).resolve().parent

readme = (cwd / "README.md").read_text()

setup(
    name="flask_pydantic_docs",
    version="0.0.1",
    author="Steve Guo",
    author_email="buildpeak@gmail.com",
    description="Add openapi docs to flask app using Flask-Pydantic",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/buildpeak/flask_pydantic_docs",
    packages=find_packages(exclude=["examples*", "tests*"]),
    package_data={"flask_pydantic_docs": ["templates/*.html"]},
    classifiers=[],
    install_requires=[
        "Flask",
        "pydantic",
        "flask-pydantic",
    ],
    zip_safe=False,
    extras_require={},
)
