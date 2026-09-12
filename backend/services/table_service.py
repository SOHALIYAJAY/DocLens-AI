# services/table_service.py
"""
Table Service for DocLens-AI Chatbot.
Handles table extraction, structured metadata preservation, table-aware retrieval,
and deterministic Python calculations for numerical operations.
"""

import re
import math
from typing import List, Dict, Any, Optional, Tuple

class TableService:
    def __init__(self):
        self.tables: List[Dict[str, Any]] = []

    def clear_tables(self):
        """Clears all stored structured tables."""
        self.tables.clear()

    def get_tables(self) -> List[Dict[str, Any]]:
        """Returns all registered tables."""
        return self.tables

    def add_table(self, table_data: Dict[str, Any]):
        """
        Registers a structured table preserving all 8 required metadata fields:
        - table_id
        - page_number
        - caption
        - headers
        - rows
        - columns
        - section
        - document_id
        """
        table_id = table_data.get("table_id") or f"table_{len(self.tables) + 1}"
        page_number = int(table_data.get("page_number", table_data.get("page", 1)))
        caption = table_data.get("caption", "")
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        columns = table_data.get("columns", {})
        section = table_data.get("section", "General")
        document_id = table_data.get("document_id", "doc_default")

        # Automatically construct columns dict if missing but headers/rows exist
        if not columns and headers and rows:
            columns = {}
            for col_idx, header in enumerate(headers):
                col_vals = []
                for row in rows:
                    if col_idx < len(row):
                        col_vals.append(str(row[col_idx]).strip())
                    else:
                        col_vals.append("")
                columns[str(header).strip()] = col_vals

        structured_table = {
            "table_id": table_id,
            "page_number": page_number,
            "caption": caption,
            "headers": headers,
            "rows": rows,
            "columns": columns,
            "section": section,
            "document_id": document_id,
            "raw_text": table_data.get("raw_text", "")
        }

        # Avoid duplicates
        for idx, existing in enumerate(self.tables):
            if existing["table_id"] == table_id and existing["document_id"] == document_id:
                self.tables[idx] = structured_table
                return

        self.tables.append(structured_table)

    def parse_markdown_table(self, text: str) -> Optional[Tuple[List[str], List[List[str]]]]:
        """
        Parses a markdown formatted table (with | headers | and | --- | separators)
        into headers and rows.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip().startswith("|") and line.strip().endswith("|")]
        if len(lines) < 2:
            return None

        # Extract headers from first line
        headers = [cell.strip() for cell in lines[0].strip("|").split("|")]

        rows = []
        for line in lines[1:]:
            # Skip delimiter line |---|---|
            if re.match(r"^\|[\s:\-|\+]+\|\s*$", line):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) == len(headers) or len(cells) > 1:
                rows.append(cells)

        if headers and rows:
            return headers, rows
        return None

    def extract_and_register_from_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Scans document chunks for table content and extracts structured table objects.
        """
        table_count = 0
        for chunk in chunks:
            content_type = chunk.get("content_type", "")
            c_text = chunk.get("text", "")
            
            if content_type == "table" or "|---" in c_text or re.search(r"\|.*\|.*\|", c_text):
                table_count += 1
                tbl_id = chunk.get("table_id") or f"table_{table_count}"
                
                parsed = self.parse_markdown_table(c_text)
                headers = []
                rows = []
                if parsed:
                    headers, rows = parsed

                self.add_table({
                    "table_id": tbl_id,
                    "page_number": chunk.get("page_number", chunk.get("page", 1)),
                    "caption": chunk.get("caption", ""),
                    "headers": headers,
                    "rows": rows,
                    "section": chunk.get("section", "General"),
                    "document_id": chunk.get("document_id", "doc_default"),
                    "raw_text": c_text
                })

    def classify_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Classifies whether a question is table-related and identifies calculation intent:
        'maximum', 'minimum', 'sum', 'average', 'percentage', 'yoy', or 'none'.
        """
        if not query:
            return {"is_table_query": False, "calc_type": "none"}

        q_lower = query.lower()

        # Keywords triggering table query
        table_keywords = [
            "table", "revenue", "profit", "sales", "expenses", "growth", "margin",
            "year", "highest", "lowest", "maximum", "minimum", "max", "min",
            "sum", "total", "average", "mean", "percentage", "percent", "%",
            "yoy", "year-over-year", "year over year", "compared to", "compare",
            "which year", "increase", "decrease"
        ]

        is_table = any(kw in q_lower for kw in table_keywords) or bool(re.search(r"\b(20\d{2}|19\d{2})\b", q_lower))

        calc_type = "none"
        if any(w in q_lower for w in ["highest", "maximum", "max", "top", "largest", "most", "peak"]):
            calc_type = "maximum"
        elif any(w in q_lower for w in ["lowest", "minimum", "min", "bottom", "smallest", "least"]):
            calc_type = "minimum"
        elif any(w in q_lower for w in ["sum", "total", "combined", "altogether"]):
            calc_type = "sum"
        elif any(w in q_lower for w in ["average", "mean", "avg"]):
            calc_type = "average"
        elif any(w in q_lower for w in ["yoy", "year-over-year", "year over year"]):
            calc_type = "yoy"
        elif any(w in q_lower for w in ["percentage", "percent", "%", "diff", "difference"]):
            calc_type = "percentage"
        elif "compare" in q_lower or "comparison" in q_lower:
            calc_type = "percentage"

        return {
            "is_table_query": is_table,
            "calc_type": calc_type
        }

    def table_aware_retrieval(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Finds the top relevant structured table matching query terms.
        """
        if not self.tables:
            return None

        q_tokens = set(re.findall(r"\w+", query.lower()))
        
        best_table = None
        best_score = -1

        for tbl in self.tables:
            score = 0
            searchable_text = f"{tbl['table_id']} {tbl['caption']} {tbl['section']} {' '.join(tbl['headers'])} {tbl['raw_text']}".lower()
            
            for token in q_tokens:
                if len(token) > 2 and token in searchable_text:
                    score += 1
                    # Give higher weight to header or caption matches
                    if any(token in h.lower() for h in tbl['headers']):
                        score += 2
                    if token in tbl['caption'].lower():
                        score += 2

            if score > best_score:
                best_score = score
                best_table = tbl

        if best_score > 0:
            return best_table

        # Return first table if tables exist and query is table-related
        return self.tables[0] if self.tables else None

    @staticmethod
    def parse_numeric_value(val_str: str) -> Optional[float]:
        """
        Parses numeric floats from financial or tabular strings like '$12.0M', '8.5M', '10,000', '45%'.
        """
        if not val_str or not isinstance(val_str, str):
            return None

        clean = val_str.strip().replace(",", "")
        
        # Check scale multiplier
        multiplier = 1.0
        if re.search(r"[mM]\b", clean):
            multiplier = 1e6
            clean = re.sub(r"[mM]\b", "", clean)
        elif re.search(r"[kB]\b", clean):
            if "k" in clean.lower():
                multiplier = 1e3
                clean = re.sub(r"[kK]\b", "", clean)
            elif "b" in clean.lower():
                multiplier = 1e9
                clean = re.sub(r"[bB]\b", "", clean)

        clean = clean.replace("$", "").replace("%", "").strip()

        match = re.search(r"[-+]?\d*\.?\d+", clean)
        if match:
            try:
                return float(match.group(0)) * multiplier
            except ValueError:
                return None
        return None

    def calculate_table_metrics(self, table: Dict[str, Any], calc_type: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Executes deterministic Python calculations for simple operations:
        - maximum
        - minimum
        - sum
        - average
        - percentage difference
        - year-over-year change (YoY)
        """
        if not table or calc_type == "none":
            return None

        headers = table.get("headers", [])
        rows = table.get("rows", [])
        columns = table.get("columns", {})

        if not rows:
            return None

        # Extract numeric columns/series
        # Scenario A: Columns are years/categories and rows are metrics (e.g. Header: [Year, Revenue, Expenses])
        # Scenario B: First column is metric name, subsequent columns are years (e.g. Header: [Metric, 2023, 2024])

        parsed_series = []

        # Try row-wise numerical series
        for row_idx, row in enumerate(rows):
            label = row[0] if len(row) > 0 else f"Row {row_idx+1}"
            numeric_items = []
            for col_idx, cell in enumerate(row[1:], start=1):
                col_header = headers[col_idx] if col_idx < len(headers) else f"Col {col_idx+1}"
                num = self.parse_numeric_value(cell)
                if num is not None:
                    numeric_items.append((col_header, cell, num))
            if numeric_items:
                parsed_series.append({"label": label, "items": numeric_items})

        # Try column-wise numerical series
        for col_idx, header in enumerate(headers):
            if col_idx == 0:
                continue
            numeric_items = []
            for row_idx, row in enumerate(rows):
                label = row[0] if len(row) > 0 else f"Row {row_idx+1}"
                if col_idx < len(row):
                    cell = row[col_idx]
                    num = self.parse_numeric_value(cell)
                    if num is not None:
                        numeric_items.append((label, cell, num))
            if numeric_items:
                parsed_series.append({"label": header, "items": numeric_items})

        if not parsed_series:
            return None

        # Execute deterministic Python calculation based on calc_type
        results = {}

        if calc_type == "maximum":
            best_val = -math.inf
            best_item = None
            best_series_label = ""
            for series in parsed_series:
                for item_label, raw_str, val in series["items"]:
                    if val > best_val:
                        best_val = val
                        best_item = (item_label, raw_str, val)
                        best_series_label = series["label"]
            if best_item:
                results = {
                    "operation": "Maximum",
                    "value": best_item[1],
                    "numeric_value": best_item[2],
                    "target_entity": f"{best_series_label} ({best_item[0]})",
                    "explanation": f"Deterministic Python calculation identified the maximum value as {best_item[1]} for {best_series_label} ({best_item[0]})."
                }

        elif calc_type == "minimum":
            best_val = math.inf
            best_item = None
            best_series_label = ""
            for series in parsed_series:
                for item_label, raw_str, val in series["items"]:
                    if val < best_val:
                        best_val = val
                        best_item = (item_label, raw_str, val)
                        best_series_label = series["label"]
            if best_item:
                results = {
                    "operation": "Minimum",
                    "value": best_item[1],
                    "numeric_value": best_item[2],
                    "target_entity": f"{best_series_label} ({best_item[0]})",
                    "explanation": f"Deterministic Python calculation identified the minimum value as {best_item[1]} for {best_series_label} ({best_item[0]})."
                }

        elif calc_type in ("sum", "average"):
            # Select first numerical series
            series = parsed_series[0]
            vals = [v for _, _, v in series["items"]]
            if vals:
                if calc_type == "sum":
                    total = sum(vals)
                    results = {
                        "operation": "Sum",
                        "value": f"{total:,.2f}".rstrip('0').rstrip('.'),
                        "numeric_value": total,
                        "target_entity": series["label"],
                        "explanation": f"Deterministic Python sum across {series['label']} equals {total:,.2f}."
                    }
                else:
                    avg = sum(vals) / len(vals)
                    results = {
                        "operation": "Average",
                        "value": f"{avg:,.2f}".rstrip('0').rstrip('.'),
                        "numeric_value": avg,
                        "target_entity": series["label"],
                        "explanation": f"Deterministic Python average across {series['label']} equals {avg:,.2f}."
                    }

        elif calc_type in ("percentage", "yoy"):
            # Find 2 numerical items in series to compare
            for series in parsed_series:
                if len(series["items"]) >= 2:
                    label1, raw1, val1 = series["items"][0]
                    label2, raw2, val2 = series["items"][1]
                    if val1 != 0:
                        pct_change = ((val2 - val1) / abs(val1)) * 100.0
                        diff = val2 - val1
                        op_name = "Year-over-Year (YoY) Change" if calc_type == "yoy" else "Percentage Difference"
                        results = {
                            "operation": op_name,
                            "value": f"{pct_change:+.2f}%",
                            "numeric_value": pct_change,
                            "absolute_difference": diff,
                            "from": f"{label1}: {raw1}",
                            "to": f"{label2}: {raw2}",
                            "target_entity": series["label"],
                            "explanation": (
                                f"Deterministic Python calculation: change from {label1} ({raw1}) to {label2} ({raw2}) "
                                f"is {pct_change:+.2f}% (difference of {diff:,.2f})."
                            )
                        }
                        break

        return results if results else None

    def format_table_context(self, table: Dict[str, Any], calculation: Optional[Dict[str, Any]] = None) -> str:
        """
        Formats structured table data and calculation results into a rich context string for the LLM.
        """
        page_str = f"Page {table['page_number']}"
        table_id = table['table_id']
        caption = table.get('caption', '')
        section = table.get('section', 'General')
        headers = table.get('headers', [])
        rows = table.get('rows', [])

        lines = [
            f"=== STRUCTURED TABLE DETECTED ===",
            f"[Table ID: {table_id}] [{page_str}] [Section: {section}]",
            f"Caption: {caption if caption else 'None'}"
        ]

        if headers:
            lines.append(f"Headers: | {' | '.join(headers)} |")
            lines.append(f"| {' | '.join(['---'] * len(headers))} |")
        
        for row in rows:
            lines.append(f"Row: | {' | '.join([str(c) for c in row])} |")

        if calculation:
            lines.append("\n=== DETERMINISTIC PYTHON CALCULATION RESULTS ===")
            lines.append(f"Operation: {calculation.get('operation')}")
            lines.append(f"Entity/Metric: {calculation.get('target_entity')}")
            lines.append(f"Calculated Result: {calculation.get('value')}")
            lines.append(f"Explanation: {calculation.get('explanation')}")

        lines.append("===================================\n")
        return "\n".join(lines)


# Global singleton instance
table_service = TableService()
