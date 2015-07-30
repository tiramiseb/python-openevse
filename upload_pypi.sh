#!/bin/bash

version=$(sed -n "s/_version = '\(.*\)'/\1/p" openevse.py)
python setup.py sdist
python setup.py bdist_wheel
twine upload dist/*-$version*
