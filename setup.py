# -*- coding: utf-8 -*-
from codecs import open
from os import path
from setuptools import setup

import openevse

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='python-openevse',
    version=openevse._version,
    description='Control OpenEVSE boards',
    long_description=long_description,
    url='https://github.com/tiramiseb/python-openevse',
    author='Sébastien Maccagnoni-Munch',
    author_email='seb+pythonopenevse@maccagnoni.eu',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='openevse serial rapi',
    py_modules=['openevse'],
    install_requires='pyserial'
)
