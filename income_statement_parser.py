from parser import Parser


class IncomeStatementParser(Parser):

    def _parse_html(self, soup):
        income_title = soup.find_all(
            lambda tag: "Consolidated Statements of Income".lower() in tag.text.strip().lower())[-1]
        table_html = str(income_title.find_next("table"))
        df, period = self.parse_table(table_html)
        return df
