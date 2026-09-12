-- =========================================================
-- MATHERA PANDOC FILTER
-- =========================================================


-- =========================================================
-- Pomocné funkce
-- =========================================================

local function block_text(block)
    return pandoc.utils.stringify(block)
end


local function is_marker(block, marker)
    return block_text(block):match(
        "^%s*" .. marker .. "%s*$"
    ) ~= nil
end


-- =========================================================
-- \hfill
-- =========================================================

local function process_math(el)
    el.text = el.text:gsub(
        "\\hfill",
        "\\qquad"
    )

    return el
end


local function process_raw_inline(el)
    if el.format ~= "tex"
        and el.format ~= "latex"
    then
        return nil
    end

    if el.text:match(
        "^%s*\\hfill%s*$"
    ) then
        return pandoc.Space()
    end

    return nil
end


-- =========================================================
-- TASKS
-- =========================================================

local function process_ordered_list(el)
    if #el.content == 0 then
        return nil
    end


    local first_item = el.content[1]

    if #first_item == 0 then
        return nil
    end


    local first_block = first_item[1]

    if first_block.t ~= "Plain"
        and first_block.t ~= "Para"
    then
        return nil
    end


    local marker_index = nil
    local columns = nil


    for index, inline in ipairs(
        first_block.content
    ) do
        if inline.t == "Str" then
            local found_columns =
                inline.text:match(
                    "^MATHERATASKSCOLS(%d+)$"
                )

            if found_columns then
                marker_index = index
                columns = tonumber(
                    found_columns
                )

                break
            end
        end
    end


    if not marker_index
        or not columns
    then
        return nil
    end


    -- Odstranění markeru.
    table.remove(
        first_block.content,
        marker_index
    )


    -- A případné mezery hned za markerem.
    if first_block.content[marker_index]
        and first_block.content[
            marker_index
        ].t == "Space"
    then
        table.remove(
            first_block.content,
            marker_index
        )
    end


    return pandoc.Div(
        {el},
        pandoc.Attr(
            "",
            {"mathera-tasks"},
            {
                style =
                    "--task-columns: "
                    .. columns
                    .. ";"
            }
        )
    )
end


-- =========================================================
-- EXERCISE
-- =========================================================

local function process_block_quote(el)
    if #el.content == 0 then
        return nil
    end


    if not is_marker(
        el.content[1],
        "MATHERAEXERCISESTART"
    ) then
        return nil
    end


    local title_marker = nil
    local body_marker = nil


    for index, block in ipairs(
        el.content
    ) do
        if is_marker(
            block,
            "MATHERAEXERCISETITLE"
        ) then
            title_marker = index
        end

        if is_marker(
            block,
            "MATHERAEXERCISEBODY"
        ) then
            body_marker = index
        end
    end


    if not title_marker
        or not body_marker
        or body_marker <= title_marker
    then
        return nil
    end


    local title_blocks = {}

    for index =
        title_marker + 1,
        body_marker - 1
    do
        table.insert(
            title_blocks,
            el.content[index]
        )
    end


    local body_blocks = {}

    for index =
        body_marker + 1,
        #el.content
    do
        table.insert(
            body_blocks,
            el.content[index]
        )
    end


    local title_div = pandoc.Div(
        title_blocks,
        pandoc.Attr(
            "",
            {"mathera-exercise-title"}
        )
    )


    local body_div = pandoc.Div(
        body_blocks,
        pandoc.Attr(
            "",
            {"mathera-exercise-body"}
        )
    )


    return pandoc.Div(
        {
            title_div,
            body_div,
        },
        pandoc.Attr(
            "",
            {"mathera-exercise"}
        )
    )
end


-- =========================================================
-- Pořadí filtrů
-- =========================================================

return {
    {
        Math = process_math,
        RawInline = process_raw_inline,
    },

    {
        OrderedList = process_ordered_list,
    },

    {
        BlockQuote = process_block_quote,
    },
}