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

"""Some generic utility functions used by Gin."""

import contextlib


def augment_exception_message_and_reraise(exception, message):
  """Reraises `exception`, appending `message` to its string representation."""

  class ExceptionProxy(type(exception)):
    """Acts as a proxy for an exception with an augmented message."""
    __module__ = type(exception).__module__

    def __init__(self):
      pass

    def __getattr__(self, attr_name):
      return getattr(exception, attr_name)

    def __str__(self):
      return str(exception) + message

  ExceptionProxy.__name__ = type(exception).__name__

  proxy = ExceptionProxy()
  ExceptionProxy.__qualname__ = type(exception).__qualname__
  raise proxy.with_traceback(exception.__traceback__) from None


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
    if isinstance(exception, SyntaxError):
      raise  # SyntaxErrors already include location information.
    augment_exception_message_and_reraise(exception, _format_location(location))
