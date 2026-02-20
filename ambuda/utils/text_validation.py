import dataclasses as dc
import re
from typing import Callable
import xml.etree.ElementTree as ET
from chanda import analyze_text
import defusedxml.ElementTree as DET
from pydantic import BaseModel, Field
from vidyut.lipi import transliterate, Scheme

import ambuda.database as db
from ambuda.utils.xml_validation import validate_tei_xml

# Whitelist of words if they exist in a line then we ignore chandas errors
CHANDAS_WHITELIST = ["उवाच"]

# pass, fail, warning


class ValidationResult(BaseModel):
    description: str = ""
    num_ok: int = 0
    num_total: int = 0
    errors: list[str] = Field(default_factory=list)

    def incr_ok(self):
        self.num_ok += 1

    def incr_total(self):
        self.num_total += 1

    def add_error(self, error: str):
        if len(self.errors) > 10:
            return
        self.errors.append(error)


class ValidationReport(BaseModel):
    results: list[ValidationResult]


@dc.dataclass
class Rule:
    desc: str
    fn: Callable
    scope: str

    def validate(self, doc: ET.Element):
        ret = self.fn(doc)
        ret.description = self.desc
        return ret


def validation_rule(desc: str, scope: str = "document"):
    def _inner(fn: Callable):
        return Rule(desc=desc, fn=fn, scope=scope)

    return _inner


def _iter_blocks(xml: ET.Element):
    for div in xml.findall("./div"):
        for block in div:
            yield block


@validation_rule(desc="Blocks have unique identifiers")
def validate_all_blocks_have_unique_n(xml: ET.Element) -> ValidationResult:
    ret = ValidationResult()
    ret.incr_total()
    seen = set()
    for block in _iter_blocks(xml):
        n = block.attrib.get("n")
        if n:
            if n in seen:
                return ret
            seen.add(n)
    ret.incr_ok()
    return ret


@validation_rule(desc="XML is well-formed")
def validate_xml_is_well_formed(xml: ET.Element) -> ValidationResult:
    ret = ValidationResult()
    for block in _iter_blocks(xml):
        ret.incr_total()
        block_results = validate_tei_xml(block)
        if block_results:
            for x in block_results:
                ret.add_error(x.message)
        elif block.tag == "lg" and len(block) == 0:
            xml_string = ET.tostring(block, encoding="unicode", method="xml")
            ret.add_error(f"Element {xml_string} has no content")
        else:
            ret.incr_ok()
    return ret


@validation_rule(desc="Sanskrit text is well-formed")
def validate_all_sanskrit_text_is_well_formed(xml: ET.Element) -> ValidationResult:
    ret = ValidationResult()
    # Sanskrit text in Devanagari is expected to match this regex.
    #
    # Unicode tables:
    # - https://www.unicode.org/charts/PDF/U0900.pdf
    # - https://www.unicode.org/charts/PDF/UA8E0.pdf
    RE_ILLEGAL = r"([^\u0900-\u097F\ua8e0-\ua8ff !,\-\.])"
    for block in xml.iter():
        ret.incr_total()
        if m := re.search(RE_ILLEGAL, block.text or ""):
            ret.add_error(
                f"oUnexpected character '{m.group(1)}' in text <{block.text or ''}>"
            )
        elif m := re.search(RE_ILLEGAL, block.tail or ""):
            ret.add_error(
                f"oUnexpected character '{m.group(1)}' in text <{block.tail or ''}>"
            )
        else:
            ret.incr_ok()
    return ret


@validation_rule(desc="Validate verse number if it exists")
def validate_verse_number_if_exists(xml: ET.Element) -> ValidationResult:
    ret = ValidationResult()
    # Captures verse numbers of the form ॥१-३॥ ॥१.३॥ ॥१-३-३॥ ॥१॥ etc.
    RE_VERSE_NUMBERS = r"॥\s*([\u0966-\u096F]+(?:[-\.]+[\u0966-\u096F]+)*)\s*॥$"
    for block in xml.findall(".//lg"):
        if (n := block.attrib.get("n", None)) is not None:
            n = n.removeprefix(block.tag)
            text = "".join(block.itertext())
            if m := re.search(RE_VERSE_NUMBERS, text):
                ret.incr_total()
                m_n = re.split(r"[-\.]", m.group(1))[-1]
                if n != transliterate(m_n, Scheme.Devanagari, Scheme.Slp1):
                    ret.add_error(
                        f"Verse number mismatch. Expected '{transliterate(n, Scheme.Slp1, Scheme.Devanagari)}' actual was <{m_n}> in text <{m.group(1)}>"
                    )
                else:
                    ret.incr_ok()
    return ret


@validation_rule(desc="Validate chandas")
def validate_chandas(xml: ET.Element) -> ValidationResult:
    ret = ValidationResult()

    for block in xml.findall(".//lg"):
        clean_text = "\n".join(block.itertext()).strip()
        results = analyze_text(clean_text, verse_mode=False, fuzzy=True)
        if len(results.result.line) > 0:
            for line in results.result.line:
                ret.incr_total()
                if line.result.found or any(
                    w in line.result.line.split() for w in CHANDAS_WHITELIST
                ):
                    ret.incr_ok()
                else:
                    ret.add_error(
                        f"No valid chandas detected for line {line.result.line}"
                    )
        else:
            ret.add_error(f"No valid chandas detected for text {clean_text}")
    return ret


def safe_parse_report(payload) -> ValidationReport | None:
    """Parse a report payload, returning None on failure."""
    try:
        return ValidationReport.model_validate(payload)
    except Exception:
        return None


RULES = [
    validate_all_blocks_have_unique_n,
    validate_xml_is_well_formed,
    validate_all_sanskrit_text_is_well_formed,
    validate_verse_number_if_exists,
    validate_chandas,
]


def validate(text: db.Text) -> ValidationReport:
    doc = ET.Element("doc")
    for section in text.sections:
        section_div = ET.SubElement(doc, "div")
        for block in section.blocks:
            el = DET.fromstring(block.xml)
            section_div.append(el)

    results = [rule.validate(doc) for rule in RULES]
    return ValidationReport(results=results)
