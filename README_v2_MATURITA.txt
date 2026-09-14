\
MATHERA v2.0 — MATURITA MVP
============================

Co patch přidává
----------------
- nový Django app `exams`
- model Exam + ExamTask
- import `\\uloha{N}{\\zadani{page}{left}{bottom}{right}{top}}`
- automatický crop originálního PDF pomocí pdfinfo + pdftocairo
- převod LaTeXového řešení přes stejný Pandoc/MathJax pipeline jako materiály
- seznam maturit, přehled úloh, reader úlohy, skryté řešení, previous/next
- odkaz „Maturita“ v hlavní navigaci

Zdroj pravdy
------------
V repozitáři / administraci stačí:
1. originální PDF testu
2. jeden .tex s řešeními a makry \\uloha / \\zadani

PNG výřezy vznikají automaticky pod:
media/generated/exams/<exam-slug>/task-XX.png

Systémové nástroje
------------------
- pandoc
- pdfinfo (Poppler)
- pdftocairo (Poppler)

Python image knihovna není potřeba.

Instalace lokálně
-----------------
1. Zkopíruj patch do projektu se zachováním cest.
2. Aktivuj venv.
3. Spusť:

   python manage.py makemigrations exams
   python manage.py migrate
   python manage.py check

4. V /admin/ vytvoř maturitu:
   title: Maturita z matematiky – jaro 2016
   slug: maturita-2016-jaro
   year: 2016
   term: Jaro
   source_pdf: MA_jaro_2016_DT.pdf
   source_tex: maturita_2016_reseni_pdfcrop.tex
   status: Publikováno

Při uložení se import spustí automaticky.

Pokud chceš reimport z terminálu:

   python manage.py import_exam maturita-2016-jaro

Očekávaný výsledek testovacího souboru:
- 26 úloh
- 26 PNG cropů
- 26 HTML řešení

URL
---
/maturita/
/maturita/maturita-2016-jaro/
/maturita/maturita-2016-jaro/uloha/1/

Poznámka
--------
Globální vyhledávání v tomto MVP stále prohledává `materials`. Prohledávání
maturitních úloh bych přidal až po ověření importu a readeru, aby byl první
v2.0 krok co nejmenší a snadno diagnostikovatelný.
