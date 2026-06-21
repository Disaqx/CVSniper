import os
import re
import unicodedata
from fpdf import FPDF

class CV_PDF(FPDF):
    def header(self):
        # Draw banner at the top (Black)
        self.set_fill_color(17, 17, 17) # Black (#111111)
        self.rect(0, 0, 210, 41, 'F')
        
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'Page %s' % self.page_no(), 0, 0, 'C')

def clean_latin1_text(text):
    if not text:
        return ""
    # Replace en-dash and em-dash with standard hyphen
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '-')
    # Replace smart quotes with standard ones
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    
    # Try encoding to latin-1, if fails, fallback to converting non-latin-1 to closest approximations
    try:
        text.encode('latin-1')
        return text
    except UnicodeEncodeError:
        # Normalize accents
        normalized = unicodedata.normalize('NFKD', text)
        cleaned = "".join(c for c in normalized if not unicodedata.combining(c))
        try:
            cleaned.encode('latin-1')
            return cleaned
        except UnicodeEncodeError:
            # Fallback to ascii representation, ignoring unencodable characters
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
            
        # Parse Name (H1)
        if line_str.startswith('# '):
            cv['name'] = clean_latin1_text(line_str[2:].strip())
        # Parse Title
        elif line_str.startswith('**') and line_str.endswith('**') and not cv['title']:
            cv['title'] = clean_latin1_text(line_str[2:-2].strip())
        # Parse Contact details
        elif line_str.startswith('- '):
            if any(k in line_str for k in ['Phone', 'Email', 'LinkedIn', 'Location', 'Availability']):
                # Clean up markdown links if any
                clean_contact = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line_str[2:])
                clean_contact = clean_contact.replace("**", "").strip()
                cv['contact'].append(clean_latin1_text(clean_contact))
            elif current_section:
                # This is a bullet point in the current section/subsection
                clean_bullet = re.sub(r'\*\*([^*]+)\*\*:', r'\1:', line_str[2:])
                clean_bullet = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_bullet)
                if current_subsection:
                    current_subsection['bullets'].append(clean_latin1_text(clean_bullet))
                else:
                    current_section['bullets'].append(clean_latin1_text(clean_bullet))
        # Parse Section Header (H2)
        elif line_str.startswith('## '):
            current_section = {
                'title': clean_latin1_text(line_str[3:].strip()),
                'subsections': [],
                'bullets': []
            }
            cv['sections'].append(current_section)
            current_subsection = None
        # Parse Subsection Header (H3)
        elif line_str.startswith('### '):
            current_subsection = {
                'title': clean_latin1_text(line_str[4:].strip()),
                'date': '',
                'bullets': []
            }
            if current_section:
                current_section['subsections'].append(current_subsection)
        # Parse dates (italics)
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

def generate_pdf(cv_data, output_path):
    pdf = CV_PDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(12, 10, 12)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    
    # --- HEADER SECTION (Inside Banner) ---
    pdf.set_y(6)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, cv_data['name'], ln=1, align='L')
    
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(209, 213, 219) # Light gray
    pdf.cell(0, 6, cv_data['title'], ln=1, align='L')
    
    # Contact Info horizontal layout in banner
    pdf.set_y(23)
    pdf.set_font('Helvetica', '', 8.5)
    pdf.set_text_color(229, 231, 235) # Very light gray
    
    contact_parts = []
    for item in cv_data['contact']:
        if ':' in item:
            contact_parts.append(item.split(':', 1)[1].strip())
        else:
            contact_parts.append(item)
            
    contact_str = "  |  ".join(contact_parts)
    pdf.cell(0, 5, contact_str, ln=1, align='L')
    
    # Reset layout below banner
    pdf.set_y(45)
    pdf.set_text_color(17, 17, 17) # Black text
    
    for section in cv_data['sections']:
        # Section title (H2)
        pdf.set_font('Helvetica', 'B', 10.5)
        pdf.set_text_color(17, 17, 17) # Black (#111111)
        pdf.cell(0, 4.5, section['title'].upper(), ln=1, align='L')
        
        # Section Divider line
        pdf.set_draw_color(17, 17, 17) # Black divider (#111111)
        pdf.set_line_width(0.3)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(1.2)
        
        # Section body / bullets
        if section['bullets']:
            pdf.set_font('Helvetica', '', 8.0)
            pdf.set_text_color(55, 65, 81)
            for bullet in section['bullets']:
                pdf.set_x(12)
                pdf.cell(3.5, 3.5, chr(149), 0, 0)
                pdf.multi_cell(182, 3.5, bullet, 0)
            pdf.ln(1.2)
            
        # Subsections
        for sub in section['subsections']:
            pdf.set_font('Helvetica', 'B', 9.0)
            pdf.set_text_color(31, 41, 55)
            
            # Print Title
            pdf.cell(140, 4, sub['title'], 0, 0, 'L')
            
            # Print Date
            if sub['date']:
                pdf.set_font('Helvetica', 'I', 8.0)
                pdf.set_text_color(107, 114, 128)
                pdf.cell(0, 4, sub['date'], 0, 1, 'R')
            else:
                pdf.ln(4)
                
            # Subsection bullets
            if sub['bullets']:
                pdf.set_font('Helvetica', '', 8.0)
                pdf.set_text_color(55, 65, 81)
                for bullet in sub['bullets']:
                    pdf.set_x(16)
                    pdf.cell(3.5, 3.5, chr(149), 0, 0)
                    pdf.multi_cell(178, 3.5, bullet, 0)
            pdf.ln(1.2)
            
    # Save the PDF
    try:
        pdf.output(output_path)
        print(f"Successfully generated PDF at {output_path}")
    except PermissionError:
        print(f"\n[WARNING] Permission Denied: Could not write to '{output_path}'.")
        print("This usually means the file is open in a PDF viewer (Adobe Acrobat, Chrome, etc.).")
        fallback_path = output_path.replace(".pdf", "_Fallback.pdf")
        try:
            pdf.output(fallback_path)
            print(f"Successfully wrote the PDF to fallback path: '{fallback_path}'")
            print("Please close the original PDF and rename this file to overwrite it.\n")
        except Exception as e:
            print(f"Failed to write to fallback path: {e}")
            import sys
            sys.exit(1)

if __name__ == '__main__':
    import shutil
    from PyPDF2 import PdfMerger
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cv_md_path = os.path.join(base_dir, "REVISED_CV.md")
    output_dir = os.path.join(base_dir, "all resumes")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Compile CV.md to Cesar_Jimenez_CV.pdf
    cv_pdf_path = os.path.join(output_dir, "Cesar_Jimenez_CV.pdf")
    cv_data = parse_markdown_cv(cv_md_path)
    generate_pdf(cv_data, cv_pdf_path)
    
    # 2. Copy the visual portfolio containing photos
    portfolio_src = r"C:\Users\cdjm2\Desktop\Documentos\Documentos Postulaciones\Visual_Portfolio_v3.pdf"
    portfolio_dst = os.path.join(output_dir, "Cesar_Jimenez_Portfolio.pdf")
    if os.path.exists(portfolio_src):
        try:
            shutil.copy(portfolio_src, portfolio_dst)
            print(f"Copied portfolio from {portfolio_src} to {portfolio_dst}")
        except Exception as e:
            print(f"Error copying portfolio: {e}")
    else:
        print(f"Warning: Portfolio source not found at {portfolio_src}")
        
    # 3. Merge CV and Portfolio
    full_profile_path = os.path.join(output_dir, "Cesar_Jimenez_Full_Profile.pdf")
    if os.path.exists(cv_pdf_path) and os.path.exists(portfolio_dst):
        try:
            merger = PdfMerger()
            merger.append(cv_pdf_path)
            merger.append(portfolio_dst)
            merger.write(full_profile_path)
            merger.close()
            print(f"Merged PDF created at: {full_profile_path}")
        except Exception as e:
            print(f"Error merging PDFs: {e}")
            
    # 4. Compress the merged PDF to Cesar_Jimenez_Compressed.pdf
    compressed_path = os.path.join(output_dir, "Cesar_Jimenez_Compressed.pdf")
    if os.path.exists(full_profile_path):
        import fitz  # PyMuPDF
        try:
            doc = fitz.open(full_profile_path)
            doc.save(compressed_path, garbage=4, deflate=True)
            doc.close()
            print(f"Compressed PDF created at: {compressed_path}")
        except Exception as e:
            print(f"Error compressing PDF to primary destination: {e}")
            fallback_compressed = compressed_path.replace(".pdf", "_Fallback.pdf")
            try:
                doc = fitz.open(full_profile_path)
                doc.save(fallback_compressed, garbage=4, deflate=True)
                doc.close()
                print(f"Successfully saved compressed PDF to fallback path: {fallback_compressed}")
            except Exception as fe:
                print(f"Failed to compress PDF to fallback path: {fe}")
                try:
                    shutil.copy(full_profile_path, fallback_compressed)
                    print(f"Copied uncompressed fallback to: {fallback_compressed}")
                except:
                    pass


