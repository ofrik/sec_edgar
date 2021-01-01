import re

from word2number import w2n

from sec_edgar import Parser


class CashFlowParser(Parser):

    def _find_relevant_lines(self, clean_lines):
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(
                    r"(CONSOLIDATED STATEMENTS? (OF )?)?CASH FLOWS?|CONSOLIDATED STATEMENTS? (OF )?CASH", line,
                    re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and ((re.search(r"- ?[0-9]+ ?-", line,
                                                 re.MULTILINE) is not None) or "</TABLE>" in line or "See accompanying notes" in line):
                end_index = i
                break
        return start_index, end_index

    def _find_table_beginning(self, line):
        if re.search(r".*(\w+)\smonths\sended.*", line, re.IGNORECASE):
            # collect period
            found_items = re.findall(r"(\w+) ?\n?months ?\n?ended", line, re.IGNORECASE | re.MULTILINE)
            periods = [w2n.word_to_num(period) for period in found_items]
            return periods

    def _find_tables_and_info(self, soup):
        cash_flow_sheet_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT", "CASH", "FLOWS"],
                                                  words_not_to_include=["CONTINUED"],
                                                  with_tag={"p", "b", "font", "div", "span"}))

        table, period, end_date = self._get_elements_between_tags(cash_flow_sheet_title, None, "table",
                                                                  stop_after_found_tag=True)
        if not table:
            raise Exception("Couldn't find the cash flow sheet table(s)")
        return table, period, end_date

    def _parse_html(self, table, period=None, end_date=None):
        table_html = str(table)
        df = self.parse_table(table_html, period, end_date)
        return df
