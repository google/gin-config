from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import absltest
import gin
from gin.config import ConfigState


@gin.configurable
def f(x='default', y='default'):
    return x, y


@gin.configurable
def g(z=None):
    return z


class ConfigStateTest(absltest.TestCase):

    def tearDown(self):
        gin.config.clear_config(clear_constants=True)
        super(ConfigStateTest, self).tearDown()

    def test_gin_state(self):
        gin.bind_parameter('f.x', 'global')
        self.assertEqual(gin.query_parameter('f.x'), 'global')
        with ConfigState() as temp_state:
            self.assertEqual(f()[0], 'default')
            gin.bind_parameter('f.x', 'temp')
            self.assertEqual(gin.query_parameter('f.x'), 'temp')
        self.assertEqual(gin.query_parameter('f.x'), 'global')
        with temp_state:
            self.assertEqual(gin.query_parameter('f.x'), 'temp')

    def test_finalize(self):
        gin.bind_parameter('f.x', 'global')
        gin.finalize()
        self.assertTrue(gin.config_is_locked())
        with ConfigState() as temp_state:
            gin.bind_parameter('f.x', 'temp')
            self.assertEqual(gin.query_parameter('f.x'), 'temp')
            self.assertFalse(gin.config_is_locked())
        self.assertTrue(gin.config_is_locked())
        with temp_state:
            self.assertFalse(gin.config_is_locked())
            gin.config.finalize()
            self.assertTrue(gin.config_is_locked())
        with temp_state:
            self.assertTrue(gin.config_is_locked())

    def test_from_global(self):
        gin.bind_parameter('f.x', 'global')
        with ConfigState(inherit_from='default') as temp_state:
            self.assertEqual(gin.query_parameter('f.x'), 'global')
            gin.bind_parameter('f.y', 'temp')

        with self.assertRaises(ValueError):
            gin.query_parameter('f.y')
        self.assertEqual(f()[1], 'default')

        self.assertEqual(gin.query_parameter('f.x'), 'global')
        with temp_state:
            self.assertEqual(gin.query_parameter('f.x'), 'global')
            self.assertEqual(gin.query_parameter('f.y'), 'temp')
            gin.bind_parameter('f.x', 'temp')
            self.assertEqual(gin.query_parameter('f.x'), 'temp')
        self.assertEqual(gin.query_parameter('f.x'), 'global')
        with temp_state:
            self.assertEqual(gin.query_parameter('f.x'), 'temp')

    def test_operative_config_str(self):
        with ConfigState():
            g()
            op_config_string = gin.operative_config_str()
            self.assertTrue('f.x' not in gin.operative_config_str())
            self.assertTrue('g.z' in gin.operative_config_str())
        f()
        op_config_string = gin.operative_config_str()
        self.assertTrue('f.x' in op_config_string)
        self.assertTrue('g.z' not in op_config_string)

    def test_singletons(self):

        @gin.configurable
        class Champ(object):
            count = 0

            def __init__(self):
                Champ.count += 1

        config = '''
chuck_norris/singleton.constructor = @Champ
f.x = @chuck_norris/singleton()
g.z = @chuck_norris/singleton()
'''
        gin.parse_config(config)
        self.assertEqual(Champ.count, 0)
        f()
        self.assertEqual(Champ.count, 1)
        g()
        self.assertEqual(Champ.count, 1)
        with ConfigState(inherit_from='default'):
            f()
            self.assertEqual(Champ.count, 1)
        with ConfigState():
            gin.parse_config(config)
            f()
            self.assertEqual(Champ.count, 2)

    def test_thrashing(self):
        a = ConfigState()
        b = ConfigState()

        def setx(x):
            gin.bind_parameter('f.x', x)

        def check_is(expected):
            return self.assertEqual(gin.query_parameter('f.x'), expected)

        setx('global')
        check_is('global')
        with a:
            setx('a0')
            check_is('a0')
            with b:
                setx('b0')
                check_is('b0')
                with a:
                    check_is('a0')
                    setx('a1')
                    check_is('a1')
                    with b:
                        check_is('b0')
                    check_is('a1')
                check_is('b0')
            check_is('a1')
        check_is('global')


if __name__ == '__main__':
    absltest.main()
