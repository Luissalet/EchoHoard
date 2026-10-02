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


def test_search_text_that_looks_like_fts_syntax_is_just_words(services):
    """The old builder left terms unquoted: a copied `NEAR(`, a stray quote or `-x` made the MATCH fail and the search came back empty."""
    services.clips.capture_text("el comando git log -n 5 --oneline", source_app="terminal", source_title="", now=services.now())
    services.clips.capture_text('cadena "entre comillas" AND otra', source_app="editor", source_title="", now=services.now())
    for hostile in ('NEAR(', '"', 'a OR', '-n', 'git AND', '*', 'col:valor', '(((', "'; DROP TABLE clips; --"):
        assert isinstance(services.search.search(hostile), list)
    assert any("git log" in h["preview"] for h in services.search.search("git log -n"))
    assert any("entre comillas" in h["preview"] for h in services.search.search('"entre comillas" AND'))


def test_search_falls_back_to_any_word_when_not_all_match(services):
    seed(services)
    hits = services.search.search("valdeniebla receta")  # nothing contains both words, two clips contain the first
    assert len(hits) == 2 and all("aldeniebla" in h["preview"] for h in hits)
    assert services.search.search("inexistente receta") == []
