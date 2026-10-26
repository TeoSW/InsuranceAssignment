# SFCR 2025, secțiunea E: Asigurări Carpați

Programul scrie draftul 2025 al secțiunii E din SFCR (fonduri proprii, SCR, MCR, rata de solvabilitate). Folosește formulările aprobate, preluate din raportul publicat pentru 2024, cifrele din registrul 2025 și faptele din documentele clientului. Unde nu poate completa corect ceva, lasă un gol vizibil: `[de completat: motiv]`. `DESIGN.md` explică designul și deciziile din spatele lui.

## Instalare

Aveți nevoie de Python 3.11 sau mai nou.

```bash
python -m venv .venv
```

Activați mediul (`.venv\Scripts\activate` pe Windows, `source .venv/bin/activate` în rest), apoi instalați dependențele:

```bash
pip install -r requirements.txt
```

## Rulare

Din folderul `date/`:

```bash
python ../src/main.py
```

Programul presupune că `date/` conține fișierele clientului și se află în rădăcina proiectului, lângă `src/`, `config/` și `output/`. Citește intrările din folderul din care este rulat și găsește `config/` și `output/` pornind de la propria locație. Pentru a-l rula pe altă versiune a `registru_2025.xlsx`, puneți fișierul nou în `date/`, cu același nume, și rulați aceeași comandă; codul și config-ul rămân neschimbate.

Codul de ieșire 0 înseamnă că draftul a fost scris. Codul de ieșire 1 înseamnă că nu s-a scris niciun draft: config-ul are o eroare, programul a întâlnit o eroare neprevăzută sau `output/` nu a putut fi golit pentru că unul dintre fișierele lui este deschis. În primele două cazuri, `output/verificari.md` spune ce nu a mers și nu rămâne niciun draft scris pe jumătate.

## Ce scrie programul

`output/` este golit la începutul fiecărei rulări, deci tot ce conține vine din ultima rulare.

- `sectiunea_E_2025.md`: draftul. Fiecare propoziție vine din `config/sentences.toml`; fiecare cifră vine din registru, dintr-un document sau dintr-un calcul pe acestea. Dacă prima linie este "ȘABLON NEAPROBAT", textul nu a fost aprobat în `config/approvals.toml` sau s-a schimbat după aprobare.
- `trasabilitate.csv`: câte o linie pentru fiecare cifră, cu valoarea exactă, ce arată textul, sursa (fișier, foaie și celulă; document și pagină; sau calculul), de ce este valoarea potrivită (`de_ce`: eticheta găsită o singură dată în foaia vizibilă, coloana și unitatea din antet și verificările trecute; pentru un document, citatul găsit și cine l-a confirmat; pentru un calcul, că pornește de la valorile nerotunjite), eticheta, unitatea, starea (`ok`, `gol`, `conflict`, `decizie`) și, pentru un gol sau un conflict, motivul. Se deschide în Excel (UTF-8, `;`).
- `verificari.md`: sumele de control ale fișierelor de intrare, foile ascunse (care nu se citesc), fiecare verificare și rezultatul ei, golurile din draft, conflictele cu valorile lor exacte, deciziile, cu cine le-a propus, cine le-a aprobat și când, faptele și dacă au fost folosite, plus aprobarea textului.

## Ce fac oamenii

Tot ce decide un om stă în `config/`, deci se păstrează și în git. Fiecare fișier își explică propriile câmpuri.

- `facts.toml`: confirmați un fapt după ce verificați citatul în document (`confirmed_by`, `confirmed_on`).
- `decisions.toml`: rezolvați un conflict. Copiați valorile exacte din `verificari.md`, apoi alegeți una dintre ele sau `"gap"`, cu o sursă, un motiv și două persoane diferite. Fișierul livrat este gol intenționat: o decizie cere două persoane diferite, iar rata de solvabilitate așteaptă decizia directorului financiar. Mutația "decizie pe o parte" din teste arată cum se aplică o decizie.
- `approvals.toml`: pentru a aproba formularea unei secțiuni, completați cine, când și sha256-ul afișat de `verificari.md` pentru textul în uz.
- `figures.toml`, `relations.toml`, `sentences.toml`, `templates/`: le actualizați când se schimbă registrul sau formularea. O schimbare în `sentences.toml` sau `templates/` cere o nouă aprobare.

## Teste

Din rădăcina proiectului:

```bash
python -X utf8 -m unittest discover -s tests
```

Pentru tabelul mutațiilor (unsprezece schimbări pe o copie a registrului 2025):

```bash
python -X utf8 tests/test_mutations.py
```

Testele care au nevoie de fișierele clientului sunt omise când lipsește `date/`.

`tests/input_sha256.txt` păstrează SHA-256 pentru fișierele clientului, așa cum au fost livrate. Niciun test nu îl folosește. Din `date/`, `sha256sum -c ../tests/input_sha256.txt` arată dacă un fișier s-a schimbat de atunci.
