import os
from PyPDF2 import PdfMerger

def merge_pdfs(files, output):
    merger = PdfMerger()
    for file in files:
        if os.path.exists(file):
            merger.append(file)
    with open(output, "wb") as fout:
        merger.write(fout)
    merger.close()

if __name__ == "__main__":
    files_to_merge = ["all resumes/CV.pdf", "all resumes/Portfolio.pdf"]
    output_file = "all resumes/Full_Profile.pdf"
    merge_pdfs(files_to_merge, output_file)
    print(f"Merged PDF created at: {output_file}")
