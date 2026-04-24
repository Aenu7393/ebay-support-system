from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import psycopg2
import os
import json
import gspread
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from .models import Spreadsheet
import time
import xmltodict
from datetime import datetime, timedelta
import pytz  # 日本時間の処理に必要
import requests
from selenium.common.exceptions import NoSuchElementException
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options



def save_scraping_failure(site_name, url, field_name, selectors, driver):
    """
    スクレイピング失敗時に、
    URL・失敗項目・試したセレクタ・HTMLを保存する。
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    failure_dir = Path(__file__).resolve().parent / "scraping_failures"
    failure_dir.mkdir(exist_ok=True)

    base_name = f"{site_name}_{timestamp}_{field_name}"

    html_path = failure_dir / f"{base_name}.html"
    json_path = failure_dir / f"{base_name}.json"

    # HTMLを保存
    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception as e:
        print(f"HTML保存に失敗しました: {e}")

    # メタ情報を保存
    failure_info = {
        "site_name": site_name,
        "url": url,
        "field_name": field_name,
        "selectors_tried": selectors,
        "html_file": str(html_path.name),
        "created_at": timestamp
    }

    try:
        json_path.write_text(
            json.dumps(failure_info, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"失敗情報JSONの保存に失敗しました: {e}")

    print(f"スクレイピング失敗情報を保存しました: {json_path}")


def load_selectors():#selectors_config.json を読み込む関数
    config_path = Path(__file__).resolve().parent / "selectors_config.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_text_by_selectors(driver, selectors, timeout=5):
    """
    複数のCSSセレクタを順番に試して、最初に取得できたテキストを返す。
    """
    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

            # metaタグの場合は content 属性を見る
            if element.tag_name == "meta":
                value = element.get_attribute("content")
            else:
                value = element.text

            if value and value.strip():
                return value.strip()

        except Exception:
            continue

    return None

#画像URL用
def get_attribute_by_selectors(driver, selectors, attribute_name, timeout=5):
    """
    複数のCSSセレクタを順番に試して、最初に取得できた属性値を返す。
    """
    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

            value = element.get_attribute(attribute_name)

            if value and value.strip():
                return value.strip()

        except Exception:
            continue

    return None


#複数画像用
def get_attributes_by_selector(driver, selector, attribute_name):
    """
    指定したCSSセレクタに一致する複数要素から属性値を取得する。
    """
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        values = []

        for element in elements:
            value = element.get_attribute(attribute_name)
            if value:
                values.append(value)

        return values

    except Exception:
        return []


def end_ebay_listing(item_id, access_token, reason="NotAvailable"):
    """
    指定された商品IDに基づいてeBayの出品を停止する関数。

    Args:
        item_id (str): 停止する商品のID。
        access_token (str): eBay APIのアクセストークン。
        reason (str): 停止理由（デフォルトは"NotAvailable"）。

    Returns:
        dict: eBay APIのレスポンス。
    """
    url = "https://api.ebay.com/ws/api.dll"
    headers = {
        "Content-Type": "text/xml",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-CALL-NAME": "EndFixedPriceItem",
        "X-EBAY-API-SITEID": "0",
        "Authorization": f"Bearer {access_token}"
    }

    # XMLリクエストボディ
    body = f"""
    <?xml version="1.0" encoding="utf-8"?>
    <EndFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <RequesterCredentials>
        <eBayAuthToken>{access_token}</eBayAuthToken>
      </RequesterCredentials>
      <ItemID>{item_id}</ItemID>
      <EndingReason>{reason}</EndingReason>
    </EndFixedPriceItemRequest>
    """

    response = requests.post(url, headers=headers, data=body)
    
    if response.status_code == 200:
        # 成功時のレスポンスを解析
        data = xmltodict.parse(response.text)
        if data.get("EndFixedPriceItemResponse", {}).get("Ack") == "Success":
            print(f"商品 {item_id} の出品を停止しました。")
            return {"status": "success", "message": f"商品 {item_id} の出品を停止しました。"}
        else:
            print(f"商品 {item_id} の停止に失敗しました: {data}")
            return {"status": "error", "message": f"商品 {item_id} の停止に失敗しました。", "details": data}
    else:
        print(f"eBay APIリクエストエラー: {response.text}")
        return {"status": "error", "message": "eBay APIリクエストエラー", "details": response.text}









def get_ebay_selling_items(access_token):
    url = "https://api.ebay.com/ws/api.dll"
    headers = {
        "Content-Type": "text/xml",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-CALL-NAME": "GetMyeBaySelling",
        "X-EBAY-API-SITEID": "0",
        "Authorization": f"Bearer {access_token}"
    }

    body = """
    <?xml version="1.0" encoding="utf-8"?>
    <GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <RequesterCredentials>
        <eBayAuthToken>{access_token}</eBayAuthToken>
      </RequesterCredentials>
      <ActiveList>
        <Sort>TimeLeft</Sort>
        <Pagination>
          <EntriesPerPage>100</EntriesPerPage>
          <PageNumber>1</PageNumber>
        </Pagination>
      </ActiveList>
    </GetMyeBaySellingRequest>
    """.format(access_token=access_token)

    response = requests.post(url, headers=headers, data=body)
    if response.status_code == 200:
        # XMLレスポンスを解析
        
        data = xmltodict.parse(response.text)
        try:
            items = data['GetMyeBaySellingResponse']['ActiveList']['ItemArray']['Item']
            return items if isinstance(items, list) else [items]  # 単一アイテムの場合リストに変換
        except KeyError:
            print("eBay APIレスポンスにエラー:", data)
            return None
    else:
        print("eBay APIリクエストエラー:", response.text)
        return None


# def write_ebay_to_google_sheets(user_id, items):
#     try:
#         print(f"デバッグ: data = {items}")
#         creds = get_credentials()
#         gc = gspread.authorize(creds)

#         # スプレッドシートのIDを取得
#         spreadsheet_id = get_user_spreadsheet_id(user_id)
#         if not spreadsheet_id:
#             spreadsheet_id = create_user_spreadsheet(user_id)

#         sh = gc.open_by_key(spreadsheet_id)

#         # eBay用のシートを取得（なければ作成）
#         sheet_name = "eBay"
#         try:
#             ws = sh.worksheet(sheet_name)
#         except gspread.exceptions.WorksheetNotFound:
#             ws = sh.add_worksheet(title=sheet_name, rows="100", cols="5")

#         # ヘッダーの定義
#         headers = ["商品ID", "商品タイトル", "価格", "現在の価格"]

#         # 既存のデータをクリアしてヘッダーを設定
#         ws.clear()  # 既存のデータをクリア
#         ws.append_row(headers)  # ヘッダーを書き込む

#         # データの書き込み
#         for item in items:
#             item_id = item.get("ItemID", "N/A")  # 商品ID
#             title = item.get("Title", "N/A")  # 商品タイトル
#             price = item.get("BuyItNowPrice", {}).get("#text", "N/A")  # 価格
#             current_price = item.get("SellingStatus", {}).get("CurrentPrice", {}).get("#text", "N/A")  # 現在の価格

#             # 行データを作成して追加
#             ws.append_row([item_id, title, price, current_price])

#         print("eBayデータがスプレッドシートに正常に書き込まれました。")

#     except Exception as e:
#         print(f"eBayデータ書き込みエラー: {e}")
#         raise
def write_ebay_to_google_sheets(user_id, items):
    try:
        print(f"デバッグ: data = {items}")
        creds = get_credentials()
        gc = gspread.authorize(creds)

        spreadsheet_id = get_user_spreadsheet_id(user_id)
        if not spreadsheet_id:
            spreadsheet_id = create_user_spreadsheet(user_id)

        sh = gc.open_by_key(spreadsheet_id)

        # ① eBayシートを取得または作成
        ebay_sheet_name = "eBay"
        try:
            ebay_ws = sh.worksheet(ebay_sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ebay_ws = sh.add_worksheet(title=ebay_sheet_name, rows="100", cols="5")

        headers = ["商品ID", "商品タイトル", "価格", "現在の価格"]
        ebay_ws.clear()
        ebay_ws.append_row(headers)

        # ② eBayデータを書き込む & 商品ID→価格辞書を作成
        ebay_price_map = {}  # 商品ID → 価格の辞書
        for item in items:
            item_id = item.get("ItemID", "N/A")
            title = item.get("Title", "N/A")
            price = item.get("BuyItNowPrice", {}).get("#text", "N/A")
            current_price = item.get("SellingStatus", {}).get("CurrentPrice", {}).get("#text", "N/A")

            ebay_ws.append_row([item_id, title, price, current_price])

            if item_id != "N/A":
                ebay_price_map[item_id] = current_price or price  # 現在価格優先

        # ③ 対象シートリスト
        target_sheets = ["メルカリ", "ヤフオク", "楽天", "アマゾン"]

        for sheet_name in target_sheets:
            try:
                ws = sh.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                print(f"{sheet_name} シートが見つかりません。スキップします。")
                continue

            # 列D（商品ID）と行数を取得
            records = ws.get_all_values()
            if not records or len(records[0]) < 4:
                continue

            updated_rows = []
            for row_index, row in enumerate(records[1:], start=2):
                if len(row) >= 4:
                    item_id = row[3]  # 列D
                    ebay_price = ebay_price_map.get(item_id)
                    if ebay_price:
                        try:
                            float_price = float(ebay_price)
                        except ValueError:
                            continue

                        dollar_display = f"{float_price}ドル"
                        yen_display = f"{round(float_price * 145)}円"

                        # 改行付きで列I（9列目）に書き込む
                        combined_display = f"{dollar_display}\n{yen_display}"
                        ws.update_cell(row_index, 9, combined_display)  # 列Iのみ使用

        print("eBayデータと他シートの価格更新が完了しました。")

    except Exception as e:
        print(f"eBayデータ書き込みエラー: {e}")
        raise







from .utils import get_access_token, update_ebay_data




def execute_scraping_for_user(user):
    try:
        token = get_access_token()
        kousinn(user.id, token)
        return update_ebay_data(user.id)
    except Exception as e:
        return {"status": "error", "message": str(e)}





def kousinn(user_id, access_token):
    creds = get_credentials()
    gc = gspread.authorize(creds)

    # ユーザーのスプレッドシートIDを取得
    spreadsheet_id = get_user_spreadsheet_id(user_id)
    if not spreadsheet_id:
        print("スプレッドシートが見つかりません。新しいスプレッドシートを作成します。")
        spreadsheet_id = create_user_spreadsheet(user_id)

    # スプレッドシートを開く
    sh = gc.open_by_key(spreadsheet_id)
    
    for seet_num in range(1, 5):
        print(f"{seet_num} 番目のシートを処理中...")
        ws = sh.get_worksheet(seet_num - 1)  # シート番号は0始まり

        # Google Sheets のデータ反映を待つ
        print("スプレッドシートのデータ取得前に少し待機します...")
        time.sleep(5)  # 5秒待機


        existing_data = ws.get_all_values()

        # 1列目（A列）の2行目以降のデータを取得
        existing_urls = [row[0] for row in existing_data[1:] if len(row) > 0 and row[0].strip()]
       
        # # データ取得方法を変更
        # existing_data = ws.get_all_values()  # シート全体のデータを取得
        # existing_urls = [row[0] for row in existing_data if len(row) > 0]  # 列Aのみ取得

        print(f"取得したURLリスト: {existing_urls}")  # デバッグ用ログ

        # URLごとにスクレイピングしてデータを更新
        for row_index, url in enumerate(existing_urls[0:], start=2):  # 最初の行をヘッダーとしてスキップ
            if not url.strip():  # 空白をスキップ
                print(f"空のURLをスキップします (行 {row_index})")
                continue
            print(f"これが検索するURL: {url}")
            if "mercari" in url:
                data = scrape_mercari(url)
            elif "store.shopping.yahoo" in url:
                data = scrape_yahoo_shopping(url)
            elif "paypayfleamarket.yahoo" in url:
                data = scrape_yahoo_hurima(url)
            elif "yahoo" in url:
                data = scrape_yahoo(url)
            elif "item.fril" in url:
                data = scrape_rakuma(url)
            elif "item.rakuten" in url:
                data = scrape_rakuten(url)
            elif "amazon" in url:
                data = scrape_amazon(url)
            else:
                print(f"不明なURL形式です: {url}")
                continue



            # スクレイピング結果をスプレッドシートに書き込む
            write_to_google_sheets(data, user_id, url, None, seet_num)

                    
                
            title = ws.cell(row_index, 2).value
            price_condition = ws.cell(row_index, 3).value
            ebay_item_id = ws.cell(row_index, 4).value# eBayの対応商品IDがある列（列4）
            image_url = ws.cell(row_index, 5).value
            sales_status = ws.cell(row_index, 6).value  # 販売状況がある列（列6）



            if sales_status == "売り切れ" and ebay_item_id:
                print(f"売り切れの商品を検出しました (商品ID: {ebay_item_id})。出品を停止します。")
                # eBayの商品出品を停止
                result = end_ebay_listing(ebay_item_id, access_token)
                print(result)
            

            elif None in [title, price_condition]:
                print(f"週品ページが見つかりませんでした (商品ID: {ebay_item_id})。出品を停止します。")
                # eBayの商品出品を停止
                result = end_ebay_listing(ebay_item_id, access_token)
                print(result)

            # elif (title==None or price_condition==None or image_url==None) and ebay_item_id:
            #     print("おおおおおおお",title,)
            #     # eBayの商品出品を停止
            #     result = end_ebay_listing(ebay_item_id, access_token)
            #     print(result)

            else:
                print(f"売り切れの商品はありません")






    print("すべてのシートのスクレイピングが完了しました。")





def scrape_mercari(url):
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["mercari"]

    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--lang=ja-JP")

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    title = price = condition = image_url = description = status = None
    images_urls = []

    try:
        driver.get(url)

        # 商品タイトル
        title = get_text_by_selectors(driver, selectors["title"])
        if not title:
            print("タイトルの取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if not price:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品状態
        condition = get_text_by_selectors(driver, selectors["condition"])
        if not condition:
            print("商品の状態の取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )

        # メイン画像
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )


        # 説明文
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品の説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

        # すべての画像URL
        images_urls = []
        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")
            if images_urls:
                break
        if not images_urls:
            print("複数画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )


        # 在庫ステータス
        status = "在庫あり"
        sold_out_found = False

        try:
            for selector in selectors["sold_out"]:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)

                if not elements:
                    continue

                for element in elements:
                    aria_label = element.get_attribute("aria-label")
                    alt = element.get_attribute("alt")
                    text = element.text

                    print(f"在庫確認: selector={selector}, aria-label={aria_label}, alt={alt}, text={text}")

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "SOLD" in (text or "")
                    ):
                        status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫ステータスの取得に失敗しました: {e}")
            status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )

    except Exception as e:
        print(f"致命的なエラーが発生しました: {e}")
        title, price, condition, image_url, description, status, images_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls

def scrape_yahoo(url):
    selectors = load_selectors()["yahoo"]

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    title = price = condition = image_url = description = status = None
    images_urls = []

    try:
        driver.get(url)

        # オークション終了の確認
        status = "在庫あり"

        try:
            closed_found = False

            for selector in selectors["closed"]:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)

                if elements:
                    closed_found = True
                    break

            if closed_found:
                status = "在庫なし"

        except Exception as e:
            print(f"オークション終了確認に失敗しました: {e}")
            status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="status",
                selectors=selectors["closed"],
                driver=driver
            )

        # 商品タイトル
        title = get_text_by_selectors(driver, selectors["title"], timeout=5)

        if not title:
            print("商品タイトルの取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"], timeout=5)

        if price:
            price = price.split("\n")[0]
        else:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品の状態
        condition = get_text_by_selectors(driver, selectors["condition"], timeout=5)

        if not condition:
            print("商品の状態の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )

        # メイン画像URL
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src", timeout=5)

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content", timeout=5)

        if not image_url:
            print("画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )

        # 商品説明
        description = get_text_by_selectors(driver, selectors["description"], timeout=5)

        if not description:
            print("商品説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

        # 商品画像URLをすべて取得
        images_urls = []

        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")

            if images_urls:
                break

        if not images_urls:
            print("商品の画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )

    except Exception as e:
        print(f"Yahooスクレイピング中に致命的なエラーが発生しました: {e}")
        title, price, condition, image_url, description, status, images_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls


def scrape_yahoo_hurima(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    title = price = condition = image_url = description = status = images_urls = None

    try:
        try:
            # 売り切れ判定処理
            sold_images = driver.find_elements(By.CSS_SELECTOR, 'img[alt="sold"]')

            # 売り切れ画像が存在し、かつ表示されているかを確認
            if any(img.is_displayed() for img in sold_images):
                status = "売り切れ"
            else:
                status = "在庫あり"
        except NoSuchElementException:
            status = "在庫あり"

    #     try:
    # # 適切な範囲で `img[alt="sold"]` を取得
    #         sold_images = driver.find_elements(By.CSS_SELECTOR, '.sc-7fc76147-1 img[alt="sold"]')

    #         # 表示されている売り切れ画像があるかチェック
    #         if any(img.is_displayed() for img in sold_images):
    #             status = "売り切れ"
    #         else:
    #             status = "在庫あり"
    #     except NoSuchElementException:
    #         status = "在庫あり"
        # 商品タイトルを取得
        try:
            title = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.sc-7b08a9bb-0 span'))
            ).text
        except TimeoutException:
            print("タイトルの取得に失敗しました。")

        # 価格を取得
        try:
            price_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.sc-c8f146f8-0 span.gjEqBV'))
            )
            price = price_element.text + "円"
        except TimeoutException:
            print("価格の取得に失敗しました。")

        # 商品の状態を取得
        try:
            condition = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'td.sc-227e83e5-3 span'))
            ).text
        except TimeoutException:
            print("商品の状態の取得に失敗しました。")

        # メイン画像URLを取得
        try:
            image_url = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.slick-slide.slick-active img'))
            ).get_attribute('src')
        except TimeoutException:
            print("メイン画像URLの取得に失敗しました。")

        # 商品説明を取得
        try:
            description = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.ItemText__Text span'))
            ).text
        except TimeoutException:
            print("商品の説明の取得に失敗しました。")

        # 商品画像URLをすべて取得（特定の `<li>` を除外）
        try:
            ul_element = driver.find_element(By.CSS_SELECTOR, 'div.slick-track')
            li_elements = ul_element.find_elements(By.CSS_SELECTOR, 'div[data-index]:not([data-index="-1"])')

            images_urls = []
            for li in li_elements:
                img_element = li.find_element(By.CSS_SELECTOR, 'img')
                images_urls.append(img_element.get_attribute('src'))
        except TimeoutException:
            print("商品の画像URLの取得に失敗しました。")
            images_urls = None

    except Exception as e:
        print(f"要素の取得中にエラーが発生しました: {e}")

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls



def scrape_yahoo_shopping(url):
    # Seleniumのオプション設定
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    # ChromeDriverを初期化
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # デフォルト値の設定
    title = price = condition = image_url = description = stock_status = None
    all_image_urls = []

    try:
        # ページを開く
        driver.get(url)

        # 商品名を取得
        try:
            title = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.styles_itemName__Cf_Kt.styles_itemName__tCTR2 p.styles_name__u228e'))
            ).text
        except TimeoutException:
            print("商品名の取得に失敗しました。")
            title = None

        # 価格を取得
        try:
            price_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.styles_priceWrap__LAAeb p.styles_price__7WGwS'))
            )
            price = price_element.text.split("円")[0] + "円"  # 価格を整形
        except TimeoutException:
            print("価格の取得に失敗しました。")
            price = None

        # 商品の状態を取得
        try:
            condition_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.styles_itemName__Cf_Kt.styles_itemName__tCTR2 p.styles_itemType__rcD2w'))
            )
            condition = condition_element.text
        except TimeoutException:
            print("商品の状態の取得に失敗しました。")
            condition = None

        # 画像URL（一枚目）を取得
        try:
            image_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.splide__slide.is-active img.styles_image__Q5O03'))
            )
            image_url = image_element.get_attribute('src')
        except TimeoutException:
            print("画像URL（一枚目）の取得に失敗しました。")
            image_url = None

        # 全ての画像URLを取得
        try:
            ul_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.splide__list'))
            )
            li_elements = ul_element.find_elements(By.CSS_SELECTOR, 'li.splide__slide')
            for li in li_elements:
                img_element = li.find_element(By.CSS_SELECTOR, 'img.styles_image__Q5O03')
                all_image_urls.append(img_element.get_attribute('src'))
        except TimeoutException:
            print("全ての画像URLの取得に失敗しました。")
            all_image_urls = []

        # 在庫状況を取得
        try:
            stock_element = driver.find_element(By.CSS_SELECTOR, 'div.text-display--1Iony.color-crimson--_Y7TS')
            if "売り切れ" in stock_element.text:
                stock_status = "売り切れ"
            else:
                stock_status = "在庫あり"
        except NoSuchElementException:
            print("在庫状況の取得に失敗しました。")
            stock_status = None

        # 商品説明（仮でNoneに設定）
        description = None

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")

    finally:
        driver.quit()

    return title, price, condition, image_url, description, stock_status, all_image_urls



def scrape_rakuma(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    # デフォルト値を設定
    title = price = condition = image_url = description = status = None

    try:
        # 商品名を取得
        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CLASS_NAME, 'item__name'))
            )
            title = title_element.text
        except TimeoutException:
            print("商品名の取得に失敗しました。")

        # 価格を取得
        try:
            price_currency = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'item__currency-symbol'))
            ).text
            price_value = driver.find_element(By.CLASS_NAME, 'item__price').text
            price = price_currency + price_value
        except TimeoutException:
            print("価格の取得に失敗しました。")

        # 商品の状態を取得
        try:
            # ラベルを含む行を取得
            condition_row = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table.item__details th'))
            )

            # ラベルの隣にある値を取得
            condition_value = condition_row.find_element(By.XPATH, '../td').text.strip()
            condition = f"商品の状態: {condition_value}"
            print(f"商品の状態: {condition}")
        except TimeoutException:
            print("商品の状態の取得に失敗しました。")
            condition = None


        # 写真URLを取得
        try:
            image_url = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.sp-image-container > img'))
            ).get_attribute('src')
        except TimeoutException:
            print("写真URLの取得に失敗しました。")

        # 商品説明を取得
        try:
            description = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'item__description__line-limited'))
            ).text
        except TimeoutException:
            print("商品説明の取得に失敗しました。")

        # 在庫状況を確認
        try:
            sold_out_element = driver.find_element(By.CSS_SELECTOR, 'span.type-modal__contents--button--sold')
            if sold_out_element:
                status = "売り切れ"
        except Exception:
            status = "在庫あり"  # 売り切れ要素が見つからなければ在庫あり
            print("売り切れ要素が見つかりませんでした。デフォルトで在庫ありに設定します。")

        try:
            images_urls="あああ"
        except TimeoutException:
            print("写真たちのURLの取得に失敗しました。")
            

    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls





def scrape_rakuten(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    # 初期化
    title = price = condition = image_url = description = status = None
    images_urls = []

    try:
        # 商品名を取得
        try:
            title_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.normal_reserve_item_name > b'))
            )
            title = title_element.text
        except TimeoutException:
            print("商品名の取得に失敗しました。")
            title = None

        # 価格を取得
        try:
            price_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.value--3Z7Nj'))
            )
            price = price_element.text
        except TimeoutException:
            print("価格の取得に失敗しました。")
            price = None

        # 商品の状態を取得
        try:
            # 商品状態が格納されている <td> 要素を取得
            condition_element = driver.find_element(By.CSS_SELECTOR, 'td[irc="ConditionTag"]')

            # <td> 内に中古を示す特定の <div> 要素があるか確認
            try:
                used_element = condition_element.find_element(By.CSS_SELECTOR, 'div.logo--392k6.used-acceptable--OOlqc')
                condition = "中古"  # 中古の場合
            except NoSuchElementException:
                condition = "新品"  # 中古要素がない場合は新品
        except NoSuchElementException:
            print("商品の状態の取得に失敗しました。デフォルト値を使用します。")
            condition = "新品"  # デフォルト値

        # メイン画像URLを取得
        try:
            main_image_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.image-wrapper--1-6ju img'))
            )
            image_url = main_image_element.get_attribute('src')
        except TimeoutException:
            print("メイン画像URLの取得に失敗しました。")
            image_url = None

        # 商品説明を取得
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, 'td[irc="SpecTableArea"]')
            description = description_element.text.strip()  # テキストを取得して余分な空白を除去
        except NoSuchElementException:
            print("商品の説明の取得に失敗しました。")
            description = None

        # 在庫情報を取得
        try:
            # 売り切れを示す特定の <div> 要素を検索
            sold_out_element = driver.find_element(By.CSS_SELECTOR, 
                                                'div.text-display--1Iony.type-body--1W5uC.size-medium--JpmnL.align-left--1hi1x.color-crimson--_Y7TS.layout-inline--1ajCj')

            # 売り切れ文言を確認
            if "この商品は売り切れです" in sold_out_element.text:
                status = "売り切れ"  # 売り切れの場合
            else:
                status = "在庫あり"  # 売り切れ文言がない場合
        except NoSuchElementException:
            # 売り切れ要素が見つからない場合は在庫ありと判断
            print("売り切れ要素が見つかりませんでした。")
            status = "在庫あり"  # デフォルト値

        # すべての画像URLを取得
        try:
            image_elements = driver.find_elements(By.CSS_SELECTOR, 'div.image-wrapper--1-6ju img')
            images_urls = [img.get_attribute('src') for img in image_elements]
        except TimeoutException:
            print("すべての画像URLの取得に失敗しました。")
            images_urls = []

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls




def scrape_amazon(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--lang=ja-JP')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    # デフォルト値を設定
    title = price = image_url = description = stock_status = None

    try:
        # 商品名を取得
        try:
            title = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, 'productTitle'))
            ).text.strip()
            print("title")
        except TimeoutException:
            print("商品名の取得に失敗しました。")

        # 価格を取得
        try:
            price_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'a-price-whole'))
            )
            price = price_element.text.strip() + "円"
        except TimeoutException:
            print("価格の取得に失敗しました。")

        condition="新品"

        # 商品画像のURLを取得
        try:
            image_url = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, 'landingImage'))
            ).get_attribute('src')
        except TimeoutException:
            print("画像URLの取得に失敗しました。")

        # 商品説明を取得
        try:
            description_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, 'feature-bullets'))
            )
            description = description_element.text.strip()
        except TimeoutException:
            print("商品の説明の取得に失敗しました。")

        # 在庫状況を確認
        try:
            sold_out_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.a-section.a-spacing-base._Y2VyY_wgtHeading_2CLNq h2.a-size-large.a-spacing-none.a-text-normal'))
            )
            if sold_out_element:
                status = "売り切れ"
        except TimeoutException:
            status = "在庫あり"  # "代替商品"要素が見つからなければ在庫あり


        
        try:
            images_urls="あああ"
        except TimeoutException:
            print("写真たちのURLの取得に失敗しました。")

    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls


  







# 認証情報を取得する関数
def get_credentials():
    try:
        credentials_info = json.loads(os.getenv('GOOGLE_SHEET_CREDENTIALS'))
        SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
        ]   
        creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        return creds
    except Exception as e:
        print(f"認証エラー: {e}")
        raise



def create_user_spreadsheet(user_id):
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)

        # スプレッドシートの作成
        spreadsheet = service.spreadsheets().create(
            body={
                'properties': {'title': f'User {user_id} Spreadsheet'},
                'sheets': [
                    {'properties': {'title': 'メルカリ'}},
                    {'properties': {'title': 'ヤフオク'}},
                    {'properties': {'title': '楽天'}},
                    {'properties': {'title': 'アマゾン'}},
                ]
            },
            fields='spreadsheetId'
        ).execute()

        spreadsheet_id = spreadsheet.get('spreadsheetId')
        print(f"新しいスプレッドシートID: {spreadsheet_id}")

        # スプレッドシートを「誰でも」編集可能にする
        drive_service = build('drive', 'v3', credentials=creds)
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={'type': 'anyone', 'role': 'writer'},
            fields='id'
        ).execute()

        # ヘッダーを追加する
        sheet_service = service.spreadsheets().values()

        # メルカリのヘッダー
        mercari_headers = [["URL", "商品名", "商品の価格と状態", "紐づけebay商品ID", "画像", "販売状況", "商品説明","写真のURL"]]
        sheet_service.update(
            spreadsheetId=spreadsheet_id,
            range="メルカリ!A1:H1",
            valueInputOption="RAW",
            body={"values": mercari_headers}
        ).execute()

        # ヤフオクのヘッダー
        yahoo_headers = [["URL", "商品名", "商品の価格と状態", "紐づけebay商品ID", "画像", "商品説明", "販売状況","写真のURL"]]
        sheet_service.update(
            spreadsheetId=spreadsheet_id,
            range="ヤフオク!A1:H1",
            valueInputOption="RAW",
            body={"values": yahoo_headers}
        ).execute()

        # 楽天のヘッダー
        rakuten_headers = [["URL", "商品名","商品の価格と状態" , "紐づけebay商品ID",  "画像", "販売状況", "商品説明","写真のURL"]]
        sheet_service.update(
            spreadsheetId=spreadsheet_id,
            range="楽天!A1:H1",
            valueInputOption="RAW",
            body={"values": rakuten_headers}
        ).execute()

         # アマゾンのヘッダー
        amazon_headers = [["URL", "商品名","商品の価格と状態" , "紐づけebay商品ID",  "画像", "販売状況", "商品説明","写真のURL"]]
        sheet_service.update(
            spreadsheetId=spreadsheet_id,
            range="アマゾン!A1:H1",
            valueInputOption="RAW",
            body={"values": amazon_headers}
        ).execute()

        # データベースにスプレッドシートIDを保存
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO work1_spreadsheet (user_id, spreadsheet_id, created_at) VALUES (%s, %s, %s)",
            (user_id, spreadsheet_id, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()

        return spreadsheet_id

    except Exception as e:
        print(f"スプレッドシート作成エラー: {e}")
        return None


# スプレッドシートIDの取得関数
def get_user_spreadsheet_id(user_id):
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        cursor.execute("SELECT spreadsheet_id FROM work1_spreadsheet WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"データベースエラー: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def write_to_google_sheets(data, user_id, url, request, seet_num):
    try:
        print("ユーザーID", user_id)
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sheets_service = build('sheets', 'v4', credentials=creds)  # Google Sheets APIを使用

        spreadsheet_id = get_user_spreadsheet_id(user_id)
        if not spreadsheet_id:
            spreadsheet_id = create_user_spreadsheet(user_id)

        print("spreadsheet_id", spreadsheet_id)
        sh = gc.open_by_key(spreadsheet_id)

        print(f"スプレッドシートID: {spreadsheet_id} は「誰でも」編集可能に設定されました。")

        # 指定されたシート番号に基づいてシートを取得
        ws = sh.get_worksheet(seet_num - 1)  # シート番号は0始まり
        existing_urls = ws.col_values(1)

        if url in existing_urls:
            row_index = existing_urls.index(url) + 1
            print(f"既存のURLが見つかりました。行番号: {row_index}")
        else:
            row_index = len(existing_urls) + 1
            print(f"新しいURLを追加します。行番号: {row_index}")

        # data[3] (画像URL) の検証とデフォルト値の設定
        clean_image_url = data[3].split('?')[0] if data[3] else "https://via.placeholder.com/150"
        image_formula = f'=IMAGE("{clean_image_url}", 4, 100, 100)'

        # 価格と状態を改行で結合
        price_with_status = f"{data[1]}\n{data[2]}" if data[1] and data[2] else data[1] or data[2] or "N/A"

        # 写真のURLを改行で結合
        photo_urls = "\n".join(data[6]) if isinstance(data[6], list) else data[6]

        # 各データを指定した行に書き込む
        ws.update_cell(row_index, 1, url)            # URL
        ws.update_cell(row_index, 2, data[0])        # タイトル
        ws.update_cell(row_index, 3, price_with_status)  # 価格と状態を改行で同じセルに書き込む
        ws.update_cell(row_index, 5, image_formula)  # 画像（列4は空白を保持）
        ws.update_cell(row_index, 6, data[5])        # 販売状況 (売り切れ/在庫あり)
        ws.update_cell(row_index, 8, "")             # 写真のURLセルを空にする

        # 商品説明をコメントとして追加（セル自体は空）
        if data[4]:  # 商品説明が存在する場合
            comment_body = {
                "requests": [
                    {
                        "updateCells": {
                            "rows": [
                                {
                                    "values": [
                                        {
                                            "note": data[4]  # 商品説明をコメントとして設定
                                        }
                                    ]
                                }
                            ],
                            "fields": "note",
                            "range": {
                                "sheetId": ws.id,
                                "startRowIndex": row_index - 1,  # Google Sheets APIは0始まり
                                "endRowIndex": row_index,        # 対象行のみ
                                "startColumnIndex": 6,          # G列（0始まり: G列が6）
                                "endColumnIndex": 7             # G列の範囲
                            }
                        }
                    }
                ]
            }
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=comment_body
            ).execute()
            print(f"コメントとして商品説明を追加しました: {data[4]}")

        # 写真のURLをコメントとして追加（セル自体は空）
        if photo_urls:  # 写真のURLが存在する場合
            comment_body = {
                "requests": [
                    {
                        "updateCells": {
                            "rows": [
                                {
                                    "values": [
                                        {
                                            "note": photo_urls  # 写真のURLをコメントとして設定
                                        }
                                    ]
                                }
                            ],
                            "fields": "note",
                            "range": {
                                "sheetId": ws.id,
                                "startRowIndex": row_index - 1,  # Google Sheets APIは0始まり
                                "endRowIndex": row_index,        # 対象行のみ
                                "startColumnIndex": 7,          # H列（0始まり: H列が7）
                                "endColumnIndex": 8             # H列の範囲
                            }
                        }
                    }
                ]
            }
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=comment_body
            ).execute()
            print(f"コメントとして写真のURLを追加しました: {photo_urls}")

        print(f"スプレッドシートID: {spreadsheet_id}")
        print(f"行番号: {row_index}, 書き込みデータ: {data}")

    except Exception as e:
        import traceback
        print(f"データ書き込みエラー: {e}")
        traceback.print_exc()
        raise



def upgrade_spreadsheets():
    try:
        # 認証情報を取得
        creds = get_credentials()
        gc = gspread.authorize(creds)

        # データベース接続
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()

        # すべてのスプレッドシートIDを取得
        cursor.execute("SELECT spreadsheet_id FROM work1_spreadsheet")
        spreadsheet_ids = cursor.fetchall()

        # 各スプレッドシートをアップグレード
        for spreadsheet_id in spreadsheet_ids:
            spreadsheet_id = spreadsheet_id[0]
            print(f"アップグレード中: {spreadsheet_id}")

            # スプレッドシートを開く
            sh = gc.open_by_key(spreadsheet_id)

            # 更新対象のシート名
            sheet_names = ["メルカリ", "ヤフオク", "楽天", "アマゾン"]

            # 各シートを更新
            for sheet_name in sheet_names:
                try:
                    ws = sh.worksheet(sheet_name)  # シートを取得

                    # 現在のヘッダーを取得
                    existing_headers = ws.row_values(1)

                    # "写真のURL"がすでに追加されていない場合のみ追加
                    if "写真のURL" not in existing_headers:
                        existing_headers.append("写真のURL")  # 新しい列を追加
                        ws.update("A1", [existing_headers])  # ヘッダー行を更新
                        print(f"{sheet_name} のヘッダーを更新しました: {existing_headers}")
                    else:
                        print(f"{sheet_name} のヘッダーには既に '写真のURL' が含まれています。")

                except gspread.exceptions.WorksheetNotFound:
                    print(f"{sheet_name} シートが見つかりませんでした。スキップします。")

        # データベース接続を閉じる
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"アップグレード中にエラーが発生しました: {e}")
