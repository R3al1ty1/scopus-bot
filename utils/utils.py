import asyncio
import traceback
import random
import pandas as pd
import io
import os
import re
import math
import shutil
import asyncio
import DrissionPage

from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bypass.CloudflareBypasser import CloudflareBypasser
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import Actions
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from utils.const import PROJECT_DIR, FILTERS_DCT


load_dotenv()

used_ports = []

project_dir = PROJECT_DIR


async def build_query_by_dialog_data(query : dict):
    """Функция для построения запроса в Scopus."""
    result = ""
    html_content = ""

    result += f"{FILTERS_DCT[query['filter_type']]}("
    result += f"{query['query']})"
    if (query['years'].split()[0] == query['years'].split()[1]):
        result = result + f" AND PUBYEAR = {query['years'].split()[0]}"
    else:
        if query['years'].split()[0] == "0":
            result = result + f" AND PUBYEAR > {query['years'].split()[0]}" + f" AND PUBYEAR < {str(int(query['years'].split()[1]) + 1)}"
        else:
            result = result + f" AND PUBYEAR > {str(int(query['years'].split()[0]) - 1)}" + f" AND PUBYEAR < {str(int(query['years'].split()[1]) + 1)}"

    langs = []
    langs_str = ''
    if (query['eng']):
        langs.append('LIMIT-TO ( LANGUAGE , "English" )')
    if (query['ru']):
        langs.append('LIMIT-TO ( LANGUAGE , "Russian" )')
    if (len(langs)):
        langs_str = ' OR '.join(langs)
        langs_str = f' AND ( {langs_str} )'
        result = result + langs_str

    files = []
    files_str = ''
    if (query['conf']):
        files.append('LIMIT-TO ( DOCTYPE , "cp" )')
    if (query['rev']):
        files.append('LIMIT-TO ( DOCTYPE , "re" )')
    if (query['art']):
        files.append('LIMIT-TO ( DOCTYPE , "ar" )')    
    if (len(files)):
        files_str = ' OR '.join(files)
        files_str = f' AND ( {files_str} )'
        result = result + files_str
    print(result)
    return result


async def get_co_authors(content, browser):
    try:
        soup = BeautifulSoup(content, "html.parser")

        rows = soup.find_all("tr", class_="Table-module__lCVi9")

        data = []
        for row in rows:
            checkbox = row.find("input", {"type": "checkbox"})
            author_id = checkbox["id"] if checkbox else None

            name_span = row.select_one("td:nth-of-type(2) a span")
            name = name_span.get_text(strip=True) if name_span else None

            doc_count_span = row.select_one("td:nth-of-type(3) a span")
            doc_count = doc_count_span.get_text(strip=True) if doc_count_span else None

            if author_id and name and doc_count:
                data.append({
                    "id": author_id,
                    "name": name,
                    "documents": doc_count
                })
        for i in range(len(data)):
            try:
                auth_id = data[i]["id"]
                print(auth_id)
                browser.get(f"https://www.scopus.com/authid/detail.uri?authorId={auth_id}")
                orcid = browser.ele('xpath://*[@id="scopus-author-profile-page-control-microui__general-information-content"]/div[2]/ul/li[3]').text
                orcids_lst = orcid.split("/")
                orcid = orcids_lst[-1]
                if orcid.count("-") == 3:
                    data[i]["id"] = orcid[:19]
                else:
                    data[i]["id"] = "-"
                browser.back()
            except:
                traceback.print_exc()

        return data

    except:
        return None


async def get_menu_name(elem_html):
    soup = BeautifulSoup(elem_html, 'html.parser')

    # Находим элемент <button> с атрибутом aria-controls
    button = soup.find('button', attrs={'aria-controls': True})

    # Извлекаем значение aria-controls
    if button:
        aria_controls_value = button['aria-controls']
        if aria_controls_value.startswith("menu"):
            return aria_controls_value
    else:
        return None

async def export_auth_docs(browser, doc_type):
    try:
        browser.scroll.down(200)
        await asyncio.sleep(2)
        exp = browser.ele('xpath://*[@id="documents-panel"]/div/div/div/div[2]/div[2]/ul/li[1]/div/span/button')
        displayed = exp.wait.displayed()
        if displayed:
            exp.click()
        await asyncio.sleep(1)
        menu_html = browser.ele('xpath://*[@id="documents-panel"]/div/div/div/div[2]/div[2]/ul/li[1]/div/span').html
        menu_name = await get_menu_name(menu_html)
        if menu_name:
            if doc_type == "csv":
                browser.ele(f'xpath://*[@id="{menu_name}"]/div[1]/button[1]', timeout=4).click()
            else:
                browser.ele(f'xpath://*[@id="{menu_name}"]/div[1]/button[2]', timeout=4).click()
            await asyncio.sleep(1)
            browser.ele('xpath://*[@id="documents-panel"]/div/div/div/div[2]/div[2]/ul/li[1]/div[2]/div/div/section/div[1]/div/div/div/div/div[3]/span/label/input').click()
            browser.ele('xpath://*[@id="documents-panel"]/div/div/div/div[2]/div[2]/ul/li[1]/div[2]/div/div/section/div[2]/div/div/span[2]/div/div/button').click()
            return True
        return False
    except:
        traceback.print_exc()
        return False

#global warning AND PUBYEAR > 1971 AND PUBYEAR < 2026 AND ( LIMIT-TO ( LANGUAGE , "English" ) OR LIMIT-TO ( LANGUAGE , "Russian" ) ) AND ( LIMIT-TO ( DOCTYPE , "cp" ) OR LIMIT-TO ( DOCTYPE , "re" ) OR LIMIT-TO ( DOCTYPE , "ar" ) )

async def downloads_done(folder_id):
    max_retries = 26
    download_dir = os.path.expanduser(f"{project_dir}/scopus_files/{folder_id}")
    file_path = os.path.join(download_dir, 'scopus.ris')
    for i in range(max_retries):
        if not os.path.isfile(file_path):
            await asyncio.sleep(2)
        else:
            break

async def generate_port():
    """Создание порта для запуска браузера."""
    while True:
        port = random.randint(9000, 9500)
        if port not in used_ports:
            return port


async def set_prefs(folder_id):
    """Установление парамтеров браузера"""
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    download_dir = os.path.expanduser(f"{project_dir}/scopus_files/{folder_id}")

    co = ChromiumOptions()
    co.set_browser_path(chrome_path)

    co.set_pref("download.default_directory", download_dir)
    co.set_pref("download.prompt_for_download", False)
    co.set_pref("directory_upgrade", True)
    co.set_pref("safebrowsing.enabled", True)
    co.set_pref(arg='profile.default_content_settings.popups', value='0')
    co.set_pref(arg='profile.managed_default_content_settings.popups', value='0')
    co.set_pref("profile.default_content_setting_values.automatic_downloads", 1)
    co.set_argument('--start-maximized')
    co.set_argument("--disable-notifications")
    co.set_argument("--disable-popup-blocking")
    
    port = await generate_port()
    used_ports.append(port)
    
    co.set_local_port(port)
    
    return co


async def authorization_scopus(browser, ac):
    """Авторизация Scopus."""
    try:
        try:
            elem = browser.ele('Enter your email to continue')
        except:
            try:
                sign_in_button = browser.ele('Sign in', timeout=4).click(by_js=True)
                print("Sign-in button clicked")
            except:
                try:
                    sign_in_button = browser.ele('xpath://*[@id="signin_link_move"]', timeout=4).click(by_js=True)
                    print("Sign-in button clicked")
                except:
                    pass
            try:
                browser.ele('Accept all cookies', timeout=4).click()
            except:
                pass
            try:
                await asyncio.sleep(2)
                browser.ele('Maybe later', timeout=4).click()
            except:
                browser.ele('×', timeout=4).click()
            finally:
                try:
                    sign_in_button = browser.ele('Sign in', timeout=4).click()
                    print("Sign-in button clicked")
                except:
                    try:
                        sign_in_button = browser.ele('xpath://*[@id="signin_link_move"]', timeout=4).click()
                        print("Sign-in button clicked")
                    except:
                        pass
        try:
            await asyncio.sleep(2)
            browser.ele('xpath://*[@id="bdd-password"]', timeout=4).input(os.getenv('PASSWORD'))
            await asyncio.sleep(0.5)
            ac.key_down('RETURN')
        except:
            try:
                browser.ele('Accept all cookies', timeout=4).click()
            except:
                pass
            try:
                browser.ele('@id:bdd-email', timeout=4).click()
                browser.ele('@id:bdd-email', timeout=4).input(os.getenv('LOGIN'))
                browser.ele('@id:bdd-email', timeout=4).click()
                
                continue_button = browser.ele('Continue', timeout=4)
                continue_button.run_js("document.getElementById('bdd-elsPrimaryBtn').removeAttribute('disabled')")
                continue_button.click()
                browser.ele('xpath://*[@id="bdd-password"]', timeout=4).input(os.getenv('PASSWORD'))
                await asyncio.sleep(0.5)
                ac.key_down('RETURN')
            except:
                print("probably, already logged in")
        # await asyncio.sleep(3)

        print("Email entered and submitted")
        
        print("Login successful")
    except DrissionPage.errors.NoRectError:
        try:
            elem = browser.ele('@id:contentEditLabel', timeout=4)
            print ("Page is ready!")
        except TimeoutException:
            browser.quit()
            print ("Loading took too much time!")
    except Exception as e:
        print('Error while logging in', e)
        traceback.print_exc()
        browser.quit()


async def prepare_for_export(browser, result):
    """Поиск по статьям из запроса."""
    # choose show 50
    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[2]/div[2]/div/div/label/select/option[3]', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()
    elem.click()
    await asyncio.sleep(1.5)


    # show all abstract
    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[3]/div/div/button/span', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()
    elem.click()
    await asyncio.sleep(1.5)

    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[2]/div[1]/table', timeout=4)
        print ("Page is ready!")
    except Exception as e:
        print('Error while logging in', e)
        traceback.print_exc()
        browser.quit()
    try:
        html_content = elem.html
    except Exception as e:
        print('Error while logging in', e)
        browser.quit()
        traceback.print_exc()


    #['Unnamed: 0', 'Document title', 'Authors', 'Source', 'Year', 'Citations']
    #'Hide abstract'
    #'View at Publisher. Opens in a new tab.Related documents'
    try:
        df = pd.read_html(io.StringIO(html_content))[0]
        i = 1
        result.append([])
        j = 2
        skip_seventh_row = False
    except Exception as e:
        print('Error while logging in', e)
        traceback.print_exc()
        browser.quit()

    await asyncio.sleep(1.5)
    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[2]/div[1]/table/tbody/tr[10]/td/div/div/button', timeout=4)
        skip_seventh_row = True
    except NoSuchElementException:
        print("do not skip")


    while (i < df.shape[0]):
        result[j].append({})
        result[j][-1]['Title'] = df['Document title'][i]
        if (not (isinstance(df['Document title'][i + 1], float) and math.isnan(df['Document title'][i + 1]))):
            result[j][-1]['Abstract'] = df['Document title'][i + 1][13:-56]
        result[j][-1]['Authors'] = df['Authors'][i]
        result[j][-1]['Source'] = df['Source'][i]
        result[j][-1]['Year'] = df['Year'][i]
        result[j][-1]['Citations'] = df['Citations'][i]
        if (i == 7 and skip_seventh_row):
            i += 1
        i = i + 3
    print(len(result[2]))


    # change to oldest

    try:
        await asyncio.sleep(1)
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[3]/div/div/div[1]/label/select/option[2]', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()
    elem.click()
    await asyncio.sleep(1.5)

    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[2]/div[1]/table', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()

    df = pd.read_html(io.StringIO(elem.html))[0]
    i = 1
    j = 3
    result.append([])

    while (i < df.shape[0]):
        result[j].append({})
        result[j][-1]['Title'] = df['Document title'][i]
        if (not (isinstance(df['Document title'][i + 1], float) and math.isnan(df['Document title'][i + 1]))):
            result[j][-1]['Abstract'] = df['Document title'][i + 1][13:-56]
        result[j][-1]['Authors'] = df['Authors'][i]
        result[j][-1]['Source'] = df['Source'][i]
        result[j][-1]['Year'] = df['Year'][i]
        result[j][-1]['Citations'] = df['Citations'][i]
        if (i == 7 and skip_seventh_row):
            i += 1
        i = i + 3
    print(len(result[j]))

    # chage to most cited

    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[3]/div/div/div[1]/label/select/option[3]', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()
    elem.click()
    await asyncio.sleep(1.5)

    try:
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[2]/div[1]/table', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()

    df = pd.read_html(io.StringIO(elem.html))[0]
    i = 1
    j = 4
    result.append([])

    while (i < df.shape[0]):
        result[j].append({})
        result[j][-1]['Title'] = df['Document title'][i]
        if (not (isinstance(df['Document title'][i + 1], float) and math.isnan(df['Document title'][i + 1]))):
            result[j][-1]['Abstract'] = df['Document title'][i + 1][13:-56]
        result[j][-1]['Authors'] = df['Authors'][i]
        result[j][-1]['Source'] = df['Source'][i]
        result[j][-1]['Year'] = df['Year'][i]
        result[j][-1]['Citations'] = df['Citations'][i]
        if (i == 7 and skip_seventh_row):
            i += 1
        i = i + 3    
    print(len(result[2]))
        

async def export_file(browser, flag, folder_id, result):
    """Экспортирование файла."""
    # export button
    try:
        elem = browser.ele('xpath://*[@id="container"]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[2]/div/div/div[1]/span/button/span[1]', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        print ("Loading took too much time!")
        browser.quit()
    elem.click()

    # await asyncio.sleep(2)
    # "my ris settings" button
    try:
        browser.ele('RIS', timeout=4).click()
        print ("Page is ready!")
    except TimeoutException:
        browser.quit()
        print ("Loading took too much time!")

    elem.click()

    # нажатие кнопки выбора кол-ва
    try:
        elem = browser.ele('xpath://*[@id="select-range"]', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        browser.quit()
        print ("Loading took too much time!")

    elem.click()    

    #левая и права границы
    try:
        elem_left = browser.ele('xpath://*[@id="container"]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[2]/div/div/div[2]/div/div/section/div[1]/div/div/div[1]/div/div/div/div/div/div/div[1]/div/label/input', timeout=4)
        elem_right = browser.ele('xpath://*[@id="container"]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[2]/div/div/div[2]/div/div/section/div[1]/div/div/div[1]/div/div/div/div/div/div/div[2]/div/label/input', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        browser.quit()
        print ("Loading took too much time!")    

    num = result[1]
    num = num.replace(',', '')
    num = min(2500, int(num))
    elem_left.input("1")
    elem_right.input(str(num))  

    # "export" (finish) button
    try:
        # await asyncio.sleep(3)
        elem = browser.ele('xpath:/html/body/div/div/div[1]/div/div/div[3]/micro-ui/document-search-results-page/div[1]/section[2]/div/div[2]/div/div[2]/div/div[1]/table/tbody/tr/td[2]/div/div/div[2]/div/div/section/div[2]/div/div/span[2]/div/div/button', timeout=4)
        print ("Page is ready!")
    except TimeoutException:
        browser.quit()
        print ("Loading took too much time!")

    elem.click()


#result = [нашлось или нет, кол-во, самые новые, самые старые, самые цитируемые]
async def download_scopus_file(query: dict, folder_id: str, flag, future):
    """Функция обработки запроса пользователя."""
    result = []
    text_query = await build_query_by_dialog_data(query)
    num = '2500'

    co = await set_prefs(folder_id=folder_id)

    try:
        browser = ChromiumPage(co)
        ac = Actions(browser)
        browser.set.timeouts(base=3, page_load=3)
        browser.get('https://www.scopus.com/search/form.uri?display=advanced')
        cf_bypasser = CloudflareBypasser(browser)
        await cf_bypasser.bypass()

        # await asyncio.sleep(3)

        await authorization_scopus(browser=browser, ac=ac)

        # await asyncio.sleep(3)

        try:
            try:
                browser.ele('Clear form', timeout=4).click()
            except:
                pass
            elem = browser.ele('@id:contentEditLabel', timeout=4)
            elem.input(text_query)
            browser.ele('xpath://*[@id="advSearch"]/span[1]', timeout=4).click()
        except Exception as e:
            print('Error while logging in', e)
            traceback.print_exc()
            browser.quit()

        #нашлось или не нашлось
        
        await asyncio.sleep(2)
        try:
            elem = browser.ele('xpath://*[@id="container"]/micro-ui/document-search-results-page/div[1]/section[1]/div[3]/div/div/div[1]/h2', timeout=4)
            result.append(True)
        except NoSuchElementException:
            print("net statey")
            future.set_result([False])
            browser.quit()
            flag.set()
            return
            
        
        result.append(elem.text.split()[0])
        print(elem.text)

    #  ----------------------

        await prepare_for_export(browser=browser, result=result)

        future.set_result(result)
        flag.set()
        # await asyncio.sleep(3)
        
        if (future.result() == False):
            browser.quit()
            return

        print("flag was set and now we are waiting")
        await flag.wait()

        await export_file(browser=browser, flag=flag, folder_id=folder_id, result=result)

        res = await downloads_done(folder_id)
        if res:
            flag.set()

        browser.quit()
        return
    except:
        print("kakoyto trouble")
        traceback.print_exc()
        future.set_result([False])
        browser.quit()
        flag.set()
        return


async def search_for_author_cred(query: dict, folder_id: str, flag, future, search_type):
    result = []
    first_name = ""
    last_name = ""
    orcid = ""
    keywords = ""
    text_query = query["query"]
    query_list = text_query.split(" ")
    if search_type == "full_name":
        last_name = query_list[0]
        first_name = query_list[1]
    elif search_type == "keywords":
        keywords = query["query"]
    else:
        orcid = query["query"]

    
    num = '2500'

    co = await set_prefs(folder_id=folder_id)

    try:
        browser = ChromiumPage(co)
        ac = Actions(browser)
        browser.set.timeouts(base=3, page_load=3)
        browser.get('https://www.scopus.com/search/form.uri?display=basic&zone=header&origin=searchadvanced#author')
        cf_bypasser = CloudflareBypasser(browser)
        await cf_bypasser.bypass()

        await authorization_scopus(browser=browser, ac=ac)
        await asyncio.sleep(2)
        try:
            if search_type == "keywords":
                browser.ele('xpath://*[@id="researcher-discovery"]', timeout=4).click()
            else:
                browser.ele('xpath://*[@id="author"]', timeout=4).click()
        except:
            pass

        await asyncio.sleep(2)

        if orcid:
            browser.ele('xpath://*[@id="scopus-author-search-form"]/div[1]/ul[1]/li/label/select').click()
            browser.ele('xpath://*[@id="scopus-author-search-form"]/div[1]/ul[1]/li/label/select/option[2]').click()
            await asyncio.sleep(2)
            browser.ele('xpath://*[@id="scopus-author-search-form"]/div[2]/div/label/input').input(orcid)

        elif keywords:
            browser.ele('xpath://*[@id="researcher-discovery-panel"]/div/div/div/div[2]/div/div[1]/div[2]/div/form/div/div/div/label/input').input(keywords)

        else:
            try:
                browser.ele('xpath://*[@id="scopus-author-search-form"]/div[2]/div[2]/div/label/input').input(first_name)
            except:
                try:
                    browser.ele('xpath://*[@id="scopus-author-search-form-experimental"]/div[2]/div[2]/div/label/input').input(first_name)
                except:
                    pass
            try:
                browser.ele('xpath://*[@id="scopus-author-search-form"]/div[2]/div[1]/div/label/input').input(last_name)
            except:
                try:
                    browser.ele('xpath://*[@id="scopus-author-search-form-experimental"]/div[2]/div[1]/div/label/input').input(last_name)
                except:
                    pass

        if not keywords:
            try:
                browser.ele('xpath://*[@id="scopus-author-search-form"]/div[3]/div[2]/button').click()
            except:
                try:
                    browser.ele('xpath://*[@id="scopus-author-search-form-experimental"]/div[3]/div[2]/button').click()
                except:
                    pass
        else:
            try:
                browser.ele('xpath://*[@id="researcher-discovery-panel"]/div/div/div/div[2]/div/div[1]/div[2]/div/form/div/div/div/div/button').click()
            except:
                try:
                    browser.ele('xpath://*[@id="researcher-discovery-panel-experimental"]/div/div/div/div[2]/div/div[1]/div[2]/div/form/div/div/div/div/button').click()
                except:
                    pass

        await asyncio.sleep(2)
        
        if not keywords:
            browser.ele('xpath://*[@id="resultsPerPage-button"]/span[1]').click()
            browser.ele('xpath://*[@id="ui-id-14"]').click()

            await asyncio.sleep(2)        

            # Извлечение таблицы и начальная настройка
            
            auths_num = browser.ele('xpath://*[@id="authorResultsOptionBar"]/div/div/header/h1/span').text
        else:
            auths_num = 0

        result = []  # Массив для хранения результатов
        i = 0
        result.append(auths_num)
        if search_type == "full_name":
            for j in range(1, 9):
                try:
                    browser.ele('xpath://*[@id="navLoad-button"]').click()
                    browser.ele(f'xpath://*[@id="navLoad-menu"]/li[{j}]').click()
                    elem = browser.ele('xpath://*[@id="srchResultsList"]')
                    html_content = elem.html
                    await asyncio.sleep(1.5)
                    i = 0
                    soup = BeautifulSoup(html_content, 'html.parser')
                    table = soup.find("table", id="srchResultsList")
                    rows = table.find_all("tr", class_="searchArea")
                    await asyncio.sleep(2)
                    result.append([])

                    # Проход по каждой строке таблицы, содержащей данные авторов
                    while i < len(rows):
                        # Создаем словарь для данных текущего автора
                        author_data = {}

                        # Инициализация переменной input_tag
                        input_tag = None

                        # Извлечение ID автора
                        checkbox_div = rows[i].find("div", class_="checkbox")
                        if checkbox_div:
                            input_tag = checkbox_div.find("input", {"value": True})
                            author_data['AuthorID'] = input_tag['value'] if input_tag else "N/A"

                        # Извлечение имени автора из `authorResultsNamesCol` или `data-name` в `input`
                        author_col = rows[i].find("td", class_="authorResultsNamesCol")
                        if author_col and author_col.find("a"):
                            author_data['Author'] = author_col.find("a").text.strip()
                        else:
                            # Если имени автора нет в `authorResultsNamesCol`, берем из `input`
                            author_data['Author'] = input_tag['data-name'] if input_tag else "N/A"
                        
                        # Извлечение порядкового номера автора из `label`
                        if input_tag:
                            input_id = input_tag['id']
                            label_tag = rows[i].find("label", {"for": input_id})
                            author_data['Order'] = label_tag.text.strip() if label_tag else "N/A"

                        # Извлечение данных из других столбцов
                        documents_col = rows[i].find("td", id=lambda x: x and x.startswith("resultsDocumentsCol"))
                        author_data['Documents'] = documents_col.text.strip() if documents_col else "N/A"

                        affiliation_col = rows[i].find("td", class_="dataCol5")
                        if affiliation_col:
                            affiliation_text = affiliation_col.find("span", class_="anchorText")
                            author_data['Affiliation'] = affiliation_text.text.strip() if affiliation_text else "N/A"

                        city_col = rows[i].find("td", class_="dataCol6")
                        author_data['City'] = city_col.text.strip() if city_col else "N/A"

                        country_col = rows[i].find("td", class_="dataCol7 alignRight")
                        author_data['Country'] = country_col.text.strip() if country_col else "N/A"

                        # Добавление данных автора в текущую группу результатов
                        result[j].append(author_data)

                        # Увеличение счетчика для перехода к следующему автору
                        i += 1
                except:
                    pass
        elif search_type == "keywords":
            await asyncio.sleep(4)

            for i in range(1, 9):
                await asyncio.sleep(1)
                browser.ele(f'xpath://*[@id="container"]/micro-ui/scopus-people-finder/div/div[2]/div[2]/div[3]/div[2]/section[2]/div[1]/ul[2]/li[2]/label/select/option[{i}]').click()
                browser.ele('xpath://*[@id="container"]/micro-ui/scopus-people-finder/div/div[2]/div[2]/div[3]/div[2]/section[2]/div[1]/ul[1]/li/button').click()
            
            await asyncio.sleep(4)

            files_path = "scopus_files/" + str(folder_id)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            folder_path = os.path.join(parent_dir, files_path)
            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            files_sorted = sorted(files, key=os.path.getctime)

            for file_name in files_sorted:
                if file_name.endswith('.csv'):
                    file_path = os.path.join(folder_path, file_name)

                    data = pd.read_csv(file_path)

                    subset = data.iloc[:50]

                    file_dict = {
                        i: {
                            'AuthorID': row['Scopus Author ID'],
                            'Author': row['Name'],
                            'Affiliation': row['Latest Affilation'],
                            'Documents': row['Number of matching documents'],
                        }
                        for i, row in subset.iterrows()
                    }

                result.append(file_dict)
            shutil.rmtree(folder_path)  # Удаляем всю папку
            os.makedirs(folder_path)
        else:
            elem = browser.ele('xpath://*[@id="srchResultsList"]')
            html_content = elem.html
            await asyncio.sleep(1.5)
            i = 0
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find("table", id="srchResultsList")
            rows = table.find_all("tr", class_="searchArea")
            await asyncio.sleep(2)
            result.append([])

            # Проход по каждой строке таблицы, содержащей данные авторов
            while i < len(rows):
                # Создаем словарь для данных текущего автора
                author_data = {}

                # Инициализация переменной input_tag
                input_tag = None

                # Извлечение ID автора
                checkbox_div = rows[i].find("div", class_="checkbox")
                if checkbox_div:
                    input_tag = checkbox_div.find("input", {"value": True})
                    author_data['AuthorID'] = input_tag['value'] if input_tag else "N/A"

                # Извлечение имени автора из `authorResultsNamesCol` или `data-name` в `input`
                author_col = rows[i].find("td", class_="authorResultsNamesCol")
                if author_col and author_col.find("a"):
                    author_data['Author'] = author_col.find("a").text.strip()
                else:
                    # Если имени автора нет в `authorResultsNamesCol`, берем из `input`
                    author_data['Author'] = input_tag['data-name'] if input_tag else "N/A"
                
                # Извлечение порядкового номера автора из `label`
                if input_tag:
                    input_id = input_tag['id']
                    label_tag = rows[i].find("label", {"for": input_id})
                    author_data['Order'] = label_tag.text.strip() if label_tag else "N/A"

                # Извлечение данных из других столбцов
                documents_col = rows[i].find("td", id=lambda x: x and x.startswith("resultsDocumentsCol"))
                author_data['Documents'] = documents_col.text.strip() if documents_col else "N/A"

                affiliation_col = rows[i].find("td", class_="dataCol5")
                if affiliation_col:
                    affiliation_text = affiliation_col.find("span", class_="anchorText")
                    author_data['Affiliation'] = affiliation_text.text.strip() if affiliation_text else "N/A"

                city_col = rows[i].find("td", class_="dataCol6")
                author_data['City'] = city_col.text.strip() if city_col else "N/A"

                country_col = rows[i].find("td", class_="dataCol7 alignRight")
                author_data['Country'] = country_col.text.strip() if country_col else "N/A"

                # Добавление данных автора в текущую группу результатов
                result[1].append(author_data)

                # Увеличение счетчика для перехода к следующему автору
                i += 1
        # Вывод результата для проверки
        result.append(browser)


        future.set_result(result)
        flag.set()
    except:
        traceback.print_exc()
        
        future.set_result([False])
        browser.quit()
        flag.set()
        return


async def get_author_info(author_id: str, folder_id: str, browser, flag, future):

    co = await set_prefs(folder_id=folder_id)
    res = []
    author_info = {}
    try:
        browser.get(f'https://www.scopus.com/authid/detail.uri?authorId={author_id}')
        await asyncio.sleep(2)
        try:
            browser.ele('Accept all cookies', timeout=4).click()
        except:
            pass
        try:
            citNum = browser.ele('xpath://*[@id="scopus-author-profile-page-control-microui__general-information-content"]/div[2]/section/div/div[1]/div/div/div/div[1]/span').text
            citDoc = browser.ele('xpath://*[@id="scopus-author-profile-page-control-microui__general-information-content"]/div[2]/section/div/div[1]/div/div/div/div[2]/span/p').text
            citDoc = re.sub(r'by(\d)', r'by \1', citDoc)
            s = citNum + " " + citDoc
            author_info["citations"] = s
        except:
            pass
        try:
            docNum = browser.ele('xpath://*[@id="scopus-author-profile-page-control-microui__general-information-content"]/div[2]/section/div/div[2]/div/div/div/div[1]/span').text
            author_info["documents"] = docNum
        except:
            pass
        try:
            hIndex = browser.ele('xpath://*[@id="scopus-author-profile-page-control-microui__general-information-content"]/div[2]/section/div/div[3]/div/div/div/div[1]/span').text
            author_info["h_index"] = hIndex
        except:
            pass

        res.append(author_info)
        await asyncio.sleep(2)
        browser.run_js("""
            window.addEventListener('beforeunload', function(event) {
                event.stopImmediatePropagation();
            });
        """)
        csv = await export_auth_docs(browser=browser, doc_type="csv")
        await asyncio.sleep(2)

        ris = await export_auth_docs(browser=browser, doc_type="ris")
        await asyncio.sleep(2)
        """
        Делаем соавторов
        """
        await downloads_done(folder_id=folder_id)
        try:
            browser.ele('xpath://*[@id="co-authors"]').click()
            await asyncio.sleep(1.5)
        except:
            pass

        try:
            elem = browser.ele('xpath://*[@id="showAllCoAuthors"]/form/table')
            content = elem.html
        except:
            pass

        co_authors = await get_co_authors(content=content, browser=browser)

        res.append(co_authors)
        browser.get(f'https://www.scopus.com/authid/detail.uri?authorId={author_id}')
        await asyncio.sleep(2)
        """
        Дальше идут графики
        """
    
        try:
            browser.ele('xpath://*[@id="AuthorProfilePage_AnalyzeAuthorOutput"]').click()
            await asyncio.sleep(5)
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="row1"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results-data"]/span[2]/span/button[2]').click()
        except:
            pass

        # =======================================
        await asyncio.sleep(1.5)
        try:
            browser.ele('xpath://*[@id="analyzeType-miniChart"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="row1"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results-data"]/span[2]/span/button[2]').click()
        except:
            pass
        # =======================================
        await asyncio.sleep(1.5)
        try:
            browser.ele('xpath://*[@id="analyzeYear-miniChart"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="row1"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results-data"]/span[2]/span/button[2]').click()
        except:
            pass
        # =======================================
        await asyncio.sleep(1.5)
        try:
            browser.ele('xpath://*[@id="analyzeSubject-miniChart"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="row1"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results-data"]/span[2]/span/button[2]').click()
        except:
            pass
        # =======================================
        await asyncio.sleep(1.5)
        try:
            browser.ele('xpath://*[@id="analyzeHindex-miniGraph"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="row1"]').click()
        except:
            pass
        try:
            browser.ele('xpath://*[@id="export_results-data"]/span[2]/span/button[2]').click()
        except:
            pass

        await asyncio.sleep(1.5)
        await asyncio.sleep(1.5)
        future.set_result(res)
        flag.set()
        browser.quit()
    except:
        traceback.print_exc()
        
        future.set_result([False])
        browser.quit()
        flag.set()
        return
