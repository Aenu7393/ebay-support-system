import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException




def scrape_mercari(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # 新しいヘッドレスモードを使用
    chrome_options.add_argument('--disable-gpu')  # GPUを無効化
    chrome_options.add_argument('--no-sandbox')  # サンドボックスを無効化
    chrome_options.add_argument('--disable-dev-shm-usage')  # 共有メモリ使用を無効化
    chrome_options.add_argument('--remote-debugging-port=9222')  # リモートデバッグを有効化

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    try:
        # 商品タイトルを取得
        title = WebDriverWait(driver, 5).until(  # タイムアウト時間を10秒→5秒に短縮
            EC.presence_of_element_located((By.CLASS_NAME, 'heading__a7d91561'))
        ).text

        # 価格を取得
        price_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="price"]'))
        )
        price_currency = price_element.find_element(By.CLASS_NAME, 'currency').text
        price_value = price_element.find_elements(By.TAG_NAME, 'span')[1].text
        price = price_currency + price_value

        # 商品の状態を取得
        condition_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-testid="商品の状態"]'))
        )
        condition = condition_element.text

        # 画像URLを取得
        image_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'img'))
        )
        image_url = image_element.get_attribute('src')

    except TimeoutException:
        print("要素の取得に失敗しました。")
        title, price, condition, image_url = None, None, None, None

    finally:
        driver.quit()

    return title, price, condition, image_url



def write_to_google_sheets(data, url):
    # Google Sheets APIの認証
    gc = gspread.service_account(
        filename="C:/Users/並木大悟/Desktop/dev/work1/pythonProject/django/work1-web/workweb/work1/spread-sheet-test.json"
    )

    # スプレッドシートにアクセス
    sh = gc.open_by_key("1SI_PcKE7EMxLhNIDuFmDkIYOa6NYp6cjQxozloLSgOw")
    ws = sh.get_worksheet(0)  # 1つ目のシートを選択

    # 既存のURL一覧を取得
    existing_urls = ws.col_values(1)  # URLが3列目にあると仮定
    print(existing_urls)    # 重複チェック
    if url in existing_urls:
        print("既に登録されているURLです。")
        return

    # クエリパラメータを削除した画像URLを作成
    clean_image_url = data[3].split('?')[0]  # ? 以降を削除

    # IMAGE() 関数形式の数式を準備（モード4でカスタムサイズ指定）
    image_formula = f'=IMAGE("{clean_image_url}", 4, 170, 170)'  # 高さ300px、幅300px

    # 書き込む行番号を取得（最終行の次の行に追加）
    next_row = len(ws.get_all_values()) + 1

    # 商品名、価格、画像URL、URLをそれぞれのセルに書き込む
    ws.update_cell(next_row, 1, url)  # 商品URL
    ws.update_cell(next_row, 2, data[0])  # 商品名
    ws.update_cell(next_row, 3, data[1])  # 価格
    ws.update_cell(next_row, 4, data[2])
    ws.update_cell(next_row, 5, image_formula)  # 画像 (数式として書き込む)
    

