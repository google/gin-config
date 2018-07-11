# coding=utf-8
# Copyright 2018 The Gin-Config Authors.
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

See:

https://github.com/google/gin-config

"""

import codecs
from os import path
import gin
from setuptools import find_packages
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with codecs.open(path.join(here, 'README.md'), encoding='utf-8') as f:
  long_description = f.read()

install_requires = ['six >= 1.10.0', 'enum34;python_version<"3.4"']
test_requirements = ['six >= 1.10.0', 'absl-py >= 0.1.6']

setup(
    name='gin-config',
    version=gin.__version__,
    include_package_data=True,
    packages=find_packages(exclude=['docs']),  # Required
    package_data={'testdata': ['testdata/*.gin']},
    install_requires=install_requires,
    extras_require={  # Optional
        'tf': ['tensorflow >= 1.6'],
    },
    tests_require=test_requirements,
    description='Gin-config: a lightweight configuration library for Python',
    long_description=long_description,
    url='https://github.com/google/gin-config',  # Optional
    author='The Gin-Config Team',  # Optional
    author_email='opensource@google.com',
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
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',

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
