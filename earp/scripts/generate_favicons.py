import os
from PIL import Image, ImageDraw

def generate_brand_icon(size: int, output_path: str):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    pad = int(size * 0.08)
    cx = size // 2
    cy = size // 2
    
    # Shield points scaled
    w_shield = (size - 2 * pad) // 2
    h_top = int(size * 0.35)
    h_bot = size - pad
    
    shield_pts = [
        (cx, pad),
        (cx + w_shield, pad + h_top // 3),
        (cx + w_shield, cy + int(size * 0.15)),
        (cx, h_bot),
        (cx - w_shield, cy + int(size * 0.15)),
        (cx - w_shield, pad + h_top // 3),
    ]
    
    # Dark slate background with emerald outline
    draw.polygon(shield_pts, fill=(10, 14, 23, 255), outline=(16, 185, 129, 255))
    
    # Checkmark inside
    check_pts = [
        (cx - int(w_shield * 0.5), cy),
        (cx - int(w_shield * 0.1), cy + int(w_shield * 0.4)),
        (cx + int(w_shield * 0.55), cy - int(w_shield * 0.4))
    ]
    line_w = max(2, int(size * 0.08))
    draw.line(check_pts, fill=(16, 185, 129, 255), width=line_w, joint="round")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Icon saved: {output_path} ({size}x{size})")

if __name__ == "__main__":
    generate_brand_icon(32, os.path.join("ui", "public", "favicon-32x32.png"))
    generate_brand_icon(180, os.path.join("ui", "public", "apple-touch-icon.png"))
