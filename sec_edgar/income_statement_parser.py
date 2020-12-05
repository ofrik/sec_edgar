import re

from word2number import w2n
import pandas as pd

from sec_edgar import Parser


class IncomeStatementParser(Parser):

    def _parse_raw(self, content):
        lines = content.replace("$", "").replace(",", "").split("\n")
        clean_lines = [re.sub(r" +", " ", line).strip() for line in lines if line]
        start_index = -1
        end_index = -1
        for i, line in enumerate(clean_lines):
            if start_index == -1 and re.search(r"(CONSOLIDATED STATEMENT (OF )?(EARNINGS|OPERATIONS))", line,
                                               re.MULTILINE) is not None:
                start_index = i
            if start_index != -1 and "=" in line:
                end_index = i
                break
        table_rows = clean_lines[start_index:end_index]
        periods = None
        num_columns = None
        rows = []
        for line in table_rows:
            if re.search(r".*(\w+) months ended.*", line, re.IGNORECASE):
                # collect period
                found_items = re.findall(r"(\w+) ?\n?months ?\n?ended", line, re.IGNORECASE | re.MULTILINE)
                periods = [w2n.word_to_num(period) for period in found_items]
                continue
            if periods and not num_columns:
                years = re.findall(r"\d{4}", line)
                if years:
                    num_columns = len(years)
                continue
            if num_columns:
                splits = line.rsplit(maxsplit=num_columns)
                if len(splits) == num_columns + 1 or len(splits) == 1:
                    rows.append(splits)
        complete_rows = []
        skip_next = False
        for i, row in enumerate(rows):
            if skip_next:
                skip_next = False
                continue
            if len(row) == num_columns + 1:
                found_item = re.search(r"[a-zA-Z]+", row[-1])
                if found_item:
                    new_row = " ".join(rows[i] + rows[i + 1]).rsplit(maxsplit=num_columns)
                    complete_rows.append(new_row)
                    skip_next = True
                    continue
            complete_rows.append(row)
            skip_next = False
        df = pd.DataFrame(complete_rows,
                          columns=["name"] + [f"period: {period}, {year}" for period in periods for year in years])
        df.replace(r"-+", "", inplace=True, regex=True)
        df.replace(r"_+", "", inplace=True, regex=True)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        # TODO check for other old reports
        return df

    def _parse_xbrl(self, soup):
        from xbrl import XBRLParser, GAAP, GAAPSerializer
        parser = XBRLParser()
        xbrl = parser.parse(open("test.xml"))
        output = parser.parseGAAP(xbrl)
        self._get_xbrl_tag(soup, "us-gaap:Revenues")
        pass

    def _find_multiple_words(self, tag, words=[], either=[], words_not_to_include=[]):
        text = tag.text.strip()
        if not text or tag.name in {"html", "body"}:
            return False
        matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE) is not None for word in
                   words]
        either_matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE) is not None for word in
                          either]
        negative_matches = [re.search(rf".*{word}.*", text, re.MULTILINE) is not None for word in
                            words_not_to_include]
        return sum(matches) == len(words) and sum(negative_matches) == 0 and sum(either_matches) == 1

    def _parse_html(self, soup):
        income_titles = soup.find(
            lambda tag: self._find_multiple_words(tag, ["CONSOLIDATED", "STATEMENT"],
                                                  ["INCOME", "EARNINGS"],
                                                  ["COMPREHENSIVE"]))
        table_html = str(income_titles.find_next("table"))
        df, period = self.parse_table(table_html)
        return df
