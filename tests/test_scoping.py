from pathlib import Path

import pytest
import yaml

from complyscope.scoping import OutOfScopeError, ScopeError, load_scope

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml"


@pytest.fixture
def write_scope(tmp_path):
    """Write a scope file from the example, with selected keys replaced or removed."""

    def _write(**changes):
        data = yaml.safe_load(EXAMPLE.read_text())
        for key, value in changes.items():
            if value is None:
                data.pop(key)
            else:
                data[key] = value
        path = tmp_path / "scope.yaml"
        path.write_text(yaml.safe_dump(data))
        return path

    return _write


def authorisation(**overrides):
    data = {"confirmed": True, "confirmed_by": "Jane Doe", "confirmed_on": "2026-11-01"}
    data.update(overrides)
    return data


def test_example_scope_loads_with_normalised_hosts():
    scope = load_scope(EXAMPLE)

    assert scope.organisation == "Acme Ltd (fictional)"
    assert scope.hosts == ("localhost", "127.0.0.1", "app.example.test")


def test_missing_authorisation_is_rejected(write_scope):
    with pytest.raises(ScopeError, match="authorisation"):
        load_scope(write_scope(authorisation=None))


def test_unconfirmed_authorisation_is_rejected(write_scope):
    with pytest.raises(ScopeError, match="confirmed"):
        load_scope(write_scope(authorisation=authorisation(confirmed=False)))


def test_authorisation_dated_in_the_future_is_rejected(write_scope):
    with pytest.raises(ScopeError, match="future"):
        load_scope(write_scope(authorisation=authorisation(confirmed_on="2999-01-01")))


def test_scope_needs_at_least_one_target(write_scope):
    with pytest.raises(ScopeError, match="targets"):
        load_scope(write_scope(targets=[]))


@pytest.mark.parametrize(
    "host",
    [
        "https://app.example.test",  # URL, not a host
        "10.0.0.0/24",  # ranges are deliberately not supported
        "*.example.test",  # wildcards could match hosts nobody authorised
        "app.example.test:8443",  # ports are chosen by the checks
        "exa mple.test",
        "",
    ],
)
def test_invalid_hosts_are_rejected(write_scope, host):
    with pytest.raises(ScopeError, match="host"):
        load_scope(write_scope(targets=[{"host": host}]))


def test_duplicate_hosts_after_normalisation_are_rejected(write_scope):
    targets = [{"host": "App.Example.Test"}, {"host": "app.example.test."}]

    with pytest.raises(ScopeError, match="duplicate.*app.example.test"):
        load_scope(write_scope(targets=targets))


def test_ipv6_hosts_are_normalised(write_scope):
    scope = load_scope(write_scope(targets=[{"host": "2001:DB8:0:0::1"}]))

    assert scope.hosts == ("2001:db8::1",)


def test_ensure_in_scope_accepts_equivalent_spellings():
    scope = load_scope(EXAMPLE)

    assert scope.ensure_in_scope("APP.example.test.") == "app.example.test"


@pytest.mark.parametrize(
    "host", ["www.app.example.test", "example.test", "192.0.2.10", "not a host"]
)
def test_ensure_in_scope_refuses_anything_not_listed(host):
    scope = load_scope(EXAMPLE)

    with pytest.raises(OutOfScopeError, match="not in scope"):
        scope.ensure_in_scope(host)


def test_scope_file_must_be_a_mapping(tmp_path):
    path = tmp_path / "scope.yaml"
    path.write_text("- localhost\n")

    with pytest.raises(ScopeError, match="scope.yaml"):
        load_scope(path)


def test_missing_scope_file_is_reported(tmp_path):
    with pytest.raises(ScopeError, match="not found"):
        load_scope(tmp_path / "scope.yaml")


def test_yaml_tags_that_construct_python_objects_are_refused(tmp_path):
    path = tmp_path / "scope.yaml"
    path.write_text("organisation: !!python/object/apply:os.system ['echo pwned']\n")

    with pytest.raises(ScopeError, match="invalid YAML"):
        load_scope(path)
