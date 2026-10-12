"""Thin offline-safe Android/Telegram runtime contracts.
The shared project service remains platform-neutral; these adapters only marshal
commands and state so native clients can be built without duplicating business logic.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class MobileCommand:
    action:str
    payload:dict[str,Any]

class AndroidRuntime:
    platform="android"
    def __init__(self,service=None): self.service=service
    def open(self,project_id): return self.service.open_project(project_id) if self.service else {"id":str(project_id)}
    def command(self,action,**payload): return MobileCommand(action,payload)

class TelegramRuntime:
    platform="telegram"
    def __init__(self,service=None): self.service=service
    def open(self,project_id): return self.service.open_project(project_id) if self.service else {"id":str(project_id)}
    def command(self,action,**payload): return MobileCommand(action,payload)
