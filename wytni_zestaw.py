import re
import shutil
from pdf2image import convert_from_path
import pdfplumber
import os
from PIL import Image


def find_zestaw_name(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()

        for line in text.split("\n"):
            if line.startswith("Zadania ") or line.startswith("Zestaw"):
                if line.startswith("Zestaw"):
                    line = line.replace("Zestaw", "Zadania")

                part = line.split()[1]
                if part.isdigit():
                    formatted_number = f"{int(part):02}"
                    line = line.replace(part, formatted_number)

                return line

    return "Zestaw"


def find_third_line_header(pdf_path, dpi=300):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        lines = page.extract_text().split("\n")

        if len(lines) >= 3 and lines[2].startswith("Ile jest różnych"):
            pil_image = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)[
                0
            ]

            all_words = page.extract_words()
            line_to_find = lines[2]

            target_words = line_to_find.split()
            i_target = 0
            bounding_boxes = []
            for w in all_words:
                if i_target < len(target_words) and w["text"] == target_words[i_target]:
                    bounding_boxes.append(w)
                    i_target += 1

                    if i_target == len(target_words):
                        break

            if not bounding_boxes:
                return None

            top = min(word["top"] for word in bounding_boxes)
            bottom = max(word["bottom"] for word in bounding_boxes)
            margin = 10
            top_crop = int(top * dpi / 72) - margin
            bottom_crop = int(bottom * dpi / 72) + margin

            top_crop = max(0, top_crop)
            bottom_crop = min(bottom_crop, pil_image.size[1])

            header_image = pil_image.crop((522, top_crop, pil_image.width, bottom_crop))
            return header_image

        return None


def find_regex_positions(pdf_path, regex):
    positions = {}
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        bbox = page.extract_words()

        matches = []
        max_bottom = 0

        numer_zadania = 1
        for word in bbox:
            max_bottom = max(max_bottom, word["bottom"] + 15)
            if str(numer_zadania) not in word["text"]:
                continue

            if re.match(regex, word["text"]):
                matches.append(word["top"])
                numer_zadania += 1

        if matches:
            matches.append(max_bottom)
            positions[0] = matches
    return positions


def split_pdf_by_regex(i, pdf_path, output_dir, regex, dpi=600):
    zestanw_name = find_zestaw_name(pdf_path)
    print(f"Tworzę zadania z {zestanw_name}")
    folder_name = os.path.join(output_dir, zestanw_name)
    os.makedirs(folder_name, exist_ok=True)

    target_path = os.path.join(folder_name, f"Zestaw_{i}.pdf")
    shutil.move(pdf_path, target_path)

    positions = find_regex_positions(target_path, regex)

    header_image = find_third_line_header(target_path, dpi=dpi)
    pages = convert_from_path(target_path, dpi=dpi)

    for page_number, pil_image in enumerate(pages):
        y_positions = [int(y * dpi / 72) for y in positions[page_number]]
        y_positions.append(pil_image.size[1])
        y_positions = sorted(set(y_positions))

        for i in range(len(y_positions) - 2):
            upper = y_positions[i] - 45
            lower = y_positions[i + 1] - 45
            cropped_image = pil_image.crop((200, upper, pil_image.width - 200, lower))

            if header_image:
                new_width = max(header_image.width, cropped_image.width)
                new_height = header_image.height + cropped_image.height
                new_img = Image.new("RGB", (new_width, new_height), color="white")
                new_img.paste(header_image, (0, 0))
                new_img.paste(cropped_image, (0, header_image.height))
                final_image = new_img
            else:
                final_image = cropped_image
            output_path = os.path.join(folder_name, f"treści_{i + 1:02d}.png")
            final_image.save(output_path)


if __name__ == "__main__":
    pdf_path = "./kanak_1-12_zestawy.pdf"  # Ścieżka do pliku PDF
    output_dir = "./Solutions/"  # Katalog wyjściowy
    regex = r"^\s*\d+\..*"  # Regex dopasowuje: opcjonalne spacje, liczby, kropkę i dowolny tekst

    for i in range(1, 13):
        split_pdf_by_regex(i, f"./Solutions/Zestaw_{i}.pdf", output_dir, regex)
