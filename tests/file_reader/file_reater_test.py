from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from absl.testing import absltest
from gin import config

HERE = os.path.realpath(os.path.dirname(__file__))
SUBDIR = os.path.join(HERE, 'subdir')
MAIN = os.path.join(SUBDIR, 'main.gin')
os.environ['SUBDIR'] = SUBDIR


@config.configurable
def f(x):
  pass


class FileReaderTest(absltest.TestCase):

  def tearDown(self):
    config.clear_config(clear_constants=True)
    config._FILE_READERS = [(open, os.path.isfile)]
    super(FileReaderTest, self).tearDown()

  def test_vars_in_includes(self):
    path = '$SUBDIR/ambiguous.gin'
    with self.assertRaises(OSError):
      config.parse_config_file(path)
    config.enable_vars_in_includes()
    config.parse_config_file(path)
    self.assertEqual(config.query_parameter('f.x'), 'subdir')

  def test_relative_includes_low_priority(self):
    config.enable_relative_includes(highest_priority=False)
    with config._change_dir_context(HERE):
      config.parse_config_file('subdir/main.gin')
    self.assertEqual(config.query_parameter('f.x'), 'root')

  def test_relative_includes_high_priority(self):
    config.enable_relative_includes(highest_priority=True)
    with config._change_dir_context(HERE):
      config.parse_config_file('subdir/main.gin')
    self.assertEqual(config.query_parameter('f.x'), 'subdir')

  def test_highest_priority_overwrite(self):
    config.enable_relative_includes(highest_priority=False)
    with config._change_dir_context(HERE):
      config.parse_config_file('subdir/main.gin')
    self.assertEqual(config.query_parameter('f.x'), 'root')
    config.enable_relative_includes(highest_priority=True)
    with config._change_dir_context(HERE):
      config.parse_config_file('subdir/main.gin')
    self.assertEqual(config.query_parameter('f.x'), 'subdir')
    self.assertEqual(len(config._FILE_READERS), 2)


if __name__ == '__main__':
  absltest.main()
