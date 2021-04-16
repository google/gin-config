# Gin Config


**Authors**: Dan Holtmann-Rice, Sergio Guadarrama, Nathan Silberman
**Contributors**: Oscar Ramirez, Marek Fiser

<!---->

Gin provides a lightweight configuration framework for Python, based on
dependency injection. Functions or classes can be decorated with
`@gin.configurable`, allowing default parameter values to be supplied from a
config file (or passed via the command line) using a simple but powerful syntax.
This removes the need to define and maintain configuration objects (e.g.
protos), or write boilerplate parameter plumbing and factory code, while often
dramatically expanding a project's flexibility and configurability.

Gin is particularly well suited for machine learning experiments (e.g. using
TensorFlow), which tend to have many parameters, often nested in complex ways.

This is not an official Google product.

## Table of Contents

[TOC]

## Basic usage

This section provides a high-level overview of Gin's main features, ordered
roughly from "basic" to "advanced". More details on these and other features can
be found in the [user guide].

[user guide]: https://github.com/google/gin-config/tree/master/docs/index.md

### 1. Setup


Install Gin with pip:

```shell
pip install gin-config
```

Install Gin from source:

```shell
git clone https://github.com/google/gin-config
cd gin-config
python -m setup.py install
```

Import Gin (without TensorFlow functionality):

```python
import gin
```

Import additional TensorFlow-specific functionality via the `gin.tf` module:

```python
import gin.tf
```

Import additional PyTorch-specific functionality via the `gin.torch` module:

```python
import gin.torch
```


### 2. Configuring default values with Gin (`@gin.configurable` and "bindings")

At its most basic, Gin can be seen as a way of providing or changing default
values for function or constructor parameters. To make a function's parameters
"configurable", Gin provides the `gin.configurable` decorator:

```python
@gin.configurable
def dnn(inputs,
        num_outputs,
        layer_sizes=(512, 512),
        activation_fn=tf.nn.relu):
  ...
```

This decorator registers the `dnn` function with Gin, and automatically makes
all of its parameters configurable. To set ("bind") a value for the
`layer_sizes` parameter above within a ".gin" configuration file:

```python
# Inside "config.gin"
dnn.layer_sizes = (1024, 512, 128)
```

Bindings have syntax `function_name.parameter_name = value`. All Python literal
values are supported as `value` (numbers, strings, lists, tuples, dicts). Once
the config file has been parsed by Gin, any future calls to `dnn` will use the
Gin-specified value for `layer_sizes` (unless a value is explicitly provided by
the caller).

Classes can also be marked as configurable, in which case the configuration
applies to constructor parameters:

```python
@gin.configurable
class DNN(object):
  # Constructor parameters become configurable.
  def __init__(self,
               num_outputs,
               layer_sizes=(512, 512),
               activation_fn=tf.nn.relu):
    ...

  def __call__(inputs):
    ...
```

Within a config file, the class name is used when binding values to constructor
parameters:

```python
# Inside "config.gin"
DNN.layer_sizes = (1024, 512, 128)
```

Finally, after defining or importing all configurable classes or functions,
parse your config file to bind your configurations (to also permit multiple
config files and command line overrides, see
[`gin.parse_config_files_and_bindings`][multiple files]):

```python
gin.parse_config_file('config.gin')
```

Note that no other changes are required to the Python code, beyond adding the
`gin.configurable` decorator and a call to one of Gin's parsing functions.

[multiple files]: https://github.com/google/gin-config/tree/master/docs/index.md#experiments-with-multiple-gin-files-and-extra-command-line-bindings

### 3. Passing functions, classes, and instances ("configurable references")

In addition to accepting Python literal values, Gin also supports passing other
Gin-configurable functions or classes. In the example above, we might want to
change the `activation_fn` parameter. If we have registered, say `tf.nn.tanh`
with Gin (see [registering external functions][external configurables]), we can
pass it to `activation_fn` by referring to it as `@tanh` (or `@tf.nn.tanh`):

```python
# Inside "config.gin"
dnn.activation_fn = @tf.nn.tanh
```

Gin refers to `@name` constructs as *configurable references*. Configurable
references work for classes as well:

```python
def train_fn(..., optimizer_cls, learning_rate):
  optimizer = optimizer_cls(learning_rate)
  ...
```

Then, within a config file:

```python
# Inside "config.gin"
train_fn.optimizer_cls = @tf.train.GradientDescentOptimizer
...
```

Sometimes it is necessary to pass the result of calling a specific function or
class constructor. Gin supports "evaluating" configurable references via the
`@name()` syntax. For example, say we wanted to use the class form of `DNN` from
above (which implements `__call__` to "behave" like a function) in the following
Python code:

```python
def build_model(inputs, network_fn, ...):
  logits = network_fn(inputs)
  ...
```

We could pass an instance of the `DNN` class to the `network_fn` parameter:

```python
# Inside "config.gin"
build_model.network_fn = @DNN()
```

To use evaluated references, all of the referenced function or class's
parameters must be provided via Gin. The call to the function or constructor
takes place *just before* the call to the function to which the result is
passed, In the above example, this would be just before `build_model` is called.

The result is not cached, so a new `DNN` instance will be constructed for each
call to `build_model`.

[external configurables]: https://github.com/google/gin-config/tree/master/docs/index.md#making-existing-classes-or-functions-configurable

### 4. Configuring the same function in different ways ("scopes")

What happens if we want to configure the same function in different ways? For
instance, imagine we're building a GAN, where we might have a "generator"
network and a "discriminator" network. We'd like to use the `dnn` function above
to construct both, but with different parameters:

```python
def build_model(inputs, generator_network_fn, discriminator_network_fn, ...):
  ...
```

To handle this case, Gin provides "scopes", which provide a name for a specific
set of bindings for a given function or class. In both bindings and references,
the "scope name" precedes the function name, separated by a "`/`" (i.e.,
`scope_name/function_name`):

```python
# Inside "config.gin"
build_model.generator_network_fn = @generator/dnn
build_model.discriminator_network_fn = @discriminator/dnn

generator/dnn.layer_sizes = (128, 256)
generator/dnn.num_outputs = 784

discriminator/dnn.layer_sizes = (512, 256)
discriminator/dnn.num_outputs = 1

dnn.activation_fn = @tf.nn.tanh
```

In this example, the generator network has increasing layer widths and 784
outputs, while the discriminator network has decreasing layer widths and 1
output.

Any parameters set on the "root" (unscoped) function name are inherited by
scoped variants (unless explicitly overridden), so in the above example both the
generator and the discriminator use the `tf.nn.tanh` activation function.

### 5. Full hierarchical configuration {#full-hierarchical}

The greatest degree of flexibility and configurability in a project is achieved
by writing small modular functions and "wiring them up" hierarchically via
(possibly scoped) references. For example, this code sketches a generic training
setup that could be used with the `tf.estimator.Estimator` API:

```python
@gin.configurable
def build_model_fn(network_fn, loss_fn, optimize_loss_fn):
  def model_fn(features, labels):
    logits = network_fn(features)
    loss = loss_fn(labels, logits)
    train_op = optimize_loss_fn(loss)
    ...
  return model_fn

@gin.configurable
def optimize_loss(loss, optimizer_cls, learning_rate):
  optimizer = optimizer_cls(learning_rate)
  return optimizer.minimize(loss)

@gin.configurable
def input_fn(file_pattern, batch_size, ...):
  ...

@gin.configurable
def run_training(train_input_fn, eval_input_fn, estimator, steps=1000):
  estimator.train(train_input_fn, steps=steps)
  estimator.evaluate(eval_input_fn)
  ...
```

In conjunction with suitable [external configurables] to register TensorFlow
functions/classes (e.g., `Estimator` and various optimizers), this could be
configured as follows:

```python
# Inside "config.gin"
run_training.train_input_fn = @train/input_fn
run_training.eval_input_fn = @eval/input_fn

input_fn.batch_size = 64  # Shared by both train and eval...
train/input_fn.file_pattern = ...
eval/input_fn.file_pattern = ...


run_training.estimator = @tf.estimator.Estimator()
tf.estimator.Estimator.model_fn = @build_model_fn()

build_model_fn.network_fn = @dnn
dnn.layer_sizes = (1024, 512, 256)

build_model_fn.loss_fn = @tf.losses.sparse_softmax_cross_entropy

build_model_fn.optimize_loss_fn = @optimize_loss

optimize_loss.optimizer_cls = @tf.train.MomentumOptimizer
MomentumOptimizer.momentum = 0.9

optimize_loss.learning_rate = 0.01
```

Note that it is straightforward to switch between different network functions,
optimizers, datasets, loss functions, etc. via different config files.

### 6. Additional features

Additional features described in more detail in the [user guide] include:

-   Automatic logging of all configured parameter values (the ["operative
    config"][operative config]), including [TensorBoard integration].
-   ["Macros"][macros], to specify a value used in multiple
    places within a config, as well as Python-defined constants.
-   [Module imports][imports] and [config file inclusion][includes].
-   [Disambiguation][modules] of configurable names via modules.

[operative config]: https://github.com/google/gin-config/tree/master/docs/index.md#retrieving-operative-parameter-values
[macros]: https://github.com/google/gin-config/tree/master/docs/index.md#gin-macros
[imports]: https://github.com/google/gin-config/tree/master/docs/index.md#importing-modules-from-within-a-gin-file
[includes]: https://github.com/google/gin-config/tree/master/docs/index.md#including-other-gin-files
[TensorBoard integration]: https://github.com/google/gin-config/tree/master/docs/index.md#saving-gins-operative-config-to-a-file-and-tensorboard
[modules]: https://github.com/google/gin-config/tree/master/docs/index.md#handling-naming-collisions-with-modules

## Best practices

At a high level, we recommend using the minimal feature set required to achieve
your project's desired degree of configurability. Many projects may only
require the features outlined in sections 2 or 3 above. Extreme configurability
comes at some cost to understandability, and the tradeoff should be carefully
evaluated for a given project.

Gin is still in alpha development and some corner-case behaviors may be
changed in backwards-incompatible ways. We recommend the following best
practices:

-   Minimize use of evaluated configurable references (`@name()`), especially
    when combined with macros (where the fact that the value is not cached may
    be surprising to new users).
-   Avoid nesting of scopes (i.e., `scope1/scope2/function_name`). While
    supported there is some ongoing debate around ordering and behavior.
-   When passing an unscoped reference (`@name`) as a parameter of a scoped
    function (`some_scope/fn.param`), the unscoped reference gets called in the
    scope of the function it is passed to... but don't rely on this behavior.
-   Wherever possible, prefer to use a function or class's name as its
    configurable name, instead of overriding it. In case of naming collisions,
    use module names (which are encouraged to be renamed to match common usage)
    for disambiguation.
-   In fact, to aid readability for complex config files, we gently suggest
    always including module names to help make it easier to find corresponding
    definitions in Python code.
-   When doing ["full hierarchical configuration"](#full-hierarchical), structure
    the code to minimize the number of "top-level" functions that are
    configured without themselves being passed as parameters. In other words,
    the configuration tree should have only one root.

In short, use Gin responsibly :)

## Syntax quick reference

A quick reference for syntax unique to Gin (which otherwise supports
non-control-flow Python syntax, including literal values and line
continuations). Note that where function and class names are used, these may
include a dotted module name prefix (`some.module.function_name`).

<table>
  <thead>
    <tr>
      <th>Syntax</th>
      <th>Description</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td><code>@gin.configurable</code></td>
      <td>Decorator in Python code that registers a function or class with Gin,
        wrapping/replacing it with a "configurable" version that respects Gin
        parameter overrides. A function or class annotated with
        `@gin.configurable` will have its parameters overridden by any provided
        configs even when called directly from other Python code.
      .</td>
    </tr>
    <tr>
      <td><code>@gin.register</code></td>
      <td>Decorator in Python code that only registers a function or class with
        Gin, but does *not* replace it with its "configurable" version.
        Functions or classes annotated with `@gin.register` will *not* have
        their parameters overridden by Gin configs when called directly from
        other Python code. However, any references in config strings or files to
        these functions (`@some_name` syntax, see below) will apply any provided
        configuration.
      </td>
    </tr>
    <tr>
      <td><code>name.param&nbsp;=&nbsp;value</code></td>
      <td>Basic syntax of a Gin binding. Once this is parsed, when the
      function or class named <code>name</code> is called, it will receive
      <code>value</code> as the value for <code>param</code>, unless a
      value is explicitly supplied by the caller. Any Python literal may be
      supplied as <code>value</code>.</td>
    </tr>
    <tr>
      <td><code>@some_name</code></td>
      <td>A <em>reference</em> to another function or class named
      <code>some_name</code>. This may be given as the value of a binding, to
      supply function- or class-valued parameters.</td>
    </tr>
    <tr>
      <td><code>@some_name()</code></td>
      <td>An <em>evaluated reference</em>. Instead of supplying the function
      or class directly, the result of calling <code>some_name</code> is
      passed instead. Note that the result is not cached; it is recomputed
      each time it is required.</td>
    </tr>
    <tr>
      <td><code>scope/name.param&nbsp;=&nbsp;value</code></td>
      <td>A scoped binding. The binding is only active when <code>name</code>
      is called within scope <code>scope</code>.</td>
    </tr>
    <tr>
      <td><code>@scope/some_name</code></td>
      <td>A scoped reference. When this is called, the call will be within
      scope <code>scope</code>, applying any relevant scoped bindings.</td>
    </tr>
    <tr>
      <td><code>MACRO_NAME&nbsp;=&nbsp;value</code></td>
      <td>A macro. This provides a shorthand name for the expression on the
      right hand side.</td>
    </tr>
    <tr>
      <td><code>%MACRO_NAME</code></td>
      <td>A reference to the macro <code>MACRO_NAME</code>. This has the
      effect of textually replacing <code>%MACRO_NAME</code> with whatever
      expression it was associated with. Note in particular that the result
      of evaluated references are not cached.</td>
    </tr>
  </tbody>
</table>
