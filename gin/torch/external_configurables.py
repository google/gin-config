# coding=utf-8
# Copyright 2019 Georgios Paraskevopoulos.
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

"""Supplies a default set of configurables from core TensorFlow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch

from gin import config


##############
# Optimizers #
##############

config.external_configurable(torch.optim.Adadelta, module='torch.optim')
config.external_configurable(torch.optim.Adagrad, module='torch.optim')
config.external_configurable(torch.optim.Adam, module='torch.optim')
config.external_configurable(torch.optim.SparseAdam, module='torch.optim')
config.external_configurable(torch.optim.Adamax, module='torch.optim')
config.external_configurable(torch.optim.ASGD, module='torch.optim')
config.external_configurable(torch.optim.LBFGS, module='torch.optim')
config.external_configurable(torch.optim.RMSprop, module='torch.optim')
config.external_configurable(torch.optim.Rprop, module='torch.optim')
config.external_configurable(torch.optim.SGD, module='torch.optim')


#############################
# Learning rate schedulers. #
#############################

config.external_configurable(
    torch.optim.lr_scheduler.LambdaLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.StepLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.MultiStepLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.ExponentialLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.CosineAnnealingLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.ReduceLROnPlateau,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.CyclicLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.CosineAnnealingWarmRestarts,
    module='torch.optim.lr_scheduler')


###########
# Losses. #
###########

config.external_configurable(
    torch.nn.modules.loss.L1Loss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.NLLLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.NLLLoss2d,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.PoissonNLLLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.KLDivLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MSELoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.BCELoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.BCEWithLogitsLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.HingeEmbeddingLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiLabelMarginLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.SmoothL1Loss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.SoftMarginLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.CrossEntropyLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiLabelSoftMarginLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.CosineEmbeddingLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MarginRankingLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiMarginLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.TripletMarginLoss,
    module='torch.nn.modules.loss')


#########################
# Activation functions. #
#########################

config.external_configurable(
    torch.nn.modules.activation.Threshold,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ReLU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.RReLU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Hardtanh,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ReLU6,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Sigmoid,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Tanh,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ELU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.CELU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.SELU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.GLU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Hardshrink,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LeakyReLU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LogSigmoid,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softplus,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softshrink,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.MultiheadAttention,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.PReLU,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softsign,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Tanhshrink,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmin,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmax,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmax2d,
    'torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LogSoftmax,
    'torch.nn.modules.activation')


#########################
# Random distributions. #
#########################

config.external_configurable(
    torch.distributions.bernoulli.Bernoulli,
    'torch.distributions.bernoulli')
config.external_configurable(
    torch.distributions.beta.Beta,
    'torch.distributions.beta')
config.external_configurable(
    torch.distributions.binomial.Binomial,
    'torch.distributions.binomial')
config.external_configurable(
    torch.distributions.categorical.Categorical,
    'torch.distributions.categorical')
config.external_configurable(
    torch.distributions.cauchy.Cauchy,
    'torch.distributions.cauchy')
config.external_configurable(
    torch.distributions.chi2.Chi2,
    'torch.distributions.chi2')
config.external_configurable(
    torch.distributions.dirichlet.Dirichlet,
    'torch.distributions.dirichlet')
config.external_configurable(
    torch.distributions.exponential.Exponential,
    'torch.distributions.exponential')
config.external_configurable(
    torch.distributions.fishersnedecor.FisherSnedecor,
    'torch.distributions.fishersnedecor')
config.external_configurable(
    torch.distributions.gamma.Gamma,
    'torch.distributions.gamma')
config.external_configurable(
    torch.distributions.geometric.Geometric,
    'torch.distributions.geometric')
config.external_configurable(
    torch.distributions.gumbel.Gumbel,
    'torch.distributions.gumbel')
config.external_configurable(
    torch.distributions.half_cauchy.HalfCauchy,
    'torch.distributions.half_cauchy')
config.external_configurable(
    torch.distributions.half_normal.HalfNormal,
    'torch.distributions.half_normal')
config.external_configurable(
    torch.distributions.independent.Independent,
    'torch.distributions.independent')
config.external_configurable(
    torch.distributions.laplace.Laplace,
    'torch.distributions.laplace')
config.external_configurable(
    torch.distributions.log_normal.LogNormal,
    'torch.distributions.log_normal')
config.external_configurable(
    torch.distributions.lowrank_multivariate_normal.LowRankMultivariateNormal,
    'torch.distributions.lowrank_multivariate_normal')
config.external_configurable(
    torch.distributions.multinomial.Multinomial,
    'torch.distributions.multinomial')
config.external_configurable(
    torch.distributions.multivariate_normal.MultivariateNormal,
    'torch.distributions.multivariate_normal')
config.external_configurable(
    torch.distributions.negative_binomial.NegativeBinomial,
    'torch.distributions.negative_binomial')
config.external_configurable(
    torch.distributions.normal.Normal,
    'torch.distributions.normal')
config.external_configurable(
    torch.distributions.one_hot_categorical.OneHotCategorical,
    'torch.distributions.one_hot_categorical')
config.external_configurable(
    torch.distributions.pareto.Pareto,
    'torch.distributions.pareto')
config.external_configurable(
    torch.distributions.poisson.Poisson,
    'torch.distributions.poisson')
config.external_configurable(
    torch.distributions.relaxed_bernoulli.RelaxedBernoulli,
    'torch.distributions.relaxed_bernoulli')
config.external_configurable(
    torch.distributions.relaxed_bernoulli.LogitRelaxedBernoulli,
    'torch.distributions.relaxed_bernoulli')
config.external_configurable(
    torch.distributions.relaxed_categorical.RelaxedOneHotCategorical,
    'torch.distributions.relaxed_categorical')
config.external_configurable(
    torch.distributions.studentT.StudentT,
    'torch.distributions.studentT')
config.external_configurable(
    torch.distributions.uniform.Uniform,
    'torch.distributions.uniform')
config.external_configurable(
    torch.distributions.weibull.Weibull,
    'torch.distributions.weibull')


#############
# Constants #
#############

config.constant('torch.float16', torch.float16)
config.constant('torch.float32', torch.float32)
config.constant('torch.float64', torch.float64)
config.constant('torch.int8', torch.int8)
config.constant('torch.uint8', torch.uint8)
config.constant('torch.int32', torch.int32)
config.constant('torch.int16', torch.int16)
config.constant('torch.int64', torch.int64)
