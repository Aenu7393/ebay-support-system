from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.conf import settings  # settings.py から招待コードを取得

class CustomUserCreationForm(UserCreationForm):
    # 招待コード用のフィールドを追加
    invite_code = forms.CharField(
        max_length=50,
        required=True,
        label="招待コード",
        widget=forms.PasswordInput(attrs={'placeholder': '招待コードを入力してください'})
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2")  # 必要なフィールドのみ指定

    def clean_invite_code(self):
        # settings.py から正しい招待コードを取得
        correct_code = getattr(settings, 'INVITE_CODE', 'default_secure_code')  # 環境変数を利用
        entered_code = self.cleaned_data.get("invite_code")

        # 招待コードが間違っている場合にエラーを発生
        if entered_code != correct_code:
            raise forms.ValidationError("招待コードが間違っています。")
        
        return entered_code