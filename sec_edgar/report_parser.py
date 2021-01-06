import os
import requests
import re
from datetime import datetime
import traceback

import warnings

warnings.filterwarnings("ignore")

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

    def _get_html_content(self, content, tag="html"):
        html_start = re.search(rf"<{tag}.*>", content, re.IGNORECASE | re.MULTILINE).start()
        html_end = re.search(rf"</{tag}>", content, re.IGNORECASE | re.MULTILINE).end()
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

    def _get_content(self, file_url, save=True):
        local_path = os.path.join(self.base_folder, file_url.split('/')[-1])
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf8") as f:
                content = f.read()
        else:
            response = requests.get(file_url, headers={'accept-encoding': 'gzip'})
            if response.status_code == 200:
                content = response.content.decode("utf8")
                if save:
                    if os.path.exists(local_path):
                        raise Exception("The file already exists")
                    with open(local_path, "w", encoding="utf8") as f:
                        f.write(content)
            else:
                raise ConnectionError(f"Couldn't get {file_url}")
        return content

    def _get_report_content(self, content):
        content_type = "html"
        if "<xbrl>" in content.lower():
            # found_html = re.search(r"<html.*>", content, re.IGNORECASE)
            # found_end_html = re.search(r"</html.*>", content, re.IGNORECASE)
            report_10_q_start = None
            report_10_q_end = None
            for item in re.finditer(r"<DESCRIPTION>(.+)", content, re.IGNORECASE):
                if report_10_q_start is None and "10-Q" in content[item.start():item.end()]:
                    report_10_q_start = item.end()
                    continue
                if report_10_q_start is not None:
                    report_10_q_end = item.start()
                    break
            if not report_10_q_end and not report_10_q_start:
                for item in re.finditer(r"<TYPE>(.+)", content, re.IGNORECASE):
                    if report_10_q_start is None and "10-Q" in content[item.start():item.end()]:
                        report_10_q_start = item.end()
                        continue
                    if report_10_q_start is not None:
                        report_10_q_end = item.start()
                        break
            if report_10_q_start and report_10_q_end:
                body_start = re.search(r"<body.*>", content[report_10_q_start:report_10_q_end], re.IGNORECASE)
                body_end = re.search(r"</body.*>", content[report_10_q_start:report_10_q_end], re.IGNORECASE)
                report_content = content[report_10_q_start + body_start.start():report_10_q_start + body_end.end()]
            else:
                report_content = content
            report_content = self._get_html_content(report_content, "body")
        elif "<html" in content.lower():
            report_content = self._get_html_content(content)
        else:
            content_type = "raw"
            report_content = content
        return report_content, content_type

    def parse(self, file_url, save=True):
        print(f"Parsing {file_url}")
        content = self._get_content(file_url, save)
        report_content, content_type = self._get_report_content(content)
        report_date = datetime.strptime(
            re.findall(r"CONFORMED PERIOD OF REPORT:[\s\t]+(\d+)", content)[0], "%Y%m%d")
        parsing_type = None
        all_tables = {}
        for parser in self.parsers:
            try:
                output, parsing_type = parser.parse(report_content, content_type, parsing_type == "native")
                # TODO validate the first column in 'name' and all the rest have some date in it
                if len(output) == 0:
                    raise Exception()
                if len(output.columns) not in [3, 5] or True:
                    print(f"columns: {len(output.columns)}, rows: {len(output)}\n{output.columns.tolist()}")
                all_tables[parser.__class__.__name__] = output
            except:
                print(f"Failed to parse {file_url} using {parser.__class__.__name__}")
                traceback.print_exc()
        return all_tables

    pass


if __name__ == '__main__':
    parser = ReportParser()
    # parser.add_parser(GeneralParser())
    parser.add_parser(IncomeStatementParser())
    parser.add_parser(BalanceSheetParser())
    parser.add_parser(CashFlowParser())

    parser.parse("https://www.sec.gov/Archives/edgar/data/18230/0000950131-99-004925.txt")
