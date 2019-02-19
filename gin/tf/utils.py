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

"""Contains TensorFlow or Google-specific utilities for Gin configuration."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from gin import config

import tensorflow as tf

# pylint: disable=g-direct-tensorflow-import
from tensorflow.core.framework import summary_pb2
# pylint: enable=g-direct-tensorflow-import


# Register TF file reader for Gin's parse_config_file.
config.register_file_reader(tf.gfile.Open, tf.gfile.Exists)


@config.configurable
def singleton_per_graph(constructor):
  key = (config.current_scope_str(), tf.get_default_graph())
  return config.singleton_value(key, constructor)


class GinConfigSaverHook(tf.train.SessionRunHook):
  """A SessionRunHook that saves and summarizes the operative config.

  This hook will save Gin's operative configuration to a specified directory, as
  well as optionally summarizing it so that it will appear in TensorBoard's
  "Text" tab.

  The hook should only be supplied to the chief worker in distributed training
  setups to prevent multiple events files from being created. Similarly, if hook
  methods are called explicitly (if not using tf.training.MonitoredSession),
  they should only be called on the chief worker.
  """

  def __init__(self,
               output_dir,
               base_name='operative_config',
               summarize_config=True,
               summary_writer=None):
    """Construct the GinConfigSaverHook.

    Args:
      output_dir: The directory in which to save the operative config. This
        should in general be the same as the directory in which summaries are
        stored (and thus may be different for train vs. eval jobs.
      base_name: The base name (name excluding path and extension) of the file
        where this hook will write the operative config. Also used as the
        summary tag if summarizing the config for display in TensorBoard.
      summarize_config: Whether to save a summary of the operative config that
        will be loaded by TensorBoard and displayed in its "Text" tab.
      summary_writer: A tf.summary.FileWriter object to use for writing
        summaries. If `None` (default), a FileWriter object for `output_dir`
        will be created/retrieved by the tf.summary.FileWriterCache associated
        with `output_dir` in `after_create_session`.
    """
    self._output_dir = output_dir
    self._base_name = base_name
    self._summarize_config = summarize_config
    self._summary_writer = summary_writer

  def _markdownify_operative_config_str(self, string):
    """Convert an operative config string to markdown format."""

    # TODO: Total hack below. Implement more principled formatting.
    def process(line):
      """Convert a single line to markdown format."""
      if not line.startswith('#'):
        return '    ' + line

      line = line[2:]
      if line.startswith('===='):
        return ''
      if line.startswith('None'):
        return '    # None.'
      if line.endswith(':'):
        return '#### ' + line
      return line

    output_lines = []
    for line in string.splitlines():
      procd_line = process(line)
      if procd_line is not None:
        output_lines.append(procd_line)

    return '\n'.join(output_lines)

  def after_create_session(self, session=None, coord=None):
    """Writes out Gin's operative config, and maybe adds a summary of it."""
    config_str = config.operative_config_str()
    if not tf.gfile.IsDirectory(self._output_dir):
      tf.gfile.MakeDirs(self._output_dir)
    global_step_val = 0
    if session is not None:
      global_step = tf.train.get_global_step()
      if global_step is not None:
        global_step_val = session.run(global_step)
    filename = '%s-%s.gin' % (self._base_name, global_step_val)
    config_path = os.path.join(self._output_dir, filename)
    with tf.gfile.GFile(config_path, 'w') as f:
      f.write(config_str)

    if self._summarize_config:
      md_config_str = self._markdownify_operative_config_str(config_str)
      summary_metadata = summary_pb2.SummaryMetadata()
      summary_metadata.plugin_data.plugin_name = 'text'
      summary_metadata.plugin_data.content = b'{}'
      text_tensor = tf.make_tensor_proto(md_config_str)
      summary = summary_pb2.Summary()
      summary.value.add(
          tag='gin/' + self._base_name,
          tensor=text_tensor,
          metadata=summary_metadata)
      if not self._summary_writer:
        # Creating the FileWriter also creates the events file, so it should be
        # done here (where it is most likely to only occur on chief workers), as
        # opposed to in the constructor.
        self._summary_writer = tf.summary.FileWriterCache.get(self._output_dir)
      self._summary_writer.add_summary(summary, global_step_val)
      self._summary_writer.flush()
