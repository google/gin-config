# coding=utf-8
# Copyright 2019 The Gin-Config Authors.
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

import torch

from absl.testing import absltest

from gin import config
from gin.torch import external_configurables  # pylint: disable=unused-import


@config.configurable
def fake_train_model(learning_rate, optimizer, scheduler=None):
    # pylint: disable=E1101
    opt = optimizer([torch.rand(10), torch.rand(10)], lr=learning_rate)
    # pylint: enable=E1101
    sch = None
    if scheduler:
        sch = scheduler(opt)
    return opt, sch


@config.configurable
def configurable(**kwargs):
    return kwargs


class PyTorchConfigTest(absltest.TestCase):

    def assertAlmostEqualList(self, xs, ys):
        for x, y in zip(xs, ys):
            self.assertAlmostEqual(x, y)

    def tearDown(self):
        config.clear_config()
        super(PyTorchConfigTest, self).tearDown()

    def testConfigureOptimizerAndLearningRate(self):
        config_str = """
            fake_train_model.learning_rate = 0.001
            fake_train_model.optimizer = @Adam
            torch.optim.Adam.betas = (0.8, 0.888)

            fake_train_model.scheduler = @StepLR
            StepLR.step_size = 10
        """
        config.parse_config(config_str)

        opt, sch = fake_train_model()  # pylint: disable=no-value-for-parameter

        self.assertIsInstance(opt, torch.optim.Adam)
        self.assertAlmostEqual(opt.param_groups[0]['betas'][0], 0.8)
        self.assertAlmostEqual(opt.param_groups[0]['betas'][1], 0.888)
        self.assertAlmostEqual(opt.defaults['betas'][0], 0.8)
        self.assertAlmostEqual(opt.defaults['betas'][1], 0.888)
        self.assertAlmostEqual(sch.step_size, 10)

        lrs = []
        for _ in range(15):
            lrs.append(opt.param_groups[0]['lr'])
            sch.step()

        # Divide lr in tenth epoch by 10
        target_lrs = [0.001, 0.001, 0.001, 0.001, 0.001,
                      0.001, 0.001, 0.001, 0.001, 0.001,
                      0.0001, 0.0001, 0.0001, 0.0001, 0.0001]

        self.assertAlmostEqualList(lrs, target_lrs)

    def testOptimizersWithDefaults(self):
        optimizers = [
            torch.optim.Adadelta,
            torch.optim.Adagrad,
            torch.optim.Adam,
            torch.optim.SparseAdam,
            torch.optim.Adamax,
            torch.optim.ASGD,
            torch.optim.LBFGS,
            torch.optim.RMSprop,
            torch.optim.Rprop,
            torch.optim.SGD,
        ]
        for optimizer in optimizers:
            config.clear_config()
            config_lines = ['fake_train_model.optimizer = @{}'
                            .format(optimizer.__name__)]
            config.parse_config(config_lines)

        # pylint: disable=no-value-for-parameter
        configed_optimizer, _ = fake_train_model(0.001)
        # pylint: enable=no-value-for-parameter
        self.assertIsInstance(configed_optimizer, optimizer)

    def testDtypes(self):
        # Spot check a few.
        config_str = """
            # Test without torch prefix, but using the
            # prefix is strongly recommended!
            configurable.float32 = %float32
            # Test with torch prefix.
            configurable.int8 = %torch.int8
            configurable.float16 = %torch.float16
        """
        config.parse_config(config_str)

        vals = configurable()
        # pylint: disable=E1101
        self.assertIs(vals['float32'], torch.float32)
        self.assertIs(vals['int8'], torch.int8)
        self.assertIs(vals['float16'], torch.float16)
        # pylint: disable=E1101

if __name__ == '__main__':
    absltest.main()
