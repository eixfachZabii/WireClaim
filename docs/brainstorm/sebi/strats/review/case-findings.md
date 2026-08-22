# Cases 08–13 — full read, with clauses quoted

Extraction: `pdftotext -layout` (poppler, `/opt/homebrew/bin/pdftotext`) worked on every
`invoices.pdf`. No guessing anywhere below; every quantity and unit is verbatim from the PDF.

Read against `docs/brainstorm/sebi/strats/review/field-findings.md`, which covers Cases 0–7.
Everything marked **NEW** is not in that document.

Convention used throughout: **verified** = the policy clause is quoted verbatim.
**inferred** = my reading, no clause says it in terms.

---

## 0. The single highest-value finding, first

### `– –` in the quantity/unit columns is a near-perfect `t = 0` label — **NEW**

`field-findings.md` notes that "some Line Items carry `– –` for quantity and unit" and warns
that a parser assuming a numeric quantity breaks. That is true but it buries the lede. Across
all 14 extracted Cases there are exactly **16** such Line Items, in 5 Cases, and **every one of
them is an item I independently verdict `t = 0`** from a quoted policy clause:

| Case | POS | Line Item (verbatim) | why `t = 0` |
| --- | ---: | --- | --- |
| 01 | 3 | Preventive replacement of plant-room electrical components (no confirmed water contact) | not related |
| 04 | 5 | HDMI cables and remote controls | not surge-affected |
| 04 | 6 | Wall-mount bracket | not affected |
| 04 | 8 | Router (no diagnostic report provided) | unproven |
| 04 | 12 | Vehicle costs – return visit | second call-out |
| 04 | 13 | Wiring safety check of property distribution board | preventive |
| 08 | 21 | Electricity for drying equipment (separately metered) | 7.1.8(d) |
| 08 | 22 | Vehicle costs – return visit | 7.1.7(f) |
| 08 | 32 | Construction waste disposal | 7.1.8(c) duplicate of POS 17 |
| 08 | 39 | Catering for work crew | 7.1.8(b) |
| 09 | 2 | Full repaint of the entire shed, including the undamaged walls | 7.1.5 |
| 09 | 3 | Ultraviolet-resistant protective exterior coating | 7.1.8(a) |
| 09 | 8 | Vehicle costs – return visit | 7.1.8(d) |
| 09 | 9 | Catering for work crew | 7.1.8(b) |
| 09 | 16 | Transport charge for the tree waste (already billed by the tree service) | 7.1.8(c) |
| 10 | 5 | Replacement of designer sunglasses (mislaid separately, not taken in robbery) | 2.3.4(a) |

**Rule (deterministic, testable):** `quantity == "–" and unit == "–"` ⇒ set coverage
probability ≈ 0 ⇒ Limit `b = 0`, Charge `a` high (R6c free option).

Status: **inferred from 16/16 consistency**, each individually **verified** against a clause.
It is not proven that the generator uses `– –` *as* the zero marker — it may simply be that
non-indemnifiable outlay has no natural quantity. Either way the correlation is what we trade on.
Validate against settled leaderboard brackets for Games 1 and 4 before hard-wiring.

**Note the converse does not hold.** Plenty of `t = 0` items carry a normal quantity
(Case 08 POS 15 "1 flat rate", Case 13 POS 14 "12 m²"). This is a high-precision, low-recall
signal.

---

## 1. Case 08 — escape of water, multi-floor townhouse, 5 trades, 39 Line Items

`policy.txt`: **RESIDENTIAL DWELLING AND HOUSEHOLD CONTENTS INSURANCE**, 1,336 lines.
This is the richest Case in the corpus and by some distance the most adversarial.

### Peril and template mapping

Escape of water — maps to the **Cases 1 / 5 escape-of-water template**, but scaled up ~4×
(39 items vs 18 and 17). Same trade roster and *identical* fictional addresses recur:
`23 Fixit Boulevard, 70173 Wrenchford` (Handy Hans All-Trades, Building Services — Cases 1, 2,
4, 7, 11, 12), `7 U-Bend Boulevard, 23456 Pipeville` (Soggy Bottom Plumbing — Cases 1, 5, 11,
13), `3 Dehumidifier Drive, 45127 Damptown` (Blow-Dry Bros Drying Tech — Cases 1, 5, 11).

Exact-wording repeats from earlier Cases: **"Vehicle costs"** (POS 38 — all 14 Cases),
**"Construction waste disposal"** (POS 17, 32 — Case 13), **"Final site cleaning"** (POS 16 —
Case 1 POS 7), **"Drying fan"** (POS 18 — Case 1 POS 17, Case 11 POS 11), **"Condensation
dryer"** (POS 26 — Case 1 POS 16), **"Skilled worker hours"** (POS 37 — Cases 11, 1),
**"Administrative and claim-processing fee"** (POS 12 — Case 4 POS 14, verbatim),
**"Vehicle costs – return visit"** (POS 22 — Case 4 POS 12, verbatim).

### The description's planted facts

> "The family were away when the upstairs guest toilet cistern fill valve let go"

> "A robot vacuum in the living room set off on its own and dragged the water across a wider
> patch of parquet than the drip would have, wetting a rug and some skirting too, and the
> machine was a write-off."

> "A couple of the crews each billed for skip hire and debris disposal, the drying firm metered
> its own power and put a second visit on the bill, and there are a few extras floating about -
> a processing fee, catering for the crew, and, while everyone was in, the decorators also
> freshened up the master bedroom next door even though the water never reached it."

The last paragraph is an unusually generous tell — the description *names* four of its own traps.

### Peril cover — verified

> **2.4.2 Escape of water damage**
> "Escaping water means water that has emerged contrary to its intended purpose from:
> (a) pipes of the water supply, whether supply or drainage lines, or hoses connected to them;
> (b) other installations connected to those pipes or hoses, or the water-carrying parts of such
> installations …"
> "It is immaterial whether the water emerged all at once or over a longer period"

A cistern fill valve is (b). "Ran unattended for hours" is expressly immaterial. Peril: **covered**.

Multi-storey travel is expressly in scope — verified:

> **7.1.5** "Where water escaping from an installation travels through the floor build-up, the
> ceiling void, a shaft, a stairwell or another part of the construction into further rooms or
> onto further storeys, those rooms count as affected insofar as the loss investigation documents
> physical damage in them. A room the investigation does not so document remains unaffected,
> however plausible it may appear that the water reached it, and however close it lies to the
> rooms that were affected."

### Line Items, verdicts and clauses

**Invoice 2026-0156 — Handy Hans All-Trades Ltd, Building Services**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Remove and transport rug | 1 | pcs | **covered** | 7.1.7(h) |
| 2 | High-quality LED lighting above billiard table | 1 | pcs | **betterment + sub-limit; likely 0** | 7.1.9, 4.8.2 |
| 3 | Specialist rug cleaning | 1 | pcs | **covered** | 7.1.10 |
| 4 | Electrical inspection of robot vacuum cleaner | 1 | pcs | **covered** | 7.1.7(i) |
| 5 | Replacement robot vacuum cleaner (total loss) | 1 | pcs | **not covered, `t = 0`** | 3.3(i), 7.1.11 |
| 6 | Disassemble billiard table | 1 | pcs | covered, **inside the 4.8 sub-limit** | 4.8.3 |
| 7 | Inspect billiard table for moisture damage | 1 | pcs | covered, inside 4.8 | 4.8.3 |
| 8 | Replace damaged billiard cloth | 1 | pcs | covered, inside 4.8 | 4.8.2 |
| 9 | Recushion billiard table rails | 1 | flat rate | covered, inside 4.8 | 4.8.2 |
| 10 | Replace old cue sets | 1 | pcs | covered, inside 4.8; betterment risk | 4.8.2, 7.1.9 |
| 11 | Align and reassemble billiard table | 1 | pcs | covered, inside 4.8 | 4.8.3 |
| 12 | Administrative and claim-processing fee | 1 | flat rate | **not covered, `t = 0`** | 7.1.8(b) |

Clauses, verbatim:

> **7.1.7** "(h) the removal, transport and disposal of affected items, and the handling
> necessary for their cleaning, repair or replacement;
> (i) the inspection, testing and measurement carried out to establish whether and how far
> property was affected by the insured event, and to what extent it can be restored; **this is
> indemnified even where the property investigated turns out not to be indemnified.**"

That last sentence is a deliberate trap-pair with POS 5: **the vacuum itself is out, the
inspection of the vacuum is in.** A binary "the robot isn't covered so neither is anything
about it" gate gets POS 4 wrong.

> **3.3** "Damage caused by the following is not covered … (i) **the operation of a movable
> appliance or device after it has come into contact with escaping water, insofar as what is in
> question is the damage that the appliance or device sustains to itself**"

> **7.1.10 Restoration by cleaning** "Where affected property can be brought back to a usable
> condition by cleaning, washing or comparable treatment, indemnity is confined to the cost of
> that treatment together with the handling under 7.1.7(h). Replacement is indemnified only where
> it is demonstrated … that the treatment cannot restore the property"

→ POS 3 (cleaning) is the *correct* remedy for the rug; a replacement rug would have been out.

> **7.1.8(b)** "outlay belonging to a contractor's own business operation rather than to the
> repair - its own tools, blades, bits and comparable reusable equipment, its own diagnostic and
> measuring devices, **protective equipment and provisioning for its own personnel**, and
> **general administrative, handling or processing charges** levied in addition to itemised
> labour and materials"

→ POS 12 and POS 39 (catering), both `t = 0`.

**Invoice 2026-0157 — Smash & Grab Demolition Ltd, Dismantling**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 13 | Restore plasterboard ceiling | 8 | m² | **covered** | 7.1.1(b), 7.1.5 |
| 14 | Fill ceiling and wall surfaces | 15 | m² | **covered** | 7.1.7 |
| 15 | Repaint and re-carpet master bedroom (adjacent, unaffected room) | 1 | flat rate | **not covered, `t = 0`** | 7.1.5 |
| 16 | Final site cleaning | 1 | pcs | **covered** | 7.1.8(a) proviso, 5.2.1 |
| 17 | Construction waste disposal | 1 | pcs | **covered — this is the first charge** | 7.1.8(c) |

> **7.1.5** "Work carried out in a room, on a surface, on a building component or on an item that
> was not itself affected is not covered. This applies even where the work is carried out …
> (c) at the same time as covered work, in the course of it, or as part of the same overall
> project; or (d) by the same contractor as the covered work, and invoiced together with it."

**Invoice 2026-0158 — Blow-Dry Bros Drying Tech Ltd**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 18 | Drying fan | 3 | pcs | **covered** | 7.1.7(b) |
| 19 | Control measurement during drying | 2 | pcs | **covered** | 7.1.7(b), 7.1.8(c) 2nd sent. |
| 20 | Final measurement | 1 | pcs | **covered** | 7.1.7(b) |
| 21 | Electricity for drying equipment (separately metered) | – | – | **not covered, `t = 0`** | 7.1.8(d) |
| 22 | Vehicle costs – return visit | – | – | **not covered, `t = 0`** | 7.1.7(f) |

> **7.1.7(b)** "… The measurements taken to establish the moisture present, **to monitor the
> progress of the drying and to confirm its completion** form part of the measure"

→ POS 19 and 20 are expressly named. **`2 pcs` on POS 19 is NOT inflation** — 7.1.8(c) says:
"measures serving … different stages of one drying or investigation operation are separate items
of cost". A naive quantity-plausibility check would wrongly haircut this. **Genuinely
counter-intuitive — NEW.**

> **7.1.8(d)** "utility consumption drawn by equipment hired or provided for the repair where
> that equipment is charged at a rental or flat rate; **such consumption is deemed included in
> that rate**"

> **7.1.7(f)** "**one travel, mileage or call-out charge per contractor per invoice**,
> irrespective of how many visits were made; where an invoice carries more than one such charge,
> only the first is indemnified"

**Invoice 2026-0159 — Underfoot & Overcharge Flooring Ltd**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 23 | Remove floor covering in guest WC | 5 | m² | **covered** | 7.1.7(a) |
| 24 | Remove skirting boards | 12 | m | **covered** | 7.1.7(a),(d) |
| 25 | Insulation layer drying | 1 | pcs | **covered** | 7.1.7(b) |
| 26 | Condensation dryer | 2 | pcs | **covered** | 7.1.7(e) last clause |
| 27 | Side channel compressor | 1 | pcs | **covered** | 7.1.7(e) |
| 28 | Remove damaged parquet | 5 | m² | **covered** | 7.1.7(a) |
| 29 | Renew parquet floor | **12** | **m** | **covered but quantity/unit suspect** | 7.1.8(e) |
| 30 | Supply and install new skirting boards | 1 | pcs | **covered** | 7.1.7(c) |
| 31 | Open water-damaged ceiling surface | 2 | pcs | **covered** | 7.1.7(e) |
| 32 | Construction waste disposal | – | – | **not covered, `t = 0` — duplicate of POS 17** | 7.1.8(c) |

> **7.1.7(b)** "including the drying of concealed layers of a floor, wall or ceiling build-up"
> — POS 25 named.

> **7.1.8(e)** "outlay that cannot be attributed to the damage established under 7.1.5 or to the
> repair actually carried out, **including material whose type, quantity or dimension does not
> correspond to the installation documented as repaired**."

POS 29 is the sharpest quantity trap in the Case: parquet **removed** at `5 m²` (POS 28) but
**renewed** at `12 m` — a different unit *and* a larger number. Under 7.1.8(e) the renewal is
confined to the 5 m² documented as removed. Treat as ~5 m² of parquet, not 12 of anything.

> **7.1.8(c)** "… **A charge for clearing, removing or disposing of debris that covers the site
> or the works as a whole is indemnified once per insured event, however many trades invoice
> it.**"

Two `Construction waste disposal` lines, POS 17 and POS 32, from two trades. First one wins.

**Invoice 2026-0160 — Soggy Bottom Plumbing Ltd**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 33 | Leak detection / cause investigation | 1 | pcs | **covered** | 7.1.7(e) |
| 34 | Moisture measurement of multiple rooms | 1 | pcs | **covered** | 7.1.7(b) |
| 35 | Inspect and disassemble toilet cistern | 1 | pcs | **covered** | 7.1.7(e) |
| 36 | Replace fill valve in toilet cistern | 1 | pcs | **covered at standard grade** | 7.1.7(e) |
| 37 | Skilled worker hours | 3 | hrs | **covered** | 7.1.7(g) |
| 38 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |
| 39 | Catering for work crew | – | – | **not covered, `t = 0`** | 7.1.8(b) |

> **7.1.7(e)** "the investigation necessary to locate and identify the source of the damage,
> including the opening up of the construction and the dismantling of an installation where that
> is required to reach the source, the making good of what was opened up or dismantled, and
> **the renewal of the defective part from which the water escaped, at the cost of a
> standard-grade part of corresponding function**"

→ The fill valve *is* indemnified (many EoW policies exclude the failed part). Grade-capped.

### Case 08 adversarial constructions

1. **Sub-limit aggregation across seven Line Items — NEW vector.** POS 2, 6, 7, 8, 9, 10, 11 all
   attach to the billiard table, and the policy collapses them into a single capped amount:

   > **4.8.1** "The following categories of household contents are insured only up to the amount
   > stated for each of them in the schedule: (a) **recreational, games and leisure furniture of
   > the large-format kind, that is to say furniture intended to be played on, played at or
   > otherwise used for a pastime** rather than for ordinary living, together with its
   > accessories; here the amount applies per item"

   > **4.8.2** "Where the amount applies per item, it covers everything belonging to that item.
   > Accessories serving the item - its playing or working surface and the covering of that
   > surface, the implements and pieces used with it, **lighting mounted above it or on it**,
   > cushions, nets, edging and comparable equipment - are included within the amount and are
   > **not payable in addition to it**."

   > **4.8.3** "The amount likewise covers the ancillary work performed on such an item:
   > inspecting it, dismantling it, moving it, cleaning it, re-covering it, levelling, realigning
   > and reassembling it, and transporting it. **All items of cost relating to one such item are
   > added together, whoever invoices them and under whatever description, and the amount is
   > applied once to that total.**"

   > **4.8.4** "The amount applies **irrespective of the purchase price, the replacement price
   > and the grade of the item** and of its accessories, and **irrespective of the cost actually
   > invoiced** for the work under 4.8.3."

   The schedule amount is not in `policy.txt` (the document only says "stated in the schedule";
   no Schedule ships with the Case). So we cannot compute the cap. What we *can* say: the
   billiard cluster's aggregate `t` is bounded and the per-item `t` values are **deflated**
   relative to standalone market prices. POS 2 in particular is named twice over — betterment
   under 7.1.9 *and* "not payable in addition to it" under 4.8.2 — so it is my best candidate
   for a `t = 0` inside an otherwise covered cluster.

2. **Red herring — the robot vacuum enlargement.** This is a Case-7-style bait.

   > **7.1.11** "Where the area affected is materially larger than the insured event would by
   > itself … have affected, and that enlargement is attributable to an intervening factor - the
   > conduct of a person, the movement of an animal, or **the operation of an appliance or
   > device** - the additional area … is indemnified **only where the policyholder demonstrates
   > that the enlargement could not reasonably have been prevented**. It is for the policyholder
   > to establish the circumstances relied on, **in particular whether anyone entitled to act was
   > present at the premises while the enlargement was occurring** …"

   The description opens with "**The family were away**". Nobody was present, so the enlargement
   could not reasonably have been prevented, and the wider parquet patch, the rug and the
   skirting stay in cover. **The bait is the robot; the antidote is the first sentence of the
   description.** (*inferred* — 7.1.11 is a burden-of-proof test, so this is genuinely two-sided;
   the clause is quoted, my resolution of it is not.) What is **verified** and unambiguous is the
   final sentence: "The damage that the intervening appliance or device sustains to itself is not
   indemnified **in either case** (3.3(i))" → POS 5 is `t = 0` regardless.

3. **Duplicate debris disposal across trades** — POS 17 vs POS 32 (7.1.8(c)).
4. **Return-visit call-out** — POS 22 (7.1.7(f)).
5. **Separately metered utility** — POS 21 (7.1.8(d)). **NEW vector.**
6. **Catering + admin fee** — POS 39, POS 12 (7.1.8(b)).
7. **Unrelated redecoration** — POS 15, master bedroom (7.1.5).
8. **Unit/quantity mismatch** — POS 29 `12 m` vs POS 28 `5 m²` (7.1.8(e)).
9. **Anti-trap** — POS 19 `2 pcs` and POS 26 `2 pcs` look like inflation and are expressly
   permitted (7.1.8(c) second sentence, 7.1.7(b)).

### Case 08 price bands (EUR, gross, whole Line Item, German market)

Anchors: skilled trade labour €60–90/h, helper €40–55/h, call-out €40–90, building
drying €40–80/day/unit, plasterboard ceiling €45–80/m², filler/skim €15–30/m², parquet supply +
lay €80–150/m², skirting €20–40/m, screed/floor strip-out €15–30/m².

| POS | band | note |
| ---: | --- | --- |
| 1 | 80–150 | trivial |
| 2 | 0–400 | betterment + 4.8.2; lean 0 |
| 3 | 120–300 | |
| 4 | 60–120 | trivial but **covered** — do not zero it |
| 5 | **0** | |
| 6 | 250–450 | capped |
| 7 | 80–150 | capped |
| 8 | **400–800** | Simonis cloth + refit; expensive |
| 9 | **400–700** | expensive |
| 10 | 150–400 | |
| 11 | 300–600 | |
| 12 | **0** | |
| 13 | **360–640** | 8 m² × 45–80 |
| 14 | 225–450 | 15 m² × 15–30 |
| 15 | **0** | |
| 16 | 150–350 | |
| 17 | 200–450 | |
| 18 | 300–700 | 3 fans × multi-day |
| 19 | 160–300 | 2 × 80–150 |
| 20 | 80–150 | |
| 21 | **0** | |
| 22 | **0** | |
| 23 | 75–150 | |
| 24 | 60–120 | |
| 25 | 300–800 | |
| 26 | 200–500 | |
| 27 | 200–500 | |
| 28 | 100–175 | |
| 29 | **400–750** | priced as ~5 m² parquet, not 12 |
| 30 | 240–480 | 12 m × 20–40 |
| 31 | 150–400 | |
| 32 | **0** | |
| 33 | **250–500** | |
| 34 | 150–350 | |
| 35 | 80–180 | |
| 36 | 40–120 | standard-grade valve |
| 37 | 180–270 | 3 h × 60–90 |
| 38 | 40–90 | |
| 39 | **0** | |

Expensive (high `t`): 8, 9, 13, 25, 29, 33, 18, 11.
Zero: 5, 12, 15, 21, 22, 32, 39 (7 of 39). Likely-zero: 2.

---

## 2. Case 09 — storm, tree onto a garden shed, 3 trades, 16 Line Items

`policy.txt`: **RESIDENTIAL DWELLING INSURANCE**, 704 lines. Buildings-only (no household
contents category at all), but with a shed-specific extension.

### Peril and template mapping

Storm — but **not** the storm-surge-electronics template of Cases 2/4/6/7. This is a **new
scenario family: storm → structural damage to an ancillary structure → tree clearance → ground
works.** First appearance in the corpus. New trades appear: `79098 Barksdale` (Tree Service),
`34117 Binbrook` (Recycling Service). Carpentry (`11 Sawdust Street, 33098 Planktown`) recurs
from Case 5.

Exact-wording repeats: **"Vehicle costs"** (POS 7, 12), **"Vehicle costs – return visit"**
(POS 8 — Cases 4, 8), **"Catering for work crew"** (POS 9 — Case 8 POS 39, verbatim).

### Cover for a shed — verified

> **4.2.5 Further site installations** "Further site installations means, **exclusively, the
> ancillary structures of light construction standing on the insured site and serving the
> storage, upkeep or amenity of the insured building**, together with the components listed in
> 4.2.2 belonging to them."

> **2.5.5 Effect on ancillary structures** — ancillary structures on the insured site and their
> cladding, glazing and trim are within the storm cover.

The shed is "declared" per the description. Peril: **covered**.

### Line Items, verdicts and clauses

**Invoice 2026-0218 — Splinter & Sons Fine Woodworks Ltd, Carpentry**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Repair of the storm-damaged shed roof section (timber and covering, restored to the pre-loss standard) | 1 | flat rate | **covered** | 7.1.1(b), 7.1.7(c) |
| 2 | Full repaint of the entire shed, including the undamaged walls | – | – | **not covered, `t = 0`** | 7.1.5 |
| 3 | Ultraviolet-resistant protective exterior coating | – | – | **not covered, `t = 0`** | 7.1.8(a) |
| 4 | Renewal of all shed trim, including undamaged trim | 1 | flat rate | **not covered, `t = 0`** (see below) | 7.1.10 |
| 5 | Skilled carpentry labour for the roof repair | 1 | pcs | **covered** | 7.1.7(d) |
| 6 | Contractor hand tools and reusable equipment | 1 | flat rate | **not covered, `t = 0`** | 7.1.8(b), 1.3 |
| 7 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |
| 8 | Vehicle costs – return visit | – | – | **not covered, `t = 0`** | 7.1.8(d) |
| 9 | Catering for work crew | – | – | **not covered, `t = 0`** | 7.1.8(b) |

POS 1 self-labels its own *qualifier*: "(timber and covering, **restored to the pre-loss
standard**)". That is the inverse of the Case-4 "names its own disqualifier" pattern —
**an item that names its own qualifier — NEW.** It is a combined position ("timber and covering")
but every element is indemnifiable, so 7.1.10 does not bite.

> **7.1.8(a)** "measures directed at the general condition, cleanliness, tidiness, upkeep,
> preservation, modernisation or improvement of the insured property … **Treatments and products
> whose purpose or effect is to protect a surface against future weathering, ultraviolet light,
> moisture, decay or infestation belong to this heading and are not indemnified, irrespective of
> whether they are applied in the course of covered work, on an affected part, or by the same
> contractor as the covered work.** This does not affect the ordinary finishing products under
> 7.1.7(c)"

POS 3 is named almost word for word. And 7.1.9 shuts the betterment escape hatch:

> **7.1.9** "… **Products falling under 7.1.8(a) are not indemnified at all and are not brought
> back into cover by this provision.**"

**This is important and NEW: 7.1.9 betterment is a haircut, but 7.1.8(a) products are a hard
zero, and the policy says so explicitly to stop you applying the haircut.**

> **7.1.8(b)** "outlay belonging to a contractor's own business operation rather than to the
> repair - **the ordinary equipment of the trade within the meaning of 1.3, including its hand
> tools, reusable items, kits, sets and consumable small equipment**; its own diagnostic and
> measuring devices; **the catering, refreshment and provisioning of its own personnel**; and
> general administrative, handling, processing or coordination charges … **Plant falling under
> 7.1.7(e) does not belong to this heading**"

The last sentence is the anti-trap for POS 11 (see below).

> **1.3** "**Ordinary equipment of a trade** - the tools, appliances and reusable items that the
> trade brings to the site as a matter of course … **Plant that has to be brought in specially
> for a particular operation**, because the operation cannot be carried out with what the trade
> ordinarily brings, is not ordinary equipment of the trade."

> **7.1.8(d)** "**more than one travel, vehicle, call-out, return-visit or re-attendance charge
> on the same invoice.**"

**Invoice 2026-0219 — Tree Service**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 10 | Cutting and removal of the storm-felled tree from the shed roof | 1 | flat rate | **covered** | 5.2.3 |
| 11 | Lifting and earth-moving machinery hire | 1 | flat rate | **covered** | 7.1.7(e) |
| 12 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |

> **5.2.3 Emergency and loss-mitigation measures** "… **The taking down, cutting up and lifting
> away of an object that the event deposited on or against insured property falls under this head
> and under 5.2.1, together with the labour and the plant required for it.**"

> **7.1.7(e)** "**the hire or engagement of lifting, hoisting, earth-moving and comparable heavy
> plant, with or without an operator**, where the covered work objectively requires plant of that
> kind and it is not ordinary equipment of the trade within the meaning of 1.3. Such plant is
> indemnified at the hire or engagement charge actually incurred, **whether it is charged by
> time, by day or by operation**"

POS 11 is a deliberate anti-trap: "machinery hire" pattern-matches to POS 6 ("equipment") and to
the contractor's-own-kit exclusion, but 1.3 + 7.1.7(e) + the last sentence of 7.1.8(b) put it
squarely in cover. **A keyword rule on "equipment/tools/hire" gets POS 6 and POS 11 both wrong.**

**Invoice 2026-0220 — Recycling Service**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 13 | Disposal of shed roof timber and the broken glass pane (building debris) | 2 | pcs | **covered** | 5.2.1(a) |
| 14 | Disposal of felled-tree green waste and root ball (single mass under one cubic metre) | 2 | pcs | **covered** | 5.2.1(b) |
| 15 | Disposal and reinstatement of excavated soil and displaced paving around the shed | 2 | pcs | **covered** | 5.2.2 |
| 16 | Transport charge for the tree waste (already billed by the tree service) | – | – | **not covered, `t = 0`** | 7.1.8(c) |

> **5.2.1** "The following count as material arising … (b) trees, branches, foliage and comparable
> vegetal material that the insured event felled, broke off or deposited on the insured site,
> **together with the root mass of a felled tree or shrub where that root mass forms a single mass
> whose volume does not exceed [volume]**"
> "The following do not count as material arising … **(e) a root mass whose volume exceeds
> [volume]**"

POS 14 self-labels its own qualifier: "**(single mass under one cubic metre)**". The `[volume]`
placeholder is unfilled in the policy, so the item's own parenthetical is the only figure
available — and it is phrased to satisfy 5.2.1(b). **Covered.** Another "names its own qualifier".

The soil line is the Case's best red herring. Two clauses appear to kill it:

> **4.3** "Not insured: … (d) **the ground material of the insured site**, and the laid or paved
> surfaces that are not terraces within the meaning of 4.2.4. Damage to such property is not
> indemnified as such; **the ground works provided for in 5.2.2 are unaffected by this**"

> **5.2.1** "(d) **ground material**, in whatever form and however processed, and irrespective of
> whether the insured event displaced, churned up or loosened it. **The ground works under 5.2.2
> are unaffected by this.**"

And 5.2.2 restores it:

> **5.2.2 Ground works made necessary by a reinstatement** "Ground material that has to be taken
> up, taken away or replaced is indemnified only where all of the following are met: (a) the work
> is carried out on the ground and the laid surfaces immediately surrounding insured property that
> the insured event affected; (b) the work is necessary in order to carry out, or arises in the
> course of carrying out, the reinstatement of that insured property; and (c) **the ground and the
> surfaces concerned are made good again as part of the same work.**
> Where those conditions are met, the taking up, the removal and disposal of the displaced
> material, and the making good of the ground and of the laid surfaces to their pre-loss condition,
> **are indemnified together as one operation.**"

POS 15 reads "Disposal **and reinstatement** of excavated soil and displaced paving **around the
shed**" — (a) around affected insured property ✓, (b) arises from the reinstatement ✓,
(c) made good as part of the same work ✓ (the word "reinstatement" is in the line item).
**Covered.** The description's "grounds-reinstatement endorsement (GR-2026)" is a *pointer*, not
a document — I grepped `case_09/policy.txt` for `GR-2026` and `endorsement`: **zero hits**.
The description names an endorsement the policy does not contain, and 5.2.2 achieves the same
result. **NEW: the description can cite a non-existent endorsement whose effect the base policy
independently delivers.** Do not treat a missing endorsement as a coverage failure without
checking the base wording.

> **7.1.8(c)** "the same item of cost where it is invoiced more than once … **In particular,
> where one trade has charged for taking material away from the insured site, a further haulage,
> transport or conveyance charge for that same material by another trade is not indemnified**;
> this does not affect a separate charge for depositing and destroying that material at the
> disposal site."

POS 16 is described by that sentence almost literally. `t = 0`.

### The Case 09 headline rule — combined positions are all-or-nothing — **NEW**

> **7.1.10 Combined positions** "A combined position within the meaning of 1.3 is indemnified
> **only where every operation, every kind of material and every part of the insured property
> that it covers is itself indemnifiable** under these conditions.
> **Where any element of a combined position is not indemnifiable, the position is not
> indemnified. The indemnifiable elements are not extracted from it and are not estimated,
> because the position does not state what falls to each.**
> The policyholder may at any time submit the position re-stated by the contractor in separate
> lines …"

> **1.3** "**Combined position** - a single line of an invoice that covers more than one
> operation, more than one kind of material, or more than one part of the insured property."

POS 4 — "Renewal of **all** shed trim, **including undamaged trim**" — is a combined position
covering both affected and unaffected trim. Under 7.1.5 the undamaged part is out; under 7.1.10
the *whole position* therefore falls away. **`t = 0`, not a partial haircut.** This directly
contradicts the general rule in `field-findings.md` that "betterment is a partial haircut, not a
binary" — that rule holds for 7.1.9 grade upgrades, but **7.1.10 converts a mixed position into a
total zero.** The distinguishing test is *what* is mixed: a mixed **grade** is a haircut
(7.1.9); a mixed **scope** in one undifferentiated line is a zero (7.1.10).

Note 7.1.7(d) contains the counterweight, so this is not a licence to zero everything bundled:

> **7.1.7(d)** "… **Labour is indemnified whether it is billed as one position or as several
> positions covering distinct operations**, provided each position corresponds to work actually
> carried out on the affected parts …"

### Case 09 price bands (EUR, gross)

Anchors: carpenter €65–90/h, tree surgeon €80–120/h + crane, skip/green-waste disposal
€120–300 per load, mini-excavator + operator €400–700/day, shed roof section (timber + felt/
shingle) €150–300/m².

| POS | band | note |
| ---: | --- | --- |
| 1 | **1,500–3,500** | biggest item in the Case |
| 2 | **0** | |
| 3 | **0** | |
| 4 | **0** | (if 7.1.10 read is wrong, 200–450 as a haircut) |
| 5 | **500–1,200** | |
| 6 | **0** | |
| 7 | 50–120 | |
| 8 | **0** | |
| 9 | **0** | |
| 10 | **800–2,000** | expensive |
| 11 | **600–1,500** | expensive |
| 12 | 50–120 | |
| 13 | 200–500 | |
| 14 | 250–600 | |
| 15 | **500–1,500** | expensive |
| 16 | **0** | |

Zero: 2, 3, 4, 6, 8, 9, 16 — **7 of 16 (44 %)**.

---

## 3. Case 10 — armed robbery abroad, watch + cash, 6 Line Items

`policy.txt`: **HOUSEHOLD AND PERSONAL EFFECTS INSURANCE**, wording "WD-2026" —
**Robbery and Personal Effects Edition**, 823 lines.

### Peril and template mapping

Theft/robbery — maps to the **Cases 0 / 3 theft template**. But unlike Case 3 (buildings-only
policy, suitcase from a car ⇒ everything `t = 0`), this policy is *purpose-built for this claim*
and the robbery itself **is** covered. New trades: `10119 Wordsworth` (Translation Services).
`88 Cheque Chase Road / 20095 Refundton` (Compensation Payment) recurs from Case 3.

Repeats: **"Shipping"** (POS 6 — Case 2 POS 2, Case 4 POS 9, verbatim),
**"Material costs"** (POS 2 — Case 11 POS 22, Case 0-era wording).

### The structural novelty — **PART 11 tells you which clauses to apply — NEW**

This policy has a section no other Case has:

> **PART 11 - LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM**
>
> **11.1** "Insured property was taken from the policyholder in circumstances falling within
> 2.3.1 while the policyholder was away from the insured premises. The event was reported to the
> competent public authority at the time. The affected items belong partly to classes for which
> sub-limits are agreed in the schedule and partly to the general class under 4.2.1, and **no
> separate valuables schedule listing an individual item and its agreed value forms part of this
> contract**. **A further item was found to be missing on a separate occasion, without an event
> within the meaning of 2.3.1.**"
>
> **11.2** "Where a replacement chosen by the policyholder exceeds the grade, material or
> specification of the item it replaces, **7.1.9 applies before any class sub-limit**. Where the
> aggregate loss on a class carrying a sub-limit exceeds that sub-limit, the sub-limit applies;
> where it does not, and where the class carries no sub-limit, the indemnifiable loss is paid in
> full subject only to 7.8."
>
> **11.3** "Charges were raised alongside the settlement of the property itself: **for rendering
> supporting documents usable for the purposes of the claim and for certifying them; for the
> working materials and administrative handling raised alongside those charges; for forwarding;
> and for travel and accommodation arranged in consequence of the event.**"
>
> **11.4** "Clauses 2.3.1, 2.3.3, 2.3.4(a), 3.1.5, 3.1.6, 3.1.7, 4.2.1, 4.2.2, 4.2.3, 4.2.4,
> 4.2.5, 5.1, 5.2.5, 6.3, 7.1.1, 7.1.5, 7.1.7, 7.1.8(b), 7.1.8(e), 7.1.8(f), 7.1.9, 7.1.10, 7.5
> and 7.8 **are the operative provisions for determining how each line of each invoice and
> settlement statement in this claim is characterised.**"

**11.4 is a solved-exam answer key.** It enumerates exactly the 24 clauses that decide the Case.
`grep -n "^PART 11"` on every new Case is a 10-millisecond, zero-token check that can collapse a
823-line policy to two dozen paragraphs. **This is the single most actionable engineering finding
after the `– –` rule.** Note 11.4 does *not* list 7.1.8(a), (c), (d) or (g) — the vectors the
generator did not plant here.

### Line Items, verdicts and clauses

**Invoice 2026-0179 — Translation Services**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Translation from Spanish to English | 2 | hrs | **not covered, `t = 0`** | 3.1.6, 7.1.8(f) |
| 2 | Material costs | 1 | pcs | **not covered, `t = 0`** | 7.1.8(f), 7.1.8(e) |

This is the cruellest trap in the corpus, because 2.3.3 makes the police report a **condition of
cover** and the description stresses "the report had to be translated before it could go with the
claim". Necessity is expressly irrelevant:

> **2.3.3 Reporting requirement** "The event must be reported without delay to the competent
> public authority … **The report is a condition of cover; the cost of obtaining, translating,
> certifying or otherwise processing it is governed by 3.1.6 and 7.1.8.**"

> **3.1.6 Preparation and substantiation of the claim** "Establishing, evidencing and presenting
> the claim is a matter for the policyholder **at its own expense**. Outlay directed at the cause,
> the extent or the substantiation of the loss, or at rendering the supporting documents usable
> for the purposes of the claim, **is not an indemnifiable head of loss under this contract**.
> This applies in particular to the obtaining, copying, certifying, notarising, authenticating,
> legalising, transcribing, summarising, **translating into or out of any language**, interpreting,
> formatting, forwarding or filing of reports, statements, records, receipts, valuations and
> comparable documents, **however necessary those steps may be for the claim to be assessed,
> whoever performs them, and whether they are charged as a service, as a working material, as a
> disbursement or as a fee.**"

> **7.1.8(f)** "charges of the kind described in 3.1.4, 3.1.5, 3.1.6 and 3.1.7, including in
> particular any charge for **translating**, interpreting, transcribing, certifying, notarising,
> authenticating, summarising or otherwise processing a document for the purposes of the claim,
> **together with any working material, disbursement, surcharge or ancillary charge raised
> alongside such a charge, whether by the same provider or by another**"

The last clause kills POS 2 by name. **Rule: an "ancillary" line inherits the verdict of the line
it accompanies. — NEW.** Note the mirror rule for call-outs in 7.1.8(d):

> **7.1.8(d)** "call-out, travel, journey, mileage, vehicle, attendance and standby charges, **save
> where incurred on the occasion of, and on the same invoice as, a benefit that is itself
> indemnifiable; where nothing billed on an invoice is indemnifiable, the attendance charge on that
> invoice is not indemnifiable either.**"

**⇒ "Vehicle costs" is NOT unconditionally covered. If every other line on its invoice is `t = 0`,
the vehicle line is `t = 0` too.** `field-findings.md` flags "Vehicle costs" as the most repeated
Line Item and worth pinning down once. **It cannot be pinned down once — it is conditional on its
invoice.** This is a direct correction to a standing recommendation.

**Invoice 2026-0180 — Compensation Payment**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 3 | Compensation for stolen watch (premium replacement model, upgrade on the one taken) | 1 | pcs | **covered, haircut to standard grade, then valuables sub-limit** | 7.1.9, 4.2.2, 11.2 |
| 4 | Compensation for cash taken in robbery | 1 | pcs | **covered at nominal, means-of-payment sub-limit** | 7.1.1(c), 4.2.3 |
| 5 | Replacement of designer sunglasses (mislaid separately, not taken in robbery) | – | – | **not covered, `t = 0`** | 2.3.4(a) |
| 6 | Shipping | 1 | pcs | **not covered, `t = 0`** | 7.1.8(b) |

> **2.3.4 Damage excluded within this group** "Not covered: (a) **property mislaid, misplaced,
> forgotten, left behind, dropped or otherwise lost without an event within the meaning of 2.3.1.
> This applies in particular where an item is found to be missing on a separate occasion, at a
> separate place, or at a separate time from the insured event, whatever the proximity of the
> two**"

11.1 restates the same fact ("A further item was found to be missing on a separate occasion").
POS 5 self-labels. Belt, braces and a second belt.

> **7.1.8(b)** "**carriage, freight, delivery, dispatch, packaging, postage, courier, transport,
> logistics and comparable charges, whether for bringing replacement property to the insured
> location**, for forwarding documents or correspondence, or for returning items, **and whether
> stated as a separate line, as a percentage or as a flat rate**"

**"Shipping" is `t = 0` under this policy.** It appears verbatim in Cases 2 and 4 too, where the
policy may differ — check per Case; do not carry the verdict across peril families.

> **4.2.2 Valuables** "Items of jewellery, adornment worked from precious metals or set with
> precious or semi-precious stones, **timepieces**, loose precious metals and stones, collections
> and comparable items of concentrated value form a single class of property. Indemnity for this
> class is subject to the valuables sub-limit stated in the schedule, applied per item and, where
> more than one such item is affected, in the aggregate per insured event across all items, all
> providers and all invoices or settlement statements. Where a separate valuables schedule listing
> an individual item and its agreed value forms part of the contract, that agreed value applies in
> place of the per-item sub-limit for that item; **in the absence of such a schedule the per-item
> sub-limit applies whatever the actual value of the item, and whatever documentary evidence of a
> higher value is produced with the claim.**"

11.1 states there is **no** valuables schedule. So the watch is capped at an unstated sub-limit,
*after* the 7.1.9 upgrade haircut (11.2: "7.1.9 applies before any class sub-limit"). Both cuts
apply, in that order. The amount is not in the document.

> **7.1.9** "… Where a higher specification, a larger format, a superior material, a greater
> capacity or a premium range is chosen instead, indemnity is limited to the cost of an equivalent
> standard-grade replacement corresponding to what was in place before the loss … **Where the
> pre-existing item is no longer obtainable, the nearest currently available equivalent of the same
> grade sets the ceiling; an unavoidable difference is not treated as an improvement, a chosen one
> is.** This limitation applies before, and in addition to, any class sub-limit."

The description says the owner "**has gone for** … a newer, higher-spec model" — a *chosen*
difference. Haircut applies.

### Case 10 adversarial constructions

1. **Necessary-but-excluded claim-preparation cost** — POS 1. **NEW and nasty.**
2. **Ancillary line inherits the parent's verdict** — POS 2. **NEW.**
3. **Item names its own disqualifier** — POS 5.
4. **Betterment** — POS 3.
5. **Shipping as a non-indemnity** — POS 6.
6. **Two stacked sub-limits with an order of application** — POS 3 (7.1.9 then 4.2.2). **NEW.**
7. **Mostly-uncovered Case** — 4 of 6 items are `t = 0`, like Case 3. But *unlike* Case 3, two
   items are worth a great deal, so "the whole Field charged 0" would be wrong here.

### Case 10 price bands (EUR, gross)

Anchors: certified translation €40–80/h or €1.50–2.20/line; German household-contents valuables
sub-limit typically 20 % of sum insured, commonly €2,000–20,000; cash sub-limit commonly
€500–1,500; parcel shipping €10–50.

| POS | band | note |
| ---: | --- | --- |
| 1 | **0** | list value would be 80–200 |
| 2 | **0** | list value 15–50 |
| 3 | **1,500–6,000** | **the largest single `t` in Cases 08–13**; but sub-limit unknown and the haircut is real — high variance, widen the posterior |
| 4 | **300–1,500** | means-of-payment sub-limit; German norm ~€1,000 |
| 5 | **0** | list value 150–400 |
| 6 | **0** | list value 10–50 |

---

## 4. Case 11 — cellar leak at a compression fitting, 5 trades, 22 Line Items

`policy.txt`: **RESIDENTIAL DWELLING** boilerplate, 1,190+ lines. `description.txt` is only
602 bytes — the shortest of the six.

### Peril and template mapping

Escape of water, small scale — the **Cases 1 / 5 / 8 template**, minimal variant. Trade roster is
the standard five: Leak Detection (`4 Trickle Terrace, 12345 Puddleton`), Building Services
(Wrenchford), Drying Technology (Damptown), Plumbing (Pipeville), Tiling
(`8 Mosaic Mews, 60594 Tilebury` — first seen in Case 0).

Exact-wording repeats — this Case is nearly all recurring templates and is therefore the best
Price Memory target in the batch:

| POS | wording | also in |
| ---: | --- | --- |
| 2, 21 | **Skilled worker hours** | Case 1 POS 11, Case 8 POS 37 |
| 3 | **Material for the work** | Case 1 POS 12 ("Material for pool pipe repair") |
| 4, 18, 23 | **Vehicle costs** | all 14 Cases |
| 6, 10 | **Room dryer unit** | — |
| 11 | **Drying fan** | Case 1 POS 17, Case 8 POS 18 |
| 15 | **Profipress elbow 45° copper 28mm** | **Case 13 POS 3 — verbatim, same qty (1 pcs)** |
| 17 | **Helper hours** | Case 13 POS 8 |
| 20 | **Service technician hours** | Case 5 POS 3, Case 13 POS 7 |
| 22 | **Material costs** | Case 10 POS 2 |

**Cases 11 and 13 share a plumbing parts list almost line for line** — `Profipress elbow 90°
copper 15mm`, `Profipress elbow 45° copper 28mm`, `Helper hours`, `Service technician hours`,
`Vehicle costs`. If either settles, the other is nearly a direct read.

### `⚠️ POS 12 does not exist — NEW, and a parser hazard`

The invoice runs `… 10, 11` (Drying Technology) then `13, 14, 15 …` (Plumbing). **POS 12 is
absent from the PDF.** Verified by grepping the raw `pdftotext` output. Consequences:

- **Never assume `line_item_index == POS − 1`, and never assume POS numbers are contiguous.**
  A pipeline that enumerates rows and submits by ordinal will be off by one on every item from
  POS 13 onward in this Case. Given `field-findings.md`'s measurement that a quantity-convention
  slip costs 30,400–38,100 in one Game, an index slip is at least as expensive.
- Parse the POS column as data; reconcile the count of parsed rows against the API's line item
  count before submitting.
- Whether the API exposes 22 or 23 line items for Case 11 is **not something I can check
  read-only** — the parent agent should verify against the live endpoint.

### Peril cover, and the red herring

> "The problem was **a compression fitting on a wall-mounted pipe bend** down in the basement — a
> joint that wasn't sealed properly, **not an actual burst pipe**."

That phrasing is bait aimed at 2.4.3 "Fracture damage to pipework". It does not matter, because
2.4.2 is a separate and independent heading:

> **2.4.1 The three headings** "The escape of water peril covers three things: **escape of water
> damage; fracture damage to pipework inside buildings; and fracture damage to pipework outside
> buildings.**"

> **2.4.2 Escape of water damage** "Escaping water means water that has **emerged contrary to its
> intended purpose** from: (a) pipes of the water supply, whether supply or drainage lines, or
> hoses connected to them; (b) **other installations connected to those pipes or hoses, or the
> water-carrying parts of such installations** …"

A leaking compression fitting is (a)/(b) and the water emerged contrary to its intended purpose.
**No fracture is required for the 2.4.2 limb.** And nothing in 3.3 excludes faulty workmanship —
I read all of 3.3 (a)–(h): the list is splash/cleaning water, dry rot, groundwater/flood/
precipitation, earthquake/snow/avalanche/volcano, subsidence, the fire group, sprinkler
operation, storm/hail. **Peril: covered. Verified.**

**Red herring, Case-7 class.** The suspicious-sounding detail ("not an actual burst pipe", "a
joint that wasn't sealed properly") does not remove cover.

### Line Items, verdicts and clauses

**Invoice 2026-0013 — Leak Detection**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Indoor leak detection | 1 | pcs | **covered** | 7.1.7(e) |

**Invoice 2026-0014 — Building Services**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 2 | Skilled worker hours | 8 | hrs | **covered, quantity suspect** | 7.1.7(g), 7.1.8(e) |
| 3 | Material for the work | 1 | pcs | **covered** | 7.1.7(c) |
| 4 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |

**Invoice 2026-0015 — Drying Technology** — the duplicate-equipment cluster

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 5 | Room drying 30 m² | 1 | flat rate | **covered** (first of the pair) | 7.1.7(b) |
| 6 | Room dryer unit | 1 | flat rate | **covered** (first of the pair) | 7.1.7(b),(e) |
| 7 | Removal and disposal of damaged insulation | 1 | m² | **covered** | 7.1.7(a) |
| 8 | Wet insulation wool from basement | 1 | pcs | **covered** | 7.1.7(a) 2nd sent. |
| 9 | Room drying 50 m² | 1 | pcs | **not covered, `t = 0`** | 7.1.8(f), 7.1.8(e) |
| 10 | Room dryer unit | 1 | pcs | **not covered, `t = 0`** | 7.1.8(f) |
| 11 | Drying fan | 1 | pcs | **not covered, `t = 0`** | 7.1.8(f) 1st sent. |

Case 11's 7.1.8 carries a sub-clause **(f) that no other policy in the corpus has**:

> **7.1.8(f)** "**an item charged in addition to equipment already charged for the same measure,
> where the additional item duplicates the function of that equipment or serves only to supplement
> it; such an item is deemed included in the charge for the equipment it accompanies.** Where one
> and the same item of equipment is charged more than once in connection with the measures under
> 7.1.7(b) undertaken in consequence of one insured event, **one charge is indemnified, however
> many stages, or parts of the affected property, those measures are carried out in.**"

Two `Room drying` lines, two `Room dryer unit` lines, plus a `Drying fan` supplementing the dryer.
The second of each pair and the fan all fall away. Reinforced by scale:

> **7.1.8(e)** "outlay that cannot be attributed to the damage established under 7.1.5 or to the
> repair actually carried out, including material whose type, quantity or dimension does not
> correspond to the installation documented as repaired."

The affected area is "maybe a square meter or so"; POS 9 bills drying for **50 m²**.

POS 7 vs POS 8 look like a duplicate but are not — 7.1.7(a) in *this* policy is worded to permit
the split:

> **7.1.7(a)** "taking down and dismantling the affected building components and finishes, **and
> carrying the material so taken down away from the insured location and disposing of it. These
> are distinct operations and may be charged separately from one another**"

**Invoice 2026-0016 — Plumbing**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 13 | Profipress elbow 90° copper 15mm model 01 | 5 | pcs | **covered, quantity suspect** | 7.1.7(c), 7.1.8(e) |
| 14 | Profipress elbow 90° copper 15mm model 02 | 5 | pcs | **covered, quantity suspect** | 7.1.7(c), 7.1.8(e) |
| 15 | Profipress elbow 45° copper 28mm model 03 | 1 | pcs | **covered** | 7.1.7(c) |
| 16 | Hose | 3 | m | **covered** | 7.1.7(c) |
| 17 | Helper hours | 5 | hrs | **covered** | 7.1.7(g) |
| 18 | Vehicle costs | **2** | pcs | **covered — both** | 7.1.7(f) |
| 19 | Transition piece 16x15mm | 3 | pcs | **covered** | 7.1.7(c) |
| 20 | Service technician hours | 5.5 | hrs | **covered** | 7.1.7(g) |

**⚠️ The call-out rule is policy-specific. Case 11 has no per-invoice cap:**

> **Case 11, 7.1.7(f)** "travel, mileage and call-out charges, **each one referable to an
> attendance at the insured location required in order to carry out the covered work**"

Compare, in the same corpus:

> **Case 08 / Case 12 / Case 13, 7.1.7(f)** "**one** travel, mileage or call-out charge **per
> contractor per invoice**, irrespective of how many visits were made"

> **Case 09, 7.1.7(f)** "**one** travel, vehicle or call-out charge **per trade invoice**"
> + **7.1.8(d)** "more than one travel, vehicle, call-out, return-visit or re-attendance charge on
> the same invoice" is not indemnified

> **Case 10, 7.1.8(d)** "… **where nothing billed on an invoice is indemnifiable, the attendance
> charge on that invoice is not indemnifiable either.** Where indemnifiable, one such charge per
> invoice is reimbursed; **return visits and repeat journeys in respect of the same insured event
> are not**"

So `Vehicle costs, 2 pcs` on Case 11 POS 18 is **covered at 2**, while the identical construction
would be halved in Cases 8, 9, 12, 13 and could be zeroed in Case 10. **Do not hard-code a
call-out rule. Extract 7.1.7(f)/7.1.8(d) per Case. — NEW, and it directly contradicts the
`field-findings.md` suggestion that "Vehicle costs" can be settled once and reused.**

**Invoice 2026-0017 — Tiling**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 21 | Skilled worker hours | **14** | hrs | **covered, but heavily quantity-suspect** | 7.1.5, 7.1.8(e) |
| 22 | Material costs | 1 | pcs | **covered** | 7.1.7(c) |
| 23 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |

14 hours of tiling labour to patch, re-level and retile roughly one square metre. `field-findings`
already logged "14 hrs for a simple leak detection" in Case 5 — **the number 14 recurs as the
generator's inflation marker.** Under 7.1.5 indemnity is confined to the ~1 m² actually affected.

### Case 11 adversarial constructions

1. **Duplicate drying equipment across one invoice** — POS 9/10/11 against 5/6. **NEW pattern:
   the same invoice bills the same measure twice under two different unit conventions
   ("flat rate" then "pcs").** The unit change is the disguise.
2. **Scale inflation** — "Room drying **50 m²**" for a ~1 m² loss.
3. **Quantity inflation on labour** — POS 21, 14 hrs; POS 2, 8 hrs.
4. **Quantity inflation on parts** — 10 identical 15 mm elbows for one compression fitting, split
   across two lines differing only by "model 01"/"model 02". **The "model NN" suffix appears to be
   pure line-splitting camouflage — NEW.** (Case 13 bills the same part without a model suffix.)
5. **Red herring** — "not an actual burst pipe" (2.4.1/2.4.2).
6. **Anti-trap** — POS 7/8 look duplicated and are expressly permitted (7.1.7(a)).
7. **Missing POS 12** — parser hazard. **NEW.**

### Case 11 price bands (EUR, gross)

Anchors: leak detection call-out €250–500; skilled trade €60–85/h; helper €40–55/h; service
technician €70–95/h; building dryer €40–80/day; Viega Profipress 15 mm elbow €5–12, 28 mm €12–25;
tile patch €60–120/m².

| POS | band | note |
| ---: | --- | --- |
| 1 | **250–500** | |
| 2 | 480–680 | 8 h × 60–85; inflation-suspect |
| 3 | 80–250 | |
| 4 | 40–90 | |
| 5 | **500–1,200** | expensive |
| 6 | 200–500 | |
| 7 | 30–80 | trivial |
| 8 | 40–120 | trivial |
| 9 | **0** | |
| 10 | **0** | |
| 11 | **0** | |
| 13 | 25–60 | trivial |
| 14 | 25–60 | trivial |
| 15 | 12–25 | trivial |
| 16 | 15–45 | trivial |
| 17 | 200–275 | |
| 18 | **80–180** | 2 × call-out, both covered here |
| 19 | 15–45 | trivial |
| 20 | 385–520 | |
| 21 | 200–450 | 14 h billed, ~1 m² payable |
| 22 | 50–200 | |
| 23 | 40–90 | |

Expensive: 1, 5, 20, 2. Zero: 9, 10, 11 (3 of 22).

---

## 5. Case 12 — washing-machine leak, floor + a high-value painting, 12 Line Items

`policy.txt`: **RESIDENTIAL DWELLING INSURANCE**, 1,190+ lines. **Buildings-only** — there is no
household-contents category in 4.1.

### Peril and template mapping

Escape of water — Cases 1 / 5 / 8 / 11 template. New trade: `01097 Palettetown`
(Fine Art Restoration). Building Services (Wrenchford) and Leak Detection (Puddleton) recur.

Repeats: **"Skilled worker hours"** (POS 8), **"Moisture measurement …"** (POS 5 — Case 1 POS 13,
Case 5 POS 2, Case 8 POS 34), **"Replace skirting boards"** (POS 4 — Case 1 POS 18, Case 8
POS 30). No `Vehicle costs` line in this Case at all — notable, since it appears in all 13 others.

### The Case-3 trap, inverted — **NEW**

The naive read is exactly Case 3's: buildings-only policy, painting is contents, `t = 0`. And
4.3(d) appears to confirm it:

> **4.3 Property not insured** "Not insured: … (d) **movable items of the household contents.
> Furnishings, personal effects, appliances that are not building accessories within the meaning
> of 4.2.3, and individual items of particular value - works of art, antiques, collection pieces
> and comparable items - fall under this heading.** **The head of cost under 5.2.6 remains
> unaffected.**"

That last sentence is the whole Case. 5.2.6 is a bespoke cost head that exists only in this
policy:

> **5.1** "The insurer reimburses the following costs … (f) **costs of securing and conserving
> individual items of particular value.**"

> **5.2.6 Securing and conserving individual items of particular value**
> "Where an individual movable item of particular value - **a work of art**, an antique, a
> collection piece or a comparable item - is affected by an insured event, the insurer reimburses
> the costs of securing and conserving that item: **its examination by a qualified specialist, its
> transport to and from that specialist, measures to dry, stabilise or otherwise arrest its
> deterioration, and its restoration.** **Reimbursement presupposes the specialist's assessment of
> the item.**
> Where the item was individually notified to the insurer before the insured event and is recorded
> in the schedule together with the value agreed for it, reimbursement is limited to that agreed
> value …
> **The limit applies once per affected item and covers all the measures named above taken in
> respect of that item together. It is not applied separately to each measure, to each contractor,
> to each invoice or to each invoice item.**"

The four restoration lines (POS 9–12) map one-to-one onto the four measures 5.2.6 names, and the
description supplies the precondition: "**It was assessed by a professional restorer**, dried and
stabilised, and then fully restored." **All four are covered.**

**This is the mirror image of Case 3.** Case 3 punished teams that priced an out-of-scope claim.
Case 12 punishes teams that learned that lesson too well and zero anything that smells like
contents under a buildings policy. **Rule: an exclusion that ends "the head of cost under X
remains unaffected" is a pointer, not an exclusion. Always follow the cross-reference before
returning `t = 0`.** (Case 09's 4.3(d)/(e) → 5.2.1/5.2.2 is the same construction.)

### Line Items, verdicts and clauses

**Invoice 2026-0135 — Building Services**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Cleaning of affected floor areas in the utility room and adjoining hallway | 1 | pcs | **covered** | 7.1.7(h) |
| 2 | Inspection of the washing machine and supply/drain connection to confirm no further leakage | 1 | pcs | **covered** | 7.1.7(e) |
| 3 | Removal and disposal of water-damaged skirting boards | 1 | pcs | **covered** | 7.1.7(a) |
| 4 | Replace skirting boards | 1 | pcs | **covered** | 4.2.2, 7.1.7(c) |

> **7.1.7(e)** "the investigation necessary to locate and identify the source of the damage,
> **including the examination of the installation, appliance or connection from which the medium
> escaped to the extent necessary to establish the source and to confirm that it no longer
> discharges, and this even where that installation or appliance is not itself insured
> property**"

POS 2 is a trap-pair with 4.3(d): the washing machine is *not insured property* (it is a movable
household item), yet inspecting it **is** indemnified, because 7.1.7(e) says so in terms. Same
structural pattern as Case 08 POS 4/POS 5. **NEW as a repeated construction: "the uninsured
object's inspection is insured".** Seen now in Cases 8 and 12.

> **7.1.7(h)** "**the cleaning of the surfaces and components affected by the insured event, where
> residues of the escaped medium have to be removed from them** before they can be repaired,
> reinstated or used again. Cleaning of surfaces, components, rooms or items that were not
> themselves affected is governed by 7.1.5."

> **4.2.2** "Also counting as building components are the fitting-out elements of the dwelling:
> **floor coverings together with their bedding, adhesive, underlay, insulating and levelling
> layers; wall and ceiling finishes; interior doors; and fixed trim, beading and comparable edging
> elements.**"

Skirting boards are "fixed trim … and comparable edging elements" ⇒ building components ⇒ insured.

**Invoice 2026-0136 — Leak Detection**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 5 | Moisture measurement of the utility room and hallway floor | 1 | pcs | **covered** | 7.1.7(b) |
| 6 | Drying of the affected floor area | 1 | pcs | **covered** | 7.1.7(b) |
| 7 | Drying unit rental | 1 | pcs | **covered** | 7.1.7(e) |
| 8 | Skilled worker hours | 4 | hrs | **covered** | 7.1.7(g) |

> **7.1.7(b)** "**the measurement of moisture**, and the drying, dehumidification and
> moisture-removal measures necessary before the repair can be carried out … **A drying measure
> may be charged for the room or space in which the affected components are situated, including
> its air volume, even where individual surfaces within that same room were not themselves wetted;
> it does not extend to other rooms.**"

**Anti-trap.** Under Case 11's 7.1.8(f) the pair POS 6 + POS 7 would collapse to one. **Case 12's
7.1.8 has no (f) sub-clause at all** — I read (a) through (e); the duplicate-equipment rule is
absent. So `Drying of the affected floor area` and `Drying unit rental` are **both covered**.
Two adjacent Cases, the same apparent construction, opposite verdicts, because the policies
differ. This is the strongest argument in the corpus against a global item-wording verdict cache.

**Invoice 2026-0137 — Fine Art Restoration**

| POS | Line Item | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 9 | Transport of the high-value painting to the specialist restorer | 1 | pcs | **covered** | 5.2.6 |
| 10 | Professional assessment of the high-value painting | 1 | pcs | **covered** | 5.2.6 |
| 11 | Conservatory drying and stabilisation of the painting | 1 | pcs | **covered** | 5.2.6 |
| 12 | Full restoration of the painting | 1 | pcs | **covered** | 5.2.6 |

All four are named by 5.2.6 in the order the invoice lists them. Caveat: if the painting were
individually scheduled, one aggregate cap would apply across POS 9–12 — the description does not
say it was, and no schedule ships with the Case, so I read the cap as not binding. **inferred.**

### Case 12 adversarial constructions

1. **Inverted Case-3 trap** — buildings-only policy + a work of art, rescued by 5.2.6. **NEW.**
2. **Uninsured appliance, insured inspection** — POS 2.
3. **Apparent duplicate that is not one** — POS 6/7 (no 7.1.8(f) here).
4. **No `Vehicle costs` line** — the one item present in all 13 other Cases is absent. If a
   pipeline injects or expects it, that is a fabrication risk.
5. **Aggregate per-item cost limit** — 5.2.6 final paragraph, latent.

Notably, Case 12 has **no** `t = 0` item that I can identify. It is the only Case in 08–13 where
every Line Item survives. **A gate that always finds something to exclude will be wrong here.**

### Case 12 price bands (EUR, gross)

Anchors: cleaning crew €40–60/h; skilled trade €60–85/h; building dryer €40–80/day; skirting
supply+fit €20–40/m; art restorer €60–120/h, condition report €250–600, full restoration of a
mid-value oil €1,500–6,000; specialist art transport €150–400.

| POS | band | note |
| ---: | --- | --- |
| 1 | 200–450 | |
| 2 | 80–200 | trivial but covered |
| 3 | 80–200 | trivial |
| 4 | 150–400 | |
| 5 | 120–300 | |
| 6 | **400–900** | |
| 7 | 200–500 | |
| 8 | 240–340 | |
| 9 | 150–400 | |
| 10 | **250–600** | |
| 11 | **500–1,500** | expensive |
| 12 | **1,500–6,000** | **largest `t` in the Case; wide posterior** |

---

## 6. Case 13 — failed copper heating pipe in the plant room, 1 trade, 17 Line Items

`policy.txt`: **RESIDENTIAL DWELLING INSURANCE**, standard boilerplate, 1,184+ lines.
Single invoice, single trade (Plumbing, Pipeville). The simplest Case of the six.

### Peril and template mapping

Escape of water — Cases 1 / 5 / 8 / 11 / 12 template. **Cases 11 and 13 share a plumbing parts
list.** Peril cover, verified:

> **2.4.2** "Escaping water means water that has emerged contrary to its intended purpose from:
> … **(c) heating or air-conditioning systems**"

> **2.4.3** "Covered inside buildings: (a) frost-related and **other fracture damage** to pipes of
> … **heating or air-conditioning systems** … This presupposes that the pipes concerned are **not
> a structural component of a boiler**, a water heater or a comparable installation."

The description says "The failed copper heating pipe **in the basement plant room**" — a pipe run,
not part of the boiler body. Covered on both limbs.

### The description hands you the answer

> "**The escaping water only ever affected the boiler/plant room itself; everything else on the
> list was general home maintenance the plumber folded onto the same invoice.**"

Then names the three: "repainting, ripping out and replacing the laminate floor in the adjacent
storage room (which was never touched by the leak), and servicing the outdoor garden tap."

### Line Items, verdicts and clauses

**Invoice 2026-0063 — Soggy Bottom Plumbing Ltd**

| POS | Line Item (verbatim) | qty | unit | verdict | clause |
| ---: | --- | ---: | --- | --- | --- |
| 1 | Profipress elbow 90° copper 15mm | 4 | pcs | **covered** | 7.1.7(c) |
| 2 | Profipress elbow 90° copper 28mm | 5 | pcs | **covered** | 7.1.7(c) |
| 3 | Profipress elbow 45° copper 28mm | 1 | pcs | **covered** | 7.1.7(c) |
| 4 | Grub screw | 8 | pcs | **covered** | 7.1.7(c), 7.1.8(e) 2nd sent. |
| 5 | Two-screw pipe clamp 25 mm | 4 | pcs | **covered** | 7.1.7(c) |
| 6 | Copper pipe 15x1 | 6.4 | m | **covered** | 7.1.7(c) |
| 7 | Service technician hours | 6.75 | hrs | **covered** | 7.1.7(g) |
| 8 | Helper hours | 5.75 | hrs | **covered** | 7.1.7(g) |
| 9 | Rock wool pipe insulation | 6 | pcs | **covered** | 7.1.7(c) |
| 10 | Binding wire | 2 | kg | **covered** | 7.1.7(c) |
| 11 | Small parts and consumables | 1 | pcs | **covered** | 7.1.8(e) 2nd sent. |
| 12 | Vehicle costs | 1 | pcs | **covered** | 7.1.7(f) |
| 13 | Construction waste disposal | 1 | pcs | **covered** | 5.2.1, 7.1.8(a) proviso |
| 14 | Repainting of basement hallway (outside boiler room) | 12 | m² | **not covered, `t = 0`** | 7.1.5 |
| 15 | Laminate flooring replacement – adjacent storage room (undamaged by leak) | 15 | m² | **not covered, `t = 0`** | 7.1.5 |
| 16 | Outdoor garden tap service | 1 | flat rate | **not covered, `t = 0`** | 7.1.5, 7.1.8(a) |
| 17 | Processing flat fee | 1 | pcs | **not covered, `t = 0`** | 7.1.8(b) |

> **7.1.5** "Work carried out in a room, on a surface, on a building component or on an item that
> was not itself affected is not covered. This applies even where the work is carried out …
> (c) at the same time as covered work, in the course of it, or as part of the same overall
> project; or **(d) by the same contractor as the covered work, and invoiced together with it.**"

7.1.5(d) is written for this Case: one contractor, one invoice, four unrelated jobs folded in.

> **7.1.7(c)** "materials of a type, quality, grade and specification corresponding to those in
> place immediately before the insured event, **including any bedding, adhesive, sealing, underlay,
> insulating or levelling layer that formed part of the component as installed before the loss**,
> together with the fixings, fastenings and consumable installation material used in carrying out
> the repair"

→ POS 9 rock wool insulation is expressly in (the description says the pipe was "re-insulated with
rock wool"). POS 4, 5, 10 are "fixings, fastenings and consumable installation material".

> **7.1.8(e)** "… **Minor fixings, fastenings and consumable installation material are assessed
> under 7.1.7(c) and are not excluded merely because they are invoiced as a lump sum or cannot be
> matched to the work item by item.**"

→ **POS 11 "Small parts and consumables" is an anti-trap.** It looks exactly like the kind of
unitemised catch-all a fraud gate should strike, and the policy pre-emptively protects it. This
sentence appears in Cases 8, 11, 12 and 13 — **treat "small parts / consumables / sundries" as
covered by default in escape-of-water Cases. NEW.**

> **7.1.8(b)** "… and **general administrative, handling or processing charges** levied in addition
> to itemised labour and materials"

→ POS 17 "Processing flat fee". Same family as Case 4 POS 14 and Case 8 POS 12.

### Case 13 adversarial constructions

1. **Unrelated maintenance folded onto the repair invoice** — POS 14, 15, 16. Three at once, all
   self-labelled. This is the cleanest single-vector Case in the corpus.
2. **Processing fee** — POS 17.
3. **Anti-trap** — POS 11 (7.1.8(e) second sentence).
4. **Mild quantity questions** — 9 elbows (POS 1+2) and 6.4 m of pipe to cut out and reconnect one
   section. Plausible for a plant-room re-pipe; I would not haircut this.

Note POS 14 and 15 carry *normal* `m²` quantities, not `– –`. **The `– –` rule is precision, not
recall.**

### Case 13 price bands (EUR, gross)

Anchors: Viega Profipress 15 mm elbow €5–12, 28 mm €12–25; copper pipe 15×1 €12–20/m; service
technician €70–95/h; helper €40–55/h; rock wool pipe shell €10–30 each; interior painting
€12–25/m²; laminate supply+lay €35–60/m²; skip €150–350.

| POS | band | note |
| ---: | --- | --- |
| 1 | 20–50 | trivial |
| 2 | 60–125 | trivial |
| 3 | 12–25 | trivial |
| 4 | 4–15 | trivial |
| 5 | 10–30 | trivial |
| 6 | 80–130 | |
| 7 | **470–640** | largest labour line |
| 8 | 230–320 | |
| 9 | 60–180 | |
| 10 | 10–30 | trivial |
| 11 | 30–100 | trivial but **covered** |
| 12 | 40–90 | |
| 13 | 80–250 | |
| 14 | **0** | list 144–300 |
| 15 | **0** | list 525–900 |
| 16 | **0** | list 80–200 |
| 17 | **0** | list 30–100 |

Expensive: 7, 8. Zero: 14, 15, 16, 17 (4 of 17).

---

## 7. Recurring Line Item templates across all 14 Cases

Key a Price Memory on **(normalised wording, peril family, trade)**. The trade is recoverable from
the invoice's fictional address, which is stable across Cases.

### Trade roster (stable identity keys — **NEW**)

| address | trade | Cases |
| --- | --- | --- |
| 23 Fixit Boulevard, 70173 Wrenchford | Building Services (Handy Hans All-Trades) | 1, 2, 4, 7, 8, 11, 12 |
| 7 U-Bend Boulevard, 23456 Pipeville | Plumbing (Soggy Bottom) | 1, 5, 8, 11, 13 |
| 4 Trickle Terrace, 12345 Puddleton | Leak Detection | 1, 5, 11, 12 |
| 3 Dehumidifier Drive, 45127 Damptown | Drying Technology (Blow-Dry Bros) | 1, 5, 8, 11 |
| 128 Circuit Crescent, 10178 Techtonic | Electronics | 2, 4, 6 |
| 11 Sawdust Street, 33098 Planktown | Carpentry (Splinter & Sons) | 5, 9 |
| 8 Mosaic Mews, 60594 Tilebury | Tiling | 0, 11 |
| 88 Cheque Chase Road, 20095 Refundton | Compensation Payment | 3, 10 |
| 16 Laminate Lane, 04109 Parquetville | Flooring (Underfoot & Overcharge) | 8 |
| 9 Rubble Rise, 40210 Crushington | Dismantling (Smash & Grab) | 8 |
| 10119 Wordsworth | Translation Services | 10 |
| 01097 Palettetown | Fine Art Restoration | 12 |
| 34117 Binbrook | Recycling Service | 9 |
| 79098 Barksdale | Tree Service | 9 |

### Tier 1 — appears in 4+ Cases

| template | Cases | typical verdict | band |
| --- | --- | --- | --- |
| **Vehicle costs** | **1, 2, 3, 4, 5, 8, 9, 11, 13** (and Case 7/12 absent) | covered — **but conditional; see the call-out rule table** | 40–120 per unit |
| **Skilled worker hours** | 1, 8, 11 (×2) | covered | 60–90 €/h |
| **Service technician hours** | 5, 11, 13 | covered | 70–95 €/h |
| **Moisture measurement …** | 1, 5, 8, 12 | covered (7.1.7(b)) | 120–350 |
| **Material costs / Material for the work** | 1, 10, 11 | covered in trade Cases; **`t = 0` when ancillary to an excluded line (Case 10)** | 50–250 |
| **Construction waste disposal** | 8 (×2), 13 | covered **once per insured event** | 80–450 |

### Tier 2 — 2–3 Cases, exact wording

| template | Cases | verdict |
| --- | --- | --- |
| **Vehicle costs – return visit** | 4, 8, 9 | **`t = 0`** in all three, always with `– –` |
| **Catering for work crew** | 8, 9 | **`t = 0`** (7.1.8(b)) |
| **Administrative and claim-processing fee** / **Processing flat fee** | 4, 8, 13 | **`t = 0`** (7.1.8(b)) |
| **Shipping** / **Freight shipping** | 2, 4, 7, 10 | `t = 0` under Case 10's 7.1.8(b); check per Case |
| **Installation** | 2, 4, 7 (×2) | covered in surge Cases; `t = 0` under Case 10's 7.1.8(c) |
| **Drying fan** | 1, 8, 11 | covered (1, 8); **`t = 0` in 11** via 7.1.8(f) |
| **Condensation dryer** | 1, 8 | covered |
| **Room dryer unit** | 11 (×2) | first covered, second `t = 0` |
| **Room drying …** | 1, 11 (×2) | first covered, second `t = 0` |
| **Leak detection …** | 1, 5, 8, 11 | covered (7.1.7(e)) |
| **Helper hours** | 11, 13 | covered, 40–55 €/h |
| **Profipress elbow 45° copper 28mm** | 11, 13 | covered, 1 pcs both times, 12–25 |
| **Profipress elbow 90° copper 15mm** | 11 (10 pcs), 13 (4 pcs) | covered; 11's quantity is inflated |
| **Final site cleaning** / **Cleaning of the installation area** | 1, 5, 8 | covered |
| **Replace / Supply and install skirting boards** | 1, 8, 12 | covered (betterment-capped in Case 1) |
| **Removal and disposal of …** | 5, 8, 11, 12 | covered (7.1.7(a)/(h)) |
| **Speaker system (surge damaged)** | 2, 4, 6 | covered |
| **TV set (surge damaged)** | 2, 4, 6 | covered |
| **Diagnostic … surge-failure report** | 4, 6 | covered; quantity inflated in both (2 pcs, 3 pcs) |

### Peril families across 14 Cases

| peril family | Cases | count |
| --- | --- | ---: |
| escape of water (indoor) | 1, 5, 8, 11, 12, 13 | **6** |
| storm surge → home electronics | 2, 4, 6, 7 | **4** |
| theft / robbery | 0, 3, 10 | **3** |
| storm → structural / tree | **9** | **1 (new family)** |

Escape of water has overtaken storm-surge as the dominant family. Cases 11 and 13 are the most
mutually predictive pair in the corpus.

---

## 8. Adversarial vector taxonomy, with counts over Cases 00–13

| # | vector | Cases | count | status |
| ---: | --- | --- | ---: | --- |
| V1 | **Item names its own disqualifier** in parentheses | 1, 4, 5, 8, 9, 10, 13 | **7 / 14** | known |
| V2 | **Preventive / unrelated / upkeep work** billed alongside the repair | 1, 4, 8, 9, 13 | **5 / 14** | known |
| V3 | **Quantity inflation** (implausible qty for the job) | 4, 5, 6, 8, 9, 11 | **6 / 14** | known |
| V4 | **Betterment / upgrade** (7.1.9 haircut) | 1, 5, 8, 9, 10 | **5 / 14** | known |
| V5 | **Duplicate charge** across trades or lines | 4, 8, 9, 11 | **4 / 14** | known |
| V6 | **Admin / claim-processing fee** | 4, 8, 13 | **3 / 14** | known |
| V7 | **Red herring** — suspicious detail that does *not* remove cover | 7, 8, 9, 11, 12 | **5 / 14** | **4 NEW** |
| V8 | **`– –` quantity/unit as a `t = 0` marker** | 1, 4, 8, 9, 10 | **5 / 14, 16 items, 16/16 zero** | **NEW as a rule** |
| V9 | **Contractor's own tools / catering / provisioning** | 8, 9 | **2 / 14** | **NEW** |
| V10 | **Sub-limit aggregation across several Line Items** | 8 (billiard), 10 (valuables + cash), 12 (art, latent) | **3 / 14** | **NEW** |
| V11 | **Anti-trap** — a line that *looks* excluded and is expressly covered | 8, 9, 11, 12, 13 | **5 / 14** | **NEW** |
| V12 | **Return-visit / second call-out** | 4, 8, 9 | **3 / 14** | known-ish |
| V13 | **Combined-position all-or-nothing** (7.1.10) | 9 | **1 / 14** | **NEW** |
| V14 | **Separately metered utility consumption** | 8 | **1 / 14** | **NEW** |
| V15 | **Necessary-but-excluded claim-preparation cost** (translation of a mandatory police report) | 10 | **1 / 14** | **NEW** |
| V16 | **Ancillary line inherits the parent line's verdict** | 10 | **1 / 14** | **NEW** |
| V17 | **Non-contiguous POS numbering** (POS 12 missing) | 11 | **1 / 14** | **NEW — parser hazard** |
| V18 | **Line-splitting camouflage** ("model 01" / "model 02") | 11 | **1 / 14** | **NEW** |
| V19 | **Mostly- or wholly-uncovered Case** | 3 (2/2), 10 (4/6), 9 (7/16) | **3 / 14** | known |
| V20 | **Zero-exclusion Case** — every line covered | 12 (0/12) | **1 / 14** | **NEW** |
| V21 | **`PART 11` operative-provisions answer key** | 10 | **1 / 14** | **NEW** |
| V22 | **Description cites a non-existent endorsement** (GR-2026) | 9 | **1 / 14** | **NEW** |

`t = 0` density in Cases 08–13: **8: 7/39 · 9: 7/16 · 10: 4/6 · 11: 3/22 · 12: 0/12 · 13: 4/17**
→ **25 of 112 Line Items (22 %)**, but ranging from 0 % to 67 % per Case. There is no safe prior.

---

## 9. Rules that generalise

### Deterministic checks — implementable without a model

| # | rule | basis |
| ---: | --- | --- |
| D1 | `quantity == "–" and unit == "–"` ⇒ `p(covered) ≈ 0` ⇒ `b = 0`, `a` high | 16/16 across Cases 1, 4, 8, 9, 10 — **inferred from correlation** |
| D2 | Parse the **POS column as data**. Never derive the submission index from row ordinal. Reconcile the parsed row count against the API's line item count and fail loudly on mismatch. | Case 11 POS 12 missing — **verified** |
| D3 | If two Line Items in one Case have **the same normalised wording**, flag the second and later ones as duplicate candidates. | Case 8 POS 17/32, Case 11 POS 5/9 and 6/10 — **verified** |
| D4 | If a Line Item's wording contains a **parenthetical**, extract it and evaluate it separately — it is the disqualifier or the qualifier ~100 % of the time. | V1, plus Case 9 POS 1/14 qualifiers — **verified** |
| D5 | `grep "^PART 11"` / "OPERATIVE PROVISIONS FOR THIS CLAIM" on every new policy. If present, restrict clause retrieval to the enumerated list. | Case 10 §11.4 — **verified** |
| D6 | Extract **7.1.7(f)** and **7.1.8(d)** verbatim **per Case** before deciding any `Vehicle costs` / call-out line. Do not cache the verdict. | five different formulations across Cases 8–13 — **verified** |
| D7 | Cross-check a **renewal** line's quantity and unit against the corresponding **removal** line. A mismatch triggers 7.1.8(e). | Case 8 POS 28 (`5 m²`) vs POS 29 (`12 m`) — **verified** |
| D8 | When an exclusion clause ends "**the head of cost under X remains unaffected**" or "**X is unaffected by this**", follow the cross-reference before returning `t = 0`. | Case 12 §4.3(d)→5.2.6; Case 9 §4.3(d)/(e)→5.2.1/5.2.2 — **verified** |

### Prompt instructions for the reading agent

| # | instruction | basis |
| ---: | --- | --- |
| P1 | "An item's **inspection** can be covered even when the **item** is not. Quote 7.1.7(e)/(i) before zeroing an inspection line." | Case 8 POS 4/5, Case 12 POS 2 — **verified** |
| P2 | "Distinguish a **mixed grade** (7.1.9 ⇒ partial haircut) from a **mixed scope in one undifferentiated line** (7.1.10 ⇒ total zero). Check whether the policy contains a 'Combined positions' clause." | Case 9 §7.1.10 vs §7.1.9 — **verified** |
| P3 | "Some products are excluded **outright and cannot be rescued by the betterment haircut**. Look for a sentence of the form 'Products falling under X are not indemnified at all and are not brought back into cover by this provision.'" | Case 9 §7.1.9 last sentence — **verified** |
| P4 | "'Ordinary equipment of the trade' is excluded; **plant brought in specially** is covered. Read the 1.3 definition; do not key on the words 'equipment' or 'hire'." | Case 9 §1.3, §7.1.7(e), §7.1.8(b) — **verified** |
| P5 | "'Small parts and consumables' / lump-sum fixings are **protected** by an express sentence in 7.1.8(e). Do not strike them as unitemised." | Cases 8, 11, 12, 13 — **verified** |
| P6 | "A repeated measurement or a multi-stage drying charge is **not** duplication where the policy says stages are separate items of cost. Quote 7.1.8(c) before haircutting a `2 pcs` measurement line." | Case 8 §7.1.8(c) 2nd sentence vs Case 11 §7.1.8(f) — **verified** |
| P7 | "An ancillary line (`Material costs`, `Shipping`, `Vehicle costs`) **inherits the verdict of the line it accompanies**. If every substantive line on an invoice is `t = 0`, so is the ancillary." | Case 10 §7.1.8(d), (f) — **verified** |
| P8 | "**Necessity does not imply cover.** A cost that is a precondition of the claim can still be expressly non-indemnifiable." | Case 10 §2.3.3 + §3.1.6 — **verified** |
| P9 | "Before concluding a whole Case is out of scope, search the policy for a **bespoke cost head** that restores it (a Part 5 head naming the excluded property type)." | Case 12 §5.2.6 — **verified** |
| P10 | "Where a sub-limit clause says the amount is applied **once to the aggregate** of all lines relating to one item, mark every one of those lines as sub-limit-bound and deflate the per-line estimate." | Case 8 §4.8.3, Case 12 §5.2.6 — **verified** |
| P11 | "A **red herring** is a suspicious fact in `description.txt` that the policy expressly neutralises. Before excluding on a description fact, search the policy for a clause that names that fact. Five of fourteen Cases plant one." | Cases 7, 8, 9, 11, 12 — **verified** |
| P12 | "The description sometimes names an **endorsement that is not in the policy**. Its absence is not a coverage failure — check whether the base wording achieves the same result." | Case 9, GR-2026, zero grep hits — **verified** |

### Corrections to `field-findings.md`

1. **"'Vehicle costs' … worth pinning down once."** — **Wrong.** The call-out rule takes five
   different forms across Cases 8–13, from "each attendance" (11, uncapped) to "one per contractor
   per invoice" (8, 12, 13) to "zero if nothing else on the invoice is indemnifiable" (10). The
   *price* of a call-out is stable (€40–120); the *count indemnified* is not.
2. **"Betterment is a partial haircut, not a binary."** — **True for 7.1.9, false where a
   'Combined positions' clause exists.** Case 9 §7.1.10 converts a mixed-scope line to a hard zero
   and says so expressly. And Case 9 §7.1.9 last sentence carves an outright exclusion out of the
   haircut.
3. **"Read the policy's scope clause first."** — Necessary but insufficient. Case 12's scope clause
   (4.1, buildings only) plus its exclusion (4.3(d), works of art) points to `t = 0` on four items
   that a Part 5 cost head fully restores. **The scope clause is the first step, not the answer.**
4. **The 14-hour marker.** `field-findings.md` logged "14 hrs for a simple leak detection" in
   Case 5. Case 11 POS 21 bills **14 hrs** of tiling for ~1 m². The literal number 14 has now
   appeared twice as an inflation marker.

---

## 10. What I could not determine

- **All sub-limit and cap amounts.** Every policy defers them to a "Schedule" that does not ship
  with the Case. Cases 9, 10, 11, 12, 13 additionally contain literal unfilled placeholders
  (`[volume]`, `[number]`, `[amount]`, `[list to be inserted]`). So Case 8's billiard cluster,
  Case 10's watch and cash, and Case 12's painting all have a known-but-unquantified ceiling.
  Widen the posterior on those items rather than picking a point.
- **Whether the API exposes 22 or 23 Line Items for Case 11.** Read-only; the parent agent should
  check the live endpoint.
- **Case 08 POS 2 (LED lighting).** Named by both 7.1.9 (betterment) and 4.8.2 ("not payable in
  addition to it"). I lean `t = 0` but cannot resolve it from the text alone.
- **Case 08 POS 5's enlargement question (7.1.11).** The clause is a burden-of-proof test. "The
  family were away" appears to discharge it, but the clause is drafted to be arguable. Only the
  self-damage exclusion is unambiguous.
- **`photo.jpg`.** Present in Cases 8, 9, 11, 12, 13; absent in Case 10. Not inspected — image
  analysis was out of scope for this pass. Case 8's is 3.6 MB and Case 9's 5.5 MB; if the loss
  investigation "by photographic record" (7.1.5) matters anywhere, it matters in Case 8 for
  establishing which rooms were affected.

---

*No repo file was modified. All extraction was read-only via `pdftotext -layout` and `sed`/`grep`.*
