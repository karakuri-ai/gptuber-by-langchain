# GPTuber

大規模言語モデルが YouTuber をやります．
GPU や TPU は不要です（代わりに，いくつかの強力な API を利用します）．

# Demo

[![YouTube](https://img.youtube.com/vi/xgUuw4k8wwY/0.jpg)](https://www.youtube.com/watch?v=xgUuw4k8wwY&t=3060s)

# Setup

Mac で動かすことを想定しています．

- 以下のインストールが必要です．

  - MeCab
    - 字幕を文節ごとに表示する処理で使用します．
  - Python >= 3.8.1
    - LangChain の最新版を利用したいためです．
  - requirements.txt に記載された Python パッケージ
    - `pip install -r requirements.txt` で入ります．
  - gcloud コマンド
    - YouTuber の音声合成に Google の Text-to-Speech API を使用しますが，その際に使用します．
  - mpg123
    - YouTuber の音声ファイルを再生する時に使用します．
  - say コマンド
    - YouTuber が使用するスマートスピーカーの発話に使用します．

- 以下の API を利用可能にしておく必要があります．

  - OpenAI
    - 大規模言語モデルを利用します．
    - 2022 年 12 月現在，アカウント登録すると，3 ヶ月間限定で使用可能な 18 ドルの無料クレジットが付与されます．[REF.](https://openai.com/api/pricing/)
  - Google Text-to-Speech API
    - YouTuber の音声合成に使用します．
    - 2022 年 12 月現在，1 ヶ月あたり 100 万文字まで無料で，それ以上は 1 文字あたり 0.000016 ドルです．[REF.](https://cloud.google.com/text-to-speech/pricing)
  - Google YouTube Data API
    - YouTube Live のチャット情報をリアルタイムで取得するために使用します．
    - 2022 年 12 月現在，無料ですが，quota の上限はあります．[REF.](https://developers.google.com/youtube/v3/getting-started)
  - serpapi
    - YouTuber がスマートスピーカーに質問した時に，スマートスピーカー（=LangChain の Agent）が内部で tool として Search（ウェブ検索）を利用しますが，その際に必要です．
    - 2022 年 12 月現在，アカウント登録すると，Free Plan の場合は 1 ヶ月あたり 100 回の検索まで無料です．[REF.](https://serpapi.com/pricing)

- 以下の環境変数を設定しておく必要があります．

```sh
# OpenAI の API により大規模言語モデルを利用するために API キーが必要
export OPENAI_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# Google の Text-to-Speech API により音声合成を行うために必要な認証情報が記載された json ファイルへのパス
export GOOGLE_APPLICATION_CREDENTIALS="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.json"
# Google の YouTube Live のチャット情報の取得用 API に必要な API キー
export YOUTUBE_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# スマートスピーカーが内部で利用する tool の 1 つである serpapi に必要な API キー
export SERPAPI_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

# Usage

(A)(B)(C) の 3 パターンに分けて記述します．

## (A): 認証情報が全て揃った状態で，手元で動かす（配信はしない）場合

以下の手順で起動します．

- `./public/index.html` をブラウザで開きます．
  - 配信用のスクリーンが表示されます．
- `cd ./src; python server.py` によりバックエンドを起動します．
  - ブラウザで開いた配信用のスクリーンのページの「バックエンドとの接続状況」のマルが灰色から緑色になれば OK です．ならない場合は，`server.py` 側のエラーを確認してください．
- 10-20 秒ほど待っていると，YouTuber が喋り始めます．また，喋りの内容が配信用のスクリーンに表示されます．

配信用のスクリーンのすぐ下にあるフォームから，YouTuber にチャットを送ることができます（タイムラグが多少ありますが）．

## (B): (A) に加えて，実際に YouTube で配信する場合

以下の手順で起動します．なお，(A) に加えて，YouTube Live の配信が可能な状態になっていること，および，
配信ソフト（OBS 等），またデスクトップ音声をキャプチャ可能な仮想マイクデバイス（Blackhole 等）が必要です．

- `./public/index.html` をブラウザで開きます．
  - 配信用のスクリーンが表示されます．
- デスクトップ音声が，デスクトップ音声をキャプチャ可能な仮想マイクデバイス（Blackhole 等）に流れるように設定します（OS 側の設定）．
- YouTube Live の配信開始画面を開きます．
- 配信ソフト（OBS 等）を起動します．
  - YouTube Live と接続するための各種情報を設定します．
  - 映像ソースとして，上記の配信用のスクリーンを指定します．
  - 音声ソースとして，上記の仮想マイクデバイスを指定します．
  - 配信を開始します．
- `cd ./src; python server.py --youtube-url "https://www.youtube.com/watch?v=xxxxxxxxxxx"` によりバックエンドを起動します．
  - `--youtube-url` には，YouTube Live の配信を視聴するための URL を指定します．
  - ブラウザで開いた配信用のスクリーンのページの「バックエンドとの接続状況」のマルが灰色から緑色になれば OK です．ならない場合は，`server.py` 側のエラーを確認してください．
- 10-20 秒ほど待っていると，YouTuber が喋り始めます．また，喋りの内容が配信用のスクリーンに表示されます．

YouTube Live のチャット欄から YouTuber にチャットを送ることができます．
また，(A) と同様，配信用スクリーンのすぐ下にあるフォームからもチャットを送ることができます．
いずれもタイムラグは多少あります．

## (C): 認証情報が不足している状態でとりあえず動かしたい場合

基本は (A)(B) の手順ですが，足りない認証情報に応じて，以下のようにします．

- `server.py` の起動時オプションを変更します．
  - OpenAI の認証情報がない場合
    - 大規模言語モデルを動かせません．`--no-llm` オプションを追加すれば起動できますが，YouTuber は `こんにちは。今日はいい天気ですね。` としか喋りません．
  - Google Text-to-Speech API の認証情報がない場合
    - YouTuber が綺麗な日本語を話せません．`--no-neural-tts` オプションを追加すれば起動できますが，YouTuber の発話音声のクオリティは下がります．
  - Google YouTube Live API の認証情報がない場合
    - YouTube Live 上のチャットを取得できません．`--youtube-url` オプションを省略すれば起動はできますが，YouTube Live 上のチャット欄に投稿した内容が YouTuber に届きません．
  - serpapi の認証情報がない場合
    - YouTuber がスマートスピーカーを利用できません．`--no-smart-agent` オプションを追加すれば起動はできますが，スマートスピーカーは `> Final Answer: Sorry I don't understand.` としか返答しません．
    - なお，そもそも YouTuber がスマートスピーカーを起動しようとするのをやめたい場合は，プロンプト自体を編集してください．

# 仕様

- YouTuber の発言は，大規模言語モデルを用いて生成されます．
  - 生成された文章の中に絵文字が含まれる場合，変換テーブルによりエモートに変換され，配信スクリーンの画像が動的に切り替わります．
  - プロンプトの前半部分に，YouTuber の基本的な設定が記載されています（絵文字を多く含む返答をする旨もここに記載があります）．
  - プロンプトの後半には「ここまでの会話の要約」が挿入されます．この要約内容も大規模言語モデルにより裏側で毎ターン生成され更新されます．
  - プロンプトのさらに続きには「直近の視聴者からのチャット内容」が挿入されます．
  - チャットがしばらくの間一件もない場合，時折「TV が何か言っている：......」という一節がプロンプトに挿入されます（TV の放送内容も大規模言語モデルにより生成されます）．これは，YouTuber の話す内容がネタ切れにならないようにするための仕組みです．
  - Google Home からの回答（後述）が得られた直後の場合は，「Google Home の回答：......」という一節がプロンプトに挿入されます．
  - YouTuber は Google Home を所有している設定に（プロンプトの前半部分の記載により）なっており，時に `OK Google,` で始まる発話をすることがあります．この時，Google Home への指示は LangChain の Agent への入力にそのままなります．
    - LangChain の Agent (`ZeroShotAgent`) は，与えられた問題を解決するため，自己思考・行動選択のループを行い（これも大規模言語モデルへの適切なプロンプトによって行われます），回答が得られたと納得した段階で最終回答を返します．挙動の例は[LangChain 公式の Docs](https://langchain.readthedocs.io/en/latest/getting_started/agents.html)をご覧ください．
    - そのログ出力内容（Thought, Action, Observation 等）は，そのまま Google Home の声として発話され，配信スクリーンに字幕も表示されます．

# 設定変更したい場合

- キャラ設定，状況設定など
  - 大規模言語モデルを LangChain を用いて呼び出すコードは `./src/lib/chains.py` にまとまっています．この中のプロンプトを適宜編集することで，キャラ設定や状況設定などを変更できます．
- 画像
  - 出力されたテキスト中の絵文字をエモートに変換する仕様となっています．変換テーブルは `./src/lib/emoji-to-emote.csv` にあります．エモート画像は `./public/img/streamer/` にあります．これらを適宜変更してください．アニメーション gif の使用を推奨します．
