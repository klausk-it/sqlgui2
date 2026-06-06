import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import textwrap

WINDOW_REGISTRATION_CALLBACK = None
RAHMEN_FRAME_CALLBACK = None


def gui_set_window_registration_callback(callback):
    global WINDOW_REGISTRATION_CALLBACK
    WINDOW_REGISTRATION_CALLBACK = callback


def gui_set_rahmen_frame_callback(callback):
    global RAHMEN_FRAME_CALLBACK
    RAHMEN_FRAME_CALLBACK = callback




def gui_text_umbruch(text, breite=30, harte_trennung=False):
    if text is None:
        return ""

    text = str(text)
    if not text:
        return ""

    zeilen = text.splitlines() or [text]
    ergebnis = []

    for zeile in zeilen:
        if not zeile.strip():
            ergebnis.append("")
            continue

        wrapped = textwrap.wrap(
            zeile,
            width=max(1, int(breite)),
            break_long_words=harte_trennung,
            break_on_hyphens=harte_trennung,
        )

        if wrapped:
            ergebnis.extend(wrapped)
        else:
            ergebnis.append(zeile)

    return "\n".join(ergebnis)


def gui_csv_wrap_status_sicherstellen(csvdaten):
    if csvdaten is None:
        return

    if "wrap_spalten" not in csvdaten:
        csvdaten["wrap_spalten"] = {}

    if "wrap_aktiv" not in csvdaten:
        csvdaten["wrap_aktiv"] = False

    if "wrap_zeilenhoehe" not in csvdaten:
        csvdaten["wrap_zeilenhoehe"] = 48


def gui_csv_anzeigezeile_mit_wrap(csvdaten, zeile):
    if csvdaten is None:
        return list(zeile)

    gui_csv_wrap_status_sicherstellen(csvdaten)

    header = csvdaten.get("header", [])
    wrap_spalten = csvdaten.get("wrap_spalten", {})
    neue_zeile = []

    for index, wert in enumerate(zeile):
        spaltenname = header[index] if index < len(header) else f"Spalte{index + 1}"

        if spaltenname in wrap_spalten:
            breite = wrap_spalten.get(spaltenname, 30)
            neue_zeile.append(gui_text_umbruch(wert, breite=breite, harte_trennung=False))
        else:
            neue_zeile.append("" if wert is None else str(wert))

    return neue_zeile


def gui_csv_kontext_auflosen(csvfenster_oder_id, Gcsvfenster=None):
    if isinstance(csvfenster_oder_id, dict):
        return None, csvfenster_oder_id

    if Gcsvfenster is None:
        return None, None

    daten = Gcsvfenster.get(csvfenster_oder_id)
    return csvfenster_oder_id, daten


def gui_csv_tree_neu_aufbauen(csvfenster_oder_id, Gcsvfenster=None, csvsuchtreffertagsaktualisieren=None):
    csvfensterid, daten = gui_csv_kontext_auflosen(csvfenster_oder_id, Gcsvfenster)
    if not daten:
        return

    treewidget = daten.get("tree")
    if treewidget is None:
        return

    gui_csv_wrap_status_sicherstellen(daten)
    treewidget.delete(*treewidget.get_children())

    rows = daten.get("sichtbarerows", daten.get("rows", []))
    limit = daten.get("vorschaulimit", len(rows))

    for zeile in rows[:limit]:
        anzeigezeile = gui_csv_anzeigezeile_mit_wrap(daten, zeile)
        treewidget.insert("", "end", values=anzeigezeile)

    treewidget.tag_configure("suchtreffer", background="#fff3b0", foreground="black")
    treewidget.tag_configure("aktiversuchtreffer", background="#ffd166", foreground="black")

    if callable(csvsuchtreffertagsaktualisieren) and csvfensterid is not None:
        csvsuchtreffertagsaktualisieren(csvfensterid)


def gui_csv_wrap_spalte_setzen(
    csvfenster_oder_id,
    spaltenname,
    breite,
    Gcsvfenster=None,
    refresh_callback=None,
    hinweis_callback=None,
):
    csvfensterid, daten = gui_csv_kontext_auflosen(csvfenster_oder_id, Gcsvfenster)
    if not daten:
        return False

    gui_csv_wrap_status_sicherstellen(daten)

    try:
        breite = max(5, int(breite))
    except Exception:
        return False

    daten["wrap_spalten"][spaltenname] = breite
    daten["wrap_aktiv"] = True

    if callable(refresh_callback):
        if csvfensterid is not None:
            refresh_callback(csvfensterid)
        else:
            refresh_callback(daten)

    if callable(hinweis_callback):
        meldung = f"Umbruch aktiv: {spaltenname} / {breite} Zeichen"
        if csvfensterid is not None:
            hinweis_callback(csvfensterid, meldung)
        else:
            hinweis_callback(daten, meldung)

    return True


def gui_csv_wrap_spalte_aufheben(
    csvfenster_oder_id,
    spaltenname,
    Gcsvfenster=None,
    refresh_callback=None,
    hinweis_callback=None,
):
    csvfensterid, daten = gui_csv_kontext_auflosen(csvfenster_oder_id, Gcsvfenster)
    if not daten:
        return False

    gui_csv_wrap_status_sicherstellen(daten)

    if spaltenname in daten["wrap_spalten"]:
        del daten["wrap_spalten"][spaltenname]

    daten["wrap_aktiv"] = bool(daten["wrap_spalten"])

    if callable(refresh_callback):
        if csvfensterid is not None:
            refresh_callback(csvfensterid)
        else:
            refresh_callback(daten)

    if callable(hinweis_callback):
        meldung = f"Umbruch aufgehoben: {spaltenname}"
        if csvfensterid is not None:
            hinweis_callback(csvfensterid, meldung)
        else:
            hinweis_callback(daten, meldung)

    return True


def gui_csv_wrap_alle_aufheben(
    csvfenster_oder_id,
    Gcsvfenster=None,
    refresh_callback=None,
    hinweis_callback=None,
):
    csvfensterid, daten = gui_csv_kontext_auflosen(csvfenster_oder_id, Gcsvfenster)
    if not daten:
        return False

    gui_csv_wrap_status_sicherstellen(daten)
    daten["wrap_spalten"].clear()
    daten["wrap_aktiv"] = False

    if callable(refresh_callback):
        if csvfensterid is not None:
            refresh_callback(csvfensterid)
        else:
            refresh_callback(daten)

    if callable(hinweis_callback):
        meldung = "Spaltenumbruch komplett aufgehoben"
        if csvfensterid is not None:
            hinweis_callback(csvfensterid, meldung)
        else:
            hinweis_callback(daten, meldung)

    return True


def gui_csv_wrap_dialog_fuer_spalte(
    parent,
    csvfensterid,
    spaltenname,
    Gcsvfenster,
    refresh_callback=None,
    hinweis_callback=None,
):
    daten = Gcsvfenster.get(csvfensterid)
    if not daten:
        return False

    gui_csv_wrap_status_sicherstellen(daten)
    vorbelegt = daten.get("wrap_spalten", {}).get(spaltenname, 30)

    breite = simpledialog.askinteger(
        "Spaltenumbruch",
        f"Bitte Umbruchbreite für die Spalte\n\n{spaltenname}\n\nin Zeichen eingeben:",
        parent=parent,
        initialvalue=vorbelegt,
        minvalue=5,
        maxvalue=500,
    )

    if breite is None:
        return False

    return gui_csv_wrap_spalte_setzen(
        csvfensterid,
        spaltenname,
        breite,
        Gcsvfenster,
        refresh_callback=refresh_callback,
        hinweis_callback=hinweis_callback,
    )


def gui_csv_zelltext_anzeigen(parent, titel, text, ziel_x=None, ziel_y=None, ziel_hoehe=None,
                              nav_hoch=None, nav_runter=None):
    """Zeigt Text im Lesefenster.
    nav_hoch / nav_runter: optionale Callbacks für ▲ ▼ Navigation.
    Callbacks erhalten das Toplevel-Fenster und die txt-Widget-Referenz
    um Inhalt und Titel dynamisch zu aktualisieren.
    """
    top = tk.Toplevel(parent)
    top.title(titel)
    top.geometry("900x420")
    top.minsize(520, 260)
    if callable(WINDOW_REGISTRATION_CALLBACK):
        try:
            WINDOW_REGISTRATION_CALLBACK(top, "Zellinhalt", titel)
        except Exception:
            pass
    if callable(RAHMEN_FRAME_CALLBACK):
        try:
            RAHMEN_FRAME_CALLBACK(top)
        except Exception:
            pass

    frame = tk.Frame(top, padx=12, pady=12)
    frame.pack(fill="both", expand=True)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    txt = tk.Text(frame, wrap="word")
    txt.grid(row=0, column=0, sticky="nsew")

    scrolly = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
    scrolly.grid(row=0, column=1, sticky="ns")
    scrollx = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
    scrollx.grid(row=1, column=0, sticky="ew")

    txt.configure(yscrollcommand=scrolly.set, xscrollcommand=scrollx.set)
    txt.insert("1.0", "" if text is None else str(text))
    txt.configure(state="disabled")

    buttonframe = tk.Frame(frame)
    buttonframe.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def kopieren():
        inhalt = txt.get("1.0", "end").rstrip("\n")
        top.clipboard_clear()
        top.clipboard_append(inhalt)
        top.update_idletasks()

    def inhalt_aktualisieren(neuer_text, neuer_titel=None):
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.insert("1.0", "" if neuer_text is None else str(neuer_text))
        txt.configure(state="disabled")
        if neuer_titel:
            top.title(neuer_titel)

    # Navigation ▲ ▼ links, Kopieren + Schließen rechts
    if callable(nav_hoch) or callable(nav_runter):
        nav_frame = tk.Frame(buttonframe)
        nav_frame.pack(side="left")
        if callable(nav_hoch):
            tk.Button(nav_frame, text="▲", width=4,
                      command=lambda: nav_hoch(inhalt_aktualisieren)).pack(side="left", padx=(0, 2))
        if callable(nav_runter):
            tk.Button(nav_frame, text="▼", width=4,
                      command=lambda: nav_runter(inhalt_aktualisieren)).pack(side="left")

    tk.Button(buttonframe, text="Kopieren", width=12, command=kopieren).pack(side="right")
    tk.Button(buttonframe, text="Schließen", width=12, command=top.destroy).pack(side="right", padx=(0, 8))

    # Smarte Positionierung
    if ziel_x is not None and ziel_y is not None:
        top.update_idletasks()
        fenster_hoehe = top.winfo_reqheight() or 420
        bildschirm_hoehe = top.winfo_screenheight()
        ziel_unten = ziel_y + (ziel_hoehe or 22)
        if ziel_unten + fenster_hoehe + 20 <= bildschirm_hoehe:
            top.geometry(f"+{ziel_x}+{ziel_unten + 4}")
        else:
            top.geometry(f"+{ziel_x}+{max(0, ziel_y - fenster_hoehe - 4)}")

    return top


def gui_csv_spaltenname_aus_kontext(csvdaten):
    if not csvdaten:
        return None

    spalteid = csvdaten.get("kontext_spalte_id") or csvdaten.get("kontextspalteid")
    header = csvdaten.get("header", [])

    if not spalteid:
        return None

    try:
        spaltenindex = int(str(spalteid).replace("#", "")) - 1
    except Exception:
        return None

    if spaltenindex < 0 or spaltenindex >= len(header):
        return None

    return header[spaltenindex]


def gui_csv_zellwert_aus_kontext(csvdaten):
    if not csvdaten:
        return None

    treewidget = csvdaten.get("tree")
    itemid = csvdaten.get("kontext_item_id") or csvdaten.get("kontextitemid")
    spalteid = csvdaten.get("kontext_spalte_id") or csvdaten.get("kontextspalteid")

    if treewidget is None or not itemid or not spalteid:
        return None

    werte = treewidget.item(itemid, "values")

    try:
        spaltenindex = int(str(spalteid).replace("#", "")) - 1
    except Exception:
        return None

    if spaltenindex < 0 or spaltenindex >= len(werte):
        return None

    return werte[spaltenindex]


def gui_csv_standard_rechtsklick_erweitern(
    kontextmenu,
    parent,
    csvfensterid,
    Gcsvfenster,
    refresh_callback=None,
    hinweis_callback=None,
):
    daten = Gcsvfenster.get(csvfensterid)
    if not daten or kontextmenu is None:
        return

    gui_csv_wrap_status_sicherstellen(daten)

    def aktuelle_spalte():
        return gui_csv_spaltenname_aus_kontext(daten)

    def wrap_setzen():
        spaltenname = aktuelle_spalte()
        if not spaltenname:
            messagebox.showwarning("Spaltenumbruch", "Bitte zuerst eine Spalte auswählen.", parent=parent)
            return

        return gui_csv_wrap_dialog_fuer_spalte(
            parent,
            csvfensterid,
            spaltenname,
            Gcsvfenster,
            refresh_callback=refresh_callback,
            hinweis_callback=hinweis_callback,
        )

    def wrap_aufheben():
        spaltenname = aktuelle_spalte()
        if not spaltenname:
            messagebox.showwarning("Spaltenumbruch", "Bitte zuerst eine Spalte auswählen.", parent=parent)
            return

        return gui_csv_wrap_spalte_aufheben(
            csvfensterid,
            spaltenname,
            Gcsvfenster,
            refresh_callback=refresh_callback,
            hinweis_callback=hinweis_callback,
        )

    def wrap_alle_aufheben():
        return gui_csv_wrap_alle_aufheben(
            csvfensterid,
            Gcsvfenster,
            refresh_callback=refresh_callback,
            hinweis_callback=hinweis_callback,
        )

    def zellinhalt_lesen():
        spaltenname = aktuelle_spalte()
        zellwert = gui_csv_zellwert_aus_kontext(daten)

        if spaltenname is None:
            messagebox.showwarning("Zellinhalt", "Bitte zuerst eine Zelle auswählen.", parent=parent)
            return

        gui_csv_zelltext_anzeigen(parent, f"CSV-Zellinhalt - {spaltenname}", zellwert)

    kontextmenu.add_separator()
    kontextmenu.add_command(label="Spaltenumbruch setzen...", command=wrap_setzen)
    kontextmenu.add_command(label="Spaltenumbruch für diese Spalte aufheben", command=wrap_aufheben)
    kontextmenu.add_command(label="Spaltenumbruch komplett aufheben", command=wrap_alle_aufheben)

