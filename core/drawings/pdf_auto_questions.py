"""Fail-closed, source-bound review answers for PDF cross-sheet ambiguities.

Answers can be recorded and exported to a local review file; they do not
modify takeoff measurements, source drawings, BOQ or financial approvals.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Mapping


class PDFQuestionDecisionLedger:
    VALID_ACTIONS = {'confirm_suggestion', 'correct', 'request_document'}

    def __init__(self, report: Mapping):
        self.questions = {q['tag']: q for q in report.get('questions', ())}
        if len(self.questions) != len(report.get('questions', ())):
            raise ValueError('duplicate PDF review question')
        self.sources = {d['document_id']: str(d['sha256']) for d in report.get('documents', ())
                        if d.get('document_id') and d.get('sha256')}
        self.graph_sha256 = (report.get('detail_evidence_graph') or {}).get('graph_sha256')
        if self.questions and len(self.sources) != len(report.get('documents', ())):
            raise ValueError('source-bound responses require source hashes')
        self.answers: dict[str, dict] = {}

    def answer(self, tag: str, action: str, *, value: str = '', reviewer: str = 'LOCAL_USER') -> dict:
        if tag not in self.questions:
            raise KeyError('no such pending PDF question')
        if action not in self.VALID_ACTIONS:
            raise ValueError('unknown reviewer decision')
        if not isinstance(value, str) or len(value) > 500:
            raise ValueError('invalid review input')
        suggestion = self.questions[tag].get('suggestion') or {}
        if action == 'confirm_suggestion':
            if suggestion.get('status') != 'PROPOSED_UNVERIFIED' or suggestion.get('value') is None:
                raise ValueError('there is no evidence-backed proposed value to confirm')
            answer_value = str(suggestion['value'])
        elif action == 'correct':
            if not value.strip():
                raise ValueError('correction must be explicit; empty values are not allowed')
            answer_value = value.strip()
        else:
            answer_value = ''
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError('reviewer is required')
        record = {
            'tag': tag, 'decision': action, 'answer': answer_value,
            'reviewer': reviewer.strip(),
            'answered_utc': datetime.now(timezone.utc).isoformat(),
            'evidence': self.questions[tag].get('evidence', []),
            'source_sha256': dict(self.sources),
            'status': 'REVIEW_ANSWER_RECORDED_NOT_ENGINEERING_APPROVED',
            'financially_payable': False,
        }
        if tag.startswith("PDF_GRAPH_"):
            record["graph_sha256"] = self.graph_sha256
        self.answers[tag] = record
        return dict(record)

    def reconcile_sources(self, new_report: Mapping) -> bool:
        new = {d['document_id']: str(d['sha256']) for d in new_report.get('documents', ())
               if d.get('document_id') and d.get('sha256')}
        current_graph = (new_report.get('detail_evidence_graph') or {}).get('graph_sha256')
        if new != self.sources or current_graph != self.graph_sha256:
            self.answers.clear()
            return False
        return True

    def export_json(self) -> str:
        return json.dumps({
            'schema_version': 1,
            'state': 'PRELIMINARY_REVIEW_ONLY',
            'source_sha256': self.sources,
            **({'graph_sha256': self.graph_sha256} if self.graph_sha256 else {}),
            'answers': list(self.answers.values()),
            'financial_approvals': 0,
        }, ensure_ascii=False, indent=2)
