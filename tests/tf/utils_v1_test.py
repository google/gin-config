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

"""Tests for gin.tf.utils."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import tempfile

from gin import config
from gin.tf import utils

from six.moves import zip
import tensorflow as tf


@config.configurable
def configurable_fn(kwarg1=0, kwarg2=1):  # pylint: disable=unused-argument
  pass


@config.configurable
class ConfigurableClass(object):

  def __init__(self, kwarg1=None, kwarg2=None):
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


@config.configurable
def no_args_fn():
  pass


# pylint: disable=unused-argument,unused-variable
@config.configurable
def not_called_fn(one=1, two=2):
  pass
# pylint: enable=unused-argument,unused-variable


@config.configurable
def new_object():
  return object()


if tf.__version__.startswith('1'):
  # most tests require tf.contrib.testing.FakeSummaryWriter
  class GinConfigSaverHookTest(tf.test.TestCase):
    CONFIG_STR = """
      configurable_fn.kwarg1 = 10

      ConfigurableClass.kwarg2 = None

      not_called_fn.one = 'one'
    """

    EXPECTED_MARKDOWN = """
      #### Parameters for configurable_fn:

          configurable_fn.kwarg1 = 10
          configurable_fn.kwarg2 = 1

      #### Parameters for ConfigurableClass:

          ConfigurableClass.kwarg1 = None
          ConfigurableClass.kwarg2 = None

      #### Parameters for no_args_fn:

          # None.
    """

    def assertEmpty(self, collection):
      self.assertEqual(len(collection), 0)

    def setUp(self):
      config.clear_config()

    def run_log_config_hook_maybe_with_summary(self, global_step_value, **kwargs):
      config.parse_config(GinConfigSaverHookTest.CONFIG_STR)

      configurable_fn()
      ConfigurableClass()
      no_args_fn()

      if global_step_value is not None:
        tf.compat.v1.get_variable(
            'global_step',
            shape=(),
            dtype=tf.int64,
            initializer=tf.constant_initializer(global_step_value),
            trainable=False)

      output_dir = tempfile.mkdtemp()
      summary_writer = tf.contrib.testing.FakeSummaryWriter(output_dir)
      h = utils.GinConfigSaverHook(
          output_dir, summary_writer=summary_writer, **kwargs)
      with tf.compat.v1.train.MonitoredSession(hooks=[h]):
        pass

      return output_dir, summary_writer

    def testSingletonPerGraph(self):
      config_str = """
        ConfigurableClass.kwarg1 = @obj1/singleton_per_graph()
        ConfigurableClass.kwarg2 = @obj2/singleton_per_graph()

        obj1/singleton_per_graph.constructor = @new_object
        obj2/singleton_per_graph.constructor = @new_object
      """
      config.parse_config(config_str)

      with tf.Graph().as_default():
        class1 = ConfigurableClass()
        class2 = ConfigurableClass()

      with tf.Graph().as_default():
        class3 = ConfigurableClass()
        class4 = ConfigurableClass()

      self.assertIs(class1.kwarg1, class2.kwarg1)
      self.assertIs(class1.kwarg2, class2.kwarg2)
      self.assertIsNot(class1.kwarg1, class1.kwarg2)
      self.assertIsNot(class2.kwarg1, class2.kwarg2)

      self.assertIs(class3.kwarg1, class4.kwarg1)
      self.assertIs(class3.kwarg2, class4.kwarg2)
      self.assertIsNot(class3.kwarg1, class3.kwarg2)
      self.assertIsNot(class4.kwarg1, class4.kwarg2)

      self.assertIsNot(class1.kwarg1, class3.kwarg1)
      self.assertIsNot(class1.kwarg2, class3.kwarg2)
      self.assertIsNot(class2.kwarg1, class4.kwarg1)
      self.assertIsNot(class2.kwarg2, class4.kwarg2)

    def testConstructingHookDoesntCreateEventFiles(self):
      with tf.Graph().as_default():
        output_dir = tempfile.mkdtemp()
        h1 = utils.GinConfigSaverHook(output_dir)
        h2 = utils.GinConfigSaverHook(output_dir)
        self.assertEqual(os.listdir(output_dir), [])

        def create_event_files(hook):
          with tf.compat.v1.train.MonitoredTrainingSession(
              chief_only_hooks=[hook]):
            pass
          return [f for f in os.listdir(output_dir) if f.startswith('events')]

        self.assertEqual(len(create_event_files(h1)), 1)
        # Check that the second hook doesn't create another events file.
        self.assertEqual(len(create_event_files(h2)), 1)

    def testGinConfigSaverHookWithoutSummary(self):
      global_step_value = 7
      with tf.Graph().as_default():
        output_dir, summary_writer = \
          self.run_log_config_hook_maybe_with_summary(
            global_step_value=global_step_value, summarize_config=False)
        expected_file_name = 'operative_config-%d.gin' % global_step_value
        with tf.io.gfile.GFile(os.path.join(output_dir, expected_file_name)) as f:
          operative_config_str = f.read()
        self.assertEqual(operative_config_str, config.operative_config_str())
        summary_writer.assert_summaries(
          test_case=self, expected_logdir=output_dir)
        self.assertEmpty(summary_writer.summaries)

    def testGinConfigSaverHookWithSummary(self):
      global_step_value = 7
      with tf.Graph().as_default():
        output_dir, summary_writer = \
            self.run_log_config_hook_maybe_with_summary(
              global_step_value=global_step_value,
              base_name='custom_name')
        expected_file_name = 'custom_name-%d.gin' % global_step_value
        with tf.io.gfile.GFile(
            os.path.join(output_dir, expected_file_name)) as f:
          operative_config_str = f.read()
        self.assertEqual(operative_config_str, config.operative_config_str())
        summary_writer.assert_summaries(
          test_case=self, expected_logdir=output_dir)

        summary = summary_writer.summaries[global_step_value][0]
        self.assertEqual(summary.value[0].tag, 'gin/custom_name')

        summary_lines = (
            summary.value[0].tensor.string_val[0].decode('utf8').splitlines())
        markdown = GinConfigSaverHookTest.EXPECTED_MARKDOWN
        markdown_lines = markdown.strip().splitlines()
        self.assertEqual(len(summary_lines), len(markdown_lines))
        for l1, l2 in zip(summary_lines, markdown_lines):
          self.assertEqual(l1.strip(), l2.strip())

    def testGinConfigSaverHookWithoutGlobalStep(self):
      with tf.Graph().as_default():
        output_dir, summary_writer = \
          self.run_log_config_hook_maybe_with_summary(global_step_value=None)
        expected_file_name = 'operative_config-0.gin'
        with tf.io.gfile.GFile(
            os.path.join(output_dir, expected_file_name)) as f:
          operative_config_str = f.read()
        self.assertEqual(operative_config_str, config.operative_config_str())
        summary_writer.assert_summaries(
          test_case=self, expected_logdir=output_dir)

        summary = summary_writer.summaries[0][0]
        self.assertEqual(summary.value[0].tag, 'gin/operative_config')

if __name__ == '__main__':
  tf.test.main()
