"""
SqlGui - bereinigte Hauptdatei mit einem einzigen CSV-Pfad.
Fokus: DB-Grundfunktionen, CSV-Vorschau und CSV-Rechtsklickmenü mit Word Wrap.
"""

__version__ = "4.6.51"
G_HELP_INFO = f"SQL-GUI {__version__}"

import csv
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import tkinter as tk
import threading
import queue
import time
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, messagebox, simpledialog, ttk

from sqlgui_text import csv_anzeigewert_formatieren
from sqlgui_udf import ipv4_to_int, ip_range_aufteilen
from sqlgui_gui import (
    gui_csv_standard_rechtsklick_erweitern,
    gui_csv_tree_neu_aufbauen,
    gui_csv_wrap_status_sicherstellen,
    gui_csv_zelltext_anzeigen,
    gui_set_window_registration_callback,
    gui_set_rahmen_frame_callback,
)

from sqlgui_sql import (
    sql_modul_initialisieren,
    sql_abfrage_fenster_oeffnen,
    sql_ergebnis_als_tabelle_speichern,
    aktives_projekt_laden,
    projekt_aktivieren,
    projekt_deaktivieren,
    projekt_fenster_oeffnen_und_positionieren,
    projekt_view_namen_lesen,
    projekt_view_laden,
    treeview_theme_aus_db_laden,
    sql_editor_hat_ungespeicherte_aenderungen,
    sql_editor_speichern,
)

root = tk.Tk()


def _tkinter_exception_handler(exc_type, exc_value, exc_tb):
    """Fängt alle unbehandelten Tkinter-Callback-Exceptions ab und schreibt sie ins Logging."""
    import traceback
    fehlertext = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        logging_eintrag_schreiben(
            f"Unbehandelte Ausnahme: {exc_type.__name__}\n"
            f". {exc_value}\n"
            + "\n".join(f".. {z}" for z in fehlertext.splitlines() if z.strip()),
            1
        )
    except Exception:
        pass
    # Auch in der Konsole ausgeben
    import sys
    print(fehlertext, file=sys.stderr)


root.report_callback_exception = _tkinter_exception_handler
G_EXE_Title = "SqlGui"
G_Size_Normal = "1200x700"
G_MAX_SPALTEN_BREITE = 500
G_geladene_db_datei = None
GULF_LIGHT_BLUE = "#93DAFE"   # Standardwert – wird durch G_fl_* überschrieben
GULF_DARK_BLUE = "#192C76"
GULF_ORANGE = "#FF7403"
GULF_WHITE = "#FFFFFF"
G_fl_hellblau = "#93DAFE"
G_fl_dunkelblau = "#192C76"
G_fl_orange = "#FF7403"
G_tabellenname = tk.StringVar(root, value="")
G_vorschau_limit = 50
G_csv_fenster = {}
G_csv_import_optionen = {
    "encoding": "auto",
    "delimiter": "auto",
    "header_vorhanden": True,
    "vorschauzeilen": 200,
}

G_DEBUG_AKTIV = False
G_DEBUG_KATEGORIEN = {"vorschau": True, "fenster": True, "allgemein": True}
G_debug_lock = threading.Lock()
G_DEBUG_MAX_EINTRAEGE = 10000

G_TABELLE_LOGGING = "zzz_Logging"
G_TABELLE_DEBUG = "zzz_Debug"
G_TABELLE_KONFIGURATION = "zzz_Konfiguration"
G_TABELLE_SQL_ABFRAGEN = "zzz_SQL_ABFRAGEN"
G_TABELLE_PROJEKTE_SCHUTZ = "zzz_Projekte"
G_TABELLE_FINDINGS = "zzz_Findings"
G_TABELLE_RELATIONEN = "zzz_Relationen"
G_GESCHUETZTE_TABELLEN = {G_TABELLE_LOGGING.upper(), G_TABELLE_DEBUG.upper(), G_TABELLE_KONFIGURATION.upper(), G_TABELLE_SQL_ABFRAGEN.upper(), G_TABELLE_PROJEKTE_SCHUTZ.upper(), G_TABELLE_FINDINGS.upper(), G_TABELLE_RELATIONEN.upper()}
G_GESCHUETZTE_AKTIONEN = {"umbenennen", "kopieren", "leeren", "löschen", "editieren"}
_ADMIN_KONFIG_BEREICH = "Admin"
G_tabellenfenster = {}
G_tabellenfenster_nach_name = {}
G_tabellen_cache = {}
G_rahmenfarbe = ""
G_rahmenfarbe2 = ""
G_rahmenfarbe3 = ""
G_rahmenhoehe = 4
G_rahmen_frames = {}
G_rahmen_frames2 = {}
G_rahmen_frames3 = {}

# Aktuell aktives Farbthema (für neu geöffnete Tabellenfenster)
G_aktuelles_theme_bg     = "white"
G_aktuelles_theme_fg     = "black"
G_aktuelles_theme_sel_bg = "#0078D7"
G_aktuelles_theme_sel_fg = "white"

G_chunk_groesse = 2000
G_db_fetch_groesse = 5000
G_spaltenbreite_update_schritt = 50000
G_fenster_insert_update_schritt = 20000
G_doppelklick_verzoegerung = 250
G_einfachklick_job = None
G_vorschau_queue = queue.Queue()
G_vorschau_laeuft = False
G_letzte_vorschau_tabelle = None
G_angeforderte_vorschau_tabelle = None
G_vorschau_request_id = 0
G_vorschau_after_id = None
G_vorschau_startzeit = None


G_fensterliste_fenster = None
G_fenster_registry = {}
G_fenster_counter = 0
G_fensterliste_auto_refresh_aktiv = False
G_fensterliste_aktives_fenster_id = None
G_fensterliste_debug_snapshot = None

G_aktives_projekt = None          # Projektname des aktiven Projekts, oder None
G_projekt_menue_index = None      # Position des Projektnamens in der Menüleiste


def fensterliste_auto_refresh_starten():
    global G_fensterliste_auto_refresh_aktiv
    if G_fensterliste_auto_refresh_aktiv:
        return
    G_fensterliste_auto_refresh_aktiv = True

    def _tick():
        global G_fensterliste_auto_refresh_aktiv
        daten = G_fensterliste_fenster
        if not daten:
            G_fensterliste_auto_refresh_aktiv = False
            return
        fenster = daten.get("fenster")
        try:
            if fenster is None or not fenster.winfo_exists():
                G_fensterliste_auto_refresh_aktiv = False
                return
        except Exception:
            G_fensterliste_auto_refresh_aktiv = False
            return
        fensterliste_aktualisieren()
        fenster.after(400, _tick)

    root.after(400, _tick)


def fenster_registry_naechste_id():
    global G_fenster_counter
    G_fenster_counter += 1
    return f"window_{G_fenster_counter}"


def fenster_registry_aufraeumen():
    loeschen = []
    for fenster_id, daten in list(G_fenster_registry.items()):
        fenster = daten.get("fenster")
        try:
            if fenster is None or not fenster.winfo_exists():
                loeschen.append(fenster_id)
        except Exception:
            loeschen.append(fenster_id)
    for fenster_id in loeschen:
        G_fenster_registry.pop(fenster_id, None)


def fensterliste_aktualisieren():
    global G_fensterliste_fenster, G_fensterliste_aktives_fenster_id, G_fensterliste_debug_snapshot
    fenster_registry_aufraeumen()
    daten = G_fensterliste_fenster
    if not daten:
        return
    fenster = daten.get("fenster")
    treewidget = daten.get("tree")
    try:
        if fenster is None or treewidget is None or not fenster.winfo_exists():
            G_fensterliste_fenster = None
            return
    except Exception:
        G_fensterliste_fenster = None
        return

    try:
        fenster.title(f"{G_EXE_Title} {__version__} - FENSTERLISTE")
    except Exception:
        pass

    aktives_fenster_id = G_fensterliste_aktives_fenster_id
    try:
        fokus_widget = root.focus_displayof()
        if fokus_widget is not None:
            top_fenster = fokus_widget.winfo_toplevel()
            for fid, info in G_fenster_registry.items():
                if info.get("fenster") is top_fenster:
                    aktives_fenster_id = fid
                    G_fensterliste_aktives_fenster_id = fid
                    break
    except Exception:
        aktives_fenster_id = None

    bisherige_auswahl = treewidget.selection()
    selektiert = aktives_fenster_id or (bisherige_auswahl[0] if bisherige_auswahl else None)
    treewidget.delete(*treewidget.get_children())

    eintraege = []
    for fenster_id, info in G_fenster_registry.items():
        fenster_obj = info.get("fenster")
        try:
            if fenster_obj is None or not fenster_obj.winfo_exists():
                continue
            titel = info.get("titel") or fenster_obj.title() or ""
            fenstertyp = info.get("typ") or "Fenster"
            status = fenster_obj.state()
            eintraege.append((fenster_id, fenstertyp, titel, status))
        except Exception:
            continue

    eintraege.sort(key=lambda item: (str(item[1]).lower(), str(item[2]).lower(), str(item[0]).lower()))
    treewidget.tag_configure("standard", background=G_fl_hellblau, foreground=G_fl_dunkelblau)
    treewidget.tag_configure("hauptfenster", background=G_fl_hellblau, foreground=G_fl_dunkelblau)

    for fenster_id, fenstertyp, titel, status in eintraege:
        tag = "hauptfenster" if fenstertyp == "Hauptfenster" else "standard"
        treewidget.insert("", "end", iid=fenster_id, values=(fenstertyp, titel, status), tags=(tag,))

    if selektiert and treewidget.exists(selektiert):
        treewidget.selection_set(selektiert)
        treewidget.focus(selektiert)
        treewidget.see(selektiert)

    try:
        neuer_snapshot = (
            selektiert,
            tuple((fenster_id, fenstertyp, titel, status) for fenster_id, fenstertyp, titel, status in eintraege),
        )
        if neuer_snapshot != G_fensterliste_debug_snapshot:
            G_fensterliste_debug_snapshot = neuer_snapshot
            debug_eintraege = " | ".join(
                f"{fenster_id}:{fenstertyp}:{status}:{titel}"
                for fenster_id, fenstertyp, titel, status in eintraege
            )
            debug_log(
                f"Fensterliste aktualisiert: selektiert={selektiert}, "
                f"anzahl={len(eintraege)}, eintraege=[{debug_eintraege}]",
                "fenster"
            )
    except Exception as e:
        debug_log(f"Fensterliste-Debug fehlgeschlagen: {e}", "fenster")


def fenster_titel_update(fenster_id):
    daten = G_fenster_registry.get(fenster_id)
    if not daten:
        return
    fenster = daten.get("fenster")
    try:
        if fenster is not None and fenster.winfo_exists():
            daten["titel"] = fenster.title()
    except Exception:
        pass
    fensterliste_aktualisieren()


def fenster_registrieren(fenster, fenstertyp, titel=None, schliessen_callback=None):
    if fenster is None:
        return None

    for vorhandene_id, info in list(G_fenster_registry.items()):
        if info.get("fenster") is fenster:
            if fenstertyp:
                info["typ"] = fenstertyp
            if titel is not None:
                info["titel"] = titel
                try:
                    if fenster.winfo_exists() and titel != fenster.title():
                        fenster.title(titel)
                except Exception:
                    pass
            if callable(schliessen_callback):
                info["schliessen_callback"] = schliessen_callback
            fensterliste_aktualisieren()
            return vorhandene_id

    if titel is not None:
        try:
            fenster.title(titel)
        except Exception:
            pass

    fenster_id = fenster_registry_naechste_id()
    G_fenster_registry[fenster_id] = {
        "fenster": fenster,
        "typ": fenstertyp or "Fenster",
        "titel": titel if titel is not None else "",
        "schliessen_callback": schliessen_callback if callable(schliessen_callback) else None,
    }

    def _destroy_event(event, fid=fenster_id, ref=fenster):
        if event.widget is ref:
            fenster_deregistrieren(fid)

    try:
        fenster.bind("<Destroy>", _destroy_event, add="+")
        fenster.bind("<Map>", lambda event: fensterliste_aktualisieren(), add="+")
        fenster.bind("<Unmap>", lambda event: fensterliste_aktualisieren(), add="+")
        fenster.bind("<FocusIn>", lambda event, fid=fenster_id: fenster_fokus_merker(fid), add="+")
        fenster.bind("<Configure>", lambda event, fid=fenster_id: fenster_titel_update(fid), add="+")
    except Exception:
        pass

    fenster_titel_update(fenster_id)

    # Neues Fenster sofort im aktiven Dunkel-Theme einfärben.
    # after(50) → Widgets sind dann bereits gebaut (Registrierung erfolgt vor Widget-Aufbau).
    _tbg = G_aktuelles_theme_bg
    if _tbg not in ("white", "#ffffff", "#f0f0f0"):
        try:
            _fl_ref = G_fensterliste_fenster.get("fenster") if G_fensterliste_fenster else None
        except Exception:
            _fl_ref = None
        if fenster is not _fl_ref:
            def _theme_auf_neues_fenster(
                w=fenster,
                bg=_tbg,
                fg=G_aktuelles_theme_fg,
                sel_bg=G_aktuelles_theme_sel_bg,
                sel_fg=G_aktuelles_theme_sel_fg,
            ):
                try:
                    if w.winfo_exists():
                        # skip_ids zur Laufzeit aufbauen: Nach 50 ms sind alle
                        # Stripe-Frames (inkl. des neu geöffneten Fensters) bereits
                        # in G_rahmen_frames eingetragen → Streifen bleiben erhalten.
                        _sids = set()
                        for _d in (G_rahmen_frames, G_rahmen_frames2, G_rahmen_frames3):
                            for _rf in _d.values():
                                try:
                                    _sids.add(id(_rf))
                                except Exception:
                                    pass
                        _fenster_einfaerben(w, bg, fg, sel_bg, sel_fg, frozenset(_sids))
                        _fenster_menu_einfaerben(w, bg, fg, sel_bg, sel_fg)
                except Exception:
                    pass
            try:
                fenster.after(50, _theme_auf_neues_fenster)
            except Exception:
                pass

    return fenster_id


def fenster_schliessen_callback_setzen(fenster, schliessen_callback):
    if fenster is None or not callable(schliessen_callback):
        return False
    for daten in G_fenster_registry.values():
        if daten.get("fenster") is fenster:
            daten["schliessen_callback"] = schliessen_callback
            return True
    return False


def fenster_fokus_merker(fenster_id):
    global G_fensterliste_aktives_fenster_id
    G_fensterliste_aktives_fenster_id = fenster_id
    fensterliste_aktualisieren()


def fenster_deregistrieren(fenster_id):
    if fenster_id in G_fenster_registry:
        G_fenster_registry.pop(fenster_id, None)
        fensterliste_aktualisieren()


def fenster_aktivieren(fenster_id):
    global G_fensterliste_aktives_fenster_id
    daten = G_fenster_registry.get(fenster_id)
    if not daten:
        return False
    fenster = daten.get("fenster")
    try:
        if fenster is None or not fenster.winfo_exists():
            fenster_deregistrieren(fenster_id)
            return False
        # Alle anderen maximierten/fullscreen Fenster zuerst normalisieren
        for fid, fdaten in list(G_fenster_registry.items()):
            if fid == fenster_id:
                continue
            anderes_fenster = fdaten.get("fenster")
            try:
                if anderes_fenster and anderes_fenster.winfo_exists():
                    if bool(anderes_fenster.attributes("-fullscreen")):
                        anderes_fenster.attributes("-fullscreen", False)
                    elif anderes_fenster.state() == "zoomed":
                        anderes_fenster.state("normal")
            except Exception:
                pass
        # Auch Hauptfenster normalisieren falls maximiert oder fullscreen
        try:
            if root.state() == "zoomed" and fenster != root:
                root.state("normal")
        except Exception:
            pass
        if fenster.state() in ("iconic", "withdrawn"):
            fenster.deiconify()
        fenster.lift()
        try:
            fenster.focus_force()
        except Exception:
            fenster.focus_set()
        G_fensterliste_aktives_fenster_id = fenster_id
        daten["titel"] = fenster.title()
        fensterliste_aktualisieren()
        return True
    except Exception:
        fenster_deregistrieren(fenster_id)
        return False


def alle_fenster_nach_vorne():
    # Im Projektmodus: gespeicherte Positionen laden (löst Fullscreen-Probleme)
    if G_aktives_projekt:
        projekt_fenster_oeffnen_und_positionieren(G_aktives_projekt)
        fensterliste_aktualisieren()
        return
    fenster_registry_aufraeumen()
    for fenster_id in list(G_fenster_registry.keys()):
        daten = G_fenster_registry.get(fenster_id)
        if not daten:
            continue
        fenster = daten.get("fenster")
        try:
            if fenster is None or not fenster.winfo_exists():
                fenster_deregistrieren(fenster_id)
                continue
            if fenster.state() in ("iconic", "withdrawn"):
                fenster.deiconify()
            fenster.lift()
        except Exception:
            fenster_deregistrieren(fenster_id)
    try:
        root.lift()
    except Exception:
        pass
    fensterliste_aktualisieren()


def fensterliste_auswahl_aktivieren(event=None):
    daten = G_fensterliste_fenster
    if not daten:
        return
    treewidget = daten.get("tree")
    if treewidget is None:
        return
    auswahl = treewidget.selection()
    if not auswahl:
        return
    fenster_aktivieren(auswahl[0])


def fensterliste_doppelklick(event):
    daten = G_fensterliste_fenster
    if not daten:
        return
    treewidget = daten.get("tree")
    if treewidget is None:
        return
    item_id = treewidget.identify_row(event.y)
    if not item_id:
        return
    treewidget.selection_set(item_id)
    treewidget.focus(item_id)
    fenster_aktivieren(item_id)


def fensterliste_schliessen():
    global G_fensterliste_fenster
    daten = G_fensterliste_fenster
    G_fensterliste_fenster = None
    if not daten:
        return
    fenster = daten.get("fenster")
    try:
        if fenster is not None and fenster.winfo_exists():
            fenster.destroy()
    except Exception:
        pass


def fensterliste_farben_setzen(hellblau, dunkelblau, orange):
    """Setzt die drei Fensterliste-Farben, speichert sie und öffnet die FL neu."""
    global G_fl_hellblau, G_fl_dunkelblau, G_fl_orange
    G_fl_hellblau = hellblau or "#93DAFE"
    G_fl_dunkelblau = dunkelblau or "#192C76"
    G_fl_orange = orange or "#FF7403"
    try:
        konfiguration_wert_speichern("Fensterliste", "farbe_hellblau", G_fl_hellblau)
        konfiguration_wert_speichern("Fensterliste", "farbe_dunkelblau", G_fl_dunkelblau)
        konfiguration_wert_speichern("Fensterliste", "farbe_orange", G_fl_orange)
    except Exception:
        pass
    # Fensterliste schließen und sofort neu öffnen (damit Farben sofort sichtbar)
    war_offen = bool(G_fensterliste_fenster)
    fensterliste_schliessen()
    if war_offen:
        root.after(50, fensterliste_anzeigen)


def datenbankwechsel_arbeitsfenster_schliessen():
    """Schliesst vor einem DB-Wechsel alle Arbeitsfenster.

    Fenster mit eigener Schliessen-Logik duerfen den Wechsel abbrechen,
    z.B. wenn ungespeicherte SQL-Aenderungen nicht verworfen werden sollen.
    """
    fensterliste_schliessen()
    fenster_registry_aufraeumen()

    for fenster_id, daten in list(G_fenster_registry.items()):
        fenstertyp = daten.get("typ") or "Fenster"
        if fenstertyp == "Hauptfenster":
            continue

        fenster = daten.get("fenster")
        try:
            if fenster is None or not fenster.winfo_exists():
                fenster_deregistrieren(fenster_id)
                continue
        except Exception:
            fenster_deregistrieren(fenster_id)
            continue

        schliessen_callback = daten.get("schliessen_callback")
        try:
            if callable(schliessen_callback):
                schliessen_callback()
            else:
                fenster.destroy()
        except Exception as e:
            debug_log(f"Fenster konnte beim Datenbankwechsel nicht geschlossen werden: typ={fenstertyp}, fehler={e}", "fenster")
            try:
                fenster.destroy()
            except Exception:
                pass

        try:
            root.update_idletasks()
        except Exception:
            pass

        try:
            if fenster.winfo_exists():
                debug_log(f"Datenbankwechsel abgebrochen: Fenster blieb offen: typ={fenstertyp}, titel={fenster.title()}", "fenster")
                return False
        except Exception:
            pass

    fenster_registry_aufraeumen()
    return True


def datenbankwechsel_vorbereiten(neue_db_datei):
    if not G_geladene_db_datei:
        return True
    if neue_db_datei == G_geladene_db_datei:
        return True
    debug_log(f"Datenbankwechsel vorbereitet: alt={G_geladene_db_datei}, neu={neue_db_datei}", "fenster")
    if not datenbankwechsel_arbeitsfenster_schliessen():
        messagebox.showinfo(
            "Datenbank laden",
            "Der Datenbankwechsel wurde abgebrochen, weil ein Fenster nicht geschlossen wurde.",
            parent=root,
        )
        return False
    return True


def fensterliste_anzeigen():
    global G_fensterliste_fenster, G_fl_hellblau, G_fl_dunkelblau, G_fl_orange
    # Farben aus Konfig lesen (falls DB geladen)
    try:
        _hb = konfiguration_wert_lesen("Fensterliste", "farbe_hellblau")
        _db = konfiguration_wert_lesen("Fensterliste", "farbe_dunkelblau")
        _or = konfiguration_wert_lesen("Fensterliste", "farbe_orange")
        if _hb: G_fl_hellblau = _hb
        if _db: G_fl_dunkelblau = _db
        if _or: G_fl_orange = _or
    except Exception:
        pass
    if G_fensterliste_fenster:
        fenster = G_fensterliste_fenster.get("fenster")
        try:
            if fenster is not None and fenster.winfo_exists():
                if fenster.state() in ("iconic", "withdrawn"):
                    fenster.deiconify()
                fenster.lift()
                fenster.focus_force()
                fensterliste_aktualisieren()
                return
        except Exception:
            G_fensterliste_fenster = None

    # Alle Fullscreen-Fenster beenden, damit die Fensterliste Fokus bekommen kann
    for _fdaten in list(G_fenster_registry.values()):
        _f = _fdaten.get("fenster")
        try:
            if _f and _f.winfo_exists() and bool(_f.attributes("-fullscreen")):
                _f.attributes("-fullscreen", False)
        except Exception:
            pass

    top = tk.Toplevel(root)
    top.title(f"{G_EXE_Title} {__version__} - FENSTERLISTE")
    top.geometry("820x430")
    top.minsize(620, 320)
    top.configure(bg=G_fl_hellblau)
    fensterliste_menue = fenster_standard_menue_anbringen(top, "820x430", "Fensterliste", fensterliste_menue_anzeigen=False)
    menue_british_racing_green_anwenden(fensterliste_menue)
    # Projekt-Cascade im Fensterliste-Menü (nur bei aktivem Projekt)
    if G_aktives_projekt:
        _fl_pm = tk.Menu(fensterliste_menue, tearoff=0)
        _fl_pname = G_aktives_projekt
        _fl_pm.config(postcommand=lambda m=_fl_pm, p=_fl_pname: _projekt_cascade_aufbauen(m, p))
        fensterliste_menue.add_cascade(label=f"● {_fl_pname}", menu=_fl_pm)

    style = ttk.Style(top)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    _fl_tree_bg = G_fl_hellblau
    style.configure(
        "Gulf.Treeview",
        background=_fl_tree_bg,
        fieldbackground=_fl_tree_bg,
        foreground=G_fl_dunkelblau,
        rowheight=26,
        borderwidth=0,
        font=("Segoe UI", 10, "bold"),
    )
    style.configure(
        "Gulf.Treeview.Heading",
        background=_fl_tree_bg,
        foreground=G_fl_dunkelblau,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padding=(8, 6),
    )
    style.map(
        "Gulf.Treeview",
        background=[("selected", G_fl_orange)],
        foreground=[("selected", G_fl_dunkelblau)],
    )
    style.map(
        "Gulf.Treeview.Heading",
        background=[("active", G_fl_orange)],
        foreground=[("active", G_fl_dunkelblau)],
    )

    kopf = tk.Frame(top, bg=G_fl_hellblau, height=56, bd=0, highlightthickness=0)
    kopf.pack(fill="x", padx=0, pady=0)
    kopf.pack_propagate(False)
    tk.Label(
        kopf,
        text="Fensterliste",
        bg=G_fl_hellblau,
        fg=G_fl_dunkelblau,
        font=("Helvetica", 18, "bold"),
        anchor="w",
    ).pack(side="left", padx=14, pady=10)

    hauptframe = tk.Frame(top, padx=10, pady=10, bg=G_fl_orange, bd=0, highlightthickness=0)
    hauptframe.pack(fill="both", expand=True)
    hauptframe.grid_rowconfigure(1, weight=1)
    hauptframe.grid_columnconfigure(0, weight=1)

    infoframe = tk.Frame(hauptframe, bg=G_fl_orange, bd=0, highlightthickness=0)
    infoframe.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    tk.Label(
        infoframe,
        text="Alle offenen Arbeitsfenster auf einen Blick",
        bg=G_fl_orange,
        fg=G_fl_dunkelblau,
        font=("Helvetica", 11, "bold"),
        anchor="w",
    ).pack(side="left")

    listenframe = tk.Frame(hauptframe, bg=G_fl_hellblau, bd=0, highlightthickness=0)
    listenframe.grid(row=1, column=0, columnspan=2, sticky="nsew")
    listenframe.grid_rowconfigure(0, weight=1)
    listenframe.grid_columnconfigure(0, weight=1)

    treewidget = ttk.Treeview(
        listenframe,
        columns=("typ", "titel", "status"),
        show="headings",
        selectmode="browse",
        style="Gulf.Treeview",
    )
    treewidget.heading("typ", text="Typ")
    treewidget.heading("titel", text="Fenstertitel")
    treewidget.heading("status", text="Status")
    treewidget.column("typ", width=140, anchor="w")
    treewidget.column("titel", width=500, anchor="w")
    treewidget.column("status", width=120, anchor="center")
    treewidget.grid(row=0, column=0, sticky="nsew")

    scrolly = ttk.Scrollbar(listenframe, orient="vertical", command=treewidget.yview)
    scrolly.grid(row=0, column=1, sticky="ns")
    treewidget.configure(yscrollcommand=scrolly.set)

    buttonframe = tk.Frame(hauptframe, bg=G_fl_orange, bd=0, highlightthickness=0)
    buttonframe.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    button_opts = {
        "bg": G_fl_hellblau,
        "fg": G_fl_dunkelblau,
        "activebackground": G_fl_orange,
        "activeforeground": G_fl_dunkelblau,
        "font": ("Helvetica", 11, "bold"),
        "bd": 0,
        "relief": "flat",
        "highlightthickness": 0,
        "padx": 12,
        "pady": 7,
    }

    tk.Button(buttonframe, text="Alle Fenster nach vorne holen", command=alle_fenster_nach_vorne, **button_opts).pack(side="left")
    tk.Button(buttonframe, text="Applikation beenden", command=app_beenden, **button_opts).pack(side="right", padx=12)

    G_fensterliste_fenster = {"fenster": top, "tree": treewidget}
    top.bind("<FocusIn>", lambda event: fensterliste_aktualisieren() if event.widget is top else None, add="+")
    treewidget.bind("<Double-1>", fensterliste_doppelklick, add="+")
    treewidget.bind("<ButtonRelease-1>", fensterliste_auswahl_aktivieren, add="+")
    treewidget.bind("<Return>", fensterliste_auswahl_aktivieren, add="+")
    top.protocol("WM_DELETE_WINDOW", fensterliste_schliessen)

    fensterliste_aktualisieren()


def standard_arbeitsfenster_anzeigen(fenster):
    try:
        if fenster.state() in ("iconic", "withdrawn"):
            fenster.deiconify()
        fenster.lift()
        try:
            fenster.focus_force()
        except Exception:
            fenster.focus_set()
        try:
            fenster.update_idletasks()
        except Exception:
            pass
    except Exception:
        pass


root.geometry(G_Size_Normal)
root.title(f"{G_EXE_Title} {__version__}")
root.minsize(300, 60)
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

fenster_registrieren(root, "Hauptfenster", f"{G_EXE_Title} {__version__}")
gui_set_window_registration_callback(fenster_registrieren)


def app_basis_verzeichnis():
    return Path(__file__).resolve().parent


def unterverzeichnis_sicherstellen(name):
    ziel = app_basis_verzeichnis() / name
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel


def db_verzeichnis_sicherstellen():
    return unterverzeichnis_sicherstellen("DB")


def export_verzeichnis_sicherstellen():
    return unterverzeichnis_sicherstellen("Export")


def csv_verzeichnis_sicherstellen():
    return unterverzeichnis_sicherstellen("CSV")


def externe_apps_verzeichnis_sicherstellen():
    return unterverzeichnis_sicherstellen("ExterneApps")


def externe_programm_kandidaten(
    exe_namen,
    standard_pfade=None,
    ordner_prefixe=None,
    shortcut_namen=None,
    path_namen=None,
    windows_system_fallbacks=None,
):
    standard_pfade = standard_pfade or []
    ordner_prefixe = ordner_prefixe or []
    shortcut_namen = shortcut_namen or []
    path_namen = path_namen or exe_namen
    windows_system_fallbacks = windows_system_fallbacks or []
    kandidaten = []
    gesehen = set()

    def hinzufuegen(wert, muss_existieren=True):
        if not wert:
            return
        text = str(wert)
        key = text.lower()
        if key in gesehen:
            return
        if muss_existieren and not os.path.exists(text):
            return
        gesehen.add(key)
        kandidaten.append(text)

    for pfad in standard_pfade:
        hinzufuegen(pfad)

    for name in path_namen:
        gefunden = shutil.which(name)
        if gefunden:
            hinzufuegen(gefunden)

    externe_apps = externe_apps_verzeichnis_sicherstellen()
    dateinamen = list(exe_namen) + list(shortcut_namen)
    for name in dateinamen:
        hinzufuegen(externe_apps / name)
        if not str(name).lower().endswith(".lnk"):
            hinzufuegen(externe_apps / f"{name}.lnk")

    try:
        for eintrag in externe_apps.iterdir():
            if not eintrag.is_dir():
                continue
            name_lower = eintrag.name.lower()
            if not any(name_lower.startswith(prefix.lower()) for prefix in ordner_prefixe):
                continue
            for dateiname in dateinamen:
                hinzufuegen(eintrag / dateiname)
                if not str(dateiname).lower().endswith(".lnk"):
                    hinzufuegen(eintrag / f"{dateiname}.lnk")
            for link in eintrag.glob("*.lnk"):
                link_lower = link.name.lower()
                if any(link_lower.startswith(exe.lower()) for exe in exe_namen):
                    hinzufuegen(link)
    except Exception:
        pass

    for fallback in windows_system_fallbacks:
        hinzufuegen(fallback, muss_existieren=False)

    return kandidaten


def externe_programm_mit_datei_starten(programmpfad, dateipfad):
    programm = str(programmpfad)
    if programm.lower().endswith(".lnk"):
        if os.name != "nt":
            raise RuntimeError("Windows-Shortcut kann nur unter Windows gestartet werden.")
        subprocess.Popen(["cmd", "/c", "start", "", programm, str(dateipfad)])
    else:
        subprocess.Popen([programm, str(dateipfad)])


def debug_tabelle_anlegen():
    if not db_ist_geladen():
        return
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_DEBUG)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            kategorie TEXT NOT NULL,
            meldung TEXT NOT NULL
        )
        """
    )
    verbindung.commit()
    verbindung.close()


def debug_log_in_db_schreiben(text, kategorie="allgemein"):
    if not db_ist_geladen():
        return
    verbindung = None
    try:
        debug_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"INSERT INTO {sql_identifier(G_TABELLE_DEBUG)} (datetime, kategorie, meldung) VALUES (?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], str(kategorie), str(text)),
        )
        cursor.execute(
            f"""
            DELETE FROM {sql_identifier(G_TABELLE_DEBUG)}
            WHERE id NOT IN (
                SELECT id
                FROM {sql_identifier(G_TABELLE_DEBUG)}
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (G_DEBUG_MAX_EINTRAEGE,),
        )
        verbindung.commit()
    except Exception:
        pass
    finally:
        try:
            if verbindung is not None:
                verbindung.close()
        except Exception:
            pass


def debug_log(text, kategorie="allgemein"):
    if not G_DEBUG_AKTIV:
        return
    if kategorie not in G_DEBUG_KATEGORIEN or not G_DEBUG_KATEGORIEN.get(kategorie, False):
        return
    try:
        zeit = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with G_debug_lock:
            print(f"[DEBUG][{zeit}][{kategorie}] {text}", flush=True)
            debug_log_in_db_schreiben(text, kategorie)
    except Exception:
        pass


def debug_set_aktiv(aktiv=True):
    global G_DEBUG_AKTIV
    G_DEBUG_AKTIV = bool(aktiv)
    print(f"[DEBUG] Debug-Modus {'aktiv' if G_DEBUG_AKTIV else 'inaktiv'}")


def debug_toggle():
    debug_set_aktiv(not G_DEBUG_AKTIV)


def datenbank_komprimieren():
    """VACUUM mit Backup, Live-Seitenzähler und Vorher/Nachher-Vergleich."""
    if not db_ist_geladen():
        messagebox.showwarning("Datenbank komprimieren", "Bitte zuerst eine Datenbank laden.", parent=root)
        return

    db_pfad = G_geladene_db_datei
    db_groesse_vorher = os.path.getsize(db_pfad)
    db_groesse_vorher_mb = db_groesse_vorher / (1024 * 1024)

    # Bestätigung mit Größenanzeige
    if not messagebox.askyesno(
        "Datenbank komprimieren",
        f"Aktuelle Dateigröße: {db_groesse_vorher_mb:.2f} MB\n\n"
        f"Vor dem Komprimieren wird ein Backup angelegt.\n"
        f"Bei großen Datenbanken kann dieser Vorgang einige Minuten dauern.\n\n"
        f"Jetzt komprimieren?",
        parent=root
    ):
        return

    # Backup anlegen
    backup_name = f"{os.path.splitext(os.path.basename(db_pfad))[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_pfad = os.path.join(os.path.dirname(db_pfad), backup_name)
    try:
        import shutil
        shutil.copy2(db_pfad, backup_pfad)
        backup_groesse = os.path.getsize(backup_pfad) / (1024 * 1024)
        debug_log(f"VACUUM Backup angelegt: {backup_pfad} ({backup_groesse:.2f} MB)", "allgemein")
    except Exception as e:
        messagebox.showerror("Backup-Fehler", f"Backup konnte nicht angelegt werden:\n{e}\n\nVACUUM wird abgebrochen.", parent=root)
        return

    # Fortschrittsfenster
    progress_fenster = tk.Toplevel(root)
    progress_fenster.title("Datenbank komprimieren")
    progress_fenster.geometry("420x180")
    progress_fenster.resizable(False, False)
    progress_fenster.grab_set()
    progress_fenster.transient(root)

    tk.Label(progress_fenster, text=f"Backup angelegt: {backup_name}", anchor="w", fg="green").pack(fill="x", padx=16, pady=(16, 4))
    tk.Label(progress_fenster, text="VACUUM läuft...", anchor="w").pack(fill="x", padx=16)
    seiten_var = tk.StringVar(value="Verarbeitet: 0 Seiten")
    tk.Label(progress_fenster, textvariable=seiten_var, anchor="w", fg="gray").pack(fill="x", padx=16, pady=(4, 0))
    status_var = tk.StringVar(value="Bitte warten...")
    tk.Label(progress_fenster, textvariable=status_var, anchor="w").pack(fill="x", padx=16, pady=(8, 0))

    seiten_zaehler = [0]
    fertig = [False]
    fehler = [None]

    def vacuum_thread():
        try:
            verbindung = sqlite3.connect(db_pfad)
            zaehler_ref = [0]

            def progress_callback():
                zaehler_ref[0] += 1
                seiten_zaehler[0] = zaehler_ref[0]

            verbindung.set_progress_handler(progress_callback, 100)
            verbindung.execute("VACUUM")
            verbindung.close()
        except Exception as e:
            fehler[0] = str(e)
        finally:
            fertig[0] = True

    def fortschritt_aktualisieren():
        if not fertig[0]:
            seiten_var.set(f"Verarbeitet: {seiten_zaehler[0]:,} Seiten")
            progress_fenster.after(200, fortschritt_aktualisieren)
        else:
            progress_fenster.destroy()
            if fehler[0]:
                logging_eintrag_schreiben(f"VACUUM fehlgeschlagen: {fehler[0]}", 1)
                messagebox.showerror("Komprimieren fehlgeschlagen", f"VACUUM fehlgeschlagen:\n{fehler[0]}", parent=root)
            else:
                db_groesse_nachher = os.path.getsize(db_pfad)
                db_groesse_nachher_mb = db_groesse_nachher / (1024 * 1024)
                gespart_mb = db_groesse_vorher_mb - db_groesse_nachher_mb
                log_meldung = (
                    f"Datenbank komprimiert: {os.path.basename(db_pfad)}\n"
                    f". Vorher: {db_groesse_vorher_mb:.2f} MB\n"
                    f". Nachher: {db_groesse_nachher_mb:.2f} MB\n"
                    f".. Gespart: {gespart_mb:.2f} MB\n"
                    f".. Backup: {backup_name}"
                )
                logging_eintrag_schreiben(log_meldung, 0)
                messagebox.showinfo(
                    "Datenbank komprimiert",
                    f"VACUUM abgeschlossen!\n\n"
                    f"Vorher:  {db_groesse_vorher_mb:.2f} MB\n"
                    f"Nachher: {db_groesse_nachher_mb:.2f} MB\n"
                    f"Gespart: {gespart_mb:.2f} MB\n\n"
                    f"Backup: {backup_name}",
                    parent=root
                )

    import threading as _threading
    _threading.Thread(target=vacuum_thread, daemon=True).start()
    progress_fenster.after(200, fortschritt_aktualisieren)


# ---------------------------------------------------------------------------
# Projekt-Aktivierung und Hauptfenster-Modus
# ---------------------------------------------------------------------------

def projekt_ist_logging_tabelle(tabellenname):
    """Gibt True zurück wenn der Tabellenname eine Logging-Tabelle ist."""
    if not tabellenname:
        return False
    name_lower = tabellenname.strip().lower()
    if name_lower == G_TABELLE_LOGGING.lower():
        return True
    if name_lower == G_TABELLE_DEBUG.lower():
        return True
    if name_lower == G_TABELLE_FINDINGS.lower():
        return True
    # Projekt-Log-Tabellen: zzz_<Name>Log
    if name_lower.startswith("zzz_") and name_lower.endswith("log"):
        return True
    return False


def _admin_code_hash_lesen():
    """Gibt (hash_hex, salt_hex) aus zzz_Konfiguration zurück, oder (None, None)."""
    h = konfiguration_wert_lesen(_ADMIN_KONFIG_BEREICH, "code_hash")
    s = konfiguration_wert_lesen(_ADMIN_KONFIG_BEREICH, "code_salt")
    return (h, s) if h and s else (None, None)


def _admin_code_hash_schreiben(code):
    """Hasht code mit pbkdf2_hmac (SHA-256, 100 000 Runden) und speichert in DB."""
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, 100_000)
    konfiguration_wert_speichern(_ADMIN_KONFIG_BEREICH, "code_salt", salt.hex())
    konfiguration_wert_speichern(_ADMIN_KONFIG_BEREICH, "code_hash", h.hex())


def _admin_code_pruefen(eingabe):
    """True wenn eingabe mit gespeichertem Hash übereinstimmt."""
    hash_hex, salt_hex = _admin_code_hash_lesen()
    if not hash_hex:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        erwarteter_hash = hashlib.pbkdf2_hmac(
            "sha256", eingabe.encode("utf-8"), salt, 100_000
        )
        return erwarteter_hash.hex() == hash_hex
    except Exception:
        return False


def _admin_code_einrichten_dialog():
    """Einmalige Ersteinrichtung des Admin-Codes für diese Datenbank.
    Gibt True zurück wenn Code gesetzt wurde, False wenn abgebrochen."""
    messagebox.showinfo(
        "Admin-Code einrichten",
        "Für diese Datenbank wurde noch kein Admin-Code festgelegt.\n\n"
        "Bitte jetzt einen Admin-Code festlegen (mindestens 4 Zeichen).",
        parent=root,
    )
    while True:
        code = simpledialog.askstring(
            "Admin-Code einrichten",
            "Neuer Admin-Code:",
            parent=root,
            show="*",
        )
        if code is None:
            return False
        code = code.strip()
        if len(code) < 4:
            messagebox.showwarning(
                "Admin-Code einrichten",
                "Bitte mindestens 4 Zeichen verwenden.",
                parent=root,
            )
            continue
        bestaetigung = simpledialog.askstring(
            "Admin-Code einrichten",
            "Code zur Bestätigung erneut eingeben:",
            parent=root,
            show="*",
        )
        if bestaetigung is None:
            return False
        if bestaetigung.strip() != code:
            messagebox.showwarning(
                "Admin-Code einrichten",
                "Codes stimmen nicht überein. Bitte erneut versuchen.",
                parent=root,
            )
            continue
        _admin_code_hash_schreiben(code)
        messagebox.showinfo(
            "Admin-Code einrichten",
            "Admin-Code wurde gesetzt.",
            parent=root,
        )
        return True


def admin_code_aendern_dialog():
    """Lässt den Benutzer den Admin-Code nach Eingabe des alten Codes ändern."""
    if not db_ist_geladen():
        messagebox.showwarning("Admin-Code ändern", "Bitte zuerst eine Datenbank laden.", parent=root)
        return
    hash_hex, _ = _admin_code_hash_lesen()
    if not hash_hex:
        _admin_code_einrichten_dialog()
        return
    alter = simpledialog.askstring(
        "Admin-Code ändern",
        "Aktuellen Admin-Code eingeben:",
        parent=root,
        show="*",
    )
    if alter is None:
        return
    if not _admin_code_pruefen(alter.strip()):
        messagebox.showwarning("Admin-Code ändern", "Falscher Code.", parent=root)
        return
    while True:
        neu = simpledialog.askstring(
            "Admin-Code ändern",
            "Neuer Admin-Code (mindestens 4 Zeichen):",
            parent=root,
            show="*",
        )
        if neu is None:
            return
        neu = neu.strip()
        if len(neu) < 4:
            messagebox.showwarning("Admin-Code ändern", "Bitte mindestens 4 Zeichen verwenden.", parent=root)
            continue
        bestaetigung = simpledialog.askstring(
            "Admin-Code ändern",
            "Neuen Code zur Bestätigung wiederholen:",
            parent=root,
            show="*",
        )
        if bestaetigung is None:
            return
        if bestaetigung.strip() != neu:
            messagebox.showwarning("Admin-Code ändern", "Codes stimmen nicht überein.", parent=root)
            continue
        _admin_code_hash_schreiben(neu)
        messagebox.showinfo("Admin-Code ändern", "Admin-Code wurde geändert.", parent=root)
        return


def adminzugang_dialog():
    """Fragt den Admin-Code ab. Gibt True zurück bei richtigem Code."""
    # Ersteinrichtung falls noch kein Hash in der DB
    hash_hex, _ = _admin_code_hash_lesen()
    if not hash_hex:
        if not _admin_code_einrichten_dialog():
            return False
    code = simpledialog.askstring(
        "Adminzugang",
        "Bitte Admin-Code eingeben:",
        parent=root,
        show="*",
    )
    if code is None:
        return False
    if _admin_code_pruefen(code.strip()):
        return True
    messagebox.showwarning("Adminzugang", "Falscher Code.", parent=root)
    return False


def hauptfenster_projekt_modus_setzen(aktiv, projektname=None):
    """Schaltet den Projekt-Modus im Hauptfenster ein oder aus.

    aktiv=True  → Tabellen/CSV/SQL ausblenden, Projektname in Menüleiste
    aktiv=False → Normalzustand wiederherstellen
    """
    global G_aktives_projekt, G_projekt_menue_index

    if aktiv and projektname:
        G_aktives_projekt = projektname
        # Menüeinträge ausblenden
        try:
            menueleiste.entryconfigure("Tabelle", state="disabled")
        except Exception:
            pass
        try:
            menueleiste.entryconfigure("CSV", state="disabled")
        except Exception:
            pass
        try:
            menueleiste.entryconfigure("SQL", state="disabled")
        except Exception:
            pass
        # Datei-Menü: nur Debug, Adminzugang, Beenden
        try:
            menudatei.entryconfigure("DB laden", state="disabled")
        except Exception:
            pass
        # Tabellenliste und Vorschau ausblenden
        try:
            main_paned.pack_forget()
        except Exception:
            pass
        # Projektname als Cascade-Menü in Menüleiste eintragen
        try:
            _pm = tk.Menu(menueleiste, tearoff=0)
            _pm.config(postcommand=lambda m=_pm, p=projektname: _projekt_cascade_aufbauen(m, p))
            menueleiste.add_cascade(label=f"● {projektname}", menu=_pm)
            G_projekt_menue_index = menueleiste.index("end")
        except Exception:
            pass
        # Adminzugang im Datei-Menü anzeigen
        try:
            menudatei.entryconfigure("Adminzugang", state="normal")
        except Exception:
            # Eintrag noch nicht vorhanden – anlegen
            menudatei.add_separator()
            menudatei.add_command(label="Adminzugang", command=adminzugang_entsperren)
        fenstertitel_aktualisieren()
        debug_log(f"Projekt-Modus aktiviert: projektname={projektname}", "allgemein")

    else:
        G_aktives_projekt = None
        # Menüeinträge wieder einblenden
        try:
            menueleiste.entryconfigure("Tabelle", state="normal")
        except Exception:
            pass
        try:
            menueleiste.entryconfigure("CSV", state="normal")
        except Exception:
            pass
        try:
            menueleiste.entryconfigure("SQL", state="normal")
        except Exception:
            pass
        try:
            menudatei.entryconfigure("DB laden", state="normal")
        except Exception:
            pass
        # Tabellenliste und Vorschau wieder einblenden
        try:
            main_paned.pack(fill="both", expand=True)
        except Exception:
            pass
        # Projektname aus Menüleiste entfernen
        if G_projekt_menue_index is not None:
            try:
                menueleiste.delete(G_projekt_menue_index)
            except Exception:
                pass
            G_projekt_menue_index = None
        fenstertitel_aktualisieren()
        debug_log("Projekt-Modus deaktiviert", "allgemein")


def adminzugang_entsperren():
    """Admin-Code prüfen und bei Erfolg Projekt-Modus deaktivieren."""
    if not adminzugang_dialog():
        return
    try:
        projekt_deaktivieren()
    except Exception:
        pass
    hauptfenster_projekt_modus_setzen(False)
    logging_eintrag_schreiben("Adminzugang: Projekt-Modus deaktiviert", 0)


def projekt_fenster_oeffnen():
    """Öffnet alle Workflow-Fenster des aktiven Projekts und stellt Positionen wieder her.
    Wird vom Hauptfenster-Menü aufgerufen — ignoriert Startview, lädt immer Admin-Ansicht."""
    if not G_aktives_projekt:
        return
    projekt_fenster_oeffnen_und_positionieren(G_aktives_projekt, ignore_startview=True)


def alle_workflow_tabellen_schliessen(projektname):
    """Schließt alle offenen Tabellenfenster (für View-Wechsel)."""
    for fenster_id in list(G_tabellenfenster.keys()):
        try:
            tabellenfenster_schliessen(fenster_id)
        except Exception:
            pass


def sql_fenster_mit_admincode_oeffnen():
    """SQL-Fenster öffnen — erst prüfen ob schon offen, dann ggf. Admin-Code."""
    from sqlgui_sql import _sql_abfrage_fenster_instanz
    try:
        if _sql_abfrage_fenster_instanz is not None and _sql_abfrage_fenster_instanz.winfo_exists():
            # Bereits offen → einfach nach vorne holen, kein Code nötig
            if _sql_abfrage_fenster_instanz.state() in ("iconic", "withdrawn"):
                _sql_abfrage_fenster_instanz.deiconify()
            _sql_abfrage_fenster_instanz.lift()
            _sql_abfrage_fenster_instanz.focus_force()
            return
    except Exception:
        pass
    # Noch nicht offen → Admin-Code abfragen
    if not adminzugang_dialog():
        return
    sql_abfrage_fenster_oeffnen()


def _projekt_cascade_aufbauen(menue, projektname):
    """Befüllt das Projekt-Untermenü mit Views + Admin-Einträgen."""
    menue.delete(0, "end")
    try:
        views = projekt_view_namen_lesen(projektname)
    except Exception:
        views = []
    for vname in views:
        menue.add_command(
            label=vname,
            command=lambda v=vname: projekt_view_laden(projektname, v),
        )
    if views:
        menue.add_separator()
    menue.add_command(label="Admin SQL Ansicht laden",
                      command=projekt_fenster_oeffnen)
    menue.add_command(label="Admin SQL-Editor öffnen",
                      command=sql_fenster_mit_admincode_oeffnen)


def projekt_beim_start_pruefen():
    """Beim DB-Laden prüfen ob ein Projekt aktiv ist, Modus setzen und Fenster öffnen."""
    try:
        name = aktives_projekt_laden()
        if name:
            hauptfenster_projekt_modus_setzen(True, name)
            projekt_fenster_oeffnen_und_positionieren(name)
        else:
            hauptfenster_projekt_modus_setzen(False)
    except Exception as e:
        debug_log(f"Projekt-Start-Prüfung fehlgeschlagen: {e}", "allgemein")


def konfiguration_tabelle_anlegen():
    if not db_ist_geladen():
        return
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_KONFIGURATION)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            bereich TEXT NOT NULL,
            schluessel TEXT NOT NULL,
            wert TEXT,
            UNIQUE(bereich, schluessel)
        )
        """
    )
    verbindung.commit()
    # Prüfen ob UNIQUE(bereich, schluessel) noch vorhanden ist
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (G_TABELLE_KONFIGURATION,),
    )
    row = cursor.fetchone()
    hat_unique = row and "UNIQUE" in (row[0] or "").upper()
    verbindung.close()
    if not hat_unique:
        _konfiguration_tabelle_reparieren()


def _konfiguration_tabelle_reparieren():
    """Stellt UNIQUE(bereich, schluessel) in zzz_Konfiguration wieder her."""
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        tmp = G_TABELLE_KONFIGURATION + "_repair_tmp"
        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(tmp)}")
        cursor.execute(
            f"""
            CREATE TABLE {sql_identifier(tmp)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT,
                bereich TEXT NOT NULL,
                schluessel TEXT NOT NULL,
                wert TEXT,
                UNIQUE(bereich, schluessel)
            )
            """
        )
        # Daten übernehmen; bei Duplikaten in (bereich, schluessel) den neuesten Eintrag behalten
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {sql_identifier(tmp)} (id, datetime, bereich, schluessel, wert)
            SELECT id, datetime, bereich, schluessel, wert
            FROM {sql_identifier(G_TABELLE_KONFIGURATION)}
            ORDER BY id
            """
        )
        cursor.execute(f"DROP TABLE {sql_identifier(G_TABELLE_KONFIGURATION)}")
        cursor.execute(f"ALTER TABLE {sql_identifier(tmp)} RENAME TO {sql_identifier(G_TABELLE_KONFIGURATION)}")
        verbindung.commit()
        verbindung.close()
    except Exception as e:
        try:
            verbindung.close()
        except Exception:
            pass
        messagebox.showerror("Konfiguration reparieren", f"Fehler beim Wiederherstellen der UNIQUE-Constraint:\n{e}")


def konfiguration_wert_speichern(bereich, schluessel, wert):
    if not db_ist_geladen():
        return False
    konfiguration_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        f"""
        INSERT INTO {sql_identifier(G_TABELLE_KONFIGURATION)} (bereich, schluessel, wert, datetime)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bereich, schluessel) DO UPDATE SET
            wert=excluded.wert,
            datetime=excluded.datetime
        """,
        (str(bereich), str(schluessel), "" if wert is None else str(wert), zeit),
    )
    verbindung.commit()
    verbindung.close()
    return True


def konfiguration_wert_lesen(bereich, schluessel):
    if not db_ist_geladen():
        return None
    konfiguration_tabelle_anlegen()
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"SELECT wert FROM {sql_identifier(G_TABELLE_KONFIGURATION)} WHERE bereich=? AND schluessel=?",
        (str(bereich), str(schluessel)),
    )
    row = cursor.fetchone()
    verbindung.close()
    return row[0] if row else None


def konfiguration_fuer_tabelle_bereinigen(tabellenname):
    if not db_ist_geladen() or not tabellenname:
        return 0
    try:
        konfiguration_tabelle_anlegen()
        name = str(tabellenname)
        muster = [
            name,
            f"tabelle:{name}",
            f"tabelle:{name}:%",
            f"tabellenfenster:{name}",
            f"tabellenfenster:{name}:%",
            f"fenster:tabelle:{name}",
            f"fenster:tabelle:{name}:%",
            f"fenster:tabellenfenster:{name}",
            f"fenster:tabellenfenster:{name}:%",
        ]
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        geloescht = 0
        for wert in muster:
            if wert.endswith("%"):
                cursor.execute(
                    f"DELETE FROM {sql_identifier(G_TABELLE_KONFIGURATION)} WHERE bereich LIKE ?",
                    (wert,),
                )
            else:
                cursor.execute(
                    f"DELETE FROM {sql_identifier(G_TABELLE_KONFIGURATION)} WHERE bereich=?",
                    (wert,),
                )
            geloescht += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        cursor.execute(
            f"DELETE FROM {sql_identifier(G_TABELLE_KONFIGURATION)} WHERE schluessel IN ('tabelle', 'tabellenname') AND wert=?",
            (name,),
        )
        geloescht += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        verbindung.commit()
        verbindung.close()
        if geloescht:
            debug_log(f"Konfiguration fuer geloeschte Tabelle bereinigt: tabelle={name}, eintraege={geloescht}", "allgemein")
        return geloescht
    except Exception as e:
        debug_log(f"Konfigurationsbereinigung fuer Tabelle fehlgeschlagen: tabelle={tabellenname}, fehler={e}", "allgemein")
        return 0


def sql_identifier(name):
    return '"' + str(name).replace('"', '""') + '"'


def spaltenkopf_text(spaltenname, cache):
    sortierung = cache.get("sortierung", {})
    if spaltenname in sortierung:
        return f"{spaltenname} {'▼' if sortierung[spaltenname] else '▲'}"
    return spaltenname

def sql_name_ok(name):
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""))


def fenstertitel_aktualisieren(zusatz=""):
    alter_titel = ""
    try:
        alter_titel = root.title()
    except Exception:
        alter_titel = ""

    if G_aktives_projekt:
        zusatz = f"  ●  {G_aktives_projekt}"

    if G_geladene_db_datei:
        neuer_titel = f"{G_EXE_Title} {__version__} - {Path(G_geladene_db_datei).name}{zusatz}"
    else:
        neuer_titel = f"{G_EXE_Title} {__version__}{zusatz}"

    root.title(neuer_titel)
    debug_log(
        f"Hauptfenster-Titel gesetzt: alt={alter_titel!r}, neu={neuer_titel!r}, zusatz={zusatz!r}",
        "fenster"
    )

    registry_id = None
    registry_alt = None
    for fenster_id, daten in G_fenster_registry.items():
        if daten.get("fenster") is root:
            registry_id = fenster_id
            registry_alt = daten.get("titel")
            daten["titel"] = neuer_titel
            break

    debug_log(
        f"Hauptfenster-Registry synchronisiert: registry_id={registry_id}, "
        f"registry_alt={registry_alt!r}, registry_neu={neuer_titel!r}",
        "fenster"
    )
    fensterliste_aktualisieren()


def sqlite_verbindung_oeffnen(db_datei=None):
    ziel = db_datei or G_geladene_db_datei
    return sqlite3.connect(ziel)


def db_ist_geladen():
    return bool(G_geladene_db_datei)


def db_pruefen_oder_warnen():
    if not db_ist_geladen():
        messagebox.showwarning("Keine Datenbank",
                               "Bitte öffnen Sie zuerst eine Datenbank.")
        return False
    return True


def logging_tabelle_anlegen():
    if not db_ist_geladen():
        return
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_LOGGING)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 0,
            meldung TEXT NOT NULL
        )
        """
    )
    verbindung.commit()
    verbindung.close()


def relationen_tabelle_anlegen():
    """Legt zzz_Relationen an, falls noch nicht vorhanden, und führt Spalten-Migrationen durch."""
    if not db_ist_geladen():
        return
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_RELATIONEN)} (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime    TEXT NOT NULL,
            Projekt     TEXT NOT NULL,
            Bezeichnung TEXT,
            QuellTabelle TEXT NOT NULL,
            QuellFeld    TEXT NOT NULL,
            ZielTabelle  TEXT NOT NULL,
            ZielFeld     TEXT NOT NULL,
            Reihenfolge  INTEGER DEFAULT 0
        )"""
    )
    # Migration: neue Spalten hinzufügen, falls noch nicht vorhanden
    for _col_sql in [
        f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN)} ADD COLUMN Typ TEXT DEFAULT '1:N'",
        f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN)} ADD COLUMN Kette TEXT",
        f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN)} ADD COLUMN AnzeigenFelder TEXT",
        f"ALTER TABLE {sql_identifier(G_TABELLE_RELATIONEN)} ADD COLUMN QuellFelder TEXT",
    ]:
        try:
            cursor.execute(_col_sql)
        except Exception:
            pass  # Spalte existiert bereits
    verbindung.commit()
    verbindung.close()


def relationen_fuer_projekt_laden(projektname):
    """Gibt Liste der Beziehungen für ein Projekt zurück."""
    if not db_ist_geladen() or not projektname:
        return []
    try:
        relationen_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen()
        rows = verbindung.execute(
            f"SELECT id, Bezeichnung, QuellTabelle, QuellFeld, ZielTabelle, ZielFeld, "
            f"Reihenfolge, Typ, Kette, AnzeigenFelder, QuellFelder "
            f"FROM {sql_identifier(G_TABELLE_RELATIONEN)} "
            f"WHERE Projekt=? ORDER BY Reihenfolge, id",
            (projektname,)
        ).fetchall()
        verbindung.close()
        return [{"id": r[0], "bezeichnung": r[1] or "", "quell_tabelle": r[2],
                 "quell_feld": r[3], "ziel_tabelle": r[4], "ziel_feld": r[5],
                 "reihenfolge": r[6], "typ": r[7] or "1:N",
                 "kette": r[8] or "", "anzeigen_felder": r[9] or "",
                 "quell_felder": r[10] or ""} for r in rows]
    except Exception:
        return []


def findings_tabelle_anlegen():
    if not db_ist_geladen():
        return
    verbindung = sqlite_verbindung_oeffnen()
    cursor = verbindung.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {sql_identifier(G_TABELLE_FINDINGS)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            TabellenName TEXT,
            idFeld TEXT,
            idFeldInhalt TEXT,
            Feldname TEXT,
            FeldInhalt TEXT,
            KurzeBeschreibung TEXT,
            UNIQUE(TabellenName, idFeld, idFeldInhalt)
        )
        """
    )
    # Für bereits bestehende Tabellen ohne den Constraint nachträglich anlegen
    try:
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_findings_unique "
            f"ON {sql_identifier(G_TABELLE_FINDINGS)} (TabellenName, idFeld, idFeldInhalt)"
        )
    except Exception:
        pass
    verbindung.commit()
    verbindung.close()


def logging_eintrag_schreiben(meldung, status=0):
    if not db_ist_geladen():
        return
    try:
        logging_tabelle_anlegen()
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"INSERT INTO {sql_identifier(G_TABELLE_LOGGING)} (datetime, status, meldung) VALUES (?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, meldung),
        )
        verbindung.commit()
        verbindung.close()
    except Exception:
        pass


def aktuelle_tabelle_ermitteln():
    auswahl = tree_tabellen.selection()
    if not auswahl:
        return None
    return tree_tabellen.item(auswahl[0], "values")[0]


def admin_code_fuer_aktion_pruefen(tabellenname, aktion):
    if not tabellenname or tabellenname.upper() not in G_GESCHUETZTE_TABELLEN or aktion not in G_GESCHUETZTE_AKTIONEN:
        return True
    # Ersteinrichtung falls noch kein Hash in der DB
    hash_hex, _ = _admin_code_hash_lesen()
    if not hash_hex:
        if not _admin_code_einrichten_dialog():
            return False
    code = simpledialog.askstring(
        "Admin-Code",
        f"Für '{aktion}' auf '{tabellenname}' bitte Admin-Code eingeben:",
        show="*",
        parent=root,
    )
    if code is None or not _admin_code_pruefen(code.strip()):
        messagebox.showwarning("Admin-Code", "Aktion nicht freigegeben.", parent=root)
        return False
    return True


def tabellenfenster_nach_vorne_holen(tabellenname):
    fenster_id = G_tabellenfenster_nach_name.get(tabellenname)
    if not fenster_id:
        return False
    fenster = G_tabellenfenster.get(fenster_id)
    if fenster is None or not fenster.winfo_exists():
        return False
    fenster.deiconify()
    fenster.lift()
    fenster.focus_force()
    return True

def fenster_in_vordergrund_holen(fenster):
    if fenster is None or not fenster.winfo_exists():
        return
    try:
        fenster.deiconify()
    except Exception:
        pass
    # Maximiertes Fenster zuerst auf Normal setzen damit andere Fenster sichtbar bleiben
    try:
        if fenster.state() == "zoomed":
            fenster.state("normal")
    except Exception:
        pass
    try:
        fenster.lift()
    except Exception:
        pass
    try:
        fenster.attributes("-topmost", True)
        fenster.update_idletasks()
        fenster.attributes("-topmost", False)
    except Exception:
        pass
    try:
        fenster.focus_force()
    except Exception:
        pass

def tabellenfenster_titel_setzen(fenster, tabellenname, zusatz=""):
    fenster.title(f"{G_EXE_Title} - {tabellenname}{zusatz}")

def tabellenfenster_basis_titel_setzen(fenster_id, zusatz=""):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tabellenname = cache["tabellenname"]
    basis_titel = f"{G_EXE_Title} - {tabellenname}{zusatz}"
    cache["basis_titel"] = basis_titel
    fenster.title(basis_titel)
    fenster_titel_update(cache.get("registry_id", fenster_id))

def tabellenfenster_temp_hinweis(fenster_id, meldung, dauer_ms=1800):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tabellenname = cache["tabellenname"]
    alter_job = cache.get("temp_hinweis_job")
    if alter_job is not None:
        try:
            fenster.after_cancel(alter_job)
        except Exception:
            pass
    fenster.title(f"{G_EXE_Title} - {tabellenname}{meldung}")
    fenster_titel_update(cache.get("registry_id", fenster_id))

    def restore():
        if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
            return
        basis_titel = G_tabellen_cache[fenster_id].get("basis_titel")
        if basis_titel:
            fenster.title(basis_titel)
        G_tabellen_cache[fenster_id]["temp_hinweis_job"] = None

    job = fenster.after(dauer_ms, restore)
    cache["temp_hinweis_job"] = job

def tree_spalten_breiten_anpassen(tree_widget, status_callback=None, update_schritt=1000, max_zeilen_pruefen=200):
    tree_font = font.nametofont("TkDefaultFont")
    items = list(tree_widget.get_children())[:max_zeilen_pruefen]
    spalten = list(tree_widget["columns"])
    for index, spalte in enumerate(spalten, start=1):
        max_breite = tree_font.measure(str(spalte))
        for item_id in items:
            wert = str(tree_widget.set(item_id, spalte))
            breite = max(tree_font.measure(teil) for teil in wert.split("\n")) if wert else 0
            max_breite = max(max_breite, breite)
        tree_widget.column(spalte, width=min(max_breite + 24, G_MAX_SPALTEN_BREITE), minwidth=60, anchor="w")
        if status_callback and update_schritt and (index % max(1, update_schritt) == 0):
            try:
                status_callback(f"Spaltenbreiten werden angepasst... ({index} / {len(spalten)})")
            except Exception:
                pass


def tabellen_laden():
    if not db_ist_geladen():
        return []
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        daten = [row[0] for row in cursor.fetchall()]
        verbindung.close()
        return daten
    except Exception as e:
        messagebox.showerror("DB-Fehler", f"Tabellen konnten nicht gelesen werden:\n{e}")
        return []


def eindeutigen_tabellennamen_vorschlagen(basisname):
    """Gibt einen Tabellennamen zurück der noch nicht existiert.
    Falls basisname schon vorhanden: basisname_2, basisname_3 usw.
    """
    vorhandene = {t.lower() for t in tabellen_laden()}
    if basisname.lower() not in vorhandene:
        return basisname
    zaehler = 2
    while True:
        kandidat = f"{basisname}_{zaehler}"
        if kandidat.lower() not in vorhandene:
            return kandidat
        zaehler += 1


# ipv4_to_int ist jetzt in sqlgui_udf.py definiert und wird oben importiert.


def eindeutigen_dateinamen_vorschlagen(verzeichnis, basisname, endung=".csv"):
    """Gibt einen Dateinamen zurück der im Verzeichnis noch nicht existiert.
    Falls basisname.csv schon vorhanden: basisname_2.csv, basisname_3.csv usw.
    """
    import pathlib
    verzeichnis = pathlib.Path(verzeichnis)
    if not (verzeichnis / f"{basisname}{endung}").exists():
        return f"{basisname}{endung}"
    zaehler = 2
    while True:
        kandidat = f"{basisname}_{zaehler}{endung}"
        if not (verzeichnis / kandidat).exists():
            return kandidat
        zaehler += 1


def tabellen_dropdown_aktualisieren(zu_selektierende_tabelle=None):
    tree_tabellen.delete(*tree_tabellen.get_children())
    tabellen = tabellen_laden()
    ziel = None
    erstes = None
    for name in tabellen:
        item = tree_tabellen.insert("", "end", values=(name,))
        if erstes is None:
            erstes = item
        if name == zu_selektierende_tabelle:
            ziel = item
    ziel = ziel or erstes
    if ziel:
        tree_tabellen.selection_set(ziel)
        tree_tabellen.focus(ziel)
        tabellenname = tree_tabellen.item(ziel, "values")[0]
        G_tabellenname.set(tabellenname)
        tabelle_vorschau_anzeigen(tabellenname)
    else:
        tree.delete(*tree.get_children())
        tree["columns"] = ()
        tree["show"] = ""


def tabelle_vorschau_anzeigen(tabellenname):
    global G_vorschau_laeuft, G_angeforderte_vorschau_tabelle
    global G_vorschau_request_id, G_vorschau_after_id, G_vorschau_startzeit
    if not tabellenname or not G_geladene_db_datei:
        debug_log(f"Vorschau nicht gestartet: tabellenname={tabellenname}, db={G_geladene_db_datei}", "vorschau")
        return

    if G_vorschau_laeuft and G_angeforderte_vorschau_tabelle == tabellenname:
        debug_log(
            f"Doppelte Vorschau-Anforderung ignoriert: tabelle={tabellenname}, "
            f"request_id={G_vorschau_request_id}, after_id={G_vorschau_after_id}",
            "vorschau"
        )
        return

    G_vorschau_request_id += 1
    request_id = G_vorschau_request_id
    G_angeforderte_vorschau_tabelle = tabellenname
    G_vorschau_laeuft = True
    G_vorschau_startzeit = time.monotonic()

    debug_log(
        f"Vorschau angefordert: request_id={request_id}, tabelle={tabellenname}, "
        f"db={G_geladene_db_datei}, limit={G_vorschau_limit}",
        "vorschau"
    )

    geleert = 0
    while True:
        try:
            G_vorschau_queue.get_nowait()
            geleert += 1
        except queue.Empty:
            break
    if geleert:
        debug_log(f"Vorschau-Queue vor Neustart geleert: request_id={request_id}, eintraege={geleert}", "vorschau")

    if G_vorschau_after_id is not None:
        try:
            root.after_cancel(G_vorschau_after_id)
            debug_log(f"Alter Vorschau-Poller abgebrochen: after_id={G_vorschau_after_id}", "vorschau")
        except Exception as e:
            debug_log(f"Alter Vorschau-Poller konnte nicht abgebrochen werden: after_id={G_vorschau_after_id}, fehler={e}", "vorschau")
        finally:
            G_vorschau_after_id = None

    fenstertitel_aktualisieren(f"  * Vorschau lädt... ({tabellenname})")
    debug_log(f"Worker startet: request_id={request_id}, tabelle={tabellenname}", "vorschau")
    worker = threading.Thread(
        target=tabelle_vorschau_laden_worker,
        args=(G_geladene_db_datei, tabellenname, G_vorschau_limit, G_vorschau_queue, request_id),
        daemon=True
    )
    worker.start()
    G_vorschau_after_id = root.after(100, tabelle_vorschau_pruefen)

def tabelle_links_ausgewaehlt(event=None):
    global G_einfachklick_job, G_angeforderte_vorschau_tabelle
    auswahl = tree_tabellen.selection()
    if not auswahl:
        debug_log("tabelle_links_ausgewaehlt ohne Auswahl", "vorschau")
        return
    item_id = auswahl[0]
    tabellenname = tree_tabellen.item(item_id, "values")[0]
    debug_log(f"Auswahl gewechselt: item_id={item_id}, tabellenname={tabellenname}", "vorschau")
    G_tabellenname.set(tabellenname)
    G_angeforderte_vorschau_tabelle = tabellenname
    if G_einfachklick_job is not None:
        root.after_cancel(G_einfachklick_job)
        G_einfachklick_job = None
    tabelle_vorschau_anzeigen(tabellenname)

def tabellenfenster_schliessen(fenster_id):
    fenster = G_tabellenfenster.pop(fenster_id, None)
    cache = G_tabellen_cache.pop(fenster_id, None)
    if cache:
        G_tabellenfenster_nach_name.pop(cache.get("tabellenname"), None)
        fenster_deregistrieren(cache.get("registry_id"))
    if fenster and fenster.winfo_exists():
        fenster.destroy()


def tabellenfenster_aktualisieren(fenster_id):
    """Lädt die Tabelle neu (F5). Position und Größe des Fensters bleiben erhalten."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tabellenname = cache.get("tabellenname", "")
    if not tabellenname:
        return
    try:
        pos_x = cache["fenster"].winfo_x()
        pos_y = cache["fenster"].winfo_y()
        breite = cache["fenster"].winfo_width()
        hoehe = cache["fenster"].winfo_height()
    except Exception:
        pos_x = pos_y = breite = hoehe = None
    tabellenfenster_schliessen(fenster_id)
    tabellenfenster_oeffnen(tabellenname)
    if pos_x is not None:
        try:
            if tabellenname in G_tabellenfenster_nach_name:
                nf_id = G_tabellenfenster_nach_name[tabellenname]
                nf = G_tabellen_cache.get(nf_id, {}).get("fenster")
                if nf:
                    nf.update_idletasks()
                    nf.geometry(f"{breite}x{hoehe}+{pos_x}+{pos_y}")
        except Exception:
            pass


def tabellenfenster_sortieren(fenster_id, spaltenname):
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tree_widget = cache["tree"]
    index = cache["spalten"].index(spaltenname)
    absteigend = not cache["sortierung"].get(spaltenname, False)
    cache["sortierung"] = {spaltenname: absteigend}

    def _sort_key(row):
        wert = row[index] if index < len(row) else None
        s = "" if wert is None else str(wert)
        try:
            return (0, float(s), s)   # Zahl: numerisch sortieren
        except (ValueError, TypeError):
            return (1, 0.0, s.lower())  # Text: alphabetisch, nach Zahlen

    cache["zeilen"].sort(key=_sort_key, reverse=absteigend)
    tree_widget.delete(*tree_widget.get_children())
    for zeile in cache["zeilen"]:
        tree_widget.insert("", "end", values=zeile)
    for spalte in cache["spalten"]:
        richt = cache["sortierung"].get(spalte)
        text = spalte if richt is None else f"{spalte} {'▼' if richt else '▲'}"
        tree_widget.heading(spalte, text=text, command=lambda c=spalte, fid=fenster_id: tabellenfenster_sortieren(fid, c))
    tree_spalten_breiten_anpassen(tree_widget)


def tabellenfenster_feld_in_zwischenablage(fenster_id):
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        return
    werte = cache["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    text = str(werte[index])
    cache["fenster"].clipboard_clear()
    cache["fenster"].clipboard_append(text)


def tabellenfenster_pk_ermitteln(fenster_id):
    """Gibt (pk_feldname, pk_wert) der aktuell markierten Zeile zurück, oder (None, None)."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return None, None
    tabellenname = cache.get("tabellenname", "")
    spalten = list(cache.get("spalten", []))
    if not tabellenname:
        return None, None
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"PRAGMA table_info({sql_identifier(tabellenname)})")
        info = cursor.fetchall()
        verbindung.close()
        pk_felder = sorted([(row[1], row[5]) for row in info if row[5] > 0], key=lambda x: x[1])
        if not pk_felder:
            return None, None
        pk_feldname = pk_felder[0][0]
        item_id = cache.get("kontext_item_id")
        if not item_id:
            return pk_feldname, None
        werte = cache["tree"].item(item_id, "values")
        if pk_feldname in spalten:
            idx = spalten.index(pk_feldname)
            pk_wert = werte[idx] if idx < len(werte) else None
        else:
            return pk_feldname, None
        return pk_feldname, pk_wert
    except Exception:
        return None, None


def tabellenfenster_feld_im_lesefenster_anzeigen(fenster_id):
    """Zeigt den Inhalt des angeklickten Feldes im Lesefenster an.
    Mit ▲ ▼ Buttons zur Navigation durch die Tabellenzeilen.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        messagebox.showwarning("Feldinhalt", "Bitte zuerst eine Zelle auswählen.", parent=cache["fenster"])
        return
    index = int(spalte_id.replace("#", "")) - 1
    spalten = list(cache.get("spalten", []))
    spaltenname = spalten[index] if index < len(spalten) else f"Spalte{index + 1}"
    tabellenname = cache.get("tabellenname", "")
    tree = cache["tree"]

    # Navigationszustand
    nav = {"item_id": item_id}

    def get_feldwert(iid):
        werte = tree.item(iid, "values")
        return str(werte[index]) if index < len(werte) else ""

    def get_titel(iid):
        alle = list(tree.get_children())
        pos = alle.index(iid) + 1 if iid in alle else "?"
        return f"Feldinhalt – {tabellenname} · {spaltenname}  [{pos}/{len(alle)}]"

    def nav_hoch(aktualisieren):
        alle = list(tree.get_children())
        if not alle:
            return
        try:
            idx = alle.index(nav["item_id"])
        except ValueError:
            return
        if idx > 0:
            nav["item_id"] = alle[idx - 1]
            tree.selection_set(nav["item_id"])
            tree.focus(nav["item_id"])
            tree.see(nav["item_id"])
            cache["kontext_item_id"] = nav["item_id"]
            aktualisieren(get_feldwert(nav["item_id"]), get_titel(nav["item_id"]))

    def nav_runter(aktualisieren):
        alle = list(tree.get_children())
        if not alle:
            return
        try:
            idx = alle.index(nav["item_id"])
        except ValueError:
            return
        if idx < len(alle) - 1:
            nav["item_id"] = alle[idx + 1]
            tree.selection_set(nav["item_id"])
            tree.focus(nav["item_id"])
            tree.see(nav["item_id"])
            cache["kontext_item_id"] = nav["item_id"]
            aktualisieren(get_feldwert(nav["item_id"]), get_titel(nav["item_id"]))

    feldwert = get_feldwert(item_id)
    titel = get_titel(item_id)

    # Zeilenposition für smarte Fensterplatzierung
    try:
        bbox = tree.bbox(item_id)
        zeil_x = cache["fenster"].winfo_rootx() + 20
        zeil_y = cache["fenster"].winfo_rooty() + (bbox[1] if bbox else 0)
        zeil_h = bbox[3] if bbox else 22
    except Exception:
        zeil_x = zeil_y = zeil_h = None

    gui_csv_zelltext_anzeigen(
        cache["fenster"], titel, feldwert,
        ziel_x=zeil_x, ziel_y=zeil_y, ziel_hoehe=zeil_h,
        nav_hoch=nav_hoch, nav_runter=nav_runter,
    )


def tabellenfenster_zeile_als_csv_in_zwischenablage(fenster_id):
    """Kopiert die aktuelle Zeile als CSV – alle Felder in Anführungszeichen (QUOTE_ALL)."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id") or (
        cache["tree"].selection()[0] if cache["tree"].selection() else None
    )
    if not item_id:
        return
    import csv as csv_modul, io
    werte = cache["tree"].item(item_id, "values")
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(["" if v is None else str(v) for v in werte])
    cache["fenster"].clipboard_clear()
    cache["fenster"].clipboard_append(ausgabe.getvalue().rstrip("\r\n"))


def tabellenfenster_header_als_csv_in_zwischenablage(fenster_id):
    """Kopiert die Spaltenüberschriften als CSV-Zeile mit QUOTE_ALL."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    spalten = list(cache.get("spalten", []))
    if not spalten:
        return
    import csv as csv_modul, io
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(spalten)
    cache["fenster"].clipboard_clear()
    cache["fenster"].clipboard_append(ausgabe.getvalue().rstrip("\r\n"))


def tabellenfenster_tabelle_als_csv_kopieren(fenster_id):
    """Kopiert alle sichtbaren Zeilen als CSV – mit Rückfrage Alle oder Anzahl."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    fenster = cache["fenster"]
    tree = cache["tree"]
    alle_ids = tree.get_children()
    if not alle_ids:
        messagebox.showwarning("Tabelle als CSV", "Keine Zeilen vorhanden.", parent=fenster)
        return
    gesamt = len(alle_ids)

    # Dialog: Alle oder Anzahl eingeben
    dialog = tk.Toplevel(fenster)
    dialog.title("Tabelle als CSV kopieren")
    dialog.geometry("380x160")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(fenster)
    tk.Label(dialog, text=f"Sichtbare Zeilen: {gesamt:,}".replace(",", "."), anchor="w").pack(fill="x", padx=16, pady=(16, 4))
    tk.Label(dialog, text="Anzahl zu kopierender Zeilen (leer = alle):", anchor="w").pack(fill="x", padx=16)
    anzahl_var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=anzahl_var, width=20)
    entry.pack(anchor="w", padx=16, pady=(4, 0))
    entry.focus_set()
    ergebnis = [None]

    def bestaetigen(event=None):
        ergebnis[0] = anzahl_var.get().strip()
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(fill="x", padx=16, pady=(12, 0))
    tk.Button(btn_frame, text="Kopieren", width=12, command=bestaetigen).pack(side="right", padx=(8, 0))
    tk.Button(btn_frame, text="Abbrechen", width=12, command=dialog.destroy).pack(side="right")
    entry.bind("<Return>", bestaetigen)
    dialog.wait_window()

    if ergebnis[0] is None:
        return
    if ergebnis[0] == "":
        ids = alle_ids
    else:
        try:
            n = int(ergebnis[0])
            ids = alle_ids[:max(1, n)]
        except ValueError:
            messagebox.showwarning("Tabelle als CSV", f"'{ergebnis[0]}' ist keine gültige Zahl.", parent=fenster)
            return

    import csv as csv_modul, io
    spalten = list(cache.get("spalten", []))
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(spalten)
    for item_id in ids:
        writer.writerow(["" if v is None else str(v) for v in tree.item(item_id, "values")])
    fenster.clipboard_clear()
    fenster.clipboard_append(ausgabe.getvalue())
    tabellenfenster_temp_hinweis(fenster_id, f" * {len(ids):,} Zeilen als CSV kopiert".replace(",", "."))


def tabellenfenster_netzwerk_ip_anzeigen(fenster_id):
    """Erkennt IP-Adressen oder Netzwerke (CIDR) im Feldinhalt und zeigt Details an.
    Durchsucht den gesamten Feldtext nach IP/CIDR – auch in längeren Texten.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    fenster = cache["fenster"]
    if not item_id or not spalte_id:
        messagebox.showwarning("Netzwerk/IP", "Bitte zuerst eine Zelle auswählen.", parent=fenster)
        return
    werte = cache["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    feldwert = str(werte[index]).strip()

    import re

    def ipv4_zu_int_lokal(ip):
        try:
            teile = ip.strip().split(".")
            if len(teile) != 4:
                return None
            oktette = [int(t) for t in teile]
            if any(o < 0 or o > 255 for o in oktette):
                return None
            return (oktette[0] << 24) | (oktette[1] << 16) | (oktette[2] << 8) | oktette[3]
        except Exception:
            return None

    def int_zu_ipv4_lokal(zahl):
        return f"{(zahl>>24)&0xFF}.{(zahl>>16)&0xFF}.{(zahl>>8)&0xFF}.{zahl&0xFF}"

    # CIDR: 4-Oktet oder 3-Oktet IP mit Maske (z.B. 172.23.124/24 oder 10.0.0.1/26)
    cidr_muster = re.findall(r'(?<![0-9])(\d{1,3}\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?/\d{1,2})(?![0-9])', feldwert)
    # Einzelne IPs nur wenn kein CIDR gefunden
    if not cidr_muster:
        ip_muster = re.findall(r'(?<![0-9])(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?![0-9])', feldwert)
        if not ip_muster:
            ip_muster = re.findall(r'(?<![0-9])(\d{1,3}\.\d{1,3}\.\d{1,3})(?!\.\d)(?![0-9])', feldwert)
    else:
        ip_muster = []

    zeilen = [f"Eingabe: {feldwert}", ""]
    gefunden = False

    for cidr in cidr_muster:
        try:
            ip_teil, prefix = cidr.split("/")
            prefix = int(prefix)
            if prefix < 0 or prefix > 32:
                continue
            ip_int = ipv4_zu_int_lokal(ip_teil)
            if ip_int is None:
                continue
            maske_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
            netz_int = ip_int & maske_int
            broadcast_int = netz_int | (~maske_int & 0xFFFFFFFF)
            erste_host = netz_int + 1 if prefix < 32 else netz_int
            letzte_host = broadcast_int - 1 if prefix < 32 else broadcast_int
            anzahl_hosts = max(0, broadcast_int - netz_int - 1) if prefix < 31 else (1 if prefix == 32 else 2)
            zeilen.append(f"CIDR: {cidr}")
            zeilen.append(f". Netzadresse:    {int_zu_ipv4_lokal(netz_int)}")
            zeilen.append(f". Subnetzmaske:   {int_zu_ipv4_lokal(maske_int)}")
            zeilen.append(f". Broadcast:      {int_zu_ipv4_lokal(broadcast_int)}")
            zeilen.append(f". Erster Host:    {int_zu_ipv4_lokal(erste_host)}")
            zeilen.append(f". Letzter Host:   {int_zu_ipv4_lokal(letzte_host)}")
            zeilen.append(f". Nutzbare Hosts: {anzahl_hosts:,}".replace(",", "."))
            zeilen.append("")
            gefunden = True
        except Exception:
            pass

    for ip in ip_muster:
        ip_int = ipv4_zu_int_lokal(ip)
        if ip_int is not None:
            zeilen.append(f"IP-Adresse: {ip}")
            zeilen.append(f". Als Integer: {ip_int}")
            zeilen.append("")
            gefunden = True

    if not gefunden:
        messagebox.showwarning(
            "Netzwerk/IP",
            f"Im Feldinhalt wurde keine IP-Adresse oder CIDR-Notation gefunden.\n\n'{feldwert}'",
            parent=fenster
        )
        return

    ergebnis_text = "\n".join(zeilen)
    top = gui_csv_zelltext_anzeigen(fenster, "Netzwerk / IP-Adresse", ergebnis_text)
    top.lift()
    top.focus_force()


def tabellenfenster_integer_zu_ipv4_anzeigen(fenster_id):
    """Wandelt den Feldinhalt als Integer in eine IPv4-Adresse um und zeigt sie an."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    fenster = cache["fenster"]
    if not item_id or not spalte_id:
        messagebox.showwarning("Integer zu IPv4", "Bitte zuerst eine Zelle auswählen.", parent=fenster)
        return
    werte = cache["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    feldwert = str(werte[index]).strip()
    try:
        zahl = int(feldwert)
        if zahl < 0 or zahl > 4294967295:
            raise ValueError()
        oktett1 = (zahl >> 24) & 0xFF
        oktett2 = (zahl >> 16) & 0xFF
        oktett3 = (zahl >> 8) & 0xFF
        oktett4 = zahl & 0xFF
        ipv4 = f"{oktett1}.{oktett2}.{oktett3}.{oktett4}"
        gui_csv_zelltext_anzeigen(
            fenster,
            "Integer zu IPv4-Adresse",
            f"Eingabe:  {feldwert}\nIPv4:     {ipv4}",
        )
    except Exception:
        messagebox.showwarning(
            "Integer zu IPv4",
            f"Der Feldinhalt '{feldwert}' ist keine gültige Ganzzahl im IPv4-Bereich (0 – 4294967295).",
            parent=fenster,
        )


def tabellenfenster_ipv4_zu_integer_anzeigen(fenster_id):
    """Wandelt den Feldinhalt als IPv4-Adresse in einen Integer um und zeigt ihn an.
    Bei ungültigem Wert wird eine freundliche Fehlermeldung angezeigt.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    fenster = cache["fenster"]
    if not item_id or not spalte_id:
        messagebox.showwarning("IPv4 zu Integer", "Bitte zuerst eine Zelle auswählen.", parent=fenster)
        return
    werte = cache["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    feldwert = str(werte[index]).strip()
    try:
        teile = feldwert.split(".")
        if len(teile) != 4:
            raise ValueError("Kein IPv4-Format")
        oktette = [int(t) for t in teile]
        if any(o < 0 or o > 255 for o in oktette):
            raise ValueError("Oktet außerhalb 0–255")
        zahl = (oktette[0] << 24) | (oktette[1] << 16) | (oktette[2] << 8) | oktette[3]
        gui_csv_zelltext_anzeigen(
            fenster,
            "IPv4-Adresse zu Integer",
            f"Eingabe:  {feldwert}\nInteger:  {zahl}",
        )
    except Exception:
        messagebox.showwarning(
            "IPv4 zu Integer",
            f"Der Feldinhalt '{feldwert}' ist keine gültige IPv4-Adresse (z.B. 192.168.1.1).",
            parent=fenster,
        )


# ip_range_aufteilen ist jetzt in sqlgui_udf.py definiert und wird oben importiert.


def tabellenfenster_ip_range_aufteilen_anzeigen(fenster_id):
    """Teilt den Feldinhalt als IP-Range auf und zeigt Start + Ende im Lesefenster."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    fenster = cache["fenster"]
    if not item_id or not spalte_id:
        messagebox.showwarning("IP-Range", "Bitte zuerst eine Zelle auswählen.", parent=fenster)
        return
    werte = cache["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    feldwert = str(werte[index]).strip()
    ergebnis = ip_range_aufteilen(feldwert)
    if not ergebnis["ok"]:
        messagebox.showwarning(
            "IP-Range aufteilen",
            f"'{feldwert}' ist kein gültiger IP-Bereich.\n\nFehler: {ergebnis['fehler']}",
            parent=fenster,
        )
        return
    gui_csv_zelltext_anzeigen(
        fenster,
        "IP-Range aufteilen",
        f"Eingabe:    {feldwert}\n"
        f"Start-IP:   {ergebnis['start']}  ({ergebnis['start_int']})\n"
        f"End-IP:     {ergebnis['end']}  ({ergebnis['end_int']})",
    )


def tabellenfenster_eindeutige_feldwerte_anzeigen(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tree_widget = cache["tree"]
    spalte_id = cache.get("kontext_spalte_id")
    if not spalte_id:
        messagebox.showwarning("Eindeutige Feldwerte", "Bitte zuerst mit der rechten Maustaste in eine Feldspalte klicken.", parent=fenster)
        return
    try:
        spaltenindex = int(spalte_id.replace("#", "")) - 1
    except Exception:
        messagebox.showwarning("Eindeutige Feldwerte", "Die angeklickte Spalte konnte nicht ermittelt werden.", parent=fenster)
        return
    spalten = list(cache.get("spalten", []))
    if spaltenindex < 0 or spaltenindex >= len(spalten):
        messagebox.showwarning("Eindeutige Feldwerte", "Die angeklickte Spalte ist ungültig.", parent=fenster)
        return

    spaltenname = spalten[spaltenindex]
    items = list(tree_widget.get_children())
    if not items:
        messagebox.showinfo("Eindeutige Feldwerte", "In der aktuellen Anzeige sind keine Datensätze vorhanden.", parent=fenster)
        return

    zaehler = {}
    for item_id in items:
        werte = tree_widget.item(item_id, "values")
        wert = ""
        if spaltenindex < len(werte):
            wert = "" if werte[spaltenindex] is None else str(werte[spaltenindex])
        zaehler[wert] = zaehler.get(wert, 0) + 1

    sortierte_werte = sorted(zaehler.items(), key=lambda eintrag: (-eintrag[1], eintrag[0].lower()))
    anzahl_datensaetze = len(items)
    anzahl_eindeutig = len(sortierte_werte)
    basis_text = "aktuelle Anzeige"
    if cache.get("filter_aktiv") and cache.get("filter_info"):
        filter_info = cache["filter_info"]
        basis_text = f"aktuelle Anzeige, Filter: {filter_info.get('spalte')} enthält '{filter_info.get('wert')}'"

    top = tk.Toplevel(fenster)
    top.title(f"{G_EXE_Title} - Eindeutige Werte: {cache['tabellenname']}.{spaltenname}")
    top.geometry("720x520")
    top.minsize(520, 360)
    fenster_registrieren(top, "Eindeutige Werte", top.title())

    hauptframe = tk.Frame(top, padx=10, pady=10)
    hauptframe.pack(fill="both", expand=True)
    hauptframe.grid_rowconfigure(1, weight=1)
    hauptframe.grid_columnconfigure(0, weight=1)

    info_text = (
        f"Tabelle: {cache['tabellenname']}    "
        f"Spalte: {spaltenname}    "
        f"Datensätze: {anzahl_datensaetze:,}    "
        f"unterschiedliche Werte: {anzahl_eindeutig:,}"
    ).replace(",", ".")
    tk.Label(hauptframe, text=info_text, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 4))
    tk.Label(hauptframe, text=f"Basis: {basis_text}", anchor="w").grid(row=1, column=0, sticky="ew", pady=(0, 8))

    tree_frame = tk.Frame(hauptframe)
    tree_frame.grid(row=2, column=0, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)
    hauptframe.grid_rowconfigure(2, weight=1)

    auswertung_tree = ttk.Treeview(tree_frame, columns=("wert", "anzahl"), show="headings", selectmode="browse")
    eindeutige_sortierung = {"spalte": "anzahl", "absteigend": True}

    def eindeutige_kopftext(spalte, text):
        if eindeutige_sortierung.get("spalte") != spalte:
            return text
        return f"{text} {'▼' if eindeutige_sortierung.get('absteigend') else '▲'}"

    def eindeutige_werte_fuellen():
        auswertung_tree.delete(*auswertung_tree.get_children())
        daten = list(sortierte_werte)
        if eindeutige_sortierung.get("spalte") == "wert":
            daten.sort(key=lambda eintrag: eintrag[0].lower(), reverse=eindeutige_sortierung.get("absteigend", False))
        else:
            daten.sort(key=lambda eintrag: (eintrag[1], eintrag[0].lower()), reverse=eindeutige_sortierung.get("absteigend", True))
        auswertung_tree.heading("wert", text=eindeutige_kopftext("wert", "Wert"), command=lambda: eindeutige_werte_sortieren("wert"))
        auswertung_tree.heading("anzahl", text=eindeutige_kopftext("anzahl", "Anzahl"), command=lambda: eindeutige_werte_sortieren("anzahl"))
        for wert, anzahl in daten:
            anzeige_wert = "(leer)" if wert == "" else wert
            auswertung_tree.insert("", "end", values=(anzeige_wert, f"{anzahl:,}".replace(",", ".")))

    def eindeutige_werte_sortieren(spalte):
        if eindeutige_sortierung.get("spalte") == spalte:
            eindeutige_sortierung["absteigend"] = not eindeutige_sortierung.get("absteigend", False)
        else:
            eindeutige_sortierung["spalte"] = spalte
            eindeutige_sortierung["absteigend"] = True if spalte == "anzahl" else False
        eindeutige_werte_fuellen()

    auswertung_tree.column("wert", anchor="w", width=480)
    auswertung_tree.column("anzahl", anchor="e", width=120)
    auswertung_tree.grid(row=0, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=auswertung_tree.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=auswertung_tree.xview)
    scroll_x.grid(row=1, column=0, sticky="ew")
    auswertung_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    eindeutige_werte_fuellen()

    # Menüleiste
    eindeutige_menue = fenster_standard_menue_anbringen(top, "720x520", "Eindeutige Werte")

    # Rechtsklick auf Werte-Tree
    def eindeutige_rechtsklick(event):
        item_id = auswertung_tree.identify_row(event.y)
        if item_id:
            auswertung_tree.selection_set(item_id)
            auswertung_tree.focus(item_id)
        menu = tk.Menu(top, tearoff=0)
        # Block 1: Kopieren
        menu.add_command(label="Feldinhalt kopieren", command=lambda: eindeutige_feld_kopieren())
        menu.add_command(label="Tabelle als CSV kopieren", command=lambda: eindeutige_tabelle_kopieren())
        menu.add_separator()
        # Block 2: Anzeigen
        menu.add_command(label="Feldinhalt im Lesefenster anzeigen", command=lambda: eindeutige_feld_im_lesefenster())
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def eindeutige_feld_kopieren():
        auswahl = auswertung_tree.selection()
        if not auswahl:
            return
        wert = auswertung_tree.item(auswahl[0], "values")[0]
        if wert == "(leer)":
            wert = ""
        top.clipboard_clear()
        top.clipboard_append(wert)

    def eindeutige_tabelle_kopieren():
        import csv as csv_modul, io
        ausgabe = io.StringIO()
        writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
        writer.writerow(["Wert", "Anzahl"])
        for item_id in auswertung_tree.get_children():
            vals = auswertung_tree.item(item_id, "values")
            writer.writerow(vals)
        top.clipboard_clear()
        top.clipboard_append(ausgabe.getvalue())

    def eindeutige_feld_im_lesefenster():
        auswahl = auswertung_tree.selection()
        if not auswahl:
            return
        wert = auswertung_tree.item(auswahl[0], "values")[0]
        if wert == "(leer)":
            wert = ""
        gui_csv_zelltext_anzeigen(top, f"Feldinhalt – {spaltenname}", wert)

    auswertung_tree.bind("<Button-3>", eindeutige_rechtsklick)
    auswertung_tree.bind("<Double-1>", lambda e: eindeutige_feld_im_lesefenster())

    button_frame = tk.Frame(hauptframe)
    button_frame.grid(row=3, column=0, sticky="e", pady=(8, 0))
    tk.Button(button_frame, text="Schließen", command=top.destroy, width=12).pack(side="right")

    debug_log(
        f"Eindeutige Feldwerte angezeigt: tabelle={cache['tabellenname']}, spalte={spaltenname}, "
        f"datensaetze={anzahl_datensaetze}, eindeutig={anzahl_eindeutig}, filter_aktiv={cache.get('filter_aktiv')}",
        "allgemein"
    )


def tabellenfenster_zeile_in_zwischenablage(fenster_id):
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id") or (cache["tree"].selection()[0] if cache["tree"].selection() else None)
    if not item_id:
        return
    text = "\t".join(str(v) for v in cache["tree"].item(item_id, "values"))
    cache["fenster"].clipboard_clear()
    cache["fenster"].clipboard_append(text)


def tabellenfenster_zeile_im_lesefenster_anzeigen(fenster_id):
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id") or (cache["tree"].selection()[0] if cache["tree"].selection() else None)
    if not item_id:
        messagebox.showwarning("Zeileninhalt", "Bitte zuerst eine Zeile auswählen.", parent=cache["fenster"])
        return
    spalten = list(cache.get("spalten", []))
    werte = list(cache["tree"].item(item_id, "values"))
    zeilen = [
        f"Tabelle: {cache.get('tabellenname', '')}",
        "",
    ]
    for index, spaltenname in enumerate(spalten):
        wert = werte[index] if index < len(werte) else ""
        zeilen.append(f"{spaltenname}: {wert}")
    gui_csv_zelltext_anzeigen(
        cache["fenster"],
        f"Zeileninhalt - {cache.get('tabellenname', '')}",
        "\n".join(zeilen),
    )


def tabellenfenster_logging_lesefenster_anzeigen(fenster_id):
    """Zeigt die meldung-Spalte einer Logging-Zeile im Lesefenster an – mit Navigation."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id") or (
        cache["tree"].selection()[0] if cache["tree"].selection() else None
    )
    if not item_id:
        messagebox.showwarning(
            "Logging-Eintrag", "Bitte zuerst eine Zeile auswählen.", parent=cache["fenster"]
        )
        return
    tabellenname = cache.get("tabellenname", "")
    tree = cache["tree"]
    spalten = list(cache.get("spalten", []))

    def get_anzeigetext(iid):
        werte = list(tree.item(iid, "values"))
        midx = next((i for i, s in enumerate(spalten) if s.lower() == "meldung"), None)
        if midx is not None and midx < len(werte):
            meldung = str(werte[midx]) if werte[midx] is not None else ""
        else:
            meldung = "\n".join(f"{s}: {werte[i] if i < len(werte) else ''}" for i, s in enumerate(spalten))
        meta = []
        for ms in ("id", "datetime", "status"):
            for i, s in enumerate(spalten):
                if s.lower() == ms and i < len(werte):
                    meta.append(f"{s}: {werte[i]}")
                    break
        kopf = " | ".join(meta)
        return f"{kopf}\n\n{meldung}" if kopf else meldung

    def get_titel(iid):
        alle = list(tree.get_children())
        pos = alle.index(iid) + 1 if iid in alle else "?"
        return f"Logging-Eintrag – {tabellenname}  [{pos}/{len(alle)}]"

    nav = {"item_id": item_id}

    def nav_hoch(aktualisieren):
        alle = list(tree.get_children())
        try:
            idx = alle.index(nav["item_id"])
        except ValueError:
            return
        if idx > 0:
            nav["item_id"] = alle[idx - 1]
            tree.selection_set(nav["item_id"])
            tree.focus(nav["item_id"])
            tree.see(nav["item_id"])
            cache["kontext_item_id"] = nav["item_id"]
            aktualisieren(get_anzeigetext(nav["item_id"]), get_titel(nav["item_id"]))

    def nav_runter(aktualisieren):
        alle = list(tree.get_children())
        try:
            idx = alle.index(nav["item_id"])
        except ValueError:
            return
        if idx < len(alle) - 1:
            nav["item_id"] = alle[idx + 1]
            tree.selection_set(nav["item_id"])
            tree.focus(nav["item_id"])
            tree.see(nav["item_id"])
            cache["kontext_item_id"] = nav["item_id"]
            aktualisieren(get_anzeigetext(nav["item_id"]), get_titel(nav["item_id"]))

    gui_csv_zelltext_anzeigen(
        cache["fenster"],
        get_titel(item_id),
        get_anzeigetext(item_id),
        nav_hoch=nav_hoch,
        nav_runter=nav_runter,
    )


def tabellenfenster_filter_dialog_oeffnen(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tree_widget = cache["tree"]
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        return
    spaltenindex = int(spalte_id.replace("#", "")) - 1
    if spaltenindex < 0 or spaltenindex >= len(cache.get("spalten", [])):
        return
    spaltenname = cache["spalten"][spaltenindex]
    werte = tree_widget.item(item_id, "values")
    feldwert = str(werte[spaltenindex]) if spaltenindex < len(werte) else ""

    dialog = tk.Toplevel(fenster)
    dialog.title(f"{G_EXE_Title} - {cache['tabellenname']} * Feld filtern")
    dialog.geometry("520x200")
    dialog.minsize(420, 180)
    dialog.transient(fenster)
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

    info = tk.Label(frame, text="Der aktuelle Zellinhalt wurde als Filter vorgeschlagen.", anchor="w")
    info.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

    button_frame = tk.Frame(frame)
    button_frame.grid(row=3, column=0, columnspan=2, sticky="e")

    def anwenden():
        filterwert_neu = filter_text.get("1.0", "end").strip()
        tabellenfenster_filter_anwenden(fenster_id, spaltenname, filterwert_neu)
        dialog.destroy()

    tk.Button(button_frame, text="Abbrechen", command=dialog.destroy, width=12).pack(side="right")
    tk.Button(button_frame, text="Hiernach filtern", command=anwenden, width=14).pack(side="right", padx=(0, 8))

    filter_text.focus_force()
    dialog.bind("<Return>", lambda event: anwenden())
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

def tabellenfenster_filter_anwenden(fenster_id, spaltenname, filterwert):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tree_widget = cache["tree"]
    if spaltenname not in cache.get("spalten", []):
        return
    filterwert = str(filterwert)
    spaltenindex = cache["spalten"].index(spaltenname)
    gefilterte_zeilen = []
    for row in cache.get("zeilen", []):
        zellwert = ""
        if spaltenindex < len(row):
            zellwert = "" if row[spaltenindex] is None else str(row[spaltenindex])
        if filterwert.lower() in zellwert.lower():
            gefilterte_zeilen.append(row)
    tree_widget.delete(*tree_widget.get_children())
    for zeile in gefilterte_zeilen:
        tree_widget.insert("", "end", values=zeile)
    cache["filter_aktiv"] = True
    cache["filter_info"] = {"spalte": spaltenname, "wert": filterwert}
    cache["suchtreffer_ids"] = []
    cache["suchtreffer_index"] = -1
    tree_widget.tag_configure("suchtreffer", background="#fff3b0", foreground="black")
    tree_widget.tag_configure("aktiver_suchtreffer", background="#ffd166", foreground="black")
    treffer_anzahl = len(gefilterte_zeilen)
    tabellenfenster_basis_titel_setzen(fenster_id, f" * gefiltert nach {spaltenname} * enthält '{filterwert}' ({treffer_anzahl} Treffer)")
    if treffer_anzahl == 0:
        aufheben = messagebox.askyesno(
            'Filter ohne Treffer',
            f"Der Filter auf '{spaltenname}' mit '{filterwert}' liefert 0 Treffer.\n\nSoll der Filter direkt wieder aufgehoben werden?",
            parent=fenster
        )
        if aufheben:
            tabellenfenster_filter_aufheben(fenster_id)

def tabellenfenster_filter_aufheben(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    tree_widget = cache["tree"]
    tree_widget.delete(*tree_widget.get_children())
    for zeile in cache.get("zeilen", []):
        tree_widget.insert("", "end", values=zeile)
    cache["filter_aktiv"] = False
    cache["filter_info"] = None
    cache["suchtreffer_ids"] = []
    cache["suchtreffer_index"] = -1
    tree_widget.tag_configure("suchtreffer", background="#fff3b0", foreground="black")
    tree_widget.tag_configure("aktiver_suchtreffer", background="#ffd166", foreground="black")
    gesamt_formatiert = f"{len(cache.get('zeilen', [])):,}".replace(",", ".")
    tabellenfenster_basis_titel_setzen(fenster_id, f" * Filter aufgehoben ({gesamt_formatiert} Datensätze)")


def tabellenfenster_ip_filter_anwenden(fenster_id):
    """Filtert die aktuelle Spalte auf Zeilen die eine IP-Adresse oder CIDR enthalten."""
    import re
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    spalte_id = cache.get("kontext_spalte_id")
    if not spalte_id:
        messagebox.showwarning("IP-Filter", "Bitte zuerst eine Spalte auswählen.", parent=cache["fenster"])
        return
    index = int(spalte_id.replace("#", "")) - 1
    spalten = list(cache.get("spalten", []))
    spaltenname = spalten[index] if index < len(spalten) else f"Spalte{index+1}"
    ip_regex = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?')
    tree = cache["tree"]
    alle_zeilen = cache.get("zeilen", [])
    treffer = [z for z in alle_zeilen if index < len(z) and ip_regex.search(str(z[index]))]
    if not treffer:
        messagebox.showinfo(
            "IP-Filter",
            f"In der Spalte '{spaltenname}' wurden keine Zeilen mit IP-Adresse oder Netzmaske gefunden.",
            parent=cache["fenster"]
        )
        return
    # Tree neu aufbauen mit nur den Treffern
    tree.delete(*tree.get_children())
    for zeile in treffer:
        tree.insert("", "end", values=zeile)
    cache["filter_aktiv"] = True
    cache["filter_info"] = f"IP-Filter: {spaltenname}"
    treffer_formatiert = f"{len(treffer):,}".replace(",", ".")
    tabellenfenster_basis_titel_setzen(fenster_id, f"  * IP-Filter: {spaltenname} ({treffer_formatiert} Treffer)")


def tabellenfenster_maske_filter_anwenden(fenster_id):
    """Filtert die aktuelle Spalte auf Zeilen die eine Netzmaske (CIDR /xx) enthalten."""
    import re
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    spalte_id = cache.get("kontext_spalte_id")
    if not spalte_id:
        messagebox.showwarning("Masken-Filter", "Bitte zuerst eine Spalte auswählen.", parent=cache["fenster"])
        return
    index = int(spalte_id.replace("#", "")) - 1
    spalten = list(cache.get("spalten", []))
    spaltenname = spalten[index] if index < len(spalten) else f"Spalte{index+1}"
    # Schrägstrich gefolgt von 1-2 Ziffern (0-32)
    maske_regex = re.compile(r'/(\d{1,2})\b')
    tree = cache["tree"]
    alle_zeilen = cache.get("zeilen", [])
    treffer = []
    for z in alle_zeilen:
        feldwert = str(z[index]) if index < len(z) else ""
        m = maske_regex.search(feldwert)
        if m:
            wert = int(m.group(1))
            if 0 <= wert <= 32:
                treffer.append(z)
    if not treffer:
        messagebox.showinfo(
            "Masken-Filter",
            f"In der Spalte '{spaltenname}' wurden keine Zeilen mit Netzmaske (/xx) gefunden.",
            parent=cache["fenster"]
        )
        return
    tree.delete(*tree.get_children())
    for zeile in treffer:
        tree.insert("", "end", values=zeile)
    cache["filter_aktiv"] = True
    cache["filter_info"] = f"Masken-Filter: {spaltenname}"
    treffer_formatiert = f"{len(treffer):,}".replace(",", ".")
    tabellenfenster_basis_titel_setzen(fenster_id, f"  * Masken-Filter: {spaltenname} ({treffer_formatiert} Treffer)")

def tabellenfenster_linksklick_auf_zelle(event, fenster_id):
    if fenster_id not in G_tabellen_cache:
        return
    cache = G_tabellen_cache[fenster_id]
    tree_widget = cache["tree"]
    region = tree_widget.identify("region", event.x, event.y)
    if region != "cell":
        return
    item_id = tree_widget.identify_row(event.y)
    spalte_id = tree_widget.identify_column(event.x)
    if not item_id or not spalte_id:
        return
    cache["kontext_item_id"] = item_id
    cache["kontext_spalte_id"] = spalte_id
    tree_widget.focus(item_id)
    tree_widget.selection_set(item_id)

def tabellenfenster_doppelklick_auf_zelle(event, fenster_id):
    if fenster_id not in G_tabellen_cache:
        return
    cache = G_tabellen_cache[fenster_id]
    tree_widget = cache["tree"]
    region = tree_widget.identify("region", event.x, event.y)
    if region != "cell":
        return
    item_id = tree_widget.identify_row(event.y)
    spalte_id = tree_widget.identify_column(event.x)
    if not item_id or not spalte_id:
        return
    cache["kontext_item_id"] = item_id
    cache["kontext_spalte_id"] = spalte_id
    tree_widget.focus(item_id)
    tree_widget.selection_set(item_id)
    tree_widget.see(item_id)
    # Bei Logging-Tabellen: spezielles Lesefenster mit meldung-Formatierung
    if projekt_ist_logging_tabelle(cache.get("tabellenname", "")):
        tabellenfenster_logging_lesefenster_anzeigen(fenster_id)
    else:
        tabellenfenster_feld_im_lesefenster_anzeigen(fenster_id)

def tabellenfenster_aktuelle_anzeige_als_csv_speichern(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tree_widget = cache["tree"]
    spalten = list(cache.get("spalten", []))
    if not spalten:
        messagebox.showwarning("CSV speichern", "Es sind keine Spalten vorhanden.", parent=fenster)
        return
    items = tree_widget.get_children()
    if not items:
        messagebox.showwarning("CSV speichern", "Es sind keine Datensätze in der aktuellen Anzeige vorhanden.", parent=fenster)
        return
    export_dir = export_verzeichnis_sicherstellen()
    basisname = f"{cache['tabellenname']}_export"
    vorgeschlagen = eindeutigen_dateinamen_vorschlagen(export_dir, basisname, ".csv")
    dateipfad = filedialog.asksaveasfilename(
        title="Aktuelle Anzeige als CSV speichern",
        defaultextension=".csv",
        initialfile=vorgeschlagen,
        initialdir=str(export_dir),
        filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")],
        parent=fenster,
    )
    if not dateipfad:
        return
    try:
        with open(dateipfad, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(spalten)
            for item_id in items:
                writer.writerow(list(tree_widget.item(item_id, "values")))
        anzahl = len(items)
        tabellenfenster_temp_hinweis(fenster_id, f" * CSV gespeichert ({anzahl} Datensätze)")
        messagebox.showinfo("CSV gespeichert", f"Die aktuelle Ergebnismenge wurde als CSV gespeichert.\n\nDatei: {dateipfad}\nDatensätze: {anzahl}", parent=fenster)
    except Exception as e:
        messagebox.showerror("CSV speichern", f"Die CSV-Datei konnte nicht gespeichert werden:\n{e}", parent=fenster)


def tabellenfenster_aktuelle_anzeige_als_tabelle_speichern(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    tree_widget = cache["tree"]
    spalten = list(cache.get("spalten", []))
    if not spalten:
        messagebox.showwarning("Als Tabelle speichern", "Es sind keine Spalten vorhanden.", parent=fenster)
        return
    items = tree_widget.get_children()
    if not items:
        messagebox.showwarning("Als Tabelle speichern", "Es sind keine Datensätze in der aktuellen Anzeige vorhanden.", parent=fenster)
        return
    zeilen = [list(tree_widget.item(item_id, "values")) for item_id in items]
    standardname = f"{cache['tabellenname']}_Ergebnis"
    if cache.get("filter_aktiv"):
        standardname = f"{cache['tabellenname']}_Filter"
    standardname = eindeutigen_tabellennamen_vorschlagen(standardname)
    debug_log(
        f"Tabellenfenster-Ergebnismenge als Tabelle speichern: quelle={cache['tabellenname']}, "
        f"ziel_vorschlag={standardname}, spalten={len(spalten)}, zeilen={len(zeilen)}, "
        f"filter_aktiv={cache.get('filter_aktiv')}",
        "allgemein"
    )
    sql_ergebnis_als_tabelle_speichern(fenster, standardname, spalten, zeilen)


def tabellenfenster_rechtsklick(event, fenster_id):
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tree_widget = cache["tree"]
    # Nur bei Klick auf Zelle (nicht Heading) das Zellenmenü zeigen
    region = tree_widget.identify("region", event.x, event.y)
    if region == "heading":
        return  # Heading-Klick wird von tabellenfenster_heading_oder_zelle_rechtsklick behandelt
    item_id = tree_widget.identify_row(event.y)
    spalte_id = tree_widget.identify_column(event.x)
    if item_id:
        tree_widget.focus(item_id)
        tree_widget.selection_set(item_id)
    cache["kontext_item_id"] = item_id
    cache["kontext_spalte_id"] = spalte_id
    menu = tk.Menu(cache["fenster"], tearoff=0)
    # Block 1: Kopieren
    menu.add_command(label="Feldinhalt kopieren", command=lambda: tabellenfenster_feld_in_zwischenablage(fenster_id))
    menu.add_command(label="Zeile kopieren", command=lambda: tabellenfenster_zeile_in_zwischenablage(fenster_id))
    menu.add_command(label="Zeile als CSV kopieren", command=lambda: tabellenfenster_zeile_als_csv_in_zwischenablage(fenster_id))
    menu.add_command(label="Header als CSV kopieren", command=lambda: tabellenfenster_header_als_csv_in_zwischenablage(fenster_id))
    menu.add_command(label="Tabelle als CSV kopieren", command=lambda: tabellenfenster_tabelle_als_csv_kopieren(fenster_id))
    menu.add_separator()
    # Block 2: Anzeigen
    menu.add_command(label="Feldinhalt im Lesefenster anzeigen", command=lambda: tabellenfenster_feld_im_lesefenster_anzeigen(fenster_id))
    menu.add_command(label="Zeile im Lesefenster anzeigen", command=lambda: tabellenfenster_zeile_im_lesefenster_anzeigen(fenster_id))
    menu.add_separator()
    # Block 3: Filtern
    menu.add_command(label="Feldfilter setzen", command=lambda: tabellenfenster_filter_dialog_oeffnen(fenster_id))
    menu.add_command(label="Feldfilter aufheben", command=lambda: tabellenfenster_filter_aufheben(fenster_id))
    menu.add_command(label="Eindeutige Feldwerte anzeigen", command=lambda: tabellenfenster_eindeutige_feldwerte_anzeigen(fenster_id))
    menu.add_command(label="Auf IP/Netzwerk filtern", command=lambda: tabellenfenster_ip_filter_anwenden(fenster_id))
    menu.add_command(label="Auf Netzmaske filtern", command=lambda: tabellenfenster_maske_filter_anwenden(fenster_id))
    menu.add_separator()
    # Block 4: IPv4
    menu.add_command(label="Integer zu IPv4-Adresse", command=lambda: tabellenfenster_integer_zu_ipv4_anzeigen(fenster_id))
    menu.add_command(label="IPv4-Adresse zu Integer", command=lambda: tabellenfenster_ipv4_zu_integer_anzeigen(fenster_id))
    menu.add_command(label="IP-Range aufteilen", command=lambda: tabellenfenster_ip_range_aufteilen_anzeigen(fenster_id))
    menu.add_command(label="Netzwerk IP oder Maske anzeigen", command=lambda: tabellenfenster_netzwerk_ip_anzeigen(fenster_id))
    menu.add_separator()
    # Block 5: Beziehungen
    menu.add_command(label="Verknüpfte Datensätze anzeigen", command=lambda: tabellenfenster_verknuepfte_datensaetze_anzeigen(fenster_id))
    menu.add_separator()
    # Block 6: Findings / Zeile löschen
    menu.add_command(label="Finding hinzufügen", command=lambda: tabellenfenster_finding_hinzufuegen(fenster_id))
    menu.add_command(label="Finding aufrufen", command=lambda: tabellenfenster_finding_aufrufen(fenster_id))
    menu.add_separator()
    menu.add_command(label="Zeile löschen", command=lambda: tabellenfenster_zeile_loeschen(fenster_id))
    menu.add_separator()
    menu.add_command(label="Feld editieren", command=lambda: tabellenfenster_feld_editieren(fenster_id))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def tabellenfenster_finding_hinzufuegen(fenster_id):
    """Speichert das angeklickte Feld als Finding in zzz_Findings. Bei Duplikat: Update der Beschreibung."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        messagebox.showwarning("Finding hinzufügen", "Bitte zuerst eine Zelle auswählen.", parent=cache["fenster"])
        return
    tabellenname = cache.get("tabellenname", "")
    spalten = list(cache.get("spalten", []))
    werte = cache["tree"].item(item_id, "values")
    spalten_index = int(spalte_id.replace("#", "")) - 1
    if spalten_index < 0 or spalten_index >= len(spalten):
        messagebox.showwarning("Finding hinzufügen", "Ungültige Spaltenauswahl.", parent=cache["fenster"])
        return
    feldname = spalten[spalten_index]
    feld_inhalt = str(werte[spalten_index]) if spalten_index < len(werte) else ""
    if not feld_inhalt:
        messagebox.showwarning("Finding hinzufügen", "Leere Zellen können nicht als Finding übernommen werden.", parent=cache["fenster"])
        return
    pk_feldname, pk_wert = tabellenfenster_pk_ermitteln(fenster_id)
    if not pk_feldname:
        messagebox.showwarning(
            "Finding hinzufügen",
            "Diese Tabelle hat keinen Primary Key.\n\nBitte zuerst einen PK hinzufügen:\nTabelle-Menü → PK hinzufügen",
            parent=cache["fenster"],
        )
        return
    fenster = cache["fenster"]

    # Prüfen ob Finding für diesen Datensatz bereits existiert
    findings_tabelle_anlegen()
    id_feld_wert = pk_feldname or ""
    id_inhalt_wert = str(pk_wert) if pk_wert is not None else ""
    bestehende_beschreibung = None
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT KurzeBeschreibung FROM {sql_identifier(G_TABELLE_FINDINGS)} "
            f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
            (tabellenname, id_feld_wert, id_inhalt_wert),
        )
        row = cursor.fetchone()
        verbindung.close()
        if row:
            bestehende_beschreibung = row[0] or ""
    except Exception:
        pass

    ist_update = bestehende_beschreibung is not None
    if ist_update:
        messagebox.showinfo(
            "Finding existiert bereits",
            "Für diesen Datensatz existiert bereits ein Finding.\nDie bestehende Beschreibung wird zur Bearbeitung geöffnet.",
            parent=fenster,
        )

    # Bestehende Beschreibungen als Auswahlliste laden
    vorhandene_beschreibungen = []
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT DISTINCT KurzeBeschreibung FROM {sql_identifier(G_TABELLE_FINDINGS)} "
            f"WHERE KurzeBeschreibung IS NOT NULL AND KurzeBeschreibung != '' "
            f"ORDER BY KurzeBeschreibung"
        )
        vorhandene_beschreibungen = [row[0] for row in cursor.fetchall()]
        verbindung.close()
    except Exception:
        pass

    dialog = tk.Toplevel(fenster)
    dialog.title("Finding bearbeiten" if ist_update else "Finding hinzufügen")
    dialog.geometry("520x280")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(fenster)
    dialog.columnconfigure(1, weight=1)

    def readonly_row(label, wert, zeile):
        tk.Label(dialog, text=label, anchor="w").grid(row=zeile, column=0, sticky="w", padx=16, pady=(6, 0))
        var = tk.StringVar(value=wert)
        e = tk.Entry(dialog, textvariable=var, state="readonly", width=52)
        e.grid(row=zeile, column=1, padx=(0, 16), pady=(6, 0), sticky="ew")

    readonly_row("Tabelle:", tabellenname, 0)
    readonly_row("ID-Feld:", pk_feldname or "(kein PK)", 1)
    readonly_row("ID-Inhalt:", id_inhalt_wert, 2)
    readonly_row("Feldname:", feldname, 3)
    readonly_row("Feldinhalt:", feld_inhalt, 4)
    tk.Label(dialog, text="Kurze Beschreibung:", anchor="w").grid(row=5, column=0, sticky="w", padx=16, pady=(6, 0))
    beschreibung_var = tk.StringVar(value=bestehende_beschreibung or "")
    beschreibung_entry = ttk.Combobox(dialog, textvariable=beschreibung_var, values=vorhandene_beschreibungen, width=50)
    beschreibung_entry.grid(row=5, column=1, padx=(0, 16), pady=(6, 0), sticky="ew")
    beschreibung_entry.focus_set()

    ergebnis = [None]

    def bestaetigen(event=None):
        ergebnis[0] = beschreibung_var.get().strip()
        dialog.destroy()

    def abbrechen():
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.grid(row=6, column=0, columnspan=2, pady=(14, 0))
    tk.Button(btn_frame, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 16))
    tk.Button(btn_frame, text="Abbrechen", width=12, command=abbrechen).pack(side="right")
    beschreibung_entry.bind("<Return>", bestaetigen)
    beschreibung_entry.bind("<Escape>", lambda e: abbrechen())
    dialog.wait_window()

    if ergebnis[0] is None:
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if ist_update:
            cursor.execute(
                f"UPDATE {sql_identifier(G_TABELLE_FINDINGS)} "
                f"SET Feldname=?, FeldInhalt=?, KurzeBeschreibung=?, datetime=? "
                f"WHERE TabellenName=? AND idFeld=? AND idFeldInhalt=?",
                (feldname, feld_inhalt, ergebnis[0], jetzt, tabellenname, id_feld_wert, id_inhalt_wert),
            )
            log_aktion = "Finding aktualisiert"
        else:
            cursor.execute(
                f"INSERT INTO {sql_identifier(G_TABELLE_FINDINGS)} "
                f"(TabellenName, idFeld, idFeldInhalt, Feldname, FeldInhalt, KurzeBeschreibung, datetime) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tabellenname, id_feld_wert, id_inhalt_wert, feldname, feld_inhalt, ergebnis[0], jetzt),
            )
            log_aktion = "Finding hinzugefügt"
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(
            f"{log_aktion}: {tabellenname} / {feldname} = {feld_inhalt[:50]}\n"
            f". Beschreibung: {ergebnis[0][:100]}"
        )
        messagebox.showinfo(log_aktion, "Das Finding wurde gespeichert.", parent=fenster)
    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Speichern des Findings: {e}", 1)
        messagebox.showerror("Finding hinzufügen", f"Fehler:\n{e}", parent=fenster)


def _join_fenster_aufbauen(quell_tab, filter_feld, filter_wert, folge_rel, parent_win):
    """Öffnet ein JOIN-Ergebnisfenster: quell_tab LEFT JOIN ziel_tab, gefiltert nach filter_feld=filter_wert."""
    join_tab = folge_rel["ziel_tabelle"]
    join_qf  = folge_rel["quell_feld"]   # Feld in quell_tab (z.B. BoundaryID)
    join_zf  = folge_rel["ziel_feld"]    # Feld in join_tab  (z.B. BoundaryID)
    try:
        vb = sqlite_verbindung_oeffnen()
        q1_cols = [r[1] for r in vb.execute(
            f"PRAGMA table_info({sql_identifier(quell_tab)})"
        ).fetchall()]
        q2_cols = [r[1] for r in vb.execute(
            f"PRAGMA table_info({sql_identifier(join_tab)})"
        ).fetchall()]
        select_teile = (
            [f"t1.{sql_identifier(c)}" for c in q1_cols] +
            [f"t2.{sql_identifier(c)}" for c in q2_cols]
        )
        sql = (
            f"SELECT {', '.join(select_teile)} "
            f"FROM {sql_identifier(quell_tab)} t1 "
            f"LEFT JOIN {sql_identifier(join_tab)} t2 "
            f"ON t2.{sql_identifier(join_zf)} = t1.{sql_identifier(join_qf)} "
            f"WHERE t1.{sql_identifier(filter_feld)} = ?"
        )
        cursor = vb.cursor()
        cursor.execute(sql, (filter_wert,))
        zeilen = cursor.fetchall()
        vb.close()
    except Exception as e:
        messagebox.showerror("JOIN-Ansicht", f"Fehler:\n{e}", parent=parent_win)
        return

    alle_spalten = (
        [f"{quell_tab}.{c}" for c in q1_cols] +
        [f"{join_tab}.{c}" for c in q2_cols]
    )

    win = tk.Toplevel(parent_win)
    win.title(f"{quell_tab} ⋈ {join_tab}  –  {filter_feld} = '{filter_wert}'")
    win.geometry("1100x500")
    win.minsize(500, 200)
    fenster_registrieren(win, "JOIN-Ansicht")
    fenster_standard_menue_anbringen(win, "1100x500",
                                     f"{quell_tab} ⋈ {join_tab}  –  {filter_feld} = '{filter_wert}'")

    haupt = tk.Frame(win)
    haupt.pack(fill="both", expand=True, padx=8, pady=8)

    kopf = (f"{quell_tab}  ⋈  {join_tab}   "
            f"(via {quell_tab}.{join_qf} = {join_tab}.{join_zf},  "
            f"{filter_feld} = '{filter_wert}')   –   {len(zeilen)} Zeilen")
    tk.Label(haupt, text=kopf, anchor="w", font=("Segoe UI", 9, "bold"),
             wraplength=1060, justify="left").pack(fill="x", pady=(0, 6))

    tv_frame = tk.Frame(haupt)
    tv_frame.pack(fill="both", expand=True)

    tv = ttk.Treeview(tv_frame, columns=alle_spalten, show="headings")
    for sp in alle_spalten:
        tv.heading(sp, text=sp)
        tv.column(sp, width=110, anchor="w", minwidth=50)
    for zeile in zeilen:
        tv.insert("", "end", values=[str(v) if v is not None else "" for v in zeile])

    sy = ttk.Scrollbar(tv_frame, orient="vertical",   command=tv.yview)
    sx = ttk.Scrollbar(tv_frame, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    sy.pack(side="right",  fill="y")
    sx.pack(side="bottom", fill="x")
    tv.pack(fill="both", expand=True)
    win.focus_set()


def _verknuepfte_datensaetze_fenster_aufbauen(tabellenname, spalten, werte, parent_win, projekt):
    """Baut ein 'Verknüpfte Datensätze'-Fenster auf. Kann rekursiv (Drill-Down) aufgerufen werden."""

    alle_relationen = relationen_fuer_projekt_laden(projekt)

    # Welche Tabellen haben selbst ausgehende Beziehungen? (für Drill-Down-Hinweis)
    tabellen_mit_ausgehenden = {r["quell_tabelle"].lower() for r in alle_relationen}

    # Nur Beziehungen, bei denen diese Tabelle die QuellTabelle ist
    relationen = [r for r in alle_relationen
                  if r["quell_tabelle"].lower() == tabellenname.lower()]

    if not relationen:
        messagebox.showinfo(
            "Verknüpfte Datensätze",
            f"Keine Beziehungen für Tabelle '{tabellenname}' im Projekt '{projekt}' definiert.\n\n"
            "Beziehungen können im SQL-Editor unter PROJEKT → Tabellenbeziehungen definiert werden.",
            parent=parent_win
        )
        return

    win = tk.Toplevel(parent_win)
    win.title(f"Verknüpfte Datensätze – {tabellenname}  ●  {projekt}")
    win.geometry("900x600")
    win.minsize(400, 200)
    fenster_registrieren(win, "Verknüpfte Datensätze")
    fenster_standard_menue_anbringen(win, "900x600", f"Verknüpfte Datensätze – {tabellenname}")

    haupt = tk.Frame(win)
    haupt.pack(fill="both", expand=True, padx=8, pady=8)

    # Kopfzeile: Quellzeile (max. 6 Felder anzeigen)
    kopf_text = "  ".join(
        f"{sp}: {werte[i] if i < len(werte) else ''}"
        for i, sp in enumerate(spalten[:6])
    )
    if len(spalten) > 6:
        kopf_text += f"  … (+{len(spalten)-6} Felder)"
    tk.Label(haupt, text=f"Quelle: {tabellenname}  –  {kopf_text}",
             anchor="w", font=("Segoe UI", 9, "bold"),
             wraplength=860, justify="left").pack(fill="x", pady=(0, 8))

    # Scrollbarer Bereich für die Ergebnisblöcke
    canvas = tk.Canvas(haupt, borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(haupt, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas)
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    scroll_frame.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    gesamt_treffer = 0

    for rel in relationen:
        quell_feld  = rel["quell_feld"]
        ziel_tab    = rel["ziel_tabelle"]
        ziel_feld   = rel["ziel_feld"]
        bezeichnung = rel["bezeichnung"]
        typ         = rel.get("typ", "1:N")

        # Wert aus der Quellzeile holen
        quell_wert = ""
        if quell_feld in spalten:
            idx = spalten.index(quell_feld)
            quell_wert = str(werte[idx]) if idx < len(werte) else ""

        # Blocküberschrift
        block_titel = bezeichnung if bezeichnung else f"{quell_feld} → {ziel_tab}.{ziel_feld}"
        ttk.Separator(scroll_frame, orient="horizontal").pack(fill="x", pady=(10, 4))
        tk.Label(scroll_frame,
                 text=f"══  [{typ}]  {block_titel}  ({quell_feld} = '{quell_wert}')  ══",
                 anchor="w", font=("Segoe UI", 9, "bold")).pack(fill="x", padx=4)

        # Abfrage (einfach oder Kette)
        try:
            verbindung = sqlite_verbindung_oeffnen()
            cursor = verbindung.cursor()
            kette_raw = rel.get("kette", "")
            if kette_raw:
                import json as _json
                kette_liste = _json.loads(kette_raw)
                tabellen = [tabellenname] + [s["zu_tab"] for s in kette_liste]
                aliases  = [f"_kt{i}" for i in range(len(tabellen))]
                anzeigen = rel.get("anzeigen_felder", "")
                if anzeigen:
                    felder_liste = [f.strip() for f in anzeigen.split(",") if f.strip()]
                    select = ", ".join(
                        f"{aliases[-1]}.{sql_identifier(f)}" for f in felder_liste)
                    ziel_spalten = felder_liste
                else:
                    select = f"{aliases[-1]}.*"
                    ziel_spalten = None
                joins = " ".join(
                    f"LEFT JOIN {sql_identifier(s['zu_tab'])} {aliases[i+1]} "
                    f"ON {aliases[i+1]}.{sql_identifier(s['zu_feld'])} "
                    f"= {aliases[i]}.{sql_identifier(s['von_feld'])}"
                    for i, s in enumerate(kette_liste)
                )
                sql = (f"SELECT {select} "
                       f"FROM {sql_identifier(tabellenname)} {aliases[0]} "
                       f"{joins} "
                       f"WHERE {aliases[0]}.{sql_identifier(quell_feld)}=?")
                cursor.execute(sql, (quell_wert,))
                if ziel_spalten is None:
                    ziel_spalten = [d[0] for d in cursor.description]
            else:
                cursor.execute(
                    f"SELECT * FROM {sql_identifier(ziel_tab)} "
                    f"WHERE {sql_identifier(ziel_feld)}=?",
                    (quell_wert,)
                )
                ziel_spalten = [d[0] for d in cursor.description]
            ziel_zeilen = cursor.fetchall()
            verbindung.close()
        except Exception as e:
            tk.Label(scroll_frame, text=f"  Fehler: {e}", fg="red", anchor="w").pack(fill="x", padx=8)
            continue

        anzahl = len(ziel_zeilen)
        gesamt_treffer += anzahl

        hat_weiteres = ziel_tab.lower() in tabellen_mit_ausgehenden
        info_text = f"  {anzahl} Datensatz/Datensätze in {ziel_tab}"
        if hat_weiteres:
            info_text += "   ▶ Rechtsklick für Drill-Down"
        tk.Label(scroll_frame, text=info_text, anchor="w", fg="#555555").pack(fill="x", padx=8)

        if anzahl == 0:
            continue

        # Treeview für diese Relation
        tv_frame = tk.Frame(scroll_frame)
        tv_frame.pack(fill="x", padx=4, pady=(2, 4))
        tv = ttk.Treeview(tv_frame, columns=ziel_spalten, show="headings",
                          height=min(anzahl, 8))
        for sp in ziel_spalten:
            tv.heading(sp, text=sp)
            tv.column(sp, width=120, anchor="w")
        for zeile in ziel_zeilen:
            tv.insert("", "end", values=[str(v) if v is not None else "" for v in zeile])
        tv.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        sx = ttk.Scrollbar(tv_frame, orient="horizontal", command=tv.xview)
        tv.configure(xscrollcommand=sx.set)
        tv.pack(fill="x")
        sx.pack(fill="x")

        # Folgebeziehungen für JOIN ermitteln (vor _drill_down_binden, da auch dort benötigt)
        folge_rels = [r for r in alle_relationen
                      if r["quell_tabelle"].lower() == ziel_tab.lower()] if hat_weiteres else []

        # Rechtsklick-Menü: nur JOIN „Alle N Zeilen" (Fabrik-Funktion gegen Closure-Fehler)
        def _rechtsklick_binden(tv, ziel_tab, ziel_feld, quell_wert, win, folge_rels, anzahl):
            def on_rechtsklick(event):
                if not folge_rels:
                    return
                menu = tk.Menu(win, tearoff=0)
                for frel in folge_rels:
                    jt = frel["ziel_tabelle"]
                    def join_alle(ziel_tab=ziel_tab, ziel_feld=ziel_feld,
                                  quell_wert=quell_wert, frel=frel, win=win):
                        _join_fenster_aufbauen(ziel_tab, ziel_feld, quell_wert, frel, win)
                    menu.add_command(
                        label=f"▶▶  Alle {anzahl} Zeilen mit '{jt}' verknüpft anzeigen",
                        command=join_alle)
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()
            tv.bind("<Button-3>", on_rechtsklick)
        _rechtsklick_binden(tv, ziel_tab, ziel_feld, quell_wert, win, folge_rels, anzahl)

        # JOIN-Buttons unterhalb des Treeviews (für schnellen Zugriff ohne Rechtsklick)
        if folge_rels:
            def _join_btn_erstellen(sf, qt, ff, fv, frel, pw, n):
                jt  = frel["ziel_tabelle"]
                bez = frel["bezeichnung"] or f"{frel['quell_feld']} → {jt}.{frel['ziel_feld']}"
                tk.Button(
                    sf,
                    text=f"▶▶  Alle {n} Zeilen mit '{jt}' verknüpft anzeigen  [{bez}]",
                    anchor="w", relief="flat", fg="#005599", cursor="hand2",
                    font=("Segoe UI", 9),
                    command=lambda qt=qt, ff=ff, fv=fv, frel=frel, pw=pw:
                        _join_fenster_aufbauen(qt, ff, fv, frel, pw)
                ).pack(fill="x", padx=12, pady=(2, 2))

            for folge_rel in folge_rels:
                _join_btn_erstellen(scroll_frame, ziel_tab, ziel_feld,
                                    quell_wert, folge_rel, win, anzahl)

    if gesamt_treffer == 0:
        tk.Label(scroll_frame, text="Keine verknüpften Datensätze gefunden.",
                 anchor="w", fg="#888888").pack(fill="x", padx=8, pady=8)

    win.focus_set()


def tabellenfenster_verknuepfte_datensaetze_anzeigen(fenster_id):
    """Zeigt für die gewählte Zeile alle verknüpften Datensätze aus anderen Tabellen."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    if not G_aktives_projekt:
        messagebox.showinfo(
            "Verknüpfte Datensätze",
            "Kein Projekt aktiv.\n\nBitte zuerst ein Projekt aktivieren und Beziehungen definieren.",
            parent=cache["fenster"]
        )
        return
    item_id = cache.get("kontext_item_id")
    if not item_id:
        messagebox.showwarning("Verknüpfte Datensätze", "Bitte zuerst eine Zeile auswählen.",
                               parent=cache["fenster"])
        return
    tabellenname = cache.get("tabellenname", "")
    spalten      = list(cache.get("spalten", []))
    werte        = list(cache["tree"].item(item_id, "values"))
    _verknuepfte_datensaetze_fenster_aufbauen(
        tabellenname, spalten, werte, cache["fenster"], G_aktives_projekt)


def tabellenfenster_finding_aufrufen(fenster_id):
    """Öffnet die Original-Tabelle aus einem zzz_Findings-Eintrag und springt auf die referenzierte Zeile."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tabellenname = cache.get("tabellenname", "")
    if tabellenname.upper() != G_TABELLE_FINDINGS.upper():
        messagebox.showinfo("Finding aufrufen", "Diese Funktion ist nur in der Tabelle zzz_Findings verfügbar.", parent=cache["fenster"])
        return
    item_id = cache.get("kontext_item_id")
    if not item_id:
        messagebox.showwarning("Finding aufrufen", "Bitte zuerst eine Zeile auswählen.", parent=cache["fenster"])
        return
    spalten = list(cache.get("spalten", []))
    werte = cache["tree"].item(item_id, "values")

    def get_wert(feldname):
        if feldname in spalten:
            idx = spalten.index(feldname)
            return str(werte[idx]) if idx < len(werte) else ""
        return ""

    ziel_tabelle = get_wert("TabellenName")
    id_feld = get_wert("idFeld")
    id_inhalt = get_wert("idFeldInhalt")

    if not ziel_tabelle:
        messagebox.showwarning("Finding aufrufen", "Kein Tabellenname im Finding gespeichert.", parent=cache["fenster"])
        return
    if not id_feld or not id_inhalt:
        messagebox.showwarning("Finding aufrufen", "Kein ID-Feld oder ID-Inhalt im Finding gespeichert.", parent=cache["fenster"])
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (ziel_tabelle,))
        if not cursor.fetchone():
            verbindung.close()
            messagebox.showwarning("Finding aufrufen", f"Tabelle '{ziel_tabelle}' existiert nicht in der aktuellen Datenbank.", parent=cache["fenster"])
            return
        verbindung.close()
    except Exception as e:
        messagebox.showerror("Finding aufrufen", f"Fehler:\n{e}", parent=cache["fenster"])
        return

    tabellenfenster_oeffnen(ziel_tabelle)

    def zeile_anspringen():
        if ziel_tabelle not in G_tabellenfenster_nach_name:
            return
        ziel_fenster_id = G_tabellenfenster_nach_name[ziel_tabelle]
        ziel_cache = G_tabellen_cache.get(ziel_fenster_id)
        if not ziel_cache:
            return
        ziel_tree = ziel_cache["tree"]
        ziel_spalten = list(ziel_cache.get("spalten", []))
        if id_feld not in ziel_spalten:
            messagebox.showwarning("Finding aufrufen", f"Spalte '{id_feld}' nicht in Tabelle '{ziel_tabelle}' gefunden.", parent=ziel_cache["fenster"])
            return
        idx = ziel_spalten.index(id_feld)
        for iid in ziel_tree.get_children():
            zeilen_werte = ziel_tree.item(iid, "values")
            if idx < len(zeilen_werte) and str(zeilen_werte[idx]) == id_inhalt:
                ziel_tree.selection_set(iid)
                ziel_tree.see(iid)
                ziel_cache["kontext_item_id"] = iid
                return
        messagebox.showinfo("Finding aufrufen", f"Zeile mit {id_feld} = {id_inhalt} nicht gefunden (Tabelle noch nicht vollständig geladen?).", parent=ziel_cache["fenster"])

    root.after(800, zeile_anspringen)


def tabellenfenster_zeile_loeschen(fenster_id):
    """Löscht die aktuell markierte Zeile über den Primary Key nach Bestätigung."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tabellenname = cache.get("tabellenname", "")
    if not tabellenname:
        messagebox.showinfo("Zeile löschen", "In SQL-Ergebnisfenstern ist das Löschen nicht möglich.", parent=cache["fenster"])
        return
    item_id = cache.get("kontext_item_id")
    if not item_id:
        messagebox.showwarning("Zeile löschen", "Bitte zuerst eine Zeile auswählen.", parent=cache["fenster"])
        return
    pk_feldname, pk_wert = tabellenfenster_pk_ermitteln(fenster_id)
    if not pk_feldname or pk_wert is None:
        messagebox.showwarning("Zeile löschen", "Kein Primary Key gefunden. Löschen ist nicht möglich.", parent=cache["fenster"])
        return
    if not admin_code_fuer_aktion_pruefen(tabellenname, "löschen"):
        return
    spalten = list(cache.get("spalten", []))
    werte = cache["tree"].item(item_id, "values")
    zeilen_vorschau = ", ".join(f"{k}={v}" for k, v in zip(spalten[:3], werte[:3]))
    if not messagebox.askyesno(
        "Zeile löschen",
        f"Soll diese Zeile wirklich gelöscht werden?\n\n{pk_feldname} = {pk_wert}\n({zeilen_vorschau})",
        parent=cache["fenster"],
    ):
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"DELETE FROM {sql_identifier(tabellenname)} WHERE {sql_identifier(pk_feldname)} = ?",
            (pk_wert,),
        )
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(f"Zeile gelöscht: {tabellenname} / {pk_feldname} = {pk_wert}")
        try:
            pos_x = cache["fenster"].winfo_x()
            pos_y = cache["fenster"].winfo_y()
        except Exception:
            pos_x = pos_y = None
        tabellenfenster_schliessen(fenster_id)
        tabellenfenster_oeffnen(tabellenname)
        if pos_x is not None:
            try:
                if tabellenname in G_tabellenfenster_nach_name:
                    nf_id = G_tabellenfenster_nach_name[tabellenname]
                    nf = G_tabellen_cache.get(nf_id, {}).get("fenster")
                    if nf:
                        nf.update_idletasks()
                        nf.geometry(f"{nf.winfo_width()}x{nf.winfo_height()}+{pos_x}+{pos_y}")
            except Exception:
                pass
    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Löschen der Zeile in {tabellenname}: {e}", 1)
        messagebox.showerror("Zeile löschen", f"Fehler:\n{e}", parent=cache["fenster"])


def tabellenfenster_feld_editieren(fenster_id):
    """Bearbeitet den Inhalt des angeklickten Feldes direkt in der Tabelle."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tabellenname = cache.get("tabellenname", "")
    if not tabellenname:
        messagebox.showinfo("Feld editieren", "In SQL-Ergebnisfenstern ist das Editieren nicht möglich.", parent=cache["fenster"])
        return
    item_id = cache.get("kontext_item_id")
    spalte_id = cache.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        messagebox.showwarning("Feld editieren", "Bitte zuerst eine Zelle auswählen.", parent=cache["fenster"])
        return
    pk_feldname, pk_wert = tabellenfenster_pk_ermitteln(fenster_id)
    if not pk_feldname or pk_wert is None:
        messagebox.showwarning("Feld editieren", "Kein Primary Key gefunden. Bitte zuerst einen PK hinzufügen.", parent=cache["fenster"])
        return
    if not admin_code_fuer_aktion_pruefen(tabellenname, "editieren"):
        return
    spalten = list(cache.get("spalten", []))
    spalten_index = int(spalte_id.replace("#", "")) - 1
    if spalten_index < 0 or spalten_index >= len(spalten):
        messagebox.showwarning("Feld editieren", "Bitte zuerst eine Datenzelle auswählen.", parent=cache["fenster"])
        return
    feldname = spalten[spalten_index]
    fenster = cache["fenster"]

    # Aktuellen Wert direkt aus der DB lesen (nicht aus dem Treeview-Cache)
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"SELECT {sql_identifier(feldname)} FROM {sql_identifier(tabellenname)} "
            f"WHERE {sql_identifier(pk_feldname)} = ?",
            (pk_wert,),
        )
        row = cursor.fetchone()
        verbindung.close()
        if row is None:
            messagebox.showwarning("Feld editieren", f"Zeile mit {pk_feldname} = {pk_wert} nicht in der DB gefunden.", parent=fenster)
            return
        aktueller_wert = str(row[0]) if row[0] is not None else ""
    except Exception as e:
        messagebox.showerror("Feld editieren", f"Fehler beim Lesen des aktuellen Wertes:\n{e}", parent=fenster)
        return

    dialog = tk.Toplevel(fenster)
    dialog.title(f"Feld editieren: {feldname}")
    dialog.geometry("500x220")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(fenster)
    dialog.columnconfigure(1, weight=1)

    tk.Label(dialog, text="Tabelle:", anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))
    tk.Label(dialog, text=f"{tabellenname}  /  {pk_feldname} = {pk_wert}", anchor="w").grid(row=0, column=1, sticky="w", pady=(14, 0))

    tk.Label(dialog, text="Feldname:", anchor="w").grid(row=1, column=0, sticky="w", padx=16, pady=(8, 0))
    tk.Label(dialog, text=feldname, anchor="w", fg="navy").grid(row=1, column=1, sticky="w", pady=(8, 0))

    tk.Label(dialog, text="Alter Wert:", anchor="w").grid(row=2, column=0, sticky="w", padx=16, pady=(8, 0))
    alter_var = tk.StringVar(value=aktueller_wert)
    tk.Entry(dialog, textvariable=alter_var, state="readonly", width=52).grid(row=2, column=1, padx=(0, 16), pady=(8, 0), sticky="ew")

    tk.Label(dialog, text="Neuer Wert:", anchor="w").grid(row=3, column=0, sticky="w", padx=16, pady=(8, 0))
    wert_var = tk.StringVar(value=aktueller_wert)
    wert_entry = tk.Entry(dialog, textvariable=wert_var, width=52)
    wert_entry.grid(row=3, column=1, padx=(0, 16), pady=(8, 0), sticky="ew")
    wert_entry.focus_set()
    wert_entry.select_range(0, tk.END)

    ergebnis = [None]

    def bestaetigen(event=None):
        ergebnis[0] = wert_var.get()
        dialog.destroy()

    def abbrechen():
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=(14, 0))
    tk.Button(btn_frame, text="OK", width=12, command=bestaetigen).pack(side="right", padx=(8, 16))
    tk.Button(btn_frame, text="Abbrechen", width=12, command=abbrechen).pack(side="right")
    wert_entry.bind("<Return>", bestaetigen)
    wert_entry.bind("<Escape>", lambda e: abbrechen())
    dialog.wait_window()

    if ergebnis[0] is None:
        return
    neuer_wert = ergebnis[0]
    if neuer_wert == aktueller_wert:
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(
            f"UPDATE {sql_identifier(tabellenname)} "
            f"SET {sql_identifier(feldname)} = ? "
            f"WHERE {sql_identifier(pk_feldname)} = ?",
            (neuer_wert, pk_wert),
        )
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(
            f"Feld editiert: {tabellenname} / {pk_feldname} = {pk_wert}\n"
            f". {feldname}: '{aktueller_wert[:80]}' -> '{neuer_wert[:80]}'"
        )
        try:
            pos_x = cache["fenster"].winfo_x()
            pos_y = cache["fenster"].winfo_y()
        except Exception:
            pos_x = pos_y = None
        tabellenfenster_schliessen(fenster_id)
        tabellenfenster_oeffnen(tabellenname)
        if pos_x is not None:
            try:
                if tabellenname in G_tabellenfenster_nach_name:
                    nf_id = G_tabellenfenster_nach_name[tabellenname]
                    nf = G_tabellen_cache.get(nf_id, {}).get("fenster")
                    if nf:
                        nf.update_idletasks()
                        nf.geometry(f"{nf.winfo_width()}x{nf.winfo_height()}+{pos_x}+{pos_y}")
            except Exception:
                pass
    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Editieren des Feldes {feldname} in {tabellenname}: {e}", 1)
        messagebox.showerror("Feld editieren", f"Fehler:\n{e}", parent=fenster)


def tabellenfenster_heading_oder_zelle_rechtsklick(event, fenster_id):
    """Rechtsklick auf Spaltenüberschrift – zeigt Menü mit 'Spalte hinzufügen' und 'Alle Spaltennamen vollständig anzeigen'."""
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tree_widget = cache["tree"]
    region = tree_widget.identify("region", event.x, event.y)
    if region != "heading":
        return
    spalte_id = tree_widget.identify_column(event.x)
    cache["kontext_spalte_id"] = spalte_id
    menu = tk.Menu(cache["fenster"], tearoff=0)
    menu.add_command(
        label="Spalte hinzufügen...",
        command=lambda: tabellenfenster_spalte_hinzufuegen(fenster_id, spalte_id)
    )
    menu.add_command(
        label="Spalte löschen...",
        command=lambda: tabellenfenster_spalte_loeschen(fenster_id, spalte_id)
    )
    menu.add_separator()
    menu.add_command(
        label="Alle Spaltennamen vollständig anzeigen",
        command=lambda: tabellenfenster_spaltennamen_vollstaendig_anzeigen(fenster_id)
    )
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def tabellenfenster_spaltennamen_vollstaendig_anzeigen(fenster_id):
    """Passt Spaltenbreiten an damit Spaltennamen lesbar sind.
    Manuell gezogene Breiten werden respektiert – nur verbreitern, nie verkleinern.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    tree_widget = cache["tree"]
    tree_font = font.nametofont("TkDefaultFont")
    spalten = list(tree_widget["columns"])
    # Manuell gesetzte Breiten aus Cache holen (werden beim Ziehen gespeichert)
    manuelle_breiten = cache.get("manuelle_spaltenbreiten", {})
    for spalte in spalten:
        min_breite = tree_font.measure(str(spalte)) + 24
        # Manuelle Breite hat Vorrang, sonst aktuelle Breite aus Widget
        manuelle = manuelle_breiten.get(spalte, 0)
        try:
            widget_breite = tree_widget.column(spalte, "width")
        except Exception:
            widget_breite = 0
        aktuelle_breite = max(manuelle, widget_breite)
        # Nur verbreitern, nie verkleinern
        neue_breite = max(min_breite, aktuelle_breite)
        tree_widget.column(spalte, width=neue_breite, minwidth=min_breite)
    tabellenfenster_temp_hinweis(fenster_id, " * Spaltenbreiten auf Spaltennamen angepasst")


def tabellenfenster_spalte_hinzufuegen(fenster_id, spalte_id):
    """Fügt eine neue Spalte links oder rechts der angeklickten Spalte ein.
    Erstellt die Tabelle neu mit gewünschter Spaltenreihenfolge und kopiert Daten um.
    Alle Schritte werden in zzz_Logging dokumentiert.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    fenster = cache["fenster"]
    tabellenname = cache.get("tabellenname", "")
    spalten = list(cache.get("spalten", []))

    if not spalten:
        messagebox.showwarning("Spalte hinzufügen", "Keine Spalteninformationen vorhanden.", parent=fenster)
        return

    # Spaltenindex aus spalte_id ermitteln
    try:
        spaltenindex = int(str(spalte_id).replace("#", "")) - 1
    except Exception:
        spaltenindex = len(spalten) - 1

    if spaltenindex < 0 or spaltenindex >= len(spalten):
        spaltenindex = len(spalten) - 1

    aktuelle_spalte = spalten[spaltenindex]

    # Dialog: Name + Position
    dialog = tk.Toplevel(fenster)
    dialog.title("Spalte hinzufügen")
    dialog.geometry("420x200")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(fenster)

    tk.Label(dialog, text=f"Neue Spalte neben: {aktuelle_spalte}", anchor="w").pack(fill="x", padx=16, pady=(16, 4))
    tk.Label(dialog, text="Name der neuen Spalte:", anchor="w").pack(fill="x", padx=16)
    name_var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=name_var, width=40)
    entry.pack(fill="x", padx=16, pady=(0, 8))
    entry.focus_set()

    position_var = tk.StringVar(value="rechts")
    pos_frame = tk.Frame(dialog)
    pos_frame.pack(fill="x", padx=16)
    tk.Radiobutton(pos_frame, text="Links davon", variable=position_var, value="links").pack(side="left", padx=(0, 16))
    tk.Radiobutton(pos_frame, text="Rechts davon", variable=position_var, value="rechts").pack(side="left")

    ergebnis = [None]

    def bestaetigen(event=None):
        ergebnis[0] = (name_var.get().strip(), position_var.get())
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

    if ergebnis[0] is None:
        return

    neuer_spaltenname, position = ergebnis[0]
    if not neuer_spaltenname:
        messagebox.showwarning("Spalte hinzufügen", "Bitte einen Spaltennamen eingeben.", parent=fenster)
        return
    if not sql_name_ok(neuer_spaltenname):
        messagebox.showwarning("Spalte hinzufügen", "Ungültiger Spaltenname.", parent=fenster)
        return
    if neuer_spaltenname in spalten:
        messagebox.showwarning("Spalte hinzufügen", f"Eine Spalte '{neuer_spaltenname}' existiert bereits.", parent=fenster)
        return

    # Neue Spaltenreihenfolge berechnen
    if position == "links":
        einfuege_index = spaltenindex
    else:
        einfuege_index = spaltenindex + 1

    neue_spalten = spalten[:einfuege_index] + [neuer_spaltenname] + spalten[einfuege_index:]

    # Tabelle neu erstellen
    tmp_name = f"{tabellenname}_tmp"
    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()

        # Originaltabelle analysieren
        cursor.execute(f"PRAGMA table_info({sql_identifier(tabellenname)})")
        original_info = {row[1]: row[2] for row in cursor.fetchall()}

        # Spaltendefinitionen für neue Tabelle
        spaltendef_teile = []
        for sp in neue_spalten:
            if sp == neuer_spaltenname:
                spaltendef_teile.append(f"{sql_identifier(sp)} TEXT")
            else:
                typ = original_info.get(sp, "TEXT")
                spaltendef_teile.append(f"{sql_identifier(sp)} {typ}")

        # _tmp erstellen
        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(tmp_name)}")
        cursor.execute(
            f"CREATE TABLE {sql_identifier(tmp_name)} ({', '.join(spaltendef_teile)})"
        )

        # Daten umkopieren (neue Spalte bleibt leer)
        alte_spalten_sql = ", ".join(
            sql_identifier(sp) if sp != neuer_spaltenname else "''"
            for sp in neue_spalten
        )
        cursor.execute(
            f"INSERT INTO {sql_identifier(tmp_name)} "
            f"SELECT {alte_spalten_sql} FROM {sql_identifier(tabellenname)}"
        )

        # Alte Tabelle löschen und _tmp umbenennen
        cursor.execute(f"DROP TABLE {sql_identifier(tabellenname)}")
        cursor.execute(
            f"ALTER TABLE {sql_identifier(tmp_name)} RENAME TO {sql_identifier(tabellenname)}"
        )
        verbindung.commit()
        verbindung.close()

        # Logging
        log_meldung = (
            f"Spalte hinzugefügt: {tabellenname}\n"
            f". Neue Spalte: {neuer_spaltenname} ({position} von {aktuelle_spalte})\n"
            f".. Neue Reihenfolge: {', '.join(neue_spalten)}"
        )
        logging_eintrag_schreiben(log_meldung, 0)

        messagebox.showinfo(
            "Spalte hinzugefügt",
            f"Spalte '{neuer_spaltenname}' wurde {position} von '{aktuelle_spalte}' eingefügt.",
            parent=fenster
        )

        # Position des Fensters merken
        try:
            fenster_geometrie = fenster.geometry()
            pos_x = fenster.winfo_x()
            pos_y = fenster.winfo_y()
        except Exception:
            pos_x = pos_y = None

        # Tabellenfenster neu laden und Position wiederherstellen
        tabellenfenster_schliessen(fenster_id)
        tabellenfenster_oeffnen(tabellenname)
        # Position wiederherstellen
        if pos_x is not None and pos_y is not None:
            try:
                # Neues Fenster finden
                if tabellenname in G_tabellenfenster_nach_name:
                    neues_fenster_id = G_tabellenfenster_nach_name[tabellenname]
                    neues_fenster = G_tabellen_cache.get(neues_fenster_id, {}).get("fenster")
                    if neues_fenster:
                        neues_fenster.update_idletasks()
                        breite = neues_fenster.winfo_width()
                        hoehe = neues_fenster.winfo_height()
                        neues_fenster.geometry(f"{breite}x{hoehe}+{pos_x}+{pos_y}")
            except Exception:
                pass

    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Hinzufügen der Spalte {neuer_spaltenname} in {tabellenname}: {e}", 1)
        messagebox.showerror("Spalte hinzufügen", f"Fehler:\n{e}", parent=fenster)


def tabellenfenster_spalte_loeschen(fenster_id, spalte_id):
    """Löscht eine Spalte aus der Tabelle nach Rückfrage.
    Erstellt die Tabelle neu ohne diese Spalte, kopiert Daten um.
    Alle Schritte werden in zzz_Logging dokumentiert.
    """
    cache = G_tabellen_cache.get(fenster_id)
    if not cache:
        return
    fenster = cache["fenster"]
    tabellenname = cache.get("tabellenname", "")
    spalten = list(cache.get("spalten", []))

    try:
        spaltenindex = int(str(spalte_id).replace("#", "")) - 1
    except Exception:
        spaltenindex = 0

    if spaltenindex < 0 or spaltenindex >= len(spalten):
        messagebox.showwarning("Spalte löschen", "Ungültige Spalte.", parent=fenster)
        return

    zu_loeschende_spalte = spalten[spaltenindex]

    if not admin_code_fuer_aktion_pruefen(tabellenname, "löschen"):
        return

    # Statistik ermitteln
    try:
        verbindung_info = sqlite_verbindung_oeffnen()
        cursor_info = verbindung_info.cursor()
        cursor_info.execute(f"SELECT COUNT(*) FROM {sql_identifier(tabellenname)}")
        gesamt_zeilen = cursor_info.fetchone()[0]
        cursor_info.execute(
            f"SELECT COUNT(*) FROM {sql_identifier(tabellenname)} "
            f"WHERE {sql_identifier(zu_loeschende_spalte)} IS NOT NULL "
            f"AND TRIM(CAST({sql_identifier(zu_loeschende_spalte)} AS TEXT)) != ''"
        )
        nicht_leer = cursor_info.fetchone()[0]
        verbindung_info.close()
        statistik = (
            f"Zeilen gesamt:          {gesamt_zeilen:,}\n"
            f"Zeilen mit Inhalt (not NULL, not leer): {nicht_leer:,}"
        ).replace(",", ".")
    except Exception:
        statistik = "(Statistik nicht verfügbar)"

    # Eigener Dialog mit kopierbarem Text
    bestaetigt = [False]
    dlg = tk.Toplevel(fenster)
    dlg.title("Spalte löschen")
    dlg.geometry("420x240")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.transient(fenster)
    nachricht = (
        f"Soll die Spalte '{zu_loeschende_spalte}' wirklich aus\n"
        f"der Tabelle '{tabellenname}' gelöscht werden?\n\n"
        f"{statistik}\n\n"
        f"Alle Daten in dieser Spalte gehen verloren!"
    )
    txt = tk.Text(dlg, wrap="word", height=10, padx=10, pady=10,
                  relief="flat", bg=dlg.cget("bg"), cursor="xterm")
    txt.pack(fill="both", expand=True, padx=12, pady=(12, 0))
    txt.insert("1.0", nachricht)
    txt.configure(state="normal")  # markierbar aber nicht editierbar via Binding
    txt.bind("<Key>", lambda e: "break")  # tippen blockieren, markieren erlauben
    btn_frame = tk.Frame(dlg)
    btn_frame.pack(fill="x", padx=12, pady=(8, 12))
    def ja():
        bestaetigt[0] = True
        dlg.destroy()
    def nein():
        dlg.destroy()
    tk.Button(btn_frame, text="Nein", width=12, command=nein).pack(side="right", padx=(8, 0))
    tk.Button(btn_frame, text="Ja, löschen", width=14, command=ja).pack(side="right")
    dlg.bind("<Return>", lambda e: ja())
    dlg.bind("<Escape>", lambda e: nein())
    dlg.wait_window()
    if not bestaetigt[0]:
        return

    neue_spalten = [s for s in spalten if s != zu_loeschende_spalte]
    if not neue_spalten:
        messagebox.showwarning("Spalte löschen", "Die letzte Spalte kann nicht gelöscht werden.", parent=fenster)
        return

    tmp_name = f"{tabellenname}_tmp"

    # Fensterposition merken
    try:
        pos_x = fenster.winfo_x()
        pos_y = fenster.winfo_y()
    except Exception:
        pos_x = pos_y = None

    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()

        # Originaltabelle analysieren
        cursor.execute(f"PRAGMA table_info({sql_identifier(tabellenname)})")
        original_info = {row[1]: row[2] for row in cursor.fetchall()}

        # _tmp erstellen ohne die zu löschende Spalte
        spaltendef_teile = []
        for sp in neue_spalten:
            typ = original_info.get(sp, "TEXT")
            spaltendef_teile.append(f"{sql_identifier(sp)} {typ}")

        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(tmp_name)}")
        cursor.execute(
            f"CREATE TABLE {sql_identifier(tmp_name)} ({', '.join(spaltendef_teile)})"
        )

        # Daten umkopieren ohne gelöschte Spalte
        spalten_sql = ", ".join(sql_identifier(sp) for sp in neue_spalten)
        cursor.execute(
            f"INSERT INTO {sql_identifier(tmp_name)} "
            f"SELECT {spalten_sql} FROM {sql_identifier(tabellenname)}"
        )

        # Alte Tabelle löschen und _tmp umbenennen
        cursor.execute(f"DROP TABLE {sql_identifier(tabellenname)}")
        cursor.execute(
            f"ALTER TABLE {sql_identifier(tmp_name)} RENAME TO {sql_identifier(tabellenname)}"
        )
        verbindung.commit()
        verbindung.close()

        # Logging
        log_meldung = (
            f"Spalte gelöscht: {tabellenname}\n"
            f". Gelöschte Spalte: {zu_loeschende_spalte}\n"
            f".. Verbleibende Spalten: {', '.join(neue_spalten)}"
        )
        logging_eintrag_schreiben(log_meldung, 0)

        messagebox.showinfo(
            "Spalte gelöscht",
            f"Spalte '{zu_loeschende_spalte}' wurde aus '{tabellenname}' gelöscht.",
            parent=fenster
        )

        # Fenster neu laden und Position wiederherstellen
        tabellenfenster_schliessen(fenster_id)
        tabellenfenster_oeffnen(tabellenname)
        if pos_x is not None and pos_y is not None:
            try:
                if tabellenname in G_tabellenfenster_nach_name:
                    nfid = G_tabellenfenster_nach_name[tabellenname]
                    nf = G_tabellen_cache.get(nfid, {}).get("fenster")
                    if nf:
                        nf.update_idletasks()
                        nf.geometry(f"{nf.winfo_width()}x{nf.winfo_height()}+{pos_x}+{pos_y}")
            except Exception:
                pass

    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Löschen der Spalte {zu_loeschende_spalte} in {tabellenname}: {e}", 1)
        messagebox.showerror("Spalte löschen", f"Fehler:\n{e}", parent=fenster)


def tabellenfenster_oeffnen(tabellenname):
    if tabellenfenster_nach_vorne_holen(tabellenname):
        return
    top = tk.Toplevel(root)
    top.geometry("1200x700")
    top.minsize(800, 100)
    fenster_id = str(top)
    tabellenfenster_titel_setzen(top, tabellenname, "  * Tabelle lädt blockweise...")
    registry_id = fenster_registrieren(top, "Tabelle", top.title())
    fenster_menue = fenster_standard_menue_anbringen(top, "1200x700", "Tabelle")
    fenster_menue.add_command(label="Als Tabelle speichern", command=lambda fid=fenster_id: tabellenfenster_aktuelle_anzeige_als_tabelle_speichern(fid))
    fenster_menue.add_command(label="Als CSV speichern", command=lambda fid=fenster_id: tabellenfenster_aktuelle_anzeige_als_csv_speichern(fid))
    fenster_menue.add_separator()
    fenster_menue.add_command(label="Tabelle aktualisieren  [F5]", command=lambda fid=fenster_id: tabellenfenster_aktualisieren(fid))
    fenster_menue.add_separator()
    fenster_menue.add_command(label="Schließen", command=lambda: tabellenfenster_schliessen(fenster_id))
    top.bind("<F5>", lambda event, fid=fenster_id: tabellenfenster_aktualisieren(fid))
    hauptframe = tk.Frame(top, bg="white")
    hauptframe.pack(fill="both", expand=True, padx=10, pady=10)
    hauptframe.grid_rowconfigure(0, weight=1)
    hauptframe.grid_columnconfigure(0, weight=1)

    tree_frame = tk.Frame(hauptframe, bg="white")
    tree_frame.grid(row=0, column=0, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)
    fenster_tree = ttk.Treeview(tree_frame, selectmode="browse")
    fenster_tree.grid(row=0, column=0, sticky="nsew")
    fenster_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=fenster_tree.yview)
    fenster_scroll_y.grid(row=0, column=1, sticky="ns")
    fenster_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=fenster_tree.xview)
    fenster_scroll_x.grid(row=1, column=0, sticky="ew")
    fenster_tree.configure(yscrollcommand=fenster_scroll_y.set, xscrollcommand=fenster_scroll_x.set)
    fenster_tree.tag_configure("suchtreffer", background="#fff3b0", foreground="black")
    fenster_tree.tag_configure("aktiver_suchtreffer", background="#ffd166", foreground="black")
    fenster_queue = queue.Queue()
    G_tabellenfenster[fenster_id] = top
    G_tabellenfenster_nach_name[tabellenname] = fenster_id
    G_tabellen_cache[fenster_id] = {
        "tabellenname": tabellenname,
        "spalten": [],
        "zeilen": [],
        "original_zeilen": [],
        "zeilen_puffer": [],
        "anzahl": 0,
        "geladen_db": 0,
        "eingefuegt_gui": 0,
        "db_fertig": False,
        "meta_ok": False,
        "spaltenbreite_fertig": False,
        "fenster": top,
        "tree": fenster_tree,
        "queue": fenster_queue,
        "sortierung": {},
        "filter_aktiv": False,
        "filter_info": None,
        "suchfenster": None,
        "suchtext_var": None,
        "suchtreffer_ids": [],
        "suchtreffer_index": -1,
        "kontext_item_id": None,
        "kontext_spalte_id": None,
        "kontext_menu": None,
        "basis_titel": f"{G_EXE_Title} - {tabellenname}  * Tabelle lädt blockweise...",
        "temp_hinweis_job": None,
        "registry_id": registry_id
    }
    kontext_menu = tk.Menu(top, tearoff=0)
    # Block 1: Kopieren
    kontext_menu.add_command(label="Feldinhalt kopieren", command=lambda fid=fenster_id: tabellenfenster_feld_in_zwischenablage(fid))
    kontext_menu.add_command(label="Zeile kopieren", command=lambda fid=fenster_id: tabellenfenster_zeile_in_zwischenablage(fid))
    kontext_menu.add_command(label="Zeile als CSV kopieren", command=lambda fid=fenster_id: tabellenfenster_zeile_als_csv_in_zwischenablage(fid))
    kontext_menu.add_command(label="Header als CSV kopieren", command=lambda fid=fenster_id: tabellenfenster_header_als_csv_in_zwischenablage(fid))
    kontext_menu.add_command(label="Tabelle als CSV kopieren", command=lambda fid=fenster_id: tabellenfenster_tabelle_als_csv_kopieren(fid))
    kontext_menu.add_separator()
    # Block 2: Anzeigen
    kontext_menu.add_command(label="Feldinhalt im Lesefenster anzeigen", command=lambda fid=fenster_id: tabellenfenster_feld_im_lesefenster_anzeigen(fid))
    kontext_menu.add_command(label="Zeile im Lesefenster anzeigen", command=lambda fid=fenster_id: tabellenfenster_zeile_im_lesefenster_anzeigen(fid))
    kontext_menu.add_separator()
    # Block 3: Filtern
    kontext_menu.add_command(label="Feldfilter setzen", command=lambda fid=fenster_id: tabellenfenster_filter_dialog_oeffnen(fid))
    kontext_menu.add_command(label="Feldfilter aufheben", command=lambda fid=fenster_id: tabellenfenster_filter_aufheben(fid))
    kontext_menu.add_command(label="Eindeutige Feldwerte anzeigen", command=lambda fid=fenster_id: tabellenfenster_eindeutige_feldwerte_anzeigen(fid))
    kontext_menu.add_command(label="Auf IP/Netzwerk filtern", command=lambda fid=fenster_id: tabellenfenster_ip_filter_anwenden(fid))
    kontext_menu.add_command(label="Auf Netzmaske filtern", command=lambda fid=fenster_id: tabellenfenster_maske_filter_anwenden(fid))
    kontext_menu.add_separator()
    # Block 4: IPv4
    kontext_menu.add_command(label="Integer zu IPv4-Adresse", command=lambda fid=fenster_id: tabellenfenster_integer_zu_ipv4_anzeigen(fid))
    kontext_menu.add_command(label="IPv4-Adresse zu Integer", command=lambda fid=fenster_id: tabellenfenster_ipv4_zu_integer_anzeigen(fid))
    kontext_menu.add_command(label="IP-Range aufteilen", command=lambda fid=fenster_id: tabellenfenster_ip_range_aufteilen_anzeigen(fid))
    kontext_menu.add_command(label="Netzwerk IP oder Maske anzeigen", command=lambda fid=fenster_id: tabellenfenster_netzwerk_ip_anzeigen(fid))
    G_tabellen_cache[fenster_id]["kontext_menu"] = kontext_menu
    fenster_tree.bind("<ButtonRelease-1>", lambda event, fid=fenster_id: tabellenfenster_linksklick_auf_zelle(event, fid))
    fenster_tree.bind("<Double-1>", lambda event, fid=fenster_id: tabellenfenster_doppelklick_auf_zelle(event, fid))
    fenster_tree.bind("<Button-3>", lambda event, fid=fenster_id: tabellenfenster_rechtsklick(event, fid))
    fenster_tree.bind("<Button-3>", lambda event, fid=fenster_id: tabellenfenster_heading_oder_zelle_rechtsklick(event, fid), add="+")

    def spaltenbreite_merken(event, fid=fenster_id):
        """Speichert alle aktuellen Spaltenbreiten nach manuellem Ziehen."""
        c = G_tabellen_cache.get(fid)
        if not c:
            return
        tw = c["tree"]
        # Immer alle Breiten speichern – auch wenn region nicht "separator"
        if "manuelle_spaltenbreiten" not in c:
            c["manuelle_spaltenbreiten"] = {}
        for spalte in tw["columns"]:
            try:
                breite = tw.column(spalte, "width")
                if breite > 0:
                    c["manuelle_spaltenbreiten"][spalte] = breite
            except Exception:
                pass

    fenster_tree.bind("<ButtonRelease-1>", lambda event, fid=fenster_id: spaltenbreite_merken(event, fid), add="+")
    top.bind("<Control-f>", lambda event, fid=fenster_id: tabellenfenster_suchfenster_oeffnen(fid))
    top.bind("<F3>", lambda event, fid=fenster_id: tabellenfenster_suchtreffer_navigieren(fid, 1))
    top.bind("<Shift-F3>", lambda event, fid=fenster_id: tabellenfenster_suchtreffer_navigieren(fid, -1))
    top.bind("<Control-c>", lambda event, fid=fenster_id: tabellenfenster_ctrl_c(event, fid))
    # Aktuelles Farbthema auf das neue Tabellenfenster anwenden
    if G_aktuelles_theme_bg not in ("white", "#ffffff"):
        _skip = set()
        for _d in (G_rahmen_frames, G_rahmen_frames2, G_rahmen_frames3):
            for _rf in _d.values():
                try:
                    _skip.add(id(_rf))
                except Exception:
                    pass
        _fenster_einfaerben(top, G_aktuelles_theme_bg, G_aktuelles_theme_fg,
                            G_aktuelles_theme_sel_bg, G_aktuelles_theme_sel_fg, _skip)
    worker = threading.Thread(target=tabelle_blockweise_laden_worker, args=(G_geladene_db_datei, tabellenname, fenster_queue, G_db_fetch_groesse), daemon=True)
    worker.start()
    top.after(100, lambda: tabellenfenster_queue_pruefen(fenster_id))
    top.protocol("WM_DELETE_WINDOW", lambda: tabellenfenster_schliessen(fenster_id))

def tabelle_vorschau_laden_worker(db_datei, tabellenname, limit, ergebnis_queue, request_id):
    startzeit = time.monotonic()
    debug_log(
        f"Worker-Beginn: request_id={request_id}, tabelle={tabellenname}, "
        f"limit={limit}, db={db_datei}",
        "vorschau"
    )
    verbindung = None
    try:
        try:
            limit_int = int(limit)
        except Exception:
            limit_int = 50
        if limit_int <= 0:
            limit_int = 50
        limit_int = min(limit_int, 1000)

        verbindung = sqlite_verbindung_oeffnen(db_datei)
        cursor = verbindung.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {sql_identifier(tabellenname)}')
        anzahl_datensaetze = cursor.fetchone()[0]
        cursor.execute(f'PRAGMA table_info({sql_identifier(tabellenname)})')
        spalten_info = cursor.fetchall()
        spalten = [row[1] for row in spalten_info]
        order_by_sql = ''
        if projekt_ist_logging_tabelle(tabellenname) and spalten:
            spalten_nach_lower = {str(spalte).lower(): spalte for spalte in spalten}
            for kandidat in ('datetime', 'id'):
                if kandidat in spalten_nach_lower:
                    order_by_sql = f' ORDER BY {sql_identifier(spalten_nach_lower[kandidat])} DESC'
                    break
        sql_preview = f'SELECT * FROM {sql_identifier(tabellenname)}{order_by_sql} LIMIT ?'
        debug_log(f"Worker-SQL: request_id={request_id}, sql={sql_preview}, limit={limit_int}", "vorschau")
        cursor.execute(sql_preview, (limit_int,))
        zeilen = cursor.fetchall()
        dauer_ms = int((time.monotonic() - startzeit) * 1000)
        ergebnis = {
            "status": "ok",
            "request_id": request_id,
            "tabellenname": tabellenname,
            "anzahl": anzahl_datensaetze,
            "spalten": spalten,
            "zeilen": zeilen,
            "dauer_ms": dauer_ms,
        }
        ergebnis_queue.put(ergebnis)
        debug_log(
            f"Worker-Ende OK: request_id={request_id}, tabelle={tabellenname}, "
            f"spalten={len(spalten)}, zeilen={len(zeilen)}, dauer_ms={dauer_ms}, "
            f"queue_nach_put~={ergebnis_queue.qsize()}",
            "vorschau"
        )
    except Exception as e:
        dauer_ms = int((time.monotonic() - startzeit) * 1000)
        debug_log(
            f"Worker-Ende FEHLER: request_id={request_id}, tabelle={tabellenname}, "
            f"fehler={e}, dauer_ms={dauer_ms}",
            "vorschau"
        )
        ergebnis_queue.put({
            "status": "fehler",
            "request_id": request_id,
            "tabellenname": tabellenname,
            "meldung": str(e),
            "traceback": traceback.format_exc(),
            "dauer_ms": dauer_ms,
        })
    finally:
        try:
            if verbindung is not None:
                verbindung.close()
        except Exception:
            pass

def tabelle_doppelklick(event=None):
    global G_einfachklick_job
    auswahl = tree_tabellen.selection()
    if not auswahl:
        return
    if G_einfachklick_job is not None:
        root.after_cancel(G_einfachklick_job)
        G_einfachklick_job = None
    item_id = auswahl[0]
    tabellenname = tree_tabellen.item(item_id, "values")[0]
    tabellenfenster_oeffnen(tabellenname)

def tabelle_blockweise_laden_worker(db_datei, tabellenname, ergebnis_queue, fetch_groesse):
    try:
        verbindung = sqlite_verbindung_oeffnen(db_datei)
        cursor = verbindung.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {sql_identifier(tabellenname)}')
        anzahl_datensaetze = cursor.fetchone()[0]
        cursor.execute(f'PRAGMA table_info({sql_identifier(tabellenname)})')
        spalten_info = cursor.fetchall()
        spalten = [row[1] for row in spalten_info]
        order_by_sql = ''
        if projekt_ist_logging_tabelle(tabellenname) and spalten:
            spalten_nach_lower = {str(spalte).lower(): spalte for spalte in spalten}
            for kandidat in ('datetime', 'id'):
                if kandidat in spalten_nach_lower:
                    order_by_sql = f' ORDER BY {sql_identifier(spalten_nach_lower[kandidat])} DESC'
                    break
        cursor.execute(f'SELECT * FROM {sql_identifier(tabellenname)}{order_by_sql}')
        if not spalten:
            spalten = [beschreibung[0] for beschreibung in cursor.description]
        ergebnis_queue.put({"status": "meta", "tabellenname": tabellenname, "anzahl": anzahl_datensaetze, "spalten": spalten})
        geladen = 0
        while True:
            block = cursor.fetchmany(fetch_groesse)
            if not block:
                break
            geladen += len(block)
            ergebnis_queue.put({"status": "datenblock", "tabellenname": tabellenname, "geladen": geladen, "anzahl": anzahl_datensaetze, "zeilen": block})
        verbindung.close()
        ergebnis_queue.put({"status": "fertig", "tabellenname": tabellenname, "anzahl": anzahl_datensaetze})
    except Exception as e:
        ergebnis_queue.put({"status": "fehler", "meldung": str(e)})

def tabellenfenster_queue_pruefen(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster = G_tabellenfenster[fenster_id]
    fenster_tree = cache["tree"]
    fenster_queue = cache["queue"]
    while True:
        try:
            ergebnis = fenster_queue.get_nowait()
        except queue.Empty:
            break
        status = ergebnis["status"]
        if status == "fehler":
            tabellenfenster_basis_titel_setzen(fenster_id, "  * Fehler beim Laden")
            messagebox.showerror("DB-Fehler", f"Tabelle konnte nicht geladen werden:\n{ergebnis['meldung']}")
            return
        if status == "meta":
            spalten = ergebnis["spalten"]
            anzahl_datensaetze = ergebnis["anzahl"]
            cache["spalten"] = spalten
            cache["anzahl"] = anzahl_datensaetze
            cache["meta_ok"] = True
            fenster_tree.delete(*fenster_tree.get_children())
            fenster_tree["columns"] = spalten
            fenster_tree["show"] = "headings"
            for spalte in spalten:
                fenster_tree.heading(spalte, text=spaltenkopf_text(spalte, cache), command=lambda c=spalte, fid=fenster_id: tabellenfenster_sortieren(fid, c))
                fenster_tree.column(spalte, anchor="w")
            tabellenfenster_basis_titel_setzen(fenster_id, "  * Struktur geladen, Daten werden gelesen...")
        elif status == "datenblock":
            block = ergebnis["zeilen"]
            cache["geladen_db"] = ergebnis["geladen"]
            cache["zeilen_puffer"].extend(block)
            cache["zeilen"].extend(block)
            cache["original_zeilen"].extend(block)
            geladen_formatiert = f"{cache['geladen_db']:,}".replace(",", ".")
            gesamt_formatiert = f"{cache['anzahl']:,}".replace(",", ".")
            tabellenfenster_basis_titel_setzen(fenster_id, f"  * Daten werden gelesen... ({geladen_formatiert} / {gesamt_formatiert})")
        elif status == "fertig":
            cache["db_fertig"] = True
    if cache["meta_ok"] and cache["zeilen_puffer"]:
        tabellenfenster_chunkweise_einfuegen(fenster_id)
    if cache["db_fertig"] and not cache["zeilen_puffer"] and cache["eingefuegt_gui"] >= cache["anzahl"]:
        if not cache["spaltenbreite_fertig"]:
            tabellenfenster_spalten_breiten_anpassen(fenster_id)
            cache["spaltenbreite_fertig"] = True
        gesamt_formatiert = f"{cache['anzahl']:,}".replace(",", ".")
        tabellenfenster_basis_titel_setzen(fenster_id, f"  * Tabelle geladen ({gesamt_formatiert} Datensätze)")
        return
    fenster.after(100, lambda: tabellenfenster_queue_pruefen(fenster_id))

def tabellenfenster_chunkweise_einfuegen(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster_tree = cache["tree"]
    if not cache["zeilen_puffer"]:
        return
    chunk = cache["zeilen_puffer"][:G_chunk_groesse]
    cache["zeilen_puffer"] = cache["zeilen_puffer"][G_chunk_groesse:]
    for zeile in chunk:
        fenster_tree.insert("", "end", values=zeile)
    cache["eingefuegt_gui"] += len(chunk)
    if cache["eingefuegt_gui"] % G_fenster_insert_update_schritt == 0 or not cache["zeilen_puffer"]:
        eingefuegt_formatiert = f"{cache['eingefuegt_gui']:,}".replace(",", ".")
        gesamt_formatiert = f"{cache['anzahl']:,}".replace(",", ".")
        tabellenfenster_basis_titel_setzen(fenster_id, f"  * Datensätze werden eingefügt... ({eingefuegt_formatiert} / {gesamt_formatiert})")

def tabellenfenster_spalten_breiten_anpassen(fenster_id):
    if fenster_id not in G_tabellen_cache or fenster_id not in G_tabellenfenster:
        return
    cache = G_tabellen_cache[fenster_id]
    fenster_tree = cache["tree"]
    tree_spalten_breiten_anpassen(tree_widget=fenster_tree, status_callback=lambda text: tabellenfenster_basis_titel_setzen(fenster_id, f"  * {text}"), update_schritt=G_spaltenbreite_update_schritt, max_zeilen_pruefen=1000)

def tabelle_vorschau_pruefen():
    global G_vorschau_laeuft, G_letzte_vorschau_tabelle, G_angeforderte_vorschau_tabelle
    global G_vorschau_after_id, G_vorschau_startzeit

    G_vorschau_after_id = None
    laufzeit_ms = None
    if G_vorschau_startzeit is not None:
        laufzeit_ms = int((time.monotonic() - G_vorschau_startzeit) * 1000)

    debug_log(
        f"Poller-Pruefung: laeuft={G_vorschau_laeuft}, "
        f"request_id={G_vorschau_request_id}, angefordert={G_angeforderte_vorschau_tabelle}, "
        f"queue_groesse~={G_vorschau_queue.qsize()}, laufzeit_ms={laufzeit_ms}",
        "vorschau"
    )

    aktuelles_ergebnis = None
    verworfen = 0
    while True:
        try:
            ergebnis = G_vorschau_queue.get_nowait()
        except queue.Empty:
            break

        result_request_id = ergebnis.get("request_id")
        result_tabelle = ergebnis.get("tabellenname")
        result_status = ergebnis.get("status")
        debug_log(
            f"Poller holt Queue-Ergebnis: status={result_status}, "
            f"request_id={result_request_id}, tabelle={result_tabelle}",
            "vorschau"
        )

        if result_request_id != G_vorschau_request_id:
            verworfen += 1
            debug_log(
                f"Verwerfe veraltetes Vorschau-Ergebnis: result_request_id={result_request_id}, "
                f"aktuell={G_vorschau_request_id}, result_tabelle={result_tabelle}, "
                f"angefordert={G_angeforderte_vorschau_tabelle}",
                "vorschau"
            )
            continue

        if result_tabelle != G_angeforderte_vorschau_tabelle:
            verworfen += 1
            debug_log(
                f"Verwerfe Ergebnis mit falscher Tabelle: request_id={result_request_id}, "
                f"result_tabelle={result_tabelle}, angefordert={G_angeforderte_vorschau_tabelle}",
                "vorschau"
            )
            continue

        aktuelles_ergebnis = ergebnis
        break

    if aktuelles_ergebnis is None:
        if G_vorschau_laeuft:
            debug_log(
                f"Poller findet noch kein aktuelles Ergebnis; neuer Poll in 100ms: "
                f"request_id={G_vorschau_request_id}, angefordert={G_angeforderte_vorschau_tabelle}, "
                f"verworfen={verworfen}",
                "vorschau"
            )
            G_vorschau_after_id = root.after(100, tabelle_vorschau_pruefen)
        else:
            debug_log(
                f"Poller beendet ohne laufende Vorschau: request_id={G_vorschau_request_id}, "
                f"verworfen={verworfen}",
                "vorschau"
            )
        return

    ergebnis = aktuelles_ergebnis
    result_request_id = ergebnis.get("request_id")
    tabellenname = ergebnis.get("tabellenname")
    status = ergebnis.get("status")
    G_vorschau_laeuft = False
    G_letzte_vorschau_tabelle = tabellenname
    G_vorschau_startzeit = None

    debug_log(
        f"Aktuelles Vorschau-Ergebnis eingetroffen: status={status}, "
        f"request_id={result_request_id}, tabelle={tabellenname}, verworfen={verworfen}, "
        f"worker_dauer_ms={ergebnis.get('dauer_ms')}",
        "vorschau"
    )

    if status == "fehler":
        debug_log(
            f"Vorschaufehler: request_id={result_request_id}, tabelle={tabellenname}, "
            f"meldung={ergebnis.get('meldung')}",
            "vorschau"
        )
        if ergebnis.get("traceback"):
            debug_log(f"Vorschaufehler-Traceback:\n{ergebnis.get('traceback')}", "vorschau")
        fenstertitel_aktualisieren(" * Fehler bei Vorschau")
        messagebox.showerror("DB-Fehler", f"Vorschau konnte nicht geladen werden\n{ergebnis.get('meldung')}")
        return

    spalten = ergebnis["spalten"]
    zeilen = ergebnis["zeilen"]
    anzahl_datensaetze = ergebnis["anzahl"]
    debug_log(
        f"Baue Vorschau-Tree neu auf: request_id={result_request_id}, "
        f"tabelle={tabellenname}, spalten={len(spalten)}, zeilen={len(zeilen)}",
        "vorschau"
    )
    tree.delete(*tree.get_children())
    tree["columns"] = spalten
    tree["show"] = "headings"
    for spalte in spalten:
        tree.heading(spalte, text=spalte)
        tree.column(spalte, anchor="w")
    eingefuegt = 0
    for zeile in zeilen:
        tree.insert("", "end", values=zeile)
        eingefuegt += 1
    debug_log(f"Tree-Inserts abgeschlossen: request_id={result_request_id}, zeilen={eingefuegt}", "vorschau")
    tree_spalten_breiten_anpassen(tree_widget=tree, status_callback=lambda text: fenstertitel_aktualisieren(f" * {text}"), update_schritt=1000, max_zeilen_pruefen=50)
    try:
        sichtbare_items = len(tree.get_children())
    except Exception:
        sichtbare_items = -1
    geladen_formatiert = f"{len(zeilen):,}".replace(",", ".")
    gesamt_formatiert = f"{anzahl_datensaetze:,}".replace(",", ".")
    debug_log(
        f"Vorschau angezeigt: request_id={result_request_id}, tabelle={tabellenname}, "
        f"geladen={geladen_formatiert}, gesamt={gesamt_formatiert}, tree_items={sichtbare_items}",
        "vorschau"
    )
    fenstertitel_aktualisieren(f" * Vorschau geladen: {tabellenname} ({geladen_formatiert} / {gesamt_formatiert})")

def db_laden():
    global G_geladene_db_datei
    dateipfad = filedialog.askopenfilename(
        title="DB-Datei auswählen",
        initialdir=str(db_verzeichnis_sicherstellen()),
        filetypes=[("SQLite-Datenbanken", "*.db *.sqlite *.sqlite3"), ("Alle Dateien", "*.*")],
    )
    if not dateipfad:
        return
    if not datenbankwechsel_vorbereiten(dateipfad):
        return
    G_geladene_db_datei = dateipfad
    # Hauptfenster-Geometrie als Erstes wiederherstellen, bevor andere Fenster geöffnet werden.
    fenster_benutzereinstellung_automatisch_anwenden(root, "Hauptfenster", G_Size_Normal)
    fenstertitel_aktualisieren(" * Datenbank geladen")
    logging_eintrag_schreiben(f"Datenbank geladen: {dateipfad}")
    tabellen_dropdown_aktualisieren()
    treeview_theme_aus_db_laden()
    # Streifen-Farben für alle bereits offenen Fenster (inkl. Hauptfenster) nachladen
    try:
        _rf1 = konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe")  or ""
        _rf2 = konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe2") or ""
        _rf3 = konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe3") or ""
        _rh  = int(konfiguration_wert_lesen("SQL-Fenster", "rahmenhoehe") or 4)
        rahmenfarbe_alle_fenster_aktualisieren(_rf1, _rf2, _rf3, _rh)
    except Exception:
        pass
    # Projekt prüfen – setzt G_aktives_projekt und stellt Projekt-Layout wieder her.
    projekt_beim_start_pruefen()
    fensterliste_anzeigen()


def tabelle_hinzufuegen():
    if not db_pruefen_oder_warnen():
        return
    name = simpledialog.askstring("Tabelle hinzufügen", "Name der neuen Tabelle:", parent=root)
    if not name:
        return
    name = name.strip()
    if not sql_name_ok(name):
        messagebox.showwarning("Tabellenname", "Ungültiger Tabellenname.")
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"CREATE TABLE {sql_identifier(name)} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(f"Tabelle angelegt: {name}")
        tabellen_dropdown_aktualisieren(name)
    except Exception as e:
        messagebox.showerror("Tabelle hinzufügen", f"Tabelle konnte nicht angelegt werden:\n{e}")


def tabelle_umbenennen():
    if not db_pruefen_oder_warnen():
        return
    alt = aktuelle_tabelle_ermitteln()
    if not alt:
        return
    if not admin_code_fuer_aktion_pruefen(alt, "umbenennen"):
        return
    neu = simpledialog.askstring("Tabelle umbenennen", "Neuer Tabellenname:", initialvalue=alt, parent=root)
    if not neu:
        return
    neu = neu.strip()
    if not sql_name_ok(neu):
        messagebox.showwarning("Tabellenname", "Ungültiger Tabellenname.")
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"ALTER TABLE {sql_identifier(alt)} RENAME TO {sql_identifier(neu)}")
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(f"Tabelle umbenannt: {alt} -> {neu}")
        tabellen_dropdown_aktualisieren(neu)
    except Exception as e:
        messagebox.showerror("Tabelle umbenennen", f"Tabelle konnte nicht umbenannt werden:\n{e}")


def tabelle_kopie_herstellen():
    if not db_pruefen_oder_warnen():
        return
    quelle = aktuelle_tabelle_ermitteln()
    if not quelle:
        return
    if not admin_code_fuer_aktion_pruefen(quelle, "kopieren"):
        return
    ziel = simpledialog.askstring("Kopie von Tabelle herstellen", "Name der Kopie:", initialvalue=f"{quelle}_Kopie", parent=root)
    if not ziel:
        return
    ziel = ziel.strip()
    if not sql_name_ok(ziel):
        messagebox.showwarning("Tabellenname", "Ungültiger Tabellenname.")
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"CREATE TABLE {sql_identifier(ziel)} AS SELECT * FROM {sql_identifier(quelle)}")
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(f"Tabellenkopie erstellt: {quelle} -> {ziel}")
        tabellen_dropdown_aktualisieren(ziel)
    except Exception as e:
        messagebox.showerror("Tabellenkopie", f"Kopie konnte nicht erstellt werden:\n{e}")


def tabelle_in_db_kopieren():
    messagebox.showinfo("Tabelle in DB kopieren", "Diese Version enthält nur die Kopie innerhalb derselben Datenbank.")


def tabelle_leeren():
    if not db_pruefen_oder_warnen():
        return
    tabellenname = aktuelle_tabelle_ermitteln()
    if not tabellenname:
        return
    if not admin_code_fuer_aktion_pruefen(tabellenname, "leeren"):
        return
    if not messagebox.askyesno("Tabelle leeren", f"Soll die Tabelle '{tabellenname}' wirklich geleert werden?", parent=root):
        return
    if not messagebox.askyesno("Sicherheitsabfrage", f"Wirklich alle Datensätze aus '{tabellenname}' löschen?", parent=root):
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"DELETE FROM {sql_identifier(tabellenname)}")
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(f"Tabelle geleert: {tabellenname}")
        tabellen_dropdown_aktualisieren(tabellenname)
        tabelle_vorschau_anzeigen(tabellenname)
    except Exception as e:
        messagebox.showerror("Tabelle leeren", f"Tabelle konnte nicht geleert werden:\n{e}")


def tabelle_loeschen():
    if not db_pruefen_oder_warnen():
        return
    tabellenname = aktuelle_tabelle_ermitteln()
    if not tabellenname:
        return
    if not admin_code_fuer_aktion_pruefen(tabellenname, "löschen"):
        return
    verbindung = None
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {sql_identifier(tabellenname)}")
        anzahl_datensaetze = cursor.fetchone()[0]
    except Exception as e:
        messagebox.showerror("Tabelle löschen", f"Der Inhalt der Tabelle konnte nicht geprüft werden:\n{e}", parent=root)
        debug_log(f"Tabelle löschen abgebrochen: Inhaltsprüfung fehlgeschlagen, tabelle={tabellenname}, fehler={e}", "allgemein")
        return
    finally:
        try:
            if verbindung is not None:
                verbindung.close()
        except Exception:
            pass

    if anzahl_datensaetze > 0:
        anzahl_formatiert = f"{anzahl_datensaetze:,}".replace(",", ".")
        messagebox.showwarning(
            "Tabelle löschen",
            f"Die Tabelle '{tabellenname}' enthält noch {anzahl_formatiert} Datensätze.\n\n"
            "Sie kann erst gelöscht werden, wenn sie leer ist.\n"
            "Bitte zuerst den Menüpunkt 'Tabelle leeren' verwenden.",
            parent=root
        )
        debug_log(
            f"Tabelle löschen blockiert: tabelle={tabellenname}, datensaetze={anzahl_datensaetze}",
            "allgemein"
        )
        return

    if not messagebox.askyesno("Tabelle löschen", f"Soll die Tabelle '{tabellenname}' wirklich gelöscht werden?", parent=root):
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"DROP TABLE {sql_identifier(tabellenname)}")
        verbindung.commit()
        verbindung.close()
        geloeschte_konfigurationen = konfiguration_fuer_tabelle_bereinigen(tabellenname)
        logging_eintrag_schreiben(f"Tabelle gelöscht: {tabellenname}")
        if geloeschte_konfigurationen:
            logging_eintrag_schreiben(f"Konfiguration bereinigt für gelöschte Tabelle {tabellenname}: {geloeschte_konfigurationen} Einträge")
        tabellen_dropdown_aktualisieren()
    except Exception as e:
        messagebox.showerror("Tabelle löschen", f"Tabelle konnte nicht gelöscht werden:\n{e}")


def header_hinzufuegen():
    messagebox.showinfo("Header hinzufügen", "Diese Version enthält keine automatische Header-Migration für bestehende Tabellen.")


def pk_hinzufuegen():
    """Fügt eine INTEGER PRIMARY KEY AUTOINCREMENT Spalte als erste Spalte einer Tabelle hinzu."""
    if not db_pruefen_oder_warnen():
        return
    tabellenname = aktuelle_tabelle_ermitteln()
    if not tabellenname:
        messagebox.showwarning("PK hinzufügen", "Bitte zuerst eine Tabelle in der Liste auswählen.")
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"PRAGMA table_info({sql_identifier(tabellenname)})")
        info = cursor.fetchall()
        verbindung.close()
    except Exception as e:
        messagebox.showerror("PK hinzufügen", f"Fehler beim Lesen der Tabellenstruktur:\n{e}")
        return
    existing_pks = [row[1] for row in info if row[5] > 0]
    if existing_pks:
        messagebox.showwarning("PK hinzufügen", f"Die Tabelle hat bereits einen Primary Key: {', '.join(existing_pks)}")
        return
    existing_columns = [row[1] for row in info]
    pk_name = simpledialog.askstring("PK hinzufügen", "Name des neuen PK-Feldes:", initialvalue="id", parent=root)
    if not pk_name:
        return
    pk_name = pk_name.strip()
    if not sql_name_ok(pk_name):
        messagebox.showwarning("PK hinzufügen", "Ungültiger Feldname.")
        return
    if pk_name in existing_columns:
        messagebox.showwarning("PK hinzufügen", f"Eine Spalte '{pk_name}' existiert bereits.")
        return
    dt_name = "datetime"
    if dt_name in existing_columns:
        messagebox.showwarning("PK hinzufügen", f"Eine Spalte '{dt_name}' existiert bereits. Bitte zuerst umbenennen.")
        return
    tmp_name = f"{tabellenname}_tmp"
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        original_typen = {row[1]: row[2] for row in info}
        spaltendef = [
            f"{sql_identifier(pk_name)} INTEGER PRIMARY KEY AUTOINCREMENT",
            f"{sql_identifier(dt_name)} TEXT",
        ]
        for sp in existing_columns:
            typ = original_typen.get(sp, "TEXT")
            spaltendef.append(f"{sql_identifier(sp)} {typ}")
        alte_spalten_sql = ", ".join(sql_identifier(sp) for sp in existing_columns)
        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(tmp_name)}")
        cursor.execute(f"CREATE TABLE {sql_identifier(tmp_name)} ({', '.join(spaltendef)})")
        cursor.execute(
            f"INSERT INTO {sql_identifier(tmp_name)} ({alte_spalten_sql}) "
            f"SELECT {alte_spalten_sql} FROM {sql_identifier(tabellenname)}"
        )
        cursor.execute(
            f"UPDATE {sql_identifier(tmp_name)} "
            f"SET {sql_identifier(dt_name)} = strftime('%Y-%m-%d %H:%M:%S', 'now')"
        )
        cursor.execute(f"DROP TABLE {sql_identifier(tabellenname)}")
        cursor.execute(f"ALTER TABLE {sql_identifier(tmp_name)} RENAME TO {sql_identifier(tabellenname)}")
        verbindung.commit()
        verbindung.close()
        logging_eintrag_schreiben(
            f"PK hinzugefügt: {tabellenname}\n"
            f". Spalten vorne: {pk_name} (INTEGER PRIMARY KEY AUTOINCREMENT), {dt_name} (TEXT)"
        )
        messagebox.showinfo("PK hinzugefügt", f"Spalten '{pk_name}' und '{dt_name}' wurden als erste Spalten eingefügt.")
        tabellen_dropdown_aktualisieren(tabellenname)
    except Exception as e:
        logging_eintrag_schreiben(f"Fehler beim Hinzufügen des PK in {tabellenname}: {e}", 1)
        messagebox.showerror("PK hinzufügen", f"Fehler:\n{e}")


def findings_hinzufuegen():
    if not db_pruefen_oder_warnen():
        return
    findings_tabelle_anlegen()
    tabellen_dropdown_aktualisieren(G_TABELLE_FINDINGS)


def findings_entfernen():
    if not db_pruefen_oder_warnen():
        return
    if not admin_code_fuer_aktion_pruefen(G_TABELLE_FINDINGS, "löschen"):
        return
    if not messagebox.askyesno("Findings entfernen", f"Soll die Tabelle '{G_TABELLE_FINDINGS}' wirklich gelöscht werden?", parent=root):
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(G_TABELLE_FINDINGS)}")
        verbindung.commit()
        verbindung.close()
        tabellen_dropdown_aktualisieren()
    except Exception as e:
        messagebox.showerror("Findings entfernen", f"Findings konnten nicht entfernt werden:\n{e}")


def logging_hinzufuegen():
    if not db_pruefen_oder_warnen():
        return
    logging_tabelle_anlegen()
    tabellen_dropdown_aktualisieren(G_TABELLE_LOGGING)


def logging_entfernen():
    if not db_pruefen_oder_warnen():
        return
    if not admin_code_fuer_aktion_pruefen(G_TABELLE_LOGGING, "löschen"):
        return
    if not messagebox.askyesno("Logging entfernen", f"Soll die Tabelle '{G_TABELLE_LOGGING}' wirklich gelöscht werden?", parent=root):
        return
    try:
        verbindung = sqlite_verbindung_oeffnen()
        cursor = verbindung.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {sql_identifier(G_TABELLE_LOGGING)}")
        verbindung.commit()
        verbindung.close()
        tabellen_dropdown_aktualisieren()
    except Exception as e:
        messagebox.showerror("Logging entfernen", f"Logging konnte nicht entfernt werden:\n{e}")



def csv_spaltennamen_normalisieren(spalten_roh):
    verwendete = set()
    ergebnis = []
    for index, name in enumerate(spalten_roh, start=1):
        basis = (name or "").strip()
        basis = re.sub(r"\s+", "_", basis)
        basis = re.sub(r"[^A-Za-z0-9_]", "_", basis)
        if not basis:
            basis = f"spalte_{index}"
        if basis[0].isdigit():
            basis = f"_{basis}"
        kandidat = basis
        zaehler = 2
        while kandidat.lower() in verwendete:
            kandidat = f"{basis}_{zaehler}"
            zaehler += 1
        verwendete.add(kandidat.lower())
        ergebnis.append(kandidat)
    return ergebnis


def csv_header_ableiten_ohne_header(spaltenanzahl):
    return [f"Spalte_{i}" for i in range(1, spaltenanzahl + 1)]


def csv_datei_laden(dateipfad, encoding_option="auto", delimiter_option="auto", header_vorhanden=True):
    delimiter_kandidaten = [",", ";", "\t", "|"]
    encodings = [encoding_option] if encoding_option != "auto" else ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    letzter_fehler = None
    for encoding in encodings:
        try:
            with open(dateipfad, "r", encoding=encoding, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                if delimiter_option != "auto":
                    delimiter = "\t" if delimiter_option == "\\t" else delimiter_option
                else:
                    delimiter = ","
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters="".join(delimiter_kandidaten))
                        delimiter = dialect.delimiter
                    except Exception:
                        counts = {k: sample.count(k) for k in delimiter_kandidaten}
                        delimiter = max(counts, key=counts.get) if any(counts.values()) else ","
                reader = csv.reader(f, delimiter=delimiter)
                zeilen = [row for row in reader]
                if not zeilen:
                    return {
                        "dateipfad": dateipfad,
                        "delimiter": delimiter,
                        "encoding": encoding,
                        "header": [],
                        "rows": [],
                        "header_vorhanden": header_vorhanden,
                    }
                spaltenanzahl = max(len(row) for row in zeilen)
                norm = [list(row) + [""] * (spaltenanzahl - len(row)) for row in zeilen]
                if header_vorhanden:
                    header = csv_spaltennamen_normalisieren(norm[0])
                    rows = norm[1:]
                else:
                    header = csv_header_ableiten_ohne_header(spaltenanzahl)
                    rows = norm
                return {
                    "dateipfad": dateipfad,
                    "delimiter": delimiter,
                    "encoding": encoding,
                    "header": header,
                    "rows": rows,
                    "header_vorhanden": header_vorhanden,
                }
        except Exception as e:
            letzter_fehler = e
    raise letzter_fehler or RuntimeError("CSV-Datei konnte nicht gelesen werden.")


def csvfenstertemphinweis(csvfensterid, meldung, dauerms=1800):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    fenster = daten.get("fenster")
    if fenster is None or not fenster.winfo_exists():
        return
    info_var = daten.get("info_var")
    if info_var is None:
        return
    original = daten.get("info_text_original", info_var.get())
    alterjob = daten.get("temphinweisjob")
    if alterjob is not None:
        try:
            fenster.after_cancel(alterjob)
        except Exception:
            pass
    info_var.set(f"{original} | {meldung}")

    def restore():
        neu = G_csv_fenster.get(csvfensterid)
        if not neu:
            return
        info = neu.get("info_var")
        if info is not None:
            info.set(neu.get("info_text_original", original))
        neu["temphinweisjob"] = None

    daten["temphinweisjob"] = fenster.after(dauerms, restore)


def csvfenstertreeaktualisieren(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    gui_csv_wrap_status_sicherstellen(daten)
    gui_csv_tree_neu_aufbauen(csvfensterid, G_csv_fenster)
    tree_widget = daten.get("tree")
    if tree_widget is not None:
        tree_spalten_breiten_anpassen(tree_widget, max_zeilen_pruefen=200)


def csv_rechtsklick(event, csvfensterid):
    fenster_info = G_csv_fenster.get(csvfensterid)
    if not fenster_info:
        return
    treecsv = fenster_info["tree"]
    item_id = treecsv.identify_row(event.y)
    spalte_id = treecsv.identify_column(event.x)
    if item_id:
        treecsv.focus(item_id)
        treecsv.selection_set(item_id)
    fenster_info["kontext_item_id"] = item_id
    fenster_info["kontext_spalte_id"] = spalte_id

    menu = tk.Menu(fenster_info["fenster"], tearoff=0)
    # Block 1: Kopieren
    menu.add_command(label="Feldinhalt kopieren", command=lambda fid=csvfensterid: csvfenster_feld_in_zwischenablage(fid))
    menu.add_command(label="Zeile kopieren", command=lambda fid=csvfensterid: csvfenster_zeile_in_zwischenablage(fid))
    menu.add_command(label="Zeile als CSV kopieren", command=lambda fid=csvfensterid: csvfenster_zeile_als_csv_in_zwischenablage(fid))
    menu.add_command(label="Header als CSV kopieren", command=lambda fid=csvfensterid: csvfenster_header_als_csv_in_zwischenablage(fid))
    menu.add_command(label="Tabelle als CSV kopieren", command=lambda fid=csvfensterid: csvfenster_tabelle_als_csv_kopieren(fid))
    menu.add_separator()
    # Block 2: Anzeigen
    menu.add_command(label="Feldinhalt im Lesefenster anzeigen", command=lambda fid=csvfensterid: csvfenster_feld_im_lesefenster_anzeigen(fid))
    menu.add_command(label="Zeile im Lesefenster anzeigen", command=lambda fid=csvfensterid: csvfenster_zeile_im_lesefenster_anzeigen(fid))
    menu.add_separator()
    # Block 3: Filtern
    menu.add_command(label="Feldfilter setzen", command=lambda fid=csvfensterid: csvfenster_feldfilter_setzen(fid))
    menu.add_command(label="Feldfilter aufheben", command=lambda fid=csvfensterid: csvfenster_feldfilter_aufheben(fid))
    menu.add_command(label="Eindeutige Feldwerte anzeigen", command=lambda fid=csvfensterid: csvfenster_eindeutige_feldwerte_anzeigen(fid))

    gui_csv_standard_rechtsklick_erweitern(
        menu,
        fenster_info["fenster"],
        csvfensterid,
        G_csv_fenster,
        refresh_callback=csvfenstertreeaktualisieren,
        hinweis_callback=csvfenstertemphinweis,
    )

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def csv_doppelklick(event, csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    treewidget = daten.get("tree")
    if treewidget is None:
        return
    item_id = treewidget.identify_row(event.y)
    spalte_id = treewidget.identify_column(event.x)
    if not item_id or not spalte_id:
        return
    daten["kontext_item_id"] = item_id
    daten["kontext_spalte_id"] = spalte_id
    werte = treewidget.item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    spaltenname = daten["header"][index] if index < len(daten.get("header", [])) else f"Spalte{index + 1}"
    gui_csv_zelltext_anzeigen(daten["fenster"], f"CSV-Zellinhalt - {spaltenname}", werte[index])


def csvfenster_feld_in_zwischenablage(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    item_id = daten.get("kontext_item_id")
    spalte_id = daten.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        return
    werte = daten["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    daten["fenster"].clipboard_clear()
    daten["fenster"].clipboard_append(str(werte[index]))


def csvfenster_zeile_in_zwischenablage(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    item_id = daten.get("kontext_item_id") or (daten["tree"].selection()[0] if daten["tree"].selection() else None)
    if not item_id:
        return
    werte = daten["tree"].item(item_id, "values")
    daten["fenster"].clipboard_clear()
    daten["fenster"].clipboard_append("\t".join(str(v) for v in werte))


def csvfenster_zeile_im_lesefenster_anzeigen(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    item_id = daten.get("kontext_item_id") or (daten["tree"].selection()[0] if daten["tree"].selection() else None)
    if not item_id:
        messagebox.showwarning("Zeileninhalt", "Bitte zuerst eine Zeile auswählen.", parent=daten["fenster"])
        return
    header = list(daten.get("header", []))
    werte = list(daten["tree"].item(item_id, "values"))
    zeilen = [
        f"CSV-Datei: {daten.get('dateiname', '')}",
        "",
    ]
    for index, wert in enumerate(werte):
        spaltenname = header[index] if index < len(header) else f"Spalte{index + 1}"
        zeilen.append(f"{spaltenname}: {wert}")
    gui_csv_zelltext_anzeigen(
        daten["fenster"],
        f"Zeile im Lesefenster – {daten.get('dateiname', 'CSV')}",
        "\n".join(zeilen),
    )


def csvfenster_feld_im_lesefenster_anzeigen(csvfensterid):
    """Zeigt den Inhalt des angeklickten CSV-Feldes im Lesefenster an."""
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    item_id = daten.get("kontext_item_id")
    spalte_id = daten.get("kontext_spalte_id")
    if not item_id or not spalte_id:
        messagebox.showwarning("Feldinhalt", "Bitte zuerst eine Zelle auswählen.", parent=daten["fenster"])
        return
    werte = daten["tree"].item(item_id, "values")
    index = int(spalte_id.replace("#", "")) - 1
    if index < 0 or index >= len(werte):
        return
    header = daten.get("header", [])
    spaltenname = header[index] if index < len(header) else f"Spalte{index + 1}"
    gui_csv_zelltext_anzeigen(
        daten["fenster"],
        f"Feldinhalt – {daten.get('dateiname', 'CSV')} · {spaltenname}",
        str(werte[index]),
    )


def csvfenster_zeile_als_csv_in_zwischenablage(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    item_id = daten.get("kontext_item_id") or (daten["tree"].selection()[0] if daten["tree"].selection() else None)
    if not item_id:
        return
    import csv as csv_modul, io
    werte = daten["tree"].item(item_id, "values")
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(["" if v is None else str(v) for v in werte])
    daten["fenster"].clipboard_clear()
    daten["fenster"].clipboard_append(ausgabe.getvalue().rstrip("\r\n"))


def csvfenster_header_als_csv_in_zwischenablage(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    import csv as csv_modul, io
    header = daten.get("header", [])
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(header)
    daten["fenster"].clipboard_clear()
    daten["fenster"].clipboard_append(ausgabe.getvalue().rstrip("\r\n"))


def csvfenster_als_tabelle_speichern(csvfensterid):
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    parent = daten.get("fenster")
    header = list(daten.get("header", []))
    rows = [list(zeile) for zeile in daten.get("rows", [])]
    dateipfad = daten.get("dateipfad", "")
    standardname = os.path.splitext(os.path.basename(dateipfad))[0] if dateipfad else "CSV_Import"
    standardname = eindeutigen_tabellennamen_vorschlagen(standardname)
    sql_ergebnis_als_tabelle_speichern(parent, standardname, header, rows)


def csvvorschaufenster_schliessen(csvfensterid):
    daten = G_csv_fenster.pop(csvfensterid, None)
    if not daten:
        return
    fenster_deregistrieren(daten.get("registry_id"))
    fenster = daten.get("fenster")
    if fenster and fenster.winfo_exists():
        fenster.destroy()


def csvvorschaufenster_oeffnen(csvdaten):
    top = tk.Toplevel(root)
    top.geometry("1100x650")
    top.minsize(800, 100)

    csvfensterid = str(top)
    dateiname = Path(csvdaten["dateipfad"]).name
    top.title(f"{G_EXE_Title} - CSV {dateiname}")
    registry_id = fenster_registrieren(top, "CSV")

    # Menüleiste mit Ansicht + Fensterliste + Als Tabelle speichern + Schließen
    csv_menue = fenster_standard_menue_anbringen(top, "1100x650", "CSV")
    csv_menue.add_command(label="Als Tabelle speichern", command=lambda fid=csvfensterid: csvfenster_als_tabelle_speichern(fid))
    csv_menue.add_command(label="Schließen", command=lambda fid=csvfensterid: csvvorschaufenster_schliessen(fid))

    header = list(csvdaten.get("header", []))
    rows = [list(zeile) for zeile in csvdaten.get("rows", [])]
    vorschauzeilen = min(len(rows), G_csv_import_optionen.get("vorschauzeilen", 200))

    toolbar = tk.Frame(top)
    toolbar.pack(fill="x", padx=10, pady=(10, 6))

    info_text = (
        f"Datei: {csvdaten['dateipfad']} | Spalten: {len(header)} | Datensätze: {len(rows)} | "
        f"Encoding: {csvdaten.get('encoding')} | Trennzeichen: {repr(csvdaten.get('delimiter', ','))}"
    )
    info_var = tk.StringVar(value=info_text)
    tk.Label(toolbar, textvariable=info_var, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

    frame = tk.Frame(top)
    frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    treecsv = ttk.Treeview(frame, show="headings", selectmode="browse")
    treecsv.grid(row=0, column=0, sticky="nsew")
    scrolly = ttk.Scrollbar(frame, orient="vertical", command=treecsv.yview)
    scrolly.grid(row=0, column=1, sticky="ns")
    scrollx = ttk.Scrollbar(frame, orient="horizontal", command=treecsv.xview)
    scrollx.grid(row=1, column=0, sticky="ew")
    treecsv.configure(yscrollcommand=scrolly.set, xscrollcommand=scrollx.set)

    if not header and rows:
        header = [f"Spalte{i + 1}" for i in range(len(rows[0]))]

    treecsv["columns"] = header
    for spalte in header:
        treecsv.heading(spalte, text=spalte)
        treecsv.column(spalte, anchor="w")

    G_csv_fenster[csvfensterid] = {
        "fenster": top,
        "tree": treecsv,
        "dateipfad": csvdaten["dateipfad"],
        "dateiname": dateiname,
        "delimiter": csvdaten.get("delimiter", ","),
        "encoding": csvdaten.get("encoding"),
        "header": header,
        "rows": rows,
        "sichtbarerows": [list(zeile) for zeile in rows],
        "vorschaulimit": vorschauzeilen,
        "sortierung": {},
        "wrap_spalten": {},
        "wrap_aktiv": False,
        "kontext_item_id": None,
        "kontext_spalte_id": None,
        "info_var": info_var,
        "info_text_original": info_text,
        "temphinweisjob": None,
        "anzeigewert_formatierer": csv_anzeigewert_formatieren,
        "registry_id": registry_id,
    }

    gui_csv_wrap_status_sicherstellen(G_csv_fenster[csvfensterid])
    csvfenstertreeaktualisieren(csvfensterid)

    treecsv.bind("<Button-3>", lambda event, fid=csvfensterid: csv_rechtsklick(event, fid))
    treecsv.bind("<Double-1>", lambda event, fid=csvfensterid: csv_doppelklick(event, fid))
    top.protocol("WM_DELETE_WINDOW", lambda fid=csvfensterid: csvvorschaufenster_schliessen(fid))


def csv_oeffnen():
    dateipfad = filedialog.askopenfilename(
        title="CSV-Datei öffnen",
        initialdir=str(csv_verzeichnis_sicherstellen()),
        filetypes=[("CSV-Dateien", "*.csv *.txt"), ("Alle Dateien", "*.*")],
    )
    if not dateipfad:
        return
    try:
        daten = csv_datei_laden(
            dateipfad,
            encoding_option=G_csv_import_optionen["encoding"],
            delimiter_option=G_csv_import_optionen["delimiter"],
            header_vorhanden=G_csv_import_optionen["header_vorhanden"],
        )
        csvvorschaufenster_oeffnen(daten)
    except Exception as e:
        messagebox.showerror("CSV öffnen", f"CSV-Datei konnte nicht geöffnet werden:\n{e}")


def csv_mit_windows_notepad_oeffnen():
    dateipfad = filedialog.askopenfilename(
        title="CSV-Datei auswählen",
        initialdir=str(csv_verzeichnis_sicherstellen()),
        filetypes=[("CSV-Dateien", "*.csv *.txt"), ("Alle Dateien", "*.*")],
    )
    if not dateipfad:
        return
    try:
        kandidaten = externe_programm_kandidaten(
            exe_namen=["notepad.exe"],
            ordner_prefixe=["Notepad"],
            shortcut_namen=[
                "notepad.exe - Shortcut.lnk",
                "notepad - Shortcut.lnk",
                "Notepad.lnk",
            ],
            path_namen=["notepad.exe", "notepad"],
            windows_system_fallbacks=["notepad.exe"],
        )
        if not kandidaten:
            messagebox.showwarning("Notepad", "Windows-Notepad wurde nicht gefunden.")
            return
        externe_programm_mit_datei_starten(kandidaten[0], dateipfad)
        debug_log(f"CSV mit Windows-Notepad geoeffnet: programm={kandidaten[0]}, datei={dateipfad}", "allgemein")
    except Exception as e:
        messagebox.showerror("Notepad", f"Konnte Notepad nicht öffnen:\n{e}")


def csv_mit_notepad_plus_plus_oeffnen():
    dateipfad = filedialog.askopenfilename(
        title="CSV-Datei auswählen",
        initialdir=str(csv_verzeichnis_sicherstellen()),
        filetypes=[("CSV-Dateien", "*.csv *.txt"), ("Alle Dateien", "*.*")],
    )
    if not dateipfad:
        return
    kandidaten = externe_programm_kandidaten(
        exe_namen=["notepad++.exe"],
        standard_pfade=[
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        ],
        ordner_prefixe=["Notepad++"],
        shortcut_namen=[
            "notepad++.exe - Shortcut.lnk",
            "notepad++ - Shortcut.lnk",
            "Notepad++.lnk",
        ],
        path_namen=["notepad++.exe", "notepad++"],
    )
    if not kandidaten:
        messagebox.showwarning(
            "Notepad++",
            "Notepad++ wurde nicht gefunden.\n\nGeprüft werden Standardpfade, PATH, ExterneApps, ExterneApps\\Notepad++... und passende Shortcuts."
        )
        return
    try:
        externe_programm_mit_datei_starten(kandidaten[0], dateipfad)
        debug_log(f"CSV mit Notepad++ geoeffnet: programm={kandidaten[0]}, datei={dateipfad}", "allgemein")
    except Exception as e:
        messagebox.showerror("Notepad++", f"Konnte Notepad++ nicht öffnen:\n{e}")


def toggle_fullscreen(event=None):
    aktuell = root.attributes("-fullscreen")
    root.attributes("-fullscreen", not aktuell)


def maximize():
    if root.attributes("-fullscreen"):
        root.attributes("-fullscreen", False)
    try:
        root.state("zoomed")
    except Exception:
        pass


def hauptfenster_drei_zeilen_anzeigen():
    hoehe = konfiguration_wert_lesen("global", "drei_zeilen_hoehe")
    if not hoehe:
        messagebox.showinfo(
            "3 Zeilen anzeigen",
            "Noch keine 3-Zeilen-Höhe gespeichert.\n\n"
            "Bitte Fenster auf die gewünschte Höhe einstellen\n"
            "und dann 'Aktuelle Höhe als 3-Zeilen-Höhe speichern' wählen.",
            parent=root
        )
        return
    try:
        breite = int(root.geometry().split("x")[0].split("+")[0])
    except Exception:
        breite = 920
    try:
        root.state("normal")
        root.attributes("-fullscreen", False)
    except Exception:
        pass
    root.geometry(f"{breite}x{hoehe}")


def hauptfenster_drei_zeilen_hoehe_speichern():
    try:
        hoehe = root.geometry().split("x")[1].split("+")[0]
        konfiguration_wert_speichern("global", "drei_zeilen_hoehe", hoehe)
        messagebox.showinfo(
            "3-Zeilen-Höhe gespeichert",
            f"Höhe {hoehe}px wurde als 3-Zeilen-Höhe gespeichert.\n"
            f"Gilt ab sofort für alle Fenster.",
            parent=root
        )
    except Exception as e:
        messagebox.showerror("Fehler", f"Höhe konnte nicht gespeichert werden:\n{e}", parent=root)


def normal():
    if root.attributes("-fullscreen"):
        root.attributes("-fullscreen", False)
    root.state("normal")
    root.geometry(G_Size_Normal)


def fenster_ansicht_normal(fenster, normal_geometry=None):
    try:
        if fenster.attributes("-fullscreen"):
            fenster.attributes("-fullscreen", False)
    except Exception:
        pass
    try:
        fenster.state("normal")
    except Exception:
        pass
    if normal_geometry:
        try:
            fenster.geometry(normal_geometry)
        except Exception:
            pass
    try:
        fenster.lift()
        fenster.focus_force()
    except Exception:
        pass


def fenster_ansicht_maximieren(fenster):
    try:
        if fenster.attributes("-fullscreen"):
            fenster.attributes("-fullscreen", False)
    except Exception:
        pass
    try:
        fenster.state("zoomed")
    except Exception:
        try:
            fenster.wm_state("zoomed")
        except Exception:
            pass
    try:
        fenster.lift()
        fenster.focus_force()
    except Exception:
        pass


def fenster_ansicht_fullscreen_umschalten(fenster):
    try:
        aktuell = bool(fenster.attributes("-fullscreen"))
        fenster.attributes("-fullscreen", not aktuell)
        if not aktuell:
            try:
                fenster.focus_force()
            except Exception:
                pass
    except Exception:
        pass


def fenster_benutzereinstellung_speichern(fenster, fenstertyp):
    if not db_ist_geladen():
        messagebox.showwarning("Benutzereinstellung", "Bitte zuerst eine Datenbank laden.")
        return
    bereich = f"fenster:{fenstertyp}"
    try:
        fullscreen = bool(fenster.attributes("-fullscreen"))
    except Exception:
        fullscreen = False
    try:
        state = fenster.state()
    except Exception:
        state = "normal"
    geometry = fenster.geometry()
    konfiguration_wert_speichern(bereich, "geometry", geometry)
    konfiguration_wert_speichern(bereich, "state", state)
    konfiguration_wert_speichern(bereich, "fullscreen", "1" if fullscreen else "0")
    debug_log(f"Fenster-Benutzereinstellung gespeichert: fenstertyp={fenstertyp}, geometry={geometry}, state={state}, fullscreen={fullscreen}", "fenster")
    messagebox.showinfo("Benutzereinstellung", f"Fenstergröße für '{fenstertyp}' wurde gespeichert.", parent=fenster)


def fenster_benutzereinstellung_anwenden(fenster, fenstertyp, normal_geometry=None):
    if not db_ist_geladen():
        messagebox.showwarning("Benutzereinstellung", "Bitte zuerst eine Datenbank laden.")
        return
    bereich = f"fenster:{fenstertyp}"
    geometry = konfiguration_wert_lesen(bereich, "geometry")
    state = konfiguration_wert_lesen(bereich, "state") or "normal"
    fullscreen = konfiguration_wert_lesen(bereich, "fullscreen") == "1"
    if not geometry and state == "normal" and not fullscreen:
        messagebox.showinfo("Benutzereinstellung", f"Für '{fenstertyp}' ist noch keine Benutzereinstellung gespeichert.", parent=fenster)
        return
    try:
        fenster.attributes("-fullscreen", False)
    except Exception:
        pass
    try:
        fenster.state("normal")
    except Exception:
        pass
    if geometry or normal_geometry:
        try:
            fenster.geometry(geometry or normal_geometry)
        except Exception:
            pass
    if fullscreen:
        try:
            fenster.attributes("-fullscreen", True)
        except Exception:
            pass
    elif state == "zoomed":
        try:
            fenster.state("zoomed")
        except Exception:
            pass
    try:
        fenster.lift()
        fenster.focus_force()
    except Exception:
        pass
    debug_log(f"Fenster-Benutzereinstellung angewendet: fenstertyp={fenstertyp}, geometry={geometry}, state={state}, fullscreen={fullscreen}", "fenster")


def fenster_benutzereinstellung_automatisch_anwenden(fenster, fenstertyp, normal_geometry=None):
    if not db_ist_geladen():
        return False
    bereich = f"fenster:{fenstertyp}"
    geometry = konfiguration_wert_lesen(bereich, "geometry")
    state = konfiguration_wert_lesen(bereich, "state")
    fullscreen_wert = konfiguration_wert_lesen(bereich, "fullscreen")
    if geometry is None and state is None and fullscreen_wert is None:
        return False
    fullscreen = fullscreen_wert == "1"
    try:
        fenster.attributes("-fullscreen", False)
    except Exception:
        pass
    try:
        fenster.state("normal")
    except Exception:
        pass
    if geometry or normal_geometry:
        try:
            fenster.geometry(geometry or normal_geometry)
        except Exception:
            pass
    if fullscreen:
        try:
            fenster.attributes("-fullscreen", True)
        except Exception:
            pass
    elif state == "zoomed":
        try:
            fenster.state("zoomed")
        except Exception:
            pass
    try:
        fenster.lift()
        fenster.focus_force()
    except Exception:
        pass
    debug_log(f"Fenster-Benutzereinstellung automatisch angewendet: fenstertyp={fenstertyp}, geometry={geometry}, state={state}, fullscreen={fullscreen}", "fenster")
    return True


def _rahmen_frame_anbringen(fenster):
    try:
        hoehe = G_rahmenhoehe or int(konfiguration_wert_lesen("SQL-Fenster", "rahmenhoehe") or 4)
    except Exception:
        hoehe = 4
    farben = [
        (G_rahmenfarbe or konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe") or "", G_rahmen_frames),
        (G_rahmenfarbe2 or konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe2") or "", G_rahmen_frames2),
        (G_rahmenfarbe3 or konfiguration_wert_lesen("SQL-Fenster", "rahmenfarbe3") or "", G_rahmen_frames3),
    ]
    for farbe, frames_dict in farben:
        # Frame immer anlegen und einpacken – auch ohne Farbe (height=0).
        # So bleibt der Pack-Order erhalten und rahmenfarbe_alle_fenster_aktualisieren
        # kann später einfach height/bg konfigurieren ohne neu zu packen.
        akt_hoehe = hoehe if farbe else 0
        akt_bg    = farbe if farbe else (fenster.cget("bg") if hasattr(fenster, "cget") else "#f0f0f0")
        rf = tk.Frame(fenster, bg=akt_bg, height=akt_hoehe)
        rf.pack_propagate(False)
        rf.pack(side="top", fill="x")
        frames_dict[fenster] = rf


def rahmenfarbe_alle_fenster_aktualisieren(farbe1, farbe2="", farbe3="", hoehe=None):
    global G_rahmenfarbe, G_rahmenfarbe2, G_rahmenfarbe3, G_rahmenhoehe
    G_rahmenfarbe = farbe1
    G_rahmenfarbe2 = farbe2
    G_rahmenfarbe3 = farbe3
    if hoehe is not None:
        G_rahmenhoehe = hoehe
    akt_hoehe = G_rahmenhoehe
    for dict_g, farbe in ((G_rahmen_frames, farbe1), (G_rahmen_frames2, farbe2), (G_rahmen_frames3, farbe3)):
        for fenster, rf in list(dict_g.items()):
            try:
                if not fenster.winfo_exists():
                    del dict_g[fenster]
                    continue
                if farbe:
                    rf.configure(bg=farbe, height=akt_hoehe)
                else:
                    rf.configure(height=0)
            except Exception:
                pass


def fenster_standard_menue_anbringen(fenster, normal_geometry=None, fenstertyp="Fenster", fensterliste_menue_anzeigen=True):
    menueleiste = tk.Menu(fenster)

    def drei_zeilen_anzeigen():
        """Setzt die Fensterhöhe auf den gespeicherten 3-Zeilen-Wert."""
        hoehe = konfiguration_wert_lesen("global", "drei_zeilen_hoehe")
        if not hoehe:
            messagebox.showinfo(
                "3 Zeilen anzeigen",
                "Noch keine 3-Zeilen-Höhe gespeichert.\n\n"
                "Bitte Fenster auf die gewünschte 3-Zeilen-Höhe einstellen\n"
                "und dann 'Aktuelle Höhe als 3-Zeilen-Höhe speichern' wählen.",
                parent=fenster
            )
            return
        try:
            aktuelle_geometrie = fenster.geometry()
            breite = int(aktuelle_geometrie.split("x")[0].split("+")[0])
        except Exception:
            breite = 800
        try:
            if fenster.attributes("-fullscreen"):
                fenster.attributes("-fullscreen", False)
        except Exception:
            pass
        try:
            fenster.state("normal")
        except Exception:
            pass
        fenster.geometry(f"{breite}x{hoehe}")

    def drei_zeilen_hoehe_speichern():
        """Speichert die aktuelle Fensterhöhe als globalen 3-Zeilen-Wert."""
        try:
            geometrie = fenster.geometry()
            hoehe = geometrie.split("x")[1].split("+")[0]
            konfiguration_wert_speichern("global", "drei_zeilen_hoehe", hoehe)
            messagebox.showinfo(
                "3-Zeilen-Höhe gespeichert",
                f"Höhe {hoehe}px wurde als 3-Zeilen-Höhe gespeichert.\n"
                f"Gilt ab sofort für alle Fenster.",
                parent=fenster
            )
        except Exception as e:
            messagebox.showerror("Fehler", f"Höhe konnte nicht gespeichert werden:\n{e}", parent=fenster)

    menuansicht = tk.Menu(menueleiste, tearoff=0)
    menuansicht.add_command(label="3 Zeilen anzeigen", command=drei_zeilen_anzeigen)
    menuansicht.add_command(label="Aktuelle Höhe als 3-Zeilen-Höhe speichern", command=drei_zeilen_hoehe_speichern)
    menuansicht.add_separator()
    menuansicht.add_command(label="Normalgröße", command=lambda: fenster_ansicht_normal(fenster, normal_geometry))
    menuansicht.add_command(label="Maximieren", command=lambda: fenster_ansicht_maximieren(fenster))
    menuansicht.add_command(label="Fullscreen", command=lambda: fenster_ansicht_fullscreen_umschalten(fenster))
    menuansicht.add_separator()
    menuansicht.add_command(label="Benutzereinstellung anwenden", command=lambda: fenster_benutzereinstellung_anwenden(fenster, fenstertyp, normal_geometry))
    menuansicht.add_command(label="Aktuelle Fenstergröße speichern", command=lambda: fenster_benutzereinstellung_speichern(fenster, fenstertyp))
    menueleiste.add_cascade(label="Ansicht", menu=menuansicht)

    if fensterliste_menue_anzeigen:
        menueleiste.add_command(label="Fensterliste", command=fensterliste_anzeigen)

    fenster.config(menu=menueleiste)
    _rahmen_frame_anbringen(fenster)
    # Menü sofort in aktivem Theme einfärben
    if G_aktuelles_theme_bg not in ("white", "#ffffff"):
        _menu_einfaerben(menueleiste, G_aktuelles_theme_bg, G_aktuelles_theme_fg,
                         G_aktuelles_theme_sel_bg, G_aktuelles_theme_sel_fg)
    fenster_benutzereinstellung_automatisch_anwenden(fenster, fenstertyp, normal_geometry)
    return menueleiste


def menue_british_racing_green_anwenden(menu):
    if menu is None:
        return
    farbe_bg = "#004225"
    farbe_fg = "#FFFFFF"
    farbe_aktiv = "#0B6B3A"
    try:
        menu.configure(
            background=farbe_bg,
            foreground=farbe_fg,
            activebackground=farbe_aktiv,
            activeforeground=farbe_fg,
            borderwidth=0,
        )
    except Exception as e:
        debug_log(f"Menue-Farbtest konnte nicht auf Menue angewendet werden: {e}", "fenster")
    try:
        ende = menu.index("end")
    except Exception:
        ende = None
    if ende is None:
        return
    for index in range(ende + 1):
        try:
            menu.entryconfigure(
                index,
                background=farbe_bg,
                foreground=farbe_fg,
                activebackground=farbe_aktiv,
                activeforeground=farbe_fg,
            )
        except Exception:
            pass
        try:
            submenu_name = menu.entrycget(index, "menu")
            if submenu_name:
                submenu = menu.nametowidget(submenu_name)
                menue_british_racing_green_anwenden(submenu)
        except Exception:
            pass


def app_beenden():
    if sql_editor_hat_ungespeicherte_aenderungen():
        antwort = messagebox.askyesnocancel(
            "Applikation beenden",
            "Im SQL Editor gibt es ungespeicherte Änderungen.\n\n"
            "Sollen die Änderungen vor dem Beenden gespeichert werden?",
            icon="warning",
        )
        if antwort is None:
            return
        if antwort:
            ok = sql_editor_speichern()
            if not ok:
                if not messagebox.askyesno(
                    "Applikation beenden",
                    "Die Abfrage konnte nicht gespeichert werden.\n\nTrotzdem beenden?",
                    icon="warning",
                ):
                    return
    root.destroy()


def hilfe_anzeigen():
    messagebox.showinfo("Hilfe", G_HELP_INFO)


def tabellenfenster_fuer_sql_holen(tabellenname):
    fid = G_tabellenfenster_nach_name.get(tabellenname)
    if not fid:
        return None
    return G_tabellen_cache.get(fid, {}).get("fenster")


# ── Dunkel-Modus: rekursives Einfärben ──────────────────────────────────────

def _fenster_einfaerben(widget, bg, fg, sel_bg, sel_fg, skip_ids):
    """Färbt ein Widget und alle seine Kinder rekursiv ein."""
    if id(widget) in skip_ids:
        return
    # Widgets mit _no_theme=True (Farbquadrate, Theme-Buttons) überspringen
    if getattr(widget, "_no_theme", False):
        return
    try:
        cls = widget.winfo_class()
        if cls in ("Frame", "Labelframe", "Toplevel"):
            widget.configure(bg=bg)
        elif cls == "Label":
            widget.configure(bg=bg, fg=fg)
        elif cls == "Button":
            widget.configure(bg=bg, fg=fg,
                             activebackground=bg, activeforeground=fg)
        elif cls in ("Entry", "Spinbox"):
            widget.configure(bg=bg, fg=fg, insertbackground=fg,
                             selectbackground=sel_bg, selectforeground=sel_fg,
                             readonlybackground=bg, disabledbackground=bg)
        elif cls == "Text":
            widget.configure(bg=bg, fg=fg, insertbackground=fg,
                             selectbackground=sel_bg, selectforeground=sel_fg)
        elif cls in ("Radiobutton", "Checkbutton"):
            widget.configure(bg=bg, fg=fg,
                             activebackground=bg, activeforeground=fg,
                             selectcolor=bg)
        elif cls == "Listbox":
            widget.configure(bg=bg, fg=fg,
                             selectbackground=sel_bg, selectforeground=sel_fg)
        elif cls == "Canvas":
            widget.configure(bg=bg)
        elif cls == "Menu":
            widget.configure(bg=bg, fg=fg,
                             activebackground=sel_bg, activeforeground=sel_fg)
        elif cls == "Scrollbar":
            widget.configure(bg=bg, troughcolor=bg, activebackground=sel_bg)
        elif cls == "Panedwindow":
            widget.configure(bg=bg)
        elif cls == "Scale":
            widget.configure(bg=bg, fg=fg, troughcolor=bg)
        elif cls in ("TEntry", "TCombobox", "TSpinbox"):
            # Für ttk-Eingabewidgets: Vordergrundfarbe direkt setzen;
            # Hintergrund läuft über ttk.Style (fieldbackground).
            # <<ThemeChanged>> erzwingt Neuzeichnung nach Style-Map-Update
            # (wichtig für readonly-Combobox, die den State-Map-Cache hält).
            try:
                widget.configure(foreground=fg)
            except Exception:
                pass
            try:
                widget.event_generate("<<ThemeChanged>>")
            except Exception:
                pass
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _fenster_einfaerben(child, bg, fg, sel_bg, sel_fg, skip_ids)
    except Exception:
        pass


def _menu_einfaerben(menu, bg, fg, sel_bg, sel_fg):
    """Färbt ein tk.Menu und alle seine Untermenüs rekursiv ein."""
    try:
        menu.configure(bg=bg, fg=fg,
                       activebackground=sel_bg, activeforeground=sel_fg,
                       disabledforeground="#888888" if bg == "#000000" else "gray")
        last = menu.index("end")
        if last is None:
            return
        for i in range(last + 1):
            try:
                if menu.type(i) == "cascade":
                    submenu_name = menu.entrycget(i, "menu")
                    submenu = menu.nametowidget(submenu_name)
                    _menu_einfaerben(submenu, bg, fg, sel_bg, sel_fg)
            except Exception:
                pass
    except Exception:
        pass


def _fenster_menu_einfaerben(fenster, bg, fg, sel_bg, sel_fg):
    """Holt das Menü eines Fensters (falls vorhanden) und färbt es ein."""
    try:
        menu_name = fenster.cget("menu")
        if menu_name:
            menu_widget = fenster.nametowidget(menu_name)
            _menu_einfaerben(menu_widget, bg, fg, sel_bg, sel_fg)
    except Exception:
        pass


def alle_fenster_dark_anwenden(bg, fg, sel_bg, sel_fg):
    """Wird vom SQL-Modul aufgerufen, wenn das Theme gewechselt wird."""
    global G_aktuelles_theme_bg, G_aktuelles_theme_fg
    global G_aktuelles_theme_sel_bg, G_aktuelles_theme_sel_fg
    G_aktuelles_theme_bg     = bg
    G_aktuelles_theme_fg     = fg
    G_aktuelles_theme_sel_bg = sel_bg
    G_aktuelles_theme_sel_fg = sel_fg

    # Stripe-Frames und Fensterliste vom Einfärben ausnehmen (vor erstem Aufruf!)
    skip_ids = set()
    for d in (G_rahmen_frames, G_rahmen_frames2, G_rahmen_frames3):
        for rf in d.values():
            try:
                skip_ids.add(id(rf))
            except Exception:
                pass

    # Fensterliste-Fenster jetzt schon in skip_ids aufnehmen,
    # damit es auch beim root-Traversal (winfo_children) übersprungen wird
    fl_fenster = None
    try:
        if G_fensterliste_fenster:
            fl_fenster = G_fensterliste_fenster.get("fenster")
            if fl_fenster:
                skip_ids.add(id(fl_fenster))
    except Exception:
        pass

    # option_add für zukünftig erzeugte tk-Widgets
    _ist_dunkel = bg not in ("white", "#ffffff", "#f0f0f0")
    try:
        if _ist_dunkel:
            root.option_add("*Background",                          bg,     "interactive")
            root.option_add("*Foreground",                          fg,     "interactive")
            root.option_add("*Entry.Background",                    bg,     "interactive")
            root.option_add("*Entry.Foreground",                    fg,     "interactive")
            root.option_add("*Text.Background",                     bg,     "interactive")
            root.option_add("*Text.Foreground",                     fg,     "interactive")
            root.option_add("*selectBackground",                    sel_bg, "interactive")
            root.option_add("*selectForeground",                    sel_fg, "interactive")
            root.option_add("*insertBackground",                    fg,     "interactive")
            root.option_add("*activeBackground",                    bg,     "interactive")
            root.option_add("*activeForeground",                    fg,     "interactive")
            # Scrollbar-Kanal (Trough) einfärben
            root.option_add("*Scrollbar.troughColor",               bg,     "interactive")
            root.option_add("*Scrollbar.background",                bg,     "interactive")
            # readonly- und disabled-Hintergrund für Entry/Spinbox
            root.option_add("*Entry.readonlyBackground",            bg,     "interactive")
            root.option_add("*Entry.disabledBackground",            bg,     "interactive")
            root.option_add("*Spinbox.readonlyBackground",          bg,     "interactive")
            root.option_add("*Spinbox.disabledBackground",          bg,     "interactive")
            # Popup-Listbox der ttk.Combobox einfärben
            root.option_add("*TCombobox*Listbox.background",        bg,     "interactive")
            root.option_add("*TCombobox*Listbox.foreground",        fg,     "interactive")
            root.option_add("*TCombobox*Listbox.selectBackground",  sel_bg, "interactive")
            root.option_add("*TCombobox*Listbox.selectForeground",  sel_fg, "interactive")
        else:
            root.option_clear()
    except Exception:
        pass

    # Hauptfenster einfärben (Fensterliste ist via skip_ids ausgenommen)
    _fenster_einfaerben(root, bg, fg, sel_bg, sel_fg, skip_ids)
    # Hauptfenster-Menü einfärben
    _fenster_menu_einfaerben(root, bg, fg, sel_bg, sel_fg)

    # Alle registrierten Tabellen-/Workflow-Fenster einfärben inkl. ihrer Menüs
    for fid, info in list(G_fenster_registry.items()):
        fenster = info.get("fenster")
        if not fenster or fenster is root:
            continue
        if fl_fenster and fenster is fl_fenster:
            continue
        try:
            if fenster.winfo_exists():
                _fenster_einfaerben(fenster, bg, fg, sel_bg, sel_fg, skip_ids)
                _fenster_menu_einfaerben(fenster, bg, fg, sel_bg, sel_fg)
        except Exception:
            pass


sql_modul_initialisieren(
    root_widget=root,
    exe_title=G_EXE_Title,
    get_geladene_db_datei=lambda: G_geladene_db_datei,
    sqlite_verbindung_oeffnen_funktion=sqlite_verbindung_oeffnen,
    sql_identifier_funktion=sql_identifier,
    sql_name_ok_funktion=sql_name_ok,
    db_ist_geladen_funktion=db_ist_geladen,
    db_pruefen_oder_warnen_funktion=db_pruefen_oder_warnen,
    tabellen_laden_funktion=tabellen_laden,
    tabellen_dropdown_aktualisieren_funktion=tabellen_dropdown_aktualisieren,
    tree_spalten_breiten_anpassen_funktion=tree_spalten_breiten_anpassen,
    fenster_registrieren_funktion=fenster_registrieren,
    ipv4_to_int_funktion=globals().get("ipv4_to_int"),
    debug_log_funktion=debug_log,
    logging_eintrag_schreiben_funktion=logging_eintrag_schreiben,
    fenster_standard_menue_anbringen_funktion=fenster_standard_menue_anbringen,
    fenster_schliessen_callback_setzen_funktion=fenster_schliessen_callback_setzen,
    ip_range_aufteilen_funktion_param=ip_range_aufteilen,
    eindeutigen_tabellennamen_param=eindeutigen_tabellennamen_vorschlagen,
    eindeutigen_dateinamen_param=eindeutigen_dateinamen_vorschlagen,
    hauptfenster_projekt_modus_setzen_funktion=hauptfenster_projekt_modus_setzen,
    tabellenfenster_oeffnen_funktion=tabellenfenster_oeffnen,
    tabellenfenster_holen_funktion=tabellenfenster_fuer_sql_holen,
    rahmenfarbe_setzen_funktion=rahmenfarbe_alle_fenster_aktualisieren,
    fensterliste_farben_setzen_funktion=fensterliste_farben_setzen,
    alle_workflow_fenster_schliessen_funktion=alle_workflow_tabellen_schliessen,
    alle_fenster_einfaerben_funktion=alle_fenster_dark_anwenden,
    admin_code_fuer_aktion_pruefen_funktion=admin_code_fuer_aktion_pruefen,
)


main_paned = ttk.Panedwindow(root, orient="horizontal")
left_frame = tk.Frame(main_paned, padx=8, pady=8)
right_frame = tk.Frame(main_paned, padx=8, pady=8)
main_paned.add(left_frame, weight=1)
main_paned.add(right_frame, weight=4)
left_frame.grid_rowconfigure(1, weight=1)
left_frame.grid_columnconfigure(0, weight=1)
right_frame.grid_rowconfigure(1, weight=1)
right_frame.grid_columnconfigure(0, weight=1)

tk.Label(left_frame, text="Tabellen", anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 6))
tree_tabellen = ttk.Treeview(left_frame, columns=("name",), show="headings", selectmode="browse")
tree_tabellen.heading("name", text="Name")
tree_tabellen.column("name", anchor="w")
tree_tabellen.grid(row=1, column=0, sticky="nsew")
sy_left = ttk.Scrollbar(left_frame, orient="vertical", command=tree_tabellen.yview)
sy_left.grid(row=1, column=1, sticky="ns")
tree_tabellen.configure(yscrollcommand=sy_left.set)

tk.Label(right_frame, text="Vorschau", anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 6))
treeframe = tk.Frame(right_frame)
treeframe.grid(row=1, column=0, sticky="nsew")
treeframe.grid_rowconfigure(0, weight=1)
treeframe.grid_columnconfigure(0, weight=1)
tree = ttk.Treeview(treeframe, show="headings")
tree.grid(row=0, column=0, sticky="nsew")
sy = ttk.Scrollbar(treeframe, orient="vertical", command=tree.yview)
sx = ttk.Scrollbar(treeframe, orient="horizontal", command=tree.xview)
sy.grid(row=0, column=1, sticky="ns")
sx.grid(row=1, column=0, sticky="ew")
tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

tree_tabellen.bind("<<TreeviewSelect>>", tabelle_links_ausgewaehlt)
tree_tabellen.bind("<Double-1>", tabelle_doppelklick)
tree_tabellen.bind("<Double-1>", tabelle_doppelklick)

menueleiste = tk.Menu(root)
menudatei = tk.Menu(menueleiste, tearoff=0)
menudatei.add_command(label="DB laden", command=db_laden)
menudatei.add_separator()
menudatei.add_command(label="Datenbank komprimieren (VACUUM)", command=datenbank_komprimieren)
menudatei.add_separator()
menudatei.add_command(label="Debug umschalten", command=debug_toggle)
menudatei.add_separator()
menudatei.add_command(label="Adminzugang", command=adminzugang_entsperren, state="disabled")
menudatei.add_command(label="Admin-Code ändern...", command=admin_code_aendern_dialog)
menudatei.add_separator()
menudatei.add_command(label="Beenden", command=app_beenden)
menueleiste.add_cascade(label="Datei", menu=menudatei)

menutabelle = tk.Menu(menueleiste, tearoff=0)
menutabelle.add_command(label="Tabelle hinzufügen", command=tabelle_hinzufuegen)
menutabelle.add_command(label="Tabelle umbenennen", command=tabelle_umbenennen)
menutabelle.add_command(label="Tabelle in DB kopieren", command=tabelle_in_db_kopieren)
menutabelle.add_command(label="Kopie von Tabelle herstellen", command=tabelle_kopie_herstellen)
menutabelle.add_separator()
menutabelle.add_command(label="Tabelle leeren", command=tabelle_leeren)
menutabelle.add_command(label="Tabelle löschen", command=tabelle_loeschen)
menutabelle.add_separator()
menutabelle.add_command(label="Header hinzufügen", command=header_hinzufuegen)
menutabelle.add_command(label="PK hinzufügen", command=pk_hinzufuegen)
menutabelle.add_separator()
menutabelle.add_command(label="Findings hinzufügen", command=findings_hinzufuegen)
menutabelle.add_command(label="Findings entfernen", command=findings_entfernen)
menutabelle.add_separator()
menutabelle.add_command(label="Logging hinzufügen", command=logging_hinzufuegen)
menutabelle.add_command(label="Logging entfernen", command=logging_entfernen)
menueleiste.add_cascade(label="Tabelle", menu=menutabelle)

menucsv = tk.Menu(menueleiste, tearoff=0)
menucsv.add_command(label="CSV öffnen", command=csv_oeffnen)
menucsv.add_separator()
menucsv.add_command(label="CSV mit Windows-Notepad öffnen", command=csv_mit_windows_notepad_oeffnen)
menucsv.add_command(label="CSV mit Notepad++ öffnen", command=csv_mit_notepad_plus_plus_oeffnen)
menueleiste.add_cascade(label="CSV", menu=menucsv)

menusql = tk.Menu(menueleiste, tearoff=0)
menusql.add_command(label="SQL Editor", command=sql_abfrage_fenster_oeffnen)
menueleiste.add_cascade(label="SQL", menu=menusql)

menuansicht = tk.Menu(menueleiste, tearoff=0)
menuansicht.add_command(label="3 Zeilen anzeigen", command=lambda: hauptfenster_drei_zeilen_anzeigen())
menuansicht.add_command(label="Aktuelle Höhe als 3-Zeilen-Höhe speichern", command=lambda: hauptfenster_drei_zeilen_hoehe_speichern())
menuansicht.add_separator()
menuansicht.add_command(label="Maximieren", command=maximize)
menuansicht.add_command(label="Normalgröße", command=normal)
menuansicht.add_command(label="Fullscreen", command=toggle_fullscreen)
menuansicht.add_separator()
menuansicht.add_command(label="Benutzereinstellung anwenden", command=lambda: fenster_benutzereinstellung_anwenden(root, "Hauptfenster", G_Size_Normal))
menuansicht.add_command(label="Aktuelle Fenstergröße speichern", command=lambda: fenster_benutzereinstellung_speichern(root, "Hauptfenster"))
menueleiste.add_cascade(label="Ansicht", menu=menuansicht)

menuhilfe = tk.Menu(menueleiste, tearoff=0)
menuhilfe.add_command(label="Hilfe", command=hilfe_anzeigen)
menueleiste.add_cascade(label="Hilfe", menu=menuhilfe)

menueleiste.add_command(label="Fensterliste", command=fensterliste_anzeigen)

root.config(menu=menueleiste)
root.protocol("WM_DELETE_WINDOW", app_beenden)
_rahmen_frame_anbringen(root)
gui_set_rahmen_frame_callback(_rahmen_frame_anbringen)
main_paned.pack(fill="both", expand=True)
root.mainloop()


def csvfenster_tabelle_als_csv_kopieren(csvfensterid):
    """Kopiert alle sichtbaren CSV-Zeilen als CSV – mit freier Anzahleingabe."""
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    fenster = daten["fenster"]
    tree = daten["tree"]
    alle_ids = tree.get_children()
    if not alle_ids:
        messagebox.showwarning("Tabelle als CSV", "Keine Zeilen vorhanden.", parent=fenster)
        return
    gesamt = len(alle_ids)

    dialog = tk.Toplevel(fenster)
    dialog.title("Tabelle als CSV kopieren")
    dialog.geometry("380x160")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(fenster)
    tk.Label(dialog, text=f"Sichtbare Zeilen: {gesamt:,}".replace(",", "."), anchor="w").pack(fill="x", padx=16, pady=(16, 4))
    tk.Label(dialog, text="Anzahl zu kopierender Zeilen (leer = alle):", anchor="w").pack(fill="x", padx=16)
    anzahl_var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=anzahl_var, width=20)
    entry.pack(anchor="w", padx=16, pady=(4, 0))
    entry.focus_set()
    ergebnis = [None]

    def bestaetigen(event=None):
        ergebnis[0] = anzahl_var.get().strip()
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(fill="x", padx=16, pady=(12, 0))
    tk.Button(btn_frame, text="Kopieren", width=12, command=bestaetigen).pack(side="right", padx=(8, 0))
    tk.Button(btn_frame, text="Abbrechen", width=12, command=dialog.destroy).pack(side="right")
    entry.bind("<Return>", bestaetigen)
    dialog.wait_window()

    if ergebnis[0] is None:
        return
    if ergebnis[0] == "":
        ids = alle_ids
    else:
        try:
            n = int(ergebnis[0])
            ids = alle_ids[:max(1, n)]
        except ValueError:
            messagebox.showwarning("Tabelle als CSV", f"'{ergebnis[0]}' ist keine gültige Zahl.", parent=fenster)
            return

    import csv as csv_modul, io
    header = list(daten.get("header", []))
    ausgabe = io.StringIO()
    writer = csv_modul.writer(ausgabe, quoting=csv_modul.QUOTE_ALL)
    writer.writerow(header)
    for item_id in ids:
        writer.writerow(["" if v is None else str(v) for v in tree.item(item_id, "values")])
    fenster.clipboard_clear()
    fenster.clipboard_append(ausgabe.getvalue())


def csvfenster_feldfilter_setzen(csvfensterid):
    """Filtert die CSV-Anzeige nach dem aktuellen Feldwert."""
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    fenster = daten["fenster"]
    spalte_id = daten.get("kontext_spalte_id")
    item_id = daten.get("kontext_item_id")
    if not spalte_id or not item_id:
        messagebox.showwarning("Feldfilter", "Bitte zuerst eine Zelle auswählen.", parent=fenster)
        return
    index = int(spalte_id.replace("#", "")) - 1
    header = daten.get("header", [])
    spaltenname = header[index] if index < len(header) else f"Spalte{index+1}"
    werte = daten["tree"].item(item_id, "values")
    feldwert = str(werte[index]) if index < len(werte) else ""

    dialog = tk.Toplevel(fenster)
    dialog.title(f"CSV – Feld filtern")
    dialog.geometry("520x200")
    dialog.minsize(420, 180)
    dialog.transient(fenster)
    dialog.grab_set()
    frame = tk.Frame(dialog, padx=12, pady=12)
    frame.pack(fill="both", expand=True)
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_columnconfigure(1, weight=1)
    tk.Label(frame, text="Spalte:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    tk.Label(frame, text=spaltenname).grid(row=0, column=1, sticky="w", pady=(0, 8))
    tk.Label(frame, text="Filterwert:").grid(row=1, column=0, sticky="nw", padx=(0, 8))
    text_frame = tk.Frame(frame)
    text_frame.grid(row=1, column=1, sticky="nsew")
    text_frame.grid_rowconfigure(0, weight=1)
    text_frame.grid_columnconfigure(0, weight=1)
    filter_text = tk.Text(text_frame, height=3, wrap="word")
    filter_text.grid(row=0, column=0, sticky="nsew")
    text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=filter_text.yview)
    text_scroll.grid(row=0, column=1, sticky="ns")
    filter_text.configure(yscrollcommand=text_scroll.set)
    filter_text.insert("1.0", feldwert)
    filter_text.focus_force()

    btn_frame = tk.Frame(frame)
    btn_frame.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))

    def anwenden():
        filterwert = filter_text.get("1.0", "end").strip()
        rows_alle = daten.get("rows", [])
        gefiltert = [z for z in rows_alle if index < len(z) and str(z[index]) == filterwert]
        daten["sichtbarerows"] = gefiltert
        gui_csv_tree_neu_aufbauen(csvfensterid, G_csv_fenster)
        csvfenstertemphinweis(csvfensterid, f" * Filter aktiv: {spaltenname} = {filterwert} ({len(gefiltert)} Zeilen)")
        dialog.destroy()

    tk.Button(btn_frame, text="Abbrechen", command=dialog.destroy, width=12).pack(side="right")
    tk.Button(btn_frame, text="Hiernach filtern", command=anwenden, width=14).pack(side="right", padx=(0, 8))
    dialog.bind("<Return>", lambda e: anwenden())


def csvfenster_feldfilter_aufheben(csvfensterid):
    """Hebt den aktuellen CSV-Filter auf und zeigt alle Zeilen wieder an."""
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    if "sichtbarerows" in daten:
        del daten["sichtbarerows"]
    gui_csv_tree_neu_aufbauen(csvfensterid, G_csv_fenster)
    csvfenstertemphinweis(csvfensterid, " * Filter aufgehoben")


def csvfenster_eindeutige_feldwerte_anzeigen(csvfensterid):
    """Zeigt eindeutige Werte der aktuellen Spalte im Lesefenster an."""
    daten = G_csv_fenster.get(csvfensterid)
    if not daten:
        return
    fenster = daten["fenster"]
    spalte_id = daten.get("kontext_spalte_id")
    if not spalte_id:
        messagebox.showwarning("Eindeutige Werte", "Bitte zuerst eine Spalte auswählen.", parent=fenster)
        return
    index = int(spalte_id.replace("#", "")) - 1
    header = daten.get("header", [])
    spaltenname = header[index] if index < len(header) else f"Spalte{index+1}"
    tree = daten["tree"]
    werte = set()
    for item_id in tree.get_children():
        vals = tree.item(item_id, "values")
        if index < len(vals):
            werte.add(str(vals[index]))
    sortiert = sorted(werte)
    text = f"Eindeutige Werte in '{spaltenname}' ({len(sortiert)}):\n\n" + "\n".join(sortiert)
    gui_csv_zelltext_anzeigen(fenster, f"Eindeutige Werte – {spaltenname}", text)



        