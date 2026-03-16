from django.db import models
from django.contrib.auth.models import User



class Spreadsheet(models.Model):
    user_id = models.IntegerField(default=1)  # 仮のデフォルト値
    spreadsheet_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'work1_spreadsheet' 
    



from datetime import datetime

class eBayAuthToken(models.Model):
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()  # アクセストークンの有効期限

    def __str__(self):
        return f"Access Token Expires At: {self.expires_at}"