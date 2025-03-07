from edge_containers_cli.utils import YamlFile


def test_yaml_processor_get(data):
    processor = YamlFile(data / "yaml.yaml")
    expect_0 = {
        "trunk_A.branch_A.leaf_A": 0,
        "trunk_A.branch_A.leaf_B": "zero",
        "trunk_A.branch_B.non_existing": None,
        "trunk_B.leaf_A": False,
        "leaf_A": "False",
    }
    for key_0 in expect_0:
        get = processor.get_key(key_0)
        expect = expect_0[key_0]
        assert get == expect, f"The value of {key_0} is unexpected"
        assert type(get) is type(expect), f"The type of {key_0} is unexpected"


def test_yaml_processor_set(data):
    processor = YamlFile(data / "yaml.yaml")
    expect_1 = {
        "trunk_A.branch_A.leaf_A": 1,
        "trunk_A.branch_A.leaf_B": "one",
        "trunk_B.leaf_A": True,
        "trunk_B.leaf_C": True,  # insertion into existing key
        "leaf_A": "True",
        "trunk_A.branch_B.something_new": False,  # insertion into empty key
    }
    for key_1 in expect_1:
        processor.set_key(key_1, expect_1[key_1])
        get = processor.get_key(key_1)
        expect = expect_1[key_1]
        assert get == expect, f"The value of {key_1} is unexpected"
        assert type(get) is type(expect), f"The type of {key_1} is unexpected"
