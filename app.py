from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
import json
from PIL import Image, ImageDraw, ImageFont, ImageStat
import uuid
import math
from dotenv import load_dotenv
import openai
from openai import OpenAI
import base64
import re
from io import BytesIO  # バイトストリーム操作のため
import svgwrite  # SVGファイル生成のため
from svgwrite import rgb  # SVGでの色指定のため

# 環境変数の読み込み
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Flaskアプリケーションの設定
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# アップロード可能なファイルかを確認
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 補色を計算する関数
def get_complementary_color(rgb):
    r, g, b = rgb
    return (255 - r, 255 - g, 255 - b)

# 画像をBase64エンコード
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# JSONを上書き保存
def update_json(json_path, new_data):
    with open(json_path, 'r+', encoding='utf-8') as file:
        original_data = json.load(file)
        original_data.update(new_data)
        file.seek(0)
        json.dump(original_data, file, ensure_ascii=False, indent=4)
        file.truncate()

# OpenAI APIのレスポンスをクリーニングして辞書型に変換
def clean_and_parse_json(response_text):
    cleaned_text = re.sub(r'^```json|```$', '', response_text, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

# OpenAI APIを呼び出す
def fetch_openai_response(image_path, json_path):
    with open(json_path, 'r', encoding='utf-8') as file:
        user_prompt = file.read()
    base64_image = encode_image(image_path)
    # Initialize the OpenAI client
    client = OpenAI()
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": """あなたは優れたコピーライターであり優れたデザイナーでもあります。広告、マーケティング、ソーシャルメディアの文章を効果的に記述し、配置することができます。 ユーザーはあなたに背景画像と共に、どのようなグラフィックデザイン画像を作成したいかという指示を与えます。 あなたはユーザーの指示を聞き、デザイン画像に含める日本語の文章を考え、それらを効果的に配置するためのjsonファイルを出力します。
            textはテキストボックス内に表示するテキストです。ユーザーの指示を聞き、最適な日本語の単語、文書を記述してください。文字数は以下の計算式から求められる値を参考にしてください。 n = round(width / height * 1.25)。また、改行はしてはいけません。
            fontは使用するフォントを表しており、画像の雰囲気や、テキストの内容にあったフォントを選択する必要があります。具体的には以下の４つの中から選択してください。 フォーマルな印象を与えたい: ipam.ttf 親しみやすさを重視:, rounded-mplus-1p-regular.ttf, 多言語に対応する場面: NotoSansJP-Regular.ttf, デジタルメディア向け: MPLUS1p-Regular.ttf
            text, fontは各テキストボックスごとに考えてください。
            出力は'{'ではじまり、'}'で終わる形式にしてください。
            """
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ],
)
    # print文はあとで消そう
    print (response.choices[0].message.content) 
    return clean_and_parse_json(response.choices[0].message.content)

def generate_svg(json_path, background_image_path, output_path):

    # JSONファイルの読み込み
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 背景画像の読み込み
    background_image = Image.open(background_image_path).convert("RGBA")
    bg_width, bg_height = background_image.size

    # 画像をBase64エンコード
    buffered = BytesIO()
    background_image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # SVG作成
    dwg = svgwrite.Drawing(output_path, profile='full', size=(bg_width, bg_height))
    background_layer = dwg.g(id="background")
    background_layer.add(dwg.image(href='data:image/png;base64,' + image_base64, insert=(0, 0), size=(bg_width, bg_height)))
    dwg.add(background_layer)

    font_directory = "./static/fonts"

    for key, value in data.items():
        # "user_intention" のキーを無視する
        if key == "user_intention":
            continue

        # valueがリストの場合に処理を進める
        if isinstance(value, list) and len(value) > 0:
            element = value[0]
            text = element["text"]
            font_file = element["font"]
            font_size = element["font_size"]
            color = tuple(map(int, element["color"].strip("[]").split(",")))  # 色をリストからタプルに変換
            left = element["left"]
            top = element["top"]
            width = element["width"]
            height = element["height"]

            # テキスト位置の計算
            text_width = font_size * len(text) * 0.5  # 簡易的な計算
            text_x = left + (width - text_width) / 2
            text_y = top + (height - font_size) / 2 + font_size * 0.75

            # SVGにテキストを追加
            text_layer = dwg.g(id=key)
            text_layer.add(dwg.text(
                text,
                insert=(text_x, text_y),
                fill=rgb(*color),
                font_size=font_size,
                font_family=font_file.split('.')[0]
            ))
            dwg.add(text_layer)

    # SVGファイルを保存
    dwg.save()

# ルートページ
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # ファイルの取得
        if 'file' not in request.files:
            return 'ファイルが見つかりません'
        file = request.files['file']

        if file.filename == '':
            return 'ファイル名が空です'

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('edit_image', filename=filename))

    return render_template('upload.html')

# 画像の編集ページ
@app.route('/edit/<filename>')
def edit_image(filename):
    return render_template('edit.html', filename=filename)

# 矩形情報を保存し、画像に描画するエンドポイント
@app.route('/save_rectangles', methods=['POST'])
def save_rectangles():
    data = request.json
    filename = data['filename']
    rectangles = data['rectangles']
    user_intention = data.get('userIntention', '')  # プロンプトを取得

    # 元の画像パスと保存用の新しいファイルパスを決定
    original_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    unique_id = str(uuid.uuid4())
    base_filename, ext = os.path.splitext(filename)
    new_filename = f'rect_{base_filename}_{unique_id}{ext}'
    new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)

    # 画像の読み込みと矩形の描画
    image = Image.open(original_image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    # フォントのパス設定
    font_path = os.path.join(app.root_path, "fonts", "Arial.ttf")

    rect_data = {"user_intention": user_intention}  # プロンプトをJSONに追加
    rect_count = 0

    for idx, rect in enumerate(rectangles, start=1):
        left = rect['left']
        top = rect['top']
        width = rect['width']
        height = rect['height']
        font_size = math.floor(height * (3 / 4))
        rect_count += 1

        rect_data[f"element{rect_count}"] = [
            {
                "text": "",
                "font": "",
                "font_size": font_size,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "color": "[R, G, B]"
            }
        ]

        try:
            font = ImageFont.truetype(font_path, size=font_size)
        except IOError:
            font = ImageFont.load_default()

        # 矩形の領域を取得して平均色を計算
        cropped = image.crop((left, top, left + width, top + height))
        mean_color = ImageStat.Stat(cropped).mean[:3]
        text_color = get_complementary_color(tuple(int(c) for c in mean_color))

        # 矩形と通し番号の描画
        draw.rectangle([left, top, left + width, top + height], outline="red", width=3)
        draw.text((left + 5, top + 5), str(idx), fill=text_color, font=font)

    # 新しい画像を保存
    image.save(new_image_path, format="JPEG")

    # 矩形情報をJSONに保存
    output_json_path = os.path.join(app.config['UPLOAD_FOLDER'], f'rect_{base_filename}_{unique_id}.json')
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(rect_data, f, ensure_ascii=False, indent=4)
    
    return jsonify({
        "message": "矩形情報と画像が保存されました。",
        "saved_image": new_filename,
        "saved_json": f"rect_{base_filename}_{unique_id}.json"
    })

# 画像の表示エンドポイント
@app.route('/uploads/<filename>')
def display_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# OpenAI APIを呼び出して補完を実行するエンドポイント
@app.route('/process', methods=['POST'])
def process():
    image_filename = request.form['image_filename']
    json_filename = request.form['json_filename']
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
    try:
        result = fetch_openai_response(image_path, json_path)
        update_json(json_path, result)
        return '', 204  # 成功時に空のレスポンスを返す
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# SVG生成用エンドポイント
@app.route('/generate_svg', methods=['POST'])
def generate_svg_endpoint():
    data = request.json
    json_filename = data['json_filename']
    image_filename = data['image_filename']
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    svg_filename = f"{os.path.splitext(json_filename)[0]}.svg"
    svg_path = os.path.join(app.config['UPLOAD_FOLDER'], svg_filename)

    try:
        generate_svg(json_path, image_path, svg_path)
        return jsonify({
            "message": "SVGファイルが生成されました。",
            "svg_url": url_for('display_image', filename=svg_filename)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)