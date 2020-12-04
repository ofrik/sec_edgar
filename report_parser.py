import os
import requests
import re
from datetime import datetime
import traceback
from balance_sheet_parser import BalanceSheetParser
from cash_flow_parser import CashFlowParser
from general_parser import GeneralParser
from income_statement_parser import IncomeStatementParser
from parser import Parser


class ReportParser(Parser):
    def __init__(self, output_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")):
        self.base_folder = output_folder
        self.parsers = []

    def add_parser(self, parser):
        self.parsers.append(parser)

    def _get_html_content(self, content):
        html_start = content.find("<HTML>")
        if html_start == -1:
            html_start = content.find("<html>")
        html_end = content.find("</HTML>")
        if html_end == -1:
            html_end = content.find("</html>")
        html_end += len("</html>")
        return content[html_start:html_end]

    def _get_xbrl_content(self, content):
        xbrl_start = content.find("<XBRL>")
        if xbrl_start == -1:
            xbrl_start = content.find("<xbrl>")
        xbrl_end = content.find("</XBRL>")
        if xbrl_end == -1:
            xbrl_end = content.find("</xbrl>")
        xbrl_end += len("</xbrl>")
        return content[xbrl_start:xbrl_end]

    def parse(self, file_url, save=True):
        # TODO check if it's not exists already
        response = requests.get(file_url)
        if response.status_code == 200:
            content = response.content.decode("utf8")
            if "<xbrl>" in content.lower():
                content_type = "xbrl"
                report_content = self._get_xbrl_content(content)
            else:
                content_type = "html"
                report_content = self._get_html_content(content)
            report_date = datetime.strptime(
                re.findall(r"CONFORMED PERIOD OF REPORT:[\s\t]+(\d+)", content)[0], "%Y%m%d")
            for parser in self.parsers:
                try:
                    output = parser.parse(report_content, content_type)
                except:
                    print(f"Failed to parse {file_url} using {parser.__class__.__name__}")
                    traceback.print_exc()
            pass
        else:
            raise Exception(f"Couldn't get {file_url}")

    pass


if __name__ == '__main__':
    parser = ReportParser()
    parser.add_parser(GeneralParser())
    parser.add_parser(IncomeStatementParser())
    parser.add_parser(BalanceSheetParser())
    parser.add_parser(CashFlowParser())
    parser.parse("https://www.sec.gov/Archives/edgar/data/1000045/0001193125-08-025292.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/000032019320000010/0000320193-20-000010.txt")
