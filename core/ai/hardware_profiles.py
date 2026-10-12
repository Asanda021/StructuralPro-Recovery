"""Local AI hardware profiles and model packaging validation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, platform

@dataclass(frozen=True)
class HardwareProfile:
    name:str
    min_ram_gb:int
    recommended_ram_gb:int
    cpu:str
    gpu:str
    notes:str

PROFILES=(
    HardwareProfile("basic",8,16,"x86_64/ARM64","CPU","small quantized model"),
    HardwareProfile("standard",16,32,"x86_64/ARM64","CPU/iGPU","medium quantized model"),
    HardwareProfile("pro",32,64,"x86_64","GPU optional","larger local model"),
)

def detect_hardware()->dict:
    ram_gb=0
    try:
        import psutil
        ram_gb=round(psutil.virtual_memory().total/1024**3)
    except Exception: pass
    return {"system":platform.system(),"machine":platform.machine(),"ram_gb":ram_gb}

def validate_model_manifest(path:str|Path)->dict:
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    required=("name","format","license","commercial_use","sha256")
    missing=[x for x in required if not data.get(x)]
    return {"valid":not missing and str(data.get("format")).lower()=="gguf","missing":missing,"manifest":data}

def select_profile(ram_gb:int)->HardwareProfile:
    if ram_gb>=32:return PROFILES[2]
    if ram_gb>=16:return PROFILES[1]
    return PROFILES[0]
