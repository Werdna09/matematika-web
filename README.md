# Matematika

Webová platforma pro výuku matematiky na střední škole.

Cílem projektu je vytvořit jednoduché, přehledné a postupně rozšiřitelné prostředí pro učební materiály, pracovní listy, úkoly a později také interaktivní matematický obsah.

Projekt je navržen tak, aby mohl být vyvíjen po jednotlivých funkčních verzích bez nutnosti při každém rozšíření přepisovat jeho základní architekturu.

## Roadmap

### V1 – Knihovna materiálů

První verze bude sloužit jako veřejně přístupná knihovna matematických materiálů.

Plánované funkce:

* členění podle ročníků a témat,
* učební materiály a pracovní listy,
* PDF soubory ke stažení,
* tagy a další možnosti třídění,
* vyhledávání,
* publikování a skrývání materiálů,
* administrační rozhraní pro správu obsahu.

V této verzi nebudou žákovské účty.

### V1.5 – Online učebnice

LaTeXové učební texty bude možné zobrazovat také přímo jako webové stránky.

LaTeX bude sloužit jako hlavní zdroj obsahu, ze kterého bude možné vytvářet:

* webovou verzi pro pohodlné online čtení,
* PDF verzi pro stažení, tisk a offline použití.

Cílem je udržovat obsah pouze na jednom místě a negenerovat ručně samostatnou webovou a PDF verzi.

### V2 – Žáci a výuka

Projekt bude rozšířen o:

* účty učitelů a žáků,
* třídy a školní roky,
* různá uživatelská oprávnění,
* osobní uložené materiály,
* materiály určené konkrétním třídám nebo žákům,
* zadávání úkolů,
* odevzdávání práce,
* historii odevzdaných verzí,
* archivaci tříd.

### V3 – Interaktivní matematika

Web bude postupně doplněn o samostatné interaktivní matematické moduly, například:

* grafy funkcí a jejich transformace,
* grafické řešení rovnic,
* geometrické konstrukce,
* analytickou geometrii,
* práci s vektory,
* další dynamické matematické vizualizace.

## Možný další vývoj

V budoucnu může být platforma rozšířena také o systém procvičování s generováním příkladů, automatickou kontrolou výsledků a historií práce žáka.

## Technologie

Projekt používá především:

* Python
* Django
* HTML
* CSS
* JavaScript

Pro lokální vývoj se používá SQLite. Pro budoucí produkční nasazení se počítá s PostgreSQL.

Frontend je záměrně vytvářen bez rozsáhlého JavaScriptového frameworku. Důraz je kladen na jednoduchost, rychlost, přehlednost a snadnou údržbu.

## Stav projektu

**V1 – počáteční vývoj**
