import re
import textwrap


def struktur_ebene_ermitteln(text):
    if text is None:
        return 0

    s = str(text).lstrip()
    if not s:
        return 0

    if s.startswith(":::"):
        return 3
    if s.startswith("::"):
        return 2
    if s.startswith(":"):
        return 1

    return 0


def struktur_prefix_entfernen(text):
    if text is None:
        return ""

    s = str(text).strip()
    if not s:
        return ""

    return re.sub(r"^:{1,3}\s*", "", s)


def text_mit_struktur_wrap(text, breite=30, einzug_pro_ebene=2, break_long_words=False):
    if text is None:
        return ""

    rohtext = str(text).strip()
    if not rohtext:
        return ""

    ebene = struktur_ebene_ermitteln(rohtext)
    inhalt = struktur_prefix_entfernen(rohtext)

    if not inhalt:
        return ""

    einzug = " " * (ebene * einzug_pro_ebene)

    wrapper = textwrap.TextWrapper(
        width=max(1, breite),
        initial_indent=einzug,
        subsequent_indent=einzug,
        break_long_words=break_long_words,
        break_on_hyphens=False,
        replace_whitespace=False,
        drop_whitespace=True,
    )

    return wrapper.fill(inhalt)


def csv_anzeigewert_formatieren(
    wert,
    struktur_umbruch_aktiv=False,
    breite=30,
    einzug_pro_ebene=2,
    break_long_words=False,
):
    if wert is None:
        return ""

    text = str(wert)

    if not struktur_umbruch_aktiv:
        return text

    return text_mit_struktur_wrap(
        text,
        breite=breite,
        einzug_pro_ebene=einzug_pro_ebene,
        break_long_words=break_long_words,
    )
