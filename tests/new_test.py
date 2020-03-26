# Copyright (c) 2019 Horizon Robotics. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from absl.testing import absltest
import gin


class ConfigTest(absltest.TestCase):
  def setUp(self):
    gin.clear_config()

  def testReferVariable(self):
    @gin.configurable
    def test_add(a, b):
      return a + b

    # Local variable
    gin.parse_config([
      'A=3',
      'test_add.a=%A',
      'test_add.b=b'])
    b = 5
    self.assertEqual(test_add(), 3 + 5)
    b = 3
    self.assertEqual(test_add(), 3 + 3)

    # Global variable
    import numpy as np
    gin.clear_config()
    gin.parse_config([
      'A=3',
      'test_add.a=%A',
      'test_add.b=np.pi'])
    self.assertEqual(test_add(), 3 + np.pi)

  def testReferUnregisteredFunction(self):
    @gin.configurable
    def test_func(func):
      return func()

    def un_registered_func():
      return 2

    gin.parse_config([
      'test_func.func=un_registered_func'
    ])
    self.assertEqual(test_func(), 2)

  def testReferFunctionCall(self):
    @gin.configurable
    def registered_add(a, b):
      return a + b

    def unregistered_add(a, b):
      return a + b

    @gin.configurable
    def test_sum(a, b, c, d):
      return a + b + c + d

    gin.parse_config([
      'A=1',
      'B=2',
      'C=3',
      'D=4',
      'test_sum.a=%A',
      'test_sum.b=@registered_add(%B, b)',
      'test_sum.c=unregistered_add(%C, c)',
      'test_sum.d=sum([@registered_add(%D, d), unregistered_add(%D, d)])'
    ])
    a, b, c, d = 1, 2, 3, 4
    self.assertEqual(test_sum(), 27)
    a, b, c, d = -1, -2, -3, -4
    self.assertEqual(test_sum(), 1)


if __name__ == '__main__':
  absltest.main()
