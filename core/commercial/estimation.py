"""Legacy estimation using the shared exact numeric boundaries; preview only."""
from dataclasses import dataclass
from typing import Iterable
from core.commercial.exact_values import number,wire,exact

@dataclass(frozen=True)
class EstimateLine:
    code:str; description:str; quantity:float; unit_price:float; unit:str=""; factor:float=1.0
    @property
    @exact
    def amount(self):return number(self.quantity,'quantity')*number(self.unit_price,'unit_price')*number(self.factor,'factor')

@exact
def estimate(lines:Iterable[EstimateLine])->dict:
    rows=[{'code':x.code,'description':x.description,'quantity':x.quantity,'unit':x.unit,'unit_price':x.unit_price,'factor':x.factor,'amount':x.amount} for x in lines]
    return wire({'lines':rows,'subtotal':sum(x['amount'] for x in rows),'currency':None,'financial_policy_status':'LEGACY_PREVIEW_NOT_FINANCIALLY_APPROVED'})

@exact
def progress_claim(lines:Iterable[EstimateLine],progress:dict[str,float])->dict:
    rows=[]
    for x in lines:
        if x.code not in progress:raise ValueError('کارکرد نامعلوم است؛ صفر فرض نمی‌شود')
        pct=number(progress[x.code],'progress percent')
        if pct>100:raise ValueError('درصد کارکرد خارج از محدوده است')
        rows.append({'code':x.code,'quantity':x.quantity,'progress_percent':pct,'executed_quantity':number(x.quantity,'quantity')*pct/100,'executed_amount':x.amount*pct/100})
    return wire({'lines':rows,'executed_amount':sum(x['executed_amount'] for x in rows)})
