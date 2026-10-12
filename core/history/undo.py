"""Small deterministic undo/redo command stack."""
class CommandStack:
    def __init__(self,limit=100): self.undo_stack=[]; self.redo_stack=[]; self.limit=limit
    def execute(self,do,undo): do(); self.undo_stack.append((do,undo)); self.redo_stack.clear(); self.undo_stack=self.undo_stack[-self.limit:]
    def undo(self):
        if not self.undo_stack:return False
        do,un=self.undo_stack.pop(); un(); self.redo_stack.append((do,un)); return True
    def redo(self):
        if not self.redo_stack:return False
        do,un=self.redo_stack.pop(); do(); self.undo_stack.append((do,un)); return True
