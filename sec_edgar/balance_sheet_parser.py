import re

from sec_edgar import Parser


class BalanceSheetParser(Parser):

    def _find_relevant_lines(self, clean_lines):
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(r"CONSOLIDATED STATEMENT (OF )?FINANCIAL POSITION", line,
                                               re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and re.search(r"CONSOLIDATED STATEMENT (OF )?CASH FLOWS?", line,
                                               re.MULTILINE) is not None:
                end_index = i
                break
        return start_index, end_index

    def _find_table_beginning(self, line):
        found_reg = re.search(
            r".*At (January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{1,2}.*",
            line, re.IGNORECASE)
        if found_reg is not None:
            return [3]

    def _parse_html(self, soup):
        balance_sheet_title = soup.find_all(
            lambda tag: "Consolidated Balance Sheets".lower() in tag.text.strip().lower())[-1]
        table_html = str(balance_sheet_title.find_next("table"))
        df, period = self.parse_table(table_html)
        return df
