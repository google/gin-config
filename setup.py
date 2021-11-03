# coding=utf-8
# Copyright 2020 The Gin-Config Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Setup script for gin-config.

See https://github.com/google/gin-config for documentation.
"""

from os import path
from setuptools import find_packages
from setuptools import setup

_VERSION = '0.5.0'

here = path.abspath(path.dirname(__file__))

long_description = """
# Gin

Gin provides a lightweight configuration framework for Python, based on
dependency injection. Functions or classes can be decorated with
`@gin.configurable`, allowing default parameter values to be supplied from a
config file (or passed via the command line) using a simple but powerful syntax.
This removes the need to define and maintain configuration objects (e.g.
protos), or write boilerplate parameter plumbing and factory code, while often
dramatically expanding a project's flexibility and configurability.

Gin is particularly well suited for machine learning experiments (e.g. using
TensorFlow), which tend to have many parameters, often nested in complex ways.


**Authors**: Dan Holtmann-Rice, Sergio Guadarrama, Nathan Silberman
**Contributors**: Oscar Ramirez, Marek Fiser
"""

setup(
    name='gin-config',
    version=_VERSION,
    include_package_data=True,
    packages=find_packages(exclude=['docs']),  # Required
    package_data={'testdata': ['testdata/*.gin']},
    install_requires=[],
    extras_require={  # Optional
        'tensorflow': ['tensorflow >= 1.13.0'],
        'tensorflow-gpu': ['tensorflow-gpu >= 1.13.0'],
        'tf-nightly': ['tf-nightly'],
        'torch': ['torch >= 1.3.0'],
        'pytorch-nightly': ['pytorch-nightly'],
        'testing': [
            'absl-py >= 0.1.6',
            'mock >= 3.0.5',
            'nose',
        ]
    },
    description='Gin-Config: A lightweight configuration library for Python',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/google/gin-config',  # Optional
    author='The Gin-Config Team',  # Optional
    classifiers=[  # Optional
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',

        # Pick your license as you wish
        'License :: OSI Approved :: Apache Software License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',

        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Mathematics',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    project_urls={  # Optional
        'Documentation': 'https://github.com/google/gin-config/docs',
        'Bug Reports': 'https://github.com/google/gin-config/issues',
        'Source': 'https://github.com/google/gin-config',
    },
    license='Apache 2.0',
    keywords='gin-config gin python configuration machine learning'
)
