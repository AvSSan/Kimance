import datetime
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import pytz

from config import APP_TIMEZONE


SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = f"{{{SHEET_NS}}}"


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{NS}si"):
        strings.append("".join(t.text or "" for t in item.iter(f"{NS}t")))
    return strings


def _sheet_paths(zf: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{{{REL_NS}}}Relationship")}

    paths = {}
    for sheet in workbook.find(f"{NS}sheets"):
        rel_id = sheet.attrib[f"{{{OFFICE_REL_NS}}}id"]
        target = rel_by_id[rel_id]
        if not target.startswith("xl/"):
            target = f"xl/{target.lstrip('/')}"
        paths[sheet.attrib["name"]] = target
    return paths


def _cell_value(cell, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.find(f"{NS}v")
        return shared_strings[int(value.text)] if value is not None and value.text else ""
    if cell_type == "inlineStr":
        inline = cell.find(f"{NS}is")
        return "".join(t.text or "" for t in inline.iter(f"{NS}t")) if inline is not None else ""

    value = cell.find(f"{NS}v")
    return value.text if value is not None and value.text is not None else ""


def read_xlsx_table(path: str | Path, sheet_name: str) -> list[tuple[int, dict]]:
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        paths = _sheet_paths(zf)
        if sheet_name not in paths:
            available = ", ".join(paths)
            raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {available}")

        shared_strings = _load_shared_strings(zf)
        worksheet = ET.fromstring(zf.read(paths[sheet_name]))
        sheet_data = worksheet.find(f"{NS}sheetData")
        rows = []

        for row in sheet_data.findall(f"{NS}row"):
            row_num = int(row.attrib["r"])
            values = {}
            for cell in row.findall(f"{NS}c"):
                values[_column_index(cell.attrib["r"])] = _cell_value(cell, shared_strings)
            if values:
                max_col = max(values)
                rows.append((row_num, [values.get(i, "") for i in range(1, max_col + 1)]))

    if not rows:
        return []

    headers = [str(value).strip() for value in rows[0][1]]
    result = []
    for row_num, values in rows[1:]:
        item = {}
        for index, header in enumerate(headers):
            if header:
                item[header] = values[index] if index < len(values) else ""
        result.append((row_num, item))
    return result


def records_from_xlsx(path: str | Path, sheet_name: str = "Расходы") -> list[dict]:
    required = ["Дата", "Время", "Тип", "Сумма", "Категория"]
    rows = read_xlsx_table(path, sheet_name)
    records = []

    for row_num, row in rows:
        if not any(str(row.get(key, "")).strip() for key in required):
            continue
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f"Missing required columns in row {row_num}: {', '.join(missing)}")

        amount_text = str(row["Сумма"]).replace(" ", "").replace(",", ".")
        records.append(
            {
                "date": str(row["Дата"]).strip(),
                "time": str(row["Время"]).strip(),
                "type": str(row["Тип"]).strip(),
                "amount": float(amount_text),
                "category": str(row["Категория"]).strip(),
                "comment": str(row.get("Комментарий", "") or "").strip(),
                "source": Path(path).name,
                "source_row": row_num,
            }
        )

    return records


def _inline_cell(ref: str, value) -> str:
    text = escape("" if value is None else str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _number_cell(ref: str, value) -> str:
    return f'<c r="{ref}"><v>{float(value):.2f}</v></c>'


def write_records_xlsx(records: list[dict], balance: float, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    headers = ["Дата", "Время", "Тип", "Сумма", "Категория", "Комментарий", "Текущий баланс"]
    rows = [headers]
    for record in records:
        rows.append(
            [
                record["date"],
                record["time"],
                record["type"],
                record["amount"],
                record["category"],
                record.get("comment", ""),
                "",
            ]
        )

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{_column_name(col_index)}{row_index}"
            if row_index > 1 and col_index == 4:
                cells.append(_number_cell(ref, value))
            elif row_index == 2 and col_index == 7:
                cells.append(_number_cell(ref, balance))
            else:
                cells.append(_inline_cell(ref, value))
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    last_row = max(len(rows), 1)
    worksheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{SHEET_NS}" xmlns:r="{OFFICE_REL_NS}">
  <dimension ref="A1:G{last_row}"/>
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="1" width="13" customWidth="1"/>
    <col min="2" max="2" width="10" customWidth="1"/>
    <col min="3" max="3" width="12" customWidth="1"/>
    <col min="4" max="4" width="12" customWidth="1"/>
    <col min="5" max="5" width="20" customWidth="1"/>
    <col min="6" max="6" width="34" customWidth="1"/>
    <col min="7" max="7" width="16" customWidth="1"/>
  </cols>
  <sheetData>{"".join(sheet_rows)}</sheetData>
</worksheet>'''

    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{SHEET_NS}" xmlns:r="{OFFICE_REL_NS}">
  <sheets><sheet name="Расходы" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''

    workbook_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="{OFFICE_REL_NS}/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="{OFFICE_REL_NS}/styles" Target="styles.xml"/>
</Relationships>'''

    root_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="{OFFICE_REL_NS}/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

    styles = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{SHEET_NS}">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>'''

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)

    return output_path


def export_filename(prefix: str = "Kimance_export") -> str:
    stamp = datetime.datetime.now(pytz.timezone(APP_TIMEZONE)).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.xlsx"
