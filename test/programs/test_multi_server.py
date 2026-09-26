import typing
import unittest
from MultiServer import Context, LimitExceeded, ServerCommandProcessor, compute_value, get_stored_value_size


class TestResolvePlayerName(unittest.TestCase):
    def test_resolve(self) -> None:
        p = ServerCommandProcessor(Context("", 0, "", "", 0, 0, False))
        p.ctx.player_names = {
            (1, 1): "AAA",
            (1, 2): "aBc",
            (1, 3): "abC",
        }
        assert not p.resolve_player("abc"), "ambiguous name entry shouldn't resolve to player"
        assert not p.resolve_player("Abc"), "ambiguous name entry shouldn't resolve to player"
        assert p.resolve_player("aBc") == (1, 2, "aBc"), "matching case resolve"
        assert p.resolve_player("abC") == (1, 3, "abC"), "matching case resolve"
        assert not p.resolve_player("aB"), "partial name shouldn't resolve to player"
        assert not p.resolve_player("abCD"), "incorrect name shouldn't resolve to player"

        p.ctx.player_names = {
            (1, 1): "aaa",
            (1, 2): "abc",
            (1, 3): "abC",
        }
        assert p.resolve_player("abc") == (1, 2, "abc"), "matching case resolve"
        assert not p.resolve_player("Abc"), "ambiguous name entry shouldn't resolve to player"
        assert not p.resolve_player("aBc"), "ambiguous name entry shouldn't resolve to player"
        assert p.resolve_player("abC") == (1, 3, "abC"), "matching case resolve"

        p.ctx.player_names = {
            (1, 1): "AbcdE",
            (1, 2): "abc",
            (1, 3): "abCD",
        }
        assert p.resolve_player("abc") == (1, 2, "abc"), "matching case resolve"
        assert p.resolve_player("abC") == (1, 2, "abc"), "case insensitive resolves when 1 match"
        assert p.resolve_player("Abc") == (1, 2, "abc"), "case insensitive resolves when 1 match"
        assert p.resolve_player("ABC") == (1, 2, "abc"), "case insensitive resolves when 1 match"
        assert p.resolve_player("abcd") == (1, 3, "abCD"), "case insensitive resolves when 1 match"
        assert not p.resolve_player("aB"), "partial name shouldn't resolve to player"

DataStorageOp = typing.Callable[[typing.Any, typing.Any], typing.Any]

class TestDataStorageOperations(unittest.TestCase):

    def test_modulo_string_any(self):
        ctx = Context("", 0, "", "", 0, 0, False)

        assert ctx.disable_string_modulo == True

        op_mod: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mod", lhs, rhs)

        self.assertRaises(ValueError, lambda: op_mod("%s", None))
        self.assertRaises(ValueError, lambda: op_mod("%s", 0))
        self.assertRaises(ValueError, lambda: op_mod("%s", 0.0))
        self.assertRaises(ValueError, lambda: op_mod("%s", ""))
        self.assertRaises(ValueError, lambda: op_mod("%s", []))
        self.assertRaises(ValueError, lambda: op_mod("%s", {}))
        self.assertRaises(ValueError, lambda: op_mod("%s", object()))

    def test_add_int_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_add: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "add", lhs, rhs)
        max_int_bits = ctx.limits["max_int_bits"].value
        max_int = 2 ** max_int_bits - 1
        min_int = -max_int

        result = op_add(max_int, 0)
        assert result == max_int
        assert result.bit_length() <= max_int_bits

        result = op_add(min_int, 0)
        assert result == min_int
        assert result.bit_length() <= max_int_bits

        self.assertRaises(LimitExceeded, lambda: op_add(max_int, 1))
        self.assertRaises(LimitExceeded, lambda: op_add(min_int, -1))

    def test_add_str_str(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_add: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "add", lhs, rhs)
        max_str_len = ctx.limits["max_string_len"].value
        max_str = "a" * max_str_len

        result = op_add(max_str, "")
        assert result == max_str
        assert len(result) <= max_str_len

        result = op_add("abc", "def")
        assert result == "abcdef"
        assert len(result) <= max_str_len

        self.assertRaises(LimitExceeded, lambda: op_add(max_str, "a"))

    def test_add_list_list(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_add: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "add", lhs, rhs)
        max_list_len = ctx.limits["max_list_len"].value
        max_list = ["a"] * max_list_len

        result = op_add(max_list, [])
        assert result == max_list
        assert len(result) <= max_list_len

        result = op_add(["abc"], ["def"])
        assert result == ["abc", "def"]
        assert len(result) <= max_list_len

        self.assertRaises(LimitExceeded, lambda: op_add(max_list, ["a"]))

    def test_mul_int_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_mul: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mul", lhs, rhs)
        max_int_bits = ctx.limits["max_int_bits"].value
        max_int = 2 ** max_int_bits - 1
        min_int = -max_int

        result = op_mul(0, 0)
        assert result == 0

        result = op_mul(0, max_int + 1)
        assert result == 0

        result = op_mul(max_int + 1, 0)
        assert result == 0

        result = op_mul(1, max_int)
        assert result == max_int

        result = op_mul(max_int, 1)
        assert result == max_int

        result = op_mul(max_int // 15, 15)
        assert result == max_int

        result = op_mul(15, max_int // 15)
        assert result == max_int

        self.assertRaises(LimitExceeded, lambda: op_mul(max_int // 15, 16))
        self.assertRaises(LimitExceeded, lambda: op_mul(16, max_int // 15))

        result = op_mul(0, min_int - 1)
        assert result == 0

        result = op_mul(min_int - 1, 0)
        assert result == 0

        result = op_mul(1, min_int)
        assert result == min_int

        result = op_mul(min_int, 1)
        assert result == min_int

        result = op_mul(min_int // 15, 15)
        assert result == min_int

        result = op_mul(15, min_int // 15)
        assert result == min_int

        self.assertRaises(LimitExceeded, lambda: op_mul(min_int // 15, 16))
        self.assertRaises(LimitExceeded, lambda: op_mul(16, min_int // 15))

    def test_mul_str_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_mul: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mul", lhs, rhs)
        max_str_len = ctx.limits["max_string_len"].value
        max_str = "a" * max_str_len

        result = op_mul("a", max_str_len)
        assert result == max_str

        self.assertRaises(LimitExceeded, lambda: op_mul("a", max_str_len + 1))

    def test_mul_int_str(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_mul: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mul", lhs, rhs)
        max_str_len = ctx.limits["max_string_len"].value
        max_str = "a" * max_str_len

        result = op_mul(max_str_len, "a")
        assert result == max_str

        self.assertRaises(LimitExceeded, lambda: op_mul(max_str_len + 1, "a"))

    def test_mul_list_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_mul: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mul", lhs, rhs)
        max_list_len = ctx.limits["max_list_len"].value
        max_list = ["a"] * max_list_len

        result = op_mul(["a"], max_list_len)
        assert result == max_list

        self.assertRaises(LimitExceeded, lambda: op_mul(["a"], max_list_len + 1))

    def test_mul_int_list(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_mul: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "mul", lhs, rhs)
        max_list_len = ctx.limits["max_list_len"].value
        max_list = ["a"] * max_list_len

        result = op_mul(max_list_len, ["a"])
        assert result == max_list

        self.assertRaises(LimitExceeded, lambda: op_mul(max_list_len + 1, ["a"]))

    def test_pow_int_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_pow: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "pow", lhs, rhs)
        max_int_bits = ctx.limits["max_int_bits"].value
        max_int = 2 ** max_int_bits - 1
        min_int = -max_int

        result = op_pow(0, 0)
        assert result == 1

        result = op_pow(0, max_int + 1)
        assert result == 0

        result = op_pow(max_int + 1, 0)
        assert result == 1

        result = op_pow(1, max_int_bits)
        assert result == 1

        result = op_pow(2, max_int_bits - 1)
        assert result == 2 ** (max_int_bits - 1)

        self.assertRaises(LimitExceeded, lambda: op_pow(2, max_int_bits))

        result = op_pow(min_int - 1, 0)
        assert result == 1

        result = op_pow(-1, max_int_bits)
        assert result == 1

        result = op_pow(-2, max_int_bits - 1)
        assert result == (-2) ** (max_int_bits - 1)

        self.assertRaises(LimitExceeded, lambda: op_pow(-2, max_int_bits))

    def test_lshift_int_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_lshift: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "left_shift", lhs, rhs)
        max_int_bits = ctx.limits["max_int_bits"].value
        max_int = 2 ** max_int_bits - 1

        result = op_lshift(0, 0)
        assert result == 0

        result = op_lshift(0, max_int)
        assert result == 0

        result = op_lshift(1, max_int_bits - 1)
        assert result == 1 << (max_int_bits - 1)

        self.assertRaises(LimitExceeded, lambda: op_lshift(1, max_int_bits))

    def test_update_list(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_update: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "update", lhs, rhs)
        max_list_len = ctx.limits["max_list_len"].value
        max_list = list(range(max_list_len))

        result = op_update([1, 2, 3], [2, 3, 4])
        assert result == [1, 2, 3, 4]

        result = op_update([1, 2, 3], [1, 2, 3])
        assert result == [1, 2, 3]

        result = op_update([], [1, 2, 3])
        assert result == [1, 2, 3]

        result = op_update([1, 2, 3], [])
        assert result == [1, 2, 3]

        result = op_update(max_list, max_list)
        assert result == max_list

        self.assertRaises(LimitExceeded, lambda: op_update(max_list, [max_list_len]))

    def test_update_dict(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_update: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "update", lhs, rhs)
        limit = ctx.limits["max_string_len"].value

        # Basic merging
        result = op_update({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

        result = op_update({"a": 1}, {"a": 99})
        assert result == {"a": 99}

        result = op_update({}, {"a": 1})
        assert result == {"a": 1}

        result = op_update({"a": 1}, {})
        assert result == {"a": 1}

        self.assertRaises(LimitExceeded, lambda: op_update({"k": "a" * (limit + 1)}, {}))

        self.assertRaises(LimitExceeded, lambda: op_update({}, {"k": "a" * (limit + 1)}))

    def test_replace_str(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_replace: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "replace", lhs, rhs)
        limit = ctx.limits["max_string_len"].value

        result = op_replace("old", "new")
        assert result == "new"

        result = op_replace("old", "a" * limit)
        assert result == "a" * limit

        self.assertRaises(LimitExceeded, lambda: op_replace("old", "a" * (limit + 1)))

    def test_replace_list(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_replace: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "replace", lhs, rhs)
        limit = ctx.limits["max_string_len"].value

        result = op_replace([1, 2, 3], [4, 5, 6])
        assert result == [4, 5, 6]

        self.assertRaises(LimitExceeded, lambda: op_replace([], ["a" * (limit + 1)]))

    def test_replace_dict(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_replace: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "replace", lhs, rhs)
        limit = ctx.limits["max_string_len"].value

        result = op_replace({"a": 1}, {"b": 2})
        assert result == {"b": 2}

        self.assertRaises(LimitExceeded, lambda: op_replace({}, {"k": "a" * (limit + 1)}))

    def test_replace_int(self):
        ctx = Context("", 0, "", "", 0, 0, False)
        op_replace: DataStorageOp = lambda lhs, rhs: compute_value(ctx, "replace", lhs, rhs)
        max_int_bits = ctx.limits["max_int_bits"].value
        max_int = 2 ** max_int_bits - 1

        result = op_replace(0, max_int)
        assert result == max_int

        self.assertRaises(LimitExceeded, lambda: op_replace(0, max_int + 1))

class TestSlotStorageLimits(unittest.TestCase):

    def _make_ctx(self, slot_total: int = 100, slot_key_limit: int = 10) -> Context:
        return Context("", 0, "", "", 0, 0, False, limit_slot_total=slot_total, limit_slot_key_total=slot_key_limit)

    def _simulate_set(self, ctx: Context, slot: int, key: str, value) -> None:
        if len(key) > ctx.limits["max_key_len"].value:
            raise LimitExceeded(ctx.limits["max_key_len"])
        new_size = get_stored_value_size(value)
        old_size = ctx.stored_data_slot_key_sizes[slot].get(key, 0)
        key_is_new = key not in ctx.stored_data_slot_key_sizes[slot]
        projected = ctx.stored_data_slot_sizes[slot] - old_size + new_size + (len(key) if key_is_new else 0)

        if key_is_new and len(ctx.stored_data_slot_key_sizes[slot]) >= ctx.limits["slot_key_limit"].value:
            raise LimitExceeded(ctx.limits["slot_key_limit"])

        if new_size > old_size and projected > ctx.limits["slot_total_limit"].value:
            raise LimitExceeded(ctx.limits["slot_total_limit"])

        ctx.stored_data[key] = value
        ctx.stored_data_slot_key_sizes[slot][key] = new_size
        ctx.stored_data_slot_sizes[slot] = projected

    def test_slot_write_within_limit(self):
        ctx = self._make_ctx(slot_total=1000)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 50)
        assert ctx.stored_data_slot_sizes[1] == 50 + len("foo"), "size includes key length"

    def test_slot_write_at_limit(self):
        ctx = self._make_ctx(slot_total=1000)
        key = "foo"
        value_size = 1000 - len(key)
        self._simulate_set(ctx, slot=1, key=key, value="a" * value_size)
        assert ctx.stored_data_slot_sizes[1] == 1000

    def test_slot_write_exceeds_limit(self):
        ctx = self._make_ctx(slot_total=100)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 50)
        # "bar" (3) + 51 = 54, total would be 53 + 54 = 107 > 100
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key="bar", value="a" * 51))

    def test_slot_overwrite_same_key_grows(self):
        ctx = self._make_ctx(slot_total=1000)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 50)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 100)
        # key len only counted once on first write
        assert ctx.stored_data_slot_sizes[1] == 100 + len("foo"), "overwrite: key len counted once"

    def test_slot_overwrite_same_key_exceeds(self):
        ctx = self._make_ctx(slot_total=1000)
        key = "foo"
        self._simulate_set(ctx, slot=1, key=key, value="a" * 50)
        limit = ctx.limits["slot_total_limit"].value
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key=key, value="a" * (limit + 1)))

    def test_slot_shrink_always_allowed(self):
        ctx = self._make_ctx(slot_total=1000)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 100)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 1)
        assert ctx.stored_data_slot_sizes[1] == 1 + len("foo"), "shrink: key len still counted"

    def test_slots_are_independent(self):
        ctx = self._make_ctx(slot_total=1000)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 100)
        self._simulate_set(ctx, slot=2, key="foo", value="a" * 100)
        assert ctx.stored_data_slot_sizes[1] == 100 + len("foo")
        assert ctx.stored_data_slot_sizes[2] == 100 + len("foo")

    def test_shared_key_different_slots_independent(self):
        ctx = self._make_ctx(slot_total=100)
        self._simulate_set(ctx, slot=1, key="shared", value="a" * 60)
        self._simulate_set(ctx, slot=2, key="shared", value="a" * 60)
        assert ctx.stored_data_slot_sizes[1] == 60 + len("shared")
        assert ctx.stored_data_slot_sizes[2] == 60 + len("shared")
        # slot 1 has 60 + 6 = 66 used, 34 remaining. "other"(5) + 30 value = 35 > 34
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key="other", value="a" * 30))

    def test_save_restore_recomputes_sizes(self):
        ctx = self._make_ctx(slot_total=1000)
        self._simulate_set(ctx, slot=1, key="foo", value="a" * 50)
        self._simulate_set(ctx, slot=1, key="bar", value="a" * 30)

        save = ctx.get_save()

        ctx2 = self._make_ctx(slot_total=1000)
        ctx2.stored_data = save["stored_data"]
        if "stored_data_slot_keys" in save:
            for slot_str, keys in save["stored_data_slot_keys"].items():
                slot = int(slot_str)
                for key in keys:
                    if key in ctx2.stored_data:
                        size = get_stored_value_size(ctx2.stored_data[key])
                        ctx2.stored_data_slot_key_sizes[slot][key] = size
                        ctx2.stored_data_slot_sizes[slot] += size + len(key)

        assert ctx2.stored_data_slot_sizes[1] == 50 + len("foo") + 30 + len("bar"), "restore includes key lengths"
        assert ctx2.stored_data_slot_key_sizes[1]["foo"] == 50
        assert ctx2.stored_data_slot_key_sizes[1]["bar"] == 30

    def test_get_stored_value_size_types(self):
        assert get_stored_value_size(None) == 0, "None should be 0"
        assert get_stored_value_size("abc") == 3, "3-char string should be 3"
        assert get_stored_value_size(0) == 0, "0 should be 0 bytes"
        assert get_stored_value_size(1) == 1, "1 should be 1 byte"
        assert get_stored_value_size(255) == 1, "255 (8 bits) should be 1 byte"
        assert get_stored_value_size(256) == 2, "256 (9 bits) should be 2 bytes"
        assert get_stored_value_size([1, 2, 3]) > 0, "non-empty list should have positive size"
        assert get_stored_value_size({"a": 1}) > 0, "non-empty dict should have positive size"

    def test_slot_key_limit_exceeded(self):
        ctx = self._make_ctx(slot_total=10000, slot_key_limit=3)
        self._simulate_set(ctx, slot=1, key="a", value="x")
        self._simulate_set(ctx, slot=1, key="b", value="x")
        self._simulate_set(ctx, slot=1, key="c", value="x")
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key="d", value="x"))

    def test_slot_key_limit_overwrite_allowed(self):
        """Overwriting an existing key does not count toward the key limit."""
        ctx = self._make_ctx(slot_total=10000, slot_key_limit=2)
        self._simulate_set(ctx, slot=1, key="a", value="x")
        self._simulate_set(ctx, slot=1, key="b", value="x")
        # Overwrite existing key — should not raise
        self._simulate_set(ctx, slot=1, key="a", value="y")
        assert ctx.stored_data["a"] == "y", "overwrite should succeed"

    def test_slot_key_limit_independent_per_slot(self):
        """Key limit is per slot — slot 2 has its own budget."""
        ctx = self._make_ctx(slot_total=10000, slot_key_limit=2)
        self._simulate_set(ctx, slot=1, key="a", value="x")
        self._simulate_set(ctx, slot=1, key="b", value="x")
        # slot 2 should have its own key budget
        self._simulate_set(ctx, slot=2, key="a", value="x")
        self._simulate_set(ctx, slot=2, key="b", value="x")
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key="c", value="x"))
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=2, key="c", value="x"))

    def test_key_len_limit(self):
        ctx = self._make_ctx(slot_total=10000, slot_key_limit=10)
        max_key_len = ctx.limits["max_key_len"].value

        # At limit — should succeed
        self._simulate_set(ctx, slot=1, key="a" * max_key_len, value="x")

        # Over limit — should fail
        self.assertRaises(LimitExceeded, lambda: self._simulate_set(ctx, slot=1, key="a" * (max_key_len + 1), value="x"))


