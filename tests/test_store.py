"""ClipStore: dedupe on sha256, kind/sensitive detection at capture time,
labels/tags/pin, soft delete + restore + purge, retention/cap."""

from fixtures import SAMPLE_TEXTS, TINY_PNG, TINY_PNG_SIZE


def test_capture_text_is_new_then_dedupes_and_bumps_times(services):
    clock = services.clock
    first = services.clips.capture_text("Reunión el jueves", source_app="notas", source_title="Notas", now=clock())
    assert first["times"] == 1 and first["kind"] == "text"
    clock.advance(seconds=30)
    second = services.clips.capture_text("Reunión el jueves", source_app="navegador", source_title="Pestaña", now=clock())
    assert second["id"] == first["id"]
    assert second["times"] == 2
    assert second["source_app"] == "navegador"
    assert second["last_seen_at"] == clock.value
    assert services.clips.count() == 1


def test_capture_text_detects_kind():
    pass  # covered thoroughly in test_detect.py; the store just calls detect_kind


def test_capture_detects_kind_per_clip(services):
    kinds = {}
    for text in SAMPLE_TEXTS:
        clip = services.clips.capture_text(text, source_app="a", source_title="", now=services.now())
    clip_a = services.clips.capture_text("https://valdeniebla.example/x", source_app="a", source_title="", now=services.now())
    assert clip_a["kind"] == "url"
    clip_b = services.clips.capture_text("42", source_app="a", source_title="", now=services.now())
    assert clip_b["kind"] == "number"


def test_capture_sensitive_text_never_stores_the_real_content(services):
    clip = services.clips.capture_text("sk-abcdefghijklmnopqrstuvwx", source_app="terminal", source_title="", now=services.now())
    assert clip["sensitive"] is True
    assert clip["text"] == "[oculto: token]"
    assert clip["preview"] == "[oculto: token]"
    assert "sk-" not in clip["text"]
    # even the FTS index only ever saw the placeholder
    hits = services.search.search("sk-abcdefghijklmnopqrstuvwx")
    assert hits == []


def test_capture_image_stores_png_file_and_dedupes(services, tmp_path):
    clip = services.clips.capture_image(TINY_PNG, width=TINY_PNG_SIZE[0], height=TINY_PNG_SIZE[1],
                                         source_app="visor", source_title="Captura", now=services.now())
    assert clip["kind"] == "image"
    assert clip["image_width"] == TINY_PNG_SIZE[0]
    assert "imagen" in clip["text"]
    path = services.clips.image_path(clip["id"])
    assert path is not None and path.read_bytes() == TINY_PNG

    services.clock.advance(seconds=5)
    again = services.clips.capture_image(TINY_PNG, width=TINY_PNG_SIZE[0], height=TINY_PNG_SIZE[1],
                                          source_app="visor", source_title="Captura", now=services.now())
    assert again["id"] == clip["id"]
    assert again["times"] == 2
    assert services.clips.count() == 1


def test_update_label_tags_pinned(services):
    clip = services.clips.capture_text("Etiquetable", source_app="a", source_title="", now=services.now())
    updated = services.clips.update(clip["id"], {"label": "Importante", "tags": ["Trabajo", "trabajo", " urgente "], "pinned": True})
    assert updated["label"] == "Importante"
    assert updated["tags"] == ["trabajo", "urgente"]
    assert updated["pinned"] is True


def test_soft_delete_restore_and_purge(services):
    clock = services.clock
    clip = services.clips.capture_text("Borrable", source_app="a", source_title="", now=clock())
    assert services.clips.soft_delete(clip["id"], clock()) is True
    assert services.clips.get(clip["id"]) is None
    assert services.clips.get(clip["id"], include_deleted=True)["deleted_at"] == clock.value
    assert services.clips.soft_delete(clip["id"], clock()) is False  # already deleted

    assert services.clips.restore(clip["id"]) is True
    assert services.clips.get(clip["id"]) is not None
    assert services.clips.restore(clip["id"]) is False  # not deleted anymore

    services.clips.soft_delete(clip["id"], clock())
    clock.advance(seconds=3600)  # within the 24h undo window
    purged = services.clips.purge_deleted_older_than(clock() - 86400)
    assert purged == 0
    clock.advance(days=2)
    purged = services.clips.purge_deleted_older_than(clock() - 86400)
    assert purged == 1
    assert services.clips.get(clip["id"], include_deleted=True) is None


def test_purge_before_is_irreversible_and_skips_pinned(services):
    clock = services.clock
    old = services.clips.capture_text("Antiguo", source_app="a", source_title="", now=clock())
    clock.advance(days=1)
    pinned = services.clips.capture_text("Fijado", source_app="a", source_title="", now=clock())
    services.clips.update(pinned["id"], {"pinned": True})
    clock.advance(days=1)
    recent = services.clips.capture_text("Reciente", source_app="a", source_title="", now=clock())

    cutoff = clock.value - 86400  # everything strictly before "recent"
    deleted = services.clips.purge_before(cutoff)
    assert deleted == 1
    assert services.clips.get(old["id"]) is None
    assert services.clips.get(pinned["id"]) is not None  # pinned survives
    assert services.clips.get(recent["id"]) is not None


def test_apply_retention_ages_out_unpinned_past_retention_days(services):
    clock = services.clock
    old = services.clips.capture_text("Viejo", source_app="a", source_title="", now=clock())
    clock.advance(days=40)
    fresh = services.clips.capture_text("Nuevo", source_app="a", source_title="", now=clock())
    result = services.clips.apply_retention(clock.value, retention_days=30, max_clips=5000, max_image_mb=200)
    assert result["deleted_age"] == 1
    assert services.clips.get(old["id"]) is None
    assert services.clips.get(fresh["id"]) is not None


def test_apply_retention_respects_pinned_clips(services):
    clock = services.clock
    old = services.clips.capture_text("Viejo pero fijado", source_app="a", source_title="", now=clock())
    services.clips.update(old["id"], {"pinned": True})
    clock.advance(days=40)
    services.clips.apply_retention(clock.value, retention_days=30, max_clips=5000, max_image_mb=200)
    assert services.clips.get(old["id"]) is not None


def test_apply_retention_caps_total_clip_count(services):
    clock = services.clock
    ids = []
    for i in range(5):
        clip = services.clips.capture_text(f"Copia {i}", source_app="a", source_title="", now=clock())
        ids.append(clip["id"])
        clock.advance(seconds=1)
    result = services.clips.apply_retention(clock.value, retention_days=0, max_clips=3, max_image_mb=200)
    assert result["deleted_cap"] == 2
    assert services.clips.count() == 3
    # the oldest ones are the ones gone
    assert services.clips.get(ids[0]) is None
    assert services.clips.get(ids[1]) is None
    assert services.clips.get(ids[-1]) is not None


def test_apply_retention_caps_image_bytes(services):
    clock = services.clock
    first = services.clips.capture_image(TINY_PNG, width=2, height=2, source_app="a", source_title="", now=clock())
    clock.advance(seconds=1)
    second = services.clips.capture_image(TINY_PNG + b"\x00", width=2, height=2, source_app="a", source_title="", now=clock())
    total = services.clips.images_total_bytes()
    result = services.clips.apply_retention(clock.value, retention_days=0, max_clips=5000, max_image_mb=0)
    assert result["deleted_images"] >= 1
    assert services.clips.images_total_bytes() < total


def test_list_filters_by_kind_and_pinned(services):
    services.clips.capture_text("https://valdeniebla.example", source_app="a", source_title="", now=services.now())
    text_clip = services.clips.capture_text("una frase cualquiera", source_app="a", source_title="", now=services.now())
    services.clips.update(text_clip["id"], {"pinned": True})

    urls = services.clips.list(kind="url")
    assert len(urls) == 1 and urls[0]["kind"] == "url"
    pinned = services.clips.list(pinned=True)
    assert len(pinned) == 1 and pinned[0]["id"] == text_clip["id"]
