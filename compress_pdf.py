import fitz  # PyMuPDF
import os

input_file = "all resumes/Cesar_Jimenez_Full_Profile.pdf"
output_file = "all resumes/Cesar_Jimenez_Compressed.pdf"

try:
    doc = fitz.open(input_file)
    
    # Save the document with garbage collection and deflation (compression)
    # garbage=4: removes unused objects, duplicate objects, etc.
    # deflate=True: compresses streams
    doc.save(output_file, garbage=4, deflate=True)
    doc.close()
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    compressed_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"Original size: {original_size:.2f} MB")
    print(f"Compressed size: {compressed_size:.2f} MB")
    
except Exception as e:
    print(f"Error compressing PDF: {e}")
