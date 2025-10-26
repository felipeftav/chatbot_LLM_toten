from PIL import Image
import os

# Caminho da imagem original
input_path = "assets/avatar_fechada.png"
# Caminho da saída em WebP
output_path = "assets/avatar_fechada.webp"

with Image.open(input_path) as img:
    img.save(output_path, "WEBP", quality=90, method=6)
