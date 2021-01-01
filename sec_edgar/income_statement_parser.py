import re

from word2number import w2n
import pandas as pd

from sec_edgar import Parser


class IncomeStatementParser(Parser):

    def _find_relevant_lines(self, clean_lines):
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(r"(CONSOLIDATED STATEMENTS? (OF )?(EARNINGS|OPERATIONS|INCOME))", line,
                                               re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and re.search(r"CONSOLIDATED (STATEMENT )?(OF )?(FINANCIAL POSITION|BALANCE SHEETS)",
                                               line,
                                               re.MULTILINE) is not None:
                end_index = i
                break
        return start_index, end_index

    def _find_table_beginning(self, line):
        if re.search(r".*(\w+) months(?: ended)?.*", line, re.IGNORECASE):
            # collect period
            found_items = re.findall(r"(\w+) ?\n?months(?: ?\n?ended)?", line, re.IGNORECASE | re.MULTILINE)
            periods = [w2n.word_to_num(period) for period in found_items]
            return periods

    def _combine_df_rows(self, df):
        df = self._combine_with_next_if_exists(df, "^Income tax (expense)/benefit related to items of$", regex=True)
        df = self._combine_with_next_if_exists(df, "^Intellectual property and custom$", regex=True)
        df = self._combine_with_next_if_exists(df, "^Income from continuing operations before$", regex=True)
        return df

    def _find_tables_and_info(self, soup):
        income_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT"],
                                                  ["INCOME", "EARNINGS", "OPERATIONS"],
                                                  ["COMPREHENSIVE", "CONTINUED"],
                                                  with_tag={"p", "b", "font", "span", "div"}))
        balance_sheet_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED"],
                                                  either=["FINANCIAL POSITION", "BALANCE SHEET"],
                                                  words_not_to_include=["CONTINUED"],
                                                  with_tag={"p", "b", "font", "span", "div"}))
        tables, period, end_date = self._get_elements_between_tags(income_title, balance_sheet_title, "table")
        if not tables:
            raise Exception("Couldn't find the income sheet table(s)")
        return tables, period, end_date

    def _parse_html(self, tables, period=None, end_date=None):
        dfs = []
        for table in tables:
            table_html = str(table)
            table_html = table_html.replace("Thre e", "Three")  # an issue with 2005
            df, period = self.parse_table(table_html)
            dfs.append(df)
        return pd.concat(dfs)
