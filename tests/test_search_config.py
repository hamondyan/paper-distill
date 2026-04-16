from __future__ import annotations

import asyncio

from server.search import crossref, openalex, semantic_scholar, unpaywall


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _RecordingAsyncClient:
    def __init__(self, requests: list[dict], payload: dict, *, headers: dict | None = None, **_: object) -> None:
        self._requests = requests
        self._payload = payload
        self._headers = dict(headers or {})

    async def __aenter__(self) -> "_RecordingAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self._requests.append(
            {
                "url": url,
                "params": dict(params or {}),
                "headers": dict(self._headers),
            }
        )
        return _FakeResponse(self._payload)


def test_search_openalex_uses_settings_contact_email(monkeypatch) -> None:
    requests: list[dict] = []

    monkeypatch.setattr(
        openalex,
        "get_search_settings",
        lambda: {
            "contact_email": "settings@example.com",
            "unpaywall_email": "",
            "semantic_scholar_api_key": "",
        },
    )
    monkeypatch.setattr(
        openalex.httpx,
        "AsyncClient",
        lambda **kwargs: _RecordingAsyncClient(requests, {"results": []}, **kwargs),
    )

    assert asyncio.run(openalex.search_openalex("robotics", max_results=3)) == []
    assert requests[0]["params"]["mailto"] == "settings@example.com"


def test_resolve_crossref_uses_settings_contact_email(monkeypatch) -> None:
    requests: list[dict] = []

    monkeypatch.setattr(
        crossref,
        "get_search_settings",
        lambda: {
            "contact_email": "settings@example.com",
            "unpaywall_email": "",
            "semantic_scholar_api_key": "",
        },
    )
    monkeypatch.setattr(
        crossref.httpx,
        "AsyncClient",
        lambda **kwargs: _RecordingAsyncClient(requests, {"message": {"title": ["Test Paper"], "DOI": "10.1/test"}}, **kwargs),
    )

    result = asyncio.run(crossref.resolve_crossref("10.1/test"))

    assert result["doi"] == "10.1/test"
    assert "mailto:settings@example.com" in requests[0]["headers"]["User-Agent"]


def test_search_semantic_scholar_uses_settings_api_key(monkeypatch) -> None:
    requests: list[dict] = []

    monkeypatch.setattr(
        semantic_scholar,
        "get_search_settings",
        lambda: {
            "contact_email": "",
            "unpaywall_email": "",
            "semantic_scholar_api_key": "settings-s2-key",
        },
    )
    monkeypatch.setattr(
        semantic_scholar.httpx,
        "AsyncClient",
        lambda **kwargs: _RecordingAsyncClient(requests, {"data": []}, **kwargs),
    )

    assert asyncio.run(semantic_scholar.search_semantic_scholar("robotics", max_results=3)) == []
    assert requests[0]["headers"]["x-api-key"] == "settings-s2-key"


def test_lookup_unpaywall_falls_back_to_settings_contact_email(monkeypatch) -> None:
    requests: list[dict] = []

    monkeypatch.setattr(
        unpaywall,
        "get_search_settings",
        lambda: {
            "contact_email": "settings@example.com",
            "unpaywall_email": "",
            "semantic_scholar_api_key": "",
        },
    )
    monkeypatch.setattr(
        unpaywall.httpx,
        "AsyncClient",
        lambda **kwargs: _RecordingAsyncClient(
            requests,
            {
                "is_oa": True,
                "oa_status": "gold",
                "journal_name": "Journal",
                "publisher": "Publisher",
                "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
            },
            **kwargs,
        ),
    )

    result = asyncio.run(unpaywall.lookup_unpaywall("10.1/test"))

    assert result["best_oa_url"] == "https://example.com/paper.pdf"
    assert requests[0]["params"]["email"] == "settings@example.com"
