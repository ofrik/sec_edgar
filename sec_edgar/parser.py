from abc import abstractmethod
import re
import html

import pandas as pd
import numpy as np
import bs4 as bs
from bs4 import BeautifulSoup
from word2number import w2n
import dateutil.parser as dparser


class Parser(object):
    def parse(self, content, type, do_html_native=False):
        df = None
        parse_type = None
        if type == "html":
            soup = BeautifulSoup(content, "lxml")
            tables, period, end_date = self._find_tables_and_info(soup)
            # try:
            if do_html_native or True:
                df, parse_type = self._parse_html_native(tables, period, end_date), "native"
            else:
                df, parse_type = self._parse_html(tables, period, end_date), "pandas"
            # except Exception as e:
            #     print("Failed to parse html, try using native html parsing")
            #     df, parse_type = self._parse_html_native(tables, period, end_date), "native"
        else:
            df, parse_type = self._parse_raw(content), "raw"
        if df is not None:
            df.dropna(axis=1, how="all", inplace=True)
            self._drop_similar_columns(df)
            df = self._normalize_column_name(df)
        return df, parse_type

    def _find_balance_sheet_title(self, line):
        return re.search(r"CONSOLIDATED (STATEMENT )?(OF )?(FINANCIAL POSITION|BALANCE SHEETS?)", line,
                         re.MULTILINE | re.IGNORECASE)

    def _find_income_sheet_title(self, line):
        return re.search(r"(CONSOLIDATED STATEMENTS? (OF )?(EARNINGS?|OPERATIONS?|INCOME))", line,
                         re.MULTILINE | re.IGNORECASE)

    def _find_cash_flow_title(self, line):
        return re.search(
            r"(CONSOLIDATED STATEMENTS? (OF )?)?CASH FLOWS?|CONSOLIDATED STATEMENTS? (OF )?CASH", line,
            re.MULTILINE | re.IGNORECASE)

    def _find_dates(self, line):
        return re.findall(
            r"((?:January|Jan\.|February|Feb\.|March|Mar\.|April|Apr\.|May|June|Jun\.|July|Jul\.|August|Aug\.|September|Sep\.|October|Oct\.|November|Nov\.|December|Dec\.)\s[0-9]{1,2})",
            line, re.IGNORECASE)

    def _normalize_column_name(self, df):
        column_mapping = {}
        for col in df.columns[1:]:
            period = 3
            date_ = None
            year = None
            found_periods = self._find_table_beginning(col)
            if found_periods:
                period = found_periods[0]
            found_dates = self._find_dates(col)
            if found_dates:
                date_ = found_dates[0]
            found_years = re.findall(r"\d{4}", col)
            if found_years:
                year = found_years[0]
            column_name = f"period: {period}, {date_.lower()}, {year}"
            column_mapping[col] = column_name
        if column_mapping:
            df.rename(columns=column_mapping, inplace=True)
        return df

    def _is_element_before(self, e1, e2):
        current_e = e1
        while current_e and current_e.previous:
            if current_e.previous == e2:
                return True
            current_e = current_e.previous
        return False

    def _get_elements_between_tags(self, first_tag, second_tag, elements_tag, stop_after_found_tag=False):
        # TODO find values scale
        period = None
        end_date = None
        found_tags = []
        current_tag = first_tag
        while current_tag and current_tag.next:
            if current_tag == second_tag:
                break
            if current_tag.name == elements_tag:
                found_tags.append(current_tag)
                if stop_after_found_tag:
                    break
            if hasattr(current_tag, 'text') and not found_tags and current_tag.find("table") is None:
                if not end_date:
                    found_dates = self._find_dates(current_tag.text)
                    if found_dates:
                        end_date = [re.sub("\s+", " ", d) for d in found_dates]
                if not period:
                    period = self._find_table_beginning(current_tag.text)
            current_tag = current_tag.next
        return found_tags, period, end_date

    @abstractmethod
    def _find_tables_and_info(self, soup):
        raise NotImplementedError()

    @abstractmethod
    def _find_relevant_lines(self, lines):
        raise NotImplementedError()

    def _check_parent_tag(self, item, tags):
        current_item = item
        while current_item.parent:
            if current_item.parent.name in tags:
                return True
            current_item = current_item.parent
        return False

    def _count_contents(self, tag):
        count = 0
        for item in tag.children:
            if item.name is None or item.name in {"br"}:
                pass
            else:
                count += 1
        return count

    def _find_multiple_words(self, tag, words=[], either=[], words_not_to_include=[], with_tag={}):
        text = tag.text.strip()
        if not text or tag.name in {"html", "body"}:
            return False
        if ((with_tag and tag.name not in with_tag) or self._count_contents(tag) > 1) and re.search(
                rf"^{' '.join(words)}(?: OF)? (?:{'|'.join(either)})", text) is None:
            return False
        if len(text) > 200:
            return False

        matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE | re.IGNORECASE) is not None for word in
                   words]
        either_matches = [re.search(rf".*{word}S?.*", text, re.MULTILINE | re.IGNORECASE) is not None for word in
                          either]
        negative_matches = [re.search(rf".*{word}.*", text, re.MULTILINE | re.IGNORECASE) is not None for word in
                            words_not_to_include]
        found_it = sum(matches) == len(words) and sum(negative_matches) == 0 and (
            sum(either_matches) == 1 if either else True)
        if found_it and tag.find_parent("table") is not None:
            # we we shouldn't get something that's within a table
            return False
        return found_it

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

    def _parse_raw(self, content, period=None, end_date=None, preprocess_table=True):
        if preprocess_table:
            lines = content.replace("$", "").split("\n")
            clean_lines = [re.sub(r"\s+", " ", line).strip() for line in lines if line]
            start_index, end_index = self._find_relevant_lines(clean_lines)
            table_rows = self._clean_multipage_table(clean_lines[start_index:end_index])
        else:
            table_rows = content
        rows, num_columns, periods, years = self._lines_to_splitted_rows(table_rows, period, end_date)
        complete_rows = self._combine_rows(num_columns, rows)
        df = pd.DataFrame(complete_rows,
                          columns=["name"] + [f"period: {period}, {year}" for period in periods for year in
                                              sorted(set(years), key=lambda x: pd.to_datetime(x), reverse=True)])

        df.replace(r"^-+", "", inplace=True, regex=True)
        df.replace(r"(\x92|\x97|\x96|_||=|\+|\*|—)+", "", inplace=True, regex=True)
        df = df.replace("", np.nan).dropna(axis=0, how="all")
        df.replace(np.nan, "", inplace=True)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        return df

    @abstractmethod
    def _find_table_beginning(self, line):
        raise NotImplementedError()

    def _should_skip_line(self, line):
        if not line:
            return True
        if re.search(r"- ?[0-9]+ ?-", line) is not None:
            return True
        if re.search(r"ITEM \d+\.", line) is not None:
            return True
        if re.search(r"CONSOLIDATED STATEMENT OF EARNINGS.*", line) is not None:
            return True
        if re.search(r"\w{3,9} \d{1,2}$", line) is not None:
            return True
        if re.search(r"^(\d{4} ?){1,}", line) is not None:
            return True
        if "(Unaudited)" in line:
            return True
        if "Months" in line:
            return True
        if "restated" in line.lower():
            return True
        if "presentation" in line.lower():
            return True
        if line.isupper() and ":" not in line:
            return True
        if line == "<PAGE>" or (line.startswith("(") and line.endswith(")")):
            return True
        if line.lower().startswith("*"):
            return True
        return False

    def _lines_to_splitted_rows(self, table_rows, periods, end_date):
        num_columns = 0
        rows = []
        years = []
        dates = end_date
        content_beginning = None
        done_before_sequences = {
            'Pro forma'.lower()
        }
        done_sequences = {
            'Cash dividends per common share'.lower()
        }
        for line in table_rows:
            if not content_beginning:
                found_dates = self._find_dates(line)
                if found_dates:
                    if dates:
                        dates += found_dates
                    else:
                        dates = found_dates
            if periods is None:
                periods = self._find_table_beginning(line)
                # if periods is not None:
                #     continue
            if (periods or dates) and not content_beginning:
                separators = None  # re.search(r"((-|_){2,}\s+(-|_){2,})", line)
                if separators is not None or "<S>" in line or (":" in line and years) or (
                        not line and dates and periods and years):
                    content_beginning = True
                    if ":" not in line and years:
                        continue
            if (periods or dates) and not content_beginning:
                found_years = re.findall(r"\d{4}", line)
                if found_years:
                    years += found_years
                    num_columns = len(years)
                if dates and periods and years and len(dates) == len(years):
                    content_beginning = True
                continue
            if num_columns:
                line = re.sub(r"(-|\.){3,}", "",
                              line.replace("_", "").replace("=", "").replace(",", "").replace("*", "")).strip()
                if self._should_skip_line(line):
                    continue
                try:
                    if re.search("[0-9]?\.[0-9]*", line) is None and re.search(
                            r".*\s+[0-9.\(\)\-_]+\s+[0-9.\(\)\-_$]+", line, re.IGNORECASE) is None:
                        dparser.parse(line, fuzzy=True)
                        splits = [line]
                    else:
                        raise
                except:
                    if line.endswith(":"):
                        splits = [line]
                    elif "(" in line and ")" not in line:
                        splits = [line]
                    elif line in ["realizable value", "Assets", "Liabilities and Stockholders' Equity"]:
                        splits = [f"{line}:"]
                    elif "DISCONTINUED OPERATIONS" in line:
                        splits = [f"{line}:"]
                    elif line.startswith("Average number of common") or line.endswith("(millions)") or line.startswith(
                            "Adjustments to reconcile"):
                        splits = [f"{line}"]
                    else:
                        splits = line.rsplit(maxsplit=num_columns)
                        # r'[0-9.\(\)\-_—]+'
                        if sum([re.search(r'[0-9]?\.?[0-9\(\)\-_—]+', p) is not None for p in splits][
                               1:]) == num_columns:
                            pass
                        # if re.search(rf".+\s+[0-9.\(\)\-_—]+\s+[0-9.\(\)\-_—$]+", line, re.IGNORECASE):
                        #     splits = line.rsplit(maxsplit=num_columns)
                        elif re.search(r"[a-zA-Z]+", line) is not None:
                            splits = [line]
                        else:
                            continue
                if "<S>" not in line and splits:
                    if sum([done_sequence in splits[0].lower() for done_sequence in done_before_sequences]) == 0:
                        rows.append(splits)
                    else:
                        break
                    if splits[0].lower() in done_sequences:
                        break
        if not periods:
            periods = [3]
        if dates:
            if len(dates) == len(years):
                years = [f"{d} {year}" for d, year in zip(dates, years)]
            else:
                years = [f"{dates[0]} {year}" for year in years]
        return rows, num_columns, periods, years

    def _combine_rows(self, num_columns, rows):
        complete_rows = []
        i = 0
        while i < len(rows):
            row = rows[i]
            combined_rows = row
            if not combined_rows[-1].endswith(":"):
                while len(row) == 1 and i < len(rows) - 1:
                    i += 1
                    row = rows[i]
                    combined_rows += row
                    if row[-1].endswith(":"):
                        combined_rows = [" ".join(combined_rows)]
                        break
            if not combined_rows[-1].endswith(":") and re.search(r"[a-zA-Z]+", combined_rows[-1]):
                i += 1
                row = rows[i]
                combined_rows += row
            if len(combined_rows) > num_columns + 1:
                combined_rows = " ".join(combined_rows).rsplit(" ", maxsplit=num_columns)
            if combined_rows[0].endswith("and"):
                combined_rows[0] += f" {rows[i + 1][0]}"
                i += 1
            i += 1
            complete_rows.append(combined_rows)
        return complete_rows

    @abstractmethod
    def _parse_xbrl(self, soup):
        raise NotImplementedError()

    @abstractmethod
    def _parse_html(self, soup, period=None, end_date=None):
        raise NotImplementedError()

    @abstractmethod
    def _parse_html_native(self, tables, period=None, end_date=None):
        if not isinstance(tables, list):
            tables = [tables]
        dfs = []
        for table in tables:
            lines = []
            rows = table.find_all("tr")
            for row in rows:
                line = re.sub(r'\u200b', ' ', row.text)
                line = line.replace("(", " (")
                line = re.sub(r'(?<=[a-zA-Z\)])(?=[0-9])|\s+', ' ',
                              line.replace("\n", " ").replace("$", " ")).strip()
                line = re.sub(r'(?<=[a-zA-Z0-9\)])\((?=[0-9])', " (", line)
                line = re.sub(r'(?<=[a-zA-Z\)])—', " —", line)
                line = re.sub(r'\s\)', ')', line)
                line = re.sub(r'\(\s', '(', line)
                line = line.replace("Thre e", "Three")
                if line and re.search('visibility\s*:\s*hidden', row.attrs.get("style", ""), re.IGNORECASE) is None:
                    lines.append(line)
            df = self._parse_raw(lines, period, end_date, preprocess_table=False)
            dfs.append(df)
        return pd.concat(dfs)

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
        df = df[df[df.columns[0]] != '(Amounts may not add due to rounding.)']
        df = df[df[df.columns[0]] != '(The accompanying notes are an integral part of the  financial statements.)']
        df = df[df[df.columns[0]] != '* Reclassified to reflect discontinued operations  presentation.']
        df.rename(columns={df.columns[0]: "name"}, inplace=True)
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
        self._drop_columns_without_values(df)
        df.reset_index(drop=True, inplace=True)
        indexes_with_categories = [i for i, x in enumerate(df["name"].values) if not pd.isna(x) and x.endswith(":")]
        for col in df.columns[1:]:
            for i in indexes_with_categories:
                df.at[i, col] = np.nan
        return df

    def _drop_columns_without_values(self, df):
        columns_without_values = []
        for col in df.columns:
            if col != "name" and df[col].nunique() / len(df[col]) < 0.33:
                columns_without_values.append(col)
        df.drop(columns=columns_without_values, inplace=True)

    def _drop_similar_columns(self, df):
        columns_to_remove = []
        for i, col in enumerate(df.columns):
            for other_col in df.columns[i + 1:]:
                if df[col].equals(df[other_col]):
                    if len(col) > len(other_col):
                        columns_to_remove.append(other_col)
                    else:
                        columns_to_remove.append(col)
        if columns_to_remove:
            print(f"Removing duplicate columns: {columns_to_remove}")
            df.drop(columns=columns_to_remove, inplace=True)

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

    def parse_table(self, table_html, period=None, end_date=None):
        df = pd.read_html(table_html)
        if isinstance(df, list):
            df = df[0]
        if df.columns.nlevels > 1:
            raise Exception("Can't parse multilevel table that way")
        df = self._clean_the_table(df)
        df = self._combine_first_rows(df)
        df = self._combine_columns(df)
        df = self._combine_df_rows(df)
        df = df.drop(index=df[df["name"] == ""].index)
        df.replace(r", ", ",", regex=True, inplace=True)
        if len(df.columns) == 1:
            raise Exception("Couldn't find the columns")
        df = df[1:]
        # period = self._find_periods(df)
        for col in df.columns[1:]:
            df[col] = df[col].apply(self._fix_values)
        if end_date:
            column_mapping = {}
            for col in df.columns[1:]:
                found_dates = self._find_dates(col)
                if not found_dates:
                    column_mapping[col] = f"{end_date[0]} {col}"
            if column_mapping:
                df.rename(columns=column_mapping, inplace=True)
        if period:
            column_mapping = {}
            for col in df.columns[1:]:
                found_period = self._find_table_beginning(col)
                if not found_period:
                    column_mapping[col] = f"period: {period[0]}, {col}"
            if column_mapping:
                df.rename(columns=column_mapping, inplace=True)
        return df


if __name__ == '__main__':
    pass
