from docling.document_converter import DocumentConverter

source = "./C541115 -CDW24C1098 1020002491 WTC_1.pdf"  # document per local path or URL
converter = DocumentConverter()
result = converter.convert(source)


MD = result.document.export_to_markdown()  # output: "## Docling Technical Report[...]"

print(MD)  # print the markdown content

#save the markdown content to a file
with open("output.md", "w", encoding="utf-8") as f:
    f.write(MD)