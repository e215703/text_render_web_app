from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
import json
from PIL import Image, ImageDraw, ImageFont, ImageStat
import uuid
import math

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
    
    return jsonify({"message": "矩形情報と画像が保存されました。", "saved_image": new_filename})

# 画像の表示エンドポイント
@app.route('/uploads/<filename>')
def display_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)