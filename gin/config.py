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
allowlisted or denylisted to mark only a subset of the function's parameters as
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

import collections
import contextlib
import copy
import enum
import functools
import inspect
import logging
import os
import pprint
import threading
import traceback
import typing
from typing import Any, Callable, Dict, Optional, Sequence, Set, Tuple, Type, Union

from gin import config_parser
from gin import selector_map
from gin import utils


class _ScopeManager(threading.local):
  """Manages currently active config scopes.

  This ensures thread safety of config scope management by subclassing
  `threading.local`. Scopes are tracked as a stack, where elements in the
  stack are lists of the currently active scope names.
  """

  def _maybe_init(self):
    if not hasattr(self, '_active_scopes'):
      self._active_scopes = [[]]

  @property
  def active_scopes(self):
    self._maybe_init()
    return self._active_scopes[:]

  @property
  def current_scope(self):
    self._maybe_init()
    return self._active_scopes[-1][:]  # Slice to get copy.

  def enter_scope(self, scope):
    """Enters the given scope, updating the list of active scopes.

    Args:
      scope: A list of active scope names, ordered from outermost to innermost.
    """
    self._maybe_init()
    self._active_scopes.append(scope)

  def exit_scope(self):
    """Exits the most recently entered scope."""
    self._maybe_init()
    self._active_scopes.pop()


class _GinBuiltins:

  def __init__(self):
    self.macro = macro
    self.constant = _retrieve_constant
    self.singleton = singleton


class ParseContext:
  """Encapsulates context for parsing a single file."""

  def __init__(self, import_manager=None):
    """Initializes the instance.

    Args:
      import_manager: If not `None`, an `ImportManager` providing an initial set
        of imports to process. Additionally, if an `ImportManager` is provided
        and dynamic registration is enabled, actually importing an unregistered
        configurable during parsing becomes an error (instead, all configurables
        are assumed to be registered already). This is used when generating
        (operative) config strings.
    """
    self._import_manager = import_manager
    self._imports = []
    self._symbol_table = {}
    self._symbol_source = {}
    self._dynamic_registration = False

    if import_manager is not None:
      for stmt in import_manager.sorted_imports:
        self.process_import(stmt)

  @property
  def imports(self):
    return self._imports

  @property
  def import_manager(self):
    return self._import_manager

  def _enable_dynamic_registration(self):
    self._dynamic_registration = True
    self._symbol_table['gin'] = _GinBuiltins()
    self._symbol_source['gin'] = None

  def process_import(self, statement: config_parser.ImportStatement):
    """Processes the given `ImportStatement`."""
    if statement.is_from and statement.module.startswith('__gin__.'):
      if statement.alias:
        raise SyntaxError('__gin__ imports do not support `as` aliasing.',
                          statement.location)
      _, feature = statement.module.split('.', maxsplit=1)
      if feature == 'dynamic_registration':
        if self._imports:
          existing_imports = [stmt.format() for stmt in self._imports]
          raise SyntaxError(
              f'Dynamic registration should be enabled before any other modules '
              f'are imported.\n\nAlready imported: {existing_imports}.',
              statement.location)
        self._enable_dynamic_registration()
      else:
        raise SyntaxError(  # pylint: disable=raising-format-tuple
            "Unrecognized __gin__ feature '{feature}'.", statement.location)
    else:
      fromlist = [''] if statement.is_from or statement.alias else None
      module = __import__(statement.module, fromlist=fromlist)
      if self._dynamic_registration:
        name = statement.bound_name()
        if name == 'gin':
          raise ValueError(
              f'The `gin` symbol is reserved; cannot bind import statement '
              f'"{statement.format()}" to `gin`. Use an alias for the import '
              f'(via `import ... as ...` or `from ... import ... [as ...]`).')
        self._symbol_table[name] = module
        self._symbol_source[name] = statement
    self._imports.append(statement)

  def _resolve_selector(self, selector):
    """Resolves the given `selector` using this context's symbol table.

    This method breaks the given `selector` into its contituent components
    (names separated by '.'), resolving the first component using this
    `ParseContext`'s symbol table, and each subsequent component as an attribute
    on the resolved value of the previous component.

    Args:
      selector: The selector to resolve into attribute names and values.

    Raises:
      NameError: If the first component of the selector is not a symbol provided
        by some import statement in the current `ParseContext`.
      AttributeError: If an internal component of the selector does is not a
        valid attribute of its parent component.

    Returns:
      A pair of lists `(attr_names, attr_values)`, with the names and values
      corresponding to each component of `selector`.
    """
    not_found = object()

    attr_names = selector.split('.')
    symbol = attr_names[0]
    module = self._symbol_table.get(symbol, not_found)
    if module is not_found:
      raise NameError(f"'{symbol}' was not provided by an import statement.")

    attr_chain = [module]
    for attr_name in attr_names[1:]:
      attr = getattr(attr_chain[-1], attr_name, not_found)
      if attr is not_found:
        raise AttributeError(
            f"Couldn't resolve selector {selector}; {attr_chain[-1]} has no "
            f'attribute {attr_name}.')
      attr_chain.append(attr)

    return attr_names, attr_chain

  def _import_source(self, import_statement, attr_names):
    """Creates an "import source" tuple for a given reference."""
    if not import_statement.is_from and not import_statement.alias:
      module_parts = import_statement.module.split('.')
      num_matches = 0
      for module_part, attr_name in zip(module_parts, attr_names[:-1]):
        if module_part != attr_name:
          break
        num_matches += 1
      module = '.'.join(module_parts[:num_matches])
      selector = '.'.join(attr_names[num_matches:])
      return (import_statement._replace(module=module), selector)
    else:
      return (import_statement, '.'.join(attr_names[1:]))

  def _register(self, attr_names, attr_values):
    """Registers the function/class at the end of the named_attrs list.

    In order to support configurable methods, if a method is registered (a
    function whose parent attribute is a class), its parent class will also be
    registered. If the parent class has already been registered, it will be
    re-registered, and any references to the class in the current config will
    be updated (re-initialized) to reference the updated class registration.

    Args:
      attr_names: A list of attribute names, as returned by `_resolve_selector`.
      attr_values: A list of attribute values corresponding to `attr_names`.

    Returns:
      The `Configurable` instance associated with the new registration.
    """
    root_name, *inner_names, fn_or_cls_name = attr_names
    *path_attrs, fn_or_cls = attr_values

    source = self._symbol_source[root_name]
    if source is None:  # This happens for Gin "builtins" like `macro`.
      module = root_name
    else:
      module = '.'.join([source.partial_path(), *inner_names])

    original = _inverse_lookup(fn_or_cls)
    _make_configurable(
        fn_or_cls,
        name=fn_or_cls_name,
        module=module,
        import_source=self._import_source(source, attr_names),
        avoid_class_mutation=True)
    if original is not None:  # We've re-registered something...
      for reference in iterate_references(_CONFIG, to=original.wrapper):
        reference.initialize()

    if inspect.isfunction(fn_or_cls) and inspect.isclass(path_attrs[-1]):
      self._register(attr_names[:-1], attr_values[:-1])

    return _INVERSE_REGISTRY[fn_or_cls]

  def get_configurable(self, selector):
    """Get a configurable matching the given `selector`."""
    if self._dynamic_registration:
      attr_names, attr_values = self._resolve_selector(selector)
      existing_configurable = _inverse_lookup(attr_values[-1])
      if existing_configurable is None and self._import_manager:
        raise RuntimeError(
            f'Encountered unregistered configurable `{selector}` in parse only '
            f'mode. This indicates an internal error. Please file a bug.')
      return existing_configurable or self._register(attr_names, attr_values)
    else:  # No dynamic registration, just look up the selector.
      return _REGISTRY.get_match(selector)


def _parse_context() -> ParseContext:
  return _PARSE_CONTEXTS[-1]


@contextlib.contextmanager
def _parse_scope(import_manager=None):
  _PARSE_CONTEXTS.append(ParseContext(import_manager))
  try:
    yield _parse_context()
  finally:
    _PARSE_CONTEXTS.pop()


# Maintains the registry of configurable functions and classes.
_REGISTRY = selector_map.SelectorMap()

# Maps registered functions or classes to their associated Configurable object.
_INVERSE_REGISTRY = {}

# Maps old selector names to new selector names for selectors that are renamed.
# This is used for handling renaming of class method modules.
_RENAMED_SELECTORS = {}

# Maps tuples of `(scope, selector)` to associated parameter values. This
# specifies the current global "configuration" set through `bind_parameter` or
# `parse_config`, but doesn't include any functions' default argument values.
_CONFIG = {}

# Keeps a set of ImportStatements that were imported via config files.
_IMPORTS = set()

# Maps `(scope, selector)` tuples to all configurable parameter values used
# during program execution (including default argument values).
_OPERATIVE_CONFIG = {}
_OPERATIVE_CONFIG_LOCK = threading.Lock()

# Keeps track of currently active config scopes.
_SCOPE_MANAGER = _ScopeManager()

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

# Parse contexts, providing file-isolated import/symbol tables.
_PARSE_CONTEXTS = [ParseContext()]

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

# List of location prefixes. Similar to PATH var in unix to be used to search
# for files with those prefixes.
_LOCATION_PREFIXES = ['']

# Value to represent required parameters.
REQUIRED = object()
# Add it to constants.
_CONSTANTS['gin.REQUIRED'] = REQUIRED


def _find_class_construction_fn(cls):
  """Find the first __init__ or __new__ method in the given class's MRO."""
  for base in inspect.getmro(cls):  # pytype: disable=wrong-arg-types
    if '__init__' in base.__dict__:
      return base.__init__
    if '__new__' in base.__dict__:
      return base.__new__


def _ensure_wrappability(fn):
  """Make sure `fn` can be wrapped cleanly by functools.wraps."""
  # Handle "builtin_function_or_method", "wrapped_descriptor", and
  # "method-wrapper" types.
  unwrappable_types = (type(sum), type(object.__init__), type(object.__call__))
  if isinstance(fn, unwrappable_types):
    # pylint: disable=unnecessary-lambda
    wrappable_fn = lambda *args, **kwargs: fn(*args, **kwargs)
    wrappable_fn.__name__ = fn.__name__
    wrappable_fn.__doc__ = fn.__doc__
    wrappable_fn.__module__ = ''  # These types have no __module__, sigh.
    wrappable_fn.__wrapped__ = fn
    return wrappable_fn

  # Otherwise we're good to go...
  return fn


def _inverse_lookup(fn_or_cls, allow_decorators=False):
  unwrapped = inspect.unwrap(fn_or_cls, stop=lambda f: f in _INVERSE_REGISTRY)
  configurable_ = _INVERSE_REGISTRY.get(unwrapped)
  if configurable_ is not None:
    wrapped_and_wrapper = (configurable_.wrapped, configurable_.wrapper)
    if allow_decorators or fn_or_cls in wrapped_and_wrapper:
      return configurable_
  return None


def _find_registered_methods(cls, selector):
  """Finds methods in `cls` that have been wrapped or registered with Gin."""
  registered_methods = {}

  def is_method(maybe_method):
    # Python 3 has no notion of an unbound method. To avoid a scenario where a
    # previously registered function is assigned as a class attribute (e.g., the
    # default value of a dataclass field) and considered a method here, we
    # require that the function's __module__ is the same as that of the class,
    # its __name__ matches the name it is accessible under via the class, and
    # its __qualname__ contains the class name as `Class.name`.
    for base in inspect.getmro(cls):  # pytype: disable=wrong-arg-types
      if (inspect.isfunction(maybe_method) and
          maybe_method.__module__ == base.__module__ and
          getattr(base, maybe_method.__name__, None) == maybe_method):
        qualname_parts = maybe_method.__qualname__.split('.')
        if len(qualname_parts) > 1 and qualname_parts[-2] == base.__name__:
          return True
    return False

  for name, method in inspect.getmembers(cls, predicate=is_method):
    if method in _INVERSE_REGISTRY:
      method_info = _INVERSE_REGISTRY[method]
      if method_info.module not in (method.__module__, selector):
        raise ValueError(
            f'Method {name} in class {cls} ({selector}) was registered with a '
            f'custom module ({method_info.module}), but the class is also '
            f'being registered. Avoid specifying a module on the method to '
            f'allow class registration to modify the method module name.')
      old_selector = method_info.selector
      new_selector = selector + '.' + method_info.name
      method_info = method_info._replace(
          module=selector, selector=new_selector, is_method=True)
      _RENAMED_SELECTORS[old_selector] = new_selector
      _REGISTRY.pop(old_selector)
      _REGISTRY[new_selector] = method_info
      _INVERSE_REGISTRY[method] = method_info
      registered_methods[name] = method_info.wrapper
    else:
      if _inverse_lookup(method, allow_decorators=True):
        registered_methods[name] = method
  return registered_methods


def _make_meta_call_wrapper(cls):
  """Creates a pickle-compatible wrapper for `type(cls).__call__`.

  This function works in tandem with `_decorate_fn_or_cls` below. It wraps
  `type(cls).__call__`, which is in general responsible for creating a new
  instance of `cls` or one of its subclasses. In cases where the to-be-created
  class is Gin's dynamically-subclassed version of `cls`, the wrapper here
  instead returns an instance of `cls`, which isn't a dynamic subclass and more
  generally doesn't have any Gin-related magic applied. This means the instance
  is compatible with pickling, and is totally transparent to any inspections by
  user code (since it really is an instance of the original type).

  Args:
    cls: The class whose metaclass's call method should be wrapped.

  Returns:
    A wrapped version of the `type(cls).__call__`.
  """
  cls_meta = type(cls)

  @functools.wraps(cls_meta.__call__)
  def meta_call_wrapper(new_cls, *args, **kwargs):
    # If `new_cls` (the to-be-created class) is a direct subclass of `cls`, we
    # can be sure that it's Gin's dynamically created subclass. In this case,
    # we directly create an instance of `cls` instead. Otherwise, some further
    # dynamic subclassing by user code has likely occurred, and we just create
    # an instance of `new_cls` to avoid issues. This instance is likely not
    # compatible with pickle, but that's generally true of dynamically created
    # subclasses and would require some user workaround with or without Gin.
    if new_cls.__bases__ == (cls,):
      new_cls = cls
    return cls_meta.__call__(new_cls, *args, **kwargs)

  return meta_call_wrapper


def _decorate_fn_or_cls(decorator,
                        fn_or_cls,
                        selector,
                        avoid_class_mutation=False,
                        decorate_methods=False):
  """Decorate a function or class with the given decorator.

  When `fn_or_cls` is a function, applies `decorator` to the function and
  returns the (decorated) result.

  When `fn_or_cls` is a class and the `avoid_class_mutation` parameter is
  `False`, this will replace either `fn_or_cls.__init__` or `fn_or_cls.__new__`
  (whichever is first implemented in the class's MRO, with a preference for
  `__init__`) with the result of applying `decorator` to it.

  When `fn_or_cls` is a class and `avoid_class_mutation` is `True`, this will
  dynamically construct a subclass of `fn_or_cls` using a dynamically
  constructed metaclass (which itself is a subclass of `fn_or_cls`'s metaclass).
  The metaclass's `__call__` method is wrapped using `decorator` to
  intercept/inject parameters for class construction. The resulting subclass has
  metadata (docstring, name, and module information) copied over from
  `fn_or_cls`, and should behave like the original as much possible, without
  modifying it (for example, inspection operations using `issubclass` should
  behave the same way as on the original class). When constructed, an instance
  of the original (undecorated) class is returned.

  Args:
    decorator: The decorator to use.
    fn_or_cls: The function or class to decorate.
    selector: The Gin selector for `fn_or_cls`. This is used to modify method
      modules to match the overall class selector.
    avoid_class_mutation: Whether to avoid class mutation using dynamic
      subclassing. This argument is ignored if `fn_or_cls` is not a class.
    decorate_methods: Whether to also decorate Gin-registered methods.

  Returns:
    The decorated function or class.
  """
  if not inspect.isclass(fn_or_cls):  # pytype: disable=wrong-arg-types
    return decorator(_ensure_wrappability(fn_or_cls))
  cls = fn_or_cls
  if avoid_class_mutation:
    # This approach enables @gin.register and gin.external_configurable(), and
    # is in most cases compatible with pickling instances. We can't use it for
    # @gin.configurable because the decorated class returned below can interact
    # poorly with `super(type, obj)` if `type` references the decorated version
    # while `obj` is an instance of the original undecorated class.
    method_overrides = _find_registered_methods(cls, selector)
    if decorate_methods:
      method_overrides = {
          name: decorator(method) for name, method in method_overrides.items()
      }
    cls_meta = type(cls)  # The metaclass of the given class.
    if method_overrides:
      # If we have methods to override, we just use cls_meta.__call__ directly.
      # This creates a new sub-class instance (`decorated_class` below) that
      # contains the replaced methods, but also means the dynamically created
      # class isn't pickle-compatible, since it differs from the base class.
      meta_call = cls_meta.__call__
    else:
      # Otherwise, we wrap the __call__ method on the metaclass. The basic
      # strategy here is to create a new metaclass (subclassing the class's
      # metaclass to preserve behavior), wrapping its __call__ method to return
      # an instance of the *original* (undecorated) class. Gin's wrapper is then
      # applied to this decorated __call__ method to ensure any configured
      # parameters are passed through to `__init__` or `__new__` appropriately.
      meta_call = _make_meta_call_wrapper(cls)  # See this for more details.
    # We decorate our possibly-wrapped metaclass __call__ with Gin's wrapper.
    decorated_call = decorator(_ensure_wrappability(meta_call))
    # And now construct a new metaclass, subclassing the one from `cls`,
    # supplying our decorated `__call__`. Most often this is just subclassing
    # Python's `type`, but when `cls` has a custom metaclass set, this ensures
    # that it will continue to work properly.
    decorating_meta = type(cls_meta)(cls_meta.__name__, (cls_meta,), {
        '__call__': decorated_call,
    })
    # Now we construct our class. This is a subclass of `cls`, but only with
    # wrapper-related overrides, since injecting/intercepting parameters is all
    # handled in the metaclass's `__call__` method. Note that we let
    # '__annotations__' simply get forwarded to the base class, since creating
    # a new type doesn't set this attribute by default.
    overrides = {
        attr: getattr(cls, attr)
        for attr in ('__module__', '__name__', '__qualname__', '__doc__')
    }
    # If `cls` won't have a `__dict__` attribute, disable `__dict__` creation on
    # our subclass as well. This seems like generally correct behavior, and also
    # prevents errors that can arise under some very specific circumstances due
    # to a CPython bug in type creation.
    if getattr(cls, '__dictoffset__', None) == 0:
      overrides['__slots__'] = ()
    # Update our overrides with any methods we need to replace.
    overrides.update(method_overrides)
    # Finally, create the decorated class using the metaclass created above.
    decorated_class = decorating_meta(cls.__name__, (cls,), overrides)
  else:
    # Here, we just decorate `__init__` or `__new__` directly, and mutate the
    # original class definition to use the decorated version. This is simpler
    # and permits reliable subclassing of @gin.configurable decorated classes.
    decorated_class = cls
    construction_fn = _find_class_construction_fn(decorated_class)
    decorated_fn = decorator(_ensure_wrappability(construction_fn))
    if construction_fn.__name__ == '__new__':
      decorated_fn = staticmethod(decorated_fn)
    setattr(decorated_class, construction_fn.__name__, decorated_fn)
  return decorated_class


class Configurable(typing.NamedTuple):
  wrapper: Callable[..., Any]
  wrapped: Callable[..., Any]
  name: str
  module: str
  import_source: Optional[Tuple[config_parser.ImportStatement, str]]
  allowlist: Optional[Sequence[str]]
  denylist: Optional[Sequence[str]]
  selector: str
  is_method: bool = False


def _raise_unknown_reference_error(ref, additional_msg=''):
  err_str = "No configurable matching reference '@{}{}'.{}"
  maybe_parens = '()' if ref.evaluate else ''
  raise ValueError(err_str.format(ref.selector, maybe_parens, additional_msg))


def _raise_unknown_configurable_error(selector):
  raise ValueError(f"No configurable matching '{selector}'.")


def _decorate_with_scope(configurable_, scope_components):
  """Decorates `configurable`, using the given `scope_components`.

  Args:
    configurable_: A `Configurable` instance, whose `wrapper` attribute should
      be decorated.
    scope_components: The list of scope components to use as a scope (e.g., as
      returned by `current_scope`).

  Returns:
    A callable function or class, that applies the given scope to
    `configurable_.wrapper`.
  """

  def scope_decorator(fn_or_cls):

    @functools.wraps(fn_or_cls)
    def scoping_wrapper(*args, **kwargs):
      with config_scope(scope_components):
        return fn_or_cls(*args, **kwargs)

    return scoping_wrapper

  if scope_components:
    return _decorate_fn_or_cls(
        scope_decorator,
        configurable_.wrapper,
        configurable_.selector,
        avoid_class_mutation=True,
        decorate_methods=True)
  else:
    return configurable_.wrapper


class ConfigurableReference:
  """Represents a reference to a configurable function or class."""

  def __init__(self, scoped_selector, evaluate):
    self._scoped_selector = scoped_selector
    self._evaluate = evaluate
    self.initialize()

  def initialize(self):
    *self._scopes, self._selector = self._scoped_selector.split('/')
    self._configurable = _parse_context().get_configurable(self._selector)
    if not self._configurable:
      _raise_unknown_reference_error(self)
    self._scoped_configurable_fn = _decorate_with_scope(
        self._configurable, scope_components=self._scopes)

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
      return (self._configurable == other._configurable and
              self._evaluate == other._evaluate)
      # pylint: enable=protected-access
    return False

  def __ne__(self, other):
    return not self.__eq__(other)

  def __hash__(self):
    return hash(repr(self))

  def __repr__(self):
    # Check if this reference is a macro or constant, i.e. @.../macro() or
    # @.../constant(). Only macros and constants correspond to the %... syntax.
    configurable_fn = self._configurable.wrapped
    if configurable_fn in (macro, _retrieve_constant) and self._evaluate:
      return '%' + '/'.join(self._scopes)
    maybe_parens = '()' if self._evaluate else ''
    import_manager = _parse_context().import_manager
    if import_manager is not None and import_manager.dynamic_registration:
      selector = import_manager.minimal_selector(self._configurable)
    else:
      selector = self.selector
    scoped_selector = '/'.join([*self.scopes, selector])
    return '@{}{}'.format(scoped_selector, maybe_parens)

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


class _UnknownConfigurableReference:
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


class ParsedBindingKey(typing.NamedTuple):
  """Represents a parsed and validated binding key.

  A "binding key" identifies a specific parameter (`arg_name`), of a specific
  configurable (`complete_selector`), in a specific scope (`scope`), to which a
  value may be bound in the global configuration. The `given_selector` field
  retains information about how the original configurable selector was
  specified, which can be helpful for error messages (but is ignored for the
  purposes of equality and hashing).
  """

  scope: str
  given_selector: str
  complete_selector: str
  arg_name: str

  @classmethod
  def parse(cls, binding_key):
    """Parses and validates the given binding key.

    This function will parse `binding_key` (if necessary), and ensure that the
    specified parameter can be bound for the given configurable selector (i.e.,
    that the parameter isn't denylisted or not allowlisted if an allowlist was
    provided).

    Args:
      binding_key: A spec identifying a parameter of a configurable (maybe in
        some scope). This should either be a string of the form
        'maybe/some/scope/maybe.modules.configurable_name.parameter_name'; or a
        list or tuple of `(scope, selector, arg_name)`; or another instance of
        `ParsedBindingKey`.

    Returns:
      A new instance of `ParsedBindingKey`.

    Raises:
      ValueError: If no function can be found matching the configurable name
        specified by `binding_key`, or if the specified parameter name is
        denylisted or not in the function's allowlist (if present).
    """
    if isinstance(binding_key, ParsedBindingKey):
      return cls(*binding_key)

    if isinstance(binding_key, (list, tuple)):
      scope, selector, arg_name = binding_key
    elif isinstance(binding_key, str):
      scope, selector, arg_name = config_parser.parse_binding_key(binding_key)
    else:
      err_str = 'Invalid type for binding_key: {}.'
      raise ValueError(err_str.format(type(binding_key)))

    configurable_ = _parse_context().get_configurable(selector)
    if not configurable_:
      _raise_unknown_configurable_error(selector)

    if configurable_.is_method and '.' not in selector:
      class_name = configurable_.selector.split('.')[-2]
      err_str = "Method '{}' referenced without class name '{}'."
      raise ValueError(err_str.format(selector, class_name))

    if not _might_have_parameter(configurable_.wrapper, arg_name):
      err_str = "Configurable '{}' doesn't have a parameter named '{}'."
      raise ValueError(err_str.format(selector, arg_name))

    if configurable_.allowlist and arg_name not in configurable_.allowlist:
      err_str = "Configurable '{}' doesn't include kwarg '{}' in its allowlist."
      raise ValueError(err_str.format(selector, arg_name))

    if configurable_.denylist and arg_name in configurable_.denylist:
      err_str = "Configurable '{}' has denylisted kwarg '{}'."
      raise ValueError(err_str.format(selector, arg_name))

    return cls(
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
    _CONSTANTS['gin.REQUIRED'] = REQUIRED
  else:
    saved_constants = _CONSTANTS.copy()
    _CONSTANTS.clear()  # Clear then redefine constants (re-adding bindings).
    for name, value in saved_constants.items():
      constant(name, value)
  _IMPORTS.clear()
  with _OPERATIVE_CONFIG_LOCK:
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
      denylisted or not in the function's allowlist (if present).
  """
  if config_is_locked():
    raise RuntimeError('Attempted to modify locked Gin config.')

  pbk = ParsedBindingKey.parse(binding_key)
  fn_dict = _CONFIG.setdefault(pbk.config_key, {})
  fn_dict[pbk.arg_name] = value


def query_parameter(binding_key):
  """Returns the currently bound value to the specified `binding_key`.

  The `binding_key` argument should look like
  'maybe/some/scope/maybe.modules.configurable_name.parameter_name'. Note that
  this will not include default parameters.

  Args:
    binding_key: The parameter whose value should be queried.

  Returns:
    The value bound to the configurable/parameter combination given in
    `binding_key`.

  Raises:
    ValueError: If no function can be found matching the configurable name
      specified by `binding_key`, or if the specified parameter name is
      denylisted or not in the function's allowlist (if present) or if there is
      no value bound for the queried parameter or configurable.
  """
  if config_parser.MODULE_RE.match(binding_key):
    matching_selectors = _CONSTANTS.matching_selectors(binding_key)
    if len(matching_selectors) == 1:
      return _CONSTANTS[matching_selectors[0]]
    elif len(matching_selectors) > 1:
      err_str = "Ambiguous constant selector '{}', matches {}."
      raise ValueError(err_str.format(binding_key, matching_selectors))
  pbk = ParsedBindingKey.parse(binding_key)
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
  if inspect.isclass(fn_or_cls):  # pytype: disable=wrong-arg-types
    fn = _find_class_construction_fn(fn_or_cls)
  else:
    fn = fn_or_cls

  while hasattr(fn, '__wrapped__'):
    fn = fn.__wrapped__
  arg_spec = _get_cached_arg_spec(fn)
  if arg_spec.varkw:
    return True
  return arg_name in arg_spec.args or arg_name in arg_spec.kwonlyargs


def _validate_parameters(fn_or_cls, arg_name_list, err_prefix):
  for arg_name in arg_name_list or []:
    if not _might_have_parameter(fn_or_cls, arg_name):
      err_str = "Argument '{}' in {} not a parameter of '{}'."
      raise ValueError(err_str.format(arg_name, err_prefix, fn_or_cls.__name__))


def _get_cached_arg_spec(fn):
  """Gets cached argspec for `fn`."""
  arg_spec = _ARG_SPEC_CACHE.get(fn)
  if arg_spec is None:
    try:
      arg_spec = inspect.getfullargspec(fn)
    except TypeError:
      # `fn` might be a callable object.
      arg_spec = inspect.getfullargspec(fn.__call__)
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


def _get_kwarg_defaults(fn):
  """Returns a dict mapping kwargs to default values for the given function."""
  arg_spec = _get_cached_arg_spec(fn)
  if arg_spec.defaults:
    default_kwarg_names = arg_spec.args[-len(arg_spec.defaults):]
    arg_vals = dict(zip(default_kwarg_names, arg_spec.defaults))
  else:
    arg_vals = {}

  if arg_spec.kwonlydefaults:
    arg_vals.update(arg_spec.kwonlydefaults)

  return arg_vals


def _get_validated_required_kwargs(fn, fn_descriptor, allowlist, denylist):
  """Gets required argument names, and validates against allow/denylist."""
  kwarg_defaults = _get_kwarg_defaults(fn)

  required_kwargs = []
  for kwarg, default in kwarg_defaults.items():
    if default is REQUIRED:
      if denylist and kwarg in denylist:
        err_str = "Argument '{}' of {} marked REQUIRED but denylisted."
        raise ValueError(err_str.format(kwarg, fn_descriptor))
      if allowlist and kwarg not in allowlist:
        err_str = "Argument '{}' of {} marked REQUIRED but not allowlisted."
        raise ValueError(err_str.format(kwarg, fn_descriptor))
      required_kwargs.append(kwarg)

  return required_kwargs


def _get_default_configurable_parameter_values(fn, allowlist, denylist):
  """Retrieve all default values for configurable parameters of a function.

  Any parameters included in the supplied denylist, or not included in the
  supplied allowlist, are excluded.

  Args:
    fn: The function whose parameter values should be retrieved.
    allowlist: The allowlist (or `None`) associated with the function.
    denylist: The denylist (or `None`) associated with the function.

  Returns:
    A dictionary mapping configurable parameter names to their default values.
  """
  arg_vals = _get_kwarg_defaults(fn)

  # Now, eliminate keywords that are denylisted, or aren't allowlisted (if
  # there's an allowlist), or aren't representable as a literal value.
  for k in list(arg_vals):
    allowlist_fail = allowlist and k not in allowlist
    denylist_fail = denylist and k in denylist
    representable = _is_literally_representable(arg_vals[k])
    if allowlist_fail or denylist_fail or not representable:
      del arg_vals[k]

  return arg_vals


def _order_by_signature(fn, arg_names):
  """Orders given `arg_names` based on their order in the signature of `fn`."""
  arg_spec = _get_cached_arg_spec(fn)
  all_args = list(arg_spec.args)
  if arg_spec.kwonlyargs:
    all_args.extend(arg_spec.kwonlyargs)
  ordered = [arg for arg in all_args if arg in arg_names]
  # Handle any leftovers corresponding to varkwargs in the order we got them.
  ordered.extend([arg for arg in arg_names if arg not in ordered])
  return ordered


def current_scope():
  return _SCOPE_MANAGER.current_scope


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
    elif name_or_scope and isinstance(name_or_scope, str):
      new_scope = current_scope()  # Returns a copy.
      new_scope.extend(name_or_scope.split('/'))
    else:
      valid_value = name_or_scope in (None, '')
      new_scope = []

    # Append new_scope first. It will be popped in the finally block if an
    # exception is raised below.
    _SCOPE_MANAGER.enter_scope(new_scope)

    scopes_are_valid = map(config_parser.MODULE_RE.match, new_scope)
    if not valid_value or not all(scopes_are_valid):
      err_str = 'Invalid value for `name_or_scope`: {}.'
      raise ValueError(err_str.format(name_or_scope))

    yield new_scope
  finally:
    _SCOPE_MANAGER.exit_scope()


_FnOrClsOrSelector = Union[Callable[..., Any], Type[Any], str]


def _as_scope_and_selector(
    fn_or_cls_or_selector: _FnOrClsOrSelector) -> Tuple[Sequence[str], str]:
  """Finds the complete selector corresponding to `fn_or_cls`.

  Args:
    fn_or_cls_or_selector: Configurable function, class or selector `str`.

  Returns:
    A tuple of `(scope_components, selector)`, where `scope_components` is a
    list of the scope elements, either as present in the selector string passed
    as input, or obtained from the current scope.
  """
  scope = []
  if isinstance(fn_or_cls_or_selector, str):
    # Resolve partial selector -> full selector
    *scope, selector = fn_or_cls_or_selector.split('/')
    selector = _REGISTRY.get_match(selector)
    if selector:
      selector = selector.selector
  else:
    configurable_ = _inverse_lookup(fn_or_cls_or_selector)
    selector = configurable_.selector if configurable_ else None

  if not scope:
    scope = current_scope()

  if selector is None:
    raise ValueError(
        f'Could not find {fn_or_cls_or_selector} in the Gin registry.')

  return scope, selector


def _get_bindings(
    selector: str,
    scope_components=None,
    inherit_scopes: bool = True,
) -> Dict[str, Any]:
  """Returns the bindings for the current full selector, with optional scope."""
  scope_components = scope_components or current_scope()
  new_kwargs = {}

  if not inherit_scopes:  # In strict scope mode, only match the exact scope
    partial_scopes = [scope_components]
  else:
    partial_scopes = [
        scope_components[:i] for i in range(len(scope_components) + 1)]
  for partial_scope in partial_scopes:
    partial_scope_str = '/'.join(partial_scope)
    new_kwargs.update(_CONFIG.get((partial_scope_str, selector), {}))
  return new_kwargs


def get_bindings(
    fn_or_cls_or_selector: _FnOrClsOrSelector,
    resolve_references: bool = True,
    inherit_scopes: bool = True,
) -> Dict[str, Any]:
  """Returns the bindings associated with the given configurable.

  Any configurable references in the bindings will be resolved during the call
  (and evaluated references will be evaluated).

  Example:

  ```python
  config.parse_config('MyParams.kwarg0 = 123')

  gin.get_bindings('MyParams') == {'kwarg0': 123}
  ```

  Note: The scope in which `get_bindings` is called will be used.

  Args:
    fn_or_cls_or_selector: Configurable function, class or selector `str`.
    resolve_references: Whether or not references (and macros) should be
      resolved. If `False`, the output may contain instances of Gin's
      `ConfigurableReference` class.
    inherit_scopes: If False, only match the exact scope (so
      `get_bindings('scope1/fn')` do not match `scope1/scope2/fn`, nor `fn` but
      only the exact 'scope1/fn').

  Returns:
    The bindings kwargs injected by Gin.
  """
  scope_components, selector = _as_scope_and_selector(fn_or_cls_or_selector)
  bindings_kwargs = _get_bindings(
      selector,
      scope_components=scope_components,
      inherit_scopes=inherit_scopes,
  )
  if resolve_references:
    return copy.deepcopy(bindings_kwargs)
  else:
    return bindings_kwargs


def get_configurable(
    fn_or_cls_or_selector: _FnOrClsOrSelector) -> Callable[..., Any]:
  """Returns the configurable version of `fn_or_cls_or_selector`.

  If a function or class has been registered with Gin, Gin's configurable
  version (which will have all relevant Gin bindings applied) can be obtained by
  calling this function with any of the following:

    - The original function or class (the "non-configurable" version);
    - The configurable function or class (so this function is effectively a
      no-op for functions annotated with `@gin.configurable`);
    - A selector string that specifies the function or class.

  If passing a selector string, a scope may be supplied, in which case the
  returned configurable will have the scope applied. If a function or class is
  passed, or no scope is supplied as part of the selector string, the current
  active scope will be used instead.

  Args:
    fn_or_cls_or_selector: Configurable function, class or selector `str`.

  Returns:
    The configurable function or class corresponding to `fn_or_cls_or_selector`.
  """
  scope_components, selector = _as_scope_and_selector(fn_or_cls_or_selector)
  configurable_ = _REGISTRY[selector]
  return _decorate_with_scope(configurable_, scope_components=scope_components)


def _make_gin_wrapper(fn, fn_or_cls, name, selector, allowlist, denylist):
  """Creates the final Gin wrapper for the given function.

  Args:
    fn: The function that will be wrapped.
    fn_or_cls: The original function or class being made configurable. This will
      differ from `fn` when making a class configurable, in which case `fn` will
      be the constructor/new function (or when proxying a class, the type's
      `__call__` method), while `fn_or_cls` will be the class.
    name: The name given to the configurable.
    selector: The full selector of the configurable (name including any module
      components).
    allowlist: An allowlist of configurable parameters.
    denylist: A denylist of non-configurable parameters.

  Returns:
    The Gin wrapper around `fn`.
  """
  # At this point we have access to the final function to be wrapped, so we
  # can cache a few things here.
  fn_descriptor = "'{}' ('{}')".format(name, fn_or_cls)
  signature_fn = fn_or_cls
  if inspect.isclass(fn_or_cls):
    signature_fn = _find_class_construction_fn(fn_or_cls)
  signature_required_kwargs = _get_validated_required_kwargs(
      signature_fn, fn_descriptor, allowlist, denylist)
  initial_configurable_defaults = _get_default_configurable_parameter_values(
      signature_fn, allowlist, denylist)

  @functools.wraps(fn)
  def gin_wrapper(*args, **kwargs):
    """Supplies fn with parameter values from the configuration."""
    current_selector = _RENAMED_SELECTORS.get(selector, selector)
    new_kwargs = _get_bindings(current_selector)
    gin_bound_args = list(new_kwargs.keys())
    scope_str = '/'.join(current_scope())

    arg_names = _get_supplied_positional_parameter_names(signature_fn, args)

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

    caller_required_kwargs = []
    for kwarg, value in kwargs.items():
      if value is REQUIRED:
        caller_required_kwargs.append(kwarg)

    # If the caller passed arguments as positional arguments that correspond to
    # a keyword arg in new_kwargs, remove the keyword argument from new_kwargs
    # to let the caller win and avoid throwing an error. Unless it is an arg
    # marked as REQUIRED.
    for arg_name in arg_names:
      if arg_name not in required_arg_names:
        new_kwargs.pop(arg_name, None)

    # Get default values for configurable parameters.
    operative_parameter_values = initial_configurable_defaults.copy()
    # Update with the values supplied via configuration.
    operative_parameter_values.update(new_kwargs)

    # Remove any values from the operative config that are overridden by the
    # caller. These can't be configured, so they won't be logged. We skip values
    # that are marked as REQUIRED.
    for k in arg_names:
      if k not in required_arg_names:
        operative_parameter_values.pop(k, None)
    for k in kwargs:
      if k not in caller_required_kwargs:
        operative_parameter_values.pop(k, None)

    # An update is performed in case another caller of this same configurable
    # object has supplied a different set of arguments. By doing an update, a
    # Gin-supplied or default value will be present if it was used (not
    # overridden by the caller) at least once.
    with _OPERATIVE_CONFIG_LOCK:
      op_cfg = _OPERATIVE_CONFIG.setdefault((scope_str, current_selector), {})
      op_cfg.update(operative_parameter_values)

    # We call deepcopy for two reasons: First, to prevent the called function
    # from modifying any of the values in `_CONFIG` through references passed in
    # via `new_kwargs`; Second, to facilitate evaluation of any
    # `ConfigurableReference` instances buried somewhere inside `new_kwargs`.
    # See the docstring on `ConfigurableReference.__deepcopy__` above for more
    # details on the dark magic happening here.
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
    for required_kwarg in signature_required_kwargs:
      if (required_kwarg not in arg_names and  # not a positional arg
          required_kwarg not in kwargs and  # or a keyword arg
          required_kwarg not in new_kwargs):  # or bound in config
        missing_required_params.append(required_kwarg)
    for required_kwarg in caller_required_kwargs:
      if required_kwarg not in new_kwargs:
        missing_required_params.append(required_kwarg)
      else:
        # Remove from kwargs and let the new_kwargs value be used.
        kwargs.pop(required_kwarg)

    if missing_required_params:
      missing_required_params = (
          _order_by_signature(signature_fn, missing_required_params))
      err_str = 'Required bindings for `{}` not provided in config: {}'
      minimal_selector = _REGISTRY.minimal_selector(current_selector)
      err_str = err_str.format(minimal_selector, missing_required_params)
      raise RuntimeError(err_str)

    # Now, update with the caller-supplied `kwargs`, allowing the caller to have
    # the final say on keyword argument values.
    new_kwargs.update(kwargs)

    try:
      return fn(*new_args, **new_kwargs)
    except Exception as e:  # pylint: disable=broad-except
      err_str = ''
      if isinstance(e, TypeError):
        all_arg_names = _get_all_positional_parameter_names(signature_fn)
        if len(new_args) < len(all_arg_names):
          unbound_positional_args = list(
              set(all_arg_names[len(new_args):]) - set(new_kwargs))
          if unbound_positional_args:
            caller_supplied_args = list(
                set(arg_names + list(kwargs)) -
                set(required_arg_names + list(caller_required_kwargs)))
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
      err_str = err_str.format(name, fn_or_cls, scope_info)
      utils.augment_exception_message_and_reraise(e, err_str)

  return gin_wrapper


def _make_configurable(fn_or_cls,
                       name=None,
                       module=None,
                       allowlist=None,
                       denylist=None,
                       avoid_class_mutation=False,
                       import_source=None):
  """Wraps `fn_or_cls` to make it configurable.

  Infers the configurable name from `fn_or_cls.__name__` if necessary, and
  updates global state to keep track of configurable name <-> function
  mappings, as well as allowlisted and denylisted parameters.

  Args:
    fn_or_cls: The function or class to decorate.
    name: A name for the configurable. If `None`, the name will be inferred from
      from `fn_or_cls`. The `name` may also include module components to be used
      for disambiguation (these will be appended to any components explicitly
      specified by `module`).
    module: The module to associate with the configurable, to help handle naming
      collisions. If `None`, `fn_or_cls.__module__` will be used (if no module
      is specified as part of `name`).
    allowlist: An allowlisted set of parameter names to supply values for.
    denylist: A denylisted set of parameter names not to supply values for.
    avoid_class_mutation: If `fn_or_cls` is a class and `avoid_class_mutation`
      is `True`, decorate by subclassing `fn_or_cls`'s metaclass and overriding
      its `__call__` method. If `False`, replace the existing `__init__` or
      `__new__` with a decorated version.
    import_source: When using dynamic registration, this provides the import
      source of the registered configurable and consists of a tuple of
      `(source_module, attribute_path)` describing the module fn_or_cls is
      imported from and its attribute path within that module.

  Returns:
    A wrapped version of `fn_or_cls` that will take parameter values from the
    global configuration.

  Raises:
    RuntimeError: If the config is locked.
    ValueError: If a configurable with `name` (or the name of `fn_or_cls`)
      already exists, or if both an allowlist and denylist are specified.
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
  if (not _INTERACTIVE_MODE and selector in _REGISTRY and
      _REGISTRY[selector].wrapped is not fn_or_cls):
    err_str = ("A different configurable matching '{}' already exists.\n\n"
               'To allow re-registration of configurables in an interactive '
               'environment, use:\n\n'
               '    gin.enter_interactive_mode()')
    raise ValueError(err_str.format(selector))

  if allowlist and denylist:
    err_str = 'An allowlist or a denylist can be specified, but not both.'
    raise ValueError(err_str)

  if allowlist and not isinstance(allowlist, (list, tuple)):
    raise TypeError('allowlist should be a list or tuple.')

  if denylist and not isinstance(denylist, (list, tuple)):
    raise TypeError('denylist should be a list or tuple.')

  _validate_parameters(fn_or_cls, allowlist, 'allowlist')
  _validate_parameters(fn_or_cls, denylist, 'denylist')

  def decorator(fn):
    """Wraps `fn` so that it obtains parameters from the configuration."""
    return _make_gin_wrapper(fn, fn_or_cls, name, selector, allowlist,
                             denylist)

  decorated_fn_or_cls = _decorate_fn_or_cls(
      decorator, fn_or_cls, selector, avoid_class_mutation=avoid_class_mutation)

  configurable_info = Configurable(
      wrapper=decorated_fn_or_cls,
      wrapped=fn_or_cls,
      name=name,
      module=module,
      import_source=import_source,
      allowlist=allowlist,
      denylist=denylist,
      selector=selector)
  _REGISTRY[selector] = configurable_info
  _INVERSE_REGISTRY[fn_or_cls] = configurable_info
  return decorated_fn_or_cls


def configurable(name_or_fn=None,
                 module=None,
                 allowlist=None,
                 denylist=None):
  """Decorator to make a function or class configurable.

  This decorator registers the decorated function/class as configurable, which
  allows its parameters to be supplied from the global configuration (i.e., set
  through `bind_parameter` or `parse_config`). The decorated function is
  associated with a name in the global configuration, which by default is simply
  the name of the function or class, but can be specified explicitly to avoid
  naming collisions or improve clarity.

  If some parameters should not be configurable, they can be specified in
  `denylist`. If only a restricted set of parameters should be configurable,
  they can be specified in `allowlist`.

  The decorator can be used without any parameters as follows:

      @config.configurable
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the function is associated with the name
  `'some_configurable_function'` in the global configuration, and both `param1`
  and `param2` are configurable.

  The decorator can be supplied with parameters to specify the configurable name
  or supply an allowlist/denylist:

      @config.configurable('explicit_configurable_name', allowlist='param2')
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the configurable is associated with the name
  `'explicit_configurable_name'` in the global configuration, and only `param2`
  is configurable.

  Classes can be decorated as well, in which case parameters of their
  constructors are made configurable:

      @config.configurable
      class SomeClass:
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
    allowlist: An allowlisted set of kwargs that should be configurable. All
      other kwargs will not be configurable. Only one of `allowlist` or
      `denylist` should be specified.
    denylist: A denylisted set of kwargs that should not be configurable. All
      other kwargs will be configurable. Only one of `allowlist` or `denylist`
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
    return _make_configurable(fn_or_cls, name, module, allowlist, denylist)

  if decoration_target:
    return perform_decoration(decoration_target)
  return perform_decoration


def external_configurable(fn_or_cls,
                          name=None,
                          module=None,
                          allowlist=None,
                          denylist=None):
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
      collisions. By default, `fn_or_cls.__module__` will be used (if no module
      is specified as part of the name).
    allowlist: An allowlist of parameter names to allow configuration for.
    denylist: A denylist of parameter names to deny configuration for.

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
      allowlist=allowlist,
      denylist=denylist,
      avoid_class_mutation=True)


def register(name_or_fn=None,
             module=None,
             allowlist=None,
             denylist=None):
  """Decorator to register a function or class configurable.

  This decorator only registers the decorated function/class with Gin, so it can
  be passed to other configurables in `bind_parameter` or `parse_config`.
  This decorator doesn't change the decorated function/class, so any direct
  calls from within Python code are not affected by the configuration.

  If some parameters should not be configurable, they can be specified in
  `denylist`. If only a restricted set of parameters should be configurable,
  they can be specified in `allowlist`.

  The decorator can be used without any parameters as follows:

      @config.register
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the function is associated with the name
  `'some_configurable_function'` in the configuration, and both `param1`
  and `param2` are configurable.

  The decorator can be supplied with parameters to specify the name used to
  register or supply an allowlist/denylist:

      @config.register('explicit_name', allowlist='param2')
      def some_configurable_function(param1, param2='a default value'):
        ...

  In this case, the function is registered with the name `'explicit_name'` in
  the configuration registry, and only `param2` is configurable.

  Classes can be decorated as well, in which case parameters of their
  constructors are made configurable:

      @config.register
      class SomeClass:
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
    allowlist: An allowlisted set of kwargs that should be configurable. All
      other kwargs will not be configurable. Only one of `allowlist` or
      `denylist` should be specified.
    denylist: A denylisted set of kwargs that should not be configurable. All
      other kwargs will be configurable. Only one of `allowlist` or `denylist`
      should be specified.

  Returns:
    When used with no parameters as a decorator (or with a function/class
    supplied as the first parameter), it returns the target function or class
    unchanged. When used with parameters, it returns a function that can be
    applied to register the target function or class with Gin (this function
    also returns the target function or class unchanged).
  """
  decoration_target = None
  if callable(name_or_fn):
    decoration_target = name_or_fn
    name = None
  else:
    name = name_or_fn

  def perform_decoration(fn_or_cls):
    # Register it as configurable but return the original fn_or_cls.
    _make_configurable(
        fn_or_cls,
        name=name,
        module=module,
        allowlist=allowlist,
        denylist=denylist,
        avoid_class_mutation=True)
    return fn_or_cls

  if decoration_target:
    return perform_decoration(decoration_target)
  return perform_decoration


def _make_unique(sequence, key=None):
  key = key or (lambda x: x)
  seen = set()
  output = []
  for x in sequence:
    key_val = key(x)
    if key_val not in seen:
      seen.add(key_val)
      output.append(x)
  return output


def _uniquify_name(candidate_name: str, existing_names: Set[str]):
  i = 2
  unique_name = candidate_name
  while unique_name in existing_names:
    unique_name = candidate_name + str(i)
    i += 1
  return unique_name


class ImportManager:
  """Manages imports required when writing out a full config string.

  This class does bookkeeping to ensure each import is only output once, and
  that each import receives a unique name/alias to avoid collisions.
  """

  def __init__(self, imports):
    """Initializes the `ImportManager` instance.

    Args:
      imports: An iterable of `ImportStatement` instances, providing existing
        imports to manage. Every effort will be taken here to respect the
        existing structure and format of the imports (e.g., any aliases
        provided, and whether the imports use the `from` syntax). Note that if
        dynamic registration is enabled, it should be included here as one of
        the provided statements.
    """
    self.dynamic_registration = any(
        statement.module == '__gin__.dynamic_registration'
        for statement in imports)
    self.imports = []
    self.module_selectors = {}
    self.names = set()
    # Prefer to order `from` style imports first.
    for statement in sorted(imports, key=lambda s: (s.module, not s.is_from)):
      self.add_import(statement)

  @property
  def sorted_imports(self):
    return sorted(self.imports, key=lambda s: s.module)

  def add_import(self, statement: config_parser.ImportStatement):
    """Adds a single import to this `ImportManager` instance.

    The provided statement is deduped and possibly re-aliased to ensure it has a
    unique name.

    Args:
      statement: The `ImportStatement` to add.
    """
    if statement.module in self.module_selectors:
      return
    unique_name = _uniquify_name(statement.bound_name(), self.names)
    if unique_name != statement.bound_name():
      statement = statement._replace(alias=unique_name)
    if statement.is_from or statement.alias:
      selector = statement.bound_name()
    else:
      selector = statement.module
    self.module_selectors[statement.module] = selector
    self.names.add(statement.bound_name())
    self.imports.append(statement)

  def require_configurable(self, configurable_: Configurable):
    """Adds the import required for `configurable_`, if not already present.

    Args:
      configurable_: The specific `Configurable` whose corresponding module
        should be imported.
    """
    if not self.dynamic_registration:
      return
    if configurable_.wrapped == macro:  # pylint: disable=comparison-with-callable
      return
    if configurable_.import_source:
      self.add_import(configurable_.import_source[0])
    elif hasattr(configurable_.wrapped, '__module__'):
      module = configurable_.wrapped.__module__
      import_statement = config_parser.ImportStatement(
          module=module,
          is_from='.' in module,
          alias=None,
          location=config_parser.Location(None, 0, None, ''))
      self.add_import(import_statement)
    else:
      logging.warning(
          'Configurable %r was not imported using dynamic registration and has '
          'no __module__ attribute; dynamic registration will not be used in '
          'the resulting config string. This is likely because the initial set '
          'of parsed Gin files included a mix of files with and without '
          'dynamic registration.', configurable_)
      for statement in self.imports:
        if statement.module == '__gin__.dynamic_registration':
          self.imports.remove(statement)
          break
      self.dynamic_registration = False

  def minimal_selector(self, configurable_: Configurable) -> str:
    """Returns a minimal selector corresponding to `configurable_`.

    This method has different behavior depending on whether dynamic registration
    has been enabled (see `__init__`). If dynamic registration is enabled, then
    the minimal selector is a full '.'-seperated attribute chain beginning with
    the name of an imported module. If dynamic registration is not enabled, then
    the returned selector is the minimal string required to uniquely identify
    `configurable_` (this includes the function/class name, and enough
    components of its module name to make the resulting selector unique).

    Args:
      configurable_: The `Configurable` to return a minimal selector for.

    Returns:
      The minimal selector for `configurable_` as a string.
    """
    if self.dynamic_registration:
      if configurable_.import_source:
        import_statement, name = configurable_.import_source
        module = import_statement.module
      else:
        module = configurable_.wrapped.__module__
        name = configurable_.wrapped.__qualname__
      return f'{self.module_selectors[module]}.{name}'
    else:
      minimal_selector = _REGISTRY.minimal_selector(configurable_.selector)
      if configurable_.is_method:
        # Methods require `Class.method` as selector.
        if '.' not in minimal_selector:
          minimal_selector = '.'.join(configurable_.selector.split('.')[-2:])
      return minimal_selector


def _config_str(configuration_object,
                max_line_length=80,
                continuation_indent=4):
  """Print the configuration specified in configuration object.

  Args:
    configuration_object: Either _OPERATIVE_CONFIG (operative config) or _CONFIG
      (all config, bound and unbound).
    max_line_length: A (soft) constraint on the maximum length of a line in the
      formatted string. Large nested structures will be split across lines, but
      e.g. long strings won't be split into a concatenation of shorter strings.
    continuation_indent: The indentation for continued lines.

  Returns:
    A config string capturing all parameter values set by the object.
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
    if _REGISTRY[selector].is_method:
      method_name = parts.pop(0)
      parts[0] += f'.{method_name}'  # parts[0] is the class name.
    return parts

  import_manager = ImportManager(_IMPORTS)
  if import_manager.dynamic_registration:
    for _, selector in configuration_object:
      import_manager.require_configurable(_REGISTRY[selector])
    for reference in iterate_references(configuration_object):
      import_manager.require_configurable(reference.configurable)

  # Build the output as an array of formatted Gin statements. Each statement may
  # span multiple lines. Imports are first, followed by macros, and finally all
  # other bindings sorted in alphabetical order by configurable name.
  formatted_statements = [
      statement.format() for statement in import_manager.sorted_imports
  ]
  if formatted_statements:
    formatted_statements.append('')

  # For config strings that use dynamic registration, we need a parse scope open
  # in order to properly resolve symbols. In particular, the
  # _is_literally_representable function checks to see if something can be
  # parsed in order to determine if it should be represented in the config str.
  with _parse_scope(import_manager=import_manager):
    macros = {}
    for (scope, selector), config in configuration_object.items():
      if _REGISTRY[selector].wrapped == macro:  # pylint: disable=comparison-with-callable
        macros[scope, selector] = config
    if macros:
      formatted_statements.append('# Macros:')
      formatted_statements.append('# ' + '=' * (max_line_length - 2))
    for (name, _), config in sorted(macros.items(), key=sort_key):
      binding = format_binding(name, config['value'])
      formatted_statements.append(binding)
    if macros:
      formatted_statements.append('')

    sorted_items = sorted(configuration_object.items(), key=sort_key)
    for (scope, selector), config in sorted_items:
      configurable_ = _REGISTRY[selector]
      if configurable_.wrapped in (macro, _retrieve_constant):  # pylint: disable=comparison-with-callable
        continue

      minimal_selector = import_manager.minimal_selector(configurable_)
      scoped_selector = (scope + '/' if scope else '') + minimal_selector
      parameters = [
          (k, v) for k, v in config.items() if _is_literally_representable(v)
      ]
      formatted_statements.append(
          '# Parameters for {}:'.format(scoped_selector))
      formatted_statements.append('# ' + '=' * (max_line_length - 2))
      for arg, val in sorted(parameters):
        binding = format_binding('{}.{}'.format(scoped_selector, arg), val)
        formatted_statements.append(binding)
      if not parameters:
        formatted_statements.append('# None.')
      formatted_statements.append('')

  return '\n'.join(formatted_statements)


def operative_config_str(max_line_length=80, continuation_indent=4):
  """Retrieve the "operative" configuration as a config string.

  The operative configuration consists of all parameter values used by
  configurable functions that are actually called during execution of the
  current program. Parameters associated with configurable functions that are
  not called (and so can have no effect on program execution) won't be included.

  The goal of the function is to return a config that captures the full set of
  relevant configurable "hyperparameters" used by a program. As such, the
  returned configuration will include the default values of arguments from
  configurable functions (as long as the arguments aren't denylisted or missing
  from a supplied allowlist), as well as any parameter values overridden via
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
    A config string capturing all parameter values set in the current program.
  """
  with _OPERATIVE_CONFIG_LOCK:
    result = _config_str(
        _OPERATIVE_CONFIG, max_line_length, continuation_indent)
  return result


def config_str(max_line_length=80, continuation_indent=4):
  """Retrieve the interpreted configuration as a config string.

  This is not the _operative configuration_, in that it may include parameter
  values which are unused by by the program.

  Args:
    max_line_length: A (soft) constraint on the maximum length of a line in the
      formatted string. Large nested structures will be split across lines, but
      e.g. long strings won't be split into a concatenation of shorter strings.
    continuation_indent: The indentation for continued lines.

  Returns:
    A config string capturing all parameter values used by the current program.
  """
  return _config_str(_CONFIG, max_line_length, continuation_indent)


class ParsedConfigFileIncludesAndImports(typing.NamedTuple):
  filename: str
  imports: Sequence[str]
  includes: Sequence['ParsedConfigFileIncludesAndImports']


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

  Returns:
    includes: List of ParsedConfigFileIncludesAndImports describing the result
      of loading nested include statements.
    imports: List of names of imported modules.
  """
  if isinstance(bindings, (list, tuple)):
    bindings = '\n'.join(bindings)

  _validate_skip_unknown(skip_unknown)
  if isinstance(skip_unknown, (list, tuple)):
    skip_unknown = set(skip_unknown)

  parser = config_parser.ConfigParser(bindings, ParserDelegate(skip_unknown))
  includes = []
  imports = []
  with _parse_scope() as parse_context:
    for statement in parser:
      if isinstance(statement, config_parser.BindingStatement):
        scope, selector, arg_name, value, location = statement
        if not arg_name:
          macro_name = '{}/{}'.format(scope, selector) if scope else selector
          with utils.try_with_location(location):
            bind_parameter((macro_name, 'gin.macro', 'value'), value)
        elif not _should_skip(selector, skip_unknown):
          with utils.try_with_location(location):
            bind_parameter((scope, selector, arg_name), value)
      elif isinstance(statement, config_parser.BlockDeclaration):
        if not _should_skip(statement.selector, skip_unknown):
          with utils.try_with_location(statement.location):
            if not parse_context.get_configurable(statement.selector):
              _raise_unknown_configurable_error(statement.selector)
      elif isinstance(statement, config_parser.ImportStatement):
        with utils.try_with_location(statement.location):
          try:
            parse_context.process_import(statement)
          except ImportError as e:
            if not skip_unknown:
              raise
            _print_unknown_import_message(statement, e)
      elif isinstance(statement, config_parser.IncludeStatement):
        with utils.try_with_location(statement.location):
          nested_includes = parse_config_file(statement.filename, skip_unknown)
          includes.append(nested_includes)
      else:
        raise AssertionError(
            'Unrecognized statement type {}.'.format(statement))
    # Update recorded imports. Using the context's recorded imports ignores any
    # `from __gin __ ...` statements used to enable e.g. dynamic registration.
    imports.extend(statement.module for statement in parse_context.imports)
    _IMPORTS.update(parse_context.imports)
  return includes, imports


def _print_unknown_import_message(statement, exception):
  """Prints a properly formatted info message when skipping unknown imports."""
  log_str = 'Skipping import of unknown module `%s` (skip_unknown=True).'
  log_args = [statement.module]
  imported_modules = statement.module.split('.')
  exception_modules = exception.name.split('.')
  modules_match = imported_modules[:len(exception_modules)] == exception_modules
  if not modules_match:
    # In case the error comes from a nested import (i.e. the module is
    # available, but it imports some unavailable module), print the traceback to
    # avoid confusion.
    log_str += '\n%s'
    log_args.append(traceback.format_exc())
  logging.info(log_str, *log_args)


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


def add_config_file_search_path(location_prefix):
  """Adds a path that will be searched for config files by parse_config_file."""
  _LOCATION_PREFIXES.append(location_prefix)


def parse_config_file(
    config_file: str,
    skip_unknown: Union[bool, Sequence[str]] = False,
    print_includes_and_imports: bool = False
) -> ParsedConfigFileIncludesAndImports:
  """Parse a Gin config file.

  Args:
    config_file: The path to a Gin config file.
    skip_unknown: A boolean indicating whether unknown configurables and imports
      should be skipped instead of causing errors (alternatively a list of
      configurable names to skip if unknown). See `parse_config` for additional
      details.
    print_includes_and_imports: Whether to print the resulting nested includes
      and imports.

  Returns:
    results: An instance of ParsedConfigFileIncludesAndImports containing the
      filename of the parse files, a list of names of imported modules and a
      list of ParsedConfigFileIncludesAndImports created from including nested
      gin files.

  Raises:
    IOError: If `config_file` cannot be read using any register file reader.
  """
  prefixes = _LOCATION_PREFIXES if not os.path.isabs(config_file) else ['']
  for location_prefix in prefixes:
    config_file_with_prefix = os.path.join(location_prefix, config_file)
    for reader, existence_check in _FILE_READERS:
      if existence_check(config_file_with_prefix):
        with reader(config_file_with_prefix) as f:
          includes, imports = parse_config(f, skip_unknown=skip_unknown)
          results = ParsedConfigFileIncludesAndImports(
              filename=config_file, imports=imports, includes=includes)
          if print_includes_and_imports:
            log_includes_and_imports(results)
          return results
  err_str = 'Unable to open file: {}. Searched config paths: {}.'
  raise IOError(err_str.format(config_file, prefixes))


def parse_config_files_and_bindings(
    config_files: Optional[Sequence[str]],
    bindings: Optional[Sequence[str]],
    finalize_config: bool = True,
    skip_unknown: Union[bool, Sequence[str]] = False,
    print_includes_and_imports: bool = False):
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
    print_includes_and_imports: If true, print a summary of the hierarchy of
      included gin config files and imported modules.

  Returns:
    includes_and_imports: List of ParsedConfigFileIncludesAndImports.
  """
  if config_files is None:
    config_files = []
  if bindings is None:
    bindings = ''
  nested_includes_and_imports = []
  for config_file in config_files:
    includes_and_imports = parse_config_file(config_file, skip_unknown)
    nested_includes_and_imports.append(includes_and_imports)
  parse_config(bindings, skip_unknown)
  if finalize_config:
    finalize()

  if print_includes_and_imports:
    for includes_and_imports in nested_includes_and_imports:
      log_includes_and_imports(includes_and_imports)
    if bindings:
      logging.info('Additional Gin bindings:')
      for binding in bindings:
        logging.info('  %s', binding)
  return nested_includes_and_imports


def log_includes_and_imports(
    file_includes_and_imports: ParsedConfigFileIncludesAndImports,
    first_line_prefix: str = '',
    prefix: str = ''):
  """Logs a ParsedConfigFileIncludesAndImports and its includes and imports."""
  logging.info('%s%s', first_line_prefix, file_includes_and_imports.filename)
  infix = ' │' if file_includes_and_imports.includes else '  '
  if file_includes_and_imports.imports:
    for imported_module in file_includes_and_imports.imports:
      logging.info('%s%s import %s', prefix, infix, imported_module)
  if file_includes_and_imports.includes:
    for i, nested_result in enumerate(file_includes_and_imports.includes):
      if i < len(file_includes_and_imports.includes) - 1:
        nested_first_line_prefix = prefix + ' ├─ '
        nested_prefix = prefix + ' │ '
      else:
        nested_first_line_prefix = prefix + ' └─ '
        nested_prefix = prefix + '   '
      log_includes_and_imports(
          nested_result,
          first_line_prefix=nested_first_line_prefix,
          prefix=nested_prefix)


def parse_value(value):
  """Parse and return a single Gin value."""
  if not isinstance(value, str):
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
      for key, value in new_bindings.items():
        pbk = ParsedBindingKey.parse(key)
        if pbk in bindings:
          err_str = 'Received conflicting updates when running {}.'
          raise ValueError(err_str.format(hook))
        bindings[pbk] = value

  for pbk, value in bindings.items():
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
  if isinstance(value, str):
    yield value
    return

  if isinstance(value, collections.abc.Mapping):
    value = collections.abc.ValuesView(value)  # pytype: disable=wrong-arg-count

  if isinstance(value, collections.abc.Iterable):
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
      if to is None or value.configurable.wrapper == to:
        yield value


def validate_reference(ref, require_bindings=True, require_evaluation=False):
  if require_bindings and ref.config_key not in _CONFIG:
    err_str = "No bindings specified for '{}' in config string: \n{}"
    raise ValueError(err_str.format(ref.scoped_selector, config_str()))

  if require_evaluation and not ref.evaluate:
    err_str = ("Reference '{}' must be evaluated (add '()') "
               'in config string: \n{}.')
    raise ValueError(err_str.format(ref, config_str()))


@register(module='gin')
def macro(value):
  """A Gin macro."""
  return value


@register('constant', module='gin')
def _retrieve_constant():
  """Fetches and returns a constant from the _CONSTANTS map."""
  return _CONSTANTS[current_scope_str()]


@register(module='gin')
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


def constants_from_enum(cls=None, module=None):
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

  def decorator(cls, module=module):
    if not issubclass(cls, enum.Enum):
      raise TypeError("Class '{}' is not subclass of enum.".format(
          cls.__name__))

    if module is None:
      module = cls.__module__
    for value in cls:
      constant('{}.{}'.format(module, str(value)), value)
    return cls

  if cls is None:
    return decorator
  return decorator(cls)


@register_finalize_hook
def validate_macros_hook(config):
  for ref in iterate_references(config, to=get_configurable(macro)):
    validate_reference(ref, require_evaluation=True)


def _format_binding_key(scope, selector, param_name):
  min_selector = _REGISTRY.minimal_selector(selector)
  return f"{scope}{'/' if scope else ''}{min_selector}.{param_name}"


@register_finalize_hook
def find_unknown_references_hook(config):
  """Hook to find/raise errors for references to unknown configurables."""
  additional_msg_fmt = " In binding for '{}'."
  for (scope, selector), param_bindings in config.items():
    for param_name, param_value in param_bindings.items():
      for maybe_unknown in _iterate_flattened_values(param_value):
        if isinstance(maybe_unknown, _UnknownConfigurableReference):
          binding_key = _format_binding_key(scope, selector, param_name)
          additional_msg = additional_msg_fmt.format(binding_key)
          _raise_unknown_reference_error(maybe_unknown, additional_msg)


@register_finalize_hook
def find_missing_overrides_hook(config):
  """Hook to find/raise errors for config bindings marked REQUIRED."""
  for (scope, selector), param_bindings in config.items():
    for param_name, param_value in param_bindings.items():
      if isinstance(param_value, ConfigurableReference):
        if param_value.configurable.wrapped == _retrieve_constant:  # pylint: disable=comparison-with-callable
          # Call the scoped _retrieve_constant() to get the constant value.
          constant_value = param_value.scoped_configurable_fn()
          if constant_value is REQUIRED:
            binding_key = _format_binding_key(scope, selector, param_name)
            fmt = '{} set to `%gin.REQUIRED` but not subsequently overridden.'
            raise ValueError(fmt.format(binding_key))


def markdown(string):
  """Convert a config string to Markdown format.

  This can be useful for rendering the config string (or operative config
  string) in dashboards that support Markdown format. Comments in the config
  string are left as Markdown headers; other lines are indented by four spaces
  to indicate they are code blocks.

  Args:
    string: The configuration string to convert to Markdown format. This should
      be the output of `gin.config_str()` or `gin.operative_config_str()`.

  Returns:
    The given configuration string in a Markdown-compatible format.
  """

  def process(line):
    """Convert a single line to markdown format."""
    if not line.startswith('#'):
      return '    ' + line

    line = line[2:]
    if line.startswith('===='):
      return ''
    if line.startswith('None'):
      return '    # None.'
    if line.endswith(':'):
      return '#### ' + line
    return line

  output_lines = []
  for line in string.splitlines():
    procd_line = process(line)
    if procd_line is not None:
      output_lines.append(procd_line)

  return '\n'.join(output_lines)
