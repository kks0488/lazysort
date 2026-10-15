from PIL import Image, ExifTags
from datetime import datetime
import os

class MetadataExtractor:
    def get_exif_data(self, file_path: str) -> dict:
        """
        Extracts basic EXIF data: DateTimeOriginal, GPS (placeholder).
        """
        metadata = {
            'date': None,
            'gps': None,
            'model': None
        }
        
        try:
            with Image.open(file_path) as img:
                exif = img._getexif()
                if not exif:
                    return metadata
                
                # Parse EXIF
                for tag, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag, tag)
                    
                    if tag_name == 'DateTimeOriginal':
                        # Format: "YYYY:MM:DD HH:MM:SS"
                        try:
                            dt = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                            metadata['date'] = dt.strftime("%Y%m%d") # YYYYMMDD
                        except:
                            pass
                            
                    if tag_name == 'Model':
                        metadata['model'] = str(value).strip()
                        
                    # GPS extraction is complex, skipping for MVP unless requested
                    
        except Exception as e:
            # print(f"Error reading EXIF for {file_path}: {e}")
            pass
            
        # Fallback to file modification time if no EXIF date
        if not metadata['date']:
            try:
                mtime = os.path.getmtime(file_path)
                dt = datetime.fromtimestamp(mtime)
                metadata['date'] = dt.strftime("%Y%m%d")
            except:
                pass
                
        return metadata
