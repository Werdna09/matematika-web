# AGENTS.md

## Projekt

Tento repozitář obsahuje projekt **Mathera** – webovou platformu pro výuku matematiky na střední škole.

Technologie:

- Python
- Django
- HTML
- CSS
- JavaScript
- SQLite pro lokální vývoj
- LaTeX
- Pandoc
- pdflatex
- TikZ / PGFPlots
- Lua filtr pro Pandoc

Aplikace je provozována produkčně na `mathera.cz`.

Produkční server používá repozitář v:

```text
/srv/fast/mathera
```

Lokální pracovní kopie může být umístěna jinde. Nikdy nepředpokládej, že máš přístup k produkčnímu serveru.

---

## Základní pravidla práce

Před každou změnou si nejprve prohlédni relevantní soubory a pochop existující implementaci.

Preferuj:

- malé a cílené změny,
- zachování současné architektury,
- opravu skutečné příčiny problému,
- jednoduchý a čitelný kód,
- minimální množství nových abstrakcí.

Nevytvářej rozsáhlé refaktory, pokud nejsou výslovně požadovány.

Neměň části projektu, které s úkolem nesouvisejí.

Pokud existuje více možností řešení, preferuj variantu, která nejméně naruší stávající funkční projekt.

---

## Git

Větev `main` odpovídá produkční verzi projektu.

Před prací vždy zkontroluj:

```bash
git status
```

Bez výslovného požadavku uživatele:

- neprováděj `git push`,
- nenasazuj změny na server,
- nemaž větve,
- nepoužívej destruktivní Git příkazy,
- nepřepisuj historii,
- neprováděj `git reset --hard`,
- neprováděj force push.

Po změnách ukaž nebo stručně popiš:

```bash
git diff
```

Commit vytvářej pouze tehdy, pokud je to výslovně požadováno.

---

## Bezpečnost produkce

Projekt je reálně používaný.

Nevykonávej žádné příkazy proti produkčnímu serveru.
Neupravuj produkční databázi.
Neupravuj obsah `media/` na produkci.
Nikdy automaticky nemaž existující uživatelská data.

Pokud změna vyžaduje migraci databáze, nejprve upozorni uživatele a vysvětli, proč je migrace potřeba.

---

## Django

Hlavní Django projekt je v:

```text
config/
```

Aktuální aplikace:

```text
core/
accounts/
materials/
exams/
sidequests/
```

Používá se vlastní uživatelský model:

```python
AUTH_USER_MODEL = "accounts.User"
```

Výchozí jazyk:

```text
cs
```

Časové pásmo:

```text
Europe/Prague
```

Lokální databáze je SQLite.

Konfigurace se načítá z `.env`.

Soubor `.env` obsahuje lokální nebo citlivou konfiguraci a nikdy se nesmí commitnout.

Příklad konfigurace je v:

```text
.env.example
```

---

## Ověření změn

Po změně Python/Django kódu spusť alespoň:

```bash
python manage.py check
```

Pokud jsou dostupné a relevantní testy, spusť také:

```bash
python manage.py test
```

Pokud příkaz nelze spustit kvůli chybějícím lokálním závislostem nebo externím programům, neoznačuj test jako úspěšný. Přesně řekni, co chybí.

Nevytvářej falešné výsledky testů.

---

## Python styl

Dodržuj styl existujícího projektu.

Preferuj:

- čitelné názvy,
- jednoduché funkce,
- explicitní chybové stavy,
- existující Django API,
- malé změny.

Nevkládej nové závislosti do `requirements.txt`, pokud nejsou skutečně potřeba.

Pokud je možné problém vyřešit standardní knihovnou nebo současnými závislostmi, nepřidávej další balíček.

---

# LaTeX a webový obsah

Mathera používá LaTeX jako hlavní zdroj části obsahu.

LaTeX se nepřevádí pouze jednoduchým Pandoc voláním. Existuje vlastní pipeline, kterou je nutné zachovat.

Před úpravou importerů vždy nejprve prostuduj existující kód.

Hlavní relevantní soubory jsou zejména:

```text
materials/services/tex_importer.py
materials/services/tex_preprocessor.py
materials/services/tikz_renderer.py
materials/services/pandoc/mathera.lua
sidequests/services/tex_importer.py
```

Nevytvářej paralelní druhou implementaci stejného převodu, pokud lze použít nebo rozšířit existující infrastrukturu.

---

## Převod LaTeXu na HTML

Zjednodušený tok zpracování je:

```text
LaTeX
  ↓
TikZ / PGFPlots rendering
  ↓
LaTeX preprocessing
  ↓
Pandoc
  ↓
Lua filtr
  ↓
HTML
```

TikZ a PGFPlots se převádějí na SVG.

Relevantní implementace:

```text
materials/services/tikz_renderer.py
```

Pandoc používá filtr:

```text
materials/services/pandoc/mathera.lua
```

Preprocessing vlastních LaTeX konstrukcí je v:

```text
materials/services/tex_preprocessor.py
```

---

## TikZ / PGFPlots

TikZ obrázky se nevkládají do Pandocu přímo.

Renderer používá mimo jiné:

```text
pdflatex
pdftocairo
```

a případně:

```text
dvisvgm
```

jako fallback.

Pokud lokálně některý z těchto programů není dostupný, upozorni na to. Neobcházej problém tím, že odstraníš TikZ podporu.

Renderer obsahuje timeouty záměrně, aby vadný LaTeX nezablokoval server. Timeouty neodstraňuj bez dobrého důvodu.

---

## Vlastní LaTeX konstrukce

`tex_preprocessor.py` převádí některé konstrukce, kterým Pandoc přímo nerozumí.

Například:

```text
exercise
exerciseblock
tasks
definitionbox
examplebox
notebox
historicalbox
solutionbox
important
```

Existuje také speciální normalizace tabulek.

Vlastní sloupcový typ:

```latex
C{...}
```

se pro web převádí na standardní sloupec.

Příkaz:

```latex
\rowcolor{...}
```

se při webovém preprocessingu odstraňuje.

Toto chování je záměrné.

PDF zdroj se tím nemá měnit.

---

# Bokovky / sidequests

Aplikace:

```text
sidequests/
```

slouží pro „Ondrovy bokovky“.

Modely:

```text
SideQuest
SideQuestSection
```

`SideQuest` může obsahovat:

- název,
- slug,
- popis,
- tagy,
- zdrojový `.tex`,
- vygenerované PDF,
- stav publikace,
- pořadí.

---

## Webové kapitoly bokovek

Kapitoly se ve zdrojovém LaTeXu vyznačují komentářem:

```latex
% MATHERA-SECTION: Název kapitoly
```

Například:

```latex
% MATHERA-SECTION: Úvod
...
% MATHERA-SECTION: Text
...
% MATHERA-SECTION: Závěr
```

Importer tyto markery používá pro vytvoření jednotlivých objektů `SideQuestSection`.

Marker je součástí importního formátu a nesmí být bez důvodu odstraněn nebo nahrazen automatickým dělením podle `\section`.

---

## Import bokovek

Relevantní soubor:

```text
sidequests/services/tex_importer.py
```

Aktuální importer provádí dvě hlavní věci:

1. vytvoří webové HTML kapitoly,
2. vytvoří PDF z původního LaTeXového zdroje.

PDF se kompiluje přes:

```text
pdflatex
```

ve dvou průchodech.

Dva průchody jsou záměrné kvůli referencím a číslování.

PDF se generuje z původního LaTeXového dokumentu, nikoli z preprocessované webové verze.

Webové části se zpracovávají samostatně.

Při změnách této pipeline je důležité zachovat stávající chování.

---

## Atomicita importu

Importer se snaží nejprve připravit výsledky a až potom měnit databázové kapitoly.

Nevytvářej řešení, které před úspěšným převodem smaže existující funkční kapitoly.

Pokud import selže, starý funkční obsah by měl pokud možno zůstat dostupný.

Dávej pozor na rozdíl mezi Django databázovou transakcí a filesystem/media storage. Uložení souboru do storage není automaticky rollbackováno databázovou transakcí.

---

# Materials

Aplikace:

```text
materials/
```

obsahuje hlavní výukové materiály.

Materiály používají stejnou základní LaTeX infrastrukturu jako bokovky.

Při opravě obecného LaTeX preprocessingu zvaž dopad současně na:

```text
materials
sidequests
```

Neopravuj problém pouze v jedné aplikaci, pokud je jeho skutečná příčina ve sdílené službě.

Současně ale nerozšiřuj zásah na druhou aplikaci, pokud se jí problém netýká.

---

# Maturitní úlohy

Aplikace:

```text
exams/
```

slouží pro maturitní testy a jednotlivé úlohy.

Obsahuje vlastní importér a PDF crop renderer.

Relevantní soubory:

```text
exams/services/tex_importer.py
exams/services/pdf_crop_renderer.py
```

Při změnách dávej pozor, aby úprava obecné LaTeX infrastruktury nerozbila import maturitních úloh.

---

# Frontend

Frontend je záměrně jednoduchý.

Nepřidávej React, Vue, Tailwind nebo jiný rozsáhlý frontendový framework bez výslovného požadavku.

Používá se klasické:

```text
Django templates
HTML
CSS
JavaScript
```

Zachovej současný vizuální styl Mathery.

Design má působit:

- čistě,
- klidně,
- akademicky,
- čitelně,
- jednoduše.

Preferuj existující komponenty a CSS před vytvářením paralelních stylů.

---

# Chování při opravě chyby

Pokud uživatel nahlásí konkrétní chybu:

1. nejprve reprodukuj nebo lokalizuj příčinu,
2. projdi související kód,
3. vysvětli si datový tok,
4. oprav příčinu, ne pouze viditelný symptom,
5. změň co nejméně souborů,
6. spusť relevantní kontroly,
7. prohlédni `git diff`,
8. stručně shrň:
   - příčinu,
   - provedenou změnu,
   - ověření.

Pokud si nejsi jistý, nehádej. Nejprve prozkoumej projekt.

---

# Co nedělat

Bez výslovného požadavku:

- nepřepisuj celý projekt,
- neměň framework,
- neměň strukturu aplikací,
- nemaž fungující funkce,
- nevytvářej nové databázové modely jen kvůli jednoduché opravě,
- neupravuj migrace zpětně,
- nemaž existující migrace,
- neměň veřejné URL bez důvodu,
- neměň produkční konfiguraci,
- nemanipuluj s produkčním serverem,
- nepushuj na GitHub,
- nedělej automatický deploy.

---

# Komunikace

Uživatel je technicky zdatný a rozumí Pythonu, C/C++, Linuxu, Gitu a LaTeXu.

Není nutné vysvětlovat základní programátorské pojmy.

Při práci:

- buď konkrétní,
- používej přesné názvy souborů,
- popisuj skutečnou příčinu problému,
- nevymýšlej si výsledky,
- pokud něco nelze ověřit, řekni to.

Komentáře v projektu mohou být česky.

Uživatelské texty a administrační hlášky mají být primárně česky.

