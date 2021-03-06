import pytest

from inspect import getfullargspec

from objectextensions import Extendable, Extension


@pytest.fixture
def hashlist_cls():
    class HashList(Extendable):
        def __init__(self, iterable=()):
            super().__init__()

            self.values = {}
            self.list = []

            for value in iterable:
                self.append(value)

        def append(self, item):
            self.list.append(item)
            self.values[item] = self.values.get(item, []) + [len(self.list) - 1]

        def index(self, item):
            """
            Returns all indexes containing the specified item.
            Much lower time complexity than a typical list due to dict lookup usage
            """

            if item not in self.values:
                raise ValueError("{0} is not in hashlist".format(item))

            return self.values[item]

    return HashList


@pytest.fixture
def listener_cls(hashlist_cls):
    class Listener(Extension):
        @staticmethod
        def can_extend(target_cls):
            return issubclass(target_cls, hashlist_cls)

        @staticmethod
        def extend(target_cls):
            Extension._set(target_cls, "increment_append_count", Listener._increment_append_count)

            Extension._wrap(target_cls, "__init__", Listener._wrap_init)
            Extension._wrap(target_cls, 'append', Listener._wrap_append)

        def _increment_append_count(self):
            self.append_count += 1

        def _wrap_init(self, *args, **kwargs):
            Extension._set(self, "append_count", 0)
            yield

        def _wrap_append(self, *args, **kwargs):
            yield
            self.increment_append_count()

    return Listener


class TestHashlist:
    def test_error_raised_if_can_extend_returns_false(self, hashlist_cls):
        class Plus(Extension):
            @staticmethod
            def can_extend(target_cls):
                return False

            @staticmethod
            def extend(target_cls):
                pass

        pytest.raises(ValueError, hashlist_cls.with_extensions, Plus)

    def test_correct_extensions_returned(self, hashlist_cls, listener_cls):
        instance = hashlist_cls.with_extensions(listener_cls)()

        assert instance.extensions == frozenset([listener_cls])

    def test_method_correctly_bound(self, hashlist_cls, listener_cls):
        instance = hashlist_cls.with_extensions(listener_cls)()

        assert instance.append_count == 0

        instance.increment_append_count()

        assert instance.append_count == 1

    def test_listener_increments_counter_on_append(self, hashlist_cls, listener_cls):
        instance = hashlist_cls.with_extensions(listener_cls)()

        instance.append(5)
        instance.append(3)

        assert instance.append_count == 2

        instance.index(5)

        assert instance.append_count == 2

    def test_wrap_preserves_method_signature(self, hashlist_cls):
        def dummy_method(self, arg_1, arg_2, kwarg_1=1, kwarg_2=2):
            pass

        def dummy_wrapper(self, *args, **kwargs):
            yield

        class Plus(Extension):
            @staticmethod
            def can_extend(target_cls):
                return True

            @staticmethod
            def extend(target_cls):
                target_cls.method = dummy_method
                Extension._wrap(target_cls, "method", dummy_wrapper)

        instance = hashlist_cls.with_extensions(Plus)()

        expected_spec = getfullargspec(dummy_method)
        actual_spec = getfullargspec(instance.method)

        assert actual_spec is not expected_spec
        assert actual_spec == expected_spec

    def test_set_duplicate_attribute_raises_error(self, hashlist_cls, listener_cls):
        class Conflict(Extension):
            @staticmethod
            def can_extend(target_cls):
                return True

            @staticmethod
            def extend(target_cls):
                Extension._wrap(target_cls, "__init__", Conflict._wrap_init)

            def _wrap_init(self, *args, **kwargs):
                Extension._set(self, "append_count", "0")
                yield

        modified_cls = hashlist_cls.with_extensions(listener_cls, Conflict)

        pytest.raises(AttributeError, modified_cls)

    def test_extendable_metadata_is_correct(self, hashlist_cls, listener_cls):
        modified_cls = hashlist_cls.with_extensions(listener_cls)
        instance = modified_cls()

        assert not hasattr(hashlist_cls, "_extensions")
        assert not hasattr(hashlist_cls, "_extension_data")

        assert modified_cls._extensions == frozenset([listener_cls])
        assert not hasattr(modified_cls, "_extension_data")

        assert instance._extensions == frozenset([listener_cls])
        assert instance._extension_data == {}
