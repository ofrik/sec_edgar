import re
from bs4 import BeautifulSoup
from parser import Parser


class GeneralParser(Parser):

    def get_num_of_shares(self, xml_content, type):
        if type == "html":
            found = re.findall(
                "the ?\n?registrant ?\n?had ?\n?([\d,]+) ?\n?shares ?\n?of ?\n?common ?\n?stock ?\n?outstanding",
                xml_content)
            if not found:
                found = re.findall("([\d,]+) ?\n?shares ?\n?of ?\n?common ?\n?stock", xml_content)
        else:
            soup = BeautifulSoup(xml_content, parser="lxml", features="lxml")
            found = soup.find(attrs={"name": "dei:EntityCommonStockSharesOutstanding"}).contents
        if len(found) > 0:
            return int(found[0].replace(",", ""))
        else:
            raise Exception("Failed to find number of shares")

    def parse(self, xml_content, type):
        num_of_shares = self.get_num_of_shares(xml_content, type)
        return {"num_of_shares": num_of_shares}
