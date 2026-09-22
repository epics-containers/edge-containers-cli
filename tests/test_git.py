from pathlib import Path

import pytest

from edge_containers_cli.git import GitError, check_chart_dependency_version

DEPENDENCY = "argocd-apps"
MIN_VERSION = "5.10.0"
FEATURE = "description"


def _write_chart(chart_dir: Path, dependencies_yaml: str) -> None:
    (chart_dir / "Chart.yaml").write_text(
        "apiVersion: v2\n"
        "name: applications\n"
        "version: 0.1.1\n"
        "appVersion: '1.0'\n"
        "\n" + dependencies_yaml
    )


def _check(chart_dir: Path) -> None:
    check_chart_dependency_version(chart_dir, DEPENDENCY, MIN_VERSION, FEATURE)


def test_old_pinned_version_refused(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.7.0\n",
    )
    with pytest.raises(GitError) as exc:
        _check(tmp_path)
    message = str(exc.value)
    assert DEPENDENCY in message
    assert "5.7.0" in message  # what was found
    assert MIN_VERSION in message  # what is needed
    assert "version-only deploy" in message  # unaffected escape hatch


def test_exact_min_version_passes(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.10.0\n",
    )
    _check(tmp_path)  # must not raise


def test_newer_version_passes(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 6.0.0\n",
    )
    _check(tmp_path)  # must not raise


def test_prerelease_of_min_version_passes(tmp_path):
    # A chart maintainer testing a pre-release of the version that
    # introduces the feature must not be refused - only the release
    # segment (major.minor.patch) is compared.
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.10.0-rc1\n",
    )
    _check(tmp_path)  # must not raise


def test_missing_dependency_entry_refused(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: some-other-chart\n    version: 9.9.9\n",
    )
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_no_dependencies_list_refused(tmp_path):
    _write_chart(tmp_path, "")
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_missing_chart_yaml_refused(tmp_path):
    # No Chart.yaml at all in chart_dir.
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_file_url_dependency_refused(tmp_path):
    # A local dev checkout pinned by path rather than a released version -
    # not special-cased to auto-allow, it fails closed like any other
    # unparsable version.
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: file://../argocd-apps\n",
    )
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_range_version_refused(tmp_path):
    for range_version in ("^5.10.0", ">=5.10.0", ">=5.8.0 <6.0.0", "~5.10.0"):
        _write_chart(
            tmp_path,
            f"dependencies:\n  - name: argocd-apps\n    version: {range_version!r}\n",
        )
        with pytest.raises(GitError, match=DEPENDENCY):
            _check(tmp_path)
