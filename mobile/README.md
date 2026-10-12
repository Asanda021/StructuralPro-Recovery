# StructuralPro Mobile Contract
Windows and Android share the same provider-neutral ClientRequest/ClientResponse and SyncRecord contracts.
Android is offline-capable and uses the authoritative local core contract; Telegram is an online client and never becomes a second engineering engine.
Conflict handling is explicit: no client silently overwrites a newer version. Disjoint fields may be merged; overlapping fields require an explicit local/remote decision.
