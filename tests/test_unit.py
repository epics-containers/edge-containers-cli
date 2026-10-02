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


def test_yaml_processor_set_unquoted_float_pin_with_incompatible_string(tmp_path):
    # A hand-edited `targetRevision: 1.0` parses as a YAML float. Setting a
    # new value that isn't itself a valid float (e.g. the next patch
    # version "1.0.1") must not coerce the new value through the old
    # scalar's type - versions are always written as plain strings.
    values_file = tmp_path / "values.yaml"
    values_file.write_text("services:\n  svc:\n    targetRevision: 1.0\n")
    processor = YamlFile(values_file)

    processor.set_key("services.svc.targetRevision", "1.0.1")

    assert processor.get_key("services.svc.targetRevision") == "1.0.1"
    processor.dump_file()
    assert "1.0.1" in values_file.read_text()


def test_yaml_processor_set_unquoted_float_pin_with_same_looking_string(tmp_path):
    # Same shape, but the new value happens to be valid float syntax too
    # ("2.0") - it must still land as a string, not be coerced back into a
    # float (which would silently reintroduce the unquoted float pin).
    values_file = tmp_path / "values.yaml"
    values_file.write_text("services:\n  svc:\n    targetRevision: 1.0\n")
    processor = YamlFile(values_file)

    processor.set_key("services.svc.targetRevision", "2.0")

    assert processor.get_key("services.svc.targetRevision") == "2.0"
    assert type(processor.get_key("services.svc.targetRevision")) is str


def test_yaml_processor_set_new_key_moves_trailing_comment_past_it(tmp_path):
    # ruamel attaches a comment between two sibling mapping entries (here,
    # between "svc" and "next-svc") as the comment following "svc"'s last
    # existing key. Adding a brand-new key to "svc" (e.g. `ec stop
    # --commit` setting `enabled` for the first time) must not leave that
    # comment sitting between the old last key and the new one - it
    # belongs after "svc" altogether, introducing "next-svc".
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  svc:\n"
        "    group: foo\n"
        "  # svc stopped by fred\n"
        "  next-svc:\n"
        "    group: bar\n"
    )
    processor = YamlFile(values_file)

    processor.set_key("services.svc.enabled", False)
    processor.dump_file()

    assert values_file.read_text() == (
        "services:\n"
        "  svc:\n"
        "    group: foo\n"
        "    enabled: false\n"
        "  # svc stopped by fred\n"
        "  next-svc:\n"
        "    group: bar\n"
    )


def test_yaml_processor_set_new_key_keeps_end_of_line_comment_in_place(tmp_path):
    # An end-of-line comment on the last key of the mapping gaining a new
    # key belongs to that line: it stays there, and only the comment lines
    # that follow it move past the new key.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  svc:\n"
        "    description: camera  # Manta G-235\n"
        "  # svc stopped by fred\n"
        "  next-svc:\n"
        "    group: bar\n"
        "  other-svc:\n"
        "    group: baz  # last line\n"
    )
    processor = YamlFile(values_file)

    processor.set_key("services.svc.enabled", False)
    processor.set_key("services.other-svc.enabled", False)
    processor.dump_file()

    assert values_file.read_text() == (
        "services:\n"
        "  svc:\n"
        "    description: camera  # Manta G-235\n"
        "    enabled: false\n"
        "  # svc stopped by fred\n"
        "  next-svc:\n"
        "    group: bar\n"
        "  other-svc:\n"
        "    group: baz  # last line\n"
        "    enabled: false\n"
    )


def test_yaml_processor_set_bool_over_quoted_string_writes_bool(tmp_path):
    # `enabled: "true"` is a string; setting it to False must write a real
    # boolean - the string "False" is truthy to Helm, so the stop would do
    # nothing.
    values_file = tmp_path / "values.yaml"
    values_file.write_text('services:\n  svc:\n    enabled: "true"\n')
    processor = YamlFile(values_file)

    processor.set_key("services.svc.enabled", False)
    processor.dump_file()

    assert values_file.read_text() == "services:\n  svc:\n    enabled: false\n"


@pytest.mark.parametrize(
    "sequences",
    [
        "  paths:\n    - a\n    # b next\n    - b\n",
        "  paths:\n  - a\n  # b next\n  - b\n",
    ],
)
def test_yaml_processor_set_keeps_sequence_indentation(tmp_path, sequences):
    # A write must keep the file's own block sequence indentation, whichever
    # of the two common styles it uses.
    values_file = tmp_path / "values.yaml"
    text = f"global:\n{sequences}services:\n  svc:\n    group: foo\n"
    values_file.write_text(text)
    processor = YamlFile(values_file)

    processor.set_key("services.svc.group", "bar")
    processor.dump_file()

    assert values_file.read_text() == text.replace("group: foo", "group: bar")


def test_yaml_processor_set_preserves_existing_quote_style(tmp_path):
    # A value quoted in the source file (e.g. `targetRevision: "main"`)
    # must stay quoted on a rewrite that doesn't touch it, not be dropped
    # to plain style just because another key in the same file was set.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        'services:\n  svc:\n    targetRevision: "main"\n    other: unquoted\n'
    )
    processor = YamlFile(values_file)

    processor.set_key("services.svc.other", "changed")
    processor.dump_file()

    assert values_file.read_text() == (
        'services:\n  svc:\n    targetRevision: "main"\n    other: changed\n'
    )


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
