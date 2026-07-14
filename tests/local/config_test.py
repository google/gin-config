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

"""Tests for the `gin.local.config` module."""

from absl.testing import absltest
from gin.local import config

import tree


class TestClass:

  def __init__(self, arg1, arg2, kwarg1=None, kwarg2=None):
    self.arg1 = arg1
    self.arg2 = arg2
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


def test_function(arg1, arg2, kwarg1=None, kwarg2=None):
  return (arg1, arg2, kwarg1, kwarg2)


class ConfigTest(absltest.TestCase):

  def test_config_for_classes(self):
    class_config = config.Config(TestClass, 1, kwarg2='kwarg2')
    self.assertEqual(class_config.arg1, 1)
    self.assertEqual(class_config.kwarg2, 'kwarg2')
    class_config.arg1 = 'arg1'
    self.assertEqual(class_config.arg1, 'arg1')
    class_config.arg2 = 'arg2'
    class_config.kwarg1 = 'kwarg1'

    partial_class = config.bind(class_config)
    instance = partial_class()
    self.assertEqual(instance.arg1, 'arg1')
    self.assertEqual(instance.arg2, 'arg2')
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')

  def test_config_for_functions(self):
    function_config = config.Config(test_function, 1, kwarg2='kwarg2')
    self.assertEqual(function_config.arg1, 1)
    self.assertEqual(function_config.kwarg2, 'kwarg2')
    function_config.arg1 = 'arg1'
    self.assertEqual(function_config.arg1, 'arg1')
    function_config.arg2 = 'arg2'
    function_config.kwarg1 = 'kwarg1'

    partial_function = config.bind(function_config)
    self.assertEqual(partial_function(), ('arg1', 'arg2', 'kwarg1', 'kwarg2'))

  def test_nested_configs(self):
    function_config1_args = ('innermost1', 'innermost2', 'kw1', 'kw2')
    function_config1 = config.Config(test_function, *function_config1_args)

    class_config = config.Config(
        TestClass, arg1=function_config1, arg2=function_config1())
    function_config2 = config.Config(
        test_function, arg1=class_config, arg2=class_config())

    function_config2_args = config.bind(function_config2)()

    test_class = function_config2_args[0]
    self.assertTrue(issubclass(test_class, TestClass))

    test_class_instance = test_class()
    self.assertEqual(type(test_class_instance), TestClass)
    self.assertEqual(test_class_instance.arg1(), function_config1_args)
    self.assertEqual(test_class_instance.arg2, function_config1_args)

    test_class_instance = function_config2_args[1]
    self.assertEqual(type(test_class_instance), TestClass)
    self.assertEqual(test_class_instance.arg1(), function_config1_args)
    self.assertEqual(test_class_instance.arg2, function_config1_args)

  def test_instance_sharing(self):
    class_config = config.Config(
        TestClass, 'arg1', 'arg2', kwarg1='kwarg1', kwarg2='kwarg2')
    instance_config = class_config()
    instance_config.arg1 = 'shared_arg1'

    # Changing instance config parameters doesn't change the class config.
    self.assertEqual(class_config.arg1, 'arg1')

    function_config = config.Config(test_function, class_config(), {
        'key1': [instance_config, instance_config],
        'key2': (instance_config,)
    })

    memo = {}
    function_args = config.bind(function_config(), memo=memo)
    separate_instance = function_args[0]
    shared_instance = memo[instance_config]
    structure = function_args[1]

    self.assertIsNot(shared_instance, separate_instance)
    for leaf in tree.flatten(structure):
      self.assertIs(leaf, shared_instance)

    self.assertEqual(separate_instance.arg1, 'arg1')
    self.assertEqual(shared_instance.arg1, 'shared_arg1')

  def test_memo_override(self):
    class_config = config.Config(
        TestClass, 'arg1', 'arg2', kwarg1='kwarg1', kwarg2='kwarg2')
    instance_config = class_config()
    function_config = config.Config(test_function, instance_config, {
        'key1': [instance_config, instance_config],
        'key2': (instance_config,)
    })

    overridden_instance_value = object()
    memo = {instance_config: overridden_instance_value}
    function_args = config.bind(function_config(), memo=memo)
    instance = function_args[0]
    structure = function_args[1]

    self.assertIs(instance, overridden_instance_value)
    for leaf in tree.flatten(structure):
      self.assertIs(leaf, overridden_instance_value)

  def test_call_config_twice_error(self):
    class_config = config.Config(
        TestClass, 'arg1', 'arg2', kwarg1='kwarg1', kwarg2='kwarg2')
    expected_err_msg = r'The config has already been marked as called\.'
    with self.assertRaisesRegex(ValueError, expected_err_msg):
      class_config()()

  def test_params(self):
    class_config = config.Config(
        TestClass, 'arg1', 'arg2', kwarg1='kwarg1', kwarg2='kwarg2')
    params = config.params(class_config)
    self.assertEqual(params, {
        'arg1': 'arg1',
        'arg2': 'arg2',
        'kwarg1': 'kwarg1',
        'kwarg2': 'kwarg2'
    })


if __name__ == '__main__':
  absltest.main()
