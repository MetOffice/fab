from fabengine.configuration_tools import WriteOnceDict
from pytest import fixture, raises


class TestConfigurationTools:
    @fixture
    def original_write_once_dict(self) -> WriteOnceDict:
        return WriteOnceDict({"key1": "item"})

    @fixture
    def updated_write_once_dict(self) -> WriteOnceDict:
        return WriteOnceDict({"key1": "item", "key2": "new_item"})

    def test_write_once_dict(
        self,
        original_write_once_dict: WriteOnceDict,
        updated_write_once_dict: WriteOnceDict,
    ):
        # Check raise error on overriding existing data
        with raises(KeyError):
            original_write_once_dict["key1"] = "new_item"
        # Check raise error on del key
        with raises(KeyError):
            del original_write_once_dict["key1"]

        # Update the dict normally
        original_write_once_dict["key2"] = "new_item"
        assert original_write_once_dict == updated_write_once_dict
