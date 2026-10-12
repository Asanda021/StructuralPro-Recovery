"""Deterministic BIM/digital-twin lineage for P191-P200.

This module adds a dependency-light project graph around existing BIM objects.
It never invents quantities: every quantity must be explicitly supplied and
linked to a known model object/source. Revision impact is deterministic and
fail-closed for missing identities.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any, Iterable

NODE_TYPES={"source","object","two_d","quantity","boq","estimate"}
EDGE_TYPES={"contains","represents","measures","maps_to","priced_as"}

@dataclass(frozen=True)
class TwinNode:
    node_id:str
    node_type:str
    version:str="1"
    evidence:dict[str,Any]|None=None

@dataclass(frozen=True)
class TwinEdge:
    edge_id:str
    source_id:str
    target_id:str
    relation:str
    version:str="1"

class DigitalTwinGraph:
    def __init__(self, nodes:Iterable[TwinNode]=(), edges:Iterable[TwinEdge]=()):
        self.nodes=list(nodes); self.edges=list(edges)
        self.validate()

    @staticmethod
    def _id(node_type:str, value:Any)->str:
        raw=f"{node_type}:{value}".encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    @staticmethod
    def _edge_id(source_id:str,target_id:str,relation:str,version:str)->str:
        raw=f"{source_id}|{target_id}|{relation}|{version}".encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    def validate(self):
        ids=set()
        for n in self.nodes:
            if n.node_type not in NODE_TYPES or not n.node_id:
                raise ValueError("invalid twin node")
            if n.node_id in ids: raise ValueError("duplicate twin node")
            ids.add(n.node_id)
        edge_ids=set()
        node_ids={n.node_id for n in self.nodes}
        for e in self.edges:
            if e.relation not in EDGE_TYPES:
                raise ValueError("invalid twin relation")
            if e.source_id not in node_ids or e.target_id not in node_ids:
                raise ValueError("twin edge references unknown node")
            if e.edge_id in edge_ids: raise ValueError("duplicate twin edge")
            edge_ids.add(e.edge_id)
        return self

    def add_node(self,node:TwinNode):
        if any(n.node_id==node.node_id for n in self.nodes): raise ValueError("duplicate twin node")
        self.nodes.append(node); self.validate(); return node

    def link(self,source_id:str,target_id:str,relation:str,version:str="1"):
        eid=self._edge_id(source_id,target_id,relation,version)
        edge=TwinEdge(eid,source_id,target_id,relation,version)
        if any(e.edge_id==eid for e in self.edges): return edge
        self.edges.append(edge); self.validate(); return edge

    def lineage(self,node_id:str)->list[str]:
        if node_id not in {n.node_id for n in self.nodes}: raise KeyError(node_id)
        by_source={}
        for e in self.edges: by_source.setdefault(e.source_id,[]).append(e.target_id)
        out=[]; seen={node_id}; stack=[node_id]
        while stack:
            cur=stack.pop()
            for nxt in sorted(by_source.get(cur,())):
                if nxt not in seen: seen.add(nxt); out.append(nxt); stack.append(nxt)
        return out

    def impact(self,changed_node_ids:Iterable[str])->dict[str,Any]:
        changed=sorted(set(changed_node_ids))
        unknown=[x for x in changed if x not in {n.node_id for n in self.nodes}]
        if unknown: raise ValueError("unknown changed twin node")
        affected=set(changed)
        for nid in changed: affected.update(self.lineage(nid))
        return {"changed":changed,"affected":sorted(affected)}

    def fingerprint(self)->str:
        payload={"nodes":[asdict(n) for n in sorted(self.nodes,key=lambda x:x.node_id)],
                 "edges":[asdict(e) for e in sorted(self.edges,key=lambda x:x.edge_id)]}
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        return hashlib.sha256(raw).hexdigest()

def build_twin_graph(*, sources:Iterable[dict[str,Any]]=(), objects:Iterable[dict[str,Any]]=(),
                     two_d:Iterable[dict[str,Any]]=(), quantities:Iterable[dict[str,Any]]=(),
                     boq:Iterable[dict[str,Any]]=(), estimates:Iterable[dict[str,Any]]=()):
    graph=DigitalTwinGraph()
    def add(t,key,evidence):
        graph.add_node(TwinNode(DigitalTwinGraph._id(t,key),t,str(evidence.get("version","1")),dict(evidence)))
        return DigitalTwinGraph._id(t,key)
    source_ids={}
    for x in sources:
        if not x.get("id"): raise ValueError("source id is required")
        source_ids[str(x["id"])]=add("source",x["id"],x)
    object_ids={}
    for x in objects:
        if not x.get("id") or not x.get("source_id"): raise ValueError("object id and source_id are required")
        if str(x["source_id"]) not in source_ids: raise ValueError("object source is unknown")
        oid=add("object",f'{x["source_id"]}:{x["id"]}',x); object_ids[str(x["id"])]=oid
        graph.link(source_ids[str(x["source_id"])],oid,"contains")
    quantity_ids={}
    for x in quantities:
        if not x.get("id") or not x.get("object_id") or "quantity" not in x:
            raise ValueError("quantity id, object_id and explicit quantity are required")
        if str(x["object_id"]) not in object_ids: raise ValueError("quantity object is unknown")
        q=float(x["quantity"])
        if q < 0 or q != q: raise ValueError("quantity must be non-negative and finite")
        qid=add("quantity",x["id"],x); quantity_ids[str(x["id"])]=qid
        graph.link(object_ids[str(x["object_id"])],qid,"measures")
    for x in two_d:
        if not x.get("id") or not x.get("object_id"): raise ValueError("2D id and object_id are required")
        if str(x["object_id"]) not in object_ids: raise ValueError("2D object is unknown")
        tid=add("two_d",x["id"],x); graph.link(tid,object_ids[str(x["object_id"])],"represents")
    boq_ids={}
    for x in boq:
        if not x.get("id") or not x.get("quantity_id"): raise ValueError("BOQ id and quantity_id are required")
        if str(x["quantity_id"]) not in quantity_ids: raise ValueError("BOQ quantity is unknown")
        bid=add("boq",x["id"],x); boq_ids[str(x["id"])]=bid
        graph.link(quantity_ids[str(x["quantity_id"])],bid,"maps_to")
    for x in estimates:
        if not x.get("id") or not x.get("boq_id"): raise ValueError("estimate id and boq_id are required")
        if str(x["boq_id"]) not in boq_ids: raise ValueError("estimate BOQ is unknown")
        eid=add("estimate",x["id"],x); graph.link(boq_ids[str(x["boq_id"])],eid,"priced_as")
    return graph
