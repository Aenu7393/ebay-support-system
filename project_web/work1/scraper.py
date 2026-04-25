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

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception as e:
        print(f"HTML保存に失敗しました: {e}")

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
    print("exists json:", json_path.exists())
    print("exists html:", html_path.exists())

    return json_path


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

    # 失敗JSONのパスをためる
    failure_json_paths = []

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
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if not price:
            print("価格の取得に失敗しました。")
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

        # 商品状態
        condition = get_text_by_selectors(driver, selectors["condition"])
        if not condition:
            print("商品の状態の取得に失敗しました。")
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

        # メイン画像
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("画像URLの取得に失敗しました。")
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

        # 説明文
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品の説明の取得に失敗しました。")
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

        # すべての画像URL
        images_urls = []
        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")
            if images_urls:
                images_urls = list(dict.fromkeys(images_urls))
                break

        if not images_urls:
            print("複数画像URLの取得に失敗しました。")
            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)

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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
                    ):
                        status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫ステータスの取得に失敗しました: {e}")
            status = "ステータスを取得できませんでした"

            failure_json_path = save_scraping_failure(
                site_name="mercari",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )
            if failure_json_path:
                failure_json_paths.append(failure_json_path)


        # 失敗が1つでもあれば、最初の1件だけAIに渡す
        if failure_json_paths:
            try:
                import sys
                from pathlib import Path

                scraper_dir = Path(__file__).resolve().parent

                if str(scraper_dir) not in sys.path:
                    sys.path.insert(0, str(scraper_dir))

                from ai_selector_repair import propose_selector_fix

                print("AIセレクタ修正案を生成します。対象:", failure_json_paths[0])

                proposal = propose_selector_fix(failure_json_paths[0])

                print("AIセレクタ修正案:")
                print(proposal)

            except Exception as e:
                print(f"AIセレクタ修正案の生成に失敗しました: {e}")

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
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["yahoo_hurima"]

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
                site_name="yahoo_hurima",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if price and not price.endswith("円"):
            price = price + "円"

        if not price:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_hurima",
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
                site_name="yahoo_hurima",
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
                site_name="yahoo_hurima",
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
                site_name="yahoo_hurima",
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
                # 重複削除
                images_urls = list(dict.fromkeys(images_urls))
                break

        if not images_urls:
            print("複数画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_hurima",
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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
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
                site_name="yahoo_hurima",
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



def scrape_yahoo_shopping(url):
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["yahoo_shopping"]

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

    title = price = condition = image_url = description = stock_status = None
    all_image_urls = []

    try:
        driver.get(url)

        # 商品名
        title = get_text_by_selectors(driver, selectors["title"])
        if not title:
            print("商品名の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if price:
            price = price.split("円")[0] + "円"

        if not price:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品の状態
        condition = get_text_by_selectors(driver, selectors["condition"])
        if not condition:
            print("商品の状態の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )

        # メイン画像URL
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("画像URL（一枚目）の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )

        # すべての画像URL
        all_image_urls = []
        for selector in selectors["images"]:
            all_image_urls = get_attributes_by_selector(driver, selector, "src")
            if all_image_urls:
                all_image_urls = list(dict.fromkeys(all_image_urls))
                break

        if not all_image_urls:
            print("全ての画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )

        # 在庫状況
        stock_status = "在庫あり"
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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "在庫なし" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
                    ):
                        stock_status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫状況の取得に失敗しました: {e}")
            stock_status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )

        # 商品説明
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品の説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="yahoo_shopping",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        title, price, condition, image_url, description, stock_status, all_image_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

    finally:
        driver.quit()

    return title, price, condition, image_url, description, stock_status, all_image_urls



def scrape_rakuma(url):
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["rakuma"]

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

        # 商品名
        title = get_text_by_selectors(driver, selectors["title"])
        if not title:
            print("商品名の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if price and not price.startswith("¥") and not price.startswith("￥"):
            price = "¥" + price

        if not price:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品の状態
        condition = get_text_by_selectors(driver, selectors["condition"])
        if condition:
            condition = f"商品の状態: {condition}"

        if not condition:
            print("商品の状態の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )

        # メイン画像URL
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("写真URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )

        # 商品説明
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

        # 複数画像URL
        images_urls = []
        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")
            if images_urls:
                images_urls = list(dict.fromkeys(images_urls))
                break

        if not images_urls:
            print("写真たちのURLの取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )

        # 在庫状況
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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
                    ):
                        status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫状況の取得に失敗しました: {e}")
            status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="rakuma",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )

    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
        title, price, condition, image_url, description, status, images_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls





def scrape_rakuten(url):
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["rakuten"]

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

        # 商品名
        title = get_text_by_selectors(driver, selectors["title"])
        if not title:
            print("商品名の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuten",
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
                site_name="rakuten",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品の状態
        condition = get_text_by_selectors(driver, selectors["condition"])

        if not condition:
            # 中古判定用の要素があれば中古、なければ新品
            used_found = False

            try:
                for selector in selectors["used_condition"]:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        used_found = True
                        break

                if used_found:
                    condition = "中古"
                else:
                    condition = "新品"

            except Exception as e:
                print(f"商品の状態の判定に失敗しました: {e}")
                condition = "新品"

        if not condition:
            print("商品の状態の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuten",
                url=url,
                field_name="condition",
                selectors=selectors["condition"],
                driver=driver
            )

        # メイン画像URL
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("メイン画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuten",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )

        # 商品説明
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品の説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuten",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

        # 在庫情報
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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "売り切れです" in (text or "")
                        or "この商品は売り切れです" in (text or "")
                        or "在庫なし" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
                    ):
                        status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫情報の取得に失敗しました: {e}")
            status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="rakuten",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )

        # すべての画像URL
        images_urls = []
        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")
            if images_urls:
                images_urls = list(dict.fromkeys(images_urls))
                break

        if not images_urls:
            print("すべての画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="rakuten",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        title, price, condition, image_url, description, status, images_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

    finally:
        driver.quit()

    return title, price, condition, image_url, description, status, images_urls


def scrape_amazon(url):
    if not url or not url.startswith("http"):
        print("無効なURL:", url)
        return None, None, None, None, None, "ステータスを取得できませんでした", []

    selectors = load_selectors()["amazon"]

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

        # 商品名
        title = get_text_by_selectors(driver, selectors["title"])
        if not title:
            print("商品名の取得に失敗しました。")
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="title",
                selectors=selectors["title"],
                driver=driver
            )

        # 価格
        price = get_text_by_selectors(driver, selectors["price"])
        if price:
            price = price.strip()
            if not price.endswith("円") and "￥" not in price and "¥" not in price:
                price = price + "円"

        if not price:
            print("価格の取得に失敗しました。")
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="price",
                selectors=selectors["price"],
                driver=driver
            )

        # 商品状態
        condition = get_text_by_selectors(driver, selectors["condition"])
        if not condition:
            condition = "新品"

        # メイン画像URL
        image_url = get_attribute_by_selectors(driver, selectors["image_url"], "src")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "data-old-hires")

        if not image_url:
            image_url = get_attribute_by_selectors(driver, selectors["image_url"], "content")

        if not image_url:
            print("画像URLの取得に失敗しました。")
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="image_url",
                selectors=selectors["image_url"],
                driver=driver
            )

        # 商品説明
        description = get_text_by_selectors(driver, selectors["description"])
        if not description:
            print("商品の説明の取得に失敗しました。")
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="description",
                selectors=selectors["description"],
                driver=driver
            )

        # 複数画像URL
        images_urls = []
        for selector in selectors["images"]:
            images_urls = get_attributes_by_selector(driver, selector, "src")
            if images_urls:
                images_urls = list(dict.fromkeys(images_urls))
                break

        if not images_urls and image_url:
            images_urls = [image_url]

        if not images_urls:
            print("写真たちのURLの取得に失敗しました。")
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="images",
                selectors=selectors["images"],
                driver=driver
            )

        # 在庫状況
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

                    print(
                        f"在庫確認: selector={selector}, "
                        f"aria-label={aria_label}, alt={alt}, text={text}"
                    )

                    if (
                        aria_label == "売り切れ"
                        or alt == "sold"
                        or "売り切れ" in (text or "")
                        or "在庫切れ" in (text or "")
                        or "現在在庫切れ" in (text or "")
                        or "一時的に在庫切れ" in (text or "")
                        or "この商品は現在お取り扱いできません" in (text or "")
                        or "SOLD" in (text or "")
                        or "sold" in (alt or "").lower()
                    ):
                        status = "売り切れ"
                        sold_out_found = True
                        break

                if sold_out_found:
                    break

        except Exception as e:
            print(f"在庫状況の取得に失敗しました: {e}")
            status = "ステータスを取得できませんでした"
            save_scraping_failure(
                site_name="amazon",
                url=url,
                field_name="status",
                selectors=selectors["sold_out"],
                driver=driver
            )

    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
        title, price, condition, image_url, description, status, images_urls = (
            None, None, None, None, None, "ステータスを取得できませんでした", []
        )

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
