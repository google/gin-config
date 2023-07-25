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

"""Supplies a default set of configurables from core scikit-learn."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gin import config

import sklearn


# Most of the classes mentioned in the docs:
# https://scikit-learn.org/stable/modules/classes.html

# Clustering
import sklearn.cluster
gin.external_configurable(sklearn.cluster.AffinityPropagation)
gin.external_configurable(sklearn.cluster.AgglomerativeClustering)
gin.external_configurable(sklearn.cluster.Birch)
gin.external_configurable(sklearn.cluster.DBSCAN)
gin.external_configurable(sklearn.cluster.FeatureAgglomeration)
gin.external_configurable(sklearn.cluster.KMeans)
gin.external_configurable(sklearn.cluster.MiniBatchKMeans)
gin.external_configurable(sklearn.cluster.MeanShift)
gin.external_configurable(sklearn.cluster.OPTICS)
gin.external_configurable(sklearn.cluster.SpectralClustering)
gin.external_configurable(sklearn.cluster.SpectralBiclustering)
gin.external_configurable(sklearn.cluster.SpectralCoclustering)

# Cross Decomposition
import sklearn.cross_decomposition
gin.external_configurable(sklearn.cross_decomposition.CCA)
gin.external_configurable(sklearn.cross_decomposition.PLSCanonical)
gin.external_configurable(sklearn.cross_decomposition.PLSRegression)
gin.external_configurable(sklearn.cross_decomposition.PLSSVD)

# Decomposition
import sklearn.decomposition
gin.external_configurable(sklearn.decomposition.DictionaryLearning)
gin.external_configurable(sklearn.decomposition.FactorAnalysis)
gin.external_configurable(sklearn.decomposition.FastICA)
gin.external_configurable(sklearn.decomposition.IncrementalPCA)
gin.external_configurable(sklearn.decomposition.KernelPCA)
gin.external_configurable(sklearn.decomposition.LatentDirichletAllocation)
gin.external_configurable(sklearn.decomposition.MiniBatchDictionaryLearning)
gin.external_configurable(sklearn.decomposition.MiniBatchSparsePCA)
gin.external_configurable(sklearn.decomposition.NMF)
gin.external_configurable(sklearn.decomposition.PCA)
gin.external_configurable(sklearn.decomposition.SparsePCA)
gin.external_configurable(sklearn.decomposition.SparseCoder)
gin.external_configurable(sklearn.decomposition.TruncatedSVD)

# Discriminant Analysis
import sklearn.discriminant_analysis
gin.external_configurable(sklearn.discriminant_analysis.LinearDiscriminantAnalysis)
gin.external_configurable(sklearn.discriminant_analysis.QuadraticDiscriminantAnalysis)

# Ensemble
import sklearn.ensemble
gin.external_configurable(sklearn.ensemble.AdaBoostClassifier)
gin.external_configurable(sklearn.ensemble.AdaBoostRegressor)
gin.external_configurable(sklearn.ensemble.BaggingClassifier)
gin.external_configurable(sklearn.ensemble.BaggingRegressor)
gin.external_configurable(sklearn.ensemble.ExtraTreesClassifier)
gin.external_configurable(sklearn.ensemble.ExtraTreesRegressor)
gin.external_configurable(sklearn.ensemble.GradientBoostingClassifier)
gin.external_configurable(sklearn.ensemble.GradientBoostingRegressor)
gin.external_configurable(sklearn.ensemble.IsolationForest)
gin.external_configurable(sklearn.ensemble.RandomForestClassifier)
gin.external_configurable(sklearn.ensemble.RandomForestRegressor)
gin.external_configurable(sklearn.ensemble.StackingClassifier)
gin.external_configurable(sklearn.ensemble.StackingRegressor)
gin.external_configurable(sklearn.ensemble.VotingClassifier)
gin.external_configurable(sklearn.ensemble.VotingRegressor)

# Feature Extraction
import sklearn.feature_extraction
gin.external_configurable(sklearn.feature_extraction.DictVectorizer)
gin.external_configurable(sklearn.feature_extraction.FeatureHasher)
gin.external_configurable(sklearn.feature_extraction.image.extract_patches_2d)
gin.external_configurable(sklearn.feature_extraction.image.grid_to_graph)
gin.external_configurable(sklearn.feature_extraction.image.img_to_graph)
gin.external_configurable(sklearn.feature_extraction.image.reconstruct_from_patches_2d)
gin.external_configurable(sklearn.feature_extraction.image.PatchExtractor)
gin.external_configurable(sklearn.feature_extraction.text.CountVectorizer)
gin.external_configurable(sklearn.feature_extraction.text.HashingVectorizer)
gin.external_configurable(sklearn.feature_extraction.text.TfidfTransformer)
gin.external_configurable(sklearn.feature_extraction.text.TfidfVectorizer)

# Feature Selection
import sklearn.feature_selection
gin.external_configurable(sklearn.feature_selection.GenericUnivariateSelect)
gin.external_configurable(sklearn.feature_selection.SelectPercentile)
gin.external_configurable(sklearn.feature_selection.SelectKBest)
gin.external_configurable(sklearn.feature_selection.SelectFpr)
gin.external_configurable(sklearn.feature_selection.SelectFdr)
gin.external_configurable(sklearn.feature_selection.SelectFromModel)
gin.external_configurable(sklearn.feature_selection.SelectFwe)
gin.external_configurable(sklearn.feature_selection.RFE)
gin.external_configurable(sklearn.feature_selection.RFECV)
gin.external_configurable(sklearn.feature_selection.VarianceThreshold)
gin.external_configurable(sklearn.feature_selection.chi2)
gin.external_configurable(sklearn.feature_selection.f_classif)
gin.external_configurable(sklearn.feature_selection.f_regression)
gin.external_configurable(sklearn.feature_selection.mutual_info_classif)
gin.external_configurable(sklearn.feature_selection.mutual_info_regression)

# Gaussian Processes
import sklearn.gaussian_process
gin.external_configurable(sklearn.gaussian_process.GaussianProcessRegressor)
gin.external_configurable(sklearn.gaussian_process.GaussianProcessClassifier)
gin.external_configurable(sklearn.gaussian_process.kernels.CompoundKernel)
gin.external_configurable(sklearn.gaussian_process.kernels.ConstantKernel)
gin.external_configurable(sklearn.gaussian_process.kernels.DotProduct)
gin.external_configurable(sklearn.gaussian_process.kernels.ExpSineSquared)
gin.external_configurable(sklearn.gaussian_process.kernels.Exponentiation)
gin.external_configurable(sklearn.gaussian_process.kernels.Hyperparameter)
gin.external_configurable(sklearn.gaussian_process.kernels.Matern)
gin.external_configurable(sklearn.gaussian_process.kernels.PairwiseKernel)
gin.external_configurable(sklearn.gaussian_process.kernels.Product)
gin.external_configurable(sklearn.gaussian_process.kernels.RBF)
gin.external_configurable(sklearn.gaussian_process.kernels.RationalQuadratic)
gin.external_configurable(sklearn.gaussian_process.kernels.Sum)
gin.external_configurable(sklearn.gaussian_process.kernels.WhiteKernel)

# Impute
import sklearn.impute
gin.external_configurable(sklearn.impute.SimpleImputer)
gin.external_configurable(sklearn.impute.MissingIndicator)
gin.external_configurable(sklearn.impute.KNNImputer)

# Isotonic
import sklearn.isotonic
gin.external_configurable(sklearn.isotonic.IsotonicRegression)

# Kernel Approximation
import sklearn.kernel_approximation
gin.external_configurable(sklearn.kernel_approximation.AdditiveChi2Sampler)
gin.external_configurable(sklearn.kernel_approximation.Nystroem)
gin.external_configurable(sklearn.kernel_approximation.RBFSampler)
gin.external_configurable(sklearn.kernel_approximation.SkewedChi2Sampler)

# Kernel Ridge Regression
import sklearn.kernel_ridge
gin.external_configurable(sklearn.kernel_ridge.KernelRidge)

# Linear Classifiers
import sklearn.linear_model
gin.external_configurable(sklearn.linear_model.LogisticRegression)
gin.external_configurable(sklearn.linear_model.LogisticRegressionCV)
gin.external_configurable(sklearn.linear_model.PassiveAggressiveClassifier)
gin.external_configurable(sklearn.linear_model.Perceptron)
gin.external_configurable(sklearn.linear_model.RidgeClassifier)
gin.external_configurable(sklearn.linear_model.RidgeClassifierCV)
gin.external_configurable(sklearn.linear_model.SGDClassifier)

# Classical Linear Regressors
gin.external_configurable(sklearn.linear_model.LinearRegression)
gin.external_configurable(sklearn.linear_model.Ridge)
gin.external_configurable(sklearn.linear_model.RidgeCV)
gin.external_configurable(sklearn.linear_model.SGDRegressor)

# Regressors with variable selection
gin.external_configurable(sklearn.linear_model.ElasticNet)
gin.external_configurable(sklearn.linear_model.ElasticNetCV)
gin.external_configurable(sklearn.linear_model.Lars)
gin.external_configurable(sklearn.linear_model.LarsCV)
gin.external_configurable(sklearn.linear_model.Lasso)
gin.external_configurable(sklearn.linear_model.LassoCV)
gin.external_configurable(sklearn.linear_model.LassoLars)
gin.external_configurable(sklearn.linear_model.LassoLarsCV)
gin.external_configurable(sklearn.linear_model.OrthogonalMatchingPursuit)
gin.external_configurable(sklearn.linear_model.OrthogonalMatchingPursuitCV)

# Bayesian Regressors
gin.external_configurable(sklearn.linear_model.ARDRegression)
gin.external_configurable(sklearn.linear_model.BayesianRidge)

# Multi-task Linear Regressors with Variable Selection
gin.external_configurable(sklearn.linear_model.MultiTaskElasticNet)
gin.external_configurable(sklearn.linear_model.MultiTaskElasticNetCV)
gin.external_configurable(sklearn.linear_model.MultiTaskLasso)
gin.external_configurable(sklearn.linear_model.MultiTaskLassoCV)

# Outlier-robust Regressors
gin.external_configurable(sklearn.linear_model.HuberRegressor)
gin.external_configurable(sklearn.linear_model.RANSACRegressor)
gin.external_configurable(sklearn.linear_model.TheilSenRegressor)

# Miscellaneous
gin.external_configurable(sklearn.linear_model.PassiveAggressiveRegressor)

# Manifold
import sklearn.manifold
gin.external_configurable(sklearn.manifold.Isomap)
gin.external_configurable(sklearn.manifold.LocallyLinearEmbedding)
gin.external_configurable(sklearn.manifold.MDS)
gin.external_configurable(sklearn.manifold.SpectralEmbedding)
gin.external_configurable(sklearn.manifold.TSNE)

# Mixture Models
import sklearn.mixture
gin.external_configurable(sklearn.mixture.GaussianMixture)
gin.external_configurable(sklearn.mixture.BayesianGaussianMixture)

# Multiclass
import sklearn.multiclass
gin.external_configurable(sklearn.multiclass.OneVsRestClassifier)
gin.external_configurable(sklearn.multiclass.OneVsOneClassifier)
gin.external_configurable(sklearn.multiclass.OutputCodeClassifier)

# Multioutput
import sklearn.multioutput
gin.external_configurable(sklearn.multioutput.ClassifierChain)
gin.external_configurable(sklearn.multioutput.MultiOutputRegressor)
gin.external_configurable(sklearn.multioutput.MultiOutputClassifier)
gin.external_configurable(sklearn.multioutput.RegressorChain)

# Naive Bayes
import sklearn.naive_bayes
gin.external_configurable(sklearn.naive_bayes.BernoulliNB)
gin.external_configurable(sklearn.naive_bayes.CategoricalNB)
gin.external_configurable(sklearn.naive_bayes.ComplementNB)
gin.external_configurable(sklearn.naive_bayes.GaussianNB)
gin.external_configurable(sklearn.naive_bayes.MultinomialNB)

# Nearest Neighbors
import sklearn.neighbors
gin.external_configurable(sklearn.neighbors.BallTree)
gin.external_configurable(sklearn.neighbors.KDTree)
gin.external_configurable(sklearn.neighbors.KNeighborsClassifier)
gin.external_configurable(sklearn.neighbors.KNeighborsRegressor)
gin.external_configurable(sklearn.neighbors.LocalOutlierFactor)
gin.external_configurable(sklearn.neighbors.RadiusNeighborsClassifier)
gin.external_configurable(sklearn.neighbors.RadiusNeighborsRegressor)
gin.external_configurable(sklearn.neighbors.NearestCentroid)
gin.external_configurable(sklearn.neighbors.NearestNeighbors)
gin.external_configurable(sklearn.neighbors.NeighborhoodComponentsAnalysis)

# Pipeline
import sklearn.pipeline
gin.external_configurable(sklearn.pipeline.FeatureUnion)
gin.external_configurable(sklearn.pipeline.Pipeline)

# Preprocessing
import sklearn.preprocessing
gin.external_configurable(sklearn.preprocessing.Binarizer)
gin.external_configurable(sklearn.preprocessing.FunctionTransformer)
gin.external_configurable(sklearn.preprocessing.KBinsDiscretizer)
gin.external_configurable(sklearn.preprocessing.KernelCenterer)
gin.external_configurable(sklearn.preprocessing.LabelBinarizer)
gin.external_configurable(sklearn.preprocessing.LabelEncoder)
gin.external_configurable(sklearn.preprocessing.MultiLabelBinarizer)
gin.external_configurable(sklearn.preprocessing.MaxAbsScaler)
gin.external_configurable(sklearn.preprocessing.MinMaxScaler)
gin.external_configurable(sklearn.preprocessing.Normalizer)
gin.external_configurable(sklearn.preprocessing.OneHotEncoder)
gin.external_configurable(sklearn.preprocessing.OrdinalEncoder)
gin.external_configurable(sklearn.preprocessing.PolynomialFeatures)
gin.external_configurable(sklearn.preprocessing.PowerTransformer)
gin.external_configurable(sklearn.preprocessing.QuantileTransformer)
gin.external_configurable(sklearn.preprocessing.RobustScaler)
gin.external_configurable(sklearn.preprocessing.StandardScaler)

# Random Projection
import sklearn.random_projection
gin.external_configurable(sklearn.random_projection.GaussianRandomProjection)
gin.external_configurable(sklearn.random_projection.SparseRandomProjection)

# Support Vector Machines
import sklearn.svm
gin.external_configurable(sklearn.svm.LinearSVC)
gin.external_configurable(sklearn.svm.LinearSVR)
gin.external_configurable(sklearn.svm.NuSVC)
gin.external_configurable(sklearn.svm.NuSVR)
gin.external_configurable(sklearn.svm.OneClassSVM)
gin.external_configurable(sklearn.svm.SVC)
gin.external_configurable(sklearn.svm.SVR)

# Decision Trees
import sklearn.tree
gin.external_configurable(sklearn.tree.DecisionTreeClassifier)
gin.external_configurable(sklearn.tree.DecisionTreeRegressor)
gin.external_configurable(sklearn.tree.ExtraTreeClassifier)
gin.external_configurable(sklearn.tree.ExtraTreeRegressor)
