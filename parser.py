from abc import abstractmethod
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from word2number import w2n
import re


class Parser(object):
    def parse(self, xml_content, type):
        soup = BeautifulSoup(xml_content, parser="lxml", features="lxml")
        if type == "html":
            return self._parse_html(soup)
        else:
            return self._parse_xbrl(soup)

    @abstractmethod
    def _parse_xbrl(self, soup):
        raise NotImplementedError()

    @abstractmethod
    def _parse_html(self, soup):
        raise NotImplementedError()

    def fix_values(self, x):
        if not x:
            return x
        x = x.replace("\x97", "0").replace(",", "")
        x = x.strip("$")
        if x.startswith("(") or x.endswith(")"):
            x = "-" + x.strip("()")
        return float(x) if "." in x else int(x)

    def parse_table(self, table_html):
        df = pd.read_html(table_html)
        if isinstance(df, list):
            df = df[0]
        df.dropna(how="all", inplace=True, axis=0)
        df.dropna(how="all", inplace=True, axis=1)
        df.rename(columns={0: "name"}, inplace=True)
        first_row = df.iloc[0]
        period_items = [item for item in first_row if not pd.isna(item) and "months ended" in item]
        period = 3
        if len(period_items) > 0:
            period = w2n.word_to_num(re.findall("(\w+) ?\n?months ?\n?ended", period_items[0])[0])
            df.drop(0, inplace=True)
            df.reset_index(inplace=True, drop=True)
            first_row = df.iloc[0]
        columns_ids = []
        for i, v in enumerate(first_row):
            if not pd.isna(v):
                columns_ids.append(i)
        columns_ids = columns_ids[:2]
        diffs = []
        for i in range(len(columns_ids) - 1):
            diffs.append(abs(columns_ids[i] - columns_ids[i + 1]))
        all_diff_are_the_same = sum([d != diffs[0] for d in diffs[1:]]) == 0
        df = df.replace(np.nan, "")
        for col in df.columns:
            df[col] = df[col].astype(str)
        columns_ids = columns_ids[:1]
        if all_diff_are_the_same:
            columns_names = ["name"]
            diff = diffs[0]
            for i, key in enumerate(df.columns):
                if i in columns_ids:
                    series = [df[df.columns[i + d]] for d in range(diff) if i + d < len(df.columns)]
                    first_col = series[0]
                    for other_col in series[1:]:
                        first_col = first_col + other_col
                    columns_names.append(first_col[0])
                    first_col.iloc[0] = ""
                    df[columns_names[-1]] = first_col
            df = df[columns_names]
            # fix values
            df["name"] = df["name"].apply(lambda x: x.replace("\x92", ""))

            for col in columns_names[1:]:
                df[col] = df[col].apply(self.fix_values)

            df = df.replace("", np.nan)
            df.dropna(how="all", inplace=True)
            # df.dropna(subset=columns_names[1:], how="all", inplace=True)
            return df, period
        else:
            print("There is inconsistent diff")


if __name__ == '__main__':
    pass
