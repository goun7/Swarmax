"""G42 README-pin: Swarmax README test-sayisi stale-kalinti-olamaz.

Kapsam: `pytest tests --collect-only -q` ( README 3426). Bu depo summary
satiri yerine dosya-basi "tests/x.py: N" ciktisi verir; pin her iki yolu da
toplar. tests/test_landing.py 26-test satiri ayca-etiketlidir ( README 406.
satir) ve ayni collect-ciktitinda-oldugu icin pin tek sayiya karsilar.
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")


def _collected_total(res_stdout: str) -> int:
    m = re.search(r"(\d+)\s+tests?\s+collected", res_stdout)
    if m:
        return int(m.group(1))
    total = 0
    for mm in re.finditer(r"^tests/[\w./-]+\.py:\s*(\d+)\s*$", res_stdout, re.M):
        total += int(mm.group(1))
    return total


def test_readme_test_count_is_not_stale():
    readme = io.open(README, encoding="utf-8").read()
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=1800,
    )
    assert res.returncode == 0, "collect-only basarisiz: %s" % res.stderr[-400:]
    collected = _collected_total(res.stdout)
    # SW-G42B: toplanan-sayi ORTAMA-GORE-DEGISIR — cryptography-kuruluysa
    # iki-capraz-dogrulama-dosyasi-tamaminia-toplanir ( module-seviye
    # importorskip); stdlib-only-CI'de-0-toplanir. Onceki-pin-bunu-gormedi
    # ve sadece-gelistirme-makinesinde-gecerliydi ( CI-39404204296-patlamasi).
    # README-standarti: stdlib-CI-esdegeri — pin HER-ortamda-ayni-degeri
    # bekler ( makine-bagimli-false-green-olamaz). Ek-miktar-collect-
    # ciktilarindan-olculur ( sabit-SAYI-tutmayacak-biyuktedir: 643+51=694).
    crypto_extra = 0
    for line in res.stdout.splitlines():
        m = re.match(r"^(tests/test_ed25519_crypto_dallar\.py|tests/test_jwk_rsa_dallar\.py):\s*(\d+)\s*$", line)
        if m:
            crypto_extra += int(m.group(2))
    ci_equivalent = collected - crypto_extra
    stale = []
    for m in re.finditer(r"(\d[\d.,]*)\s*tests\s*\(", readme):
        claimed = int(m.group(1).replace(".", "").replace(",", ""))
        if claimed != ci_equivalent:
            stale.append(m.group(0))
    assert not stale, (
        "README tests-sayisi stale: %s (taze collect-only=%d, stdlib-CI-esdegeri=%d)"
        % (stale, collected, ci_equivalent)
    )
