from parser import Parser


class BalanceSheetParser(Parser):

    def _parse_html(self, soup):
        balance_sheet_title = soup.find_all(
            lambda tag: "Consolidated Balance Sheets".lower() in tag.text.strip().lower())[-1]
        table_html = str(balance_sheet_title.find_next("table"))
        df, period = self.parse_table(table_html)
        return df

    def _get_xbrl_tag(self, soup, name):
        cash_end_eq = soup.find(attrs={"name": name})
        scale = int(cash_end_eq.attrs["scale"])
        self.fix_values(cash_end_eq.text)
        value = self.fix_values(cash_end_eq.text) * scale
        return value

    def _parse_xbrl(self, soup):
        cash_end_eq = self._get_xbrl_tag(soup, "us-gaap:CashAndCashEquivalentsAtCarryingValue")
        pass
