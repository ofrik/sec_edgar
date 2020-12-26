import re

from word2number import w2n

from sec_edgar import Parser


class CashFlowParser(Parser):

    def _find_relevant_lines(self, clean_lines):
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(r"CONSOLIDATED STATEMENT (OF )?CASH FLOWS?", line,
                                               re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and re.search(r"- ?[0-9]+ ?-", line,
                                               re.MULTILINE) is not None:
                end_index = i
                break
        return start_index, end_index

    def _find_table_beginning(self, line):
        if re.search(r".*(\w+) months ended.*", line, re.IGNORECASE):
            # collect period
            found_items = re.findall(r"(\w+) ?\n?months ?\n?ended", line, re.IGNORECASE | re.MULTILINE)
            periods = [w2n.word_to_num(period) for period in found_items]
            return periods

    def _parse_html(self, soup):
        cash_flow_sheet_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT", "CASH", "FLOWS"],
                                                  words_not_to_include=["CONTINUED"], with_tag={"p", "b"}))

        table = cash_flow_sheet_title.find_next("table")
        if not table:
            raise Exception("Couldn't find the cash flow sheet table(s)")
        table_html = str(table)
        df, period = self.parse_table(table_html)
        return df
