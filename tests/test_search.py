"""FTS5 search: diacritics-insensitive, prefix match, filters, never leaks sensitive content."""


def seed(services):
    services.clips.capture_text("Informe de Valdeniebla, tercer trimestre", source_app="editor", source_title="informe.md", now=services.now())
    services.clips.capture_text("https://valdeniebla.example/mapa", source_app="navegador", source_title="Mapa", now=services.now())
    services.clips.capture_text("Lista de la compra: pan, leche, café", source_app="notas", source_title="Notas", now=services.now())


def test_search_matches_accent_insensitive_and_prefix(services):
    seed(services)
    hits = services.search.search("valdeniebla")  # no accent needed for "Valdeniebla"
    assert any("Valdeniebla" in h["preview"] for h in hits)
    prefix_hits = services.search.search("infor")
    assert any("Informe" in h["preview"] for h in prefix_hits)
    none_hits = services.search.search("inexistente")
    assert none_hits == []


def test_search_filters_by_kind(services):
    seed(services)
    urls = services.search.search("valdeniebla", kind="url")
    assert all(h["kind"] == "url" for h in urls)


def test_search_snippet_has_mark_tags(services):
    seed(services)
    hits = services.search.search("compra")
    assert hits and "<mark>" in hits[0]["snippet"]


def test_search_empty_query_returns_nothing(services):
    seed(services)
    assert services.search.search("   ") == []


def test_search_never_surfaces_sensitive_content(services):
    services.clips.capture_text("sk-abcdefghijklmnopqrstuvwx", source_app="terminal", source_title="", now=services.now())
    hits = services.search.search("abcdefghijklmnopqrstuvwx")
    assert hits == []
    # searching for the placeholder word itself does find the row, but never the secret
    hits2 = services.search.search("oculto")
    assert len(hits2) == 1
    assert hits2[0]["sensitive"] is True
    assert "sk-" not in hits2[0]["snippet"]
