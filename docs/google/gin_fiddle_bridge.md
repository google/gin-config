# The Gin-Fiddle Bridge

go/gin-fiddle-bridge

<!--*
# Document freshness: For more information, see go/fresh-source.
freshness: { owner: 'dhr' reviewed: '2022-05-20' }
*-->

## Overview

The Gin-Fiddle bridge aims to provide a simple way of converting an existing
Gin-based setup into a Fiddle configuration.

The bridge provides two functions `as_config` and `as_partial`, that look up the
current Gin configuration for `fn_or_cls_or_selector`, and create a
corresponding `fdl.Config` or `fdl.Partial` object.

The returned values should behave just like the Gin-configured callable when
built with `fdl.build()`. For example,
`fdl.build(gin_fiddle_bridge.as_config('some_selector'))` should return exactly
the same value as `gin.get_configurable('some_selector')()`, assuming all
required argument values have been configured and the Gin configuration does not
rely on global injection. (To ensure that no global injection of parameters
takes place, it may be desirable to call `gin.clear_config()` after calling this
function.)

## Operation

The `as_config` and `as_partial` functions return a `fdl.Buildable` derived from
the Gin configuration for a specific function or class, which may be specified
either as a literal Python function or class value (which will be looked up in
the Gin registry), or as a string which will be interpreted as a Gin selector
(optionally including a scope), for example
'optional_scope/optional_module.some_function'.

The functions then recursively create additional `fdl.Config` or `fdl.Partial`
objects for any references present in Gin's configured parameters. A
`fdl.Config` will be created and used in place of any evaluated references
(`@some_callable_value()`), while a `fdl.Partial` will be used in place of
unevaluated references (`@some_callable_value`).

Gin macros (`%SOME_MACRO`) and constants (`%maybe_module.registered_constant`)
are special cases: any encountered macro is converted into a `fdl.TaggedValue`,
using a (dynamically created) `fdl.Tag` with the same name as the macro.
Constant values are looked up and used directly.

## Preserving Gin semantics

Preserving Gin's semantics completely in a `fdl.Config` requires some special
care, and there are two main behaviors that do not translate directly from Gin
into Fiddle.

### Reevaluating `Config`s inside `Partial`s

Gin injects parameters at call time, and each time a Gin-configured function is
called, any evaluated references in its configured parameters are re-evaluated.
By contrast, Fiddle will evaluate a given `fdl.Config` exactly once during
`fdl.build`. If that `fdl.Config` is a parameter of a `fdl.Partial`, and after
`fdl.build` the resulting `functools.partial` is called multiple times, each
call will reuse the value obtained from building the `fdl.Config`:

```
partial_cfg = fdl.Partial(lambda x: x, x=fdl.Config(SomeClass))
partial_fn = fdl.build(partial_cfg)
assert partial_fn() is partial_fn()
```

To preserve the Gin behavior, by default `as_config` and `as_partial` detect
when a `fdl.Config` is contained in a parameter of a `fdl.Partial`. To implement
reevaluation, they use a special `ReevaluatedConfig` type in place of the
`fdl.Config`, and a `PartialWithReevaluations` type for the `fdl.Partial`. When
built, the `ReevaluatedConfig` produces a special `Reevaluated` class containing
a callable to reevaluate; when the `PartialWithReevaluations` is built, it
decorates its function or class to scan arguments for `Reevaluated` instances
and wraps the decorated version in a `functools.partial`.

If it is known that a given Gin configuration doesn't rely on this reevaluation
behavior (for example because any partials are only called at most once), it can
be disabled by setting `reevaluate_configs_inside_partials` to `False`.

#### Tracking Reevaluations

To help verify whether reevaluating `fdl.Config`s inside `fdl.Partial`s is
necessary for a given config, the Gin-Fiddle bridge provides a
`reevaluation_tracker` context manager, which can log how many times
reevaluation occurs within a given block of code:

```py
train_partial = gin_fiddle_bridge.as_partial()  # Or as_config()
gin.clear_config()  # Best practice, not strictly necessary.
with gin_fiddle_bridge.reevaluation_tracker() as reevaluated_calls:
  train_fn = fdl.build(train_partial)
  train_fn()

# Inspect reevaluated_calls... for example:
print(reevaluated_calls)
if any([len(calls) <= 1 for calls in reevaluated_calls.values()]):
  print('No `Reevaluated` instances were called multiple times!')
```

In general, both the `fdl.build()` call and and subsequent calls to resulting
`functools.partial` objects should be inside the context manager.

Note that just because reevaluation doesn't happen for a given configuration
doesn't necessarily mean another configuration of the same codebase won't
require it; concluding that reevaluation is never needed requires an
understanding of the overall code structure, but this tracker can help serve as
additional validation.

### Using partial classes

Fiddle has no separate representation for partial classes, and for simplicity
uses `functools.partial` for both functions and classes:

```py
assert isinstance(fdl.build(fdl.Partial(SomeClass)), functools.partial)
```

Gin, however, attempts to allow partial classes (i.e., unevaluated references to
a class such as `@SomeClass`) to pass (some) type checks. To accomplish this,
Gin decorates the configured class via a dynamic subclassing approach, allowing
`issubclass(partial_class, SomeClass)` to work. It is rare to require this
behavior, but to preserve compatibility `as_config` allows using a
`PartialClass` subclass of `fdl.Partial` for classes that employs a similar
dynamic subclassing approach. By default, this behavior is disabled. It can be
enabled by setting `use_partial_classes` to `True`.

## Limitations

Only Gin configurations which do not rely on global injection can be converted
via this function. A Gin configuration relies on global injection when
`@gin.configurable`-decorated functions that have parameters configured are
called directly from within Python code, as opposed to via a reference inside
the Gin configuration. In other words, for `as_config` to capture the full
configuration, the Gin configuration for the function/class it is applied to
must depend on Gin parameters for other functions and classes only through an
explicit chain of references (`@some_callable`) in the configuration.
