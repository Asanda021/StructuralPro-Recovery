"""P62 — explicit Iranian takeoff rule registry and user-import contract."""
from __future__ import annotations
from dataclasses import dataclass
import json
from hashlib import sha256

@dataclass(frozen=True)
class IranianRule:
    rule_id:str
    source:str
    version:str
    discipline:str
    item_code:str
    unit:str
    factor:float
    rounding_decimals:int=3
    waste_allowed:bool=False

def validate_rule(rule:IranianRule)->None:
    if any(not isinstance(v,str) or not v.strip() for v in (rule.rule_id,rule.source,rule.version,rule.discipline,rule.item_code,rule.unit)):
        raise ValueError("Iranian rule identity is incomplete")
    if rule.factor < 0 or rule.rounding_decimals < 0: raise ValueError("invalid Iranian rule")
    if rule.waste_allowed and rule.factor == 0: raise ValueError("zero factor cannot be waste-enabled")

def apply_rule(quantity:float, rule:IranianRule, waste:float=0.0)->float:
    validate_rule(rule)
    if quantity < 0 or waste < 0 or waste > 1: raise ValueError("invalid quantity/waste")
    if waste and not rule.waste_allowed: raise ValueError("waste is not allowed by source rule")
    value=quantity*rule.factor*(1+waste)
    return round(value,rule.rounding_decimals)

def import_rules(payload:str)->tuple[IranianRule,...]:
    try: raw=json.loads(payload)
    except json.JSONDecodeError as exc: raise ValueError("invalid rule import JSON") from exc
    if not isinstance(raw,list) or not raw: raise ValueError("rule import must be a non-empty list")
    rules=[]
    for x in raw:
        rule=IranianRule(
            str(x["rule_id"]),str(x["source"]),str(x["version"]),str(x["discipline"]),
            str(x["item_code"]),str(x["unit"]),float(x["factor"]),
            int(x.get("rounding_decimals",3)),bool(x.get("waste_allowed",False))
        )
        validate_rule(rule); rules.append(rule)
    return tuple(rules)

def rule_fingerprint(rules)->str:
    normalized=[]
    for rule in rules:
        validate_rule(rule); normalized.append(rule.__dict__)
    return sha256(json.dumps(normalized,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
