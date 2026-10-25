"""
FHIRPath Query Evaluator
Inspired by @medplum/core (src/fhirpath/):

Features:
- Path navigation: Patient.name.family, Observation.valueQuantity.value
- Expression filtering: .where(path = 'value')
- Functions: .first(), .last(), .count(), .exists()
- Multi-resource querying across FHIR Bundles: Observation, Condition, Patient
"""

import re
from typing import Any, List, Optional, Union

def eval_fhirpath(expression: str, resource_or_bundle: Any) -> List[Any]:
    """
    Evaluates a FHIRPath expression against a FHIR resource or Bundle.
    Returns a list of matching values.
    """
    if not expression or not resource_or_bundle:
        return []

    # Clean expression
    expr = expression.strip()

    # If evaluating on a Bundle, handle root ResourceType navigation
    # e.g. "Observation" on Bundle -> [all Observation resources in bundle.entry]
    context: List[Any] = []
    if isinstance(resource_or_bundle, dict) and resource_or_bundle.get("resourceType") == "Bundle":
        entries = resource_or_bundle.get("entry", [])
        all_resources = [e.get("resource", {}) for e in entries if e.get("resource")]
        
        # Check if first segment is a ResourceType filter
        tokens = split_fhirpath_segments(expr)
        first_seg = tokens[0] if tokens else ""

        if any(r.get("resourceType") == first_seg for r in all_resources):
            context = [r for r in all_resources if r.get("resourceType") == first_seg]
            tokens = tokens[1:]
        elif first_seg == "Bundle":
            context = [resource_or_bundle]
            tokens = tokens[1:]
        else:
            context = [resource_or_bundle]
    elif isinstance(resource_or_bundle, list):
        context = list(resource_or_bundle)
        tokens = split_fhirpath_segments(expr)
    else:
        context = [resource_or_bundle]
        tokens = split_fhirpath_segments(expr)

    # Sequentially evaluate each segment
    for token in tokens:
        if not context:
            break
        context = eval_segment(token, context)

    return context

def split_fhirpath_segments(expr: str) -> List[str]:
    """Splits expression by dots, respecting parentheses in functions like where(...)"""
    segments = []
    current = []
    paren_depth = 0

    for ch in expr:
        if ch == '(' or ch == '[':
            paren_depth += 1
            current.append(ch)
        elif ch == ')' or ch == ']':
            paren_depth -= 1
            current.append(ch)
        elif ch == '.' and paren_depth == 0:
            if current:
                segments.append("".join(current).strip())
                current = []
        else:
            current.append(ch)

    if current:
        segments.append("".join(current).strip())

    return segments

def eval_segment(token: str, current_items: List[Any]) -> List[Any]:
    next_items = []

    # 1. Check for function calls: name(...)
    func_match = re.match(r'^([a-zA-Z0-9_]+)\((.*)\)$', token)
    if func_match:
        func_name = func_match.group(1)
        args_str = func_match.group(2).strip()

        if func_name == "where":
            return eval_where(args_str, current_items)
        elif func_name == "first":
            return current_items[:1] if current_items else []
        elif func_name == "last":
            return current_items[-1:] if current_items else []
        elif func_name == "count":
            return [len(current_items)]
        elif func_name == "exists":
            return [len(current_items) > 0]
        elif func_name == "select":
            # select(path)
            return [res for it in current_items for res in eval_fhirpath(args_str, it)]

    # 2. Check for indexers: [0]
    idx_match = re.match(r'^([a-zA-Z0-9_]+)\[(\d+)\]$', token)
    if idx_match:
        prop = idx_match.group(1)
        idx = int(idx_match.group(2))
        for item in current_items:
            if isinstance(item, dict) and prop in item:
                val = item[prop]
                if isinstance(val, list) and 0 <= idx < len(val):
                    next_items.append(val[idx])
                elif idx == 0 and not isinstance(val, list):
                    next_items.append(val)
        return next_items

    # 3. Simple property navigation
    for item in current_items:
        if isinstance(item, dict):
            if token in item:
                val = item[token]
                if isinstance(val, list):
                    next_items.extend(val)
                elif val is not None:
                    next_items.append(val)
        elif isinstance(item, list):
            for sub_it in item:
                if isinstance(sub_it, dict) and token in sub_it:
                    val = sub_it[token]
                    if isinstance(val, list):
                        next_items.extend(val)
                    elif val is not None:
                        next_items.append(val)

    return next_items

def eval_where(condition_str: str, items: List[Any]) -> List[Any]:
    """Evaluates where(path = 'value') or where(path != 'value')"""
    # Matches: path = 'value' or path = value
    cond_match = re.match(r'^(.*?)\s*(=|!=)\s*\'?(.*?)\'?$', condition_str)
    if not cond_match:
        # Simple existence check: where(name)
        matched = []
        for it in items:
            res = eval_fhirpath(condition_str, it)
            if res and any(res):
                matched.append(it)
        return matched

    path = cond_match.group(1).strip()
    op = cond_match.group(2).strip()
    target_val = cond_match.group(3).strip().strip("'\"")

    matched = []
    for it in items:
        actual_vals = eval_fhirpath(path, it)
        actual_strings = [str(v) for v in actual_vals]

        if op == "=":
            if target_val in actual_strings:
                matched.append(it)
        elif op == "!=":
            if target_val not in actual_strings:
                matched.append(it)

    return matched
