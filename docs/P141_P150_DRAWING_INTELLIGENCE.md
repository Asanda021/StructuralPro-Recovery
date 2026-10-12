# P141-P150 Drawing Intelligence — Generation 2

Production-depth upgrade after the P1-P140 gap audit.

Implemented:
- sheet identity detection and page fallback
- title evidence extraction
- scale notation and metadata evidence
- confidence-based accept/review/reject decisions
- normalized member semantic linking across pages
- deterministic duplicate suppression
- fail-closed source identity handling

Boundary:
- missing engineering dimensions are never invented
- low-confidence recognition is never silently accepted
- source identity is mandatory for accepted lineage
