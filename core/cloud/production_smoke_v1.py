from core.cloud.collaboration_v4 import Event,apply_event,fingerprint,three_way
def smoke_event(project_id="smoke-project")->dict:
    base={"project_id":project_id,"revision":1,"items":[]}; fp=fingerprint(base)
    event=Event(project_id,2,"smoke-user","editor",fp,{"project_id":project_id,"revision":2,"items":[{"id":"Q1"}]},"update")
    accepted=apply_event(1,fp,event)
    conflict_event=Event(project_id,3,"other-user","editor","0"*64,{"project_id":project_id,"revision":3},"update")
    conflict=apply_event(2,accepted["fingerprint"],conflict_event)
    merge=three_way({"qty":1},{"qty":2},{"qty":3})
    if not accepted["accepted"] or not conflict["conflict"] or not merge["requires_review"]: raise AssertionError("cloud collaboration smoke gate failed")
    return {"accepted":accepted,"conflict":conflict,"merge":merge}
