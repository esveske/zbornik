if not FORMAT:match("latex") then
  error('non latex output')
end
-- Missing: TitleEng
-- ToDo: handle `cites`
function Header(el)
  if el.attr.classes[1] == 'Literatura' then
    return {}
  end
  if el.attr.classes[1] == 'Naslov' then
    local text = pandoc.utils.stringify(el)
    return pandoc.RawBlock('latex', '\\Title{' .. text .. '}')
  end
  if el.attr.classes[1] == 'Ime-i-prezime' then
    local text = pandoc.utils.stringify(el)
    return pandoc.RawBlock('latex', '\\Author{' .. text .. '}')
  end
end

-- ToDo: working with twocolumn mode
function Table(el)
  local text = pandoc.write(pandoc.Pandoc { el }, 'latex')
  text = text:gsub('\\begin{longtable}', '\\onecolumn\\begin{longtable}')
  text = text:gsub('\\end{longtable}', '\\end{longtable}\\twocolumn')
  return pandoc.RawBlock("latex", text)
end

-- ToDo: how to connect captions
function Para(el)
  local image
  for _, inline in ipairs(el.content) do
    if inline.t == "Image" then
      image = inline
      break
    end
  end
  return image and pandoc.RawBlock('latex', '\\Figure{' .. image.src .. '}{ToDo}{ToDo}')
end

local blockQuoteNr = 0
function BlockQuote(el)
  -- classes for anytything that other than `header` doesn't exist.
  -- so we use BlockQuote as `Apstrakt` and `Author `
  if blockQuoteNr == 0 then
    blockQuoteNr = blockQuoteNr + 1
    local text = pandoc.utils.stringify(el)
    return pandoc.RawBlock('latex', '\\begin{Abstract}\n' .. text .. '\n\\end{Abstract}\n' .. '\\StartDoublePaper')
  end
  if blockQuoteNr == 1 then
    blockQuoteNr = blockQuoteNr + 1
    local text = pandoc.utils.stringify(el)
    return pandoc.RawBlock('latex', '\\begin{AuthorEx}\n' .. text .. '\n\\end{AuthorEx}\n' .. '\\AuthorExHere')
  end
end
