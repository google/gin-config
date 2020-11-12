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

"""Tests for gin.tf.utils."""

import os
import tempfile

from gin import config
from gin.tf import utils

import tensorflow as tf

# pylint: disable=g-direct-tensorflow-import
from tensorflow.core.framework import summary_pb2
# pylint: enable=g-direct-tensorflow-import


@config.configurable
def configurable_fn(kwarg1=0, kwarg2=1):  # pylint: disable=unused-argument
  pass


@config.configurable
class ConfigurableClass:

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


class FakeSummaryWriter:

  def __init__(self):
    self._summaries = {}

  @property
  def summaries(self):
    return self._summaries

  def add_summary(self, summ, current_global_step):
    """Add summary."""
    if isinstance(summ, bytes):
      summary_proto = summary_pb2.Summary()
      summary_proto.ParseFromString(summ)
      summ = summary_proto
    if current_global_step in self._summaries:
      step_summaries = self._summaries[current_global_step]
    else:
      step_summaries = []
      self._summaries[current_global_step] = step_summaries
    step_summaries.append(summ)

  def flush(self):
    pass


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

  def setUp(self):
    super().setUp()
    tf.compat.v1.disable_eager_execution()
    tf.compat.v1.reset_default_graph()
    config.clear_config()

  def run_log_config_hook_maybe_with_summary(self, global_step_value, **kwargs):
    config.parse_config(GinConfigSaverHookTest.CONFIG_STR)

    configurable_fn()
    ConfigurableClass()
    no_args_fn()

    output_dir = tempfile.mkdtemp()
    summary_writer = FakeSummaryWriter()
    h = utils.GinConfigSaverHook(
        output_dir, summary_writer=summary_writer, **kwargs)
    with self.session() as sess:
      if global_step_value is not None:
        global_step = tf.compat.v1.train.get_or_create_global_step()
        sess.run(global_step.assign(global_step_value))
      h.after_create_session(sess)

    return output_dir, summary_writer

  def testConstructingHookDoesntCreateEventFiles(self):
    output_dir = tempfile.mkdtemp()
    h1 = utils.GinConfigSaverHook(output_dir)
    h2 = utils.GinConfigSaverHook(output_dir)
    self.assertEqual(os.listdir(output_dir), [])

    def create_event_files(hook):
      with self.session() as sess:
        hook.after_create_session(sess)
      return [f for f in os.listdir(output_dir) if f.startswith('events')]

    self.assertEqual(len(create_event_files(h1)), 1)
    # Check that the second hook doesn't create another events file.
    self.assertEqual(len(create_event_files(h2)), 1)

  def testGinConfigSaverHookWithoutSummary(self):
    global_step_value = 7
    output_dir, summary_writer = self.run_log_config_hook_maybe_with_summary(
        global_step_value=global_step_value, summarize_config=False)
    expected_file_name = 'operative_config-%d.gin' % global_step_value
    with tf.io.gfile.GFile(os.path.join(output_dir, expected_file_name)) as f:
      operative_config_str = f.read()
    self.assertEqual(operative_config_str, config.operative_config_str())
    self.assertEmpty(summary_writer.summaries)

  def testGinConfigSaverHookWithSummary(self):
    global_step_value = 7
    output_dir, summary_writer = self.run_log_config_hook_maybe_with_summary(
        global_step_value=global_step_value,
        base_name='custom_name')
    expected_file_name = 'custom_name-%d.gin' % global_step_value
    with tf.io.gfile.GFile(os.path.join(output_dir, expected_file_name)) as f:
      operative_config_str = f.read()
    self.assertEqual(operative_config_str, config.operative_config_str())

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
    output_dir, summary_writer = self.run_log_config_hook_maybe_with_summary(
        global_step_value=None)
    expected_file_name = 'operative_config-0.gin'
    with tf.io.gfile.GFile(os.path.join(output_dir, expected_file_name)) as f:
      operative_config_str = f.read()
    self.assertEqual(operative_config_str, config.operative_config_str())

    summary = summary_writer.summaries[0][0]
    self.assertEqual(summary.value[0].tag, 'gin/operative_config')

  def testGinConfigSaverHookIncludeStepFalse(self):
    output_dir, _ = self.run_log_config_hook_maybe_with_summary(
        global_step_value=7, include_step_in_filename=False)
    expected_file_name = 'operative_config.gin'
    with tf.io.gfile.GFile(os.path.join(output_dir, expected_file_name)) as f:
      operative_config_str = f.read()
    self.assertEqual(operative_config_str, config.operative_config_str())


class UtilsTest(tf.test.TestCase):

  def setUp(self):
    super().setUp()
    tf.compat.v1.reset_default_graph()
    config.clear_config()

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


if __name__ == '__main__':
  tf.test.main()
