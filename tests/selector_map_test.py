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

from absl.testing import absltest

from gin import selector_map


class SelectorMapTest(absltest.TestCase):

  def testBasicOperations(self):
    sm = selector_map.SelectorMap()
    sm['signifier'] = 'signified'
    sm['module.chain.name'] = 'value'

    self.assertIn('signifier', sm)
    self.assertEqual(sm['signifier'], 'signified')
    self.assertIn('module.chain.name', sm)
    self.assertEqual(sm['module.chain.name'], 'value')

    with self.assertRaises(KeyError):
      _ = sm['nonexistent']

  def testInvalidSelectors(self):
    self.assertFalse(selector_map.SELECTOR_RE.match('.a'))
    self.assertFalse(selector_map.SELECTOR_RE.match('a.'))
    self.assertFalse(selector_map.SELECTOR_RE.match('0.a'))
    self.assertFalse(selector_map.SELECTOR_RE.match('a.0'))
    self.assertFalse(selector_map.SELECTOR_RE.match('$'))
    self.assertFalse(selector_map.SELECTOR_RE.match('a.b!'))

    sm = selector_map.SelectorMap()
    with self.assertRaises(ValueError):
      sm['0oops'] = 0

  def testPartiallyMatchingCompleteSelectors(self):
    sm = selector_map.SelectorMap()
    sm['more.specific.selector'] = 1
    sm['specific.selector'] = 2
    self.assertEqual(sm.get_match('specific.selector'), 2)
    self.assertEqual(sm.get_match('more.specific.selector'), 1)
    self.assertCountEqual(sm.get_all_matches('selector'), [1, 2])
    # Because 'specific.selector' exactly matches an existing selector, it isn't
    # ambiguous and `get_all_matches` only returns one value.
    self.assertCountEqual(sm.get_all_matches('specific.selector'), [2])

    # Try in the reverse order.
    sm = selector_map.SelectorMap()
    sm['specific.selector'] = 2
    sm['more.specific.selector'] = 1
    self.assertEqual(sm.get_match('more.specific.selector'), 1)
    self.assertEqual(sm.get_match('specific.selector'), 2)
    self.assertCountEqual(sm.get_all_matches('selector'), [1, 2])

    self.assertEqual(
        sm.minimal_selector('specific.selector'), 'specific.selector')
    self.assertEqual(
        sm.minimal_selector('more.specific.selector'), 'more.specific.selector')

  def testPartialMatching(self):
    sm = selector_map.SelectorMap()
    sm['a.a.a.name'] = 'one'
    sm['a.a.b.name'] = 2
    sm['a.a.a.moose'] = ['three']

    self.assertEqual(sm.get_match('moose'), ['three'])
    self.assertEqual(sm.get_match('a.name'), 'one')
    self.assertEqual(sm.get_match('b.name'), 2)
    self.assertEqual(sm.get_match('a.b.name'), 2)
    self.assertEqual(sm.get_match('a.a.b.name'), 2)
    self.assertEqual(sm.get_match('nonexistent', 'default'), 'default')

  def testAmbiguityException(self):
    sm = selector_map.SelectorMap()
    sm['a.a.a.name'] = 'one'
    sm['b.a.a.name'] = 2

    with self.assertRaisesRegex(KeyError, 'Ambiguous'):
      sm.get_match('name')
    with self.assertRaisesRegex(KeyError, 'Ambiguous'):
      sm.get_match('a.name')
    with self.assertRaisesRegex(KeyError, 'Ambiguous'):
      sm.get_match('a.a.name')

    sm.get_match('a.a.a.name')
    sm.get_match('b.a.a.name')

  def testMinimalSelector(self):
    sm = selector_map.SelectorMap()
    sm['a.a.a.name'] = 'one'
    sm['a.b.a.name'] = 2
    sm['a.a.a.moose'] = ['three']

    self.assertEqual(sm.minimal_selector('a.a.a.moose'), 'moose')
    self.assertEqual(sm.minimal_selector('a.b.a.name'), 'b.a.name')

  def testPop(self):
    sm = selector_map.SelectorMap()
    sm['a.a.a.name'] = 'one'
    sm['a.b.a.name'] = 2
    sm['a.a.a.moose'] = ['three']

    self.assertLen(sm, 3)
    self.assertEqual(sm.pop('a.a.a.name'), 'one')
    self.assertLen(sm, 2)
    self.assertNotIn('a.a.a.name', sm)
    self.assertEqual(sm['a.a.a.moose'], ['three'])
    self.assertEqual(sm.minimal_selector('a.b.a.name'), 'name')
    self.assertEqual(sm.pop('a.a.a.moose'), ['three'])
    self.assertLen(sm, 1)
    self.assertNotIn('a.a.a.moose', sm)
    self.assertEqual(list(sm.items()), [('a.b.a.name', 2)])
    self.assertEqual(sm.pop('a.b.a.name'), 2)
    self.assertEmpty(sm)


if __name__ == '__main__':
  absltest.main()
