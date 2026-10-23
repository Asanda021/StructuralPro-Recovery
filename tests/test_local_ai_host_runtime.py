"""Command/discovery contracts. Fixtures do not claim actual GGUF inference."""
import os
import subprocess
from core.ai.local_engine import LocalAIEngine


def test_native_runtime_discovery(tmp_path, monkeypatch):
    monkeypatch.setenv('STRUCTURALPRO_AI_RUNTIME_DIR', str(tmp_path))
    binary=tmp_path/('llama-cli.exe' if os.name=='nt' else 'llama-cli')
    binary.write_text('path fixture');binary.chmod(0o755)
    assert LocalAIEngine(model_dir=tmp_path,edition='standard')._binary('llama-cli')==binary


def test_external_model_directory(tmp_path,monkeypatch):
    monkeypatch.setenv('STRUCTURALPRO_AI_MODEL_DIR',str(tmp_path))
    assert LocalAIEngine(edition='standard').model_dir==tmp_path


def test_bounded_text_command_and_project_evidence(tmp_path,monkeypatch):
    e=LocalAIEngine(model_dir=tmp_path,edition='standard',n_ctx=2048)
    e.model_path=tmp_path/'hash-only.fixture';e.model_path.write_bytes(b'not a model')
    command=[]
    def capture(argv,**kwargs):
        command.extend(argv);return subprocess.CompletedProcess(argv,0,'fixture output','')
    monkeypatch.setattr(subprocess,'run',capture)
    e._llama_text_answer('question',{'name':'P','takeoffs':[{'member_code':'B1','quantities':[{'amount':'6','unit':'m'}]}]})
    assert '-sys' in command
    assert command[command.index('-c')+1]=='2048'
    assert 'B1' in command[command.index('-p')+1]
    assert '--no-display-prompt' in command


def test_native_model_controls_fail_closed(tmp_path):
    import sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    for edition in ('light','standard','pro','enterprise'):
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',STRUCTURALPRO_EDITION=edition,PYTHONPATH=str(root))
        env.pop('STRUCTURALPRO_AI_MODEL_DIR',None);env.pop('STRUCTURALPRO_AI_RUNTIME_DIR',None)
        r=subprocess.run([sys.executable,str(root/'tests/phase2_priority6_model_ui_probe.py'),str(tmp_path/edition)],cwd=root,env=env,capture_output=True,text=True,timeout=60)
        assert r.returncode==0,r.stdout+r.stderr


def test_multimodal_command_matches_pinned_runtime(tmp_path,monkeypatch):
    """Flag contract only; synthetic bytes are not a model acceptance test."""
    e=LocalAIEngine(model_dir=tmp_path,edition='pro')
    e.model_path=tmp_path/'hash-only.fixture';e.model_path.write_bytes(b'model hash fixture')
    e.mmproj_path=tmp_path/'projector.fixture';e.mmproj_path.write_bytes(b'projector hash fixture')
    image=tmp_path/'image.fixture';image.write_bytes(b'image hash fixture')
    monkeypatch.setattr(e,'_binary',lambda name:tmp_path/name)
    command=[]
    def capture(argv,**kwargs):
        command.extend(argv);return subprocess.CompletedProcess(argv,0,'fixture output','')
    monkeypatch.setattr(subprocess,'run',capture)
    result=e.answer_with_image(image,'Describe only')
    assert '-st' not in command
    assert '--mmproj' in command and '--image' in command
    assert result.requires_user_confirmation and not result.quantity_authority


def test_project_question_uses_available_model_not_rules(tmp_path,monkeypatch):
    from core.ai.local_engine import AIResponse
    e=LocalAIEngine(model_dir=tmp_path,edition='standard')
    e.model_path=tmp_path/'presence-only.fixture';e.model_path.write_bytes(b'not a GGUF')
    monkeypatch.setattr(e,'_binary',lambda name:tmp_path/name)
    called=[]
    def record(prompt,project):
        called.append((prompt,project));return AIResponse('dispatch fixture')
    monkeypatch.setattr(e,'_llama_text_answer',record)
    e.answer('بررسی متره',{'name':'P'})
    assert called==[('بررسی متره',{'name':'P'})]
