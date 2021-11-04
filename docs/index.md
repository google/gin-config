# Gin Config


**Authors**: Dan Holtmann-Rice, Sergio Guadarrama, Nathan Silberman
**Contributors**: Oscar Ramirez, Marek Fiser

<!---->

Gin provides a lightweight, dependency injection driven approach to specifying
and configuring hyperparameters.

#### Table of Contents

[TOC]

## Motivation

Modern ML experiments require configuring a dizzying array of hyperparameters,
ranging from small details like learning rates or thresholds all the way to
parameters affecting the model architecture.

Many choices for representing such configuration (proto buffers, tf.HParams,
ParameterContainer, ConfigDict) require that model and experiment parameters are
duplicated: at least once in the code where they are defined and used, and again
when declaring the set of configurable hyperparameters.

Gin provides a lightweight dependency injection driven approach to configuring
experiments in a reliable and transparent fashion. It allows functions or
classes to be annotated as `@gin.configurable`, which enables setting their
parameters via a simple config file using a clear and powerful syntax. This
approach reduces configuration maintenance, while making experiment
configuration transparent and easily repeatable.

## Registering functions and classes with Gin

### Using `@gin.configurable`

Any function or class can be marked configurable using the `@gin.configurable`
decorator:

```python
@gin.configurable
def my_network(images, num_outputs, num_layers=3, weight_decay=1e-4):
  ...
```

The `@gin.configurable` decorator does three things:

1.  It associates a "configurable name" with the function or class (by default,
    just the function or class name).
2.  It determines which parameters of the function or class constructor are
    configurable (by default, all of them).
3.  It wraps the function or class, intercepting calls and supplying the
    function's configurable parameters with values from a global registry of
    parameter settings (for parameters not already supplied by the function's
    caller).

To determine which parameters are configurable, `@gin.configurable` takes an
`allowlist` or a `denylist` parameter. If some parameters are allowlisted the
others would be denylisted and vice versa. For instance, in the example above,
allowlisting `num_layers` and `weight_decay` would imply that `images` and
`num_outputs` are denylisted. Since configuring the `images` parameter doesn't
make much sense, it would be best to denylist that parameter. Additionally, we
could specify a different name for the configurable object than "my_network":

```python
@gin.configurable('supernet', denylist=['images'])
def my_network(images, num_outputs, num_layers=3, weight_decay=1e-4):
  ...
```

In case of collisions, configurable names can be disambiguated by
[specifying the module](#handling-naming-collisions-with-modules) of the
intended configurable.

Note: Gin-configurable functions are not pickleable.

### Using `gin.register`

Gin additionally provides `gin.register`, which can be used either as a
decorator or standalone function to register classes and functions with Gin. It
has the same signature as `gin.configurable`, but performs "pure" registration,
returning the original class or function unaltered (while storing a
"configurable" version of the class in Gin's internal registry). This means that
calls in Python to the class or function do not receive any parameters bound by
Gin. Instead, the configurable version of the class can only be referenced
within Gin files using [configurable references](#configurable-references) (see
below for more details).

As a general rule, in order to remain transparent to other Python code and to
make it easier to reason about where Gin parameter "injection" takes place
within a codebase, it is recommended to annotate most classes and functions with
`@gin.register`, reserving a single `@gin.configurable` annotation for a "root"
injection site.

### Registering class methods

In some cases, it may be desirable to also register class methods with Gin. Gin
permits use of `gin.register` on class methods. If the class itself is also
registered, any instances of the class will have registered methods replaced by
their configurable versions, such that Gin bindings will apply. Additionally, at
upon class registration, registered methods will have their module set to match
that of the class, appended with the class name. Any [scopes](#scoping) applied
to a class instance will also be applied for any registered methods called on
that instance.

For example:

```python
@gin.register
class LanguageGenerator:

  def __init__(self, network):
    ...

  @gin.register
  def sample(self, temperature=0.0):
    ...
```

Once `LanguageGenerator` has been registered, the `temperature` parameter of the
`sample` method can have its parameters [bound](binding-parameters-to-values)
within a Gin file via (for example)
`generators.LanguageGenerator.sample.temperature = 1.0` (or simply
`LanguageGenerator.sample.temperature = 1.0`).

## Binding parameters to values

Once a function has been marked as configurable, parameter values can be bound
programmatically using `gin.bind_parameter`, or supplied through a configuration
string to `gin.parse_config` (generally more convenient). Programmatic binding
uses the following syntax:

```
gin.bind_parameter('configurable_name.parameter_name', value)
```

Here `configurable_name` refers to the registered configurable name (determined
by `@gin.configurable`), `parameter_name` refers to the name of the function or
constructor argument that should be set. For example, we might configure our
network above:

```
gin.bind_parameter('supernet.num_layers', 5)
gin.bind_parameter('supernet.weight_decay', 1e-3)
```

The `parse_config` function accepts configuration strings, which should consist
of newline-separated statements of the form

```
configurable_name.parameter_name = value
```

Here `value` can be any valid Python literal value (lists, tuples, dicts,
strings, etc., although note [configurable references](#configurable-references)
below). A valid configuration string for the above network might be:

```
supernet.num_layers = 5
supernet.weight_decay = 1e-3
```

Gin's configuration syntax supports Python-style comments and line continuation
(using '`\ `' or within a container), and in general parsing of values should
behave as in Python. Arithmetic expressions are not supported.

Once `gin.parse_config` has been called, any supplied bindings will be used in
all future calls to configurable functions or classes. In cases where a
parameter is both given as a binding and explicitly supplied by a configurable
function's caller, the caller's value will take precedence. In particular, note
that this means that when multiple classes in a class hierarchy are made
configurable, Gin bindings applied to a base class's parameters will generally
be ignored when constructing a subclass if the subclass passes these parameters
to the base class's constructor.

### Querying bound parameters

Configurable parameters can be queried using `gin.query_parameter`. The query
syntax is similar to the one used by `gin.bind_parameter` above. Note that a
`ValueError` exception will be raised if there is no value bound to the
parameter being queried.

```
num_layers = gin.query_parameter('supernet.num_layers')
weight_decay = gin.query_parameter('supernet.weight_decay')
```

### Configurable references

In addition to Python values, Gin recognizes any value starting with '`@`' (even
when nested inside a container) as a reference to another configurable function
or class. Consider the following code:

```python
@gin.configurable
class DNN(object):
  def __init__(self, num_units=(1024, 1024)):
    ...
  def __call__(inputs, num_outputs):
    ...

@gin.configurable(denylist=['data'])
def train_model(network_fn, data, learning_rate, optimizer):
  ...
```

We might configure this code in the Gin file as follows:

```
train_model.network_fn = @DNN()  # An instance of DNN is passed.
train_model.optimizer = @MomentumOptimizer  # The class itself is passed.
train_model.learning_rate = 0.001

DNN.num_units = (2048, 2048, 2048)
MomentumOptimizer.momentum = 0.9
```

The above example demonstrates Gin's two flavors of configurable references.
Because the `@DNN()` reference ends in `()`, the value supplied to
`train_model`'s `network_fn` parameter will be the result of calling the
configurable named `DNN` (in this case that means constructing the `DNN` class).
This call happens *just before* the result is passed to `train_model`

The `@MomentumOptimizer` reference lacks `()`, so the bare (uncalled)
configurable object (the `MomentumOptimizer` class) is passed to `train_model`'s
`optimizer` parameter. The `train_model` function will then be responsible for
calling the object.

**Note:** Evaluated configurable references (those ending in `()`) will be
called *every time* their result is required as the value of another
configurable parameter. In the above example, a new instance of `DNN` will be
created for every call to `train_model`. To cache the result of evaluating a
configurable reference (e.g., to share an instance of a class among multiple
bindings), see [singletons](#singletons).

## Making existing classes or functions configurable

Existing classes or functions that can't be explicitly annotated (maybe they're
in another project) can be made configurable via the `gin.external_configurable`
function. For example:

```python
gin.external_configurable(tf.train.MomentumOptimizer)
```

registers TensorFlow's `MomentumOptimizer` class with Gin, making it possible to
reference it from configuration files and specify its parameters (as in the
above example).

Gin provides a
[`tf.external_configurables` module](#importing-the-predefined-set-of-tf-configurable-objects)
that can be imported to register a
[default set](https://github.com/google/gin-config/tree/master/gin//tf/external_configurables.py)
of TensorFlow optimizers, losses, and learning rate decays with Gin.

(Note that `gin.external_configurable` does not modify the existing class or
function, so only calls resulting from references to the configurable name in
configuration strings, or calls to the return value of
`gin.external_configurable`, will have parameter bindings applied. Direct calls
will remain unaffected.)

## Handling naming collisions with modules

If two configurable functions or classes with the same name are marked
`@configurable`, it isn't possible to bind parameters to them using only their
configurable names (this would be ambiguous). Instead, a configurable's module
can be used to disambiguate it, by prepending as much of the module as is
necessary to uniquely identify the configurable. For instance, if
`some_configurable` is present in both module `a.b.c.configurables` and module
`x.y.z.configurables`, we can bind parameters to the one in
`a.b.c.configurables` in the following ways:

```
c.configurables.some_configurable.param = 'value'
b.c.configurables.some_configurable.param = 'value'
a.b.c.configurables.some_configurable.param = 'value'
```

This syntax is supported wherever a configurable name can be supplied (so
configurables can be disambiguated in a similar way when using
[configurable references](#configurable-references)).

Just as a configurable name can be customized relative to the underlying
function's name, the module used to disambiguate a configurable can also be
different from the module the configurable function is actually defined in. Both
`gin.configurable` and `gin.external_configurable` accept a `module` keyword
argument to specify the module Gin should use for disambiguation. For example:

```
@gin.configurable(module='custom.module.spec')
def my_network(images, num_outputs, num_layers=3, weight_decay=1e-4):
  ...
```

Alternatively, if both the name and module are being customized, the module can
be specified as part of the name. For example, to call the above `'supernet'`
instead of `'my_network'`:

```
@gin.configurable('custom.module.spec.supernet')
def my_network(images, num_outputs, num_layers=3, weight_decay=1e-4):
  ...
```

Users are encouraged to specify a custom module in cases where the true module
name is not obvious from how the function is typically used. The custom module
should match typical Python usage. For example, the TensorFlow function
`tf.nn.relu` is defined in the module 'tensorflow.python.ops.gen_nn_ops'. It
would be better to specify an explicit module of `'tf.nn'`, in one of the
following ways:

```
gin.external_configurable(tf.nn.relu, module='tf.nn')
gin.external_configurable(tf.nn.relu, 'tf.nn.relu')
```

## Scoping

When a configurable function is called more than once during program execution,
it may be necessary to provide different parameter bindings for each invocation.
Gin provides a scoping mechanism to facilitate this.

As an example, suppose we want to implement a GAN, where we must alternate
training a generator and a discriminator. In TensorFlow, this is most easily
achieved with two optimizers, so we might have a function like:

```python
gin.external_configurable(tf.train.GradientDescentOptimizer)

@gin.configurable(allowlist=['generator_optimizer', 'discriminator_optimizer'])
def gan_trainer(
    generator_loss, generator_vars, generator_optimizer,
    discriminator_loss, discriminator_vars, discriminator_optimizer):
  # Construct the optimizers and minimize w.r.t. the correct variables.
  generator_train_op = generator_optimizer().minimize(
      generator_loss, generator_vars)
  discriminator_train_op = discriminator_optimizer().minimize(
      discriminator_loss, discriminator_vars)
  ...
```

How could we configure `generator_optimizer` and `discriminator_optimizer` to
both be `@GradientDescentOptimizer`, but with different learning rates? The
following __will not work__:

```
# Won't work!
gan_trainer.generator_optimizer = @GradientDescentOptimizer
GradientDescentOptimizer.learning_rate = 0.01

gan_trainer.discriminator_optimizer = @GradientDescentOptimizer
# This binding will overwrite the previous one:
GradientDescentOptimizer.learning_rate = 0.001
```

In the above configuration, both optimizers will have their learning rates set
to `0.001`, since the second parameter binding for
`GradientDescentOptimizer.learning_rate` overrides the first.

Gin provides a scoping mechanism to handle this situation. Any configurable
reference can be preceded by a scope name, separated from the configurable name
by a `/` character. Similarly, bindings can be applied that are specific to a
scope, once again by preceding the configurable name by a scope name. For the
above example, we could write:

```
# This will work! Use scoping to apply different parameter bindings.
gan_trainer.generator_optimizer = @generator/GradientDescentOptimizer
gan_trainer.discriminator_optimizer = @discriminator/GradientDescentOptimizer

generator/GradientDescentOptimizer.learning_rate = 0.01
discriminator/GradientDescentOptimizer.learning_rate = 0.001
```

Here, we have used two scope names, `generator` and `discriminator`, to provide
separate parameter bindings for the two instances of `GradientDescentOptimizer`.

### Nesting scopes

Parameters set on the root scope (no explicit scope supplied) are inherited by
all scoped versions of the configurable (unless overridden within the scope).
For example:

```python
preprocess_images.crop_size = [64, 64]
preprocess_images.normalize_image = True
preprocess_images.random_flip_lr = False

train/preprocess_images.crop_location = 'random'
train/preprocess_images.random_flip_lr = True

eval/preprocess_images.crop_location = 'center'
```

The `crop_size` and `normalize_image` parameters above will be shared in both
the `train` and `eval` scopes; `train` will receive `random_flip_lr = True`,
while `eval` inherits the setting of `False` from the root scope; the
`crop_location` setting will be `'random'` in the `train` scope and `'center'`
in the `eval` scope.

Scopes can be nested (to arbitrary depth), and parameters bound at higher levels
are inherited by lower levels, so e.g. parameters bound in a hypothetical
`eval/train_data` scope would override those bound in `eval` (which override
bindings in the root scope).

While nesting of scopes is supported there is some ongoing debate around their
ordering and behavior, so try to avoid relying on the ordering.

### Explicit scopes

In addition to the "implicit" scopes described above (where the scope is
specified and referenced entirely from within the Gin config file), a call site
can be wrapped with an "explicit" configuration scope, using the `config_scope`
context manager:

```
with gin.config_scope('scope_name'):
  some_configurable_function()
```

Within the configuration file, the scope name can be prefixed as before to bind
values only to a specific call site (in the above example, it suffices to
provide bindings for `scope_name/some_configurable_function`).

Passing `None` or `''` to `config_scope` will temporarily clear all currently
active scopes (within the `with` block; they will be restored afterwards).

### Accessing the current scope within a function

When adding "features" to Gin, it is often useful to use the current scope as an
identifier. For example, under the hood Gin's implementation of constants uses a
`constant` configurable that looks up values in a Gin-internal dictionary
depending on the scope in which it is called. A string representation of the
current Gin scope is available via the `current_scope_str` function.

## Marking parameters as `gin.REQUIRED`

Gin allows you to indicate that certain parameters __must__ be provided in a Gin
config. This can be done in two ways:

1.  At the call site of a function;
2.  In a function's signature.

When calling a configurable, you can mark any arg or kwarg as required by
passing the `gin.REQUIRED` object:

```
my_network(images, gin.REQUIRED, num_layers=5, weight_decay=gin.REQUIRED)
```

The `REQUIRED` parameters will be checked at call time. If there are no Gin
bindings supplied for these parameters, an error will be raised listing the
missing parameter bindings along with the configurable name that requires them.

When defining a configurable, you can mark an argument as required by using
`gin.REQUIRED` as its default value:

```
@gin.configurable
def run_training(model_dir=gin.REQUIRED, network=gin.REQUIRED, ...):
  ...
```

When a function with parameters defaulting to `gin.REQUIRED` is called, either
the caller or the current Gin configuration must supply a value for the
parameter, or an error will be raised.

Providing `gin.REQUIRED` at the call site of a function is strictly more
flexible than providing it in the signature (if the function is called more than
once), avoids altering the function's signature in a Gin-dependent way, and may
yield more readable code, so this approach should generally be preferred.

## Importing modules from within a Gin file

Most Gin files will depend on a number of modules having been imported (to
register the configurable functions they provide with Gin). One approach is just
to ensure that these modules are imported in the main binary file (often the
same file that calls `parse_config`). However, Gin also allows modules to be
imported from within a Gin file itself, making the dependencies more explicit.
The import statement follows standard Python syntax:

```
import some.module.spec
```

When the Gin file is parsed, any specified modules will be dynamically imported
and their configurables registered.


## Including other Gin files

One Gin file can include other Gin files, to make it easier to split a config
into separate components (e.g., a "base" config, that is included and modified
by other derived configs). Including another Gin file can be done with the
following syntax:

```
include 'path/to/another/file.gin'
```

The included file will be read and parsed prior to continuing with the current
file (the one containing the include statement), as if the included file had
been literally "pasted" at the location of the include statement.

## Finalizing the config

Once all configuration has been finished (parsing of config files or calls to
`gin.bind_parameter`), the config can be locked to prevent further modification
by calling `gin.finalize()`. (If necessary, the config can be temporarily
unlocked using the `gin.unlock_config()` context manager.) Gin also allows
inspection and validation (and potentially a final modification) of the config
through "finalize hooks", which run when `gin.finalize` is called.

## Gin "macros"

Sometimes a value should be shared among multiple bindings. To facilitate this
and avoid duplicating the value multiple times (leading to maintenance burdens),
Gin provides the following predefined configurable function:

```python
@gin.configurable
def macro(value):
  return value
```

The macro can be "set" by binding a value to the `value` argument (within a
scope acting as the macro's name). The "macro" function can then be referenced
(with evaluation via "()") to retrieve the value. For example:

```
num_layers/macro.value = 10
network.num_layers = @num_layers/macro()
```

Gin provides a simple syntactic sugar using `%` for macros. The above can also
be written as:

```
num_layers = 10
network.num_layers = %num_layers
```

In other words, bindings without an argument name specified (i.e. without `.`)
are interpreted as macros, and the macro can be referenced using `%` instead of
`@` without needing to ever reference the `macro` function directly.

Additional error-checking of macros (e.g., ensuring they are bound to a value)
can be done by calling `gin.finalize()` after all configuration files have been
parsed. This runs a provided [finalize hook](#finalizing-the-config) that
validates all macros.

Note: When using a macro to refer to an evaluated configurable reference
(`@some_scope/some_fun()`), _each reference to the macro implies a separate call
to the underlying configurable_ (the behavior is as if each macro were textually
replaced by whatever the macro's value is set to). If you need the same
**instance** of an object to be shared among multiple bindings, see
[singletons](#singletons) below.

As with all other Gin bindings, the very last binding (across all parsed Gin
files) that provides a value for a function's argument is used for _all_
references to that function; i.e., the relative ordering between bindings to
`macro` and references to `macro` doesn't matter; the last binding is always
used.

### Singletons

A single instance of an object can be shared among multiple bindings using the
`singleton` configurable function. For example:

```
shared_object_name/gin.singleton.constructor = @callable

some_function.shared_object = @shared_object_name/gin.singleton()
another_function.shared_object = @shared_object_name/gin.singleton()
```

In the above example, the scope ("shared_object_name") is used as an identifier
for the singleton; the first time the `@shared_object_name/gin.singleton()` is
called, it will in turn call `callable` and cache the result. Subsequent calls
to `@shared_object_name/gin.singleton()` will reuse the cached value. This can
be used with macros:

```
SHARED_OBJECT = @shared_object_name/gin.singleton()
shared_object_name/gin.singleton.constructor = @callable

some_function.shared_object = %SHARED_OBJECT
another_function.shared_object = %SHARED_OBJECT
```

### Constants

The `gin.constant` function can be used to define constants that will be
accessible through the macro syntax described above. For example, in Python:

```
gin.constant('THE_ANSWER', 42)
```

Then, in a Gin config file:

```
meaning.of_life = %THE_ANSWER
```

Note that any Python object can be used as the value of a constant (including
objects not representable as Gin literals). Values will be stored until program
termination in a Gin-internal dictionary, so avoid creating constants with
values that should have a limited lifetime.

Optionally (but definitely encouraged), a disambiguating module may be prefixed
onto the constant name. For instance:

```
  gin.constant('some.modules.PI', 3.14159)
```

As with configurables, any (sufficiently long) suffix of the modules can be used
to disambiguate the constant if there is a naming collision.

#### Using enums as constants

It is not possible to directly use Python enums in Gin config files. However,
there is a decorator `@gin.constants_from_enum` that generates Gin constants
from a class that derives from `Enum`. Generated constants are in format
`module.EnumClassName.ENUM_VALUE`. The module part of the name is optional.

For example, in `my_code.py`:

```python
@gin.constants_from_enum
class SomeEnum(enum.Enum):
  A = 0
  B = 1

@gin.configurable
def my_function(x, y):
  print(x)
  print(y)
```

Then, in `my_config.gin` file:

```
import my_code

my_function.x = %SomeEnum.A
my_function.y = %my_code.SomeEnum.B
```

## Retrieving "operative" parameter values

A binary may include many configurable functions (different network
architectures, optimizers, etc.), but only a subset are generally called during
a given execution. The parameter values of functions in this subset form the
"operative" configuration—the set of parameter values affecting the current
program's execution.

Gin provides the `gin.operative_config_str` function, which can be called to
retrieve the operative configuration as a string parseable by
`gin.parse_config`. This serves as a snapshot of relevant parameter values for a
given program execution, and contains all configurable parameter values from
invoked configurable functions, including those functions' default argument
values (if those arguments could be configured in accordance with the functions'
allowlists and denylists). It also includes `import` statements for any modules
dynamically imported via a config file. It excludes any parameters supplied by a
configurable function's caller, since configuring such parameters has no effect
(the caller's value always takes precedence).

The output will be organized alphabetically by configurable name. For example,
it might look like:

```
# Parameters for AdamOptimizer:
# ==============================================================================
AdamOptimizer.beta1 = 0.9
AdamOptimizer.beta2 = 0.999
AdamOptimizer.epsilon = 0.001
AdamOptimizer.name = 'Adam'
AdamOptimizer.use_locking = False

# Parameters for exponential_decay:
# ==============================================================================
exponential_decay.learning_rate = 0.001
exponential_decay.decay_steps = 72926
exponential_decay.decay_rate = 0.92

# Parameters for NetworkTrainer:
# ==============================================================================
NetworkTrainer.dataset = @ImageNetDataset
NetworkTrainer.learning_rate = @exponential_decay
NetworkTrainer.network_fn = @inception_v3
NetworkTrainer.optimizer = @AdamOptimizer
NetworkTrainer.train_steps = 1000000

...
```

When used in conjunction with TensorFlow, Gin provides
[`gin.tf.GinConfigSaverHook`](#saving-gins-operative-config-to-a-file-and-tensorboard)
to automatically save this to a file (as well as summarize it to TensorBoard).

## Experiments with multiple Gin files and extra command line bindings

In many cases one can define multiple Gin files that contain different parts of
the overall configuration of an experiment. Additional "tweaks" to the overall
config can be passed as individual bindings via command line flags.

A recommended way to do this (when using Bazel and Abseil) is to create a folder
with multiple Gin configs, then create a BUILD file containing:

```
filegroup(
    name = "gin_files",
    srcs = glob(["*.gin"]),
    visibility = [":internal"],
)
```

This filegroup can be used as a data dependency in the binaries:

```
data = ["//path/to/configs:gin_files",]
```

In the binary file, one can define the following flags:

```
from absl import flags

flags.DEFINE_multi_string(
  'gin_file', None, 'List of paths to the config files.')
flags.DEFINE_multi_string(
  'gin_param', None, 'Newline separated list of Gin parameter bindings.')

FLAGS = flags.FLAGS
```

and then use Gin to parse them:

```
gin.parse_config_files_and_bindings(FLAGS.gin_file, FLAGS.gin_param)
```

Finally the binary file can be run as:

```
.../run_gin_eval \
  --gin_file=$CONFIGS_PATH/cartpole_balance.gin \
  --gin_file=$CONFIGS_PATH/base_dqn.gin \
  --gin_file=$CONFIGS_PATH/eval.gin \
  --gin_param='evaluate.num_episodes_eval = 10' \
  --gin_param='evaluate.generate_videos = False' \
  --gin_param='evaluate.eval_interval_secs = 60'
```

## Gin's `gin.tf` package: TensorFlow specific functionality

The core of Gin is not specific to TensorFlow (and could be used to configure
any Python program). However, Gin provides a `tf` package with additional
TensorFlow specific functionality.


### Importing the predefined set of TF configurable objects

Since it is common to want to configure built in TF functions or class, Gin
provides a module that can be imported to make all basic TF optimizers, learning
rate decays, and losses configurable (using `gin.external_configurable`). These
can then be referenced through
[configurable references](#configurable-references) in a Gin config file. To
import the module, add

```python
import gin.tf.external_configurables
```

alongside any other modules being imported for their Gin-configurable functions
(either from Python or within a Gin file).

### Saving Gin's operative config to a file and TensorBoard

Gin provides `gin.tf.GinConfigSaverHook`: a `tf.train.SessionRunHook` that can
save the [operative configuration](#retrieving-operative-parameter-values) to a
file, as well as create a summary that will display the operative configuration
in TensorBoard's "Text" tab. The resulting hook should be added to a
`MonitoredSession`'s hooks. In distributed training mode, it should run only on
the chief. For example:

```python
# Construct the hook. (The summarize_config parameter defaults to True.)
config_saver = gin.tf.GinConfigSaverHook(output_dir, summarize_config=True)

# Pass as a chief-only hook to MonitoredTrainingSession.
with tf.train.MonitoredTrainingSession(
    ..., chief_only_hooks=[config_saver], ...) as sess:
  ...
```

Exactly where to add the hook will vary with different training frameworks
(e.g., core TensorFlow vs. TF.learn). Once the graph has been finalized and the
TF session has been created, the hook will save a file named
`operative_config-#.gin` to `output_dir`, where `#` is replaced by the current
global step. If the job is relaunched (potentially with new parameters), a new
file (presumably with a different value for the global step) will be written.

The hook will also write a summary file that logs the operative config to
TensorBoard's "Text" tab, with the name "gin/operative_config". This can be
disabled by creating the hook as `gin.tf.GinConfigSaverHook(output_dir,
summarize_config=False)`.

Note: If the training framework being used doesn't support `SessionRunHook` (for
instance, if it still uses `tf.train.Supervisor`), the `after_create_session`
method of the hook can be called explicitly. Specifically,
`hook.after_create_session(sess)` should be called once the session has been
created and initialization ops have been run. This method should only be called
by the chief worker when doing distributed training.

### TensorFlow per-graph singletons

When using Gin to configure TensorFlow pipelines, it is sometimes useful to
cache values once per TensorFlow graph instead of once globally (e.g., whenever
the constructed object creates any graph elements). Gin provides a
`singleton_per_graph` function analogous to the [`singleton`](#singletons)
function that calls the singleton's constructor whenever the default graph
changes (maintaining a cache keyed by the tuple `("shared_object_name",
graph_instance)`).

