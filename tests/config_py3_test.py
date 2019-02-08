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

# python3

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import absltest

from gin import config


@config.configurable
def fn_with_kw_only_args(arg1, *, kwarg1=None):
  return arg1, kwarg1


class ConfigTest(absltest.TestCase):

  def tearDown(self):
    config.clear_config()
    super(ConfigTest, self).tearDown()

  def testKwOnlyArgs(self):
    config_str = """
      fn_with_kw_only_args.arg1 = 'arg1'
      fn_with_kw_only_args.kwarg1 = 'kwarg1'
    """

    arg, kwarg = fn_with_kw_only_args(None)
    self.assertEqual(arg, None)
    self.assertEqual(kwarg, None)
    self.assertIn('fn_with_kw_only_args.kwarg1 = None',
                  config.operative_config_str())

    config.parse_config(config_str)

    arg, kwarg = fn_with_kw_only_args('arg1')
    self.assertEqual(arg, 'arg1')
    self.assertEqual(kwarg, 'kwarg1')
    self.assertIn("fn_with_kw_only_args.kwarg1 = 'kwarg1'",
                  config.operative_config_str())


if __name__ == '__main__':
  absltest.main()
