# SWARMAX — Yatırımcı Tek Sayfası

*Ajan filolarının işletim katmanı (Fleet Operations Layer)* · v4.2.0 · 16.09.2026 · Tam veri: `SWARMAX.md` (kanıtlı master blueprint, E1–E15)

---

**Problem.** Otonom ajan filoları büyüdükçe dört kâbus: **maliyet kaçakları, davranış sürüklenmesi, denetim/kanıt boşluğu, SLA'sız insan gözetimi.** Gartner'a göre agentic projelerin **%40+'ı 2027 sonuna kadar iptal riskinde** (25.06.2025) ve **$234B** kurumsal yazılım harcaması bu dalgaya maruz (01.07.2026). Framework'ler (LangGraph, CrewAI, AutoGen…) filoyu *inşa eder*; **işleten kimse yok.**

**Çözüm.** Swarmax = filonun işletim katmanı:
1. **5 metrik ailesi** (maliyet/gecikme/hata/sürükleme/eskalasyon) — EWMA, MAD, JSD, Page-Hinkley; her biri literatür kaynaklı, eşikleri kalibre edilebilir.
2. **Kanıt-zincirli denetim:** Ed25519 + Merkle append-only ledger; GDPR/KVKK uyumlu crypto-shredding; AB AI Act md. 12/14 teknik altyapısı.
3. **SLA'lı insan eskalasyon (HITL):** 30 dk–24 saat geri sayımlı triaj kuyruğu; kill-switch çok-katmanlı infaz.
4. **Sıfır kilitleşme:** pinli OTel GenAI şeması + açık `swx.*` uzantı namespace; tam çıkış ≤ 1 saat.

**Neden şimdi.** (a) 2026'da kurumsal uygulamaların **%40'ı** görev-özel ajan içeriyor (Gartner, 26.08.2025). (b) AB Digital Omnibus (2026/1744) yüksek-risk takvimini **02.12.2027**'ye sabitledi → ~**15 aylık** kanıt-altyapısı penceresi açık. (c) Rakip manzarası (Langfuse'un ClickHouse'a katılması dahil) developer-observability'ye sıkışmış; **işletme katmanı boş.**

**Pazar.** Agentic AI yazılım harcaması **2030'da $985B** (Gartner, Şub 2026; 2025–30 CAGR %62,7).

**Fiyat — hibrit güven-hendeği modeli (v4.3.2 kararı):** Açık Çekirdek **$0** (Apache-2.0, tam özellikli — self-host hendeği ücretsiz) · **Yönetilen Bulut:** Ekip **$99/ay** (10 ajan, operasyon bizde) · Filo+Kanıt **$599/ay** (50 ajan + kanıt teslimi) · Kurumsal **$2.400/ay+** (BYO-storage, özel SLA). Eski **$199/ay** Team rakamı
internal-only'dir — sunulmaz (sahip kararı 2026-09-29; kamu fiyatlandırması
`docs/landing.md`). **İlk-90-gün odağı — Evidence Trust Services:** haftalık mühür köklerine HSM'li **RFC 3161 sayaç-imzası** + denetçi portalı + bağımsız doğrulama API'si (**$350/ay**) — self-signed kanıtın hukuken zayıf kaldığı yerde üçüncü-taraf güveni satılır; hendek kod değil **güven ağı**. Enterprise modülü (SAML/SIEM/HA) yalnız ödenmiş pilotla doğrulanınca yazılır.

**Birim ekonomi.** Marj **%88–95** · Başabaş **1 müşteri** · Onboarding ~3 sa · Bakım ≤ 1 sa/ay/müşteri.

**12 ay hedefi (senaryo; churn=0 varsayımı — tahmin değil).** 50 müşteri → MRR $24.5K → **ARR ~$294K**, marj **%95,1**.

**Akademik ve güvenlik omurgası.** MAST hata taksonomisi (NeurIPS 2025) · ReliabilityBench tabanlı **MT-1…MT-8** ölçüm-taahhüt protokolü (pass^k, R(k,ε,λ) güvenilirlik yüzeyi) · Who&When tabanlı hata-atribusiyonu, alan SOTA'sı (%65,9) ile kalibre edilmiş insan-onay kapısı (v1.1 — depoda canlı) · MITRE ATLAS v5.1.0 + OWASP Agentic T&M/LLM Top 10 2026 ile *kontrol→telemetri→kanıt* matrisi. **Çalışan kanıt:** 147 test + **10M-olay ClickHouse ölçek kapısı gerçek sunucuda PASS** (en kötü ajan sorgusu 78.4 ms, §10.1; kanıt defterine mühürlü); OTLP alımı (HMAC anti-replay), Ed25519+Merkle mühür, çok kullanıcılı konsol (scrypt/CSRF/roller + **OIDC SSO**), ajan detay sayfaları + **grafik PNG dışa aktarımı + haftalık rapor e-posta** (RFC 5322, 6 PNG eki), S3-uyumlu soğuk arşiv (SigV4), **RFC 8439 kripto-shred silme yolu (Art. 17 `/forget`)**, çalıştırılabilir denetçi tatbikatı (`make compliance-drill`), **pip-installable wheel** (pip install → şema kurulumu tek başına) — hepsi sıfır-çalışma-zamanı-bağımlılıkla. **AI Act uyum boşluğu kaydı: B1–B5'in tamamı kod+test ile kapandı.**

**Dürüst riskler (kırmızı-takım denetimi §14 ile beyanlı).** Tek-geliştirici kilit noktası (F3'ten itibaren operatör) · OTel GenAI semconv'ları Development statüsünde (pinli registry stratejisi bilinçli tercih) · v1 SLA %99,5 + tek-düğüm RPO=0, DR replikası RPO ≤ 5 sn (dürüst tanım) · P&L hedef senaryodur.

**Yol.** 12 hafta, 6 faz (F0 kanıt tabanı → F5 sertleştirme), **dogfood-öncelikli**; her faz kabul ölçütü **8/8 alarm-enjeksiyon testi** ve MT protokolüyle doğrulanır.

**Ask.** Dogfood pilotu için ilk **5 üretim ajan filosu**; kanıt-paketi (Filo+Kanıt) için finans/uyum odaklı **2 kurumsal tasarım ortağı.**
