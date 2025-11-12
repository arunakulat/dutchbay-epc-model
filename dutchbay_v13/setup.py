from setuptools import setup, find_packages

setup(
    name="dutchbay-v13",
    version="0.1.0",
    packages=find_packages(
        include=["dutchbay_v13", "dutchbay_v13.*"], exclude=["inputs*"]
    ),
    install_requires=[],
)
