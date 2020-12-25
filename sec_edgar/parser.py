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

    def _get_elements_between_tags(self, first_tag, second_tag, elements_tag):
        found_tags = []
        current_tag = first_tag
        while current_tag and current_tag.next:
            if current_tag == second_tag:
                break
            if current_tag.name == elements_tag:
                found_tags.append(current_tag)
            current_tag = current_tag.next
        return found_tags

    @abstractmethod
    def _find_relevant_lines(self, lines):
        raise NotImplementedError()

    def _find_multiple_words(self, tag, words=[], either=[], words_not_to_include=[], with_tag={}):
        text = tag.text.strip()
        if not text or tag.name in {"html", "body"}:
            return False
        if with_tag and tag.name not in with_tag:
            return False
        matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE) is not None for word in
                   words]
        either_matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE) is not None for word in
                          either]
        negative_matches = [re.search(rf".*{word}.*", text, re.MULTILINE) is not None for word in
                            words_not_to_include]
        return sum(matches) == len(words) and sum(negative_matches) == 0 and (
            sum(either_matches) == 1 if either else True)

    def _clean_multipage_table(self, lines):
        clean_lines = []
        finished_page = False
        finished_table = False
        started_table = False
        in_content = False
        can_filter_out_of_content = False
        for i, line in enumerate(lines):
            if re.search(r"</Table>", line, re.IGNORECASE):
                finished_table = True
                started_table = False
                in_content = False
                can_filter_out_of_content = True
            if re.search(r"<Table>", line, re.IGNORECASE):
                finished_table = False
                started_table = True
            if started_table and "<S>" in line:
                in_content = True
            if re.search(r"$- [0-9]+ -", line):
                finished_page = True
            if "<S>" in line:
                finished_page = False
            if finished_page or finished_table or (not in_content and can_filter_out_of_content):
                continue
            clean_lines.append(line)
        return clean_lines

    def _parse_raw(self, content):
        lines = content.replace("$", "").replace(",", "").split("\n")
        clean_lines = [re.sub(r" +", " ", line).strip() for line in lines if line]
        start_index, end_index = self._find_relevant_lines(clean_lines)
        table_rows = self._clean_multipage_table(clean_lines[start_index:end_index])
        rows, num_columns, periods, years = self._lines_to_splitted_rows(table_rows)
        complete_rows = self._combine_rows(num_columns, rows)
        df = pd.DataFrame(complete_rows,
                          columns=["name"] + [f"period: {period}, {year}" for period in periods for year in
                                              sorted(set(years), reverse=True)])

        df.replace(r"^-+", "", inplace=True, regex=True)
        df.replace(r"_+", "", inplace=True, regex=True)
        df.replace(r"=+", "", inplace=True, regex=True)
        df.replace(r"\*", "", inplace=True, regex=True)
        df = df.replace("", np.nan).dropna(axis=0, how="all")
        df.replace(np.nan, "", inplace=True)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        return df

    @abstractmethod
    def _find_table_beginning(self, line):
        raise NotImplementedError()

    def _lines_to_splitted_rows(self, table_rows):
        # TODO better splitting, find pattern
        periods = None
        num_columns = 0
        rows = []
        years = []
        content_beginning = None
        for line in table_rows:
            if periods is None:
                periods = self._find_table_beginning(line)
                if periods is not None:
                    continue
            if not content_beginning:
                separators = re.search(r"((-|_){2,}\s+(-|_){2,})", line)
                if separators is not None:
                    content_beginning = True
                    continue
            if periods and not content_beginning:
                found_years = re.findall(r"\d{4}", line)
                if found_years:
                    years += found_years
                    num_columns = len(years)
                continue
            if num_columns:
                if re.search(r"- ?[0-9]+ ?-", line) is not None:
                    continue
                if re.search(r"ITEM \d+\.", line) is not None:
                    continue
                if re.search(r"CONSOLIDATED STATEMENT OF EARNINGS.*", line) is not None:
                    continue
                if re.search(r"\w{3,9} \d{1,2}$", line) is not None:
                    continue
                if re.search(r"^(\d{4} ?){1,}", line) is not None:
                    continue
                if re.search(r"shares authorized", line, re.IGNORECASE) is not None:
                    continue
                if "(Unaudited)" in line:
                    continue
                if "Months" in line:
                    continue
                if line.isupper():
                    continue
                if line == "<PAGE>" or (line.startswith("(") and line.endswith(")")):
                    continue
                if line.lower().startswith("*"):
                    continue
                if line.endswith(":"):
                    splits = [line]
                elif line in ["realizable value", "Assets", "Liabilities and Stockholders' Equity"]:
                    splits = [f"{line}:"]
                elif "DISCONTINUED OPERATIONS" in line:
                    splits = [f"{line}:"]
                elif line.startswith("Average number of common") or line.endswith("(millions)"):
                    splits = [f"{line}"]
                else:
                    splits = line.rsplit(maxsplit=num_columns)
                if "<S>" not in line and splits:
                    rows.append(splits)
                    if splits[0].lower() == 'Cash dividends per common share'.lower():
                        break
        return rows, num_columns, periods, years

    def _combine_rows(self, num_columns, rows):
        complete_rows = []
        skip_next = False
        for i, row in enumerate(rows):
            if skip_next:
                skip_next = False
                continue
            found_item = re.search(r"[a-zA-Z]+", row[-1])
            if found_item is None and len(row) > 1:
                found_item = row[-2] == "receivable" and row[-1] == "-"
            if len(row) == num_columns + 1 or (found_item and not row[0].endswith(":")) or row[
                0].lower().endswith("and") or row[0].lower().endswith("common"):
                if row[0].lower().endswith("common"):
                    row_name = " ".join([rows[i][0], rows[i + 1][0]])
                    new_row = [row_name]
                    complete_rows.append(new_row)
                    skip_next = True
                    continue
                if i < len(rows) - 1 and rows[i + 1] == ['realizable value:']:
                    new_row = " ".join(rows[i] + rows[i + 1])
                    complete_rows.append([new_row])
                    skip_next = True
                    continue
                if found_item:
                    new_row = " ".join(rows[i] + rows[i + 1]).rsplit(maxsplit=num_columns)
                    complete_rows.append(new_row)
                    skip_next = True
                    continue
                if row[0].lower().endswith("and"):
                    row_name = " ".join([rows[i][0], rows[i + 1][0]])
                    new_row = " ".join([row_name] + rows[i][1:]).rsplit(maxsplit=num_columns)
                    complete_rows.append(new_row)
                    skip_next = True
                    continue
            complete_rows.append(row)
            skip_next = False
        return complete_rows

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
        df.replace("\u200b", np.nan, inplace=True)
        df.dropna(how="all", inplace=True, axis=0)
        df.dropna(how="all", inplace=True, axis=1)
        # still_empty_columns = df.columns[(df.nunique() == 1).values].tolist()
        # df.drop(columns=still_empty_columns, inplace=True)
        # still_empty_rows = df.index[(df.nunique(axis=1) == 1).values].tolist()
        # df.drop(index=still_empty_rows, inplace=True)
        df = df[df[0] != '(Amounts may not add due to rounding.)']
        df = df[df[0] != '(The accompanying notes are an integral part of the  financial statements.)']
        df = df[df[0] != '* Reclassified to reflect discontinued operations  presentation.']
        df.rename(columns={0: "name"}, inplace=True)
        df.replace("\x92", "", inplace=True, regex=True)
        df.replace("\x97", "", inplace=True, regex=True)
        df.replace("\xa0", " ", inplace=True, regex=True)
        df.replace('–', "", inplace=True)
        df.replace('—', "", inplace=True)
        df.replace(r', ', ",", inplace=True, regex=True)
        df.replace(r'\n', "", inplace=True, regex=True)
        df.replace(" +", " ", regex=True, inplace=True)
        df.replace(r"\*", "", regex=True, inplace=True)
        df.replace(r"\(Unaudited\)", "", regex=True, inplace=True)
        df = df[df[1:].dropna(how="all", axis=1).columns.tolist()]
        columns_without_values = []
        for col in df.columns:
            if col != "name" and df[col].nunique() / len(df[col]) < 0.33:
                columns_without_values.append(col)
        df.drop(columns=columns_without_values, inplace=True)
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
        unique_rows = [x for x in first_row[1:].unique() if x]
        indexes_to_combine = {}
        for row_type in unique_rows:
            indexes = []
            for i in first_row.index:
                if first_row[i] == row_type:
                    indexes.append(i)
            if len(indexes) >= 1:
                indexes_to_combine[row_type] = indexes
        for col_name in indexes_to_combine:
            if "name" in indexes_to_combine[col_name]:
                new_column_name = "name"
            else:
                new_column_name = re.sub(r", ", ",", col_name)
            df[new_column_name] = df[indexes_to_combine[col_name]].agg(self._selective_join, axis=1)
        df.drop(columns=first_row[1:].index.tolist(), inplace=True)
        return df

    def _combine_df_rows(self, df):
        return df

    def _combine_with_next_if_exists(self, df, string, regex=False):
        df.reset_index(drop=True, inplace=True)
        df_ = df[df["name"].str.contains(string, regex=regex)]
        if len(df_) > 0:
            index = df_.index[0]
            for col in df.columns:
                df.at[index, col] = f"{df.at[index, col]} {df.at[index + 1, col]}".strip()
            df.drop(index=[index + 1], inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    def parse_table(self, table_html):
        df = pd.read_html(table_html)
        if isinstance(df, list):
            df = df[0]
        df = self._clean_the_table(df)
        df = self._combine_first_rows(df)
        df = self._combine_columns(df)
        df = self._combine_df_rows(df)
        df = df.drop(index=df[df["name"] == ""].index)
        df.replace(r", ", ",", regex=True, inplace=True)
        df = df[1:]
        # period = self._find_periods(df)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        return df, 3


if __name__ == '__main__':
    pass
