# from __future__ import absolute_import, unicode_literals
# import os
# from celery import Celery

# # Djangoのデフォルト設定モジュールを設定
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workweb.settings')

# # Celeryアプリケーションのインスタンスを作成
# app = Celery('workweb')

# # Django設定からCELERY関連設定を読み込む
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # タスクモジュールを自動検出
# app.autodiscover_tasks()

# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')