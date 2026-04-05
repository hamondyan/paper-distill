---
name: process-inbox
description: Move approved inbox notes into raw/source + raw/notes and hand them off to Zotero
user_invocable: true
---

Run the inbox processing workflow using the `paper-distill:process-inbox` skill.

This reads `status=approved` inbox notes, captures cleaned arXiv source content into `raw/source`, generates CRGP-DNL notes into `raw/notes`, then either exports local Zotero import packs or creates cloud Zotero items depending on the configured mode.
