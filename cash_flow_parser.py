from parser import Parser


class CashFlowParser(Parser):

    def _parse_html(self, soup):
        cash_flow_title = soup.find_all(
            lambda tag: "CONSOLIDATED STATEMENTS OF CASH FLOWS".lower() in tag.text.strip().lower())[-1]
        table_html = str(cash_flow_title.find_next("table"))
        df, period = self.parse_table(table_html)
        return df
