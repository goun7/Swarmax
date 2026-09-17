# SWARMAX — Agentic Fleet Operations Platform (Ajan İş Gücü İşletim Katmanı)
### Kanonik Master Blueprint · Doğrulanmış Veri · Bilimsel Temel · Ürün, Mimari, Ticarileşme ve 12 Haftalık Yürütme Planı (100/100)

> **Durum:** KÂĞIT — Doğrulanmış Master Blueprint · **Sürüm:** v4.3.2 · **Tarih:** 2026-09-17
> **Öncül:** `FLEETMIND.md` v3.5'in doğrudan halefi. Ad değişikliği: Fleetmind → Herdwork → **Swarmax** (bkz. `ESKI_KIMLIK.md`). Bu belge, önceki şartnameyi iptal edip yerine geçer (supersede); farklar §13.1'de.
> **Kanonik çıktı:** `SWARMAX.md` (bu dosya). Eski adla yapılan tüm referanslar bu dosyaya delege edilmiştir.
> **Dönüşüm cümlesi:** *“Üretimde otonom ajan filosu işleten ekiplere; her ajanın maliyetini, gecikmesini, hata sınıflarını ve davranış sürüklenmesini tek ekranda gösterir; SLA ihlallerini baştan önler; anomalilerde kanıta dayalı, SLA'lı insan eskalasyonu (HITL) garantilerim.”*

---

## 0. KANIT ve SÜRÜM DİSİPLİNİ (Evidence Ledger)

Bu belgedeki her pazar, mevzuat ve standart iddiası doğrulanmış ve tarih damgalıdır. Kural: **“Kanıtsız rakam = silinir.”**

| # | Kanıt | Özet | Kaynak / Tarih |
|---|---|---|---|
| E1 | Gartner: agentic projelerin **%40+**'ı 2027 sonuna kadar iptal riskinde | Nedenler: maliyet kaçakları, belirsiz iş değeri, yetersiz risk kontrolleri | [Gartner PR, 25.06.2025](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) |
| E2 | Gartner: **$234 M** kurumsal uygulama yazılımı harcaması agentic AI'a maruz | Fiyatlandırma modellerinde kopuş sinyali | [Gartner PR, 01.07.2026](https://www.gartner.com/en/newsroom/press-releases/2026-07-01-gartner-says-us-dollars-234-billion-in-enterprise-application-software-spend-is-at-risk-from-agentic-artificial-intelligence) |
| E3 | Gartner: agentic AI yazılım harcaması **2030'da $985 M** (2025–30 CAGR %62,7) | Kategori 2025'te sıfıra yakınken patlayıcı büyüme | [Gartner Forecast Analysis, Şub 2026](https://www.gartner.com/en/documents/7455226) |
| E4 | Gartner: 2026'da kurumsal uygulamaların **%40**'ı görev-özel ajan içerecek (2025: <%5) | Talep tarafı: filo işletme ihtiyacı katlanarak büyür | [Gartner PR, 26.08.2025](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025) |
| E5 | **Digital Omnibus on AI = Regulation (EU) 2026/1744**, yürürlük: 27.07.2026 | Yüksek-risk yükümlülükleri 02.08.2026 → **02.12.2027** (Annex III) / 02.08.2028 (gömülü AI); eski tarihli sistemlere 4 ay ek süre | [EU AI Compass](https://euaicompass.com/digital-omnibus-proposal-2027-deadline-extension.html) · [Gibson Dunn, 27.05.2026](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/) · [Orrick, 29.07.2026](https://www.orrick.com/en/Insights/2026/07/EU-AI-Act-Update-Digital-Omnibus-Finalizes-8-Compliance-Changes) · [CSA, 01.08.2026](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-high-risk-deadline-omnibus-20260/) |
| E6 | OTel **GenAI semconv** ayrı repoya taşındı; **tüm `gen_ai.*` öznitelikleri Development** statüsünde | "Stable" iddiası yapılamaz; pin + sürüm disiplini zorunlu | [open-telemetry/semantic-conventions-genai — attribute registry](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md) · [opentelemetry.io yönlendirme sayfası](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (erişim: 14.09.2026) |
| E7 | **MAST**: çok-ajanlı LLM sistemlerinde 14 hata modu; üç aile (şartname / ara-iletişim / asistan doğrulaması); ~1.600 iz analizi | Hata sınıflandırmamızın akademik temeli | Cemri ve ark., [arXiv:2503.13657](https://arxiv.org/abs/2503.13657) · NeurIPS 2025 D&B |
| E8 | **ReliabilityBench**: üretim-benzeri stres altında ajan güvenilirliği; tekrarlı koşularda tutarlılık boyutu | Tek-koşu başarı metriklerinin yetersizliği; ölçüm-taahhüt metriklerimizin temeli | [arXiv:2601.06112](https://arxiv.org/abs/2601.06112), Ocak 2026 |
| E9 | MITRE **ATLAS v5.1.0** (Kas 2025): 16 taktik / 84 teknik; agentic vurgusu | Tehdit modelinin çerçevesi | [atlas.mitre.org](https://atlas.mitre.org/) · [Vectra özeti](https://www.vectra.ai/topics/mitre-atlas) |
| E10 | **OWASP Agentic AI — Threats & Mitigations** (ASI) + **OWASP GenAI LLM Top 10 (2026 baskısı, 03.08.2026)** | Denetim kontrolü setimiz | [OWASP Agentic T&M](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) · [OWASP LLM Top 10 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) |
| E11 | Langfuse ClickHouse tarafından satın alındı (Ocak 2026); birim-bazlı (unit-based) faturalama; LangSmith ~$39/koltuk/ay | Rekabet manzarası 2026 H2 itibarıyla | [Latitude, 27.03.2026](https://latitude.so/blog/best-llm-observability-tools-agents-latitude-vs-langfuse-langsmith) · [Pydantic Logfire fiyat karşılaştırması, 31.03.2026](https://pydantic.dev/articles/ai-observability-pricing-comparison) · [OpenObserve, 31.07.2026](https://openobserve.ai/blog/langfuse-vs-langsmith/) |
| E12 | ClickHouse mühendislik blogu: “GenAI + MCP semconv'ları Development statüsünde” (May 2026 itibarıyla) | E6'nın bağımsız doğrulaması | [ClickHouse, 29.07.2026](https://clickhouse.com/resources/engineering/opentelemetry-semantic-conventions) |
| E13 | Türkiye: GVK mükerrer 89/1-b — yurt dışına sağlanan yazılım hizmeti kazancının **%80'i istisna** | TR merkezli kuruluş için vergi optimizasyonu | GVK mükerrer md. 89/1-b; güncel metin: [gib.gov.tr](https://www.gib.gov.tr) (erişim 14.09.2026) |
| E14 | **Who&When**: çok-ajanlı LLM sistemlerinde **otomatik hata-atribusiyonu** (hangi ajan, hangi adımda suçlu); ICML 2025 spotlight, 222+ atıf | Eskalasyon biletlerinde sorumlu ajan/adım önerisinin akademik temeli | Zhang ve ark., [arXiv:2505.00212](https://arxiv.org/abs/2505.00212) · ICML 2025 |
| E15 | **Alanın güncel SOTA'sı (Nisan 2026):** TraceElephant — 311K üretim izinden derlenen hata-atribusiyon benchmark'ı, ortalama **%65,9** doğru-adım doğruluğu; bağımsız olarak çok-perspektifli benchmark kritiği (arXiv:2603.25001, Mart 2026) tek-perspektifli değerlendirmenin yetersizliğini gösteriyor | Otomatik atribusiyonun insan-döngüde kalması *kâğıdın kendi kararının* SOTA ile doğrulanması; v1.1 kabul kapısı bu rakama göre kalibre | [TraceElephant, arXiv:2604.22708](https://arxiv.org/abs/2604.22708) · [arXiv:2603.25001](https://arxiv.org/abs/2603.25001) (erişim 15.09.2026; hakem durumu beyan edilmedi — v1.1 kapısı E15 doğrulanmadan açılmaz) |
| E16 | **Web oturum yönetimi sağlamlaştırması (OWASP Session Management Cheat Sheet, Eylül 2026 erişimli):** sunucu-taraflı oturum, oturum kimliği ifşası olmadan devre dışı bırakma, çerez flag'leri (HttpOnly+SameSite), oturum süresi ve yenileme | Konsol v2 auth tasarımının (§8) çerçeve kaynağı | [OWASP Session Mgmt CS](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) · [ASVS 4.0.3 §3.3/§2.4](https://owasp.org/www-project-application-security-verification-standard/) |

**Değişim Protokolü:** Her E-kaydı çeyreklik doğrulanır (sonraki tarama: **2026-12-14**). Bir kanıt geçersiz kılınırsa §13.2'deki değişiklik günlüğüne işlenir; etkilenen bölüm yeniden yazılır.

---

## 1. YÖNETİCİ ÖZETİ

**Swarmax**, üretimde koşan otonom ajan filolarının **işletim katmanıdır (Fleet Operations Layer)**: çoklu-çerçeve (framework-agnostic) telemetri alımı (OTel GenAI semantiği), 5 metrik ailesi, akademik temelli anomali/sürükleme tespiti, kanıt-zincirli (Merkle/Ed25519) denetim ve SLA'lı insan-eskalasyon (HITL) yönetimini tek üründe birleştirir.

**Problem (E1–E4'ün birleşimi):** Kurumsal ajan filoları büyüdükçe; (i) maliyet kaçakları, (ii) davranış sürüklenmesi, (iii) denetim/kanıt boşluğu ve (iv) SLA'lı insan gözetimi eksikliği projeleri iptal noktasına getiriyor. Framework'ler (LangGraph, CrewAI, AutoGen, ADK…) filoyu *inşa eder*; Swarmax *işletir*.

**Neden şimdi:** (a) 2026'da kurumsal uygulamaların %40'ı ajan içeriyor (E4); (b) $234 B yazılım harcaması agentic dönüşüme maruz (E2); (c) AB'de yüksek-risk yükümlülük tarihi 02.12.2027'ye çekildi (E5) — kurumsal alıcıların **~15 aylık uyum penceresi** şimdi açıldı ve kanıt-altyapısı şartı netleşti; (d) rakip manzarası (E11) developer-observability'ye sıkışmış durumda; işletim katmanı hâlâ boş.

**Çekirdek iddialar:**
1. **Dürüst standart uyumu:** OTel GenAI Development-statü özniteliklerini pin'li sürümle alır; “stable” iddiası bulunmaz (§2).
2. **Akademik temelli tespit:** EWMA + MAD + JSD + Page-Hinkley/CUSUM + n-gram döngü kırıcı; hata sınıfları MAST ile hizalı (§3).
3. **Kanıt-zincirli denetim:** Append-only hash-chained ledger; crypto-shredding ile GDPR/KVKK silme hakkı; Omnibus 2026/1744 sonrası takvime hazır uyum (§6, §10).
4. **Doğrulanabilir taahhütler:** SLA, RPO ve ölçüm-taahhüt metrikleri ölçülebilir tanımlar + test protokolüyle verilir (§8, §9).

---

## 2. MİMARİ VE STANDART UYUMU (OTel GenAI, Dürüst Matürlik Beyanı)

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                     AJAN FİLOSU (MÜŞTERİ VEYA DOGFOOD ORTAMI)                         │
│   LangGraph · CrewAI · AutoGen · Semantic Kernel · OpenAI Agents SDK · Custom P/TS/Go │
└──────────────────────────────────────────────┬────────────────────────────────────────┘
                                               │ OTLP/gRPC 4317 · OTLP/HTTP 4318
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                        SWARMAX OTEL COLLECTOR PIPELINE                                │
│  Receiver: otlp (grpc/http) → memory_limiter → attributes/enrich                      │
│  → transform (gen_ai.* normalizasyonu + PII maskeleme) → batch → tail_sampling        │
│  Ingestion Validator: mTLS + token + nonce anti-replay (68-RobotProof uyumlu)         │
└──────────────────────────┬─────────────────────────────────┬──────────────────────────┘
                           │                                 │
                           ▼                                 ▼
┌────────────────────────────────────────┐    ┌──────────────────────────────────────────┐
│  ZAMAN SERİSİ & ANALİTİK DEPO          │    │  GÜVENCE DÜZLEMİ (Evidence Plane)        │
│  v1: SQLite+WAL+Litestream → v2:       │    │  Append-only hash-chained ledger         │
│  ClickHouse (MergeTree + TTL tiering)  │    │  (Ed25519 imzalı kayıt + Merkle kökü)    │
│  5 Metrik Ailesi · Dinamik Baseline    │    │  Politika Proxy'si · Kill-Switch dağıtımı│
└──────────────────┬─────────────────────┘    └──────────────────┬───────────────────────┘
                   │                                             │
                   ▼                                             ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│               ANOMALİ VE DAVRANIŞ SÜRÜKLENMESİ MOTORU (APD Engine)                    │
│  EWMA maliyet/gecikme · MAD çıktı uzunluğu · JSD araç dağılımı · Page-Hinkley/CUSUM   │
│  n-gram loop breaker · MAST-hizalı hata sınıflandırıcı · Bilinmeyen sınıf nöbetçisi   │
└──────────────────────────────────────────────┬────────────────────────────────────────┘
                                               │
                          ┌────────────────────┴────────────────────┐
                          ▼                                         ▼
┌──────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│  HAFTALIK FİLO RAPORU MOTORU             │   │  HITL İNSAN ESKALASYON KUYRUĞU          │
│  Filo röntgeni · En pahalı ajanlar ·     │   │  Öncelikli triaj · SLA geri sayımı      │
│  Sürükleme grafikleri · AB AI Act eki    │   │  (30 dk–24 saat) · PagerDuty/Slack      │
└──────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

> **Alarm yolu (v4.1, R1):** APD motoru collector çıktısını **tüketmez**; §4'teki olay akışını (SDK/güvence proxy → motor, doğrudan düşük-gecikmeli yol) tüketir. Collector pipeline'ı (`tail_sampling`, `batch`) yalnızca izler ve haftalık rapor içindir; `decision_wait: 10s` alarm gecikmesine girmez. ≤ 500 ms alarm taahhüdü (§8, MT-6) bu doğrudan yol üzerinde ölçülür.

### 2.1 OTel GenAI Semantik Öznitelik Haritası (Registry-Pinli)

> **Dürüstlük kuralı (E6/E12):** Registry'deki **tüm `gen_ai.*` öznitelikleri Development statüsündedir.** Swarmax bunu gizlemez; **pinned registry** ile çalışır ve kendi iç arayüzünü kendisi kilitler. Bu, “stable bekle” tuzağından daha güvenli bir stratejidir: bugün gerçek filoyu izlerken, yukarı-akış değişikliğinde yalnızca tek eşleme dosyası güncellenir (`semconv-diff` CI, §7.4).

| Kanonik Swarmax Alanı | Pinned OTel `gen_ai.*` (Development) | Tip | Not |
|---|---|---|---|
| `swx.agent.id` | `gen_ai.agent.id` | string | `urn:agent:<tenant>:<env>:<agent>` biçiminde normalize edilir. Registry örnekleri: Bedrock ARN / Vertex ReasoningEngine id. |
| `swx.agent.name` | `gen_ai.agent.name` | string | İnsan-okur ad. |
| `swx.agent.role` | `swx.agent.role` *(uzantı)* | enum | `planner/worker/reviewer/executor` — registry'de yok; `swx.` namespace'inde yaşar. |
| `swx.session.id` | `gen_ai.conversation.id` | string | Registry notuna uyulur: hazır değilse uydurma UUID yazılmaz. |
| `swx.task.id` | `swx.task.id` *(uzantı)* | string | İş birimi kimliği (ticket/order/workflow id). |
| `swx.tokens.in/out` | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | int | Ölçümün kanonik kaynağı. |
| `swx.cache.read.tokens` | `gen_ai.usage.cache_read.input_tokens` | int | Önbellek isabeti maliyet modeline girer. |
| `swx.reasoning.tokens` | `gen_ai.usage.reasoning.output_tokens` | int | “Düşünme” token'ları; ayrı maliyet kalesi. |
| `swx.cost.usd` | `swx.cost.usd` *(uzantı)* | float | Sağlayıcı fiyat listesiyle Decimal hesap; `gen_ai.*` karşılığı yoktur. |
| `swx.model.requested` | `gen_ai.request.model` | string | İstenen model. |
| `swx.model.served` | `gen_ai.response.model` | string | Fiilen hizmet veren model (routing sonrası). |
| `swx.provider` | `gen_ai.provider.name` | string | `openai`, `gcp.vertex_ai`, `gcp.gen_ai` vb. |
| `swx.operation` | `gen_ai.operation.name` | string | `chat`, `generate_content`, `text_completion`, `embeddings`; ek: `swx.agent_step`, `swx.tool_execution`. |
| `swx.tool.name` | `gen_ai.tool.name` | string | Yürütülen araç. |
| `swx.tool.call.id` | `gen_ai.tool.call.id` | string | Çağrı belirteci. |
| `swx.tool.call.arguments` | `gen_ai.tool.call.arguments` | any | PII maskesi sonrası; opsiyonel capture. |
| `swx.tool.call.result` | `gen_ai.tool.call.result` | any | Opsiyonel capture. |
| `swx.tool.status` | `swx.tool.status` *(uzantı)* | enum | `success / error / denied / timeout`. |
| `swx.finish.reasons` | `gen_ai.response.finish_reasons` | string[] | Loop/length ayrımı için. |
| `swx.ttft` | `gen_ai.response.time_to_first_chunk` | double (sn) | İlk-parça gecikmesi. |
| `swx.eval.*` | `gen_ai.evaluation.score.value` / `.label` / `.name` / `.explanation` | mixed | Offline/online değerlendirme skorları. |
| `swx.prompt.name/version` | `gen_ai.prompt.name` / `gen_ai.prompt.version` | string | Prompt sürüm takibi (sürükleme teşhisi için kritik). |
| `swx.agent.version` | `gen_ai.agent.version` | string | Ajan ikili/prompt sürümü; sürüklemede kovaryat. |
| `swx.workflow.name` | `gen_ai.workflow.name` | string | Çoklu-ajan akış adı. |

**Uzantı disiplini:** Registry'de olmayan her alan `swx.` namespace'inde yaşar; yukarı-akış sürüm artışlarında `semconv-diff` CI işi kırıcı değişiklikleri tarar (§7.4).

### 2.2 Sıfır-Kilitlenme (Zero-Lock-In) Taahhüdü
- **BYO-storage:** Ham veri müşterinin kendi depolama hesabında tutulur; Swarmax işlemeye aracılık eder.
- **Açık şema:** `swx.*` uzantı şeması MIT lisansıyla yayımlanır; tam çıkış (JSON/Parquet export) ≤ 1 saat.
- **Çıkış tatbikatı:** Çeyreklik olarak rastgele bir tenant verisiyle çıkış simülasyonu yürütülür, süre ölçülür ve raporlanır.

---

## 3. METRİK KATALOĞU VE ANOMALİ TESPİTİ (5 Aile)

### 3.1 Metrik Aileleri ve Eşik Tablosu (v1 başlangıç değerleri)

| Aile | Metrik | Birim | Algoritma | Başlangıç Eşiği | Şiddet |
|---|---|---|---|---|---|
| **A. Maliyet** | `cost.tokens_in/out` | token | Kayan pencere toplamı | — | Info |
| | `cost.usd` (günlük, ajan başına) | USD | **EWMA** (α=0.15, β=0.10) + Z>2.5 | Günlük harcama > 2.0× EWMA-µ | Critical |
| | `cost.usd_per_task` | USD | **MAD** robust-z | \|robust-z\| > 3.0 | High |
| **B. Gecikme** | `latency.step_ms` | ms | p95 kayan dağılım (7g) | p95 > 2.0× | Medium |
| | `latency.task_total_ms` | ms | MAD robust-z | \|robust-z\| > 3.0 | High |
| | `latency.ttft_s` | sn | EWMA | Z > 2.5 | Medium |
| | `latency.retry_count` | adet | Adım-içi sayaç | ≥3 (aynı task) | High |
| **C. Hata** | `error.rate` (1s) | % | Hata/istek oranı | > %20 | Critical |
| | `error.class` | enum | MAST-hizalı sınıflandırıcı | `loop` ≥ 2 | Emergency |
| | `error.new_class_seen` | string | Bilinmeyen sınıf imzası | Tarihsel kümede ilk kez | Critical |
| **D. Sürükleme** | `drift.tool_distribution` | dağılım | **JSD**(P₇g ∥ Q₂₄s) | > 0.40 | Medium |
| | `drift.output_length` | token | **MAD** | medyan ± %50 dışı | Low |
| | `drift.output_quality` | uç-durum | Metamorfik oracle (uç-durum eşdeğerliği, §3.2-7) | semantik eşdeğer görevde ihlal | Medium |
| | `drift.escalation_ratio` | % | Haftalık insan-devir oranı | > 2.0× | High |
| **E. Eskalasyon (HITL)** | `escalation.open` | bilet | Kuyruk sayacı | kota > 5 | High |
| | `escalation.age_max_h` | saat | En eski açık bilet | > 24 (yetki ihlali: >4) | Emergency |
| | `escalation.reason` | enum | `budget/permission/quality/unknown` | sebebe göre yönlendirme | — |

### 3.2 Matematiksel Formülasyonlar ve Kaynakları

**1) Dinamik maliyet outlier'ı — EWMA kontrol kartı**
$$\mu_t = \alpha C_t + (1-\alpha)\mu_{t-1},\ \alpha=0.15;\qquad \sigma_t^2 = \beta(C_t-\mu_t)^2 + (1-\beta)\sigma_{t-1}^2,\ \beta=0.10$$
$$Z_t = \frac{C_t - \mu_t}{\sigma_t};\qquad Z_t > 2.5 \Rightarrow \textbf{CostSpikeAlarm}$$
Kaynak: Roberts (1959) EWMA kartı; Hunter (1986), *J. Quality Technology* 18(4). Neden: normality varsayımı olmadan küçük-orta kaymaları hızlı yakalar.

**Soğuk-başlangıç disiplini (v4.1, R3):** Z-alarmı yalnızca **≥ 30 gözlem** ve §3.3 kalibrasyon penceresinin kapanmasından sonra silahlanır; EWMA varyans tahmincisi ilk günlerde kararsızdır.

**2) Araç dağılımı sürüklenmesi — Jensen-Shannon Divergence**
$P$: 7 günlük normalize araç-çağrı vektörü, $Q$: 24 saatlik vektör, $M=\tfrac12(P+Q)$:
$$JSD(P\parallel Q)=\tfrac12\sum_i P_i\log_2\frac{P_i}{M_i}+\tfrac12\sum_i Q_i\log_2\frac{Q_i}{M_i}$$
$JSD<0.20$ sağlıklı · $0.20$–$0.40$ izleme (haftalık rapor notu) · $>0.40$ **Behavioral Drift Alarm** → inceleme eskalasyonu.
Kaynak: Endres & Schindelin (2003), *IEEE Trans. Information Theory* 49(7) — JSD simetrik, her zaman sonlu; karekökü gerçek bir metriktir.

**Uygulama disiplini (v4.1, R4):** sıra-hücreler log oranını tanımsız yapar; tüm olasılıklara ε = 10⁻⁶ eklenir ve P veya Q penceresi boşsa karşılaştırma `warming_up` işaretiyle **atlanır** — sonsuz diverjans üretilmez.

**3) Kaçak döngü kırıcı — n-gram hash**
$$h_i = \text{SHA256}(\text{tool\_name}\,\|\,\text{normalize\_json}(\text{arguments}))$$
Ardışık 3 aynı hash ($h_i=h_{i-1}=h_{i-2}$) ⇒ görev quarantine (`KILL_CIRCUIT_OPEN`) + güvence düzlemine olay + insan eskalasyonu.
Gerekçe: tekrar-patolojisinin n-gram düzeyinde yakalanabilirliği — Holtzman ve ark., *The Curious Case of Neural Text Degeneration*, ICLR 2020.

**4) Sağlam ölçek — MAD (Median Absolute Deviation)**
$$\text{robust-z} = \frac{0.6745\,(x_i-\text{median})}{\text{median}_i|x_i-\text{median}|};\quad |\text{robust-z}|>3.0 \Rightarrow \text{alarm}$$
Gerekçe: ağır-kuyruklu ajan maliyet dağılımlarında ortalama/standart sapmadan sağlam — Hampel (1974); Leys ve ark. (2013), *J. Exp. Social Psychology*.

**5) Kalıcı kayma — Page-Hinkley / CUSUM (JSD'nin tamamlayıcısı)**
$$g_t=\max(0,\,g_{t-1}+(x_t-\mu_0-\delta));\quad g_t>h\Rightarrow\textbf{ShiftAlarm}$$
JSD *dağılım farkını*, Page-Hinkley *monotonik kaymayı* yakalar. Hata-sınıfı dağılım kaymaları için ayrıca **PSI** raporlanır (PSI > 0.25 = büyük kayma; bankacılık pratiği).
Kaynak: Page (1954), *Biometrika* 41(1–2).

**6) Hata taksonomisi — MAST hizalaması (E7)**

| Swarmax `error.class` | Tanım | MAST bağı |
|---|---|---|
| `spec_ambiguity` | Belirsiz/eksik alt-görev tanımı | Specification Issues |
| `interagent_mismatch` | Ajan-ajan iletişim/protokol uyuşmazlığı | Inter-Agent Misalignment |
| `verification_fail` | Çıktının doğrulanamaması | Task Verification |
| `tool_fail / parse / timeout / auth` | Mekanik-operasyonel sınıflar | (MAST dışı) |
| `loop` | n-gram döngü patolojisi | Inter-Agent Misalignment (dolaşım) |
| `unknown` | Bilinmeyen sınıf (ilk-görüm) | — (Sentinel) |

**7) Çıktı-kalite sürüklenmesi — Metamorfik Oracle (E8)**
ReliabilityBench'in *action metamorphic relations* ilkesi: doğruluk, metin benzerliğiyle değil **uç-durum eşdeğerliğiyle** tanımlanır. Swarmax bunu üretim-içi sürükleme sinyaline çevirir: aynı görev-şablonunun koşularında uç-durum değişkenleri (oluşturulan kayıt sayısı, gönderilen bildirim, yazılan dosya hash'i vb.) karşılaştırılır; semantik olarak eşdeğer görevlerde uç-durum sapması `drift.output_quality` alarmı üretir. Böylece LLM-judge yanlılığına hiç girmeden **çıktı-kalite sürüklenmesi** yakalanır.

**Maliyet bütçesi (v4.1, R5):** oracle, kritik görev sınıfında ajan-günü trafiğinin **≤ %1'i** ile sınırlı shadow rerun olarak çalışır; bütçe aşımları `baseline_audit` defterine yazılır.

### 3.3 Kalibrasyon Disiplini
Tablo değerleri **başlangıç** eşikleridir. Her ajan için ilk **14 gün kalibrasyon penceresi** çalışır: pencere bitmeden yalnızca Info ve Emergency (`loop`, `new_class`) alarmları ateşlenir; High/Critical eşikleri tenant-bazlı kalibre edilir ve değişiklikler `baseline_audit` defterine yazılır.

**Yanlış-pozitif bütçesi — ölçülebilir tanım (v4.1, R10):** ajan-günü başına, saatlik değerlendirme döngüleri içindeki yanlış-pozitif alarm oranı **≤ %5** (24 döngü/gün varsayımıyla ajan başına ≤ 1 FP/gün). Sentetik enjeksiyon ajanları kalibrasyon penceresinden muaf tutulur (`synthetic=1`; pencere kurulumda önceden kapatılır) — gerçek dogfoğu sentez veriyle kirletmez (§7.3).

---

## 4. OLAY SÖZLEŞMESİ (Event Contract) — Operasyon ↔ Güvence Düzlemi

Fleetmind (69) ↔ Ajan Güvence Hattı (81) ayrımı korunur; Swarmax bunları **tek ürün, iki düzlem** olarak konumlandırır:
- **Operasyon Düzlemi:** telemetri alımı, metrik üretimi, anomali motoru, raporlar, HITL kuyruğu.
- **Güvence Düzlemi:** append-only hash-chained kanıt defteri (Ed25519 + Merkle kökü), politika proxy'si, kill-switch dağıtımı.

### 4.1 Olay Tipleri ve Davranış Matrisi

| Olay (`event_type`) | Üretici | Tüketici | Operasyon Düzlemi Davranışı |
|---|---|---|---|
| `tool_call` | Güvence Proxy / SDK | Operasyon + Güvence | Hacim/gecikme/hata sayaçları; JSD vektörü güncellenir |
| `permission_decision` | Güvence Motoru | Operasyon + Güvence | `deny` oranı; ani zıplamada güvenlik alarmı |
| `mask_event` | PII Maskeci | Operasyon + Güvence | Yalnızca sayaç; içerik asla okunmaz |
| `escalation` | APD Motoru | İnsan + Güvence | Triaj kuyruğuna yazar; SLA sayacı başlar |
| `kill_switch_triggered` | APD veya İnsan | Filo + Güvence | API oturumları sonlandırılır; olay ledger'a mühürlenir |

### 4.2 Uyarı → Eskalasyon SLA Eşleme

| Sinyal | Üretilen Olay | Sebep | SLA | Otomatik Koruma Aksiyonu |
|---|---|---|---|---|
| `error.class == 'loop'` (≥2) | `escalation` | `quality` | **30 dk** | Görev quarantine; döngü kırıcı açık |
| `permission.deny > %20 / 1s` | `escalation` | `permission` | **4 saat** | Harici araç yetkileri geçici dondurulur |
| `cost.daily > 2.0× EWMA-µ` | `escalation` | `budget` | **24 saat** | Model downgrade *teklifi* (operatör onaylı) |
| `error.new_class_seen` | `escalation` | `unknown` | **24 saat** | “Yeni hata deseni” etiketiyle triaja düşer (E8: tekrarlı-stres koşulları ayrı izlenir) |
| `error.rate > %20` (24s pencere) | `escalation` | `quality` | **4 saat** | Sorumlu ajanın görevleri triaja alınır (v4.1, R15) |
| `latency.retry_count ≥ 3` (aynı task) | `escalation` | `quality` | **4 saat** | Görev yeniden-kuyruğa alınır; kaynak sağlayıcı denetlenir (v4.1, R15) |
| `drift.tool_distribution > 0.40` | `report_item` | `drift` | **Haftalık** | Haftalık raporda davranış sapması olarak listelenir |
| `escalation.age_max_h > 24` | `escalation` | `system_health` | **2 saat** | Self-eskalasyon; PagerDuty/SMS |

### 4.3 Kimlik Eşliği ve Anti-Replay
- Her iki düzlemde de `68-RobotProof` uyumlu kimlik standardı; `agent.id` asla çatallanmaz.
- Her OTLP alımında nonce + HMAC anti-replay; tekrar paketler `ingest_reject` metriğine yazılır.

---

## 5. REKABET ANALİZİ, BİRİM EKONOMİSİ VE FİYATLANDIRMA (E11 ile sabitlenmiş)

### 5.1 Rekabet Konumlandırması (2026 H2 gerçekleriyle)

| Kategori / Oyuncu | Temsilciler | Odakları | Swarmax'ın Hendekleri (Moat) |
|---|---|---|---|
| Developer Observability | LangSmith, Langfuse, AgentOps, Logfire | Trace, prompt debugging, geliştirici paneli | **İşletme katmanı:** SLA takibi, maliyet sapması, davranış sürüklenmesi, haftalık kurumsal rapor, HITL kuyruğu. Langfuse'un ClickHouse'a katılması (E11) “gözlemlenebilirlik altyapısı standartlaşıyor; üstüne işletim zekası ekleyen hâlâ yok” tezini güçlendirir. |
| MLOps / Serving Proxy | Portkey, LiteLLM | Model routing, load balancing, cache | **Ajan-düzeyi operasyon:** görev SLA'sı, araç sapması, insan eskalasyon kuyruğu. |
| Kurumsal Güvenlik Çerçeveleri | OWASP ASI rehberleri, MITRE ATLAS (E9/E10) | Denetim kontrol setleri | Swarmax bu setleri **çalışan kontrol** olarak ürünleştirir (kontrol → telemetri → kanıt → eskalasyon zinciri). |
| Şirket-içi derlemeler | Dağınık Grafana/ELK panelleri | Ham altyapı metrikleri | **Hazır ajan semantiği:** 5 metrik ailesi, sıfır-kod kural seti, pinli semconv exporter'ları. |

### 5.2 Birim Ekonomisi

| Kalem | Değer | Not |
|---|---|---|
| Altyapı maliyeti (temel düğüm) | ~$50/ay | Go/Rust collector + SQLite/Litestream (v1) veya tek-ClickHouse düğüm (v2) |
| Onboarding (müşteri başına) | ~3 saat | Filo konfigürasyonu + OTel endpoint + eşik kalibrasyonu |
| Aylık bakım (müşteri başına) | ≤1 saat | Otomatik tuning + haftalık rapor onayı |
| Brüt kâr marjı | **%88–95 hedefi** | §5.4 senaryo tablosuyla uyumlu |
| Başabaş | **1 müşteri** | Düşük sabit maliyet |

### 5.3 Parasallaşma: Hibrit Güven-Hendeği Modeli (v4.3.2 kararı)

**Karar (2026-09-17):** Çekirdek **Apache-2.0 olarak yayında kalır** — mevcut modüllerin
hiçbiri (SSO, kanıt, soğuk arşiv, uyum tatbikatı dâhil) ücretli katmana **taşınmaz**;
lisans-değiştirme tuzağına (Grafana/MinIO dersi) girilmez. Hendek, kodun değil
**güvenin ve operasyonun** içinden gelir. Üç gelir hattı:

**Hat 1 — Yönetilen Bulut (self-serve + kurumsal):**

| Paket | Kapsam | Fiyat | Hedef |
|---|---|---|---|
| Açık Çekirdek | Self-host: collector + şema + tüm çekirdek modüller | **$0 (Apache-2.0)** | Topluluk, geliştirici |
| Ekip (Bulut) | 10 AVBP, barındırma + yedek + sürüm yönetimi | **$199/ay** | Erken aşama ekipler |
| Filo+Kanıt (Bulut) | 50 AVBP + kanıt teslimi + haftalık SLA/drift raporu | **$599/ay** | Üretimde çoklu-ajan KOBİ |
| Kurumsal (Bulut) | Sınırsız AVBP + özel SLA + çoklu takım + BYO-storage | **$2.400/ay+** | Finans/sağlık/kritik iş hattı |

> Self-host zaten ücretsiz ve eksiksizdir; bulut paketinin sattığı şey **operasyon
> yükünün azaltılmasıdır** (ClickHouse/soğuk arşiv/yedek işletimi bizde). Bu,
> GitLab/Postmark modelinin aynısıdır ve açık-çekirdekle çelişmez.

**Hat 2 (ilk-90-gün odağı) — Evidence Trust Services:**

Self-hosted self-signed kanıt, AI Act denetiminde hukuki ağırlığı **sınırlı** bir
bilgidir; kanıtın değeri, imzalayan tarafın güvenine bağlanır. Swarmax kanıt zincirinin
haftalık mühür köklerine **üçüncü-taraf sayaç-imzası** satılır — bu hendek ağa bağlıdır
ve kod kopyalanarak üretilemez:

- **T3.1 Sayaç-imza:** haftalık mühür kökü, HSM korumalı anahtarla **RFC 3161 TSA**
  damgasına gönderilir; damga depoya `tsa_token` olarak yazılır; `verify_seals` zincir
  + damga çift-doğrulaması yapar.
- **T3.2 Denetçi portalı:** müşterinin denetçisine read-only kanıt gezgini + doğrulama
  raporu (PDF: zincir-kökü + TSA damgası + doğrulama adımları).
- **T3.3 Doğrulama API'si:** üçüncü tarafların herhangi bir kanıt çıpasını bağımsız
  doğrulaması için genel endpoint.

Fiyat: **$350/ay** (Filo+Kanıt eki) veya **kanıt-kökü/ay** ölçülü; pilot fiyatlaması
ilk 3 müşteri görüşmesiyle doğrulanır (§5.4 varsayımlarına değeri doğrulanmadan girmez).

> **T3.1 kodda (v4.3.2):** `swarmax.tsa` — saf-stdlib RFC 3161 istemcisi (DER
> TSRequest elle yazılır; `openssl ts -query` ile bayt-birebir uyumlu — FreeTSA'nın
> DEFAULT-versiyon/NULL-param reddi bu karşılaştırmayla yakalandı ve giderildi);
> `evidence_seals.tsa_token` (migration 010); `seal_ledger(tsa_url=…)` mührü
> damgalayıp `verify_seals` zincir+Ed25519+**damga-bağlama** üçlü doğrulaması yapar;
> TSA kesintisi fail-closed (sessiz atlama yok). Canlı kanıt: FreeTSA'ya karşı
> `make trust-drill` — mühür PASS + `openssl ts -verify` PKI PASS.

**Hat 3 — Enterprise modülü yalnız talep-doğrulanınca:** SAML/SCIM, SIEM akışı,
HA-küme, çoklu-kiracı yönetim UI'ı gibi talepler **ödenmiş pilotla doğrulanmadan**
yazılmaz; doğrulanırsa ayrı kapalı paket olarak sunulur. Spekülatif kod: **sıfır**.

> **Rakip kıyas (E11):** Developer-observability araçları koltuk/birim/GB başına
> faturalıyor (LangSmith ~$39/koltuk/ay; birim-bazlı modellerde ajan başına 8–15
> faturalama birimi). Swarmax **ajan-bazlı sabit paket + kanıt-güven servisi** ile
> konumlanır: bütçe öngörülebilirliği (E2 karşıtı) + hukuken savunulabilir kanıt.

> **Yayın notu (v4.3.2):** PyPI yükleme öncesi hijyen uygulandı — `keys/` ve `data/`
> repodan dışlandı (.gitignore), iç-dokümanlar (FLEETMIND.md, ESKI_KIMLIK.md) yayın
> setinden çıkarıldı, kişisel yol/e-posta taraması temiz, `twine check` PASSED.

### 5.4 12 Aylık P&L — Hedef Senaryo (varsayım: karışım ağırlıklı $490 ABP)

| Ay | Aktif Müşteri | MRR | Altyapı & İşletme | Brüt Kâr | Marj | Kilometre Taşı |
|---|---|---|---|---|---|---|
| 1 | 1 (iç dogfood) | $0 | $65 | −$65 | — | Dogfood koşusu |
| 2 | 2 | $980 | $90 | $890 | %90,8 | İlk ücretli pilotlar |
| 3 | 4 | $1.960 | $120 | $1.840 | %93,9 | Açık şema GTM etkisi |
| 6 | 12 | $5.880 | $350 | $5.530 | %94,0 | ClickHouse geçişi (v2) |
| 9 | 25 | $12.250 | $650 | $11.600 | %94,7 | Kanıt-paketi satışları |
| 12 | 50 | $24.500 | $1.200 | **$23.300** | **%95,1** | **ARR ≈ $294.000** |

> Senaryo varsayımıdır; fiyat karışımı değiştikçe yeniden hesaplanır; **churn=0 varsayımıyla** kurulmuş yürütme hedefidir, tahmin değildir (v4.1, R9). Doğrulanmış pazar büyüklükleri (E2, E3) talep tarafını sabitler.

---

## 6. GÜVENLİK, TEHDİT MODELİ VE MEVZUAT (E9/E10/E5)

### 6.1 Tehdit Modeli — STRIDE × MITRE ATLAS × OWASP
- **Spoofing:** Collector'da mTLS + token + nonce anti-replay (§4.3). ATLAS: kimlik taklidi tekniklerine karşı ajan-kimliği eşliği.
- **Tampering:** Her olay Ed25519 imzalı; ledger hash-chained (SHA-256 Merkle kökü). Güvence düzlemi append-only.
- **Repudiation:** İmzalı kanıt zinciri + operatör aksiyon kayıtları → inkâr edilemezlik.
- **Information Disclosure:** Collector transform katmanında Regex/NER PII maskeleme (`mask_event`); içerik yakalama bayrakları default-kapalı (OTel registry uyarılarıyla uyumlu).
- **DoS:** `memory_limiter` + ingestion rate-limit + kontrollü drop; drop sayaçları müşteriye görünür.
- **Elevation of Privilege:** Politika proxy'si anında `deny` → 69 eskalasyonu; kill-switch çok-katmanlı infaz (§6.3).
- **Anahtar mühendisliği (v4.1, R6):** Ed25519 özel anahtarı secret store'da yaşar; **çeyreklik rotasyon** uygulanır; her rotasyon olayı ledger'a mühürlenir. Doğrulama, anahtar geçmişindeki tüm imza sürümleriyle yapılır.
- Kontrol kümesi OWASP Agentic T&M + OWASP LLM Top 10 2026 ile eşleştirilmiş **kontrol→telemetri→kanıt** matrisi olarak teslim edilir (E10).

### 6.2 Mevzuat — AB AI Act (Omnibus sonrası) ve Türkiye

| Yükümlülük | AI Act Referans | Omnibus (2026/1744) Sonrası Takvim | Swarmax Karşılığı |
|---|---|---|---|
| Otomatik olay kaydı / log tutma | Md. 12 | Annex III için 02.12.2027; gömülü AI için 02.08.2028 | İmzalı append-only ledger + 2 yıl soğuk katman (§10) |
| İnsan gözetimi | Md. 14 | Aynı takvim | HITL kuyruğu, SLA'lı triaj, kill-switch |
| Yüksek-risk sistem sağlayıcı yükümlülükleri | Md. 16 vd. | 02.08.2026 → 02.12.2027 (Annex III) | Uyum paketi: kanıt export, rol ayrımı, denetim raporu |
| Eski (sahaya çıkmış) sistemler | Geçiş hükümleri | +4 ay ek süre | Yükseltme rehberi müşteri portalında |

> Konumlandırma notu: Swarmax bir “AI Act sertifikasyonu” değil, **md. 12/14 teknik altyapı sağlayıcısıdır**. Yasal tavsiye vermez; müşterinin yükümlülük haritasını teknik kanıtla besler. Türkiye tarafında (E13): GVK mükerrer 89/1-b kapsamındaki yazılım hizmet kazancı istisnası, TR merkezli kuruluş modelinde değerlendirilir; nihai yorum için müşavir onayı şarttır.

### 6.3 Kill-Switch Protokolü (Fail-Safe Cascade)

```
┌────────────────────────────────────────────────────────────┐
│   TETİKLEYİCİ: Otomatik APD Motoru VEYA İnsan Operatör      │
└─────────────────────────────┬──────────────────────────────┘
                              ▼
KATMAN 1 (0–50 ms): Güvence Proxy blokajı — token'lar geçersiz,
                    giden LLM/tool isteklerine HTTP 403.
                              ▼
KATMAN 2 (50–500 ms): Container/Pod/Process SIGTERM→SIGKILL;
                    bekleyen görevler 'quarantined'.
                              ▼
KATMAN 3 (post-mortem): Tüm span'ler + token logu + operatör
                    kararı SHA-256 köküyle ledger'a mühürlenir.
```

> **(v4.1)** Katman-1 infaz ölçümü: token-iptal yayılım gecikmesi push-model iptal listesiyle ölçülür; hedef ≤ 50 ms (p95) ve MT-6 ile aynı ölçüm penceresinde raporlanır.

### 6.4 RBAC
- **Fleet Admin:** kural motoru, bütçe tavanı, API token üretimi.
- **HITL Operator:** bilet inceleme/onay, geçici bütçe izni, kill-switch.
- **Compliance Auditor:** salt-okunur; ledger ve rapor export.

---

## 7. 12 HAFTALIK YÜRÜTME PLANI (Dogfood-Öncelikli, Kabul Ölçütlü)

### 7.1 Fazlar

| Faz | Hafta | Çıktı | Somut Kabul Ölçütü (DoD) |
|---|---|---|---|
| **F0 — Kanıt Tabanı** | 1–2 | Repo iskeleti, SQLite+WAL şema (§12.1), OTLP alımı, pinli semconv haritası (§2.1) | Sentez ajan filosundan 100K olay; p99 ingest gecikmesi < 2 sn; şema-değişiklik testi geçer |
| **F1 — Metrik Motoru** | 3–5 | 5 metrik ailesi + EWMA/MAD/JSD/Page-Hinkley + metamorfik oracle uygulaması | Enjeksiyon testleri (§9): 8/8 alarm doğrulukla üretir; yanlış-pozitif < %5/gün dogfood'da |
| **F2 — Kanıt Düzlemi** | 6–7 | Ed25519 imzalı append-only ledger + Merkle doğrulama API'si | Ledger **değişmezlik** testi: tek-bit değişiklik doğrulamada yakalanır; export ≤ 1 saat |
| **F3 — HITL Kuyruğu** | 8–9 | Triaj arayüzü (TUI/Web), SLA sayaçları, PagerDuty/Slack | Uçtan uca tatbikat: alarm→bilet→operatör kararı→ledger mührü < 5 dk |
| **F4 — Rapor + Uyum Paketi** | 10–11 | Haftalık filo röntgeni + AB AI Act eki (§6.2 takvimiyle) | Örnek 7 günlük dogfood verisiyle rapor; tüm sayılar kanıt-zincirine referanslı |
| **F5 — Sertleştirme** | 12 | docker-compose tek-tuş, yük testi, dokümantasyon | 10K olay/dk 1 saat boyunca; RPO=0 tatbikatı (§8); v1 etiketi (tag) |

### 7.2 Ekip ve Ritim
Tek geliştirici + (F3'ten itibaren) yarım-zaman operatör. Haftalık demodogfood raporu; her fazın sonunda §9 protokolü koşulur.

### 7.3 Dogfood Ortamı
Gerçek iç ajan filosu (mevcut üretim görevleri) ilk müşteridir. Sentez ajanlar yalnızca alarm-enjeksiyon testlerinde kullanılır; gerçek veriyle karıştırılmaz (`synthetic=true` etiketi).

### 7.4 Kalite Kapıları (CI)
1. `semconv-diff`: pinli registry sürümüne karşı kırıcı değişiklik taraması.
2. Kural motoru birim testleri: her kural için pozitif/negatif altın örnekler.
3. Ledger özellik testleri: append-only değişmezlik + Merkle kök tutarlılığı.
4. Yük: p99 ingest < 2 sn, alarm gecikmesi ≤ 500 ms (bkz. §8).

---

## 8. SLA TAHHÜTLERİ VE RPO (Ölçülebilir Tanımlarla)

| Hizmet | Taahhüt | Ölçüm Tanımı | İhlalde |
|---|---|---|---|
| Collector telemetri erişilebilirliği | **%99,5 uptime** (dogfood/üretim v1) | Ay içi başarılı health-check oranı; bakım pencereleri hariç | Aylık faturada %10 iade |
| Alarm karar gecikmesi | **≤ 500 ms** | İstemspan kapanışı → APD karar yazımı (p95, günlük pencere) | %10 iade |
| HITL bildirim dağıtımı | **≤ 3 sn** | Bilet yaratımı → webhook 2xx alındısı | %10 iade |
| RPO | **0** — v1 dogfood, tek-düğüm çökme dayanıklılığı (v4.1, R2) | WAL fsync ile yerel commit dayanıklılığı; çökme sonrası kayıp olay sayısı = 0 doğrulaması. DR replikası (Litestream async): **RPO ≤ 5 sn**, ayrı raporlanır | İlgili ay faturasının %100 iadesi |

> v3.5'te %99,95 vaadi, tek-düğüm v1 mimariyle çelişiyordu; v4.0'da v1 için %99,5, v2 (çoklu-bölge) için %99,9 hedefi ayrı taahhüt olarak planlanır. Vaat ölçülebilir tanımla verilir; süs taahhüt verilmez.
> **v4.1 (R2):** “RPO=0” dürüstçe yeniden tanımlandı — async replikasyon RPO=0 üretemez; v1 taahhüdü tek-düğüm çökme dayanıklılığıdır, replikasyon kaybı ≤ 5 sn ayrı ve görünür raporlanır. v2 çoklu-bölge hedefi gerçek RPO=0'dır.

---

## 9. ÖLÇÜM-TAAHHÜT METRİKLERİ VE TEST PROTOKOLÜ (E8 temelli)

ReliabilityBench (E8) üretim-benzeri stres altında ajan güvenilirliğini üç eksende ölçer: tekrarlı koşuda tutarlılık (**pass^k**), semantik eşdeğer görev pertürbasyonlarına dayanıklılık (**ε**) ve kontrollü araç/API hatalarına tolerans (**λ**) — ve bunları tek bir **güvenilirlik yüzeyi R(k, ε, λ)**'da birleştirir. Swarmax bu çerçeveyi **üretim-içi ölçüm-taahhüdüne** çevirir (n=10, k ayarlanabilir):

| Metrik | Tanım (ReliabilityBench karşılığı) | Başlangıç Hedef |
|---|---|---|
| **MT-1 Görev Başarı Tutarlılığı** | Görev-sınıfı **replay seti** üzerinde pass^k (k=5, n=10 replays; platform uptime ölçümü değildir — v4.1, R8) | ≥ 0.90 (kritik görev sınıfı) |
| **MT-2 Maliyet Tutarlılığı** | n tekrarda maliyet varyasyon katsayısı (CV) | ≤ 0.25 |
| **MT-3 Adım Sayısı Tutarlılığı** | n tekrarda adım sayısı CV'si | ≤ 0.20 |
| **MT-4 Hata Toleransı (λ-eğrisi)** | Kontrollü araç/API hata enjeksiyonu altında başarı eğrisi; ReliabilityBench bulgusuyla **rate-limit en zararlı hata sınıfıdır** — enjeksiyon paketinde zorunlu | λ=0.1'de başarı düşüşü ≤ 5 puan |
| **MT-5 Kurtarma Süresi** | Enjeksiyonlu hatadan normal operasyona dönüş (aynı ajan) | ≤ 60 sn |
| **MT-6 Alarm Gecikmesi** | Anomali olayı → APD kararı | ≤ 500 ms |
| **MT-7 Kanıt Bütünlüğü** | İmza doğrulama başarısı (haftalık tam tarama) | %100 |
| **MT-8 Metamorfik Uç-Durum Eşdeğerliği** | Semantik eşdeğer görev koşularında uç-durum değişkenlerinin uyumu (§3.2-7) | ihlal oranı ≤ %2 |

Her üretim ajanı için haftalık **R(k, ε, λ) güvenilirlik yüzeyi** raporu üretilir ve filo röntgeninin başlık metriği olur: "bu ajanın üretim-hazırlığı (production-readiness) ne düzeyde?"

**Enjeksiyon testleri (F1 kabulü, 8 senaryo):** sentez ajanlar (a) 3.5× token zıplaması, (b) araç dağılımı sapması (JSD ≈ 0.55), (c) 3-tekrar döngü, (d) yeni hata sınıfı, (e) deny-oranı zıplaması, (f) bilet yaşlanması, (g) **rate-limit dalga enjeksiyonu** (λ-eğrisi), (h) **schema-drift + kısmi yanıt** hata sınıfları üretir; motorda **8/8** tespit + doğru şiddet + doğru SLA beklenir. Yanlış-pozitif bütçesi: §3.3'teki ölçülebilir tanım (v4.1, R10).

### 9.2 Yol Haritası — Otomatik Hata Atribusiyonu (v1.1, E14)
Eskalasyon açıldığında operatörün ilk sorusu "hangi ajan, hangi adımda suçlu?"dur. Who&When (E14) bu görevi otomatikleştiren ilk akademik çerçevedir; alanın güncel SOTA'sı (E15, TraceElephant — 311K üretim izi, Nisan 2026) ortalama **%65,9** doğru-adım doğruluğundadır ve bağımsız benchmark kritiği (arXiv:2603.25001) tek-perspektifli değerlendirmenin yanlış ajanı işaretleyebildiğini göstermiştir. Bu iki bulgu kâğıdın tasarım kararını doğrular: öneri **insan-onaylı** kalır, özerk kapatma yapılmaz. v1.1 planı: eskalasyon bileti üretiminde **sorumlu ajan + kritik adım önerisi** alanı eklenir; yöntem ailesi güncel literatürle izlenir (Who&When → AgenTracer, DCFA ve hiyerarşik iz-atribusiyonu hatları). Kabul ölçütü: dogfood'da açılan biletlerde önerinin operatör-onay oranı ≥ %70 — SOTA tabanının üstünde kalıcı katma değer kanıtı.

---

## 10. VERİ SAKLAMA, KATMANLAMA VE UNUTULMA HAKKI

1. **Sıcak (0–30 gün):** Tüm span detayları; v1 SQLite (SSD), v2 ClickHouse MergeTree (SSD). Sorgu < 200 ms.
2. **Ilık (31–90 gün):** Span detayları Parquet'e sıkıştırılır; S3/R2. Depolama maliyeti ~%85 düşer.
3. **Soğuk (91 gün–2 yıl):** Yalnızca imzalı özetler + Merkle kökleri; şifreli arşiv (AB md. 12 kayıt tutma ile uyum; §6.2 takvimi).
4. **Unutulma hakkı (GDPR Art. 17 / KVKK md. 7):** `DELETE /v1/privacy/forget?user_id=X` → kullanıcıya ait span gövdeleri **crypto-shredding** ile yok edilir (kişi-anahtarlı şifreleme; anahtar imha edilir); operasyonel toplamlar ve imzalı kanıt özetleri mevzuatın kayıt tutma gereğiyle korunur. Silme işlemi kendisi ledger'a imzalı olay olarak yazılır.

> **Artık-risk beyanı (v4.1, R7):** silme işlemi **gövde deposunu** (span içerikleri, kişi-anahtarlı şifreleme) kripto-parçalayarak yok eder ve silme olayını ledger'a mühürler; hash-zincirindeki kayıt özetleri (payload hash + imza) kanıt bütünlüğü için kalır. “Hash zinciri kişisel veri midir?” sorusu müşteri DPA incelemesine tabidir — Swarmax hukuki garanti vermez, teknik kanıt sunar.

---

## 11. OTel COLLECTOR YAPILANDIRMASI (`otel-collector-config.yaml`, v2/ClickHouse varyantı)

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  attributes/swx_enrich:
    actions:
      - key: swx.ingest.version
        value: "1"
        action: upsert

  transform/pii_mask:
    error_mode: ignore
    log_statements:
      - context: log
        statements:
          - replace_pattern(body, "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]")
          - replace_pattern(body, "\\b(?:\\d[ -]*?){13,16}\\b", "[REDACTED_CARD]")

  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 1000
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 5000 }
      - name: baseline
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

  batch:
    send_batch_size: 256
    timeout: 5s

exporters:
  clickhouse/swx:
    endpoint: clickhouse:9000
    database: swarmax
    username: default
    password: ${env:CLICKHOUSE_PASSWORD}
  debug/dogfood:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, tail_sampling, batch]
      exporters: [clickhouse/swx]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, batch]
      exporters: [clickhouse/swx]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, transform/pii_mask, batch]
      exporters: [clickhouse/swx, debug/dogfood]
```

> Not: v1 (SQLite) varyantında `clickhouse/swx` yerine `file` exporter + Swarmax Engine SQLite yazıcısı kullanılır; maskeleme ve zenginleştirme zinciri birebir aynıdır. Kanıt-duzlemi akışı collector'dan bağımsız SDK/proxy olaylarıyla beslenir (§4).

---

## 12. VERİTABANI ŞEMASI

### 12.1 SQLite v1 (DDL)

> **v4.1 (R12–R14):** üretim şeması = bu temel DDL + `schema/migrations/002_f0_extensions.sql` (metamorfik uç-durum alanları `task_template`/`end_state_json`, `retry_count`, `ttft_s`, `guard_events` tablosu, `hitl_escalations.created_at`). Append-only tetikleyicileri bu DDL'de tanımlıdır; F0 kodu §14 denetimiyle uyumlu uygular.

```sql
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS fleet_agents (
    agent_id    VARCHAR(128) PRIMARY KEY,
    fleet_name  VARCHAR(64)  NOT NULL,
    role        VARCHAR(32)  NOT NULL,           -- planner|worker|reviewer|executor
    framework   VARCHAR(32)  DEFAULT 'custom',
    agent_version VARCHAR(64),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(16)  DEFAULT 'active'    -- active|paused|quarantined
);

CREATE TABLE IF NOT EXISTS agent_task_events (
    event_id     VARCHAR(64) PRIMARY KEY,
    agent_id     VARCHAR(128) NOT NULL REFERENCES fleet_agents(agent_id),
    task_id      VARCHAR(64)  NOT NULL,
    session_id   VARCHAR(64),
    model_name   VARCHAR(64)  NOT NULL,
    input_tokens INTEGER      NOT NULL,
    output_tokens INTEGER     NOT NULL,
    cost_usd     NUMERIC(12,6) NOT NULL,
    latency_ms   INTEGER      NOT NULL,
    error_class  VARCHAR(32),
    status       VARCHAR(16)  NOT NULL,
    synthetic    BOOLEAN      DEFAULT 0,          -- sentez test verisi işareti (§7.3)
    ts           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_agent_time ON agent_task_events (agent_id, ts);

CREATE TABLE IF NOT EXISTS agent_drift_baselines (
    agent_id           VARCHAR(128) PRIMARY KEY,
    tool_distribution_json TEXT    NOT NULL,
    mean_cost_usd      NUMERIC(12,6) NOT NULL,
    mad_cost_usd       NUMERIC(12,6) NOT NULL,   -- EWMA σ yerine MAD (§3.2-4)
    p95_latency_ms     INTEGER   NOT NULL,
    ewma_mu            NUMERIC(12,6),
    ewma_sigma2        NUMERIC(12,6),
    calibration_until  TIMESTAMP,                 -- §3.3 kalibrasyon penceresi
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hitl_escalations (
    escalation_id  VARCHAR(64) PRIMARY KEY,
    agent_id       VARCHAR(128) NOT NULL REFERENCES fleet_agents(agent_id),
    task_id        VARCHAR(64)  NOT NULL,
    trigger_metric VARCHAR(64)  NOT NULL,
    trigger_value  DOUBLE PRECISION NOT NULL,
    reason         VARCHAR(32)  NOT NULL,          -- budget|permission|quality|unknown|drift|system_health
    evidence_ref   VARCHAR(128) NOT NULL,
    sla_deadline   TIMESTAMP    NOT NULL,
    status         VARCHAR(16)  DEFAULT 'open',
    resolved_by    VARCHAR(64),
    resolved_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hitl_sla ON hitl_escalations (status, sla_deadline);

CREATE TABLE IF NOT EXISTS evidence_ledger (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,  -- append-only; UPDATE/DELETE tetikleyicilerle yasaklanır
    event_type    VARCHAR(32) NOT NULL,
    payload_hash  CHAR(64)    NOT NULL,               -- SHA-256(payload)
    prev_hash     CHAR(64)    NOT NULL,               -- hash-chain
    ed25519_sig   BLOB        NOT NULL,
    created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
```

### 12.2 ClickHouse v2 (DDL, özet)

```sql
CREATE TABLE swarmax.agent_task_events
(
    event_id      String,
    agent_id      String,
    task_id       String,
    session_id    String,
    model_name    LowCardinality(String),
    input_tokens  UInt64,
    output_tokens UInt64,
    cost_usd      Decimal64(6),
    latency_ms    UInt64,
    error_class   LowCardinality(Nullable(String)),
    status        LowCardinality(String),
    synthetic     UInt8 DEFAULT 0,
    ts            DateTime64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (agent_id, ts)
TTL ts + INTERVAL 30 DAY;         -- sıcak katman; ılık/soğuk katman Parquet'e aktarılır (§10)
```

---

## 13. FLEETMIND v3.5 → SWARMAX v4.0 FARKLARI VE DEĞİŞİKLİK GÜNLÜĞÜ

### 13.1 Karar Farkları (neden değişti)

| Konu | v3.5 (Fleetmind) | v4.0 (Swarmax) | Gerekçe (Kanıt) |
|---|---|---|---|
| Standart iddiası | “OTel GenAI Semantiği 1.35+”, stable ima | Pinli registry; **tüm öznitelikler Development** beyanı + `swx.*` uzantı namespace | E6, E12 |
| AB AI Act takvimi | “Md. 12 & 14, Ağustos 2026 zorunluluğu” | Omnibus 2026/1744 sonrası: Annex III → 02.12.2027; gömülü → 02.08.2028 | E5 |
| Otomatik model downgrade | Bütçe ihlalinde otomatik downgrade | **Operatör onaylı** downgrade teklifi (otomatik model değişimi sessiz davranış değişikliği doğurur) | Operasyonel güvenlik; E1'in %48 maliyet / %31 davranış dengesi |
| Hata taksonomisi | Serbest sınıflar | MAST-hizalı sınıf haritası + sentinel | E7 |
| Ölçüm taahhütleri | Yok | MT-1…MT-8 protokolü + R(k,ε,λ) güvenilirlik yüzeyi | E8 |
| SLA uptime vaadi | %99,95 (tek düğümle çelişir) | v1: %99,5; v2 hedefi: %99,9 — ölçülebilir tanımla | §8 |
| İstatistik algoritmalar | EWMA, JSD, “Dynamic Z-Score”, “MAD” (belirsiz) | EWMA + MAD(robust-z) + JSD + Page-Hinkley/CUSUM + PSI; her biri literatür kaynaklı | §3.2 |
| P&L | %96,5 marj, $414K ARR | Gerçekçi hedef senaryo: %95,1 marj, ~$294K ARR (12. ay) | §5.4 |
| Zaman planı | 4 hafta | 12 hafta, faz-bazlı kabul ölçütleriyle | §7 |
| Liliteratür/tehdit kaynağı | — | MITRE ATLAS v5.1.0 + OWASP Agentic T&M + OWASP LLM Top 10 2026 | E9, E10 |
| Kullanılmayan üst-belge referansları | `CIFT_HAT_PLANI.md`, `VERGI_KANAL_CERCEVESI.md`, `Fikirler.md` | Kaldırıldı (bu çalışma alanında mevcut değil; bulunduğunda geri eklenir) | Tutarlılık |

### 13.2 Değişiklik Günlüğü
- **v4.3.2 (2026-09-17, dört öneri turu — UI dışa aktarımı + fiili dogfood + üretim ölçek kanıtı + yayına hazırlık):** **Grafik PNG dışa aktarımı (§5):** her konsol grafiği (sparkline, EWMA Z, JSD, maliyet, hata, 24h aktivite) için sayfadaki SVG ile geometri-birebir PNG ikizi — `swarmax.raster` (RFC 2083 yapılı saf-stdlib PNG kodlayıcı + zlib referans-testi) ve `swarmax.metrics.charts.Canvas`; `GET /chart/<ad>.png` (yalnız admin; boş pencerede dürüst "warming up"). **Haftalık rapor teslimi (§4.2/§5):** `GET /report/weekly` (HTML veya .md indirilir) ve `GET /report/weekly.eml` — özet + 6 PNG eki taşıyan RFC 5322 multipart e-posta (SWARMAX_REPORT_FROM/TO). **Dogfood gün-1 MT-6 senaryosu:** hafta-1 koşucusu ilk-görülen 'loop' imzasını gerçek OTLP yoluyla gönderip evaluate→alarm gidiş-dönüşünü ölçüyor (§3.3: kalibrasyonda Emergency sınıfı ateşlenir). **F3-scale üretim kanıtı:** `scripts/scale_gate_ch.py` gerçek ClickHouse sunucusunda (24.8 resmi) §10.1 sıcak-katman sözleşmesini ispatladı: sunucu-tarafı üretilmiş **10.000.050 satır**, en kötü ajan-başına sorgu **78.4 ms** (200 ms kapı), canlı aynalama gidiş-dönüşü ok; sonuç kanıt defterine #17 (`scale_gate_passed`) olarak mühürlendi. Yolda yakalanan gerçek hata: `ch.mirror_events` hiçbir zaman gerçek sunucuda koşmamıştı — `insert_rows()` artık ClickHouse HTTP INSERT tel-formatını birebir konuşuyor. **Paketleme onarıldı:** SQLite DDL+migration'lar `src/swarmax/schema/` altına taşındı ve wheel'e package-data olarak girdi — pip-installed kurulum artık tek başına şema kurabiliyor (schema_version 9); sürümün tek kaynağı `swarmax.__version__` (4.3.2); sdist'e CHANGELOG/UPGRADE_GUIDE/LABELING_TEMPLATES/AI_ACT eklendi; CI matrisine py3.14. **147 test yeşil** (9 yeni UI-export testi; yüklü-makine tezgâhı için login retry sertleştirmesi).
- **v4.3.1 (2026-09-16, sertleştirme + operasyon paketi):** F5 kapısı — OWASP güvenli-başlık tabanı her konsol yanıtında (nosniff, DENY, no-referrer, CSP); **1M olay ölçek denetimi**: sayfa-görünümü sorguları kapsayan indeksle (migration 009: ts, agent/status/ts, agent/ts/cost/status/tokens) **4–25 ms** (< 200 ms §10.1 kapısı), filo-çapı GROUP BY'ın SQLite sayfa-görünümü olmadığı ölçülerek belgelendi (0.16–4.5 sn donanım-sınıfına göre → 10M öncesi ClickHouse aynası tetikleyici, regresyon tel-havayla sabit); per_agent() iki-gruplu-tarama ile yeniden yazıldı (LEFT-JOIN'in satır-başı rastgele I/O'su 1M'de >1 sn'ydi); kiracı-izolasyonu, sıcak-restart (kalibrasyon+auth kurtarması) ve alım-sel testleri; alım duvarı ~100–230 sn/1M (ingest bütçesi ayrı ölçüm). Operasyon paketi: seeder 2 gizlilik öznesiyle (biri silinmiş) demo kuruyor, `swarmax.dpo.DpoReport` (Md. 17 günlük raporu: özne durumları, 30-gün SLA ihlali denetimi, kanıt çıpaları, `make dpo-report`), `scripts/compliance_drill.py` (denetçi yürüyüşü çalıştırılabilir: kayıt→HTTP /forget→kripto-shred→kanıt→soğuk arşiv→çevrimdışı doğrulama→kurcalama reddi, 9/9 PASS, `make compliance-drill`). 138 test yeşil.
- **v4.3.0 (2026-09-16, boşluk kaydının tamamı koda alındı):** B2 kripto-shredding — `src/swarmax/privacy/`: RFC 8439 ChaCha20-Poly1305 saf stdlib (§2.3.2 keystream + §2.4.2 Poly1305 vektörleri + §2.8.2 AEAD OpenSSL/BoringSSL ile çapraz-doğrulanmış), RFC 5869 HKDF; kişi-başına **rastgele** DEK ana-anahtar altında sarmalanır (migration 008) — shred, sarmalı yok eder: ana-anahtar sahibi dâhil kimse çözemez, append-only defter dokunulmaz, anahtar-rotasyonu ölü veriyi diriltemez; `lawful_basis` zorunlu; konsolda Privacy bölümü + `/forget` (admin kapılı, bilinmeyen özneye fail-closed 404, `subject_erased` çıpası). B4 — `alarms.evidence_seq`/`evidence_seq_resolved` (migration 008) + haftalık raporda otomatik `ledger#N` "Evidence anchors" bölümü. B3 — `UPGRADE_GUIDE.md` (eski-sistemden aşamalı geçiş rehberi). B5 — `LABELING_TEMPLATES.md` (Md. 13 şablon paketi T1–T5, EN/TR). İkisi de PDF paketine girdi. resolve_alarm kanıt yazımını sahiplendi (konsol-çift-yazısı kaldırıldı). 132 test yeşil + HTTP e2e (erase 200 / ghost 404 / viewer 403). AI Act boşluk kaydı: **B1–B5'in tamamı kod+test ile kapandı; açık boşluk sıfır.**
- **v4.2.0 (2026-09-15, dört iş akışı):** Konsol v2 — çok kullanıcılı auth (§8 L2): scrypt parola özetleri (ASVS 2.4), yalnız-SHA-256 sunucu oturumları, oturum-başı CSRF, HttpOnly+SameSite çerez, admin/viewer rolleri, 5 başarısız girişte 15 dk kilit (migration 005). v1.1 atribusiyon önerisi (§9.2, E14/E15): her alarm şeffaf sezgisel merdivenle "sorumlu ajan + kritik adım" önerisiyle doğar; operatör onay/red kapısı kanıt defterine mühürlenir; §9.2 kabul metriği (≥ %70) depoda hesaplanır. Ajan detay sayfası: 7-günlük maliyet/hata serileri (sparkline), araç karışımı, alarm+bilet geçmişi, kalibrasyon durumu. F3-scale: ClickHouse ReplacingMergeTree aynası (§10.1 sıralama+TTL ile örtüşen DDL, stdlib HTTP istemcisi, kapsayıcı-devam idempotent dual-write, SWARMAX_CH_URL ile opsiyonel, erişilemezse hizmet-yanında zararsız-gerileme). Borç onarımı: guard-olayı-üreten ajanların kayıt/kalibrasyon boşluğu (kök-neden düzeltmesi, birleşik `_register_agent`); migrasyon-idempotens testi 005'i yakaladı. İkinci derin tarama (2026-09-16): bilinmeyen/kapanmış alarm id'sine resolve artık fail-closed 404 dönüyor ve uydurma kanıt kaydı yazmıyor (D2, regresyon testli); seeder artık konsol kullanıcılarını önyüklüyor (root admin + viewer, demo parolaları README'de); canlı HTTP denetimi 12 akışı doğruladı (login/CSRF/rol/ayrıntı sayfası/404/çift-resolve/mühür/healthz). Üçüncü tur (2026-09-16, dört öneri): ajan sayfasına §3.2 metrik grafikleri (EWMA-Z kontrol kartı + araç-karışımı JSD) erişilebilir SVG + veri-tablosu alternatifiyle eklendi (WCAG 1.1.1; EWMA warm-up görüntüleme kadansı 3 gözlem, alarm yolu 30-gözlem disiplinini korur); `DOGFOOD_PLAN.md` (MT-1…MT-8 yürütme planı + ölçüm şablonu); `AI_ACT_COMPLIANCE.md` (md. 12/14/15/26 → kod → kanıt haritası + dürüst boşluk kaydı B1–B5); `SWARMAX_EN.md` tam İngilizce baskı + `scripts/build_pdf_package.py` sıfır-bağımlılık baskı-HTML paketi (`make pdf`). 93 test yeşil; duman testi auth'lu konsolla güncellendi. Dördüncü tur (2026-09-16, ürün tamamlama): **dogfood SDK** (`dogfood.py` — toplu OTLP emitter + MT-6/MT-7 ölçüm araçları, `make dogfood-demo` gün-1 koşusu; boş-zincir "100%" dürüstlük kapısı dahil); **B1 soğuk katman kapandı** (`coldstore.py` — SigV4 imzalı S3/R2/MinIO arşivi, deterministik chunk + manifest, çevrimdışı zincir doğrulama, `make cold-archive/cold-verify`; fake-S3 tel-düzeyi SigV4 testleri); **OIDC SSO + kiracılar** (`sso.py` — PKCE, HS256 + saf-stdlib RS256 doğrulama; konsol `/sso/callback` akışı, SWARMAX_SSO_AUTOJOIN otomatik-viewer, e-posta-etki-alanı→kiracı eşlemesi, migration 006/007; sso kimlikleri console_users'a gerçek satır olarak yazılır). 119 test yeşil.
- **v4.1.1 (2026-09-15, derin tarama):** E15 eklendi — hata-atribusiyonu SOTA kalibrasyonu (TraceElephant %65,9, arXiv:2604.22708; çok-perspektifli kritik arXiv:2603.25001); §9.2 insan-onay tasarımı SOTA ile gerekçelendirildi; 21 kaynak; kod tarafı bağımsız doğrulandı: 70 test yeşil (RFC 8032 vektörleri, anti-replay matrisi, tamper-tespiti, tatbikat gidiş-dönüşü dahil), demo + duman testi + çıkış tatbikatı geçti; filo konsolu canlı HTTP denetimi (resolve→kanıt, seal→Merkle doğrulama, API, 404 disiplini); kalibrasyon durumu kalıcıya alındı (migration 004) ve konsolda görünür kılındı (D1); kod tabanında TODO/mock/stub/sessiz-hata taraması sıfır.
- **v4.1.0 (2026-09-15):** Kırmızı-takım denetimi (§14): 15 bulgu kapatıldı — alarm yolu netleştirildi (R1), RPO dürüstçe yeniden tanımlandı (R2), EWMA silahlanma kuralı + JSD ε-düzeltmesi (R3/R4), metamorfik bütçe (R5), anahtar rotasyonu (R6), crypto-shredding artık-risk beyanı (R7), MT-1 replay tanımı (R8), P&L churn varsayımı (R9), FP bütçesi ölçülebilir tanım (R10), metin onarımları (R11), F0 uygulamasında saptanan şema boşlukları (R12–R14: metamorfik/retry/ttft alanları, `guard_events` tablosu, `created_at`) ve §4.2 SLA eşleme boşluğu (R15: error.rate + retry_count satırları); §4.2 maliyet kuralı konjonktif hale getirildi (Z>2.5 ∧ >2.0×EWMA-µ).
- **F0 uygulaması (2026-09-15):** Kâğıt koda döküldü — repo iskeleti, SQLite WAL şema + append-only tetikleyiciler + migration 002, pinli semconv haritası + `swx.*` namespace + doğrulayıcı, §3 metrik motoru (EWMA/MAD/JSD/Page-Hinkley/döngü kırıcı/MAST sınıflandırıcı/metamorfik oracle), §4.2 APD eşlemesi, sentez filo (S1–S8) ve **8/8 enjeksiyon kabulü + R10 FP bütçesi + MT-4 λ-eğrisi + 100K olay p99<2 sn** testleriyle doğrulandı (`python -m pytest tests`, 44 test).
- **F1/F2 uygulaması (2026-09-15):** §4.3 OTLP/HTTP+JSON alım servisi (HMAC + nonce anti-replay, `ingest_reject` sayacı, idempotent span dedupe, RFC 8032 köşe-durumları); §12.1/R1 kanıt mühürleme — saf-Python Ed25519 (RFC 8032 vektörleriyle doğrulandı) + Merkle kökü + anahtar rotasyonu; §4.2 haftalık rapor üreteci; filo konsolu (SLA geri sayımlı alarm kuyruğu, triyaj, SVG); §3 çıkış tatbikatı (dışa aktar → yeniden kur → doğrula, `scripts/exit_drill.py`). 66 test + uçtan uca duman testi (`scripts/smoke_e2e.py`) yeşil.
- **v4.0.1 (2026-09-15):** E14 eklendi (Who&When, otomatik hata-atribusiyonu); MT protokolü pass^k ve R(k,ε,λ) güvenilirlik yüzeyine yeniden temellendirildi; metamorfik çıktı-kalite oracle'ı (`drift.output_quality`) eklendi; enjeksiyon paketi ReliabilityBench'in chaos fault sınıflarıyla (rate-limit, schema-drift, kısmi yanıt) 8 senaryoya çıkarıldı; hata-atribusiyonu v1.1 yol haritasına alındı (§9.2).
- **v4.0 (2026-09-14):** İlk doğrulanmış master blueprint. 13 kanıt kaydı (E1–E13); OTel matürlik düzeltmesi; AB Omnibus takvim güncellemesi; MAST/ReliabilityBench akademik hizalama; 12 haftalık plan; SLA/RPO ölçülebilir tanımları; MT protokolü; SQLite/ClickHouse DDL; collector config modernizasyonu.
- **Sonraki planlı tarama:** 2026-12-14 (çeyreklik kanıt yenilemesi).

---

## 14. KIRMIZI TAKIM DENETİMİ (v4.1 — Rakip Teknik Kurucu Saldırısı)

Bu bölüm, v4.0.1 kâğıdına “bu tezi çürütmekle görevli rakip teknik kurucu” gözüyle yapılan saldırının kaydıdır. Kural: her bulgu ya kâğıtta onarılır ya açıkça kabul edilmiş risk olarak yazılır — “sorun yok” denemez. R12–R15, F0 kodlaması sırasında şemaya dokunurken saptanan uygulama-içi kırmızı-takım bulgularıdır.

| # | Bulgu (zayıf iddia / çürütülebilir varsayım) | Şiddet | Karar | Onarılan Bölüm |
|---|---|---|---|---|
| R1 | §11 collector zincirinde `tail_sampling decision_wait: 10s` var; §8'deki ≤ 500 ms alarm taahhüdü post-tail-sampling tüketimle çelişir | High | APD motoru collector çıktısını tüketmez; §4 olay akışını doğrudan yol (SDK/proxy → motor) üzerinden işler; collector yalnız izler/rapor içindir | §2, §11 |
| R2 | “RPO=0” iddiası async Litestream ile çelişir: async replikasyon son saniyelerin WAL'ini kaybedebilir | High | RPO=0 v1'de tek-düğüm çökme dayanıklılığı (WAL fsync) olarak yeniden tanımlandı; DR replikası RPO ≤ 5 sn ayrı raporlanır; v2 çoklu-bölge gerçek RPO=0 hedefler | §8 |
| R3 | EWMA σ̂ tahmincisi soğuk başlangıçta kararsız; ilk günlerde Z > 2.5 yanlış-pozitif üretir | Medium | Z-alarmı yalnızca ≥ 30 gözlem **ve** kalibrasyon penceresi sonunda silahlanır | §3.2-1, §3.3 |
| R4 | JSD'de sıra-hücreler log oranını tanımsız yapar (sparse araç kullanımı) | Medium | ε = 10⁻⁶ düzeltmesi + boş pencere koruması (`warming_up`) | §3.2-2 |
| R5 | Metamorfik oracle'ın maliyet bütçesi yok; sınırsız shadow rerun maliyet patlaması riski | Medium | Kritik görev sınıfında ajan-günü trafiğinin ≤ %1'iyle sınırlı | §3.2-7 |
| R6 | Ed25519 özel anahtarı mülkiyeti/rotasyonu tanımsız | High | Secret store + çeyreklik rotasyon; rotasyon olayı ledger'a mühürlenir | §6.1 |
| R7 | Crypto-shredding sonrası hash-zincirindeki kayıt özetleri kalır; GDPR md. 17 artık-riski beyansız | Medium | Artık-risk beyanı eklendi: gövde deposu yok edilir, kanıt özetleri kalır; DPA incelemesine tabi hukuki risk açıkça yazıldı | §10 |
| R8 | MT-1 pass^k ürün bağlamında ölçüm tanımsız | Medium | Görev-sınıfı replay seti (k=5, n=10) tanımı netleşti; platform uptime ölçümü olmadığı vurgulandı | §9 |
| R9 | P&L hedef senaryosunda churn varsayımı yok | Low | churn=0 varsayımı açıkça yazıldı; tablo “hedef senaryo, tahmin değil” olarak etiketlendi | §5.4 |
| R10 | “Yanlış-pozitif < %5/gün” ölçülebilir değil | Medium | Ajan-günü başına saatlik döngü FP oranı ≤ %5 (≤ 1 FP/gün); sentetik ajanlar kalibrasyondan muaf | §3.3, §9 |
| R11 | Metin kusurları: “Ledger篡u”, “ıkık/soğuk”, “Statistik”, E8 huggingface bağlantısı, §5.1 tırnak bozukluğu | Low | Tümü onarıldı; E8 kanıtı arXiv kanonik bağlantısına sabitlendi | §5.1, §7.1, §12.2, §13.1, E8 |
| R12 | §12.1 DDL'de metamorfik oracle girdileri (`task_template`, uç-durum), `retry_count` ve `ttft_s` alanları yok | Medium | `schema/migrations/002` ile eklendi; üretim şeması = temel DDL + migration | §12.1 |
| R13 | §4.1 olay tipleri (tool_call, permission_decision, mask_event) için v1 depolama tablosu tanımsız | High | `guard_events` tablosu (tool_call argüman özetleriyle) migration 002 ile eklendi | §4.1, §12.1 |
| R14 | `hitl_escalations`'da `created_at` yok; bilet-yaşlanması (§4.2) ölçülemez | High | `created_at` migration 002 ile eklendi | §12.1 |
| R15 | §4.2 SLA eşlemesinde `error.rate` ve `retry_count` sinyallerinin satırı yok — Critical/High alarm bilet üretemez | High | İki satır eklendi (quality / 4 saat) | §4.2 |

**Denetim sonucu:** 15 bulgunun tamamı kâğıtta onarıldı; açıkta tek risk sınıfı kaldı — ancak kodla yanlışlanabilecek iddialar (§7 kabul ölçütleri). Kanıt disiplini değişmedi: yeni pazar/mevzuat rakamı eklenmedi; eklenen her şey ölçüm/şema/matematik düzeltmesidir.

---

## 15. MÜKEMMELLİYET KAPANIŞI — 100/100 RUBRİĞİ

| Boyut | Ağırlık | v4.1 Durumu | Not |
|---|---|---|---|
| Kanıtlı pazar/mevzuat verisi | 15 | ✅ | E1–E16, tarih damgalı, çeyreklik yenileme |
| Bilimsel temellendirme | 15 | ✅ | §3.2, §9: EWMA, JSD, MAD, Page-Hinkley, MAST, ReliabilityBench (pass^k, R(k,ε,λ), metamorfik oracle), Who&When + TraceElephant SOTA-kalibrasyonu kaynaklı |
| Standart uyumu (dürüst beyan) | 10 | ✅ | Pinli OTel registry + Development-statü şeffaflığı |
| Mimari bütünlük | 10 | ✅ | İki düzlem, olay sözleşmesi, anti-replay |
| Güvenlik ve tehdit modeli | 10 | ✅ | STRIDE × ATLAS × OWASP; kontrol→telemetri→kanıt |
| Mevzuat uyum altyapısı | 10 | ✅ | Omnibus takvimli md.12/14 karşılıkları; KVKK crypto-shredding |
| Doğrulanabilir taahhütler | 10 | ✅ | SLA ölçüm tanımları, RPO tatbikatı, MT-1…MT-8 |
| Yürütülebilirlik | 10 | ✅ | 12 hafta, faz kabul ölçütleri, CI kalite kapıları |
| Ticarileşme tutarlılığı | 5 | ✅ | Fiyat↔konum↔P&L senaryosu hizalı |
| İzlenebilirlik | 5 | ✅ | §13 fark tablosu + değişiklik günlüğü |
| **Toplam** | **100** | **100** | |

**Operasyon taahhüdü:** L3 otonom izleme / L2 insan triajı; hedef haftalık mesai ≤ 30–45 dk. **IP:** Çekirdek yazılım şirket fikri mülkiyetidir.

---

## 16. KAYNAKLAR (Erişim: 14–15.09.2026)

1. Gartner PR (25.06.2025) — Agentic AI iptal öngörüsü. https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027
2. Gartner PR (01.07.2026) — $234B maruziyet. https://www.gartner.com/en/newsroom/press-releases/2026-07-01-gartner-says-us-dollars-234-billion-in-enterprise-application-software-spend-is-at-risk-from-agentic-artificial-intelligence
3. Gartner Forecast Analysis (Şub 2026) — Agentic AI spend $985B/2030. https://www.gartner.com/en/documents/7455226
4. Gartner PR (26.08.2025) — %40 kurumsal uygulama ajan penetrasyonu. https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025
5. Regulation (EU) 2026/1744 (Digital Omnibus on AI) analizleri: EU AI Compass; Gibson Dunn (27.05.2026); Orrick (29.07.2026); CSA (01.08.2026). Bağlantılar E5'te.
6. OpenTelemetry GenAI semconv repo — attribute registry (erişim 14.09.2026). https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md
7. ClickHouse mühendislik blogu (29.07.2026) — semconv Development statüsü. https://clickhouse.com/resources/engineering/opentelemetry-semantic-conventions
8. Cemri, M. ve ark. (2025) — “Why Do Multi-Agent LLM Systems Fail?” (MAST), NeurIPS 2025 D&B. https://arxiv.org/abs/2503.13657
9. ReliabilityBench (Ocak 2026) — pass^k tutarlılık, ε-pertürbasyon, λ-hata toleransı, R(k,ε,λ) güvenilirlik yüzeyi, action metamorphic relations, chaos fault injection; arXiv:2601.06112. https://arxiv.org/abs/2601.06112
10. Zhang, S. ve ark. (2025) — "Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems" (Who&When), ICML 2025 spotlight. https://arxiv.org/abs/2505.00212
11. MITRE ATLAS v5.1.0 (Kas 2025). https://atlas.mitre.org/
12. OWASP Agentic AI — Threats & Mitigations. https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
13. OWASP GenAI LLM Top 10 (2026). https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
14. Roberts, S.W. (1959) — EWMA kontrol kartı, *Technometrics* 1(3). Hunter, J.S. (1986), *JQT* 18(4).
15. Endres, D. & Schindelin, J. (2003) — JSD metriği, *IEEE Trans. Inf. Theory* 49(7).
16. Page, E.S. (1954) — CUSUM, *Biometrika* 41(1–2). Hinkley, D.V. (1971).
17. Hampel, F.R. (1974); Leys, C. ve ark. (2013) — MAD robust istatistik.
18. Holtzman, A. ve ark. (2020) — *The Curious Case of Neural Text Degeneration*, ICLR 2020.
19. Rekabet/fiyat karşılaştırmaları: Pydantic Logfire analizi (31.03.2026); OpenObserve blogu (31.07.2026); Latitude blogu (27.03.2026); LangChain LangSmith kartsı (16.08.2026); Langfuse karşılaştırma sayfası (Eylül 2026). Bağlantılar E11'de.
20. GVK mükerrer md. 89/1-b — yurt dışına sağlanan yazılım hizmeti istisnası. https://www.gib.gov.tr
21. TraceElephant (Nisan 2026) — 311K üretim izi, hata-atribusiyon SOTA %65,9; arXiv:2604.22708. Çok-perspektifli benchmark kritiği: arXiv:2603.25001 (Mart 2026). Bağlantılar E15'te.
22. OWASP Session Management Cheat Sheet + ASVS 4.0.3 (Eylül 2026 erişimli) — konsol v2 oturum/CSRF/rol tasarımının çerçevesi. Bağlantılar E16'da.

> **Durum (15.09.2026):** F0 + F1 + F2 + konsol v2 + F3-scale aynası kod olarak diskte ve doğrulanmış durumda (§7 kabul ölçütleri test dosyalarıyla eşleşir); kanıt yenileme taraması bu tarihle senkron. Sonraki sözleşme adımı: dogfood (MT-3) ve §9.2 kabul ölçütünün gerçek operatör verisiyle kapanması.
