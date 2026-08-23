# OffGrid — Go-To-Market Plan

Target: self-hosted creators & agencies fed up with per-clip / credit billing on hosted
AI media platforms. Product: self-hosted batch AI orchestration (queue, batch, retry,
resume) — BYO keys / BYO backend, one REST API + web dashboard, docker-compose up.

---

## 1 · Positioning — the wedge

**One line:**
> "Your AI media pipeline, on your infrastructure. Pay a flat rate for the orchestrator —
> stop renting every frame you make."

**Why it lands (the wedge is real, not invented):** hosted platforms monetize heavy users
with per-clip and per-second pricing and credits that expire. The person who does *volume*
(a 430-shot film, a content farm, an agency batch) hits a wall: marginal cost per output
stays high forever, and a ToS/censorship/price change is an existential risk to their
pipeline. OffGrid is the **"I escaped the toll booth"** product: they already own the keys
or the backend — they want to own the *pipeline* too.

Anti-positioning (what we do NOT sell and never claim): we are not a model, not a GPU
cloud, not "unlimited everything." Saying that loudly builds trust with exactly these buyers.

**The one-roof framing:** OffGrid converts a **variable per-output cost into a flat
orchestrator fee + their own direct infra cost.** That's the whole pitch.

---

## 2 · Target segments (who, and their exact trigger)

| Persona | Trigger (the moment they'll buy) | Willing to |
|---|---|---|
| **Solo heavy creator / filmmaker** (Grant is the avatar) | Got the bill for a big batch project; credits expired mid-project | Pay $30–50/mo to never think about per-clip again |
| **AI-content agency / studio ops** | Client deliverable requiring thousands of clips; margin eaten by per-second pricing | Pay $100–200/mo for team + node control |
| **Product teams embedding AI media** | "Our app's per-second AI cost is killing our margin" | Pay for the orchestrator + care about API/CI |
| **Self-hosters / platform refugees** | Values owning infra; hates vendor lock | Free tier, evangelize loudly (channel, not revenue) |

Secondary TAM (ethical + cheap to mention, don't lead with it): **data-stay** buyers —
businesses that want no footage/key material leaving their infra. Same product, different
motivation; helps enterprise/on-prem.

---

## 3 · Pricing tiers

Anchoring: **"costs less than a couple months of the per-output charges you're escaping."**

| Tier | Price | What you get | Fits |
|---|---|---|---|
| **Community** | $0 | 1 node · 3 concurrent jobs · 500 queued · all providers · dashboard + API · community support | Evaluation, self-hosters, spillover |
| **Pro** | **$39/mo** ($32 annual) | 12 concurrent · unlimited queued · priority lane · tuning (`max_attempts`, backoff) · DB backups · email support | Solo heavy creators (the 430-shot case) |
| **Studio** | **$149/mo** ($124 annual) | 5 nodes · 48 concurrent · 5 team seats · per-team API keys · audit log · priority support | Agencies, teams |
| **Enterprise / On-prem** | Custom one-time + support retainer | Air-gap deploy, DSO, white-glove install, SLA, custom providers | Businesses needing data to stay |

**Worked ROI (the number that sells):**
Heavy creator: **500 clips/mo.** Hosted platform at ~$1.20/clip avg = **$600/mo**, forever,
per-clip. OffGrid Pro **$39/mo** + direct model cost ~$0.30/clip = **$150/mo** → **$189/mo
total vs $600/mo. Save ~$411/mo (~68%)** — and the direct cost is *theirs to optimize*,
down to near-zero if they run their own stack. The orchestrator fee is the only price that
never moves with volume.

**Discounts that create urgency without cheapening:** first-100 Pro = **$29/mo** for 3 months;
annual = ~2 months free. Never discount Studio's first tier — anchor it as "the team plan."

**Price floor rationale:** $39 > the "buy once, done" homelab tinkerer (leave them to free).
The heavy-use persona self-segregates to $39 because the saving compounds with volume.

---

## 4 · Launch channels

Lead with **community ignition + the proof**, follow with **business selling**. Every channel
below is entered *honestly* — story-first, and the story is his.

### Community / developer (Phase 1 core)
- **GitHub open core** — the free tier's source is the funnel. Clear "Pro vs Community" in the README; `awesome-selfhosted` listing (when it qualifies).
- **Hacker News — Show HN.** Title stakes the wedge: *"Show HN: I made a 430-shot AI film and built a self-hosted batch engine so the per-clip bills wouldn't kill it."* The specific number + the escape is a built-in hook.
- **r/selfhosted** — the exact audience; post the story + repo, not a sales pitch. This sub rewards "I escaped X, here's my alternative."
- **Product Hunt** — timed launch; cover image = the pipeline draining the film.
- **X/Twitter** — thread: show 22 batch JSONs → OffGrid → draining queue → done. Before/after cost screenshot. Tag the AI-video creator crowd.
- **r/artificial, r/machinelearning, r/sideprojects, IndieHackers, dev.to** — secondary reposts.

### Creator distribution (Phase 2 swing — his home turf)
- **YouTube / TikTok / Shorts**: *"I shot a 500-clip AI film and made the tool that stopped me going broke."* The pipeline draining IS the video. He's a creator — this is native content, not ads.
- **1-2 influencer partnerships**: pay or gift Pro to 2 mid-tier AI-creator accounts for a genuine walkthrough + testimonial.
- **Case studies**: 2-3 agencies who "installed it, stopped paying per-clip, recovered cost in a month."

### Business (Phase 3)
- **Cold outreach to small AI-content studios / agencies**: framed as a cost-recovery tool with a 30-min ROI calc, not a SaaS pitch.
- **LinkedIn function content** for Ops/DevAI audiences.
- **"Alternatives to [platform]" demand capture**: content + landing that answers the people already searching "how do I stop paying per-clip / credits expired."

---

## 5 · Launch strategy (phased, with KPIs)

**Phase 0 — Dogfood (1 week).** Run OffGrid on Grant's own film batches end-to-end. This
produces the proof asset (video + cost delta) *and* hardens the product against his own
scale. Nothing launches before this runs.

**Phase 1 — Community ignition (days 1-14).** Open-core GitHub + Show HN + r/selfhosted + PH
on the same day (the "launch."). Early-bird Pro ($29/3mo) runs here. Goal: **500 signups,
≥30 paid** in 30 days. KPIs: signups, activation (≥1 batch import in week 1 — the real
"aha"), newsletter capture.

**Phase 2 — Creator swing (weeks 3-6).** The proof video across YouTube/TikTok/X + 2
partnership posts + first 2 case studies. Goal: drive *paid* signups, not just eyeballs.
KPI: free→paid conversion ≥4-6%, cost-to-recover < the monthly saving.

**Phase 3 — Business selling (month 2+).** Case-study-led outreach to agencies, Studio tier
push, white-glove install offer. KPI: MRR, Pro→Studio expansion, churn <3%, ≥1 on-prem deal
as proof of the enterprise motion.

**North-star metric:** **paid jobs processed / week.** It's the honest measure of value
delivered (not signups). Secondary: batch-import activation rate.

---

## 6 · Landing page copy (ready to drop in)

> # Your AI media pipeline. On your infrastructure. No per-clip toll.
> **Stop renting every frame you make.** Bring your own keys or your own backend —
> OffGrid owns the queue, the batched, the retries. One flat orchestrator fee, a web
> dashboard, and `docker compose up`.

> **The problem:** you paint in batches. A 500-clip project, a client deliverable, a
> content calendar. And every single clip is a line item — per-second billing, credits
> that expire, a bill that grows with your ambition and never shrinks. Worst of all,
> you're married to one platform's terms and one platform's prices.

> **The escape:** keep the models and keys you already have. Point OffGrid at your own
> keys or your own backend, drop in your batch JSON, and let it drain — prioritized,
> retried, resumable, on your box. **One flat price you'll actually want to grow into:
> the more you make, the better the math gets.**

> **Own it in 30 seconds:** `docker compose up` → open `http://localhost:8000` → import
> your batch → watch it drain. No credit card, no cloud signup, no vendor.

> **Built for the people who actually hit the limit:** a 430-shot film taught us that the
> per-clip bill is the real enemy of making at volume. This is the tool that stopped us
> going broke — we open-sourced the core so you never have to trust us either.

Sections: **How it drains** (the three-step queue/provide/batch visual) · **Bring your own
world** (three provider cards) · **The math** (the 500-clip ROI table) · **Pricing** (3
tiers, annual toggle) · **Trust** (open core, "your data never leaves your infra") · **FAQ
& objections** (below). CTA: **Try it free — Docker or Pro.**

---

## 7 · Objections → copy answers (must be first-party honest)

| Objection | Honest answer we put in writing |
|---|---|
| "Running models is expensive anyway" | You already pay for the keys. OffGrid stops the middleman's per-clip markup and the caps — your direct cost is yours to optimize, down to running your own stack. |
| "Self-hosting is hard / I'm not technical" | Web dashboard for you; API for your devs; `docker compose up` for the curious; we'll install it on your box for you (paid). Nobody's left on a CLI they don't want. |
| "Is this just a toy / another 'unlimited' scam?" | We never claim unlimited anything. We're an orchestrator, not a model or a GPU cloud. That's the entire point. |
| "My data / footage safety" | Runs where you choose. Your queue, your keys, your output never leave your infra. |
| "What if I'm locked into my provider?" | Then don't switch. Point `generic_http` at it and OffGrid sits in front — you still own the queue. |

Risks worth naming internally: model/GPU-cloud players may bundle an orchestrator for free
(mitigate with BYO-backend openness + the flat-price wedge); self-hosters are price-sensitive
(mitigate with free core + $39 heavy-user upcharge); support cost of self-hosted installs
(mitigate with paid white-glove tier + docs).

---

## 8 · 30 / 60 / 90

- **30 days:** Phase 0 film runs → Phase 1 launch done → 500 signups, 30 paid, activation ≥40%.
- **60 days:** Phase 2 proof video + partnerships live → 100 paid, ~$4k MRR, 2 case studies written.
- **90 days:** Phase 3 agency motion running → 150 paid / ~$8k MRR, ≥1 on-prem deal signed,
  pipeline documented (the 430-shot film as the flagship case study).

**The through-line:** every step sells the same story — *you already paid for the means to
make; stop paying per frame.* OffGrid is the tool you'd have wanted before your project got
big, which is how you know the buyer exists: he's you.