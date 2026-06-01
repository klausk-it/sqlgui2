"""SQL-Hilfsmodul fuer SqlGui Version 4.6.51.

Dieses Modul enthaelt den SQL-spezifischen Programmteil:
- SQL-Abfragen-Tabelle
- gespeicherte SQL-Abfragen
- SQL-Fenster
- SQL-Ergebnisfenster
- Ablage von SQL-/CSV-Ergebnissen als Tabelle

Die Hauptdatei initialisiert das Modul ueber sql_modul_initialisieren(...),
damit Abhaengigkeiten explizit und einheitlich uebergeben werden.
"""

import json
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from datetime import datetime
from sqlgui_udf import udf_alle_registrieren

G_TABELLE_SQL_ABFRAGEN = "zzz_SQL_ABFRAGEN"
G_TABELLE_PROJEKTE = "zzz_Projekte"
G_TABELLE_PROJEKT_WORKFLOW = "zzz_Projekt_Workflow"

SQL_ABFRAGEN_SCHEMA_SPALTEN = {
    "beziehung_links": "TEXT",
    "beziehung_rechts": "TEXT",
    "beziehung1_typ": "TEXT",
    "beziehung1_tabelle": "TEXT",
    "beziehung1_links_tabelle": "TEXT",
    "beziehung1_rechts_tabelle": "TEXT",
    "beziehung1_links": "TEXT",
    "beziehung1_rechts": "TEXT",
    "beziehung2_typ": "TEXT",
    "beziehung2_tabelle": "TEXT",
    "beziehung2_links_tabelle": "TEXT",
    "beziehung2_rechts_tabelle": "TEXT",
    "beziehung2_links": "TEXT",
    "beziehung2_rechts": "TEXT",
    "beziehung3_typ": "TEXT",
    "beziehung3_tabelle": "TEXT",
    "beziehung3_links_tabelle": "TEXT",
    "beziehung3_rechts_tabelle": "TEXT",
    "beziehung3_links": "TEXT",
    "beziehung3_rechts": "TEXT",
    "beziehungen_json": "TEXT",
    "where_json": "TEXT",
    "update_tabelle": "TEXT",
    "update_sets_json": "TEXT",
    "update_where_json": "TEXT",
    "delete_tabelle": "TEXT",
    "delete_where_json": "TEXT",
    "insert_tabelle": "TEXT",
    "insert_werte_json": "TEXT",
    "order_by_json": "TEXT",
    "haupttabelle": "TEXT",
}

root = None
G_EXE_Title = "SqlGui"
get_geladene_db_datei = lambda: None

def _nicht_initialisiert(*args, **kwargs):
    raise RuntimeError("SqlGui SQL-Modul wurde noch nicht initialisiert.")

sqlite_verbindung_oeffnen = _nicht_initialisiert
sql_identifier = _nicht_initialisiert
sql_name_ok = _nicht_initialisiert
db_ist_geladen = _nicht_initialisiert
db_pruefen_oder_warnen = _nicht_initialisiert
tabellen_laden = _nicht_initialisiert
tabellen_dropdown_aktualisieren = _nicht_initialisiert
tree_spalten_breiten_anpassen = _nicht_initialisiert
fenster_registrieren = _nicht_initialisiert
ipv4_to_int = None
debug_log = lambda text, kategorie="allgemein": None
logging_eintrag_schreiben = lambda meldung, status=0: None
ip_range_aufteilen_funktion = lambda text: {"ok": False, "fehler": "Nicht initialisiert"}
eindeutigen_tabellennamen_vorschlagen_funktion = lambda name: name
eindeutigen_dateinamen_vorschlagen_funktion = lambda verz, name, ext=".csv": f"{name}{ext}"
fenster_schliessen_callback_setzen = lambda fenster, schliessen_callback: False
hauptfenster_projekt_modus_setzen = lambda aktiv, projektname=None: None
tabellenfenster_oeffnen = lambda tabellenname: None
tabellenfenster_holen = lambda tabellenname: None
rahmenfarbe_setzen = lambda farbe1, farbe2="", farbe3="", hoehe=None: None
fensterliste_farben_setzen = lambda hellblau, dunkelblau, orange: None
alle_workflow_fenster_schliessen = lambda projektname: None
alle_fenster_einfaerben = lambda bg, fg, sel_bg, sel_fg: None
admin_code_fuer_aktion_pruefen = lambda tabellenname, aktion: True   # wird durch Hauptdatei ersetzt


_SQL_KONFIG_BEREICH = "SQL-Fenster"
_PROJEKT_LAYOUT_BEREICH = "Projekt-Layout"

# Modul-weit sichtbares ausgewähltes Projekt (unabhängig vom Kiosk-Aktivierungsstatus).
# Wird von sql_abfrage_fenster_oeffnen() bei Projektwechsel aktualisiert.
_G_ausgewaehltes_projekt = {"name": None}


_TV_SORT_ZUSTAND = {}   # {(id(tv), col_id): aufsteigend_bool}
_IP_RE = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')

def _ip_zu_int(s):
    """Erste IPv4-Adresse aus s als 32-Bit-Integer, oder None."""
    m = _IP_RE.match(str(s).strip())
    if not m:
        return None
    return (int(m.group(1)) << 24) | (int(m.group(2)) << 16) | (int(m.group(3)) << 8) | int(m.group(4))



def _tv_sortieren(tv, col):
    """Generische Spalten-Sortierung für beliebige ttk.Treeview. Togglet ▲/▼."""
    alle = list(tv["columns"])
    if col not in alle:
        return
    key = (id(tv), col)
    aufsteigend = not _TV_SORT_ZUSTAND.get(key, False)
    _TV_SORT_ZUSTAND[key] = aufsteigend

    idx = alle.index(col)
    items = [(tv.item(iid, "values"), iid) for iid in tv.get_children()]

    def _sk(item):
        v = item[0][idx] if idx < len(item[0]) else ""
        vs = str(v).strip()
        ip_int = _ip_zu_int(vs)
        if ip_int is not None:
            return (0, ip_int, "")
        try:
            return (1, float(vs.replace(",", ".").replace(" ", "")), "")
        except (ValueError, TypeError):
            return (2, 0, vs.lower())
    items.sort(key=_sk, reverse=not aufsteigend)
    for _, iid in items:
        tv.move(iid, "", "end")

    for c in alle:
        try:
            kopf = tv.heading(c, "text").rstrip().rstrip("▲▼").rstrip()
            pf = " ▲" if (c == col and aufsteigend) else (" ▼" if c == col else "")
            tv.heading(c, text=kopf + pf, anchor="w")
        except Exception:
            pass


def _tv_spalten_minimum(tv):
    """Setzt jede Spalte auf die Breite ihres Spaltenkopf-Textes (Minimum)."""
    import tkinter.font as _tkfont
    fnt = _tkfont.nametofont("TkDefaultFont")
    for col in tv["columns"]:
        kopf = tv.heading(col, "text")
        tv.column(col, width=fnt.measure(kopf) + 16)


def _tv_spalten_menue_aufbauen(menu, tv, alle_sp_cmd):
    """Fügt die drei Standard-Spaltenbreiten-Einträge zu einem Menü hinzu."""
    menu.add_command(label="Daten optimal",
                     command=lambda: alle_sp_cmd())
    menu.add_command(label="Spaltennamen optimal",
                     command=lambda: _tv_spalten_minimum(tv))
    menu.add_command(label="Alle Spaltennamen vollständig anzeigen",
                     command=lambda: alle_sp_cmd())


_TREEVIEW_THEMES = {
    "standard":  {"bg": "white",   "fg": "black",   "sel_bg": "#0078D7", "sel_fg": "white",   "ttk_theme": None},
    "bernstein": {"bg": "#000000", "fg": "#FFBF00", "sel_bg": "#7A5C00", "sel_fg": "#FFBF00", "ttk_theme": "clam"},
    "phosphor":  {"bg": "#000000", "fg": "#33FF33", "sel_bg": "#1A6600", "sel_fg": "#33FF33", "ttk_theme": "clam"},
}
_original_ttk_theme = None
_themed_text_widgets = []   # tk.Text-Widgets, die das aktuelle Theme übernehmen sollen


def _projekt_layout_speichern(projektname, schluessel, wert):
    try:
        if not db_ist_geladen():
            return
        bereich = f"{_PROJEKT_LAYOUT_BEREICH}:{projektname}"
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO "zzz_Konfiguration" (bereich, schluessel, wert, datetime)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bereich, schluessel) DO UPDATE SET
                wert=excluded.wert, datetime=excluded.datetime
            """,
            (bereich, schluessel, str(wert), zeit),
        )
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def _projekt_layout_lesen(projektname, schluessel):
    try:
        if not db_ist_geladen():
            return None
        bereich = f"{_PROJEKT_LAYOUT_BEREICH}:{projektname}"
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            'SELECT wert FROM "zzz_Konfiguration" WHERE bereich=? AND schluessel=?',
            (bereich, schluessel),
        )
        row = cursor.fetchone()
        verbindung.close()
        return row[0] if row else None
    except Exception:
        return None


_PROJEKT_VIEW_NAMEN_BEREICH  = "Projekt-Views"
_PROJEKT_VIEW_DATEN_BEREICH  = "Projekt-View"
_PROJEKT_STARTVIEW_BEREICH   = "Projekt-Startview"


def _projekt_view_db_speichern(bereich, schluessel, wert):
    try:
        if not db_ist_geladen():
            return
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            'INSERT INTO "zzz_Konfiguration" (bereich, schluessel, wert, datetime) '
            'VALUES (?, ?, ?, ?) '
            'ON CONFLICT(bereich, schluessel) DO UPDATE SET '
            'wert=excluded.wert, datetime=excluded.datetime',
            (bereich, schluessel, str(wert), zeit),
        )
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def _projekt_view_db_lesen(bereich, schluessel):
    try:
        if not db_ist_geladen():
            return None
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            'SELECT wert FROM "zzz_Konfiguration" WHERE bereich=? AND schluessel=?',
            (bereich, schluessel),
        )
        row = cursor.fetchone()
        verbindung.close()
        return row[0] if row else None
    except Exception:
        return None


def _projekt_view_db_bereich_loeschen(bereich):
    try:
        if not db_ist_geladen():
            return
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute('DELETE FROM "zzz_Konfiguration" WHERE bereich=?', (bereich,))
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def projekt_view_namen_lesen(projektname):
    """Gibt sortierte Liste der gespeicherten View-Namen für ein Projekt zurück."""
    raw = _projekt_view_db_lesen(_PROJEKT_VIEW_NAMEN_BEREICH, projektname)
    if not raw:
        return []
    return [n.strip() for n in raw.split("|||") if n.strip()]


def _projekt_view_namen_speichern(projektname, namen):
    _projekt_view_db_speichern(_PROJEKT_VIEW_NAMEN_BEREICH, projektname, "|||".join(namen))


def _naechste_view_nummer(projektname):
    namen = projekt_view_namen_lesen(projektname)
    nummern = set()
    for n in namen:
        try:
            nummern.add(int(n.split("-")[0].strip()))
        except Exception:
            pass
    i = 1
    while i in nummern:
        i += 1
    return str(i)


def projekt_view_speichern(projektname, viewname):
    """Speichert aktuell offene Workflow-Fenster + Positionen als benannte View."""
    bereich = f"{_PROJEKT_VIEW_DATEN_BEREICH}:{projektname}:{viewname}"
    _projekt_view_db_bereich_loeschen(bereich)
    eintraege = workflow_laden(projektname)
    for _eid, typ, name in eintraege:
        fenster = None
        if typ == "Tabelle":
            fenster = tabellenfenster_holen(name)
        elif typ == "SQL-Abfrage":
            fenster = _workflow_offene_sql_fenster.get(name)
        elif typ == "Kette":
            fenster = _workflow_offene_ketten_fenster.get(name)
        if fenster:
            try:
                _projekt_view_db_speichern(bereich, f"{typ}|{name}", fenster.winfo_geometry())
            except Exception:
                pass
    try:
        _projekt_view_db_speichern(bereich, "Hauptfenster", root.winfo_geometry())
        _projekt_view_db_speichern(bereich, "Hauptfenster_state", root.state())
    except Exception:
        pass
    # Namen-Liste aktualisieren
    namen = projekt_view_namen_lesen(projektname)
    if viewname not in namen:
        namen.append(viewname)
        def _sort_key(n):
            try:
                return (int(n.split("-")[0].strip()), n)
            except Exception:
                return (999, n)
        namen.sort(key=_sort_key)
        _projekt_view_namen_speichern(projektname, namen)


def projekt_view_laden(projektname, viewname):
    """Schließt alle Workflow-Fenster, öffnet genau die View-Fenster an gespeicherten Positionen."""
    bereich = f"{_PROJEKT_VIEW_DATEN_BEREICH}:{projektname}:{viewname}"
    eintraege = workflow_laden(projektname)
    # SQL-Abfrage-Fenster schließen
    for name in list(_workflow_offene_sql_fenster.keys()):
        f = _workflow_offene_sql_fenster.pop(name, None)
        try:
            if f and f.winfo_exists():
                f.destroy()
        except Exception:
            pass
    # Ketten-Fenster schließen
    for name in list(_workflow_offene_ketten_fenster.keys()):
        f = _workflow_offene_ketten_fenster.pop(name, None)
        try:
            if f and f.winfo_exists():
                f.destroy()
        except Exception:
            pass
    # Tabellen-Fenster schließen (via Callback aus Hauptmodul)
    try:
        alle_workflow_fenster_schliessen(projektname)
    except Exception:
        pass

    # 1. Hauptfenster sofort positionieren
    hf_geo = _projekt_view_db_lesen(bereich, "Hauptfenster")
    hf_state = _projekt_view_db_lesen(bereich, "Hauptfenster_state")
    try:
        if root.state() in ("iconic", "withdrawn"):
            root.deiconify()
    except Exception:
        pass
    # update_idletasks() stellt sicher, dass ausstehende Fenstermanager-Nachrichten
    # (z.B. geometry()-Aufrufe beim DB-Laden) abgearbeitet sind, bevor wir positionieren.
    try:
        root.update_idletasks()
    except Exception:
        pass
    if hf_state == "zoomed":
        try:
            root.state("zoomed")
        except Exception:
            pass
    elif hf_geo:
        try:
            root.state("normal")
            root.update_idletasks()   # Zustandswechsel abwarten bevor Geometrie gesetzt wird
            root.geometry(hf_geo)
        except Exception:
            pass

    # 2. Nur Fenster aus der View öffnen
    offene = []
    for _eid, typ, name in eintraege:
        if not _projekt_view_db_lesen(bereich, f"{typ}|{name}"):
            continue
        try:
            if typ == "Tabelle":
                tabellenfenster_oeffnen(name)
                offene.append(("Tabelle", name))
            elif typ == "SQL-Abfrage":
                _workflow_abfrage_fenster_oeffnen_modul(name)
                offene.append(("SQL-Abfrage", name))
            elif typ == "Kette":
                _workflow_ketten_fenster_oeffnen(name, projektname)
                offene.append(("Kette", name))
        except Exception:
            pass

    # 3. Positionen der Workflow-Fenster nach kurzer Wartezeit setzen
    def _positionieren():
        for typ, name in offene:
            geo = _projekt_view_db_lesen(bereich, f"{typ}|{name}")
            if not geo:
                continue
            if typ == "Tabelle":
                fenster = tabellenfenster_holen(name)
            elif typ == "SQL-Abfrage":
                fenster = _workflow_offene_sql_fenster.get(name)
            elif typ == "Kette":
                fenster = _workflow_offene_ketten_fenster.get(name)
            else:
                fenster = None
            if fenster:
                try:
                    if not fenster.winfo_exists():
                        continue
                    fenster.state("normal")
                    fenster.update_idletasks()
                    fenster.geometry(geo)
                except Exception:
                    pass

    root.after(1000, _positionieren)


def projekt_view_loeschen(projektname, viewname):
    """Löscht eine View vollständig."""
    bereich = f"{_PROJEKT_VIEW_DATEN_BEREICH}:{projektname}:{viewname}"
    _projekt_view_db_bereich_loeschen(bereich)
    namen = projekt_view_namen_lesen(projektname)
    if viewname in namen:
        namen.remove(viewname)
        _projekt_view_namen_speichern(projektname, namen)
    # Startview-Referenz aufheben falls diese View als Startview gesetzt war
    if projekt_startview_lesen(projektname) == viewname:
        projekt_startview_aufheben(projektname)


def projekt_startview_lesen(projektname):
    """Gibt den Namen der Startview zurück, oder None (= Admin View wird geladen)."""
    return _projekt_view_db_lesen(_PROJEKT_STARTVIEW_BEREICH, projektname)


def projekt_startview_setzen(projektname, viewname):
    """Setzt eine benannte View als Startview für das Projekt."""
    _projekt_view_db_speichern(_PROJEKT_STARTVIEW_BEREICH, projektname, viewname)


def projekt_startview_aufheben(projektname):
    """Löscht die Startview-Einstellung – beim Start wird wieder die Admin View geladen."""
    try:
        if not db_ist_geladen():
            return
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            'DELETE FROM "zzz_Konfiguration" WHERE bereich=? AND schluessel=?',
            (_PROJEKT_STARTVIEW_BEREICH, projektname),
        )
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def _sql_konfig_lesen(schluessel):
    try:
        if not db_ist_geladen():
            return None
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            'SELECT wert FROM "zzz_Konfiguration" WHERE bereich=? AND schluessel=?',
            (_SQL_KONFIG_BEREICH, schluessel),
        )
        row = cursor.fetchone()
        verbindung.close()
        return row[0] if row else None
    except Exception:
        return None


def _sql_konfig_speichern(schluessel, wert):
    try:
        if not db_ist_geladen():
            return
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO "zzz_Konfiguration" (bereich, schluessel, wert, datetime)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bereich, schluessel) DO UPDATE SET
                wert=excluded.wert, datetime=excluded.datetime
            """,
            (_SQL_KONFIG_BEREICH, schluessel, str(wert), zeit),
        )
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def treeview_theme_anwenden(theme_name, speichern=True):
    """Setzt das Farbthema app-weit (Standard / Bernstein / Phosphor-Grün)."""
    global _original_ttk_theme
    theme = _TREEVIEW_THEMES.get(theme_name, _TREEVIEW_THEMES["standard"])
    bg     = theme["bg"]
    fg     = theme["fg"]
    sel_bg = theme["sel_bg"]
    sel_fg = theme["sel_fg"]
    is_dark = theme["ttk_theme"] is not None   # Retro-Theme → dunkel

    style = ttk.Style()
    if _original_ttk_theme is None:
        _original_ttk_theme = style.theme_use()
    # ttk-Theme wechseln (clam für Retro-Themes, Original für Standard)
    ziel_ttk_theme = theme["ttk_theme"] or _original_ttk_theme or "default"
    try:
        if style.theme_use() != ziel_ttk_theme:
            style.theme_use(ziel_ttk_theme)
    except Exception:
        pass

    # ── Treeview ────────────────────────────────────────────────────────────
    style.configure("Treeview",
                    background=bg, foreground=fg, fieldbackground=bg)
    style.map("Treeview",
              background=[("selected", sel_bg)],
              foreground=[("selected", sel_fg)])
    if is_dark:
        style.configure("Treeview.Heading",
                        background="#1a1a1a", foreground=fg, relief="flat")
        style.map("Treeview.Heading", background=[("active", "#2a2a2a")])
    else:
        style.configure("Treeview.Heading")
        style.map("Treeview.Heading", background=[], foreground=[])

    # ── Volle ttk-Widget-Palette ─────────────────────────────────────────────
    if is_dark:
        head_bg  = "#1a1a1a"
        head_act = "#2a2a2a"
        entry_bg = "#1a1a1a"
        btn_bg   = "#1a1a1a"
        btn_act  = "#2a2a2a"
        sep_bg   = "#444444"
        scroll_bg= "#2a2a2a"
        scroll_tr= "#1a1a1a"
    else:
        head_bg  = ""
        head_act = ""
        entry_bg = "white"
        btn_bg   = ""
        btn_act  = ""
        sep_bg   = ""
        scroll_bg= ""
        scroll_tr= ""

    def _cfg(widget, **kw):
        try:
            style.configure(widget, **{k: v for k, v in kw.items() if v != ""})
        except Exception:
            pass

    def _map(widget, **kw):
        try:
            style.map(widget, **{k: v for k, v in kw.items() if v})
        except Exception:
            pass

    if is_dark:
        _cfg("TFrame",       background=bg)
        _cfg("TLabel",       background=bg, foreground=fg)
        _cfg("TButton",      background=btn_bg, foreground=fg,
                             bordercolor=sep_bg, focuscolor=sel_bg)
        _map("TButton",
             background=[("active", btn_act), ("pressed", sel_bg)],
             foreground=[("active", fg)])
        _cfg("TEntry",       fieldbackground=entry_bg, background=entry_bg, foreground=fg,
                             insertcolor=fg, selectbackground=sel_bg, selectforeground=sel_fg)
        _map("TEntry",       fieldbackground=[("focus", entry_bg), ("!disabled", entry_bg)],
             background=[("focus", entry_bg), ("!disabled", entry_bg)],
             foreground=[("focus", fg), ("!disabled", fg)])
        _cfg("TCombobox",    fieldbackground=entry_bg, background=entry_bg, foreground=fg,
                             selectbackground=sel_bg, selectforeground=sel_fg,
                             arrowcolor=fg, insertcolor=fg)
        _map("TCombobox",
             fieldbackground=[("readonly", entry_bg), ("focus", entry_bg), ("!disabled", entry_bg)],
             background=[("readonly", entry_bg), ("focus", entry_bg), ("active", entry_bg), ("!disabled", entry_bg)],
             foreground=[("readonly", fg), ("focus", fg), ("!disabled", fg)])
        _cfg("TSpinbox",     fieldbackground=entry_bg, background=entry_bg, foreground=fg,
                             insertcolor=fg, arrowcolor=fg)
        _map("TSpinbox",
             fieldbackground=[("focus", entry_bg), ("!disabled", entry_bg)],
             background=[("focus", entry_bg), ("!disabled", entry_bg)])
        # Popup-Liste der Combobox (tk.Listbox intern)
        try:
            style.configure("ComboboxPopdownFrame", relief="flat", background=entry_bg)
        except Exception:
            pass
        _cfg("TNotebook",    background=bg, bordercolor=sep_bg)
        _cfg("TNotebook.Tab", background=head_bg, foreground=fg,
                              padding=[8, 4])
        _map("TNotebook.Tab",
             background=[("selected", sel_bg), ("active", head_act)],
             foreground=[("selected", sel_fg), ("active", fg)])
        _cfg("TScrollbar",   background=scroll_bg, troughcolor=scroll_tr,
                             arrowcolor=fg, bordercolor=sep_bg)
        _map("TScrollbar",   background=[("active", sel_bg)])
        _cfg("TSeparator",   background=sep_bg)
        _cfg("TLabelframe",  background=bg, foreground=fg, bordercolor=sep_bg)
        _cfg("TLabelframe.Label", background=bg, foreground=fg)
        _cfg("TPanedwindow", background=bg)
        _cfg("Sash",         sashthickness=5, handlesize=6,
                             background=sep_bg)
        _cfg("TRadiobutton", background=bg, foreground=fg,
                             focuscolor=bg, indicatorcolor=entry_bg)
        _map("TRadiobutton",
             background=[("active", bg)],
             foreground=[("active", fg)],
             indicatorcolor=[("selected", fg)])
        _cfg("TCheckbutton", background=bg, foreground=fg,
                             focuscolor=bg, indicatorcolor=entry_bg)
        _map("TCheckbutton",
             background=[("active", bg)],
             foreground=[("active", fg)],
             indicatorcolor=[("selected", fg)])
        _cfg("TProgressbar", background=sel_bg, troughcolor=scroll_tr)
        _cfg("TScale",       background=bg, troughcolor=scroll_tr)
        _map("TScale",       background=[("active", bg)])
    else:
        # Standard: ttk-Styles zurücksetzen (alles auf leer → Theme-Default)
        for widget_name in (
            "TFrame", "TLabel", "TButton", "TEntry", "TCombobox",
            "TNotebook", "TNotebook.Tab", "TScrollbar", "TSeparator",
            "TSpinbox", "TLabelframe", "TLabelframe.Label", "TPanedwindow",
            "Sash", "TRadiobutton", "TCheckbutton", "TProgressbar", "TScale",
        ):
            try:
                style.configure(widget_name)
            except Exception:
                pass
            try:
                style.map(widget_name,
                          background=[], foreground=[], indicatorcolor=[],
                          fieldbackground=[], arrowcolor=[], bordercolor=[])
            except Exception:
                pass

    # ── Registrierte tk.Text-Widgets einfärben ───────────────────────────────
    for w in list(_themed_text_widgets):
        try:
            if w.winfo_exists():
                w.configure(bg=bg, fg=fg, insertbackground=fg,
                            selectbackground=sel_bg, selectforeground=sel_fg)
            else:
                _themed_text_widgets.remove(w)
        except Exception:
            try:
                _themed_text_widgets.remove(w)
            except Exception:
                pass

    # ── <<ThemeChanged>> erzwingen, damit ttk-Widgets neu zeichnen ──────────────
    # Wenn das ttk-Theme unverändert bleibt (z.B. Bernstein → Phosphor-Grün,
    # beide "clam"), wird style.theme_use() oben nicht erneut aufgerufen.
    # Ohne diesen Aufruf feuert kein <<ThemeChanged>>-Event – TCombobox und
    # andere ttk-Widgets übernehmen dann das aktualisierte Style-Map nicht.
    # Fix: kurz auf das Original-Theme wechseln und sofort zurück (synchron,
    # kein sichtbares Flackern, da Tkinter Repaints bündelt).
    try:
        _aktuell = style.theme_use()
        _fallback = _original_ttk_theme or "default"
        if _aktuell != _fallback:
            style.theme_use(_fallback)   # <<ThemeChanged>> → weg von clam
            style.theme_use(_aktuell)    # <<ThemeChanged>> → zurück zu clam (neue Farben)
    except Exception:
        pass

    # ── Alle tk-Fenster rekursiv einfärben ───────────────────────────────────
    try:
        alle_fenster_einfaerben(bg, fg, sel_bg, sel_fg)
    except Exception:
        pass

    if speichern:
        try:
            _sql_konfig_speichern("treeview_theme", theme_name)
        except Exception:
            pass


def treeview_theme_aus_db_laden():
    """Liest gespeichertes Treeview-Theme aus zzz_Konfiguration und wendet es an.
    Ist kein Theme in der DB gespeichert, bleibt das aktuell aktive Theme erhalten."""
    try:
        theme_name = _sql_konfig_lesen("treeview_theme")
        if theme_name:
            treeview_theme_anwenden(theme_name, speichern=False)
        # Kein Eintrag in der DB → aktuelles Theme beibehalten (kein Reset auf Standard)
    except Exception:
        pass


def sql_text_im_lesefenster_anzeigen(parent, titel, text):
    fenster = tk.Toplevel(parent)
    fenster.title(titel)
    fenster.geometry("760x520")
    fenster.minsize(420, 260)

    frame = tk.Frame(fenster, padx=10, pady=10)
    frame.pack(fill="both", expand=True)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    textfeld = tk.Text(frame, wrap="word", undo=False)
    textfeld.grid(row=0, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(frame, orient="vertical", command=textfeld.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    textfeld.configure(yscrollcommand=scroll_y.set)
    textfeld.insert("1.0", "" if text is None else str(text))
    textfeld.configure(state="disabled")

    button_frame = tk.Frame(frame)
    button_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(8, 0))

    def kopieren():
        fenster.clipboard_clear()
        fenster.clipboard_append("" if text is None else str(text))

    tk.Button(button_frame, text="In Zwischenspeicher kopieren", command=kopieren).pack(side="right", padx=(8, 0))
    tk.Button(button_frame, text="Schließen", command=fenster.destroy, width=12).pack(side="right")
    try:
        fenster_registrieren(fenster, "Lesefenster", titel)
    except Exception:
        pass


def sql_zeile_im_lesefenster_mit_navigation(parent, basis_titel, tv, spalten, start_item_id, kontext_zeile=""):
    """Zeile im Lesefenster mit ▲/▼-Navigation zwischen den Treeview-Zeilen."""
    alle_items = list(tv.get_children())
    if not alle_items:
        return
    try:
        idx_var = [alle_items.index(start_item_id)]
    except ValueError:
        idx_var = [0]

    fenster = tk.Toplevel(parent)
    fenster.geometry("760x520")
    fenster.minsize(420, 260)

    frame = tk.Frame(fenster, padx=10, pady=10)
    frame.pack(fill="both", expand=True)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    textfeld = tk.Text(frame, wrap="word", undo=False)
    textfeld.grid(row=0, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(frame, orient="vertical", command=textfeld.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    textfeld.configure(yscrollcommand=scroll_y.set)

    button_frame = tk.Frame(frame)
    button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def zeile_anzeigen():
        item_id = alle_items[idx_var[0]]
        werte   = list(tv.item(item_id, "values"))
        zeilen  = ([kontext_zeile, ""] if kontext_zeile else [])
        for i, sp in enumerate(spalten):
            zeilen.append(f"{sp}: {werte[i] if i < len(werte) else ''}")
            zeilen.append("")
        gesamt = len(alle_items)
        fenster.title(f"{basis_titel}  [{idx_var[0] + 1}/{gesamt}]")
        textfeld.configure(state="normal")
        textfeld.delete("1.0", "end")
        textfeld.insert("1.0", "\n".join(zeilen))
        textfeld.configure(state="disabled")
        try:
            tv.selection_set(item_id)
            tv.see(item_id)
        except Exception:
            pass

    def vorherige(event=None):
        if idx_var[0] > 0:
            idx_var[0] -= 1
            zeile_anzeigen()

    def naechste(event=None):
        if idx_var[0] < len(alle_items) - 1:
            idx_var[0] += 1
            zeile_anzeigen()

    def kopieren():
        item_id = alle_items[idx_var[0]]
        werte   = list(tv.item(item_id, "values"))
        zeilen  = ([kontext_zeile, ""] if kontext_zeile else [])
        for i, sp in enumerate(spalten):
            zeilen.append(f"{sp}: {werte[i] if i < len(werte) else ''}")
            zeilen.append("")
        fenster.clipboard_clear()
        fenster.clipboard_append("\n".join(zeilen))

    nav_frame = tk.Frame(button_frame)
    nav_frame.pack(side="left")
    tk.Button(nav_frame, text="▲ Vorherige", command=vorherige, width=12).pack(side="left", padx=(0, 4))
    tk.Button(nav_frame, text="▼ Nächste",   command=naechste,  width=12).pack(side="left")

    tk.Button(button_frame, text="In Zwischenspeicher kopieren", command=kopieren).pack(side="right", padx=(8, 0))
    tk.Button(button_frame, text="Schließen", command=fenster.destroy, width=12).pack(side="right")

    fenster.bind("<Up>",     vorherige)
    fenster.bind("<Down>",   naechste)
    fenster.bind("<Escape>", lambda e: fenster.destroy())

    zeile_anzeigen()
    try:
        fenster_registrieren(fenster, "Lesefenster", basis_titel)
    except Exception:
        pass


def sql_modul_initialisieren(
    root_widget,
    exe_title,
    get_geladene_db_datei,
    sqlite_verbindung_oeffnen_funktion,
    sql_identifier_funktion,
    sql_name_ok_funktion,
    db_ist_geladen_funktion,
    db_pruefen_oder_warnen_funktion,
    tabellen_laden_funktion,
    tabellen_dropdown_aktualisieren_funktion,
    tree_spalten_breiten_anpassen_funktion,
    fenster_registrieren_funktion,
    ipv4_to_int_funktion=None,
    debug_log_funktion=None,
    logging_eintrag_schreiben_funktion=None,
    fenster_standard_menue_anbringen_funktion=None,
    fenster_schliessen_callback_setzen_funktion=None,
    ip_range_aufteilen_funktion_param=None,
    eindeutigen_tabellennamen_param=None,
    eindeutigen_dateinamen_param=None,
    hauptfenster_projekt_modus_setzen_funktion=None,
    tabellenfenster_oeffnen_funktion=None,
    tabellenfenster_holen_funktion=None,
    rahmenfarbe_setzen_funktion=None,
    fensterliste_farben_setzen_funktion=None,
    alle_workflow_fenster_schliessen_funktion=None,
    alle_fenster_einfaerben_funktion=None,
    admin_code_fuer_aktion_pruefen_funktion=None,
):
    """Initialisiert die Abhaengigkeiten des SQL-Moduls aus der Hauptdatei."""
    global root, G_EXE_Title
    global sqlite_verbindung_oeffnen, sql_identifier, sql_name_ok
    global db_ist_geladen, db_pruefen_oder_warnen
    global tabellen_laden, tabellen_dropdown_aktualisieren
    global tree_spalten_breiten_anpassen, fenster_registrieren
    global ipv4_to_int, debug_log, logging_eintrag_schreiben, fenster_standard_menue_anbringen
    global fenster_schliessen_callback_setzen, ip_range_aufteilen_funktion
    global eindeutigen_tabellennamen_vorschlagen_funktion, eindeutigen_dateinamen_vorschlagen_funktion
    global hauptfenster_projekt_modus_setzen, tabellenfenster_oeffnen, tabellenfenster_holen, rahmenfarbe_setzen, fensterliste_farben_setzen, alle_workflow_fenster_schliessen, alle_fenster_einfaerben
    global admin_code_fuer_aktion_pruefen

    root = root_widget
    G_EXE_Title = exe_title
    globals()["get_geladene_db_datei"] = get_geladene_db_datei
    sqlite_verbindung_oeffnen = sqlite_verbindung_oeffnen_funktion
    sql_identifier = sql_identifier_funktion
    sql_name_ok = sql_name_ok_funktion
    db_ist_geladen = db_ist_geladen_funktion
    db_pruefen_oder_warnen = db_pruefen_oder_warnen_funktion
    tabellen_laden = tabellen_laden_funktion
    tabellen_dropdown_aktualisieren = tabellen_dropdown_aktualisieren_funktion
    tree_spalten_breiten_anpassen = tree_spalten_breiten_anpassen_funktion
    fenster_registrieren = fenster_registrieren_funktion
    ipv4_to_int = ipv4_to_int_funktion
    if callable(debug_log_funktion):
        debug_log = debug_log_funktion
    if callable(logging_eintrag_schreiben_funktion):
        logging_eintrag_schreiben = logging_eintrag_schreiben_funktion
    if callable(fenster_standard_menue_anbringen_funktion):
        fenster_standard_menue_anbringen = fenster_standard_menue_anbringen_funktion
    if callable(fenster_schliessen_callback_setzen_funktion):
        fenster_schliessen_callback_setzen = fenster_schliessen_callback_setzen_funktion
    if callable(ip_range_aufteilen_funktion_param):
        ip_range_aufteilen_funktion = ip_range_aufteilen_funktion_param
    if callable(eindeutigen_tabellennamen_param):
        eindeutigen_tabellennamen_vorschlagen_funktion = eindeutigen_tabellennamen_param
    if callable(eindeutigen_dateinamen_param):
        eindeutigen_dateinamen_vorschlagen_funktion = eindeutigen_dateinamen_param
    if callable(hauptfenster_projekt_modus_setzen_funktion):
        hauptfenster_projekt_modus_setzen = hauptfenster_projekt_modus_setzen_funktion
    if callable(tabellenfenster_oeffnen_funktion):
        tabellenfenster_oeffnen = tabellenfenster_oeffnen_funktion
    if callable(tabellenfenster_holen_funktion):
        tabellenfenster_holen = tabellenfenster_holen_funktion
    if callable(rahmenfarbe_setzen_funktion):
        rahmenfarbe_setzen = rahmenfarbe_setzen_funktion
    if callable(fensterliste_farben_setzen_funktion):
        fensterliste_farben_setzen = fensterliste_farben_setzen_funktion
    if callable(alle_workflow_fenster_schliessen_funktion):
        alle_workflow_fenster_schliessen = alle_workflow_fenster_schliessen_funktion
    if callable(alle_fenster_einfaerben_funktion):
        alle_fenster_einfaerben = alle_fenster_einfaerben_funktion
    if callable(admin_code_fuer_aktion_pruefen_funktion):
        admin_code_fuer_aktion_pruefen = admin_code_fuer_aktion_pruefen_funktion


def sql_logging_eintrag_sicher_schreiben(meldung, status=0):
    """Schreibt einen SQL-Logeintrag, ohne die eigentliche SQL-Ausfuehrung zu stoeren."""
    try:
        logging_eintrag_schreiben(meldung, status)
    except Exception as log_fehler:
        debug_log(f"SQL-Logging konnte nicht geschrieben werden: {log_fehler}", "allgemein")


def sql_abfragen_tabelle_anlegen():
    if not get_geladene_db_datei():
        return
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            ziel_tabelle TEXT NOT NULL,
            beziehung1_typ TEXT,
            beziehung1_tabelle TEXT,
            beziehung1_links_tabelle TEXT,
            beziehung1_rechts_tabelle TEXT,
            beziehung1_links TEXT,
            beziehung1_rechts TEXT,
            beziehung2_typ TEXT,
            beziehung2_tabelle TEXT,
            beziehung2_links_tabelle TEXT,
            beziehung2_rechts_tabelle TEXT,
            beziehung2_links TEXT,
            beziehung2_rechts TEXT,
            beziehung3_typ TEXT,
            beziehung3_tabelle TEXT,
            beziehung3_links_tabelle TEXT,
            beziehung3_rechts_tabelle TEXT,
            beziehung3_links TEXT,
            beziehung3_rechts TEXT,
            beziehungen_json TEXT,
            where_json TEXT,
            update_tabelle TEXT,
            update_sets_json TEXT,
            update_where_json TEXT,
            delete_tabelle TEXT,
            delete_where_json TEXT,
            insert_tabelle TEXT,
            insert_werte_json TEXT,
            order_by_json TEXT,
            haupttabelle TEXT,
            sql_text TEXT NOT NULL,
            erstellt_am TEXT NOT NULL,
            geaendert_am TEXT NOT NULL
        )
        """
    )
    cursor.execute(f"PRAGMA table_info({sql_identifier(G_TABELLE_SQL_ABFRAGEN)})")
    vorhandene_spalten = {row[1] for row in cursor.fetchall()}

    for spalte, typ in SQL_ABFRAGEN_SCHEMA_SPALTEN.items():
        if spalte not in vorhandene_spalten:
            cursor.execute(f"ALTER TABLE {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} ADD COLUMN {sql_identifier(spalte)} {typ}")
            vorhandene_spalten.add(spalte)

    cursor.execute(f"""
        UPDATE {sql_identifier(G_TABELLE_SQL_ABFRAGEN)}
        SET beziehung1_links = COALESCE(NULLIF(beziehung1_links, ''), COALESCE(beziehung_links, ''))
        WHERE COALESCE(beziehung1_links, '') = ''
    """)
    cursor.execute(f"""
        UPDATE {sql_identifier(G_TABELLE_SQL_ABFRAGEN)}
        SET beziehung1_rechts = COALESCE(NULLIF(beziehung1_rechts, ''), COALESCE(beziehung_rechts, ''))
        WHERE COALESCE(beziehung1_rechts, '') = ''
    """)

    verbindung.commit()
    verbindung.close()


def projekte_tabelle_anlegen():
    if not get_geladene_db_datei():
        return
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_PROJEKTE)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projektname TEXT NOT NULL UNIQUE,
            aktiv INTEGER NOT NULL DEFAULT 0,
            erstellt_am TEXT NOT NULL,
            geaendert_am TEXT NOT NULL
        )
        """
    )
    # Schema-Migration: Spalte aktiv nachrüsten falls noch nicht vorhanden
    cursor.execute(f"PRAGMA table_info({sql_identifier(G_TABELLE_PROJEKTE)})")
    vorhandene_spalten = {row[1] for row in cursor.fetchall()}
    if "aktiv" not in vorhandene_spalten:
        cursor.execute(
            f"ALTER TABLE {sql_identifier(G_TABELLE_PROJEKTE)} ADD COLUMN aktiv INTEGER NOT NULL DEFAULT 0"
        )
    verbindung.commit()
    verbindung.close()


def projekt_workflow_tabelle_anlegen():
    if not get_geladene_db_datei():
        return
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT,
            projektname TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            typ TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    cursor.execute(
        f"UPDATE {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} SET typ='SQL-Abfrage' WHERE typ='SQL'"
    )
    verbindung.commit()
    verbindung.close()


def workflow_laden(projektname):
    """Gibt Liste von (id, typ, name) für ein Projekt zurück, sortiert nach position."""
    if not get_geladene_db_datei() or not projektname:
        return []
    try:
        projekt_workflow_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT id, typ, name FROM {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} "
            f"WHERE projektname=? ORDER BY position, id",
            (projektname,)
        )
        zeilen = [(int(row[0]), str(row[1]), str(row[2])) for row in cursor.fetchall()]
        verbindung.close()
        return zeilen
    except Exception:
        return []


def workflow_eintrag_hinzufuegen(projektname, typ, name):
    """Fügt einen Eintrag am Ende des Workflows ein."""
    projekt_workflow_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(
        f"SELECT COALESCE(MAX(position), -1) + 1 FROM {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} "
        f"WHERE projektname=?",
        (projektname,)
    )
    naechste_pos = cursor.fetchone()[0]
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        f"INSERT INTO {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} "
        f"(datetime, projektname, position, typ, name) VALUES (?,?,?,?,?)",
        (zeit, projektname, naechste_pos, typ, name)
    )
    verbindung.commit()
    verbindung.close()


def workflow_eintrag_entfernen(eintrag_id):
    """Löscht einen Eintrag aus dem Workflow."""
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(
        f"DELETE FROM {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} WHERE id=?",
        (eintrag_id,)
    )
    verbindung.commit()
    verbindung.close()


def workflow_positionen_aktualisieren(projektname, id_reihenfolge):
    """Schreibt neue Positions-Werte entsprechend der übergebenen ID-Reihenfolge."""
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    for pos, eintrag_id in enumerate(id_reihenfolge):
        cursor.execute(
            f"UPDATE {sql_identifier(G_TABELLE_PROJEKT_WORKFLOW)} SET position=? WHERE id=?",
            (pos, eintrag_id)
        )
    verbindung.commit()
    verbindung.close()


def abfrage_sql_text_laden(abfragename):
    """Gibt den SQL-Text einer gespeicherten Abfrage anhand des Namens zurück."""
    if not get_geladene_db_datei():
        return None
    try:
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT sql_text FROM {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} WHERE name=? LIMIT 1",
            (abfragename,)
        )
        row = cursor.fetchone()
        verbindung.close()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None


_workflow_offene_sql_fenster    = {}
_workflow_offene_ketten_fenster = {}   # key = str(rel_id)


def _tv_spalten_auto_breite(tv, spalten_sichtbar, zeilen, pad_kopf=24, pad_daten=16, max_b=400, min_b=40):
    """Setzt Treeview-Spaltenbreiten automatisch: max(Spaltenkopf, längster Datenwert).

    spalten_sichtbar: Liste der angezeigten Spaltennamen (in Reihenfolge).
    zeilen: Sequenz von Tupeln mit den Zeilenwerten (alle Spalten, nicht nur sichtbare).
    Für Treeviews mit displaycolumns werden nur die sichtbaren Spalten angepasst.
    """
    try:
        import tkinter.font as _tkfont
        measure = _tkfont.nametofont("TkDefaultFont").measure
    except Exception:
        def measure(t): return len(str(t)) * 7   # Fallback: 7px pro Zeichen

    # Indizes der sichtbaren Spalten in der Gesamt-Spaltenliste (tv["columns"])
    alle_spalten = list(tv["columns"])
    for sp in spalten_sichtbar:
        breite = measure(str(sp)) + pad_kopf      # Spaltenkopf (mehr Padding für Sort-Pfeil)
        if sp in alle_spalten:
            col_idx = alle_spalten.index(sp)
            for zeile in zeilen:
                try:
                    wert = str(zeile[col_idx]) if zeile[col_idx] is not None else ""
                    breite = max(breite, measure(wert) + pad_daten)
                except (IndexError, TypeError):
                    pass
        tv.column(sp, width=max(min_b, min(breite, max_b)))


def standard_tv_rechtsklick_anbinden(tv_widget, tabellenname, parent_win,
                                      sql_text_hint=None, extra_menue_fn=None,
                                      db_edit=True, nav_override_fn=None):
    """Bindet das vollständige 6-Block Rechtsklick-Menü an tv_widget.

    Gibt ein zeilen_ref-Dict zurück; der Caller befüllt zeilen_ref['alle']
    nach jedem Datenladen (wird für Filter-Aufheben benötigt).

    sql_text_hint:  Optionaler SQL-Text für Finding-Tabellennamen-Extraktion.
    extra_menue_fn: Optional callable(m, item_id, sp_name).
                    Wird am ANFANG des Menüs aufgerufen (vor Block 1).
                    Falls es Einträge hinzufügt, wird automatisch ein Trenner gesetzt.
    db_edit:        True (Standard) = Block 6 (Zeile löschen / Feld editieren) anzeigen.
                    False = Block 6 ausblenden (für reine Schema-Bäume).
    """
    _lok = {"item": None, "spalte": ""}
    zeilen_ref = {"alle": [], "filter_aktiv": False,
                  "filter_spalte": None, "filter_wert": None}

    # ── Spalten-Hilfsfunktionen ───────────────────────────────────────────────
    def _sichtb():
        dc_raw = tv_widget["displaycolumns"]
        if isinstance(dc_raw, str):
            dc_list = [dc_raw] if dc_raw else []
        else:
            dc_list = [str(x) for x in dc_raw if x]
        if not dc_list or "#all" in dc_list:
            return list(tv_widget["columns"])
        return dc_list

    def _alle_sp():
        return list(tv_widget["columns"])

    def _sp_name():
        sp_id = _lok.get("spalte", "")
        if not sp_id:
            return None
        try:
            idx = int(sp_id.replace("#", "")) - 1
        except Exception:
            return None
        s = _sichtb()
        return s[idx] if 0 <= idx < len(s) else None

    def _sp_idx():
        sp = _sp_name()
        if sp is None:
            return None
        try:
            return _alle_sp().index(sp)
        except ValueError:
            return None

    def _ang_werte(iid):
        werte = tv_widget.item(iid, "values")
        alle  = _alle_sp()
        return [str(werte[alle.index(sp)]) if sp in alle and alle.index(sp) < len(werte) else ""
                for sp in _sichtb()]

    # ── Block 1: Kopieren ────────────────────────────────────────────────────
    def feld_kopieren():
        iid = _lok["item"]
        idx = _sp_idx()
        if not iid or idx is None:
            return
        w = tv_widget.item(iid, "values")
        parent_win.clipboard_clear()
        parent_win.clipboard_append(str(w[idx]) if idx < len(w) else "")

    def zeile_kopieren():
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            return
        parent_win.clipboard_clear()
        parent_win.clipboard_append("\t".join(_ang_werte(iid)))

    def zeile_als_csv_kopieren():
        import csv as _c, io as _io
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            return
        buf = _io.StringIO()
        _c.writer(buf, quoting=_c.QUOTE_ALL).writerow(_ang_werte(iid))
        parent_win.clipboard_clear()
        parent_win.clipboard_append(buf.getvalue().rstrip("\r\n"))

    def header_als_csv_kopieren():
        import csv as _c, io as _io
        sp = _sichtb()
        if not sp:
            return
        buf = _io.StringIO()
        _c.writer(buf, quoting=_c.QUOTE_ALL).writerow(sp)
        parent_win.clipboard_clear()
        parent_win.clipboard_append(buf.getvalue().rstrip("\r\n"))

    def tabelle_als_csv_kopieren():
        import csv as _c, io as _io
        ids = tv_widget.get_children()
        if not ids:
            messagebox.showwarning("Tabelle als CSV", "Keine Zeilen vorhanden.", parent=parent_win)
            return
        n = len(ids)
        antwort = messagebox.askyesnocancel(
            "Tabelle als CSV kopieren",
            f"Es sind {n} Zeilen sichtbar.\n\nAlle {n} Zeilen kopieren?\n\n"
            "(Ja = alle, Nein = nur erste 100, Abbrechen = abbrechen)", parent=parent_win)
        if antwort is None:
            return
        ids_exp = ids if antwort else ids[:100]
        sp = _sichtb()
        buf = _io.StringIO()
        w = _c.writer(buf, quoting=_c.QUOTE_ALL)
        w.writerow(sp)
        for iid in ids_exp:
            w.writerow(_ang_werte(iid))
        parent_win.clipboard_clear()
        parent_win.clipboard_append(buf.getvalue())

    # ── Block 2: Anzeigen ────────────────────────────────────────────────────
    def feld_im_lesefenster():
        iid = _lok["item"]
        idx = _sp_idx()
        sp  = _sp_name()
        if not iid or idx is None:
            messagebox.showwarning("Feldinhalt", "Bitte zuerst eine Zelle auswählen.", parent=parent_win)
            return
        w = tv_widget.item(iid, "values")
        sql_text_im_lesefenster_anzeigen(
            parent_win, f"Feldinhalt – {tabellenname} – {sp}",
            str(w[idx]) if idx < len(w) else "")

    def zeile_im_lesefenster():
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            messagebox.showwarning("Zeileninhalt", "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        sql_zeile_im_lesefenster_mit_navigation(
            parent_win, f"Zeile – {tabellenname}", tv_widget, _sichtb(), iid,
            kontext_zeile=tabellenname)

    def alle_sp_anzeigen():
        tree_spalten_breiten_anpassen(tv_widget)

    # ── Block 3: Filtern ─────────────────────────────────────────────────────
    def _filter_setzen(sp_name, filterwert):
        alle = _alle_sp()
        try:
            idx = alle.index(sp_name)
        except ValueError:
            return
        tv_widget.delete(*tv_widget.get_children())
        for z in zeilen_ref["alle"]:
            wert = str(z[idx]) if idx < len(z) else ""
            if filterwert.lower() in wert.lower():
                tv_widget.insert("", "end", values=[str(v) if v is not None else "" for v in z])
        zeilen_ref.update({"filter_aktiv": True,
                           "filter_spalte": sp_name, "filter_wert": filterwert})

    def filter_dialog_oeffnen():
        sp_name = _sp_name()
        if sp_name is None:
            messagebox.showwarning("Feldfilter", "Bitte zuerst in eine Spalte klicken.", parent=parent_win)
            return
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        idx = _sp_idx()
        vorwert = ""
        if iid and idx is not None:
            w = tv_widget.item(iid, "values")
            vorwert = str(w[idx]) if idx < len(w) else ""
        dlg = tk.Toplevel(parent_win)
        dlg.title("Feldfilter setzen")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text=f"Filter für Spalte: {sp_name}", anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        entry = tk.Entry(dlg, width=40)
        entry.pack(padx=12, pady=(0, 8))
        entry.insert(0, vorwert)
        entry.select_range(0, "end")
        entry.focus_set()
        def ok():
            wert = entry.get()
            dlg.destroy()
            _filter_setzen(sp_name, wert)
        entry.bind("<Return>", lambda e: ok())
        tk.Button(dlg, text="Filter anwenden", command=ok).pack(pady=(0, 10))

    def filter_aufheben():
        tv_widget.delete(*tv_widget.get_children())
        for z in zeilen_ref["alle"]:
            tv_widget.insert("", "end", values=[str(v) if v is not None else "" for v in z])
        zeilen_ref.update({"filter_aktiv": False,
                           "filter_spalte": None, "filter_wert": None})

    def eindeutige_werte_anzeigen():
        sp_name = _sp_name()
        if sp_name is None:
            messagebox.showwarning("Eindeutige Feldwerte", "Bitte zuerst in eine Spalte klicken.", parent=parent_win)
            return
        alle = _alle_sp()
        try:
            idx = alle.index(sp_name)
        except ValueError:
            return
        items = list(tv_widget.get_children())
        rohdaten = [str(tv_widget.item(iid, "values")[idx])
                    if idx < len(tv_widget.item(iid, "values")) else ""
                    for iid in items]
        if not rohdaten:
            messagebox.showinfo("Eindeutige Feldwerte", "Keine Daten vorhanden.", parent=parent_win)
            return
        top_w = tk.Toplevel(parent_win)
        top_w.title(f"{G_EXE_Title} – Eindeutige Werte: {tabellenname}.{sp_name}")
        top_w.geometry("720x560")
        top_w.minsize(520, 380)
        fenster_registrieren(top_w, "Eindeutige Werte", top_w.title())
        haupt = tk.Frame(top_w, padx=10, pady=10)
        haupt.pack(fill="both", expand=True)
        haupt.grid_columnconfigure(0, weight=1)
        haupt.grid_rowconfigure(3, weight=1)
        basis_text = f"{tabellenname}.{sp_name}"
        if zeilen_ref.get("filter_aktiv") and zeilen_ref.get("filter_spalte"):
            basis_text += f"  |  Filter: {zeilen_ref['filter_spalte']} enthält '{zeilen_ref['filter_wert']}'"
        info_var = tk.StringVar()
        tk.Label(haupt, textvariable=info_var, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 4))
        pf = tk.Frame(haupt)
        pf.grid(row=1, column=0, sticky="w", pady=(0, 4))
        tk.Label(pf, text="Erste Zeichen (0 = alle):").pack(side="left")
        prefix_var = tk.IntVar(value=0)
        tk.Spinbox(pf, from_=0, to=9999, width=6, textvariable=prefix_var,
                   font=("TkDefaultFont", 13)).pack(side="left", padx=(4, 4))
        def _ph(): prefix_var.set(min(9999, prefix_var.get() + 1))
        def _pn(): prefix_var.set(max(0,    prefix_var.get() - 1))
        tk.Button(pf, text="▲", command=_ph, font=("TkDefaultFont", 11), width=2).pack(side="left", padx=(0, 2))
        tk.Button(pf, text="▼", command=_pn, font=("TkDefaultFont", 11), width=2).pack(side="left", padx=(0, 8))
        tk.Label(haupt, text=f"Basis: {basis_text}", anchor="w").grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tf2 = tk.Frame(haupt)
        tf2.grid(row=3, column=0, sticky="nsew")
        tf2.grid_rowconfigure(0, weight=1)
        tf2.grid_columnconfigure(0, weight=1)
        srt = {"spalte": "anzahl", "absteigend": True}
        akt = {"daten": []}
        wtv = ttk.Treeview(tf2, columns=("wert", "anzahl"), show="headings", selectmode="browse")
        wtv.column("wert", anchor="w", width=480)
        wtv.column("anzahl", anchor="e", width=120)
        wtv.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(tf2, orient="vertical",   command=wtv.yview).grid(row=0, column=1, sticky="ns")
        ttk.Scrollbar(tf2, orient="horizontal", command=wtv.xview).grid(row=1, column=0, sticky="ew")
        def _kopf(s, t):
            return t if srt.get("spalte") != s else f"{t} {'▼' if srt.get('absteigend') else '▲'}"
        def _fuellen(*_):
            try:
                p = prefix_var.get()
            except Exception:
                return
            zaehler = {}
            for w2 in rohdaten:
                key = w2[:p] if p > 0 else w2
                zaehler[key] = zaehler.get(key, 0) + 1
            daten = list(zaehler.items())
            if srt.get("spalte") == "wert":
                daten.sort(key=lambda e: e[0].lower(), reverse=srt.get("absteigend", False))
            else:
                daten.sort(key=lambda e: (e[1], e[0].lower()), reverse=srt.get("absteigend", True))
            akt["daten"] = daten
            p_info = f"    Prefix: {p} Zeichen" if p > 0 else ""
            info_var.set((f"Spalte: {sp_name}    Datensätze: {len(items):,}    "
                           f"unterschiedliche Werte: {len(daten):,}{p_info}").replace(",", "."))
            wtv.heading("wert",   text=_kopf("wert",   "Wert"), anchor="w",   command=lambda: _sort("wert"))
            wtv.heading("anzahl", text=_kopf("anzahl", "Anzahl"), anchor="w", command=lambda: _sort("anzahl"))
            wtv.delete(*wtv.get_children())
            for w2, anz in daten:
                wtv.insert("", "end", values=("(leer)" if w2 == "" else w2,
                                               f"{anz:,}".replace(",", ".")))
        def _sort(s):
            if srt.get("spalte") == s:
                srt["absteigend"] = not srt.get("absteigend", False)
            else:
                srt["spalte"] = s
                srt["absteigend"] = (s == "anzahl")
            _fuellen()
        def _wert_sel():
            sel = wtv.selection()
            if not sel:
                return None
            w2 = wtv.item(sel[0], "values")[0]
            return "" if w2 == "(leer)" else w2
        def _eindeutig_rk(event):
            iid2 = wtv.identify_row(event.y)
            if not iid2:
                return
            wtv.selection_set(iid2)
            w2 = _wert_sel()
            if w2 is None:
                return
            m2 = tk.Menu(top_w, tearoff=0)
            m2.add_command(label="Wert kopieren",
                           command=lambda: (top_w.clipboard_clear(), top_w.clipboard_append(w2)))
            m2.add_separator()
            m2.add_command(label="Als Filter anwenden",
                           command=lambda: _filter_setzen(sp_name, w2))
            try:
                m2.tk_popup(event.x_root, event.y_root)
            finally:
                m2.grab_release()
        wtv.bind("<Button-3>", _eindeutig_rk)
        wtv.bind("<Double-1>", lambda e: _filter_setzen(sp_name, _wert_sel()) if _wert_sel() is not None else None)
        prefix_var.trace_add("write", _fuellen)
        _fuellen()
        bf_e = tk.Frame(haupt)
        bf_e.grid(row=4, column=0, sticky="e", pady=(8, 0))
        def _wkopieren():
            ze = [f"Spalte\t{sp_name}", f"Basis\t{basis_text}", "", "Wert\tAnzahl"]
            for w2, anz in akt["daten"]:
                ze.append(f"{w2}\t{anz}")
            top_w.clipboard_clear()
            top_w.clipboard_append("\n".join(ze))
        tk.Button(bf_e, text="In Zwischenspeicher kopieren", command=_wkopieren).pack(side="right", padx=(8, 0))
        tk.Button(bf_e, text="Schließen", command=top_w.destroy, width=12).pack(side="right")

    # ── Block 4: IPv4 ────────────────────────────────────────────────────────
    def ip_vollstaendig_analysieren():
        """Erkennt den Typ des Feldinhalts (Integer, IPv4, CIDR, Range, Maske) automatisch
        und zeigt alle verfügbaren Informationen im Lesefenster an."""
        import re as _re
        iid = _lok["item"]
        idx = _sp_idx()
        if not iid or idx is None:
            messagebox.showwarning("IP analysieren",
                "Bitte zuerst eine Zelle auswählen.", parent=parent_win)
            return
        w  = tv_widget.item(iid, "values")
        fv = str(w[idx]).strip() if idx < len(w) else ""
        if not fv:
            messagebox.showwarning("IP analysieren", "Feldinhalt ist leer.", parent=parent_win)
            return

        # ── Hilfsfunktionen ──────────────────────────────────────────────────
        W = 24   # Breite der Bezeichner-Spalte

        def _i2ip(z):
            return (f"{(z>>24)&0xFF}.{(z>>16)&0xFF}"
                    f".{(z>>8)&0xFF}.{z&0xFF}")

        def _ip2i(ip):
            try:
                t = ip.strip().split(".")
                if len(t) != 4:
                    return None
                o = [int(x) for x in t]
                if any(x < 0 or x > 255 for x in o):
                    return None
                return (o[0]<<24)|(o[1]<<16)|(o[2]<<8)|o[3]
            except Exception:
                return None

        def _hex(z):
            return (f"0x{z:08X}"
                    f"  ({(z>>24)&0xFF:02X}.{(z>>16)&0xFF:02X}"
                    f".{(z>>8)&0xFF:02X}.{z&0xFF:02X})")

        def _bin(z):
            o = [(z>>24)&0xFF,(z>>16)&0xFF,(z>>8)&0xFF,z&0xFF]
            return ".".join(f"{x:08b}" for x in o)

        def _n(val):
            # Leerzeichen als Tausendertrennzeichen (kein Punkt – würde wie IP aussehen)
            return f"{val:,}".replace(",", " ")

        def _klasse(z):
            f0 = (z>>24)&0xFF
            if f0 < 128: return "A  (1.0.0.0 – 127.255.255.255)"
            if f0 < 192: return "B  (128.0.0.0 – 191.255.255.255)"
            if f0 < 224: return "C  (192.0.0.0 – 223.255.255.255)"
            if f0 < 240: return "D  (Multicast, 224.0.0.0 – 239.255.255.255)"
            return         "E  (Reserviert, 240.0.0.0 – 255.255.255.255)"

        def _typen(z):
            t = []
            if 0x0A000000 <= z <= 0x0AFFFFFF: t.append("Privat – RFC 1918  (10.0.0.0/8)")
            if 0xAC100000 <= z <= 0xAC1FFFFF: t.append("Privat – RFC 1918  (172.16.0.0/12)")
            if 0xC0A80000 <= z <= 0xC0A8FFFF: t.append("Privat – RFC 1918  (192.168.0.0/16)")
            if 0x7F000000 <= z <= 0x7FFFFFFF: t.append("Loopback  (127.0.0.0/8)")
            if 0xA9FE0000 <= z <= 0xA9FEFFFF: t.append("Link-Local / APIPA  (169.254.0.0/16)")
            if 0xE0000000 <= z <= 0xEFFFFFFF: t.append("Multicast  (224.0.0.0/4)")
            if 0xF0000000 <= z <= 0xFFFFFFFE: t.append("Reserviert  (240.0.0.0/4)")
            if z == 0xFFFFFFFF:               t.append("Limited Broadcast  (255.255.255.255)")
            if z == 0x00000000:               t.append("Unspezifiziert  (0.0.0.0)")
            if 0x64400000 <= z <= 0x647FFFFF: t.append("Shared Address Space – RFC 6598  (100.64.0.0/10)")
            if 0xC0000200 <= z <= 0xC00002FF: t.append("TEST-NET-1 – RFC 5737  (192.0.2.0/24)")
            if 0xC6336400 <= z <= 0xC63364FF: t.append("TEST-NET-2 – RFC 5737  (198.51.100.0/24)")
            if 0xCB007100 <= z <= 0xCB0071FF: t.append("TEST-NET-3 – RFC 5737  (203.0.113.0/24)")
            if not t:
                t.append("Öffentlich (Global Unicast)")
            return t

        def _valid_mask(z):
            if z == 0: return True
            inv = (~z) & 0xFFFFFFFF
            return (inv & (inv + 1)) == 0

        def _prefix_von_maske(z):
            return bin(z).count("1")

        def _netz_info(ip_i, prefix):
            maske = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix < 32 else 0xFFFFFFFF
            wild  = (~maske) & 0xFFFFFFFF
            netz  = ip_i & maske
            bc    = netz | wild
            total = bc - netz + 1
            hosts = total if prefix >= 31 else max(0, total - 2)
            eh    = netz + (0 if prefix == 32 else 1)
            lh    = bc   - (0 if prefix == 32 else 1)
            return {"maske": maske, "wild": wild, "netz": netz, "bc": bc,
                    "total": total, "hosts": hosts, "eh": eh, "lh": lh}

        SEP = "─" * 58

        def _rdns(ip_i):
            o = [(ip_i>>24)&0xFF,(ip_i>>16)&0xFF,(ip_i>>8)&0xFF,ip_i&0xFF]
            return f"{o[3]}.{o[2]}.{o[1]}.{o[0]}.in-addr.arpa"

        def _ip_zeilen(ip_i, label="IPv4-Adresse"):
            lines = [
                f"{label+':':{W}}{_i2ip(ip_i)}",
                f"{'Integer:':{W}}{_n(ip_i)}",
                f"{'Hexadezimal:':{W}}{_hex(ip_i)}",
                f"{'Binär (IP):':{W}}{_bin(ip_i)}",
                f"{'IP-Klasse:':{W}}{_klasse(ip_i)}",
            ]
            for typ in _typen(ip_i):
                lines.append(f"{'Typ:':{W}}{typ}")
            lines.append(f"{'Reverse-DNS:':{W}}{_rdns(ip_i)}")
            # Häufigstes Subnetz /24 als praktische Annahme (CIDR, nicht Classful)
            d24 = _netz_info(ip_i, 24)
            m24 = d24["maske"]
            w24 = d24["wild"]
            lines += [
                "",
                "Wahrscheinlichstes Subnetz (Annahme /24):",
                f"{'  Subnetzmaske:':{W}}{_i2ip(m24)}",
                f"{'  Maske Binär:':{W}}{_bin(m24)}",
                f"{'  Wildcard-Maske:':{W}}{_i2ip(w24)}",
                f"{'  Wildcard Binär:':{W}}{_bin(w24)}",
                f"{'  Netzadresse:':{W}}{_i2ip(d24['netz'])}",
                f"{'  Broadcast:':{W}}{_i2ip(d24['bc'])}",
                f"{'  Erster Host:':{W}}{_i2ip(d24['eh'])}",
                f"{'  Letzter Host:':{W}}{_i2ip(d24['lh'])}",
                f"{'  Nutzb. Hosts:':{W}}{_n(d24['hosts'])}",
            ]
            # Gängige Subnetz-Zugehörigkeiten – je nach IP-Typ angepasste Präfixe
            if 0x0A000000 <= ip_i <= 0x0AFFFFFF:          # 10/8 RFC 1918
                pf_liste = [(8,  "RFC 1918-Grenze (10.0.0.0/8)"),
                            (16, ""),
                            (24, "wahrscheinlichstes Subnetz"),
                            (32, "Host-Route")]
            elif 0xAC100000 <= ip_i <= 0xAC1FFFFF:        # 172.16/12 RFC 1918
                pf_liste = [(8,  ""),
                            (12, "RFC 1918-Grenze (172.16.0.0/12)"),
                            (16, ""),
                            (24, "wahrscheinlichstes Subnetz"),
                            (32, "Host-Route")]
            elif 0xC0A80000 <= ip_i <= 0xC0A8FFFF:        # 192.168/16 RFC 1918
                pf_liste = [(16, "RFC 1918-Grenze (192.168.0.0/16)"),
                            (24, "wahrscheinlichstes Subnetz"),
                            (32, "Host-Route")]
            else:                                          # Öffentlich / Sonstige
                pf_liste = [(8,  ""),
                            (16, ""),
                            (24, "wahrscheinlichstes Subnetz"),
                            (32, "Host-Route")]
            lines += ["", "Gängige Netze dieser IP:"]
            for pf, notiz in pf_liste:
                nd = _netz_info(ip_i, pf)
                notiz_str = f"   ← {notiz}" if notiz else ""
                lines.append(
                    f"  /{pf:<3}  Netz: {_i2ip(nd['netz']):<18}"
                    f"  Broadcast: {_i2ip(nd['bc']):<18}"
                    f"  Hosts: {_n(nd['hosts'])}{notiz_str}")
            return lines

        def _netz_zeilen(prefix, d):
            note = ""
            if prefix == 31: note = "  (point-to-point, RFC 3021)"
            if prefix == 32: note = "  (Host-Route)"
            hb = 32 - prefix
            return [
                f"{'Präfix-Länge:':{W}}/{prefix}{note}",
                f"{'Netz-Bits / Host-Bits:':{W}}{prefix} / {hb}",
                f"{'Subnetzmaske:':{W}}{_i2ip(d['maske'])}",
                f"{'Maske Hexadezimal:':{W}}{_hex(d['maske'])}",
                f"{'Maske Binär:':{W}}{_bin(d['maske'])}",
                f"{'Wildcard-Maske:':{W}}{_i2ip(d['wild'])}",
                f"{'Wildcard Hexadezimal:':{W}}{_hex(d['wild'])}",
                f"{'Wildcard Binär:':{W}}{_bin(d['wild'])}",
                f"{'Netzadresse:':{W}}{_i2ip(d['netz'])}  ({_n(d['netz'])})",
                f"{'Broadcast:':{W}}{_i2ip(d['bc'])}  ({_n(d['bc'])})",
                f"{'Erster Host:':{W}}{_i2ip(d['eh'])}",
                f"{'Letzter Host:':{W}}{_i2ip(d['lh'])}",
                f"{'Nutzb. Hosts:':{W}}{_n(d['hosts'])}",
                f"{'Gesamt-IPs:':{W}}{_n(d['total'])}",
            ]

        out = [f"Analyse:  {fv}", SEP]

        # ── 1. Reine Ganzzahl (kein Punkt im String) ──────────────────────────
        if not _re.search(r'\.', fv):
            try:
                val = int(fv.replace(" ", "").replace(",", ""))
                if 0 <= val <= 4294967295:
                    out += ["", "[ Als IPv4-Adresse ]"]
                    out += _ip_zeilen(val)
                    d32 = _netz_info(val, 32)
                    out += ["", "[ Als Host-Route (/32) ]"]
                    out += _netz_zeilen(32, d32)
                    sql_text_im_lesefenster_anzeigen(
                        parent_win, f"IP-Analyse: {fv}", "\n".join(out))
                    return
            except (ValueError, OverflowError):
                pass

        # ── 2. IP-Range  a.b.c.d – a.b.c.d ──────────────────────────────────
        rm = _re.match(
            r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[-–]\s*'
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', fv)
        if rm:
            si = _ip2i(rm.group(1))
            ei = _ip2i(rm.group(2))
            if si is not None and ei is not None and si <= ei:
                count = ei - si + 1
                out += ["", "[ IP-Range ]",
                        f"{'Start-IP:':{W}}{_i2ip(si)}",
                        f"{'Start Integer:':{W}}{_n(si)}",
                        f"{'Start Hexadezimal:':{W}}{_hex(si)}",
                        f"{'Start Binär:':{W}}{_bin(si)}",
                        f"{'End-IP:':{W}}{_i2ip(ei)}",
                        f"{'End Integer:':{W}}{_n(ei)}",
                        f"{'End Hexadezimal:':{W}}{_hex(ei)}",
                        f"{'End Binär:':{W}}{_bin(ei)}",
                        f"{'Anzahl IPs:':{W}}{_n(count)}",
                        ""]
                def _interpoliere(adj_s, adj_e):
                    """Prüft ob (adj_s, adj_e) ein sauberes ausgerichtetes Subnetz ergibt."""
                    if adj_s < 0 or adj_e > 0xFFFFFFFF:
                        return None
                    cnt2 = adj_e - adj_s + 1
                    if cnt2 <= 0 or (cnt2 & (cnt2 - 1)) != 0:
                        return None
                    pref2 = 32 - cnt2.bit_length() + 1
                    d2 = _netz_info(adj_s, pref2)
                    if d2["netz"] == adj_s and d2["bc"] == adj_e:
                        return pref2, d2
                    return None

                if count > 0 and (count & (count - 1)) == 0:
                    pref = 32 - count.bit_length() + 1
                    d = _netz_info(si, pref)
                    if d["netz"] == si and d["bc"] == ei:
                        out += ["[ Entspricht sauberem Subnetz ]",
                                f"{'CIDR:':{W}}{_i2ip(si)}/{pref}"]
                        out += _netz_zeilen(pref, d)
                    else:
                        out.append("Größe ist 2^n, aber nicht an Netzgrenze ausgerichtet.")
                        # Trotzdem Interpolation versuchen
                        count = -1   # erzwingt den Interpolationsblock unten
                if count <= 0 or (count & (count - 1)) != 0:
                    # Versuche Netzadresse / Broadcast zu ergänzen und Subnetz zu erkennen
                    interpoliert = False
                    pruef_kandidaten = [
                        (si - 1, ei + 1,
                         f"Netzadresse ({_i2ip(si - 1)}) und Broadcast ({_i2ip(ei + 1)}) ergänzt"),
                        (si - 1, ei,
                         f"Netzadresse ({_i2ip(si - 1)}) ergänzt"),
                        (si,     ei + 1,
                         f"Broadcast ({_i2ip(ei + 1)}) ergänzt"),
                    ]
                    for adj_s, adj_e, beschr in pruef_kandidaten:
                        res = _interpoliere(adj_s, adj_e)
                        if res:
                            pref2, d2 = res
                            out += [
                                f"[ Subnetz erkannt (interpoliert: {beschr}) ]",
                                f"{'CIDR:':{W}}{_i2ip(adj_s)}/{pref2}",
                            ]
                            out += _netz_zeilen(pref2, d2)
                            interpoliert = True
                            break
                    if not interpoliert:
                        out.append(
                            f"Kein Subnetz erkennbar – Größe {_n(count)} ergibt auch nach "
                            f"Ergänzung von Netzadresse/Broadcast kein ausgerichtetes Subnetz.")
                sql_text_im_lesefenster_anzeigen(
                    parent_win, f"IP-Analyse: {fv}", "\n".join(out))
                return

        # ── 3. CIDR  a.b.c.d/prefix ──────────────────────────────────────────
        cm = _re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/(\d{1,2})$', fv.strip())
        if cm:
            ip_i   = _ip2i(cm.group(1))
            prefix = int(cm.group(2))
            if ip_i is not None and 0 <= prefix <= 32:
                d = _netz_info(ip_i, prefix)
                out += ["", "[ CIDR-Netz ]"]
                out += _netz_zeilen(prefix, d)
                label = "Host-IP im Netz" if ip_i != d["netz"] else "Netzadresse"
                out += ["", f"[ {label}: {cm.group(1)} ]"]
                out += _ip_zeilen(ip_i)
                sql_text_im_lesefenster_anzeigen(
                    parent_win, f"IP-Analyse: {fv}", "\n".join(out))
                return

        # ── 4. Einfache IPv4-Adresse ──────────────────────────────────────────
        if _re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', fv.strip()):
            ip_i = _ip2i(fv.strip())
            if ip_i is not None:
                out += ["", "[ IPv4-Adresse ]"]
                out += _ip_zeilen(ip_i)
                if _valid_mask(ip_i):
                    pref   = _prefix_von_maske(ip_i)
                    wild_i = (~ip_i) & 0xFFFFFFFF
                    total  = 2 ** (32 - pref) if pref < 32 else 1
                    hosts  = max(0, total - 2) if pref < 31 else total
                    out += ["", "[ Mögliche Subnetzmaske ]",
                            f"{'CIDR-Präfix:':{W}}/{pref}",
                            f"{'Maske Binär:':{W}}{_bin(ip_i)}",
                            f"{'Wildcard-Maske:':{W}}{_i2ip(wild_i)}",
                            f"{'Wildcard Binär:':{W}}{_bin(wild_i)}",
                            f"{'Netzgröße:':{W}}{_n(total)} IPs  /  {_n(hosts)} nutzbare Hosts",
                            ]
                sql_text_im_lesefenster_anzeigen(
                    parent_win, f"IP-Analyse: {fv}", "\n".join(out))
                return

        # ── 5. Freier Text: alle eingebetteten IPs/CIDRs heraussuchen ─────────
        cidr_hits = _re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}', fv)
        ip_hits   = [x for x in _re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', fv)
                     if not any(x in c for c in cidr_hits)]
        if not cidr_hits and not ip_hits:
            messagebox.showwarning("IP analysieren",
                f"Kein erkennbarer IP-Wert gefunden in:\n'{fv}'", parent=parent_win)
            return
        for cidr in cidr_hits:
            cm2 = _re.match(r'^(.+)/(\d+)$', cidr)
            if not cm2: continue
            ip_i = _ip2i(cm2.group(1))
            pref = int(cm2.group(2))
            if ip_i is None or pref > 32: continue
            d = _netz_info(ip_i, pref)
            out += ["", f"[ CIDR: {cidr} ]"]
            out += _netz_zeilen(pref, d)
        for ip in ip_hits:
            ip_i = _ip2i(ip)
            if ip_i is None: continue
            out += ["", f"[ IP: {ip} ]"]
            out += _ip_zeilen(ip_i)
        sql_text_im_lesefenster_anzeigen(
            parent_win, f"IP-Analyse: {fv}", "\n".join(out))

    def ip_ueberschneidungen_suchen():
        """Liest alle Werte der angeklickten Spalte, parst IPv4/CIDR/Range/Integer
        und zeigt alle paarweisen Überschneidungen in einem eigenen Fenster."""
        import re as _re2
        idx = _sp_idx()
        if idx is None:
            messagebox.showwarning("IP-Überschneidungen",
                "Bitte zuerst in eine IP-Spalte klicken.", parent=parent_win)
            return
        alle_sp = _alle_sp()
        alle_iids = tv_widget.get_children()
        if not alle_iids:
            messagebox.showwarning("IP-Überschneidungen",
                "Keine Zeilen vorhanden.", parent=parent_win)
            return
        sp_name = _sp_name() or f"Spalte {idx + 1}"

        # ── Parse-Hilfsfunktionen ─────────────────────────────────────────────
        def _p_ip2i(ip):
            try:
                t = ip.strip().split(".")
                if len(t) != 4: return None
                o = [int(x) for x in t]
                if any(x < 0 or x > 255 for x in o): return None
                return (o[0]<<24)|(o[1]<<16)|(o[2]<<8)|o[3]
            except Exception:
                return None

        def _p_i2ip(z):
            return f"{(z>>24)&0xFF}.{(z>>16)&0xFF}.{(z>>8)&0xFF}.{z&0xFF}"

        def _p_netz(ip_i, pref):
            maske = (0xFFFFFFFF << (32 - pref)) & 0xFFFFFFFF if pref < 32 else 0xFFFFFFFF
            netz  = ip_i & maske
            bc    = netz | ((~maske) & 0xFFFFFFFF)
            return netz, bc

        def _parse_eintrag(fv):
            """Gibt (start_int, end_int) zurück oder None."""
            fv = fv.strip()
            if not fv: return None
            # CIDR
            cm = _re2.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/(\d{1,2})$', fv)
            if cm:
                ip_i = _p_ip2i(cm.group(1))
                pref = int(cm.group(2))
                if ip_i is not None and 0 <= pref <= 32:
                    return _p_netz(ip_i, pref)
            # Range
            rm = _re2.match(
                r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[-–]\s*'
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', fv)
            if rm:
                si = _p_ip2i(rm.group(1))
                ei = _p_ip2i(rm.group(2))
                if si is not None and ei is not None and si <= ei:
                    return si, ei
            # Plain IPv4
            if _re2.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', fv):
                ip_i = _p_ip2i(fv)
                if ip_i is not None:
                    return ip_i, ip_i
            # Integer
            if not _re2.search(r'\.', fv):
                try:
                    val = int(fv.replace(" ", "").replace(",", ""))
                    if 0 <= val <= 4294967295:
                        return val, val
                except (ValueError, OverflowError):
                    pass
            return None

        # ── Alle Spalteneinträge sammeln ──────────────────────────────────────
        eintraege = []   # (start_int, end_int, original_string, zeilennummer)
        nicht_erkannt = 0
        sp_pos = alle_sp.index(alle_sp[idx]) if idx < len(alle_sp) else idx
        for zn, iid in enumerate(alle_iids, start=1):
            werte = tv_widget.item(iid, "values")
            fv = str(werte[sp_pos]) if sp_pos < len(werte) else ""
            parsed = _parse_eintrag(fv)
            if parsed:
                eintraege.append((parsed[0], parsed[1], fv, zn))
            elif fv:
                nicht_erkannt += 1

        if len(eintraege) < 2:
            messagebox.showinfo("IP-Überschneidungen",
                f"Zu wenig erkannte IP-Einträge ({len(eintraege)}) für eine Analyse.\n"
                f"Nicht erkannt: {nicht_erkannt} Zeilen.", parent=parent_win)
            return

        # ── Sweep-Line: sortiert nach Start-IP, dann alle Paare prüfen ────────
        eintraege.sort(key=lambda x: x[0])
        ueberschneidungen = []   # (zn_a, str_a, zn_b, str_b, ol_start, ol_end, cnt)
        for i in range(len(eintraege)):
            s1, e1, d1, r1 = eintraege[i]
            for j in range(i + 1, len(eintraege)):
                s2, e2, d2, r2 = eintraege[j]
                if s2 > e1:
                    break   # Sortiert → keine weiteren Überschneidungen für i möglich
                ol_s = max(s1, s2)
                ol_e = min(e1, e2)
                ueberschneidungen.append(
                    (r1, d1, r2, d2,
                     _p_i2ip(ol_s), _p_i2ip(ol_e), ol_e - ol_s + 1))

        # ── Ergebnisfenster ───────────────────────────────────────────────────
        win = tk.Toplevel(parent_win)
        win.title(f"IP-Überschneidungen – {sp_name}")
        win.geometry("1020x520")
        win.minsize(640, 300)
        fenster_registrieren(win, "IP-Überschneidungen")

        n_ue  = len(ueberschneidungen)
        n_erk = len(eintraege)
        farbe = "green" if n_ue == 0 else "red"
        status = "✓  Keine Überschneidungen gefunden." if n_ue == 0 else \
                 f"⚠  {n_ue} Überschneidung(en) gefunden!"
        info = (f"Spalte: {sp_name}   ·   "
                f"Erkannte Einträge: {n_erk}   ·   "
                f"Nicht erkannt: {nicht_erkannt}   ·   "
                f"Überschneidungen: {n_ue}")
        tk.Label(win, text=info, anchor="w", padx=8, pady=3).pack(fill="x")
        tk.Label(win, text=status, anchor="w", padx=8, pady=2,
                 fg=farbe, font=("TkDefaultFont", 10, "bold")).pack(fill="x")

        if n_ue == 0:
            tk.Button(win, text="Schließen", command=win.destroy,
                      width=12).pack(pady=12)
            return

        frm = tk.Frame(win)
        frm.pack(fill="both", expand=True, padx=6, pady=(4, 0))
        frm.grid_rowconfigure(0, weight=1)
        frm.grid_columnconfigure(0, weight=1)

        cols = ("z_a", "eintrag_a", "z_b", "eintrag_b", "ol_start", "ol_end", "anz")
        tv2 = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        tv2.heading("z_a",      text="Zeile A",           anchor="w", command=lambda: _tv_sortieren(tv2, "z_a"))
        tv2.heading("eintrag_a", text="Eintrag A",         anchor="w", command=lambda: _tv_sortieren(tv2, "eintrag_a"))
        tv2.heading("z_b",      text="Zeile B",           anchor="w", command=lambda: _tv_sortieren(tv2, "z_b"))
        tv2.heading("eintrag_b", text="Eintrag B",         anchor="w", command=lambda: _tv_sortieren(tv2, "eintrag_b"))
        tv2.heading("ol_start",  text="Überschn. Start",  anchor="w", command=lambda: _tv_sortieren(tv2, "ol_start"))
        tv2.heading("ol_end",    text="Überschn. End",    anchor="w", command=lambda: _tv_sortieren(tv2, "ol_end"))
        tv2.heading("anz",       text="Anzahl IPs",        anchor="w", command=lambda: _tv_sortieren(tv2, "anz"))
        tv2.column("z_a",       width=60,  anchor="e")
        tv2.column("eintrag_a", width=180, anchor="w")
        tv2.column("z_b",       width=60,  anchor="e")
        tv2.column("eintrag_b", width=180, anchor="w")
        tv2.column("ol_start",  width=130, anchor="w")
        tv2.column("ol_end",    width=130, anchor="w")
        tv2.column("anz",       width=80,  anchor="e")
        vsb2 = ttk.Scrollbar(frm, orient="vertical",   command=tv2.yview)
        hsb2 = ttk.Scrollbar(frm, orient="horizontal", command=tv2.xview)
        tv2.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        tv2.grid(row=0, column=0, sticky="nsew")
        vsb2.grid(row=0, column=1, sticky="ns")
        hsb2.grid(row=1, column=0, sticky="ew")

        for r1, d1, r2, d2, ol_s, ol_e, cnt in ueberschneidungen:
            tv2.insert("", "end", values=(r1, d1, r2, d2, ol_s, ol_e, cnt))
        tree_spalten_breiten_anpassen(tv2)

        btn_frm = tk.Frame(win)
        btn_frm.pack(fill="x", padx=6, pady=6)

        def _kopieren():
            zeilen = ["Zeile A\tEintrag A\tZeile B\tEintrag B\t"
                      "Überschn. Start\tÜberschn. End\tAnzahl IPs"]
            for r1, d1, r2, d2, ol_s, ol_e, cnt in ueberschneidungen:
                zeilen.append(f"{r1}\t{d1}\t{r2}\t{d2}\t{ol_s}\t{ol_e}\t{cnt}")
            win.clipboard_clear()
            win.clipboard_append("\n".join(zeilen))
            messagebox.showinfo("Kopiert",
                f"{n_ue} Zeilen in Zwischenablage kopiert.", parent=win)

        tk.Button(btn_frm, text="Ergebnisse kopieren", command=_kopieren).pack(side="left")
        tk.Button(btn_frm, text="Schließen", command=win.destroy,
                  width=12).pack(side="right")

    def ip_ueberschneidungen_in_kette_suchen():
        """Sucht IP-Überschneidungen über eine definierte Kettenbeziehung (IpSuchFeld).
        Liest die Kette aus zzz_Relationen, baut SQL-JOINs und gruppiert nach Quellfeld."""
        import re as _re3
        import json as _json3

        _TAB_REL = "zzz_Relationen"
        _TAB_ANA = "zzz_Ketten_Analyse"
        _TAB_DET = "zzz_Ketten_Analyse_Details"

        # ── 1. DB + ausgewähltes Projekt prüfen ───────────────────────────────
        if not db_ist_geladen():
            messagebox.showwarning("Überschneidungen in Kette",
                "Es ist keine Datenbank geladen.", parent=parent_win)
            return
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            messagebox.showwarning("Überschneidungen in Kette",
                "Kein Projekt ausgewählt. Bitte zuerst ein Projekt auswählen.",
                parent=parent_win)
            return

        # ── 2. Kettenbeziehungen mit IpSuchFeld laden ─────────────────────────
        try:
            _vb0 = sqlite_verbindung_oeffnen()
            _vb0.execute(
                f"ALTER TABLE {sql_identifier(_TAB_REL)} ADD COLUMN IpSuchFeld TEXT"
            )
            _vb0.commit()
        except Exception:
            pass
        try:
            _vb0.close()
        except Exception:
            pass

        try:
            vb = sqlite_verbindung_oeffnen()
            ketten_rows = vb.execute(
                f"SELECT id, Bezeichnung, QuellTabelle, QuellFeld, Kette, IpSuchFeld "
                f"FROM {sql_identifier(_TAB_REL)} "
                f"WHERE Projekt=? AND Typ='Kette' "
                f"AND IpSuchFeld IS NOT NULL AND IpSuchFeld != '' "
                f"ORDER BY Reihenfolge, id",
                (pname,)
            ).fetchall()
            vb.close()
        except Exception as e:
            messagebox.showerror("Überschneidungen in Kette",
                f"Fehler beim Laden der Beziehungen:\n{e}", parent=parent_win)
            return

        if not ketten_rows:
            messagebox.showinfo("Überschneidungen in Kette",
                f"Für Projekt '{pname}' sind keine Kettenbeziehungen mit IP-Suchfeld definiert.\n\n"
                f"Bitte im Beziehungsfenster (Rechtsklick → Tabellenbeziehungen) eine\n"
                f"Kettenbeziehung anlegen und ein IP-Suchfeld festlegen.",
                parent=parent_win)
            return

        # ── 3. Beziehung auswählen (falls mehrere) ────────────────────────────
        if len(ketten_rows) == 1:
            rel_row = ketten_rows[0]
        else:
            dlg_sel = tk.Toplevel(parent_win)
            dlg_sel.title("Kettenbeziehung auswählen")
            dlg_sel.geometry("560x260")
            dlg_sel.resizable(True, False)
            dlg_sel.grab_set()
            dlg_sel.transient(parent_win)
            dlg_sel.columnconfigure(0, weight=1)
            tk.Label(dlg_sel,
                     text="Mehrere Kettenbeziehungen mit IP-Suchfeld vorhanden. Bitte eine auswählen:",
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
            sc_cols = ("bez", "qt", "qf", "ip")
            sc_tv = ttk.Treeview(dlg_sel, columns=sc_cols, show="headings",
                                 selectmode="browse",
                                 height=min(len(ketten_rows), 7))
            sc_tv.heading("bez", text="Bezeichnung",  anchor="w", command=lambda: _tv_sortieren(sc_tv, "bez"))
            sc_tv.heading("qt",  text="Quelltabelle", anchor="w", command=lambda: _tv_sortieren(sc_tv, "qt"))
            sc_tv.heading("qf",  text="Quellfeld",    anchor="w", command=lambda: _tv_sortieren(sc_tv, "qf"))
            sc_tv.heading("ip",  text="IP-Suchfeld",  anchor="w", command=lambda: _tv_sortieren(sc_tv, "ip"))
            sc_tv.column("bez",  width=200, anchor="w")
            sc_tv.column("qt",   width=130, anchor="w")
            sc_tv.column("qf",   width=110, anchor="w")
            sc_tv.column("ip",   width=110, anchor="w")
            sc_tv.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
            for r in ketten_rows:
                sc_tv.insert("", "end", iid=str(r[0]),
                             values=(r[1] or "", r[2] or "", r[3] or "", r[5] or ""))
            sc_tv.selection_set(str(ketten_rows[0][0]))
            chosen = [None]
            def _ok_sel():
                sel = sc_tv.selection()
                if sel:
                    rid = int(sel[0])
                    chosen[0] = next((r for r in ketten_rows if r[0] == rid), None)
                dlg_sel.destroy()
            bf_sel = tk.Frame(dlg_sel)
            bf_sel.grid(row=2, column=0, pady=(0, 12))
            tk.Button(bf_sel, text="Analysieren", width=12, command=_ok_sel).pack(
                side="right", padx=(8, 12))
            tk.Button(bf_sel, text="Abbrechen",   width=10,
                      command=dlg_sel.destroy).pack(side="right")
            sc_tv.bind("<Double-1>", lambda e: _ok_sel())
            dlg_sel.bind("<Return>",  lambda e: _ok_sel())
            dlg_sel.wait_window()
            if chosen[0] is None:
                return
            rel_row = chosen[0]

        rel_id, bez_titel, qt, qf, kette_json, ip_feld = rel_row
        rel_id_str = str(rel_id)

        # ── 4. Kette parsen ───────────────────────────────────────────────────
        try:
            kette_alle = _json3.loads(kette_json) if kette_json else []
        except Exception:
            kette_alle = []
        aktive_schritte = [s for s in kette_alle if s.get("aktiv", True)]
        if not aktive_schritte:
            messagebox.showwarning("Überschneidungen in Kette",
                f"Beziehung '{bez_titel}' hat keine aktiven Schritte.",
                parent=parent_win)
            return

        # ── 5. SQL-Abfrage mit JOIN-Kette ─────────────────────────────────────
        n_schr  = len(aktive_schritte)
        aliases = [f"_ks{i}" for i in range(n_schr + 1)]
        joins_sql = " ".join(
            f"LEFT JOIN {sql_identifier(s['zu_tab'])} {aliases[i+1]} "
            f"ON {aliases[i+1]}.{sql_identifier(s['zu_feld'])} "
            f"= {aliases[i]}.{sql_identifier(s['von_feld'])}"
            for i, s in enumerate(aktive_schritte)
        )
        letzter_alias = aliases[n_schr]
        # ip_feld kann "Tabelle.Feld" (neu) oder "Feld" (alt, letzte Tabelle) sein
        if "." in ip_feld:
            _ip_tab_name, _ip_feld_name = ip_feld.split(".", 1)
            _ip_alias = aliases[0] if _ip_tab_name == qt else None
            for _ji, _js in enumerate(aktive_schritte):
                if _js["zu_tab"] == _ip_tab_name:
                    _ip_alias = aliases[_ji + 1]
                    break
            if _ip_alias is None:
                _ip_alias = letzter_alias
        else:
            _ip_alias     = letzter_alias
            _ip_feld_name = ip_feld
        # DisplayName auto-erkennen (PRAGMA auf ip_feld-Tabelle)
        _disp_feld_sql  = ""
        _disp_feld_name = None
        _prio_kw_disp   = ("display", "name", "bezeichn", "label", "titel", "title")
        try:
            _pr_disp_tab = _ip_tab_name if "." in ip_feld else (
                aktive_schritte[-1]["zu_tab"] if aktive_schritte else qt)
            _pr_disp_alias = _ip_alias
            _vb_dpr = sqlite_verbindung_oeffnen()
            _pr_disp_rows = _vb_dpr.execute(
                "PRAGMA table_info(" + sql_identifier(_pr_disp_tab) + ")"
            ).fetchall()
            _vb_dpr.close()
            for _pr_d in _pr_disp_rows:
                _pf_d = _pr_d[1]
                if _pf_d == _ip_feld_name:
                    continue
                if any(_kw in _pf_d.lower() for _kw in _prio_kw_disp):
                    _disp_feld_name = _pf_d
                    _disp_feld_sql  = (
                        f", {_pr_disp_alias}.{sql_identifier(_pf_d)} AS disp_wert"
                    )
                    break
        except Exception:
            pass

        sql_ana = (
            f"SELECT {aliases[0]}.{sql_identifier(qf)} AS gruppe, "
            f"{_ip_alias}.{sql_identifier(_ip_feld_name)} AS ip_wert"
            f"{_disp_feld_sql} "
            f"FROM {sql_identifier(qt)} {aliases[0]} "
            f"{joins_sql}"
        )
        try:
            vb2 = sqlite_verbindung_oeffnen()
            db_zeilen = vb2.execute(sql_ana).fetchall()
            vb2.close()
        except Exception as e:
            messagebox.showerror("Überschneidungen in Kette",
                f"Fehler bei der DB-Abfrage:\n{e}\n\nSQL:\n{sql_ana}",
                parent=parent_win)
            return

        # ── 6. IP-Hilfsfunktionen ─────────────────────────────────────────────
        def _k_ip2i(ip):
            try:
                t = ip.strip().split(".")
                if len(t) != 4: return None
                o = [int(x) for x in t]
                if any(x < 0 or x > 255 for x in o): return None
                return (o[0]<<24)|(o[1]<<16)|(o[2]<<8)|o[3]
            except Exception:
                return None

        def _k_i2ip(z):
            return f"{(z>>24)&0xFF}.{(z>>16)&0xFF}.{(z>>8)&0xFF}.{z&0xFF}"

        def _k_parse(fv):
            fv = fv.strip()
            if not fv: return None
            cm = _re3.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/(\d{1,2})$', fv)
            if cm:
                ip_i = _k_ip2i(cm.group(1))
                pref = int(cm.group(2))
                if ip_i is not None and 0 <= pref <= 32:
                    maske = (0xFFFFFFFF << (32 - pref)) & 0xFFFFFFFF if pref < 32 else 0xFFFFFFFF
                    netz  = ip_i & maske
                    return netz, netz | ((~maske) & 0xFFFFFFFF)
            rm = _re3.match(
                r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[-–]\s*'
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', fv)
            if rm:
                si = _k_ip2i(rm.group(1))
                ei = _k_ip2i(rm.group(2))
                if si is not None and ei is not None and si <= ei:
                    return si, ei
            if _re3.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', fv):
                ip_i = _k_ip2i(fv)
                if ip_i is not None: return ip_i, ip_i
            if not _re3.search(r'\.', fv):
                try:
                    val = int(fv.replace(" ", "").replace(",", ""))
                    if 0 <= val <= 4294967295: return val, val
                except (ValueError, OverflowError):
                    pass
            return None

        def _sweep(eintraege_roh):
            """eintraege_roh: [(zn, ip_str), ...]  →  Liste Überschneidungs-Tupel."""
            parsed = []
            for zn, roh in eintraege_roh:
                r = _k_parse(roh)
                if r:
                    parsed.append((r[0], r[1], zn, roh))
            parsed.sort(key=lambda x: x[0])
            ue = []
            for i in range(len(parsed)):
                s1, e1, r1, d1 = parsed[i]
                for j in range(i + 1, len(parsed)):
                    s2, e2, r2, d2 = parsed[j]
                    if s2 > e1: break
                    ol_s = s2
                    ol_e = min(e1, e2)
                    ue.append((r1, d1, r2, d2, _k_i2ip(ol_s), _k_i2ip(ol_e), ol_e - ol_s + 1))
            return ue

        # ── 7. Gruppen aus DB-Zeilen aufbauen ────────────────────────────────────
        gruppen = {}
        _zn_zu_disp = {}   # zn → DisplayName-String
        for zn, row in enumerate(db_zeilen, 1):
            gw_raw = row[0]
            iw_raw = row[1]
            gw = str(gw_raw) if gw_raw is not None else "(leer)"
            iw = str(iw_raw) if iw_raw is not None else ""
            if gw not in gruppen:
                gruppen[gw] = []
            gruppen[gw].append((zn, iw))
            if len(row) > 2 and row[2] is not None:
                _zn_zu_disp[zn] = str(row[2])

        # ── 8. Sweep je Gruppe ────────────────────────────────────────────────
        gruppen_info = []    # [(grp_wert, n_ips, n_ue, details_list), ...]
        for gw, eintr in gruppen.items():
            details = _sweep(eintr)
            gruppen_info.append((gw, len(eintr), len(details), details))
        gruppen_info.sort(key=lambda x: (-x[2], str(x[0]).lower()))

        # Alle Zeilennummern die an mind. einer Überschneidung beteiligt sind
        _overlap_zns = set()
        for _gw_ov, _ni_ov, _nu_ov, _det_ov in gruppen_info:
            for _r1_ov, _d1_ov, _r2_ov, _d2_ov, *_ in _det_ov:
                _overlap_zns.add(_r1_ov)
                _overlap_zns.add(_r2_ov)

        gesamt_ue   = sum(g[2] for g in gruppen_info)
        n_mit_ue    = sum(1    for g in gruppen_info if g[2] > 0)
        n_gesamt_ip = sum(g[1] for g in gruppen_info)
        n_gruppen   = len(gruppen_info)

        # ── 9. Analyse-Tabellen sicherstellen (für "In DB speichern") ─────────
        def _analyse_tabellen_sicherstellen():
            try:
                vb_at = sqlite_verbindung_oeffnen()
                vb_at.execute(
                    f"CREATE TABLE IF NOT EXISTS {sql_identifier(_TAB_ANA)} ("
                    f"id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    f"datetime TEXT NOT NULL, "
                    f"Projekt TEXT NOT NULL, "
                    f"RelationID INTEGER, "
                    f"Bezeichnung TEXT, "
                    f"QuellTabelle TEXT, "
                    f"QuellFeld TEXT, "
                    f"LetzteTabelle TEXT, "
                    f"IpSuchFeld TEXT, "
                    f"AnzahlGruppen INTEGER DEFAULT 0, "
                    f"AnzahlUeberschneidungen INTEGER DEFAULT 0)"
                )
                vb_at.execute(
                    f"CREATE TABLE IF NOT EXISTS {sql_identifier(_TAB_DET)} ("
                    f"id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    f"analyse_id INTEGER NOT NULL, "
                    f"Gruppe TEXT, "
                    f"EintragA TEXT, "
                    f"EintragB TEXT, "
                    f"UeberschneidungStart TEXT, "
                    f"UeberschneidungEnde TEXT, "
                    f"AnzahlIPs INTEGER DEFAULT 0)"
                )
                vb_at.commit()
                vb_at.close()
                return True
            except Exception:
                return False

        def _analyse_in_db_speichern():
            if not _analyse_tabellen_sicherstellen():
                messagebox.showerror("In DB speichern",
                    "Fehler beim Anlegen der Analyse-Tabellen.", parent=win2)
                return
            from datetime import datetime as _dt_ana
            jetzt = _dt_ana.now().strftime("%Y-%m-%d %H:%M:%S")
            letzte_tab_ana = aktive_schritte[-1]["zu_tab"] if aktive_schritte else ""
            try:
                vb_s = sqlite_verbindung_oeffnen()
                cur_s = vb_s.cursor()
                cur_s.execute(
                    f"INSERT INTO {sql_identifier(_TAB_ANA)} "
                    f"(datetime, Projekt, RelationID, Bezeichnung, QuellTabelle, QuellFeld, "
                    f"LetzteTabelle, IpSuchFeld, AnzahlGruppen, AnzahlUeberschneidungen) "
                    f"VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (jetzt, pname, rel_id, bez_titel, qt, qf,
                     letzte_tab_ana, ip_feld, n_gruppen, gesamt_ue)
                )
                ana_id = cur_s.lastrowid
                for gw_d, _, _, det_d in gruppen_info:
                    for r1_d, d1_d, r2_d, d2_d, ol_s_d, ol_e_d, cnt_d in det_d:
                        cur_s.execute(
                            f"INSERT INTO {sql_identifier(_TAB_DET)} "
                            f"(analyse_id, Gruppe, EintragA, EintragB, "
                            f"UeberschneidungStart, UeberschneidungEnde, AnzahlIPs) "
                            f"VALUES (?,?,?,?,?,?,?)",
                            (ana_id, gw_d, d1_d, d2_d, ol_s_d, ol_e_d, cnt_d)
                        )
                vb_s.commit()
                vb_s.close()
            except Exception as e:
                messagebox.showerror("In DB speichern",
                    f"Fehler beim Speichern:\n{e}", parent=win2)
                return
            n_det = sum(len(g[3]) for g in gruppen_info)
            antwort = messagebox.askyesno("Gespeichert",
                f"Analyse gespeichert ({n_gruppen} Gruppen, {n_det} Überschneidungspaare).\n\n"
                f"Frühere Analysen ansehen?", parent=win2)
            if antwort:
                _analyse_browsen()

        def _analyse_browsen():
            """Zeigt alle gespeicherten Analysen für das aktive Projekt."""
            if not _analyse_tabellen_sicherstellen():
                return
            bwin = tk.Toplevel(win2)
            bwin.title(f"{G_EXE_Title} – Ketten-Analysen: {pname}")
            bwin.geometry("1060x580")
            bwin.minsize(700, 400)
            fenster_registrieren(bwin, "Ketten-Analysen", bwin.title())
            bwin.columnconfigure(0, weight=1)
            bwin.rowconfigure(1, weight=2)
            bwin.rowconfigure(3, weight=3)

            tk.Label(bwin, text=f"Gespeicherte Analysen – Projekt: {pname}",
                     anchor="w", font=("Segoe UI", 9, "bold"),
                     padx=8, pady=4).grid(row=0, column=0, sticky="ew")

            # Oberes Panel: Analyse-Läufe
            frm_b_oben = tk.Frame(bwin)
            frm_b_oben.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
            frm_b_oben.rowconfigure(0, weight=1)
            frm_b_oben.columnconfigure(0, weight=1)
            a_cols = ("dt", "bez", "qt", "qf", "ip", "gruppen", "ue")
            a_tv = ttk.Treeview(frm_b_oben, columns=a_cols, show="headings",
                                selectmode="browse")
            a_tv.heading("dt",      text="Zeitpunkt",        anchor="w", command=lambda: _tv_sortieren(a_tv, "dt"))
            a_tv.heading("bez",     text="Bezeichnung",      anchor="w", command=lambda: _tv_sortieren(a_tv, "bez"))
            a_tv.heading("qt",      text="Quelltabelle",     anchor="w", command=lambda: _tv_sortieren(a_tv, "qt"))
            a_tv.heading("qf",      text="Quellfeld",        anchor="w", command=lambda: _tv_sortieren(a_tv, "qf"))
            a_tv.heading("ip",      text="IP-Suchfeld",      anchor="w", command=lambda: _tv_sortieren(a_tv, "ip"))
            a_tv.heading("gruppen", text="Gruppen",          anchor="w", command=lambda: _tv_sortieren(a_tv, "gruppen"))
            a_tv.heading("ue",      text="Überschneidungen", anchor="w", command=lambda: _tv_sortieren(a_tv, "ue"))
            a_tv.column("dt",       width=140, anchor="w")
            a_tv.column("bez",      width=170, anchor="w")
            a_tv.column("qt",       width=120, anchor="w")
            a_tv.column("qf",       width=100, anchor="w")
            a_tv.column("ip",       width=100, anchor="w")
            a_tv.column("gruppen",  width=70,  anchor="e")
            a_tv.column("ue",       width=110, anchor="e")
            ttk.Scrollbar(frm_b_oben, orient="vertical",
                          command=a_tv.yview).grid(row=0, column=1, sticky="ns")
            ttk.Scrollbar(frm_b_oben, orient="horizontal",
                          command=a_tv.xview).grid(row=1, column=0, sticky="ew")
            a_tv.grid(row=0, column=0, sticky="nsew")

            tk.Label(bwin, text="Details der gewählten Analyse:",
                     anchor="w", padx=8).grid(row=2, column=0, sticky="ew")

            frm_b_unten = tk.Frame(bwin)
            frm_b_unten.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 4))
            frm_b_unten.rowconfigure(0, weight=1)
            frm_b_unten.columnconfigure(0, weight=1)
            bd_cols = ("gruppe", "ea", "eb", "ol_s", "ol_e", "cnt")
            bd_tv = ttk.Treeview(frm_b_unten, columns=bd_cols, show="headings",
                                 selectmode="browse")
            bd_tv.heading("gruppe", text="Gruppe",            anchor="w", command=lambda: _tv_sortieren(bd_tv, "gruppe"))
            bd_tv.heading("ea",     text="Eintrag A",         anchor="w", command=lambda: _tv_sortieren(bd_tv, "ea"))
            bd_tv.heading("eb",     text="Eintrag B",         anchor="w", command=lambda: _tv_sortieren(bd_tv, "eb"))
            bd_tv.heading("ol_s",   text="Überschn. Start",   anchor="w", command=lambda: _tv_sortieren(bd_tv, "ol_s"))
            bd_tv.heading("ol_e",   text="Überschn. Ende",    anchor="w", command=lambda: _tv_sortieren(bd_tv, "ol_e"))
            bd_tv.heading("cnt",    text="Anzahl IPs",        anchor="w", command=lambda: _tv_sortieren(bd_tv, "cnt"))
            bd_tv.column("gruppe",  width=220, anchor="w")
            bd_tv.column("ea",      width=170, anchor="w")
            bd_tv.column("eb",      width=170, anchor="w")
            bd_tv.column("ol_s",    width=120, anchor="w")
            bd_tv.column("ol_e",    width=120, anchor="w")
            bd_tv.column("cnt",     width=80,  anchor="e")
            ttk.Scrollbar(frm_b_unten, orient="vertical",
                          command=bd_tv.yview).grid(row=0, column=1, sticky="ns")
            ttk.Scrollbar(frm_b_unten, orient="horizontal",
                          command=bd_tv.xview).grid(row=1, column=0, sticky="ew")
            bd_tv.grid(row=0, column=0, sticky="nsew")

            def _b_laden():
                a_tv.delete(*a_tv.get_children())
                try:
                    vb_b = sqlite_verbindung_oeffnen()
                    a_rows = vb_b.execute(
                        f"SELECT id, datetime, Bezeichnung, QuellTabelle, QuellFeld, "
                        f"IpSuchFeld, AnzahlGruppen, AnzahlUeberschneidungen "
                        f"FROM {sql_identifier(_TAB_ANA)} "
                        f"WHERE Projekt=? ORDER BY id DESC",
                        (pname,)
                    ).fetchall()
                    vb_b.close()
                except Exception:
                    a_rows = []
                for r in a_rows:
                    a_tv.insert("", "end", iid=str(r[0]),
                                values=(r[1], r[2] or "", r[3] or "",
                                        r[4] or "", r[5] or "", r[6], r[7]))
                if a_rows:
                    a_tv.selection_set(str(a_rows[0][0]))
                    _b_details_zeigen()

            def _b_details_zeigen(event=None):
                sel = a_tv.selection()
                bd_tv.delete(*bd_tv.get_children())
                if not sel:
                    return
                ana_id_b = int(sel[0])
                try:
                    vb_bd = sqlite_verbindung_oeffnen()
                    det_rows = vb_bd.execute(
                        f"SELECT Gruppe, EintragA, EintragB, "
                        f"UeberschneidungStart, UeberschneidungEnde, AnzahlIPs "
                        f"FROM {sql_identifier(_TAB_DET)} "
                        f"WHERE analyse_id=? ORDER BY Gruppe, id",
                        (ana_id_b,)
                    ).fetchall()
                    vb_bd.close()
                except Exception:
                    det_rows = []
                for dr in det_rows:
                    bd_tv.insert("", "end",
                                 values=(dr[0] or "", dr[1] or "", dr[2] or "",
                                         dr[3] or "", dr[4] or "", dr[5]))
                if det_rows:
                    tree_spalten_breiten_anpassen(bd_tv)

            def _b_loeschen():
                sel = a_tv.selection()
                if not sel:
                    return
                if not messagebox.askyesno("Löschen",
                        "Gewählte Analyse und ihre Details löschen?", parent=bwin):
                    return
                ana_id_del = int(sel[0])
                try:
                    vb_del = sqlite_verbindung_oeffnen()
                    vb_del.execute(
                        f"DELETE FROM {sql_identifier(_TAB_DET)} WHERE analyse_id=?",
                        (ana_id_del,))
                    vb_del.execute(
                        f"DELETE FROM {sql_identifier(_TAB_ANA)} WHERE id=?",
                        (ana_id_del,))
                    vb_del.commit()
                    vb_del.close()
                except Exception as e:
                    messagebox.showerror("Löschen", f"Fehler:\n{e}", parent=bwin)
                    return
                _b_laden()

            a_tv.bind("<<TreeviewSelect>>", _b_details_zeigen)
            btn_b = tk.Frame(bwin, padx=8, pady=6)
            btn_b.grid(row=4, column=0, sticky="ew")
            tk.Button(btn_b, text="Aktualisieren", width=12,
                      command=_b_laden).pack(side="left", padx=(0, 6))
            tk.Button(btn_b, text="Analyse löschen", width=14,
                      command=_b_loeschen).pack(side="left")
            tk.Button(btn_b, text="Schließen", width=10,
                      command=bwin.destroy).pack(side="right")
            _b_laden()

        # ── 10. Ergebnisfenster ───────────────────────────────────────────────
        ketten_pfad = " → ".join(
            [f"{qt}.{qf}"]
            + [f"{s['zu_tab']}.{s['zu_feld']}" for s in aktive_schritte[:-1]]
            + ([f"{aktive_schritte[-1]['zu_tab']}.{ip_feld}"] if aktive_schritte else [])
        )

        # Gruppenname aus Quelltabelle auto-erkennen
        _gw_zu_name    = {}
        _grp_name_feld = None
        _prio_kw_grp   = ("name", "bezeichn", "label", "titel", "title", "display")
        try:
            _vb_gn = sqlite_verbindung_oeffnen()
            _pr_qt = _vb_gn.execute(
                f"PRAGMA table_info({sql_identifier(qt)})"
            ).fetchall()
            for _pr_q in _pr_qt:
                _pf_q = _pr_q[1]
                if _pf_q.lower() == qf.lower():
                    continue
                if any(_kw in _pf_q.lower() for _kw in _prio_kw_grp):
                    _grp_name_feld = _pf_q
                    break
            if _grp_name_feld:
                for _gnr in _vb_gn.execute(
                    f"SELECT DISTINCT {sql_identifier(qf)}, "
                    f"{sql_identifier(_grp_name_feld)} FROM {sql_identifier(qt)}"
                ).fetchall():
                    if _gnr[0] is not None:
                        _gw_zu_name[str(_gnr[0])] = (
                            str(_gnr[1]) if _gnr[1] is not None else "")
            _vb_gn.close()
        except Exception:
            pass

        win2 = tk.Toplevel(parent_win)
        win2.title(
            f"{G_EXE_Title} – Überschneidungen in Kette: "
            f"{bez_titel}  [{qf}] → [{ip_feld}]")
        win2.geometry("1560x720")
        win2.minsize(900, 480)

        fenster_registrieren(win2, "Überschneidungen Kette", win2.title())
        _win2_menue = fenster_standard_menue_anbringen(
            win2, "1560x720", "Überschneidungen Kette")
        win2.title(
            f"{G_EXE_Title} – Überschneidungen in Kette: "
            f"{bez_titel}  [{qf}] → [{ip_feld}]")
        _ue_pos_key = f"ue_pos_{rel_id_str}"
        _ue_pos = _sql_konfig_lesen(_ue_pos_key)
        if _ue_pos:
            win2.after(50, lambda _g=_ue_pos: win2.geometry(_g))
        def _ue_pos_speichern(event=None):
            try:
                _sql_konfig_schreiben(_ue_pos_key,
                    f"{win2.winfo_width()}x{win2.winfo_height()}"
                    f"+{win2.winfo_x()}+{win2.winfo_y()}")
            except Exception:
                pass
        win2.bind("<Configure>", _ue_pos_speichern)

        # 2-Spalten-Layout: links Gruppen+Details, rechts Schrittfenster
        haupt = tk.Frame(win2, padx=8, pady=8)
        haupt.pack(fill="both", expand=True)
        haupt.columnconfigure(0, weight=1)
        haupt.columnconfigure(1, weight=0)   # rechts: feste Breite, links dehnt sich
        haupt.rowconfigure(2, weight=1)

        # Info + Status (beide Spalten)
        tk.Label(haupt, text=f"Kette: {ketten_pfad}", anchor="w",
                 fg="#444444").grid(row=0, column=0,
                                    sticky="ew", pady=(0, 2))
        farbe = "#007700" if gesamt_ue == 0 else "#CC0000"
        sym   = "✓" if gesamt_ue == 0 else "⚠"
        stat  = (f"{sym}  Keine Überschneidungen in {n_gruppen} Gruppe(n)."
                 if gesamt_ue == 0 else
                 f"{sym}  {gesamt_ue} Überschneidung(en) in {n_mit_ue} von {n_gruppen} Gruppe(n)  "
                 f"·  {n_gesamt_ip} IP-Einträge gesamt")
        tk.Label(haupt, text=stat, anchor="w", fg=farbe,
                 font=("TkDefaultFont", 10, "bold")).grid(
                     row=1, column=0, sticky="ew", pady=(0, 4))

        # ── Linke Seite: Gruppen (oben) + Details (unten) ─────────────────────
        links_frame = tk.Frame(haupt)
        links_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        links_frame.columnconfigure(0, weight=1)
        links_frame.rowconfigure(1, weight=2)
        links_frame.rowconfigure(4, weight=3)

        tk.Label(links_frame, text=f"Gruppen  ({qf})",
                 anchor="w", font=("Segoe UI", 9, "bold")).grid(
                     row=0, column=0, sticky="ew", pady=(0, 2))

        frm_oben = tk.Frame(links_frame)
        frm_oben.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        frm_oben.rowconfigure(0, weight=1)
        frm_oben.columnconfigure(0, weight=1)

        _hat_grp_name = bool(_gw_zu_name)
        g_cols = ("gruppenname", "n_ips", "n_ue") if _hat_grp_name else ("n_ips", "n_ue")
        g_tv = ttk.Treeview(frm_oben, columns=g_cols, show="tree headings",
                             selectmode="browse")
        g_tv.heading("#0", text=qf, anchor="w")
        if _hat_grp_name:
            g_tv.heading("gruppenname", text=_grp_name_feld or "Gruppenname", anchor="w")
            g_tv.column("gruppenname", anchor="w", width=180, stretch=True, minwidth=60)
        g_tv.heading("n_ips", text="IP-Einträge", anchor="w",
                     command=lambda: _tv_sortieren(g_tv, "n_ips"))
        g_tv.heading("n_ue",  text="Überschneidungen", anchor="w",
                     command=lambda: _tv_sortieren(g_tv, "n_ue"))
        g_tv.column("#0",    anchor="w", width=160, stretch=True, minwidth=60)
        g_tv.column("n_ips", anchor="w", width=80,  stretch=False)
        g_tv.column("n_ue",  anchor="w", width=110, stretch=False)
        ttk.Scrollbar(frm_oben, orient="vertical",
                      command=g_tv.yview).grid(row=0, column=1, sticky="ns")
        ttk.Scrollbar(frm_oben, orient="horizontal",
                      command=g_tv.xview).grid(row=1, column=0, sticky="ew")
        g_tv.grid(row=0, column=0, sticky="nsew")

        iid_zu_details  = {}
        iid_zu_gw       = {}
        _kind_zu_eltern = {}
        for gw, n_ip, n_ue, det in gruppen_info:
            _tags = ("ue",) if n_ue > 0 else ()
            _gname = _gw_zu_name.get(str(gw), "")
            _vals  = (_gname, n_ip, n_ue) if _hat_grp_name else (n_ip, n_ue)
            iid2 = g_tv.insert("", "end", text=str(gw), values=_vals, tags=_tags)
            iid_zu_details[iid2] = det
            iid_zu_gw[iid2] = gw
            _a_zns_set  = set()
            _b_zns_set  = set()
            _a_zu_b_lst = {}
            for _dt in det:
                _a_zns_set.add(_dt[0])
                _b_zns_set.add(_dt[2])
                _a_zu_b_lst.setdefault(_dt[0], []).append(
                    (_dt[2], _dt[3], _dt[4], _dt[5]))
            _b_only_zns = _b_zns_set - _a_zns_set
            _sorted_eintr = sorted(
                gruppen.get(gw, []),
                key=lambda _e: (_k_parse(_e[1]) or (0, 0))[0]
            )
            for _zn_k, _iw_k in _sorted_eintr:
                if _zn_k in _b_only_zns:
                    continue
                _tag_k = ("ue",) if _zn_k in _a_zns_set else ("detail",)
                _disp_k = _zn_zu_disp.get(_zn_k, "")
                _lbl_k  = _iw_k   # IP-Wert im Baumfeld, Anzeigename in Spalte
                _cv_k   = (_disp_k, "", "") if _hat_grp_name else ("", "")
                _kiid = g_tv.insert(iid2, "end", text=_lbl_k,
                                    values=_cv_k, tags=_tag_k)
                _kind_zu_eltern[_kiid] = iid2
                for _r2_b, _d2_b, _ol_s_b, _ol_e_b in _a_zu_b_lst.get(_zn_k, []):
                    _disp_b = _zn_zu_disp.get(_r2_b, "")
                    _lbl_b  = "↳ " + _d2_b
                    _cv_b   = (_disp_b, "", "") if _hat_grp_name else ("", "")
                    _bkiid = g_tv.insert(iid2, "end", text=_lbl_b,
                                         values=_cv_b, tags=("ue_pair",))
                    _kind_zu_eltern[_bkiid] = iid2
        g_tv.tag_configure("ue",      foreground="#CC0000")
        g_tv.tag_configure("detail",  foreground="#777777")
        g_tv.tag_configure("ue_pair", foreground="#995500")
        # Nach dem Rendern optimieren, damit Fontmetriken korrekt sind
        win2.after(200, lambda: tree_spalten_breiten_anpassen(g_tv))

        # Navigation-Override für g_tv: gewählte Gruppe im Quell-Treeview markieren
        _outer_tv_nav = tv_widget
        def _nav_g_tv_zu_quellzeile(_otv=_outer_tv_nav, _win=win2, _qf_nav=qf):
            sel = g_tv.selection()
            if not sel:
                messagebox.showwarning("Vorherige Tabelle",
                    "Bitte zuerst eine Zeile auswählen.", parent=_win)
                return
            _iid = sel[0]
            _par = g_tv.parent(_iid)
            _gw_nav = g_tv.item(_iid if not _par else _par, "text")
            _cols_nav = list(_otv["columns"])
            _qi_nav = _cols_nav.index(_qf_nav) if _qf_nav in _cols_nav else -1
            _found = False
            for _riid in _otv.get_children():
                _rvals = _otv.item(_riid, "values")
                if _qi_nav >= 0 and _qi_nav < len(_rvals):
                    _chk = str(_rvals[_qi_nav])
                else:
                    _chk = next((str(v) for v in _rvals
                                 if str(v) == str(_gw_nav)), None)
                if _chk == str(_gw_nav):
                    _otv.selection_set(_riid)
                    _otv.see(_riid)
                    _found = True
                    break
            if _found:
                try:
                    _otv.winfo_toplevel().lift()
                    _otv.winfo_toplevel().focus_force()
                except Exception:
                    pass
            else:
                messagebox.showinfo("Vorherige Tabelle",
                    f"Gruppe '{_gw_nav}' nicht in der Quelltabelle gefunden.",
                    parent=_win)
        standard_tv_rechtsklick_anbinden(g_tv, qt, win2,
                                         nav_override_fn=_nav_g_tv_zu_quellzeile)

        ttk.Separator(links_frame, orient="horizontal").grid(
            row=2, column=0, sticky="ew", pady=(2, 2))
        _detail_kopf_frm = tk.Frame(links_frame)
        _detail_kopf_frm.grid(row=3, column=0, sticky="ew", pady=(0, 2))
        tk.Label(_detail_kopf_frm, text="Details zur gewählten Gruppe:",
                 anchor="w").pack(side="left")
        detail_lbl_var = tk.StringVar(value="")
        tk.Label(_detail_kopf_frm, textvariable=detail_lbl_var, anchor="w",
                 fg="#555555").pack(side="left", padx=(8, 0))

        frm_unten = tk.Frame(links_frame)
        frm_unten.grid(row=4, column=0, sticky="nsew")
        frm_unten.rowconfigure(0, weight=1)
        frm_unten.columnconfigure(0, weight=1)

        d_cols = ("z_a", "eintrag_a", "z_b", "eintrag_b", "ol_start", "ol_end", "anz")
        d_tv = ttk.Treeview(frm_unten, columns=d_cols, show="headings",
                             selectmode="browse")
        d_tv.heading("z_a",       text="Zeile A",         anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "z_a"))
        d_tv.heading("eintrag_a", text="Eintrag A",        anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "eintrag_a"))
        d_tv.heading("z_b",       text="Zeile B",         anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "z_b"))
        d_tv.heading("eintrag_b", text="Eintrag B",        anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "eintrag_b"))
        d_tv.heading("ol_start",  text="Überschn. Start", anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "ol_start"))
        d_tv.heading("ol_end",    text="Überschn. Ende",  anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "ol_end"))
        d_tv.heading("anz",       text="Anzahl IPs",       anchor="w",
                     command=lambda: _tv_sortieren(d_tv, "anz"))
        d_tv.column("z_a",        width=55,  anchor="w", stretch=False)
        d_tv.column("eintrag_a",  width=160, anchor="w", stretch=False)
        d_tv.column("z_b",        width=55,  anchor="w", stretch=False)
        d_tv.column("eintrag_b",  width=160, anchor="w", stretch=False)
        d_tv.column("ol_start",   width=110, anchor="w", stretch=False)
        d_tv.column("ol_end",     width=110, anchor="w", stretch=False)
        d_tv.column("anz",        width=70,  anchor="w", stretch=False)
        ttk.Scrollbar(frm_unten, orient="vertical",
                      command=d_tv.yview).grid(row=0, column=1, sticky="ns")
        ttk.Scrollbar(frm_unten, orient="horizontal",
                      command=d_tv.xview).grid(row=1, column=0, sticky="ew")
        d_tv.grid(row=0, column=0, sticky="nsew")

        standard_tv_rechtsklick_anbinden(d_tv, qt, win2)


        # ── Rechte Seite: Schrittfenster ──────────────────────────────────────
        rechts_frame = tk.Frame(haupt, relief="groove", bd=1)
        rechts_frame.grid(row=0, column=1, rowspan=3, sticky="nsew")
        rechts_frame.columnconfigure(0, weight=1)
        rechts_frame.rowconfigure(3, weight=1)
        _rechts_basis_w = [750]
        rechts_frame.config(width=_rechts_basis_w[0])
        rechts_frame.grid_propagate(False)
        win2.after(400, lambda: _rechts_basis_w.__setitem__(0, rechts_frame.winfo_width()))

        tk.Label(rechts_frame, text="Schrittweise Ausführen",
                 anchor="w", font=("Segoe UI", 9, "bold"),
                 padx=6, pady=4).grid(row=0, column=0, sticky="ew")

        _schr_btn_frm = tk.Frame(rechts_frame, padx=6)
        _schr_btn_frm.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        _schr_idx2  = [0]      # aktueller Zeilen-Index bei Einzelschritt
        _schr_gw2   = [None]   # aktuell angezeigte GroupID
        _schr_rows2 = [[]]     # gecachte Ergebniszeilen
        _schr_cols2 = [[]]     # Spaltennamen des letzten Ergebnisses
        _schr_mode2 = ['all']  # 'all' oder 'single'

        _btn_einzel_z = tk.Button(_schr_btn_frm, text="◄ Einzelschritt", width=14)
        _btn_einzel_z.pack(side="left", padx=(0, 4))
        _schr_lbl2 = tk.Label(_schr_btn_frm, text="—", anchor="center",
                               font=("Segoe UI", 9, "bold"))
        _schr_lbl2.pack(side="left", expand=True, fill="x", padx=4)
        _btn_einzel_w = tk.Button(_schr_btn_frm, text="Einzelschritt ►", width=14)
        _btn_einzel_w.pack(side="left", padx=(4, 8))
        _btn_alle2 = tk.Button(_schr_btn_frm, text="Alle ausführen", width=14)
        _btn_alle2.pack(side="left", padx=(0, 8))

        # Zweite Button-Zeile: Alle Gruppen Ergebnis
        _schr_btn_frm2 = tk.Frame(rechts_frame, padx=6)
        _schr_btn_frm2.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        _btn_alle_grp = tk.Button(_schr_btn_frm2,
            text="Alle Gruppen: Ergebnis (Schritt 5)",
            font=("Segoe UI", 8))
        _btn_alle_grp.pack(side="left")

        _schr_tv_frm = tk.Frame(rechts_frame, padx=6)
        _schr_tv_frm.grid(row=3, column=0, sticky="nsew")
        _schr_tv_frm.columnconfigure(0, weight=1)
        _schr_tv_frm.rowconfigure(1, weight=1)

        _schr_status2 = tk.Label(_schr_tv_frm,
            text="← Gruppe auswählen", anchor="w", fg="#555555")
        _schr_status2.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 2))

        _schr_tv2 = ttk.Treeview(_schr_tv_frm, columns=(), show="tree",
                                  selectmode="browse")
        _schr_tv2.column("#0", width=900, minwidth=300, stretch=True)
        _schr_tv2.heading("#0", text="")

        _schr_sy2 = ttk.Scrollbar(_schr_tv_frm, orient="vertical",
                                   command=_schr_tv2.yview)
        _schr_sx2 = ttk.Scrollbar(_schr_tv_frm, orient="horizontal",
                                   command=_schr_tv2.xview)
        _schr_tv2.configure(yscrollcommand=_schr_sy2.set,
                            xscrollcommand=_schr_sx2.set)
        _schr_tv2.grid(row=1, column=0, sticky="nsew")
        _schr_sy2.grid(row=1, column=1, sticky="ns")
        _schr_sx2.grid(row=2, column=0, sticky="ew")
        # Systemfarben bleiben — nur Schrift fett+groß für alle Farbmodi lesbar
        _schr_tv2.tag_configure("step_hdr",
            font=("Segoe UI", 10, "bold"))
        _schr_tv2.tag_configure("col_hdr",
            font=("Consolas", 9))
        _schr_tv2.tag_configure("daten",
            font=("Consolas", 10, "bold"))
        _schr_tv2.tag_configure("daten_ja",
            font=("Consolas", 10, "bold"), foreground="#CC0000")

        # ── Schrittweise: Auto-Resize win2 je nach TV-Inhalt ────────────────────
        def _schr_auto_breite():
            """Misst längste Zeile und weitet rechts_frame innerhalb win2 aus.
            win2 selbst bleibt unverändert in Position und Größe."""
            try:
                import tkinter.font as _tkf
                _fnt = _tkf.Font(family="Consolas", size=10, weight="bold")
                _max_w = 400
                def _mess(iid, tiefe=0):
                    nonlocal _max_w
                    txt = _schr_tv2.item(iid, "text")
                    w = _fnt.measure(txt) + 24 + tiefe * 20
                    if w > _max_w:
                        _max_w = w
                    for ch in _schr_tv2.get_children(iid):
                        _mess(ch, tiefe + 1)
                for _top in _schr_tv2.get_children():
                    _mess(_top)
                # TV-Spalte auf gemessene Breite setzen
                _col_w = min(_max_w + 24, 2000)
                _schr_tv2.column("#0", width=_col_w, minwidth=300)
                # rechts_frame nur ausweiten wenn nötig, nie über Fensterhälfte
                _frame_w = _col_w + 28          # Scrollbar + Rand
                _win_w   = win2.winfo_width()
                _min_lks = 380                   # linkes Panel min. 380px
                _max_rechts = max(_rechts_basis_w[0],
                                  _win_w - _min_lks - 16)
                _frame_w = min(_frame_w, _max_rechts)
                if _frame_w > rechts_frame.winfo_width():
                    rechts_frame.config(width=_frame_w)
            except Exception:
                pass

        def _schr_reset_breite():
            """Setzt rechts_frame auf Basis-Breite zurück (neue Gruppe)."""
            try:
                _schr_tv2.column("#0", width=900, minwidth=300)
                rechts_frame.config(width=_rechts_basis_w[0])
            except Exception:
                pass

        # ── Schrittweise: Alle Ergebniszeilen laden (Vollabfrage) ─────────────
        # ── Schrittweise: Algorithmus-Schritte aufbauen ──────────────────────
        def _schr2_build_steps(gw_val):
            """Baut 5 Algorithmus-Schritte aus den vorberechneten Daten."""
            gw_s  = str(gw_val)
            eintr = gruppen.get(gw_s, [])
            schritte = []

            # Schritt 1: DB-Einträge
            sp1 = ["Zeile", "IP-Wert", "Anzeigename"]
            z1  = [(str(zn), iw, _zn_zu_disp.get(zn, ""))
                   for zn, iw in eintr]
            schritte.append({"titel": "DB-Einträge", "spalten": sp1, "zeilen": z1,
                             "status": f"Schritt 1: {len(z1)} Einträge aus der DB"})

            # Schritt 2: IP → Integer
            sp2 = ["Zeile", "IP-Wert", "Typ",
                   "Start-IP", "End-IP", "Start-Int", "End-Int", "Umfang"]
            z2 = []
            parsed = []
            for zn, iw in eintr:
                r = _k_parse(iw)
                if r:
                    typ = ("CIDR"     if "/" in iw else
                           "Range"    if _re3.search(r"[-–]", iw) else
                           "Einzel-IP")
                    z2.append((str(zn), iw, typ,
                               _k_i2ip(r[0]), _k_i2ip(r[1]),
                               str(r[0]), str(r[1]), str(r[1]-r[0]+1)))
                    parsed.append((r[0], r[1], zn, iw))
                else:
                    z2.append((str(zn), iw, "ungültig",
                               "—","—","—","—","—"))
            n_ok = sum(1 for row in z2 if row[2] != "ungültig")
            schritte.append({"titel": "IP → Integer",
                             "spalten": sp2, "zeilen": z2,
                             "status": f"Schritt 2: {n_ok} gültig"})

            # Schritt 3: Sortiert
            sortiert = sorted(parsed, key=lambda x: x[0])
            sp3 = ["Rang", "Start-IP", "End-IP", "Umfang", "Zeile", "IP-Wert"]
            z3  = [(str(i+1), _k_i2ip(s), _k_i2ip(e),
                    str(e-s+1), str(zn), iw)
                   for i, (s, e, zn, iw) in enumerate(sortiert)]
            schritte.append({"titel": "Sortiert nach Start-IP",
                             "spalten": sp3, "zeilen": z3,
                             "status": f"Schritt 3: {len(z3)} sortiert"})

            # Schritt 4: Sweep
            sp4 = ["Zeile A", "IP A", "Zeile B", "IP B",
                   "Überschneidung?",
                   "Überschn. Start", "Überschn. Ende", "Anzahl IPs"]
            z4 = []
            overlaps = []
            for i in range(len(sortiert)):
                s1, e1, r1, d1 = sortiert[i]
                for j in range(i+1, len(sortiert)):
                    s2, e2, r2, d2 = sortiert[j]
                    if s2 > e1:
                        z4.append((str(r1), d1, str(r2), d2,
                                   "Nein – Abstand", "","",""))
                        break
                    ol_s = s2; ol_e = min(e1, e2); cnt = ol_e-ol_s+1
                    z4.append((str(r1), d1, str(r2), d2, "Ja",
                               _k_i2ip(ol_s), _k_i2ip(ol_e), str(cnt)))
                    overlaps.append(
                        (r1, d1, r2, d2, _k_i2ip(ol_s), _k_i2ip(ol_e), cnt))
            n_ja = sum(1 for row in z4 if row[4] == "Ja")
            schritte.append({"titel": "Sweep – Paarweiser Vergleich",
                             "spalten": sp4, "zeilen": z4,
                             "status": (f"Schritt 4: {len(z4)} Vergleiche, "
                                        f"{n_ja} Überschneidung(en)")})

            # Schritt 5: Ergebnis (mit Anzeigenamen + Gruppenname)
            _grp_nm5 = _gw_zu_name.get(gw_s, "")
            sp5 = ["Zeile A", "Eintrag A", "Anzeigename A",
                   "Zeile B", "Eintrag B", "Anzeigename B",
                   "Überschn. Start", "Überschn. Ende", "Anzahl IPs"]
            z5  = [(str(r1), d1, _zn_zu_disp.get(r1, ""),
                    str(r2), d2, _zn_zu_disp.get(r2, ""),
                    ol_s, ol_e, str(cnt))
                   for r1, d1, r2, d2, ol_s, ol_e, cnt in overlaps]
            schritte.append({"titel": "Ergebnis",
                             "spalten": sp5, "zeilen": z5,
                             "gruppiert": True,
                             "gw_id":   gw_s,
                             "gw_name": _grp_nm5,
                             "status": f"Schritt 5: {len(z5)} Überschneidung(en)"})
            return schritte

        def _schr2_step_anhaengen(s, idx, n_ges):
            """Hängt einen Schritt als flache Root-Zeilen ans TV an –
            kein Einzug, kein Klappmechanismus, alles bündig links."""
            sep = " │ "
            ist_letzter = (idx == n_ges - 1)
            titel = (f"═══  Schritt {idx+1}/{n_ges}: {s['titel']}"
                     f"  ({len(s['zeilen'])} Einträge)  ═══")
            _schr_tv2.insert("", "end", text=titel, tags=("step_hdr",))
            spalten = s["spalten"]
            zeilen  = s["zeilen"]
            if s.get("gruppiert"):
                # Ergebnis-Schritt: Gruppe oben, A als Kopfzeile, B eingerückt
                # Spalten: [ZeileA, EintragA, AnzA, ZeileB, EintragB, AnzB, olS, olE, cnt]
                gw_id   = s.get("gw_id", "")
                gw_name = s.get("gw_name", "")
                _grp_hdr = f"Gruppe: {gw_id}"
                if gw_name:
                    _grp_hdr += f"  –  {gw_name}"
                _schr_tv2.insert("", "end", text=_grp_hdr, tags=("step_hdr",))
                sp_a = spalten[:3]   # Zeile A, Eintrag A, Anzeigename A
                sp_b = spalten[3:]   # Zeile B, Eintrag B, Anzeigename B, Überschn...
                _prev_a = None
                for row in zeilen:
                    a_key = (row[0], row[1])
                    if a_key != _prev_a:
                        # A-Spaltenköpfe + A-Datenzeile
                        _schr_tv2.insert("", "end",
                            text=sep.join(sp_a), tags=("col_hdr",))
                        _schr_tv2.insert("", "end",
                            text=sep.join(str(v) for v in row[:3]),
                            tags=("daten",))
                        # B-Spaltenköpfe
                        _schr_tv2.insert("", "end",
                            text="      " + sep.join(sp_b), tags=("col_hdr",))
                        _prev_a = a_key
                    # B-Datenzeile eingerückt
                    _schr_tv2.insert("", "end",
                        text="      " + sep.join(str(v) for v in row[3:]),
                        tags=("daten",))
            else:
                _schr_tv2.insert("", "end",
                    text=sep.join(spalten), tags=("col_hdr",))
                for row in zeilen:
                    is_ja = (len(row) > 4 and str(row[4]) == "Ja")
                    tag   = ("daten_ja",) if is_ja else ("daten",)
                    _schr_tv2.insert("", "end",
                        text=sep.join(str(v) for v in row), tags=tag)
            # Trenner: leer + (letzter Schritt → 10 Leerzeilen zum Scrollen)
            _schr_tv2.insert("", "end", text="", tags=("daten",))
            if ist_letzter:
                for _ in range(10):
                    _schr_tv2.insert("", "end", text="", tags=("daten",))

        def _schr2_laden(gw_val):
            """Lädt eine Gruppe: führt sofort alle Schritte aus und scrollt ans Ende.
            Einzelschritt ► setzt danach auf Schritt 1 zurück (Schritt-für-Schritt-Modus)."""
            _schr_gw2[0]   = gw_val
            _schr_idx2[0]  = 0
            _schr_mode2[0] = "alle"
            _schr_tv2.delete(*_schr_tv2.get_children())
            _schr_reset_breite()
            if not gw_val:
                _schr_status2.config(text="← Gruppe auswählen")
                _schr_lbl2.config(text="—")
                _btn_einzel_z.config(state="disabled")
                _btn_einzel_w.config(state="disabled")
                return
            schritte = _schr2_build_steps(gw_val)
            _schr_rows2[0] = schritte
            n = len(schritte)
            for i, s in enumerate(schritte):
                _schr2_step_anhaengen(s, i, n)
            _schr_idx2[0] = n - 1
            alle_kinder = _schr_tv2.get_children()
            if alle_kinder:
                _schr_tv2.see(alle_kinder[-1])
            _schr_lbl2.config(text=f"Alle {n} Schritte")
            _schr_status2.config(
                text=f"Alle {n} Schritte  (Gruppe: {gw_val})")
            _btn_einzel_z.config(state="disabled")
            _btn_einzel_w.config(
                state="normal" if n > 0 else "disabled",
                text="◄ Schritt 1")
            win2.after(120, _schr_auto_breite)

        def _schr2_einzelschritt(richtung):
            """Vorwärts: wenn alle Schritte gezeigt → Reset auf Schritt 1 (Schritt-für-Schritt).
            Danach: jeweils nächsten Schritt anhängen."""
            schritte = _schr_rows2[0]
            if not schritte or richtung < 0:
                return
            n = len(schritte)
            # Wenn alle Schritte sichtbar → zurücksetzen auf Schritt 1
            if _schr_idx2[0] >= n - 1:
                _schr_tv2.delete(*_schr_tv2.get_children())
                _schr_idx2[0] = 0
                _schr_mode2[0] = "kum"
                _schr2_step_anhaengen(schritte[0], 0, n)
                _schr_lbl2.config(
                    text=f"Schritt 1/{n}: {schritte[0]['titel']}")
                _schr_status2.config(text=schritte[0]["status"])
                _btn_einzel_w.config(
                    state="normal" if n > 1 else "disabled",
                    text="Einzelschritt ►")
                win2.after(120, _schr_auto_breite)
                return
            # Normal: nächsten Schritt anhängen
            next_idx = _schr_idx2[0] + 1
            _schr_idx2[0] = next_idx
            _schr2_step_anhaengen(schritte[next_idx], next_idx, n)
            alle_kinder = _schr_tv2.get_children()
            if alle_kinder:
                _schr_tv2.see(alle_kinder[-1])
            _schr_lbl2.config(
                text=f"Schritt {next_idx+1}/{n}: {schritte[next_idx]['titel']}")
            _schr_status2.config(text=schritte[next_idx]["status"])
            _btn_einzel_z.config(state="disabled")
            _btn_einzel_w.config(
                state="normal",
                text="◄ Schritt 1" if next_idx >= n-1 else "Einzelschritt ►")
            win2.after(120, _schr_auto_breite)

        def _schr2_alle():
            """Zeigt alle 5 Schritte auf einmal."""
            schritte = _schr_rows2[0]
            if not schritte and _schr_gw2[0]:
                schritte = _schr2_build_steps(_schr_gw2[0])
                _schr_rows2[0] = schritte
            if not schritte:
                return
            _schr_tv2.delete(*_schr_tv2.get_children())
            n = len(schritte)
            for i, s in enumerate(schritte):
                _schr2_step_anhaengen(s, i, n)
            _schr_idx2[0] = n - 1
            alle_kinder = _schr_tv2.get_children()
            if alle_kinder:
                _schr_tv2.see(alle_kinder[-1])
            _schr_lbl2.config(text=f"Alle {n} Schritte")
            _schr_status2.config(
                text=f"Alle {n} Schritte  (Gruppe: {_schr_gw2[0]})")
            _btn_einzel_z.config(state="disabled")
            _btn_einzel_w.config(state="disabled")
            win2.after(120, _schr_auto_breite)

        _btn_einzel_z.config(command=lambda: _schr2_einzelschritt(-1))
        _btn_einzel_w.config(command=lambda: _schr2_einzelschritt(+1))
        _btn_alle2.config(command=_schr2_alle)

        def _alle_gruppen_ergebnis():
            """Zeigt Schritt-5-Ergebnisse aller Gruppen MIT Überschneidungen."""
            _schr_tv2.delete(*_schr_tv2.get_children())
            _schr_reset_breite()
            _schr_gw2[0]  = None
            _schr_idx2[0] = 0
            _gruppen_mit_ue = [(gw, n_ue, det)
                               for gw, n_ip, n_ue, det in gruppen_info
                               if n_ue > 0]
            if not _gruppen_mit_ue:
                _schr_status2.config(text="Keine Überschneidungen vorhanden.")
                return
            _schr_status2.config(
                text=f"Alle Gruppen: {len(_gruppen_mit_ue)} mit Überschneidungen")
            _schr_lbl2.config(text=f"Alle Gruppen – Schritt 5")
            for gw, n_ue, det in _gruppen_mit_ue:
                schritte = _schr2_build_steps(gw)
                if schritte:
                    s5 = schritte[-1]   # Schritt 5 = letzter
                    _schr2_step_anhaengen(s5, 4, 5)
            alle_kinder = _schr_tv2.get_children()
            if alle_kinder:
                _schr_tv2.see(alle_kinder[0])  # Zum Anfang scrollen
            _btn_einzel_w.config(state="disabled", text="Einzelschritt ►")
            _btn_einzel_z.config(state="disabled")
            win2.after(150, _schr_auto_breite)

        _btn_alle_grp.config(command=_alle_gruppen_ergebnis)

        # Gruppen-Selektion aktualisiert Details + Schrittfenster
        def _details_zeigen(event=None):
            sel = g_tv.selection()
            if not sel:
                return
            _eiid = _kind_zu_eltern.get(sel[0], sel[0])
            det = iid_zu_details.get(_eiid, [])
            gw  = iid_zu_gw.get(_eiid, g_tv.item(_eiid, "text"))
            d_tv.delete(*d_tv.get_children())
            # A immer als eigene Zeile (fett), B immer eingerückt darunter
            _prev_a = None
            for r1, d1, r2, d2, ol_s, ol_e, cnt in det:
                if (r1, d1) != _prev_a:
                    d_tv.insert("", "end",
                                values=(r1, d1, "", "", "", "", ""),
                                tags=("dtv_first",))
                    _prev_a = (r1, d1)
                d_tv.insert("", "end",
                            values=("", "", r2, d2, ol_s, ol_e, cnt),
                            tags=("dtv_cont",))
            d_tv.tag_configure("dtv_first", font=("TkDefaultFont", 9, "bold"))
            d_tv.tag_configure("dtv_cont",  foreground="#664400")
            if det:
                tree_spalten_breiten_anpassen(d_tv)
            detail_lbl_var.set(
                f"Gruppe: {gw}  ·  {len(det)} Überschneidung(en)" if det
                else f"Gruppe: {gw}  ·  Keine Überschneidungen")
            _schr_gw2[0] = gw
            if aktive_schritte:
                _schr2_laden(gw)

        g_tv.bind("<<TreeviewSelect>>", _details_zeigen)

        for iid2 in g_tv.get_children():
            if iid_zu_details.get(iid2):
                g_tv.selection_set(iid2)
                g_tv.see(iid2)
                _details_zeigen()
                break
        else:
            kinder = g_tv.get_children()
            if kinder:
                g_tv.selection_set(kinder[0])
                _details_zeigen()

        # Aktionen
        def _alle_kopieren():
            zeilen = [f"Gruppe ({qf})\tIP-Einträge\tÜberschneidungen"]
            for gw, n_ip, n_ue, _ in gruppen_info:
                zeilen.append(f"{gw}\t{n_ip}\t{n_ue}")
            zeilen.append("")
            zeilen.append("Zeile A\tEintrag A\tZeile B\tEintrag B\t"
                          "Überschn. Start\tÜberschn. Ende\t"
                          "Anzahl IPs\tGruppe")
            for gw, _, _, det in gruppen_info:
                for r1, d1, r2, d2, ol_s, ol_e, cnt in det:
                    zeilen.append(
                        f"{r1}\t{d1}\t{r2}\t{d2}\t{ol_s}\t{ol_e}\t{cnt}\t{gw}")
            win2.clipboard_clear()
            win2.clipboard_append("\n".join(zeilen))
            messagebox.showinfo("Kopiert",
                f"Übersicht + {gesamt_ue} Detailzeile(n) kopiert.",
                parent=win2)

        _win2_menue.add_separator()
        _win2_menue.add_command(label="In DB speichern",
                                command=_analyse_in_db_speichern)
        _win2_menue.add_command(label="Frühere Analysen...",
                                command=_analyse_browsen)
        _win2_menue.add_command(label="Alle Ergebnisse kopieren",
                                command=_alle_kopieren)
        _win2_menue.add_separator()
        _win2_menue.add_command(label="Schließen", command=win2.destroy)


    def ip_range_aufteilen_lokal():
        iid = _lok["item"]
        idx = _sp_idx()
        if not iid or idx is None:
            messagebox.showwarning("IP-Range", "Bitte zuerst eine Zelle auswählen.", parent=parent_win)
            return
        w = tv_widget.item(iid, "values")
        fv = str(w[idx]).strip() if idx < len(w) else ""
        ergebnis = ip_range_aufteilen_funktion(fv) if callable(ip_range_aufteilen_funktion) else None
        if ergebnis is None or not ergebnis.get("ok"):
            fehler = ergebnis.get("fehler", "Unbekannter Fehler") if ergebnis else "Funktion nicht verfügbar"
            messagebox.showwarning("IP-Range aufteilen",
                f"'{fv}' ist kein gültiger IP-Bereich.\n\nFehler: {fehler}", parent=parent_win)
            return
        sql_text_im_lesefenster_anzeigen(parent_win, "IP-Range aufteilen",
            f"Eingabe:    {fv}\n"
            f"Start-IP:   {ergebnis['start']}  ({ergebnis['start_int']})\n"
            f"End-IP:     {ergebnis['end']}  ({ergebnis['end_int']})")

    # ── Block 5: Findings ────────────────────────────────────────────────────
    def _finding_id_felder_ermitteln(iid):
        """Gibt (alle_tabellen, id_feld, id_wert, sp_sicht, werte_all, alle_sp) zurück."""
        import re as _re
        sp_sicht  = _sichtb()
        werte_all = tv_widget.item(iid, "values")
        alle_sp   = _alle_sp()
        id_feld   = next((s for s in sp_sicht if s.lower() == "id"), (sp_sicht[0] if sp_sicht else ""))
        def _wert(sp_n):
            try:
                return str(werte_all[alle_sp.index(sp_n)]) if sp_n in alle_sp else ""
            except Exception:
                return ""
        id_wert = _wert(id_feld)
        alle_tabellen = []
        if sql_text_hint:
            try:
                gefunden = _re.findall(
                    r'\b(?:FROM|JOIN|INTO|UPDATE)\s+[`"\[]?(\w+)[`"\]]?',
                    sql_text_hint, _re.IGNORECASE)
                seen = set()
                for t in gefunden:
                    tl = t.lower()
                    if tl not in seen:
                        seen.add(tl)
                        alle_tabellen.append(t)
            except Exception:
                pass
        if not alle_tabellen and tabellenname:
            alle_tabellen = [tabellenname]
        if not alle_tabellen:
            try:
                vb = sqlite_verbindung_oeffnen()
                alle_tabellen = [r[0] for r in vb.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()]
                vb.close()
            except Exception:
                pass
        return alle_tabellen, id_feld, id_wert, sp_sicht, werte_all, alle_sp, _wert

    def finding_aufrufen():
        """Zeigt das vorhandene Finding für die gewählte Zeile an – oder bietet an, eines anzulegen."""
        _tab_f = "zzz_Findings"
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            messagebox.showwarning("Finding aufrufen",
                "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        alle_tabellen, id_feld, id_wert, sp_sicht, werte_all, alle_sp, _wert = \
            _finding_id_felder_ermitteln(iid)
        tabname = alle_tabellen[0] if alle_tabellen else ""
        # Finding suchen
        row_f = None
        try:
            vb = sqlite_verbindung_oeffnen()
            row_f = vb.execute(
                f"SELECT id, datetime, TabellenName, idFeld, idFeldInhalt, "
                f"Feldname, FeldInhalt, KurzeBeschreibung "
                f"FROM {sql_identifier(_tab_f)} "
                f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                (tabname, id_feld, id_wert)).fetchone()
            vb.close()
        except Exception:
            pass
        if row_f is None:
            if messagebox.askyesno(
                    "Finding aufrufen",
                    f"Kein Finding für:\n  Tabelle: {tabname}\n"
                    f"  {id_feld} = {id_wert}\n\n"
                    f"Jetzt ein Finding hinzufügen?", parent=parent_win):
                finding_hinzufuegen()
            return
        # Finding anzeigen / bearbeiten
        f_id, f_dt, f_tab, f_id_feld, f_id_wert, f_feldname, f_feldinhalt, f_beschr = row_f
        dlg = tk.Toplevel(parent_win)
        dlg.title(f"Finding – {f_tab} / {f_id_feld} = {f_id_wert}")
        dlg.geometry("560x340")
        dlg.resizable(True, False)
        dlg.grab_set()
        dlg.transient(parent_win)
        dlg.columnconfigure(1, weight=1)
        def _lbl(row, text, val, readonly=True):
            tk.Label(dlg, text=text, anchor="w").grid(
                row=row, column=0, sticky="w", padx=16, pady=(6, 2))
            if readonly:
                tk.Label(dlg, text=val, anchor="w", relief="groove").grid(
                    row=row, column=1, sticky="ew", padx=(0, 16), pady=(6, 2))
            else:
                var = tk.StringVar(value=val or "")
                e = tk.Entry(dlg, textvariable=var, width=50)
                e.grid(row=row, column=1, sticky="ew", padx=(0, 16), pady=(6, 2))
                return var
        _lbl(0, "Finding-ID:",    str(f_id))
        _lbl(1, "Gespeichert:",   f_dt or "–")
        _lbl(2, "Tabellenname:",  f_tab or "–")
        _lbl(3, f"ID ({f_id_feld}):", f_id_wert or "–")
        _lbl(4, "Feldname:",      f_feldname or "–")
        _lbl(5, "Feldinhalt:",    f_feldinhalt or "–")
        beschr_var = _lbl(6, "Beschreibung:", f_beschr or "", readonly=False)
        beschr_var.set(f_beschr or "")
        bf = tk.Frame(dlg)
        bf.grid(row=7, column=0, columnspan=2, pady=(12, 12))
        def _speichern():
            neu_beschr = beschr_var.get().strip()
            try:
                from datetime import datetime as _dt
                vb = sqlite_verbindung_oeffnen()
                vb.execute(
                    f"UPDATE {sql_identifier(_tab_f)} "
                    f"SET KurzeBeschreibung=?, datetime=? WHERE id=?",
                    (neu_beschr, _dt.now().strftime("%Y-%m-%d %H:%M:%S"), f_id))
                vb.commit()
                vb.close()
                sql_logging_eintrag_sicher_schreiben(
                    f"Finding aktualisiert (ID {f_id}): {f_tab} / {f_id_feld}={f_id_wert}", 0)
                messagebox.showinfo("Finding gespeichert",
                    "Die Beschreibung wurde aktualisiert.", parent=dlg)
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Finding", f"Fehler beim Speichern:\n{e}", parent=dlg)
        def _loeschen():
            if not messagebox.askyesno("Finding löschen",
                    f"Finding ID {f_id} wirklich löschen?", parent=dlg):
                return
            try:
                vb = sqlite_verbindung_oeffnen()
                vb.execute(f"DELETE FROM {sql_identifier(_tab_f)} WHERE id=?", (f_id,))
                vb.commit()
                vb.close()
                sql_logging_eintrag_sicher_schreiben(
                    f"Finding gelöscht (ID {f_id}): {f_tab} / {f_id_feld}={f_id_wert}", 0)
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Finding löschen", f"Fehler:\n{e}", parent=dlg)
        tk.Button(bf, text="Speichern",      width=12, command=_speichern).pack(side="right", padx=(8, 16))
        tk.Button(bf, text="Finding löschen",width=14, command=_loeschen, fg="red").pack(side="right", padx=(8, 0))
        tk.Button(bf, text="Schließen",      width=12, command=dlg.destroy).pack(side="right")
        dlg.wait_window()

    def finding_hinzufuegen():
        import re as _re
        _tab_f = "zzz_Findings"
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            messagebox.showwarning("Finding hinzufügen",
                "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        sp_sicht  = _sichtb()
        werte_all = tv_widget.item(iid, "values")
        alle_sp   = _alle_sp()
        def _wert(sp_n):
            try:
                return str(werte_all[alle_sp.index(sp_n)]) if sp_n in alle_sp else ""
            except Exception:
                return ""
        # zzz_Findings sicherstellen
        try:
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"CREATE TABLE IF NOT EXISTS {sql_identifier(_tab_f)} ("
                f"id INTEGER PRIMARY KEY AUTOINCREMENT, datetime TEXT NOT NULL, "
                f"TabellenName TEXT, idFeld TEXT, idFeldInhalt TEXT, "
                f"Feldname TEXT, FeldInhalt TEXT, KurzeBeschreibung TEXT, "
                f"UNIQUE(TabellenName, idFeld, idFeldInhalt))")
            try:
                vb.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS idx_findings_unique "
                    f"ON {sql_identifier(_tab_f)} (TabellenName, idFeld, idFeldInhalt)")
            except Exception:
                pass
            vb.commit()
            vb.close()
        except Exception as e:
            messagebox.showerror("Finding hinzufügen",
                f"Tabelle konnte nicht angelegt werden:\n{e}", parent=parent_win)
            return
        # Tabellennamen ermitteln
        alle_tabellen = []
        if sql_text_hint:
            try:
                gefunden_tabs = _re.findall(
                    r'\b(?:FROM|JOIN|INTO|UPDATE)\s+[`"\[]?(\w+)[`"\]]?',
                    sql_text_hint, _re.IGNORECASE)
                seen = set()
                for t in gefunden_tabs:
                    tl = t.lower()
                    if tl not in seen:
                        seen.add(tl)
                        alle_tabellen.append(t)
            except Exception:
                pass
        if not alle_tabellen and tabellenname:
            alle_tabellen = [tabellenname]
        if not alle_tabellen:
            try:
                vb = sqlite_verbindung_oeffnen()
                alle_tabellen = [r[0] for r in vb.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()]
                vb.close()
            except Exception:
                pass
        # Vorhandene Beschreibungen laden
        vorhandene = []
        try:
            vb = sqlite_verbindung_oeffnen()
            vorhandene = [r[0] for r in vb.execute(
                f"SELECT DISTINCT KurzeBeschreibung FROM {sql_identifier(_tab_f)} "
                f"WHERE KurzeBeschreibung IS NOT NULL AND KurzeBeschreibung != '' "
                f"ORDER BY KurzeBeschreibung").fetchall()]
            vb.close()
        except Exception:
            pass
        dlg = tk.Toplevel(parent_win)
        dlg.title("Finding hinzufügen")
        dlg.geometry("560x320")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(parent_win)
        dlg.columnconfigure(1, weight=1)
        tk.Label(dlg, text="Tabellenname:", anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(10, 2))
        tn_var = tk.StringVar(value=alle_tabellen[0] if alle_tabellen else "")
        ttk.Combobox(dlg, textvariable=tn_var, values=alle_tabellen, width=48).grid(
            row=0, column=1, padx=(0, 16), pady=(10, 2), sticky="ew")
        tk.Label(dlg, text="ID-Feld:", anchor="w").grid(row=1, column=0, sticky="w", padx=16, pady=(4, 2))
        id_start = next((s for s in sp_sicht if s.lower() == "id"), (sp_sicht[0] if sp_sicht else ""))
        id_var = tk.StringVar(value=id_start)
        id_cb = ttk.Combobox(dlg, textvariable=id_var, values=sp_sicht, width=48)
        id_cb.grid(row=1, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")
        tk.Label(dlg, text="ID-Inhalt:", anchor="w").grid(row=2, column=0, sticky="w", padx=16, pady=(4, 2))
        idinhalt_var = tk.StringVar(value=_wert(id_var.get()))
        tk.Entry(dlg, textvariable=idinhalt_var, state="readonly", width=50).grid(
            row=2, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")
        id_cb.bind("<<ComboboxSelected>>", lambda e: idinhalt_var.set(_wert(id_var.get())))
        tk.Label(dlg, text="Feldname:", anchor="w").grid(row=3, column=0, sticky="w", padx=16, pady=(4, 2))
        k_sp = _sp_name() or (sp_sicht[0] if sp_sicht else "")
        fn_var = tk.StringVar(value=k_sp if k_sp in sp_sicht else (sp_sicht[0] if sp_sicht else ""))
        fn_cb = ttk.Combobox(dlg, textvariable=fn_var, values=sp_sicht, width=48)
        fn_cb.grid(row=3, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")
        tk.Label(dlg, text="Feldinhalt:", anchor="w").grid(row=4, column=0, sticky="w", padx=16, pady=(4, 2))
        fi_var = tk.StringVar(value=_wert(fn_var.get()))
        tk.Entry(dlg, textvariable=fi_var, state="readonly", width=50).grid(
            row=4, column=1, padx=(0, 16), pady=(4, 16), sticky="ew")
        fn_cb.bind("<<ComboboxSelected>>", lambda e: fi_var.set(_wert(fn_var.get())))
        tk.Label(dlg, text="Kurze Beschreibung:", anchor="w").grid(row=5, column=0, sticky="w", padx=16, pady=(0, 2))
        bf2 = tk.Frame(dlg)
        bf2.grid(row=5, column=1, padx=(0, 16), pady=(0, 2), sticky="ew")
        bf2.columnconfigure(0, weight=1)
        beschr_var = tk.StringVar()
        beschr_cb = ttk.Combobox(bf2, textvariable=beschr_var, values=vorhandene, width=34)
        beschr_cb.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        af_var = tk.StringVar(value="Aus Feld ▾")
        af_cb = ttk.Combobox(bf2, textvariable=af_var, values=sp_sicht, width=14, state="readonly")
        af_cb.grid(row=0, column=1, sticky="e")
        af_cb.bind("<<ComboboxSelected>>", lambda e: (
            beschr_var.set(_wert(af_var.get())) if af_var.get() in sp_sicht else None,
            af_var.set("Aus Feld ▾")))
        erg = [None]
        def _ok(event=None):
            erg[0] = {"tabellenname": tn_var.get().strip(), "id_feld": id_var.get().strip(),
                      "id_inhalt": idinhalt_var.get(), "feldname": fn_var.get().strip(),
                      "feldinhalt": fi_var.get(), "beschreibung": beschr_var.get().strip()}
            dlg.destroy()
        btnf = tk.Frame(dlg)
        btnf.grid(row=6, column=0, columnspan=2, pady=(10, 10))
        tk.Button(btnf, text="OK", width=12, command=_ok).pack(side="right", padx=(8, 16))
        tk.Button(btnf, text="Abbrechen", width=12, command=dlg.destroy).pack(side="right")
        beschr_cb.bind("<Return>", _ok)
        beschr_cb.bind("<Escape>", lambda e: dlg.destroy())
        beschr_cb.focus_set()
        dlg.wait_window()
        if erg[0] is None:
            return
        d = erg[0]
        if not d["tabellenname"]:
            messagebox.showwarning("Finding hinzufügen",
                "Bitte einen Tabellennamen angeben.", parent=parent_win)
            return
        ist_update = False
        try:
            vb = sqlite_verbindung_oeffnen()
            row_f = vb.execute(
                f"SELECT KurzeBeschreibung FROM {sql_identifier(_tab_f)} "
                f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                (d["tabellenname"], d["id_feld"], d["id_inhalt"])).fetchone()
            vb.close()
            if row_f is not None:
                ist_update = True
        except Exception:
            pass
        if ist_update:
            if not messagebox.askyesno("Finding existiert bereits",
                "Für diesen Datensatz existiert bereits ein Finding.\n\nSoll es überschrieben werden?",
                parent=parent_win):
                return
        try:
            from datetime import datetime as _dt
            jetzt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            vb = sqlite_verbindung_oeffnen()
            if ist_update:
                vb.execute(
                    f"UPDATE {sql_identifier(_tab_f)} "
                    f"SET Feldname=?, FeldInhalt=?, KurzeBeschreibung=?, datetime=? "
                    f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                    (d["feldname"], d["feldinhalt"], d["beschreibung"], jetzt,
                     d["tabellenname"], d["id_feld"], d["id_inhalt"]))
                log_aktion = "Finding aktualisiert"
            else:
                vb.execute(
                    f"INSERT INTO {sql_identifier(_tab_f)} "
                    f"(TabellenName, idFeld, idFeldInhalt, Feldname, FeldInhalt, KurzeBeschreibung, datetime) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (d["tabellenname"], d["id_feld"], d["id_inhalt"],
                     d["feldname"], d["feldinhalt"], d["beschreibung"], jetzt))
                log_aktion = "Finding hinzugefügt"
            vb.commit()
            vb.close()
            sql_logging_eintrag_sicher_schreiben(
                f"{log_aktion}: {d['tabellenname']} / {d['feldname']} = {d['feldinhalt'][:50]}\n"
                f". Beschreibung: {d['beschreibung'][:100]}", 0)
            messagebox.showinfo(log_aktion, "Das Finding wurde gespeichert.", parent=parent_win)
        except Exception as e:
            sql_logging_eintrag_sicher_schreiben(f"Fehler beim Speichern des Findings: {e}", 1)
            messagebox.showerror("Finding hinzufügen", f"Fehler:\n{e}", parent=parent_win)

    # ── Block 6: Zeile löschen / Feld editieren ─────────────────────────────
    def _tabelle_auswaehlen_dialog(tabellen_liste):
        """Zeigt Auswahldialog, gibt gewählten Namen zurück oder None."""
        if not tabellen_liste:
            messagebox.showwarning("Tabelle wählen",
                "Keine Tabellen gefunden.", parent=parent_win)
            return None
        dlg = tk.Toplevel(parent_win)
        dlg.title("Zieltabelle auswählen")
        dlg.geometry("360x300")
        dlg.resizable(False, True)
        dlg.grab_set()
        dlg.transient(parent_win)
        tk.Label(dlg, text="Bitte Zieltabelle auswählen:", anchor="w").pack(
            fill="x", padx=12, pady=(10, 4))
        lf = tk.Frame(dlg)
        lf.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        lb = tk.Listbox(lf, selectmode="browse", activestyle="dotbox")
        lb.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(lf, orient="vertical", command=lb.yview).grid(row=0, column=1, sticky="ns")
        for t in tabellen_liste:
            lb.insert("end", t)
        lb.selection_set(0)
        ergebnis = [None]
        def _ok(event=None):
            sel = lb.curselection()
            if sel:
                ergebnis[0] = tabellen_liste[sel[0]]
            dlg.destroy()
        lb.bind("<Double-1>", _ok)
        lb.bind("<Return>", _ok)
        bf = tk.Frame(dlg)
        bf.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(bf, text="OK",        width=10, command=_ok).pack(side="right", padx=(4, 0))
        tk.Button(bf, text="Abbrechen", width=10, command=dlg.destroy).pack(side="right")
        dlg.wait_window()
        return ergebnis[0]

    def _echte_tabelle_ermitteln():
        """Gibt echten DB-Tabellennamen zurück oder öffnet Auswahl-Dialog. None = Abbruch."""
        import re as _re
        kandidat = (tabellenname or "").strip()
        # 1. tabellenname direkt testen (kein Leerzeichen/Komma → kein JOIN-Ausdruck)
        if kandidat and not _re.search(r'[\s,]', kandidat):
            try:
                vb = sqlite_verbindung_oeffnen()
                row = vb.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=? COLLATE NOCASE",
                    (kandidat,)).fetchone()
                vb.close()
                if row:
                    return row[0]
            except Exception:
                pass
        # 2. Aus SQL-Hint extrahieren
        tabs = []
        if sql_text_hint:
            try:
                found = _re.findall(
                    r'\b(?:FROM|JOIN|INTO|UPDATE)\s+[`"\[]?(\w+)[`"\]]?',
                    sql_text_hint, _re.IGNORECASE)
                seen = set()
                for t in found:
                    tl = t.lower()
                    if tl not in seen:
                        seen.add(tl)
                        tabs.append(t)
            except Exception:
                pass
        if len(tabs) == 1:
            return tabs[0]
        if len(tabs) > 1:
            return _tabelle_auswaehlen_dialog(tabs)
        # 3. Alle DB-Tabellen anzeigen
        alle = []
        try:
            vb = sqlite_verbindung_oeffnen()
            alle = [r[0] for r in vb.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            vb.close()
        except Exception:
            pass
        return _tabelle_auswaehlen_dialog(alle)

    def _id_feld_ermitteln(spalten):
        """Findet das ID-Feld: erste Spalte namens 'id'/'ID', sonst erste Spalte."""
        for sp in spalten:
            if sp.lower() == "id":
                return sp
        return spalten[0] if spalten else None

    def zeile_loeschen():
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            messagebox.showwarning("Zeile löschen",
                "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        tabname = _echte_tabelle_ermitteln()
        if not tabname:
            return
        # Admin-Check für geschützte Tabellen
        if not admin_code_fuer_aktion_pruefen(tabname, "löschen"):
            return
        # ID-Feld ermitteln
        alle_sp = _alle_sp()
        id_feld = _id_feld_ermitteln(alle_sp)
        if not id_feld:
            messagebox.showwarning("Zeile löschen", "Keine Spalten gefunden.", parent=parent_win)
            return
        werte = tv_widget.item(iid, "values")
        id_idx = alle_sp.index(id_feld)
        id_wert = werte[id_idx] if id_idx < len(werte) else None
        if id_wert is None or str(id_wert).strip() == "":
            messagebox.showwarning("Zeile löschen",
                f"ID-Feld '{id_feld}' hat keinen Wert.", parent=parent_win)
            return
        zeil_text = " | ".join(str(v) for v in list(werte)[:5])
        if not messagebox.askyesno(
                "Zeile löschen",
                f"Tabelle:  {tabname}\n"
                f"ID-Feld:  {id_feld} = {id_wert}\n\n"
                f"Zeile:  {zeil_text}\n\n"
                f"Wirklich löschen?", parent=parent_win):
            return
        try:
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"DELETE FROM {sql_identifier(tabname)} WHERE {sql_identifier(id_feld)}=?",
                (id_wert,))
            vb.commit()
            vb.close()
        except Exception as e:
            messagebox.showerror("Zeile löschen", f"Fehler:\n{e}", parent=parent_win)
            return
        tv_widget.delete(iid)
        try:
            idx2 = alle_sp.index(id_feld)
            zeilen_ref["alle"] = [
                z for z in zeilen_ref["alle"]
                if not (len(z) > idx2 and str(z[idx2]) == str(id_wert))
            ]
        except Exception:
            pass
        sql_logging_eintrag_sicher_schreiben(
            f"Zeile gelöscht: {tabname} WHERE {id_feld}={id_wert}", 0)

    def feld_editieren():
        iid = _lok["item"] or (tv_widget.selection()[0] if tv_widget.selection() else None)
        if not iid:
            messagebox.showwarning("Feld editieren",
                "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        sp_name = _sp_name()
        if sp_name is None:
            sp_sicht = _sichtb()
            if not sp_sicht:
                messagebox.showwarning("Feld editieren",
                    "Keine Spalten vorhanden.", parent=parent_win)
                return
            sp_name = sp_sicht[0]
        tabname = _echte_tabelle_ermitteln()
        if not tabname:
            return
        # Admin-Check für geschützte Tabellen
        if not admin_code_fuer_aktion_pruefen(tabname, "editieren"):
            return
        # ID-Feld und Werte
        alle_sp = _alle_sp()
        id_feld = _id_feld_ermitteln(alle_sp)
        if not id_feld:
            messagebox.showwarning("Feld editieren", "Keine Spalten gefunden.", parent=parent_win)
            return
        werte  = tv_widget.item(iid, "values")
        id_idx = alle_sp.index(id_feld)
        id_wert  = werte[id_idx] if id_idx < len(werte) else None
        sp_idx   = alle_sp.index(sp_name) if sp_name in alle_sp else None
        alt_wert = str(werte[sp_idx]) if sp_idx is not None and sp_idx < len(werte) else ""
        # Edit-Dialog
        dlg = tk.Toplevel(parent_win)
        dlg.title("Feld editieren")
        dlg.geometry("500x230")
        dlg.resizable(True, False)
        dlg.grab_set()
        dlg.transient(parent_win)
        dlg.columnconfigure(1, weight=1)
        tk.Label(dlg, text="Tabelle:",        anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        tk.Label(dlg, text=tabname,           anchor="w").grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(12, 2))
        tk.Label(dlg, text=f"ID ({id_feld}):", anchor="w").grid(row=1, column=0, sticky="w", padx=16, pady=(2, 2))
        tk.Label(dlg, text=str(id_wert),      anchor="w").grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(2, 2))
        tk.Label(dlg, text="Feld:",           anchor="w").grid(row=2, column=0, sticky="w", padx=16, pady=(2, 2))
        tk.Label(dlg, text=sp_name,           anchor="w").grid(row=2, column=1, sticky="w", padx=(0, 16), pady=(2, 2))
        tk.Label(dlg, text="Neuer Wert:",     anchor="w").grid(row=3, column=0, sticky="w", padx=16, pady=(10, 2))
        entry = tk.Entry(dlg, width=50)
        entry.grid(row=3, column=1, sticky="ew", padx=(0, 16), pady=(10, 2))
        entry.insert(0, alt_wert)
        entry.select_range(0, "end")
        entry.focus_set()
        ergebnis = [None]
        def _ok(event=None):
            ergebnis[0] = entry.get()
            dlg.destroy()
        entry.bind("<Return>", _ok)
        entry.bind("<Escape>", lambda e: dlg.destroy())
        bf = tk.Frame(dlg)
        bf.grid(row=4, column=0, columnspan=2, pady=(12, 12))
        tk.Button(bf, text="Speichern", width=12, command=_ok).pack(side="right", padx=(8, 16))
        tk.Button(bf, text="Abbrechen", width=12, command=dlg.destroy).pack(side="right")
        dlg.wait_window()
        if ergebnis[0] is None:
            return
        neu_wert = ergebnis[0]
        if neu_wert == alt_wert:
            return
        try:
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"UPDATE {sql_identifier(tabname)} "
                f"SET {sql_identifier(sp_name)}=? WHERE {sql_identifier(id_feld)}=?",
                (neu_wert, id_wert))
            vb.commit()
            vb.close()
        except Exception as e:
            messagebox.showerror("Feld editieren", f"Fehler:\n{e}", parent=parent_win)
            return
        # Treeview-Zeile aktualisieren
        neue_werte = list(werte)
        if sp_idx is not None and sp_idx < len(neue_werte):
            neue_werte[sp_idx] = neu_wert
        tv_widget.item(iid, values=neue_werte)
        # zeilen_ref["alle"] aktualisieren
        try:
            zeilen_ref["alle"] = [
                tuple(neu_wert if i == sp_idx else v for i, v in enumerate(z))
                if len(z) > id_idx and str(z[id_idx]) == str(id_wert)
                else z
                for z in zeilen_ref["alle"]
            ]
        except Exception:
            pass
        sql_logging_eintrag_sicher_schreiben(
            f"Feld editiert: {tabname}.{sp_name} "
            f"WHERE {id_feld}={id_wert}: "
            f"'{alt_wert[:50]}' → '{neu_wert[:50]}'", 0)

    # ── Block 7: Beziehungen / Navigation ───────────────────────────────────
    def definierte_beziehungen_anzeigen():
        try:
            _vb_br = sqlite_verbindung_oeffnen()
            _rels  = _vb_br.execute(
                "SELECT Bezeichnung, Typ, QuellTabelle, QuellFeld, "
                "ZielTabelle, ZielFeld "
                "FROM zzz_Relationen "
                "WHERE QuellTabelle=? OR ZielTabelle=? "
                "ORDER BY Bezeichnung",
                (tabellenname, tabellenname)
            ).fetchall()
            _vb_br.close()
        except Exception as _e_br:
            messagebox.showwarning("Beziehungen",
                f"Fehler:\n{_e_br}", parent=parent_win)
            return
        if not _rels:
            messagebox.showinfo("Beziehungen",
                f"Für '{tabellenname}' sind keine Beziehungen definiert.",
                parent=parent_win)
            return
        _txt = f"Definierte Beziehungen für Tabelle '{tabellenname}':\n\n"
        for _bez, _typ, _qt, _qf, _zt, _zf in _rels:
            _richtung = "→" if _qt == tabellenname else "←"
            _txt += (f"  [{_typ}]  {_bez or '(ohne Bezeichnung)'}\n"
                     f"    {_qt}.{_qf}  {_richtung}  {_zt}.{_zf}\n\n")
        sql_text_im_lesefenster_anzeigen(
            parent_win, f"Beziehungen: {tabellenname}", _txt)

    def in_vorhergehender_tabelle_zeigen():
        if not _lok["item"]:
            messagebox.showwarning("Vorherige Tabelle",
                "Bitte zuerst eine Zeile auswählen.", parent=parent_win)
            return
        try:
            _vb_vt = sqlite_verbindung_oeffnen()
            _vt_rels = _vb_vt.execute(
                "SELECT Bezeichnung, QuellTabelle, QuellFeld, ZielFeld "
                "FROM zzz_Relationen WHERE ZielTabelle=? "
                "ORDER BY Bezeichnung",
                (tabellenname,)
            ).fetchall()
            _vb_vt.close()
        except Exception as _e_vt:
            messagebox.showwarning("Vorherige Tabelle",
                f"Fehler:\n{_e_vt}", parent=parent_win)
            return
        if not _vt_rels:
            messagebox.showinfo("Vorherige Tabelle",
                f"Keine Beziehung gefunden, bei der '{tabellenname}' "
                f"die Zieltabelle ist.",
                parent=parent_win)
            return
        # Falls mehrere Beziehungen: erste nehmen (oder auswählen lassen)
        _vt_bez, _vt_qt, _vt_qf, _vt_zf = _vt_rels[0]
        _alle_sp = _alle_sp()
        _werte   = tv_widget.item(_lok["item"], "values")
        _zf_wert = None
        if _vt_zf in _alle_sp:
            _zi = _alle_sp.index(_vt_zf)
            _zf_wert = _werte[_zi] if _zi < len(_werte) else None
        if not _zf_wert:
            messagebox.showinfo("Vorherige Tabelle",
                f"Verknüpfungsfeld '{_vt_zf}' nicht in der aktuellen Anzeige.\n"
                f"Quelltabelle wäre: {_vt_qt}",
                parent=parent_win)
            return
        try:
            _vb_vt2 = sqlite_verbindung_oeffnen()
            _cur_vt  = _vb_vt2.cursor()
            _cur_vt.execute(
                f"SELECT * FROM {sql_identifier(_vt_qt)} "
                f"WHERE {sql_identifier(_vt_qf)}=?",
                (_zf_wert,)
            )
            _rows_vt = _cur_vt.fetchall()
            _cols_vt = ([d[0] for d in _cur_vt.description]
                        if _cur_vt.description else [])
            _vb_vt2.close()
        except Exception as _e_vt2:
            messagebox.showwarning("Vorherige Tabelle",
                f"Fehler beim Laden aus '{_vt_qt}':\n{_e_vt2}",
                parent=parent_win)
            return
        if not _rows_vt:
            messagebox.showinfo("Vorherige Tabelle",
                f"Kein Eintrag in '{_vt_qt}' "
                f"wo {_vt_qf} = '{_zf_wert}'.",
                parent=parent_win)
            return
        _txt_vt = (f"Vorherige Tabelle: {_vt_qt}\n"
                   f"Beziehung: {_vt_bez or '(ohne Bezeichnung)'}\n"
                   f"Filter: {_vt_qf} = '{_zf_wert}'\n\n")
        for _row_vt in _rows_vt[:20]:
            for _col_vt, _val_vt in zip(_cols_vt, _row_vt):
                _txt_vt += f"  {_col_vt}: {_val_vt}\n"
            _txt_vt += "\n"
        sql_text_im_lesefenster_anzeigen(
            parent_win, f"Vorherige Tabelle: {_vt_qt}", _txt_vt)

    # ── Rechtsklick-Event ────────────────────────────────────────────────────
    def rechtsklick(event):
        region = tv_widget.identify_region(event.x, event.y)
        if region == "heading":
            m = tk.Menu(parent_win, tearoff=0)
            _tv_spalten_menue_aufbauen(m, tv_widget, alle_sp_anzeigen)
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
            return
        item_id = tv_widget.identify_row(event.y)
        spalte_id = tv_widget.identify_column(event.x)
        if item_id:
            tv_widget.focus(item_id)
            tv_widget.selection_set(item_id)
        _lok["item"]   = item_id
        _lok["spalte"] = spalte_id
        m = tk.Menu(parent_win, tearoff=0)
        # Optionale benutzerdefinierte Einträge zuerst (SQL-Editor-spezifische Aktionen)
        if callable(extra_menue_fn):
            n_before = m.index("end")
            extra_menue_fn(m, item_id, _sp_name())
            n_after = m.index("end")
            if n_after is not None and n_after != n_before:
                m.add_separator()
        # Block 1: Kopieren
        m.add_command(label="Feldinhalt kopieren",       command=feld_kopieren)
        m.add_command(label="Zeile kopieren",            command=zeile_kopieren)
        m.add_command(label="Zeile als CSV kopieren",    command=zeile_als_csv_kopieren)
        m.add_command(label="Header als CSV kopieren",   command=header_als_csv_kopieren)
        m.add_command(label="Tabelle als CSV kopieren",  command=tabelle_als_csv_kopieren)
        m.add_separator()
        # Block 2: Anzeigen
        m.add_command(label="Feldinhalt im Lesefenster anzeigen", command=feld_im_lesefenster)
        m.add_command(label="Zeile im Lesefenster anzeigen",      command=zeile_im_lesefenster)
        m.add_command(label="Daten optimal",                      command=alle_sp_anzeigen)
        m.add_command(label="Spaltennamen optimal",               command=lambda: _tv_spalten_minimum(tv_widget))
        m.add_command(label="Alle Spaltennamen vollständig anzeigen", command=alle_sp_anzeigen)
        m.add_separator()
        # Block 3: Filtern
        m.add_command(label="Feldfilter setzen",             command=filter_dialog_oeffnen)
        m.add_command(label="Feldfilter aufheben",           command=filter_aufheben)
        m.add_command(label="Eindeutige Feldwerte anzeigen", command=eindeutige_werte_anzeigen)
        m.add_separator()
        # Block 4: IP / Netzwerk
        m.add_command(label="IP-Range aufteilen",                    command=ip_range_aufteilen_lokal)
        m.add_command(label="IP / Netz vollständig analysieren",   command=ip_vollstaendig_analysieren)
        m.add_command(label="Überschneidungen in Spalte suchen",   command=ip_ueberschneidungen_suchen)
        m.add_command(label="Überschneidungen in Kette suchen",    command=ip_ueberschneidungen_in_kette_suchen)
        m.add_separator()
        # Block 5: Finding
        m.add_command(label="Finding aufrufen",                command=finding_aufrufen)
        m.add_command(label="Finding hinzufügen",              command=finding_hinzufuegen)
        # Block 6: Zeile löschen / Feld editieren
        if db_edit:
            m.add_separator()
            m.add_command(label="Zeile löschen",  command=zeile_loeschen)
            m.add_command(label="Feld editieren",  command=feld_editieren)
        # Block 7: Tabellenbeziehungen / Navigation
        m.add_separator()
        m.add_command(label="Definierte Beziehungen anzeigen",
                      command=definierte_beziehungen_anzeigen)
        m.add_command(label="In vorhergehender Tabelle zeigen",
                      command=nav_override_fn if nav_override_fn else in_vorhergehender_tabelle_zeigen)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    tv_widget.bind("<Button-3>", rechtsklick)
    return zeilen_ref


def _workflow_ketten_fenster_oeffnen(rel_id_str, projektname):
    """Öffnet ein Master-Detail-Fenster für eine Kettenbeziehung (Workflow-Typ Kette).
    rel_id_str: ID der Beziehung in zzz_Relationen als String."""
    import json as _json
    G_TABELLE_REL = "zzz_Relationen"

    # Bereits offen?
    if rel_id_str in _workflow_offene_ketten_fenster:
        f = _workflow_offene_ketten_fenster[rel_id_str]
        try:
            if f and f.winfo_exists():
                f.lift()
                f.focus_force()
                return f
        except Exception:
            pass
        _workflow_offene_ketten_fenster.pop(rel_id_str, None)

    # Beziehungsdaten laden
    try:
        vb = sqlite_verbindung_oeffnen()
        # Sicherstellen dass neue Spalten vorhanden sind
        for _cm in [
            f"ALTER TABLE {sql_identifier(G_TABELLE_REL)} ADD COLUMN Kette TEXT",
            f"ALTER TABLE {sql_identifier(G_TABELLE_REL)} ADD COLUMN AnzeigenFelder TEXT",
            f"ALTER TABLE {sql_identifier(G_TABELLE_REL)} ADD COLUMN QuellFelder TEXT",
        ]:
            try:
                vb.execute(_cm)
            except Exception:
                pass
        vb.commit()
        row = vb.execute(
            f"SELECT Bezeichnung, QuellTabelle, QuellFeld, ZielTabelle, ZielFeld, "
            f"Kette, AnzeigenFelder, QuellFelder "
            f"FROM {sql_identifier(G_TABELLE_REL)} WHERE id=?",
            (int(rel_id_str),)
        ).fetchone()
        vb.close()
    except Exception as e:
        messagebox.showerror("Ketten-Fenster", f"Fehler beim Laden der Beziehung:\n{e}")
        return None

    if not row:
        messagebox.showwarning("Ketten-Fenster",
                               f"Beziehung #{rel_id_str} nicht gefunden.")
        return None

    bez, qt, qf, zt, zf, kette_raw, anzeigen_raw, quell_raw = row
    bez = bez or f"{qt} → {zt}"
    kette_liste    = []
    quell_felder   = [f.strip() for f in (quell_raw  or "").split(",") if f.strip()]
    anzeigen_felder= [f.strip() for f in (anzeigen_raw or "").split(",") if f.strip()]
    try:
        if kette_raw:
            kette_liste = _json.loads(kette_raw)
    except Exception:
        pass

    # Rückwärtskompatibilität: Hat kein Schritt ein "aktiv"-Feld?
    # → nur letzten Schritt aktiv; AnzeigenFelder aus DB für letzten Schritt verwenden.
    _any_has_aktiv_kf = any("aktiv" in s for s in kette_liste)
    if not _any_has_aktiv_kf and kette_liste:
        for _ki, _ks in enumerate(kette_liste):
            _ks.setdefault("aktiv", _ki == len(kette_liste) - 1)
            _ks.setdefault("felder", anzeigen_felder if _ki == len(kette_liste) - 1 else [])

    def _get_felder_kf(tab):
        """Gibt alle Spalten einer Tabelle zurück (Hilfsfunktion im Ketten-Fenster)."""
        try:
            _vb = sqlite_verbindung_oeffnen()
            _cols = [r[1] for r in _vb.execute(
                f"PRAGMA table_info({sql_identifier(tab)})"
            ).fetchall()]
            _vb.close()
            return _cols
        except Exception:
            return []

    # Fenster aufbauen
    win = tk.Toplevel(root)
    _workflow_offene_ketten_fenster[rel_id_str] = win
    win.title(f"⛓ {bez} — Kette  —  {projektname}")
    win.geometry("1100x660")
    win.minsize(500, 340)
    fenster_registrieren(win, "Kette", bez)
    kf_menue = fenster_standard_menue_anbringen(win, "1100x660", f"Kette: {bez}")
    # Titel NACH fenster_standard_menue_anbringen setzen, damit er nicht überschrieben wird
    win.title(f"⛓ {bez} — Kette  —  {projektname}")

    def _schliessen():
        _workflow_offene_ketten_fenster.pop(rel_id_str, None)
        try:
            win.destroy()
        except Exception:
            pass
    win.protocol("WM_DELETE_WINDOW", _schliessen)

    # ── Hilfs-Sortierfunktion für beide Treeviews ────────────────────────────
    _sort_richtung = {}   # {(id(tv), spaltenname): aufsteigend_bool}

    def _tv_ketten_sortiere(tv, sp):
        """Sortiert den Treeview tv nach Spalte sp, togglet ▲/▼."""
        alle = list(tv["columns"])
        if not alle:
            return
        # displaycolumns kann als String "#all" oder Tuple ("#all",) kommen
        dc_raw = tv["displaycolumns"]
        if isinstance(dc_raw, str):
            dc_list = [dc_raw] if dc_raw else []
        else:
            dc_list = [str(x) for x in dc_raw if x]
        sichtb = alle if (not dc_list or "#all" in dc_list) else dc_list

        key = (id(tv), sp)
        aufsteigend = not _sort_richtung.get(key, False)  # erster Klick = aufsteigend
        _sort_richtung[key] = aufsteigend

        items = [(tv.item(iid, "values"), iid) for iid in tv.get_children()]
        try:
            idx = alle.index(sp)
        except ValueError:
            return

        def _sk(item):
            v = item[0][idx] if idx < len(item[0]) else ""
            vs = str(v).strip()
            ip_int = _ip_zu_int(vs)
            if ip_int is not None:
                return (0, ip_int, "")
            try:
                return (1, float(vs.replace(",", ".")), "")
            except (ValueError, TypeError):
                return (2, 0, vs.lower())

        items.sort(key=_sk, reverse=not aufsteigend)
        for _, iid in items:
            tv.move(iid, "", "end")
        for s in sichtb:
            pf = " ▲" if s == sp and aufsteigend else (" ▼" if s == sp else "")
            tv.heading(s, text=s + pf, anchor="w",
                       command=lambda c=s, t=tv: _tv_ketten_sortiere(t, c))

    haupt = tk.Frame(win)
    haupt.pack(fill="both", expand=True, padx=6, pady=6)
    haupt.columnconfigure(0, weight=1)
    haupt.rowconfigure(1, weight=1)   # Quelltabelle
    haupt.rowconfigure(5, weight=1)   # Zieltabelle (verschoben wegen Checkbox-Leiste)

    # ── Quelltabelle (oben) ───────────────────────────────────────────────────
    quell_titel = f"Quelltabelle: {qt}"
    if quell_felder:
        quell_titel += f"  [{', '.join(quell_felder)}]"
    _quell_lbl = tk.Label(haupt, text=quell_titel, anchor="w",
             font=("Segoe UI", 9, "bold"))
    _quell_lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

    quell_frame = tk.Frame(haupt)
    quell_frame.grid(row=1, column=0, sticky="nsew")
    quell_frame.columnconfigure(0, weight=1)
    quell_frame.rowconfigure(0, weight=1)

    # Join-Schlüssel (qf) muss immer im Query sein; falls nicht in quell_felder, wird er
    # als versteckte Spalte mitgeladen (nicht in displaycolumns).
    try:
        vb2 = sqlite_verbindung_oeffnen()
        if quell_felder:
            # qf hinzufügen falls noch nicht enthalten (als letzten unsichtbaren Wert)
            felder_mit_qf = list(quell_felder)
            qf_hidden = qf not in felder_mit_qf
            if qf_hidden:
                felder_mit_qf.append(qf)
            quell_spalten = felder_mit_qf
            quell_sql = (f"SELECT {', '.join(sql_identifier(c) for c in felder_mit_qf)} "
                         f"FROM {sql_identifier(qt)}")
            angezeigte_spalten = list(quell_felder)   # ohne qf, wenn hidden
        else:
            quell_spalten = [r[1] for r in vb2.execute(
                f"PRAGMA table_info({sql_identifier(qt)})"
            ).fetchall()]
            quell_sql = f"SELECT * FROM {sql_identifier(qt)}"
            angezeigte_spalten = list(quell_spalten)
            qf_hidden = False
        cursor_q = vb2.cursor()
        cursor_q.execute(quell_sql)
        quell_zeilen = cursor_q.fetchall()
        vb2.close()
        _quell_lbl.config(
            text=quell_titel + f"  ·  {len(quell_zeilen)} Datensätze")
    except Exception as e:
        quell_zeilen = []
        quell_spalten = []
        angezeigte_spalten = []
        qf_hidden = False
        messagebox.showwarning("Ketten-Fenster",
                               f"Quelltabelle konnte nicht geladen werden:\n{e}", parent=win)

    quell_tv = ttk.Treeview(quell_frame, columns=quell_spalten,
                             displaycolumns=angezeigte_spalten,
                             show="headings", selectmode="browse")
    for sp in angezeigte_spalten:
        quell_tv.heading(sp, text=sp, anchor="w",
                         command=lambda c=sp: _tv_ketten_sortiere(quell_tv, c))
        quell_tv.column(sp, width=80, anchor="w", minwidth=40, stretch=False)
    for zeile in quell_zeilen:
        quell_tv.insert("", "end", values=[str(v) if v is not None else "" for v in zeile])
    _tv_spalten_auto_breite(quell_tv, angezeigte_spalten, quell_zeilen)
    q_sy = ttk.Scrollbar(quell_frame, orient="vertical",   command=quell_tv.yview)
    q_sx = ttk.Scrollbar(quell_frame, orient="horizontal", command=quell_tv.xview)
    quell_tv.configure(yscrollcommand=q_sy.set, xscrollcommand=q_sx.set)
    q_sy.grid(row=0, column=1, sticky="ns")
    q_sx.grid(row=1, column=0, sticky="ew")
    quell_tv.grid(row=0, column=0, sticky="nsew")

    # ── Trennlinie ───────────────────────────────────────────────────────────
    ttk.Separator(haupt, orient="horizontal").grid(
        row=2, column=0, sticky="ew", pady=(6, 2))

    # ── Live-Checkbox-Leiste: welche Schritte im Ergebnis erscheinen ──────────
    schritt_aktiv_vars = []   # tk.BooleanVar pro Schritt
    cb_leiste_frame = tk.Frame(haupt)
    cb_leiste_frame.grid(row=3, column=0, sticky="ew", padx=2, pady=(0, 2))

    def _ziel_neu_laden_bei_cb_change():
        """Wird aufgerufen wenn eine Schritt-Checkbox geändert wird."""
        sel = quell_tv.selection()
        if not sel:
            return
        werte = quell_tv.item(sel[0], "values")
        if qf in quell_spalten:
            idx = quell_spalten.index(qf)
            quell_wert = werte[idx] if idx < len(werte) else ""
        else:
            quell_wert = werte[0] if werte else ""
        _ziel_laden(quell_wert)

    if kette_liste:
        tk.Label(cb_leiste_frame, text="Schritte im Ergebnis:",
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 6))
        for _cb_i, _cb_s in enumerate(kette_liste):
            _cb_var = tk.BooleanVar(value=_cb_s.get("aktiv", _cb_i == len(kette_liste) - 1))
            schritt_aktiv_vars.append(_cb_var)
            _cb_label = f"Schritt {_cb_i+1}: {_cb_s.get('zu_tab', '?')}"
            tk.Checkbutton(cb_leiste_frame, text=_cb_label, variable=_cb_var,
                           command=_ziel_neu_laden_bei_cb_change
                           ).pack(side="left", padx=(0, 8))
    else:
        schritt_aktiv_vars = []

    # ── Zieltabelle / kombiniertes Ergebnis (unten) ───────────────────────────
    ziel_titel_lbl = tk.Label(haupt, text="Ergebnis  —  bitte oben auswählen",
                              anchor="w", font=("Segoe UI", 9, "bold"))
    ziel_titel_lbl.grid(row=4, column=0, sticky="w", pady=(0, 2))

    ziel_frame = tk.Frame(haupt)
    ziel_frame.grid(row=5, column=0, sticky="nsew")
    ziel_frame.columnconfigure(0, weight=1)
    ziel_frame.rowconfigure(0, weight=1)

    ziel_spalten_cache = [None]   # wird beim ersten Laden befüllt
    ziel_tv = ttk.Treeview(ziel_frame, columns=(), show="headings", selectmode="browse")
    z_sy = ttk.Scrollbar(ziel_frame, orient="vertical",   command=ziel_tv.yview)
    z_sx = ttk.Scrollbar(ziel_frame, orient="horizontal", command=ziel_tv.xview)
    ziel_tv.configure(yscrollcommand=z_sy.set, xscrollcommand=z_sx.set)
    z_sy.grid(row=0, column=1, sticky="ns")
    z_sx.grid(row=1, column=0, sticky="ew")
    ziel_tv.grid(row=0, column=0, sticky="nsew")

    def _ziel_laden(quell_wert):
        """Führt die Ketten-JOIN-Abfrage durch und befüllt das kombinierte Zielergebnis."""
        if quell_wert is None:
            return
        try:
            vb3 = sqlite_verbindung_oeffnen()
            if kette_liste:
                # Aliases für alle Tabellen (Quelltabelle + alle Schritt-Tabellen)
                aliases = [f"_kt{i}" for i in range(len(kette_liste) + 1)]

                # Aktive Schritte (von den Live-Checkboxes)
                aktive_idx = [i for i in range(len(kette_liste))
                              if i < len(schritt_aktiv_vars) and schritt_aktiv_vars[i].get()]

                if not aktive_idx:
                    # Kein Schritt aktiv → leeres Ergebnis anzeigen
                    spalten = ["(kein Schritt aktiv — bitte Checkbox setzen)"]
                    zeilen  = []
                else:
                    # Felder pro aktivem Schritt einsammeln
                    from collections import Counter as _Counter
                    felder_pro_schritt = []
                    for i in aktive_idx:
                        s   = kette_liste[i]
                        tab = s["zu_tab"]
                        als = aliases[i + 1]
                        sf  = s.get("felder", [])
                        if not sf:
                            sf = _get_felder_kf(tab)
                        felder_pro_schritt.append((i, tab, als, sf))

                    # Konflikte erkennen: Feldname kommt in mehr als einem Schritt vor
                    alle_namen = [f for (_, _, _, fl) in felder_pro_schritt for f in fl]
                    feld_zaehler = _Counter(alle_namen)

                    # SELECT aufbauen
                    select_parts = []
                    spalten      = []
                    for (i, tab, als, felder) in felder_pro_schritt:
                        for f in felder:
                            col_alias = f"{tab}.{f}" if feld_zaehler[f] > 1 else f
                            select_parts.append(
                                f"{als}.{sql_identifier(f)} AS {sql_identifier(col_alias)}")
                            spalten.append(col_alias)

                    # JOIN-Kette (alle Schritte, nicht nur aktive!)
                    joins = " ".join(
                        f"LEFT JOIN {sql_identifier(s['zu_tab'])} {aliases[i+1]} "
                        f"ON {aliases[i+1]}.{sql_identifier(s['zu_feld'])} "
                        f"= {aliases[i]}.{sql_identifier(s['von_feld'])}"
                        for i, s in enumerate(kette_liste)
                    )
                    sql_z = (f"SELECT {', '.join(select_parts)} "
                             f"FROM {sql_identifier(qt)} {aliases[0]} "
                             f"{joins} WHERE {aliases[0]}.{sql_identifier(qf)}=?")
                    cur = vb3.cursor()
                    cur.execute(sql_z, (quell_wert,))
                    zeilen = cur.fetchall()
            else:
                # Kein Ketten-JSON: einfache Abfrage auf Zieltabelle
                cur = vb3.cursor()
                cur.execute(
                    f"SELECT * FROM {sql_identifier(zt)} "
                    f"WHERE {sql_identifier(zf)}=?",
                    (quell_wert,)
                )
                spalten = [d[0] for d in cur.description]
                zeilen  = cur.fetchall()
            vb3.close()
        except Exception as e:
            messagebox.showwarning("Ketten-Fenster",
                                   f"Fehler beim Laden des Ergebnisses:\n{e}", parent=win)
            return

        # Treeview neu konfigurieren wenn Spalten sich geändert haben
        if ziel_spalten_cache[0] != spalten:
            ziel_spalten_cache[0] = spalten
            ziel_tv.configure(columns=spalten)
            for sp in spalten:
                ziel_tv.heading(sp, text=sp, anchor="w",
                                command=lambda c=sp: _tv_ketten_sortiere(ziel_tv, c))
                ziel_tv.column(sp, width=80, anchor="w", minwidth=40, stretch=False)
        # Auto-Sort: erste IP-Spalte erkennen, Zeilen aufsteigend sortieren
        _probe_z = zeilen[:20]
        _ip_sp_idx = None
        for _zi in range(len(spalten)):
            if sum(1 for _zr in _probe_z if _zi < len(_zr) and
                   _ip_zu_int(str(_zr[_zi]).strip()) is not None
                   ) >= max(1, len(_probe_z) // 2):
                _ip_sp_idx = _zi
                break
        if _ip_sp_idx is not None:
            zeilen = sorted(zeilen,
                key=lambda _r: _ip_zu_int(str(_r[_ip_sp_idx]).strip()) or (1 << 32))
        ziel_tv.delete(*ziel_tv.get_children())
        for zeile in zeilen:
            ziel_tv.insert("", "end", values=[str(v) if v is not None else "" for v in zeile])
        _tv_spalten_auto_breite(ziel_tv, spalten, zeilen)
        ziel_titel_lbl.config(
            text=f"Ergebnis  —  {len(zeilen)} Datensätze  ({qf} = '{quell_wert}')")

    def _on_quell_select(event=None):
        sel = quell_tv.selection()
        if not sel:
            return
        # QuellFeld-Wert aus der gewählten Zeile holen (qf ist immer in quell_spalten enthalten)
        werte = quell_tv.item(sel[0], "values")
        if qf in quell_spalten:
            idx = quell_spalten.index(qf)
            quell_wert = werte[idx] if idx < len(werte) else ""
        else:
            quell_wert = werte[0] if werte else ""
        _ziel_laden(quell_wert)

    # ── Vollständiges Rechtsklick-Menü für beide Treeviews ───────────────────
    def _ketten_tv_rechtsklick_anbinden(tv_widget, tabellenname):
        """Delegiert an die zentrale Rechtsklick-Funktion."""
        return standard_tv_rechtsklick_anbinden(tv_widget, tabellenname, win)

    # Menus anbinden
    q_ref = _ketten_tv_rechtsklick_anbinden(quell_tv, qt)
    q_ref["alle"] = [quell_tv.item(iid, "values") for iid in quell_tv.get_children()]

    z_ref = _ketten_tv_rechtsklick_anbinden(ziel_tv, zt)

    # _ziel_laden erweitern: z_ref["alle"] nach jedem Reload aktualisieren
    _ziel_laden_orig = _ziel_laden

    def _ziel_laden_mit_ref(quell_wert):
        _ziel_laden_orig(quell_wert)
        z_ref["alle"] = [ziel_tv.item(iid, "values") for iid in ziel_tv.get_children()]
        z_ref.update({"filter_aktiv": False, "filter_spalte": None, "filter_wert": None})

    # _ziel_laden auf _ziel_laden_mit_ref umbiegen, damit auch Checkbox-Callbacks z_ref aktualisieren
    _ziel_laden = _ziel_laden_mit_ref  # noqa: F841

    # Selektion in Quelltabelle → Zieltabelle aktualisieren
    def _on_quell_select(event=None):
        if not quell_tv.selection():
            return
        _qw = (quell_tv.item(quell_tv.selection()[0], "values")[quell_spalten.index(qf)]
               if qf in quell_spalten else None)
        _ziel_laden_mit_ref(_qw)

    quell_tv.bind("<<TreeviewSelect>>", _on_quell_select)

    win.focus_set()
    return win


def _workflow_abfrage_fenster_oeffnen_modul(abfragename):
    """Öffnet ein eigenständiges Ergebnisfenster für eine gespeicherte SQL-Abfrage."""
    if abfragename in _workflow_offene_sql_fenster:
        try:
            _workflow_offene_sql_fenster[abfragename].lift()
            _workflow_offene_sql_fenster[abfragename].focus_force()
            return _workflow_offene_sql_fenster[abfragename]
        except Exception:
            del _workflow_offene_sql_fenster[abfragename]
    sql_text = abfrage_sql_text_laden(abfragename)
    if not sql_text:
        messagebox.showerror("SQL-Abfrage öffnen", f"SQL-Text für '{abfragename}' nicht gefunden.")
        return None
    res = tk.Toplevel(root)
    _workflow_offene_sql_fenster[abfragename] = res
    res.title(f"SQL-Abfrage: {abfragename}")
    res.geometry("1000x600")
    res.minsize(300, 80)
    fenster_registrieren(res, "SQL-Abfrage")

    def _schliessen():
        _workflow_offene_sql_fenster.pop(abfragename, None)
        res.destroy()

    res_menue = fenster_standard_menue_anbringen(res, "1000x600", f"Workflow-SQL: {abfragename}")
    res_menue.add_command(label="Schließen", command=_schliessen)
    res.protocol("WM_DELETE_WINDOW", _schliessen)

    tv_frame = tk.Frame(res)
    tv_frame.pack(fill="both", expand=True, padx=6, pady=6)
    tv_frame.grid_rowconfigure(0, weight=1)
    tv_frame.grid_columnconfigure(0, weight=1)

    tv = ttk.Treeview(tv_frame, show="headings", selectmode="browse")
    vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
    hsb = ttk.Scrollbar(tv_frame, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tv.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    def abfrage_ausfuehren():
        try:
            verbindung = sqlite_verbindung_mit_udf_oeffnen(get_geladene_db_datei())
            cursor = verbindung.cursor()
            cursor.execute(sql_text)
            spalten = [desc[0] for desc in cursor.description] if cursor.description else []
            zeilen = cursor.fetchall()
            verbindung.close()
        except Exception as e:
            messagebox.showerror("SQL-Abfrage", f"Fehler beim Ausführen:\n{e}", parent=res)
            return
        tv["columns"] = spalten
        for sp in spalten:
            tv.heading(sp, text=sp, anchor="w", command=lambda s=sp: spalte_sortieren(s))
            tv.column(sp, width=120, anchor="w", stretch=False)
        tv.delete(*tv.get_children())
        for z in zeilen:
            tv.insert("", "end", values=z)
        tree_spalten_breiten_anpassen(tv)
        zeilen_ref["alle"] = list(zeilen)

    sortier_zustand = {}
    def spalte_sortieren(sp):
        items = list(tv.get_children())
        if not items:
            return
        reverse = sortier_zustand.get(sp, False)
        def _sk_sp(i):
            vs = str(tv.set(i, sp)).strip()
            ip = _ip_zu_int(vs)
            if ip is not None:
                return (0, ip, "")
            try:
                return (1, float(vs.replace(",", ".")), "")
            except (ValueError, TypeError):
                return (2, 0, vs.lower())
        items.sort(key=_sk_sp, reverse=reverse)
        for idx, item in enumerate(items):
            tv.move(item, "", idx)
        sortier_zustand[sp] = not reverse

    zeilen_ref = standard_tv_rechtsklick_anbinden(tv, abfragename, res, sql_text_hint=sql_text)


    abfrage_ausfuehren()
    return res


def projekt_fenster_oeffnen_und_positionieren(projektname, ignore_startview=False):
    """Öffnet alle Workflow-Fenster eines Projekts und stellt gespeicherte Positionen wieder her.
    ignore_startview=True: Startview-Prüfung überspringen und immer Admin-Ansicht laden
    (wird z.B. von 'Admin SQL Ansicht laden' verwendet)."""
    # Startview-Prüfung: wenn eine Startview definiert ist, diese statt der Admin View laden
    if not ignore_startview:
        try:
            _startview = projekt_startview_lesen(projektname)
            if _startview:
                projekt_view_laden(projektname, _startview)
                return
        except Exception:
            pass

    # 1. Hauptfenster sofort positionieren (ist bereits offen, braucht keine Wartezeit)
    hf_geo = _projekt_layout_lesen(projektname, "Hauptfenster")
    hf_state = _projekt_layout_lesen(projektname, "Hauptfenster_state")
    try:
        if root.state() in ("iconic", "withdrawn"):
            root.deiconify()
    except Exception:
        pass
    # update_idletasks() stellt sicher, dass alle ausstehenden Fenstermanager-
    # Nachrichten (z.B. vorherige geometry()-Aufrufe beim DB-Laden) vollständig
    # abgearbeitet sind, bevor wir die Projekt-Position setzen.
    try:
        root.update_idletasks()
    except Exception:
        pass
    if hf_state == "zoomed":
        try:
            root.state("zoomed")
        except Exception:
            pass
    elif hf_geo:
        try:
            root.state("normal")
            root.update_idletasks()   # Zustandswechsel abwarten bevor Geometrie gesetzt wird
            root.geometry(hf_geo)
        except Exception:
            pass

    # 2. Workflow-Fenster öffnen
    eintraege = workflow_laden(projektname)
    offene_fenster = []
    for _eid, typ, name in eintraege:
        try:
            if typ == "Tabelle":
                tabellenfenster_oeffnen(name)
                offene_fenster.append(("Tabelle", name))
            elif typ == "SQL-Abfrage":
                _workflow_abfrage_fenster_oeffnen_modul(name)
                offene_fenster.append(("SQL-Abfrage", name))
            elif typ == "Kette":
                _workflow_ketten_fenster_oeffnen(name, projektname)
                offene_fenster.append(("Kette", name))
        except Exception as e:
            debug_log(f"Workflow-Fenster konnte nicht geöffnet werden: typ={typ}, name={name}, fehler={e}", "allgemein")

    # 3. Positionen der Workflow-Fenster nach kurzer Wartezeit setzen
    def positionen_anwenden():
        for typ, name in offene_fenster:
            geo = _projekt_layout_lesen(projektname, f"{typ}|{name}")
            if not geo:
                continue
            fenster = None
            if typ == "Tabelle":
                fenster = tabellenfenster_holen(name)
            elif typ == "SQL-Abfrage":
                fenster = _workflow_offene_sql_fenster.get(name)
            elif typ == "Kette":
                fenster = _workflow_offene_ketten_fenster.get(name)
            if fenster:
                try:
                    if not fenster.winfo_exists():
                        continue
                    fenster.state("normal")
                    fenster.update_idletasks()
                    fenster.geometry(geo)
                except Exception:
                    pass

    root.after(1000, positionen_anwenden)


def gespeicherte_abfragen_laden():
    """Gibt Liste von (id, name) aller gespeicherten SQL-Abfragen zurück."""
    if not get_geladene_db_datei():
        return []
    try:
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT id, name FROM {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} "
            f"WHERE name IS NOT NULL AND name != '' ORDER BY lower(name)"
        )
        zeilen = [(int(row[0]), str(row[1])) for row in cursor.fetchall()]
        verbindung.close()
        return zeilen
    except Exception:
        return []


def aktives_projekt_laden():
    """Gibt den Projektnamen des aktiven Projekts zurück, oder None."""
    if not get_geladene_db_datei():
        return None
    try:
        projekte_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT projektname FROM {sql_identifier(G_TABELLE_PROJEKTE)} WHERE aktiv = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        verbindung.close()
        return str(row[0]) if row else None
    except Exception:
        return None


def projekt_aktivieren(projektname):
    """Setzt genau ein Projekt auf aktiv=1, alle anderen auf aktiv=0."""
    if not get_geladene_db_datei():
        raise RuntimeError("Es ist keine Datenbank geladen.")
    projekte_tabelle_anlegen()
    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"UPDATE {sql_identifier(G_TABELLE_PROJEKTE)} SET aktiv = 0")
    cursor.execute(
        f"UPDATE {sql_identifier(G_TABELLE_PROJEKTE)} SET aktiv = 1, geaendert_am = ? WHERE projektname = ?",
        (jetzt, str(projektname))
    )
    verbindung.commit()
    verbindung.close()


def projekt_deaktivieren():
    """Setzt alle Projekte auf aktiv=0."""
    if not get_geladene_db_datei():
        return
    try:
        projekte_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()
        cursor.execute(f"UPDATE {sql_identifier(G_TABELLE_PROJEKTE)} SET aktiv = 0")
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def projekte_laden():
    if not db_ist_geladen():
        return []
    projekte_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"""
        SELECT projektname
        FROM {sql_identifier(G_TABELLE_PROJEKTE)}
        ORDER BY lower(projektname), projektname
    """)
    namen = [str(row[0]) for row in cursor.fetchall()]
    verbindung.close()
    return namen


def projekte_laden_mit_status():
    """Gibt Liste von (projektname, aktiv) zurück, sortiert nach Name."""
    if not db_ist_geladen():
        return []
    projekte_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(f"""
        SELECT projektname, aktiv
        FROM {sql_identifier(G_TABELLE_PROJEKTE)}
        ORDER BY lower(projektname), projektname
    """)
    zeilen = [(str(row[0]), int(row[1])) for row in cursor.fetchall()]
    verbindung.close()
    return zeilen


def projekt_in_db_speichern(projektname):
    name = str(projektname or "").strip()
    if not name:
        raise ValueError("Projektname fehlt.")
    if not db_ist_geladen():
        raise RuntimeError("Es ist keine Datenbank geladen.")
    projekte_tabelle_anlegen()
    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(
        f"SELECT id FROM {sql_identifier(G_TABELLE_PROJEKTE)} WHERE projektname = ?",
        (name,)
    )
    vorhanden = cursor.fetchone()
    if vorhanden:
        cursor.execute(
            f"UPDATE {sql_identifier(G_TABELLE_PROJEKTE)} SET geaendert_am = ? WHERE projektname = ?",
            (jetzt, name)
        )
    else:
        cursor.execute(
            f"""
            INSERT INTO {sql_identifier(G_TABELLE_PROJEKTE)}
                (projektname, erstellt_am, geaendert_am)
            VALUES (?, ?, ?)
            """,
            (name, jetzt, jetzt)
        )
    verbindung.commit()
    verbindung.close()


def projekt_aus_db_loeschen(projektname):
    name = str(projektname or "").strip()
    if not name:
        return
    if not db_ist_geladen():
        raise RuntimeError("Es ist keine Datenbank geladen.")
    projekte_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
    cursor = verbindung.cursor()
    cursor.execute(
        f"DELETE FROM {sql_identifier(G_TABELLE_PROJEKTE)} WHERE projektname = ?",
        (name,)
    )
    verbindung.commit()
    verbindung.close()


def sql_abfragen_schema_update_ausfuehren(parent=None):
    try:
        sql_abfragen_tabelle_anlegen()
        projekte_tabelle_anlegen()
        try:
            tabellen_dropdown_aktualisieren(G_TABELLE_PROJEKTE)
        except Exception as refresh_fehler:
            debug_log(f"Tabellenliste nach Schema-Update konnte nicht aktualisiert werden: fehler={refresh_fehler}", "allgemein")
        messagebox.showinfo(
            "SQL-Abfragen Schema-Update",
            f"Schema-Update für {G_TABELLE_SQL_ABFRAGEN} und {G_TABELLE_PROJEKTE} wurde ausgeführt.",
            parent=parent or root
        )
        return True
    except Exception as e:
        messagebox.showerror(
            "SQL-Abfragen Schema-Update",
            f"Schema-Update für {G_TABELLE_SQL_ABFRAGEN} / {G_TABELLE_PROJEKTE} ist fehlgeschlagen:\n{e}",
            parent=parent or root
        )
        return False

def sql_abfragen_laden():
    if not db_ist_geladen():
        return []
    sql_abfragen_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(f"""
        SELECT
            name,
            ziel_tabelle,
            beziehung1_typ, beziehung1_tabelle, beziehung1_links_tabelle, beziehung1_rechts_tabelle, beziehung1_links, beziehung1_rechts,
            beziehung2_typ, beziehung2_tabelle, beziehung2_links_tabelle, beziehung2_rechts_tabelle, beziehung2_links, beziehung2_rechts,
            beziehung3_typ, beziehung3_tabelle, beziehung3_links_tabelle, beziehung3_rechts_tabelle, beziehung3_links, beziehung3_rechts,
            beziehungen_json,
            where_json,
            update_tabelle,
            update_sets_json,
            update_where_json,
            delete_tabelle,
            delete_where_json,
            insert_tabelle,
            insert_werte_json,
            order_by_json,
            sql_text,
            haupttabelle
        FROM {sql_identifier(G_TABELLE_SQL_ABFRAGEN)}
        ORDER BY name
        """)
    daten = cursor.fetchall()
    verbindung.close()
    return daten


def sql_abfrage_direkt_speichern(name, ziel_tabelle, sql_text,
                                 beziehung1_typ="", beziehung1_tabelle="", beziehung1_links="", beziehung1_rechts="",
                                 beziehung2_typ="", beziehung2_tabelle="", beziehung2_links="", beziehung2_rechts="",
                                 beziehung3_typ="", beziehung3_tabelle="", beziehung3_links="", beziehung3_rechts="",
                                 beziehungen=None, where_bedingungen=None,
                                 update_tabelle="", update_sets=None, update_where_bedingungen=None,
                                 delete_tabelle="", delete_where_bedingungen=None,
                                 insert_tabelle="", insert_werte=None,
                                 order_by_zeilen=None, haupttabelle=""):
    if not db_pruefen_oder_warnen():
        return False, "Keine Datenbank geladen."

    name = str(name).strip()
    ziel_tabelle = str(ziel_tabelle).strip()
    sql_text = str(sql_text).strip()

    if not name:
        return False, "Bitte einen Namen für die SQL-Abfrage angeben."
    if not ziel_tabelle:
        return False, "Bitte eine Zieltabelle angeben."
    if not sql_text:
        return False, "Bitte SQL-Text angeben."

    sql_abfragen_tabelle_anlegen()
    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    beziehungen = list(beziehungen or [
        {"typ": beziehung1_typ, "tabelle": beziehung1_tabelle, "links_tabelle": "", "rechts_tabelle": "", "links": beziehung1_links, "rechts": beziehung1_rechts},
        {"typ": beziehung2_typ, "tabelle": beziehung2_tabelle, "links_tabelle": "", "rechts_tabelle": "", "links": beziehung2_links, "rechts": beziehung2_rechts},
        {"typ": beziehung3_typ, "tabelle": beziehung3_tabelle, "links_tabelle": "", "rechts_tabelle": "", "links": beziehung3_links, "rechts": beziehung3_rechts},
    ])
    where_bedingungen = list(where_bedingungen or [])
    update_tabelle = str(update_tabelle or "").strip()
    update_sets = list(update_sets or [])
    update_where_bedingungen = list(update_where_bedingungen or [])
    delete_tabelle = str(delete_tabelle or "").strip()
    delete_where_bedingungen = list(delete_where_bedingungen or [])
    insert_tabelle = str(insert_tabelle or "").strip()
    insert_werte = list(insert_werte or [])
    order_by_zeilen = list(order_by_zeilen or [])
    haupttabelle = str(haupttabelle or "").strip()
    while len(beziehungen) < 3:
        beziehungen.append({"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""})
    beziehungen_json = json.dumps(beziehungen, ensure_ascii=False)
    where_json = json.dumps(where_bedingungen, ensure_ascii=False)
    update_sets_json = json.dumps(update_sets, ensure_ascii=False)
    update_where_json = json.dumps(update_where_bedingungen, ensure_ascii=False)
    delete_where_json = json.dumps(delete_where_bedingungen, ensure_ascii=False)
    insert_werte_json = json.dumps(insert_werte, ensure_ascii=False)
    order_by_json = json.dumps(order_by_zeilen, ensure_ascii=False)
    b1, b2, b3 = beziehungen[0], beziehungen[1], beziehungen[2]

    try:
        verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
        cursor = verbindung.cursor()

        cursor.execute(
            f"SELECT id FROM {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} WHERE name = ?",
            (name,)
        )
        vorhanden = cursor.fetchone()

        if vorhanden:
            cursor.execute(f"""
                UPDATE {sql_identifier(G_TABELLE_SQL_ABFRAGEN)}
                SET ziel_tabelle = ?,
                    beziehung1_typ = ?,
                    beziehung1_tabelle = ?,
                    beziehung1_links_tabelle = ?,
                    beziehung1_rechts_tabelle = ?,
                    beziehung1_links = ?,
                    beziehung1_rechts = ?,
                    beziehung2_typ = ?,
                    beziehung2_tabelle = ?,
                    beziehung2_links_tabelle = ?,
                    beziehung2_rechts_tabelle = ?,
                    beziehung2_links = ?,
                    beziehung2_rechts = ?,
                    beziehung3_typ = ?,
                    beziehung3_tabelle = ?,
                    beziehung3_links_tabelle = ?,
                    beziehung3_rechts_tabelle = ?,
                    beziehung3_links = ?,
                    beziehung3_rechts = ?,
                    beziehungen_json = ?,
                    where_json = ?,
                    update_tabelle = ?,
                    update_sets_json = ?,
                    update_where_json = ?,
                    delete_tabelle = ?,
                    delete_where_json = ?,
                    insert_tabelle = ?,
                    insert_werte_json = ?,
                    order_by_json = ?,
                    haupttabelle = ?,
                    sql_text = ?,
                    geaendert_am = ?
                WHERE name = ?
            """, (
                ziel_tabelle,
                b1.get("typ", ""), b1.get("tabelle", ""), b1.get("links_tabelle", ""), b1.get("rechts_tabelle", ""), b1.get("links", ""), b1.get("rechts", ""),
                b2.get("typ", ""), b2.get("tabelle", ""), b2.get("links_tabelle", ""), b2.get("rechts_tabelle", ""), b2.get("links", ""), b2.get("rechts", ""),
                b3.get("typ", ""), b3.get("tabelle", ""), b3.get("links_tabelle", ""), b3.get("rechts_tabelle", ""), b3.get("links", ""), b3.get("rechts", ""),
                beziehungen_json,
                where_json,
                update_tabelle,
                update_sets_json,
                update_where_json,
                delete_tabelle,
                delete_where_json,
                insert_tabelle,
                insert_werte_json,
                order_by_json,
                haupttabelle,
                sql_text,
                jetzt,
                name
            ))
        else:
            cursor.execute(f"""
                INSERT INTO {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} (
                    name,
                    ziel_tabelle,
                    beziehung1_typ, beziehung1_tabelle, beziehung1_links_tabelle, beziehung1_rechts_tabelle, beziehung1_links, beziehung1_rechts,
                    beziehung2_typ, beziehung2_tabelle, beziehung2_links_tabelle, beziehung2_rechts_tabelle, beziehung2_links, beziehung2_rechts,
                    beziehung3_typ, beziehung3_tabelle, beziehung3_links_tabelle, beziehung3_rechts_tabelle, beziehung3_links, beziehung3_rechts,
                    beziehungen_json,
                    where_json,
                    update_tabelle,
                    update_sets_json,
                    update_where_json,
                    delete_tabelle,
                    delete_where_json,
                    insert_tabelle,
                    insert_werte_json,
                    order_by_json,
                    haupttabelle,
                    sql_text,
                    erstellt_am,
                    geaendert_am
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                ziel_tabelle,
                b1.get("typ", ""), b1.get("tabelle", ""), b1.get("links_tabelle", ""), b1.get("rechts_tabelle", ""), b1.get("links", ""), b1.get("rechts", ""),
                b2.get("typ", ""), b2.get("tabelle", ""), b2.get("links_tabelle", ""), b2.get("rechts_tabelle", ""), b2.get("links", ""), b2.get("rechts", ""),
                b3.get("typ", ""), b3.get("tabelle", ""), b3.get("links_tabelle", ""), b3.get("rechts_tabelle", ""), b3.get("links", ""), b3.get("rechts", ""),
                beziehungen_json,
                where_json,
                update_tabelle,
                update_sets_json,
                update_where_json,
                delete_tabelle,
                delete_where_json,
                insert_tabelle,
                insert_werte_json,
                order_by_json,
                haupttabelle,
                sql_text,
                jetzt,
                jetzt
            ))

        verbindung.commit()
        verbindung.close()
        return True, f"Die SQL-Abfrage '{name}' wurde gespeichert."

    except Exception as e:
        return False, str(e)

# Neu für V4.3.48

def sqlite_verbindung_mit_udf_oeffnen(db_datei=None):
    """Öffnet eine SQLite-Verbindung und registriert alle UDFs aus sqlgui_udf."""
    verbindung = sqlite_verbindung_oeffnen(db_datei)
    return udf_alle_registrieren(verbindung)


def tabellenspalten_laden(tabellenname):
    if not db_ist_geladen() or not tabellenname:
        return []
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"PRAGMA table_info({sql_identifier(tabellenname)})")
        spalten = [row[1] for row in cursor.fetchall()]
        verbindung.close()
        return spalten
    except Exception:
        return []


def sql_fenster_felder_laden(tabellenname, tree_felder):
    tree_felder.delete(*tree_felder.get_children())
    if not tabellenname:
        return
    for spalte in tabellenspalten_laden(tabellenname):
        tree_felder.insert("", "end", values=(f"{tabellenname}.{spalte}",))


def sql_ergebnis_als_tabelle_speichern(parent, vorgeschlagene_zieltabelle, spalten, zeilen):
    if not db_pruefen_oder_warnen():
        return

    # Eigener Dialog – dynamisch breit für lange Tabellennamen
    dialog = tk.Toplevel(parent)
    dialog.title("Als Tabelle ablegen")
    dialog.resizable(True, False)
    dialog.grab_set()
    dialog.transient(parent)

    # Breite dynamisch: min 480, max 800, basierend auf Vorschlagslänge
    vorschlag = vorgeschlagene_zieltabelle or ""
    breite = max(480, min(800, 200 + len(vorschlag) * 9))
    dialog.geometry(f"{breite}x130")

    tk.Label(dialog, text="Name der Zieltabelle:", anchor="w").pack(fill="x", padx=16, pady=(16, 4))
    entry_var = tk.StringVar(value=vorschlag)
    entry = tk.Entry(dialog, textvariable=entry_var, width=60)
    entry.pack(fill="x", padx=16)
    entry.select_range(0, "end")
    entry.focus_set()

    tabellenname_ergebnis = [None]

    def bestaetigen(event=None):
        tabellenname_ergebnis[0] = entry_var.get().strip()
        dialog.destroy()

    def abbrechen():
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(fill="x", padx=16, pady=(12, 0))
    tk.Button(btn_frame, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 0))
    tk.Button(btn_frame, text="Abbrechen", width=12, command=abbrechen).pack(side="right")
    entry.bind("<Return>", bestaetigen)
    entry.bind("<Escape>", lambda e: abbrechen())

    dialog.wait_window()
    tabellenname = tabellenname_ergebnis[0]

    if tabellenname is None:
        return
    if not tabellenname:
        messagebox.showwarning("Als Tabelle ablegen", "Bitte einen Namen für die Zieltabelle angeben.", parent=parent)
        return
    if not sql_name_ok(tabellenname):
        messagebox.showwarning("Als Tabelle ablegen", "Ungültiger Tabellenname.", parent=parent)
        return
    # Doppelte Spaltennamen automatisch umbenennen (z.B. BoundaryType → BoundaryType_2)
    def spaltennamen_eindeutig_machen(spalten_liste):
        gezaehlt = {}
        ergebnis = []
        for sp in spalten_liste:
            sp_norm = str(sp) if sp else "Spalte"
            if sp_norm not in gezaehlt:
                gezaehlt[sp_norm] = 1
                ergebnis.append(sp_norm)
            else:
                gezaehlt[sp_norm] += 1
                neuer_name = f"{sp_norm}_{gezaehlt[sp_norm]}"
                ergebnis.append(neuer_name)
        return ergebnis
    bereinigte_spalten = spaltennamen_eindeutig_machen(spalten) if spalten else spalten
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS {sql_identifier(tabellenname)}')
        if not bereinigte_spalten:
            cursor.execute(f'CREATE TABLE {sql_identifier(tabellenname)} (id INTEGER PRIMARY KEY AUTOINCREMENT)')
        else:
            spaltendef = ', '.join(f'{sql_identifier(sp)} TEXT' for sp in bereinigte_spalten)
            cursor.execute(f'CREATE TABLE {sql_identifier(tabellenname)} ({spaltendef})')
            if zeilen:
                platzhalter = ', '.join(['?'] * len(bereinigte_spalten))
                cursor.executemany(
                    f'INSERT INTO {sql_identifier(tabellenname)} VALUES ({platzhalter})',
                    [tuple("" if v is None else str(v) for v in row[:len(bereinigte_spalten)]) for row in zeilen]
                )
        verbindung.commit()
        verbindung.close()
        tabellen_dropdown_aktualisieren(tabellenname)
        # Hinweis wenn Spaltennamen umbenannt wurden
        umbenannt = [f"{a} → {b}" for a, b in zip(spalten, bereinigte_spalten) if a != b] if spalten else []
        if umbenannt:
            hinweis = "Folgende Spaltennamen wurden umbenannt:\n" + "\n".join(umbenannt) + "\n\n"
        else:
            hinweis = ""
        messagebox.showinfo("Als Tabelle ablegen", f"{hinweis}Ergebnis wurde als Tabelle '{tabellenname}' gespeichert.", parent=parent)
    except Exception as e:
        messagebox.showerror("Als Tabelle ablegen", f"Ergebnis konnte nicht als Tabelle gespeichert werden:\n{e}", parent=parent)


_sql_abfrage_fenster_instanz = None
_hat_ungespeicherte_aenderungen_func = None
_speichern_func = None


def sql_editor_hat_ungespeicherte_aenderungen():
    """Gibt True zurück wenn der SQL Editor offen ist und ungespeicherte Änderungen hat."""
    if callable(_hat_ungespeicherte_aenderungen_func):
        try:
            return _hat_ungespeicherte_aenderungen_func()
        except Exception:
            pass
    return False


def sql_editor_speichern():
    """Speichert die aktuelle Abfrage im SQL Editor. Gibt True zurück bei Erfolg."""
    if callable(_speichern_func):
        try:
            return _speichern_func()
        except Exception:
            pass
    return False


def sql_abfrage_fenster_oeffnen():
    global _sql_abfrage_fenster_instanz
    if not db_pruefen_oder_warnen():
        return
    # Bereits offen? → nach vorne holen
    if _sql_abfrage_fenster_instanz is not None:
        try:
            if _sql_abfrage_fenster_instanz.winfo_exists():
                if _sql_abfrage_fenster_instanz.state() in ("iconic", "withdrawn"):
                    _sql_abfrage_fenster_instanz.deiconify()
                _sql_abfrage_fenster_instanz.lift()
                _sql_abfrage_fenster_instanz.focus_force()
                return
        except Exception:
            pass
        _sql_abfrage_fenster_instanz = None

    sql_funktionsvorlagen = [
        ("IPv4 → Integer          NULL / Integer",       "ipv4_to_int(IP_Adresse) AS IPv4_Integer"),
        ("IP-Range aufteilen      ERROR / Start|Ende",   "ip_range_aufteilen(IP_Range) AS IP_Range_Info"),
        ("IP-Range Start          NULL / IP",            "ip_range_start(IP_Range) AS IP_Start"),
        ("IP-Range Ende           NULL / IP",            "ip_range_end(IP_Range) AS IP_Ende"),
        ("Hat IP-Adresse          NULL / IP",            "hat_ip(Textfeld) AS Gefundene_IP"),
        ("Hat Netzmaske           NULL / /24",           "hat_netzmaske(Textfeld) AS Gefundene_Maske"),
        ("IP in Range prüfen      ERROR / OK",           "ip_in_range_pruefen(IP_Adresse, Netzmaske, IP_Range) AS IP_In_Range"),
    ]
    linke_liste_hoehe = 4
    linke_liste_abstand = 5

    try:
        liste_breite = int(_sql_konfig_lesen("liste_breite") or 220)
    except Exception:
        liste_breite = 220
    try:
        eingabe_breite = int(_sql_konfig_lesen("eingabe_breite") or 38)
    except Exception:
        eingabe_breite = 38
    try:
        auswahl_breite = int(_sql_konfig_lesen("auswahl_breite") or 30)
    except Exception:
        auswahl_breite = 30
    try:
        feld_breite = int(_sql_konfig_lesen("feld_breite") or 30)
    except Exception:
        feld_breite = 30

    top = tk.Toplevel(root)
    _sql_abfrage_fenster_instanz = top
    top.bind("<Destroy>", lambda e: globals().update(
        _sql_abfrage_fenster_instanz=None,
        _hat_ungespeicherte_aenderungen_func=None,
        _speichern_func=None,
    ) if e.widget is top else None)
    top.title(f"{G_EXE_Title} - SQL Editor")
    top.geometry("1380x780")
    top.minsize(800, 300)
    fenster_registrieren(top, "SQL")
    fenster_standard_menue_anbringen(top, "1380x780", "SQL")

    main = tk.Frame(top, padx=10, pady=10)
    main.pack(fill="both", expand=True)
    main.grid_rowconfigure(0, weight=1)
    main.grid_columnconfigure(1, weight=1)

    left = tk.Frame(main)
    left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
    left.pack_propagate(False)
    left.config(width=liste_breite)
    right = tk.Frame(main)
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_columnconfigure(0, weight=0)
    right.grid_columnconfigure(1, weight=1)
    right.grid_rowconfigure(1, weight=1)

    tk.Label(left, text="Tabellen:").pack(anchor="w")
    tree_tab = ttk.Treeview(left, columns=("t",), show="headings", height=linke_liste_hoehe, selectmode="browse")
    tree_tab.heading("t", text="Tabelle", anchor="w", command=lambda: _tv_sortieren(tree_tab, "t"))
    tree_tab.column("t", width=liste_breite, anchor="w")
    tree_tab.pack(fill="x", pady=(0, linke_liste_abstand))

    tk.Label(left, text="Felder:").pack(anchor="w")
    tree_fel = ttk.Treeview(left, columns=("f",), show="headings", height=linke_liste_hoehe, selectmode="browse")
    tree_fel.heading("f", text="Feld", anchor="w", command=lambda: _tv_sortieren(tree_fel, "f"))
    tree_fel.column("f", width=liste_breite, anchor="w")
    tree_fel.pack(fill="x", pady=(0, linke_liste_abstand))

    tk.Label(left, text="Gespeicherte SQL-Abfragen:").pack(anchor="w")
    tree_saved = ttk.Treeview(left, columns=("name", "ziel"), show="headings", height=linke_liste_hoehe, selectmode="browse")
    tree_saved.heading("name", text="Name", anchor="w", command=lambda: _tv_sortieren(tree_saved, "name"))
    tree_saved.heading("ziel", text="Zieltabelle", anchor="w", command=lambda: _tv_sortieren(tree_saved, "ziel"))
    tree_saved.column("name", width=max(60, int(liste_breite * 0.6)), anchor="w")
    tree_saved.column("ziel", width=max(40, int(liste_breite * 0.4)), anchor="w")
    tree_saved.pack(fill="x", pady=(0, linke_liste_abstand))

    tk.Label(left, text="Funktionen:").pack(anchor="w")
    func_frame = tk.Frame(left)
    func_frame.pack(fill="x", pady=(0, linke_liste_abstand))
    tree_func = ttk.Treeview(func_frame, columns=("name",), show="headings", height=linke_liste_hoehe, selectmode="browse")
    tree_func.heading("name", text="Name", anchor="w", command=lambda: _tv_sortieren(tree_func, "name"))
    tree_func.column("name", width=liste_breite, anchor="w")
    func_scroll = ttk.Scrollbar(func_frame, orient="vertical", command=tree_func.yview)
    tree_func.configure(yscrollcommand=func_scroll.set)
    tree_func.pack(side="left", fill="x", expand=True)
    func_scroll.pack(side="right", fill="y")
    for funktionsname, funktionsausdruck in sql_funktionsvorlagen:
        tree_func.insert("", "end", values=(funktionsname,), tags=(funktionsausdruck,))

    tk.Label(left, text="Projekte:").pack(anchor="w")
    tree_projekte = ttk.Treeview(left, columns=("name", "status"), show="headings", height=linke_liste_hoehe, selectmode="browse")
    tree_projekte.heading("name", text="Projekt", anchor="w", command=lambda: _tv_sortieren(tree_projekte, "name"))
    tree_projekte.column("name", width=max(60, liste_breite - 70), anchor="w")
    tree_projekte.heading("status", text="Status", anchor="w", command=lambda: _tv_sortieren(tree_projekte, "status"))
    tree_projekte.column("status", width=70, anchor="center")
    tree_projekte.pack(fill="x")
    projekt_namen = []
    projekt_status = {"aktuell": None}
    projekt_name_anzeige = tk.StringVar(value="")
    aktiv_var = tk.BooleanVar(value=False)
    sql_name_var = tk.StringVar(value="")
    sql_zieltabelle_var = tk.StringVar(value="")

    class _StringVarEntryAdapter:
        def __init__(self, variable):
            self.variable = variable

        def get(self):
            return self.variable.get()

        def delete(self, start, end=None):
            self.variable.set("")

        def insert(self, index, text):
            self.variable.set("" if text is None else str(text))

    name_ziel_entries = []
    entry_name = _StringVarEntryAdapter(sql_name_var)
    entry_ziel = _StringVarEntryAdapter(sql_zieltabelle_var)

    def sql_reiter_kopffelder_anlegen(parent):
        kopf = tk.Frame(parent)
        kopf._sql_kopfbereich = True
        kopf.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        tk.Label(kopf, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 4))
        _e_name = tk.Entry(kopf, textvariable=sql_name_var, width=eingabe_breite)
        _e_name.grid(row=0, column=1, sticky="w", padx=(0, 36))
        name_ziel_entries.append(_e_name)
        tk.Label(kopf, text="Zieltabelle").grid(row=0, column=2, sticky="w", padx=(0, 4))
        _e_ziel = tk.Entry(kopf, textvariable=sql_zieltabelle_var, width=eingabe_breite)
        _e_ziel.grid(row=0, column=3, sticky="w")
        name_ziel_entries.append(_e_ziel)

    def sql_reiter_inhalte_nach_unten_verschieben(parent):
        for widget in parent.winfo_children():
            if getattr(widget, "_sql_kopfbereich", False):
                continue
            info = widget.grid_info()
            if not info:
                continue
            widget.grid_configure(row=int(info.get("row", 0)) + 1)

    builder_notebook = ttk.Notebook(right)
    builder_notebook.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))

    select_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(select_tab, text="SELECT")
    select_tab.grid_columnconfigure(1, weight=1)

    # Kopfbereich für SELECT: Name/Zieltabelle + Select FROM in einem Frame
    select_kopf = tk.Frame(select_tab)
    select_kopf._sql_kopfbereich = True
    select_kopf.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))

    # Zeile 0: Name + Zieltabelle
    tk.Label(select_kopf, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 4))
    _sel_name = tk.Entry(select_kopf, textvariable=sql_name_var, width=eingabe_breite)
    _sel_name.grid(row=0, column=1, sticky="w", padx=(0, 36))
    name_ziel_entries.append(_sel_name)
    tk.Label(select_kopf, text="Zieltabelle").grid(row=0, column=2, sticky="w", padx=(0, 4))
    _sel_ziel = tk.Entry(select_kopf, textvariable=sql_zieltabelle_var, width=eingabe_breite)
    _sel_ziel.grid(row=0, column=3, sticky="w")
    name_ziel_entries.append(_sel_ziel)

    # Zeile 1: Select FROM Dropdown
    tk.Label(select_kopf, text="Select FROM:").grid(row=1, column=0, sticky="w", pady=(6, 0), padx=(0, 4))
    select_from_frame = tk.Frame(select_kopf)
    select_from_frame.grid(row=1, column=1, columnspan=3, sticky="w", pady=(6, 0))
    tabellen_combos = []
    feld_combos = []
    tk.Label(select_from_frame, text="Haupttabelle").grid(row=0, column=0, sticky="w")
    select_from_tabelle = ttk.Combobox(select_from_frame, state="readonly", width=auswahl_breite)
    select_from_tabelle.grid(row=0, column=1, sticky="w", padx=(8, 0))
    tabellen_combos.append(select_from_tabelle)
    button_select_from_einfuegen = tk.Button(select_from_frame, text="In Statement einfügen", width=18)
    button_select_from_einfuegen.grid(row=0, column=2, sticky="w", padx=(12, 0))

    update_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(update_tab, text="UPDATE")
    update_tab.grid_columnconfigure(1, weight=1)
    sql_reiter_kopffelder_anlegen(update_tab)

    update_sets = [
        {"feld": "", "wert": ""},
    ]
    aktuelle_update_set = {"index": 0}
    update_where_bedingungen = [
        {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
    ]
    aktuelle_update_where = {"index": 0}

    tk.Label(update_tab, text="UPDATE:").grid(row=0, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    update_kopf = tk.Frame(update_tab)
    update_kopf.grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 4))
    tk.Label(update_kopf, text="Tabelle").grid(row=0, column=0, sticky="w")
    update_tabelle = ttk.Combobox(update_kopf, state="readonly", width=auswahl_breite)
    tabellen_combos.append(update_tabelle)
    update_tabelle.grid(row=1, column=0, sticky="w")
    button_update_einfuegen = tk.Button(update_kopf, text="In Statement einfügen", width=18)
    button_update_einfuegen.grid(row=1, column=1, sticky="w", padx=(12, 0))

    tk.Label(update_tab, text="SET:").grid(row=1, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    update_set_kopf = tk.Frame(update_tab)
    update_set_kopf.grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 4))
    update_set_auswahl = ttk.Combobox(update_set_kopf, state="readonly", width=12, values=["SET 1"])
    update_set_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    update_set_auswahl.set("SET 1")
    update_set_status = tk.Label(update_set_kopf, text="Bearbeitet wird SET 1 von 1.", anchor="w")
    update_set_status.grid(row=0, column=1, sticky="w")
    button_update_set_neu = tk.Button(update_set_kopf, text="Neu", width=8)
    button_update_set_neu.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_update_set_loeschen = tk.Button(update_set_kopf, text="Löschen", width=8)
    button_update_set_loeschen.grid(row=0, column=3, sticky="w", padx=(8, 0))

    tk.Label(update_tab, text="Feld / Wert:").grid(row=2, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    update_set_frame = tk.Frame(update_tab)
    update_set_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 6))
    update_set_feld = ttk.Combobox(update_set_frame, width=auswahl_breite)
    feld_combos.append(update_set_feld)
    update_set_feld.grid(row=0, column=0, sticky="w")
    tk.Label(update_set_frame, text="=").grid(row=0, column=1, padx=4)
    update_set_wert = tk.Entry(update_set_frame, width=eingabe_breite)
    update_set_wert.grid(row=0, column=2, sticky="w")

    tk.Label(update_tab, text="WHERE:").grid(row=3, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    update_where_kopf = tk.Frame(update_tab)
    update_where_kopf.grid(row=3, column=1, columnspan=3, sticky="w", pady=(0, 4))
    update_where_auswahl = ttk.Combobox(update_where_kopf, state="readonly", width=14, values=["Bedingung 1"])
    update_where_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    update_where_auswahl.set("Bedingung 1")
    update_where_status = tk.Label(update_where_kopf, text="Bearbeitet wird Bedingung 1 von 1.", anchor="w")
    update_where_status.grid(row=0, column=1, sticky="w")
    button_update_where_neu = tk.Button(update_where_kopf, text="Neu", width=8)
    button_update_where_neu.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_update_where_loeschen = tk.Button(update_where_kopf, text="Löschen", width=8)
    button_update_where_loeschen.grid(row=0, column=3, sticky="w", padx=(8, 0))

    tk.Label(update_tab, text="Feld / Wert:").grid(row=4, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    update_where_frame = tk.Frame(update_tab)
    update_where_frame.grid(row=4, column=1, columnspan=3, sticky="w", pady=(0, 6))
    update_where_verknuepfung = ttk.Combobox(update_where_frame, state="readonly", width=10, values=["WHERE", "AND", "OR"])
    update_where_verknuepfung.grid(row=0, column=0, sticky="w", padx=(0, 8))
    update_where_feld = ttk.Combobox(update_where_frame, width=auswahl_breite)
    feld_combos.append(update_where_feld)
    update_where_feld.grid(row=0, column=1, sticky="w", padx=(0, 8))
    update_where_operator = ttk.Combobox(
        update_where_frame,
        state="readonly",
        width=12,
        values=["=", "<>", "LIKE", "NOT LIKE", ">", ">=", "<", "<=", "IS NULL", "IS NOT NULL", "IN", "NOT IN"]
    )
    update_where_operator.grid(row=0, column=2, sticky="w", padx=(0, 8))
    update_where_wert = tk.Entry(update_where_frame, width=eingabe_breite)
    update_where_wert.grid(row=0, column=3, sticky="w")

    delete_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(delete_tab, text="DELETE")
    delete_tab.grid_columnconfigure(1, weight=1)
    sql_reiter_kopffelder_anlegen(delete_tab)

    delete_where_bedingungen = [
        {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
    ]
    aktuelle_delete_where = {"index": 0}

    tk.Label(delete_tab, text="DELETE:").grid(row=0, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    delete_kopf = tk.Frame(delete_tab)
    delete_kopf.grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 4))
    tk.Label(delete_kopf, text="Tabelle").grid(row=0, column=0, sticky="w")
    delete_tabelle = ttk.Combobox(delete_kopf, state="readonly", width=auswahl_breite)
    tabellen_combos.append(delete_tabelle)
    delete_tabelle.grid(row=1, column=0, sticky="w")
    button_delete_einfuegen = tk.Button(delete_kopf, text="In Statement einfügen", width=18)
    button_delete_einfuegen.grid(row=1, column=1, sticky="w", padx=(12, 0))

    tk.Label(delete_tab, text="WHERE:").grid(row=1, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    delete_where_kopf = tk.Frame(delete_tab)
    delete_where_kopf.grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 4))
    delete_where_auswahl = ttk.Combobox(delete_where_kopf, state="readonly", width=14, values=["Bedingung 1"])
    delete_where_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    delete_where_auswahl.set("Bedingung 1")
    delete_where_status = tk.Label(delete_where_kopf, text="Bearbeitet wird Bedingung 1 von 1.", anchor="w")
    delete_where_status.grid(row=0, column=1, sticky="w")
    button_delete_where_neu = tk.Button(delete_where_kopf, text="Neu", width=8)
    button_delete_where_neu.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_delete_where_loeschen = tk.Button(delete_where_kopf, text="Löschen", width=8)
    button_delete_where_loeschen.grid(row=0, column=3, sticky="w", padx=(8, 0))

    tk.Label(delete_tab, text="Feld / Wert:").grid(row=2, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    delete_where_frame = tk.Frame(delete_tab)
    delete_where_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 6))
    delete_where_verknuepfung = ttk.Combobox(delete_where_frame, state="readonly", width=10, values=["WHERE", "AND", "OR"])
    delete_where_verknuepfung.grid(row=0, column=0, sticky="w", padx=(0, 8))
    delete_where_feld = ttk.Combobox(delete_where_frame, width=auswahl_breite)
    feld_combos.append(delete_where_feld)
    delete_where_feld.grid(row=0, column=1, sticky="w", padx=(0, 8))
    delete_where_operator = ttk.Combobox(
        delete_where_frame,
        state="readonly",
        width=12,
        values=["=", "<>", "LIKE", "NOT LIKE", ">", ">=", "<", "<=", "IS NULL", "IS NOT NULL", "IN", "NOT IN"]
    )
    delete_where_operator.grid(row=0, column=2, sticky="w", padx=(0, 8))
    delete_where_wert = tk.Entry(delete_where_frame, width=eingabe_breite)
    delete_where_wert.grid(row=0, column=3, sticky="w")

    insert_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(insert_tab, text="INSERT")
    insert_tab.grid_columnconfigure(1, weight=1)
    sql_reiter_kopffelder_anlegen(insert_tab)

    insert_werte = [
        {"feld": "", "wert": ""},
    ]
    aktuelle_insert_zeile = {"index": 0}

    tk.Label(insert_tab, text="INSERT:").grid(row=0, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    insert_kopf = tk.Frame(insert_tab)
    insert_kopf.grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 4))
    tk.Label(insert_kopf, text="Tabelle").grid(row=0, column=0, sticky="w")
    insert_tabelle = ttk.Combobox(insert_kopf, state="readonly", width=auswahl_breite)
    tabellen_combos.append(insert_tabelle)
    insert_tabelle.grid(row=1, column=0, sticky="w")
    button_insert_einfuegen = tk.Button(insert_kopf, text="In Statement einfügen", width=18)
    button_insert_einfuegen.grid(row=1, column=1, sticky="w", padx=(12, 0))

    tk.Label(insert_tab, text="Wert:").grid(row=1, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    insert_wert_kopf = tk.Frame(insert_tab)
    insert_wert_kopf.grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 4))
    insert_auswahl = ttk.Combobox(insert_wert_kopf, state="readonly", width=14, values=["Wert 1"])
    insert_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    insert_auswahl.set("Wert 1")
    insert_status = tk.Label(insert_wert_kopf, text="Bearbeitet wird Wert 1 von 1.", anchor="w")
    insert_status.grid(row=0, column=1, sticky="w")
    button_insert_neu = tk.Button(insert_wert_kopf, text="Neu", width=8)
    button_insert_neu.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_insert_loeschen = tk.Button(insert_wert_kopf, text="Löschen", width=8)
    button_insert_loeschen.grid(row=0, column=3, sticky="w", padx=(8, 0))

    tk.Label(insert_tab, text="Feld / Wert:").grid(row=2, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    insert_wert_frame = tk.Frame(insert_tab)
    insert_wert_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 6))
    insert_feld = ttk.Combobox(insert_wert_frame, width=auswahl_breite)
    feld_combos.append(insert_feld)
    insert_feld.grid(row=0, column=0, sticky="w")
    tk.Label(insert_wert_frame, text="=").grid(row=0, column=1, padx=4)
    insert_wert = tk.Entry(insert_wert_frame, width=eingabe_breite)
    insert_wert.grid(row=0, column=2, sticky="w")

    projekt_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(projekt_tab, text="PROJEKT")
    projekt_tab.grid_columnconfigure(0, weight=1)
    projekt_tab.grid_columnconfigure(1, weight=1)
    projekt_tab.grid_rowconfigure(2, weight=1)

    projekt_kopf = tk.Frame(projekt_tab)
    projekt_kopf.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    tk.Label(projekt_kopf, text="Projekt:").grid(row=0, column=0, sticky="w", padx=(0, 6))
    tk.Checkbutton(projekt_kopf, text="aktiv", variable=aktiv_var, command=lambda: aktiv_toggle()).grid(row=0, column=1, sticky="w", padx=(0, 4))
    tk.Entry(projekt_kopf, textvariable=projekt_name_anzeige, state="readonly", width=30).grid(row=0, column=2, sticky="w")
    tk.Button(projekt_kopf, text="Admin SQL Ansicht speichern",
              command=lambda: projekt_fenster_positionen_merken()).grid(row=0, column=3, sticky="w", padx=(8, 4))
    tk.Button(projekt_kopf, text="Admin SQL Ansicht laden",
              command=lambda: gespeicherte_positionen_laden()).grid(row=0, column=4, sticky="w")

    einstellungen_tab = tk.Frame(builder_notebook, padx=6, pady=6)
    builder_notebook.add(einstellungen_tab, text="EINSTELLUNGEN")

    tk.Label(einstellungen_tab, text="Listenbreite (px):").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=(0, 6))
    liste_breite_var = tk.IntVar(value=liste_breite)
    tk.Spinbox(einstellungen_tab, from_=80, to=600, increment=10, textvariable=liste_breite_var, width=6).grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(0, 6))

    tk.Label(einstellungen_tab, text="Eingabebreite (Zeichen):").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=(0, 6))
    eingabe_breite_var = tk.IntVar(value=eingabe_breite)
    tk.Spinbox(einstellungen_tab, from_=10, to=120, increment=2, textvariable=eingabe_breite_var, width=6).grid(row=0, column=3, sticky="w", padx=(0, 16), pady=(0, 6))

    tk.Label(einstellungen_tab, text="Tabellenbreite (Zeichen):").grid(row=0, column=4, sticky="w", padx=(0, 4), pady=(0, 6))
    tabellen_breite_var = tk.IntVar(value=auswahl_breite)
    tk.Spinbox(einstellungen_tab, from_=10, to=120, increment=2, textvariable=tabellen_breite_var, width=6).grid(row=0, column=5, sticky="w", padx=(0, 16), pady=(0, 6))

    tk.Label(einstellungen_tab, text="Feldbreite (Zeichen):").grid(row=0, column=6, sticky="w", padx=(0, 4), pady=(0, 6))
    feld_breite_var = tk.IntVar(value=feld_breite)
    tk.Spinbox(einstellungen_tab, from_=10, to=120, increment=2, textvariable=feld_breite_var, width=6).grid(row=0, column=7, sticky="w", padx=(0, 16), pady=(0, 6))

    tk.Button(einstellungen_tab, text="Anwenden", command=lambda: breiten_anwenden()).grid(row=0, column=8, sticky="w", pady=(0, 6))

    _FARB_OPTIONEN_FARBEN = [
        "#FF0000",   # Rot
        "#FFD700",   # Gelb
        "#93DAFE",   # Hellblau
        "#FF7403",   # Orange
        "#192C76",   # Dunkelblau
        "#90EE90",   # Helles Grün
        "#2E7D32",   # Dunkles Grün
        "#FF00FF",   # Magenta
        "#FFBF00",   # Bernstein
        "#33FF33",   # Phosphor-Grün
    ]

    def _farb_radio_zeile_bauen(row, label_text, konfig_schluessel):
        tk.Label(einstellungen_tab, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=(0, 4))
        var = tk.StringVar(value=_sql_konfig_lesen(konfig_schluessel) or "")
        optionen_frame = tk.Frame(einstellungen_tab)
        optionen_frame.grid(row=row, column=1, columnspan=8, sticky="w", pady=(0, 4))
        tk.Radiobutton(optionen_frame, text="—", variable=var, value="").pack(side="left", padx=(0, 8))
        for farbe in _FARB_OPTIONEN_FARBEN:
            rb = tk.Radiobutton(
                optionen_frame,
                variable=var,
                value=farbe,
                bg=farbe,
                activebackground=farbe,
                selectcolor=farbe,
                indicatoron=False,
                width=2,
                height=1,
                relief="raised",
                bd=2,
                cursor="hand2",
            )
            rb.pack(side="left", padx=2)
            rb._no_theme = True   # Farbquadrate nie durch Theme überschreiben
        return var

    rahmenfarbe_var = _farb_radio_zeile_bauen(1, "Streifen 1:", "rahmenfarbe")
    rahmenfarbe2_var = _farb_radio_zeile_bauen(2, "Streifen 2:", "rahmenfarbe2")
    rahmenfarbe3_var = _farb_radio_zeile_bauen(3, "Streifen 3:", "rahmenfarbe3")

    _hoehe_zeile = tk.Frame(einstellungen_tab)
    _hoehe_zeile.grid(row=4, column=0, columnspan=9, sticky="w", pady=(4, 6))
    tk.Label(_hoehe_zeile, text="Streifenhöhe:").pack(side="left", padx=(0, 6))
    _gespeicherte_hoehe = _sql_konfig_lesen("rahmenhoehe")
    rahmenhoehe_var = tk.IntVar(value=int(_gespeicherte_hoehe) if _gespeicherte_hoehe else 4)
    tk.Spinbox(_hoehe_zeile, from_=1, to=20, increment=1, textvariable=rahmenhoehe_var, width=4).pack(side="left")
    tk.Label(_hoehe_zeile, text="px").pack(side="left", padx=(4, 16))

    def rahmenfarbe_anwenden():
        farbe1 = rahmenfarbe_var.get()
        farbe2 = rahmenfarbe2_var.get()
        farbe3 = rahmenfarbe3_var.get()
        try:
            hoehe = int(rahmenhoehe_var.get())
        except Exception:
            hoehe = 4
        _sql_konfig_speichern("rahmenfarbe", farbe1)
        _sql_konfig_speichern("rahmenfarbe2", farbe2)
        _sql_konfig_speichern("rahmenfarbe3", farbe3)
        _sql_konfig_speichern("rahmenhoehe", str(hoehe))
        rahmenfarbe_setzen(farbe1, farbe2, farbe3, hoehe)

    tk.Button(_hoehe_zeile, text="Anwenden", command=rahmenfarbe_anwenden).pack(side="left")

    # ── Fensterliste-Farben ──────────────────────────────────────────────────
    ttk.Separator(einstellungen_tab, orient="horizontal").grid(
        row=5, column=0, columnspan=9, sticky="ew", pady=(8, 0))
    tk.Label(einstellungen_tab, text="Fensterliste-Farben:", font=("Segoe UI", 9, "bold")).grid(
        row=6, column=0, sticky="w", pady=(4, 2))

    fl_hellblau_var   = _farb_radio_zeile_bauen(7, "Hellblau:",   "fl_hellblau")
    fl_dunkelblau_var = _farb_radio_zeile_bauen(8, "Dunkelblau:", "fl_dunkelblau")
    fl_orange_var     = _farb_radio_zeile_bauen(9, "Orange:",     "fl_orange")

    _fl_zeile = tk.Frame(einstellungen_tab)
    _fl_zeile.grid(row=10, column=0, columnspan=9, sticky="w", pady=(4, 6))

    def fl_farben_anwenden():
        hb  = fl_hellblau_var.get()
        db  = fl_dunkelblau_var.get()
        or_ = fl_orange_var.get()
        _sql_konfig_speichern("fl_hellblau",   hb)
        _sql_konfig_speichern("fl_dunkelblau", db)
        _sql_konfig_speichern("fl_orange",     or_)
        fensterliste_farben_setzen(hb, db, or_)

    tk.Button(_fl_zeile, text="Anwenden", command=fl_farben_anwenden).pack(side="left")

    # ── Treeview-Theme ──────────────────────────────────────────────────────
    ttk.Separator(einstellungen_tab, orient="horizontal").grid(
        row=11, column=0, columnspan=9, sticky="ew", pady=(8, 0))
    tk.Label(einstellungen_tab, text="Tabellen-Theme:", font=("Segoe UI", 9, "bold")).grid(
        row=12, column=0, sticky="w", pady=(4, 2))

    _tv_theme_var = tk.StringVar(value=_sql_konfig_lesen("treeview_theme") or "standard")
    _tv_theme_frame = tk.Frame(einstellungen_tab)
    _tv_theme_frame.grid(row=13, column=0, columnspan=9, sticky="w", pady=(0, 6))

    def _tv_theme_anwenden():
        treeview_theme_anwenden(_tv_theme_var.get(), speichern=True)

    _tv_themes_konfig = [
        ("standard",  "Standard",
         {"bg": "#f0f0f0", "fg": "black",   "activebackground": "#d0d0d0", "activeforeground": "black",   "selectcolor": "#f0f0f0"}, {}),
        ("bernstein", "Bernstein",
         {"bg": "#000000", "fg": "#FFBF00", "activebackground": "#7A5C00", "activeforeground": "#FFBF00", "selectcolor": "#000000"}, {}),
        ("phosphor",  "Phosphor-Grün",
         {"bg": "#000000", "fg": "#33FF33", "activebackground": "#1A6600", "activeforeground": "#33FF33", "selectcolor": "#000000"}, {}),
    ]
    for _tv_val, _tv_lbl, _tv_style, _ in _tv_themes_konfig:
        _tv_btn = tk.Radiobutton(
            _tv_theme_frame,
            text=_tv_lbl,
            variable=_tv_theme_var,
            value=_tv_val,
            indicatoron=False,
            width=14,
            relief="raised",
            bd=2,
            cursor="hand2",
            command=_tv_theme_anwenden,
            **_tv_style,
        )
        _tv_btn.pack(side="left", padx=(0, 6))
        _tv_btn._no_theme = True   # Theme-Buttons behalten immer ihre eigene Farbe

    workflow_frame = tk.Frame(projekt_tab)
    workflow_frame.grid(row=2, column=1, sticky="nsew", pady=(0, 2), padx=(4, 0))
    workflow_frame.grid_rowconfigure(0, weight=1)
    workflow_frame.grid_columnconfigure(0, weight=1)

    tree_workflow = ttk.Treeview(
        workflow_frame,
        columns=("typ", "name"),
        show="headings",
        selectmode="browse",
        height=5,
    )
    tree_workflow.heading("typ", text="Typ", anchor="w", command=lambda: _tv_sortieren(tree_workflow, "typ"))
    tree_workflow.column("typ", width=80, anchor="w", stretch=False)
    tree_workflow.heading("name", text="Name", anchor="w", command=lambda: _tv_sortieren(tree_workflow, "name"))
    tree_workflow.column("name", width=400, anchor="w", stretch=True)
    wf_scroll = ttk.Scrollbar(workflow_frame, orient="vertical", command=tree_workflow.yview)
    tree_workflow.configure(yscrollcommand=wf_scroll.set)
    tree_workflow.grid(row=0, column=0, sticky="nsew")
    wf_scroll.grid(row=0, column=1, sticky="ns")

    beziehungen = [
        {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
        {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
        {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
    ]
    aktuelle_beziehung = {"index": 0}

    tk.Label(select_tab, text="Beziehung:").grid(row=0, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    beziehungs_kopf = tk.Frame(select_tab)
    beziehungs_kopf.grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 4))
    beziehungs_kopf.grid_columnconfigure(1, weight=1)
    beziehung_auswahl = ttk.Combobox(
        beziehungs_kopf,
        state="readonly",
        width=14,
        values=["Beziehung 1", "Beziehung 2", "Beziehung 3"]
    )
    beziehung_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    beziehung_auswahl.set("Beziehung 1")
    beziehung_status = tk.Label(beziehungs_kopf, text="Eine Beziehung bearbeiten.", anchor="w")
    beziehung_status.grid(row=0, column=1, sticky="ew")
    button_beziehung_einfuegen = tk.Button(beziehungs_kopf, text="In Statement einfügen", width=18)
    button_beziehung_einfuegen.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_beziehung_neu = tk.Button(beziehungs_kopf, text="Neu", width=8)
    button_beziehung_neu.grid(row=0, column=3, sticky="w", padx=(8, 0))
    button_beziehung_loeschen = tk.Button(beziehungs_kopf, text="Löschen", width=8)
    button_beziehung_loeschen.grid(row=0, column=4, sticky="w", padx=(8, 0))

    tk.Label(select_tab, text="JOIN:").grid(row=1, column=0, sticky="nw", pady=(0, 4), padx=(0, 6))
    beziehung_oben = tk.Frame(select_tab)
    beziehung_oben.grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 4))
    tk.Label(beziehung_oben, text="Typ").grid(row=0, column=0, sticky="w")
    tk.Label(beziehung_oben, text="Join-Tabelle").grid(row=0, column=1, sticky="w", padx=(8, 0))
    tk.Label(beziehung_oben, text="linke Tabelle").grid(row=0, column=2, sticky="w", padx=(8, 0))
    tk.Label(beziehung_oben, text="rechte Tabelle").grid(row=0, column=3, sticky="w", padx=(8, 0))
    b_typ = ttk.Combobox(beziehung_oben, state="readonly", width=13, values=["", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN"])
    b_typ.grid(row=1, column=0, sticky="w")
    b_tab = ttk.Combobox(beziehung_oben, state="readonly", width=auswahl_breite)
    b_tab.grid(row=1, column=1, sticky="w", padx=(8, 0))
    tabellen_combos.append(b_tab)
    b_links_tab = ttk.Combobox(beziehung_oben, state="readonly", width=auswahl_breite)
    b_links_tab.grid(row=1, column=2, sticky="w", padx=(8, 0))
    tabellen_combos.append(b_links_tab)
    b_rechts_tab = ttk.Combobox(beziehung_oben, state="readonly", width=auswahl_breite)
    b_rechts_tab.grid(row=1, column=3, sticky="w", padx=(8, 0))
    tabellen_combos.append(b_rechts_tab)

    tk.Label(select_tab, text="Felder:").grid(row=2, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    beziehung_felder = tk.Frame(select_tab)
    beziehung_felder.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 6))
    b_links = ttk.Combobox(beziehung_felder, width=auswahl_breite)
    b_links.grid(row=0, column=0, sticky="w")
    feld_combos.append(b_links)
    tk.Label(beziehung_felder, text="=").grid(row=0, column=1, padx=4)
    b_rechts = ttk.Combobox(beziehung_felder, width=auswahl_breite)
    b_rechts.grid(row=0, column=2, sticky="w")
    feld_combos.append(b_rechts)

    where_bedingungen = [
        {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        {"verknuepfung": "AND", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        {"verknuepfung": "AND", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        {"verknuepfung": "AND", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        {"verknuepfung": "AND", "tabelle": "", "links": "", "operator": "=", "wert": ""},
    ]
    aktuelle_where_bedingung = {"index": 0}

    tk.Label(select_tab, text="WHERE:").grid(row=3, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    where_kopf = tk.Frame(select_tab)
    where_kopf.grid(row=3, column=1, columnspan=3, sticky="w", pady=(0, 4))
    where_kopf.grid_columnconfigure(1, weight=1)
    where_auswahl = ttk.Combobox(
        where_kopf,
        state="readonly",
        width=14,
        values=["Bedingung 1", "Bedingung 2", "Bedingung 3", "Bedingung 4", "Bedingung 5"]
    )
    where_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    where_auswahl.set("Bedingung 1")
    where_status = tk.Label(where_kopf, text="Eine WHERE-Bedingung bearbeiten.", anchor="w")
    where_status.grid(row=0, column=1, sticky="ew")
    button_where_einfuegen = tk.Button(where_kopf, text="In Statement einfügen", width=18)
    button_where_einfuegen.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_where_neu = tk.Button(where_kopf, text="Neu", width=8)
    button_where_neu.grid(row=0, column=3, sticky="w", padx=(8, 0))
    button_where_loeschen = tk.Button(where_kopf, text="Löschen", width=8)
    button_where_loeschen.grid(row=0, column=4, sticky="w", padx=(8, 0))

    tk.Label(select_tab, text="Tabelle:").grid(row=4, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    where_tabelle_frame = tk.Frame(select_tab)
    where_tabelle_frame.grid(row=4, column=1, columnspan=3, sticky="w", pady=(0, 4))
    tk.Label(where_tabelle_frame, text="Verknüpfung").grid(row=0, column=0, sticky="w")
    tk.Label(where_tabelle_frame, text="Tabelle").grid(row=0, column=1, sticky="w", padx=(8, 0))
    w_verknuepfung = ttk.Combobox(where_tabelle_frame, state="readonly", width=10, values=["WHERE", "AND", "OR"])
    w_verknuepfung.grid(row=1, column=0, sticky="w")
    w_tab = ttk.Combobox(where_tabelle_frame, state="readonly", width=auswahl_breite)
    tabellen_combos.append(w_tab)
    w_tab.grid(row=1, column=1, sticky="w", padx=(8, 0))

    tk.Label(select_tab, text="Feld / Wert:").grid(row=5, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    where_frame = tk.Frame(select_tab)
    where_frame.grid(row=5, column=1, columnspan=3, sticky="w", pady=(0, 6))
    w_links = ttk.Combobox(where_frame, width=auswahl_breite)
    feld_combos.append(w_links)
    w_links.grid(row=0, column=0, sticky="w", padx=(0, 8))
    w_operator = ttk.Combobox(
        where_frame,
        state="readonly",
        width=12,
        values=["=", "<>", "LIKE", "NOT LIKE", ">", ">=", "<", "<=", "IS NULL", "IS NOT NULL", "IN", "NOT IN"]
    )
    w_operator.grid(row=0, column=1, sticky="w", padx=(0, 8))
    w_wert = tk.Entry(where_frame, width=eingabe_breite)
    w_wert.grid(row=0, column=2, sticky="w")

    order_by_zeilen = [
        {"feld": "", "richtung": "ASC"},
    ]
    aktuelle_order_by = {"index": 0}

    tk.Label(select_tab, text="ORDER BY:").grid(row=6, column=0, sticky="w", pady=(0, 4), padx=(0, 6))
    order_by_kopf = tk.Frame(select_tab)
    order_by_kopf.grid(row=6, column=1, columnspan=3, sticky="w", pady=(0, 4))
    order_by_kopf.grid_columnconfigure(1, weight=1)
    order_by_auswahl = ttk.Combobox(
        order_by_kopf,
        state="readonly",
        width=14,
        values=["Eintrag 1"]
    )
    order_by_auswahl.grid(row=0, column=0, sticky="w", padx=(0, 8))
    order_by_auswahl.set("Eintrag 1")
    order_by_status = tk.Label(order_by_kopf, text="Einen ORDER BY Eintrag bearbeiten.", anchor="w")
    order_by_status.grid(row=0, column=1, sticky="ew")
    button_order_by_einfuegen = tk.Button(order_by_kopf, text="In Statement einfügen", width=18)
    button_order_by_einfuegen.grid(row=0, column=2, sticky="w", padx=(12, 0))
    button_alle_order_by_einfuegen = tk.Button(order_by_kopf, text="Alle einfügen", width=13)
    button_alle_order_by_einfuegen.grid(row=0, column=3, sticky="w", padx=(8, 0))
    button_order_by_neu = tk.Button(order_by_kopf, text="Neu", width=8)
    button_order_by_neu.grid(row=0, column=4, sticky="w", padx=(8, 0))
    button_order_by_loeschen = tk.Button(order_by_kopf, text="Löschen", width=8)
    button_order_by_loeschen.grid(row=0, column=5, sticky="w", padx=(8, 0))

    tk.Label(select_tab, text="Feld / Richtung:").grid(row=7, column=0, sticky="w", pady=(0, 6), padx=(0, 6))
    order_by_frame = tk.Frame(select_tab)
    order_by_frame.grid(row=7, column=1, columnspan=3, sticky="w", pady=(0, 6))
    order_by_tab = ttk.Combobox(order_by_frame, state="readonly", width=auswahl_breite)
    tabellen_combos.append(order_by_tab)
    order_by_tab.grid(row=0, column=0, sticky="w", padx=(0, 8))
    order_by_feld = ttk.Combobox(order_by_frame, width=auswahl_breite)
    feld_combos.append(order_by_feld)
    order_by_feld.grid(row=0, column=1, sticky="w", padx=(0, 8))
    order_by_richtung = ttk.Combobox(order_by_frame, state="readonly", width=8, values=["ASC", "DESC"])
    order_by_richtung.set("ASC")
    order_by_richtung.grid(row=0, column=2, sticky="w")

    editor = tk.Text(right, wrap="word")
    editor.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(6, 8))
    _themed_text_widgets.append(editor)
    def _editor_destroy(event, _w=editor):
        try:
            _themed_text_widgets.remove(_w)
        except Exception:
            pass
    editor.bind("<Destroy>", _editor_destroy)

    button_frame = tk.Frame(right)
    button_frame.grid(row=2, column=0, columnspan=4, sticky="w")

    daten_cache = {}

    def set_entry(widget, value):
        wert = value or ""
        try:
            if isinstance(widget, ttk.Combobox):
                aktuelle_werte = list(widget.cget("values"))
                if wert and wert not in aktuelle_werte:
                    widget["values"] = aktuelle_werte + [wert]
                widget.set(wert)
            else:
                widget.delete(0, "end")
                widget.insert(0, wert)
        except Exception:
            try:
                widget.set(wert)
            except Exception:
                pass

    def qualifizierte_felder_fuer_tabelle(tabellenname):
        tabellenname = (tabellenname or "").strip()
        if not tabellenname:
            return []
        try:
            return [f"{tabellenname}.{spalte}" for spalte in tabellenspalten_laden(tabellenname)]
        except Exception as e:
            debug_log(f"Feldliste konnte nicht geladen werden: tabelle={tabellenname}, fehler={e}", "allgemein")
            return []

    def combobox_wertliste_setzen(combobox, werte, aktueller_wert=""):
        werte_liste = [""] + list(werte)
        if aktueller_wert and aktueller_wert not in werte_liste:
            werte_liste.append(aktueller_wert)
        combobox["values"] = werte_liste
        if aktueller_wert:
            combobox.set(aktueller_wert)

    def beziehung_auswahlwerte_aktualisieren():
        werte = [f"Beziehung {i + 1}" for i in range(len(beziehungen))]
        beziehung_auswahl["values"] = werte
        if werte:
            index = max(0, min(aktuelle_beziehung["index"], len(werte) - 1))
            aktuelle_beziehung["index"] = index
            beziehung_auswahl.set(werte[index])

    def where_auswahlwerte_aktualisieren():
        werte = [f"Bedingung {i + 1}" for i in range(len(where_bedingungen))]
        where_auswahl["values"] = werte
        if werte:
            index = max(0, min(aktuelle_where_bedingung["index"], len(werte) - 1))
            aktuelle_where_bedingung["index"] = index
            where_auswahl.set(werte[index])

    def join_linke_felder_aktualisieren(event=None):
        combobox_wertliste_setzen(b_links, qualifizierte_felder_fuer_tabelle(b_links_tab.get()), b_links.get().strip())

    def join_rechte_felder_aktualisieren(event=None):
        combobox_wertliste_setzen(b_rechts, qualifizierte_felder_fuer_tabelle(b_rechts_tab.get()), b_rechts.get().strip())

    def where_felder_aktualisieren(event=None):
        combobox_wertliste_setzen(w_links, qualifizierte_felder_fuer_tabelle(w_tab.get()), w_links.get().strip())

    def join_zieltabelle_gewechselt(event=None):
        if b_tab.get().strip() and not b_rechts_tab.get().strip():
            b_rechts_tab.set(b_tab.get().strip())
        join_rechte_felder_aktualisieren()

    def beziehung_widgetwerte_speichern():
        index = aktuelle_beziehung["index"]
        beziehungen[index]["typ"] = b_typ.get().strip()
        beziehungen[index]["tabelle"] = b_tab.get().strip()
        beziehungen[index]["links_tabelle"] = b_links_tab.get().strip()
        beziehungen[index]["rechts_tabelle"] = b_rechts_tab.get().strip()
        beziehungen[index]["links"] = b_links.get().strip()
        beziehungen[index]["rechts"] = b_rechts.get().strip()

    def beziehung_widgetwerte_laden(index):
        daten = beziehungen[index]
        b_typ.set(daten.get("typ", "") or "")
        set_entry(b_tab, daten.get("tabelle", ""))
        set_entry(b_links_tab, daten.get("links_tabelle", ""))
        set_entry(b_rechts_tab, daten.get("rechts_tabelle", ""))
        join_linke_felder_aktualisieren()
        join_rechte_felder_aktualisieren()
        set_entry(b_links, daten.get("links", ""))
        set_entry(b_rechts, daten.get("rechts", ""))
        beziehung_status.config(text=f"Bearbeitet wird Beziehung {index + 1} von {len(beziehungen)}.")

    def beziehung_auswahl_gewechselt(event=None):
        beziehung_widgetwerte_speichern()
        auswahl = beziehung_auswahl.get().strip()
        try:
            neuer_index = int(auswahl.split()[-1]) - 1
        except Exception:
            neuer_index = 0
        if neuer_index < 0 or neuer_index >= len(beziehungen):
            neuer_index = 0
        aktuelle_beziehung["index"] = neuer_index
        beziehung_widgetwerte_laden(neuer_index)

    def beziehung_neu():
        beziehung_widgetwerte_speichern()
        beziehungen.append({"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""})
        aktuelle_beziehung["index"] = len(beziehungen) - 1
        beziehung_auswahlwerte_aktualisieren()
        beziehung_widgetwerte_laden(aktuelle_beziehung["index"])

    def beziehung_loeschen():
        if len(beziehungen) <= 1:
            messagebox.showwarning("Beziehung löschen", "Mindestens eine Beziehung bleibt erhalten.", parent=top)
            return
        index = aktuelle_beziehung["index"]
        if not messagebox.askyesno("Beziehung löschen", f"Beziehung {index + 1} wirklich löschen?", parent=top):
            return
        del beziehungen[index]
        aktuelle_beziehung["index"] = max(0, min(index, len(beziehungen) - 1))
        beziehung_auswahlwerte_aktualisieren()
        beziehung_widgetwerte_laden(aktuelle_beziehung["index"])

    def beziehung_in_statement_einfuegen():
        beziehung_widgetwerte_speichern()
        daten = beziehungen[aktuelle_beziehung["index"]]
        typ = daten.get("typ", "").strip()
        tabelle = daten.get("tabelle", "").strip()
        links = daten.get("links", "").strip()
        rechts = daten.get("rechts", "").strip()
        if not typ or not tabelle or not links or not rechts:
            messagebox.showwarning(
                "Beziehung einfügen",
                "Bitte Beziehungstyp, Tabelle, linkes Feld und rechtes Feld ausfüllen.",
                parent=top
            )
            return
        snippet = f"{typ} {tabelle} ON {links} = {rechts}"
        aktueller_text = editor.get("1.0", "end-1c")
        einfuegetext = snippet
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            einfuegetext = "\n" + einfuegetext
        editor.insert("insert", einfuegetext + "\n")
        editor.focus_force()
        debug_log(
            f"SQL-Beziehung in Statement eingefuegt: beziehung={aktuelle_beziehung['index'] + 1}, snippet={snippet}",
            "allgemein"
        )

    def where_widgetwerte_speichern():
        index = aktuelle_where_bedingung["index"]
        where_bedingungen[index]["verknuepfung"] = w_verknuepfung.get().strip() or "WHERE"
        where_bedingungen[index]["tabelle"] = w_tab.get().strip()
        where_bedingungen[index]["links"] = w_links.get().strip()
        where_bedingungen[index]["operator"] = w_operator.get().strip() or "="
        where_bedingungen[index]["wert"] = w_wert.get().strip()

    def where_widgetwerte_laden(index):
        daten = where_bedingungen[index]
        w_verknuepfung.set(daten.get("verknuepfung", "") or ("WHERE" if index == 0 else "AND"))
        set_entry(w_tab, daten.get("tabelle", ""))
        where_felder_aktualisieren()
        set_entry(w_links, daten.get("links", ""))
        w_operator.set(daten.get("operator", "") or "=")
        set_entry(w_wert, daten.get("wert", ""))
        where_status.config(text=f"Bearbeitet wird Bedingung {index + 1} von {len(where_bedingungen)}.")

    def where_auswahl_gewechselt(event=None):
        where_widgetwerte_speichern()
        auswahl = where_auswahl.get().strip()
        try:
            neuer_index = int(auswahl.split()[-1]) - 1
        except Exception:
            neuer_index = 0
        if neuer_index < 0 or neuer_index >= len(where_bedingungen):
            neuer_index = 0
        aktuelle_where_bedingung["index"] = neuer_index
        where_widgetwerte_laden(neuer_index)

    def where_neu():
        where_widgetwerte_speichern()
        verknuepfung = "WHERE" if len(where_bedingungen) == 0 else "AND"
        where_bedingungen.append({"verknuepfung": verknuepfung, "tabelle": "", "links": "", "operator": "=", "wert": ""})
        aktuelle_where_bedingung["index"] = len(where_bedingungen) - 1
        where_auswahlwerte_aktualisieren()
        where_widgetwerte_laden(aktuelle_where_bedingung["index"])

    def where_loeschen():
        if len(where_bedingungen) <= 1:
            messagebox.showwarning("WHERE löschen", "Mindestens eine WHERE-Bedingung bleibt erhalten.", parent=top)
            return
        index = aktuelle_where_bedingung["index"]
        if not messagebox.askyesno("WHERE löschen", f"Bedingung {index + 1} wirklich löschen?", parent=top):
            return
        del where_bedingungen[index]
        aktuelle_where_bedingung["index"] = max(0, min(index, len(where_bedingungen) - 1))
        where_auswahlwerte_aktualisieren()
        where_widgetwerte_laden(aktuelle_where_bedingung["index"])

    def where_wert_sql_formatieren(operator, wert):
        operator = operator.upper().strip()
        wert = str(wert).strip()
        if operator in ("IS NULL", "IS NOT NULL"):
            return ""
        if operator in ("IN", "NOT IN"):
            if wert.startswith("(") and wert.endswith(")"):
                return wert
            return f"({wert})"
        if not wert:
            return "''"
        if (
            wert.startswith("'")
            or wert.startswith('"')
            or wert.startswith("(")
            or wert.upper() in ("NULL", "TRUE", "FALSE")
        ):
            return wert
        try:
            float(wert.replace(",", "."))
            return wert.replace(",", ".")
        except Exception:
            return "'" + wert.replace("'", "''") + "'"

    def where_in_statement_einfuegen():
        where_widgetwerte_speichern()
        daten = where_bedingungen[aktuelle_where_bedingung["index"]]
        verknuepfung = daten.get("verknuepfung", "WHERE").strip() or "WHERE"
        links = daten.get("links", "").strip()
        operator = daten.get("operator", "=").strip() or "="
        wert = daten.get("wert", "").strip()
        if not links:
            messagebox.showwarning("WHERE einfügen", "Bitte ein Feld oder einen Ausdruck für die linke Seite angeben.", parent=top)
            return
        if operator.upper() not in ("IS NULL", "IS NOT NULL") and not wert:
            messagebox.showwarning("WHERE einfügen", "Bitte einen Vergleichswert angeben.", parent=top)
            return
        wert_sql = where_wert_sql_formatieren(operator, wert)
        if wert_sql:
            snippet = f"{verknuepfung} {links} {operator} {wert_sql}"
        else:
            snippet = f"{verknuepfung} {links} {operator}"
        aktueller_text = editor.get("1.0", "end-1c")
        einfuegetext = snippet
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            einfuegetext = "\n" + einfuegetext
        editor.insert("insert", einfuegetext + "\n")
        editor.focus_force()
        debug_log(
            f"SQL-WHERE in Statement eingefuegt: bedingung={aktuelle_where_bedingung['index'] + 1}, snippet={snippet}",
            "allgemein"
        )

    def order_by_felder_aktualisieren(event=None):
        feldliste = qualifizierte_felder_fuer_tabelle(order_by_tab.get())
        combobox_wertliste_setzen(order_by_feld, feldliste, order_by_feld.get().strip())

    def order_by_auswahlwerte_aktualisieren():
        werte = [f"Eintrag {i + 1}" for i in range(len(order_by_zeilen))]
        order_by_auswahl["values"] = werte
        if werte:
            index = max(0, min(aktuelle_order_by["index"], len(werte) - 1))
            aktuelle_order_by["index"] = index
            order_by_auswahl.set(werte[index])

    def order_by_widgetwerte_speichern():
        index = aktuelle_order_by["index"]
        tab = order_by_tab.get().strip()
        feld = order_by_feld.get().strip()
        if tab and feld and not feld.startswith(tab + "."):
            feld = f"{tab}.{feld}"
        order_by_zeilen[index]["feld"] = feld
        order_by_zeilen[index]["richtung"] = order_by_richtung.get().strip() or "ASC"

    def order_by_widgetwerte_laden(index):
        daten = order_by_zeilen[index]
        feld = daten.get("feld", "")
        richtung = daten.get("richtung", "ASC") or "ASC"
        if "." in feld:
            tab = feld.split(".", 1)[0]
        else:
            tab = ""
        set_entry(order_by_tab, tab)
        if tab:
            order_by_felder_aktualisieren()
        set_entry(order_by_feld, feld)
        order_by_richtung.set(richtung)
        order_by_status.config(text=f"Bearbeitet wird Eintrag {index + 1} von {len(order_by_zeilen)}.")

    def order_by_auswahl_gewechselt(event=None):
        order_by_widgetwerte_speichern()
        try:
            neuer_index = int(order_by_auswahl.get().split()[-1]) - 1
        except Exception:
            neuer_index = 0
        if neuer_index < 0 or neuer_index >= len(order_by_zeilen):
            neuer_index = 0
        aktuelle_order_by["index"] = neuer_index
        order_by_widgetwerte_laden(neuer_index)

    def order_by_neu():
        order_by_widgetwerte_speichern()
        order_by_zeilen.append({"feld": "", "richtung": "ASC"})
        aktuelle_order_by["index"] = len(order_by_zeilen) - 1
        order_by_auswahlwerte_aktualisieren()
        order_by_widgetwerte_laden(aktuelle_order_by["index"])

    def order_by_loeschen():
        if len(order_by_zeilen) <= 1:
            messagebox.showwarning("ORDER BY löschen", "Mindestens ein ORDER BY Eintrag bleibt erhalten.", parent=top)
            return
        index = aktuelle_order_by["index"]
        if not messagebox.askyesno("ORDER BY löschen", f"Eintrag {index + 1} wirklich löschen?", parent=top):
            return
        del order_by_zeilen[index]
        aktuelle_order_by["index"] = max(0, min(index, len(order_by_zeilen) - 1))
        order_by_auswahlwerte_aktualisieren()
        order_by_widgetwerte_laden(aktuelle_order_by["index"])

    def order_by_in_statement_einfuegen():
        order_by_widgetwerte_speichern()
        daten = order_by_zeilen[aktuelle_order_by["index"]]
        feld = daten.get("feld", "").strip()
        richtung = daten.get("richtung", "ASC").strip() or "ASC"
        if not feld:
            messagebox.showwarning("ORDER BY einfügen", "Bitte zuerst ein Feld angeben.", parent=top)
            return
        snippet = f"ORDER BY {feld} {richtung}"
        aktueller_text = editor.get("1.0", "end-1c")
        einfuegetext = snippet
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            einfuegetext = "\n" + einfuegetext
        editor.insert("insert", einfuegetext + "\n")
        editor.focus_force()
        debug_log(f"SQL-ORDER BY Eintrag eingefuegt: snippet={snippet}", "allgemein")

    def alle_order_by_in_statement_einfuegen():
        order_by_widgetwerte_speichern()
        teile = []
        for eintrag in order_by_zeilen:
            feld = eintrag.get("feld", "").strip()
            richtung = eintrag.get("richtung", "ASC").strip() or "ASC"
            if feld:
                teile.append(f"{feld} {richtung}")
        if not teile:
            messagebox.showwarning("ORDER BY einfügen", "Bitte mindestens ein Feld angeben.", parent=top)
            return
        snippet = "ORDER BY " + ", ".join(teile)
        aktueller_text = editor.get("1.0", "end-1c")
        einfuegetext = snippet
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            einfuegetext = "\n" + einfuegetext
        editor.insert("insert", einfuegetext + "\n")
        editor.focus_force()
        debug_log(f"SQL-ORDER BY komplett eingefuegt: {snippet}", "allgemein")

    def update_felder_aktualisieren(event=None):
        feldliste = qualifizierte_felder_fuer_tabelle(update_tabelle.get())
        combobox_wertliste_setzen(update_set_feld, feldliste, update_set_feld.get().strip())
        combobox_wertliste_setzen(update_where_feld, feldliste, update_where_feld.get().strip())

    def update_set_auswahlwerte_aktualisieren():
        werte = [f"SET {i + 1}" for i in range(len(update_sets))]
        update_set_auswahl["values"] = werte
        index = max(0, min(aktuelle_update_set["index"], len(werte) - 1))
        aktuelle_update_set["index"] = index
        update_set_auswahl.set(werte[index])

    def update_set_widgetwerte_speichern():
        index = aktuelle_update_set["index"]
        update_sets[index]["feld"] = update_set_feld.get().strip()
        update_sets[index]["wert"] = update_set_wert.get().strip()

    def update_set_widgetwerte_laden(index):
        daten = update_sets[index]
        update_felder_aktualisieren()
        set_entry(update_set_feld, daten.get("feld", ""))
        set_entry(update_set_wert, daten.get("wert", ""))
        update_set_status.config(text=f"Bearbeitet wird SET {index + 1} von {len(update_sets)}.")

    def update_set_auswahl_gewechselt(event=None):
        update_set_widgetwerte_speichern()
        try:
            neuer_index = int(update_set_auswahl.get().split()[-1]) - 1
        except Exception:
            neuer_index = 0
        neue_grenze = max(0, min(neuer_index, len(update_sets) - 1))
        aktuelle_update_set["index"] = neue_grenze
        update_set_widgetwerte_laden(neue_grenze)

    def update_set_neu():
        update_set_widgetwerte_speichern()
        update_sets.append({"feld": "", "wert": ""})
        aktuelle_update_set["index"] = len(update_sets) - 1
        update_set_auswahlwerte_aktualisieren()
        update_set_widgetwerte_laden(aktuelle_update_set["index"])

    def update_set_loeschen():
        if len(update_sets) <= 1:
            messagebox.showwarning("SET löschen", "Mindestens eine SET-Zeile bleibt erhalten.", parent=top)
            return
        index = aktuelle_update_set["index"]
        if not messagebox.askyesno("SET löschen", f"SET {index + 1} wirklich löschen?", parent=top):
            return
        del update_sets[index]
        aktuelle_update_set["index"] = max(0, min(index, len(update_sets) - 1))
        update_set_auswahlwerte_aktualisieren()
        update_set_widgetwerte_laden(aktuelle_update_set["index"])

    def update_where_auswahlwerte_aktualisieren():
        werte = [f"Bedingung {i + 1}" for i in range(len(update_where_bedingungen))]
        update_where_auswahl["values"] = werte
        index = max(0, min(aktuelle_update_where["index"], len(werte) - 1))
        aktuelle_update_where["index"] = index
        update_where_auswahl.set(werte[index])

    def update_where_widgetwerte_speichern():
        index = aktuelle_update_where["index"]
        update_where_bedingungen[index]["verknuepfung"] = update_where_verknuepfung.get().strip() or "WHERE"
        update_where_bedingungen[index]["tabelle"] = update_tabelle.get().strip()
        update_where_bedingungen[index]["links"] = update_where_feld.get().strip()
        update_where_bedingungen[index]["operator"] = update_where_operator.get().strip() or "="
        update_where_bedingungen[index]["wert"] = update_where_wert.get().strip()

    def update_where_widgetwerte_laden(index):
        daten = update_where_bedingungen[index]
        update_felder_aktualisieren()
        update_where_verknuepfung.set(daten.get("verknuepfung", "") or ("WHERE" if index == 0 else "AND"))
        set_entry(update_where_feld, daten.get("links", ""))
        update_where_operator.set(daten.get("operator", "") or "=")
        set_entry(update_where_wert, daten.get("wert", ""))
        update_where_status.config(text=f"Bearbeitet wird Bedingung {index + 1} von {len(update_where_bedingungen)}.")

    def update_where_auswahl_gewechselt(event=None):
        update_where_widgetwerte_speichern()
        try:
            neuer_index = int(update_where_auswahl.get().split()[-1]) - 1
        except Exception:
            neuer_index = 0
        neue_grenze = max(0, min(neuer_index, len(update_where_bedingungen) - 1))
        aktuelle_update_where["index"] = neue_grenze
        update_where_widgetwerte_laden(neue_grenze)

    def update_where_neu():
        update_where_widgetwerte_speichern()
        update_where_bedingungen.append({"verknuepfung": "AND", "tabelle": update_tabelle.get().strip(), "links": "", "operator": "=", "wert": ""})
        aktuelle_update_where["index"] = len(update_where_bedingungen) - 1
        update_where_auswahlwerte_aktualisieren()
        update_where_widgetwerte_laden(aktuelle_update_where["index"])

    def update_where_loeschen():
        if len(update_where_bedingungen) <= 1:
            messagebox.showwarning("WHERE löschen", "Mindestens eine WHERE-Bedingung bleibt erhalten.", parent=top)
            return
        index = aktuelle_update_where["index"]
        if not messagebox.askyesno("WHERE löschen", f"Bedingung {index + 1} wirklich löschen?", parent=top):
            return
        del update_where_bedingungen[index]
        aktuelle_update_where["index"] = max(0, min(index, len(update_where_bedingungen) - 1))
        update_where_auswahlwerte_aktualisieren()
        update_where_widgetwerte_laden(aktuelle_update_where["index"])

    def update_in_statement_einfuegen():
        update_set_widgetwerte_speichern()
        update_where_widgetwerte_speichern()
        tabelle = update_tabelle.get().strip()
        if not tabelle:
            messagebox.showwarning("UPDATE einfügen", "Bitte zuerst eine UPDATE-Tabelle auswählen.", parent=top)
            return

        def update_feldname_bereinigen(feldname):
            feldname = (feldname or "").strip()
            if "." in feldname:
                feldname = feldname.rsplit(".", 1)[1].strip()
            return feldname

        set_teile = []
        for eintrag in update_sets:
            feld = update_feldname_bereinigen(eintrag.get("feld", ""))
            wert = eintrag.get("wert", "").strip()
            if feld:
                set_teile.append(f"{sql_identifier(feld)} = {where_wert_sql_formatieren('=', wert)}")
        if not set_teile:
            messagebox.showwarning("UPDATE einfügen", "Bitte mindestens ein SET-Feld angeben.", parent=top)
            return
        where_teile = []
        for i, eintrag in enumerate(update_where_bedingungen):
            links = update_feldname_bereinigen(eintrag.get("links", ""))
            operator = eintrag.get("operator", "=").strip() or "="
            wert = eintrag.get("wert", "").strip()
            verknuepfung = eintrag.get("verknuepfung", "WHERE").strip() or ("WHERE" if i == 0 else "AND")
            if not links:
                continue
            wert_sql = where_wert_sql_formatieren(operator, wert)
            if wert_sql:
                where_teile.append(f"{verknuepfung} {sql_identifier(links)} {operator} {wert_sql}")
            else:
                where_teile.append(f"{verknuepfung} {sql_identifier(links)} {operator}")
        snippet = f"UPDATE {sql_identifier(tabelle)}\nSET " + ",\n    ".join(set_teile)
        if where_teile:
            snippet += "\n" + "\n".join(where_teile)
        else:
            if not messagebox.askyesno(
                "UPDATE ohne WHERE",
                "Es wurde keine WHERE-Bedingung angegeben.\n\nSoll das UPDATE-Statement trotzdem eingefügt werden?",
                parent=top
            ):
                return
        aktueller_text = editor.get("1.0", "end-1c")
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            snippet = "\n" + snippet
        editor.insert("insert", snippet + "\n")
        editor.focus_force()
        debug_log(f"SQL-UPDATE in Statement eingefuegt: tabelle={tabelle}, sets={len(set_teile)}, where={len(where_teile)}", "allgemein")

    def delete_felder_aktualisieren(event=None):
        feldliste = qualifizierte_felder_fuer_tabelle(delete_tabelle.get())
        combobox_wertliste_setzen(delete_where_feld, feldliste, delete_where_feld.get().strip())

    def delete_where_auswahlwerte_aktualisieren():
        werte = [f"Bedingung {i + 1}" for i in range(len(delete_where_bedingungen))]
        delete_where_auswahl["values"] = werte
        index = max(0, min(aktuelle_delete_where["index"], len(werte) - 1))
        aktuelle_delete_where["index"] = index
        delete_where_auswahl.set(werte[index])

    def delete_where_widgetwerte_speichern():
        index = aktuelle_delete_where["index"]
        delete_where_bedingungen[index]["verknuepfung"] = delete_where_verknuepfung.get().strip() or ("WHERE" if index == 0 else "AND")
        delete_where_bedingungen[index]["tabelle"] = delete_tabelle.get().strip()
        delete_where_bedingungen[index]["links"] = delete_where_feld.get().strip()
        delete_where_bedingungen[index]["operator"] = delete_where_operator.get().strip() or "="
        delete_where_bedingungen[index]["wert"] = delete_where_wert.get().strip()

    def delete_where_widgetwerte_laden(index):
        daten = delete_where_bedingungen[index]
        delete_felder_aktualisieren()
        set_entry(delete_where_verknuepfung, daten.get("verknuepfung", "WHERE" if index == 0 else "AND"))
        set_entry(delete_where_feld, daten.get("links", ""))
        set_entry(delete_where_operator, daten.get("operator", "="))
        set_entry(delete_where_wert, daten.get("wert", ""))
        delete_where_status.config(text=f"Bearbeitet wird Bedingung {index + 1} von {len(delete_where_bedingungen)}.")

    def delete_where_auswahl_gewechselt(event=None):
        delete_where_widgetwerte_speichern()
        try:
            index = int(delete_where_auswahl.get().replace("Bedingung", "").strip()) - 1
        except Exception:
            index = 0
        aktuelle_delete_where["index"] = max(0, min(index, len(delete_where_bedingungen) - 1))
        delete_where_widgetwerte_laden(aktuelle_delete_where["index"])

    def delete_where_neu():
        delete_where_widgetwerte_speichern()
        delete_where_bedingungen.append({"verknuepfung": "AND", "tabelle": delete_tabelle.get().strip(), "links": "", "operator": "=", "wert": ""})
        aktuelle_delete_where["index"] = len(delete_where_bedingungen) - 1
        delete_where_auswahlwerte_aktualisieren()
        delete_where_widgetwerte_laden(aktuelle_delete_where["index"])

    def delete_where_loeschen():
        if len(delete_where_bedingungen) <= 1:
            messagebox.showwarning("DELETE-WHERE löschen", "Mindestens eine WHERE-Bedingung bleibt erhalten.", parent=top)
            return
        index = aktuelle_delete_where["index"]
        if not messagebox.askyesno("DELETE-WHERE löschen", f"Bedingung {index + 1} wirklich löschen?", parent=top):
            return
        del delete_where_bedingungen[index]
        aktuelle_delete_where["index"] = max(0, min(index, len(delete_where_bedingungen) - 1))
        delete_where_auswahlwerte_aktualisieren()
        delete_where_widgetwerte_laden(aktuelle_delete_where["index"])

    def delete_feldname_bereinigen(feldname):
        feldname = (feldname or "").strip()
        if "." in feldname:
            feldname = feldname.rsplit(".", 1)[1].strip()
        return feldname

    def delete_in_statement_einfuegen():
        delete_where_widgetwerte_speichern()
        tabelle = delete_tabelle.get().strip()
        if not tabelle:
            messagebox.showwarning("DELETE einfügen", "Bitte zuerst eine DELETE-Tabelle auswählen.", parent=top)
            return
        where_teile = []
        for i, eintrag in enumerate(delete_where_bedingungen):
            links = delete_feldname_bereinigen(eintrag.get("links", ""))
            operator = eintrag.get("operator", "=").strip() or "="
            wert = eintrag.get("wert", "").strip()
            verknuepfung = eintrag.get("verknuepfung", "WHERE").strip() or ("WHERE" if i == 0 else "AND")
            if not links:
                continue
            wert_sql = where_wert_sql_formatieren(operator, wert)
            if wert_sql:
                where_teile.append(f"{verknuepfung} {sql_identifier(links)} {operator} {wert_sql}")
            else:
                where_teile.append(f"{verknuepfung} {sql_identifier(links)} {operator}")
        if not where_teile:
            messagebox.showwarning(
                "DELETE einfügen",
                "Bitte mindestens eine WHERE-Bedingung angeben.\n\nAus Sicherheitsgründen wird kein DELETE ohne WHERE erzeugt.",
                parent=top
            )
            return
        snippet = f"DELETE FROM {sql_identifier(tabelle)}\n" + "\n".join(where_teile)
        aktueller_text = editor.get("1.0", "end-1c")
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            snippet = "\n" + snippet
        editor.insert("insert", snippet + "\n")
        editor.focus_force()
        debug_log(f"SQL-DELETE in Statement eingefuegt: tabelle={tabelle}, where={len(where_teile)}", "allgemein")

    def insert_felder_aktualisieren(event=None):
        feldliste = qualifizierte_felder_fuer_tabelle(insert_tabelle.get())
        combobox_wertliste_setzen(insert_feld, feldliste, insert_feld.get().strip())

    def insert_auswahlwerte_aktualisieren():
        werte = [f"Wert {i + 1}" for i in range(len(insert_werte))]
        insert_auswahl["values"] = werte
        index = max(0, min(aktuelle_insert_zeile["index"], len(werte) - 1))
        aktuelle_insert_zeile["index"] = index
        insert_auswahl.set(werte[index])

    def insert_widgetwerte_speichern():
        index = aktuelle_insert_zeile["index"]
        insert_werte[index]["feld"] = insert_feld.get().strip()
        insert_werte[index]["wert"] = insert_wert.get().strip()

    def insert_widgetwerte_laden(index):
        daten = insert_werte[index]
        insert_felder_aktualisieren()
        set_entry(insert_feld, daten.get("feld", ""))
        set_entry(insert_wert, daten.get("wert", ""))
        insert_status.config(text=f"Bearbeitet wird Wert {index + 1} von {len(insert_werte)}.")

    def insert_auswahl_gewechselt(event=None):
        insert_widgetwerte_speichern()
        try:
            index = int(insert_auswahl.get().replace("Wert", "").strip()) - 1
        except Exception:
            index = 0
        aktuelle_insert_zeile["index"] = max(0, min(index, len(insert_werte) - 1))
        insert_widgetwerte_laden(aktuelle_insert_zeile["index"])

    def insert_neu():
        insert_widgetwerte_speichern()
        insert_werte.append({"feld": "", "wert": ""})
        aktuelle_insert_zeile["index"] = len(insert_werte) - 1
        insert_auswahlwerte_aktualisieren()
        insert_widgetwerte_laden(aktuelle_insert_zeile["index"])

    def insert_loeschen():
        if len(insert_werte) <= 1:
            messagebox.showwarning("INSERT-Wert löschen", "Mindestens eine INSERT-Zeile bleibt erhalten.", parent=top)
            return
        index = aktuelle_insert_zeile["index"]
        if not messagebox.askyesno("INSERT-Wert löschen", f"Wert {index + 1} wirklich löschen?", parent=top):
            return
        del insert_werte[index]
        aktuelle_insert_zeile["index"] = max(0, min(index, len(insert_werte) - 1))
        insert_auswahlwerte_aktualisieren()
        insert_widgetwerte_laden(aktuelle_insert_zeile["index"])

    def insert_feldname_bereinigen(feldname):
        feldname = (feldname or "").strip()
        if "." in feldname:
            feldname = feldname.rsplit(".", 1)[1].strip()
        return feldname

    def insert_in_statement_einfuegen():
        insert_widgetwerte_speichern()
        tabelle = insert_tabelle.get().strip()
        if not tabelle:
            messagebox.showwarning("INSERT einfügen", "Bitte zuerst eine INSERT-Tabelle auswählen.", parent=top)
            return
        felder = []
        werte = []
        for eintrag in insert_werte:
            feld = insert_feldname_bereinigen(eintrag.get("feld", ""))
            wert = eintrag.get("wert", "").strip()
            if feld:
                felder.append(sql_identifier(feld))
                werte.append(where_wert_sql_formatieren("=", wert))
        if not felder:
            messagebox.showwarning("INSERT einfügen", "Bitte mindestens ein INSERT-Feld angeben.", parent=top)
            return
        snippet = (
            f"INSERT INTO {sql_identifier(tabelle)} ("
            + ", ".join(felder)
            + ")\nVALUES ("
            + ", ".join(werte)
            + ")"
        )
        aktueller_text = editor.get("1.0", "end-1c")
        if aktueller_text and not aktueller_text.endswith(("\n", " ")):
            snippet = "\n" + snippet
        editor.insert("insert", snippet + "\n")
        editor.focus_force()
        debug_log(f"SQL-INSERT in Statement eingefuegt: tabelle={tabelle}, werte={len(felder)}", "allgemein")

    def tabellen_liste_fuellen():
        tree_tab.delete(*tree_tab.get_children())
        tabellen = tabellen_laden()
        for t in tabellen:
            tree_tab.insert("", "end", values=(t,))
        join_values = [""] + list(tabellen)
        select_from_tabelle["values"] = join_values
        b_tab["values"] = join_values
        b_links_tab["values"] = join_values
        b_rechts_tab["values"] = join_values
        w_tab["values"] = join_values
        order_by_tab["values"] = join_values
        update_tabelle["values"] = join_values
        delete_tabelle["values"] = join_values
        insert_tabelle["values"] = join_values
        try:
            tab_ref["alle"] = [(t,) for t in tabellen]
        except NameError:
            pass

    def tabellenlisten_nach_systemtabellen_aenderung_aktualisieren(zu_selektierende_tabelle=G_TABELLE_PROJEKTE):
        try:
            tabellen_dropdown_aktualisieren(zu_selektierende_tabelle)
        except Exception as e:
            debug_log(f"Haupt-Tabellenliste konnte nicht aktualisiert werden: fehler={e}", "allgemein")
        try:
            tabellen_liste_fuellen()
        except Exception as e:
            debug_log(f"SQL-Tabellenliste konnte nicht aktualisiert werden: fehler={e}", "allgemein")

    def schema_update_und_tabellen_aktualisieren():
        if sql_abfragen_schema_update_ausfuehren(top):
            tabellenlisten_nach_systemtabellen_aenderung_aktualisieren(G_TABELLE_PROJEKTE)

    def gespeicherte_fuellen():
        tree_saved.delete(*tree_saved.get_children())
        daten_cache.clear()
        for row in sql_abfragen_laden():
            if len(row) >= 15:
                daten_cache[str(row[0])] = row
                tree_saved.insert("", "end", values=(row[0], row[1]))

    gespeicherter_zustand = {"wert": None}
    tree_saved_status = {"lade_aktiv": False, "letzter_name": None}

    def tree_saved_name_markieren(name):
        vorher_lade_aktiv = tree_saved_status.get("lade_aktiv", False)
        tree_saved_status["lade_aktiv"] = True
        try:
            tree_saved.selection_remove(tree_saved.selection())
            if not name:
                return
            for item_id in tree_saved.get_children():
                values = tree_saved.item(item_id, "values")
                if values and str(values[0]) == str(name):
                    tree_saved.selection_set(item_id)
                    tree_saved.focus(item_id)
                    tree_saved.see(item_id)
                    return
        except Exception:
            pass
        finally:
            tree_saved_status["lade_aktiv"] = vorher_lade_aktiv

    def tree_saved_auswahl_wiederherstellen():
        tree_saved_name_markieren(tree_saved_status.get("letzter_name"))

    def aktueller_zustand_erfassen():
        beziehung_widgetwerte_speichern()
        where_widgetwerte_speichern()
        order_by_widgetwerte_speichern()
        update_set_widgetwerte_speichern()
        update_where_widgetwerte_speichern()
        delete_where_widgetwerte_speichern()
        insert_widgetwerte_speichern()
        return {
            "name": entry_name.get().strip(),
            "ziel_tabelle": entry_ziel.get().strip(),
            "sql_text": editor.get("1.0", "end").strip(),
            "beziehungen": json.dumps(beziehungen, ensure_ascii=False, sort_keys=True),
            "where_bedingungen": json.dumps(where_bedingungen, ensure_ascii=False, sort_keys=True),
            "order_by_zeilen": json.dumps(order_by_zeilen, ensure_ascii=False, sort_keys=True),
            "update_tabelle": update_tabelle.get().strip(),
            "update_sets": json.dumps(update_sets, ensure_ascii=False, sort_keys=True),
            "update_where_bedingungen": json.dumps(update_where_bedingungen, ensure_ascii=False, sort_keys=True),
            "delete_tabelle": delete_tabelle.get().strip(),
            "delete_where_bedingungen": json.dumps(delete_where_bedingungen, ensure_ascii=False, sort_keys=True),
            "insert_tabelle": insert_tabelle.get().strip(),
            "insert_werte": json.dumps(insert_werte, ensure_ascii=False, sort_keys=True),
        }

    def gespeicherten_zustand_merken():
        gespeicherter_zustand["wert"] = aktueller_zustand_erfassen()

    def hat_ungespeicherte_aenderungen():
        letzter_zustand = gespeicherter_zustand.get("wert")
        if letzter_zustand is None:
            letzter_zustand = {
                "name": "",
                "ziel_tabelle": "",
                "sql_text": "",
                "beziehungen": json.dumps([
                    {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
                    {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
                    {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
                ], ensure_ascii=False, sort_keys=True),
                "where_bedingungen": json.dumps([
                    {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
                ], ensure_ascii=False, sort_keys=True),
                "order_by_zeilen": json.dumps([
                    {"feld": "", "richtung": "ASC"},
                ], ensure_ascii=False, sort_keys=True),
                "update_tabelle": "",
                "update_sets": json.dumps([
                    {"feld": "", "wert": ""},
                ], ensure_ascii=False, sort_keys=True),
                "update_where_bedingungen": json.dumps([
                    {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
                ], ensure_ascii=False, sort_keys=True),
                "delete_tabelle": "",
                "delete_where_bedingungen": json.dumps([
                    {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
                ], ensure_ascii=False, sort_keys=True),
                "insert_tabelle": "",
                "insert_werte": json.dumps([
                    {"feld": "", "wert": ""},
                ], ensure_ascii=False, sort_keys=True),
            }
        return aktueller_zustand_erfassen() != letzter_zustand

    global _hat_ungespeicherte_aenderungen_func
    _hat_ungespeicherte_aenderungen_func = hat_ungespeicherte_aenderungen

    def projektliste_fuellen():
        try:
            mit_status = projekte_laden_mit_status()
        except Exception as e:
            debug_log(f"Projektliste konnte nicht geladen werden: fehler={e}", "allgemein")
            mit_status = []
        projekt_namen[:] = [name for name, _ in mit_status]
        tree_projekte.delete(*tree_projekte.get_children())
        for name, aktiv in mit_status:
            status_text = "✔ aktiv" if aktiv else "nicht aktiv"
            tree_projekte.insert("", "end", values=(name, status_text))

    def sql_builder_auf_leeren_projektzustand_setzen(projektname):
        projekt_name_anzeige.set(projektname)
        entry_name.delete(0, "end")
        entry_name.insert(0, projektname)
        entry_ziel.delete(0, "end")

        beziehungen.clear()
        beziehungen.append({"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""})
        where_bedingungen.clear()
        where_bedingungen.append({"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""})
        order_by_zeilen.clear()
        order_by_zeilen.append({"feld": "", "richtung": "ASC"})
        update_sets.clear()
        update_sets.append({"feld": "", "wert": ""})
        update_where_bedingungen.clear()
        update_where_bedingungen.append({"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""})
        delete_where_bedingungen.clear()
        delete_where_bedingungen.append({"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""})
        insert_werte.clear()
        insert_werte.append({"feld": "", "wert": ""})

        update_tabelle.set("")
        delete_tabelle.set("")
        insert_tabelle.set("")
        editor.delete("1.0", "end")

        aktuelle_beziehung["index"] = 0
        beziehung_auswahlwerte_aktualisieren()
        beziehung_widgetwerte_laden(0)
        aktuelle_where_bedingung["index"] = 0
        where_auswahlwerte_aktualisieren()
        where_widgetwerte_laden(0)
        aktuelle_order_by["index"] = 0
        order_by_auswahlwerte_aktualisieren()
        order_by_widgetwerte_laden(0)
        aktuelle_update_set["index"] = 0
        update_set_auswahlwerte_aktualisieren()
        update_set_widgetwerte_laden(0)
        aktuelle_update_where["index"] = 0
        update_where_auswahlwerte_aktualisieren()
        update_where_widgetwerte_laden(0)
        aktuelle_delete_where["index"] = 0
        delete_where_auswahlwerte_aktualisieren()
        delete_where_widgetwerte_laden(0)
        aktuelle_insert_zeile["index"] = 0
        insert_auswahlwerte_aktualisieren()
        insert_widgetwerte_laden(0)
        try:
            builder_notebook.select(projekt_tab)
        except Exception:
            pass
        gespeicherten_zustand_merken()

    def projekt_neu():
        name = simpledialog.askstring("Projekt neu", "Name des neuen Projekts:", parent=top)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in projekt_namen:
            messagebox.showwarning("Projekt neu", f"Das Projekt '{name}' ist bereits vorhanden.", parent=top)
            return
        try:
            projekt_in_db_speichern(name)
            tabellenlisten_nach_systemtabellen_aenderung_aktualisieren(G_TABELLE_PROJEKTE)
        except Exception as e:
            messagebox.showerror("Projekt neu", f"Projekt konnte nicht gespeichert werden:\n{e}", parent=top)
            debug_log(f"Projekt konnte nicht angelegt werden: name={name}, fehler={e}", "allgemein")
            return
        projektliste_fuellen()
        for item_id in tree_projekte.get_children():
            values = tree_projekte.item(item_id, "values")
            if values and values[0] == name:
                tree_projekte.selection_set(item_id)
                tree_projekte.focus(item_id)
                tree_projekte.see(item_id)
                break
        projekt_status["aktuell"] = name
        _G_ausgewaehltes_projekt["name"] = name
        sql_builder_auf_leeren_projektzustand_setzen(name)
        workflow_fuellen(name)
        _on_projekt_ausgewaehlt_fuer_views(name)
        debug_log(f"Projekt angelegt: name={name}", "allgemein")

    def projekt_loeschen():
        auswahl = tree_projekte.selection()
        if not auswahl:
            return
        values = tree_projekte.item(auswahl[0], "values")
        if not values:
            return
        name = str(values[0])
        if not messagebox.askyesno("Projekt löschen", f"Soll das Projekt '{name}' gelöscht werden?", parent=top):
            return
        try:
            projekt_aus_db_loeschen(name)
            tabellenlisten_nach_systemtabellen_aenderung_aktualisieren(G_TABELLE_PROJEKTE)
        except Exception as e:
            messagebox.showerror("Projekt löschen", f"Projekt konnte nicht gelöscht werden:\n{e}", parent=top)
            debug_log(f"Projekt konnte nicht geloescht werden: name={name}, fehler={e}", "allgemein")
            return
        projektliste_fuellen()
        if projekt_status.get("aktuell") == name:
            projekt_status["aktuell"] = None
            _G_ausgewaehltes_projekt["name"] = None
            projekt_name_anzeige.set("")
        debug_log(f"Projekt geloescht: name={name}", "allgemein")

    def projekt_auswahl_gewechselt(event=None):
        auswahl = tree_projekte.selection()
        if not auswahl:
            return
        values = tree_projekte.item(auswahl[0], "values")
        if not values:
            return
        name = str(values[0])
        projekt_status["aktuell"] = name
        _G_ausgewaehltes_projekt["name"] = name
        # Checkbox-Status aus Tabelle lesen
        try:
            ist_aktiv = bool(aktives_projekt_laden() == name)
        except Exception:
            ist_aktiv = False
        aktiv_var.set(ist_aktiv)
        sql_builder_auf_leeren_projektzustand_setzen(name)
        workflow_fuellen(name)
        _on_projekt_ausgewaehlt_fuer_views(name)
        debug_log(f"Projekt ausgewaehlt: name={name}", "allgemein")

    def aktiv_toggle():
        name = projekt_status.get("aktuell")
        if not name:
            aktiv_var.set(False)
            return
        if aktiv_var.get():
            try:
                projekt_aktivieren(name)
                hauptfenster_projekt_modus_setzen(True, name)
                logging_eintrag_schreiben(f"Projekt aktiviert: {name}")
                projekt_fenster_oeffnen_und_positionieren(name)
            except Exception as e:
                messagebox.showerror("Projekt aktivieren", f"Fehler:\n{e}", parent=top)
                aktiv_var.set(False)
        else:
            try:
                projekt_deaktivieren()
                hauptfenster_projekt_modus_setzen(False)
                logging_eintrag_schreiben(f"Projekt deaktiviert: {name}")
            except Exception as e:
                messagebox.showerror("Projekt deaktivieren", f"Fehler:\n{e}", parent=top)
                aktiv_var.set(True)
        projektliste_fuellen()
        # Selektion wiederherstellen
        for item_id in tree_projekte.get_children():
            if tree_projekte.item(item_id, "values")[0] == name:
                tree_projekte.selection_set(item_id)
                tree_projekte.see(item_id)
                break

    def workflow_fuellen(projektname):
        tree_workflow.delete(*tree_workflow.get_children())
        if not projektname:
            return
        G_TABELLE_REL_WF = "zzz_Relationen"
        for eintrag_id, typ, name in workflow_laden(projektname):
            display = name
            if typ == "Kette":
                # ID → menschenlesbaren Namen auflösen
                try:
                    vb_wf = sqlite_verbindung_oeffnen()
                    r_wf = vb_wf.execute(
                        f"SELECT COALESCE(Bezeichnung, QuellTabelle || ' → ' || ZielTabelle) "
                        f"FROM {sql_identifier(G_TABELLE_REL_WF)} WHERE id=?",
                        (int(name),)
                    ).fetchone()
                    vb_wf.close()
                    if r_wf:
                        display = r_wf[0]
                except Exception:
                    pass
            tree_workflow.insert("", "end", iid=str(eintrag_id), values=(typ, display))

    def workflow_tabelle_auswaehlen():
        namen = tabellen_laden() if callable(tabellen_laden) else []
        if not namen:
            messagebox.showinfo("Tabelle hinzufügen", "Keine Tabellen verfügbar.", parent=top)
            return None
        dlg = tk.Toplevel(top)
        dlg.title("Tabelle auswählen")
        dlg.geometry("320x400")
        dlg.grab_set()
        dlg.transient(top)
        tk.Label(dlg, text="Tabelle auswählen:").pack(anchor="w", padx=8, pady=(8, 2))
        frame = tk.Frame(dlg)
        frame.pack(fill="both", expand=True, padx=8)
        lb = tk.Listbox(frame, selectmode="single")
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for n in sorted(namen, key=str.lower):
            lb.insert("end", n)
        ergebnis = [None]
        def bestaetigen(event=None):
            sel = lb.curselection()
            if sel:
                ergebnis[0] = lb.get(sel[0])
            dlg.destroy()
        tk.Button(dlg, text="OK", width=12, command=bestaetigen).pack(pady=8)
        lb.bind("<Double-1>", bestaetigen)
        dlg.wait_window()
        return ergebnis[0]

    def workflow_sql_auswaehlen():
        abfragen = gespeicherte_abfragen_laden()
        if not abfragen:
            messagebox.showinfo("SQL-Abfrage hinzufügen", "Keine gespeicherten Abfragen vorhanden.", parent=top)
            return None
        dlg = tk.Toplevel(top)
        dlg.title("SQL-Abfrage auswählen")
        dlg.geometry("380x400")
        dlg.grab_set()
        dlg.transient(top)
        tk.Label(dlg, text="Gespeicherte Abfrage auswählen:").pack(anchor="w", padx=8, pady=(8, 2))
        frame = tk.Frame(dlg)
        frame.pack(fill="both", expand=True, padx=8)
        lb = tk.Listbox(frame, selectmode="single")
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        id_liste = []
        for abfrage_id, name in abfragen:
            lb.insert("end", name)
            id_liste.append((abfrage_id, name))
        ergebnis = [None]
        def bestaetigen(event=None):
            sel = lb.curselection()
            if sel:
                ergebnis[0] = id_liste[sel[0]][1]
            dlg.destroy()
        tk.Button(dlg, text="OK", width=12, command=bestaetigen).pack(pady=8)
        lb.bind("<Double-1>", bestaetigen)
        dlg.wait_window()
        return ergebnis[0]

    def workflow_eintrag_hoch():
        auswahl = tree_workflow.selection()
        if not auswahl:
            return
        alle = list(tree_workflow.get_children())
        idx = alle.index(auswahl[0])
        if idx == 0:
            return
        alle[idx - 1], alle[idx] = alle[idx], alle[idx - 1]
        name = projekt_status.get("aktuell")
        if name:
            workflow_positionen_aktualisieren(name, [int(i) for i in alle])
        workflow_fuellen(name)
        tree_workflow.selection_set(auswahl[0])

    def workflow_eintrag_runter():
        auswahl = tree_workflow.selection()
        if not auswahl:
            return
        alle = list(tree_workflow.get_children())
        idx = alle.index(auswahl[0])
        if idx >= len(alle) - 1:
            return
        alle[idx], alle[idx + 1] = alle[idx + 1], alle[idx]
        name = projekt_status.get("aktuell")
        if name:
            workflow_positionen_aktualisieren(name, [int(i) for i in alle])
        workflow_fuellen(name)
        tree_workflow.selection_set(auswahl[0])

    def workflow_rechtsklick(event):
        item_id = tree_workflow.identify_row(event.y)
        if item_id:
            tree_workflow.selection_set(item_id)
        name = projekt_status.get("aktuell")
        menu = tk.Menu(top, tearoff=0)
        def tabelle_hinzufuegen():
            if not name:
                messagebox.showwarning("Tabelle hinzufügen", "Bitte zuerst ein Projekt auswählen.", parent=top)
                return
            tabellenname = workflow_tabelle_auswaehlen()
            if tabellenname:
                workflow_eintrag_hinzufuegen(name, "Tabelle", tabellenname)
                workflow_fuellen(name)
        def sql_hinzufuegen():
            if not name:
                messagebox.showwarning("SQL-Abfrage hinzufügen", "Bitte zuerst ein Projekt auswählen.", parent=top)
                return
            abfragename = workflow_sql_auswaehlen()
            if abfragename:
                workflow_eintrag_hinzufuegen(name, "SQL-Abfrage", abfragename)
                workflow_fuellen(name)
        def kette_hinzufuegen():
            if not name:
                messagebox.showwarning("Kette hinzufügen", "Bitte zuerst ein Projekt auswählen.", parent=top)
                return
            # Kette-Relationen des Projekts laden
            G_TABELLE_REL_K = "zzz_Relationen"
            try:
                vb_k = sqlite_verbindung_oeffnen()
                ketten = vb_k.execute(
                    f"SELECT id, COALESCE(Bezeichnung, QuellTabelle || ' → ' || ZielTabelle) "
                    f"FROM {sql_identifier(G_TABELLE_REL_K)} "
                    f"WHERE Projekt=? AND Typ='Kette' ORDER BY Reihenfolge, id",
                    (name,)
                ).fetchall()
                vb_k.close()
            except Exception:
                ketten = []
            if not ketten:
                messagebox.showinfo("Kette hinzufügen",
                                    "Keine Kettenbeziehungen für dieses Projekt definiert.\n\n"
                                    "Bitte zuerst unter Tabellenbeziehungen eine Kettenbeziehung anlegen.",
                                    parent=top)
                return
            # Auswahl-Dialog
            dlg_k = tk.Toplevel(top)
            dlg_k.title("Kette auswählen")
            dlg_k.geometry("360x300")
            dlg_k.grab_set()
            dlg_k.transient(top)
            tk.Label(dlg_k, text="Kettenbeziehung auswählen:").pack(anchor="w", padx=8, pady=(8, 2))
            frame_k = tk.Frame(dlg_k)
            frame_k.pack(fill="both", expand=True, padx=8)
            lb_k = tk.Listbox(frame_k, selectmode="single")
            sb_k = ttk.Scrollbar(frame_k, orient="vertical", command=lb_k.yview)
            lb_k.configure(yscrollcommand=sb_k.set)
            lb_k.pack(side="left", fill="both", expand=True)
            sb_k.pack(side="right", fill="y")
            id_liste = []
            for rel_id_k, bez_k in ketten:
                lb_k.insert("end", bez_k)
                id_liste.append(str(rel_id_k))
            ergebnis_k = [None]
            def bestaetigen_k(event=None):
                sel_k = lb_k.curselection()
                if sel_k:
                    ergebnis_k[0] = id_liste[sel_k[0]]
                    dlg_k.destroy()
            lb_k.bind("<Double-1>", bestaetigen_k)
            btn_k = tk.Frame(dlg_k)
            btn_k.pack(pady=6)
            tk.Button(btn_k, text="OK", width=10, command=bestaetigen_k).pack(side="left", padx=4)
            tk.Button(btn_k, text="Abbrechen", width=10, command=dlg_k.destroy).pack(side="left", padx=4)
            dlg_k.wait_window()
            if ergebnis_k[0]:
                workflow_eintrag_hinzufuegen(name, "Kette", ergebnis_k[0])
                workflow_fuellen(name)
        def eintrag_entfernen():
            auswahl = tree_workflow.selection()
            if not auswahl:
                return
            eintrag_id = int(auswahl[0])
            werte = tree_workflow.item(auswahl[0], "values")
            if not messagebox.askyesno("Eintrag entfernen", f"'{werte[0]}: {werte[1]}' aus dem Workflow entfernen?", parent=top):
                return
            workflow_eintrag_entfernen(eintrag_id)
            workflow_fuellen(name)
        menu.add_command(label="Tabelle hinzufügen",      command=tabelle_hinzufuegen)
        menu.add_command(label="SQL-Abfrage hinzufügen",  command=sql_hinzufuegen)
        menu.add_command(label="⛓  Kette hinzufügen",    command=kette_hinzufuegen)
        menu.add_separator()
        menu.add_command(label="Eintrag entfernen",       command=eintrag_entfernen)
        menu.add_separator()
        menu.add_command(label="↑  Hoch", command=workflow_eintrag_hoch)
        menu.add_command(label="↓  Runter", command=workflow_eintrag_runter)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree_workflow.bind("<Button-3>", workflow_rechtsklick)

    def workflow_abfrage_fenster_oeffnen(abfragename):
        return _workflow_abfrage_fenster_oeffnen_modul(abfragename)

    def workflow_doppelklick(event):
        auswahl = tree_workflow.selection()
        if not auswahl:
            return
        werte = tree_workflow.item(auswahl[0], "values")
        if not werte:
            return
        typ  = str(werte[0])
        pname_wf = projekt_status.get("aktuell") or ""
        # name aus dem Treeview ist bei Kette die display-form; wir brauchen die echte ID
        # → aus dem Workflow-Eintrag (iid = eintrag_id) holen
        eintrag_id = int(auswahl[0])
        wf_eintraege = workflow_laden(pname_wf)
        echt_name = str(werte[1])
        for _eid, _typ, _name in wf_eintraege:
            if _eid == eintrag_id:
                echt_name = _name
                break
        if typ == "Tabelle":
            tabellenfenster_oeffnen(echt_name)
        elif typ == "SQL-Abfrage":
            workflow_abfrage_fenster_oeffnen(echt_name)
        elif typ == "Kette":
            _workflow_ketten_fenster_oeffnen(echt_name, pname_wf)

    tree_workflow.bind("<Double-1>", workflow_doppelklick)

    def projekt_fenster_positionen_merken():
        projektname = projekt_status.get("aktuell")
        if not projektname:
            messagebox.showwarning("Position merken", "Kein Projekt ausgewählt.", parent=top)
            return
        eintraege = workflow_laden(projektname)
        anzahl = 0
        for _eid, typ, name in eintraege:
            fenster = None
            if typ == "Tabelle":
                fenster = tabellenfenster_holen(name)
            elif typ == "SQL-Abfrage":
                fenster = _workflow_offene_sql_fenster.get(name)
            elif typ == "Kette":
                fenster = _workflow_offene_ketten_fenster.get(name)
            if fenster:
                try:
                    _projekt_layout_speichern(projektname, f"{typ}|{name}", fenster.winfo_geometry())
                    anzahl += 1
                except Exception:
                    pass
        try:
            _projekt_layout_speichern(projektname, "Hauptfenster", root.winfo_geometry())
            _projekt_layout_speichern(projektname, "Hauptfenster_state", root.state())
            anzahl += 1
        except Exception:
            pass
        messagebox.showinfo("Position merken", f"Positionen gespeichert: {anzahl} Fenster.", parent=top)

    def gespeicherte_positionen_laden():
        projektname = projekt_status.get("aktuell")
        if not projektname:
            messagebox.showwarning("Positionen laden", "Kein Projekt ausgewählt.", parent=top)
            return
        # ignore_startview=True: immer Admin-Ansicht laden, Startview-Prüfung überspringen
        projekt_fenster_oeffnen_und_positionieren(projektname, ignore_startview=True)
        def _sql_editor_vorne():
            try:
                if top.winfo_exists():
                    top.lift()
            except Exception:
                pass
        top.after(1100, _sql_editor_vorne)

    # ── Views ────────────────────────────────────────────────────────────────
    tk.Label(projekt_tab, text="Views:", font=("Segoe UI", 9, "bold")).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(6, 2))

    _view_steuer_frame = tk.Frame(projekt_tab)
    _view_steuer_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 2))

    _view_var = tk.StringVar()
    _view_combo = ttk.Combobox(_view_steuer_frame, textvariable=_view_var,
                               state="readonly", width=28)
    _view_combo.pack(side="left", padx=(0, 6))

    def _view_liste_aktualisieren(setze_ersten=False):
        pname = _G_ausgewaehltes_projekt.get("name")
        namen = projekt_view_namen_lesen(pname) if pname else []
        _view_combo["values"] = namen
        if setze_ersten and namen:
            _view_var.set(namen[0])
        elif _view_var.get() not in namen:
            _view_var.set(namen[0] if namen else "")

    def _view_laden():
        pname = _G_ausgewaehltes_projekt.get("name")
        vname = _view_var.get()
        if not pname or not vname:
            messagebox.showwarning("View laden", "Kein Projekt oder keine View ausgewählt.", parent=top)
            return
        projekt_view_laden(pname, vname)
        # Nach dem Positionieren (1000 ms) SQL Editor wieder nach vorne holen,
        # damit er nicht von den neu geöffneten Tabellenfenstern verdeckt wird.
        def _sql_editor_vorne():
            try:
                if top.winfo_exists():
                    top.lift()
            except Exception:
                pass
        top.after(1100, _sql_editor_vorne)

    def _view_loeschen():
        pname = _G_ausgewaehltes_projekt.get("name")
        vname = _view_var.get()
        if not pname or not vname:
            return
        if not messagebox.askyesno("View löschen", f"View '{vname}' löschen?", parent=top):
            return
        projekt_view_loeschen(pname, vname)
        _view_liste_aktualisieren(setze_ersten=True)

    def _view_ueberschreiben():
        pname = _G_ausgewaehltes_projekt.get("name")
        vname = _view_var.get()
        if not pname or not vname:
            messagebox.showwarning("View speichern", "Kein Projekt oder keine View ausgewählt.", parent=top)
            return
        projekt_view_speichern(pname, vname)

    tk.Button(_view_steuer_frame, text="Laden",    command=_view_laden).pack(side="left", padx=(0, 4))
    tk.Button(_view_steuer_frame, text="Löschen",  command=_view_loeschen).pack(side="left", padx=(0, 4))
    tk.Button(_view_steuer_frame, text="Speichern", command=_view_ueberschreiben).pack(side="left")

    # Startview-Zeile (row=4)
    _startview_frame = tk.Frame(projekt_tab)
    _startview_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 2))

    _startview_anzeige_var = tk.StringVar(value="Admin View (Standard)")

    def _startview_anzeige_aktualisieren():
        pname = _G_ausgewaehltes_projekt.get("name")
        if pname:
            sv = projekt_startview_lesen(pname)
            _startview_anzeige_var.set(sv if sv else "Admin View (Standard)")
        else:
            _startview_anzeige_var.set("—")

    def _startview_setzen():
        pname = _G_ausgewaehltes_projekt.get("name")
        vname = _view_var.get()
        if not pname or not vname:
            messagebox.showwarning("Startview", "Kein Projekt oder keine View ausgewählt.", parent=top)
            return
        projekt_startview_setzen(pname, vname)
        _startview_anzeige_aktualisieren()

    def _startview_aufheben():
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            return
        projekt_startview_aufheben(pname)
        _startview_anzeige_aktualisieren()

    tk.Button(_startview_frame, text="Als Startview", command=_startview_setzen).pack(side="left", padx=(0, 4))
    tk.Button(_startview_frame, text="Aufheben",      command=_startview_aufheben).pack(side="left", padx=(0, 10))
    tk.Label(_startview_frame,  text="Startview:").pack(side="left", padx=(0, 4))
    tk.Label(_startview_frame,  textvariable=_startview_anzeige_var, foreground="#0055aa").pack(side="left")

    _view_neu_frame = tk.Frame(projekt_tab)
    _view_neu_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 4))
    tk.Label(_view_neu_frame, text="Name:").pack(side="left", padx=(0, 4))
    _view_name_var = tk.StringVar()
    _view_name_entry = tk.Entry(_view_neu_frame, textvariable=_view_name_var, width=28)
    _view_name_entry.pack(side="left", padx=(0, 6))

    def _view_speichern():
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            messagebox.showwarning("View speichern", "Kein Projekt ausgewählt.", parent=top)
            return
        vname = _view_name_var.get().strip()
        if not vname:
            vname = _naechste_view_nummer(pname)
            _view_name_var.set(vname)
        projekt_view_speichern(pname, vname)
        _view_liste_aktualisieren()
        _view_var.set(vname)
        # Nächste Nummer vorschlagen
        _view_name_var.set(_naechste_view_nummer(pname))

    tk.Button(_view_neu_frame, text="Aktuelle Fenster als View speichern",
              command=_view_speichern).pack(side="left")

    # View-Liste und Startview-Anzeige aktualisieren wenn Projekt-Auswahl wechselt
    def _on_projekt_ausgewaehlt_fuer_views(name):
        _view_name_var.set(_naechste_view_nummer(name) if name else "")
        _view_liste_aktualisieren(setze_ersten=True)
        _startview_anzeige_aktualisieren()
        try:
            _relationen_liste_aktualisieren()
        except NameError:
            pass  # noch nicht initialisiert

    # ── Tabellenbeziehungen ──────────────────────────────────────────────────
    _rel_header_frame = tk.Frame(projekt_tab)
    _rel_header_frame.grid(row=1, column=0, sticky="w", pady=(4, 2))
    tk.Label(_rel_header_frame, text="Tabellenbeziehungen:",
             font=("Segoe UI", 9, "bold")).pack(side="left")

    G_TABELLE_RELATIONEN_SQL = "zzz_Relationen"

    def _relationen_tabelle_sicherstellen():
        try:
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"""CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_RELATIONEN_SQL)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime TEXT NOT NULL,
                    Projekt TEXT NOT NULL,
                    Bezeichnung TEXT,
                    QuellTabelle TEXT NOT NULL,
                    QuellFeld TEXT NOT NULL,
                    ZielTabelle TEXT NOT NULL,
                    ZielFeld TEXT NOT NULL,
                    Typ TEXT DEFAULT '1:N',
                    Reihenfolge INTEGER DEFAULT 0)"""
            )
            # Migration: neue Spalten nachrüsten falls noch nicht vorhanden
            for _col_sql in [
                f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} ADD COLUMN Typ TEXT DEFAULT '1:N'",
                f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} ADD COLUMN Kette TEXT",
                f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} ADD COLUMN AnzeigenFelder TEXT",
                f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} ADD COLUMN QuellFelder TEXT",
                f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} ADD COLUMN IpSuchFeld TEXT",
            ]:
                try:
                    vb.execute(_col_sql)
                except Exception:
                    pass  # Spalte bereits vorhanden
            vb.commit()
            vb.close()
        except Exception:
            pass

    def _relationen_laden():
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname or not db_ist_geladen():
            return []
        try:
            _relationen_tabelle_sicherstellen()
            vb = sqlite_verbindung_oeffnen()
            rows = vb.execute(
                f"SELECT id, Bezeichnung, QuellTabelle, QuellFeld, ZielTabelle, ZielFeld, Typ, Kette, AnzeigenFelder, QuellFelder, IpSuchFeld "
                f"FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                f"WHERE Projekt=? ORDER BY Reihenfolge, id",
                (pname,)
            ).fetchall()
            vb.close()
            return rows
        except Exception:
            return []

    def _relationen_liste_aktualisieren():
        import json as _json
        rel_tree.delete(*rel_tree.get_children())
        for row in _relationen_laden():
            bez  = row[1] or ""
            typ  = row[6] or "1:N"
            kette_raw  = row[7]
            ip_suchfeld = row[10] if len(row) > 10 else None
            if kette_raw:
                try:
                    schritte = _json.loads(kette_raw)
                    kette_tabs = " → ".join(s["zu_tab"] for s in schritte)
                    pfeil = f"{row[2]}  →  {kette_tabs}"
                    typ = "Kette"
                except Exception:
                    pfeil = f"{row[2]}.{row[3]}  →  {row[4]}.{row[5]}"
            else:
                pfeil = f"{row[2]}.{row[3]}  →  {row[4]}.{row[5]}"
            if ip_suchfeld:
                pfeil += f"  🔍 {ip_suchfeld}"
            rel_tree.insert("", "end", iid=str(row[0]), values=(bez, typ, pfeil))

    rel_tree_frame = tk.Frame(projekt_tab)
    rel_tree_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 2), padx=(0, 4))
    rel_tree = ttk.Treeview(rel_tree_frame,
                            columns=("bezeichnung", "typ", "pfeil"),
                            show="headings", height=4)
    rel_tree.heading("bezeichnung", text="Bezeichnung", anchor="w", command=lambda: _tv_sortieren(rel_tree, "bezeichnung"))
    rel_tree.heading("typ", text="Typ", anchor="w", command=lambda: _tv_sortieren(rel_tree, "typ"))
    rel_tree.heading("pfeil", text="QuellTabelle.QuellFeld  →  ZielTabelle.ZielFeld", anchor="w", command=lambda: _tv_sortieren(rel_tree, "pfeil"))
    rel_tree.column("bezeichnung", width=130, anchor="w")
    rel_tree.column("typ", width=46, anchor="center")
    rel_tree.column("pfeil", width=360, anchor="w")
    rel_sb = ttk.Scrollbar(rel_tree_frame, orient="vertical", command=rel_tree.yview)
    rel_sb.pack(side="right", fill="y")
    rel_tree.pack(side="left", fill="both", expand=True)
    rel_tree.configure(yscrollcommand=rel_sb.set)

    def _relation_hinzufuegen():
        import re as _re
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            messagebox.showwarning("Beziehung hinzufügen", "Kein Projekt ausgewählt.", parent=top)
            return
        if not db_ist_geladen():
            messagebox.showwarning("Beziehung hinzufügen", "Keine Datenbank geladen.", parent=top)
            return
        _relationen_tabelle_sicherstellen()
        # Alle Tabellen der DB
        try:
            vb = sqlite_verbindung_oeffnen()
            alle_tabellen = [r[0] for r in vb.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            vb.close()
        except Exception:
            alle_tabellen = []

        dlg = tk.Toplevel(top)
        dlg.title("Tabellenbeziehung hinzufügen")
        dlg.geometry("500x310")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(top)
        dlg.columnconfigure(1, weight=1)

        def lbl(text, zeile):
            tk.Label(dlg, text=text, anchor="w").grid(
                row=zeile, column=0, sticky="w", padx=16, pady=(8, 2))

        def get_felder(tabellenname):
            if not tabellenname:
                return []
            try:
                vb = sqlite_verbindung_oeffnen()
                cols = [r[1] for r in vb.execute(
                    f"PRAGMA table_info({sql_identifier(tabellenname)})"
                ).fetchall()]
                vb.close()
                return cols
            except Exception:
                return []

        lbl("Bezeichnung (optional):", 0)
        bez_var = tk.StringVar()
        tk.Entry(dlg, textvariable=bez_var, width=44).grid(
            row=0, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Quelltabelle:", 1)
        qt_var = tk.StringVar()
        qt_cb = ttk.Combobox(dlg, textvariable=qt_var, values=alle_tabellen,
                              state="readonly", width=42)
        qt_cb.grid(row=1, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Quellfeld:", 2)
        qf_var = tk.StringVar()
        qf_cb = ttk.Combobox(dlg, textvariable=qf_var, state="readonly", width=42)
        qf_cb.grid(row=2, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Zieltabelle:", 3)
        zt_var = tk.StringVar()
        zt_cb = ttk.Combobox(dlg, textvariable=zt_var, values=alle_tabellen,
                              state="readonly", width=42)
        zt_cb.grid(row=3, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Zielfeld:", 4)
        zf_var = tk.StringVar()
        zf_cb = ttk.Combobox(dlg, textvariable=zf_var, state="readonly", width=42)
        zf_cb.grid(row=4, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Beziehungstyp:", 5)
        typ_var = tk.StringVar(value="1:N")
        typ_frame = tk.Frame(dlg)
        typ_frame.grid(row=5, column=1, sticky="w", padx=(0, 16), pady=(8, 2))
        for typ_wert, typ_hilfe in [
            ("1:1", "1 Quell-DS → 1 Ziel-DS   (ZielFeld = Schlüsselfeld in ZielTabelle)"),
            ("1:N", "1 Quell-DS → N Ziel-DS   (ZielFeld = FK-Spalte in ZielTabelle)"),
            ("N:1", "N Quell-DS → 1 Ziel-DS   (ZielFeld = Schlüsselfeld in ZielTabelle)"),
        ]:
            tk.Radiobutton(typ_frame, text=f"{typ_wert}  –  {typ_hilfe}",
                           variable=typ_var, value=typ_wert,
                           anchor="w").pack(anchor="w")

        def on_qt_selected(event=None):
            felder = get_felder(qt_var.get())
            qf_cb["values"] = felder
            qf_var.set(felder[0] if felder else "")
        def on_zt_selected(event=None):
            felder = get_felder(zt_var.get())
            zf_cb["values"] = felder
            zf_var.set(felder[0] if felder else "")
        qt_cb.bind("<<ComboboxSelected>>", on_qt_selected)
        zt_cb.bind("<<ComboboxSelected>>", on_zt_selected)

        ergebnis = [None]
        def bestaetigen(event=None):
            if not qt_var.get() or not qf_var.get() or not zt_var.get() or not zf_var.get():
                messagebox.showwarning("Beziehung hinzufügen",
                                       "Bitte alle Pflichtfelder ausfüllen.", parent=dlg)
                return
            ergebnis[0] = (bez_var.get().strip(), qt_var.get(), qf_var.get(),
                           zt_var.get(), zf_var.get(), typ_var.get())
            dlg.destroy()

        btn_f = tk.Frame(dlg)
        btn_f.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        tk.Button(btn_f, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 16))
        tk.Button(btn_f, text="Abbrechen", width=12, command=dlg.destroy).pack(side="right")
        dlg.bind("<Return>", bestaetigen)
        dlg.wait_window()

        if ergebnis[0] is None:
            return
        bez, qt, qf, zt, zf, typ = ergebnis[0]
        try:
            from datetime import datetime as _dt
            jetzt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"INSERT INTO {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                f"(datetime, Projekt, Bezeichnung, QuellTabelle, QuellFeld, ZielTabelle, ZielFeld, Typ) "
                f"VALUES (?,?,?,?,?,?,?,?)",
                (jetzt, pname, bez, qt, qf, zt, zf, typ)
            )
            vb.commit()
            vb.close()
            _relationen_liste_aktualisieren()
        except Exception as e:
            messagebox.showerror("Beziehung hinzufügen", f"Fehler:\n{e}", parent=top)

    def _relation_loeschen():
        sel = rel_tree.selection()
        if not sel:
            messagebox.showwarning("Beziehung löschen", "Bitte zuerst eine Beziehung auswählen.", parent=top)
            return
        rel_id = int(sel[0])
        if not messagebox.askyesno("Beziehung löschen",
                                   "Ausgewählte Beziehung wirklich löschen?", parent=top):
            return
        try:
            vb = sqlite_verbindung_oeffnen()
            vb.execute(f"DELETE FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?", (rel_id,))
            vb.commit()
            vb.close()
            _relationen_liste_aktualisieren()
        except Exception as e:
            messagebox.showerror("Beziehung löschen", f"Fehler:\n{e}", parent=top)

    def _relation_verschieben(richtung):
        """Verschiebt die gewählte Beziehung um einen Platz nach oben (-1) oder unten (+1)."""
        sel = rel_tree.selection()
        if not sel:
            return
        alle_iids = list(rel_tree.get_children())
        pos = alle_iids.index(sel[0])
        ziel_pos = pos + richtung
        if ziel_pos < 0 or ziel_pos >= len(alle_iids):
            return
        id_a = int(alle_iids[pos])
        id_b = int(alle_iids[ziel_pos])
        try:
            vb = sqlite_verbindung_oeffnen()
            # Aktuelle Reihenfolge-Werte lesen
            r_a = vb.execute(
                f"SELECT Reihenfolge FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?",
                (id_a,)).fetchone()
            r_b = vb.execute(
                f"SELECT Reihenfolge FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?",
                (id_b,)).fetchone()
            # Falls beide denselben Wert haben, temporär Positionsindex verwenden
            reihe_a = r_a[0] if r_a and r_a[0] is not None else pos
            reihe_b = r_b[0] if r_b and r_b[0] is not None else ziel_pos
            if reihe_a == reihe_b:
                reihe_a, reihe_b = pos, ziel_pos
            # Tauschen
            vb.execute(
                f"UPDATE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} SET Reihenfolge=? WHERE id=?",
                (reihe_b, id_a))
            vb.execute(
                f"UPDATE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} SET Reihenfolge=? WHERE id=?",
                (reihe_a, id_b))
            vb.commit()
            vb.close()
        except Exception as e:
            messagebox.showerror("Beziehung verschieben", f"Fehler:\n{e}", parent=top)
            return
        _relationen_liste_aktualisieren()
        # Selektion wiederherstellen (die verschobene Zeile wieder markieren)
        for iid in rel_tree.get_children():
            if int(iid) == id_a:
                rel_tree.selection_set(iid)
                rel_tree.see(iid)
                break

    def _relation_bearbeiten():
        sel = rel_tree.selection()
        if not sel:
            messagebox.showwarning("Beziehung bearbeiten",
                                   "Bitte zuerst eine Beziehung auswählen.", parent=top)
            return
        rel_id = int(sel[0])
        # Aktuelle Werte aus DB laden
        try:
            vb = sqlite_verbindung_oeffnen()
            row = vb.execute(
                f"SELECT Bezeichnung, QuellTabelle, QuellFeld, ZielTabelle, ZielFeld, Typ "
                f"FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?",
                (rel_id,)
            ).fetchone()
            alle_tabellen = [r[0] for r in vb.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            vb.close()
        except Exception as e:
            messagebox.showerror("Beziehung bearbeiten", f"Fehler beim Laden:\n{e}", parent=top)
            return
        if row is None:
            return
        alt_bez, alt_qt, alt_qf, alt_zt, alt_zf, alt_typ = row

        dlg = tk.Toplevel(top)
        dlg.title("Tabellenbeziehung bearbeiten")
        dlg.geometry("500x310")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(top)
        dlg.columnconfigure(1, weight=1)

        def lbl(text, zeile):
            tk.Label(dlg, text=text, anchor="w").grid(
                row=zeile, column=0, sticky="w", padx=16, pady=(8, 2))

        def get_felder(tabellenname):
            if not tabellenname:
                return []
            try:
                vb2 = sqlite_verbindung_oeffnen()
                cols = [r[1] for r in vb2.execute(
                    f"PRAGMA table_info({sql_identifier(tabellenname)})"
                ).fetchall()]
                vb2.close()
                return cols
            except Exception:
                return []

        lbl("Bezeichnung (optional):", 0)
        bez_var = tk.StringVar(value=alt_bez or "")
        tk.Entry(dlg, textvariable=bez_var, width=44).grid(
            row=0, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Quelltabelle:", 1)
        qt_var = tk.StringVar(value=alt_qt)
        qt_cb = ttk.Combobox(dlg, textvariable=qt_var, values=alle_tabellen,
                              state="readonly", width=42)
        qt_cb.grid(row=1, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Quellfeld:", 2)
        qf_var = tk.StringVar(value=alt_qf)
        qf_felder = get_felder(alt_qt)
        qf_cb = ttk.Combobox(dlg, textvariable=qf_var, values=qf_felder,
                              state="readonly", width=42)
        qf_cb.grid(row=2, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Zieltabelle:", 3)
        zt_var = tk.StringVar(value=alt_zt)
        zt_cb = ttk.Combobox(dlg, textvariable=zt_var, values=alle_tabellen,
                              state="readonly", width=42)
        zt_cb.grid(row=3, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Zielfeld:", 4)
        zf_var = tk.StringVar(value=alt_zf)
        zf_felder = get_felder(alt_zt)
        zf_cb = ttk.Combobox(dlg, textvariable=zf_var, values=zf_felder,
                              state="readonly", width=42)
        zf_cb.grid(row=4, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

        lbl("Beziehungstyp:", 5)
        typ_var = tk.StringVar(value=alt_typ or "1:N")
        typ_frame = tk.Frame(dlg)
        typ_frame.grid(row=5, column=1, sticky="w", padx=(0, 16), pady=(8, 2))
        for typ_wert, typ_hilfe in [
            ("1:1", "1 Quell-DS → 1 Ziel-DS   (ZielFeld = Schlüsselfeld in ZielTabelle)"),
            ("1:N", "1 Quell-DS → N Ziel-DS   (ZielFeld = FK-Spalte in ZielTabelle)"),
            ("N:1", "N Quell-DS → 1 Ziel-DS   (ZielFeld = Schlüsselfeld in ZielTabelle)"),
        ]:
            tk.Radiobutton(typ_frame, text=f"{typ_wert}  –  {typ_hilfe}",
                           variable=typ_var, value=typ_wert,
                           anchor="w").pack(anchor="w")

        def on_qt_selected(event=None):
            felder = get_felder(qt_var.get())
            qf_cb["values"] = felder
            qf_var.set(felder[0] if felder else "")
        def on_zt_selected(event=None):
            felder = get_felder(zt_var.get())
            zf_cb["values"] = felder
            zf_var.set(felder[0] if felder else "")
        qt_cb.bind("<<ComboboxSelected>>", on_qt_selected)
        zt_cb.bind("<<ComboboxSelected>>", on_zt_selected)

        ergebnis = [None]
        def bestaetigen(event=None):
            if not qt_var.get() or not qf_var.get() or not zt_var.get() or not zf_var.get():
                messagebox.showwarning("Beziehung bearbeiten",
                                       "Bitte alle Pflichtfelder ausfüllen.", parent=dlg)
                return
            ergebnis[0] = (bez_var.get().strip(), qt_var.get(), qf_var.get(),
                           zt_var.get(), zf_var.get(), typ_var.get())
            dlg.destroy()

        btn_f = tk.Frame(dlg)
        btn_f.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        tk.Button(btn_f, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 16))
        tk.Button(btn_f, text="Abbrechen", width=12, command=dlg.destroy).pack(side="right")
        dlg.bind("<Return>", bestaetigen)
        dlg.wait_window()

        if ergebnis[0] is None:
            return
        bez, qt, qf, zt, zf, typ = ergebnis[0]
        try:
            from datetime import datetime as _dt
            jetzt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            vb = sqlite_verbindung_oeffnen()
            vb.execute(
                f"UPDATE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                f"SET datetime=?, Bezeichnung=?, QuellTabelle=?, QuellFeld=?, "
                f"    ZielTabelle=?, ZielFeld=?, Typ=? "
                f"WHERE id=?",
                (jetzt, bez, qt, qf, zt, zf, typ, rel_id)
            )
            vb.commit()
            vb.close()
            _relationen_liste_aktualisieren()
        except Exception as e:
            messagebox.showerror("Beziehung bearbeiten", f"Fehler:\n{e}", parent=top)

    def _kettenbeziehung_dialog(rel_id=None):
        """Dialog zum Anlegen/Bearbeiten einer Kettenbeziehung (mehrere Tabellen-Hops)."""
        import json as _json

        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            messagebox.showwarning("Kettenbeziehung", "Kein Projekt ausgewählt.", parent=top)
            return
        if not db_ist_geladen():
            messagebox.showwarning("Kettenbeziehung", "Keine Datenbank geladen.", parent=top)
            return
        _relationen_tabelle_sicherstellen()

        try:
            vb = sqlite_verbindung_oeffnen()
            alle_tabellen = [r[0] for r in vb.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            vb.close()
        except Exception:
            alle_tabellen = []

        def get_felder(tab):
            if not tab:
                return []
            try:
                vb2 = sqlite_verbindung_oeffnen()
                cols = [r[1] for r in vb2.execute(
                    f"PRAGMA table_info({sql_identifier(tab)})"
                ).fetchall()]
                vb2.close()
                return cols
            except Exception:
                return []

        # Startwerte (für Bearbeiten)
        alt_bez, alt_qt, alt_qf, alt_kette, alt_felder, alt_quell_felder, alt_ip_suchfeld = \
            "", "", "", [], [], [], ""
        if rel_id is not None:
            try:
                vb = sqlite_verbindung_oeffnen()
                row = vb.execute(
                    f"SELECT Bezeichnung, QuellTabelle, QuellFeld, Kette, AnzeigenFelder, QuellFelder, IpSuchFeld "
                    f"FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?",
                    (rel_id,)
                ).fetchone()
                vb.close()
                if row:
                    alt_bez = row[0] or ""
                    alt_qt  = row[1] or ""
                    alt_qf  = row[2] or ""
                    try:
                        alt_kette = _json.loads(row[3]) if row[3] else []
                    except Exception:
                        alt_kette = []
                    alt_felder       = [f.strip() for f in (row[4] or "").split(",") if f.strip()]
                    alt_quell_felder = [f.strip() for f in (row[5] or "").split(",") if f.strip()]
                    alt_ip_suchfeld  = row[6] or ""
            except Exception:
                pass

        dlg = tk.Toplevel(top)
        dlg.title("Kettenbeziehung " + ("bearbeiten" if rel_id else "hinzufügen"))
        dlg.geometry("820x720")
        dlg.minsize(620, 540)
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.transient(top)
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(5, weight=2)   # Schritte-Bereich dehnt sich
        dlg.rowconfigure(8, weight=1)   # Felder-Bereich dehnt sich

        # ── Bezeichnung ──────────────────────────────────────────────────────
        f_bez = tk.Frame(dlg)
        f_bez.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        f_bez.columnconfigure(1, weight=1)
        tk.Label(f_bez, text="Bezeichnung:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        bez_var = tk.StringVar(value=alt_bez)
        tk.Entry(f_bez, textvariable=bez_var).grid(row=0, column=1, sticky="ew")

        # ── Quelltabelle + Quellfeld ──────────────────────────────────────────
        f_qt = tk.Frame(dlg)
        f_qt.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        f_qt.columnconfigure(1, weight=1)
        f_qt.columnconfigure(3, weight=1)
        tk.Label(f_qt, text="Quelltabelle:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        qt_var = tk.StringVar(value=alt_qt)
        qt_cb = ttk.Combobox(f_qt, textvariable=qt_var, values=alle_tabellen,
                             state="readonly", width=24)
        qt_cb.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        tk.Label(f_qt, text="Quellfeld (Join-Schlüssel):").grid(row=0, column=2, sticky="w", padx=(0, 4))
        qf_var = tk.StringVar(value=alt_qf)
        qf_cb = ttk.Combobox(f_qt, textvariable=qf_var, state="readonly", width=24)
        qf_cb.grid(row=0, column=3, sticky="ew")
        if alt_qt:
            qf_cb["values"] = get_felder(alt_qt)

        ttk.Separator(dlg, orient="horizontal").grid(
            row=2, column=0, sticky="ew", padx=8, pady=(8, 2))
        tk.Label(dlg, text="Schritte (Zwischen- und Zieltabellen):",
                 font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, sticky="w", padx=12, pady=(2, 0))
        tk.Button(dlg, text="+ Schritt hinzufügen",
                  command=lambda: _schritt_hinzufuegen()).grid(
            row=4, column=0, sticky="w", padx=12, pady=(2, 2))

        # ── Schritte (scrollbar) ──────────────────────────────────────────────
        steps_outer = tk.Frame(dlg, relief="sunken", bd=1)
        steps_outer.grid(row=5, column=0, sticky="nsew", padx=12, pady=2)
        steps_outer.columnconfigure(0, weight=1)
        steps_outer.rowconfigure(0, weight=1)
        steps_canvas = tk.Canvas(steps_outer, highlightthickness=0, height=180)
        steps_sb = ttk.Scrollbar(steps_outer, orient="vertical", command=steps_canvas.yview)
        steps_frame = tk.Frame(steps_canvas)
        steps_frame.bind("<Configure>", lambda e: steps_canvas.configure(
            scrollregion=steps_canvas.bbox("all")))
        steps_canvas.create_window((0, 0), window=steps_frame, anchor="nw")
        steps_canvas.configure(yscrollcommand=steps_sb.set)
        steps_sb.pack(side="right", fill="y")
        steps_canvas.pack(side="left", fill="both", expand=True)
        steps_frame.columnconfigure(1, weight=1)
        steps_frame.columnconfigure(3, weight=1)

        ttk.Separator(dlg, orient="horizontal").grid(
            row=6, column=0, sticky="ew", padx=8, pady=(6, 2))
        tk.Label(dlg, text="Anzuzeigende Felder je Schritt  (nichts markiert = alle Felder des Schritts):",
                 font=("Segoe UI", 9, "bold")).grid(
            row=7, column=0, sticky="w", padx=12, pady=(2, 0))

        # ── Felder-Auswahl: Quelltabelle (links) + Zieltabelle (rechts) ──────
        f_felder_both = tk.Frame(dlg)
        f_felder_both.grid(row=8, column=0, sticky="nsew", padx=12, pady=(2, 4))
        f_felder_both.columnconfigure(0, weight=1)
        f_felder_both.columnconfigure(1, weight=1)
        f_felder_both.rowconfigure(1, weight=1)

        # Linke Seite: Quelltabellen-Felder (oben angezeigt im Ketten-Fenster)
        quell_felder_lbl = tk.Label(f_felder_both,
            text="Quelltabelle — oben angezeigt:", anchor="w",
            font=("Segoe UI", 9, "italic"))
        quell_felder_lbl.grid(row=0, column=0, sticky="w", padx=(0, 4), pady=(0, 2))
        f_ql = tk.Frame(f_felder_both, relief="sunken", bd=1)
        f_ql.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        f_ql.columnconfigure(0, weight=1)
        f_ql.rowconfigure(0, weight=1)
        quell_felder_lb = tk.Listbox(f_ql, selectmode="multiple", height=5,
                                     exportselection=False)
        quell_felder_lb_sb = ttk.Scrollbar(f_ql, orient="vertical",
                                            command=quell_felder_lb.yview)
        quell_felder_lb.configure(yscrollcommand=quell_felder_lb_sb.set)
        quell_felder_lb_sb.pack(side="right", fill="y")
        quell_felder_lb.pack(side="left", fill="both", expand=True)

        # Rechte Seite: Felder des gewählten Schritts (per "Felder bearbeiten"-Radiobutton wählbar)
        felder_lbl = tk.Label(f_felder_both,
            text="Felder (Schritt auswählen):", anchor="w",
            font=("Segoe UI", 9, "italic"))
        felder_lbl.grid(row=0, column=1, sticky="w", padx=(4, 0), pady=(0, 2))
        f_zl = tk.Frame(f_felder_both, relief="sunken", bd=1)
        f_zl.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        f_zl.columnconfigure(0, weight=1)
        f_zl.rowconfigure(0, weight=1)
        felder_lb = tk.Listbox(f_zl, selectmode="multiple", height=5,
                               exportselection=False)
        felder_lb_sb = ttk.Scrollbar(f_zl, orient="vertical", command=felder_lb.yview)
        felder_lb.configure(yscrollcommand=felder_lb_sb.set)
        felder_lb_sb.pack(side="right", fill="y")
        felder_lb.pack(side="left", fill="both", expand=True)

        # ── IP-Suchfeld ───────────────────────────────────────────────────────
        # alt_ip_suchfeld kann "Feld" (alt) oder "Tabelle.Feld" (neu) sein
        _ip_init_tab, _ip_init_feld = "", ""
        if alt_ip_suchfeld:
            if "." in alt_ip_suchfeld:
                _ip_init_tab, _ip_init_feld = alt_ip_suchfeld.split(".", 1)
            else:
                # Altes Format: Feld gehörte zur letzten Tabelle
                _ip_init_feld = alt_ip_suchfeld
                _ip_init_tab  = (alt_kette[-1].get("zu_tab", "") if alt_kette else "")

        f_ip = tk.Frame(dlg)
        f_ip.grid(row=9, column=0, sticky="ew", padx=12, pady=(4, 2))
        f_ip.columnconfigure(3, weight=1)
        tk.Label(f_ip,
                 text="IP-Analyse-Feld  (optional – für 'Überschneidungen in Kette suchen'):",
                 anchor="w").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 2))

        # Zeile 1: Tabelle wählen
        tk.Label(f_ip, text="Tabelle:").grid(row=1, column=0, sticky="w", padx=(0, 4))
        ip_tab_var = tk.StringVar(value=_ip_init_tab)
        ip_tab_cb  = ttk.Combobox(f_ip, textvariable=ip_tab_var,
                                   state="readonly", width=24)
        ip_tab_cb.grid(row=1, column=1, sticky="w", padx=(0, 16))

        # Zeile 1: Feld wählen
        tk.Label(f_ip, text="Feld:").grid(row=1, column=2, sticky="w", padx=(0, 4))
        ip_suchfeld_var = tk.StringVar(value=_ip_init_feld)
        ip_suchfeld_cb  = ttk.Combobox(f_ip, textvariable=ip_suchfeld_var,
                                        state="readonly", width=24)
        ip_suchfeld_cb.grid(row=1, column=3, sticky="w")
        tk.Button(f_ip, text="✕", width=3,
                  command=lambda: (ip_tab_var.set(""), ip_suchfeld_var.set(""))).grid(
            row=1, column=4, sticky="w", padx=(6, 0))

        ip_suchfeld_info = tk.Label(f_ip,
            text="Welches Feld welcher Tabelle enthält IP-Adressen / Subnetze?",
            anchor="w", fg="#555555", font=("TkDefaultFont", 8))
        ip_suchfeld_info.grid(row=2, column=0, columnspan=5, sticky="w", pady=(2, 0))

        def _ip_tab_liste_aktualisieren(*_):
            """Aktualisiert die Tabellen-Auswahl im IP-Feld-Bereich
            (Quelltabelle + alle Schritt-Zieltabellen)."""
            tabs = []
            if qt_var.get():
                tabs.append(qt_var.get())
            for sd in schritte_data:
                t = sd["zu_tab_var"].get()
                if t and t not in tabs:
                    tabs.append(t)
            ip_tab_cb["values"] = tabs
            # Falls aktuelle Auswahl nicht mehr in der Liste: zurücksetzen
            if ip_tab_var.get() not in tabs:
                ip_tab_var.set(tabs[-1] if tabs else "")
                ip_suchfeld_var.set("")
            _ip_suchfeld_cb_aktualisieren()

        def _ip_suchfeld_cb_aktualisieren(*_):
            """Aktualisiert die verfügbaren Felder für das IP-Suchfeld-Dropdown
            (Felder der gewählten Tabelle)."""
            tab = ip_tab_var.get()
            felder = get_felder(tab) if tab else []
            ip_suchfeld_cb["values"] = [""] + felder
            if ip_suchfeld_var.get() not in felder:
                ip_suchfeld_var.set("")

        ip_tab_cb.bind("<<ComboboxSelected>>", _ip_suchfeld_cb_aktualisieren)

        # ── Buttons ───────────────────────────────────────────────────────────
        f_btn = tk.Frame(dlg)
        f_btn.grid(row=10, column=0, pady=(8, 12))
        tk.Button(f_btn, text="OK", width=12,
                  command=lambda: _bestaetigen()).pack(side="right", padx=(8, 12))
        tk.Button(f_btn, text="Abbrechen", width=12,
                  command=dlg.destroy).pack(side="right")

        # ── Schritte-Daten ────────────────────────────────────────────────────
        schritte_data = []
        # Index des Schritts, dessen Felder gerade in felder_lb angezeigt werden
        aktiver_felder_schritt = {"idx": -1}
        # Gemeinsame IntVar für Radiobuttons (welcher Schritt für Felder-Bearbeitung aktiv)
        felder_schritt_rbvar = tk.IntVar(value=-1)

        def _vorherige_tabelle(idx):
            return schritte_data[idx - 1]["zu_tab_var"].get() if idx > 0 else qt_var.get()

        def _speichere_felder_lb():
            """Speichert die aktuelle felder_lb-Selektion zurück in schritte_data[idx]['felder']."""
            idx = aktiver_felder_schritt["idx"]
            if 0 <= idx < len(schritte_data):
                alle = list(felder_lb.get(0, "end"))
                schritte_data[idx]["felder"] = [alle[j] for j in felder_lb.curselection()]

        def _schritt_felder_anzeigen(idx):
            """Zeigt die Felder des Schritts idx in felder_lb an.
            Speichert vorher den WIRKLICH bisher aktiven Schritt – aber nur wenn
            ein echter Wechsel stattfindet und felder_lb bereits befüllt ist.
            (Verhindert, dass beim Laden die gespeicherte Feldauswahl überschrieben wird.)"""
            alt_idx = aktiver_felder_schritt["idx"]
            # Nur speichern wenn wir zu einem ANDEREN Schritt wechseln
            # und felder_lb tatsächlich Einträge enthält (d.h. einen echten Zustand zeigt)
            if alt_idx != idx and 0 <= alt_idx < len(schritte_data) and felder_lb.size() > 0:
                alle = list(felder_lb.get(0, "end"))
                schritte_data[alt_idx]["felder"] = [alle[j] for j in felder_lb.curselection()]
            aktiver_felder_schritt["idx"] = idx
            felder_schritt_rbvar.set(idx)
            felder_lb.delete(0, "end")
            if 0 <= idx < len(schritte_data):
                sd = schritte_data[idx]
                tab = sd["zu_tab_var"].get()
                felder_lbl.config(
                    text=f"Schritt {idx+1} – '{tab}' – Felder (leer = alle):")
                for f in get_felder(tab):
                    felder_lb.insert("end", f)
                alle_f = list(felder_lb.get(0, "end"))
                for af in sd["felder"]:
                    if af in alle_f:
                        felder_lb.selection_set(alle_f.index(af))
            else:
                felder_lbl.config(text="Felder (Schritt auswählen):")

        def _refresh_felder_lb():
            """Zeigt felder_lb für den aktuellen Schritt (oder letzten falls ungültig)."""
            if not schritte_data:
                felder_lb.delete(0, "end")
                felder_lbl.config(text="Felder (kein Schritt vorhanden):")
                felder_schritt_rbvar.set(-1)
                aktiver_felder_schritt["idx"] = -1
                return
            idx = aktiver_felder_schritt["idx"]
            if idx < 0 or idx >= len(schritte_data):
                idx = len(schritte_data) - 1
            _schritt_felder_anzeigen(idx)

        def _quell_felder_listbox_aktualisieren():
            """Aktualisiert die Quelltabelle-Felder-Listbox."""
            qt = qt_var.get()
            quell_felder_lb.delete(0, "end")
            if qt:
                quell_felder_lbl.config(
                    text=f"Quelltabelle '{qt}' — oben angezeigt:")
                for f in get_felder(qt):
                    quell_felder_lb.insert("end", f)
                alle_f = list(quell_felder_lb.get(0, "end"))
                for af in alt_quell_felder:
                    if af in alle_f:
                        quell_felder_lb.selection_set(alle_f.index(af))
            else:
                quell_felder_lbl.config(text="Quelltabelle — oben angezeigt:")

        def _schritte_neu_zeichnen():
            for w in steps_frame.winfo_children():
                w.destroy()
            for i, sd in enumerate(schritte_data):
                _schritt_zeile_zeichnen(i, sd)
            _refresh_felder_lb()
            _ip_tab_liste_aktualisieren()

        def _schritt_zeile_zeichnen(i, sd):
            prev_tab    = _vorherige_tabelle(i)
            prev_felder = get_felder(prev_tab)

            row_f = tk.Frame(steps_frame, relief="groove", bd=1)
            row_f.grid(row=i, column=0, sticky="ew", padx=4, pady=3)

            # Zeile 0: Join-Felder
            tk.Label(row_f, text=f"{i+1}.", width=3, anchor="e").grid(row=0, column=0, padx=(2, 0))

            vf_cb = ttk.Combobox(row_f, textvariable=sd["von_feld_var"],
                                  values=prev_felder, state="readonly", width=16)
            vf_cb.grid(row=0, column=1, padx=(2, 2))
            if not sd["von_feld_var"].get() and prev_felder:
                sd["von_feld_var"].set(prev_felder[0])

            tk.Label(row_f, text="→").grid(row=0, column=2, padx=4)

            zt_cb = ttk.Combobox(row_f, textvariable=sd["zu_tab_var"],
                                  values=alle_tabellen, state="readonly", width=18)
            zt_cb.grid(row=0, column=3, padx=(0, 2))
            tk.Label(row_f, text="auf").grid(row=0, column=4, padx=4)

            zu_felder = get_felder(sd["zu_tab_var"].get())
            zf_cb = ttk.Combobox(row_f, textvariable=sd["zu_feld_var"],
                                  values=zu_felder, state="readonly", width=16)
            zf_cb.grid(row=0, column=5, padx=(0, 4))
            if not sd["zu_feld_var"].get() and zu_felder:
                sd["zu_feld_var"].set(zu_felder[0])

            typ_cb = ttk.Combobox(row_f, textvariable=sd["typ_var"],
                                   values=["1:1", "1:N", "N:1"],
                                   state="readonly", width=5)
            typ_cb.grid(row=0, column=6, padx=(0, 4))
            if not sd["typ_var"].get():
                sd["typ_var"].set("1:N")

            def _loeschen(idx=i):
                _speichere_felder_lb()
                schritte_data.pop(idx)
                if aktiver_felder_schritt["idx"] >= len(schritte_data):
                    aktiver_felder_schritt["idx"] = len(schritte_data) - 1
                _schritte_neu_zeichnen()

            def _hoch(idx=i):
                if idx > 0:
                    _speichere_felder_lb()
                    schritte_data[idx - 1], schritte_data[idx] = \
                        schritte_data[idx], schritte_data[idx - 1]
                    aktiver_felder_schritt["idx"] = idx - 1
                    _schritte_neu_zeichnen()

            def _runter(idx=i):
                if idx < len(schritte_data) - 1:
                    _speichere_felder_lb()
                    schritte_data[idx], schritte_data[idx + 1] = \
                        schritte_data[idx + 1], schritte_data[idx]
                    aktiver_felder_schritt["idx"] = idx + 1
                    _schritte_neu_zeichnen()

            tk.Button(row_f, text="✕", width=2, command=_loeschen).grid(row=0, column=7, padx=(0, 2))
            tk.Button(row_f, text="▲", width=2, command=_hoch).grid(row=0, column=8, padx=(0, 2))
            tk.Button(row_f, text="▼", width=2, command=_runter).grid(row=0, column=9, padx=(0, 4))

            # Zeile 1: Aktivieren-Checkbox + Felder-Radiobutton
            sub = tk.Frame(row_f)
            sub.grid(row=1, column=0, columnspan=8, sticky="w", padx=(22, 4), pady=(0, 4))
            tk.Checkbutton(sub, text="Im Ergebnis anzeigen",
                           variable=sd["aktiv_var"]).pack(side="left", padx=(0, 16))
            tk.Radiobutton(sub, text="Felder bearbeiten ▶",
                           variable=felder_schritt_rbvar, value=i,
                           command=lambda idx=i: _schritt_felder_anzeigen(idx)
                           ).pack(side="left")

            def on_zt_changed(event=None, sd=sd, idx=i):
                felder = get_felder(sd["zu_tab_var"].get())
                sd["zu_feld_var"].set(felder[0] if felder else "")
                sd["felder"] = []   # Feldauswahl zurücksetzen wenn Tabelle wechselt
                _schritte_neu_zeichnen()
            zt_cb.bind("<<ComboboxSelected>>", on_zt_changed)

        def _schritt_hinzufuegen(von_feld="", zu_tab="", zu_feld="", typ="1:N",
                                  aktiv=True, felder=None):
            sd = {
                "von_feld_var": tk.StringVar(value=von_feld),
                "zu_tab_var":   tk.StringVar(value=zu_tab),
                "zu_feld_var":  tk.StringVar(value=zu_feld),
                "typ_var":      tk.StringVar(value=typ),
                "aktiv_var":    tk.BooleanVar(value=aktiv),
                "felder":       list(felder) if felder else [],
            }
            schritte_data.append(sd)
            aktiver_felder_schritt["idx"] = len(schritte_data) - 1
            _schritte_neu_zeichnen()

        def _qt_changed(event=None):
            felder = get_felder(qt_var.get())
            qf_cb["values"] = felder
            qf_var.set(felder[0] if felder else "")
            _quell_felder_listbox_aktualisieren()
            _schritte_neu_zeichnen()
            _ip_tab_liste_aktualisieren()
        qt_cb.bind("<<ComboboxSelected>>", _qt_changed)

        def _bestaetigen():
            if not qt_var.get() or not qf_var.get():
                messagebox.showwarning("Kettenbeziehung",
                                       "Quelltabelle und Quellfeld sind Pflichtfelder.",
                                       parent=dlg)
                return
            if not schritte_data:
                messagebox.showwarning("Kettenbeziehung",
                                       "Bitte mindestens einen Schritt hinzufügen.",
                                       parent=dlg)
                return
            for i, sd in enumerate(schritte_data):
                if not sd["von_feld_var"].get() or not sd["zu_tab_var"].get() \
                        or not sd["zu_feld_var"].get():
                    messagebox.showwarning("Kettenbeziehung",
                                           f"Schritt {i+1}: Bitte alle Felder ausfüllen.",
                                           parent=dlg)
                    return
            # Aktuelle felder_lb-Selektion in schritte_data sichern
            _speichere_felder_lb()
            kette = _json.dumps([
                {"von_feld": sd["von_feld_var"].get(),
                 "zu_tab":   sd["zu_tab_var"].get(),
                 "zu_feld":  sd["zu_feld_var"].get(),
                 "typ":      sd["typ_var"].get(),
                 "aktiv":    sd["aktiv_var"].get(),
                 "felder":   sd["felder"]}
                for sd in schritte_data
            ])
            letzte_tab   = schritte_data[-1]["zu_tab_var"].get()
            letztes_zu   = schritte_data[-1]["zu_feld_var"].get()
            # AnzeigenFelder: letzter aktiver Schritt (für Rückwärtskompatibilität)
            aktive_schritte = [sd for sd in schritte_data if sd["aktiv_var"].get()]
            letzter_aktiver = aktive_schritte[-1] if aktive_schritte else schritte_data[-1]
            anzeigen = ",".join(letzter_aktiver["felder"])
            sel_idx_q    = quell_felder_lb.curselection()
            quell_felder = ",".join(quell_felder_lb.get(i) for i in sel_idx_q)
            try:
                from datetime import datetime as _dt
                jetzt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                vb = sqlite_verbindung_oeffnen()
                _ip_tab_save  = ip_tab_var.get().strip()
                _ip_feld_save = ip_suchfeld_var.get().strip()
                ip_sf = f"{_ip_tab_save}.{_ip_feld_save}" \
                        if (_ip_tab_save and _ip_feld_save) else ""
                if rel_id is None:
                    vb.execute(
                        f"INSERT INTO {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                        f"(datetime, Projekt, Bezeichnung, QuellTabelle, QuellFeld, "
                        f"ZielTabelle, ZielFeld, Typ, Kette, AnzeigenFelder, QuellFelder, IpSuchFeld) "
                        f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (jetzt, pname, bez_var.get().strip(),
                         qt_var.get(), qf_var.get(),
                         letzte_tab, letztes_zu, "Kette", kette, anzeigen, quell_felder, ip_sf or None)
                    )
                else:
                    vb.execute(
                        f"UPDATE {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                        f"SET datetime=?, Bezeichnung=?, QuellTabelle=?, QuellFeld=?, "
                        f"ZielTabelle=?, ZielFeld=?, Typ=?, Kette=?, AnzeigenFelder=?, QuellFelder=?, IpSuchFeld=? "
                        f"WHERE id=?",
                        (jetzt, bez_var.get().strip(),
                         qt_var.get(), qf_var.get(),
                         letzte_tab, letztes_zu, "Kette", kette, anzeigen, quell_felder,
                         ip_sf or None, rel_id)
                    )
                vb.commit()
                vb.close()
                _relationen_liste_aktualisieren()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Kettenbeziehung", f"Fehler:\n{e}", parent=dlg)

        # Startschritte laden (für Bearbeiten) + Listboxen befüllen
        _quell_felder_listbox_aktualisieren()
        # Rückwärtskompatibilität: Hat kein Schritt ein "aktiv"-Feld?
        _any_has_aktiv = any("aktiv" in s for s in alt_kette)
        for _i_s, schritt in enumerate(alt_kette):
            _is_last = (_i_s == len(alt_kette) - 1)
            # Feldauswahl: neue Records aus "felder", alte Records: letzter Schritt aus alt_felder
            _step_felder = schritt.get("felder", [])
            if not _step_felder and _is_last and alt_felder and not _any_has_aktiv:
                _step_felder = alt_felder
            # Aktivierung: neue Records aus "aktiv", alte Records: nur letzten Schritt aktivieren
            _step_aktiv = schritt.get("aktiv", _is_last) if _any_has_aktiv else _is_last
            _schritt_hinzufuegen(
                von_feld=schritt.get("von_feld", ""),
                zu_tab=schritt.get("zu_tab", ""),
                zu_feld=schritt.get("zu_feld", ""),
                typ=schritt.get("typ", "1:N"),
                aktiv=_step_aktiv,
                felder=_step_felder,
            )
        if not alt_kette:
            _refresh_felder_lb()
        # Tabellen-Liste und Feld-Dropdown initialisieren
        _ip_tab_liste_aktualisieren()
        # IP-Tabelle und IP-Feld aus DB wiederherstellen
        if _ip_init_tab:
            ip_tab_var.set(_ip_init_tab)
        _ip_suchfeld_cb_aktualisieren()
        if _ip_init_feld and _ip_init_feld in (ip_suchfeld_cb["values"] or []):
            ip_suchfeld_var.set(_ip_init_feld)
        dlg.wait_window()

    def _relation_bearbeiten_auto():
        """Öffnet je nach Typ den passenden Bearbeiten-Dialog."""
        import json as _json
        sel = rel_tree.selection()
        if not sel:
            messagebox.showwarning("Beziehung bearbeiten",
                                   "Bitte zuerst eine Beziehung auswählen.", parent=top)
            return
        rel_id = int(sel[0])
        try:
            vb = sqlite_verbindung_oeffnen()
            row = vb.execute(
                f"SELECT Kette FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE id=?",
                (rel_id,)
            ).fetchone()
            vb.close()
            ist_kette = bool(row and row[0])
        except Exception:
            ist_kette = False
        if ist_kette:
            _kettenbeziehung_dialog(rel_id=rel_id)
        else:
            _relation_bearbeiten()


    def _fk_aus_db_importieren():
        """Liest PRAGMA foreign_key_list aller Tabellen und lässt den Nutzer
        FK-Constraints als Beziehungen in zzz_Relationen importieren."""
        import datetime as _dt
        pname = _G_ausgewaehltes_projekt.get("name")
        if not pname:
            messagebox.showwarning("FK importieren", "Kein Projekt ausgewählt.", parent=top)
            return
        if not db_ist_geladen():
            messagebox.showwarning("FK importieren", "Keine Datenbank geladen.", parent=top)
            return
        _relationen_tabelle_sicherstellen()

        # ── 1. Alle FKs aus der DB lesen ──────────────────────────────────
        try:
            vb = sqlite_verbindung_oeffnen()
            alle_tabellen = [r[0] for r in vb.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            fks_gefunden = []   # (quell_tab, quell_feld, ziel_tab, ziel_feld)
            for tab in alle_tabellen:
                try:
                    rows = vb.execute(f"PRAGMA foreign_key_list({sql_identifier(tab)})").fetchall()
                    for r in rows:
                        # r: id, seq, table, from, to, on_update, on_delete, match
                        fks_gefunden.append((tab, r[3], r[2], r[4]))
                except Exception:
                    pass
            # Bereits vorhandene Beziehungen für Duplikat-Markierung
            bereits = set()
            for row in vb.execute(
                f"SELECT QuellTabelle, QuellFeld, ZielTabelle, ZielFeld "
                f"FROM {sql_identifier(G_TABELLE_RELATIONEN_SQL)} WHERE Projekt=?",
                (pname,)
            ).fetchall():
                bereits.add((row[0], row[1], row[2], row[3]))
            vb.close()
        except Exception as e:
            messagebox.showerror("FK importieren", f"Fehler beim Lesen: {e}", parent=top)
            return

        if not fks_gefunden:
            messagebox.showinfo("FK importieren",
                "Keine FOREIGN KEY-Constraints in der Datenbank gefunden.\n\n"
                "Hinweis: SQLite erzwingt FKs nur wenn 'PRAGMA foreign_keys=ON' gesetzt ist,\n"
                "speichert aber die Definitionen in der CREATE TABLE-Anweisung.",
                parent=top)
            return

        # ── 2. Dialog ─────────────────────────────────────────────────────
        dlg = tk.Toplevel(top)
        dlg.title("FK-Constraints als Beziehungen importieren")
        dlg.geometry("780x460")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.transient(top)
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        # Info-Zeile
        tk.Label(dlg,
            text=f"Gefundene FK-Constraints  –  bereits vorhanden = grau  (Projekt: {pname})",
            anchor="w", font=("Segoe UI", 9)
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

        # Treeview
        tv_frm = tk.Frame(dlg)
        tv_frm.grid(row=1, column=0, sticky="nsew", padx=10, pady=2)
        tv_frm.columnconfigure(0, weight=1)
        tv_frm.rowconfigure(0, weight=1)
        tv = ttk.Treeview(tv_frm,
            columns=("quell_tab", "quell_feld", "ziel_tab", "ziel_feld", "status"),
            show="headings", selectmode="extended")
        tv.heading("quell_tab",   text="Quell-Tabelle",  anchor="w")
        tv.heading("quell_feld",  text="Quell-Feld",     anchor="w")
        tv.heading("ziel_tab",    text="Ziel-Tabelle",   anchor="w")
        tv.heading("ziel_feld",   text="Ziel-Feld",      anchor="w")
        tv.heading("status",      text="Status",         anchor="w")
        tv.column("quell_tab",  width=180, anchor="w")
        tv.column("quell_feld", width=120, anchor="w")
        tv.column("ziel_tab",   width=180, anchor="w")
        tv.column("ziel_feld",  width=120, anchor="w")
        tv.column("status",     width=100, anchor="w")
        tv.tag_configure("vorhanden", foreground="#888888")
        tv_sb = ttk.Scrollbar(tv_frm, orient="vertical", command=tv.yview)
        tv_sb.grid(row=0, column=1, sticky="ns")
        tv.grid(row=0, column=0, sticky="nsew")
        tv.configure(yscrollcommand=tv_sb.set)

        neu_iids = []
        for i, (qt, qf, zt, zf) in enumerate(fks_gefunden):
            ist_da = (qt, qf, zt, zf) in bereits
            tag    = ("vorhanden",) if ist_da else ()
            status = "bereits vorhanden" if ist_da else "neu"
            iid = tv.insert("", "end", values=(qt, qf, zt, zf, status), tags=tag)
            if not ist_da:
                neu_iids.append(iid)

        # Neue vorauswählen
        if neu_iids:
            tv.selection_set(neu_iids)

        # Bezeichnung-Prefix
        bez_frm = tk.Frame(dlg)
        bez_frm.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 2))
        tk.Label(bez_frm, text="Bezeichnung (optional, wird vor Tabellenpfad gestellt):").pack(side="left")
        bez_var = tk.StringVar()
        tk.Entry(bez_frm, textvariable=bez_var, width=30).pack(side="left", padx=(6, 0))

        # Typ
        typ_frm = tk.Frame(dlg)
        typ_frm.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 4))
        tk.Label(typ_frm, text="Typ:").pack(side="left")
        typ_var = tk.StringVar(value="1:N")
        for _t in ("1:1", "1:N", "N:M"):
            tk.Radiobutton(typ_frm, text=_t, variable=typ_var, value=_t).pack(side="left", padx=4)

        # Buttons
        btn_frm = tk.Frame(dlg)
        btn_frm.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

        def _alle_neu_auswaehlen():
            tv.selection_set(neu_iids)

        def _importieren():
            auswahl = tv.selection()
            if not auswahl:
                messagebox.showwarning("FK importieren", "Keine Einträge ausgewählt.", parent=dlg)
                return
            try:
                vb = sqlite_verbindung_oeffnen()
                now = _dt.datetime.now().isoformat(sep=" ", timespec="seconds")
                bez_prefix = bez_var.get().strip()
                typ = typ_var.get()
                n = 0
                for iid in auswahl:
                    vals = tv.item(iid, "values")
                    qt, qf, zt, zf = vals[0], vals[1], vals[2], vals[3]
                    bez = (f"{bez_prefix}: " if bez_prefix else "") + f"{qt}.{qf} → {zt}.{zf}"
                    vb.execute(
                        f"INSERT INTO {sql_identifier(G_TABELLE_RELATIONEN_SQL)} "
                        f"(datetime, Projekt, Bezeichnung, QuellTabelle, QuellFeld, "
                        f" ZielTabelle, ZielFeld, Typ) VALUES (?,?,?,?,?,?,?,?)",
                        (now, pname, bez, qt, qf, zt, zf, typ)
                    )
                    n += 1
                vb.commit()
                vb.close()
            except Exception as e:
                messagebox.showerror("FK importieren", f"Fehler beim Speichern: {e}", parent=dlg)
                return
            _relationen_liste_aktualisieren()
            dlg.destroy()
            messagebox.showinfo("FK importieren",
                f"{n} Beziehung(en) importiert.", parent=top)

        tk.Button(btn_frm, text="Alle Neuen auswählen", command=_alle_neu_auswaehlen).pack(side="left", padx=(0,8))
        tk.Button(btn_frm, text="Importieren", command=_importieren,
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(btn_frm, text="Abbrechen", command=dlg.destroy).pack(side="right")


    def _rel_tree_rechtsklick(event):
        item_id = rel_tree.identify_row(event.y)
        if item_id:
            rel_tree.selection_set(item_id)
        menu = tk.Menu(top, tearoff=0)
        menu.add_command(label="Einfache Beziehung hinzufügen",  command=_relation_hinzufuegen)
        menu.add_command(label="Kettenbeziehung hinzufügen",      command=_kettenbeziehung_dialog)
        menu.add_command(label="FK aus DB importieren …",          command=_fk_aus_db_importieren)
        menu.add_separator()
        menu.add_command(label="▲  Nach oben",                    command=lambda: _relation_verschieben(-1))
        menu.add_command(label="▼  Nach unten",                   command=lambda: _relation_verschieben(+1))
        menu.add_separator()
        menu.add_command(label="Beziehung bearbeiten",            command=_relation_bearbeiten_auto)
        menu.add_separator()
        menu.add_command(label="Beziehung löschen",               command=_relation_loeschen)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    rel_tree.bind("<Button-3>",  _rel_tree_rechtsklick)
    rel_tree.bind("<Alt-Up>",    lambda e: _relation_verschieben(-1))
    rel_tree.bind("<Alt-Down>",  lambda e: _relation_verschieben(+1))

    # ── Workflow ─────────────────────────────────────────────────────────────
    tk.Label(projekt_tab, text="Workflow:", font=("Segoe UI", 9, "bold")).grid(
        row=1, column=1, sticky="w", pady=(4, 2), padx=(4, 0))

    def breiten_anwenden():
        lb = max(80, liste_breite_var.get())
        eb = max(10, eingabe_breite_var.get())
        tb = max(10, tabellen_breite_var.get())
        fb = max(10, feld_breite_var.get())
        # Linkes Panel + Treeview-Spalten
        left.config(width=lb)
        tree_saved.column("name", width=max(40, int(lb * 0.6)))
        tree_saved.column("ziel", width=max(30, int(lb * 0.4)))
        tree_projekte.column("name", width=max(60, lb - 70))
        # Wert-Eingabefelder (Entry) aktualisieren
        for widget in (update_set_wert, update_where_wert, delete_where_wert, insert_wert, w_wert):
            try:
                widget.config(width=eb)
            except Exception:
                pass
        # Name/Zieltabelle-Entries
        for widget in name_ziel_entries:
            try:
                widget.config(width=eb)
            except Exception:
                pass
        # Tabellen-Comboboxen
        for widget in tabellen_combos:
            try:
                widget.config(width=tb)
            except Exception:
                pass
        # Feld-Comboboxen
        for widget in feld_combos:
            try:
                widget.config(width=fb)
            except Exception:
                pass
        # In Konfiguration speichern
        _sql_konfig_speichern("liste_breite", lb)
        _sql_konfig_speichern("eingabe_breite", eb)
        _sql_konfig_speichern("auswahl_breite", tb)
        _sql_konfig_speichern("feld_breite", fb)

    def projekt_rechtsklick(event):
        item_id = tree_projekte.identify_row(event.y)
        if item_id:
            tree_projekte.selection_set(item_id)
            tree_projekte.focus(item_id)
        menu = tk.Menu(top, tearoff=0)
        menu.add_command(label="Neu", command=projekt_neu)
        menu.add_command(label="Löschen", command=projekt_loeschen)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def projekt_speichern():
        name = entry_name.get().strip()
        if not name:
            messagebox.showwarning("Projekt speichern", "Bitte zuerst einen Projektnamen eingeben oder ein Projekt auswählen.", parent=top)
            return
        try:
            projekt_in_db_speichern(name)
            tabellenlisten_nach_systemtabellen_aenderung_aktualisieren(G_TABELLE_PROJEKTE)
        except Exception as e:
            messagebox.showerror("Projekt speichern", f"Projekt konnte nicht gespeichert werden:\n{e}", parent=top)
            debug_log(f"Projekt konnte nicht gespeichert werden: name={name}, fehler={e}", "allgemein")
            return
        projektliste_fuellen()
        projekt_status["aktuell"] = name
        _G_ausgewaehltes_projekt["name"] = name
        projekt_name_anzeige.set(name)
        messagebox.showinfo(
            "Projekt speichern",
            f"Projekt '{name}' wurde in {G_TABELLE_PROJEKTE} gespeichert.",
            parent=top,
        )
        debug_log(f"Projekt gespeichert: name={name}, tabelle={G_TABELLE_PROJEKTE}", "allgemein")

    def sql_ersten_befehl_erkennen(sql_text):
        text = (sql_text or "").strip()
        while text.startswith("--"):
            zeilen = text.splitlines()
            text = "\n".join(zeilen[1:]).strip() if len(zeilen) > 1 else ""
        if text.startswith("/*") and "*/" in text:
            text = text.split("*/", 1)[1].strip()
        return text.split(None, 1)[0].upper() if text else ""

    def builder_reiter_fuer_abfrage_waehlen(sql_text, update_tabelle_wert, update_sets_liste, update_where_liste, delete_tabelle_wert, delete_where_liste, insert_tabelle_wert, insert_werte_liste):
        befehl = sql_ersten_befehl_erkennen(sql_text)
        ziel_tab = select_tab
        ziel_name = "SELECT"

        if befehl == "UPDATE":
            ziel_tab = update_tab
            ziel_name = "UPDATE"
        elif befehl == "INSERT":
            ziel_tab = insert_tab
            ziel_name = "INSERT"
        elif befehl == "DELETE":
            ziel_tab = delete_tab
            ziel_name = "DELETE"
        elif befehl in ("SELECT", "WITH"):
            ziel_tab = select_tab
            ziel_name = "SELECT"
        else:
            update_hat_inhalt = bool(update_tabelle_wert) or any(
                eintrag.get("feld", "").strip() or eintrag.get("wert", "").strip()
                for eintrag in update_sets_liste
            ) or any(
                eintrag.get("links", "").strip() or eintrag.get("wert", "").strip()
                for eintrag in update_where_liste
            )
            insert_hat_inhalt = bool(insert_tabelle_wert) or any(
                eintrag.get("feld", "").strip() or eintrag.get("wert", "").strip()
                for eintrag in insert_werte_liste
            )
            delete_hat_inhalt = bool(delete_tabelle_wert) or any(
                eintrag.get("links", "").strip() or eintrag.get("wert", "").strip()
                for eintrag in delete_where_liste
            )
            if insert_hat_inhalt:
                ziel_tab = insert_tab
                ziel_name = "INSERT"
            elif delete_hat_inhalt:
                ziel_tab = delete_tab
                ziel_name = "DELETE"
            elif update_hat_inhalt:
                ziel_tab = update_tab
                ziel_name = "UPDATE"

        try:
            builder_notebook.select(ziel_tab)
            debug_log(f"SQL-Builder-Reiter automatisch gewaehlt: reiter={ziel_name}, befehl={befehl or 'unbekannt'}", "allgemein")
        except Exception as e:
            debug_log(f"SQL-Builder-Reiter konnte nicht automatisch gewaehlt werden: fehler={e}", "allgemein")

    def gespeicherte_laden(event=None):
        auswahl = tree_saved.selection()
        if not auswahl:
            return
        values = tree_saved.item(auswahl[0], "values")
        if not values:
            return
        name = str(values[0])
        row = daten_cache.get(name)
        if not row:
            return
        if hat_ungespeicherte_aenderungen():
            antwort = messagebox.askyesnocancel(
                "SQL-Abfrage laden",
                "Es gibt ungespeicherte Änderungen.\n\nSollen die Änderungen vor dem Laden gespeichert werden?",
                parent=top
            )
            if antwort is None:
                tree_saved_auswahl_wiederherstellen()
                return
            if antwort:
                if not speichern():
                    tree_saved_auswahl_wiederherstellen()
                    return
            else:
                debug_log("SQL-Abfrage wird trotz ungespeicherter Aenderungen neu geladen.", "allgemein")
        entry_name.delete(0, "end"); entry_name.insert(0, row[0])
        entry_ziel.delete(0, "end"); entry_ziel.insert(0, row[1])
        geladene_haupttabelle = row[31] if len(row) > 31 and row[31] else ""
        try:
            if geladene_haupttabelle:
                select_from_tabelle.set(geladene_haupttabelle)
            else:
                select_from_tabelle.set("")
        except Exception:
            pass
        geladene_beziehungen = []
        geladene_where = []
        geladene_update_sets = []
        geladene_update_where = []
        geladene_delete_where = []
        geladene_insert_werte = []
        try:
            if len(row) > 20 and row[20]:
                geladene_beziehungen = json.loads(row[20])
        except Exception:
            geladene_beziehungen = []
        try:
            if len(row) > 21 and row[21]:
                geladene_where = json.loads(row[21])
        except Exception:
            geladene_where = []
        geladene_update_tabelle = row[22] if len(row) > 22 and row[22] else ""
        try:
            if len(row) > 23 and row[23]:
                geladene_update_sets = json.loads(row[23])
        except Exception:
            geladene_update_sets = []
        try:
            if len(row) > 24 and row[24]:
                geladene_update_where = json.loads(row[24])
        except Exception:
            geladene_update_where = []
        geladene_delete_tabelle = row[25] if len(row) > 25 and row[25] else ""
        try:
            if len(row) > 26 and row[26]:
                geladene_delete_where = json.loads(row[26])
        except Exception:
            geladene_delete_where = []
        geladene_insert_tabelle = row[27] if len(row) > 27 and row[27] else ""
        try:
            if len(row) > 28 and row[28]:
                geladene_insert_werte = json.loads(row[28])
        except Exception:
            geladene_insert_werte = []
        geladene_order_by = []
        try:
            if len(row) > 29 and row[29]:
                geladene_order_by = json.loads(row[29])
        except Exception:
            geladene_order_by = []
        if not geladene_beziehungen:
            geladene_beziehungen = [
                {"typ": row[2] or "", "tabelle": row[3] or "", "links_tabelle": row[4] or "", "rechts_tabelle": row[5] or "", "links": row[6] or "", "rechts": row[7] or ""},
                {"typ": row[8] or "", "tabelle": row[9] or "", "links_tabelle": row[10] or "", "rechts_tabelle": row[11] or "", "links": row[12] or "", "rechts": row[13] or ""},
                {"typ": row[14] or "", "tabelle": row[15] or "", "links_tabelle": row[16] or "", "rechts_tabelle": row[17] or "", "links": row[18] or "", "rechts": row[19] or ""},
            ]
        if not geladene_beziehungen:
            geladene_beziehungen = [{"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""}]
        if not geladene_where:
            geladene_where = [{"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""}]
        if not geladene_update_sets:
            geladene_update_sets = [{"feld": "", "wert": ""}]
        if not geladene_update_where:
            geladene_update_where = [{"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""}]
        if not geladene_delete_where:
            geladene_delete_where = [{"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""}]
        if not geladene_insert_werte:
            geladene_insert_werte = [{"feld": "", "wert": ""}]
        if not geladene_order_by:
            geladene_order_by = [{"feld": "", "richtung": "ASC"}]
        beziehungen.clear()
        beziehungen.extend(geladene_beziehungen)
        where_bedingungen.clear()
        where_bedingungen.extend(geladene_where)
        order_by_zeilen.clear()
        order_by_zeilen.extend(geladene_order_by)
        update_sets.clear()
        update_sets.extend(geladene_update_sets)
        update_where_bedingungen.clear()
        update_where_bedingungen.extend(geladene_update_where)
        update_tabelle.set(geladene_update_tabelle)
        update_felder_aktualisieren()
        delete_where_bedingungen.clear()
        delete_where_bedingungen.extend(geladene_delete_where)
        delete_tabelle.set(geladene_delete_tabelle)
        delete_felder_aktualisieren()
        insert_werte.clear()
        insert_werte.extend(geladene_insert_werte)
        insert_tabelle.set(geladene_insert_tabelle)
        insert_felder_aktualisieren()
        aktuelle_beziehung["index"] = 0
        beziehung_auswahlwerte_aktualisieren()
        beziehung_widgetwerte_laden(0)
        aktuelle_where_bedingung["index"] = 0
        where_auswahlwerte_aktualisieren()
        where_widgetwerte_laden(0)
        aktuelle_order_by["index"] = 0
        order_by_auswahlwerte_aktualisieren()
        order_by_widgetwerte_laden(0)
        aktuelle_update_set["index"] = 0
        update_set_auswahlwerte_aktualisieren()
        update_set_widgetwerte_laden(0)
        aktuelle_update_where["index"] = 0
        update_where_auswahlwerte_aktualisieren()
        update_where_widgetwerte_laden(0)
        aktuelle_delete_where["index"] = 0
        delete_where_auswahlwerte_aktualisieren()
        delete_where_widgetwerte_laden(0)
        aktuelle_insert_zeile["index"] = 0
        insert_auswahlwerte_aktualisieren()
        insert_widgetwerte_laden(0)
        geladener_sql_text = row[30] if len(row) > 30 else ""
        editor.delete("1.0", "end"); editor.insert("1.0", geladener_sql_text)
        builder_reiter_fuer_abfrage_waehlen(
            geladener_sql_text,
            geladene_update_tabelle,
            geladene_update_sets,
            geladene_update_where,
            geladene_delete_tabelle,
            geladene_delete_where,
            geladene_insert_tabelle,
            geladene_insert_werte,
        )
        gespeicherten_zustand_merken()
        tree_saved_status["letzter_name"] = name
        tree_saved_name_markieren(name)
        debug_log(
            f"SQL-Abfrage geladen: name={row[0]}, update_sets={len(update_sets)}, update_where={len(update_where_bedingungen)}, delete_where={len(delete_where_bedingungen)}, insert_werte={len(insert_werte)}",
            "allgemein"
        )

    def gespeicherte_auswahl_gewechselt(event=None):
        if tree_saved_status.get("lade_aktiv"):
            return
        auswahl = tree_saved.selection()
        if not auswahl:
            return
        values = tree_saved.item(auswahl[0], "values")
        if not values:
            return
        name = str(values[0])
        if name == tree_saved_status.get("letzter_name") and not hat_ungespeicherte_aenderungen():
            return
        tree_saved_status["lade_aktiv"] = True
        try:
            gespeicherte_laden(event)
        finally:
            tree_saved_status["lade_aktiv"] = False

    def tabellen_auswahl(event=None):
        auswahl = tree_tab.selection()
        if not auswahl:
            return
        tname = tree_tab.item(auswahl[0], "values")[0]
        sql_fenster_felder_laden(tname, tree_fel)
        try:
            fel_ref["alle"] = [(tree_fel.item(iid, "values")[0],)
                               for iid in tree_fel.get_children()]
        except NameError:
            pass
        if not b_links_tab.get().strip():
            b_links_tab.set(tname)
            join_linke_felder_aktualisieren()
        if not w_tab.get().strip():
            w_tab.set(tname)
            where_felder_aktualisieren()
        if not update_tabelle.get().strip():
            update_tabelle.set(tname)
            update_felder_aktualisieren()
        if not delete_tabelle.get().strip():
            delete_tabelle.set(tname)
            delete_felder_aktualisieren()
        if not insert_tabelle.get().strip():
            insert_tabelle.set(tname)
            insert_felder_aktualisieren()

    def feld_einfuegen(event=None):
        auswahl = tree_fel.selection()
        if not auswahl:
            return
        feld = tree_fel.item(auswahl[0], "values")[0]
        aktueller_text = editor.get("1.0", "end").strip()
        sql_upper = " ".join(aktueller_text.upper().split())

        if not aktueller_text:
            # Noch gar nichts im Editor – SELECT automatisch setzen
            editor.delete("1.0", "end")
            editor.insert("1.0", f"SELECT {feld}, ")
        else:
            # Feld einfügen
            editor.insert("insert", feld + ", ")
            # Prüfen ob FROM fehlt und Tabellenname aus Feld extrahierbar
            aktueller_text = editor.get("1.0", "end").strip()
            sql_upper = " ".join(aktueller_text.upper().split())
            hat_from = " FROM " in f" {sql_upper} "
            if not hat_from and "." in feld:
                tabellenname = feld.split(".")[0]
                # FROM nach letztem Feld einfügen: am Ende der ersten Zeile
                editor.insert("end", f"\nFROM {tabellenname}\n")

        editor.focus_force()

    def select_from_einfuegen():
        """Setzt FROM <Haupttabelle> im Statement – analog zu update_in_statement_einfuegen."""
        tabellenname = select_from_tabelle.get().strip()
        if not tabellenname:
            messagebox.showwarning("Select FROM", "Bitte zuerst eine Haupttabelle auswählen.", parent=top)
            return
        aktueller_text = editor.get("1.0", "end").strip()
        sql_upper = " ".join(aktueller_text.upper().split())
        hat_from = " FROM " in f" {sql_upper} "
        hat_select = sql_upper.startswith("SELECT")

        if not aktueller_text:
            editor.insert("1.0", f"SELECT *\nFROM {tabellenname}\n")
        elif not hat_select:
            editor.insert("1.0", f"SELECT *\nFROM {tabellenname}\n")
        elif hat_from:
            # FROM ersetzen: alte FROM-Zeile suchen und ersetzen
            zeilen = editor.get("1.0", "end").splitlines()
            neue_zeilen = []
            ersetzt = False
            for zeile in zeilen:
                if not ersetzt and zeile.strip().upper().startswith("FROM"):
                    neue_zeilen.append(f"FROM {tabellenname}")
                    ersetzt = True
                else:
                    neue_zeilen.append(zeile)
            if not ersetzt:
                neue_zeilen.append(f"FROM {tabellenname}")
            editor.delete("1.0", "end")
            editor.insert("1.0", "\n".join(neue_zeilen))
        else:
            # SELECT vorhanden, kein FROM – nach SELECT-Zeile einfügen
            zeilen = editor.get("1.0", "end").splitlines()
            neue_zeilen = []
            eingefuegt = False
            for zeile in zeilen:
                neue_zeilen.append(zeile)
                if not eingefuegt and zeile.strip().upper().startswith("SELECT"):
                    neue_zeilen.append(f"FROM {tabellenname}")
                    eingefuegt = True
            if not eingefuegt:
                neue_zeilen.append(f"FROM {tabellenname}")
            editor.delete("1.0", "end")
            editor.insert("1.0", "\n".join(neue_zeilen))
        editor.focus_force()
        debug_log(f"Select FROM gesetzt: tabelle={tabellenname}", "allgemein")

    def funktion_in_statement_einfuegen(event=None):
        auswahl = tree_func.selection()
        if not auswahl:
            return
        values = tree_func.item(auswahl[0], "values")
        tags = tree_func.item(auswahl[0], "tags")
        if not values or not tags:
            return
        funktionsname = values[0]
        ausdruck = tags[0]
        # Feldname durch aktuell gewähltes Feld ersetzen falls vorhanden
        aktuelles_feld = None
        feld_auswahl = tree_fel.selection()
        if feld_auswahl:
            feld = tree_fel.item(feld_auswahl[0], "values")[0]
            tab_auswahl = tree_tab.selection()
            if tab_auswahl:
                tname = tree_tab.item(tab_auswahl[0], "values")[0]
                aktuelles_feld = f"{tname}.{feld}"
            else:
                aktuelles_feld = feld
        if aktuelles_feld:
            ausdruck = ausdruck.replace("Feldname", aktuelles_feld)
        editor.insert("insert", ausdruck + " ")
        editor.focus_force()
        debug_log(f"SQL-Funktion in Statement eingefuegt: funktion={funktionsname}, ausdruck={ausdruck}", "allgemein")

    def feld_in_where_links_einfuegen(event=None):
        auswahl = tree_fel.selection()
        if not auswahl:
            return
        feld = tree_fel.item(auswahl[0], "values")[0]
        aktuelle_tabellenwahl = tree_tab.selection()
        if aktuelle_tabellenwahl:
            tname = tree_tab.item(aktuelle_tabellenwahl[0], "values")[0]
            set_entry(w_tab, tname)
            where_felder_aktualisieren()
            feld = f"{tname}.{feld}"
        set_entry(w_links, feld)
        w_links.focus_force()

    def speichern():
        beziehung_widgetwerte_speichern()
        where_widgetwerte_speichern()
        order_by_widgetwerte_speichern()
        update_set_widgetwerte_speichern()
        update_where_widgetwerte_speichern()
        delete_where_widgetwerte_speichern()
        insert_widgetwerte_speichern()
        beziehung_fallback = {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""}
        b_save = list(beziehungen) + [beziehung_fallback, beziehung_fallback, beziehung_fallback]
        ok, meldung = sql_abfrage_direkt_speichern(
            entry_name.get().strip(),
            entry_ziel.get().strip(),
            editor.get("1.0", "end").strip(),
            b_save[0]["typ"], b_save[0]["tabelle"], b_save[0]["links"], b_save[0]["rechts"],
            b_save[1]["typ"], b_save[1]["tabelle"], b_save[1]["links"], b_save[1]["rechts"],
            b_save[2]["typ"], b_save[2]["tabelle"], b_save[2]["links"], b_save[2]["rechts"],
            beziehungen=beziehungen,
            where_bedingungen=where_bedingungen,
            update_tabelle=update_tabelle.get().strip(),
            update_sets=update_sets,
            update_where_bedingungen=update_where_bedingungen,
            delete_tabelle=delete_tabelle.get().strip(),
            delete_where_bedingungen=delete_where_bedingungen,
            insert_tabelle=insert_tabelle.get().strip(),
            insert_werte=insert_werte,
            order_by_zeilen=order_by_zeilen,
            haupttabelle=select_from_tabelle.get().strip(),
        )
        if ok:
            gespeicherte_fuellen()
            gespeicherten_zustand_merken()
            debug_log(
                f"SQL-Abfrage gespeichert: name={entry_name.get().strip()}, update_tabelle={update_tabelle.get().strip()}, update_sets={len(update_sets)}, update_where={len(update_where_bedingungen)}, delete_tabelle={delete_tabelle.get().strip()}, delete_where={len(delete_where_bedingungen)}, insert_tabelle={insert_tabelle.get().strip()}, insert_werte={len(insert_werte)}",
                "allgemein"
            )
            messagebox.showinfo("SQL speichern", meldung, parent=top)
            return True
        else:
            messagebox.showerror("SQL speichern", meldung, parent=top)
            return False

    def schliessen():
        if hat_ungespeicherte_aenderungen():
            antwort = messagebox.askyesnocancel(
                "SQL-Abfrage schließen",
                "Es gibt ungespeicherte Änderungen.\n\nSollen die Änderungen vor dem Schließen gespeichert werden?",
                parent=top
            )
            if antwort is None:
                return
            if antwort:
                ok = speichern()
                if not ok:
                    # Speichern fehlgeschlagen – nochmal fragen ob trotzdem schließen
                    if not messagebox.askyesno(
                        "SQL-Abfrage schließen",
                        "Die Abfrage konnte nicht gespeichert werden.\n\nTrotzdem schließen?",
                        parent=top
                    ):
                        return
            else:
                debug_log("SQL-Fenster wird mit ungespeicherten Aenderungen geschlossen.", "allgemein")
        top.destroy()

    global _speichern_func
    _speichern_func = speichern

    def pruefen():
        sql_text = editor.get("1.0", "end").strip()
        if not sql_text:
            messagebox.showwarning("SQL prüfen", "Bitte zuerst SQL-Text eingeben.", parent=top)
            return

        # Vorab-Prüfungen vor SQLite-Befragung
        sql_upper = " ".join(sql_text.upper().split())
        sql_typ = ""
        for _z in sql_text.splitlines():
            _zs = _z.strip()
            if _zs and not _zs.startswith("--"):
                sql_typ = _zs.split(None, 1)[0].upper()
                break

        if sql_typ == "SELECT":
            hat_from = " FROM " in f" {sql_upper} "
            hat_join = " JOIN " in f" {sql_upper} "
            hat_where = " WHERE " in f" {sql_upper} "
            if not hat_from and (hat_join or hat_where):
                messagebox.showwarning(
                    "SQL prüfen – FROM fehlt",
                    "Das SELECT-Statement enthält JOIN oder WHERE,\naber kein FROM.\n\n"
                    "Beispiel:\n  SELECT ... FROM <Haupttabelle>\n  INNER JOIN ...",
                    parent=top
                )
                return
            if not hat_from:
                messagebox.showwarning(
                    "SQL prüfen – FROM fehlt",
                    "Das SELECT-Statement hat kein FROM.\n\n"
                    "Beispiel:\n  SELECT ... FROM <Tabellenname>",
                    parent=top
                )
                return

        elif sql_typ == "UPDATE":
            if " SET " not in f" {sql_upper} ":
                messagebox.showwarning(
                    "SQL prüfen – SET fehlt",
                    "Das UPDATE-Statement hat kein SET.\n\n"
                    "Beispiel:\n  UPDATE <Tabelle> SET <Feld> = <Wert>",
                    parent=top
                )
                return
            if " WHERE " not in f" {sql_upper} ":
                if not messagebox.askyesno(
                    "SQL prüfen – WHERE fehlt",
                    "Das UPDATE-Statement hat keine WHERE-Bedingung.\n\n"
                    "Das kann alle Datensätze betreffen!\n\nTrotzdem prüfen?",
                    parent=top
                ):
                    return

        elif sql_typ == "DELETE":
            if " WHERE " not in f" {sql_upper} ":
                if not messagebox.askyesno(
                    "SQL prüfen – WHERE fehlt",
                    "Das DELETE-Statement hat keine WHERE-Bedingung.\n\n"
                    "Das kann alle Datensätze löschen!\n\nTrotzdem prüfen?",
                    parent=top
                ):
                    return

        elif sql_typ == "INSERT":
            if " INTO " not in f" {sql_upper} ":
                messagebox.showwarning(
                    "SQL prüfen – INTO fehlt",
                    "Das INSERT-Statement hat kein INTO.\n\n"
                    "Beispiel:\n  INSERT INTO <Tabelle> (...) VALUES (...)",
                    parent=top
                )
                return

        try:
            verbindung = sqlite_verbindung_mit_udf_oeffnen()
            cursor = verbindung.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql_text}")
            cursor.fetchall()
            verbindung.close()
            messagebox.showinfo("SQL prüfen", "Die SQL-Abfrage ist syntaktisch ausführbar.", parent=top)
        except Exception as e:
            messagebox.showerror("SQL prüfen", f"SQL konnte nicht geprüft werden:\n{e}", parent=top)

    def ausfuehren():
        sql_text = editor.get("1.0", "end").strip()
        if not sql_text:
            messagebox.showwarning("SQL ausführen", "Bitte zuerst SQL-Text eingeben.", parent=top)
            return

        # Tippfehler-Prüfung: "comit" → Warnung
        import re as _re_check
        if _re_check.search(r'\bcomit\b', sql_text, _re_check.IGNORECASE):
            messagebox.showwarning(
                "Tippfehler erkannt",
                "Im Statement wurde 'comit' gefunden.\n\nMeinten Sie 'COMMIT'?\n\nBitte korrigieren und erneut ausführen.",
                parent=top
            )
            return

        # BEGIN TRANSACTION / COMMIT automatisch entfernen
        zeilen_bereinigt = []
        entfernte = []
        for zeile in sql_text.splitlines():
            z_upper = zeile.strip().upper()
            if z_upper in ("BEGIN TRANSACTION", "BEGIN", "COMMIT", "COMMIT;", "BEGIN TRANSACTION;", "BEGIN;"):
                entfernte.append(zeile.strip())
            else:
                zeilen_bereinigt.append(zeile)
        if entfernte:
            sql_text = "\n".join(zeilen_bereinigt).strip()
            messagebox.showinfo(
                "Hinweis",
                f"Folgende Zeilen wurden automatisch entfernt,\nda der Code Transaktionen selbst verwaltet:\n\n"
                + "\n".join(entfernte),
                parent=top
            )
            if not sql_text:
                return
        sql_typ = ""
        for _z in sql_text.splitlines():
            _zs = _z.strip()
            if _zs and not _zs.startswith("--"):
                sql_typ = _zs.split(None, 1)[0].upper()
                break
        sql_text_normalisiert = " ".join(sql_text.upper().split())
        if sql_typ in ("UPDATE", "DELETE") and " WHERE " not in f" {sql_text_normalisiert} ":
            if not messagebox.askyesno(
                f"{sql_typ} ohne WHERE",
                f"Das Statement ist ein {sql_typ} ohne WHERE-Bedingung.\n\n"
                "Das kann sehr viele oder alle Datensätze betreffen.\n\n"
                "Soll es wirklich ausgeführt werden?",
                parent=top
            ):
                debug_log(f"SQL-Ausfuehrung abgebrochen: typ={sql_typ}, grund=ohne WHERE", "allgemein")
                sql_logging_eintrag_sicher_schreiben(
                    f"SQL-Ausführung {sql_typ}: Abgebrochen, ohne WHERE",
                    1
                )
                return
        try:
            import time as _time
            debug_log(f"SQL-Ausfuehrung startet: typ={sql_typ}, laenge={len(sql_text)}", "allgemein")
            verbindung = sqlite_verbindung_mit_udf_oeffnen()
            cursor = verbindung.cursor()

            # UPDATE/DELETE/INSERT in Transaktion ausführen
            if sql_typ in ("UPDATE", "DELETE", "INSERT"):
                # Mehrere Statements per Semikolon aufteilen
                statements = [s.strip() for s in sql_text.split(";") if s.strip()]
                start_zeit = _time.time()
                gesamt_betroffene = 0
                cursor.execute("BEGIN TRANSACTION")
                try:
                    for stmt in statements:
                        cursor.execute(stmt)
                        rc = cursor.rowcount
                        if rc and rc > 0:
                            gesamt_betroffene += rc
                    verbindung.commit()
                except Exception as e:
                    verbindung.rollback()
                    raise e
                dauer = _time.time() - start_zeit
                dauer_text = f"{dauer:.3f}s"

                # WAL Checkpoint – warten bis alles auf die Platte geschrieben ist
                checkpoint_text = ""
                try:
                    checkpoint_start = _time.time()
                    verbindung.execute("PRAGMA wal_checkpoint(FULL)")
                    verbindung.commit()
                    checkpoint_dauer = _time.time() - checkpoint_start
                    checkpoint_text = f"\nCheckpoint (Schreiben auf Platte): {checkpoint_dauer:.3f}s"
                except Exception as _ce:
                    checkpoint_text = f"\nCheckpoint: {_ce}"

                try:
                    verbindung.close()
                except Exception:
                    pass

                if gesamt_betroffene == 0 or gesamt_betroffene < 0:
                    betroffene_text = "0 (kein Datensatz betroffen)"
                else:
                    betroffene_text = str(gesamt_betroffene)

                meldung = (
                    f"Transaktion erfolgreich ausgeführt.\n\n"
                    f"Statements: {len(statements)}\n"
                    f"Betroffene Datensätze: {betroffene_text}\n"
                    f"Ausführungszeit: {dauer_text}"
                    f"{checkpoint_text}"
                )
                if gesamt_betroffene == 0:
                    meldung += "\n\nHinweis: Die WHERE-Bedingung hat keinen Datensatz getroffen."

                # Ausführliches Logging
                sql_kurz = sql_text[:1000] + "..." if len(sql_text) > 1000 else sql_text
                log_meldung = (
                    f"SQL-Transaktion {sql_typ}: erfolgreich\n"
                    f". Statements: {len(statements)} | Betroffene Zeilen: {betroffene_text}\n"
                    f". Ausführungszeit: {dauer_text}{checkpoint_text}\n"
                    f".. Statement:\n"
                    + "\n".join(f".. {zeile}" for zeile in sql_kurz.splitlines())
                )
                sql_logging_eintrag_sicher_schreiben(log_meldung, 0)
                debug_log(f"SQL-Transaktion abgeschlossen: typ={sql_typ}, zeilen={betroffene_text}, dauer={dauer_text}", "allgemein")
                messagebox.showinfo("SQL ausführen", meldung, parent=top if top.winfo_exists() else None)
                return

            # SELECT und andere → wie bisher
            import time as _time
            start_zeit = _time.time()
            cursor.execute(sql_text)
            if cursor.description:
                spalten = [d[0] for d in cursor.description]
                zeilen = cursor.fetchall()
                dauer = _time.time() - start_zeit
                dauer_text = f"{dauer:.3f}s"
                debug_log(
                    f"SQL-Ausfuehrung Ergebnis: typ={sql_typ}, spalten={len(spalten)}, zeilen={len(zeilen)}, dauer={dauer_text}",
                    "allgemein"
                )
                sql_logging_eintrag_sicher_schreiben(
                    f"SQL-Ausführung {sql_typ}: Ergebnisfenster angezeigt\n"
                    f". Spalten={len(spalten)} | Zeilen={len(zeilen)} | Dauer={dauer_text}",
                    0
                )
                abfrage_name = entry_name.get().strip()
                ziel_tabelle = entry_ziel.get().strip()
                fenster_suffix = abfrage_name or ziel_tabelle or "SQL"
                res = tk.Toplevel(top)
                res.title(f"{G_EXE_Title} - SQL-Ergebnis - {fenster_suffix} ({len(zeilen)} Zeilen, {dauer_text})")
                res.geometry("1000x600")
                fenster_registrieren(res, "SQL-Ergebnis")
                res_menue = fenster_standard_menue_anbringen(res, "1000x600", f"SQL-Ergebnis - {fenster_suffix}")
                rf = tk.Frame(res, padx=8, pady=8)
                rf.pack(fill="both", expand=True)
                rf.grid_rowconfigure(0, weight=1)
                rf.grid_columnconfigure(0, weight=1)
                tv = ttk.Treeview(rf, columns=spalten, show="headings")
                tv.grid(row=0, column=0, sticky="nsew")
                sy = ttk.Scrollbar(rf, orient="vertical", command=tv.yview)
                sx = ttk.Scrollbar(rf, orient="horizontal", command=tv.xview)
                sy.grid(row=0, column=1, sticky="ns")
                sx.grid(row=1, column=0, sticky="ew")
                tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

                ergebnis_cache = {
                    "spalten": list(spalten),
                    "alle_zeilen": list(zeilen),
                    "anzeige_zeilen": list(zeilen),
                    "sortierung": {},
                    "filter_aktiv": False,
                    "filter_info": None,
                    "kontext_item_id": None,
                    "kontext_spalte_id": None,
                }

                def ergebnis_spaltenkopf(spalte):
                    richtung = ergebnis_cache["sortierung"].get(spalte)
                    if richtung is None:
                        return spalte
                    return f"{spalte} {'▼' if richtung else '▲'}"

                def ergebnis_anzeigen(zeilen_liste=None):
                    if zeilen_liste is not None:
                        ergebnis_cache["anzeige_zeilen"] = list(zeilen_liste)
                    tv.delete(*tv.get_children())
                    for zeile in ergebnis_cache["anzeige_zeilen"]:
                        tv.insert("", "end", values=zeile)
                    for spalte in ergebnis_cache["spalten"]:
                        tv.heading(spalte, text=ergebnis_spaltenkopf(spalte), anchor="w", command=lambda c=spalte: ergebnis_sortieren(c))
                        tv.column(spalte, anchor="w")
                    tree_spalten_breiten_anpassen(tv)

                def ergebnis_titel_aktualisieren(zusatz=""):
                    basis = f"{G_EXE_Title} - SQL-Ergebnis - {fenster_suffix}"
                    res.title(basis + zusatz)

                def ergebnis_sortieren(spaltenname):
                    if spaltenname not in ergebnis_cache["spalten"]:
                        return
                    index = ergebnis_cache["spalten"].index(spaltenname)
                    absteigend = not ergebnis_cache["sortierung"].get(spaltenname, True)
                    ergebnis_cache["sortierung"] = {spaltenname: absteigend}
                    def _sk_erg(row, _idx=index):
                        vs = str(row[_idx] if _idx < len(row) else "").strip()
                        ip = _ip_zu_int(vs)
                        if ip is not None:
                            return (0, ip, "")
                        try:
                            return (1, float(vs.replace(",", ".")), "")
                        except (ValueError, TypeError):
                            return (2, 0, vs.lower())
                    ergebnis_cache["anzeige_zeilen"].sort(key=_sk_erg, reverse=absteigend)
                    ergebnis_anzeigen()
                    debug_log(f"SQL-Ergebnis sortiert: spalte={spaltenname}, absteigend={absteigend}", "allgemein")

                def ergebnis_kontext_spaltenindex():
                    spalte_id = ergebnis_cache.get("kontext_spalte_id")
                    if not spalte_id:
                        return None
                    try:
                        index = int(spalte_id.replace("#", "")) - 1
                    except Exception:
                        return None
                    if index < 0 or index >= len(ergebnis_cache["spalten"]):
                        return None
                    return index

                def ergebnis_feld_in_zwischenablage():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    res.clipboard_clear()
                    res.clipboard_append(str(werte[index]))

                def ergebnis_zeile_in_zwischenablage():
                    item_id = ergebnis_cache.get("kontext_item_id") or (tv.selection()[0] if tv.selection() else None)
                    if not item_id:
                        return
                    text = "\t".join(str(v) for v in tv.item(item_id, "values"))
                    res.clipboard_clear()
                    res.clipboard_append(text)

                def ergebnis_zeile_im_lesefenster_anzeigen():
                    item_id = ergebnis_cache.get("kontext_item_id") or (tv.selection()[0] if tv.selection() else None)
                    if not item_id:
                        messagebox.showwarning("Zeileninhalt", "Bitte zuerst eine Zeile auswählen.", parent=res)
                        return
                    sql_zeile_im_lesefenster_mit_navigation(
                        res,
                        f"Zeile – SQL-Ergebnis – {fenster_suffix}",
                        tv,
                        ergebnis_cache["spalten"],
                        item_id,
                        kontext_zeile=f"SQL-Ergebnis: {fenster_suffix}"
                    )

                def ergebnis_feld_im_lesefenster_anzeigen():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        messagebox.showwarning("Feldinhalt", "Bitte zuerst eine Zelle auswählen.", parent=res)
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    spaltenname = ergebnis_cache["spalten"][index] if index < len(ergebnis_cache["spalten"]) else f"Spalte{index+1}"
                    sql_text_im_lesefenster_anzeigen(
                        res,
                        f"Feldinhalt – SQL-Ergebnis – {spaltenname}",
                        str(werte[index]),
                    )

                def ergebnis_zeile_als_csv_in_zwischenablage():
                    item_id = ergebnis_cache.get("kontext_item_id") or (tv.selection()[0] if tv.selection() else None)
                    if not item_id:
                        return
                    import csv as csv_modul, io
                    werte = tv.item(item_id, "values")
                    ausgabe = io.StringIO()
                    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
                    writer.writerow(["" if v is None else str(v) for v in werte])
                    res.clipboard_clear()
                    res.clipboard_append(ausgabe.getvalue().rstrip("\r\n"))

                def ergebnis_header_als_csv_in_zwischenablage():
                    import csv as csv_modul, io
                    spalten = ergebnis_cache.get("spalten", [])
                    if not spalten:
                        return
                    ausgabe = io.StringIO()
                    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
                    writer.writerow(spalten)
                    res.clipboard_clear()
                    res.clipboard_append(ausgabe.getvalue().rstrip("\r\n"))

                def ergebnis_tabelle_als_csv_kopieren():
                    alle_ids = tv.get_children()
                    if not alle_ids:
                        messagebox.showwarning("Tabelle als CSV", "Keine Zeilen vorhanden.", parent=res)
                        return
                    gesamt = len(alle_ids)
                    antwort = messagebox.askyesnocancel(
                        "Tabelle als CSV kopieren",
                        f"Es sind {gesamt:,} Zeilen sichtbar.\n\nAlle {gesamt:,} Zeilen kopieren?\n\n"
                        f"(Ja = alle, Nein = nur erste 100, Abbrechen = abbrechen)",
                        parent=res
                    )
                    if antwort is None:
                        return
                    ids = alle_ids if antwort else alle_ids[:100]
                    import csv as csv_modul, io
                    ausgabe = io.StringIO()
                    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
                    writer.writerow(ergebnis_cache.get("spalten", []))
                    for item_id in ids:
                        writer.writerow(tv.item(item_id, "values"))
                    res.clipboard_clear()
                    res.clipboard_append(ausgabe.getvalue())

                def ergebnis_integer_zu_ipv4():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        messagebox.showwarning("Integer zu IPv4", "Bitte zuerst eine Zelle auswählen.", parent=res)
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    feldwert = str(werte[index]).strip()
                    try:
                        zahl = int(feldwert)
                        if zahl < 0 or zahl > 4294967295:
                            raise ValueError()
                        ipv4 = f"{(zahl>>24)&0xFF}.{(zahl>>16)&0xFF}.{(zahl>>8)&0xFF}.{zahl&0xFF}"
                        sql_text_im_lesefenster_anzeigen(res, "Integer zu IPv4-Adresse", f"Eingabe:  {feldwert}\nIPv4:     {ipv4}")
                    except Exception:
                        messagebox.showwarning("Integer zu IPv4", f"'{feldwert}' ist keine gültige Ganzzahl im IPv4-Bereich (0–4294967295).", parent=res)

                def ergebnis_ipv4_zu_integer():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        messagebox.showwarning("IPv4 zu Integer", "Bitte zuerst eine Zelle auswählen.", parent=res)
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    feldwert = str(werte[index]).strip()
                    try:
                        teile = feldwert.split(".")
                        if len(teile) != 4:
                            raise ValueError()
                        oktette = [int(t) for t in teile]
                        if any(o < 0 or o > 255 for o in oktette):
                            raise ValueError()
                        zahl = (oktette[0]<<24)|(oktette[1]<<16)|(oktette[2]<<8)|oktette[3]
                        sql_text_im_lesefenster_anzeigen(res, "IPv4-Adresse zu Integer", f"Eingabe:  {feldwert}\nInteger:  {zahl}")
                    except Exception:
                        messagebox.showwarning("IPv4 zu Integer", f"'{feldwert}' ist keine gültige IPv4-Adresse (z.B. 192.168.1.1).", parent=res)

                def ergebnis_ip_range_aufteilen():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        messagebox.showwarning("IP-Range", "Bitte zuerst eine Zelle auswählen.", parent=res)
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    feldwert = str(werte[index]).strip()
                    ergebnis = ip_range_aufteilen_funktion(feldwert) if callable(ip_range_aufteilen_funktion) else None
                    if ergebnis is None or not ergebnis.get("ok"):
                        fehler = ergebnis.get("fehler", "Unbekannter Fehler") if ergebnis else "Funktion nicht verfügbar"
                        messagebox.showwarning("IP-Range aufteilen", f"'{feldwert}' ist kein gültiger IP-Bereich.\n\nFehler: {fehler}", parent=res)
                        return
                    sql_text_im_lesefenster_anzeigen(
                        res,
                        "IP-Range aufteilen",
                        f"Eingabe:    {feldwert}\n"
                        f"Start-IP:   {ergebnis['start']}  ({ergebnis['start_int']})\n"
                        f"End-IP:     {ergebnis['end']}  ({ergebnis['end_int']})",
                    )

                def ergebnis_netzwerk_ip_anzeigen():
                    import re
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        messagebox.showwarning("Netzwerk/IP", "Bitte zuerst eine Zelle auswählen.", parent=res)
                        return
                    werte = tv.item(item_id, "values")
                    if index >= len(werte):
                        return
                    feldwert = str(werte[index]).strip()

                    def ipv4_zu_int_l(ip):
                        try:
                            t = ip.split(".")
                            if len(t) != 4:
                                return None
                            o = [int(x) for x in t]
                            if any(x < 0 or x > 255 for x in o):
                                return None
                            return (o[0]<<24)|(o[1]<<16)|(o[2]<<8)|o[3]
                        except Exception:
                            return None

                    def int_zu_ipv4_l(z):
                        return f"{(z>>24)&0xFF}.{(z>>16)&0xFF}.{(z>>8)&0xFF}.{z&0xFF}"

                    cidr_muster = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})', feldwert)
                    ip_muster = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', feldwert)
                    zeilen = [f"Eingabe: {feldwert}", ""]
                    gefunden = False
                    for cidr in cidr_muster:
                        try:
                            ip_teil, prefix = cidr.split("/")
                            prefix = int(prefix)
                            ip_int = ipv4_zu_int_l(ip_teil)
                            if ip_int is None or prefix < 0 or prefix > 32:
                                continue
                            maske_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                            netz_int = ip_int & maske_int
                            broadcast_int = netz_int | (~maske_int & 0xFFFFFFFF)
                            erste_host = netz_int + 1 if prefix < 32 else netz_int
                            letzte_host = broadcast_int - 1 if prefix < 32 else broadcast_int
                            anzahl = max(0, broadcast_int - netz_int - 1) if prefix < 31 else (1 if prefix == 32 else 2)
                            zeilen += [f"CIDR: {cidr}", f". Netzadresse:    {int_zu_ipv4_l(netz_int)}",
                                       f". Subnetzmaske:   {int_zu_ipv4_l(maske_int)}", f". Broadcast:      {int_zu_ipv4_l(broadcast_int)}",
                                       f". Erster Host:    {int_zu_ipv4_l(erste_host)}", f". Letzter Host:   {int_zu_ipv4_l(letzte_host)}",
                                       f". Nutzbare Hosts: {anzahl}", ""]
                            gefunden = True
                        except Exception:
                            pass
                    if not gefunden:
                        for ip in ip_muster:
                            ip_int = ipv4_zu_int_l(ip)
                            if ip_int is not None:
                                zeilen += [f"IP-Adresse: {ip}", f". Als Integer: {ip_int}", ""]
                                gefunden = True
                    if not gefunden:
                        messagebox.showwarning("Netzwerk/IP", f"Keine IP oder CIDR gefunden in:\n'{feldwert}'", parent=res)
                        return
                    sql_text_im_lesefenster_anzeigen(res, "Netzwerk / IP-Adresse", "\n".join(zeilen))

                def ergebnis_eindeutige_werte_anzeigen():
                    index = ergebnis_kontext_spaltenindex()
                    if index is None:
                        messagebox.showwarning("Eindeutige Feldwerte", "Bitte zuerst mit der rechten Maustaste in eine Feldspalte klicken.", parent=res)
                        return
                    spaltenname = ergebnis_cache["spalten"][index]
                    items = list(tv.get_children())
                    if not items:
                        messagebox.showinfo("Eindeutige Feldwerte", "In der aktuellen Anzeige sind keine Datensätze vorhanden.", parent=res)
                        return
                    # Rohwerte einmal einlesen
                    rohdaten = []
                    for item_id in items:
                        werte = tv.item(item_id, "values")
                        wert = ""
                        if index < len(werte):
                            wert = "" if werte[index] is None else str(werte[index])
                        rohdaten.append(wert)
                    top_werte = tk.Toplevel(res)
                    top_werte.title(f"{G_EXE_Title} - Eindeutige Werte: SQL-Ergebnis.{spaltenname}")
                    top_werte.geometry("720x560")
                    top_werte.minsize(520, 380)
                    fenster_registrieren(top_werte, "Eindeutige Werte", top_werte.title())
                    haupt = tk.Frame(top_werte, padx=10, pady=10)
                    haupt.pack(fill="both", expand=True)
                    haupt.grid_columnconfigure(0, weight=1)
                    haupt.grid_rowconfigure(3, weight=1)
                    basis_text = f"SQL Ergebnis – {fenster_suffix}"
                    if ergebnis_cache.get("filter_aktiv") and ergebnis_cache.get("filter_info"):
                        info = ergebnis_cache["filter_info"]
                        basis_text = f"SQL Ergebnis – {fenster_suffix}  |  Filter: {info.get('spalte')} enthält '{info.get('wert')}'"
                    # Row 0: dynamische Info-Zeile
                    info_var = tk.StringVar()
                    tk.Label(haupt, textvariable=info_var, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 4))
                    # Row 1: Prefix-Steuerung
                    prefix_frame = tk.Frame(haupt)
                    prefix_frame.grid(row=1, column=0, sticky="w", pady=(0, 4))
                    tk.Label(prefix_frame, text="Erste Zeichen (0 = alle):").pack(side="left")
                    prefix_var = tk.IntVar(value=0)
                    prefix_spin = tk.Spinbox(prefix_frame, from_=0, to=9999, width=6, textvariable=prefix_var, font=("TkDefaultFont", 13))
                    prefix_spin.pack(side="left", padx=(4, 4))

                    def _prefix_hoch():
                        try:
                            prefix_var.set(min(9999, prefix_var.get() + 1))
                        except Exception:
                            pass

                    def _prefix_runter():
                        try:
                            prefix_var.set(max(0, prefix_var.get() - 1))
                        except Exception:
                            pass

                    tk.Button(prefix_frame, text="▲", command=_prefix_hoch,
                              font=("TkDefaultFont", 11), width=2, padx=4).pack(side="left", padx=(0, 2))
                    tk.Button(prefix_frame, text="▼", command=_prefix_runter,
                              font=("TkDefaultFont", 11), width=2, padx=4).pack(side="left", padx=(0, 8))
                    # Row 2: Basis-Text
                    tk.Label(haupt, text=f"Basis: {basis_text}", anchor="w").grid(row=2, column=0, sticky="ew", pady=(0, 8))
                    # Row 3: Treeview
                    tree_frame_werte = tk.Frame(haupt)
                    tree_frame_werte.grid(row=3, column=0, sticky="nsew")
                    tree_frame_werte.grid_rowconfigure(0, weight=1)
                    tree_frame_werte.grid_columnconfigure(0, weight=1)
                    auswertung_tree = ttk.Treeview(tree_frame_werte, columns=("wert", "anzahl"), show="headings", selectmode="browse")
                    eindeutige_sortierung = {"spalte": "anzahl", "absteigend": True}
                    aktuell = {"daten": []}

                    def eindeutige_kopftext(spalte, text):
                        if eindeutige_sortierung.get("spalte") != spalte:
                            return text
                        return f"{text} {'▼' if eindeutige_sortierung.get('absteigend') else '▲'}"

                    def eindeutige_werte_fuellen():
                        prefix = prefix_var.get()
                        zaehler = {}
                        for wert in rohdaten:
                            key = wert[:prefix] if prefix > 0 else wert
                            zaehler[key] = zaehler.get(key, 0) + 1
                        daten = sorted(zaehler.items(), key=lambda e: (-e[1], e[0].lower()))
                        aktuell["daten"] = daten
                        prefix_info = f"    Prefix: {prefix} Zeichen" if prefix > 0 else ""
                        info_var.set((
                            f"Spalte: {spaltenname}    "
                            f"Datensätze: {len(items):,}    "
                            f"unterschiedliche Werte: {len(daten):,}"
                            f"{prefix_info}"
                        ).replace(",", "."))
                        if eindeutige_sortierung.get("spalte") == "wert":
                            daten.sort(key=lambda e: e[0].lower(), reverse=eindeutige_sortierung.get("absteigend", False))
                        else:
                            daten.sort(key=lambda e: (e[1], e[0].lower()), reverse=eindeutige_sortierung.get("absteigend", True))
                        auswertung_tree.delete(*auswertung_tree.get_children())
                        auswertung_tree.heading("wert", text=eindeutige_kopftext("wert", "Wert"),     anchor="w", command=lambda: eindeutige_werte_sortieren("wert"))
                        auswertung_tree.heading("anzahl", text=eindeutige_kopftext("anzahl", "Anzahl"), anchor="w", command=lambda: eindeutige_werte_sortieren("anzahl"))
                        for wert, anzahl in daten:
                            auswertung_tree.insert("", "end", values=("(leer)" if wert == "" else wert, f"{anzahl:,}".replace(",", ".")))

                    def eindeutige_werte_sortieren(spalte):
                        if eindeutige_sortierung.get("spalte") == spalte:
                            eindeutige_sortierung["absteigend"] = not eindeutige_sortierung.get("absteigend", False)
                        else:
                            eindeutige_sortierung["spalte"] = spalte
                            eindeutige_sortierung["absteigend"] = True if spalte == "anzahl" else False
                        eindeutige_werte_fuellen()

                    def _prefix_geaendert(*_):
                        try:
                            eindeutige_werte_fuellen()
                        except Exception:
                            pass
                    prefix_var.trace_add("write", _prefix_geaendert)
                    auswertung_tree.column("wert", anchor="w", width=480)
                    auswertung_tree.column("anzahl", anchor="e", width=120)
                    auswertung_tree.grid(row=0, column=0, sticky="nsew")
                    scroll_y_werte = ttk.Scrollbar(tree_frame_werte, orient="vertical", command=auswertung_tree.yview)
                    scroll_y_werte.grid(row=0, column=1, sticky="ns")
                    scroll_x_werte = ttk.Scrollbar(tree_frame_werte, orient="horizontal", command=auswertung_tree.xview)
                    scroll_x_werte.grid(row=1, column=0, sticky="ew")
                    auswertung_tree.configure(yscrollcommand=scroll_y_werte.set, xscrollcommand=scroll_x_werte.set)

                    def eindeutige_wert_aus_selektion():
                        sel = auswertung_tree.selection()
                        if not sel:
                            return None
                        angezeigt = auswertung_tree.item(sel[0], "values")[0]
                        return "" if angezeigt == "(leer)" else angezeigt

                    def eindeutige_rechtsklick(event):
                        item_id = auswertung_tree.identify_row(event.y)
                        if not item_id:
                            return
                        auswertung_tree.selection_set(item_id)
                        wert = eindeutige_wert_aus_selektion()
                        if wert is None:
                            return
                        menu = tk.Menu(top_werte, tearoff=0)
                        menu.add_command(label="Wert kopieren",
                                         command=lambda: (top_werte.clipboard_clear(),
                                                          top_werte.clipboard_append(wert)))
                        menu.add_separator()
                        menu.add_command(label="Als Filter anwenden",
                                         command=lambda: ergebnis_filter_anwenden(spaltenname, wert))
                        try:
                            menu.tk_popup(event.x_root, event.y_root)
                        finally:
                            menu.grab_release()

                    def eindeutige_doppelklick(event):
                        wert = eindeutige_wert_aus_selektion()
                        if wert is not None:
                            ergebnis_filter_anwenden(spaltenname, wert)

                    auswertung_tree.bind("<Button-3>", eindeutige_rechtsklick)
                    auswertung_tree.bind("<Double-1>", eindeutige_doppelklick)
                    eindeutige_werte_fuellen()
                    # Row 4: Buttons
                    button_frame_werte = tk.Frame(haupt)
                    button_frame_werte.grid(row=4, column=0, sticky="e", pady=(8, 0))

                    def werte_in_zwischenablage():
                        zeilen_export = [f"Spalte\t{spaltenname}", f"Basis\t{basis_text}", "", "Wert\tAnzahl"]
                        for wert, anzahl in aktuell["daten"]:
                            zeilen_export.append(f"{wert}\t{anzahl}")
                        top_werte.clipboard_clear()
                        top_werte.clipboard_append("\n".join(zeilen_export))

                    tk.Button(button_frame_werte, text="In Zwischenspeicher kopieren", command=werte_in_zwischenablage).pack(side="right", padx=(8, 0))
                    tk.Button(button_frame_werte, text="Schließen", command=top_werte.destroy, width=12).pack(side="right")

                def ergebnis_filter_dialog_oeffnen():
                    item_id = ergebnis_cache.get("kontext_item_id")
                    index = ergebnis_kontext_spaltenindex()
                    if not item_id or index is None:
                        return
                    spaltenname = ergebnis_cache["spalten"][index]
                    werte = tv.item(item_id, "values")
                    feldwert = str(werte[index]) if index < len(werte) else ""
                    dialog = tk.Toplevel(res)
                    dialog.title(f"{G_EXE_Title} - SQL-Ergebnis * Feld filtern")
                    dialog.geometry("520x200")
                    dialog.minsize(420, 180)
                    dialog.transient(res)
                    dialog.grab_set()
                    frame = tk.Frame(dialog, padx=12, pady=12)
                    frame.pack(fill="both", expand=True)
                    frame.grid_rowconfigure(1, weight=1)
                    frame.grid_columnconfigure(1, weight=1)
                    tk.Label(frame, text="Spalte:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
                    tk.Label(frame, text=spaltenname).grid(row=0, column=1, sticky="w", pady=(0, 8))
                    tk.Label(frame, text="Filterwert:").grid(row=1, column=0, sticky="nw", padx=(0, 8), pady=(0, 8))
                    text_frame = tk.Frame(frame)
                    text_frame.grid(row=1, column=1, sticky="nsew", pady=(0, 8))
                    text_frame.grid_rowconfigure(0, weight=1)
                    text_frame.grid_columnconfigure(0, weight=1)
                    filter_text = tk.Text(text_frame, height=3, wrap="word")
                    filter_text.grid(row=0, column=0, sticky="nsew")
                    text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=filter_text.yview)
                    text_scroll.grid(row=0, column=1, sticky="ns")
                    filter_text.configure(yscrollcommand=text_scroll.set)
                    filter_text.insert("1.0", feldwert)
                    filter_text.tag_add("sel", "1.0", "end")
                    zaehler_var = tk.StringVar(value=f"{len(feldwert):,} Zeichen".replace(",", "."))
                    tk.Label(frame, textvariable=zaehler_var, anchor="e", fg="gray").grid(row=1, column=2, sticky="e", padx=(4, 0))

                    def zaehler_aktualisieren(event=None):
                        inhalt = filter_text.get("1.0", "end").strip()
                        zaehler_var.set(f"{len(inhalt):,} Zeichen".replace(",", "."))

                    filter_text.bind("<KeyRelease>", zaehler_aktualisieren)
                    filter_text.bind("<<Paste>>", lambda e: frame.after(10, zaehler_aktualisieren))
                    tk.Label(frame, text="Der aktuelle Zellinhalt wurde als Filter vorgeschlagen.", anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
                    button_frame_filter = tk.Frame(frame)
                    button_frame_filter.grid(row=3, column=0, columnspan=2, sticky="e")

                    def anwenden():
                        ergebnis_filter_anwenden(spaltenname, filter_text.get("1.0", "end").strip())
                        dialog.destroy()

                    tk.Button(button_frame_filter, text="Abbrechen", command=dialog.destroy, width=12).pack(side="right")
                    tk.Button(button_frame_filter, text="Hiernach filtern", command=anwenden, width=14).pack(side="right", padx=(0, 8))
                    filter_text.focus_force()
                    dialog.bind("<Return>", lambda event: anwenden())
                    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

                def ergebnis_filter_anwenden(spaltenname, filterwert):
                    if spaltenname not in ergebnis_cache["spalten"]:
                        return
                    filterwert = str(filterwert)
                    index = ergebnis_cache["spalten"].index(spaltenname)
                    gefilterte_zeilen = []
                    for row in ergebnis_cache["alle_zeilen"]:
                        zellwert = ""
                        if index < len(row):
                            zellwert = "" if row[index] is None else str(row[index])
                        if filterwert.lower() in zellwert.lower():
                            gefilterte_zeilen.append(row)
                    ergebnis_cache["filter_aktiv"] = True
                    ergebnis_cache["filter_info"] = {"spalte": spaltenname, "wert": filterwert}
                    ergebnis_anzeigen(gefilterte_zeilen)
                    ergebnis_titel_aktualisieren(f" * gefiltert nach {spaltenname} * enthält '{filterwert}' ({len(gefilterte_zeilen)} Treffer)")
                    debug_log(f"SQL-Ergebnis gefiltert: spalte={spaltenname}, filter={filterwert}, treffer={len(gefilterte_zeilen)}", "allgemein")
                    if len(gefilterte_zeilen) == 0:
                        aufheben = messagebox.askyesno(
                            "Filter ohne Treffer",
                            f"Der Filter auf '{spaltenname}' mit '{filterwert}' liefert 0 Treffer.\n\nSoll der Filter direkt wieder aufgehoben werden?",
                            parent=res
                        )
                        if aufheben:
                            ergebnis_filter_aufheben()

                def ergebnis_filter_aufheben():
                    ergebnis_cache["filter_aktiv"] = False
                    ergebnis_cache["filter_info"] = None
                    ergebnis_anzeigen(ergebnis_cache["alle_zeilen"])
                    ergebnis_titel_aktualisieren(f" * Filter aufgehoben ({len(ergebnis_cache['alle_zeilen']):,} Datensätze)".replace(",", "."))

                def ergebnis_aktuelle_anzeige_als_tabelle_speichern():
                    aktuelle_zeilen = [list(tv.item(item_id, "values")) for item_id in tv.get_children()]
                    if not aktuelle_zeilen:
                        messagebox.showwarning("Als Tabelle speichern", "Es sind keine Datensätze in der aktuellen Anzeige vorhanden.", parent=res)
                        return
                    standardziel = ziel_tabelle or f"{fenster_suffix}_Ergebnis"
                    if ergebnis_cache.get("filter_aktiv"):
                        standardziel = f"{standardziel}_Filter"
                    standardziel = eindeutigen_tabellennamen_vorschlagen_funktion(standardziel)
                    sql_ergebnis_als_tabelle_speichern(res, standardziel, spalten, aktuelle_zeilen)

                def ergebnis_aktuelle_anzeige_als_csv_speichern():
                    aktuelle_zeilen = [list(tv.item(item_id, "values")) for item_id in tv.get_children()]
                    if not aktuelle_zeilen:
                        messagebox.showwarning("Als CSV speichern", "Es sind keine Datensätze in der aktuellen Anzeige vorhanden.", parent=res)
                        return
                    try:
                        from tkinter import filedialog
                        import csv as csv_modul
                        basisname = f"{fenster_suffix}_Ergebnis"
                        if ergebnis_cache.get("filter_aktiv"):
                            basisname = f"{basisname}_Filter"
                        import pathlib, os
                        export_dir = pathlib.Path(os.path.dirname(get_geladene_db_datei()) if get_geladene_db_datei() else ".")
                        vorgeschlagen = eindeutigen_dateinamen_vorschlagen_funktion(export_dir, basisname, ".csv")
                        dateipfad = filedialog.asksaveasfilename(
                            title="SQL-Ergebnis als CSV speichern",
                            defaultextension=".csv",
                            initialfile=vorgeschlagen,
                            initialdir=str(export_dir),
                            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")],
                            parent=res,
                        )
                        if not dateipfad:
                            return
                        with open(dateipfad, "w", encoding="utf-8", newline="") as f:
                            writer = csv_modul.writer(f, delimiter=",", quotechar='"', quoting=csv_modul.QUOTE_ALL)
                            writer.writerow(spalten)
                            for zeile in aktuelle_zeilen:
                                writer.writerow(zeile)
                        messagebox.showinfo("CSV gespeichert", f"Ergebnis wurde als CSV gespeichert.\n\nDatei: {dateipfad}\nDatensätze: {len(aktuelle_zeilen)}", parent=res)
                    except Exception as e:
                        messagebox.showerror("CSV speichern", f"CSV konnte nicht gespeichert werden:\n{e}", parent=res)

                def ergebnis_finding_manuell_hinzufuegen():
                    """Finding aus SQL-Ergebniszeile manuell in zzz_Findings eintragen."""
                    import re as _re
                    G_TABELLE_FINDINGS = "zzz_Findings"
                    item_id = ergebnis_cache.get("kontext_item_id")
                    if not item_id:
                        messagebox.showwarning("Finding hinzufügen", "Bitte zuerst eine Zeile auswählen.", parent=res)
                        return
                    werte = list(tv.item(item_id, "values"))

                    # zzz_Findings-Tabelle sicherstellen
                    try:
                        vb = sqlite_verbindung_oeffnen()
                        vb.execute(
                            f"""CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_FINDINGS)} (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                datetime TEXT NOT NULL,
                                TabellenName TEXT,
                                idFeld TEXT,
                                idFeldInhalt TEXT,
                                Feldname TEXT,
                                FeldInhalt TEXT,
                                KurzeBeschreibung TEXT,
                                UNIQUE(TabellenName, idFeld, idFeldInhalt))"""
                        )
                        try:
                            vb.execute(
                                f"CREATE UNIQUE INDEX IF NOT EXISTS idx_findings_unique "
                                f"ON {sql_identifier(G_TABELLE_FINDINGS)} (TabellenName, idFeld, idFeldInhalt)"
                            )
                        except Exception:
                            pass
                        vb.commit()
                        vb.close()
                    except Exception as e:
                        messagebox.showerror("Finding hinzufügen", f"Tabelle konnte nicht angelegt werden:\n{e}", parent=res)
                        return

                    # Tabellennamen aus der SQL-Abfrage extrahieren
                    alle_tabellen = []
                    try:
                        gefunden = _re.findall(
                            r'\b(?:FROM|JOIN|INTO|UPDATE)\s+[`"\[]?(\w+)[`"\]]?',
                            sql_text, _re.IGNORECASE
                        )
                        seen = set()
                        for t in gefunden:
                            tl = t.lower()
                            if tl not in seen:
                                seen.add(tl)
                                alle_tabellen.append(t)
                    except Exception:
                        pass
                    # Fallback: alle DB-Tabellen, falls Parsing nichts liefert
                    if not alle_tabellen:
                        try:
                            vb = sqlite_verbindung_oeffnen()
                            alle_tabellen = [r[0] for r in vb.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                            ).fetchall()]
                            vb.close()
                        except Exception:
                            pass

                    # Bestehende Beschreibungen laden
                    vorhandene_beschreibungen = []
                    try:
                        vb = sqlite_verbindung_oeffnen()
                        vorhandene_beschreibungen = [r[0] for r in vb.execute(
                            f"SELECT DISTINCT KurzeBeschreibung FROM {sql_identifier(G_TABELLE_FINDINGS)} "
                            f"WHERE KurzeBeschreibung IS NOT NULL AND KurzeBeschreibung != '' "
                            f"ORDER BY KurzeBeschreibung"
                        ).fetchall()]
                        vb.close()
                    except Exception:
                        pass

                    # Dialog
                    dialog = tk.Toplevel(res)
                    dialog.title("Finding hinzufügen")
                    dialog.geometry("560x320")
                    dialog.resizable(False, False)
                    dialog.grab_set()
                    dialog.transient(res)
                    dialog.columnconfigure(1, weight=1)

                    # Hilfsfunktion: Wert einer Spalte aus der aktuellen Zeile
                    def zeilenwert(spaltenname):
                        if spaltenname in spalten:
                            idx = spalten.index(spaltenname)
                            return str(werte[idx]) if idx < len(werte) else ""
                        return ""

                    # Zeile 0: Tabellenname
                    tk.Label(dialog, text="Tabellenname:", anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(10, 2))
                    tabellen_var = tk.StringVar(value=alle_tabellen[0] if alle_tabellen else "")
                    tabellen_cb = ttk.Combobox(dialog, textvariable=tabellen_var, values=alle_tabellen, width=48)
                    tabellen_cb.grid(row=0, column=1, padx=(0, 16), pady=(10, 2), sticky="ew")

                    # Zeile 1: ID-Feld
                    tk.Label(dialog, text="ID-Feld:", anchor="w").grid(row=1, column=0, sticky="w", padx=16, pady=(4, 2))
                    id_feld_var = tk.StringVar()
                    id_feld_start = next((s for s in spalten if s.lower() == "id"), (spalten[0] if spalten else ""))
                    id_feld_var.set(id_feld_start)
                    id_feld_cb = ttk.Combobox(dialog, textvariable=id_feld_var, values=spalten, width=48)
                    id_feld_cb.grid(row=1, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")

                    # Zeile 2: ID-Inhalt (readonly, auto-fill)
                    tk.Label(dialog, text="ID-Inhalt:", anchor="w").grid(row=2, column=0, sticky="w", padx=16, pady=(4, 2))
                    id_inhalt_var = tk.StringVar(value=zeilenwert(id_feld_var.get()))
                    id_inhalt_entry = tk.Entry(dialog, textvariable=id_inhalt_var, state="readonly", width=50)
                    id_inhalt_entry.grid(row=2, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")

                    def on_id_feld_selected(event=None):
                        id_inhalt_var.set(zeilenwert(id_feld_var.get()))
                    id_feld_cb.bind("<<ComboboxSelected>>", on_id_feld_selected)

                    # Zeile 3: Feldname
                    tk.Label(dialog, text="Feldname:", anchor="w").grid(row=3, column=0, sticky="w", padx=16, pady=(4, 2))
                    feldname_var = tk.StringVar()
                    kontext_spalte_id = ergebnis_cache.get("kontext_spalte_id", "#1")
                    try:
                        kontext_idx = max(0, int(kontext_spalte_id.replace("#", "")) - 1)
                    except (ValueError, AttributeError):
                        kontext_idx = 0
                    feldname_start = spalten[kontext_idx] if kontext_idx < len(spalten) else (spalten[0] if spalten else "")
                    feldname_var.set(feldname_start)
                    feldname_cb = ttk.Combobox(dialog, textvariable=feldname_var, values=spalten, width=48)
                    feldname_cb.grid(row=3, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")

                    # Zeile 4: Feldinhalt (readonly, auto-fill)
                    tk.Label(dialog, text="Feldinhalt:", anchor="w").grid(row=4, column=0, sticky="w", padx=16, pady=(4, 2))
                    feldinhalt_var = tk.StringVar(value=zeilenwert(feldname_var.get()))
                    feldinhalt_entry = tk.Entry(dialog, textvariable=feldinhalt_var, state="readonly", width=50)
                    feldinhalt_entry.grid(row=4, column=1, padx=(0, 16), pady=(4, 16), sticky="ew")

                    def on_feldname_selected(event=None):
                        feldinhalt_var.set(zeilenwert(feldname_var.get()))
                    feldname_cb.bind("<<ComboboxSelected>>", on_feldname_selected)

                    # Zeile 5: KurzeBeschreibung + Aus-Feld-Knopf
                    tk.Label(dialog, text="Kurze Beschreibung:", anchor="w").grid(row=5, column=0, sticky="w", padx=16, pady=(0, 2))
                    beschr_frame = tk.Frame(dialog)
                    beschr_frame.grid(row=5, column=1, padx=(0, 16), pady=(0, 2), sticky="ew")
                    beschr_frame.columnconfigure(0, weight=1)
                    beschreibung_var = tk.StringVar()
                    beschreibung_cb = ttk.Combobox(beschr_frame, textvariable=beschreibung_var, values=vorhandene_beschreibungen, width=34)
                    beschreibung_cb.grid(row=0, column=0, sticky="ew", padx=(0, 4))
                    aus_feld_var = tk.StringVar(value="Aus Feld ▾")
                    aus_feld_cb = ttk.Combobox(beschr_frame, textvariable=aus_feld_var, values=spalten, width=14, state="readonly")
                    aus_feld_cb.grid(row=0, column=1, sticky="e")

                    def on_aus_feld_selected(event=None):
                        gewaehlt = aus_feld_var.get()
                        if gewaehlt in spalten:
                            beschreibung_var.set(zeilenwert(gewaehlt))
                        aus_feld_var.set("Aus Feld ▾")
                    aus_feld_cb.bind("<<ComboboxSelected>>", on_aus_feld_selected)

                    ergebnis = [None]

                    def bestaetigen(event=None):
                        ergebnis[0] = {
                            "tabellenname": tabellen_var.get().strip(),
                            "id_feld":      id_feld_var.get().strip(),
                            "id_inhalt":    id_inhalt_var.get(),
                            "feldname":     feldname_var.get().strip(),
                            "feldinhalt":   feldinhalt_var.get(),
                            "beschreibung": beschreibung_var.get().strip(),
                        }
                        dialog.destroy()

                    def abbrechen():
                        dialog.destroy()

                    btn_frame = tk.Frame(dialog)
                    btn_frame.grid(row=6, column=0, columnspan=2, pady=(10, 10))
                    tk.Button(btn_frame, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 16))
                    tk.Button(btn_frame, text="Abbrechen", width=12, command=abbrechen).pack(side="right")
                    beschreibung_cb.bind("<Return>", bestaetigen)
                    beschreibung_cb.bind("<Escape>", lambda e: abbrechen())
                    beschreibung_cb.focus_set()
                    dialog.wait_window()

                    if ergebnis[0] is None:
                        return

                    d = ergebnis[0]
                    if not d["tabellenname"]:
                        messagebox.showwarning("Finding hinzufügen", "Bitte einen Tabellennamen angeben.", parent=res)
                        return

                    # Prüfen ob Finding bereits existiert
                    ist_update = False
                    try:
                        vb = sqlite_verbindung_oeffnen()
                        row = vb.execute(
                            f"SELECT KurzeBeschreibung FROM {sql_identifier(G_TABELLE_FINDINGS)} "
                            f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                            (d["tabellenname"], d["id_feld"], d["id_inhalt"]),
                        ).fetchone()
                        vb.close()
                        if row is not None:
                            ist_update = True
                    except Exception:
                        pass

                    if ist_update:
                        if not messagebox.askyesno(
                            "Finding existiert bereits",
                            "Für diesen Datensatz existiert bereits ein Finding.\n\nSoll es überschrieben werden?",
                            parent=res,
                        ):
                            return

                    try:
                        from datetime import datetime as _dt
                        jetzt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                        vb = sqlite_verbindung_oeffnen()
                        if ist_update:
                            vb.execute(
                                f"UPDATE {sql_identifier(G_TABELLE_FINDINGS)} "
                                f"SET Feldname=?, FeldInhalt=?, KurzeBeschreibung=?, datetime=? "
                                f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                                (d["feldname"], d["feldinhalt"], d["beschreibung"], jetzt,
                                 d["tabellenname"], d["id_feld"], d["id_inhalt"]),
                            )
                            log_aktion = "Finding aktualisiert"
                        else:
                            vb.execute(
                                f"INSERT INTO {sql_identifier(G_TABELLE_FINDINGS)} "
                                f"(TabellenName, idFeld, idFeldInhalt, Feldname, FeldInhalt, KurzeBeschreibung, datetime) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (d["tabellenname"], d["id_feld"], d["id_inhalt"],
                                 d["feldname"], d["feldinhalt"], d["beschreibung"], jetzt),
                            )
                            log_aktion = "Finding hinzugefügt"
                        vb.commit()
                        vb.close()
                        sql_logging_eintrag_sicher_schreiben(
                            f"{log_aktion}: {d['tabellenname']} / {d['feldname']} = {d['feldinhalt'][:50]}\n"
                            f". Beschreibung: {d['beschreibung'][:100]}",
                            0,
                        )
                        messagebox.showinfo(log_aktion, "Das Finding wurde gespeichert.", parent=res)
                    except Exception as e:
                        sql_logging_eintrag_sicher_schreiben(f"Fehler beim Speichern des Findings: {e}", 1)
                        messagebox.showerror("Finding hinzufügen", f"Fehler:\n{e}", parent=res)

                def ergebnis_rechtsklick(event):
                    region = tv.identify_region(event.x, event.y)
                    if region == "heading":
                        menu = tk.Menu(res, tearoff=0)
                        _tv_spalten_menue_aufbauen(menu, tv,
                                                   lambda: tree_spalten_breiten_anpassen(tv))
                        try:
                            menu.tk_popup(event.x_root, event.y_root)
                        finally:
                            menu.grab_release()
                        return
                    item_id = tv.identify_row(event.y)
                    spalte_id = tv.identify_column(event.x)
                    if item_id:
                        tv.focus(item_id)
                        tv.selection_set(item_id)
                    ergebnis_cache["kontext_item_id"] = item_id
                    ergebnis_cache["kontext_spalte_id"] = spalte_id
                    menu = tk.Menu(res, tearoff=0)
                    # Block 1: Kopieren
                    menu.add_command(label="Feldinhalt kopieren", command=ergebnis_feld_in_zwischenablage)
                    menu.add_command(label="Zeile kopieren", command=ergebnis_zeile_in_zwischenablage)
                    menu.add_command(label="Zeile als CSV kopieren", command=ergebnis_zeile_als_csv_in_zwischenablage)
                    menu.add_command(label="Header als CSV kopieren", command=ergebnis_header_als_csv_in_zwischenablage)
                    menu.add_command(label="Tabelle als CSV kopieren", command=ergebnis_tabelle_als_csv_kopieren)
                    menu.add_separator()
                    # Block 2: Anzeigen
                    menu.add_command(label="Feldinhalt im Lesefenster anzeigen", command=ergebnis_feld_im_lesefenster_anzeigen)
                    menu.add_command(label="Zeile im Lesefenster anzeigen", command=ergebnis_zeile_im_lesefenster_anzeigen)
                    menu.add_command(label="Daten optimal",                  command=lambda: tree_spalten_breiten_anpassen(tv))
                    menu.add_command(label="Spaltennamen optimal",           command=lambda: _tv_spalten_minimum(tv))
                    menu.add_command(label="Alle Spaltennamen vollständig anzeigen",
                                     command=lambda: tree_spalten_breiten_anpassen(tv))
                    menu.add_separator()
                    # Block 3: Filtern
                    menu.add_command(label="Feldfilter setzen", command=ergebnis_filter_dialog_oeffnen)
                    menu.add_command(label="Feldfilter aufheben", command=ergebnis_filter_aufheben)
                    menu.add_command(label="Eindeutige Feldwerte anzeigen", command=ergebnis_eindeutige_werte_anzeigen)
                    menu.add_separator()
                    # Block 4: IPv4
                    menu.add_command(label="Integer zu IPv4-Adresse", command=ergebnis_integer_zu_ipv4)
                    menu.add_command(label="IPv4-Adresse zu Integer", command=ergebnis_ipv4_zu_integer)
                    menu.add_command(label="IP-Range aufteilen", command=ergebnis_ip_range_aufteilen)
                    menu.add_command(label="Netzwerk IP oder Maske anzeigen", command=ergebnis_netzwerk_ip_anzeigen)
                    menu.add_separator()
                    # Block 5: Findings
                    menu.add_command(label="Finding hinzufügen", command=ergebnis_finding_manuell_hinzufuegen)
                    try:
                        menu.tk_popup(event.x_root, event.y_root)
                    finally:
                        menu.grab_release()

                tv.bind("<Button-3>", ergebnis_rechtsklick)
                ergebnis_anzeigen()
                # Menüeinträge ergänzen
                res_menue.add_command(label="Als Tabelle speichern", command=ergebnis_aktuelle_anzeige_als_tabelle_speichern)
                res_menue.add_command(label="Als CSV speichern", command=ergebnis_aktuelle_anzeige_als_csv_speichern)
                res_menue.add_command(label="Schließen", command=res.destroy)
            else:
                betroffene_zeilen = cursor.rowcount
                verbindung.commit()
                if betroffene_zeilen is None or betroffene_zeilen < 0:
                    meldung = "Anweisung erfolgreich ausgeführt.\n\nBetroffene Datensätze: unbekannt"
                elif betroffene_zeilen == 0:
                    meldung = (
                        "Anweisung erfolgreich ausgeführt.\n\n"
                        "Betroffene Datensätze: 0\n\n"
                        "Hinweis: Die WHERE-Bedingung hat keinen vorhandenen Datensatz getroffen."
                    )
                elif betroffene_zeilen == 1:
                    meldung = "Anweisung erfolgreich ausgeführt.\n\nBetroffene Datensätze: 1"
                else:
                    meldung = f"Anweisung erfolgreich ausgeführt.\n\nBetroffene Datensätze: {betroffene_zeilen}"
                sql_kurz = sql_text[:1000] + "..." if len(sql_text) > 1000 else sql_text
                log_meldung = (
                    f"SQL-Ausführung {sql_typ}: erfolgreich\n"
                    f". Betroffene Zeilen: {betroffene_zeilen}\n"
                    f".. Statement:\n"
                    + "\n".join(f".. {zeile}" for zeile in sql_kurz.splitlines())
                )
                debug_log(f"SQL-Ausfuehrung abgeschlossen: typ={sql_typ}, rowcount={betroffene_zeilen}", "allgemein")
                sql_logging_eintrag_sicher_schreiben(log_meldung, 0)
                messagebox.showinfo("SQL ausführen", meldung, parent=top)
            verbindung.close()
        except Exception as e:
            debug_log(f"SQL-Ausfuehrung Fehler: typ={sql_typ}, fehler={e}", "allgemein")
            sql_logging_eintrag_sicher_schreiben(
                f"SQL-Ausführung {sql_typ}: Fehler: {e}",
                1
            )
            messagebox.showerror("SQL ausführen", f"SQL konnte nicht ausgeführt werden:\n{e}", parent=top)

    def abfrage_neu():
        """Leert das Formular für eine neue SQL-Abfrage."""
        if hat_ungespeicherte_aenderungen():
            antwort = messagebox.askyesnocancel(
                "Neue Abfrage",
                "Es gibt ungespeicherte Änderungen.\n\nSollen die Änderungen vor dem Leeren gespeichert werden?",
                parent=top
            )
            if antwort is None:
                return
            if antwort:
                if not speichern():
                    if not messagebox.askyesno(
                        "Neue Abfrage",
                        "Die Abfrage konnte nicht gespeichert werden.\n\nTrotzdem neu beginnen?",
                        parent=top
                    ):
                        return
        entry_name.delete(0, "end")
        entry_ziel.delete(0, "end")
        editor.delete("1.0", "end")
        # Listen mit Standardwerten neu befüllen (nicht nur leeren!)
        beziehungen[:] = [
            {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
            {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
            {"typ": "", "tabelle": "", "links_tabelle": "", "rechts_tabelle": "", "links": "", "rechts": ""},
        ]
        where_bedingungen[:] = [
            {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        ]
        order_by_zeilen[:] = [{"feld": "", "richtung": "ASC"}]
        update_sets[:] = [{"feld": "", "wert": ""}]
        update_where_bedingungen[:] = [
            {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        ]
        delete_where_bedingungen[:] = [
            {"verknuepfung": "WHERE", "tabelle": "", "links": "", "operator": "=", "wert": ""},
        ]
        insert_werte[:] = [{"feld": "", "wert": ""}]
        aktuelle_beziehung["index"] = 0
        aktuelle_where_bedingung["index"] = 0
        aktuelle_order_by["index"] = 0
        aktuelle_update_set["index"] = 0
        aktuelle_update_where["index"] = 0
        aktuelle_delete_where["index"] = 0
        aktuelle_insert_zeile["index"] = 0
        beziehung_widgetwerte_laden(0)
        where_widgetwerte_laden(0)
        order_by_widgetwerte_laden(0)
        update_set_widgetwerte_laden(0)
        update_where_widgetwerte_laden(0)
        delete_where_widgetwerte_laden(0)
        insert_widgetwerte_laden(0)
        beziehung_auswahlwerte_aktualisieren()
        where_auswahlwerte_aktualisieren()
        order_by_auswahlwerte_aktualisieren()
        update_set_auswahlwerte_aktualisieren()
        update_where_auswahlwerte_aktualisieren()
        delete_where_auswahlwerte_aktualisieren()
        insert_auswahlwerte_aktualisieren()
        gespeicherten_zustand_merken()
        tree_saved.selection_remove(tree_saved.selection())
        tree_saved_status["letzter_name"] = None
        debug_log("Neue SQL-Abfrage gestartet (Formular geleert)", "allgemein")

    def abfrage_loeschen():
        """Löscht die aktuell gewählte SQL-Abfrage nach Rückfrage."""
        auswahl = tree_saved.selection()
        if not auswahl:
            messagebox.showwarning("Abfrage löschen", "Bitte zuerst eine Abfrage auswählen.", parent=top)
            return
        values = tree_saved.item(auswahl[0], "values")
        name = values[0] if values else ""
        if not name:
            return
        if not messagebox.askyesno(
            "Abfrage löschen",
            f"Soll die Abfrage '{name}' wirklich gelöscht werden?",
            parent=top
        ):
            return
        try:
            verbindung = sqlite_verbindung_oeffnen(get_geladene_db_datei())
            cursor = verbindung.cursor()
            cursor.execute(
                f"DELETE FROM {sql_identifier(G_TABELLE_SQL_ABFRAGEN)} WHERE name = ?",
                (name,)
            )
            verbindung.commit()
            verbindung.close()
            gespeicherte_fuellen()
            gespeicherten_zustand_merken()
            tree_saved_status["letzter_name"] = None
            debug_log(f"SQL-Abfrage gelöscht: name={name}", "allgemein")
            sql_logging_eintrag_sicher_schreiben(f"SQL-Abfrage gelöscht: {name}", 0)
        except Exception as e:
            messagebox.showerror("Abfrage löschen", f"Löschen fehlgeschlagen:\n{e}", parent=top)

    def abfrage_rechtsklick(event):
        item_id = tree_saved.identify_row(event.y)
        if item_id:
            tree_saved.selection_set(item_id)
            tree_saved.focus(item_id)
        menu = tk.Menu(top, tearoff=0)
        menu.add_command(label="Neu", command=abfrage_neu)
        menu.add_command(label="Löschen", command=abfrage_loeschen)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── Rechtsklick-Menüs: Tabellen, Felder, Funktionen, SQL-Editor ──────────

    def _funktion_direkt_einfuegen(ausdruck):
        """Fügt ausdruck an der Cursor-Position ein; ersetzt 'Feldname' wenn ein Feld gewählt ist."""
        aktuelles_feld = None
        feld_sel = tree_fel.selection()
        if feld_sel:
            feld = tree_fel.item(feld_sel[0], "values")[0]
            tab_sel = tree_tab.selection()
            if tab_sel:
                tname = tree_tab.item(tab_sel[0], "values")[0]
                aktuelles_feld = f"{tname}.{feld}"
            else:
                aktuelles_feld = feld
        expr = ausdruck.replace("Feldname", aktuelles_feld) if aktuelles_feld else ausdruck
        editor.insert("insert", expr + " ")
        editor.focus_force()

    def feld_in_where_wert_einfuegen(event=None):
        """Setzt das gewählte Feld als WHERE-Wert (rechte Seite / Vergleichswert)."""
        auswahl = tree_fel.selection()
        if not auswahl:
            return
        feld = tree_fel.item(auswahl[0], "values")[0]
        tab_auswahl = tree_tab.selection()
        if tab_auswahl:
            tname = tree_tab.item(tab_auswahl[0], "values")[0]
            feld = f"{tname}.{feld}"
        set_entry(w_wert, feld)
        w_wert.focus_force()

    # ── Rechtsklick Tabellen-/Felder-/Funktionsliste: extra SQL-Aktionen vorn ──
    def _tab_extra(m, iid, sp_name):
        m.add_command(label="Aktualisieren  (F5)", command=tabellen_liste_fuellen)
        m.add_separator()
        tname = tree_tab.item(iid, "values")[0] if iid else ""
        if tname:
            m.add_command(
                label=f"Tabellenname einfügen: {tname}",
                command=lambda t=tname: (editor.insert("insert", t + " "),
                                         editor.focus_force()))
            m.add_command(
                label=f"SELECT * FROM {tname}",
                command=lambda t=tname: (select_from_tabelle.set(t),
                                         select_from_einfuegen()))

    def _fel_extra(m, iid, sp_name):
        feld = tree_fel.item(iid, "values")[0] if iid else ""
        if feld:
            m.add_command(label="In SELECT einfügen",
                          command=feld_einfuegen)
            m.add_command(label="In WHERE Feld einfügen  (Shift+Doppelklick)",
                          command=feld_in_where_links_einfuegen)
            m.add_command(label="In WHERE Wert einfügen",
                          command=feld_in_where_wert_einfuegen)

    def _func_extra(m, iid, sp_name):
        if not iid:
            return
        fname    = tree_func.item(iid, "values")[0]
        ausdruck = (tree_func.item(iid, "tags") or ("",))[0]
        sql_fname = ausdruck.split("(")[0].strip() if "(" in ausdruck else ausdruck
        if fname:
            m.add_command(label="In SQL einfügen  (Doppelklick)",
                          command=funktion_in_statement_einfuegen)
            m.add_command(label="SQL-Ausdruck kopieren",
                          command=lambda a=ausdruck: (top.clipboard_clear(),
                                                       top.clipboard_append(a)))
            m.add_command(label=f"Funktionsname kopieren: {sql_fname}",
                          command=lambda n=sql_fname: (top.clipboard_clear(),
                                                        top.clipboard_append(n)))

    tab_ref  = standard_tv_rechtsklick_anbinden(tree_tab,  "Tabellen",   top,
                                                 extra_menue_fn=_tab_extra,  db_edit=False)
    fel_ref  = standard_tv_rechtsklick_anbinden(tree_fel,  "Felder",     top,
                                                 extra_menue_fn=_fel_extra,  db_edit=False)
    func_ref = standard_tv_rechtsklick_anbinden(tree_func, "Funktionen", top,
                                                 extra_menue_fn=_func_extra, db_edit=False)
    func_ref["alle"] = [(fn,) for fn, _ in sql_funktionsvorlagen]

    def editor_rechtsklick(event):
        m = tk.Menu(top, tearoff=0)
        m.add_command(label="Ausschneiden",
                      command=lambda: editor.event_generate("<<Cut>>"))
        m.add_command(label="Kopieren",
                      command=lambda: editor.event_generate("<<Copy>>"))
        m.add_command(label="Einfügen",
                      command=lambda: editor.event_generate("<<Paste>>"))
        m.add_command(label="Alles markieren",
                      command=lambda: (editor.tag_add("sel", "1.0", "end-1c"),
                                       editor.mark_set("insert", "1.0")))
        m.add_separator()
        sub = tk.Menu(m, tearoff=0)
        for _fname, _ausdruck in sql_funktionsvorlagen:
            # Anzeigename: nur der erste Teil vor den mehrfachen Leerzeichen
            _label = _fname.strip().split("  ")[0].rstrip()
            sub.add_command(
                label=_label,
                command=lambda a=_ausdruck: _funktion_direkt_einfuegen(a))
        m.add_cascade(label="Funktion einfügen  ▶", menu=sub)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ── Bindings ─────────────────────────────────────────────────────────────
    # tree_tab, tree_fel, tree_func: Rechtsklick-Bindings durch standard_tv_rechtsklick_anbinden gesetzt
    editor.bind("<Button-3>", editor_rechtsklick)

    tree_tab.bind("<<TreeviewSelect>>", tabellen_auswahl)
    tree_tab.bind("<F5>", lambda e: tabellen_liste_fuellen())
    top.bind("<F5>",     lambda e: tabellen_liste_fuellen())
    tree_saved.bind("<<TreeviewSelect>>", gespeicherte_auswahl_gewechselt)
    tree_saved.bind("<Button-3>", abfrage_rechtsklick)
    tree_projekte.bind("<<TreeviewSelect>>", projekt_auswahl_gewechselt)
    tree_projekte.bind("<Button-3>", projekt_rechtsklick)
    tree_fel.bind("<Double-1>", feld_einfuegen)
    tree_fel.bind("<Shift-Double-1>", feld_in_where_links_einfuegen)
    tree_func.bind("<Double-1>", funktion_in_statement_einfuegen)
    beziehung_auswahl.bind("<<ComboboxSelected>>", beziehung_auswahl_gewechselt)
    button_select_from_einfuegen.configure(command=select_from_einfuegen)
    b_tab.bind("<<ComboboxSelected>>", join_zieltabelle_gewechselt)
    b_links_tab.bind("<<ComboboxSelected>>", join_linke_felder_aktualisieren)
    b_rechts_tab.bind("<<ComboboxSelected>>", join_rechte_felder_aktualisieren)
    button_beziehung_einfuegen.configure(command=beziehung_in_statement_einfuegen)
    button_beziehung_neu.configure(command=beziehung_neu)
    button_beziehung_loeschen.configure(command=beziehung_loeschen)
    where_auswahl.bind("<<ComboboxSelected>>", where_auswahl_gewechselt)
    w_tab.bind("<<ComboboxSelected>>", where_felder_aktualisieren)
    button_where_einfuegen.configure(command=where_in_statement_einfuegen)
    button_where_neu.configure(command=where_neu)
    button_where_loeschen.configure(command=where_loeschen)
    order_by_auswahl.bind("<<ComboboxSelected>>", order_by_auswahl_gewechselt)
    order_by_tab.bind("<<ComboboxSelected>>", order_by_felder_aktualisieren)
    button_order_by_einfuegen.configure(command=order_by_in_statement_einfuegen)
    button_alle_order_by_einfuegen.configure(command=alle_order_by_in_statement_einfuegen)
    button_order_by_neu.configure(command=order_by_neu)
    button_order_by_loeschen.configure(command=order_by_loeschen)
    update_tabelle.bind("<<ComboboxSelected>>", update_felder_aktualisieren)
    update_set_auswahl.bind("<<ComboboxSelected>>", update_set_auswahl_gewechselt)
    button_update_set_neu.configure(command=update_set_neu)
    button_update_set_loeschen.configure(command=update_set_loeschen)
    update_where_auswahl.bind("<<ComboboxSelected>>", update_where_auswahl_gewechselt)
    button_update_where_neu.configure(command=update_where_neu)
    button_update_where_loeschen.configure(command=update_where_loeschen)
    button_update_einfuegen.configure(command=update_in_statement_einfuegen)
    delete_tabelle.bind("<<ComboboxSelected>>", delete_felder_aktualisieren)
    delete_where_auswahl.bind("<<ComboboxSelected>>", delete_where_auswahl_gewechselt)
    button_delete_where_neu.configure(command=delete_where_neu)
    button_delete_where_loeschen.configure(command=delete_where_loeschen)
    button_delete_einfuegen.configure(command=delete_in_statement_einfuegen)
    insert_tabelle.bind("<<ComboboxSelected>>", insert_felder_aktualisieren)
    insert_auswahl.bind("<<ComboboxSelected>>", insert_auswahl_gewechselt)
    button_insert_neu.configure(command=insert_neu)
    button_insert_loeschen.configure(command=insert_loeschen)
    button_insert_einfuegen.configure(command=insert_in_statement_einfuegen)

    sql_reiter_inhalte_nach_unten_verschieben(select_tab)
    sql_reiter_inhalte_nach_unten_verschieben(update_tab)
    sql_reiter_inhalte_nach_unten_verschieben(delete_tab)
    sql_reiter_inhalte_nach_unten_verschieben(insert_tab)

    tk.Button(button_frame, text="SQL prüfen", width=12, command=pruefen).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="SQL ausführen", width=16, command=ausfuehren).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="SQL speichern", width=16, command=speichern).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Schema-Update", width=14, command=schema_update_und_tabellen_aktualisieren).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Projekt speichern", width=15, command=projekt_speichern).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Schließen", width=12, command=schliessen).pack(side="left")
    fenster_schliessen_callback_setzen(top, schliessen)
    top.protocol("WM_DELETE_WINDOW", schliessen)

    tabellen_liste_fuellen()
    gespeicherte_fuellen()
    projektliste_fuellen()
    # Aktives Projekt automatisch vorauswählen, damit der Benutzer es nicht
    # nach dem Öffnen des SQL Editors noch manuell anklicken muss.
    try:
        _aktiv = aktives_projekt_laden()
        if _aktiv:
            for _item in tree_projekte.get_children():
                _vals = tree_projekte.item(_item, "values")
                if _vals and _vals[0] == _aktiv:
                    tree_projekte.selection_set(_item)
                    tree_projekte.focus(_item)
                    tree_projekte.see(_item)
                    projekt_status["aktuell"] = _aktiv
                    _G_ausgewaehltes_projekt["name"] = _aktiv
                    projekt_name_anzeige.set(_aktiv)
                    aktiv_var.set(True)
                    sql_builder_auf_leeren_projektzustand_setzen(_aktiv)
                    workflow_fuellen(_aktiv)
                    _on_projekt_ausgewaehlt_fuer_views(_aktiv)
                    break
    except Exception:
        pass
    beziehung_auswahlwerte_aktualisieren()
    where_auswahlwerte_aktualisieren()
    order_by_auswahlwerte_aktualisieren()
    update_set_auswahlwerte_aktualisieren()
    update_where_auswahlwerte_aktualisieren()
    update_set_widgetwerte_laden(0)
    update_where_widgetwerte_laden(0)
    delete_where_auswahlwerte_aktualisieren()
    delete_where_widgetwerte_laden(0)
    insert_auswahlwerte_aktualisieren()
    insert_widgetwerte_laden(0)
    gespeicherten_zustand_merken()
    # Theme auf neu geöffnetes SQL-Editor-Fenster anwenden
    treeview_theme_anwenden(_sql_konfig_lesen("treeview_theme") or "standard", speichern=False)
