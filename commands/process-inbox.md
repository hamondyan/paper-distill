---
name: process-inbox
description: Move approved inbox notes into raw/source + raw/notes and hand them off to Zotero
user_invocable: true
---

Run the inbox processing workflow using the `paper-distill:process-inbox` skill.

This asks the knowledge maintainer to ingest `status=approved` inbox notes, capture cleaned arXiv source content into `raw/source`, generate CRGP-DNL notes into `raw/notes`, and hand the paper off to Zotero in the configured mode.
