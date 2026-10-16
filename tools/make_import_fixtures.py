#!/usr/bin/env python3
"""Génère les bases de test de l'import (vrai SQLite, via Python).

Ces fichiers servent de « témoins » : ils reproduisent les schémas réels de
Chromium (`History`) et de Firefox (`places.sqlite`), y compris les cas
difficiles — beaucoup de lignes (pages intérieures), titres très longs (pages
de débordement), lignes supprimées (liste des pages libres), colonnes dans un
ordre inhabituel.

    python3 tools/make_import_fixtures.py
"""
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "fixtures"

CHROME_EPOCH_OFFSET = 11_644_473_600  # secondes entre 1601-01-01 et 1970-01-01


def chrome_us(unix_seconds: int) -> int:
    return (unix_seconds + CHROME_EPOCH_OFFSET) * 1_000_000


def make_chrome_history(path: pathlib.Path, rows: int = 400) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    # Schéma de Chromium (simplifié mais dans l'ordre réel).
    cur.execute(
        """CREATE TABLE urls(id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR,
           visit_count INTEGER DEFAULT 0 NOT NULL, typed_count INTEGER DEFAULT 0 NOT NULL,
           last_visit_time INTEGER NOT NULL, hidden INTEGER DEFAULT 0 NOT NULL)"""
    )
    cur.execute(
        """CREATE TABLE visits(id INTEGER PRIMARY KEY, url INTEGER NOT NULL,
           visit_time INTEGER NOT NULL, from_visit INTEGER)"""
    )
    cur.execute("CREATE INDEX urls_url_index ON urls(url)")

    data = []
    for i in range(rows):
        url = f"https://exemple-{i}.fr/page/{i}?q=test"
        ts = chrome_us(1_700_000_000 + i * 60)
        data.append((None, url, f"Page numéro {i}", i % 7, i % 3, ts, 0))
    # Titre très long : force une chaîne de pages de débordement.
    data.append((
        None,
        "https://tres-long.example.org/",
        "Titre interminable " * 400,
        1, 0, chrome_us(1_700_500_000), 0,
    ))
    # URL très longue également.
    data.append((
        None,
        "https://long-url.example.org/" + "segment/" * 900,
        "URL très longue",
        1, 0, chrome_us(1_700_600_000), 0,
    ))
    cur.executemany("INSERT INTO urls VALUES (?,?,?,?,?,?,?)", data)
    cur.executemany(
        "INSERT INTO visits VALUES (?,?,?,?)",
        [(i, i, chrome_us(1_700_000_000 + i * 60), 0) for i in range(1, 40)],
    )
    # Une ligne supprimée laisse une zone libre dans la page : le lecteur doit
    # l'ignorer proprement.
    cur.execute("DELETE FROM urls WHERE id IN (SELECT id FROM urls LIMIT 5)")
    con.commit()
    con.close()


def make_chrome_history_shuffled(path: pathlib.Path) -> None:
    """Même contenu, mais colonnes dans un ordre volontairement décalé."""
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE urls(last_visit_time INTEGER NOT NULL, hidden INTEGER DEFAULT 0,
           visit_count INTEGER DEFAULT 0, id INTEGER PRIMARY KEY, title VARCHAR,
           typed_count INTEGER DEFAULT 0, url VARCHAR NOT NULL)"""
    )
    cur.executemany(
        "INSERT INTO urls VALUES (?,?,?,?,?,?,?)",
        [
            (chrome_us(1_700_000_000), 0, 1, 1, "Alpha", 0, "https://alpha.fr/"),
            (chrome_us(1_700_000_100), 0, 2, 2, "Beta", 0, "https://beta.fr/"),
        ],
    )
    con.commit()
    con.close()


def make_firefox_places(path: pathlib.Path) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE moz_places(id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR,
           rev_host LONGVARCHAR, visit_count INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0 NOT NULL,
           typed INTEGER NOT NULL DEFAULT 0, frecency INTEGER, last_visit_date INTEGER,
           guid TEXT, foreign_count INTEGER DEFAULT 0 NOT NULL, url_hash INTEGER DEFAULT 0 NOT NULL)"""
    )
    cur.execute("CREATE TABLE moz_bookmarks(id INTEGER PRIMARY KEY, fk INTEGER, title LONGVARCHAR)")
    rows = [
        (1, "https://www.mozilla.org/fr/", "Mozilla France", 5, 0, 0, 100, 1_700_000_000_000_000, "abc"),
        (2, "https://addons.mozilla.org/", "Modules Firefox", 3, 0, 0, 90, 1_700_000_500_000_000, "def"),
        (3, "place:sort=8&maxResults=10", "Les plus visités", 1, 0, 0, 80, None, "ghi"),
    ]
    cur.executemany(
        "INSERT INTO moz_places VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (r[0], r[1], r[2], "", r[3], r[4], r[5], r[6], r[7], r[8], 0, 0)
            for r in rows
        ],
    )
    con.commit()
    con.close()


def make_bookmarks_html(path: pathlib.Path) -> None:
    path.write_text(
        """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Favoris</TITLE>
<H1>Favoris</H1>
<DL><p>
    <DT><H3 ADD_DATE="1700000000">Développement</H3>
    <DL><p>
        <DT><A HREF="https://doc.rust-lang.org/book/" ADD_DATE="1700000001">Le livre Rust</A>
        <DT><A HREF="https://crates.io/" ADD_DATE="1700000002">crates.io</A>
        <DT><A HREF="https://github.com/PyO3/pyo3" ADD_DATE="1700000003">PyO3 &amp; Python</A>
    </DL><p>
    <DT><A HREF="https://www.ecosia.org/" ADD_DATE="1700000004">Ecosia</A>
    <DT><A HREF="https://fr.wikipedia.org/wiki/Navigateur_web">Wikip&#233;dia</A>
</DL><p>
""",
        encoding="utf-8",
    )


def make_chromium_bookmarks(path: pathlib.Path) -> None:
    payload = {
        "roots": {
            "bookmark_bar": {
                "type": "folder",
                "name": "Barre",
                "children": [
                    {"type": "url", "name": "Brave Search", "url": "https://search.brave.com/"},
                    {
                        "type": "folder",
                        "name": "Travail",
                        "children": [
                            {"type": "url", "name": "Notion", "url": "https://www.notion.so/"},
                            {"type": "url", "name": "Figma", "url": "https://www.figma.com/"},
                        ],
                    },
                ],
            },
            "other": {
                "type": "folder",
                "name": "Autres",
                "children": [
                    {"type": "url", "name": "", "url": "https://example.org/"},
                ],
            },
            "synced": {"type": "folder", "name": "Appareils", "children": []},
        },
        "version": 1,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_chrome_history(OUT / "chrome-history.sqlite")
    make_chrome_history_shuffled(OUT / "chrome-history-colonnes-melangees.sqlite")
    make_firefox_places(OUT / "firefox-places.sqlite")
    make_bookmarks_html(OUT / "favoris-export.html")
    make_chromium_bookmarks(OUT / "Bookmarks")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name:44s} {f.stat().st_size:>9,} octets")
    print("\nFixtures écrites dans tools/fixtures/")


if __name__ == "__main__":
    main()
