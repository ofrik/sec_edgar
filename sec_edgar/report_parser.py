import os
import requests
import re
from datetime import datetime
import traceback
from sec_edgar import Parser
from sec_edgar import BalanceSheetParser
from sec_edgar import CashFlowParser
from sec_edgar import GeneralParser
from sec_edgar import IncomeStatementParser


class ReportParser(Parser):
    def __init__(self, output_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")):
        self.base_folder = output_folder
        self.parsers = []

    def add_parser(self, parser):
        self.parsers.append(parser)

    def _get_html_content(self, content):
        html_start = re.search(r"<html.*>", content, re.IGNORECASE | re.MULTILINE).start()
        html_end = re.search(r"</html>", content, re.IGNORECASE | re.MULTILINE).end()
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
        # TODO the reports before the last quarter of 2003 are in different format
        response = requests.get(file_url)
        if response.status_code == 200:
            content = response.content.decode("utf8")
            content_type = "html"
            if "<xbrl>" in content.lower():
                report_content = self._get_xbrl_content(content)
                report_content = self._get_html_content(report_content)
            elif "<html" in content.lower():
                report_content = self._get_html_content(content)
            else:
                content_type = "raw"
                report_content = content
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
    # parser.add_parser(GeneralParser())
    parser.add_parser(IncomeStatementParser())
    # parser.add_parser(BalanceSheetParser())
    # parser.add_parser(CashFlowParser())
    parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-94-001226.txt")  # IBM 1994
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000100547701501962/0001005477-01-501962.txt")  # IBM 2001
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465909026661/0001104659-09-026661.txt")  # IBM 2009
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000155837020011799/0001558370-20-011799.txt")  # APPL 2020
