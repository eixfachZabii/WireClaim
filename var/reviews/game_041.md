<!-- scripts/review_game.py · model sonnet · 2026-08-22T21:28:04Z -->

### Review — Game 41

- **what happened**: Item 3 (robbery compensation) cost 81,672.72 in wrongful-rejection penalties, turning a 61,321.23-income Game into a −20,423.49 net.
- **stage**: charge-far-below-t — charged 3,826.35 against reconstructed `t ≥ 11,130.90`; even the pre-Charge-factor estimate median (5,523.66) sat under half of `t_lo`.
- **case evidence**: "this watch is specifically declared on a Valuables Schedule with a current valuation certificate, at a value well above the standard per-item jewellery limit" (description.txt) — an explicit textual signal that this item's value exceeds normal ranges, which the evidence channels (B:memory, C:model) failed to translate into a high enough price band before the 0.7 Charge factor compressed it further.
- **verdict**: signal — this is exactly the "censored sample" risk CLAUDE.md already flags (items with no `t_hi`, i.e. never rightfully rejected, are plausibly the expensive ones); one Game doesn't clear 26,622 alone, but it matches a standing concern rather than adding a new one.
- **candidate**: across all settled Games, do items whose description/policy text contains an explicit high-value cue ("above the standard limit", "valuation certificate", etc.) show a larger median `charge/t` shortfall than items without such cues?
