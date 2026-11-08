"""Diff mantiqi va CLI."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "jdiff.py")

spec = importlib.util.spec_from_file_location("jdiff", SCRIPT)
jd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jd)


def ops(a, b, **kw):
    return [(c.op, c.path) for c in jd.diff(a, b, **kw)]


class DiffTest(unittest.TestCase):
    def test_identical_documents_produce_nothing(self):
        self.assertEqual(ops({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}), [])

    def test_key_order_is_not_a_difference(self):
        self.assertEqual(ops({"a": 1, "b": 2}, {"b": 2, "a": 1}), [])

    def test_a_changed_value(self):
        self.assertEqual(ops({"a": 1}, {"a": 2}), [("~", "a")])

    def test_added_and_removed_keys(self):
        self.assertEqual(sorted(ops({"a": 1}, {"b": 1})), [("+", "b"), ("-", "a")])

    def test_nested_paths_are_spelled_out(self):
        self.assertEqual(ops({"s": {"p": 1}}, {"s": {"p": 2}}), [("~", "s.p")])

    def test_a_type_change_counts_even_when_python_calls_them_equal(self):
        # JSON'da true va 1 boshqa narsa, Python'da esa True == 1
        self.assertEqual(ops({"a": True}, {"a": 1}), [("~", "a")])
        self.assertEqual(ops({"a": 1}, {"a": 1.0}), [("~", "a")])

    def test_a_scalar_replaced_by_a_container(self):
        self.assertEqual(ops({"a": 1}, {"a": {"b": 2}}), [("~", "a")])

    def test_null_is_a_value_like_any_other(self):
        self.assertEqual(ops({"a": None}, {"a": 1}), [("~", "a")])
        self.assertEqual(ops({"a": None}, {"a": None}), [])

    def test_lists_compare_by_position_by_default(self):
        self.assertEqual(ops({"x": [1, 2]}, {"x": [1, 3]}), [("~", "x[1]")])

    def test_a_longer_list_adds_at_the_end(self):
        self.assertEqual(ops({"x": [1]}, {"x": [1, 2]}), [("+", "x[1]")])

    def test_a_shorter_list_removes_from_the_end(self):
        self.assertEqual(ops({"x": [1, 2]}, {"x": [1]}), [("-", "x[1]")])


class ArrayByTest(unittest.TestCase):
    def setUp(self):
        self.a = {"users": [{"id": 2, "n": "b"}, {"id": 1, "n": "a"}]}
        self.b = {"users": [{"id": 0, "n": "new"}, {"id": 2, "n": "b"},
                            {"id": 1, "n": "A"}]}

    def test_without_a_key_an_insert_shifts_everything(self):
        self.assertGreater(len(ops(self.a, self.b)), 3)

    def test_with_a_key_only_the_real_changes_show(self):
        self.assertEqual(sorted(ops(self.a, self.b, field="id")),
                         [("+", "users.id=0"), ("~", "users.id=1.n")])

    def test_reversing_the_sides_reverses_the_diff(self):
        # id=0 yo'qoladi, va id=1 ning nomi ham teskari tomonga o'zgaradi
        self.assertEqual(sorted(ops(self.b, self.a, field="id")),
                         [("-", "users.id=0"), ("~", "users.id=1.n")])

    def test_it_falls_back_to_position_when_the_key_is_missing(self):
        a = {"x": [{"id": 1}, {"name": "no id here"}]}
        b = {"x": [{"id": 1}, {"name": "changed"}]}
        self.assertEqual(ops(a, b, field="id"), [("~", "x[1].name")])

    def test_it_falls_back_when_the_key_is_not_unique(self):
        a = {"x": [{"id": 1, "v": 1}, {"id": 1, "v": 2}]}
        b = {"x": [{"id": 1, "v": 1}, {"id": 1, "v": 3}]}
        self.assertEqual(ops(a, b, field="id"), [("~", "x[1].v")])

    def test_it_falls_back_for_lists_of_scalars(self):
        self.assertEqual(ops({"x": [1, 2]}, {"x": [1, 3]}, field="id"),
                         [("~", "x[1]")])


class IgnoreTest(unittest.TestCase):
    def test_an_ignored_path_is_dropped(self):
        self.assertEqual(ops({"a": 1, "b": 1}, {"a": 2, "b": 2}, ignore=["a"]),
                         [("~", "b")])

    def test_ignoring_a_prefix_covers_everything_under_it(self):
        a = {"meta": {"built_at": 1, "hash": "x"}, "real": 1}
        b = {"meta": {"built_at": 2, "hash": "y"}, "real": 2}
        self.assertEqual(ops(a, b, ignore=["meta"]), [("~", "real")])

    def test_a_prefix_does_not_catch_a_similar_name(self):
        self.assertEqual(ops({"meta": 1, "metadata": 1}, {"meta": 2, "metadata": 2},
                             ignore=["meta"]),
                         [("~", "metadata")])

    def test_ignoring_a_list_index_prefix(self):
        a = {"x": [{"t": 1, "v": 1}]}
        b = {"x": [{"t": 2, "v": 2}]}
        self.assertEqual(ops(a, b, ignore=["x[0].t"]), [("~", "x[0].v")])


class BriefTest(unittest.TestCase):
    def test_short_values_are_shown_whole(self):
        self.assertEqual(jd.brief(8080), "8080")
        self.assertEqual(jd.brief("hi"), '"hi"')

    def test_big_containers_are_summarised(self):
        self.assertEqual(jd.brief({str(i): i for i in range(50)}), "{50 keys}")
        self.assertEqual(jd.brief(list(range(100))), "[100 items]")

    def test_a_long_string_is_cut(self):
        out = jd.brief("x" * 200)
        self.assertLessEqual(len(out), 61)
        self.assertTrue(out.endswith("…"))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jdiff-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def file(self, name, data, raw=None):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(data))
        return path

    def run_cli(self, *args, **kw):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True, input=kw.get("stdin"))

    def test_identical_files_exit_zero(self):
        a = self.file("a.json", {"x": 1})
        b = self.file("b.json", {"x": 1})
        out = self.run_cli(a, b)
        self.assertEqual(out.returncode, 0)
        self.assertIn("identical", out.stdout)

    def test_differences_exit_three(self):
        a = self.file("a.json", {"x": 1})
        b = self.file("b.json", {"x": 2})
        out = self.run_cli(a, b)
        self.assertEqual(out.returncode, 3)
        self.assertIn("1 change", out.stdout)
        self.assertIn("1 -> 2", out.stdout)

    def test_invalid_json_exits_one_and_names_the_file(self):
        a = self.file("a.json", None, raw="{not json")
        b = self.file("b.json", {"x": 1})
        out = self.run_cli(a, b)
        self.assertEqual(out.returncode, 1)
        self.assertIn("invalid JSON", out.stderr)
        self.assertIn("a.json", out.stderr)

    def test_a_missing_file_exits_one(self):
        b = self.file("b.json", {"x": 1})
        self.assertEqual(self.run_cli(os.path.join(self.tmp, "gone.json"), b).returncode, 1)

    def test_stdin_can_be_one_side(self):
        b = self.file("b.json", {"x": 2})
        out = self.run_cli("-", b, stdin='{"x": 1}')
        self.assertEqual(out.returncode, 3)

    def test_keys_only_hides_value_changes(self):
        a = self.file("a.json", {"x": 1, "gone": 1})
        b = self.file("b.json", {"x": 2, "new": 1})
        out = self.run_cli(a, b, "--keys-only")
        self.assertNotIn("->", out.stdout)
        self.assertIn("+ new", out.stdout)
        self.assertIn("- gone", out.stdout)

    def test_json_output_carries_old_and_new(self):
        a = self.file("a.json", {"x": 1})
        b = self.file("b.json", {"x": 2})
        data = json.loads(self.run_cli(a, b, "--json").stdout)
        self.assertFalse(data["ok"])
        self.assertEqual(data["changes"][0], {"op": "~", "path": "x", "old": 1, "new": 2})

    def test_unicode_survives(self):
        a = self.file("a.json", {"k": "ko'prik"})
        b = self.file("b.json", {"k": "quyosh"})
        self.assertIn("ko'prik", self.run_cli(a, b).stdout)


if __name__ == "__main__":
    unittest.main()
