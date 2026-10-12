"""Token-free Telegram adapter; network transport is injected."""
from dataclasses import dataclass
@dataclass(frozen=True)
class TelegramCommand:
    update_id:int; chat_id:str; command:str; text:str=""
class TelegramAdapter:
    def __init__(self,sender): self._sender=sender
    def parse_update(self,update):
        if not isinstance(update,dict) or "update_id" not in update: raise ValueError("invalid Telegram update")
        message=update.get("message") or update.get("edited_message")
        if not isinstance(message,dict): raise ValueError("Telegram update has no message")
        chat_id=str((message.get("chat") or {}).get("id","")).strip()
        if not chat_id: raise ValueError("Telegram chat id is required")
        text=str(message.get("text") or ""); parts=text.split(maxsplit=1)
        command=parts[0] if parts and parts[0].startswith("/") else "text"
        return TelegramCommand(int(update["update_id"]),chat_id,command,parts[1] if len(parts)>1 else "")
    def send_text(self,command,text):
        if not text: raise ValueError("message text is required")
        return self._sender(command.chat_id,text)
