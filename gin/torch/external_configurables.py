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

"""Supplies a default set of configurables from PyTorch."""

from gin import config

import torch

# Losses.

config.external_configurable(
    torch.nn.modules.loss.BCELoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.BCEWithLogitsLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.CosineEmbeddingLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.CrossEntropyLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.CTCLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.HingeEmbeddingLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.KLDivLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.L1Loss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MarginRankingLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MSELoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiLabelMarginLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiLabelSoftMarginLoss,
    module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.MultiMarginLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.NLLLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.NLLLoss2d, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.PoissonNLLLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.SmoothL1Loss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.SoftMarginLoss, module='torch.nn.modules.loss')
config.external_configurable(
    torch.nn.modules.loss.TripletMarginLoss, module='torch.nn.modules.loss')

# Optimizers.

config.external_configurable(torch.optim.Adadelta, module='torch.optim')
config.external_configurable(torch.optim.Adagrad, module='torch.optim')
config.external_configurable(torch.optim.Adam, module='torch.optim')
config.external_configurable(torch.optim.Adamax, module='torch.optim')
config.external_configurable(torch.optim.AdamW, module='torch.optim')
config.external_configurable(torch.optim.ASGD, module='torch.optim')
config.external_configurable(torch.optim.LBFGS, module='torch.optim')
config.external_configurable(torch.optim.RMSprop, module='torch.optim')
config.external_configurable(torch.optim.Rprop, module='torch.optim')
config.external_configurable(torch.optim.SGD, module='torch.optim')
config.external_configurable(torch.optim.SparseAdam, module='torch.optim')

# Learning rate schedulers.

config.external_configurable(
    torch.optim.lr_scheduler.CosineAnnealingLR,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.CosineAnnealingWarmRestarts,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.CyclicLR, module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.ExponentialLR, module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.LambdaLR, module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.MultiStepLR, module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.OneCycleLR, module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.ReduceLROnPlateau,
    module='torch.optim.lr_scheduler')
config.external_configurable(
    torch.optim.lr_scheduler.StepLR, module='torch.optim.lr_scheduler')

# Activation functions.

config.external_configurable(
    torch.nn.modules.activation.CELU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ELU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.GLU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Hardshrink,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Hardtanh, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LeakyReLU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LogSigmoid,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.LogSoftmax,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.MultiheadAttention,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.PReLU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ReLU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.ReLU6, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.RReLU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.SELU, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Sigmoid, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmax, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmax2d, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softmin, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softplus, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softshrink,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Softsign, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Tanh, module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Tanhshrink,
    module='torch.nn.modules.activation')
config.external_configurable(
    torch.nn.modules.activation.Threshold, module='torch.nn.modules.activation')

# Random distributions.

config.external_configurable(
    torch.distributions.bernoulli.Bernoulli,
    module='torch.distributions.bernoulli')
config.external_configurable(
    torch.distributions.beta.Beta, module='torch.distributions.beta')
config.external_configurable(
    torch.distributions.binomial.Binomial,
    module='torch.distributions.binomial')
config.external_configurable(
    torch.distributions.categorical.Categorical,
    module='torch.distributions.categorical')
config.external_configurable(
    torch.distributions.cauchy.Cauchy, module='torch.distributions.cauchy')
config.external_configurable(
    torch.distributions.chi2.Chi2, module='torch.distributions.chi2')
config.external_configurable(
    torch.distributions.dirichlet.Dirichlet,
    module='torch.distributions.dirichlet')
config.external_configurable(
    torch.distributions.exponential.Exponential,
    module='torch.distributions.exponential')
config.external_configurable(
    torch.distributions.fishersnedecor.FisherSnedecor,
    module='torch.distributions.fishersnedecor')
config.external_configurable(
    torch.distributions.gamma.Gamma, module='torch.distributions.gamma')
config.external_configurable(
    torch.distributions.geometric.Geometric,
    module='torch.distributions.geometric')
config.external_configurable(
    torch.distributions.gumbel.Gumbel, module='torch.distributions.gumbel')
config.external_configurable(
    torch.distributions.half_cauchy.HalfCauchy,
    module='torch.distributions.half_cauchy')
config.external_configurable(
    torch.distributions.half_normal.HalfNormal,
    module='torch.distributions.half_normal')
config.external_configurable(
    torch.distributions.independent.Independent,
    module='torch.distributions.independent')
config.external_configurable(
    torch.distributions.laplace.Laplace, module='torch.distributions.laplace')
config.external_configurable(
    torch.distributions.log_normal.LogNormal,
    module='torch.distributions.log_normal')
config.external_configurable(
    torch.distributions.lowrank_multivariate_normal.LowRankMultivariateNormal,
    module='torch.distributions.lowrank_multivariate_normal')
config.external_configurable(
    torch.distributions.multinomial.Multinomial,
    module='torch.distributions.multinomial')
config.external_configurable(
    torch.distributions.multivariate_normal.MultivariateNormal,
    module='torch.distributions.multivariate_normal')
config.external_configurable(
    torch.distributions.negative_binomial.NegativeBinomial,
    module='torch.distributions.negative_binomial')
config.external_configurable(
    torch.distributions.normal.Normal, module='torch.distributions.normal')
config.external_configurable(
    torch.distributions.one_hot_categorical.OneHotCategorical,
    module='torch.distributions.one_hot_categorical')
config.external_configurable(
    torch.distributions.pareto.Pareto, module='torch.distributions.pareto')
config.external_configurable(
    torch.distributions.poisson.Poisson, module='torch.distributions.poisson')
config.external_configurable(
    torch.distributions.relaxed_bernoulli.LogitRelaxedBernoulli,
    module='torch.distributions.relaxed_bernoulli')
config.external_configurable(
    torch.distributions.relaxed_bernoulli.RelaxedBernoulli,
    module='torch.distributions.relaxed_bernoulli')
config.external_configurable(
    torch.distributions.relaxed_categorical.RelaxedOneHotCategorical,
    module='torch.distributions.relaxed_categorical')
config.external_configurable(
    torch.distributions.studentT.StudentT,
    module='torch.distributions.studentT')
config.external_configurable(
    torch.distributions.uniform.Uniform, module='torch.distributions.uniform')
config.external_configurable(
    torch.distributions.weibull.Weibull, module='torch.distributions.weibull')

# Constants

config.constant('torch.float16', torch.float16)
config.constant('torch.float32', torch.float32)
config.constant('torch.float64', torch.float64)
config.constant('torch.int8', torch.int8)
config.constant('torch.uint8', torch.uint8)
config.constant('torch.int16', torch.int16)
config.constant('torch.int32', torch.int32)
config.constant('torch.int64', torch.int64)
