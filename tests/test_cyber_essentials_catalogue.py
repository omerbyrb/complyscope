"""Sanity checks on the shipped Cyber Essentials catalogue (schema checks run on load)."""

import pytest

from complyscope.controls import FrameworkLoadError, builtin_framework_dirs, load_builtin_framework

THEME_PREFIX = {
    "firewalls": "CE-FW-",
    "secure_configuration": "CE-SC-",
    "security_update_management": "CE-SU-",
    "user_access_control": "CE-UA-",
    "malware_protection": "CE-MP-",
}


@pytest.fixture(scope="module")
def ce():
    return load_builtin_framework("cyber-essentials")


def test_cyber_essentials_is_a_builtin_framework():
    assert "cyber-essentials" in builtin_framework_dirs()


def test_catalogue_tracks_requirements_v3_3(ce):
    assert ce.version == "3.3"
    assert "v3-3" in ce.source_url


def test_catalogue_covers_all_five_themes_in_ncsc_order(ce):
    assert ce.themes == tuple(THEME_PREFIX)
    assert [c.theme for c in ce.controls] == sorted(
        (c.theme for c in ce.controls), key=list(THEME_PREFIX).index
    )
    for theme in THEME_PREFIX:
        assert any(c.theme == theme for c in ce.controls), f"no controls for {theme}"


def test_control_ids_use_their_theme_prefix(ce):
    for control in ce.controls:
        assert control.id.startswith(THEME_PREFIX[control.theme]), control.id


def test_every_control_has_a_crosswalk_to_iso_and_nist(ce):
    for control in ce.controls:
        assert set(control.crosswalk) == {"iso27001-2022", "nist-csf-2.0"}, control.id


def test_unknown_builtin_framework_lists_available_ones():
    with pytest.raises(FrameworkLoadError, match="available: cyber-essentials"):
        load_builtin_framework("pci-dss")
