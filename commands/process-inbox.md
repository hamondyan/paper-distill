---
name: process-inbox
description: Move approved inbox notes into sources/evidence + sources/notes and hand them off to Zotero
user_invocable: true
---

Run the inbox processing workflow using the `paper-distill:source-ingest` skill in `approved_inbox` mode.

This asks the knowledge maintainer to ingest `status=approved` inbox notes, capture cleaned arXiv source content into `sources/evidence`, generate CRGP-DNL notes into `sources/notes`, and hand the paper off to Zotero in the configured mode.
