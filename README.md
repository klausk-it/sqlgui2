# SqlGui

**Version:** 4.6.51

SqlGui ist eine Desktop-Anwendung zur interaktiven Verwaltung und Abfrage von SQLite-Datenbanken mit grafischer Oberfläche (Tkinter), CSV-Import/-Export und erweiterter SQL-Unterstützung.

## Dateien

| Datei | Beschreibung |
|---|---|
| `sqlgui.py` | Hauptdatei, Einstiegspunkt |
| `sqlgui_gui.py` | GUI-Komponenten und Fenster-Hilfsfunktionen |
| `sqlgui_sql.py` | SQL-Abfrage- und Datenbankfunktionen |
| `sqlgui_text.py` | Text- und CSV-Formatierungsfunktionen |
| `sqlgui_udf.py` | Benutzerdefinierte SQLite-Funktionen (UDFs) |

## Start

```bash
python sqlgui.py
```

---

## Release Notes

### Aktuelle Änderungen (seit letztem Tag)

#### Foreign Keys & Primary Keys (Tabelle-Menü)
- Neuer Menüpunkt **„Tabelle → Foreign Keys bearbeiten …"**: ein einziger Dialog zeigt die `CREATE TABLE`-DDL aus `sqlite_master` (eingerückt, mehrzeilig), den aktuellen Primary Key sowie alle FOREIGN KEY-Constraints via `PRAGMA foreign_key_list`.
- **Primary Key setzen**: Mehrfachauswahl per Listbox (Strg+Klick) für zusammengesetzte PKs (z. B. Verknüpfungstabellen mit `ByGrID + ByID`).
- **FKs hinzufügen / löschen**: QuellFeld → ZielTabelle.ZielFeld, beliebig viele Einträge.
- **„Tabelle neu erstellen"**: schreibt PK und FKs als echte Constraints in die `CREATE TABLE`-Definition – alle Datensätze bleiben erhalten. `PRAGMA foreign_key_list` und `PRAGMA table_info` geben danach die korrekten Ergebnisse zurück.
- Verbesserte Fehlermeldungen bei `database is locked` (offene Tabellenfenster schließen) und `UNIQUE constraint failed` (Hinweis auf Mehrfachauswahl für zusammengesetzte PKs).

#### FK-Import aus Datenbank (Relationen)
- Rechtsklick auf die Relationenliste → **„FK aus DB importieren …"**: liest alle `PRAGMA foreign_key_list`-Einträge aller Tabellen, markiert bereits vorhandene Beziehungen grau, neue werden vorausgewählt. Per Klick in `zzz_Relationen` übernehmen.

#### Tabellenliste aktualisieren (F5)
- **Hauptfenster**: Menü „Tabelle → Tabellenliste aktualisieren [F5]" + F5-Taste aktualisiert die linke Tabellenliste nach `CREATE TABLE`-Befehlen.
- **SQL-Fenster**: F5 + Rechtsklick-Menüeintrag „Aktualisieren (F5)" auf der Tabellenliste.

#### Workflow-SQL-Ergebnisfenster
- Neue Menüpunkte: **Als Tabelle speichern**, **Als CSV speichern**, **Tabelle aktualisieren [F5]** – entspricht dem Funktionsumfang der anderen Ergebnisfenster.

#### CSV-Export
- Alle CSV-Exporte aus dem SQL-Fenster und dem Workflow-SQL-Fenster landen jetzt automatisch im Verzeichnis `Export/` (eine Ebene über dem `DB/`-Ordner). Das Verzeichnis wird angelegt, falls es nicht existiert.
- Alle Felder werden konsequent in **doppelte Anführungszeichen** gesetzt (`QUOTE_ALL`).

#### Überschneidungsanalyse / Schrittweise-Fenster
- **Alle Gruppen: Ergebnis (Schritt 5)**: neuer Button zeigt Schritt 5 für alle Gruppen mit Überschneidungen in einer Ansicht.
- Button-Reihenfolge: „Alle Gruppen: Ergebnis (Schritt 5)" steht jetzt über der Einzelschritt-Zeile.
- Gruppenklick → alle 5 Schritte werden sofort angezeigt; „Einzelschritt ►" setzt auf Schritt 1 zurück.
- Schritt 5 enthält Anzeigenamen A/B, Gruppenname und -ID; A als Kopfzeile, B eingerückt; 10 Leerzeilen am Ende.
- Details-TV (`d_tv`): A immer eigene fette Zeile, B immer darunter eingerückt – auch bei nur 1 Überschneidung.
- `g_tv` wird nach dem Fenster-Render mit „Daten optimal" formatiert.
