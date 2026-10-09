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

"""Tests for resource_reader."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys

from absl.testing import absltest

from gin import config
from gin import resource_reader


class ResourceReaderTest(absltest.TestCase):

  def __init__(self, *args, **kwargs):
    super(ResourceReaderTest, self).__init__(*args, **kwargs)
    config.register_file_reader(resource_reader.system_path_reader,
                                resource_reader.system_path_file_exists)

  def testParseConfigFromPythonSystemPath(self):
    """Load config only found in python system path."""
    test_srcdir = absltest.get_default_test_srcdir()
    relative_testdata_path = 'gin/testdata'
    absolute_testdata_path = os.path.join(test_srcdir, relative_testdata_path,
                                          'fake_package')
    sys.path.append(absolute_testdata_path)
    config_file = ('fake_gin_package/config/foo.gin')
    result = config.parse_config_file(
        config_file, print_includes_and_imports=True, skip_unknown=True)
    sys.path.remove(absolute_testdata_path)
    self.assertEqual(result.includes[0].filename,
                     'fake_gin_package/parent.gin')

  def testModuleLoggerName(self):
    """Ensure resource_reader uses a namespaced logger under gin."""
    self.assertEqual(resource_reader.logger.name, 'gin.resource_reader')

  def testLoggingCanBeFilteredViaModuleLogger(self):
    """Verify that logs emitted by resource_reader go through its logger."""
    import logging
    records = []

    class TestHandler(logging.Handler):
      def emit(self, record):
        records.append(record)

    handler = TestHandler()
    logger = logging.getLogger('gin.resource_reader')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
      resource_reader.system_path_file_exists('nonexistent_package_12345/foo.gin')
      self.assertTrue(any('system_path_file_exists' in r.getMessage() for r in records))
      self.assertTrue(any('Path not found' in r.getMessage() for r in records))
      for r in records:
        self.assertEqual(r.name, 'gin.resource_reader')
    finally:
      logger.removeHandler(handler)


if __name__ == '__main__':
  absltest.main()
