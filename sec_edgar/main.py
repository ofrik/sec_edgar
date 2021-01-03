import traceback

from datetime import datetime
import requests
import os
import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from tqdm import tqdm

from sec_edgar import BalanceSheetParser
from sec_edgar import CashFlowParser
from sec_edgar import GeneralParser
from sec_edgar import IncomeStatementParser
from sec_edgar import ReportParser


class SecEdgar(object):
    def __init__(self, symbols,
                 output_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")):
        self._symbols = set(symbols)
        self._output_folder = output_folder
        if output_folder is not None:
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
        self._ciks_map = self.get_cik(symbols)

    def get_cik(self, symbols):
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url)
        if response.status_code == 200:
            all_data = json.loads(response.content)
            symbol_to_cik_map = {all_data[i]["ticker"]: all_data[i]["cik_str"] for i in all_data if
                                 all_data[i]["ticker"] in symbols}
            return symbol_to_cik_map
        else:
            raise Exception("Failed to get ticker company map")
        pass

    def get_quarter_index(self, year, quarter):
        if year < 1994:
            raise Exception("The earliest year accessible is 1994")
        print(f"Getting {year}-{quarter}")
        output_path = os.path.join(self._output_folder, f"{year}_{quarter}.index.json")
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                return json.load(f)
        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
        response = requests.get(url)
        if response.status_code == 200:
            output = self.get_reports_paths(response.content.decode("utf8", errors="ignore"))
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output, f)
            return output
        else:
            raise Exception(f"Failed to get data from {url}")

    def get_reports_paths(self, master_idx):
        content_lines = master_idx.splitlines()
        data = []
        for line in content_lines:
            if line.startswith("CIK"):
                columns = line.split("|")
            else:
                if line.endswith(".txt"):
                    data.append(line.split("|"))
        df = pd.DataFrame(data, columns=columns)
        annual_and_quarterly_forms = df[(df["Form Type"] == "10-Q") | (df["Form Type"] == "10-K")]
        annual_and_quarterly_forms["Filename"] = annual_and_quarterly_forms["Filename"].apply(
            lambda x: f"https://www.sec.gov/Archives/{x}")
        output = annual_and_quarterly_forms[["CIK", "Form Type", "Filename"]].groupby(by=["CIK", "Form Type"])[
            "Filename"].apply(list).to_dict()
        output = {"_".join(k): v for k, v in output.items()}
        return output

    def get_specific_report(self, symbol, quarter_index, report_type):
        symbol_files = quarter_index.get(f"{self._ciks_map[symbol]}_{report_type}", None)
        if not symbol_files:
            raise Exception(f"Couldn't find files for {symbol}")
        if len(symbol_files) > 1:
            print("There are multiple files, check out the differences")
            raise Exception("There are multiple files, we don't know how to handle that in the meanwhile")
        report = parser.parse(symbol_files[0], save=True)
        return report

    def get_reports(self, parser, from_year, from_quarter, to_year=datetime.today().year,
                    to_quarter=pd.Timestamp(datetime.today()).quarter - 1, report_type="10-Q"):
        max_year = datetime.today().year
        max_quarter = pd.Timestamp(datetime.today()).quarter - 1
        if to_year > max_year:
            to_year = max_year
            to_quarter = min(max_quarter, to_quarter)
        if to_year == max_year:
            to_quarter = min(max_quarter, to_quarter)

        current_year = from_year
        current_quarter = from_quarter

        while current_year < to_year or (current_year == to_year and current_quarter <= to_quarter):
            quarter_index = self.get_quarter_index(current_year, current_quarter)
            pbar = tqdm(total=len(self._symbols), leave=False, desc=f"Q{current_quarter} {current_year}")
            with ThreadPoolExecutor(5) as executor:
                futures = [executor.submit(self.get_specific_report, symbol, quarter_index, report_type) for symbol in
                           self._symbols]
                for future in futures:
                    try:
                        output = future.result()
                    except Exception as e:
                        pass
                    finally:
                        pbar.update(1)
            pbar.close()

            current_quarter += 1
            if current_quarter % 5 == 0:
                current_quarter = 1
                current_year += 1


if __name__ == '__main__':
    edgar_sec = SecEdgar(["AAPL", "IBM", "LVS", "A"])
    # edgar_sec = SecEdgar(["CAT"])  # CAT # F
    # edgar_sec.get_quarter_index(1994, 1)
    parser = ReportParser()
    # parser.add_parser(GeneralParser())
    parser.add_parser(IncomeStatementParser())
    parser.add_parser(BalanceSheetParser())
    parser.add_parser(CashFlowParser())
    edgar_sec.get_reports(parser, from_year=1994, from_quarter=1)
    pass
