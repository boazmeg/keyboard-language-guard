import mac_accessibility


def test_secure_field_true_and_false(monkeypatch):
    mac_accessibility.reset_cache()
    monkeypatch.setattr(mac_accessibility, "_query_secure_field", lambda: True)
    assert mac_accessibility.is_secure_field_focused(use_cache=False) is True

    monkeypatch.setattr(mac_accessibility, "_query_secure_field", lambda: False)
    assert mac_accessibility.is_secure_field_focused(use_cache=False) is False


def test_cache_avoids_repeated_queries(monkeypatch):
    mac_accessibility.reset_cache()
    calls = {"n": 0}

    def counting_query():
        calls["n"] += 1
        return True

    monkeypatch.setattr(mac_accessibility, "_query_secure_field", counting_query)

    # First call populates the cache; the second is served from it.
    assert mac_accessibility.is_secure_field_focused() is True
    assert mac_accessibility.is_secure_field_focused() is True
    assert calls["n"] == 1


def test_reset_cache_forces_requery(monkeypatch):
    mac_accessibility.reset_cache()
    calls = {"n": 0}

    def counting_query():
        calls["n"] += 1
        return True

    monkeypatch.setattr(mac_accessibility, "_query_secure_field", counting_query)
    mac_accessibility.is_secure_field_focused()
    mac_accessibility.reset_cache()
    mac_accessibility.is_secure_field_focused()
    assert calls["n"] == 2
