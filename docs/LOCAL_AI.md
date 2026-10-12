# Local AI Packaging

StructuralPro's AI is offline-first.

## Runtime
- GGUF model weights live outside the source tree under `models/`.
- `llama-cpp-python` is an optional local runtime adapter.
- No OpenAI, Claude, Gemini, or other cloud API is required.
- If the runtime/model is absent, the deterministic local QA engine remains active.

## Production packaging
The Windows installer should:
1. Detect CPU/RAM/GPU capability.
2. Select an approved GGUF model profile.
3. Install/copy the model locally.
4. Verify the model checksum.
5. Run a local smoke test.
6. Never require an internet connection to answer normal project questions.

Model licenses must be checked before redistribution.