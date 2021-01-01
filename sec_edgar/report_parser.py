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
            response = requests.get(file_url)
            if response.status_code == 200:
                content = response.content.decode("utf8")
                if save:
                    if os.path.exists(local_path):
                        raise Exception("The file already exists")
                    with open(local_path, "w", encoding="utf8") as f:
                        f.write(content)
            else:
                raise Exception(f"Couldn't get {file_url}")
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
        for parser in self.parsers:
            try:
                output, parsing_type = parser.parse(report_content, content_type, parsing_type == "native")
                # TODO validate the first column in 'name' and all the rest have some date in it
                if len(output) == 0:
                    raise Exception()
                if len(output.columns) not in [3, 5] or True:
                    print(f"columns: {len(output.columns)}, rows: {len(output)}\n{output.columns.tolist()}")
            except:
                print(f"Failed to parse {file_url} using {parser.__class__.__name__}")
                traceback.print_exc()
        pass

    pass


if __name__ == '__main__':
    parser = ReportParser()
    # parser.add_parser(GeneralParser())
    # parser.add_parser(IncomeStatementParser())
    # parser.add_parser(BalanceSheetParser())
    parser.add_parser(CashFlowParser())
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001104659-04-021678.txt")  # strange columns
    parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001104659-04-013278.txt")  # strange columns
    parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-04-013021.txt")  # strange columns
    parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-04-022384.txt")  # strange columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-94-000002.txt")  # AAPL 1994
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-95-000003.txt")  # AAPL 1995
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-96-000002.txt")  # AAPL 1996
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-97-000002.txt")  # AAPL 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-98-000006.txt")  # AAPL 1998
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-99-000002.txt")  # AAPL 1999
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-99-000004.txt")  # AAPL 1999
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000912057-00-033901.txt")  # AAPL 2000
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000912057-01-515409.txt")  # AAPL 2001
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000912057-01-528148.txt")  # AAPL 2001
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000912057-02-004945.txt")  # AAPL 2002
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000912057-02-030796.txt")  # AAPL 2002
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-04-022384.txt")  # AAPL 2004
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-05-020421.txt")  # AAPL 2005
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-05-035792.txt")  # AAPL 2005
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-06-084286.txt")  # AAPL 2006
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-07-037745.txt")  # AAPL 2007
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001104659-07-059873.txt")  # AAPL 2007
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001193125-11-010144.txt")  # AAPL 2011
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001193125-11-192493.txt")  # AAPL 2011
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001628280-17-000717.txt")  # AAPL 2017
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001628280-17-004790.txt")  # AAPL 2017
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-17-000009.txt")  # AAPL 2017
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-19-000066.txt")  # AAPL 2019
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-19-000076.txt")  # AAPL 2019
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-20-000010.txt")  # AAPL 2020
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-20-000052.txt")  # AAPL 2020
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-94-001226.txt")  # IBM 1994
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-94-002130.txt")  # IBM 1994
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-94-002881.txt")  # IBM 1994
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-95-001268.txt")  # IBM 1995
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-95-002045.txt")  # IBM 1995
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-95-002932.txt")  # IBM 1995
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-96-001476.txt")  # IBM 1996
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-96-002735.txt")  # IBM 1996
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-96-000435.txt")  # IBM 1996
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-97-001362.txt")  # IBM 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000912057-97-027788.txt")  # IBM 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-97-002469.txt")  # IBM 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-97-002469.txt")  # IBM 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-98-002456.txt")  # IBM 1998
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-99-002266.txt")  # IBM 1999
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000912057-02-020756.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000912057-02-040785.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001047469-03-036586.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001104659-04-032411.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001104659-04-013278.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0001193125-12-023398.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000051143-13-000007.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-00-007765.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000912057-02-031609.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000912057-02-040785.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000051143-14-000004.txt")
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001104659-05-018203.txt")  # strange num of columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-19-000076.txt")  # strange num of columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-19-000066.txt")  # strange num of columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-20-000052.txt")  # strange num of columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/320193/0000320193-20-000062.txt")  # strange num of columns
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001047469-03-018510.txt")
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000100547700003871/0001005477-00-003871.txt")  # IBM 2000
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000100547701500586/0001005477-01-500586.txt")  # IBM 2001
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000091205702031609/0000912057-02-031609.txt")  # IBM 2002
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000104746903018510/0001047469-03-018510.txt")  # IBM 2003
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465904021678/0001104659-04-021678.txt")  # IBM 2004
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465905034155/0001104659-05-034155.txt")  # IBM 2005
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465906048719/0001104659-06-048719.txt")  # IBM 2006
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465907057458/0001104659-07-057458.txt")  # IBM 2007
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465908048278/0001104659-08-048278.txt")  # IBM 2008
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465909045198/0001104659-09-045198.txt")  # IBM 2009
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465910039808/0001104659-10-039808.txt")  # IBM 2010
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465911040759/0001104659-11-040759.txt")  # IBM 2011
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465912052637/0001104659-12-052637.txt")  # IBM 2012
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465913058041/0001104659-13-058041.txt")  # IBM 2013
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000005114314000007/0000051143-14-000007.txt")  # IBM 2014
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000005114315000005/0000051143-15-000005.txt")  # IBM 2015
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465916134367/0001104659-16-134367.txt")  # IBM 2016
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465917046808/0001104659-17-046808.txt")  # IBM 2017
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000110465918048404/0001104659-18-048404.txt")  # IBM 2018
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000155837019006560/0001558370-19-006560.txt")  # IBM 2019
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000155837020008516/0001558370-20-008516.txt")  # IBM 2020
