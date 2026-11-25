from __future__ import annotations

from pytest import MonkeyPatch

from zabm import cli
from zabm.web import WEB_PAGE


def test_web_defaults_to_all_network_interfaces() -> None:
    args = cli._parser().parse_args(["web"])  # pyright: ignore[reportPrivateUsage]

    assert args.host == "0.0.0.0"


def test_wildcard_web_binding_reports_local_and_network_urls(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_local_ipv4_addresses", lambda: ("192.168.1.42",))

    assert cli._web_urls("0.0.0.0", 8765) == (  # pyright: ignore[reportPrivateUsage]
        "http://127.0.0.1:8765",
        "http://192.168.1.42:8765",
    )


def test_explicit_loopback_binding_reports_only_the_loopback_url() -> None:
    assert cli._web_urls("127.0.0.1", 8765) == (  # pyright: ignore[reportPrivateUsage]
        "http://127.0.0.1:8765",
    )


def test_web_page_renders_localized_korean_answer_prose() -> None:
    assert "response.localized.claims.map" in WEB_PAGE
    assert "displayClaims(response)" in WEB_PAGE
    assert "지원되는 답변" in WEB_PAGE
