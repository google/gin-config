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

"""Some generic utility functions used by Gin."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import sys

import six


def augment_exception_message_and_reraise(exception, message):
  """Reraises `exception`, appending `message` to its string representation."""
  if len(exception.args) == 1 and isinstance(exception.args[0], str):
    # Exception with single string argument (most common case)
    exception.args = (exception.args[0] + message)
  else:
    exception.args = exception.args + (message,)
  
  if six.PY3:
    six.raise_from(exception, None)
  else:
    six.reraise(exception, None, sys.exc_info()[2])


def _format_location(location):
  filename, line_num, char_num, line = location
  filename = 'file "{}",'.format(filename) if filename else 'bindings string'
  line_info = '\n  In {filename} line {line_num}\n    {line}'.format(
      filename=filename, line_num=line_num, line=line.rstrip())
  char_info = '\n    {}^'.format(' ' * char_num) if char_num else ''
  return line_info + char_info


@contextlib.contextmanager
def try_with_location(location):
  try:
    yield
  except Exception as exception:  # pylint: disable=broad-except
    augment_exception_message_and_reraise(exception, _format_location(location))
