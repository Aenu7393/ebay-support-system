from django.core.management.base import BaseCommand
from work1.scraper import kousinn
from datetime import datetime
from work1.models import eBayAuthToken
from django.contrib.auth.models import User
from work1.models import eBayAuthToken
from work1.views import update_ebay_data ,get_access_token
from django.http import HttpResponse, JsonResponse




class Command(BaseCommand):
    help = '1時間おきにスクレイピングを実行して eBay 出品を管理します'

    def handle(self, *args, **kwargs):
        self.stdout.write(f"[INFO] タスク開始: {datetime.now()}")

        try:
            try:
                token = get_access_token()  # アクセストークンを取得
            except Exception as e:
                return HttpResponse(f"Error: {str(e)}アクセストークンの取得失敗してる", status=500)
            self.stdout.write(f"[DEBUG] 取得したアクセストークン: {token[:5]}***")  # トークンの一部を表示


            
            # データベースからすべてのユーザーを取得
            users = User.objects.all()
            user_count = users.count()  # ユーザーの合計数を取得
            self.stdout.write(f"[INFO] 現在のユーザー数: {user_count}")  # ログに出力

           
            for user in users:
                self.stdout.write(f"[INFO] ユーザー {user.username} ({user.id}) の処理を開始")
                
                # kousinn関数を実行
                kousinn(user.id, token)

                # update_ebay_data関数を実行
                result = update_ebay_data(user.id)
                if result["status"] == "success":
                    self.stdout.write(self.style.SUCCESS(f"ユーザー {user.username} のeBayデータ更新に成功しました"))
                else:
                    self.stdout.write(self.style.ERROR(f"ユーザー {user.username} のeBayデータ更新に失敗しました: {result['message']}"))

            self.stdout.write(self.style.SUCCESS("すべてのユーザーのタスクが正常に終了しました"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"エラー: {str(e)}"))