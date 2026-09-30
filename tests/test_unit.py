import pytest

from edge_containers_cli.utils import YamlFile, YamlFileError


def test_yaml_processor_get(data):
    processor = YamlFile(data / "yaml.yaml")
    expect_0 = {
        "trunk_A.branch_A.leaf_A": 0,
        "trunk_A.branch_A.leaf_B": "zero",
        "trunk_A.branch_A.leaf_C": None,
        "trunk_B.leaf_A": False,
        "leaf_A": "False",
    }
    for key_0 in expect_0:
        get = processor.get_key(key_0)
        expect = expect_0[key_0]
        if expect is None:
            assert get is expect, f"The value of {key_0} is unexpected"
        else:
            assert get == expect, f"The value of {key_0} is unexpected"
        assert type(get) is type(expect), f"The type of {key_0} is unexpected"

    with pytest.raises(YamlFileError):
        processor.get_key("trunk_A.branch_A.leaf_D")


def test_yaml_processor_set(data):
    processor = YamlFile(data / "yaml.yaml")
    expect_1 = {
        "trunk_A.branch_A.leaf_A": 1,
        "trunk_A.branch_A.leaf_B": "one",
        "trunk_B.leaf_A": True,
        "trunk_B.leaf_C": True,  # insertion into existing key
        "leaf_A": "True",
        "trunk_A.branch_B.something_new": False,  # insertion into empty key
        "trunk_A.branch_B.something_empty": None,  # insertion of None
    }
    for key_1 in expect_1:
        processor.set_key(key_1, expect_1[key_1])
        get = processor.get_key(key_1)
        expect = expect_1[key_1]
        assert get == expect, f"The value of {key_1} is unexpected"
        assert type(get) is type(expect), f"The type of {key_1} is unexpected"


def test_yaml_processor_remove(data):
    processor = YamlFile(data / "yaml.yaml")
    test_key = "trunk_A.branch_A.leaf_A"
    assert processor.get_key(test_key) == 0
    processor.remove_key(test_key)
    with pytest.raises(YamlFileError):
        processor.get_key(test_key)


def test_yaml_processor_remove_missing_leaf_raises_yamlfileerror(data):
    # The leaf itself (as opposed to an intermediate mapping) not existing
    # must raise the same YamlFileError every other failure mode of
    # remove_key raises - not a bare KeyError leaking out of the `del`.
    processor = YamlFile(data / "yaml.yaml")
    with pytest.raises(YamlFileError):
        processor.remove_key("trunk_A.branch_A.leaf_D")


def test_yaml_processor_remove_leaves_empty_mapping_not_null(tmp_path):
    # A mapping whose only key gets removed must dump as `{}`, never a
    # bare `null` - Helm v4 drops keys whose value is null, so a null
    # entry would make a service disappear and Argo CD prune it
    # (edge-containers-cli#268 comment).
    values_file = tmp_path / "values.yaml"
    values_file.write_text("services:\n  svc:\n    targetRevision: old-pin\n")
    processor = YamlFile(values_file)
    processor.remove_key("services.svc.targetRevision")
    processor.dump_file()
    assert values_file.read_text() == "services:\n  svc: {}\n"
