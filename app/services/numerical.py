"""Conservative arithmetic for explicit percentage changes, never unit guessing."""
import re

from app.core.schemas import NumericalComparison


def check_change(claim, evidence, claim_stats, evidence_stats):
    change = re.search(r'from\s+(\d+(?:\.\d+)?)\s*%\s+to\s+(\d+(?:\.\d+)?)\s*%', evidence, re.I)
    amount = re.search(r'by\s+(\d+(?:\.\d+)?)\s*(percentage points?|%|percent)', claim, re.I)
    result = NumericalComparison(status='NUMERICAL_CHECK_UNSUPPORTED', has_numerical_data=bool(claim_stats),
        claim_entities=claim_stats, evidence_entities=evidence_stats,
        details='Numerical expression requires structured context not safely resolved by this check.')
    if change and amount:
        a, b, stated = float(change[1]), float(change[2]), float(amount[1])
        direction = -1 if re.search(r'\b(reduc|decreas|declin|drop)', claim, re.I) else 1
        absolute = direction * (b-a)
        relative = direction * (b-a)/a*100 if a else None
        result.calculation = f'{b:g} - {a:g} = {b-a:g} percentage points; relative change = {relative}%.'
        if amount[2].lower().startswith('percentage point'):
            expected = absolute
        elif 'relative' in claim.lower() and relative is not None:
            expected = relative
        else:
            result.details = 'Percent improvement is ambiguous: percentage points and relative percent differ.'
            return result
        common = set(re.findall(r'[a-z]{4,}', claim.lower())) & set(re.findall(r'[a-z]{4,}', evidence.lower()))
        if not common - {'from', 'with', 'this', 'that', 'improved', 'increased', 'decreased'}:
            result.details = 'Cannot associate the change with the same measured quantity.'
            return result
        result.is_match = abs(stated-expected) <= .05
        result.status = 'PASSED' if result.is_match else 'FAILED'
        result.details = 'Computed change agrees.' if result.is_match else 'Computed change differs from the claim.'
        return result
    if re.search(r'(?:\bp\s*[<>=]|\bconfidence interval|\brelative (?:improvement|increase)|\bbetween \d+|\d+\s*[-–]\s*\d+)', claim, re.I):
        return result
    return None
