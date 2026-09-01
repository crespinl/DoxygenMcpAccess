# Copyright (c) 2026 Louis Crespin
# MIT License

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from fastmcp import FastMCP

XML_DIR = Path(os.environ.get("DOXYGEN_XML_DIR", "./xml"))

# Name of the library being documented, to be used in tool names and descriptions
LIBRARY_NAME = os.environ.get("LIBRARY_NAME", "external-library")

mcp = FastMCP(f"docs-{LIBRARY_NAME}")


# --------------------------------------------------------------------------
# Indexation
# --------------------------------------------------------------------------

class MemberParam(TypedDict):
    type: str
    name: str

class MemberValue(TypedDict):
    name: str
    initializer: str
    brief: str

class MemberDoc(TypedDict, total=False):
    signature: str
    brief: str
    detailed: str
    params: list[MemberParam]
    values: list[MemberValue]
    enum: str
    initializer: str
    error: str

class CompoundMember(TypedDict, total=False):
    name: str
    kind: str
    signature: str
    values: list[str]

class CompoundDoc(TypedDict, total=False):
    name: str
    kind: str
    brief: str
    detailed: str
    members: list[CompoundMember]
    error: str

@dataclass
class SymbolEntry:
    name: str                 # qualified name, ex: MyNamespace::MyClass::doThing
    kind: str                 # class, struct, namespace, file, function, variable...
    refid: str                # id doxygen, for retrieving the source XML file
    compound_file: str        # XML file of the "compound" parent (class/file)
    member_id: str = ""       # anchor of the member if it's a method/variable
    brief: str = ""


_index: dict[str, list[SymbolEntry]] = {}


def _text_of(elem: ET.Element | None) -> str:
    """Concatenates the text of a doxygen XML node (description) into plain text."""
    if elem is None:
        return ""
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def _load_index() -> None:
    """Parses index.xml to build a name -> SymbolEntry index."""
    index_file = XML_DIR / "index.xml"
    if not index_file.exists():
        raise FileNotFoundError(
            f"index.xml not found in {XML_DIR}. Check DOXYGEN_XML_DIR and that GENERATE_XML=YES has run."
        )

    root = ET.parse(index_file).getroot()

    for compound in root.findall("compound"):
        refid = str(compound.get("refid"))
        kind = str(compound.get("kind"))
        name_elem = compound.find("name")
        compound_name = str(name_elem.text if name_elem is not None else refid)

        _index.setdefault(compound_name, []).append(
            SymbolEntry(
                name=compound_name,
                kind=kind,
                refid=refid,
                compound_file=f"{refid}.xml",
            )
        )

        # members (functions, variables, enums...) declared in this compound
        for member in compound.findall("member"):
            m_kind = str(member.get("kind"))
            m_refid = str(member.get("refid"))
            m_name_elem = member.find("name")
            m_name = str(m_name_elem.text if m_name_elem is not None else m_refid)
            qualified = f"{compound_name}::{m_name}"

            _index.setdefault(qualified, []).append(
                SymbolEntry(
                    name=qualified,
                    kind=m_kind,
                    refid=m_refid,
                    compound_file=f"{refid}.xml",
                    member_id=m_refid,
                )
            )
            # also allow lookup by short name (without namespace/class)
            _index.setdefault(m_name, []).append(_index[qualified][-1])


def _get_index() -> dict[str, list[SymbolEntry]]:
    if not _index:
        _load_index()
    return _index


# --------------------------------------------------------------------------
# Detailed extraction of member documentation from a compound XML file
# --------------------------------------------------------------------------

def _extract_member_doc(compound_xml_path: Path, member_refid: str) -> MemberDoc:
    root = ET.parse(compound_xml_path).getroot()
    for member in root.iter("memberdef"):
        if member.get("id") == member_refid:
            name = _text_of(member.find("name"))
            args = _text_of(member.find("argsstring"))
            ret_type = _text_of(member.find("type"))
            brief = _text_of(member.find("briefdescription"))
            detailed = _text_of(member.find("detaileddescription"))

            params: list[MemberParam] = []
            for param in member.findall("param"):
                params.append({
                    "type": _text_of(param.find("type")),
                    "name": _text_of(param.find("declname")),
                })

            result: MemberDoc = {
                "signature": f"{ret_type} {name}{args}".strip(),
                "brief": brief,
                "detailed": detailed,
                "params": params,
            }

            if member.get("kind") == "enum":
                result["values"] = [
                    {
                        "name": _text_of(ev.find("name")),
                        "initializer": _text_of(ev.find("initializer")),
                        "brief": _text_of(ev.find("briefdescription")),
                    }
                    for ev in member.findall("enumvalue")
                ]
            return result

        if member.get("kind") == "enum":
            for enumvalue in member.findall("enumvalue"):
                if enumvalue.get("id") == member_refid:
                    return {
                        "signature": _text_of(enumvalue.find("name")),
                        "enum": _text_of(member.find("name")),
                        "initializer": _text_of(enumvalue.find("initializer")),
                        "brief": _text_of(enumvalue.find("briefdescription")),
                        "detailed": _text_of(enumvalue.find("detaileddescription")),
                        "params": [],
                    }

    return {"error": f"Member {member_refid} not found in {compound_xml_path.name}"}


def _extract_compound_doc(compound_xml_path: Path) -> CompoundDoc:
    root = ET.parse(compound_xml_path).getroot()
    compounddef = root.find("compounddef")
    if compounddef is None:
        return {"error": "compounddef not found"}

    name = _text_of(compounddef.find("compoundname"))
    brief = _text_of(compounddef.find("briefdescription"))
    detailed = _text_of(compounddef.find("detaileddescription"))

    members: list[CompoundMember] = []
    for member in compounddef.iter("memberdef"):
        entry: CompoundMember = {
            "name": _text_of(member.find("name")),
            "kind": str(member.get("kind", "")),
            "signature": f"{_text_of(member.find('type'))} {_text_of(member.find('name'))} {_text_of(member.find('argsstring'))}".strip(),
        }
        if member.get("kind") == "enum":
            entry["values"] = [_text_of(ev.find("name")) for ev in member.findall("enumvalue")]

        members.append(entry)

    return {
        "name": name,
        "kind": str(compounddef.get("kind", "")),
        "brief": brief,
        "detailed": detailed,
        "members": members,
    }


# --------------------------------------------------------------------------
# MCP Tools
# --------------------------------------------------------------------------

@mcp.tool(name=f"search_symbols_in_{LIBRARY_NAME}")
def search_symbols(query: str, limit: int = 20) -> list[dict[str, str]]:
    """
    Search the library's EXTERNAL DOCUMENTATION
    (generated by Doxygen, independent of the current project's
    code) for classes, functions, variables, namespaces, etc., whose names
    contain `query` (case-insensitive). DO NOT search the
    files of the project you are currently working on—use
    the usual code search tools for that.
    Returns the qualified name + type, without detailed content (use
    `get_doc_from_{LIBRARY_NAME}` next).
    """
    index = _get_index()
    q = query.lower()
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for name, entries in index.items():
        if q in name.lower() and name not in seen:
            seen.add(name)
            entry = entries[0]
            results.append({"name": name, "kind": entry.kind})
            if len(results) >= limit:
                break
    return results


@mcp.tool(name=f"get_doc_from_{LIBRARY_NAME}")
def get_symbol_doc(name: str) -> MemberDoc | CompoundDoc:
    """
    Returns the complete documentation for a symbol in the
    library (class, function, variable, etc.):
    signature, short and detailed descriptions, and parameters. This documentation comes
    from the library, not the current project.
    `name` can be the qualified name (e.g., MyClass::doThing) or the short name.
    """
    index = _get_index()
    entries = index.get(name)
    if not entries:
        return {"error": f"Symbol '{name}' not found. Use search_symbols first."}

    entry = entries[0]
    compound_path = XML_DIR / entry.compound_file
    if not compound_path.exists():
        return {"error": f"XML file {entry.compound_file} not found"}

    if entry.member_id:
        return _extract_member_doc(compound_path, entry.member_id)
    return _extract_compound_doc(compound_path)


@mcp.tool(name=f"list_members_in_{LIBRARY_NAME}")
def list_class_members(class_name: str) -> dict[str, str | list[CompoundMember]]:
    """
    Lists the members (methods, attributes, enums) of a class/struct/namespace
    in the library, along with their signatures, without
    detailed descriptions (to get those, use `get_doc_from_{LIBRARY_NAME}` on
    the specific member).
    """
    doc = get_symbol_doc(class_name)
    if "error" in doc:
        return {"error": doc["error"]}
    if "name" in doc:
        return {"class": doc["name"], "members": doc.get("members", [])}
    return {"error": "Unexpected documentation format"}



if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9000)
