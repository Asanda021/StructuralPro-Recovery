"""Commercial payment statement with transparent contractual deductions."""
from __future__ import annotations
from typing import Iterable
from core.projects.statement_engine import StatementLine,build_statement

def build_payment_statement(contract,current:Iterable[StatementLine],*,previous_paid=0.0,
                            advance_recovery_rate=0.0,other_deduction_rate=0.0):
    errors=contract.validate()
    if errors: raise ValueError("; ".join(errors))
    base=build_statement(current,retention_rate=contract.retention_rate,
        advance_recovery_rate=advance_recovery_rate,
        other_deduction_rate=other_deduction_rate,advance_paid=contract.advance_paid)
    gross=round(float(base.get("gross_current",0)),10)
    commercial_base=round(contract.commercial_total(gross),10)
    tax=round(commercial_base*float(contract.tax_rate),10)
    insurance=round(commercial_base*float(contract.insurance_rate),10)
    payable=round(float(base.get("payable",0))+tax-insurance,10)
    return {**base,"contract_id":contract.contract_id,"contract_total":round(contract.total(),10),
            "commercial_base_current":gross,"commercial_total_current":commercial_base,
            "tax":tax,"insurance":insurance,"payable":payable,
            "previous_paid":float(previous_paid),
            "balance_after_current":round(contract.commercial_total()-float(previous_paid)-payable,10),
            "commercial_factors":{"overhead_rate":contract.overhead_rate,"regional_rate":contract.regional_rate,
                "retention_rate":contract.retention_rate,"tax_rate":contract.tax_rate,
                "insurance_rate":contract.insurance_rate}}
class PaymentStatement:
    def __init__(self,contract): self.contract=contract
    def build(self,lines,**kwargs): return build_payment_statement(self.contract,lines,**kwargs)
