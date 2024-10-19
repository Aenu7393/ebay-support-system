from django.shortcuts import render, redirect
from django.views import View
from .scraper import scrape_mercari, write_to_google_sheets

class IndexView(View):
    def get(self, request):
        # スプレッドシートのURL
        sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR9vg2QpzWF8phmNWoltMrFcmI924iJlfit-LF-2ZBKHDLWGOI3PoZvSAmrTfiEhrIXyFX8rIj4e7MS/pubhtml"
        return render(request, "work1/index.html", {"sheet_url": sheet_url})
    
    
    def post(self, request):
        # フォームからURLを取得
        url = request.POST.get('url')

        # 取得したURLを使ってスクレイピングを実行
        title, price, condition, image_url = scrape_mercari(url)

        # スクレイピング結果をGoogleスプレッドシートに書き込む
        data = [title, price, condition, image_url]
        write_to_google_sheets(data, url)  # URLも一緒に渡す

                # リダイレクトして、再読み込み時の再送信を防止
        return redirect('/')  # ここでリダイレクトする

index = IndexView.as_view()