#!/usr/bin/env python3
"""Decode unencrypted Mobipocket/AZW3 v8 HuffDic text to Markdown."""

# Standard Library
import argparse
import html.parser
import pathlib
import posixpath
import re
import struct
import zipfile

# PIP3 modules
import lxml.etree
import mobi


HUFF_COMPRESSION = 0x4448
MOBI_HEADER_OFFSET = 16
MOBI_HUFF_RECORD_OFFSET = 0x60
MOBI_HUFF_RECORD_COUNT = 0x64
MOBI_TITLE_OFFSET = 0x44
MOBI_TITLE_LENGTH = 0x48


#============================================
def read_u16(data: bytes, offset: int) -> int:
	"""Read one big-endian unsigned short from a validated byte range."""
	value = struct.unpack_from(">H", data, offset)[0]
	return value


#============================================
def read_u32(data: bytes, offset: int) -> int:
	"""Read one big-endian unsigned integer from a validated byte range."""
	value = struct.unpack_from(">I", data, offset)[0]
	return value


#============================================
def record_offsets(data: bytes) -> list[int]:
	"""Return the ordered Palm database record offsets."""
	if len(data) < 78:
		raise ValueError("AZW3 source is smaller than the Palm database header")
	record_count = read_u16(data, 76)
	table_end = 78 + record_count * 8
	if record_count < 2 or table_end > len(data):
		raise ValueError("AZW3 source has an invalid Palm database record table")
	offsets = [read_u32(data, 78 + index * 8) for index in range(record_count)]
	if offsets[0] < table_end or offsets[-1] >= len(data):
		raise ValueError("AZW3 source record offsets are outside the source")
	if offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
		raise ValueError("AZW3 source record offsets are not strictly ordered")
	return offsets


#============================================
def record_bytes(data: bytes, offsets: list[int], index: int) -> bytes:
	"""Return one Palm database record without changing source order."""
	start = offsets[index]
	end = offsets[index + 1] if index + 1 < len(offsets) else len(data)
	record = data[start:end]
	return record


#============================================
class HuffDicReader:
	"""Decode the HUFF/CDIC records used by unencrypted Mobipocket text."""

	def __init__(self, huff_record: bytes, cdic_records: list[bytes]) -> None:
		"""Load the source's HUFF code tables and ordered CDIC phrases."""
		if huff_record[:8] != b"HUFF\x00\x00\x00\x18":
			raise ValueError("AZW3 source does not contain a supported HUFF header")
		off1 = read_u32(huff_record, 8)
		off2 = read_u32(huff_record, 12)
		if off1 + 1024 > len(huff_record) or off2 + 256 > len(huff_record):
			raise ValueError("AZW3 source HUFF table is truncated")
		self.dict1 = [self.decode_dict1(value) for value in struct.unpack_from(">256I", huff_record, off1)]
		dict2 = struct.unpack_from(">64I", huff_record, off2)
		self.mincode = [0]
		self.maxcode = [0]
		for code_length, mincode in enumerate(dict2[0::2], start=1):
			self.mincode.append(mincode << (32 - code_length))
		for code_length, maxcode in enumerate(dict2[1::2], start=1):
			self.maxcode.append(((maxcode + 1) << (32 - code_length)) - 1)
		self.dictionary: list[tuple[bytes, bool] | None] = []
		for cdic_record in cdic_records:
			self.load_cdic(cdic_record)

	#============================================
	def decode_dict1(self, value: int) -> tuple[int, bool, int]:
		"""Convert one compact HUFF lookup entry to a decoder tuple."""
		code_length = value & 0x1F
		terminated = bool(value & 0x80)
		maximum = value >> 8
		if code_length == 0:
			raise ValueError("AZW3 source HUFF table contains a zero-length code")
		if code_length <= 8 and not terminated:
			raise ValueError("AZW3 source HUFF table has an incomplete short code")
		maximum = ((maximum + 1) << (32 - code_length)) - 1
		result = (code_length, terminated, maximum)
		return result

	#============================================
	def load_cdic(self, cdic_record: bytes) -> None:
		"""Load one CDIC phrase table in its source-defined order."""
		if cdic_record[:8] != b"CDIC\x00\x00\x00\x10":
			raise ValueError("AZW3 source does not contain a supported CDIC header")
		phrase_count = read_u32(cdic_record, 8)
		bit_count = read_u32(cdic_record, 12)
		available = phrase_count - len(self.dictionary)
		if available < 0:
			raise ValueError("AZW3 source CDIC phrase count is inconsistent")
		phrase_limit = min(1 << bit_count, available)
		entry_table_end = 16 + phrase_limit * 2
		if entry_table_end > len(cdic_record):
			raise ValueError("AZW3 source CDIC entry table is truncated")
		for entry_index in range(phrase_limit):
			offset = read_u16(cdic_record, 16 + entry_index * 2)
			if offset + 2 > len(cdic_record):
				raise ValueError("AZW3 source CDIC phrase offset is outside its record")
			phrase_length = read_u16(cdic_record, 16 + offset)
			phrase_end = 18 + offset + (phrase_length & 0x7FFF)
			if phrase_end > len(cdic_record):
				raise ValueError("AZW3 source CDIC phrase is truncated")
			phrase = cdic_record[18 + offset:phrase_end]
			self.dictionary.append((phrase, bool(phrase_length & 0x8000)))

	#============================================
	def unpack(self, packed: bytes) -> bytes:
		"""Decode one source text record using the loaded HUFF/CDIC tables."""
		bits_left = len(packed) * 8
		data = packed + b"\x00\x00\x00\x00\x00\x00\x00\x00"
		position = 0
		window = struct.unpack_from(">Q", data, position)[0]
		bits_available = 32
		result = bytearray()
		while True:
			if bits_available <= 0:
				position += 4
				window = struct.unpack_from(">Q", data, position)[0]
				bits_available += 32
			code = (window >> bits_available) & 0xFFFFFFFF
			code_length, terminated, maximum = self.dict1[code >> 24]
			if not terminated:
				while code < self.mincode[code_length]:
					code_length += 1
				if code_length >= len(self.maxcode):
					raise ValueError("AZW3 source HUFF code exceeds its declared table")
				maximum = self.maxcode[code_length]
			bits_available -= code_length
			bits_left -= code_length
			if bits_left < 0:
				break
			phrase_index = (maximum - code) >> (32 - code_length)
			if phrase_index >= len(self.dictionary):
				raise ValueError("AZW3 source HUFF code references an absent CDIC phrase")
			phrase_entry = self.dictionary[phrase_index]
			if phrase_entry is None:
				raise ValueError("AZW3 source HUFF phrase recursion is circular")
			phrase, complete = phrase_entry
			if not complete:
				self.dictionary[phrase_index] = None
				phrase = self.unpack(phrase)
				self.dictionary[phrase_index] = (phrase, True)
			result.extend(phrase)
		decoded = bytes(result)
		return decoded


#============================================
def huffdic_header(source_path: pathlib.Path) -> tuple[bytes, bytes, list[int], int]:
	"""Load the source header and validate its supported unencrypted HuffDic contract."""
	data = source_path.read_bytes()
	offsets = record_offsets(data)
	header = record_bytes(data, offsets, 0)
	if header[MOBI_HEADER_OFFSET:MOBI_HEADER_OFFSET + 4] != b"MOBI":
		raise ValueError("source is not a Mobipocket/AZW3 document")
	if read_u32(header, MOBI_HEADER_OFFSET + 20) != 8:
		raise ValueError("only Mobipocket/AZW3 version 8 is supported")
	if read_u16(header, 0) != HUFF_COMPRESSION:
		raise ValueError("only Mobipocket HuffDic text is supported")
	if read_u16(header, 12) != 0:
		raise ValueError("encrypted Mobipocket/AZW3 text is not supported")
	declared_bytes = read_u32(header, 4)
	if declared_bytes == 0:
		raise ValueError("AZW3 source declares zero PalmDOC text bytes")
	result = (data, header, offsets, declared_bytes)
	return result


#============================================
def extract_huffdic_bytes(source_path: pathlib.Path) -> bytes:
	"""Decode native HuffDic records only when their bytes match PalmDOC framing."""
	data, header, offsets, declared_bytes = huffdic_header(source_path)
	text_record_count = read_u16(header, 8)
	huff_record_index = read_u32(header, MOBI_HEADER_OFFSET + MOBI_HUFF_RECORD_OFFSET)
	huff_record_count = read_u32(header, MOBI_HEADER_OFFSET + MOBI_HUFF_RECORD_COUNT)
	if text_record_count + 1 > len(offsets):
		raise ValueError("AZW3 source text record count exceeds its record table")
	if huff_record_count < 2 or huff_record_index + huff_record_count > len(offsets):
		raise ValueError("AZW3 source does not declare usable HuffDic records")
	huff_record = record_bytes(data, offsets, huff_record_index)
	cdic_records = [
		record_bytes(data, offsets, huff_record_index + index)
		for index in range(1, huff_record_count)
	]
	decoder = HuffDicReader(huff_record, cdic_records)
	chunks = [decoder.unpack(record_bytes(data, offsets, index)) for index in range(1, text_record_count + 1)]
	decoded = b"".join(chunks)
	if len(decoded) > declared_bytes:
		raise ValueError("AZW3 HuffDic output exceeds PalmDOC declared text bytes")
	if len(decoded) < declared_bytes:
		raise ValueError("AZW3 HuffDic output is shorter than PalmDOC declared text bytes")
	return decoded


#============================================
def xml_local_name(tag: str | object) -> str:
	"""Return a namespace-free element name or an empty non-element sentinel."""
	if not isinstance(tag, str):
		return ""
	name = tag.rsplit("}", 1)[-1]
	return name


#============================================
def epub_spine_html(epub_path: pathlib.Path) -> str:
	"""Return body XHTML in the source EPUB's declared reading order."""
	with zipfile.ZipFile(epub_path) as archive:
		container = lxml.etree.fromstring(archive.read("META-INF/container.xml"))
		rootfile = next(
			element for element in container.iter()
			if xml_local_name(element.tag) == "rootfile"
		)
		opf_path = rootfile.attrib["full-path"]
		opf_root = lxml.etree.fromstring(archive.read(opf_path))
		manifest = {
			element.attrib["id"]: posixpath.normpath(
				posixpath.join(posixpath.dirname(opf_path), element.attrib["href"].split("#", 1)[0])
			)
			for element in opf_root.iter()
			if xml_local_name(element.tag) == "item"
		}
		spine = [
			manifest[element.attrib["idref"]]
			for element in opf_root.iter()
			if xml_local_name(element.tag) == "itemref"
		]
		bodies = []
		for path in spine:
			root = lxml.etree.fromstring(archive.read(path))
			body = next(
				element for element in root.iter()
				if xml_local_name(element.tag) == "body"
			)
			bodies.append(lxml.etree.tostring(body, encoding="unicode"))
	html_text = "<html><body>" + "\n".join(bodies) + "</body></html>"
	return html_text


#============================================
def extract_azw3_text(source_path: pathlib.Path) -> str:
	"""Recover ordered reading XHTML with the installed Mobipocket decoder."""
	huffdic_header(source_path)
	_temporary_root, extracted_epub = mobi.extract(str(source_path))
	text = epub_spine_html(pathlib.Path(extracted_epub))
	if "\ufffd" in text:
		raise ValueError("mobi EPUB recovery contains a replacement marker")
	return text


#============================================
def extract_azw3_title(source_path: pathlib.Path) -> str:
	"""Read the source-declared Mobipocket title from its header record."""
	data = source_path.read_bytes()
	offsets = record_offsets(data)
	header = record_bytes(data, offsets, 0)
	if header[MOBI_HEADER_OFFSET:MOBI_HEADER_OFFSET + 4] != b"MOBI":
		raise ValueError("source is not a Mobipocket/AZW3 document")
	title_offset = read_u32(header, MOBI_HEADER_OFFSET + MOBI_TITLE_OFFSET)
	title_length = read_u32(header, MOBI_HEADER_OFFSET + MOBI_TITLE_LENGTH)
	title_end = title_offset + title_length
	if title_length == 0 or title_end > len(header):
		raise ValueError("AZW3 source has no usable title in its header")
	title = header[title_offset:title_end].decode("utf-8", errors="replace").strip()
	return title


#============================================
class MarkdownRenderer(html.parser.HTMLParser):
	"""Render the simple inline and block markup emitted by Mobipocket text records."""

	def __init__(self) -> None:
		"""Initialize an entity-aware source-order HTML renderer."""
		super().__init__(convert_charrefs=True)
		self.pieces: list[str] = []
		self.heading_level: int | None = None
		self.excluded_depth = 0

	#============================================
	def block_break(self) -> None:
		"""Separate source block elements without adding repeated blank lines."""
		if not self.pieces or self.pieces[-1].endswith("\n\n"):
			return
		self.pieces.append("\n\n")

	#============================================
	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		"""Render source markup that carries block or inline text meaning."""
		if tag in {"head", "script", "style"}:
			self.excluded_depth += 1
			return
		if self.excluded_depth:
			return
		if tag in {"p", "div", "section", "article", "blockquote", "pre", "table", "tr"}:
			self.block_break()
		elif tag == "br":
			self.pieces.append("\n")
		elif tag == "hr":
			self.block_break()
			self.pieces.append("---\n\n")
		elif tag == "li":
			self.block_break()
			self.pieces.append("- ")
		elif tag in {"b", "strong"}:
			self.pieces.append("**")
		elif tag in {"i", "em"}:
			self.pieces.append("_")
		elif re.fullmatch(r"h[1-6]", tag):
			self.block_break()
			source_level = int(tag[1])
			self.heading_level = source_level + 1 if source_level == 1 else source_level
			self.pieces.append("#" * self.heading_level + " ")
		elif tag == "img":
			for name, value in attrs:
				if name.lower() == "alt" and value:
					self.pieces.append("[Image: " + value + "]")

	#============================================
	def handle_endtag(self, tag: str) -> None:
		"""Close source markup that has a Markdown representation."""
		if tag in {"head", "script", "style"}:
			self.excluded_depth -= 1
			return
		if self.excluded_depth:
			return
		if tag in {"p", "div", "section", "article", "blockquote", "pre", "table", "tr", "li"}:
			self.block_break()
		elif tag in {"b", "strong"}:
			self.pieces.append("**")
		elif tag in {"i", "em"}:
			self.pieces.append("_")
		elif re.fullmatch(r"h[1-6]", tag):
			self.heading_level = None
			self.block_break()

	#============================================
	def handle_data(self, data: str) -> None:
		"""Preserve source-visible text in the order received from the source."""
		if self.excluded_depth:
			return
		self.pieces.append(data)


#============================================
def join_numbered_headings(markdown: str) -> str:
	"""Join a source-visible chapter number with its immediately following heading."""
	pattern = re.compile(r"\n\n([1-9][0-9]{0,2})\n\n## (.+?)(?=\n)")
	joined = pattern.sub(r"\n\n## \1 \2", markdown)
	return joined


#============================================
def html_to_markdown(text: str, title: str) -> str:
	"""Convert source HTML text to compact ASCII Markdown without reordering content."""
	renderer = MarkdownRenderer()
	renderer.feed(text)
	renderer.close()
	markdown = "# " + title + "\n\n" + "".join(renderer.pieces)
	markdown = re.sub(r"[ 	]+\n", "\n", markdown)
	markdown = re.sub(r"\n[ 	]+", "\n", markdown)
	markdown = re.sub(r"\n{3,}", "\n\n", markdown)
	markdown = join_numbered_headings(markdown)
	markdown = markdown.encode("ascii", "xmlcharrefreplace").decode("ascii")
	markdown = markdown.strip() + "\n"
	return markdown


#============================================
def extract_azw3_markdown(source_path: pathlib.Path) -> str:
	"""Return one title-normalized Markdown rendition of the exact source."""
	title = extract_azw3_title(source_path)
	text = extract_azw3_text(source_path)
	markdown = html_to_markdown(text, title)
	return markdown


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse input and output paths for AZW3 source conversion."""
	parser = argparse.ArgumentParser(description="Decode unencrypted AZW3 v8 HuffDic text to Markdown")
	parser.add_argument("input", help="Input AZW3 file")
	parser.add_argument("-o", "--output", dest="output_file", required=True, help="Output Markdown path")
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""Decode one source and write its source-order Markdown rendition."""
	args = parse_args()
	source_path = pathlib.Path(args.input)
	output_path = pathlib.Path(args.output_file)
	markdown = extract_azw3_markdown(source_path)
	output_path.write_text(markdown, encoding="utf-8")
	print(f"Wrote {output_path} from {source_path}")


#============================================
if __name__ == "__main__":
	main()
