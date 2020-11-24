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

"""Module for reading gin configs in the python system path."""
import importlib
import logging
import os
from typing import Any

from gin import config


def system_path_reader(config_path: str) -> Any:
  """Loads a gin config as a resource from within a package.

  Args:
    config_path: Path to the gin file, e.g. /foo/bar/config/walker2d.gin and
      foo.bar.config/walker2d.gin

  Returns:
    An open file to the config.
  """
  path = _parse_config_path(config_path)
  f = open(path)
  logging.info('gin-config opened resource file:%s', path)
  return f


def system_path_file_exists(config_path: str) -> bool:
  """Checks if the config_path points to a config on the Python system path.

  Args:
    config_path: String path to the gin file, e.g. /foo/bar/config/walker2d.gin.

  Returns:
    True if the file exists.
  """
  logging.info('system_path_file_exists:%s', config_path)
  try:
    path = _parse_config_path(config_path)
  except (ModuleNotFoundError, ValueError, ImportError):
    # Package was not found. Thus the file does not exist.
    logging.error('Path not found: %s', config_path)
    return False

  return os.path.isfile(path)


def _parse_config_path(config_path: str) -> str:
  """Turns config_path into path to the config in python system path.

  Path is split into head and filename using `os.path.split`. The head is
  treated as a Python package and the filename as a gin file. Path to where the
  package is located on the fileystem is determined and then joined with the
  filename.

  `importlib.resources` was not used because it is new in python 3.7.

  Args:
    config_path: String path to the gin file, e.g.
    /foo/bar/config/walker2d.gin.

  Returns:
    Absolute path to gin config in python system path.

  Raises:
    ValueError: if the package cannot be loaded.
  """
  head, filename = os.path.split(config_path)
  pkg = head.replace('/', '.')
  # importlib.util.find_spec is valid for python >= 3.4.
  spec = importlib.util.find_spec(pkg)  # type: ignore
  if spec is None:
    raise ValueError('Package not found', pkg)
  file_sys_path = spec.origin
  # file_sys_path often ends with __init__.py.
  path = os.path.join(os.path.dirname(file_sys_path), filename)
  return path

# Register TF file reader for Gin's parse_config_file.
config.register_file_reader(system_path_reader, system_path_file_exists)
