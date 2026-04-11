---
name: process-inbox
description: Move approved inbox notes into sources/evidence + wiki/papers and hand them off to Zotero
user_invocable: true
---

Run the inbox processing workflow using the `paper-distill:paper-intake` skill in `approved_inbox` mode.

This asks the knowledge maintainer to ingest `status=approved` inbox notes, capture cleaned arXiv source content into `sources/evidence`, create or refresh canonical pages in `wiki/papers`, and hand the paper off to Zotero in the configured mode.
