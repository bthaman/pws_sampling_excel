import lxml.html
import requests
import pandas as pd
import xlwings as xw
import msgbox
import re


def _unpack(row, kind='td'):
    elts = row.findall('.//%s' % kind)
    # if the tag was found, the list has members and its boolean is True
    if elts:
        return [val.text_content().strip() for val in elts]
    else:
        return ''


def _unpack2(row, xpath_arg):
    elts = row.xpath(xpath_arg)
    # xpath_arg for all tags is './/*'
    # xpath arg for matching any node of any kind is 'node()'
    # xpath arg to union multiple nodes is e.g., './/span | .//div | .//font'
    # if the tag was found, the list has members and its boolean is True
    if elts:
        return [val.text_content().strip() for val in elts]
    else:
        return ''


def get_samples():
    try:
        # sht = xw.Book.caller().sheets[0]
        sht = xw.Book.caller().sheets.active
        sht.range('D1').expand().clear_contents()
        url = sht.range('B4').value
        if not 'AnalyteListByCode' in url:
            raise ValueError('url must represent Analyte List by Code')
        headers = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                 'Chrome/51.0.2704.103 Safari/537.36'}
        r = requests.get(url=url, headers=headers)
        doc = lxml.html.fromstring(r.content)
        tables = doc.findall('.//table')
        # get name of PWS in 4th table
        info_table = tables[3]
        tr_info = info_table.findall('.//tr')
        td_info = [_unpack(tr, kind='p') for tr in tr_info[2]]
        sys_name = td_info[1]
        sysnum = sht.range('A3').value
        sht.range('B8').value = sys_name[0] + ' (' + sysnum + ')'
        # links are in the 5th table
        analyte_table = tables[4]
        # each analyte's info is in a separate tr
        tr_tags = analyte_table.findall('.//tr')
        a_tags = [tr.findall('.//a') for tr in tr_tags[2:]]
        # use a list comprehension to get all the url's
        base_url = 'https://dww2.tceq.texas.gov/DWW/JSP/'
        urls = [base_url + re.sub(r'\s', '', a_tag[0].get('href')) for a_tag in a_tags]
        # for each tr, get all the td's
        td_vals = [_unpack(tr) for tr in tr_tags[2:]]
        # get the table values and create dataframe
        analyte_codes = [el[0] for el in td_vals]
        analyte_names = [el[1] for el in td_vals]
        analyte_type = [el[2] for el in td_vals]
        analyte_num_results = [el[3] for el in td_vals]
        df_analyte = pd.DataFrame({'URL': urls, 'Code': analyte_codes, 'Name': analyte_names, 'Type': analyte_type,
                                   'Number Results': analyte_num_results})
        # get the list of analytes to filter the dataframe
        filter_list = sht.range('B10').options(ndim=1).expand('down').value
        if type(filter_list) is str:
            filter_list = [filter_list]
        if filter_list is None:
            raise TypeError('There is no analyte list')
        df_scrape = df_analyte[df_analyte['Name'].isin(filter_list)]
        if df_scrape.empty:
            raise ValueError('None of the analytes in the list exist for this PWS')
        # for each url, get the sampling data and build a pandas dataframe
        df_sampling = pd.DataFrame()
        columns = ['Code', 'Name', 'Facility', 'Sample Point', 'Sample Collection Date', 'TCEQ Sample ID',
                   'Laboratory Sample ID', 'Method', 'Less Than Ind.', 'Level Type', 'Reporting Level', 'Concentration',
                   'Current MCL']
        for index, row in df_scrape.iterrows():
            r = requests.get(url=row['URL'], headers=headers)
            doc = lxml.html.fromstring(r.content)
            tables = doc.findall('.//table')
            # sampling data in the 5th table
            sampling_table = tables[4]
            # get the tr's: headings in the 2nd tr, data starts in 3rd tr
            tr_tags = sampling_table.findall('.//tr')
            # get the headers: html is inconsistent - use xpath function to get all nodes within the th
            # headers = [_unpack2(tr, xpath_arg='node()') for tr in tr_tags[1]]
            # headers = [el[0] for el in headers]
            # get the values
            td_vals = [_unpack(tr) for tr in tr_tags[2:]]
            # create a sampling dataframe
            for i, item in enumerate(td_vals):
                zipped = zip(columns, item)
                dict_item = {k: v for k, v in zipped}
                df_sampling = df_sampling.append(dict_item, ignore_index=True)
        df_sampling['Sample Collection Date'] = pd.to_datetime(df_sampling['Sample Collection Date'])
        # put columns in correct order
        df_sampling = df_sampling[columns]
        if not df_sampling.empty:
            sht.range('D1').options(index=False).value = df_sampling
        else:
            msgbox.show_message('Message', 'No results')
    except Exception as e:
        msgbox.show_error('Error', e)

if __name__ == '__main__':
    get_samples()

