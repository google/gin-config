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

"""Defines a generic `partial` that works for both classes and functions."""

import functools
import inspect

from typing import Any, Callable, Type


def _make_meta_call_wrapper(cls: Type[object]):
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
  def meta_call_wrapper(new_cls: Type[object], *args, **kwargs):
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


def partialclass(cls, *args, **kwargs):
  """Creates a class with partially-specified parameters.

  This class should generally behave interchangeably with `cls` in most
  settings. The method used here is to create a dynamic subclass of `cls`, with
  a metaclass which is itself a dynamic subclass of `cls`'s metaclass. This
  metaclass supplies partial parameters to `cls` during instance creation, with
  that result that constructing a `partial_cls` yields actual instances of
  `cls`.

  The returned `partial_cls` will have the following properties:

    - `issubclass(partial_cls, cls) == True`
    - `issubclass(cls, partial_cls) == False`
    - `isinstance(partial_cls, type(cls)) == True`
    - `type(partial_cls(...)) == cls`

  Args:
    cls: The class to partially specify parameters for.
    *args: Positional parameters to provide when constructing `cls`.
    **kwargs: Keyword arguments to provide when constructing `cls`.

  Returns:
    A dynamic subclass of `cls`, with parameters partially specified.
  """
  cls_meta = type(cls)
  meta_call = _make_meta_call_wrapper(cls)  # See this for more details.
  # Construct a new metaclass, subclassing the one from `cls`, supplying our
  # decorated `__call__`. Most often this is just subclassing Python's `type`,
  # but when `cls` has a custom metaclass set, this ensures that it will
  # continue to work properly.
  decorating_meta = type(cls_meta)(cls_meta.__name__, (cls_meta,), {
      '__call__': functools.partialmethod(meta_call, *args, **kwargs),
  })
  # Now we construct our class. This is a subclass of `cls`, but only with
  # wrapper-related overrides, since currying parameters is all handled via the
  # metaclass's `__call__` method. Note that we let '__annotations__' simply get
  # forwarded to the base class, since creating a new type doesn't set this
  # attribute by default.
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
  # Finally, create the partial class using the metaclass created above.
  return decorating_meta(cls.__name__, (cls,), overrides)


def partial(fn_or_cls: Callable[..., Any], *args, **kwargs):
  if inspect.isclass(fn_or_cls):
    return partialclass(fn_or_cls, *args, **kwargs)
  else:
    return functools.partial(fn_or_cls, *args, **kwargs)
