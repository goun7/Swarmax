# Swarmax Dogfood Planı — MT-1…MT-8 (2 Hafta)

> **İlke:** Kendi ürünümüzü kendi geliştirme filomuzda işletmeden tek bir müşteri sözü
> etmiyoruz. Her ölçüm **kanıt defterinden** hesaplanır; elle yazılan hiçbir sayı
> kabul edilmez. Bu dosya kâğıdın §9 ölçüm taahhüt protokolünün yürütme planıdır;
> ölçüm tanımları oraya tabidir, burada tekrarlanmaz.

## 0. Pilot filo (gün 1'de kaydolur, `synthetic=0`)

| Ajan | Görev sınıfı | MT-1 replay seti | Otomatik doğrulama |
|---|---|---|---|
| `dog-doc` | Dokümantasyon güncelleme | n=10 görev (README/API doc düzeltmeleri) | diff + link kontrolü |
| `dog-test` | Birim test ekleme | n=10 görev (eksik test keşfi) | `pytest` yeşil + kapsam artışı |
| `dog-refactor` | Küçük refactor | n=10 görev (ölçülmüş fonksiyon bölmeleri) | testler yeşil + diff limiti |

Hepsi OTLP alımından (`make otlp`) beslenir — dogfood, §4.3 alım yolunun da
kabul testidir. §3.3 uyarınca 14 günlük kalibrasyon penceresi **gün 1'de açılır**;
bu pencere kapanmadan maliyet/adım alarmları bastırılır (konsolda görünür).

## 1. 14 günlük çizelge

| Gün | İş | Çıktı |
|---|---|---|
| 1 | Ajan kaydı + alım hattı + `MT-7` ilk koşusu | Kalibrasyon satırları açık; mühür zinciri doğrulandı |
| 2–5 | Gerçek görev akışı (haftalık iş yükü doğal akışı) | 7d referans penceresi dolar; günlük konsol triyajı |
| 6–7 | **Hata-enjeksiyon düzeneği** (`scripts/dogfood/fault_proxy.py`): rate-limit / 5xx / timeout enjeksiyonu, λ oranında | MT-4/MT-5 koşulabilir hale gelir |
| 8 | **MT-6** alarm-latency ölçümü: guard olayı → APD karar (doğrudan yol, R1) | p95 ≤ 500 ms raporu |
| 9 | **MT-8** metamorfik koşular (doc/test sınıflarında uç-durum eşdeğerliği) | İhlal oranı ≤ %2 |
| 10 | **MT-4** λ-eğrisi: λ ∈ {0.05, 0.1, 0.2} | λ=0.1'de düşüş ≤ 5 puan |
| 10 | **MT-5** kurtarma: enjeksiyon sonu → EWMA bandına dönüş | ≤ 60 sn |
| 11–13 | Kalibrasyon kapanır (gün 15'e kadar) → **MT-1/2/3** tam koşu: her görev sınıfında k=5, n=10 replay | pass^k ≥ 0.90 · CV(maliyet) ≤ 0.25 · CV(adım) ≤ 0.20 |
| 14 | Kapanış: tüm MT kartları mühürlü kanıtla + R10 FP bütçesi denetimi + **çıkış tatbikatı** | F3 kapısı kararı |

**Dürüst kısıt:** tek düğüm v1; MT-1/2/3'ün tam ölçümü kalibrasyon penceresi
yüzünden gün 11'den önce anlamlı değildir. MT-6/MT-7 kalibrasyondan bağımsızdır ve
gün 1'den itibaren doğrulanır — ertelenmez.

## 2. MT kartları (ölçüm → araç → kabul)

Her kart tek tablodur; "araç" sütunundaki scriptler `scripts/dogfood/` altına
gün 6–7'de düşer ve **depodaki mağazanın kendisini** sorgular (kendi ürünümüzle
ölçüyoruz — bu, dogfood'un ikinci amacıdır).

| Kart | Ölçüm kaynağı | Araç | Kabul |
|---|---|---|---|
| MT-1 | `agent_task_events` + replay koşucu | `run_mt1.py` (pass^k) | ≥ 0.90 (kritik sınıf) |
| MT-2 | `SUM(cost_usd)` / görev | `run_mt23.py` | CV ≤ 0.25 |
| MT-3 | görev başına olay sayısı | `run_mt23.py` | CV ≤ 0.20 |
| MT-4 | fault_proxy enjeksiyon günlüğü | `run_mt4.py` | λ=0.1 düşüş ≤ 5 puan |
| MT-5 | EWMA bandına dönüş zamanı | `run_mt5.py` | ≤ 60 sn |
| MT-6 | guard ts → APD karar ts farkı | `run_mt6.py` | p95 ≤ 500 ms |
| MT-7 | `verify_seals` + haftalık tatbikat | mevcut `scripts/exit_drill.py` | %100 |
| MT-8 | `end_state_json` karşılaştırması | mevcut metamorfik oracle | ihlal ≤ %2 |

## 3. Ölçüm şablonu (haftalık dogfood raporuna yapıştırılır)

```markdown
## Dogfood Haftası N (tarih aralığı)
- Alım: N olay, M reddi (anti-replay) — `ingest_reject_total`
- MT-1 pass^k: doc=?, test=?, refactor=?  → kabul ≥ 0.90  [kanıt: seq#…]
- MT-2 maliyet CV: ? / MT-3 adım CV: ?    → kabul ≤ 0.25 / ≤ 0.20
- MT-4 λ-eğrisi: λ=0.1 düşüş ? puan       → kabul ≤ 5
- MT-5 kurtarma ? sn                      → kabul ≤ 60
- MT-6 alarm p95 ? ms                     → kabul ≤ 500
- MT-7 mühür doğrulama ?%                 → kabul %100
- MT-8 uç-durum ihlal ?%                  → kabul ≤ 2
- FP bütçesi (R10): ?/? saatlik döngü ≤ %5
- §9.2 atribusiyon onay oranı: ?%         → hedef ≥ %70
- İnsan triyaj: ? alarm, ? çözüm, ort. ? dk
```

## 4. Yönetişim ve başarısızlık protokolü

- Her MT kartı **mühürlü kanıtla** kapanır (`seal` + `verify`); kart başarısızsa
  kâğıdın R-bulgu süreci işler: kök neden → kâğıt/codex düzeltmesi → yeniden koşu.
- Haftalık inceleme: konsol SLA kuyruğundaki tüm alarmlar triyaj edilmiş olmalı;
  açık ticket yaşlanması §4.2'ye göre otomatik yükselir.
- **F3 kapısı:** 8/8 MT kartı yeşil + FP bütçesi + tatbikat PASS olmadan hiçbir
  dış müşteri pilotu açılmaz.

## 5. Bu planın kendisi bir kabul ölçütüdür

MT-6'ya kadar araçlar gün 8'de hazır olmalı; gecikirse dogfood planı değil,
araç borcu olarak kaydedilir ve §14 R-sürecine girer.
