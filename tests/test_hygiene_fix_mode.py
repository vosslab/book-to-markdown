"""The explicit source-fix option keeps ordinary hygiene runs read-only."""

import importlib.util
import pathlib
import sys

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
	"repository_conftest_test_module", REPOSITORY_ROOT / "tests/conftest.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class OptionRecorder:
	"""Capture the pytest option declaration without invoking private APIs."""

	def __init__(self) -> None:
		self.options: dict[str, object] = {}

	def addoption(self, *option_strings: str, **kwargs: object) -> None:
		self.options = {"option_strings": option_strings, **kwargs}


def test_hygiene_fix_requires_explicit_opt_in() -> None:
	"""The registered option disables the no-fix guard only when requested."""
	parser = OptionRecorder()
	MODULE.pytest_addoption(parser)
	assert parser.options["option_strings"] == ("--fix-repo-files",)
	assert parser.options["dest"] == "no_ascii_fix"
	assert parser.options["action"] == "store_false"
	assert parser.options["default"] is True
