"""StructuralPro embedded local AI runtime.

The AI engine is part of the StructuralPro desktop application. AI-enabled
editions ship their model assets and a pinned llama.cpp Windows runtime inside
the same installation; there is no separate user-facing AI application.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess
import hashlib
import json

from core.ai.edition_models import AITier, ai_model_spec_for_edition
from core.platform.product import packaged_edition


@dataclass
class AIResponse:
    text: str
    source: str = "local-rule-engine"
    confidence: float = 1.0
    requires_user_confirmation: bool = True
    quantity_authority: bool = False
    provenance: dict = field(default_factory=lambda: {
        "model_id": "local-rule-engine-v1", "mode": "deterministic_offline_qa"})


class LocalAIEngine:
    def __init__(self, model_dir=None, model_path=None, n_ctx=4096, edition=None):
        self.bundle_dir = Path(__file__).resolve().parents[2]
        self.edition = str(edition or os.getenv("STRUCTURALPRO_EDITION", "")).strip().lower()
        if not self.edition:
            packaged = packaged_edition(self.bundle_dir, fail_closed=False)
            self.edition = packaged.value if packaged else "unified"
        self.model_dir = Path(model_dir or os.getenv("STRUCTURALPRO_AI_MODEL_DIR") or self.bundle_dir / "models")
        self.runtime_dir = Path(os.getenv("STRUCTURALPRO_AI_RUNTIME_DIR") or self.bundle_dir / "ai_runtime")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.n_ctx = n_ctx
        self._load_error = None
        spec = ai_model_spec_for_edition(self.edition) if self.edition else None
        self.tier = spec.tier if spec else AITier.NONE
        self.model_path = Path(model_path) if model_path else self._find_model(spec)
        self.mmproj_path = self._find_mmproj(spec)

    def _find_model(self, spec):
        if not spec:
            return None
        candidate = self.model_dir / spec.model_filename
        if candidate.exists():
            return candidate
        return None

    def _find_mmproj(self, spec):
        if not spec or not spec.mmproj_filename:
            return None
        candidate = self.model_dir / spec.mmproj_filename
        return candidate if candidate.exists() else None

    def _binary(self, name):
        exe = (name if name.lower().endswith(".exe") else f"{name}.exe") if os.name == "nt" else name.removesuffix(".exe")
        candidate = self.runtime_dir / exe
        return candidate if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)) else None

    @property
    def is_local(self):
        return True

    @property
    def _unified_assets_ready(self):
        # Explicit old-tier fixtures remain compatibility-only. Canonical one-
        # edition execution must pass the complete offline A1 release gate.
        if self.edition != "unified":
            return True
        from core.ai.release_gate import inspect_ai_release_assets
        gate = inspect_ai_release_assets(
            self.model_dir / "release_manifest.json", self.model_dir
        )
        return gate.ready

    @property
    def has_llm_model(self):
        return (self.tier is not AITier.NONE and self.model_path is not None
                and self.model_path.is_file() and self._unified_assets_ready)

    @property
    def has_vision_model(self):
        return (
            self.tier is AITier.TAKEOFF
            and self.has_llm_model
            and self.mmproj_path is not None
            and self.mmproj_path.exists()
        )

    @property
    def runtime_available(self):
        return self._binary("llama-cli") is not None

    def inspect_project(self, project):
        if self.edition == "light":
            return AIResponse("نسخه سبک فاقد هوش مصنوعی محلی است.",
                              source="fail-closed", confidence=0.0)
        project = project if isinstance(project, dict) else {}
        missing = []
        takeoffs = project.get("takeoffs", []) or []
        if not project.get("name"):
            missing.append("نام پروژه")
        if not takeoffs:
            missing.append("حداقل یک متره")
        for i, item in enumerate(takeoffs, 1):
            if not item.get("member_code"):
                missing.append(f"کد عضو متره {i}")
            if not item.get("quantities"):
                missing.append(f"خروجی متره عضو {i}")
        return AIResponse(self._format_check(missing, len(takeoffs)), confidence=0.99,
                          provenance={"model_id": "local-rule-engine-v1",
                                      "mode": "deterministic_offline_qa",
                                      "data_sha256": hashlib.sha256(json.dumps(
                                          project, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})

    def answer(self, prompt, project=None):
        if self.edition == "light":
            return AIResponse("نسخه سبک فاقد هوش مصنوعی محلی است.",
                              source="fail-closed", confidence=0.0)
        p = (prompt or "").strip()
        if self.has_llm_model and self.runtime_available and p:
            return self._llama_text_answer(p, project)

        if project is not None and any(k in p for k in ("بررسی", "کنترل", "جا افتاده", "نقص", "متره")):
            return self.inspect_project(project)

        if re.search(r"آفلاین|اینترنت|آنلاین", p):
            return AIResponse(
                "StructuralPro و هوش مصنوعی محلی آن به اینترنت وابسته نیستند. "
                "اینترنت فقط برای همگام‌سازی، پشتیبان‌گیری و به‌روزرسانی اختیاری است."
            )

        return AIResponse(
            "پاسخ محلی آماده است. برای تحلیل عمیق‌تر، پروژه را در StructuralPro انتخاب کنید؛ "
            "اطلاعات پروژه برای پاسخ‌گویی محلی به سرویس خارجی ارسال نمی‌شود."
        )

    def answer_with_image(self, image_path, prompt, project=None):
        """Run the bundled multimodal model for Pro/Enterprise."""
        image = Path(image_path)
        p = ("Advisory suggestions only. Never infer undocumented dimensions, scale, thickness, "
             "materials, reinforcement or prices. State missing evidence and require human review.\n"
             + (prompt or "این نقشه را برای بازبینی انسانی توصیف کن.").strip())
        binary = self._binary("llama-mtmd-cli")
        if not self.has_vision_model or binary is None:
            return AIResponse(
                "مدل تصویری یا موتور محلی AI Takeoff در بسته نصب موجود نیست؛ متره قطعی انجام نشد.",
                source="fail-closed",
                confidence=0.0,
            )
        try:
            result = subprocess.run(
                [
                    str(binary),
                    "-m", str(self.model_path),
                    "--mmproj", str(self.mmproj_path),
                    "--image", str(image),
                    "-p", p,
                    "-n", "768", "-c", str(self.n_ctx), "-t", "4",
                    "--temp", "0.1",
                ],
                cwd=str(self.runtime_dir),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            text = (result.stdout or "").strip()
            if result.returncode != 0 or not text:
                self._load_error = (result.stderr or "multimodal runtime failed").strip()
                return AIResponse(
                    "تحلیل تصویری AI ناموفق بود؛ نتیجه حدس‌زده وارد BOQ نمی‌شود.",
                    source="fail-closed",
                    confidence=0.0,
                )
            return AIResponse(text, source="local-gguf-vision", confidence=0.80,
                              provenance=self._model_provenance(project, image))
        except Exception as exc:
            self._load_error = str(exc)
            return AIResponse(
                "تحلیل تصویری AI قابل اجرا نبود؛ نتیجه حدس‌زده وارد BOQ نمی‌شود.",
                source="fail-closed",
                confidence=0.0,
            )

    def _llama_text_answer(self, prompt, project=None):
        context = ""
        if project:
            context = "Read-only project evidence: " + json.dumps({"name": project.get("name"), "takeoffs": project.get("takeoffs", [])}, ensure_ascii=False, sort_keys=True)
        system = (
            "You are StructuralPro Local AI, an offline construction quantity-takeoff assistant. "
            "Never invent numeric measurements, example dimensions, prices or material details. "
            "If required inputs are missing, request verified documents and human review; do not calculate. "
            "Never claim that an AI answer replaces a deterministic engineering calculation."
        )
        user = f"{context}\nUser: {prompt}".strip()
        binary = self._binary("llama-completion") or self._binary("llama-cli")
        try:
            result = subprocess.run(
                [
                    str(binary), "-m", str(self.model_path),
                    "-sys", system, "-p", user, "-n", "768", "-c", str(self.n_ctx),
                    "-t", "4", "--temp", "0.1", "-st", "--no-display-prompt",
                ],
                cwd=str(self.runtime_dir),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            text = (result.stdout or "").strip()
            if result.returncode != 0 or not text:
                raise RuntimeError((result.stderr or "llama.cpp failed").strip())
            return AIResponse(text, source="local-gguf", confidence=0.85,
                              provenance=self._model_provenance(project))
        except Exception as exc:
            self._load_error = str(exc)
            return AIResponse(
                "مدل محلی در دسترس نبود؛ کنترل پایه آفلاین فعال است.",
                source="local-rule-engine",
                confidence=0.70,
            )

    def _model_provenance(self, project, image=None):
        """Record actual loaded assets; never claim a configured model was run."""
        def digest(path):
            result = hashlib.sha256()
            with Path(path).open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    result.update(chunk)
            return result.hexdigest()
        result = {
            "mode": "local_gguf_advisory", "model_id": self.model_path.name,
            "model_sha256": digest(self.model_path),
            "data_sha256": hashlib.sha256(json.dumps(
                project, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        }
        if image is not None:
            result.update(source_path=str(image), source_sha256=digest(image),
                          projector_sha256=digest(self.mmproj_path))
        return result

    def _format_check(self, missing, count):
        if not missing:
            return (
                f"کنترل اولیه پروژه انجام شد: {count} مورد متره موجود است و "
                "مورد ضروریِ شناخته‌شده‌ای ناقص نیست."
            )
        return "مواردی که باید بررسی شوند:\n" + "\n".join(f"• {item}" for item in missing)
