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

"""Defines the Gin configuration framework.

Programs frequently have a number of "hyperparameters" that require variation
across different executions of the program. When the number of such parameters
grows even moderately large, or use of some parameter is deeply embedded in the
code, top-level flags become very cumbersome. This module provides an
alternative mechanism for setting such hyperparameters, by allowing injection of
parameter values for any function marked as "configurable".

For detailed documentation, please see the user guide:

https://github.com/google/gin-config/tree/master/docs/index.md

# Making functions and classes configurable

Functions and classes can be marked configurable using the `@configurable`
decorator, which associates a "configurable name" with the function or class (by
default, just the function or class name). Optionally, parameters can be
whitelisted or blacklisted to mark only a subset of the function's parameters as
configurable. Once parameters have been bound (see below) to this function, any
subsequent calls will have those parameters automatically supplied by Gin.

If an argument supplied to a function by its caller (either as a positional
argument or as a keyword argument) corresponds to a parameter configured by Gin,
the caller's value will take precedence.

# A short example

Python code:

    @gin.configurable
    def mix_cocktail(ingredients):
      ...

    @gin.configurable
    def serve_random_cocktail(available_cocktails):
      ...

    @gin.configurable
    def drink(cocktail):
      ...

Gin configuration:

    martini/mix_cocktail.ingredients = ['gin', 'vermouth', 'twist of lemon']
    gin_and_tonic/mix_cocktail.ingredients = ['gin', 'tonic water']

    serve_random_cocktail.available_cocktails = {
        'martini': @martini/mix_cocktail,
        'gin_and_tonic': @gin_and_tonic/mix_cocktail,
    }

    drink.cocktail = @serve_random_cocktail()

In the above example, there are three configurable functions: `mix_cocktail`
(with a parameter `ingredients`), `serve_random_cocktail` (with parameter
`available_cocktails`), and `drink` (with parameter `cocktail`).

When `serve_random_cocktail` is called, it will receive a dictionary
containing two scoped *references* to the `mix_cocktail` function (each scope
providing unique parameters, meaning calling the different references will
presumably produce different outputs).

On the other hand, when the `drink` function is called, it will receive the
*output* of calling `serve_random_cocktail` as the value of its `cocktail`
parameter, due to the trailing `()` in `@serve_random_cocktail()`.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import contextlib
import copy
import functools
import inspect
import logging
import os
import pprint

import enum

from gin import config_parser
from gin import selector_map
from gin import utils

import six


# Maintains the registry of configurable functions and classes.
_REGISTRY = selector_map.SelectorMap()

# Maps tuples of `(scope, selector)` to associated parameter values. This
# specifies the current global "configuration" set through `bind_parameter` or
# `parse_config`, but doesn't include any functions' default argument values.
_CONFIG = {}

# Keeps a set of module names that were dynamically imported via config files.
_IMPORTED_MODULES = set()

# Maps `(scope, selector)` tuples to all configurable parameter values used
# during program execution (including default argument values).
_OPERATIVE_CONFIG = {}

# Keeps track of currently active config scopes, as a stack of lists of config
# scope names.
_ACTIVE_SCOPES = [[]]

# Keeps track of hooks to run when the Gin config is finalized.
_FINALIZE_HOOKS = []
# Keeps track of whether the config is locked.
_CONFIG_IS_LOCKED = False
# Keeps track of whether "interactive mode" is enabled, in which case redefining
# a configurable is not an error.
_INTERACTIVE_MODE = False

# Keeps track of constants created via gin.constant, to both prevent duplicate
# definitions and to avoid writing them to the operative config.
_CONSTANTS = selector_map.SelectorMap()

# Keeps track of singletons created via the singleton configurable.
_SINGLETONS = {}

# Keeps track of file readers. These are functions that behave like Python's
# `open` function (can be used a context manager) and will be used to load
# config files. Each element of this list should be a tuple of `(function,
# exception_type)`, where `exception_type` is the type of exception thrown by
# `function` when a file can't be opened/read successfully.
_FILE_READERS = [(open, os.path.isfile)]

# Maintains a cache of argspecs for functions.
_ARG_SPEC_CACHE = {}
# Maintains a cache of argument defaults for functions.
_ARG_DEFAULTS_CACHE = {}

REQUIRED = '__gin_required__'


def _find_class_construction_fn(cls):
  """Find the first __init__ or __new__ method in the given class's MRO."""
  for base in type.mro(cls):
    if '__init__' in base.__dict__:
      return base.__init__
    if '__new__' in base.__dict__:
      return base.__new__


def _ensure_wrappability(fn):
  """Make sure `fn` can be wrapped cleanly by functools.wraps."""
  # Handle "wrapped_descriptor" and "method-wrapper" types.
  if isinstance(fn, (type(object.__init__), type(object.__call__))):
    # pylint: disable=unnecessary-lambda
    wrappable_fn = lambda *args, **kwargs: fn(*args, **kwargs)
    wrappable_fn.__name__ = fn.__name__
    wrappable_fn.__doc__ = fn.__doc__
    wrappable_fn.__module__ = ''  # These types have no __module__, sigh.
    wrappable_fn.__wrapped__ = fn
    return wrappable_fn

  # Otherwise we're good to go...
  return fn


def _decorate_fn_or_cls(decorator, fn_or_cls, subclass=False):
  """Decorate a function or class with the given decorator.

  When `fn_or_cls` is a function, applies `decorator` to the function and
  returns the (decorated) result.

  When `fn_or_cls` is a class and the `subclass` parameter is `False`, this will
  replace `fn_or_cls.__init__` with the result of applying `decorator` to it.

  When `fn_or_cls` is a class and `subclass` is `True`, this will subclass the
  class, but with `__init__` defined to be the result of applying `decorator` to
  `fn_or_cls.__init__`. The decorated class has metadata (docstring, name, and
  module information) copied over from `fn_or_cls`. The goal is to provide a
  decorated class the behaves as much like the original as possible, without
  modifying it (for example, inspection operations using `isinstance` or
  `issubclass` should behave the same way as on the original class).

  Args:
    decorator: The decorator to use.
    fn_or_cls: The function or class to decorate.
    subclass: Whether to decorate classes by subclassing. This argument is
      ignored if `fn_or_cls` is not a class.

  Returns:
    The decorated function or class.
  """
  if not inspect.isclass(fn_or_cls):
    return decorator(_ensure_wrappability(fn_or_cls))

  construction_fn = _find_class_construction_fn(fn_or_cls)

  if subclass:
    class DecoratedClass(fn_or_cls):
      __doc__ = fn_or_cls.__doc__
      __module__ = fn_or_cls.__module__
    DecoratedClass.__name__ = fn_or_cls.__name__
    if six.PY3:
      DecoratedClass.__qualname__ = fn_or_cls.__qualname__
    cls = DecoratedClass
  else:
    cls = fn_or_cls

  decorated_fn = decorator(_ensure_wrappability(construction_fn))
  if construction_fn.__name__ == '__new__':
    decorated_fn = staticmethod(decorated_fn)
  setattr(cls, construction_fn.__name__, decorated_fn)
  return cls


class Configurable(
    collections.namedtuple('Configurable', [
        'fn_or_cls', 'name', 'module', 'whitelist', 'blacklist', 'selector'
    ])):
  pass


def _raise_unknown_reference_error(ref, additional_msg=''):
  err_str = "No configurable matching reference '@{}{}'.{}"
  maybe_parens = '()' if ref.evaluate else ''
  raise ValueError(err_str.format(ref.selector, maybe_parens, additional_msg))


class ConfigurableReference(object):
  """Represents a reference to a configurable function or class."""

  def __init__(self, scoped_selector, evaluate):
    self._scoped_selector = scoped_selector
    self._evaluate = evaluate

    scoped_selector_parts = self._scoped_selector.split('/')
    self._scopes = scoped_selector_parts[:-1]
    self._selector = scoped_selector_parts[-1]
    self._configurable = _REGISTRY.get_match(self._selector)
    if not self._configurable:
      _raise_unknown_reference_error(self)

    def reference_decorator(fn):
      if self._scopes:
        @six.wraps(fn)
        def scoping_wrapper(*args, **kwargs):
          with config_scope(self._scopes):
            return fn(*args, **kwargs)
        return scoping_wrapper
      return fn
    self._scoped_configurable_fn = _decorate_fn_or_cls(
        reference_decorator, self.configurable.fn_or_cls, True)

  @property
  def configurable(self):
    return self._configurable

  @property
  def scoped_configurable_fn(self):
    return self._scoped_configurable_fn

  @property
  def scopes(self):
    return self._scopes

  @property
  def selector(self):
    return self._selector

  @property
  def scoped_selector(self):
    return self._scoped_selector

  @property
  def config_key(self):
    return ('/'.join(self._scopes), self._configurable.selector)

  @property
  def evaluate(self):
    return self._evaluate

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      # pylint: disable=protected-access
      return (
          self._configurable == other._configurable and
          self._evaluate == other._evaluate)
      # pylint: enable=protected-access
    return False

  def __ne__(self, other):
    return not self.__eq__(other)

  def __repr__(self):
    # Check if this reference is a macro or constant, i.e. @.../macro() or
    # @.../constant(). Only macros and constants correspond to the %... syntax.
    configurable_fn = self._configurable.fn_or_cls
    if configurable_fn in (macro, _retrieve_constant) and self._evaluate:
      return '%' + '/'.join(self._scopes)
    maybe_parens = '()' if self._evaluate else ''
    return '@{}{}'.format(self._scoped_selector, maybe_parens)

  def __deepcopy__(self, memo):
    """Dishonestly implements the __deepcopy__ special method.

    When called, this returns either the `ConfigurableReference` instance itself
    (when `self._evaluate` is `False`) or the result of calling the underlying
    configurable. Configurable references may be deeply nested inside other
    Python data structures, and by providing this implementation,
    `copy.deepcopy` can be used on the containing Python structure to return a
    copy replacing any `ConfigurableReference` marked for evaluation with its
    corresponding configurable's output.

    Args:
      memo: The memoization dict (unused).

    Returns:
      When `self._evaluate` is `False`, returns the underlying configurable
      (maybe wrapped to be called in the proper scope). When `self._evaluate` is
      `True`, returns the output of calling the underlying configurable.
    """
    if self._evaluate:
      return self._scoped_configurable_fn()
    return self._scoped_configurable_fn


class _UnknownConfigurableReference(object):
  """Represents a reference to an unknown configurable.

  This class acts as a substitute for `ConfigurableReference` when the selector
  doesn't match any known configurable.
  """

  def __init__(self, selector, evaluate):
    self._selector = selector.split('/')[-1]
    self._evaluate = evaluate

  @property
  def selector(self):
    return self._selector

  @property
  def evaluate(self):
    return self._evaluate

  def __deepcopy__(self, memo):
    """Dishonestly implements the __deepcopy__ special method.

    See `ConfigurableReference` above. If this method is called, it means there
    was an attempt to use this unknown configurable reference, so we throw an
    error here.

    Args:
      memo: The memoization dict (unused).

    Raises:
      ValueError: To report that there is no matching configurable.
    """
    addl_msg = '\n\n    To catch this earlier, ensure gin.finalize() is called.'
    _raise_unknown_reference_error(self, addl_msg)


def _validate_skip_unknown(skip_unknown):
  if not isinstance(skip_unknown, (bool, list, tuple, set)):
    err_str = 'Invalid value for `skip_unknown`: {}'
    raise ValueError(err_str.format(skip_unknown))


def _should_skip(selector, skip_unknown):
  """Checks whether `selector` should be skipped (if unknown)."""
  _validate_skip_unknown(skip_unknown)
  if _REGISTRY.matching_selectors(selector):
    return False  # Never skip known configurables.
  if isinstance(skip_unknown, (list, tuple, set)):
    return selector in skip_unknown
  return skip_unknown  # Must be a bool by validation check.


class ParserDelegate(config_parser.ParserDelegate):
  """Delegate to handle creation of configurable references and macros."""

  def __init__(self, skip_unknown=False):
    self._skip_unknown = skip_unknown

  def configurable_reference(self, scoped_selector, evaluate):
    unscoped_selector = scoped_selector.rsplit('/', 1)[-1]
    if _should_skip(unscoped_selector, self._skip_unknown):
      return _UnknownConfigurableReference(scoped_selector, evaluate)
    return ConfigurableReference(scoped_selector, evaluate)

  def macro(self, name):
    matching_selectors = _CONSTANTS.matching_selectors(name)
    if matching_selectors:
      if len(matching_selectors) == 1:
        name = matching_selectors[0]
        return ConfigurableReference(name + '/gin.constant', True)
      err_str = "Ambiguous constant selector '{}', matches {}."
      raise ValueError(err_str.format(name, matching_selectors))
    return ConfigurableReference(name + '/gin.macro', True)


class ParsedBindingKey(
    collections.namedtuple('ParsedBindingKey', [
        'scope', 'given_selector', 'complete_selector', 'arg_name'
    ])):
  """Represents a parsed and validated binding key.

  A "binding key" identifies a specific parameter (`arg_name`), of a specific
  configurable (`complete_selector`), in a specific scope (`scope`), to which a
  value may be bound in the global configuration. The `given_selector` field
  retains information about how the original configurable selector was
  specified, which can be helpful for error messages (but is ignored for the
  purposes of equality and hashing).
  """

  def __new__(cls, binding_key):
    """Parses and validates the given binding key.

    This function will parse `binding_key` (if necessary), and ensure that the
    specified parameter can be bound for the given configurable selector (i.e.,
    that the parameter isn't blacklisted or not whitelisted if a whitelist was
    provided).

    Args:
      binding_key: A spec identifying a parameter of a configurable (maybe in
        some scope). This should either be a string of the form
        'maybe/some/scope/maybe.moduels.configurable_name.parameter_name'; or a
        list or tuple of `(scope, selector, arg_name)`; or another instance of
        `ParsedBindingKey`.

    Returns:
      A new instance of `ParsedBindingKey`.

    Raises:
      ValueError: If no function can be found matching the configurable name
        specified by `binding_key`, or if the specified parameter name is
        blacklisted or not in the function's whitelist (if present).
    """
    if isinstance(binding_key, ParsedBindingKey):
      return super(ParsedBindingKey, cls).__new__(cls, *binding_key)

    if isinstance(binding_key, (list, tuple)):
      scope, selector, arg_name = binding_key
    elif isinstance(binding_key, six.string_types):
      scope, selector, arg_name = config_parser.parse_binding_key(binding_key)
    else:
      err_str = 'Invalid type for binding_key: {}.'
      raise ValueError(err_str.format(type(binding_key)))

    configurable_ = _REGISTRY.get_match(selector)
    if not configurable_:
      raise ValueError("No configurable matching '{}'.".format(selector))

    if not _might_have_parameter(configurable_.fn_or_cls, arg_name):
      err_str = "Configurable '{}' doesn't have a parameter named '{}'."
      raise ValueError(err_str.format(selector, arg_name))

    if configurable_.whitelist and arg_name not in configurable_.whitelist:
      err_str = "Configurable '{}' doesn't include kwarg '{}' in its whitelist."
      raise ValueError(err_str.format(selector, arg_name))

    if configurable_.blacklist and arg_name in configurable_.blacklist:
      err_str = "Configurable '{}' has blacklisted kwarg '{}'."
      raise ValueError(err_str.format(selector, arg_name))

    return super(ParsedBindingKey, cls).__new__(
        cls,
        scope=scope,
        given_selector=selector,
        complete_selector=configurable_.selector,
        arg_name=arg_name)

  @property
  def config_key(self):
    return self.scope, self.complete_selector

  @property
  def scope_selector_arg(self):
    return self.scope, self.complete_selector, self.arg_name

  def __equal__(self, other):
    # Equality ignores the `given_selector` field, since two binding keys should
    # be equal whenever they identify the same parameter.
    return self.scope_selector_arg == other.scope_selector_arg

  def __hash__(self):
    return hash(self.scope_selector_arg)


def _format_value(value):
  """Returns `value` in a format parseable by `parse_value`, or `None`.

  Simply put, This function ensures that when it returns a string value, the
  following will hold:

      parse_value(_format_value(value)) == value

  Args:
    value: The value to format.

  Returns:
    A string representation of `value` when `value` is literally representable,
    or `None`.
  """
  literal = repr(value)
  try:
    if parse_value(literal) == value:
      return literal
  except SyntaxError:
    pass
  return None


def _is_literally_representable(value):
  """Returns `True` if `value` can be (parseably) represented as a string.

  Args:
    value: The value to check.

  Returns:
    `True` when `value` can be represented as a string parseable by
    `parse_literal`, `False` otherwise.
  """
  return _format_value(value) is not None


def clear_config(clear_constants=False):
  """Clears the global configuration.

  This clears any parameter values set by `bind_parameter` or `parse_config`, as
  well as the set of dynamically imported modules. It does not remove any
  configurable functions or classes from the registry of configurables.

  Args:
    clear_constants: Whether to clear constants created by `constant`. Defaults
      to False.
  """
  _set_config_is_locked(False)
  _CONFIG.clear()
  _SINGLETONS.clear()
  if clear_constants:
    _CONSTANTS.clear()
  else:
    saved_constants = _CONSTANTS.copy()
    _CONSTANTS.clear()  # Clear then redefine constants (re-adding bindings).
    for name, value in six.iteritems(saved_constants):
      constant(name, value)
  _IMPORTED_MODULES.clear()
  _OPERATIVE_CONFIG.clear()


def bind_parameter(binding_key, value):
  """Binds the parameter value specified by `binding_key` to `value`.

  The `binding_key` argument should either be a string of the form
  `maybe/scope/optional.module.names.configurable_name.parameter_name`, or a
  list or tuple of `(scope, selector, parameter_name)`, where `selector`
  corresponds to `optional.module.names.configurable_name`. Once this function
  has been called, subsequent calls (in the specified scope) to the specified
  configurable function will have `value` supplied to their `parameter_name`
  parameter.

  Example:

      @configurable('fully_connected_network')
      def network_fn(num_layers=5, units_per_layer=1024):
         ...

      def main(_):
        config.bind_parameter('fully_connected_network.num_layers', 3)
        network_fn()  # Called with num_layers == 3, not the default of 5.

  Args:
    binding_key: The parameter whose value should be set. This can either be a
      string, or a tuple of the form `(scope, selector, parameter)`.
    value: The desired value.

  Raises:
    RuntimeError: If the config is locked.
    ValueError: If no function can be found matching the configurable name
      specified by `binding_key`, or if the specified parameter name is
      blacklisted or not in the function's whitelist (if present).
  """
  if config_is_locked():
    raise RuntimeError('Attempted to modify locked Gin config.')

  pbk = ParsedBindingKey(binding_key)
  fn_dict = _CONFIG.setdefault(pbk.config_key, {})
  fn_dict[pbk.arg_name] = value


def query_parameter(binding_key):
  """Returns the currently bound value to the specified `binding_key`.

  The `binding_key` argument should look like
  'maybe/some/scope/maybe.moduels.configurable_name.parameter_name'. Note that
  this will not include default parameters.

  Args:
    binding_key: The parameter whose value should be set.

  Returns:
    The value bound to the configurable/parameter combination given in
    `binding_key`.

  Raises:
    ValueError: If no function can be found matching the configurable name
      specified by `biding_key`, or if the specified parameter name is
      blacklisted or not in the function's whitelist (if present) or if there is
      no value bound for the queried parameter or configurable.
  """
  pbk = ParsedBindingKey(binding_key)
  if pbk.config_key not in _CONFIG:
    err_str = "Configurable '{}' has no bound parameters."
    raise ValueError(err_str.format(pbk.given_selector))
  if pbk.arg_name not in _CONFIG[pbk.config_key]:
    err_str = "Configurable '{}' has no value bound for parameter '{}'."
    raise ValueError(err_str.format(pbk.given_selector, pbk.arg_name))
  return _CONFIG[pbk.config_key][pbk.arg_name]


def _might_have_parameter(fn_or_cls, arg_name):
  """Returns True if `arg_name` might be a valid parameter for `fn_or_cls`.

  Specifically, this means that `fn_or_cls` either has a parameter named
  `arg_name`, or has a `**kwargs` parameter.

  Args:
    fn_or_cls: The function or class to check.
    arg_name: The name fo the parameter.

  Returns:
    Whether `arg_name` might be a valid argument of `fn`.
  """
  if inspect.isclass(fn_or_cls):
    fn = _find_class_construction_fn(fn_or_cls)
  else:
    fn = fn_or_cls

  while hasattr(fn, '__wrapped__'):
    fn = fn.__wrapped__
  arg_spec = _get_cached_arg_spec(fn)
  if six.PY3:
    if arg_spec.varkw:
      return True
    return arg_name in arg_spec.args or arg_name in arg_spec.kwonlyargs
  else:
    if arg_spec.keywords:
      return True
    return arg_name in arg_spec.args


def _validate_parameters(fn_or_cls, arg_name_list, err_prefix):
  for arg_name in arg_name_list or []:
    if not _might_have_parameter(fn_or_cls, arg_name):
      err_str = "Argument '{}' in {} not a parameter of '{}'."
      raise ValueError(err_str.format(arg_name, err_prefix, fn_or_cls.__name__))


def _get_cached_arg_spec(fn):
  """Gets cached argspec for `fn`."""

  arg_spec = _ARG_SPEC_CACHE.get(fn)
  if arg_spec is None:
    arg_spec_fn = inspect.getfullargspec if six.PY3 else inspect.getargspec
    try:
      arg_spec = arg_spec_fn(fn)
    except TypeError:
      # `fn` might be a callable object.
      arg_spec = arg_spec_fn(fn.__call__)
    _ARG_SPEC_CACHE[fn] = arg_spec
  return arg_spec


def _get_supplied_positional_parameter_names(fn, args):
  """Returns the names of the supplied arguments to the given function."""
  arg_spec = _get_cached_arg_spec(fn)
  # May be shorter than len(args) if args contains vararg (*args) arguments.
  return arg_spec.args[:len(args)]


def _get_all_positional_parameter_names(fn):
  """Returns the names of all positional arguments to the given function."""
  arg_spec = _get_cached_arg_spec(fn)
  args = arg_spec.args
  if arg_spec.defaults:
    args = args[:-len(arg_spec.defaults)]
  return args


def _get_default_configurable_parameter_values(fn, whitelist, blacklist):
  """Retrieve all default values for configurable parameters of a function.

  Any parameters included in the supplied blacklist, or not included in the
  supplied whitelist, are excluded.

  Args:
    fn: The function whose parameter values should be retrieved.
    whitelist: The whitelist (or `None`) associated with the function.
    blacklist: The blacklist (or `None`) associated with the function.

  Returns:
    A dictionary mapping configurable parameter names to their default values.
  """
  arg_vals = _ARG_DEFAULTS_CACHE.get(fn)
  if arg_vals is not None:
    return arg_vals.copy()

  # First, grab any default values not captured in the kwargs var.
  arg_spec = _get_cached_arg_spec(fn)
  if arg_spec.defaults:
    default_kwarg_names = arg_spec.args[-len(arg_spec.defaults):]
    arg_vals = dict(zip(default_kwarg_names, arg_spec.defaults))
  else:
    arg_vals = {}

  if six.PY3 and arg_spec.kwonlydefaults:
    arg_vals.update(arg_spec.kwonlydefaults)

  # Now, eliminate keywords that are blacklisted, or aren't whitelisted (if
  # there's a whitelist), or aren't representable as a literal value.
  for k in list(six.iterkeys(arg_vals)):
    whitelist_fail = whitelist and k not in whitelist
    blacklist_fail = blacklist and k in blacklist
    representable = _is_literally_representable(arg_vals[k])
    if whitelist_fail or blacklist_fail or not representable:
      del arg_vals[k]

  _ARG_DEFAULTS_CACHE[fn] = arg_vals
  return arg_vals.copy()


def current_scope():
  return _ACTIVE_SCOPES[-1][:]  # Slice to get copy.


def current_scope_str():
  return '/'.join(current_scope())


@contextlib.contextmanager
def config_scope(name_or_scope):
  """Opens a new configuration scope.

  Provides a context manager that opens a new explicit configuration
  scope. Explicit configuration scopes restrict parameter bindings to only
  certain sections of code that run within the scope. Scopes can be nested to
  arbitrary depth; any configurable functions called within a scope inherit
  parameters defined by higher level scopes.

  For example, suppose a function named `preprocess_images` is called in two
  places in a codebase: Once when loading data for a training task, and once
  when loading data for an evaluation task:

      def load_training_data():
        ...
        with gin.config_scope('train'):
          images = preprocess_images(images)
        ...


      def load_eval_data():
        ...
        with gin.config_scope('eval'):
          images = preprocess_images(images)
        ...

  By using a `config_scope` to wrap each invocation of `preprocess_images` as
  above, it is possible to use Gin to supply specific parameters to each. Here
  is a possible configuration for the above example:

      preprocess_images.crop_size = [64, 64]
      preprocess_images.normalize_image = True

      train/preprocess_images.crop_location = 'random'
      train/preprocess_images.random_flip_lr = True

      eval/preprocess_images.crop_location = 'center'

  The `crop_size` and `normalize_image` parameters above will be shared by both
  the `train` and `eval` invocations; only `train` will receive
  `random_flip_lr`, and the two invocations receive different values for
  `crop_location`.

  Passing `None` or `''` to `config_scope` will temporarily clear all currently
  active scopes (within the `with` block; they will be restored afterwards).

  Args:
    name_or_scope: A name for the config scope, or an existing scope (e.g.,
      captured from `with gin.config_scope(...) as scope`), or `None` to clear
      currently active scopes.

  Raises:
    ValueError: If `name_or_scope` is not a list, string, or None.

  Yields:
    The resulting config scope (a list of all active scope names, ordered from
    outermost to innermost).
  """
  try:
    valid_value = True
    if isinstance(name_or_scope, list):
      new_scope = name_or_scope
    elif name_or_scope and isinstance(name_or_scope, six.string_types):
      new_scope = current_scope()  # Returns a copy.
      new_scope.extend(name_or_scope.split('/'))
    else:
      valid_value = name_or_scope in (None, '')
      new_scope = []

    # Append new_scope first. It will be popped in the finally block if an
    # exception is raised below.
    _ACTIVE_SCOPES.append(new_scope)

    scopes_are_valid = map(config_parser.MODULE_RE.match, new_scope)
    if not valid_value or not all(scopes_are_valid):
      err_str = 'Invalid value for `name_or_scope`: {}.'
      raise ValueError(err_str.format(name_or_scope))

    yield new_scope
  finally:
    _ACTIVE_SCOPES.pop()


def _make_configurable(fn_or_cls,
                       name=None,
                       module=None,
                       whitelist=None,
                       blacklist=None,
                       subclass=False):
  """Wraps `fn_or_cls` to make it configurable.

  Infers the configurable name from `fn_or_cls.__name__` if necessary, and
  updates global state to keep track of configurable name <-> function
  mappings, as well as whitelisted and blacklisted parameters.

  Args:
    fn_or_cls: The function or class to decorate.
    name: A name for the configurable. If `None`, the name will be inferred from
      from `fn_or_cls`. The `name` may also include module components to be used
      for disambiguation (these will be appended to any components explicitly
      specified by `module`).
    module: The module to associate with the configurable, to help handle naming
      collisions. If `None`, `fn_or_cls.__module__` will be used (if no module
      is specified as part of `name`).
    whitelist: A whitelisted set of parameter names to supply values for.
    blacklist: A blacklisted set of parameter names not to supply values for.
    subclass: If `fn_or_cls` is a class and `subclass` is `True`, decorate by
      subclassing `fn_or_cls` and overriding its `__init__` method. If `False`,
      replace the existing `__init__` with a decorated version.

  Returns:
    A wrapped version of `fn_or_cls` that will take parameter values from the
    global configuration.

  Raises:
    RuntimeError: If the config is locked.
    ValueError: If a configurable with `name` (or the name of `fn_or_cls`)
      already exists, or if both a whitelist and blacklist are specified.
  """
  if config_is_locked():
    err_str = 'Attempted to add a new configurable after the config was locked.'
    raise RuntimeError(err_str)

  name = fn_or_cls.__name__ if name is None else name
  if config_parser.IDENTIFIER_RE.match(name):
    default_module = getattr(fn_or_cls, '__module__', None)
    module = default_module if module is None else module
  elif not config_parser.MODULE_RE.match(name):
    raise ValueError("Configurable name '{}' is invalid.".format(name))

  if module is not None and not config_parser.MODULE_RE.match(module):
    raise ValueError("Module '{}' is invalid.".format(module))

  selector = module + '.' + name if module else name
  if not _INTERACTIVE_MODE and selector in _REGISTRY:
    err_str = "A configurable matching '{}' already exists."
    raise ValueError(err_str.format(selector))

  if whitelist and blacklist:
    err_str = 'A whitelist or a blacklist can be specified, but not both.'
    raise ValueError(err_str)

  if whitelist and not isinstance(whitelist, (list, tuple)):
    raise TypeError('Whitelist should be a list or tuple.')

  if blacklist and not isinstance(blacklist, (list, tuple)):
    raise TypeError('Blacklist should be a list or tuple.')

  _validate_parameters(fn_or_cls, whitelist, 'whitelist')
  _validate_parameters(fn_or_cls, blacklist, 'blacklist')

  def apply_config(fn):
    """Wraps `fn` so that it obtains parameters from the configuration."""

    @six.wraps(fn)
    def wrapper(*args, **kwargs):
      """Supplies fn with parameter values from the configuration."""
      scope_components = current_scope()
      new_kwargs = {}
      for i in range(len(scope_components) + 1):
        partial_scope_str = '/'.join(scope_components[:i])
        new_kwargs.update(_CONFIG.get((partial_scope_str, selector), {}))
      gin_bound_args = list(new_kwargs.keys())
      scope_str = partial_scope_str

      arg_names = _get_supplied_positional_parameter_names(fn, args)

      for arg in args[len(arg_names):]:
        if arg is REQUIRED:
          raise ValueError(
              'gin.REQUIRED is not allowed for unnamed (vararg) parameters. If '
              'the function being called is wrapped by a non-Gin decorator, '
              'try explicitly providing argument names for positional '
              'parameters.')

      required_arg_names = []
      required_arg_indexes = []
      for i, arg in enumerate(args[:len(arg_names)]):
        if arg is REQUIRED:
          required_arg_names.append(arg_names[i])
          required_arg_indexes.append(i)

      required_kwargs = []
      for kwarg, value in six.iteritems(kwargs):
        if value is REQUIRED:
          required_kwargs.append(kwarg)

      # If the caller passed arguments as positional arguments that correspond
      # to a keyword arg in new_kwargs, remove the keyword argument from
      # new_kwargs to let the caller win and avoid throwing an error. Unless it
      # is an arg marked as REQUIRED.
      for arg_name in arg_names:
        if arg_name not in required_arg_names:
          new_kwargs.pop(arg_name, None)

      # Get default values for configurable parameters.
      operative_parameter_values = _get_default_configurable_parameter_values(
          fn, whitelist, blacklist)
      # Update with the values supplied via configuration.
      operative_parameter_values.update(new_kwargs)

      # Remove any values from the operative config that are overridden by the
      # caller. These can't be configured, so they won't be logged. We skip
      # values that are marked as REQUIRED.
      for k in arg_names:
        if k not in required_arg_names:
          operative_parameter_values.pop(k, None)
      for k in kwargs:
        if k not in required_kwargs:
          operative_parameter_values.pop(k, None)

      # An update is performed in case another caller of this same configurable
      # object has supplied a different set of arguments. By doing an update, a
      # Gin-supplied or default value will be present if it was used (not
      # overridden by the caller) at least once.
      _OPERATIVE_CONFIG.setdefault((scope_str, selector), {}).update(
          operative_parameter_values)

      # We call deepcopy for two reasons: First, to prevent the called function
      # from modifying any of the values in `_CONFIG` through references passed
      # in via `new_kwargs`; Second, to facilitate evaluation of any
      # `ConfigurableReference` instances buried somewhere inside
      # `new_kwargs`. See the docstring on `ConfigurableReference.__deepcopy__`
      # above for more details on the dark magic happening here.
      new_kwargs = copy.deepcopy(new_kwargs)

      # Validate args marked as REQUIRED have been bound in the Gin config.
      missing_required_params = []
      new_args = list(args)
      for i, arg_name in zip(required_arg_indexes, required_arg_names):
        if arg_name not in new_kwargs:
          missing_required_params.append(arg_name)
        else:
          new_args[i] = new_kwargs.pop(arg_name)

      # Validate kwargs marked as REQUIRED have been bound in the Gin config.
      for kwarg in required_kwargs:
        if kwarg not in new_kwargs:
          missing_required_params.append(kwarg)
        else:
          # Remove from kwargs and let the new_kwargs value be used.
          kwargs.pop(kwarg)

      if missing_required_params:
        err_str = 'Required bindings for `{}` not provided in config: {}'
        minimal_selector = _REGISTRY.minimal_selector(selector)
        err_str = err_str.format(minimal_selector, missing_required_params)
        raise RuntimeError(err_str)

      # Now, update with the caller-supplied `kwargs`, allowing the caller to
      # have the final say on keyword argument values.
      new_kwargs.update(kwargs)

      try:
        return fn(*new_args, **new_kwargs)
      except Exception as e:  # pylint: disable=broad-except
        err_str = ''
        if isinstance(e, TypeError):
          all_arg_names = _get_all_positional_parameter_names(fn)
          if len(new_args) < len(all_arg_names):
            unbound_positional_args = list(
                set(all_arg_names[len(new_args):]) - set(new_kwargs))
            if unbound_positional_args:
              caller_supplied_args = list(
                  set(arg_names + list(kwargs)) -
                  set(required_arg_names + list(required_kwargs)))
              fmt = ('\n  No values supplied by Gin or caller for arguments: {}'
                     '\n  Gin had values bound for: {gin_bound_args}'
                     '\n  Caller supplied values for: {caller_supplied_args}')
              canonicalize = lambda x: list(map(str, sorted(x)))
              err_str += fmt.format(
                  canonicalize(unbound_positional_args),
                  gin_bound_args=canonicalize(gin_bound_args),
                  caller_supplied_args=canonicalize(caller_supplied_args))
        err_str += "\n  In call to configurable '{}' ({}){}"
        scope_info = " in scope '{}'".format(scope_str) if scope_str else ''
        err_str = err_str.format(name, fn, scope_info)
        utils.augment_exception_message_and_reraise(e, err_str)

    return wrapper

  decorated_fn_or_cls = _decorate_fn_or_cls(
      apply_config, fn_or_cls, subclass=subclass)

  _REGISTRY[selector] = Configurable(
      decorated_fn_or_cls,
      name=name,
      module=module,
      whitelist=whitelist,
      blacklist=blacklist,
      selector=selector)
  return decorated_fn_or_cls


def configurable(name_or_fn=None, module=None, whitelist=None, blacklist=None):
  """Decorator to make a function or class configurable.

  This decorator registers the decorated function/class as configurable, which
  allows its parameters to be supplied from the global configuration (i.e., set
  through `bind_parameter` or `parse_config`). The decorated function is
  associated with a name in the global configuration, which by default is simply
  the name of the function or class, but can be specified explicitly to avoid
  naming collisions or improve clarity.

  If some parameters should not be configurable, they can be specified in
  `blacklist`. If only a restricted set of parameters should be configurable,
  they can be specified in `whitelist`.

  The decorator can be used without any parameters as follows:

      @config.configurable
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the function is associated with the name
  `'some_configurable_function'` in the global configuration, and both `param1`
  and `param2` are configurable.

  The decorator can be supplied with parameters to specify the configurable name
  or supply a whitelist/blacklist:

      @config.configurable('explicit_configurable_name', whitelist='param2')
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the configurable is associated with the name
  `'explicit_configurable_name'` in the global configuration, and only `param2`
  is configurable.

  Classes can be decorated as well, in which case parameters of their
  constructors are made configurable:

      @config.configurable
      class SomeClass(object):
        def __init__(self, param1, param2='a default value'):
          ...

  In this case, the name of the configurable is `'SomeClass'`, and both `param1`
  and `param2` are configurable.

  Args:
    name_or_fn: A name for this configurable, or a function to decorate (in
      which case the name will be taken from that function). If not set,
      defaults to the name of the function/class that is being made
      configurable. If a name is provided, it may also include module components
      to be used for disambiguation (these will be appended to any components
      explicitly specified by `module`).
    module: The module to associate with the configurable, to help handle naming
      collisions. By default, the module of the function or class being made
      configurable will be used (if no module is specified as part of the name).
    whitelist: A whitelisted set of kwargs that should be configurable. All
      other kwargs will not be configurable. Only one of `whitelist` or
      `blacklist` should be specified.
    blacklist: A blacklisted set of kwargs that should not be configurable. All
      other kwargs will be configurable. Only one of `whitelist` or `blacklist`
      should be specified.

  Returns:
    When used with no parameters (or with a function/class supplied as the first
    parameter), it returns the decorated function or class. When used with
    parameters, it returns a function that can be applied to decorate the target
    function or class.
  """
  decoration_target = None
  if callable(name_or_fn):
    decoration_target = name_or_fn
    name = None
  else:
    name = name_or_fn

  def perform_decoration(fn_or_cls):
    return _make_configurable(fn_or_cls, name, module, whitelist, blacklist)

  if decoration_target:
    return perform_decoration(decoration_target)
  return perform_decoration


def external_configurable(fn_or_cls,
                          name=None,
                          module=None,
                          whitelist=None,
                          blacklist=None):
  """Allow referencing/configuring an external class or function.

  This alerts Gin to the existence of the class or function `fn_or_cls` in the
  event that it can't be easily annotated with `@configurable` (for instance, if
  it is from another project). This allows `fn_or_cls` to be configured and
  referenced (using the `@name` notation) via parameter binding strings.

  Note that only calls to the return value of this function or resulting from
  references to `fn_or_cls` made through binding strings (configurations) will
  have their parameters injected by Gin---explicit calls to `fn_or_cls` directly
  won't have any parameter bindings applied.

  Args:
    fn_or_cls: The external function or class that should be made configurable.
    name: The configurable name to be associated with `fn_or_cls`. The name may
      also include module components to be used for disambiguation (these will
      be appended to any components explicitly specified by `module`).
    module: The module to associate with the configurable, to help handle naming
      collisions. By default, `fn_or_cls.__module__` will be used (if no
      module is specified as part of the name).
    whitelist: A whitelist of parameter names to allow configuration for.
    blacklist: A blacklist of parameter names not to allow configuration for.

  Returns:
    A decorated version of `fn_or_cls` that permits parameter binding. For
    functions, this is just a wrapped version of the function. For classes, this
    is a carefully constructed subclass of `fn_or_cls` designed to behave nearly
    identically (even under many type inspection operations) save for the
    addition of parameter binding.
  """
  return _make_configurable(
      fn_or_cls,
      name=name,
      module=module,
      whitelist=whitelist,
      blacklist=blacklist,
      subclass=True)


def operative_config_str(max_line_length=80, continuation_indent=4):
  """Retrieve the "operative" configuration as a config string.

  The operative configuration consists of all parameter values used by
  configurable functions that are actually called during execution of the
  current program. Parameters associated with configurable functions that are
  not called (and so can have no effect on program execution) won't be included.

  The goal of the function is to return a config that captures the full set of
  relevant configurable "hyperparameters" used by a program. As such, the
  returned configuration will include the default values of arguments from
  configurable functions (as long as the arguments aren't blacklisted or missing
  from a supplied whitelist), as well as any parameter values overridden via
  `bind_parameter` or through `parse_config`.

  Any parameters that can't be represented as literals (capable of being parsed
  by `parse_config`) are excluded. The resulting config string is sorted
  lexicographically and grouped by configurable name.

  Args:
    max_line_length: A (soft) constraint on the maximum length of a line in the
      formatted string. Large nested structures will be split across lines, but
      e.g. long strings won't be split into a concatenation of shorter strings.
    continuation_indent: The indentation for continued lines.

  Returns:
    A config string capturing all parameter values used by the current program.
  """
  def format_binding(key, value):
    """Pretty print the given key/value pair."""
    formatted_val = pprint.pformat(
        value, width=(max_line_length - continuation_indent))
    formatted_val_lines = formatted_val.split('\n')
    if (len(formatted_val_lines) == 1 and
        len(key + formatted_val) <= max_line_length):
      output = '{} = {}'.format(key, formatted_val)
    else:
      indented_formatted_val = '\n'.join(
          [' ' * continuation_indent + line for line in formatted_val_lines])
      output = '{} = \\\n{}'.format(key, indented_formatted_val)
    return output

  def sort_key(key_tuple):
    """Sort configurable selector/innermost scopes, ignoring case."""
    scope, selector = key_tuple[0]
    parts = selector.lower().split('.')[::-1] + scope.lower().split('/')[::-1]
    return '/'.join(parts)

  # Build the output as an array of formatted Gin statements. Each statement may
  # span multiple lines. Imports are first, followed by macros, and finally all
  # other bindings sorted in alphabetical order by configurable name.
  formatted_statements = [
      'import {}'.format(module) for module in sorted(_IMPORTED_MODULES)
  ]
  if formatted_statements:
    formatted_statements.append('')

  macros = {}
  for (scope, selector), config in six.iteritems(_OPERATIVE_CONFIG):
    if _REGISTRY[selector].fn_or_cls == macro:
      macros[scope, selector] = config
  if macros:
    formatted_statements.append('# Macros:')
    formatted_statements.append('# ' + '=' * (max_line_length - 2))
  for (name, _), config in sorted(macros.items(), key=sort_key):
    binding = format_binding(name, config['value'])
    formatted_statements.append(binding)
  if macros:
    formatted_statements.append('')

  sorted_items = sorted(_OPERATIVE_CONFIG.items(), key=sort_key)
  for (scope, selector), config in sorted_items:
    configurable_ = _REGISTRY[selector]

    fn = configurable_.fn_or_cls
    if fn == macro or fn == _retrieve_constant:
      continue

    minimal_selector = _REGISTRY.minimal_selector(configurable_.selector)
    scoped_selector = (scope + '/' if scope else '') + minimal_selector
    parameters = [(k, v) for k, v in six.iteritems(config)
                  if _is_literally_representable(v)]
    formatted_statements.append('# Parameters for {}:'.format(scoped_selector))
    formatted_statements.append('# ' + '=' * (max_line_length - 2))
    for arg, val in sorted(parameters):
      binding = format_binding('{}.{}'.format(scoped_selector, arg), val)
      formatted_statements.append(binding)
    if not parameters:
      formatted_statements.append('# None.')
    formatted_statements.append('')

  return '\n'.join(formatted_statements)


def parse_config(bindings, skip_unknown=False):
  """Parse a file, string, or list of strings containing parameter bindings.

  Parses parameter binding strings to set up the global configuration.  Once
  `parse_config` has been called, any calls to configurable functions will have
  parameter values set according to the values specified by the parameter
  bindings in `bindings`.

  An individual parameter binding has the format

      maybe/some/scopes/configurable_name.parameter_name = value

  Multiple binding strings can be passed either in the form of a file-like
  object supporting the `readline` method, a single string with each individual
  parameter binding separated by a newline, or as a list of individual parameter
  binding strings.

  Any Python literal (lists, tuples, dicts, strings, etc.) is acceptable to the
  right of the equals sign, and follows standard Python rules for line
  continuation. Additionally, a value starting with '@' is interpreted as a
  (possibly scoped) reference to another configurable function, in which case
  this value is replaced by a reference to that function. If the value
  furthermore ends in `()` (e.g., `@configurable_name()`), then the value
  returned when calling the function is used (it will be called *just before*
  the function consuming the output is called).

  See the module documentation for a more detailed description of scoping
  mechanisms and a complete example.

  Reading from a file could be done as follows:

      with open('/path/to/file.config') as bindings:
        gin.parse_config(bindings)

  Passing a newline separated string of parameter bindings might look like:

      bindings = '''
          my_class.param_one = 'asdf'
          my_class_param_two = 9.7
      '''
      gin.parse_config(bindings)

  Alternatively, one can declare a list of parameter bindings and pass it in:

      bindings = [
          'my_class.param_one = "asdf"',
          'my_class.param_two = 9.7',
      ]
      gin.parse_config(bindings)

  Can skip unknown configurables. For example, if no module containing a
  'training' configurable was imported, errors can be avoided by specifying
  `skip_unknown=True`:

      bindings = [
          'my_class.param_one = "asdf"',
          'my_class.param_two = 9.7',
          'training.learning_rate = 0.1',
      ]
      gin.parse_config(bindings, skip_unknown=True)

  Args:
    bindings: A file-like object supporting the readline method, a newline
      separated string of parameter bindings, or a list of individual parameter
      binding strings.
    skip_unknown: A boolean indicating whether unknown configurables and imports
      should be skipped (instead of causing an error). Configurable references
      to unknown configurables will cause errors if they are present in a
      binding that is not itself skipped due to an unknown configurable. This
      can also be a list of configurable names: any unknown configurables that
      do not match an item in the list will still cause errors. Note that
      bindings for known configurables will always be parsed.
  """
  if isinstance(bindings, (list, tuple)):
    bindings = '\n'.join(bindings)

  _validate_skip_unknown(skip_unknown)
  if isinstance(skip_unknown, (list, tuple)):
    skip_unknown = set(skip_unknown)

  parser = config_parser.ConfigParser(bindings, ParserDelegate(skip_unknown))
  for statement in parser:
    if isinstance(statement, config_parser.BindingStatement):
      scope, selector, arg_name, value, location = statement
      if not arg_name:
        macro_name = '{}/{}'.format(scope, selector) if scope else selector
        with utils.try_with_location(location):
          bind_parameter((macro_name, 'gin.macro', 'value'), value)
        continue
      if not _should_skip(selector, skip_unknown):
        with utils.try_with_location(location):
          bind_parameter((scope, selector, arg_name), value)
    elif isinstance(statement, config_parser.ImportStatement):
      if skip_unknown:
        try:
          __import__(statement.module)
          _IMPORTED_MODULES.add(statement.module)
        except ImportError:
          log_str = 'Skipping import of unknown module `%s` (skip_unknown=%r).'
          logging.info(log_str, statement.module, skip_unknown)
      else:
        with utils.try_with_location(statement.location):
          __import__(statement.module)
        _IMPORTED_MODULES.add(statement.module)
    elif isinstance(statement, config_parser.IncludeStatement):
      with utils.try_with_location(statement.location):
        parse_config_file(statement.filename, skip_unknown)
    else:
      raise AssertionError('Unrecognized statement type {}.'.format(statement))


def register_file_reader(*args):
  """Register a file reader for use in parse_config_file.

  Registered file readers will be used to try reading files passed to
  `parse_config_file`. All file readers (beginning with the default `open`) will
  be tried until one of them succeeds at opening the file.

  This function may also be be used used as a decorator. For example:

      @register_file_reader(IOError)
      def exotic_data_source(filename):
        ...

  Args:
    *args: (When used as a decorator, only the existence check is supplied.)
      - file_reader_fn: The file reader function to register. This should be a
        function that can be used as a context manager to open a file and
        provide a file-like object, similar to Python's built-in `open`.
      - is_readable_fn: A function taking the file path and returning a boolean
        indicating whether the file can be read by `file_reader_fn`.

  Returns:
    `None`, or when used as a decorator, a function that will perform the
    registration using the supplied readability predicate.
  """
  def do_registration(file_reader_fn, is_readable_fn):
    if file_reader_fn not in list(zip(*_FILE_READERS))[0]:
      _FILE_READERS.append((file_reader_fn, is_readable_fn))

  if len(args) == 1:  # It's a decorator.
    return functools.partial(do_registration, is_readable_fn=args[0])
  elif len(args) == 2:
    do_registration(*args)
  else:  # 0 or > 2 arguments supplied.
    err_str = 'register_file_reader() takes 1 or 2 arguments ({} given)'
    raise TypeError(err_str.format(len(args)))


def parse_config_file(config_file, skip_unknown=False):
  """Parse a Gin config file.

  Args:
    config_file: The path to a Gin config file.
    skip_unknown: A boolean indicating whether unknown configurables and imports
      should be skipped instead of causing errors (alternatively a list of
      configurable names to skip if unknown). See `parse_config` for additional
      details.

  Raises:
    IOError: If `config_file` cannot be read using any register file reader.
  """
  for reader, existence_check in _FILE_READERS:
    if existence_check(config_file):
      with reader(config_file) as f:
        parse_config(f, skip_unknown=skip_unknown)
        return
  raise IOError('Unable to open file: {}'.format(config_file))


def parse_config_files_and_bindings(config_files,
                                    bindings,
                                    finalize_config=True,
                                    skip_unknown=False):
  """Parse a list of config files followed by extra Gin bindings.

  This function is equivalent to:

      for config_file in config_files:
        gin.parse_config_file(config_file, skip_configurables)
      gin.parse_config(bindings, skip_configurables)
      if finalize_config:
        gin.finalize()

  Args:
    config_files: A list of paths to the Gin config files.
    bindings: A list of individual parameter binding strings.
    finalize_config: Whether to finalize the config after parsing and binding
      (defaults to True).
    skip_unknown: A boolean indicating whether unknown configurables and imports
      should be skipped instead of causing errors (alternatively a list of
      configurable names to skip if unknown). See `parse_config` for additional
      details.
  """
  if config_files is None:
    config_files = []
  if bindings is None:
    bindings = ''
  for config_file in config_files:
    parse_config_file(config_file, skip_unknown)
  parse_config(bindings, skip_unknown)
  if finalize_config:
    finalize()


def parse_value(value):
  """Parse and return a single Gin value."""
  if not isinstance(value, six.string_types):
    raise ValueError('value ({}) should be a string type.'.format(value))
  return config_parser.ConfigParser(value, ParserDelegate()).parse_value()


def config_is_locked():
  return _CONFIG_IS_LOCKED


def _set_config_is_locked(is_locked):
  global _CONFIG_IS_LOCKED
  _CONFIG_IS_LOCKED = is_locked


@contextlib.contextmanager
def unlock_config():
  """A context manager that temporarily unlocks the config.

  Once the config has been locked by `gin.finalize`, it can only be modified
  using this context manager (to make modifications explicit). Example:

      with gin.unlock_config():
        ...
        gin.bind_parameter(...)

  In the case where the config is already unlocked, this does nothing (the
  config remains unlocked).

  Yields:
    None.
  """
  config_was_locked = config_is_locked()
  _set_config_is_locked(False)
  yield
  _set_config_is_locked(config_was_locked)


def enter_interactive_mode():
  global _INTERACTIVE_MODE
  _INTERACTIVE_MODE = True


def exit_interactive_mode():
  global _INTERACTIVE_MODE
  _INTERACTIVE_MODE = False


@contextlib.contextmanager
def interactive_mode():
  try:
    enter_interactive_mode()
    yield
  finally:
    exit_interactive_mode()


def finalize():
  """A function that should be called after parsing all Gin config files.

  Calling this function allows registered "finalize hooks" to inspect (and
  potentially modify) the Gin config, to provide additional functionality. Hooks
  should not modify the configuration object they receive directly; instead,
  they should return a dictionary mapping Gin binding keys to (new or updated)
  values. This way, all hooks see the config as originally parsed.

  Raises:
    RuntimeError: If the config is already locked.
    ValueError: If two or more hooks attempt to modify or introduce bindings for
      the same key. Since it is difficult to control the order in which hooks
      are registered, allowing this could yield unpredictable behavior.
  """
  if config_is_locked():
    raise RuntimeError('Finalize called twice (config already locked).')

  bindings = {}
  for hook in _FINALIZE_HOOKS:
    new_bindings = hook(_CONFIG)
    if new_bindings is not None:
      for key, value in six.iteritems(new_bindings):
        pbk = ParsedBindingKey(key)
        if pbk in bindings:
          err_str = 'Received conflicting updates when running {}.'
          raise ValueError(err_str.format(hook))
        bindings[pbk] = value

  for pbk, value in six.iteritems(bindings):
    bind_parameter(pbk, value)

  _set_config_is_locked(True)


def register_finalize_hook(fn):
  """Registers `fn` as a hook that will run during `gin.finalize`.

  All finalize hooks should accept the current config, and return a dictionary
  containing any additional parameter bindings that should occur in the form of
  a mapping from (scoped) configurable names to values.

  Args:
    fn: The function to register.

  Returns:
    `fn`, allowing `register_finalize_hook` to be used as a decorator.
  """
  _FINALIZE_HOOKS.append(fn)
  return fn


def _iterate_flattened_values(value):
  """Provides an iterator over all values in a nested structure."""
  if isinstance(value, six.string_types):
    yield value
    return

  if isinstance(value, collections.Mapping):
    value = collections.ValuesView(value)

  if isinstance(value, collections.Iterable):
    for nested_value in value:
      for nested_nested_value in _iterate_flattened_values(nested_value):
        yield nested_nested_value

  yield value


def iterate_references(config, to=None):
  """Provides an iterator over references in the given config.

  Args:
    config: A dictionary mapping scoped configurable names to argument bindings.
    to: If supplied, only yield references whose `configurable_fn` matches `to`.

  Yields:
    `ConfigurableReference` instances within `config`, maybe restricted to those
    matching the `to` parameter if it is supplied.
  """
  for value in _iterate_flattened_values(config):
    if isinstance(value, ConfigurableReference):
      if to is None or value.configurable.fn_or_cls == to:
        yield value


def validate_reference(ref, require_bindings=True, require_evaluation=False):
  if require_bindings and ref.config_key not in _CONFIG:
    err_str = "No bindings specified for '{}'."
    raise ValueError(err_str.format(ref.scoped_selector))

  if require_evaluation and not ref.evaluate:
    err_str = "Reference '{}' must be evaluated (add '()')."
    raise ValueError(err_str.format(ref))


@configurable(module='gin')
def macro(value):
  """A Gin macro."""
  return value


@configurable('constant', module='gin')
def _retrieve_constant():
  """Fetches and returns a constant from the _CONSTANTS map."""
  return _CONSTANTS[current_scope_str()]


@configurable(module='gin')
def singleton(constructor):
  return singleton_value(current_scope_str(), constructor)


def singleton_value(key, constructor=None):
  if key not in _SINGLETONS:
    if not constructor:
      err_str = "No singleton found for key '{}', and no constructor was given."
      raise ValueError(err_str.format(key))
    if not callable(constructor):
      err_str = "The constructor for singleton '{}' is not callable."
      raise ValueError(err_str.format(key))
    _SINGLETONS[key] = constructor()
  return _SINGLETONS[key]


def constant(name, value):
  """Creates a constant that can be referenced from gin config files.

  After calling this function in Python, the constant can be referenced from
  within a Gin config file using the macro syntax. For example, in Python:

      gin.constant('THE_ANSWER', 42)

  Then, in a Gin config file:

      meaning.of_life = %THE_ANSWER

  Note that any Python object can be used as the value of a constant (including
  objects not representable as Gin literals). Values will be stored until
  program termination in a Gin-internal dictionary, so avoid creating constants
  with values that should have a limited lifetime.

  Optionally, a disambiguating module may be prefixed onto the constant
  name. For instance:

      gin.constant('some.modules.PI', 3.14159)

  Args:
    name: The name of the constant, possibly prepended by one or more
      disambiguating module components separated by periods. An macro with this
      name (including the modules) will be created.
    value: The value of the constant. This can be anything (including objects
      not representable as Gin literals). The value will be stored and returned
      whenever the constant is referenced.

  Raises:
    ValueError: If the constant's selector is invalid, or a constant with the
      given selector already exists.
  """
  if not config_parser.MODULE_RE.match(name):
    raise ValueError("Invalid constant selector '{}'.".format(name))

  if _CONSTANTS.matching_selectors(name):
    err_str = "Constants matching selector '{}' already exist ({})."
    raise ValueError(err_str.format(name, _CONSTANTS.matching_selectors(name)))

  _CONSTANTS[name] = value


def constants_from_enum(cls, module=None):
  """Decorator for an enum class that generates Gin constants from values.

  Generated constants have format `module.ClassName.ENUM_VALUE`. The module
  name is optional when using the constant.

  Args:
    cls: Class type.
    module: The module to associate with the constants, to help handle naming
      collisions. If `None`, `cls.__module__` will be used.

  Returns:
    Class type (identity function).

  Raises:
    TypeError: When applied to a non-enum class.
  """
  if not issubclass(cls, enum.Enum):
    raise TypeError("Class '{}' is not subclass of enum.".format(cls.__name__))

  if module is None:
    module = cls.__module__
  for value in cls:
    constant('{}.{}'.format(module, str(value)), value)
  return cls


@register_finalize_hook
def validate_macros_hook(config):
  for ref in iterate_references(config, to=macro):
    validate_reference(ref, require_evaluation=True)


@register_finalize_hook
def find_unknown_references_hook(config):
  """Hook to find/raise errors for references to unknown configurables."""
  additional_msg_fmt = " In binding for '{}'."
  for (scope, selector), param_bindings in six.iteritems(config):
    for param_name, param_value in six.iteritems(param_bindings):
      for maybe_unknown in _iterate_flattened_values(param_value):
        if isinstance(maybe_unknown, _UnknownConfigurableReference):
          scope_str = scope + '/' if scope else ''
          min_selector = _REGISTRY.minimal_selector(selector)
          binding_key = '{}{}.{}'.format(scope_str, min_selector, param_name)
          additional_msg = additional_msg_fmt.format(binding_key)
          _raise_unknown_reference_error(maybe_unknown, additional_msg)
