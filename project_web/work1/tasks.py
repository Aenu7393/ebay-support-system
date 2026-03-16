# from celery import shared_task
# from .scraper import kousinn



# @shared_task
# def kousinn_task(user_id, access_token):
#     """
#     kousinn関数を非同期で実行するタスク
#     """
#     try:
#         kousinn(user_id, access_token)
#         return "kousinn executed successfully."
#     except Exception as e:
#         return f"Error in kousinn_task: {e}"
    

# @shared_task
# def run_hourly_scraper():
#     """
#     Django 管理コマンド `hourly_scraper` を非同期タスクとして実行
#     """
#     try:
#         # `manage.py` コマンドを実行
#         call(["python", "manage.py", "hourly_scraper"])
#     except Exception as e:
#         # タスクの失敗を記録
#         print(f"エラー: {e}")