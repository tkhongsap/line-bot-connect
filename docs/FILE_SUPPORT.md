# File Type Support Documentation

## Overview

The LINE Bot now supports comprehensive file type analysis, enabling users to upload and analyze various file formats using AI-powered analysis through GPT-4.1-nano.

## Supported File Types

### Documents
- **PDF** (.pdf) - Portable Document Format files
- **Microsoft Word** (.doc, .docx) - Word documents (legacy and modern)
- **Text Files** (.txt) - Plain text files
- **Rich Text Format** (.rtf) - Formatted text documents
- **Markdown** (.md) - Markdown formatted text

### Spreadsheets
- **Microsoft Excel** (.xls, .xlsx) - Excel spreadsheets (legacy and modern)
- **CSV** (.csv) - Comma-separated values
- **TSV** (.tsv) - Tab-separated values

### Presentations
- **Microsoft PowerPoint** (.ppt, .pptx) - PowerPoint presentations (legacy and modern)

### Code Files
- **Python** (.py) - Python source code
- **JavaScript** (.js) - JavaScript files
- **HTML** (.html) - Web markup files
- **CSS** (.css) - Cascading Style Sheets
- **JSON** (.json) - JSON data files
- **XML** (.xml) - XML markup files
- **SQL** (.sql) - SQL database queries
- **YAML/YML** (.yaml, .yml) - YAML configuration files

### Data Files
- **Log Files** (.log) - Application log files
- **JSON Lines** (.jsonl) - Newline-delimited JSON

### Images (for reference)
- **JPEG** (.jpg, .jpeg) - JPEG images
- **PNG** (.png) - PNG images
- **GIF** (.gif) - GIF images
- **WebP** (.webp) - WebP images
- **BMP** (.bmp) - Bitmap images
- **TIFF** (.tiff, .tif) - TIFF images

## File Size Limits

- **Maximum file size**: 20 MB
- **Download timeout**: 10 seconds
- **Supported dimensions**: Up to 4K resolution for images

## How to Use

1. **Upload a file** to the LINE Bot chat
2. **Wait for processing** - You'll receive a status message indicating the file is being analyzed
3. **Receive AI analysis** - The bot will provide insights, summaries, or analysis based on the file content

## Features

### Automatic File Type Detection
- **Content-based detection** using file signatures (magic bytes)
- **Filename extension analysis** as fallback
- **Intelligent validation** to ensure file integrity

### AI-Powered Analysis
- **Document summarization** for text and PDF files
- **Data insights** for spreadsheets and CSV files
- **Code review** for programming files
- **Content extraction** from various formats

### Error Handling
- **Bilingual error messages** (Thai/English)
- **Clear guidance** on supported file types
- **Helpful error codes** for troubleshooting

## Error Messages

### File Too Large
```
ไฟล์ขนาดใหญ่เกินไป (สูงสุด 20MB)
File too large (maximum 20MB)
```

### Unsupported File Type
```
ไฟล์ประเภท .xyz ไม่รองรับ กรุณาส่งไฟล์ประเภทที่รองรับ
File type .xyz not supported. Please send a supported file type.

รองรับ / Supported: PDF, DOC, DOCX, TXT, XLS, XLSX, CSV, PPT, PPTX, PY, JS, HTML, CSS, JSON, XML, SQL, MD, YAML
```

### Download Failed
```
ไม่สามารถดาวน์โหลดไฟล์ได้ กรุณาลองใหม่
Cannot download file, please try again
```

### Analysis Failed
```
ไฟล์分析失敗，請稍後再試。
File analysis failed, please try again later.
```

## Technical Implementation

### File Processing Pipeline
1. **File Reception** - LINE Bot receives FileMessage event
2. **Download** - File content downloaded from LINE's content API
3. **Validation** - File type and size validation
4. **Upload** - File uploaded to OpenAI's file API
5. **Analysis** - GPT-4.1-nano processes and analyzes content
6. **Response** - AI-generated insights sent back to user

### File Type Detection Methods
- **Magic Bytes Detection** - Analyzes file signatures for accurate type identification
- **Extension Analysis** - Fallback method using filename extensions
- **Content Analysis** - Text encoding detection for text-based files

### Security Features
- **File size limits** to prevent abuse
- **Type validation** to ensure safe processing
- **Timeout protection** for download operations
- **Error isolation** to prevent system crashes

## Best Practices

### For Users
1. **Use descriptive filenames** for better context
2. **Keep files under 20MB** for optimal processing
3. **Use supported formats** for best results
4. **Wait for processing** before sending another file

### For Developers
1. **Monitor file processing logs** for debugging
2. **Implement proper error handling** in client applications
3. **Consider rate limiting** for high-volume usage
4. **Use appropriate file formats** for specific use cases

## Troubleshooting

### Common Issues

**Q: My file isn't being processed**
A: Check if the file type is supported and under 20MB size limit.

**Q: Analysis seems incomplete**
A: Large or complex files may need more processing time. Try splitting into smaller sections.

**Q: Getting timeout errors**
A: Network issues may cause download timeouts. Try uploading the file again.

**Q: File type not detected correctly**
A: Ensure the file has the correct extension and isn't corrupted.

### Support
For technical issues or questions about file support, refer to the main bot documentation or contact support.

## API Integration

### FileMessage Handler
```python
@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    # Processes uploaded files automatically
```

### File Type Validation
```python
processor = FileProcessor()
validation = processor.validate_file_type(filename, file_data)
if validation['success']:
    # Process file
else:
    # Handle unsupported type
```

## Version History

- **v1.0** - Initial file type support implementation
- Added comprehensive file type detection
- Implemented bilingual error handling
- Integrated with GPT-4.1-nano for analysis

---

*Last updated: 2024-07-29* 