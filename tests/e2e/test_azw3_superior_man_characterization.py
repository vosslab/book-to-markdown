#!/usr/bin/env python3
"""Characterize ordered plaintext recovery from the assigned AZW3 source."""

# Standard Library
import hashlib
import pathlib
import sys


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXTRACT_ROOT = REPOSITORY_ROOT / "extract"
SOURCE_PATH = pathlib.Path(
	"/home/vosslab/BOOKS_to_CONVERT/Sept_12/relationships_sexuality/"
	"The_Way_of_the_Superior_Man_by_David_Deida.azw3"
)
SOURCE_SHA256 = "fff7e8e0efdea69eea21912bd79d2d57894e62c4eabdca58a3145f24bf02e027"

sys.path.insert(0, str(EXTRACT_ROOT))
import azw3_to_markdown


#============================================
def main() -> None:
	"""Verify that the exact AZW3 source decodes to ordered readable text."""
	source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
	assert source_hash == SOURCE_SHA256
	text = azw3_to_markdown.extract_azw3_text(SOURCE_PATH)
	assert "The Way of the Superior Man" in text
	assert text.index("PART TWO: Dealing With Women") < text.index("PART SEVEN: Body Practices")
	markdown = azw3_to_markdown.extract_azw3_markdown(SOURCE_PATH)
	assert markdown.startswith("# The Way of the Superior Man\n")
	assert "\n## Cover\n" in markdown
	assert "\n## 1 Stop Hoping for a Completion of Anything in Life\n" in markdown
	assert "\n\n1\n\n## Stop Hoping for a Completion of Anything in Life\n" not in markdown


#============================================
if __name__ == "__main__":
	main()
