# simpleworkernet/utils/graphics.py
"""
Модуль для работы с графическими форматами (SVG, PNG, ...)
Поддерживает сохранение, загрузку, конвертацию и отображение
"""

import os
import tempfile
import re
import hashlib
import base64
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union, Tuple, List, Dict, Any, Literal
from datetime import datetime
import html


_logger = None

def _get_logger():
    """Ленивый импорт логгера"""
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger

from ..core.exceptions import GraphicsError, SVGValidationError

# ==================== Условный импорт библиотек ====================

# IPython (для отображения)
try:
    from IPython.display import SVG, Image, display
    IPYTHON_AVAILABLE = True
except:
    IPYTHON_AVAILABLE = False

# CairoSVG
try:
    import cairosvg
    CAIRO_AVAILABLE = True
except:
    CAIRO_AVAILABLE = False

# ReportLab + svglib
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    RENDER_AVAILABLE = True
    REPORTLAB_AVAILABLE = True
except:
    RENDER_AVAILABLE = False
    REPORTLAB_AVAILABLE = False

# Pillow (PIL)
try:
    from PIL import Image as PILImage
    from PIL import ImageDraw, ImageFont
    PIL_AVAILABLE = True
except:
    PIL_AVAILABLE = False

# Wand (ImageMagick) - приоритетный метод для Windows
try:
    from wand.image import Image as WandImage
    from wand.drawing import Drawing
    from wand.color import Color
    WAND_AVAILABLE = True
except:
    WAND_AVAILABLE = False

# Matplotlib (запасной вариант)
try:
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    from matplotlib.patches import Rectangle
    from matplotlib.font_manager import FontProperties
    MATPLOTLIB_AVAILABLE = True
except:
    MATPLOTLIB_AVAILABLE = False

# WeasyPrint - опционально, если установлено
try:
    # Раскомментировать, если установлено
    # from weasyprint import HTML
    # WEASYPRINT_AVAILABLE = True
    WEASYPRINT_AVAILABLE = True
except:
    WEASYPRINT_AVAILABLE = False

# Inkscape (проверка наличия в системе)
try:
    INKSCAPE_AVAILABLE = bool(shutil.which('inkscape') or shutil.which('inkscape.com'))
except:
    INKSCAPE_AVAILABLE = False


class SVGHandler:
    """
    Обработчик SVG-изображений.
    
    Поддерживает:
    - Сохранение в файл
    - Загрузку из файла
    - Конвертацию в PNG
    - Отображение в Jupyter
    - Извлечение метаданных
    - Валидацию SVG
    """
    
    # Список шрифтов с поддержкой кириллицы
    CYRILLIC_FONTS = [
        'Arial', 'Times New Roman', 'Verdana', 'Tahoma', 
        'Courier New', 'Georgia', 'Trebuchet MS', 'Comic Sans MS',
        'Roboto', 'Open Sans', 'DejaVu Sans', 'Liberation Sans'
    ]
    
    def __init__(self, data: Optional[Union[bytes, str, Path]] = None, 
                 validate: bool = True, strict: bool = False):
        """
        Инициализация обработчика SVG.
        
        Args:
            data: Данные SVG (байты, строка, или путь к файлу)
            validate: Выполнять валидацию SVG при загрузке
            strict: Строгая валидация (требовать точное наличие </svg>)
        
        Raises:
            SVGValidationError: Если данные не являются валидным SVG и validate=True
        """
        self._data: Optional[bytes] = None
        self._metadata: Dict[str, Any] = {}
        self._source: Optional[str] = None
        self._width: float = 0.0
        self._height: float = 0.0
        self._is_valid_svg: bool = False
        self._strict = strict
        _get_logger()
        if data is not None:
            self.load(data, validate)
    
    # ==================== Загрузка и сохранение ====================
    
    def load(self, data: Union[bytes, str, Path], validate: bool = True) -> 'SVGHandler':
        """
        Загружает SVG данные.
        
        Args:
            data: Данные SVG (байты, строка, или путь к файлу)
            validate: Выполнять валидацию SVG
        
        Returns:
            self для цепочек вызовов
            
        Raises:
            SVGValidationError: Если данные не являются валидным SVG и validate=True
        """
        if isinstance(data, Path) or (isinstance(data, str) and Path(data).exists()):
            # Загрузка из файла
            path = Path(data)
            with open(path, 'rb') as f:
                self._data = f.read()
            self._source = str(path)
            _logger.debug(f"Данные загружены из файла: {path} ({len(self._data)} байт)")
            
        elif isinstance(data, str):
            # Строка с данными
            self._data = data.encode('utf-8')
            self._source = "string"
            _logger.debug(f"Данные загружены из строки ({len(self._data)} байт)")
            
        elif isinstance(data, bytes):
            # Байты с данными
            self._data = data
            self._source = "bytes"
            _logger.debug(f"Данные загружены из байтов ({len(self._data)} байт)")
            
        else:
            raise GraphicsError(f"Неподдерживаемый тип данных: {type(data)}")
        
        # Проверяем, является ли загруженное SVG
        self._is_valid_svg = self._quick_svg_check()
        
        if validate and not self._is_valid_svg:
            preview = self._data[:200].decode('utf-8', errors='ignore')
            raise SVGValidationError(
                f"Данные не являются валидным SVG. "
                f"Начало данных: {preview[:100]}..."
            )
        
        # Извлекаем метаданные (только если это SVG)
        if self._is_valid_svg:
            self._extract_metadata()
        else:
            _logger.warning("Загруженные данные не являются SVG, метаданные не извлекаются")
        
        return self
    
    def _quick_svg_check(self) -> bool:
        """
        Быстрая проверка, являются ли данные SVG.
        
        Returns:
            True если данные похожи на SVG
        """
        if not self._data or len(self._data) < 10:
            return False
        
        # Проверяем первые 500 байт на наличие признаков SVG
        preview = self._data[:500].decode('utf-8', errors='ignore').lower()
        
        # Проверяем наличие тега <svg
        if '<svg' not in preview:
            return False
        
        # Для нестрогой проверки достаточно наличия <svg
        if not self._strict:
            return True
        
        # Для строгой проверки проверяем наличие закрывающего тега
        full_preview = self._data[:2000].decode('utf-8', errors='ignore').lower()
        if '</svg>' not in full_preview:
            return False
        
        return True
    
    def save(self, path: Union[str, Path], mkdir: bool = True, 
             as_svg: bool = True, force: bool = False) -> Path:
        """
        Сохраняет данные в файл.
        
        Args:
            path: Путь для сохранения
            mkdir: Создавать директории при необходимости
            as_svg: Сохранять как SVG (добавлять расширение .svg)
            force: Сохранять даже если данные не являются SVG
        
        Returns:
            Path сохранённого файла
            
        Raises:
            SVGValidationError: Если данные не SVG и force=False
        """
        if not self._data:
            raise GraphicsError("Нет данных для сохранения")
        
        if not force and not self._is_valid_svg:
            raise SVGValidationError(
                "Данные не являются SVG. Используйте force=True для принудительного сохранения"
            )
        
        path = Path(path)
        
        # Добавляем расширение .svg если нужно
        if as_svg and not path.suffix:
            path = path.with_suffix('.svg')
        
        if mkdir:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            f.write(self._data)
        
        _logger.info(f"Данные сохранены в {path} ({len(self._data)} байт)")
        return path
    
    def save_auto(self, prefix: str = "scheme", directory: Optional[Union[str, Path]] = None,
                  force: bool = False) -> Path:
        """
        Автоматически сохраняет данные с уникальным именем.
        
        Args:
            prefix: Префикс имени файла
            directory: Директория для сохранения (по умолчанию ./output)
            force: Сохранять даже если данные не являются SVG
        
        Returns:
            Path сохранённого файла
        """
        if directory is None:
            directory = Path.cwd() / "output"
        else:
            directory = Path(directory)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self._is_valid_svg:
            hash_part = self._metadata.get('hash', hashlib.md5(self._data).hexdigest()[:8])
            filename = f"{prefix}_{timestamp}_{hash_part}.svg"
        else:
            # Для не-SVG данных используем .bin расширение
            filename = f"{prefix}_{timestamp}.bin"
        
        return self.save(directory / filename, force=force, as_svg=self._is_valid_svg)
    
    # ==================== Извлечение метаданных ====================
    
    def _extract_dimensions_from_svg(self, svg_str: str) -> Tuple[float, float]:
        """
        Извлекает размеры из SVG, даже если они нестандартные.
        
        Returns:
            Кортеж (ширина, высота)
        """
        width = 0.0
        height = 0.0
        
        try:
            # Пробуем распарсить XML
            root = ET.fromstring(svg_str)
            
            # 1. Пробуем получить из атрибутов width/height
            if 'width' in root.attrib:
                w_str = root.attrib['width']
                # Убираем единицы измерения (px, pt, em и т.д.)
                w_str = re.sub(r'[^0-9.]', '', w_str)
                if w_str:
                    width = float(w_str)
            
            if 'height' in root.attrib:
                h_str = root.attrib['height']
                h_str = re.sub(r'[^0-9.]', '', h_str)
                if h_str:
                    height = float(h_str)
            
            # 2. Если нет width/height, пробуем viewBox
            if (width == 0 or height == 0) and 'viewBox' in root.attrib:
                viewbox = root.attrib['viewBox'].split()
                if len(viewbox) == 4:
                    # viewBox = "min-x min-y width height"
                    width = float(viewbox[2])
                    height = float(viewbox[3])
            
            # 3. Если всё ещё нет, пробуем вычислить по содержимому
            if width == 0 or height == 0:
                # Ищем все элементы с координатами
                max_x = 0
                max_y = 0
                
                for elem in root.iter():
                    # Проверяем атрибуты x, y, width, height
                    if 'x' in elem.attrib:
                        try:
                            x = float(re.sub(r'[^0-9.-]', '', elem.attrib['x']))
                            max_x = max(max_x, x)
                        except:
                            pass
                    
                    if 'y' in elem.attrib:
                        try:
                            y = float(re.sub(r'[^0-9.-]', '', elem.attrib['y']))
                            max_y = max(max_y, y)
                        except:
                            pass
                    
                    if 'width' in elem.attrib:
                        try:
                            w = float(re.sub(r'[^0-9.]', '', elem.attrib['width']))
                            if 'x' in elem.attrib:
                                x = float(re.sub(r'[^0-9.-]', '', elem.attrib['x']))
                                max_x = max(max_x, x + w)
                        except:
                            pass
                    
                    if 'height' in elem.attrib:
                        try:
                            h = float(re.sub(r'[^0-9.]', '', elem.attrib['height']))
                            if 'y' in elem.attrib:
                                y = float(re.sub(r'[^0-9.-]', '', elem.attrib['y']))
                                max_y = max(max_y, y + h)
                        except:
                            pass
                
                if width == 0 and max_x > 0:
                    width = max_x
                if height == 0 and max_y > 0:
                    height = max_y
            
        except Exception as e:
            _logger.warning(f"Не удалось извлечь размеры из SVG: {e}")
        
        return width, height
    
    def _extract_metadata(self):
        """Извлекает метаданные из SVG"""
        if not self._data or not self._is_valid_svg:
            return
        
        try:
            svg_str = self._data.decode('utf-8', errors='ignore')
            
            # Извлекаем размеры
            self._width, self._height = self._extract_dimensions_from_svg(svg_str)
            self._metadata['width'] = self._width
            self._metadata['height'] = self._height
            
            # Извлекаем размеры из viewBox
            viewbox_match = re.search(r'viewBox="([^"]+)"', svg_str)
            if viewbox_match:
                parts = viewbox_match.group(1).split()
                if len(parts) == 4:
                    self._metadata['viewbox'] = {
                        'min_x': float(parts[0]),
                        'min_y': float(parts[1]),
                        'width': float(parts[2]),
                        'height': float(parts[3])
                    }
            
            # Считаем количество элементов
            self._metadata['element_count'] = len(re.findall(r'<[a-zA-Z]', svg_str))
            
            # Проверяем наличие кириллицы
            cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]', re.UNICODE)
            self._metadata['has_cyrillic'] = bool(cyrillic_pattern.search(svg_str))
            
            # Хеш содержимого
            self._metadata['hash'] = hashlib.md5(self._data).hexdigest()[:8]
            
        except Exception as e:
            _logger.warning(f"Не удалось извлечь метаданные из SVG: {e}")
    
    # ==================== Подготовка SVG для конвертации ====================
    
    def _ensure_cyrillic_support(self, svg_str: str, font_family: str = 'Arial') -> str:
        """
        Добавляет поддержку кириллицы в SVG.
        
        Args:
            svg_str: Исходный SVG в виде строки
            font_family: Предпочтительный шрифт для текста
        
        Returns:
            Модифицированный SVG с поддержкой кириллицы
        """
        # Добавляем объявление кодировки если нет
        if '<?xml' not in svg_str:
            svg_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_str
        
        # Проверяем, есть ли уже стили
        if '<style' not in svg_str:
            # Создаём CSS с поддержкой кириллицы
            fonts = ', '.join(f'"{f}"' for f in [font_family] + self.CYRILLIC_FONTS)
            style = f'''
    <style type="text/css">
        /* Поддержка кириллицы */
        text {{
            font-family: {fonts};
        }}
        /* Для совместимости с разными браузерами */
        * {{
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
    </style>
'''
            # Вставляем стиль после открывающего тега svg
            svg_str = svg_str.replace('<svg', '<svg>\n' + style, 1)
        
        return svg_str
    
    def _fix_cyrillic_text(self, svg_str: str) -> str:
        """
        Исправляет проблемы с кириллицей в текстовых элементах.
        Экранирует специальные символы и проверяет кодировку.
        
        Args:
            svg_str: Исходный SVG в виде строки
        
        Returns:
            SVG с исправленным текстом
        """
        def replace_text(match):
            full_tag = match.group(0)
            text_content = match.group(1)
            
            # Проверяем наличие кириллицы
            if any(ord(c) > 127 for c in text_content):
                # Экранируем специальные HTML-символы
                safe_text = html.escape(text_content)
                # Заменяем текст в теге
                return full_tag.replace(text_content, safe_text)
            
            return full_tag
        
        # Применяем замену ко всем текстовым элементам
        pattern = r'>([^<]+)</text>'
        svg_str = re.sub(pattern, replace_text, svg_str)
        
        return svg_str
    
    def prepare_for_conversion(self, font_family: str = 'Arial') -> str:
        """
        Подготавливает SVG для конвертации в PNG.
        Применяет все необходимые исправления для поддержки кириллицы.
        
        Returns:
            Подготовленный SVG в виде строки
            
        Raises:
            SVGValidationError: Если данные не являются SVG
        """
        if not self._is_valid_svg:
            raise SVGValidationError(
                "Невозможно конвертировать в PNG: данные не являются SVG"
            )
        
        svg_str = self.to_str()
        
        # Применяем все исправления
        svg_str = self._ensure_cyrillic_support(svg_str, font_family)
        svg_str = self._fix_cyrillic_text(svg_str)
        
        return svg_str
    
    # ==================== Конвертация в PNG ====================
    
    def to_png_wand(self, output_path: Union[str, Path], 
                    font_family: str = 'Arial',
                    scale: float = 1.0,
                    dpi: int = 300) -> Path:
        """
        Конвертирует SVG в PNG используя Wand (ImageMagick).
        Лучший вариант для Windows!
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста
            scale: Масштаб
            dpi: Разрешение
        
        Returns:
            Path сохранённого PNG
        """
        if not WAND_AVAILABLE:
            raise GraphicsError(
                "Wand не установлен. Установите:\n"
                "1. ImageMagick: https://imagemagick.org/script/download.php#windows\n"
                "2. pip install Wand"
            )
        
        # Подготавливаем SVG
        svg_str = self.prepare_for_conversion(font_family)
        
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix('.png')
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(svg_str)
            tmp_path = tmp.name
        
        try:
            with WandImage(filename=tmp_path, resolution=dpi) as img:
                if scale != 1.0:
                    img.resize(int(img.width * scale), int(img.height * scale))
                img.save(filename=str(output_path))
            
            _logger.info(f"SVG сконвертирован в PNG (Wand): {output_path}")
            
        except Exception as e:
            raise GraphicsError(f"Ошибка Wand: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        return output_path
    
    def to_png_cairo(self, output_path: Union[str, Path], 
                     font_family: str = 'Arial',
                     scale: float = 1.0,
                     dpi: int = 300) -> Path:
        """
        Конвертирует SVG в PNG используя CairoSVG.
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста
            scale: Масштаб
            dpi: Разрешение
        
        Returns:
            Path сохранённого PNG
        """
        if not CAIRO_AVAILABLE:
            raise GraphicsError(
                "CairoSVG не установлен. Установите: pip install cairosvg\n"
                "Также требуется системная библиотека Cairo."
            )
        
        # Подготавливаем SVG
        svg_str = self.prepare_for_conversion(font_family)
        
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix('.png')
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            cairosvg.svg2png(
                bytestring=svg_str.encode('utf-8'),
                write_to=str(output_path),
                scale=scale,
                dpi=dpi
            )
            _logger.info(f"SVG сконвертирован в PNG (Cairo): {output_path}")
        except Exception as e:
            raise GraphicsError(f"Ошибка CairoSVG: {e}")
        
        return output_path
    
    def to_png_inkscape(self, output_path: Union[str, Path],
                        font_family: str = 'Arial',
                        dpi: int = 300) -> Path:
        """
        Конвертирует SVG в PNG используя Inkscape.
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста
            dpi: Разрешение
        
        Returns:
            Path сохранённого PNG
        """
        if not INKSCAPE_AVAILABLE:
            raise GraphicsError(
                "Inkscape не найден. Скачайте с https://inkscape.org/"
            )
        
        # Подготавливаем SVG
        svg_str = self.prepare_for_conversion(font_family)
        
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix('.png')
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(svg_str)
            tmp_path = tmp.name
        
        try:
            inkscape_path = shutil.which('inkscape') or shutil.which('inkscape.com')
            cmd = [
                inkscape_path,
                tmp_path,
                f'--export-filename={output_path}',
                f'--export-dpi={dpi}',
                '--export-background=white'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise GraphicsError(f"Ошибка Inkscape: {result.stderr}")
            
            _logger.info(f"SVG сконвертирован в PNG (Inkscape): {output_path}")
            
        except Exception as e:
            raise GraphicsError(f"Ошибка Inkscape: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        return output_path
    
    def to_png_weasyprint(self, output_path: Union[str, Path],
                          font_family: str = 'Arial',
                          scale: float = 1.0) -> Path:
        """
        Конвертирует SVG в PNG используя WeasyPrint.
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста
            scale: Масштаб
        
        Returns:
            Path сохранённого PNG
        """
        if not WEASYPRINT_AVAILABLE:
            raise GraphicsError(
                "WeasyPrint не установлен. Установите: pip install weasyprint"
            )
        
        # Подготавливаем SVG
        svg_str = self.prepare_for_conversion(font_family)
        
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix('.png')
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Временный HTML файл с SVG
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="margin: 0; padding: 0;">
            {svg_str}
        </body>
        </html>
        """
        
        temp_html = Path(tempfile.gettempdir()) / f"temp_{self._metadata.get('hash', 'unknown')}.html"
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        try:
            HTML(str(temp_html)).write_png(str(output_path), scale=scale)
            _logger.info(f"SVG сконвертирован в PNG (WeasyPrint): {output_path}")
        except Exception as e:
            raise GraphicsError(f"Ошибка WeasyPrint: {e}")
        finally:
            if temp_html.exists():
                temp_html.unlink()
        
        return output_path
    
    def to_png_matplotlib(self, output_path: Union[str, Path], 
                          font_family: str = 'Arial',
                          scale: float = 1.0,
                          dpi: int = 300) -> Path:
        """
        Конвертирует SVG в PNG используя matplotlib.
        Создаёт информационную заглушку, так как matplotlib не умеет конвертировать SVG.
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста
            scale: Масштаб
            dpi: Разрешение
        
        Returns:
            Path сохранённого PNG
        """
        if not MATPLOTLIB_AVAILABLE:
            raise GraphicsError(
                "Matplotlib не установлен. Установите: pip install matplotlib"
            )
        
        if not PIL_AVAILABLE:
            raise GraphicsError(
                "Pillow не установлен. Установите: pip install Pillow"
            )
        
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix('.png')
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Определяем размеры фигуры
        width_inches = self._width / dpi if self._width > 0 else 10
        height_inches = self._height / dpi if self._height > 0 else 10
        
        # Применяем масштаб
        width_inches *= scale
        height_inches *= scale
        
        # Создаём фигуру
        fig, ax = plt.subplots(figsize=(width_inches, height_inches), dpi=dpi)
        ax.axis('off')
        
        # Добавляем информацию о размерах
        ax.text(0.5, 0.5, 
                f'SVG размером {self._width:.0f}x{self._height:.0f}px',
                ha='center', va='center', transform=ax.transAxes, 
                fontsize=12, fontfamily=font_family)
        
        # Добавляем рамку
        rect = Rectangle((0.1, 0.1), 0.8, 0.8, fill=None, edgecolor='blue', linewidth=2)
        ax.add_patch(rect)
        
        # Сохраняем
        plt.savefig(output_path, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0)
        plt.close()
        
        _logger.info(f"SVG сконвертирован в PNG (matplotlib, информационная заглушка): {output_path}")
        return output_path
    
    def to_png(self, output_path: Union[str, Path], 
               font_family: str = 'Arial',
               scale: float = 1.0,
               dpi: int = 300,
               method: Literal['auto', 'wand', 'cairo', 'inkscape', 'weasyprint', 'matplotlib'] = 'auto',
               max_size: Optional[Tuple[int, int]] = None,
               fit_to_size: bool = True,
               debug_save_svg: bool = False) -> Path:
        """
        Конвертирует SVG в PNG с поддержкой кириллицы.
        Автоматически выбирает доступный метод конвертации.
        
        Args:
            output_path: Путь для сохранения PNG
            font_family: Шрифт для текста (по умолчанию Arial)
            scale: Масштаб изображения
            dpi: Разрешение (точек на дюйм)
            method: Метод конвертации 
                   ('auto', 'wand', 'cairo', 'inkscape', 'weasyprint', 'matplotlib')
            max_size: Максимальный размер (ширина, высота) в пикселях
            fit_to_size: Подгонять размер, если превышает max_size
            debug_save_svg: Сохранить промежуточный SVG для отладки
        
        Returns:
            Path сохранённого PNG
            
        Raises:
            SVGValidationError: Если данные не являются SVG
            GraphicsError: Если нет доступных методов конвертации
        """
        # Проверяем, что это действительно SVG
        if not self._is_valid_svg:
            preview = self._data[:200].decode('utf-8', errors='ignore')
            raise SVGValidationError(
                f"Невозможно конвертировать в PNG: данные не являются SVG.\n"
                f"Первые 200 байт: {preview}"
            )
        
        # Подготавливаем SVG
        svg_str = self.prepare_for_conversion(font_family)
        
        # Сохраняем промежуточный SVG для отладки если нужно
        if debug_save_svg:
            debug_path = Path(output_path).with_suffix('.debug.svg')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(svg_str)
            _logger.info(f"Промежуточный SVG сохранён: {debug_path}")
        
        # Проверяем размеры и при необходимости корректируем масштаб
        if max_size and fit_to_size and self._width > 0 and self._height > 0:
            max_w, max_h = max_size
            scale_w = max_w / self._width if self._width > max_w else 1
            scale_h = max_h / self._height if self._height > max_h else 1
            scale_factor = min(scale_w, scale_h)
            
            if scale_factor < 1:
                scale *= scale_factor
                _logger.debug(f"Размер SVG {self._width}x{self._height} превышает лимит, применяем масштаб {scale_factor}")
        
        # Выбор метода
        if method == 'auto':
            # Приоритет: wand (ImageMagick) -> cairo -> inkscape -> weasyprint -> matplotlib
            if WAND_AVAILABLE:
                method = 'wand'
                _logger.debug("Автовыбор: Wand (ImageMagick)")
            elif CAIRO_AVAILABLE:
                method = 'cairo'
                _logger.debug("Автовыбор: CairoSVG")
            elif INKSCAPE_AVAILABLE:
                method = 'inkscape'
                _logger.debug("Автовыбор: Inkscape")
            elif WEASYPRINT_AVAILABLE:
                method = 'weasyprint'
                _logger.debug("Автовыбор: WeasyPrint")
            elif MATPLOTLIB_AVAILABLE:
                method = 'matplotlib'
                _logger.debug("Автовыбор: matplotlib (информационная заглушка)")
            else:
                raise GraphicsError(
                    "Нет доступных методов конвертации. Установите один из:\n"
                    "- Wand (ImageMagick): pip install Wand\n"
                    "- CairoSVG: pip install cairosvg\n"
                    "- Inkscape: скачайте с inkscape.org\n"
                    "- WeasyPrint: pip install weasyprint"
                )
        
        # Вызов соответствующего метода
        if method == 'wand':
            return self.to_png_wand(output_path, font_family, scale, dpi)
        elif method == 'cairo':
            return self.to_png_cairo(output_path, font_family, scale, dpi)
        elif method == 'inkscape':
            return self.to_png_inkscape(output_path, font_family, dpi)
        elif method == 'weasyprint':
            return self.to_png_weasyprint(output_path, font_family, scale)
        elif method == 'matplotlib':
            return self.to_png_matplotlib(output_path, font_family, scale, dpi)
        else:
            raise GraphicsError(f"Неизвестный метод конвертации: {method}")
    
    # ==================== Базовые методы ====================
    
    def to_bytes(self) -> bytes:
        """Возвращает данные как байты"""
        if not self._data:
            raise GraphicsError("Нет данных")
        return self._data
    
    def to_str(self) -> str:
        """Возвращает данные как строку"""
        if not self._data:
            raise GraphicsError("Нет данных")
        return self._data.decode('utf-8', errors='replace')
    
    def to_base64(self) -> str:
        """Возвращает SVG в формате Base64"""
        if not self._data:
            raise GraphicsError("Нет данных")
        return base64.b64encode(self._data).decode('ascii')
    
    def to_html(self, width: Optional[int] = None, height: Optional[int] = None) -> str:
        """
        Возвращает HTML-код для встраивания SVG.
        
        Args:
            width: Ширина в пикселях
            height: Высота в пикселях
        """
        svg_str = self.to_str()
        
        # Добавляем атрибуты ширины/высоты если нужно
        if width or height:
            # Удаляем существующие атрибуты ширины/высоты
            svg_str = re.sub(r'\s+width="[^"]*"', '', svg_str)
            svg_str = re.sub(r'\s+height="[^"]*"', '', svg_str)
            
            # Вставляем новые
            attrs = []
            if width:
                attrs.append(f'width="{width}"')
            if height:
                attrs.append(f'height="{height}"')
            
            svg_str = svg_str.replace('<svg', f'<svg {" ".join(attrs)}', 1)
        
        return svg_str
    
    def is_svg(self) -> bool:
        """Проверяет, являются ли данные SVG"""
        return self._is_valid_svg
    
    # ==================== Отображение ====================
    
    def display(self, width: Optional[int] = None, height: Optional[int] = None):
        """
        Отображает SVG в Jupyter notebook.
        
        Args:
            width: Ширина в пикселях
            height: Высота в пикселях
        """
        if not IPYTHON_AVAILABLE:
            _logger.warning("IPython не доступен, невозможно отобразить SVG")
            return
        
        svg_html = self.to_html(width, height)
        display(SVG(svg_html))
    
    # ==================== Извлечение информации ====================
    
    def extract_texts(self) -> List[str]:
        """
        Извлекает все текстовые элементы из SVG.
        
        Returns:
            Список текстовых строк
        """
        svg_str = self.to_str()
        texts = re.findall(r'>([^<]+)</text>', svg_str)
        return [t.strip() for t in texts if t.strip()]
    
    def extract_node_ids(self) -> List[int]:
        """
        Извлекает ID узлов из атрибутов next_node_id.
        
        Returns:
            Список ID узлов
        """
        svg_str = self.to_str()
        ids = re.findall(r'next_node_id="(\d+)"', svg_str)
        return [int(id) for id in ids]
    
    # ==================== Свойства ====================
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Возвращает метаданные"""
        return self._metadata.copy()
    
    @property
    def size(self) -> Tuple[int, int]:
        """Возвращает размеры изображения (ширина, высота)"""
        return (int(self._width), int(self._height))
    
    @property
    def width(self) -> float:
        """Возвращает ширину SVG"""
        return self._width
    
    @property
    def height(self) -> float:
        """Возвращает высоту SVG"""
        return self._height
    
    @property
    def has_cyrillic(self) -> bool:
        """Проверяет, содержит ли SVG кириллические символы"""
        return self._metadata.get('has_cyrillic', False)
    
    # ==================== Магические методы ====================
    
    def __len__(self) -> int:
        return len(self._data) if self._data else 0
    
    def __repr__(self) -> str:
        if not self._data:
            return "SVGHandler(empty)"
        
        if not self._is_valid_svg:
            preview = self._data[:50].decode('utf-8', errors='ignore')
            return f"SVGHandler(not SVG, size={len(self._data)} bytes, preview='{preview}...')"
        
        size = len(self._data)
        meta = self._metadata
        cyrillic = "✓" if meta.get('has_cyrillic', False) else "✗"
        return (f"SVGHandler(size={size} bytes, "
                f"elements={meta.get('element_count', 0)}, "
                f"cyrillic={cyrillic}, "
                f"size={self._width:.0f}x{self._height:.0f})")


class ImageHandler:
    """
    Универсальный обработчик изображений.
    Поддерживает различные форматы.
    """
    
    def __init__(self, data: Optional[Union[bytes, Path]] = None):
        self._data = data
        self._format = None
        self._metadata = {}
        _get_logger()
        if data is not None:
            self._detect_format()
    
    def _detect_format(self):
        """Определяет формат изображения по первым байтам"""
        if not self._data or len(self._data) < 12:
            return
        
        # Проверяем SVG
        if self._data[:4] == b'<svg' or b'<svg' in self._data[:100]:
            self._format = 'svg'
            return
        
        # PNG
        if self._data[:8] == b'\x89PNG\r\n\x1a\n':
            self._format = 'png'
            return
        
        # JPEG
        if self._data[:2] == b'\xff\xd8':
            self._format = 'jpeg'
            return
        
        # GIF
        if self._data[:6] in (b'GIF87a', b'GIF89a'):
            self._format = 'gif'
            return
    
    def save(self, path: Union[str, Path]) -> Path:
        """Сохраняет изображение в файл"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            f.write(self._data)
        
        _logger.info(f"Изображение сохранено в {path}")
        return path
    
    @property
    def format(self) -> Optional[str]:
        return self._format


# ==================== Функции для быстрого использования ====================

def save_svg(data: Union[bytes, str], path: Union[str, Path], force: bool = False) -> Path:
    """Быстрое сохранение данных в файл"""
    handler = SVGHandler(data, validate=not force)
    return handler.save(path, force=force)


def load_svg(path: Union[str, Path], validate: bool = True, strict: bool = False) -> SVGHandler:
    """Быстрая загрузка данных из файла"""
    return SVGHandler(path, validate=validate, strict=strict)


def is_svg(data: Union[bytes, str, Path]) -> bool:
    """Быстрая проверка, являются ли данные SVG"""
    try:
        handler = SVGHandler(data, validate=False)
        return handler.is_svg()
    except:
        return False


def svg_to_png(data: Union[bytes, str, SVGHandler, Path], 
               output_path: Union[str, Path],
               font_family: str = 'Arial',
               scale: float = 1.0,
               dpi: int = 300,
               method: str = 'auto',
               max_size: Optional[Tuple[int, int]] = None,
               strict: bool = False,
               debug_save_svg: bool = False) -> Path:
    """
    Быстрая конвертация SVG в PNG с поддержкой кириллицы.
    
    Args:
        data: Данные SVG (байты, строка, SVGHandler или путь к файлу)
        output_path: Путь для сохранения PNG
        font_family: Шрифт для текста
        scale: Масштаб
        dpi: Разрешение
        method: Метод конвертации ('auto', 'wand', 'cairo', 'inkscape', 'weasyprint', 'matplotlib')
        max_size: Максимальный размер (ширина, высота) в пикселях
        strict: Строгая валидация SVG
        debug_save_svg: Сохранить промежуточный SVG для отладки
    
    Returns:
        Path сохранённого PNG
    """
    if isinstance(data, SVGHandler):
        handler = data
    elif isinstance(data, (str, Path)) and Path(data).exists():
        # Если передан путь к файлу
        handler = SVGHandler(data, validate=True, strict=strict)
    else:
        # Если переданы байты или строка
        handler = SVGHandler(data, validate=True, strict=strict)
    
    return handler.to_png(
        output_path, 
        font_family=font_family, 
        scale=scale, 
        dpi=dpi, 
        method=method, 
        max_size=max_size,
        debug_save_svg=debug_save_svg
    )


# ==================== Экспорт ====================

__all__ = [
    'SVGHandler',
    'ImageHandler',
    'save_svg',
    'load_svg',
    'is_svg',
    'svg_to_png',
    'IPYTHON_AVAILABLE',
    'CAIRO_AVAILABLE',
    'REPORTLAB_AVAILABLE',
    'RENDER_AVAILABLE',
    'PIL_AVAILABLE',
    'WAND_AVAILABLE',
    'MATPLOTLIB_AVAILABLE',
    'WEASYPRINT_AVAILABLE',
    'INKSCAPE_AVAILABLE'
]