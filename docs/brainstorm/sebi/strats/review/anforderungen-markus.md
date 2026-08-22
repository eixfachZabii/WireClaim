# Was ich von deinem Detector brauche

**Kurz: Ich brauche pro Line Item eine Zahl zwischen 0 und 1 — die Wahrscheinlichkeit, dass
die Police diese Position bezahlt — plus die Klausel, die das belegt. Kein `0` / `1`.**

## Warum keine 0/1

Du wolltest mir pro Item `0` oder `1` geben, Fraud oder kein Fraud. Das funktioniert, ich
baue einen Fallback dafür (siehe unten), aber es kostet uns Geld, und zwar messbar.

Der Grund ist der Grenzwert `2/3`. Aus der Auszahlungstabelle folgt: eine Rechnung
annehmen kostet `a`. Sie ablehnen kostet `1,5 · a`, **aber nur wenn sie berechtigt war** —
sonst nichts. Annehmen lohnt sich also genau dann, wenn

```
P(Position ist gedeckt und der Preis ist fair)  >  2/3
```

Unser Limit `b` ist deshalb das **untere Drittel** unserer Preisverteilung. Wenn du mir
eine Wahrscheinlichkeit gibst, rechne ich sie als Wahrscheinlichkeitsmasse bei Null in
diese Verteilung ein, und unterhalb von `2/3` fällt das Limit **von allein auf 0**. Ohne
Sonderfall, ohne Schwellwert im Code.

Mit `0` / `1` verliere ich genau die Mitte — und die Mitte ist der einzige Bereich, in dem
diese Entscheidung überhaupt getroffen wird. Ein `1` bei einem Item, bei dem du dir zu 60 %
sicher bist, sagt mir "voll bezahlen", und das ist falsch.

**Was das kostet:** Spiel 17 hat `70.736` an angenommenen Rechnungen bezahlt, netto
`−63.789`, während die Führenden mit demselben Case `+18.577` und `+24.141` gemacht haben.
Die Ursache war genau dieser Informationsverlust: ein Bug hat jede Deckungs­wahrscheinlichkeit
auf mindestens `0,9` hochgezogen, das Limit konnte nie zusammenfallen, und wir haben auf den
**40 % der Positionen, die nichts wert sind**, voll gezahlt.

---

## Erst die Begriffe, sonst reden wir aneinander vorbei

Das ist wichtig, weil "Fraud" hier zwei verschiedene Dinge bedeuten kann:

| Begriff | Bedeutung | Wer entscheidet |
| --- | --- | --- |
| **Deckung** | Zahlt die Police für diese Position überhaupt? Wenn nein, ist der Fair Value `t = 0`. | **Du** |
| **Fraud / Überhöhung** | Ist der *Preis* `a` höher als `t`? | **Ich** (Preis-Engine) |

**`p_covered` ist NICHT die Fraud-Wahrscheinlichkeit.** Es ist die Wahrscheinlichkeit, dass
die Position **überhaupt erstattungsfähig** ist, also dass `t > 0`. Ob ein Preis überhöht
ist, ist eine reine Preisfrage und macht meine Seite.

Anders gesagt: du bist streng genommen kein Fraud-Detector, sondern ein **Deckungs-Prüfer**.
Das ist die wertvollere Aufgabe: **76 von 192** abgerechneten Positionen haben `t = 0`. Jede
davon, die du erkennst, spart uns direkt Geld, weil unser Limit dann auf 0 geht — und wir
trotzdem weiter Geld verlangen dürfen (dazu unten).

---

# Wie — im Detail

## 1. Das Format

Pro Line Item:

```json
{
  "index": 7,
  "p_covered": 0.15,
  "clause": "3.1.6 The insurer does not indemnify the cost of translating into or out of any language, however necessary those steps may be for the claim to be assessed.",
  "reasoning": "Position ist eine Übersetzung des Polizeiberichts."
}
```

- **`index`** ist die **gedruckte POS.-Nummer auf der Rechnung**, nicht die Zeilennummer.
  Das ist wichtig: Case 11 hat keine POS 12, und das Turnier hat für dieses Spiel auch keinen
  Index 12. Niemals durchnummerieren.
- **`p_covered`**: `0.0` = sicher nicht gedeckt, `1.0` = sicher gedeckt. Wenn du nichts
  gefunden hast, gib **`0.9`** (Deckung ist der Normalfall), nicht `0.5`.
- **`clause`**: die Klausel **wortwörtlich** aus `policy.txt`, mindestens 60 Zeichen.
  Ohne Zitat kein Urteil. Ich prüfe im Code, dass der Text zeichengenau in der Police
  vorkommt und Ausschluss-Sprache enthält (`not covered`, `excluded`, `does not cover`, …).
  Es gibt schon eine fertige Funktion dafür: `src/policy_quote.py -> is_policy_quote()`.
  **Bitte benutz die, nicht selbst nachbauen** — sie stand schon zweimal im Code und die
  beiden Kopien sind auseinandergelaufen.

## 2. Falls du bei 0/1 bleiben willst

Kein Problem, dann mappe ich so:

| dein Wert | wird bei mir zu |
| --- | --- |
| `1` (gedeckt) | `p_covered = 0.9` |
| `0` (nicht gedeckt) **mit** gültigem Zitat | `p_covered = 0.0` → Limit 0 |
| `0` **ohne** gültiges Zitat | wird verworfen, `p_covered = 0.9` |

Das funktioniert. Es ist nur schlechter, weil jedes Item entweder "voll bezahlen" oder
"gar nichts" wird und es kein Dazwischen gibt. **Wenn du einen Confidence-Wert vom Modell
sowieso schon hast, gib ihn mir einfach durch** — dann ist es dieselbe Arbeit für dich und
deutlich besser für uns.

## 3. Zwei Dinge, die dein Detector nicht anfassen darf

- **Er darf `a` (unseren Preis) nie auf 0 setzen.** Eine ungedeckte Position hat `t = 0`,
  also kostet eine abgelehnte Forderung uns **nichts** — Geld verlangen ist gratis. Beweis
  aus Spiel 3: dort war *jede* Position ungedeckt, zwei Teams haben trotzdem ~100 verlangt
  und von 2 der 16 Gegner bezahlt bekommen, der ganze Rest hat 0 gemacht. Also: bei
  „nicht gedeckt" → **Limit 0, Preis bleibt plausibel** (nicht extrem hoch — es kaufen nur
  Teams, die die Position falsch als gedeckt eingestuft haben, und deren Limit passt zu
  einem realistischen Preis).
- **Er darf die Abgabe nie blockieren.** Läuft parallel, ein spätes Ergebnis überschreibt
  per `PUT`. Wir haben in Spiel 10–12 zusammen `139.904` verloren, weil gar nichts
  abgeschickt wurde. Lieber ein ungeprüftes Ergebnis als keins.

## 4. Der wichtigste Trick: beurteile die *Leistung*, nicht den *Gegenstand*

Du hattest gefragt, wie man Fälle wie Case 8 POS 4 überhaupt erkennt. Genau hier:

> Der Staubsaugerroboter selbst ist **nicht** versichert (`t = 0`). Abgerechnet wird aber
> nicht der Roboter, sondern **seine Untersuchung** — und §7.1.7(i) erstattet die
> ausdrücklich, *"even where the property investigated turns out not to be indemnified"*.

Die Regel dahinter: **die Position ist die abgerechnete Leistung, nicht das Objekt, um das
es geht.** Untersuchung, Leckortung, Trocknung, Gutachten werden oft auch dann erstattet,
wenn der untersuchte Gegenstand selbst nicht versichert ist. Case 12 POS 2 ist dasselbe
Muster mit der Waschmaschine (§7.1.7(e)).

**Zweiter Trick — Querverweise zu Ende lesen.** Endet ein Ausschluss mit einem Satz wie
*"The head of cost under 5.2.6 remains unaffected"*, dann ist das **kein Ausschluss, sondern
ein Verweis**. Case 12 schließt Kunstgegenstände aus und erstattet über §5.2.6 genau deren
Restaurierung. Praktisch: **bevor du „nicht gedeckt" sagst, suche die genannte
Klausel­nummer in der Police und lies, ob sie die Deckung wiederherstellt.**

Falls du Kontext sparen willst: 6 der 14 Policen haben einen Abschnitt
**`PART 11 – LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM`**, der die
entscheidenden Klauseln für genau diesen Fall aufzählt — praktisch eine Lösungsskizze.
`src/policy_slice.py` schneidet die Police deterministisch auf die relevanten Teile
(PART 3, 4, 5, 7, 11) herunter, etwa die Hälfte des Textes, ohne LLM-Aufruf.

## 5. Ein geschenktes Signal, das du sofort mitnehmen kannst

Steht in der Rechnung bei Menge und Einheit nur ein Strich (`– –`), ist die Position
**mit Sicherheit nichts wert**: **20 von 20** solchen Positionen in den abgerechneten
Spielen hatten `t = 0`, gegen eine Grundrate von 33 %. Der Parser markiert das jetzt als
`quantity_missing: true`, und das Feld steht schon in dem JSON, das dein Prompt bekommt.
Nimm es als starkes Indiz — aber zitiere trotzdem die Klausel.

## 6. Woran du dich selbst messen kannst

Das ist der beste Teil: **wir haben die Wahrheit.** `scripts/invert_fair_values.py` rechnet
aus den abgerechneten Spielen den echten Fair Value jeder Position zurück (exakt, kein
Modell — eine abgelehnte Transaktion mit Betrag > 0 beweist `a ≤ t`, eine mit Betrag 0
beweist `a > t`). Damit kennst du für **192 Positionen** die richtige Antwort.

```bash
python scripts/invert_fair_values.py --games 1-14 --verify
```

Deine Zielgröße: bei welchem Anteil der Positionen mit `t = 0` liegst du richtig, und wie
viele gedeckte Positionen stufst du fälschlich als ungedeckt ein? Der zweite Fehler ist
teurer, als es aussieht: er kostet uns den garantierten Umsatz **und** macht uns zum
Zahlmeister.

**Und die wichtigste Warnung dazu:** es gibt **keinen sicheren Grundwert**. Der Anteil
ungedeckter Positionen schwankt pro Case zwischen **0 % und 67 %** — Case 12 hat **null**
ungedeckte Positionen, Case 10 hat 4 von 6. Ein Detector, der immer irgendetwas findet,
liegt bei Case 12 komplett falsch. Kalibriere pro Case, nicht global.

---

## Zusammenfassung

1. `p_covered` als Zahl von 0 bis 1, nicht `0`/`1`. Wenn nichts gefunden: `0.9`.
2. Immer die Klausel **wortwörtlich** mitgeben, mindestens 60 Zeichen, geprüft mit
   `src/policy_quote.py`.
3. `index` = gedruckte POS.-Nummer, Lücken behalten.
4. Nie `a` auf 0 setzen, nie die Abgabe blockieren.
5. Die **Leistung** beurteilen, nicht den Gegenstand. Querverweise zu Ende lesen.
6. `– –` bei der Menge ⇒ mit hoher Sicherheit `t = 0`.
7. Gegen `scripts/invert_fair_values.py` selbst messen, pro Case kalibrieren.

Details zur Preis-Seite: [`strategy2-plan.md`](strategy2-plan.md). Zahlen und Verluste:
[`report.md`](report.md).
