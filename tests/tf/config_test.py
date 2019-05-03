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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gin.tf
import six

import tensorflow as tf


class TFConfigTest(tf.test.TestCase):

  def tearDown(self):
    gin.clear_config()
    super(TFConfigTest, self).tearDown()

  def testAugmentExceptionMessageOnTFError(self):
    @gin.configurable('config_name')
    def broken(sess):
      index = tf.compat.v1.placeholder(tf.int32, name='index')
      slice_op = tf.range(10)[index]
      sess.run(slice_op, feed_dict={index: 11})

    with tf.Graph().as_default():
      with self.test_session() as sess:
        with self.assertRaises(tf.errors.InvalidArgumentError) as assert_raises:
          broken(sess)

        self.assertIn(assert_raises.exception.message,
                      str(assert_raises.exception))
        # Note that in Python3 (but not Python2) the function name will be in
        # the exception message, which is caught with the '\S*'.
        self.assertRegex(
            str(assert_raises.exception),
            r"'config_name' \(<function \S*broken")
        self.assertEqual(assert_raises.exception.op.name, 'strided_slice')


if __name__ == '__main__':
  tf.test.main()
