from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from .scraper import scrape_yahoo_shopping, scrape_rakuten,scrape_yahoo_hurima, scrape_amazon,scrape_mercari, scrape_yahoo, scrape_rakuma, write_to_google_sheets,get_user_spreadsheet_id,get_ebay_selling_items,write_ebay_to_google_sheets,kousinn,execute_scraping_for_user
import urllib.parse
import json
import requests
import base64
from datetime import timedelta
from .models import eBayAuthToken
import uuid
import threading
import os

#出品サイトへ

def ebay_form(request):
    """出品フォームのページをレンダリング"""
    return render(request, "work1/ebay_form.html")




def get_category_fields(request):
    category_id = request.GET.get('category_id')

    if not category_id:
        return JsonResponse({"error": "カテゴリIDが指定されていません"}, status=400)

    # 固定された category_tree_id（例: US マーケットプレイス）
    category_tree_id = "0"  # 必要に応じて変更（USの場合は "0"）

    # 正しい eBay API エンドポイント
    ebay_api_url = (
        f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_item_aspects_for_category"
        f"?category_id={category_id}"
    )

    # アクセストークンを取得（models から取得する）
    try:
        ebay_token = eBayAuthToken.objects.latest('expires_at').access_token
    except eBayAuthToken.DoesNotExist:
        return JsonResponse({"error": "eBayアクセストークンが見つかりません"}, status=500)

    headers = {
        "Authorization": f"Bearer {ebay_token}",
        "Content-Type": "application/json",
    }

    # APIリクエストを送信
    try:
        response = requests.get(ebay_api_url, headers=headers)
        if response.status_code != 200:
            print(f"APIエラー: ステータスコード {response.status_code}, 内容: {response.text}")
            return JsonResponse({"error": "eBay APIの呼び出しに失敗しました"}, status=response.status_code)

        response_data = response.json()

        # 必須項目を取得
        fields = [
            {
                "name": aspect.get("localizedAspectName"),
                "required": aspect.get("aspectConstraint", {}).get("aspectRequired", False),
            }
            for aspect in response_data.get("aspects", [])
        ]

        print(f"カテゴリID: {category_id}, 必須項目: {fields}")  # デバッグ用ログ
        return JsonResponse(fields, safe=False)

    except requests.exceptions.RequestException as e:
        print(f"APIリクエストエラー: {e}")
        return JsonResponse({"error": "eBay APIリクエストに失敗しました"}, status=500)



import uuid
import requests
from django.http import JsonResponse
from .models import eBayAuthToken

import uuid
import requests
from django.http import JsonResponse
from .models import eBayAuthToken


def list_item(request):
    if request.method == "POST":
        # 基本情報を取得
        title = request.POST.get('title')
        price = request.POST.get('price')
        description = request.POST.get('description')
        image_url = request.POST.get('image_url')
        category_id = request.POST.get('category')

        # 必須フィールドのチェック
        if not all([title, price, description, image_url, category_id]):
            return JsonResponse({"error": "全ての必須フィールドを入力してください"}, status=400)

        # ユニークなSKUを生成
        sku = str(uuid.uuid4())
        print(f"Generated SKU: {sku}")

        # eBayアクセストークンを取得
        try:
            access_token = eBayAuthToken.objects.latest('expires_at').access_token
        except eBayAuthToken.DoesNotExist:
            return JsonResponse({"error": "eBayアクセストークンが見つかりません"}, status=500)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json", 
        }

        # カテゴリ特有の項目（aspects）を収集（空の値は除外）
        category_fields = {
            key: [value] for key, value in request.POST.items()
            if key not in ['csrfmiddlewaretoken', 'title', 'price', 'description', 'image_url', 'category']
            and value.strip() != ""
        }

        inventory_payload = {
            "sku": sku,
            "marketplaceId": "EBAY_US",  
            "product": {
                "title": title,
                "description": description,
                "aspects": category_fields,
                "imageUrls": [image_url],
            },
            "condition": "NEW",
        }

        print("在庫登録ペイロード:", inventory_payload)

        # **(1) 在庫登録**
        inventory_url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
        inventory_response = requests.put(inventory_url, headers=headers, json=inventory_payload)

        if inventory_response.status_code not in [200, 204]:  # 204は成功、200は更新成功
            try:
                inventory_response_data = inventory_response.json()
            except ValueError:
                inventory_response_data = {"error": "レスポンスのJSONデコードに失敗"}
            print("在庫登録エラー:", inventory_response_data)
            return JsonResponse({"error": "在庫登録エラー", "details": inventory_response_data}, status=inventory_response.status_code)

        print("在庫登録成功")

        # **(2) オファー作成**
        offer_payload = {
            "sku": sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "listingDescription": description,
            "pricingSummary": {"price": {"value": float(price), "currency": "USD"}},
        }

        print("オファー作成ペイロード:", offer_payload)

        offer_response = requests.post("https://api.ebay.com/sell/inventory/v1/offer", headers=headers, json=offer_payload)

        try:
            offer_response_data = offer_response.json()
        except ValueError:
            offer_response_data = {"error": "レスポンスのJSONデコードに失敗"}

        print("オファー作成レスポンス:", offer_response_data)

        if offer_response.status_code != 201 or "errors" in offer_response_data:
            return JsonResponse({"error": "オファー作成エラー", "details": offer_response_data}, status=offer_response.status_code)

        offer_id = offer_response_data.get("offerId")
        if not offer_id:
            return JsonResponse({"error": "オファーIDの取得に失敗しました", "details": offer_response_data}, status=500)

        print(f"オファー作成成功: offer_id={offer_id}")

        # **(3) オファーの公開**
        publish_url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
        publish_response = requests.post(publish_url, headers=headers)

        try:
            publish_response_data = publish_response.json()
        except ValueError:
            publish_response_data = {"error": "レスポンスのJSONデコードに失敗"}

        print("オファー公開レスポンス:", publish_response_data)

        if publish_response.status_code != 200 or "errors" in publish_response_data:
            return JsonResponse({"error": "オファー公開エラー", "details": publish_response_data}, status=publish_response.status_code)

        print("オファー公開成功")

        return JsonResponse({"success": "商品が出品されました", "offer_id": offer_id})

    return JsonResponse({"error": "無効なリクエスト"}, status=400)
# @csrf_exempt
# def list_item(request):
#     """フォームから受け取った情報を基にeBay出品"""
#     if request.method == 'POST':
#         try:
#             # アクセストークンを取得
#             access_token = get_access_token()

#             # eBay APIに送信するデータを準備
#             item_data = {
#                 "title": request.POST.get('title'),
#                 "price": request.POST.get('price'),
#                 "description": request.POST.get('description'),
#                 "category_id": request.POST.get('category_id'),
#             }

#             # eBay APIにリクエストを送信
#             ebay_api_url = "https://api.ebay.com/sell/inventory/v1/item"
#             headers = {
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#             }
#             response = requests.post(ebay_api_url, json=item_data, headers=headers)
#             response_data = response.json()

#             # 成功/失敗のレスポンスを返す
#             if response.status_code == 201:
#                 return JsonResponse({"message": "出品が完了しました！", "data": response_data})
#             else:
#                 return JsonResponse({"message": "出品に失敗しました。", "error": response_data}, status=400)

#         except ValueError as e:
#             return JsonResponse({"message": str(e)}, status=400)

#     return JsonResponse({"message": "無効なリクエストです。"}, status=405)




@method_decorator(login_required, name='dispatch')
class UpdateScrapersView(View):
    def post(self, request, *args, **kwargs):
        user = request.user

        # 非同期でスクレイピング処理を実行
        thread = threading.Thread(target=execute_scraping_for_user, args=(user,))
        thread.start()

        # 即レスポンス返してユーザーをトップページへ
        return redirect("/")
        

def update_ebay_data(user_id):
    try:
        # アクセストークンを取得
        token = eBayAuthToken.objects.first()
        if not token:
            raise Exception("eBayトークンが見つかりません")

        access_token = token.access_token
        items = get_ebay_selling_items(access_token)
        if items:
            write_ebay_to_google_sheets(user_id, items)
            return {"status": "success"}
        else:
            return {"status": "error", "message": "eBay出品情報の取得に失敗しました。"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@method_decorator(login_required, name='dispatch')
class UpdateEbayView(View):
    def post(self, request):
        user_id = request.user.id

        
        try:
            access_token = get_access_token()  # アクセストークンを取得
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}", status=500)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        

        try:
            items = get_ebay_selling_items(access_token)
            if items:
                write_ebay_to_google_sheets(user_id, items)
                # 成功時に元のページにリダイレクト
                return redirect('/')
            else:
                return JsonResponse({"status": "error", "message": "eBay出品情報の取得に失敗しました。"}, status=500)
        except Exception as e:
            print(f"エラー: {e}")
            return JsonResponse({"status": "error", "message": "エラーが発生しました。"}, status=500)



EXPECTED_TOKEN = os.getenv("EXPECTED_TOKEN")


def privacy_policy(request):
    return render(request, 'privacy_policy.html')


def oauth_declined(request):
    return render(request, 'oauth_declined.html')

from datetime import datetime, timedelta
from .models import eBayAuthToken

def callback(request):
    """
    eBayからリダイレクトされた後、アクセストークンを取得し保存する。
    """
    authorization_code = request.GET.get('code', None)
    if not authorization_code:
        return HttpResponse("Authorization code not found", status=400)

    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")

    redirect_uri = os.getenv("EBAY_REDIRECT_URI")
    token_url = os.getenv("EBAY_TOKEN_URL")
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
    }

    # eBayからトークンを取得
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()

        # スコープをログに出して確認
        print("取得したスコープ:", token_data.get('scope', 'スコープなし'))

        # トークン情報を保存
        eBayAuthToken.objects.update_or_create(
            id=1,
            defaults={
                "access_token": token_data['access_token'],
                "refresh_token": token_data['refresh_token'],
                "expires_at": timezone.now() + timedelta(seconds=token_data['expires_in']),
            }
        )
        return redirect("/")
    else:
        return HttpResponse(f"Error: {response.text}", status=500)



def refresh_access_token():
    """
    リフレッシュトークンを使って新しいアクセストークンを取得する。
    """
    token = eBayAuthToken.objects.first()
    if not token or not token.refresh_token:
        raise Exception("No refresh token available. Please authenticate again.")

    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    token_url = os.getenv("EBAY_TOKEN_URL")
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        # "scope" を削除
    }
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        token.access_token = token_data['access_token']
        token.expires_at = timezone.now() + timedelta(seconds=token_data['expires_in'])
        token.save()
        return token.access_token
    else:
        raise Exception(f"Failed to refresh token: {response.text}")

def get_access_token():
    """
    eBayのアクセストークンを取得または更新する。
    """
    # データベースからトークンを取得
    token = eBayAuthToken.objects.first()
    if not token:
        raise Exception("No token available. Please authenticate first.")

    # トークンが期限切れの場合はリフレッシュ
    if token.expires_at <= timezone.now():
        return refresh_access_token()
    
    return token.access_token




from .forms import CustomUserCreationForm
class SignupView(View):
    def get(self, request):
        form = CustomUserCreationForm()
        return render(request, 'work1/signup.html', {'form': form})

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/accounts/login/')  # ログインページにリダイレクト
        return render(request, 'work1/signup.html', {'form': form})

signup = SignupView.as_view()

def generate_auth_url():
    client_id = os.getenv("EBAY_CLIENT_ID")
    redirect_uri = os.getenv("EBAY_REDIRECT_URI")
    scope = "https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/commerce.taxonomy.readonly"
    encoded_scope = urllib.parse.quote(scope)  # URLエンコードを適用

    auth_url = (
        f"https://auth.ebay.com/oauth2/authorize?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={encoded_scope}"
    )
    return auth_url

@method_decorator(login_required, name='dispatch')
class IndexView(View):
    @method_decorator(login_required)
    def get(self, request):
        user_id = request.user.id
        spreadsheet_id = get_user_spreadsheet_id(user_id)
        
        if spreadsheet_id:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        else:
            sheet_url = None  # スプレッドシートがまだ作成されていない場合

        auth_url = generate_auth_url()

        return render(request, "work1/index.html", {"sheet_url": sheet_url, "auth_url": auth_url})

    def post(self, request):
        try:
            url = request.POST.get('url')
            user_id = request.user.id
            print("POST / called")
            print("url:", url)
            print("user_id:", user_id)

            if "mercari" in url:#メルカリ
                data = scrape_mercari(url)
                print("scrape_mercari done")
                write_to_google_sheets(data, user_id, url, request, 1)

            elif "store.shopping.yahoo" in url:#ヤフーショッピング
                data = scrape_yahoo_shopping(url)
                print("scrape_yahoo_shopping done")
                write_to_google_sheets(data, user_id, url, request, 2)

            elif "paypayfleamarket.yahoo" in url:#ヤフオクフリマ
                data = scrape_yahoo_hurima(url)
                print("scrape_yahoo_hurima done")
                write_to_google_sheets(data, user_id, url, request, 2)

            elif "yahoo" in url:#ヤフオク
                data = scrape_yahoo(url)
                print("scrape_yahoo done")
                write_to_google_sheets(data, user_id, url, request, 2)

            elif "item.fril" in url:#ラクマ
                data = scrape_rakuma(url)
                print("scrape_rakuma done")
                write_to_google_sheets(data, user_id, url, request, 3)

            elif "item.rakuten" in url:#楽天
                data = scrape_rakuten(url)
                print("scrape_rakuten done")
                write_to_google_sheets(data, user_id, url, request, 3)

            elif "amazon" in url:#アマゾン
                data = scrape_amazon(url)
                print("scrape_amazon done")
                write_to_google_sheets(data, user_id, url, request, 4)

            else:
                print("unknown url format:", url)

            return redirect('/')

        except Exception as e:
            import traceback
            print("IndexView.post error:", e)
            traceback.print_exc()
            raise

index = IndexView.as_view()