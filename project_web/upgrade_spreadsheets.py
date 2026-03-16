import os
import django
import gspread
from google.oauth2.service_account import Credentials
import psycopg2
import time

# Django環境のセットアップ
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workweb.settings')  # settings.pyのパスを指定
django.setup()

from work1.models import Spreadsheet  # 必要なモデルをインポート

def upgrade_spreadsheets():
    try:
        # 認証情報を取得
        creds = get_credentials()
        gc = gspread.authorize(creds)

        # データベース接続
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()

        # 全てのスプレッドシートIDを取得
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
                time.sleep(15)
        # データベース接続を閉じる
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"アップグレード中にエラーが発生しました: {e}")


def get_credentials():
    try:
        import json
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


if __name__ == "__main__":
    upgrade_spreadsheets()