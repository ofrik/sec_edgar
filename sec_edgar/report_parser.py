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
                found_xbrl = re.search(r"<xbrl>", content, re.IGNORECASE)
                found_html = re.search(r"<html.*>", content, re.IGNORECASE)
                if found_xbrl.start() < found_html.start():
                    report_content = self._get_xbrl_content(content)
                else:
                    report_content = content
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
                    pass
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
    # parser.add_parser(IncomeStatementParser())
    parser.add_parser(BalanceSheetParser())
    # parser.add_parser(CashFlowParser())
    # TODO handle financial

    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-94-001226.txt")  # IBM 1994
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0000950112-95-001268.txt")  # IBM 1995
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-96-000435.txt")  # IBM 1996
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-97-002469.txt")  # IBM 1997
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-98-002456.txt")  # IBM 1998
    # parser.parse("https://www.sec.gov/Archives/edgar/data/51143/0001005477-99-002266.txt")  # IBM 1999
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000100547700003871/0001005477-00-003871.txt")  # IBM 2000
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000100547701500586/0001005477-01-500586.txt")  # IBM 2001
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000091205702031609/0000912057-02-031609.txt")  # IBM 2002
    # parser.parse(
    #     "https://www.sec.gov/Archives/edgar/data/51143/000104746903018510/0001047469-03-018510.txt")  # IBM 2003
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465904021678/0001104659-04-021678.txt")  # IBM 2004
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465905034155/0001104659-05-034155.txt")  # IBM 2005
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465906048719/0001104659-06-048719.txt")  # IBM 2006
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465907057458/0001104659-07-057458.txt")  # IBM 2007
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465908048278/0001104659-08-048278.txt")  # IBM 2008
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465909045198/0001104659-09-045198.txt")  # IBM 2009
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465910039808/0001104659-10-039808.txt")  # IBM 2010
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465911040759/0001104659-11-040759.txt")  # IBM 2011
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465912052637/0001104659-12-052637.txt")  # IBM 2012
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465913058041/0001104659-13-058041.txt")  # IBM 2013
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000005114314000007/0000051143-14-000007.txt")  # IBM 2014
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000005114315000005/0000051143-15-000005.txt")  # IBM 2015
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465916134367/0001104659-16-134367.txt")  # IBM 2016
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465917046808/0001104659-17-046808.txt")  # IBM 2017
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000110465918048404/0001104659-18-048404.txt")  # IBM 2018
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000155837019006560/0001558370-19-006560.txt")  # IBM 2019
    parser.parse(
        "https://www.sec.gov/Archives/edgar/data/51143/000155837020008516/0001558370-20-008516.txt")  # IBM 2020
