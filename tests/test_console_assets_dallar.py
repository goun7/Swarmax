"""test_console_assets_dallar.py — _favicon_bytes + _hero_bytes dal-kesen suite.

ORTAM-ANATOMI (swarmax/console.py):
  _favicon_bytes() -> bytes (L52): module-level _FAVICON cache; ilk cagrida
    importlib.resources.files("swarmax").joinpath("assets/favicon-32.png")
    .read_bytes(); (FileNotFoundError, ModuleNotFoundError) -> b""
  _hero_bytes()   -> bytes (L65): ayni pattern, assets/hero-400.png

ORTAM-OGRENDILER:
  (1) Wheel ile gelen gercek PNG asset'leri: favicon-32.png = 2901 bayt,
      32x32 RGBA (bit-depth 8, color-type 6); hero-400.png = 94795 bayt,
      1200x400 RGB (bit-depth 8, color-type 2).
  (2) PNG magic: b'\x89PNG\r\n\x1a\n' + IHDR chunk (uzunluk 13).
  (3) Cache: tekrar cagri AYNI baytlari doner; global None -> ilk okuma.
  (4) Graceful degradation: asset bulunamazsa b"" doner (asla traceback).

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory (network/subprocess YASAK). --noconftest ZORUNLU.
"""
import importlib
import struct
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import console  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _ihdr(blob):
    assert blob[:8] == PNG_MAGIC
    assert blob[12:16] == b"IHDR"
    return struct.unpack(">II", blob[16:24])  # width, height


@pytest.fixture(autouse=True)
def _reset_asset_caches():
    # her test temiz cache ile baslar (Kural: state sızıntısı yok)
    console._FAVICON = None
    console._HERO = None
    yield
    console._FAVICON = None
    console._HERO = None


# ====================================================== _favicon_bytes ======
def test_favicon_bytes_returns_bytes():
    assert isinstance(console._favicon_bytes(), bytes)


def test_favicon_bytes_nonempty():
    assert len(console._favicon_bytes()) > 0


def test_favicon_bytes_png_magic():
    assert console._favicon_bytes()[:8] == PNG_MAGIC


def test_favicon_bytes_dimensions_32x32():
    w, h = _ihdr(console._favicon_bytes())
    assert (w, h) == (32, 32)


def test_favicon_bytes_ihdr_after_magic():
    blob = console._favicon_bytes()
    assert blob[12:16] == b"IHDR"
    assert struct.unpack(">I", blob[8:12])[0] == 13  # IHDR data length


def test_favicon_bytes_bit_depth_and_color_type():
    blob = console._favicon_bytes()
    assert blob[24] == 8       # bit depth
    assert blob[25] == 6       # color type 6 = RGBA


def test_favicon_bytes_cached_identical():
    a = console._favicon_bytes()
    b = console._favicon_bytes()
    assert a == b


def test_favicon_bytes_sets_module_cache():
    assert console._FAVICON is None
    blob = console._favicon_bytes()
    assert console._FAVICON is blob


def test_favicon_bytes_cache_reused_without_reread(monkeypatch):
    console._FAVICON = b"CACHED"
    # cache doluyken resources'a erisim olmamali
    monkeypatch.setattr(importlib.resources, "files",
                        lambda *a, **k: pytest.fail("cache doluyken okumamali"))
    assert console._favicon_bytes() == b"CACHED"


def test_favicon_bytes_reread_after_cache_reset():
    first = console._favicon_bytes()
    console._FAVICON = None
    second = console._favicon_bytes()
    assert first == second  # ayni asset, yeni okuma


def test_favicon_bytes_missing_asset_returns_empty(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("no asset")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._favicon_bytes() == b""


def test_favicon_bytes_module_not_found_returns_empty(monkeypatch):
    def boom(*args, **kwargs):
        raise ModuleNotFoundError("no module")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._favicon_bytes() == b""


def test_favicon_bytes_missing_asset_caches_empty(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise FileNotFoundError("no asset")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._favicon_bytes() == b""
    assert console._favicon_bytes() == b""
    assert len(calls) == 1  # b"" de cache'lenir


def test_favicon_bytes_known_length():
    # CHARACTERIZATION: wheel'e ship edilen asset boyutu (2901 bayt)
    assert len(console._favicon_bytes()) == 2901


def test_favicon_bytes_chunk_structure():
    blob = console._favicon_bytes()
    # IHDR + en az bir IDAT + IEND (0-uzunluk data + CRC)
    assert blob[-8:-4] == b"IEND"
    assert struct.unpack(">I", blob[-12:-8])[0] == 0
    assert b"IDAT" in blob


# ========================================================= _hero_bytes ======
def test_hero_bytes_returns_bytes():
    assert isinstance(console._hero_bytes(), bytes)


def test_hero_bytes_nonempty():
    assert len(console._hero_bytes()) > 0


def test_hero_bytes_png_magic():
    assert console._hero_bytes()[:8] == PNG_MAGIC


def test_hero_bytes_dimensions():
    w, h = _ihdr(console._hero_bytes())
    assert w == 1200 and h == 400


def test_hero_bytes_bit_depth_and_color_type():
    blob = console._hero_bytes()
    assert blob[24] == 8   # bit depth
    assert blob[25] == 2   # color type 2 = RGB


def test_hero_bytes_cached_identical():
    assert console._hero_bytes() == console._hero_bytes()


def test_hero_bytes_sets_module_cache():
    assert console._HERO is None
    blob = console._hero_bytes()
    assert console._HERO is blob


def test_hero_bytes_cache_reused_without_reread(monkeypatch):
    console._HERO = b"CACHED"
    monkeypatch.setattr(importlib.resources, "files",
                        lambda *a, **k: pytest.fail("cache doluyken okumamali"))
    assert console._hero_bytes() == b"CACHED"


def test_hero_bytes_reread_after_cache_reset():
    first = console._hero_bytes()
    console._HERO = None
    assert console._hero_bytes() == first


def test_hero_bytes_missing_asset_returns_empty(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("no asset")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._hero_bytes() == b""


def test_hero_bytes_module_not_found_returns_empty(monkeypatch):
    def boom(*args, **kwargs):
        raise ModuleNotFoundError("no module")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._hero_bytes() == b""


def test_hero_bytes_missing_asset_caches_empty(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise FileNotFoundError("no asset")
    monkeypatch.setattr(importlib.resources, "files", boom)
    assert console._hero_bytes() == b""
    assert console._hero_bytes() == b""
    assert len(calls) == 1


def test_hero_bytes_known_length():
    # CHARACTERIZATION: wheel'e ship edilen asset boyutu (94795 bayt)
    assert len(console._hero_bytes()) == 94795


def test_hero_bytes_chunk_structure():
    blob = console._hero_bytes()
    assert blob[-8:-4] == b"IEND"
    assert struct.unpack(">I", blob[-12:-8])[0] == 0
    assert b"IDAT" in blob


# ================================================== iki-fonksiyon karsilik ==
def test_favicon_and_hero_are_distinct():
    assert console._favicon_bytes() != console._hero_bytes()


def test_favicon_smaller_than_hero():
    assert len(console._favicon_bytes()) < len(console._hero_bytes())


def test_both_are_valid_png_with_crc_tail():
    for blob in (console._favicon_bytes(), console._hero_bytes()):
        assert len(blob) > 33
        assert blob[-8:-4] == b"IEND"
        # IEND chunk'u 0-uzunluk data + 4 bayt CRC
        assert struct.unpack(">I", blob[-12:-8])[0] == 0


def test_both_caches_independent():
    f = console._favicon_bytes()
    h = console._hero_bytes()
    assert console._FAVICON is f
    assert console._HERO is h
    assert console._FAVICON is not console._HERO
