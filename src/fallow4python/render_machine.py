"""Machine-readable renderers: versioned JSON envelope and SARIF 2.1.0."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .model import Finding, SCHEMA_VERSION, TOOL_VERSION

_SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}


def build_json_envelope(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": report["summary"],
        "verdict": report.get("verdict"),
        "insights": [asdict(i) for i in report["insights"]],
        "metrics": [asdict(m) for m in report["_metrics"]],
        "findings": [asdict(f) for f in report["_findings"]],
    }


def _sarif_rule(f: Finding, rule_id: str) -> Dict[str, Any]:
    return {
        "id": rule_id, "name": rule_id,
        "shortDescription": {"text": f"{f.tool} {f.category}"},
        "properties": {"category": f.category, "tool": f.tool},
    }


def _sarif_location(f: Finding) -> Dict[str, Any]:
    region: Dict[str, Any] = {}
    if f.line is not None:
        region["startLine"] = f.line
    if f.column is not None:
        region["startColumn"] = f.column
    phys: Dict[str, Any] = {"artifactLocation": {"uri": f.file}}
    if region:
        phys["region"] = region
    return {"physicalLocation": phys}


def _sarif_result(f: Finding) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ruleId": f"{f.tool}/{f.rule or f.category}",
        "level": _SARIF_LEVEL.get(f.severity, "note"),
        "message": {"text": f.message},
        "properties": {"changed": f.changed, "rank": f.rank,
                       "confidence": f.confidence},
    }
    if f.file:
        result["locations"] = [_sarif_location(f)]
    return result


def build_sarif(report: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Finding] = report["_findings"]
    rules: Dict[str, Dict[str, Any]] = {}
    results: List[Dict[str, Any]] = []
    for f in findings:
        rule_id = f"{f.tool}/{f.rule or f.category}"
        rules.setdefault(rule_id, _sarif_rule(f, rule_id))
        results.append(_sarif_result(f))
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "fallow4python", "version": TOOL_VERSION,
                "informationUri": "https://example.invalid/fallow4python",
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }
