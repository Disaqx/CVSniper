import os
import re
import shutil
import unicodedata
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import fitz  # PyMuPDF

# Default portfolio configuration
images_dir_default = r"C:\Users\cdjm2\Desktop\Documentos\Fotos prooftech"
default_projects = [
    {
        "title": "Flipper Zero Multi-Board Integration",
        "desc": "Custom integrated ESP32 (WiFi Dev Board), CC1101 (sub-GHz transceiver), and nRF24 (2.4GHz transceiver) onto a single hardware PCB. Enabled hardware-level wireless auditing, signal sniffing, BadUSB scripting, and Captive Portal credential harvesting. Designed custom layout configurations and optimized RF pathways for maximum transmission efficiency.",
        "img_file": "Flipper zero con ESP32 CC1101 NRF24 integrados en la misma placa ejecutando evil portal.jpeg"
    },
    {
        "title": "Bazzite Linux Secure Boot Cryptography",
        "desc": "Configured secure bootloaders and compiled custom kernel modules on Legion Go handheld hardware. Registered custom Machine Owner Keys (MOK) in Secure Boot database and signed EFI boot loader binaries manually. Formulated safe and fully integrated Bazzite Linux & Windows dual-boot systems, retaining maximum hardware security boundaries.",
        "img_file": "Leegion go firmada en Bazzite.jpeg"
    },
    {
        "title": "Nintendo Switch Modchip & Custom Bootloaders",
        "desc": "Executed micro-soldering precision layout installation of modchips onto Switch mainboards. Programmed low-level Hekate bootloader boot chains and sandboxed custom firmware (Atmosphère). Set up memory management tools and advanced homebrew structures, creating safe platforms for hardware system audits.",
        "img_file": "Nintendo switch en homebrewchannel con el canal donut instalado.jpeg"
    },
    {
        "title": "3D CAD Engineering & Consumer Repairs",
        "desc": "Designed exact replacement hinges and structural parts in Autodesk Fusion 360 to repair high-wear spots on consumer laptops (Lenovo Ideapad Gaming 3). Conducted thermal expansion calculations and structural tension audits. Printed parts in high-strength PETG/PLA materials, extending electronic hardware life.",
        "img_file": "Proyecto cults repuesto diseñado para PC lenovo gaming 3.jpeg"
    },
    {
        "title": "Gridfinity Workspace Lab Optimization",
        "desc": "Designed modular and secure storage systems following the Gridfinity layout to organize professional diagnostic tools, soldering setups, and electronics components. Engineered specific magnetic lockers, wire brackets, and stackable modular organization trays to maximize hardware bench efficiency and safety.",
        "img_file": "Proyecto grande gridfinity para organizar cables y cosas que tengo para arreglar cosas y conectar.jpeg"
    },
    {
        "title": "RFID Protocols & Access Audits",
        "desc": "Audited and analyzed residential high-frequency RFID credential tokens. Utilized protocol analysis tools to decrypt sector keys, dump access blocks, duplicate access badges, and audit structural weaknesses in Mifare Classic 1K systems. Formulated recommendations to secure domestic entryways.",
        "img_file": "Analisis de como funciona un RFID de mi casa.png"
    },
    {
        "title": "Custom PC Build & Hardware Integration",
        "desc": "Sourced, benchmarked, and integrated high-performance PC components for a custom desktop build. Optimized airflow layout, cable management, and thermal performance for intensive computing and rendering workloads.",
        "img_file": "PC con accesorios montada y componentes elegidos por mi.jpeg"
    },
    {
        "title": "3D Spatial Modeling & Architecture",
        "desc": "Modeled comprehensive room layouts and custom furniture pieces in Autodesk Fusion 360. Calculated exact dimensional constraints to optimize spatial efficiency and workflow ergonomics for a professional lab environment.",
        "img_file": "boceto de como quiero mi cuarto algun dia en fusion 365.png"
    }
]

# We no longer use FPDF; we generate HTML and use Playwright

def clean_latin1_text(text):
    if not text:
        return ""
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '-')
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    try:
        text.encode('latin-1')
        return text
    except UnicodeEncodeError:
        normalized = unicodedata.normalize('NFKD', text)
        cleaned = "".join(c for c in normalized if not unicodedata.combining(c))
        try:
            cleaned.encode('latin-1')
            return cleaned
        except UnicodeEncodeError:
            return cleaned.encode('ascii', 'ignore').decode('ascii')

def parse_markdown_cv(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    cv = {
        'name': '',
        'title': '',
        'contact': [],
        'sections': []
    }
    
    current_section = None
    current_subsection = None
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        if line_str.startswith('# '):
            cv['name'] = clean_latin1_text(line_str[2:].strip())
        elif line_str.startswith('**') and line_str.endswith('**') and not cv['title']:
            cv['title'] = clean_latin1_text(line_str[2:-2].strip())
        elif line_str.startswith('- '):
            if any(k in line_str for k in ['Phone', 'Email', 'LinkedIn', 'Location', 'Availability']):
                clean_contact = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line_str[2:])
                clean_contact = clean_contact.replace("**", "").strip()
                cv['contact'].append(clean_latin1_text(clean_contact))
            elif current_section:
                clean_bullet = re.sub(r'\*\*([^*]+)\*\*:', r'\1:', line_str[2:])
                clean_bullet = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_bullet)
                if current_subsection:
                    current_subsection['bullets'].append(clean_latin1_text(clean_bullet))
                else:
                    current_section['bullets'].append(clean_latin1_text(clean_bullet))
        elif line_str.startswith('## '):
            current_section = {
                'title': clean_latin1_text(line_str[3:].strip()),
                'subsections': [],
                'bullets': []
            }
            cv['sections'].append(current_section)
            current_subsection = None
        elif line_str.startswith('### '):
            current_subsection = {
                'title': clean_latin1_text(line_str[4:].strip()),
                'date': '',
                'bullets': []
            }
            if current_section:
                current_section['subsections'].append(current_subsection)
        elif line_str.startswith('*') and line_str.endswith('*'):
            if current_subsection:
                current_subsection['date'] = clean_latin1_text(line_str[1:-1].strip())
        else:
            if current_section:
                if current_subsection:
                    current_subsection['bullets'].append(clean_latin1_text(line_str))
                else:
                    current_section['bullets'].append(clean_latin1_text(line_str))
                    
    return cv

def generate_full_portfolio(cv_data, output_path, include_portfolio=True, projects=None, images_dir=None):
    import base64

    def get_base64_image(path):
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode('utf-8')
            ext = path.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            return f"data:image/{ext};base64,{encoded}"
        except Exception:
            return ""

    owner_name = cv_data.get("name", "Candidate").upper()

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;700&family=Space+Grotesk:wght@300;400;500;700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', sans-serif; color: #111; background: #fff; font-size: 9.5px; line-height: 1.3; }

  /* ── PAGE: strict A4 single page. overflow:hidden CLIPS anything that doesn't fit. ── */
  .page {
    width: 210mm;
    height: 277mm;
    overflow: hidden;
    padding: 8mm 12mm;
    page-break-after: always;
    break-after: page;
  }
  .page:last-child {
    page-break-after: auto;
    break-after: auto;
  }

  /* ── CV HEADER ── */
  .header { margin-bottom: 5px; }
  h1 { font-family: 'Space Grotesk', sans-serif; font-size: 20px; font-weight: 700;
       margin: 0 0 2px 0; letter-spacing: -0.02em; line-height: 1.1; }
  .cv-title { font-size: 10px; color: #444; margin-bottom: 3px; font-style: italic; }
  .header-gradient { height: 2px; background: #111; margin-bottom: 3px; }
  .contact-row { display: flex; flex-wrap: wrap; gap: 3px 10px; font-size: 8.5px; color: #555; }
  .contact-row span.sep { color: #ccc; }

  /* ── CV SECTIONS ── */
  h2 { font-family: 'Space Grotesk', sans-serif; font-size: 10.5px; font-weight: 700;
       text-transform: uppercase; letter-spacing: 0.05em;
       border-bottom: 1.5px solid #111; padding-bottom: 1px; margin: 5px 0 2px 0; }
  .cv-section { margin-bottom: 2px; }
  .subsection-title { font-weight: 700; font-size: 10px;
                      display: flex; justify-content: space-between; align-items: baseline; }
  .subsection-date { font-weight: normal; font-size: 8.5px; color: #777; white-space: nowrap; }
  ul { margin: 1px 0 2px 0; padding-left: 13px; }
  li { margin-bottom: 0.5px; color: #222; font-size: 8.8px; line-height: 1.25; }

  /* ── PORTFOLIO PAGE ── */
  .portfolio-header {
    text-align: center; font-family: 'Space Grotesk', sans-serif;
    font-size: 10.5px; color: #fff; background: #111; padding: 7px;
    font-weight: bold; margin-bottom: 8px;
    margin-top: -8mm; margin-left: -12mm; margin-right: -12mm;
    letter-spacing: 0.06em;
  }
  .portfolio-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
  }
  .project-card {
    display: flex; flex-direction: column; background: #fff;
    border-radius: 5px; overflow: hidden;
    box-shadow: 0 2px 6px rgba(0,0,0,0.07); border: 1px solid #e0e0e0;
    break-inside: avoid;
  }
  /* With image */
  .project-img-container {
    width: 100%; height: 85px; overflow: hidden;
    background: #f0f0f0; display: flex; align-items: center; justify-content: center;
    border-bottom: 1px solid #eee;
  }
  .project-img { width: 100%; height: 100%; object-fit: cover; }
  /* No image – dark accent strip */
  .project-icon-strip {
    width: 100%; height: 22px;
    background: linear-gradient(90deg, #111 0%, #3a3a3a 100%);
    display: flex; align-items: center; padding: 0 8px;
  }
  .project-icon-strip span {
    font-family: 'Space Grotesk', sans-serif; font-size: 8px;
    color: rgba(255,255,255,0.65); letter-spacing: 0.08em; text-transform: uppercase;
  }
  .project-info { padding: 6px 8px; flex-grow: 1; }
  .project-title { font-family: 'Space Grotesk', sans-serif; font-size: 10px;
                   font-weight: 700; color: #111; margin: 0 0 2px 0; }
  .project-desc { font-size: 8.2px; color: #444; line-height: 1.3; }
  .more-projects-banner {
    grid-column: 1 / -1; background: #f8f9fa;
    border: 1px dashed #ccc; border-radius: 5px; padding: 4px;
    text-align: center; color: #444;
    font-family: 'Space Grotesk', sans-serif;
  }
  .more-projects-banner span { font-size: 9.5px; font-weight: 700; display: block; }
  .more-projects-banner .sub { font-size: 7.5px; font-weight: normal;
                                margin-top: 1px; color: #777;
                                font-family: 'DM Sans', sans-serif; }
</style>
</head>
<body>
"""

    # ── PAGE 1: CV ────────────────────────────────────────────────────
    html += '<div class="page">'
    html += '<div class="header">'
    html += f'<h1>{cv_data["name"]}</h1>'
    if cv_data.get("title"):
        html += f'<div class="cv-title">{cv_data["title"]}</div>'
    html += '<div class="header-gradient"></div>'

    contact_parts = []
    for item in cv_data.get('contact', []):
        val = item.split(':', 1)[1].strip() if ':' in item else item
        contact_parts.append(val)
    html += '<div class="contact-row">'
    html += ' <span class="sep">|</span> '.join(f'<span>{c}</span>' for c in contact_parts)
    html += '</div>'
    html += '</div>'  # end .header

    for section in cv_data.get('sections', []):
        html += f'<h2>{section["title"]}</h2>'
        html += '<div class="cv-section">'
        if section.get('bullets'):
            html += '<ul>' + ''.join(f'<li>{b}</li>' for b in section['bullets']) + '</ul>'
        for sub in section.get('subsections', []):
            html += (
                f'<div class="subsection-title">'
                f'<span>{sub["title"]}</span>'
                f'<span class="subsection-date">{sub.get("date", "")}</span>'
                f'</div>'
            )
            if sub.get('bullets'):
                html += '<ul>' + ''.join(f'<li>{b}</li>' for b in sub['bullets']) + '</ul>'
        html += '</div>'  # end .cv-section

    html += '</div>'  # end page 1

    # ── PAGE 2: PORTFOLIO (optional) ──────────────────────────────────
    if include_portfolio and projects:
        html += '<div class="page">'
        html += f'<div class="portfolio-header">{owner_name} | PROOF OF TECH PORTFOLIO</div>'
        html += '<div class="portfolio-grid">'

        for project in projects:
            if images_dir:
                img_path = os.path.join(images_dir, project['img_file'])
            else:
                img_path = project.get('img_file', '')
            img_b64 = get_base64_image(img_path)

            html += '<div class="project-card">'
            if img_b64:
                html += f'<div class="project-img-container"><img class="project-img" src="{img_b64}"></div>'
            else:
                # No image → styled dark accent strip as visual divider
                html += f'<div class="project-icon-strip"><span>▸ {project["title"][:35]}</span></div>'
            html += (
                f'<div class="project-info">'
                f'<div class="project-title">{project["title"]}</div>'
                f'<div class="project-desc">{project["desc"]}</div>'
                f'</div>'
                f'</div>'  # end .project-card
            )

        html += (
            '<div class="more-projects-banner">'
            '<span>+ 13 ADDITIONAL ENGINEERING &amp; GITHUB PROJECTS AVAILABLE UPON REQUEST</span>'
            '<span class="sub">Including Hardware Mods, PC Builds, Custom Furniture, &amp; Python Automation Scripts (e.g., AI LinkedIn Auto-Applier)</span>'
            '</div>'
            '</div>'   # end .portfolio-grid
            '</div>'   # end page 2
        )

    html += '</body></html>'

    # Write HTML
    temp_html = output_path.replace('.pdf', '_temp.html')
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html)
        
    import subprocess
    base_dir = os.path.dirname(os.path.abspath(__file__))
    node_script = os.path.abspath(os.path.join(base_dir, "..", "career-ops", "generate-pdf.mjs"))
    
    print("Generating PDF via Playwright (HTML rendering)...")
    try:
        subprocess.run(["node", node_script, temp_html, output_path, "--format=a4"], check=True)
        print(f"Generated unified PDF at: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate PDF via Node: {e}")
        raise e
    finally:
        if os.path.exists(temp_html):
            os.remove(temp_html)

def generate_cv_from_basic_info(first_name, last_name, phone, location, title, output_path, include_portfolio=False, projects=None, images_dir=None, extra_sections=None):
    """
    Helper function to generate a CV from basic information without needing a Markdown file.
    `extra_sections` is an optional list of section dictionaries to add basic experience or skills.
    """
    name = f"{first_name} {last_name}".strip()
    contact_list = []
    if phone:
        contact_list.append(f"Phone: {phone}")
    if location and location.strip().strip(","):
        contact_list.append(f"Location: {location}")

    cv_data = {
        'name': name,
        'title': title,
        'contact': contact_list,
        'sections': extra_sections if extra_sections else []
    }
    generate_full_portfolio(cv_data, output_path, include_portfolio=include_portfolio, projects=projects, images_dir=images_dir)

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cv_md_path = os.path.join(base_dir, "REVISED_CV.md")
    output_dir = os.path.join(base_dir, "all resumes")
    images_dir = images_dir_default
    projects = default_projects
    
    os.makedirs(output_dir, exist_ok=True)
    
    full_portfolio_path = os.path.join(output_dir, "Cesar_Jimenez_CV_FULLPORTFOLIO.pdf")
    
    # 1. Compile CV data and generate unified PDF
    cv_data = parse_markdown_cv(cv_md_path)
    generate_full_portfolio(cv_data, full_portfolio_path, include_portfolio=True, projects=projects, images_dir=images_dir)
    
    # 2. Compress PDF using PyMuPDF (fitz)
    compressed_path = full_portfolio_path
    temp_uncompressed = full_portfolio_path.replace(".pdf", "_uncompressed.pdf")
    if os.path.exists(full_portfolio_path):
        try:
            shutil.move(full_portfolio_path, temp_uncompressed)
            doc = fitz.open(temp_uncompressed)
            doc.save(compressed_path, garbage=4, deflate=True)
            doc.close()
            os.remove(temp_uncompressed)
            print(f"Successfully compressed PDF to: {compressed_path}")
        except Exception as e:
            print(f"Error compressing PDF: {e}")
            fallback_compressed = full_portfolio_path.replace(".pdf", "_Fallback.pdf")
            try:
                doc = fitz.open(temp_uncompressed)
                doc.save(fallback_compressed, garbage=4, deflate=True)
                doc.close()
                print(f"Successfully saved compressed fallback PDF to: {fallback_compressed}")
            except Exception as fe:
                print(f"Failed to compress fallback PDF: {fe}")
                try:
                    shutil.copy(temp_uncompressed, fallback_compressed)
                except:
                    pass
