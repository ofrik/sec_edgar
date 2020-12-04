from datetime import datetime
import pandas as pd
import requests
import os
import json
from tqdm import tqdm
import json


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
        output_path = os.path.join(self._output_folder, f"{year}_{quarter}.index.json")
        if os.path.exists(output_path):
            with open(output_path, "r") as f:
                return json.load(f)
        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
        response = requests.get(url)
        if response.status_code == 200:
            output = self.get_reports_paths(response.content.decode("utf8"), year, quarter)
            with open(output_path, "w") as f:
                json.dump(output, f)
            return output
        else:
            raise Exception(f"Failed to get data from {url}")

    def get_reports_paths(self, master_idx, year, quarter):
        content_lines = master_idx.splitlines()
        data = []
        for line in content_lines:
            if line.startswith("CIK"):
                columns = line.split("|")
            else:
                if line.endswith(".txt"):
                    data.append(line.split("|"))
        df = pd.DataFrame(data, columns=columns)
        only_quarter = df[df["Form Type"] == "10-Q"]
        only_quarter["Filename"] = only_quarter["Filename"].apply(lambda x: f"https://www.sec.gov/Archives/{x}")
        output = pd.Series(only_quarter.Filename.values, index=only_quarter.CIK).to_dict()
        return output

    def get_reports(self, parser, from_year, from_quarter, to_year=datetime.today().year,
                    to_quarter=pd.Timestamp(datetime.today()).quarter - 1):
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
            print(f"Getting {current_year}-{current_quarter}")

            quarter_index = self.get_quarter_index(current_year, current_quarter)
            cik_files = quarter_index[f"{current_year}-{current_quarter}"]
            for symbol in tqdm(self._symbols, leave=False):
                try:
                    symbol_file = cik_files[self._ciks_map[symbol]]
                    report = parser.parse(symbol_file, save=True)
                except:
                    print(f"Failed to get {symbol}")

            current_quarter += 1
            if current_quarter % 5 == 0:
                current_quarter = 1
                current_year += 1


if __name__ == '__main__':
    edgar_sec = SecEdgar(["AAPL", "IBM"])
    edgar_sec.get_quarter_index(2008, 1)
    pass
