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

from gin import config
from gin.tf import external_configurables  # pylint: disable=unused-import

import tensorflow as tf

# Necessary for AdagradaDAOptimizer test.
config.external_configurable(tf.compat.v1.train.get_global_step)


@config.configurable
def fake_train_model(learning_rate, optimizer):
  global_step = tf.compat.v1.train.get_or_create_global_step()
  lr = learning_rate(global_step=global_step)
  opt = optimizer(learning_rate=lr)
  return lr, opt


@config.configurable
def configurable(**kwargs):
  return kwargs


class TFConfigTest(tf.test.TestCase):

  def tearDown(self):
    config.clear_config()
    super(TFConfigTest, self).tearDown()

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

    self.assertIsInstance(opt, tf.compat.v1.train.MomentumOptimizer)
    self.assertAlmostEqual(opt._momentum, 0.95)

    global_step = tf.compat.v1.train.get_or_create_global_step()
    self.evaluate(tf.compat.v1.global_variables_initializer())
    self.assertAlmostEqual(self.evaluate(lr), 0.01)
    self.evaluate(global_step.assign(300000))
    self.assertAlmostEqual(self.evaluate(lr), 0.001)

  def testOptimizersWithDefaults(self):
    optimizers = [
        tf.compat.v1.train.GradientDescentOptimizer,
        tf.compat.v1.train.AdadeltaOptimizer,
        tf.compat.v1.train.AdagradOptimizer,
        (tf.compat.v1.train.AdagradDAOptimizer, {
            'global_step': '@get_global_step()'
        }),
        (tf.compat.v1.train.MomentumOptimizer, {
            'momentum': 0.9
        }),
        tf.compat.v1.train.AdamOptimizer,
        tf.compat.v1.train.FtrlOptimizer,
        tf.compat.v1.train.ProximalGradientDescentOptimizer,
        tf.compat.v1.train.ProximalAdagradOptimizer,
        tf.compat.v1.train.RMSPropOptimizer,
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

  def testDynamicRegistrationImportAsGinError(self):
    config_str = """
      from __gin__ import dynamic_registration
      import gin.tf.external_configurables
      import __main__

      __main__.configurable.arg = %gin.REQUIRED
    """
    expected_msg = 'The `gin` symbol is reserved; cannot bind import statement '
    with self.assertRaisesRegex(ValueError, expected_msg):
      config.parse_config(config_str)

  def testCompatibilityWithDynamicRegistration(self):
    config_str = """
      from __gin__ import dynamic_registration
      from gin.tf import external_configurables
      import __main__

      __main__.configurable.arg = %tf.float32
    """
    config.parse_config(config_str)
    self.assertEqual(configurable(), {'arg': tf.float32})


if __name__ == '__main__':
  tf.test.main()
