# SqlGui2 – Übersicht aller Rechtsklick-Menüs

Stand: 2026-05-27  
Patch: `patch_rechtsklick_verknuepft.py` (commit b0c6e49)

---

## Vollständiges Standard-Menü (`standard_tv_rechtsklick_anbinden`)

Das Standard-Menü ist überall aktiv, wo `standard_tv_rechtsklick_anbinden(...)` aufgerufen wird (Zeilen mit `⬇` unten). Klick auf **Spaltenheader** zeigt nur Block 0; Klick auf **Datenzeilen** zeigt alle Blöcke.

| Block | Eintrag | Notizen |
|-------|---------|---------|
| 0 (Heading) | Kopf + Daten optimal | nur bei Klick auf Spaltenheader |
| 0 (Heading) | Daten optimal | |
| 0 (Heading) | Spaltennamen optimal | |
| 0 (Heading) | Alle Spaltennamen vollständig | |
| **1 – Kopieren** | Feldinhalt kopieren | |
| | Zeile kopieren | |
| | Zeile als CSV kopieren | |
| | Header als CSV kopieren | |
| | Tabelle als CSV kopieren | |
| **2 – Anzeigen** | Feldinhalt im Lesefenster | |
| | Zeile im Lesefenster | |
| | Kopf + Daten optimal | |
| | Daten optimal | |
| | Spaltennamen optimal | |
| | Alle Spaltennamen vollständig | |
| **3 – Filtern** | Feldfilter setzen | |
| | Feldfilter aufheben | |
| | Eindeutige Feldwerte anzeigen | |
| **4 – IP/Netz** | IP-Range aufteilen | |
| | IP / Netz vollständig analysieren | |
| | Überschneidungen in Spalte suchen | |
| | Überschneidungen in Kette suchen | |
| **4.5 – Verknüpft** | **Verknüpfte Datensätze anzeigen** ✨ | öffnet Ketten-Fenster aus zzz_Relationen |
| **5 – Finding** | Finding aufrufen | |
| | Finding hinzufügen | |
| **6 – Bearbeiten** | Zeile löschen | nur wenn `db_edit=True` |
| | Feld editieren | nur wenn `db_edit=True` |

---

## Wo das Standard-Menü verwendet wird

| Fenster / Widget | Tabelle | db_edit | Zeile in Code |
|-----------------|---------|---------|---------------|
| **Haupt-Tabellenfenster** (alle Daten-TVs) | Tabellenname aus DB | ✅ Ja | L4033 |
| **Überschneidungen in Spalte** – Ergebnisliste | Quelltabelle | ❌ Nein | L1998 ✨ |
| **Überschneidungen in Kette** – Gruppenübersicht (oben) | Quelltabelle | ❌ Nein | L2754 ✨ |
| **Überschneidungen in Kette** – Detailansicht (unten) | Quelltabelle | ❌ Nein | L2792 ✨ |
| **Ketten-Fenster** (Workflow) – Quelltabelle-TV | Quelltabelle | ✅ Ja | L4504 |
| **Ketten-Fenster** (Workflow) – Zieltabelle-TV | Zieltabelle | ✅ Ja | L4504 |
| **SQL-Abfragefenster** – Ergebnistabelle | Abfragename | ❌ Nein | L4613 |
| **SQL-Editor** – Tabellen-Baum | "Tabellen" | ❌ Nein | L10273 |
| **SQL-Editor** – Felder-Baum | "Felder" | ❌ Nein | L10275 |
| **SQL-Editor** – Funktionen-Baum | "Funktionen" | ❌ Nein | L10277 |

✨ = In diesem Patch auf Standard-Menü umgestellt (vorher nur Spaltenbreiten)

---

## Sondermenüs (kontextspezifisch, kein Standard-Menü)

Diese Menüs haben bewusst weniger Einträge, weil der Kontext es erfordert.

### Eindeutige-Werte-Popup (L1460 + L9577)
Öffnet sich, wenn man „Eindeutige Feldwerte anzeigen" aufruft.

| Eintrag | Funktion |
|---------|----------|
| Wert kopieren | Ausgewählten Wert in Zwischenablage |
| *(Trenner)* | |
| Als Filter anwenden | Filtert Haupttabelle auf diesen Wert |

### SQL-Abfragefenster – Ergebnistabelle `ergebnis_rechtsklick` (L9999)
Eigene Implementierung mit ähnlichem Umfang wie Standard-Menü, aber ohne „Verknüpfte Datensätze".

| Block | Eintrag |
|-------|---------|
| Kopieren | Feldinhalt, Zeile, Zeile CSV, Header CSV, Tabelle CSV |
| Anzeigen | Lesefenster, Spaltenbreiten |
| Filtern | Feldfilter setzen/aufheben, Eindeutige Werte |
| IP/Netz | Integer↔IPv4, IP-Range, Netzwerk |
| Finding | Finding hinzufügen |

### Workflow-Verwaltung `workflow_rechtsklick` (L7067)
Nur im Workflow-Editor (keine Datenzeilen).

| Eintrag |
|---------|
| Tabelle hinzufügen |
| SQL-Abfrage hinzufügen |
| ⛓ Kette hinzufügen |
| Eintrag entfernen |
| ↑ Hoch / ↓ Runter |

### Beziehungs-Verwaltung `_rel_tree_rechtsklick` (L8370)
Nur in Projekteinstellungen → Beziehungen.

| Eintrag |
|---------|
| Einfache Beziehung hinzufügen |
| Kettenbeziehung hinzufügen |
| ▲ Nach oben / ▼ Nach unten |
| Beziehung bearbeiten |
| Beziehung löschen |

### Projekt-Verwaltung `projekt_rechtsklick` (L8437)

| Eintrag |
|---------|
| Neu |
| Löschen |

### SQL-Abfragen-Verwaltung `abfrage_rechtsklick` (L10190)

| Eintrag |
|---------|
| Neu |
| Löschen |

### SQL-Editor Textfeld `editor_rechtsklick` (L10281)

| Eintrag |
|---------|
| Ausschneiden |
| Kopieren |
| Einfügen |
| Alles markieren |
| *(Snippets-Untermenü)* |

---

## Verknüpfte Datensätze anzeigen – Logik

1. Lookup in `zzz_Relationen` nach `QuellTabelle = aktuelle_Tabelle` mit gesetztem `Kette`-Feld
2. **0 Treffer** → `tabellenfenster_oeffnen(tabellenname)` (öffnet Tabelle direkt)
3. **1 Treffer** → `_workflow_ketten_fenster_oeffnen(rel_id, projektname)` direkt
4. **Mehrere Treffer** → Auswahlmenü mit allen passenden Kettenbeziehungen

---

## Zusammenfassung der Änderungen in diesem Patch

| Bereich | Vorher | Nachher |
|---------|--------|---------|
| Überschneidungen Spalte | Nur Spaltenbreiten | Vollständiges Standard-Menü |
| Überschneidungen Kette (Gruppen) | Nur Spaltenbreiten | Vollständiges Standard-Menü |
| Überschneidungen Kette (Details) | Nur Spaltenbreiten | Vollständiges Standard-Menü |
| Alle Standard-Menüs | 17 Einträge (ohne Verknüpft) | 18 Einträge + „Verknüpfte Datensätze anzeigen" |
