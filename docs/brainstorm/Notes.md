### Aufgaben:

- .zip holen + extraction (jonas)
- devin api (mathi)
- policy violation detection per line item--> b=0 und a=t (markus)
- t value guess (condifenz interval) (lukas)
- given t value guess, error margin and PV (policy violation boolean) calculate a and b per lineitem
- post to api (markus)
- strategie optimization (sebi)

### Gedanken aus Beschreibung:

- b darf nie unter t sein // das führt zu falsche ablehnung
- a darf nie über t sein // dann können andere uns rechtmäßif ablehnen ABER kosten hier nur opportunity cost da bei ablehnung einfach kein geld fliest.
- 1,5a >= b //da bei Überschreitung 1,5a gezahlt wird würde sich keine Akzeptanz über kosten bei Verweigerung lohnen - ja letzteres a ist vom anderen Team aber alle haben das gleiche t
- (offensichtlich) a = b = t ist optimal

- für sinnvolle risikobewertung macht es sinn beträge mit Kontostand zu vergleichen
