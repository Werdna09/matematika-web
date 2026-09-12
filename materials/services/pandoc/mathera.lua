-- =========================================================
-- MATHERA PANDOC FILTER
-- Překlad LaTeXových konstrukcí do webově kompatibilní podoby
-- =========================================================


-- \hfill uvnitř matematiky MathJax nepodporuje tak,
-- jak jej používá TeX pro sazbu stránky.
--
-- Pro web jej zatím převádíme na \qquad.
function Math(el)
    el.text = el.text:gsub("\\hfill", "\\qquad")
    return el
end


-- Pokud se \hfill objeví mimo matematický režim
-- jako samostatný raw LaTeX příkaz, nahradíme jej mezerou.
function RawInline(el)
    if el.format ~= "tex" and el.format ~= "latex" then
        return nil
    end

    if el.text:match("^%s*\\hfill%s*$") then
        return pandoc.Space()
    end

    return nil
end