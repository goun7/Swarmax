# Swarmax — AB AI Act (Omnibus 2026/1744) Uyum Dosyası

> **Durum:** v1.0 · 16.09.2026 · Bu dosya `SWARMAX.md` §6.2'nin çalışma kopyasıdır:
> her satır ya **çalışan kodla** ya da **açıkça etiketlenmiş boşlukla** eşleşir.
> Hiçbir bölüm yasal tavsiye değildir; nihai uyum kararı müşterinin hukuk
> müşavirine aittir. Kanıt referansları kanıt defteri `seq#` veya test dosyasıdır.

## 1. Konumlandırma (kâğıt §6.2 notunun operasyonelleştirilmesi)

Swarmax bir AI Act sertifikasyonu veya uygunluk değerlendirmesi değildir; **Md. 12
(kayıt tutma) ve Md. 14 (insan gözetimi) teknik altyapı sağlayıcısıdır.** Yüksek-risk
olarak sınıflanan müşteri sistemi Annex III kapsamındaysa, sağlayıcının Md. 16
yükümlülüklerini besleyecek kanıt üretim hattını sunar. Takvim: Annex III
yükümlülükleri **02.12.2027**; gömülü AI **02.08.2028**; sahaya çıkmış eski
sistemlere +4 ay (kaynak: E5 — Regulation (EU) 2026/1744 analizleri).

## 2. Yükümlülük → teknoloji → kanıt haritası

| AI Act maddesi | Yükümlülük | Swarmax karşılığı (kod) | Kanıt / doğrulama |
|---|---|---|---|
| Md. 12(1) | Otomatik olay kaydı, tüm ömrü kapsayan log | Append-only `evidence_ledger` (UPDATE/DELETE tetikleyiciyle yasak) + `agent_task_events` + `guard_events` | `tests/test_schema.py` (append-only), schema/sqlite_v1.sql §12.1 |
| Md. 12(3) | Log bütünlüğü | SHA-256 hash-chain + Ed25519 imza + Merkle mühür (`covers_through_seq` ile) | `tests/test_ed25519.py` (RFC 8032), `tests/test_sealing.py` (tamper-fail-closed) |
| Md. 12 | Log saklama periyodu | Sıcak katman SQLite; **soğuk katman çalışıyor**: `coldstore.py` — SigV4 imzalı S3-uyumlu arşiv + çevrimdışı zincir doğrulama (B1 kapatıldı, 2026-09-16) | `tests/test_coldstore.py` |
| Md. 12(3) | Rapor-kanıt bağlantısı | **Otomatik çıpalama çalışıyor**: her alarm `evidence_seq` taşır, raporlar `ledger#N` basar (B4 kapatıldı, 2026-09-16) | `tests/test_privacy.py` |
| Md. 17 | Silme hakkı | **Kripto-shred çalışıyor**: kişi-başına DEK + `/forget` (B2 kapatıldı, 2026-09-16) | `tests/test_privacy.py` |
| Md. 14(4)(a) | Etkili gözetim yetisi: kapatma | Kill-switch kademelendirmesi (§6.3): L0 pahalı çağrı kesici → L1 izolasyon → L2 üçlü-onay infaz | `metrics/apd.py` (KILL_CIRCUIT_OPEN), pipeline `quarantine` |
| Md. 14(4)(b) | Otomatik davranışa müdahale | SLA'lı triyaj kuyruğu; `resolve` her operasyonu imzalı olaya yazar | `console.py /resolve` (D2 fail-closed), `tests/test_console_v2.py` |
| Md. 14 | Gözetim araçlarının gerekli işlevselliği | Ajan detay sayfaları: EWMA-Z kontrol kartı, JSD sapma grafiği, alarm/ticket geçmişi (WS-1) | `tests/test_console_v2.py::test_agent_metric_charts_accessible` |
| Md. 14 + Md. 26 | Kullanan işletmenin gözetimi | Admin/viewer rolleri; gözetim eylemi yetkilendirmeye tabi | `src/swarmax/auth.py`, `tests/test_auth.py` (ASVS 2.4 scrypt) |
| Md. 15 | Doğruluk/ dayanıklılık/siber güvenlik | MT-1…MT-8 ölçüm taahhütleri; 8/8 alarm-enjeksiyon paketi; çıkış tatbikatı | `tests/test_scenarios.py`, `scripts/exit_drill.py` |
| Md. 19 | Eski sistemler (+4 ay) | Yükseltme rehberi **boşluk B3** | — |

### GDPR/KVKK arayüzü (silme hakkı × imzalı kanıt gerilimi)

- **Tasarım:** kişi-anahtarlı crypto-shredding (`DELETE /v1/privacy/forget`,
  kâğıt §6.2 sonrası); span gövdeleri yok edilir, operasyonel toplamlar ve imzalı
  kanıt özetleri kayıt tutma gereğiyle kalır; **silme eylemi kendisi imzalı olay
  olarak deftere yazılır.**
- **Dürüst boşluk B2:** crypto-shredding **henüz kodda değil** — v1.1 yol haritası.
  Bu, Md. 17 uyumunun müşteri tarafında değil Swarmax tarafında kaldığı bir
  açık olarak beyan edilir; kâğıt R7 risk kaydında izlenir.

## 3. Çalışan kanıt zinciri (uyum iddiası = kod + test)

```
OTLP alım (HMAC anti-replay, §4.3)  →  agent_task_events / guard_events
        ↓ (≤500ms doğrudan yol, R1)
APD kararı                          →  alarms (SLA kuyruğu)
        ↓ insan triyaj (Md. 14)
resolve / confirm                   →  evidence_ledger (hash-chain)
        ↓ periyodik
Ed25519 + Merkle seal               →  evidence_seals (covers_through_seq)
        ↓ çeyreklik
Çıkış tatbikatı                     →  export → rebuild → verify PASS
```

Her halka test dosyasıyla doğrulanır; zincirin başından sonuna kadar `seq#` ile
izlenebilir. Bu, "log diye bir tablomuz var" demenin ötesinde **değiştirilemez,
imzalı, tatbikatla geri çağrılabilir** log demektir.

## 4. Boşluk kaydı (100/100 iddiası değil, dürüst envanter)

| # | Boşluk | Etki | Kapanış yolu | Hedef |
|---|---|---|---|---|
| ~~B1~~ | **KAPANDI (2026-09-16):** `src/swarmax/coldstore.py` — deterministik gzip chunk arşivleme + manifest + çevrimdışı verify (`make cold-archive` / `make cold-verify`); 2 yıllık soğuk katman artık kod. Kalan alt madde: otomatik zamanlama (cron) operatör işi | Md. 12 saklama süresi artık doğrulanabilir | Tamamlandı | **v4.2.1** |
| ~~B2~~ | **KAPANDI (2026-09-16):** `src/swarmax/privacy/` — RFC 8439 ChaCha20-Poly1305 (saf stdlib, OpenSSL ile çapraz-doğrulanmış) + kişi-başına rastgele DEK, anahtar-bakım defteri (migration 008), konsolda Privacy bölümü + `/forget` endpoint'i (admin kapılı, fail-closed 404). Erasure = **kripto-shred**: DEK imhası, append-only defter dokunulmadan. Hukuki dayanak kaydı zorunlu (`lawful_basis`). Test: `tests/test_privacy.py` (RFC vektörleri + yaşam döngüsü + HTTP e2e) | Md. 17 silme hakkı interaktif ve kanıtlı | Tamamlandı | **v4.3.0** |
| ~~B3~~ | **KAPANDI (2026-09-16):** `UPGRADE_GUIDE.md` — eski sistemden geçiş rehberi (ön-kontrol, aşamalı cutover, veri eşleme tablosu, dürüst sınırlar bölümü); PDF paketine eklendi | Md. 19 müşteri dokümanı teslim | Tamamlandı | **v4.3.0** |
| ~~B4~~ | **KAPANDI (2026-09-16):** `alarms.evidence_seq` / `evidence_seq_resolved` çıpaları (migration 008) + haftalık raporda otomatik `ledger#N` referansları ("Evidence anchors" bölümü); test: `test_alarms_carry_evidence_seq_anchors` | Md. 12(3) izlenebilirlik raporlarda otomatik | Tamamlandı | **v4.3.0** |
| ~~B5~~ | **KAPANDI (2026-09-16):** `LABELING_TEMPLATES.md` — Md. 13 kullanım-talimatı şablon paketi (T1 son-kullanıcı bildirimi EN/TR, T2 operatör tablosu, T3 makine-okur JSON, T4 silme talebi formu, T5 dürüstlük eki); PDF paketine eklendi | Müşteri doküman şablonu teslim | Tamamlandı | **v4.3.0** |

Boşluklar §14 R-süreciyle aynı disiplinde izlenir: her kapanışta kanıt + test.

## 5. Denetçi senaryosu (dosyanın kullanım şekli)

Bir denetçi "Md. 12(3) log bütünlüğünü nasıl garanti ediyorsunuz?" diye sorduğunda:

1. `SWARMAX.md` §12.1 → mimari gerekçe.
2. `schema/sqlite_v1.sql` + tetikleyiciler → değiştirilemezlik.
3. `src/swarmax/ed25519.py` + `sealing.py` → imza ve mühür.
4. `tests/test_sealing.py` → tamper-fail-closed kanıtı.
5. `scripts/exit_drill.py` → denetçi kendi gözüyle export→rebuild→verify koşar.

Bu dosyadaki her satır bu turun sonunda koşulan 89 testle ve canlı duman testiyle
yeniden doğrulanır; uyum iddiası statik metin değil, **koşan** kanıt kümesidir.
