"""Shared provider-neutral platform contracts; preserves the legacy ProductClient API."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

SUPPORTED_PLATFORMS=("windows","android","telegram")

@dataclass
class ClientSession:
    platform: str
    project_id: str | None = None
    offline: bool = True

@dataclass(frozen=True)
class ClientRequest:
    request_id:str; platform:str; action:str; project_id:str; payload:dict[str,Any]
    def __post_init__(self):
        if self.platform not in SUPPORTED_PLATFORMS: raise ValueError("unsupported client platform")
        if not self.request_id.strip() or not self.action.strip() or not self.project_id.strip(): raise ValueError("request identity is required")
        if not isinstance(self.payload, dict): raise TypeError("request payload must be a dictionary")

@dataclass(frozen=True)
class ClientResponse:
    request_id:str; ok:bool; data:dict[str,Any]; error:str=""
    def __post_init__(self):
        if not isinstance(self.data, dict): raise TypeError("response data must be a dictionary")
        if self.ok and self.error: raise ValueError("successful response cannot contain an error")
        if not self.ok and not self.error: raise ValueError("failed response requires an error")

class ProductClient:
    SUPPORTED=set(SUPPORTED_PLATFORMS)
    def __init__(self, platform: str, project_service: Callable[...,Any] | None=None, request_handler: Callable[[ClientRequest],dict[str,Any]] | None=None):
        platform=str(platform).lower()
        if platform not in self.SUPPORTED: raise ValueError("unsupported platform")
        self.session=ClientSession(platform, offline=(platform != "telegram"))
        self.project_service=project_service
        self.request_handler=request_handler

    def open_project(self, project_id: str):
        self.session.project_id=str(project_id)
        if self.project_service: return self.project_service(project_id)
        return {"id":str(project_id),"platform":self.session.platform}

    def request(self, request: ClientRequest) -> ClientResponse:
        if request.platform != self.session.platform:
            return ClientResponse(request.request_id, False, {}, "request platform mismatch")
        if self.session.project_id is not None and request.project_id != self.session.project_id:
            return ClientResponse(request.request_id, False, {}, "request project mismatch")
        if self.request_handler is not None:
            try:
                data=self.request_handler(request)
                if not isinstance(data, dict):
                    return ClientResponse(request.request_id, False, {}, "request handler returned invalid data")
                return ClientResponse(request.request_id, True, data)
            except Exception as exc:
                return ClientResponse(request.request_id, False, {}, f"request failed: {type(exc).__name__}")
        if request.action == "open_project":
            return ClientResponse(request.request_id, True, self.open_project(request.project_id))
        return ClientResponse(request.request_id, False, {}, "unsupported client action")

    def state(self)->dict[str,Any]:
        return {"platform":self.session.platform,"project_id":self.session.project_id,"offline":self.session.offline}

def capability_manifest():
    return {
        "windows":{"offline":True,"sync":True,"reports":True,"takeoff":True},
        "android":{"offline":True,"sync":True,"reports":True,"takeoff":True},
        "telegram":{"offline":False,"sync":True,"reports":True,"takeoff":True},
    }
