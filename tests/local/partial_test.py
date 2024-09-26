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

"""Tests for the `gin.local.partial` module."""

import typing

from absl.testing import absltest
from gin.local import partial


class TestMetaClass(type):

  def __call__(cls, *args, **kwargs):
    instance = super().__call__(*args, **kwargs)
    instance.meta_was_run = True
    return instance


class TestClass(metaclass=TestMetaClass):
  """A test class for testing partial.partialclass."""

  def __init__(self, arg1, arg2, kwarg1=None, kwarg2=None):
    self.arg1 = arg1
    self.arg2 = arg2
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2

  def method(self, arg1, arg2, kwarg1=None, kwarg2=None):
    return (self, arg1, arg2, kwarg1, kwarg2)


class TestNamedTuple(typing.NamedTuple):
  arg1: int
  arg2: int
  kwarg1: str = 'default'
  kwarg2: str = 'default'


def test_function(arg1, arg2, kwarg1=None, kwarg2=None):
  return (arg1, arg2, kwarg1, kwarg2)


class PartialTest(absltest.TestCase):

  def test_partial_class(self):
    partial_class = partial.partialclass(TestClass, 1, kwarg2='kwarg2')
    self.assertTrue(issubclass(partial_class, TestClass))
    self.assertIsInstance(partial_class, TestMetaClass)
    self.assertEqual(partial_class.__module__, TestClass.__module__)
    self.assertEqual(partial_class.__name__, TestClass.__name__)
    self.assertEqual(partial_class.__qualname__, TestClass.__qualname__)
    self.assertEqual(partial_class.__doc__, TestClass.__doc__)

    instance = partial_class(2, kwarg1='kwarg1')
    self.assertEqual(type(instance), TestClass)
    self.assertEqual(instance.arg1, 1)
    self.assertEqual(instance.arg2, 2)
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')
    self.assertTrue(instance.meta_was_run)

  def test_partial_class_dynamic_subclass(self):
    partial_class = partial.partialclass(TestClass, 1, kwarg2='kwarg2')

    class DynamicSubclass(partial_class):

      def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subclass_init_called = True

    instance = DynamicSubclass(2, kwarg1='kwarg1')
    self.assertEqual(type(instance), DynamicSubclass)
    self.assertEqual(instance.arg1, 1)
    self.assertEqual(instance.arg2, 2)
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')
    self.assertTrue(instance.meta_was_run)
    self.assertTrue(instance.subclass_init_called)

  def test_partial_namedtuple(self):
    partial_class = partial.partialclass(TestNamedTuple, 1, kwarg2='kwarg2')
    self.assertEqual(partial_class.__slots__, ())

    instance = partial_class(2, kwarg1='kwarg1')
    self.assertEqual(type(instance), TestNamedTuple)
    self.assertEqual(instance.arg1, 1)
    self.assertEqual(instance.arg2, 2)
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')

  def test_partial(self):
    partial_class = partial.partial(TestClass, 1, 2, 'kwarg1', 'kwarg2')
    instance = partial_class()
    self.assertEqual(type(instance), TestClass)
    self.assertEqual(instance.arg1, 1)
    self.assertEqual(instance.arg2, 2)
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')

    partial_method = partial.partial(
        instance.method, 'a', 'b', kwarg1='c', kwarg2='d')
    self.assertEqual(partial_method(), (instance, 'a', 'b', 'c', 'd'))

    partial_fn = partial.partial(test_function, 'one', 'two', 'three', 'four')
    self.assertEqual(partial_fn(), ('one', 'two', 'three', 'four'))


if __name__ == '__main__':
  absltest.main()
