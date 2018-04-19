# Gin

Gin provides a lightweight dependency injection framework for Python. It allows
functions or classes to be annotated as `@gin.configurable`, which enables
setting their parameters via a simple config file using a clear and powerful
syntax. This makes it possible to specify parameters of functions with a config
file, without needing to write any extra code to parse the config file. This
avoids the need to define new protos, or write boiler plate conversion code.
Gin is particularly useful for machine learning experiments (e.g. using TF),
which tend to have many parameters, often nested in complex ways. Gin makes it
easy to specify these, and to easily keep track of all their values, making
experiments transparent and easily repeatable.

**Code**: https://github.com/google/gin-config/tree/master/gin/ \
**Buganizer component**: [Research > BigML >
Gin](b/issues?q=componentid:193973%20status:open) \
**User mailing list**: gin-config-users@ \
**Authors**: [Dan Holtmann-Rice](teams@dhr), [Sergio
Guadarrama](teams@sguada), Nathan Silberman (Xoogler)


This is not an official Google product.

## Full user-guide

The full user-guide can be found at
https://github.com/google/gin-config/tree/master/docs/index.md

## Basic usage

__Import Gin__

Add the following dependency to the BUILD file:

```
//research/bigml/gin
```

In Python code:

```python
import gin
```

__Define a configurable function__

```python
@gin.configurable(blacklist=['images', 'num_outputs'])
def my_network(images, num_outputs, num_layers=3, weight_decay=1e-4):
  ...
```

__Define a configurable class__

```python
@gin.configurable
class MyNetwork(tf.train.Optimizer):
  def __init__(self, num_layers=3, weight_decay=1e-4)
    ...
  def __call__(self, images, num_outputs):
    ...
```

__Configure it__

```python
# This configures the functional version above. For the class, we'd use
# MyNetwork instead of my_network.
gin.parse_config("""
  my_network.num_layers = 4
  my_network.weight_decay = 1e-3
""")
```
