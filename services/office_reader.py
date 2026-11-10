"""Read DOCX and ODT packages into a preview model off the GUI thread."""
from html import escape
from pathlib import Path
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from PyQt5 import QtCore, QtGui


def _text(value):
    return escape(value).replace("\n", "<br>").replace("\t", "&nbsp;" * 4)


def _table(rows, break_before=False):
    html = []
    for index, row in enumerate(rows):
        cells = []
        for content, span in row:
            tag = "th" if index == 0 else "td"
            shade = "tableHeader" if index == 0 else "tableStripe" if index % 2 else "tableCell"
            cells.append(f'<{tag} class="{shade}" colspan="{span}">{content}</{tag}>')
        html.append("<tr>" + "".join(cells) + "</tr>")
    style = ' style="page-break-before:always"' if break_before else ""
    return f'<table{style} cellspacing="0" cellpadding="10" width="100%">' + "".join(html) + "</table>"


class OfficeReader:
    def __init__(self, path):
        self.file_path = path
        self.sheet = QtCore.QSizeF(794, 1123)
        self.margins = QtCore.QMarginsF(88, 88, 88, 88)
        self.images = []
        self.content = self._docx_html() if Path(path).suffix.lower() == ".docx" else self._odt_html()

    def _embedded_image(self, data, width=None, height=None, floating=None):
        buffer = QtCore.QBuffer()
        buffer.setData(data)
        buffer.open(QtCore.QIODevice.ReadOnly)
        reader = QtGui.QImageReader(buffer)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > 64_000_000:
            return ""
        content_width = self.sheet.width() - self.margins.left() - self.margins.right()
        content_height = self.sheet.height() - self.margins.top() - self.margins.bottom()
        width = width or size.width()
        height = height or size.height()
        factor = min(1.0, content_width / width, content_height / height)
        width, height = max(1, round(width * factor)), max(1, round(height * factor))
        if size.width() > width * 2 or size.height() > height * 2:
            size.scale(width * 2, height * 2, QtCore.Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        image = reader.read()
        if image.isNull():
            return ""
        url = QtCore.QUrl(f"office-image:{len(self.images)}")
        self.images.append((url, image))
        style = f' style="float:{floating}"' if floating else ""
        return f'<img src="{url.toString()}" width="{width}" height="{height}"{style}>'

    def _docx_html(self):
        from docx import Document
        from docx.oxml.ns import qn
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        from docx.text.run import Run
        from docx.enum.section import WD_SECTION_START

        page_break = "<!--page-break-->"
        alternate = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
        vml_image = "{urn:schemas-microsoft-com:vml}imagedata"

        def legacy_images(element, part):
            images = []
            for node in element.iter(vml_image):
                relation = part.rels.get(node.get(qn("r:id")))
                if relation is not None and not relation.is_external:
                    images.append(self._embedded_image(relation.target_part.blob))
            return "".join(images)

        def inline_items(container):
            for item in container:
                if item.tag == qn("w:sdt"):
                    content = item.find(qn("w:sdtContent"))
                    if content is not None:
                        yield from inline_items(content)
                elif item.tag in {qn("w:ins"), qn("w:smartTag"), qn("w:customXml")}:
                    yield from inline_items(item)
                else:
                    yield item

        def image_html(drawing, part):
            parts = []
            for frame in drawing:
                if frame.tag not in {qn("wp:inline"), qn("wp:anchor")}:
                    continue
                extent = frame.find(qn("wp:extent"))
                try:
                    width, height = (max(0, int(extent.get(key, 0))) / 9525
                                     for key in ("cx", "cy")) if extent is not None else (0, 0)
                except ValueError:
                    width, height = 0, 0
                floating = None
                wrap = next((frame.find(qn(f"wp:{name}")) for name in
                             ("wrapSquare", "wrapTight", "wrapThrough")
                             if frame.find(qn(f"wp:{name}")) is not None), None)
                if wrap is not None:
                    side = wrap.get("wrapText")
                    align = frame.find(f"{qn('wp:positionH')}/{qn('wp:align')}")
                    offset = frame.find(f"{qn('wp:positionH')}/{qn('wp:posOffset')}")
                    if side in {"left", "right"}:
                        floating = "right" if side == "left" else "left"
                    elif align is not None and align.text in {"right", "left"}:
                        floating = align.text
                    else:
                        try:
                            x = int(offset.text) / 9525 if offset is not None else 0
                        except (TypeError, ValueError):
                            x = 0
                        floating = "right" if x + width / 2 > self.sheet.width() / 2 else "left"
                for node in frame.iter(qn("a:blip")):
                    relation = part.rels.get(node.get(qn("r:embed")))
                    if relation is not None and not relation.is_external:
                        image = self._embedded_image(relation.target_part.blob, width, height, floating)
                        if frame.find(qn("wp:wrapTopAndBottom")) is not None:
                            image = "<br>" + image + "<br>"
                        parts.append(image)
            return "".join(parts)

        def run_html(run):
            def render_element(element):
                if element.tag == qn("w:t"):
                    return _text(element.text or "")
                elif element.tag == qn("w:tab"):
                    return "&nbsp;" * 4
                elif element.tag in {qn("w:br"), qn("w:cr")}:
                    return page_break if element.get(qn("w:type")) == "page" else "<br>"
                elif element.tag == qn("w:drawing"):
                    return image_html(element, run.part)
                elif element.tag == qn("w:pict"):
                    return legacy_images(element, run.part)
                elif element.tag == alternate:
                    for branch in element:
                        rendered = "".join(render_element(child) for child in branch)
                        if rendered:
                            return rendered
                return ""

            part = "".join(render_element(element) for element in run._r)
            for enabled, tag in ((run.bold, "b"), (run.italic, "i"), (run.underline, "u")):
                if enabled:
                    part = page_break.join(f"<{tag}>{piece}</{tag}>" if piece else ""
                                           for piece in part.split(page_break))
            if run.font.size:
                size = max(4, min(100, run.font.size.pt))
                part = page_break.join(f'<span style="font-size:{size:g}pt">{piece}</span>' if piece else ""
                                       for piece in part.split(page_break))
            return part

        def link(body, target):
            url = QtCore.QUrl(target)
            bookmark = url.hasFragment() and not url.path() and not url.scheme()
            if bookmark or url.scheme().lower() in {"https", "http", "mailto"}:
                href = escape(target, quote=True)
                return page_break.join(f'<a href="{href}">{piece}</a>' if piece else ""
                                       for piece in body.split(page_break))
            return body

        def field_target(instruction):
            match = re.match(r'^\s*HYPERLINK\s+(?:"([^"]+)"|(\S+))', instruction or "", re.I)
            if not match:
                return ""
            local = re.search(r'\\l\s+"([^"]+)"', instruction, re.I)
            if local:
                return "#" + local[1]
            return match[1] or match[2]

        def paragraph_parts(paragraph):
            parts = []
            instruction = None
            target = ""
            for child in inline_items(paragraph._p):
                if child.tag == qn("w:r"):
                    for flag in child.findall(qn("w:fldChar")):
                        kind = flag.get(qn("w:fldCharType"))
                        if kind == "begin":
                            instruction, target = "", ""
                        elif kind == "separate":
                            target = field_target(instruction)
                            instruction = None
                        elif kind == "end":
                            instruction, target = None, ""
                    if instruction is not None:
                        instruction += "".join(node.text or "" for node in child.findall(qn("w:instrText")))
                    parts.append(link(run_html(Run(child, paragraph)), target))
                elif child.tag in {qn("w:hyperlink"), qn("w:fldSimple")}:
                    body = "".join(run_html(Run(run, paragraph)) for run in inline_items(child) if run.tag == qn("w:r"))
                    if child.tag == qn("w:fldSimple"):
                        parts.append(link(body, field_target(child.get(qn("w:instr")))))
                        continue
                    anchor = child.get(qn("w:anchor"))
                    relation = paragraph.part.rels.get(child.get(qn("r:id")))
                    destination = relation.target_ref if relation is not None and relation.is_external else ""
                    if anchor:
                        destination = destination.split("#", 1)[0] + "#" + anchor
                    parts.append(link(body, destination))
                elif child.tag == qn("w:bookmarkStart"):
                    name = child.get(qn("w:name"))
                    if name:
                        parts.append(f'<a name="{escape(name, quote=True)}">&#8203;</a>')
            return "".join(parts)

        def paragraph_html(paragraph, pending_break):
            style = paragraph.style
            name = style.name if style else ""
            level = re.fullmatch(r"Heading ([1-6])", name)
            tag = f"h{level[1]}" if level else "h1" if name == "Title" else "p"
            text = paragraph_parts(paragraph)
            if name.startswith("List Bullet"):
                text = "• &nbsp;" + text
            alignment = {0: "left", 1: "center", 2: "right", 3: "justify"}.get(paragraph.alignment)
            before = paragraph.paragraph_format.page_break_before
            visited = set()
            while before is None and style is not None and style.style_id not in visited:
                visited.add(style.style_id)
                before = style.paragraph_format.page_break_before
                style = style.base_style
            pending_break = pending_break or bool(before)
            html = []
            pieces = text.split(page_break)
            for index, piece in enumerate(pieces):
                if index:
                    if pending_break:
                        html.append('<p style="page-break-before:always">&nbsp;</p>')
                    pending_break = True
                if not piece and len(pieces) > 1:
                    continue
                css = [f"text-align:{alignment}"] if alignment else []
                if pending_break:
                    css.append("page-break-before:always")
                html.append(f'<{tag} style="{";".join(css)}">{piece or "&nbsp;"}</{tag}>')
                pending_break = False
            return "".join(html), pending_break

        def table_html(table, pending_break):
            rows = []
            for row in table.rows:
                cells = []
                previous = None
                for cell in row.cells:
                    if cell._tc is previous:
                        content, count = cells[-1]
                        cells[-1] = (content, count + 1)
                    else:
                        cells.append((blocks(cell._tc, cell), 1))
                    previous = cell._tc
                rows.append(cells)
            return _table(rows, pending_break)

        def blocks(container, parent, sections=()):
            parts = []
            pending_break = False
            section_index = 0
            for element in inline_items(container):
                if isinstance(element, CT_P):
                    content, pending_break = paragraph_html(Paragraph(element, parent), pending_break)
                    parts.append(content)
                    if sections and element.find(f"{qn('w:pPr')}/{qn('w:sectPr')}") is not None:
                        section_index += 1
                        if section_index < len(sections):
                            kind = sections[section_index].start_type
                            if kind in {WD_SECTION_START.NEW_PAGE, WD_SECTION_START.EVEN_PAGE, WD_SECTION_START.ODD_PAGE}:
                                pending_break = True
                elif isinstance(element, CT_Tbl):
                    parts.append(table_html(Table(element, parent), pending_break))
                    pending_break = False
            if pending_break:
                parts.append('<p style="page-break-before:always">&nbsp;</p>')
            return "".join(parts)

        doc = Document(self.file_path)
        section = doc.sections[0]
        width = section.page_width
        height = section.page_height
        if width and height:
            self.sheet = QtCore.QSizeF(
                max(120, min(3000, width.inches * 96)),
                max(120, min(4000, height.inches * 96)),
            )
        dimensions = (section.left_margin, section.top_margin, section.right_margin, section.bottom_margin)
        defaults = (88, 88, 88, 88)
        margins = [max(0, value.inches * 96) if value is not None else default
                   for value, default in zip(dimensions, defaults)]
        for first, second, limit in ((0, 2, self.sheet.width()),
                                     (1, 3, self.sheet.height())):
            if margins[first] + margins[second] >= limit - 48:
                margins[first] = margins[second] = limit * 0.12
        self.margins = QtCore.QMarginsF(*margins)
        return blocks(doc.element.body, doc, doc.sections)

    def _odt_html(self):
        ns = {
            "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
            "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
            "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
            "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
            "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
        }
        def key(prefix, name):
            return f"{{{ns[prefix]}}}{name}"

        def convert(node):
            if node.tag in {key("text", "p"), key("text", "h")}:
                level = node.get(key("text", "outline-level"), "1")
                tag = f"h{level}" if node.tag == key("text", "h") and level in {"1", "2", "3", "4", "5", "6"} else "p"
                before = node.get(key("text", "style-name")) in page_break_styles
                style = ' style="page-break-before:always"' if before else ""
                return f"<{tag}{style}>{_text(''.join(node.itertext()))}</{tag}>"
            if node.tag == key("text", "list"):
                items = [f"<li>{''.join(map(convert, item))}</li>" for item in node]
                return "<ul>" + "".join(items) + "</ul>"
            if node.tag == key("table", "table"):
                return _table([[("".join(map(convert, cell)), 1)
                                for cell in row.findall("table:table-cell", ns)]
                               for row in (node.findall("table:table-header-rows/table:table-row", ns)
                                           + node.findall("table:table-row", ns))])
            return ""

        def read_xml(package, name):
            if package.getinfo(name).file_size > 16 * 1024 * 1024:
                raise ValueError("Документ слишком большой для предпросмотра.")
            data = package.read(name)
            if b"\x00" in data or re.search(br"<!\s*(DOCTYPE|ENTITY)", data, re.I):
                raise ValueError("Неподдерживаемый XML документа.")
            return ET.fromstring(data)

        with ZipFile(self.file_path) as package:
            content = read_xml(package, "content.xml")
            styles = read_xml(package, "styles.xml") if "styles.xml" in package.namelist() else None
        style_roots = [styles, content] if styles is not None else [content]
        page_break_styles = set()
        for root in style_roots:
            for style in root.findall(".//style:style", ns):
                props = style.find("style:paragraph-properties", ns)
                if props is not None and props.get(key("fo", "break-before")) == "page":
                    name = style.get(key("style", "name"))
                    if name:
                        page_break_styles.add(name)
        for root in style_roots:
            page = root.find(".//style:page-layout-properties", ns)
            if page is not None:
                self._apply_odt_page_size(page, key)
                break
        body = content.find("office:body/office:text", ns)
        if body is None:
            raise ValueError("Текст документа не найден.")
        return "".join(map(convert, body))

    def _apply_odt_page_size(self, properties, key):
        def pixels(name, default):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)(cm|mm|in|pt|px)",
                                 properties.get(key("fo", name), ""))
            if not match:
                return default
            units = {"cm": 96 / 2.54, "mm": 96 / 25.4, "in": 96, "pt": 96 / 72, "px": 1}
            return float(match[1]) * units[match[2]]

        width = max(120, min(3000, pixels("page-width", self.sheet.width())))
        height = max(120, min(4000, pixels("page-height", self.sheet.height())))
        default = pixels("margin", 88)
        self.sheet = QtCore.QSizeF(width, height)
        self.margins = QtCore.QMarginsF(
            min(width * 0.4, pixels("margin-left", default)),
            min(height * 0.4, pixels("margin-top", default)),
            min(width * 0.4, pixels("margin-right", default)),
            min(height * 0.4, pixels("margin-bottom", default)),
        )
