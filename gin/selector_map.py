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

"""Provides a dict-like object that handles Gin "selectors"."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import re

import six

# Key used to represent terminal nodes (nodes that correspond to a complete
# selector that was added to the map) in the selector tree.
_TERMINAL_KEY = '$'

# A regular expression that matches valid selectors.
SELECTOR_RE = re.compile(r'^([a-zA-Z_]\w*\.)*[a-zA-Z_]\w*$')


class SelectorMap(object):
  """A dict-like object that supports partial matches of "selectors".

  A "selector" is an identifier consisting of multiple components separated by
  periods, for instance "outer.inner.name". The `SelectorMap` object acts like a
  dictionary, allowing these selectors to be stored and retrieved (but currently
  not deleted). Additionally, it supports partial matching of selectors through
  the `matching_selectors`, `get_match`, and `get_all_matches` methods. Partial
  matching is done from the *innermost* components of selectors. For instance
  "name" and "inner.name" both match "outer.inner.name", but "outer" and
  "outer.inner" do not.
  """

  def __init__(self):
    """Constructs an empty `SelectorMap`."""
    # Stores a suffix-tree representation of selectors as a dictionary of
    # dictionaries (of dictionaries ...), where the top-level dictionary's keys
    # are *innermost* selector components. The values in the leaves of the tree
    # are the complete selectors corresponding to the path to the terminal.
    self._selector_tree = {}
    # Stores a mapping from complete selectors to values.
    self._selector_map = {}

  def clear(self):
    self._selector_tree.clear()
    self._selector_map.clear()

  def copy(self):
    # pylint: disable=protected-access
    sm = SelectorMap()
    sm._selector_tree = self._selector_tree.copy()
    sm._selector_map = self._selector_map.copy()
    return sm

  def __copy__(self):
    return self.copy()

  def iteritems(self):
    return six.iteritems(self._selector_map)

  def items(self):
    if six.PY2:
      return self._selector_map.items()
    return self.iteritems()

  def __setitem__(self, complete_selector, value):
    """Associates a value with `complete_selector`.

    This function also performs some additional bookkeeping to facilitate
    partial matching of selectors.

    Args:
      complete_selector: The (complete) selector to associate a value with.
      value: The value to associate.

    Raises:
      ValueError: If `complete_selector` isn't a string consisting of valid
        Python identifiers separated by periods.
    """
    if not SELECTOR_RE.match(complete_selector):
      raise ValueError("Invalid selector '{}'.".format(complete_selector))

    selector_components = complete_selector.split('.')
    node = self._selector_tree

    # Iterate backwards over the components of the selector.
    for component in selector_components[::-1]:
      node = node.setdefault(component, {})
    node[_TERMINAL_KEY] = complete_selector
    self._selector_map[complete_selector] = value

  def __getitem__(self, complete_selector):
    """Look up the value of `complete_selector` (no partial matching)."""
    return self._selector_map[complete_selector]

  def __contains__(self, complete_selector):
    """Check if `complete_selector` is present."""
    return complete_selector in self._selector_map

  def get(self, complete_selector, default=None):
    """Look up the value of `complete_selector` if present, or `default`."""
    return self._selector_map.get(complete_selector, default)

  def matching_selectors(self, partial_selector):
    """Retrieves all selectors matching `partial_selector`.

    For instance, if "one.a.b" and "two.a.b" are stored in a `SelectorMap`, both
    `matching_selectors('b')` and `matching_selectors('a.b')` will return them.

    In the event that `partial_selector` exactly matches an existing complete
    selector, only that complete selector is returned. For instance, if
    "a.b.c.d" and "c.d" are stored, `matching_selectors('c.d')` will return only
    `['c.d']`, while `matching_selectors('d')` will return both.

    Args:
      partial_selector: The partial selector to find matches for.

    Returns:
      A list of selectors matching `partial_selector`.
    """
    if partial_selector in self._selector_map:
      return [partial_selector]

    selector_components = partial_selector.split('.')
    node = self._selector_tree

    for component in reversed(selector_components):
      if component not in node:
        return []
      node = node[component]

    selectors = []
    dfs_stack = [node]
    while dfs_stack:
      node = dfs_stack.pop().copy()
      selector = node.pop(_TERMINAL_KEY, None)
      dfs_stack.extend(node.values())
      if selector:
        selectors.append(selector)

    return selectors

  def get_match(self, partial_selector, default=None):
    """Gets a (single) value matching `partial_selector`.

    If the partial_selector exactly matches a complete selector, the value
    associated with the complete selector is returned.

    Args:
      partial_selector: The partial selector to find values for.
      default: A default value to return if nothing matches `partial_selector`.

    Returns:
      The value associated with `partial_selector` if it exists, else `default`.

    Raises:
      KeyError: If `partial_selector` matches more than one selector in the map.
    """
    matching_selectors = self.matching_selectors(partial_selector)
    if not matching_selectors:
      return default
    if len(matching_selectors) > 1:
      err_str = "Ambiguous selector '{}', matches {}."
      raise KeyError(err_str.format(partial_selector, matching_selectors))
    return self._selector_map[matching_selectors[0]]

  def get_all_matches(self, partial_selector):
    """Returns all values matching `partial_selector` as a list."""
    matching_selectors = self.matching_selectors(partial_selector)
    return [self._selector_map[selector] for selector in matching_selectors]

  def minimal_selector(self, complete_selector):
    """Returns the minimal selector that uniquely matches `complete_selector`.

    Args:
      complete_selector: A complete selector stored in the map.

    Returns:
      A partial selector that unambiguously matches `complete_selector`.

    Raises:
      KeyError: If `complete_selector` is not in the map.
    """
    if complete_selector not in self._selector_map:
      raise KeyError("No value with selector '{}'.".format(complete_selector))

    selector_components = complete_selector.split('.')
    node = self._selector_tree

    start = None
    for i, component in enumerate(reversed(selector_components)):
      if len(node) == 1:
        if start is None:
          start = -i  # Negative index, since we're iterating in reverse.
      else:
        start = None
      node = node[component]

    if len(node) > 1:  # The selector is a substring of another selector.
      return complete_selector
    return '.'.join(selector_components[start:])
