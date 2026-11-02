import os

from PIL import Image, ImageDraw, ImageFont


def generate_og_image(output_path: str):
    width = 1200
    height = 630

    # Create image with deep slate canvas
    img = Image.new("RGBA", (width, height), (8, 9, 13, 255))
    draw = ImageDraw.Draw(img)

    # Subtle background gradient effect
    for y in range(height):
        alpha = int(15 * (1 - y / height))
        draw.line([(0, y), (width, y)], fill=(16, 185, 129, alpha))

    # Subtle architectural grid hairline
    for x in range(0, width, 60):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 6))
    for y in range(0, height, 60):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 6))

    # Outer frame
    draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(30, 41, 59, 255), width=2)

    # Shield Icon Container
    shield_cx, shield_cy = 130, 200
    # Shield polygon
    shield_points = [
        (shield_cx, shield_cy - 60),
        (shield_cx + 50, shield_cy - 40),
        (shield_cx + 50, shield_cy + 10),
        (shield_cx, shield_cy + 60),
        (shield_cx - 50, shield_cy + 10),
        (shield_cx - 50, shield_cy - 40),
    ]
    draw.polygon(shield_points, fill=(19, 24, 36, 255), outline=(16, 185, 129, 255))

    # Verification checkmark in shield
    check_points = [
        (shield_cx - 25, shield_cy),
        (shield_cx - 5, shield_cy + 20),
        (shield_cx + 25, shield_cy - 20),
    ]
    draw.line(check_points, fill=(16, 185, 129, 255), width=6, joint="round")

    # Load fonts (fallback to default if system font not found)
    try:
        font_brand = ImageFont.truetype("arialbd.ttf", 54)
        font_title = ImageFont.truetype("arialbd.ttf", 46)
        font_sub = ImageFont.truetype("arial.ttf", 24)
        font_badge = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font_brand = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    # Brand Title
    draw.text((210, 150), "ARGVTIX", font=font_brand, fill=(248, 250, 252, 255))

    # Version Badge
    badge_x, badge_y = 560, 168
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + 150, badge_y + 32)],
        radius=4,
        fill=(16, 185, 129, 35),
        outline=(16, 185, 129, 120),
        width=1,
    )
    draw.text((badge_x + 12, badge_y + 6), "v1.2.0-PROD", font=font_badge, fill=(16, 185, 129, 255))

    # Subhead
    draw.text(
        (210, 222), "ENTERPRISE AI RELIABILITY PLATFORM", font=font_badge, fill=(148, 163, 184, 255)
    )

    # Main Headline
    draw.text(
        (80, 310),
        "Deterministic Safety Guard & Grounding for AI Agents",
        font=font_title,
        fill=(255, 255, 255, 255),
    )

    # 3 Architectural Feature Pillars
    pillar_y = 410
    draw.line([(80, pillar_y - 20), (width - 80, pillar_y - 20)], fill=(30, 41, 59, 255), width=1)

    # Feature 1
    draw.text((80, pillar_y), "01 | Action Guard", font=font_badge, fill=(16, 185, 129, 255))
    draw.text(
        (80, pillar_y + 30),
        "Pre-action AST boundary enforcement.\nZero direct DB access for raw LLMs.",
        font=font_sub,
        fill=(148, 163, 184, 255),
    )

    # Feature 2
    draw.text((450, pillar_y), "02 | Claim Verifier", font=font_badge, fill=(56, 189, 248, 255))
    draw.text(
        (450, pillar_y + 30),
        "Cross-checks agent output vs SQL state.\nCatches hallucinations and phantom actions.",
        font=font_sub,
        fill=(148, 163, 184, 255),
    )

    # Feature 3
    draw.text((830, pillar_y), "03 | State Watchdog", font=font_badge, fill=(245, 158, 11, 255))
    draw.text(
        (830, pillar_y + 30),
        "Continuous background reconciliation.\nShopify & Salesforce ledger alignment.",
        font=font_sub,
        fill=(148, 163, 184, 255),
    )

    # Bottom Bar
    draw.line([(80, 550), (width - 80, 550)], fill=(30, 41, 59, 255), width=1)
    draw.text(
        (80, 565),
        "Self-Hosted & VPC Air-Gapped Ready  •  DPDP Act 2023 & GDPR Compliant  •  Zero Model Training",
        font=font_badge,
        fill=(100, 116, 139, 255),
    )
    draw.text((width - 250, 565), "https://argvtix.ai", font=font_badge, fill=(16, 185, 129, 255))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Social preview saved to {output_path} ({width}x{height})")


if __name__ == "__main__":
    out = os.path.join("ui", "public", "og-preview.png")
    generate_og_image(out)
