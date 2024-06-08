from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
import os
import fitz  # PyMuPDF
from io import BytesIO
import base64
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CORRECT_PDFS_FOLDER = 'correct_pdfs'
TEMP_FOLDER = 'temp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CORRECT_PDFS_FOLDER'] = CORRECT_PDFS_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(CORRECT_PDFS_FOLDER):
    os.makedirs(CORRECT_PDFS_FOLDER)
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

def clear_temp_folder():
    for filename in os.listdir(TEMP_FOLDER):
        file_path = os.path.join(TEMP_FOLDER, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

@app.route('/')
def upload_form():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and file.filename.endswith('.pdf'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        num_pages = get_pdf_page_count(filepath)
        return redirect(url_for('display_pdf', filename=file.filename, num_pages=num_pages))
    return redirect(request.url)

def get_pdf_page_count(filepath):
    pdf_document = fitz.open(filepath)
    return pdf_document.page_count

@app.route('/display/<filename>/<int:num_pages>', methods=['GET', 'POST'])
def display_pdf(filename, num_pages):
    if request.method == 'POST':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_document = fitz.open(filepath)
        writer = fitz.open()

        for i in range(num_pages):
            page_status = request.form.get(f'page-{i+1}')
            if page_status == 'not-ok':
                correct_filepath = os.path.join(app.config['CORRECT_PDFS_FOLDER'], f'page-{i+1}.pdf')
                cropped_filepath = os.path.join(app.config['TEMP_FOLDER'], 'cropped_image.png')  # Use the latest cropped image

                if os.path.exists(correct_filepath):
                    print(f"Processing NOT OK page {i+1}")
                    correct_document = fitz.open(correct_filepath)
                    original_page = pdf_document.load_page(i)
                    correct_page = correct_document.load_page(0)

                    if os.path.exists(cropped_filepath):
                        # Load the cropped image
                        cropped_image = Image.open(cropped_filepath)

                        # Resize cropped image to 15% of the page height
                        new_height = int(original_page.rect.height * 0.15)
                        new_width = int(original_page.rect.width)
                        cropped_image = cropped_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        cropped_image_bytes = BytesIO()
                        cropped_image.save(cropped_image_bytes, format='PNG')
                        cropped_image_pix = fitz.Pixmap(cropped_image_bytes.getvalue())

                        new_page = writer.new_page(width=original_page.rect.width, height=original_page.rect.height)

                        # Clip the top 85% from the correct page and show it on the new page
                        correct_clip_rect = fitz.Rect(0, 0, correct_page.rect.width, correct_page.rect.height * 0.85)
                        new_page.show_pdf_page(fitz.Rect(0, 0, new_page.rect.width, new_page.rect.height * 0.85), correct_document, 0, clip=correct_clip_rect)

                        # Add the cropped image to the bottom 15% of the new page
                        cropped_rect = fitz.Rect(0, new_page.rect.height * 0.85, new_page.rect.width, new_page.rect.height)
                        new_page.insert_image(cropped_rect, pixmap=cropped_image_pix)

                        print(f"Replaced top 85% and bottom 15% of NOT OK page {i+1}")
                    else:
                        print(f"Cropped image not found for page {i+1}")
                else:
                    print(f"Correct page not found for page {i+1}")
                    writer.insert_pdf(pdf_document, from_page=i, to_page=i)
            else:
                writer.insert_pdf(pdf_document, from_page=i, to_page=i)

        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'corrected_{filename}')
        writer.save(corrected_filepath)

        # Clear the temp folder
        clear_temp_folder()

        return send_file(corrected_filepath, as_attachment=True)
    return render_template('display.html', filename=filename, num_pages=num_pages)

@app.route('/uploads/<filename>')
def send_uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/crop', methods=['POST'])
def crop_page():
    data = request.json
    filename = data['filename']
    page_number = data['page_number']
    x, y, width, height = data['x'], data['y'], data['width'], data['height']

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    doc = fitz.open(filepath)
    page = doc.load_page(page_number - 1)  # page_number is 1-based

    clip = fitz.Rect(x, y, x + width, y + height)
    pix = page.get_pixmap(clip=clip)

    cropped_filepath = os.path.join(app.config['TEMP_FOLDER'], 'cropped_image.png')  # Use a common name
    pix.save(cropped_filepath)

    with open(cropped_filepath, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    return jsonify({'cropped_image': encoded_string})

@app.route('/get_page_image', methods=['POST'])
def get_page_image():
    data = request.json
    filename = data['filename']
    page_number = data['page_number']

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    doc = fitz.open(filepath)
    page = doc.load_page(page_number - 1)  # page_number is 1-based

    pix = page.get_pixmap()
    image_bytes = pix.tobytes("png")

    return base64.b64encode(image_bytes).decode('utf-8')

if __name__ == '__main__':
    app.run(debug=True)
