import unittest
from dataclasses import dataclass

from resmon.process_classify import belongs_to_app, subtree_totals


class BelongsToAppTests(unittest.TestCase):
    def setUp(self):
        # A small process tree:
        #   1 (init) -> 100 (shell) -> 200 (app root, window owner)
        #                                -> 201 (renderer) -> 202 (gpu helper)
        #                              -> 300 (unrelated background daemon)
        self.ppid_of = {
            100: 1,
            200: 100,
            201: 200,
            202: 201,
            300: 1,
        }
        self.app_roots = {200}

    def test_root_belongs_to_itself(self):
        self.assertTrue(belongs_to_app(200, self.ppid_of, self.app_roots))

    def test_direct_child_belongs(self):
        self.assertTrue(belongs_to_app(201, self.ppid_of, self.app_roots))

    def test_grandchild_belongs(self):
        self.assertTrue(belongs_to_app(202, self.ppid_of, self.app_roots))

    def test_unrelated_process_does_not_belong(self):
        self.assertFalse(belongs_to_app(300, self.ppid_of, self.app_roots))

    def test_shell_ancestor_does_not_belong(self):
        # 100 is the app's parent, not its child — shouldn't be swept in.
        self.assertFalse(belongs_to_app(100, self.ppid_of, self.app_roots))

    def test_unknown_pid_does_not_belong(self):
        self.assertFalse(belongs_to_app(9999, self.ppid_of, self.app_roots))

    def test_cache_is_populated_and_reused(self):
        cache: dict[int, bool] = {}
        self.assertTrue(belongs_to_app(202, self.ppid_of, self.app_roots, cache))
        # Every node on the walked path should now be cached...
        self.assertIn(202, cache)
        self.assertIn(201, cache)
        self.assertIn(200, cache)
        # ...and a second call must return the same answer from the cache.
        self.assertTrue(belongs_to_app(202, self.ppid_of, self.app_roots, cache))

    def test_self_parented_pid_does_not_infinite_loop(self):
        ppid_of = {50: 50}
        self.assertFalse(belongs_to_app(50, ppid_of, set()))

    def test_deep_chain_stops_at_depth_guard(self):
        # A pathological chain with no root anywhere in it must terminate
        # (via the depth guard) rather than recurse forever.
        ppid_of = {i: i - 1 for i in range(1, 200)}
        self.assertFalse(belongs_to_app(199, ppid_of, set()))


@dataclass
class _Proc:
    pid: int
    cpu: float
    mem: float


class SubtreeTotalsTests(unittest.TestCase):
    def test_leaf_returns_its_own_values(self):
        cpu, mem = subtree_totals(1, {}, 5.0, 2.0)
        self.assertEqual((cpu, mem), (5.0, 2.0))

    def test_sums_direct_children(self):
        children_of = {
            1: [_Proc(2, 3.0, 1.0), _Proc(3, 4.0, 1.5)],
        }
        cpu, mem = subtree_totals(1, children_of, 1.0, 0.5)
        self.assertEqual(cpu, 1.0 + 3.0 + 4.0)
        self.assertEqual(mem, 0.5 + 1.0 + 1.5)

    def test_sums_grandchildren_too(self):
        children_of = {
            1: [_Proc(2, 3.0, 1.0)],
            2: [_Proc(3, 10.0, 5.0)],
        }
        cpu, mem = subtree_totals(1, children_of, 1.0, 0.0)
        self.assertEqual(cpu, 1.0 + 3.0 + 10.0)
        self.assertEqual(mem, 0.0 + 1.0 + 5.0)


if __name__ == "__main__":
    unittest.main()
