from sec_edgar import Parser


class BalanceSheetParser(Parser):

    def _parse_html(self, soup):
        balance_sheet_title = soup.find_all(
            lambda tag: "Consolidated Balance Sheets".lower() in tag.text.strip().lower())[-1]
        table_html = str(balance_sheet_title.find_next("table"))
        df, period = self.parse_table(table_html)
        return df
