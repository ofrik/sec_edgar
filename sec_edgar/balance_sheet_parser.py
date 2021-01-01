import re

import pandas as pd

from sec_edgar import Parser


class BalanceSheetParser(Parser):

    def _find_relevant_lines(self, clean_lines):
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(r"CONSOLIDATED (STATEMENT )?(OF )?(FINANCIAL POSITION|BALANCE SHEETS)",
                                               line,
                                               re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and (re.search(r"(CONSOLIDATED STATEMENT (OF )?)?CASH( FLOWS?)?", line,
                                                re.MULTILINE) is not None):
                end_index = i
                break
        return start_index, end_index

    def _find_table_beginning(self, line):
        found_reg = re.search(
            r".*(?:At )?((?:January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{1,2}).*",
            line, re.IGNORECASE)
        if found_reg is not None:
            return [3]

    def _combine_df_rows(self, df):
        df = self._combine_with_next_if_exists(df, r"Notes.*\(net.*(?<!\))$", regex=True)
        df = self._combine_with_next_if_exists(df, r"Other accounts.*\(net.*(?<!\))$", regex=True)
        df = self._combine_with_next_if_exists(df, r"Long-term.*\(net.*(?<!\))$", regex=True)
        df = self._combine_with_next_if_exists(df, r"Short-term.*\(net.*(?<!\))$", regex=True)
        return df

    def _find_tables_and_info(self, soup):
        balance_sheet_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED"],
                                                  ["FINANCIAL POSITION", "BALANCE SHEET"],
                                                  with_tag={"p", "b", "font", "div", "span"}))
        title_limit = None
        shareholders_equity_title = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT", "SHAREHOLDERS’", "EQUITY"],
                                                  with_tag={"p", "b", "font", "div", "span"}))
        if shareholders_equity_title is None:
            cash_flow_sheet_title = soup.find(
                lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT", "CASH", "FLOWS"],
                                                      words_not_to_include=["CONTINUED"],
                                                      with_tag={"p", "b", "font", "div", "span"}))
            title_limit = cash_flow_sheet_title
        else:
            title_limit = shareholders_equity_title

        tables, period, end_date = self._get_elements_between_tags(balance_sheet_title, title_limit, "table")
        if not tables:
            raise Exception("Couldn't find the balance sheet table(s)")
        return tables, period, end_date

    def _parse_html(self, tables, period=None, end_date=None):
        dfs = []
        for table in tables:
            table_html = str(table)
            df = self.parse_table(table_html)
            dfs.append(df)
        return pd.concat(dfs)
