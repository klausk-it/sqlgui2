# =============================================================================
# SqlGui V4.6.51 – User Defined Functions (UDFs) für SQLite
# =============================================================================
#
# Dieses Modul enthält alle SQLite-UDFs als reine Python-Funktionen.
# Jede Funktion kann direkt in Python aufgerufen werden (z. B. zum Testen)
# und wird von sqlite_verbindung_mit_udf_oeffnen() auf der SQLite-Verbindung
# registriert.
#
# Registrierung: udf_alle_registrieren(verbindung)
#
# Verfügbare UDFs:
#   ipv4_to_int(Feld)      – IPv4-Adresse → Integer  (für Bereichssuchen)
#   ip_range_start(Feld)   – Startadresse eines IP-Bereichs
#   ip_range_end(Feld)     – Endadresse eines IP-Bereichs
#   hat_ip(Feld)           – Extrahiert eine IPv4-Adresse aus einem Text
#   hat_netzmaske(Feld)    – Extrahiert eine CIDR-Maske (/0–/32) aus einem Text
# =============================================================================

import re as _re


# ─────────────────────────────────────────────────────────────────────────────
# Interne Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _ipv4_zu_int(ip):
    """Wandelt einen IPv4-String in einen Integer um. Wirft ValueError bei ungültigem Format."""
    teile = str(ip).strip().split(".")
    if len(teile) != 4:
        raise ValueError(f"Kein IPv4-Format: {ip}")
    oktette = [int(t) for t in teile]
    if any(o < 0 or o > 255 for o in oktette):
        raise ValueError(f"Oktet außerhalb 0-255: {ip}")
    return (oktette[0] << 24) | (oktette[1] << 16) | (oktette[2] << 8) | oktette[3]


def _int_zu_ipv4(zahl):
    """Wandelt einen Integer in einen IPv4-String um."""
    return f"{(zahl >> 24) & 0xFF}.{(zahl >> 16) & 0xFF}.{(zahl >> 8) & 0xFF}.{zahl & 0xFF}"


# ─────────────────────────────────────────────────────────────────────────────
# UDF: ipv4_to_int
# ─────────────────────────────────────────────────────────────────────────────

def ipv4_to_int(ip):
    """
    SQLite-UDF: ipv4_to_int(Feld)

    Wandelt eine IPv4-Adresse in eine vorzeichenlose Ganzzahl um.
    Ermöglicht numerische Bereichssuchen (BETWEEN, <, >).

    Gibt NULL zurück bei leerem oder ungültigem Wert.

    Beispiele:
        SELECT ipv4_to_int('192.168.1.1')
        -- Ergebnis: 3232235777

        SELECT ipv4_to_int(ClientIps.IPAddressNumber) AS IPv4 FROM ClientIps

        SELECT ipv4_to_int(ClientIps.IP_Addresses0) AS IP_Integer FROM ClientIps

        SELECT * FROM Hosts
         WHERE ipv4_to_int(IPAdresse) BETWEEN ipv4_to_int('10.0.0.0')
                                           AND ipv4_to_int('10.255.255.255')
    """
    if ip is None or str(ip).strip() == "":
        return None
    try:
        return _ipv4_zu_int(ip)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ip_range_aufteilen  (Python-Hilfsfunktion, auch direkt verwendbar)
# ─────────────────────────────────────────────────────────────────────────────

def ip_range_aufteilen(range_text):
    """
    Zerlegt einen IP-Bereich in Start- und Endadresse.

    Unterstützte Formate:
        '10.236.245.57-10.236.245.58'  →  start='10.236.245.57', end='10.236.245.58'
        '10.236.245.57-58'             →  start='10.236.245.57', end='10.236.245.58'
        '10.236.245.57'                →  start=end='10.236.245.57'

    Rückgabe-Dict bei Erfolg:
        {
          'ok':        True,
          'start':     '10.236.245.57',
          'end':       '10.236.245.58',
          'start_int': 182184249,
          'end_int':   182184250,
          'fehler':    None
        }
    Rückgabe-Dict bei Fehler:
        {'ok': False, 'fehler': '<Fehlermeldung>'}
    """
    if not range_text:
        return {"ok": False, "fehler": "Leerer Eingabewert"}

    text = str(range_text).strip()

    try:
        if "-" not in text:
            start_int = _ipv4_zu_int(text)
            return {
                "ok": True, "start": text, "end": text,
                "start_int": start_int, "end_int": start_int, "fehler": None,
            }

        teile     = text.split("-", 1)
        start_ip  = teile[0].strip()
        end_teil  = teile[1].strip()
        start_int = _ipv4_zu_int(start_ip)

        # Kurzes Format: nur letztes Oktet angegeben (z. B. "10.236.245.57-58")
        if "." not in end_teil:
            basis  = ".".join(start_ip.split(".")[:3])
            end_ip = f"{basis}.{end_teil}"
        else:
            end_ip = end_teil

        end_int = _ipv4_zu_int(end_ip)

        if start_int > end_int:
            return {"ok": False, "fehler": f"Startadresse {start_ip} ist größer als Endadresse {end_ip}"}

        return {
            "ok": True, "start": start_ip, "end": end_ip,
            "start_int": start_int, "end_int": end_int, "fehler": None,
        }

    except Exception as e:
        return {"ok": False, "fehler": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# UDF: ip_range_start
# ─────────────────────────────────────────────────────────────────────────────

def ip_range_aufteilen_sql(text):
    """
    SQLite-UDF: ip_range_aufteilen(IP_Range)

    Gibt Start- und Endadresse eines IP-Bereichs als lesbaren Text zurück.
    Bei ungültigem Bereich wird eine ERROR-Meldung zurückgegeben.

    Rückgabe:
        'Start: 10.0.0.1 | Ende: 10.0.0.254'  – bei gültigem Bereich
        'ERROR: ...'                            – bei Fehler

    Beispiele:
        SELECT ip_range_aufteilen('10.0.0.1-10.0.0.254')
        -- Ergebnis: 'Start: 10.0.0.1 | Ende: 10.0.0.254'

        SELECT ip_range_aufteilen('172.23.122.1-172.21.123.254')
        -- Ergebnis: 'ERROR: Startadresse 172.23.122.1 ist größer als Endadresse 172.21.123.254'
    """
    if text is None or str(text).strip() == "":
        return "ERROR [Eingabe]: IP-Range fehlt"
    ergebnis = ip_range_aufteilen(text)
    if ergebnis.get("ok"):
        if "-" in str(text).strip():
            if ergebnis["start_int"] == ergebnis["end_int"]:
                return f"Start-Ende identisch    {ergebnis['start']}"
            return f"Start-Ende    {ergebnis['start']} - {ergebnis['end']}"
        else:
            return f"Start/Einzeladresse  {ergebnis['start']}  (ohne Maske nicht eindeutig bestimmbar)"
    return f"ERROR [IP-Range]: {ergebnis.get('fehler', 'Unbekannter Fehler')}"


def ip_range_start(text):
    """
    SQLite-UDF: ip_range_start(Feld)

    Gibt die Startadresse eines IP-Bereichs zurück.
    Gibt NULL zurück bei leerem oder ungültigem Wert.

    Beispiele:
        SELECT ip_range_start('10.0.0.5-10.0.0.20')
        -- Ergebnis: '10.0.0.5'

        SELECT ip_range_start(IPRange) AS IP_Start FROM Netzwerke
    """
    if text is None or str(text).strip() == "":
        return None
    ergebnis = ip_range_aufteilen(text)
    return ergebnis.get("start") if ergebnis and ergebnis.get("ok") else None


# ─────────────────────────────────────────────────────────────────────────────
# UDF: ip_range_end
# ─────────────────────────────────────────────────────────────────────────────

def ip_range_end(text):
    """
    SQLite-UDF: ip_range_end(Feld)

    Gibt die Endadresse eines IP-Bereichs zurück.
    Gibt NULL zurück bei leerem oder ungültigem Wert.

    Beispiele:
        SELECT ip_range_end('10.0.0.5-10.0.0.20')
        -- Ergebnis: '10.0.0.20'

        SELECT ip_range_end(IPRange) AS IP_Ende FROM Netzwerke
    """
    if text is None or str(text).strip() == "":
        return None
    ergebnis = ip_range_aufteilen(text)
    return ergebnis.get("end") if ergebnis and ergebnis.get("ok") else None


# ─────────────────────────────────────────────────────────────────────────────
# UDF: hat_ip
# ─────────────────────────────────────────────────────────────────────────────

_IP_REGEX_VOLL = _re.compile(r'(?<![0-9])(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?![0-9])')
_IP_REGEX_DREI = _re.compile(r'(?<![0-9])(\d{1,3}\.\d{1,3}\.\d{1,3})(?!\.\d)(?![0-9])')


def hat_ip(text):
    """
    SQLite-UDF: hat_ip(Feld)

    Durchsucht einen Text nach einer IPv4-Adresse und gibt die erste
    gefundene Adresse zurück. Gibt NULL zurück wenn keine IP gefunden wurde.

    Nützlich zum Filtern oder Extrahieren von IPs aus gemischten Textfeldern.

    Beispiele:
        SELECT hat_ip('Host: 192.168.1.5 verbunden')
        -- Ergebnis: '192.168.1.5'

        SELECT * FROM Logs WHERE hat_ip(Message) IS NOT NULL

        SELECT hat_ip(Boundary.Boundary.Value) AS GefundeneIP
          FROM Boundary
         WHERE hat_ip(Boundary.Boundary.Value) IS NOT NULL
    """
    if text is None:
        return None
    s = str(text)
    m = _IP_REGEX_VOLL.search(s)
    if m:
        return m.group(1)
    # Fallback: 3 Oktette (unvollständige Adresse)
    m = _IP_REGEX_DREI.search(s)
    if m:
        return m.group(1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# UDF: hat_netzmaske
# ─────────────────────────────────────────────────────────────────────────────

_MASKE_REGEX = _re.compile(r'/(\d{1,2})(?!\d)(?!\.\d)')


def hat_netzmaske(text):
    """
    SQLite-UDF: hat_netzmaske(Feld)

    Sucht in einem Text nach einer CIDR-Netzmaske (/0 bis /32) und gibt sie zurück.
    Gibt NULL zurück wenn keine Maske gefunden wurde.
    Bei mehreren Treffern wird die letzte Maske zurückgegeben.

    Beispiele:
        SELECT hat_netzmaske('10.0.0.0/24 Subnetz')
        -- Ergebnis: '/24'

        SELECT * FROM Boundary WHERE hat_netzmaske(Value) IS NOT NULL

        SELECT hat_netzmaske(Boundary.Boundary.Value) AS Maske
          FROM Boundary
         WHERE hat_netzmaske(Boundary.Boundary.Value) IS NOT NULL
    """
    if text is None:
        return None
    treffer = list(_MASKE_REGEX.finditer(str(text)))
    if not treffer:
        return None
    m = treffer[-1]  # letztes Vorkommen
    if 0 <= int(m.group(1)) <= 32:
        return "/" + m.group(1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# UDF: ip_in_range_pruefen
# ─────────────────────────────────────────────────────────────────────────────

def ip_in_range_pruefen(ip, maske, ip_range):
    """
    SQLite-UDF: ip_in_range_pruefen(ip, maske, ip_range)

    Prüft ob eine IP-Adresse oder ein IP-Netz vollständig
    innerhalb eines IP-Bereichs liegt.

    Parameter:
        ip       – IP-Adresse, z.B. '192.168.240.0' oder '192.168.240.0/21'
        maske    – Netzmaske, z.B. '/21' oder '21' oder None/'' wenn in ip enthalten
        ip_range – IP-Range, z.B. '192.168.240.1-192.168.247.254'

    Rückgabe:
        'OK'           – alles liegt in der IP-Range
        'FEHLER: ...'  – was nicht passt oder fehlt

    Beispiele:
        SELECT ip_in_range_pruefen('192.168.240.0', '/21', '192.168.240.0-192.168.247.255')
        -- Ergebnis: 'OK'

        SELECT ip_in_range_pruefen('192.168.240.0/21', NULL, '192.168.240.0-192.168.247.255')
        -- Ergebnis: 'OK'

        SELECT ip_in_range_pruefen('192.168.51.1', NULL, '192.168.51.1-192.168.51.254')
        -- Ergebnis: 'OK'

        SELECT ip_in_range_pruefen('192.168.240.0', '/21', '192.168.241.0-192.168.247.255')
        -- Ergebnis: 'ERROR [Prüfung]: Start 192.168.240.0 liegt nicht in IP-Range 192.168.241.0-192.168.247.255'
    """

    # ── Eingaben prüfen ──────────────────────────────────────────────────────

    if ip is None or str(ip).strip() == "":
        if ip_range is not None and str(ip_range).strip() != "":
            range_info = ip_range_aufteilen(ip_range)
            if range_info.get("ok"):
                if "-" in str(ip_range).strip():
                    if range_info["start_int"] == range_info["end_int"]:
                        return (f"Hinweis [Eingabe]: IP-Adresse fehlt  |  "
                                f"Start-Ende identisch    {range_info['start']} – kein Vergleich möglich")
                    else:
                        return (f"Hinweis [Eingabe]: IP-Adresse fehlt  |  "
                                f"Start-Ende    {range_info['start']} - {range_info['end']} – kein Vergleich möglich")
                else:
                    return (f"Hinweis [Eingabe]: IP-Adresse fehlt  |  "
                            f"Start    {range_info['start']} – kein Vergleich möglich")
            else:
                return (f"ERROR [Eingabe]: IP-Adresse fehlt  |  "
                        f"ERROR [IP-Range]: {range_info.get('fehler', 'Unbekannter Fehler')}")
        return "ERROR [Eingabe]: IP-Adresse fehlt"

    if ip_range is None or str(ip_range).strip() == "":
        return "ERROR [Eingabe]: IP-Range fehlt"

    ip_str   = str(ip).strip()
    mask_str = str(maske).strip() if maske is not None else ""

    # ── Netzmaske aus IP extrahieren falls nötig ─────────────────────────────

    if mask_str == "" or mask_str == "None":
        if "/" in ip_str:
            teile    = ip_str.split("/", 1)
            ip_str   = teile[0].strip()
            mask_str = "/" + teile[1].strip()
        else:
            mask_str = None

    # ── Netzmaske auswerten ──────────────────────────────────────────────────

    if mask_str is not None:
        try:
            prefix = int(str(mask_str).lstrip("/"))
        except ValueError:
            return f"ERROR [Netzmaske]: nicht lesbar – '{mask_str}' ist keine Zahl"

        if not (0 <= prefix <= 32):
            return f"ERROR [Netzmaske]: /{prefix} ungültig – erlaubt ist /0 bis /32"
    else:
        prefix = None

    # ── IP-Adresse prüfen ────────────────────────────────────────────────────

    teile = ip_str.split(".")
    if len(teile) != 4:
        fehlend     = 4 - len(teile)
        oktt_wort   = "Oktett" if fehlend == 1 else "Oktette"
        basis       = f"IP-Adresse '{ip_str}' fehlt {fehlend} {oktt_wort}"
        # Annahme: fehlende Oktette als .0 ergänzen und Range prüfen
        annahme_ip  = ip_str + ".0" * fehlend
        range_info  = ip_range_aufteilen(ip_range) if ip_range and str(ip_range).strip() else {"ok": False}
        if not range_info.get("ok"):
            return f"ERROR [Oktett]: {basis} - IP-Range ungültig ({ip_range})"
        annahme_int  = sum(int(o) << (8 * (3 - i)) for i, o in enumerate(annahme_ip.split(".")))
        range_bez    = f"({range_info['start']} - {range_info['end']})" if "-" in str(ip_range).strip() else f"({range_info['start']})"
        prefix_str   = f"/{prefix}" if prefix is not None else ""
        annahme_bez  = f"{annahme_ip}{prefix_str}"
        # Wenn Maske bekannt: vollständige Netzprüfung statt Punkt-Check
        if prefix is not None:
            mask_int_okt   = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
            netz_s_okt     = annahme_int & mask_int_okt
            netz_e_okt     = netz_s_okt | (~mask_int_okt & 0xFFFFFFFF)
            pruef_s        = netz_s_okt + 1 if prefix < 31 else netz_s_okt
            pruef_e        = netz_e_okt - 1 if prefix < 31 else netz_e_okt
            rs, re         = range_info["start_int"], range_info["end_int"]
            if rs >= pruef_s and re <= pruef_e:
                range_hosts = re - rs + 1
                netz_hosts  = pruef_e - pruef_s + 1
                return (f"Hinweis [Oktett]: {basis}  |  "
                        f"Annahme .0 → {annahme_bez} – Range liegt im Netz, "
                        f"umfasst nur {range_hosts} von {netz_hosts} nutzbaren Hosts "
                        f"({ip_range})")
        # Kein Prefix: engsten passenden Prefix suchen
        if prefix is None and "-" in str(ip_range).strip():
            rs, re = range_info["start_int"], range_info["end_int"]
            passender_prefix = None
            pass_pruef_s = pass_pruef_e = 0
            for p in range(32, 0, -1):
                mask_p   = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
                netz_s_p = annahme_int & mask_p
                if netz_s_p != annahme_int:
                    continue  # annahme_ip ist keine gültige Netzadresse für /{p}
                netz_e_p    = netz_s_p | (~mask_p & 0xFFFFFFFF)
                pruef_s_p   = netz_s_p + 1 if p < 31 else netz_s_p
                pruef_e_p   = netz_e_p - 1 if p < 31 else netz_e_p
                if rs >= pruef_s_p and re <= pruef_e_p:
                    passender_prefix = p
                    pass_pruef_s, pass_pruef_e = pruef_s_p, pruef_e_p
                    break
            if passender_prefix is not None:
                range_hosts = re - rs + 1
                netz_hosts  = pass_pruef_e - pass_pruef_s + 1
                return (f"Hinweis [Oktett]: {basis}  |  "
                        f"Annahme .0 → {annahme_ip} – Range ({ip_range}) "
                        f"passt zu /{passender_prefix} "
                        f"({range_hosts} von {netz_hosts} nutzbaren Hosts)")
        # Einfacher Punkt-Check als Fallback
        in_range     = range_info["start_int"] <= annahme_int <= range_info["end_int"]
        if in_range:
            return (f"Hinweis [Oktett]: {basis} - "
                    f"Annahme .0 → {annahme_bez} liegt in IP-Range {range_bez}")
        else:
            return (f"ERROR [Oktett]: {basis} - "
                    f"Annahme .0 → {annahme_bez} liegt NICHT in IP-Range {range_bez}")

    for t in teile:
        if not t.isdigit():
            return f"ERROR [Oktett]: '{t}' in '{ip_str}' ist keine Zahl"
        if not (0 <= int(t) <= 255):
            basis_okt  = f"Hinweis [Oktett]: {t} in '{ip_str}' liegt außerhalb 0–255"
            ri         = ip_range_aufteilen(ip_range) if ip_range and str(ip_range).strip() else {"ok": False}
            if ri.get("ok"):
                if "-" in str(ip_range).strip():
                    return f"{basis_okt}  |  Range {ip_range} zulässig – kein Vergleich möglich"
                else:
                    return f"{basis_okt}  |  Start    {ri['start']} – kein Vergleich möglich"
            return f"ERROR [Oktett]: {t} in '{ip_str}' liegt außerhalb 0–255"

    # ── IP-Range auswerten ───────────────────────────────────────────────────

    range_info  = ip_range_aufteilen(ip_range)
    if not range_info.get("ok"):
        prefix_str  = f"/{prefix}" if prefix is not None else ""
        vorgabe_bez = f"{ip_str}{prefix_str}"
        return f"ERROR [IP-Range]: {range_info.get('fehler')} – Vorgabe {vorgabe_bez} nicht prüfbar"

    range_start = range_info["start_int"]
    range_end   = range_info["end_int"]

    # ── IP-Integer berechnen ─────────────────────────────────────────────────

    try:
        ip_int = _ipv4_zu_int(ip_str)
    except Exception as e:
        return f"ERROR [Eingabe]: {e}"

    # ── Netz-Ende berechnen (nur wenn Maske vorhanden) ───────────────────────

    if prefix is not None:
        mask_int       = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        netz_start_int = ip_int & mask_int
        netz_end_int   = netz_start_int | (~mask_int & 0xFFFFFFFF)
        if prefix < 31:
            # Netzadresse und Broadcast ausschließen – nur nutzbare Hosts prüfen
            pruef_start_int = netz_start_int + 1
            pruef_end_int   = netz_end_int   - 1
        else:
            # /31 und /32: alle Adressen sind nutzbar
            pruef_start_int = netz_start_int
            pruef_end_int   = netz_end_int
    else:
        netz_start_int  = ip_int
        netz_end_int    = ip_int
        pruef_start_int = ip_int
        pruef_end_int   = ip_int

    pruef_start = _int_zu_ipv4(pruef_start_int)
    pruef_end   = _int_zu_ipv4(pruef_end_int)

    # ── Prüfung ──────────────────────────────────────────────────────────────

    start_ok = pruef_start_int >= range_start
    end_ok   = pruef_end_int   <= range_end

    if start_ok and end_ok:
        host_anzahl  = range_end - range_start + 1
        if host_anzahl > 65534:
            netz_groesse  = pruef_end_int - pruef_start_int + 1
            range_str     = f"{host_anzahl:,}".replace(",", ".")
            netz_str      = f"{netz_groesse:,}".replace(",", ".")
            netz_wort     = "Host" if netz_groesse == 1 else "Hosts"
            prefix_str    = f" /{prefix}" if prefix is not None else ""
            if netz_groesse == host_anzahl:
                return (f"Hinweis [Vorgabe]: IP-Range sehr groß ({range_str} Hosts)"
                        f" – konform mit Vorgabe{prefix_str}")
            return (f"Hinweis [Vorgabe]: IP-Range sehr groß ({range_str} Hosts)"
                    f" – Vorgabe{prefix_str} umfasst nur {netz_str} {netz_wort} – unüblich, aber zulässig")
        netz_ip_str = _int_zu_ipv4(netz_start_int)
        prefix_bez  = f"{netz_ip_str}/{prefix}" if prefix is not None else netz_ip_str
        netz_bez    = f"des {prefix_bez}-Netzes " if prefix is not None else ""
        return (f"OK – Nutzbare Hosts {netz_bez}"
                f"({pruef_start} – {pruef_end}) liegen innerhalb "
                f"der IP-Range ({ip_range}) (SCCM-konform)")

    # Kein Prefix: engsten passenden Prefix für vollständige IP suchen
    if prefix is None and "-" in str(ip_range).strip():
        rs, re = range_start, range_end
        passender_prefix = None
        pass_pruef_s = pass_pruef_e = 0
        for p in range(32, 0, -1):
            mask_p   = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
            netz_s_p = ip_int & mask_p
            if netz_s_p != ip_int:
                continue  # ip_int ist keine gültige Netzadresse für /{p}
            netz_e_p    = netz_s_p | (~mask_p & 0xFFFFFFFF)
            pruef_s_p   = netz_s_p + 1 if p < 31 else netz_s_p
            pruef_e_p   = netz_e_p - 1 if p < 31 else netz_e_p
            if rs >= pruef_s_p and re <= pruef_e_p:
                passender_prefix = p
                pass_pruef_s, pass_pruef_e = pruef_s_p, pruef_e_p
                break
        if passender_prefix is not None:
            range_hosts = re - rs + 1
            netz_hosts  = pass_pruef_e - pass_pruef_s + 1
            nutzbar_s   = _int_zu_ipv4(pass_pruef_s)
            nutzbar_e   = _int_zu_ipv4(pass_pruef_e)
            if range_hosts == netz_hosts:
                return (f"Hinweis [Prüfung]: {ip_str} ohne Maske – passt zu /{passender_prefix}: "
                        f"Nutzbare Hosts ({nutzbar_s} – {nutzbar_e}) "
                        f"decken IP-Range ({ip_range}) vollständig")
            return (f"Hinweis [Prüfung]: {ip_str} ohne Maske – passt zu /{passender_prefix}: "
                    f"Range liegt im Netz, umfasst nur {range_hosts} von {netz_hosts} "
                    f"nutzbaren Hosts ({ip_range})")

        # Prefix-Suche mit IP schlug fehl → Netz-Mismatch: Range-Netz ermitteln
        rng_s   = range_info["start_int"]
        rng_e   = range_info["end_int"]
        range_prefix = None
        rng_netz_int = rng_pruef_s = rng_pruef_e = 0
        for p in range(32, 0, -1):
            mask_p   = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
            netz_s_p = rng_s & mask_p
            netz_e_p = netz_s_p | (~mask_p & 0xFFFFFFFF)
            ps       = netz_s_p + 1 if p < 31 else netz_s_p
            pe       = netz_e_p - 1 if p < 31 else netz_e_p
            if rng_s >= ps and rng_e <= pe:
                range_prefix = p
                rng_netz_int, rng_pruef_s, rng_pruef_e = netz_s_p, ps, pe
                break

        # Abweichende Oktette zwischen IP und Netzadresse der Range
        ip_okt   = [int(x) for x in ip_str.split(".")]
        if range_prefix is not None:
            ref_okt = [int(x) for x in _int_zu_ipv4(rng_netz_int).split(".")]
        else:
            ref_okt = [int(x) for x in range_info["start"].split(".")]
        abweich = [(i + 1, ip_okt[i], ref_okt[i]) for i in range(4) if ip_okt[i] != ref_okt[i]]
        abweich_str = (", ".join(f"Oktett {nr}: {a} ≠ {b}" for nr, a, b in abweich)
                       if abweich else "alle Oktette abweichend")

        if range_prefix is not None:
            rng_netz_ip = _int_zu_ipv4(rng_netz_int)
            rng_nutz_s  = _int_zu_ipv4(rng_pruef_s)
            rng_nutz_e  = _int_zu_ipv4(rng_pruef_e)
            rng_hosts   = rng_e - rng_s + 1
            netz_hosts  = rng_pruef_e - rng_pruef_s + 1
            if rng_hosts == netz_hosts:
                range_info_str = (f"{rng_netz_ip}/{range_prefix} – alle {netz_hosts} nutzbaren Hosts "
                                  f"({rng_nutz_s}–{rng_nutz_e})")
            else:
                range_info_str = (f"{rng_netz_ip}/{range_prefix} – {rng_hosts} von {netz_hosts} nutzbaren Hosts "
                                  f"({rng_nutz_s}–{rng_nutz_e})")
            return (f"Hinweis [Prüfung]: {ip_str} liegt nicht in Range {ip_range}"
                    f"  |  Netz-Mismatch ({abweich_str})"
                    f"  |  Range gehört zu {range_info_str}")
        else:
            return (f"Hinweis [Prüfung]: {ip_str} liegt nicht in Range {ip_range}"
                    f"  |  Netz-Mismatch ({abweich_str})")

    # Einzeladresse als Range + Maske: alle Spezialfälle
    if prefix is not None and "-" not in str(ip_range).strip():
        netz_ip      = _int_zu_ipv4(netz_start_int)
        prefix_bez   = f"{ip_str}/{prefix}"
        netz_hosts   = pruef_end_int - pruef_start_int + 1
        netz_hosts_s = f"{netz_hosts:,}".replace(",", ".")
        nutzbar_s    = _int_zu_ipv4(pruef_start_int)
        nutzbar_e    = _int_zu_ipv4(pruef_end_int)

        maske_erkl = f"/{prefix}-Maske auf {ip_str} ergibt Netz {netz_ip}/{prefix}"
        if range_start == netz_start_int:
            # Range ist genau die Netzadresse → nicht nutzbar
            return (f"ERROR [Netzadresse]: {prefix_bez} – IP-Range ({ip_range}) ist die Netzadresse "
                    f"des /{prefix}-Netzes, keine nutzbare Host-Adresse – nicht nutzbar "
                    f"({maske_erkl}: {nutzbar_s}–{nutzbar_e})")
        if range_start == netz_end_int:
            # Range ist genau die Broadcast-Adresse → nicht nutzbar
            return (f"ERROR [Broadcast]: {prefix_bez} – IP-Range ({ip_range}) ist die Broadcast-Adresse "
                    f"des /{prefix}-Netzes, keine nutzbare Host-Adresse – nicht nutzbar "
                    f"({maske_erkl}: {nutzbar_s}–{nutzbar_e})")
        if pruef_start_int <= range_start <= pruef_end_int:
            # Range-IP liegt im Netz, ist aber nur ein einzelner Host
            return (f"Hinweis [Einzeladresse]: {prefix_bez} – Range enthält nur einzelne IP ({ip_range}), "
                    f"kein Netzbereich – {maske_erkl} "
                    f"mit {netz_hosts_s} nutzbaren Hosts ({nutzbar_s}–{nutzbar_e})")
        # Range-IP liegt komplett außerhalb des Netzes
        return (f"ERROR [Netz-Mismatch]: {prefix_bez} – Range-IP {ip_range} liegt nicht im Netz – "
                f"{maske_erkl} ({nutzbar_s}–{nutzbar_e})")

    if not start_ok and not end_ok:
        return (f"ERROR [Prüfung]: Start {pruef_start} und Ende {pruef_end} "
                f"liegen nicht in IP-Range {ip_range}")

    if not start_ok:
        return f"ERROR [Prüfung]: Start {pruef_start} liegt nicht in IP-Range {ip_range}"

    return f"ERROR [Prüfung]: Ende {pruef_end} liegt nicht in IP-Range {ip_range}"


# ─────────────────────────────────────────────────────────────────────────────
# Registrierung aller UDFs auf einer SQLite-Verbindung
# ─────────────────────────────────────────────────────────────────────────────

def udf_alle_registrieren(verbindung):
    """
    Registriert alle UDFs aus diesem Modul auf der übergebenen SQLite-Verbindung.

    Wird automatisch von sqlite_verbindung_mit_udf_oeffnen() aufgerufen.
    Kann bei Bedarf auch manuell auf einer bestehenden Verbindung aufgerufen werden.

    Parameter:
        verbindung – sqlite3.Connection-Objekt

    Rückgabe:
        verbindung (dasselbe Objekt, für Method-Chaining)

    Hinweis: Das dritte Argument von create_function() gibt die Anzahl der
    SQLite-Argumente an. -1 bedeutet variable Argumentanzahl (nicht verwendet).
    """
    for name, n_args, func in [
        ("ipv4_to_int",         1, ipv4_to_int),
        ("ip_range_aufteilen",  1, ip_range_aufteilen_sql),
        ("ip_range_start",      1, ip_range_start),
        ("ip_range_end",        1, ip_range_end),
        ("hat_ip",              1, hat_ip),
        ("hat_netzmaske",       1, hat_netzmaske),
        ("ip_in_range_pruefen", 3, ip_in_range_pruefen),
    ]:
        try:
            verbindung.create_function(name, n_args, func)
        except Exception:
            pass
    return verbindung
