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

import tensorflow as tf

from gin import config

# pylint: disable=unused-import
from gin.tf import external_configurables
# pylint: enable=unused-import

# Necessary for AdagradaDAOptimizer test.
config.external_configurable(tf.train.get_global_step)


@config.configurable
def fake_train_model(learning_rate, optimizer):
  global_step = tf.train.get_or_create_global_step()
  lr = learning_rate(global_step=global_step)
  opt = optimizer(learning_rate=lr)
  return lr, opt


@config.configurable
def configurable(**kwargs):
  return kwargs


class TFConfigTest(tf.test.TestCase):

  def tearDown(self):
    config.clear_config()

  def testConfigureOptimizerAndLearningRate(self):
    config_str = """
      fake_train_model.learning_rate = @piecewise_constant
      piecewise_constant.boundaries = [200000]
      piecewise_constant.values = [0.01, 0.001]

      fake_train_model.optimizer = @MomentumOptimizer
      MomentumOptimizer.momentum = 0.95
    """
    config.parse_config(config_str)

    lr, opt = fake_train_model()  # pylint: disable=no-value-for-parameter
    global_step = tf.contrib.framework.get_or_create_global_step()
    update_global_step = global_step.assign(300000)
    init = tf.global_variables_initializer()

    self.assertIsInstance(opt, tf.train.MomentumOptimizer)
    self.assertAlmostEqual(opt._momentum, 0.95)
    with self.test_session() as sess:
      sess.run(init)
      self.assertAlmostEqual(sess.run(lr), 0.01)
      sess.run(update_global_step)
      self.assertAlmostEqual(sess.run(lr), 0.001)

  def testOptimizersWithDefaults(self):
    optimizers = [
        tf.train.GradientDescentOptimizer,
        tf.train.AdadeltaOptimizer,
        tf.train.AdagradOptimizer,
        (tf.train.AdagradDAOptimizer, {'global_step': '@get_global_step()'}),
        (tf.train.MomentumOptimizer, {'momentum': 0.9}),
        tf.train.AdamOptimizer,
        tf.train.FtrlOptimizer,
        tf.train.ProximalGradientDescentOptimizer,
        tf.train.ProximalAdagradOptimizer,
        tf.train.RMSPropOptimizer,
    ]
    constant_lr = lambda global_step: 0.01
    for optimizer in optimizers:
      extra_bindings = {}
      if isinstance(optimizer, tuple):
        optimizer, extra_bindings = optimizer

      config.clear_config()
      config_lines = ['fake_train_model.optimizer = @%s' % optimizer.__name__]
      for param, val in extra_bindings.items():
        config_lines.append('%s.%s = %s' % (optimizer.__name__, param, val))
      config.parse_config(config_lines)

      # pylint: disable=no-value-for-parameter
      _, configed_optimizer = fake_train_model(constant_lr)
      # pylint: enable=no-value-for-parameter
      self.assertIsInstance(configed_optimizer, optimizer)

  def testDtypes(self):
    # Spot check a few.
    config_str = """
      # Test without tf prefix, but using the prefix is strongly recommended!
      configurable.float32 = %float32
      # Test with tf prefix.
      configurable.string = %tf.string
      configurable.qint8 = %tf.qint8
    """
    config.parse_config(config_str)

    vals = configurable()
    self.assertIs(vals['float32'], tf.float32)
    self.assertIs(vals['string'], tf.string)
    self.assertIs(vals['qint8'], tf.qint8)


if __name__ == '__main__':
  tf.test.main()
