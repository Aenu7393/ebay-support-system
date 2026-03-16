
from django.utils import timezone
from work1.models import eBayAuthToken
from work1.scraper import get_ebay_selling_items, write_ebay_to_google_sheets

def get_access_token():
    token = eBayAuthToken.objects.first()
    if not token:
        raise Exception("eBayトークンがありません。認証が必要です。")
    if token.expires_at <= timezone.now():
        raise Exception("トークンの有効期限が切れています。")
    return token.access_token


def update_ebay_data(user_id):
    try:
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