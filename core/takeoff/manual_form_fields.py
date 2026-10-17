"""Display contracts, not formulas/default engineering quantities."""
LABELS={'length':('طول','متر'),'width':('عرض','متر'),'height':('ارتفاع','متر'),'depth':('عمق','متر'),'thickness':('ضخامت','متر'),'count':('تعداد','عدد'),'openings':('بازشو','واحد نتیجه؛ طبق مبنا'),'unit_weight':('وزن_واحد','کیلوگرم بر متر؛ مرجع صریح'),'diameter':('قطر','میلی‌متر'),'area':('مساحت','متر مربع'),'layers':('تعداد_لایه','عدد'),'coats':('تعداد_دست','عدد'),'overlap':('همپوشانی','طبق مبنای صریح')}
GROUPS={
 'earth':('عملیات خاکی',('length','width','depth','count')),
 'concrete':('بتن و قالب‌بندی',('length','width','height','thickness','count','openings')),
 'rebar':('میلگرد',('length','count','unit_weight','diameter')),
 'roof':('سقف‌ها؛ دیتایل مستقل لازم است',('length','width','thickness','count','openings')),
 'steel':('اسکلت فولادی',('length','count','unit_weight','area')),
 'wall':('دیوارچینی',('length','height','thickness','count','openings')),
 'plaster':('گچ و اندود',('length','height','count','openings')),
 'ceramic':('کاشی و سرامیک',('length','width','height','count','openings')),
 'floor':('کف‌سازی',('length','width','thickness','count')),
 'insulation':('عایق‌کاری',('length','width','height','layers','overlap')),
 'opening':('در و پنجره',('width','height','count')),
 'mechanical':('تأسیسات مکانیکی',('length','count','diameter')),
 'electrical':('تأسیسات برقی',('length','count')),
 'site':('محوطه و بازسازی',('length','width','height','thickness','count')),
 'documented':('فرمول دستی مستند',()),
}
SETS={
 'earth':{'external_earthwork','excavation'},
 'concrete':{'column','column_joint','isolated_footing','strip_footing','mat_footing','tie_beam','pile_foundation','pile_cap','bored_pile','shear_wall','stair','blinding_concrete','beam_concrete_formwork'},
 'rebar':{'beam_reinforcement'},'steel':{'steel_frame','composite_frame','beam_schedule','stair_metal','handrails_metalwork'},
 'wall':{'block_wall','brick_wall','gypsum_partition'},'plaster':{'plaster_finish','cement_render','paint_finish'},'ceramic':{'ceramic_finish'},
 'floor':{'floor_finish','stone_floor'},'insulation':{'waterproofing','thermal_insulation','acoustic_insulation'},
 'opening':{'door_window','upvc_aluminium_windows','glass_curtain_wall'},
 'mechanical':{'plumbing','sanitary_drainage','hvac','mechanical_ventilation','plantroom','natural_gas','fire_protection'},
 'electrical':{'electrical_power','lighting','low_voltage','fire_alarm','data_network','security_systems','emergency_power','elevator'},
 'site':{'external_works','site_drains','demolition','concrete_repair','seismic_retrofit','historic_restoration','stone_cladding','facade_cladding','retaining_structures','timber_frame'},
 'roof':{'solid_slab','joist_block','joist_foam','waffle','uboot','cobiax','hollow_core','steel_deck','kromit_roof','composite_roof','sandwich_roof','timber_roof','precast_roof','suspended_ceiling'},
}
ALIASES={name:key for key,(name,unit) in LABELS.items()};ALIASES.update({'وزن':'unit_weight','وزن واحد':'unit_weight','ضخامت رویه':'topping_thickness'})
def canonical(name):return ALIASES.get(name,name)
def family_fields(code):
    group=next((g for g,items in SETS.items() if code in items),'documented');return GROUPS[group]

def expression(source,display=False):
    import io,tokenize
    tokens=[]
    for token in tokenize.generate_tokens(io.StringIO(str(source)).readline):
        if token.type==tokenize.NAME:
            name=LABELS.get(token.string,(token.string,''))[0] if display else canonical(token.string)
            token=token._replace(string=name)
        tokens.append(token)
    return tokenize.untokenize(tokens)

def persian_error(error):
    import re
    message=str(error)
    for key,(label,unit) in LABELS.items():message=re.sub(r'(?<!\w)'+re.escape(key)+r'(?!\w)',label,message)
    if re.search(r'[A-Za-z]{3,}',message):
        import logging
        logging.getLogger(__name__).warning('Manual takeoff validation: %s',error)
        return 'ورودی یا ساختار داده معتبر نیست؛ فرمول، منبع و نسخه را بررسی کنید. جزئیات فنی در گزارش خطا ثبت شد.'
    return message
