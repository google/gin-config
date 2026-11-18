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

"""Defines the `gin.Config` class and associated functions."""

import copy
import inspect
from typing import Any, Callable, Dict, Optional

from gin.local import partial

import tree


class ConfigState:
  """Encapsulates state associated with a `Config`.

  This is separated out into its own class to avoid any possibility of name
  collisions when assigning parameters to a `Config` instance.
  """

  def __init__(self, fn_or_cls: Callable[..., Any]):
    self.fn_or_cls = fn_or_cls
    self.signature = inspect.signature(fn_or_cls)
    self.has_kwargs = any(  # Used to disable param name validation.
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in self.signature.parameters.values())
    self.call = False

  def validate(self, arg_name, unused_value):
    """Validates `arg_name` to ensure it is a parameter of `self.fn_or_cls`."""
    if not self.has_kwargs and arg_name not in self.signature.parameters:
      raise TypeError(f"No argument named '{arg_name}' in {self.fn_or_cls}.")


class Config:
  """Captures configuration for a specific function or class.

  This class represents the configuration for a given function or class,
  exposing configured parameters as mutable attributes. For example, for a class

      TestClass:

        def __init__(self, arg, kwarg=None):
          self.arg = arg
          self.kwarg = kwarg

  a configuration may (for instance) be accomplished via

      class_config = Config(TestClass, kwarg='kwarg')
      class_config.arg = 1

  This `Config` instance may then be passed to the `bind` function to obtain
  a "partial class" with values bound for the `arg` and `kwarg` parameters of
  the test class constructor:

      partial_class = bind(class_config)
      instance = partial_class()
      assert instance.arg == 'arg'
      assert instance.kwarg == 'kwarg'

  A given `Config` instance may be "called" to make it an "instance
  configuration". This will have the effect that when `bind` is called, the
  result of calling the corresponding partial will be provided instead of the
  partial itself:

      instance_config = class_config()
      instance = bind(instance_config)
      assert instance.arg == 'arg'
      assert instance.kwarg == 'kwarg'

  The instance config becomes separated from the class config, so any further
  changes to `class_config` are not reflected by `instance_config` (and vice
  versa).
  """

  __state__: ConfigState  # Lets pytype know about the __state__ attribute.

  def __init__(self, fn_or_cls: Callable[..., Any], *args, **kwargs):
    """Initialize for `fn_or_cls`, optionally specifying parameters.

    Args:
      fn_or_cls: The function or class to configure.
      *args: Any positional arguments to configure for `fn_or_cls`.
      **kwargs: Any keyword arguments to configure for `fn_or_cls`.
    """
    super().__setattr__('__state__', ConfigState(fn_or_cls))
    signature = self.__state__.signature
    bound_arguments = signature.bind_partial(*args, **kwargs)
    for name, value in bound_arguments.arguments.items():
      if signature.parameters[name].kind == inspect.Parameter.POSITIONAL_ONLY:
        raise ValueError('Positional only arguments not supported.')
      if signature.parameters[name].kind == inspect.Parameter.VAR_POSITIONAL:
        raise ValueError('Variable positional arguments not supported.')
      setattr(self, name, value)

  # Providing this pass-through method prevents spurious pytype errors.
  def __getattr__(self, name: str):
    """Get parameter with given `name`."""
    super().__getattribute__(name)

  def __setattr__(self, name: str, value: Any):
    """Sets parameter `name` to `value`."""
    self.__state__.validate(name, value)  # Make sure it's a valid param name.
    super().__setattr__(name, value)

  def __repr__(self):
    formatted_fn_or_cls = self.__state__.fn_or_cls.__qualname__
    formatted_params = [f'{k}={v}' for k, v in params(self).items()]
    return f"Config[{formatted_fn_or_cls}]({', '.join(formatted_params)})"

  def __copy__(self):
    config_copy = object.__new__(type(self))
    new_dict = copy.copy(self.__dict__)
    new_dict['__state__'] = copy.deepcopy(self.__state__)
    config_copy.__dict__.update(new_dict)
    return config_copy

  def __call__(self):
    """Creates a "called" copy of this `Config` instance."""
    if self.__state__.call:
      raise ValueError('The config has already been marked as called.')
    new_config = copy.copy(self)
    new_config.__state__.call = True
    return new_config


def params(config: Config):
  """Returns a dictionary of the parameters specified by `config`."""
  return {
      name: value for name, value in vars(config).items() if name != '__state__'
  }


def bind(config: Config, memo: Optional[Dict[Config, Any]] = None) -> Any:
  """Binds `config`, returning a `partial` with bound parameters.

  This is the core function for turning a `Config` into a (partially) bound
  object. It recursively walks through `config`'s parameters, binding any nested
  `Config` instances. The returned result is a callable `partial` with all
  config parameters set.

  If the same `Config` instance is seen multiple times during traversal of the
  configuration tree, `bind` is called only once (for the first instance
  encountered), and the result is reused for subsequent copies of the instance.
  This is achieved via the `memo` dictionary (similar to `deepcopy`). This has
  the effect that for configured class instances, each separate config instance
  is in one-to-one correspondence with an actual instance of the configured
  class after calling `bind` (shared config instances <=> shared class
  instances).

  Args:
    config: A `Config` instance to bind.
    memo: An optional dictionary mapping `Config` instances to their "bound"
      values. This is used to map shared instances of a "instantiated" `Config`
      in the configuration tree to a single shared object instance/value after
      binding. If an empty dictionary is supplied, it will be filled with a
      mapping of all `Config` instances in the full tree reachable from `config`
      to their corresponding partial or instance values.

  Returns:
    The bound version of `config`.
  """
  memo = {} if memo is None else memo

  def map_fn(leaf):
    return bind(leaf, memo) if isinstance(leaf, Config) else leaf

  if config not in memo:
    kwargs = {}
    for name, value in params(config).items():
      value = tree.map_structure(map_fn, value)
      kwargs[name] = value
    state = config.__state__
    bindings = state.signature.bind_partial(**kwargs)
    result = partial.partial(state.fn_or_cls, *bindings.args, **bindings.kwargs)
    memo[config] = result() if state.call else result

  return memo[config]
