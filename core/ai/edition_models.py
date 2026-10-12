"""Edition-specific embedded local AI model contract.

AI is part of the StructuralPro application package. The edition determines
which model assets are bundled; there is no separate user-facing AI program.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AITier(str, Enum):
    NONE = "none"
    BASE = "base"
    TAKEOFF = "takeoff"


@dataclass(frozen=True)
class AIModelSpec:
    tier: AITier
    model_filename: str | None
    model_url: str | None
    model_sha256: str | None
    mmproj_filename: str | None = None
    mmproj_url: str | None = None
    mmproj_sha256: str | None = None


# Official/open model artifacts selected for the Windows-first package.
# Qwen2.5-0.5B-Instruct-GGUF is Apache-2.0 and is used for the lighter tier.
# Qwen2.5-VL-3B-Instruct-GGUF is Apache-2.0 and provides the multimodal
# foundation for AI Takeoff in Pro/Enterprise.
MODEL_SPECS = {
    AITier.BASE: AIModelSpec(
        tier=AITier.BASE,
        model_filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        model_url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        model_sha256="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
    ),
    AITier.TAKEOFF: AIModelSpec(
        tier=AITier.TAKEOFF,
        model_filename="Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        model_url="https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        model_sha256="d02fe9b69ad8cadbbd228e387667af66612c44bed29ffc8eb1e7caf9ac486c12",
        mmproj_filename="mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        mmproj_url="https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        mmproj_sha256="980c9b2f78c04e6cff93d277ada09e768394f112d75db3b4e9dea8a69f9fb904",
    ),
}

# llama.cpp is MIT-licensed and is bundled inside AI-enabled Windows editions.
LLAMA_CPP_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b10549/llama-b10549-bin-win-cpu-x64.zip"
LLAMA_CPP_SHA256 = "11d38f2ed878489b2c3d02b3d1a67683c02fbfb3d265876b9ede749a8dff5f1c"


def ai_tier_for_edition(edition: str) -> AITier:
    value = str(edition).lower()
    if value == "light":
        return AITier.NONE
    if value == "standard":
        return AITier.BASE
    if value in {"pro", "enterprise"}:
        return AITier.TAKEOFF
    raise ValueError(f"Unsupported edition: {edition!r}")


def ai_model_spec_for_edition(edition: str) -> AIModelSpec | None:
    tier = ai_tier_for_edition(edition)
    return MODEL_SPECS.get(tier)
