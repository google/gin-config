"""Setup script for gin-config.

See:

https://github.com/google/gin-config

"""

import codecs
from os import path
from setuptools import find_packages
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with codecs.open(path.join(here, 'README.md'), encoding='utf-8') as f:
  long_description = f.read()


setup(
    name='gin-config',
    version='0.1',
    include_package_data=True,
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),  # Required
    extras_require={  # Optional
        'tf': ['tensorflow'],
        'test': ['coverage'],
    },
    description='Gin-config: a lightweight configuration library for Python',
    long_description=long_description,
    url='https://github.com/google/gin-config',  # Optional
    author='The Gin-Config Team',  # Optional
    classifiers=[  # Optional
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: ML Tools',

        # Pick your license as you wish
        'License :: OSI Approved :: Apache License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/google/gin-config/issues',
        'Source': 'https://github.com/google/gin-config',
    },
)
