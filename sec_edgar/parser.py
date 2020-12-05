from abc import abstractmethod
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from word2number import w2n
import re


class Parser(object):
    def parse(self, content, type):

        if type == "html":
            soup = BeautifulSoup(content, "lxml")
            return self._parse_html(soup)
        else:
            return self._parse_raw(content)

    def _get_xbrl_tag(self, soup, name):
        tag = soup.find(attrs={"name": name})
        scale = int(tag.attrs["scale"])
        value = self._fix_values(tag.text) * scale
        return value

    @abstractmethod
    def _parse_raw(self, content):
        raise NotImplementedError()

    @abstractmethod
    def _parse_xbrl(self, soup):
        raise NotImplementedError()

    @abstractmethod
    def _parse_html(self, soup):
        raise NotImplementedError()

    def _fix_values(self, x):
        if not x:
            return x
        x = x.replace("\x97", "0").replace(",", "")
        x = x.strip("$")
        if x.startswith("(") or x.endswith(")"):
            x = "-" + x.strip("()")
        return float(x) if "." in x else int(x)

    def _clean_the_table(self, df):
        df = df.replace("\u200b", np.nan)
        df.dropna(how="all", inplace=True, axis=0)
        df.dropna(how="all", inplace=True, axis=1)
        # still_empty_columns = df.columns[(df.nunique() == 1).values].tolist()
        # df.drop(columns=still_empty_columns, inplace=True)
        # still_empty_rows = df.index[(df.nunique(axis=1) == 1).values].tolist()
        # df.drop(index=still_empty_rows, inplace=True)
        df.rename(columns={0: "name"}, inplace=True)
        df = df.replace("\x92", "")
        df = df.replace("\x97", "")
        df = df.replace("\xa0", " ")
        df = df[df[1:].dropna(how="all", axis=1).columns.tolist()]
        return df

    def _combine_first_rows(self, df):
        df = df.replace(np.nan, "")
        new_row = df.iloc[0].str.cat(df.iloc[1])
        df.drop(index=df.index[0], inplace=True)
        df.iloc[0] = new_row
        return df

    def _find_period(self, df):
        period_items = [item for item in df.columns if not pd.isna(item) and "months ended" in item.lower()]
        period = 3
        if len(period_items) > 0:
            period = w2n.word_to_num(
                re.findall("(\w+) ?\n?months ?\n?ended", period_items[0], re.IGNORECASE | re.MULTILINE)[0])
            df.drop(index=df.index[0], inplace=True)
            df.reset_index(inplace=True, drop=True)
            first_row = df.iloc[0]
        pass

    def _selective_join(self, lst):
        return "".join(lst.unique())

    def _combine_columns(self, df):
        first_row = df.iloc[0]
        unique_rows = first_row[1:].unique()
        indexes_to_combine = {}
        for row_type in unique_rows:
            indexes = []
            for i in first_row.index:
                if first_row[i] == row_type:
                    indexes.append(i)
            if len(indexes) > 1:
                indexes_to_combine[row_type] = indexes
        for col_name in indexes_to_combine:
            df[col_name] = df[indexes_to_combine[col_name]].agg(self._selective_join, axis=1)
        df.drop(columns=first_row[1:].index.tolist(), inplace=True)
        return df

    def parse_table(self, table_html):
        df = pd.read_html(table_html)
        if isinstance(df, list):
            df = df[0]
        df = self._clean_the_table(df)
        df = self._combine_first_rows(df)
        df = self._combine_columns(df)
        df = df[1:]
        # period = self._find_periods(df)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        return df, 3


if __name__ == '__main__':
    pass
