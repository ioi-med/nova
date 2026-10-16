//! Lecteur SQLite minimal, en **lecture seule**.
//!
//! Pourquoi ne pas utiliser une bibliothèque ? Importer l'historique d'un autre
//! navigateur demande de lire quelques colonnes d'une seule table : embarquer
//! SQLite entier (plusieurs centaines de kilo-octets de code C) pour cela serait
//! disproportionné. Ce module lit donc le format de fichier directement, sans
//! aucune dépendance.
//!
//! Ce qui est implémenté (suffisant pour `History` de Chromium et
//! `places.sqlite` de Firefox, tous deux en UTF-8 sans index nécessaire) :
//!
//! * en-tête du fichier (taille de page, espace réservé, encodage) ;
//! * parcours des arbres B « table » : pages intérieures et pages feuilles ;
//! * décodage des enregistrements (varints + types de série) ;
//! * chaînes de pages de débordement (les titres longs y sont stockés).
//!
//! Ce qui n'est **pas** implémenté, volontairement : écriture, index, journaux
//! `-wal`/`-journal` (le fichier principal est lu tel quel), tables virtuelles.
//! Toute anomalie de structure interrompt la lecture sans paniquer : on renvoie
//! ce qui a pu être lu.

use std::collections::HashSet;
use std::path::Path;

/// Valeur d'une colonne SQLite.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Int(i64),
    Real(f64),
    Text(String),
    Blob(Vec<u8>),
}

/// Table SQLite : page racine et colonnes dans l'ordre de déclaration.
#[derive(Debug, Clone)]
pub struct Table {
    pub root: u32,
    pub columns: Vec<String>,
}

impl Table {
    /// Position d'une colonne, insensible à la casse.
    pub fn index_of(&self, name: &str) -> Option<usize> {
        self.columns
            .iter()
            .position(|c| c.eq_ignore_ascii_case(name))
    }
}

/// Extrait les noms de colonnes d'un `CREATE TABLE`. Les contraintes de table
/// (`PRIMARY KEY`, `UNIQUE`, `CHECK`, `FOREIGN KEY`, `CONSTRAINT`) ne sont pas
/// des colonnes : elles sont ignorées, tout comme les séparateurs imbriqués.
fn parse_columns(sql: &str) -> Vec<String> {
    let mut out = Vec::new();
    let Some(open) = sql.find('(') else { return out };
    let mut depth = 0usize;
    let mut clause = String::new();
    for c in sql[open..].chars() {
        match c {
            '(' => {
                depth += 1;
                if depth == 1 {
                    continue;
                }
                clause.push(c);
            }
            ')' => {
                depth = depth.saturating_sub(1);
                if depth == 0 {
                    add_column(&clause, &mut out);
                    break;
                }
                clause.push(c);
            }
            ',' if depth == 1 => {
                add_column(&clause, &mut out);
                clause.clear();
            }
            _ => clause.push(c),
        }
    }
    out
}

fn add_column(clause: &str, out: &mut Vec<String>) {
    let clause = clause.trim();
    if clause.is_empty() {
        return;
    }
    let mut rest = clause;
    if let Some(rest2) = rest.strip_prefix("CONSTRAINT") {
        // « CONSTRAINT nom ... » : pas une colonne.
        let _ = rest2;
        return;
    }
    // Nom de colonne : nu, ou entre guillemets / crochets / accents graves.
    let (name, tail) = if let Some(r) = rest.strip_prefix('"') {
        match r.find('"') {
            Some(e) => (&r[..e], &r[e + 1..]),
            None => (r, ""),
        }
    } else if let Some(r) = rest.strip_prefix('[') {
        match r.find(']') {
            Some(e) => (&r[..e], &r[e + 1..]),
            None => (r, ""),
        }
    } else if let Some(r) = rest.strip_prefix('`') {
        match r.find('`') {
            Some(e) => (&r[..e], &r[e + 1..]),
            None => (r, ""),
        }
    } else {
        let end = rest
            .find(|c: char| c.is_whitespace() || c == '(')
            .unwrap_or(rest.len());
        (&rest[..end], &rest[end..])
    };
    rest = tail.trim_start();
    let upper = rest.to_ascii_uppercase();
    for keyword in ["PRIMARY", "UNIQUE", "CHECK", "FOREIGN"] {
        if upper.starts_with(keyword) {
            return;
        }
    }
    if !name.is_empty() {
        out.push(name.trim().to_string());
    }
}

impl Value {
    pub fn text(&self) -> String {
        match self {
            Value::Text(t) => t.clone(),
            Value::Blob(b) => String::from_utf8_lossy(b).into_owned(),
            Value::Null => String::new(),
            Value::Int(i) => i.to_string(),
            Value::Real(f) => f.to_string(),
        }
    }

    pub fn int(&self) -> i64 {
        match self {
            Value::Int(i) => *i,
            Value::Real(f) => *f as i64,
            Value::Text(t) => t.trim().parse().unwrap_or(0),
            _ => 0,
        }
    }
}

pub struct Db {
    data: Vec<u8>,
    page_size: usize,
    reserved: usize,
    encoding: u32,
}

impl Db {
    pub fn open(path: &Path) -> Result<Db, String> {
        let data = std::fs::read(path).map_err(|e| format!("lecture impossible : {e}"))?;
        Self::from_bytes(data)
    }

    pub fn from_bytes(data: Vec<u8>) -> Result<Db, String> {
        if data.len() < 100 || &data[..16] != b"SQLite format 3\0" {
            return Err("ce fichier n'est pas une base SQLite".into());
        }
        let raw_page = be_u16(&data, 16);
        let page_size = if raw_page == 1 { 65536 } else { raw_page as usize };
        if page_size == 0 || !page_size.is_power_of_two() {
            return Err("taille de page invalide".into());
        }
        let encoding = be_u32(&data, 56);
        // Octets réservés par page (lus **avant** de déplacer `data`).
        let reserved = data.get(20).copied().unwrap_or(0) as usize;
        Ok(Db {
            data,
            page_size,
            reserved,
            encoding: if (1..=3).contains(&encoding) { encoding } else { 1 },
        })
    }

    fn usable(&self) -> usize {
        self.page_size.saturating_sub(self.reserved)
    }

    /// Une page (numérotée à partir de 1) ; `None` si le fichier est tronqué.
    fn page(&self, number: u32) -> Option<&[u8]> {
        if number == 0 {
            return None;
        }
        let start = (number as usize - 1).checked_mul(self.page_size)?;
        let end = start.checked_add(self.page_size)?;
        if end > self.data.len() {
            return None;
        }
        Some(&self.data[start..end])
    }

    /// Schéma d'une table : page racine et noms des colonnes, **dans l'ordre**.
    ///
    /// Les colonnes sont résolues par leur nom (et non par leur position) car
    /// les schémas évoluent d'une version de navigateur à l'autre.
    pub fn table_schema(&self, name: &str) -> Option<Table> {
        for row in self.walk(1) {
            let kind = row.first().map(Value::text).unwrap_or_default();
            let table = row.get(1).map(Value::text).unwrap_or_default();
            if kind == "table" && table == name {
                let sql = row.get(4).map(Value::text).unwrap_or_default();
                let root = row.get(3).map(Value::int).unwrap_or(0) as u32;
                if root == 0 {
                    return None;
                }
                return Some(Table { root, columns: parse_columns(&sql) });
            }
        }
        None
    }

    /// Toutes les lignes d'une table, dans l'ordre du fichier.
    pub fn rows(&self, root: u32) -> Vec<Vec<Value>> {
        self.walk(root)
    }

    /// Nombre de pages du fichier (pour les bornes de sécurité).
    fn page_count(&self) -> u32 {
        (self.data.len() / self.page_size.max(1)) as u32
    }

    fn walk(&self, root: u32) -> Vec<Vec<Value>> {
        let mut out = Vec::new();
        let mut seen = HashSet::new();
        self.walk_page(root, &mut seen, 0, &mut out);
        out
    }

    /// Parcours récursif d'un arbre B. `depth` et `seen` protègent d'un fichier
    /// corrompu qui boucherait sur lui-même (plutôt que de planter).
    fn walk_page(&self, number: u32, seen: &mut HashSet<u32>, depth: u32, out: &mut Vec<Vec<Value>>) {
        if depth > 32 || !seen.insert(number) {
            return;
        }
        let Some(page) = self.page(number) else { return };
        let usable = self.usable().min(page.len());
        if usable < 8 {
            return;
        }
        // Les 100 premiers octets de la page 1 sont réservés à l'en-tête du
        // fichier : l'en-tête de l'arbre B y commence à l'octet 100 (le lire à
        // l'octet 0 revenait à lire le « S » de « SQLite format 3 »).
        let header = if number == 1 { 100 } else { 0 };
        if header + 4 > usable {
            return;
        }
        let kind = page[header];
        let cells = be_u16(page, header + 3) as usize;

        // Pages intérieures (5 = table intérieure) : on descend, la clé
        // (rowid) ne nous intéresse pas.
        if kind == 5 {
            // Page intérieure : le tableau des pointeurs (offset +12) donne la
            // position des cellules, et chaque **cellule** commence par le
            // numéro de page de l'enfant. (Lire le numéro de page dans le
            // tableau des pointeurs parcourait une page arbitraire.)
            for i in 0..cells {
                let at = header + 12 + i * 2;
                if at + 2 > usable {
                    break;
                }
                let cell = be_u16(page, at) as usize;
                if cell + 4 > usable {
                    continue;
                }
                let child = be_u32(page, cell);
                self.walk_page(child, seen, depth + 1, out);
            }
            let at = header + 8;
            if at + 4 <= usable {
                self.walk_page(be_u32(page, at), seen, depth + 1, out);
            }
            return;
        }
        if kind != 13 {
            // 2/10 = index (inutile ici), 13 = feuille de table.
            return;
        }
        for i in 0..cells {
            let at = header + 8 + i * 2;
            if at + 2 > usable {
                break;
            }
            let cell = be_u16(page, at) as usize;
            if cell >= usable {
                continue;
            }
            if let Some(record) = self.read_cell(page, cell, usable) {
                out.push(record);
            }
        }
    }

    /// Lit une cellule de page feuille : longueur, rowid, enregistrement, et
    /// éventuellement la chaîne de débordement.
    fn read_cell(&self, page: &[u8], cell: usize, usable: usize) -> Option<Vec<Value>> {
        let (payload_len, n1) = varint(page, cell)?;
        let (_rowid, n2) = varint(page, cell + n1)?;
        let start = cell + n1 + n2;
        let payload_len = payload_len as usize;

        // Une charge utile plus grande que la place disponible est répartie
        // entre la page et une chaîne de pages de débordement. La part gardée
        // dans la page suit la règle de SQLite (`fillInCell`) : au maximum
        // `usable - 35` octets, et pour un enregistrement franchement plus gros,
        // `minLocal` (arrondi pour que le reste se découpe en pages pleines).
        let max_inline = usable.saturating_sub(35);
        let mut payload = Vec::new();
        if payload_len <= max_inline {
            let end = start.checked_add(payload_len)?;
            if end > page.len() {
                return None;
            }
            payload.extend_from_slice(&page[start..end]);
        } else {
            // minLocal = ((usableSize - 12) * 32 / 255) - 23
            let min_local = ((usable - 12) * 32 / 255).saturating_sub(23);
            let surplus = min_local + (payload_len - min_local) % (usable - 4);
            let local = if surplus <= max_inline { surplus } else { min_local };
            let end = start.checked_add(local)?;
            if end + 4 > page.len() {
                return None;
            }
            payload.extend_from_slice(&page[start..end]);
            let mut next = be_u32(page, end);
            let mut guard = 0;
            while next != 0 && payload.len() < payload_len && guard < 4096 {
                guard += 1;
                let Some(over) = self.page(next) else { break };
                let usable_over = self.usable().min(over.len());
                if usable_over < 8 {
                    break;
                }
                next = be_u32(over, 0);
                let take = (payload_len - payload.len()).min(usable_over - 4);
                payload.extend_from_slice(&over[4..4 + take]);
            }
        }
        Some(self.decode_record(&payload))
    }

    /// Décode un enregistrement : en-tête (types de série) puis valeurs.
    fn decode_record(&self, payload: &[u8]) -> Vec<Value> {
        let mut out = Vec::new();
        let Some((header_len, n)) = varint(payload, 0) else {
            return out;
        };
        let header_len = header_len as usize;
        if header_len > payload.len() || header_len < n {
            return out;
        }
        let mut cursor = n;
        let mut body = header_len;
        while cursor < header_len {
            let Some((serial, used)) = varint(payload, cursor) else { break };
            cursor += used;
            let size = match serial {
                0 | 8 | 9 => 0,
                1 => 1,
                2 => 2,
                3 => 3,
                4 => 4,
                5 => 6,
                6 | 7 => 8,
                n if n >= 12 => ((n - 12) / 2) as usize,
                _ => break,
            };
            if body + size > payload.len() {
                out.push(Value::Null);
                break;
            }
            let bytes = &payload[body..body + size];
            out.push(match serial {
                0 => Value::Null,
                1 => Value::Int(bytes[0] as i8 as i64),
                2 => Value::Int(i16::from_be_bytes([bytes[0], bytes[1]]) as i64),
                3 => Value::Int(int_from_be(bytes)),
                4 => Value::Int(int_from_be(bytes)),
                5 => Value::Int(int_from_be(bytes)),
                6 => Value::Int(int_from_be(bytes)),
                7 => Value::Real(f64::from_bits(u64::from_be_bytes([
                    bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
                ]))),
                8 => Value::Int(0),
                9 => Value::Int(1),
                n if n >= 12 && n % 2 == 0 => Value::Blob(bytes.to_vec()),
                _ => Value::Text(self.decode_text(bytes)),
            });
            body += size;
        }
        out
    }

    fn decode_text(&self, bytes: &[u8]) -> String {
        match self.encoding {
            2 | 3 => {
                // UTF-16, petit ou gros boutiste selon l'en-tête.
                let little = self.encoding == 2;
                let units: Vec<u16> = bytes
                    .chunks_exact(2)
                    .map(|c| {
                        if little {
                            u16::from_le_bytes([c[0], c[1]])
                        } else {
                            u16::from_be_bytes([c[0], c[1]])
                        }
                    })
                    .collect();
                String::from_utf16_lossy(&units)
            }
            _ => String::from_utf8_lossy(bytes).into_owned(),
        }
    }

    /// Nombre de pages du fichier. Utilisé par les tests et les diagnostics
    /// (d'où l'attribut : le binaire ne s'en sert pas directement).
    #[allow(dead_code)]
    pub fn page_total(&self) -> u32 {
        self.page_count()
    }
}

/* ------------------------------ utilitaires ------------------------------ */

fn be_u16(data: &[u8], at: usize) -> u16 {
    match (data.get(at), data.get(at + 1)) {
        (Some(a), Some(b)) => u16::from_be_bytes([*a, *b]),
        _ => 0,
    }
}

fn be_u32(data: &[u8], at: usize) -> u32 {
    match (data.get(at), data.get(at + 1), data.get(at + 2), data.get(at + 3)) {
        (Some(a), Some(b), Some(c), Some(d)) => u32::from_be_bytes([*a, *b, *c, *d]),
        _ => 0,
    }
}

fn int_from_be(bytes: &[u8]) -> i64 {
    // Entier signé, complément à deux, sur 1 à 8 octets.
    let mut value: i64 = if bytes.first().is_some_and(|b| b & 0x80 != 0) { -1 } else { 0 };
    for b in bytes {
        value = (value << 8) | (*b as i64);
    }
    value
}

/// Entier à taille variable (1 à 9 octets, base 128, gros boutiste).
fn varint(data: &[u8], at: usize) -> Option<(u64, usize)> {
    let mut value: u64 = 0;
    for i in 0..9 {
        let byte = *data.get(at + i)?;
        if i == 8 {
            return Some(((value << 8) | byte as u64, 9));
        }
        value = (value << 7) | (byte & 0x7f) as u64;
        if byte & 0x80 == 0 {
            return Some((value, i + 1));
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejette_un_fichier_etranger() {
        assert!(Db::from_bytes(b"ceci n'est pas une base".to_vec()).is_err());
        assert!(Db::from_bytes(Vec::new()).is_err());
    }

    #[test]
    fn varints() {
        // Cas de référence du format SQLite.
        assert_eq!(varint(&[0x00], 0), Some((0, 1)));
        assert_eq!(varint(&[0x7f], 0), Some((127, 1)));
        assert_eq!(varint(&[0x81, 0x00], 0), Some((128, 2)));
        assert_eq!(varint(&[0x82, 0x24], 0), Some((0x124, 2)));
        assert_eq!(varint(&[0xff, 0xff, 0x7f], 0), Some((0x1F_FFFF, 3)));
    }

    #[test]
    fn colonnes_extraites_du_schema() {
        let sql = "CREATE TABLE urls(id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR, \
                   visit_count INTEGER DEFAULT 0 NOT NULL, last_visit_time INTEGER NOT NULL, \
                   hidden INTEGER DEFAULT 0 NOT NULL, CONSTRAINT x CHECK (url <> ''))";
        let cols = parse_columns(sql);
        assert_eq!(
            cols,
            vec!["id", "url", "title", "visit_count", "last_visit_time", "hidden"]
        );
        let t = Table { root: 2, columns: cols };
        assert_eq!(t.index_of("LAST_VISIT_TIME"), Some(4));
        assert_eq!(t.index_of("absent"), None);

        let quoted = parse_columns("CREATE TABLE t (\"a b\" TEXT, [c d] INT, `e` INT)");
        assert_eq!(quoted, vec!["a b", "c d", "e"]);
    }

    #[test]
    fn entiers_signes() {
        assert_eq!(int_from_be(&[0x7f]), 127);
        assert_eq!(int_from_be(&[0xff]), -1);
        assert_eq!(int_from_be(&[0x80, 0x00]), -32768);
        assert_eq!(int_from_be(&[0x01, 0x00]), 256);
    }
}
